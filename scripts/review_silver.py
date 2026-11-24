"""Read-only, reproducible triage of unresolved Silver evidence (no adjudication)."""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

try:
    from . import build_silver as silver
    from .pipeline_context import write_text
    from .releases import data_root, default_silver
except ImportError:
    import build_silver as silver
    from pipeline_context import write_text
    from releases import data_root, default_silver


QUERIES = {
    'temporal_recoveries': """SELECT d.name AS source,COUNT(*) AS evidence_reports,
        SUM(b.date_event IS NULL AND s.date_event IS NOT NULL) AS recovered_points,
        SUM(length(b.date_event)=4 AND length(s.date_event)=7) AS refined_year_to_month,
        SUM(b.date_event IS NOT NULL AND s.date_event IS NOT NULL
            AND length(s.date_event)<length(b.date_event)) AS removed_excess_precision,
        SUM(e.interpretation IN ('range','decade')) AS intervals
        FROM temporal_evidence e JOIN sighting s ON s.id=e.sighting_id
        JOIN bronze.sighting b ON b.id=s.id JOIN source_database d ON d.id=s.source_db_id
        GROUP BY d.name ORDER BY d.name""",
    'temporal_evidence': """SELECT d.name AS source,e.interpretation,e.applied,
        COUNT(*) AS reports FROM temporal_evidence e JOIN sighting s ON s.id=e.sighting_id
        JOIN source_database d ON d.id=s.source_db_id
        GROUP BY d.name,e.interpretation,e.applied ORDER BY reports DESC,source,e.interpretation,e.applied""",
    'analytical_coverage': """SELECT source_name,COUNT(*) AS reports,
        SUM(is_canonical) AS canonical_representatives,SUM(usable_for_map) AS map_reports,
        SUM(usable_for_calendar) AS calendar_reports,SUM(usable_for_country) AS country_reports,
        SUM(usable_for_nuclear_proximity) AS proximity_reports
        FROM sighting_analytical GROUP BY source_name ORDER BY source_name""",
    'country_conflicts_by_geocoder': """SELECT b.geocode_src,COUNT(*) AS locations,
        SUM((SELECT COUNT(*) FROM sighting s WHERE s.location_id=b.id)) AS reports
        FROM bronze.location b JOIN location l ON l.id=b.id
        WHERE l.country_status='conflict' GROUP BY b.geocode_src ORDER BY locations DESC""",
    'unrecognized_countries': """SELECT table_name,raw_value,COUNT(*) AS records
        FROM quality_issue WHERE rule_id='country_unrecognized'
        GROUP BY table_name,raw_value ORDER BY records DESC,table_name,raw_value""",
    'date_causes': """SELECT d.name AS source,
        CASE WHEN e.interpretation='conflict' THEN 'representation_conflict'
        WHEN d.name='UFOCAT' AND b.date_event='19' THEN 'ufocat_short_19'
        WHEN d.name='UFOCAT' AND b.date_event LIKE '0019-%' THEN 'ufocat_0019_sentinel'
        WHEN length(b.date_event) BETWEEN 1 AND 3 AND b.date_event NOT GLOB '*[^0-9]*'
          THEN 'short_year_ambiguous'
        ELSE 'calendar_or_format_or_future' END AS cause,
        COUNT(*) AS reports FROM sighting s JOIN bronze.sighting b ON b.id=s.id
        JOIN source_database d ON d.id=s.source_db_id LEFT JOIN temporal_evidence e ON e.sighting_id=s.id WHERE s.date_status IN ('invalid','review')
        GROUP BY d.name,cause ORDER BY reports DESC,source,cause""",
    'dates_by_evidence': """SELECT d.name AS source,q.rule_id,q.column_name,
        q.raw_value,b.date_event_raw,COUNT(*) AS reports,MIN(b.id) AS example_id
        FROM quality_issue q JOIN bronze.sighting b ON b.id=CAST(q.record_id AS INTEGER)
        JOIN source_database d ON d.id=b.source_db_id
        WHERE q.table_name='sighting' AND q.rule_id IN ('date_invalid','date_suspect')
        GROUP BY d.name,q.rule_id,q.column_name,q.raw_value,b.date_event_raw
        ORDER BY reports DESC,source,q.column_name,q.raw_value,b.date_event_raw""",
    'source_datetime_precision': """SELECT d.name AS source,s.datetime_precision,
        COUNT(*) AS reports FROM sighting s JOIN source_database d ON d.id=s.source_db_id
        GROUP BY d.name,s.datetime_precision ORDER BY d.name,s.datetime_precision""",
    'candidate_methods': """SELECT c.match_method,a.name AS source_a,b.name AS source_b,
        r.decision,COUNT(*) AS pairs,MIN(c.similarity_score) AS min_score,
        MAX(c.similarity_score) AS max_score FROM duplicate_candidate c
        JOIN duplicate_resolution r ON r.candidate_id=c.id
        JOIN sighting sa ON sa.id=c.sighting_id_a JOIN sighting sb ON sb.id=c.sighting_id_b
        JOIN source_database a ON a.id=sa.source_db_id JOIN source_database b ON b.id=sb.source_db_id
        GROUP BY c.match_method,a.name,b.name,r.decision ORDER BY pairs DESC""",
    'quarantined_reports_in_map': """SELECT COUNT(*) AS reports FROM quality_issue q
        JOIN sighting_for_map m ON m.id=CAST(q.record_id AS INTEGER)
        WHERE q.table_name='sighting' AND q.rule_id='coordinate_country_conflict'""",
    'geographic_dependencies': """SELECT column_name,COUNT(*) AS records FROM quality_issue
        WHERE rule_id='geographic_dependency' GROUP BY column_name ORDER BY column_name""",
    'coordinate_quarantine': """SELECT table_name,COUNT(*) AS records FROM quality_issue
        WHERE rule_id='coordinate_country_conflict' GROUP BY table_name ORDER BY table_name""",
    'calendar_precision': """SELECT source_name,calendar_precision,day_placeholder_risk,
        month_placeholder_risk,COUNT(*) AS reports FROM sighting_analytical
        GROUP BY 1,2,3,4 ORDER BY 1,2,3,4""",
    'date_placeholder_profile': """SELECT d.name AS source,p.pattern,p.value,p.observed,
        p.baseline,p.ratio,p.flagged FROM temporal_placeholder_profile p
        JOIN source_database d ON d.id=p.source_db_id ORDER BY d.name,p.pattern,p.value""",
    'unsupported_raw_dates': """SELECT d.name AS source,e.raw_value,COUNT(*) AS reports,
        MIN(e.sighting_id) AS example_id FROM temporal_evidence e
        JOIN sighting s ON s.id=e.sighting_id JOIN source_database d ON d.id=s.source_db_id
        WHERE e.interpretation='unsupported' GROUP BY 1,2 ORDER BY reports DESC,source,e.raw_value""",
    'source_geography_decisions': """SELECT country_check,coordinate_check,COUNT(*) AS reports,
        MIN(bronze_distance_km) AS min_distance_km,MAX(bronze_distance_km) AS max_distance_km,
        MIN(sighting_id) AS example_id FROM source_geography_evidence GROUP BY 1,2 ORDER BY 1,2""",
    'external_evidence': """SELECT source_name,coordinate_basis,country_basis,time_basis,
        COUNT(*) AS reports FROM sighting_analytical WHERE uses_external_evidence=1
        OR coordinate_basis!='bronze' OR country_basis NOT IN ('location')
        GROUP BY 1,2,3,4 ORDER BY reports DESC""",
}


