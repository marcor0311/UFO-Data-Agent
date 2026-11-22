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
else:
    import build_silver as silver


def readiness(source, database, manifest, policy):
    verification=silver.verify(source,database,manifest,policy)
    with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as conn:
        cursor=conn.execute('''SELECT source_name,COUNT(*) AS reports,
            SUM(usable_for_calendar) AS calendar_reports,SUM(usable_for_map) AS map_reports,
            SUM(usable_for_country) AS country_reports,
            SUM(usable_for_nuclear_proximity) AS proximity_reports
            FROM sighting_analytical GROUP BY source_name ORDER BY source_name''')
        names=[column[0] for column in cursor.description]
        coverage=[dict(zip(names,row)) for row in cursor]
        pending=conn.execute("SELECT COUNT(*) FROM duplicate_resolution WHERE decision='needs_review'").fetchone()[0]
        issues=[dict(zip(('rule','action','records'),row)) for row in conn.execute('''
            SELECT rule_id,action,SUM(affected_records) FROM quality_summary
            GROUP BY rule_id,action ORDER BY rule_id,action''')]
    return {'ready_for_gold':verification['passed'],
        'silver_sha256':silver.digest(database),'bronze_sha256':manifest['sha256'],
        'policy_version':policy['version'],'verification':verification,
        'coverage_by_source':coverage,'pending_candidate_pairs':pending,
        'quality_metrics':issues,
        'consumer_contract':{
            'grain':'one report per sighting_analytical row',
            'calendar':'sighting_reports_for_time_analysis; respect date_precision and date_certainty',
            'map':'sighting_reports_for_map; respect coordinate_basis',
            'country':'sighting_analytical WHERE usable_for_country=1; respect country_basis',
            'proximity':'sighting_analytical WHERE usable_for_nuclear_proximity=1',
            'deduplication':'event_membership preserves every report; representatives do not prove distinct real events',
            'uncertainty':'unresolved evidence is retained; quarantine is not a source correction',
            'refresh':'rebuild and pass this gate after every new Bronze snapshot or Silver policy change'},
        'interpretation':'Acceptance of the implemented Silver contract, aligned with the medallion pattern; not a Databricks certification or proof that every source value is complete or true.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=silver.ROOT/'data/bronze/ufo.db')
    parser.add_argument('--database',type=Path,default=silver.ROOT/'data/silver/ufo.db')
    parser.add_argument('--output',type=Path,default=silver.ROOT/'data/silver/ufo.readiness.json')
    args=parser.parse_args()
    protected={args.source.resolve(),args.database.resolve(),args.database.with_suffix('.validation.json').resolve(),
               silver.POLICY.resolve(),silver.MANIFEST.resolve()}
    if args.output.resolve() in protected:
        parser.error('El informe no puede sustituir una base, política o validación')
    try:
        result=readiness(args.source,args.database,json.loads(silver.MANIFEST.read_text()),json.loads(silver.POLICY.read_text()))
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    except (OSError,ValueError,sqlite3.Error) as exc:
        print(f'NO APTA PARA GOLD: {exc}',file=sys.stderr)
        return 1
    print(f"Silver apta para Gold: {result['verification']['checks']} controles; informe {args.output}")
    return 0


if __name__=='__main__':raise SystemExit(main())
