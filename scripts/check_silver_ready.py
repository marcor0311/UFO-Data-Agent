"""Executable acceptance gate for consuming the current Silver snapshot in Gold."""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

if __package__:
    from . import build_silver as silver
    from .pipeline_context import write_text
    from .releases import data_root, default_silver
else:
    import build_silver as silver
    from pipeline_context import write_text
    from releases import data_root, default_silver


def readiness(source, database, manifest, policy):
    verification=silver.verify(source,database,manifest,policy)
    with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as conn:
        cursor=conn.execute('''SELECT source_name,COUNT(*) AS reports,
            SUM(usable_for_calendar) AS calendar_reports,
            SUM(usable_for_month_analysis) AS month_analysis_reports,
            SUM(usable_for_day_analysis) AS day_analysis_reports,
            SUM(day_placeholder_risk) AS day_placeholder_risk_reports,
            SUM(usable_for_map) AS map_reports,
            SUM(usable_for_country) AS country_reports,
            SUM(usable_for_nuclear_proximity) AS proximity_reports,
            SUM(uses_external_evidence) AS external_evidence_reports,
            SUM(coordinate_basis='original_catalog_place' AND usable_for_map) AS external_map_reports,
            SUM(country_basis='original_catalog' AND usable_for_country) AS external_country_reports,
            SUM(time_basis IS 'original_catalog') AS external_time_reports
            FROM sighting_analytical GROUP BY source_name ORDER BY source_name''')
        names=[column[0] for column in cursor.description]
        coverage=[dict(zip(names,row)) for row in cursor]
        placeholders=[dict(zip(('source','pattern','value','observed','baseline','ratio'),row)) for row in conn.execute('''
            SELECT d.name,p.pattern,p.value,p.observed,p.baseline,p.ratio FROM temporal_placeholder_profile p
            JOIN source_database d ON d.id=p.source_db_id WHERE p.flagged=1 ORDER BY d.name,p.pattern,p.value''')]
        geography=[dict(zip(('country_check','coordinate_check','reports'),row)) for row in conn.execute('''
            SELECT country_check,coordinate_check,COUNT(*) FROM source_geography_evidence
            GROUP BY 1,2 ORDER BY 1,2''')]
        pending=conn.execute("SELECT COUNT(*) FROM duplicate_resolution WHERE decision='needs_review'").fetchone()[0]
        issues=[dict(zip(('rule','action','records'),row)) for row in conn.execute('''
            SELECT rule_id,action,SUM(affected_records) FROM quality_summary
            GROUP BY rule_id,action ORDER BY rule_id,action''')]
    return {'ready_for_gold':verification['passed'],
        'silver_sha256':silver.digest(database),'bronze_sha256':manifest['sha256'],
        'policy_version':policy['version'],'verification':verification,
        'coverage_by_source':coverage,'pending_candidate_pairs':pending,
        'flagged_date_placeholders':placeholders,'source_geography_decisions':geography,
        'quality_metrics':issues,
        'consumer_contract':{
            'grain':'one report per sighting_analytical row; count reports, not events',
            'calendar':'sighting_reports_for_time_analysis for years; calendar_precision is the finest safe precision',
            'month_analysis':'sighting_analytical WHERE usable_for_month_analysis=1',
            'day_analysis':'sighting_analytical WHERE usable_for_day_analysis=1; day_placeholder_risk marks source placeholder excess',
            'map':'sighting_reports_for_map; respect coordinate_basis',
            'country':'sighting_analytical WHERE usable_for_country=1; respect country_basis',
            'proximity':'sighting_analytical WHERE usable_for_nuclear_proximity=1',
            'external_evidence':'uses_external_evidence=1 marks values from the pinned UFO-search catalogue that Bronze lacks; filter uses_external_evidence=0 for a Bronze-only analysis',
            'deduplication':'event_membership preserves every report; representatives do not prove distinct real events',
            'uncertainty':'unresolved evidence is retained; quarantine is not a source correction',
            'refresh':'rebuild and pass this gate after every new Bronze snapshot or Silver policy change'},
        'interpretation':'Acceptance of the implemented Silver contract, aligned with the medallion pattern; not a Databricks certification or proof that every source value is complete or true.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    data=data_root()
    parser.add_argument('--source',type=Path,default=data/'bronze/ufo.db')
    parser.add_argument('--database',type=Path,default=None,
                        help='Silver a revisar (por defecto: la versión aprobada del catálogo)')
    parser.add_argument('--output',type=Path,default=data/'silver/ufo.readiness.json')
    args=parser.parse_args()
    args.database=args.database or default_silver(data)
    protected={args.source.resolve(),args.database.resolve(),args.database.with_suffix('.validation.json').resolve(),
               silver.POLICY.resolve(),silver.MANIFEST.resolve()}
    if args.output.resolve() in protected:
        parser.error('El informe no puede sustituir una base, política o validación')
    try:
        result=readiness(args.source,args.database,json.loads(silver.MANIFEST.read_text(encoding='utf-8')),
                         json.loads(silver.POLICY.read_text(encoding='utf-8')))
        write_text(args.output,json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    except (OSError,ValueError,sqlite3.Error) as exc:
        print(f'NO APTA PARA GOLD: {exc}',file=sys.stderr)
        return 1
    print(f"Silver apta para Gold: {result['verification']['checks']} controles; informe {args.output}")
    return 0


if __name__=='__main__':raise SystemExit(main())