def candidate_query(minimum=2, require_time=True, check_certainty=False):
    descriptors = ['color','duration_seconds','num_witnesses','sound','direction','hynek','vallee','event_type','weather','terrain']
    def count(alias):
        return '+'.join(f'meaningful({alias}.{name})' for name in descriptors)
    differences = ' OR '.join(f'norm(a.{name}) IS NOT norm(b.{name})' for name in descriptors)
    certainty = "WHEN a.date_certainty NOT IN ('source','coarsened') OR b.date_certainty NOT IN ('source','coarsened') THEN 'datetime_qualified'" if check_certainty else ''
    return f"""WITH classified AS (
        SELECT c.id,c.match_method,CASE
        WHEN a.id=b.id THEN 'same_record'
        WHEN r.decision='confirmed_exact' THEN 'confirmed_exact'
        WHEN a.sighting_datetime IS NULL OR b.sighting_datetime IS NULL
          OR a.datetime_precision NOT IN ('minute','second','fractional_second')
          OR b.datetime_precision NOT IN ('minute','second','fractional_second') THEN 'datetime_insufficient'
        {certainty}
        WHEN a.sighting_datetime!=b.sighting_datetime THEN 'datetime_differs'
        WHEN a.coordinate_status!='valid' OR b.coordinate_status!='valid' THEN 'coordinates_unusable'
        WHEN a.lat!=b.lat OR a.lng!=b.lng THEN 'coordinates_differ'
        WHEN NOT meaningful(a.standardized_shape) OR NOT meaningful(b.standardized_shape) THEN 'shape_insufficient'
        WHEN norm(a.standardized_shape)!=norm(b.standardized_shape) THEN 'shape_differs'
        WHEN {int(require_time)} AND (NOT meaningful(a.time_raw) OR NOT meaningful(b.time_raw)) THEN 'time_raw_insufficient'
        WHEN ({count('a')})<{int(minimum)} OR ({count('b')})<{int(minimum)} THEN 'descriptors_insufficient'
        WHEN {differences} THEN 'descriptors_differ'
        ELSE 'strict_match_unconfirmed' END AS first_blocker
        FROM duplicate_candidate c JOIN sighting a ON a.id=c.sighting_id_a
        JOIN sighting b ON b.id=c.sighting_id_b
        JOIN duplicate_resolution r ON r.candidate_id=c.id)
        SELECT first_blocker,match_method,COUNT(*) AS pairs,MIN(id) AS example_candidate_id
        FROM classified GROUP BY first_blocker,match_method ORDER BY pairs DESC,first_blocker,match_method"""


def review(source, database, policy):
    # Verify the controlling artifacts before interpreting derived quality states.
    # The full acceptance runs once per exact snapshot and invocation (shared
    # with check_silver_ready and the Gold gate through the run context).
    try:
        from . import check_silver_ready
        from .pipeline_context import silver_acceptance
    except ImportError:
        import check_silver_ready
        from pipeline_context import silver_acceptance
    manifest = json.loads(silver.MANIFEST.read_text(encoding='utf-8'))
    accepted = silver_acceptance(database, source, lambda s, b: check_silver_ready.readiness(b, s, manifest, policy))
    verification = accepted.get('verification') or {}
    if not accepted.get('ready_for_gold') or not verification.get('passed'):
        raise ValueError('Silver no validada')
    queries = dict(QUERIES)
    dedup = policy['quality']['deduplication']
    queries['candidate_first_blocker'] = candidate_query(dedup['minimum_additional_descriptors'],dedup.get('require_time_raw',True),bool(policy['quality'].get('analytical_contract')))
    with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True)) as conn:
        conn.execute('ATTACH DATABASE ? AS bronze',(source.resolve().as_uri()+'?mode=ro',))
        conn.execute('PRAGMA query_only=ON')
        conn.create_function('norm',1,lambda v: v.strip().casefold() if isinstance(v,str) else v,deterministic=True)
        conn.create_function('meaningful',1,lambda v: v is not None and str(v).strip().casefold() not in ('','unknown','other','n/a','?','unidentified'),deterministic=True)
        findings = {}
        for name,sql in queries.items():
            cursor=conn.execute(sql)
            columns=[col[0] for col in cursor.description]
            findings[name]={'sql':sql,'rows':[dict(zip(columns,row)) for row in cursor]}
        if findings['quarantined_reports_in_map']['rows'][0]['reports']:
            raise ValueError('Un informe en cuarentena aparece en el mapa')
        candidate_total=conn.execute('SELECT COUNT(*) FROM duplicate_candidate').fetchone()[0]
        classified=sum(row['pairs'] for row in findings['candidate_first_blocker']['rows'])
        if classified != candidate_total:
            raise ValueError('Clasificación incompleta de candidatos')
        return {'bronze_sha256':silver.digest(source),'silver_sha256':silver.digest(database),
            'script_sha256':silver.digest(Path(__file__)), 'lineage':json.loads(conn.execute('SELECT metadata FROM silver_run').fetchone()[0]),
            'candidate_pairs_classified':classified,
            'interpretation':'Primer impedimento según orden explícito del CASE; categorías excluyentes, no prueba de eventos distintos. No adjudica ni modifica registros.',
            'findings':findings}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    data=data_root()
    parser.add_argument('--source',type=Path,default=data/'bronze/ufo.db')
    parser.add_argument('--database',type=Path,default=None,
                        help='Silver a revisar (por defecto: la versión aprobada del catálogo)')
    parser.add_argument('--output',type=Path,default=data/'silver/ufo.review.json')
    args=parser.parse_args()
    args.database=args.database or default_silver(data)
    if args.output.resolve() in (args.source.resolve(),args.database.resolve()):
        parser.error('El informe no puede sustituir una base de datos')
    result=review(args.source,args.database,json.loads(silver.POLICY.read_text(encoding='utf-8')))
    write_text(args.output,json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(f"Revisión guardada: {args.output}; {result['candidate_pairs_classified']:,} pares clasificados.")


if __name__=='__main__':
    main()
