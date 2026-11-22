"""Loss-aware temporal evidence and report-grain analytical contracts for Silver."""
from __future__ import annotations

from datetime import date
import calendar
import re

MONTHS = {name.casefold(): number for number in range(1,13)
          for name in (calendar.month_name[number],calendar.month_abbr[number])}
MONTH = '|'.join(sorted(MONTHS,key=len,reverse=True))


def interpret_raw_date(value):
    """Only anchored, unambiguous expressions. No two-digit years or fuzzy parser.

    A season or early/mid/late marker supplies a year/month, never a synthetic
    day. Winter, approximate, relative and multi-date prose stay qualified.
    Explicit ranges and decades are intervals, not a representative date.
    """
    if not isinstance(value,str) or not value.strip():
        return {'kind':'unresolved','candidate':None,'year_min':None,'year_max':None}
    text=' '.join(value.strip().split())
    result={'kind':'unresolved','candidate':None,'year_min':None,'year_max':None}
    match=re.fullmatch(r'(\d{4})\s*(?:-|–|/|to)\s*(\d{4})',text,re.I)
    if match:
        lower,upper=map(int,match.groups())
        if 1 <= lower < upper <= 9999:
            return {**result,'kind':'range','year_min':lower,'year_max':upper}
        return {**result,'kind':'qualified'}
    match=re.fullmatch(r"(?:(?:early|mid|late)[ -]+)?(\d{3}0)(?:s|'s|’s)",text,re.I)
    if match and int(match[1])>0:
        return {**result,'kind':'decade','year_min':int(match[1]),'year_max':int(match[1])+9}
    candidate=None
    kind='exact'
    # Explicit calendar precision, including UFOCAT empty day/month separators.
    if re.fullmatch(r'(?:[1-9]\d{3}|\d{4}-\d{2}(?:-\d{2})?)',text):
        candidate=text
    elif match := re.fullmatch(r'(\d{4})--',text):
        candidate=match[1]
    elif match := re.fullmatch(r'(\d{4})-(\d{2})-\s*[EML?]?',text):
        candidate=f'{match[1]}-{match[2]}'
        kind='coarsened'
    elif match := re.fullmatch(fr'({MONTH})\.?\s+(\d{{4}})(?:,?\s+(?:evening|morning|night|afternoon|dawn|dusk))?',text,re.I):
        candidate=f'{match[2]}-{MONTHS[match[1].casefold()]:02d}'
    elif match := re.fullmatch(fr'(\d{{1,2}})\s+({MONTH})\.?\s+(\d{{4}})',text,re.I):
        candidate=f'{match[3]}-{MONTHS[match[2].casefold()]:02d}-{int(match[1]):02d}'
    elif match := re.fullmatch(fr'({MONTH})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})',text,re.I):
        candidate=f'{match[3]}-{MONTHS[match[1].casefold()]:02d}-{int(match[2]):02d}'
    elif match := re.fullmatch(r'(?:(?:early|mid|late)|(?:(?:in the )?(?:spring|summer|autumn|fall)(?: evening| night| morning| afternoon)?(?: of| in)?))\s+(\d{4})(?:\s+(?:night|day|evening|morning|afternoon))?',text,re.I):
        candidate=match[1];kind='coarsened'
    elif match := re.fullmatch(fr'(?:early|mid|late)\s+({MONTH})\.?\s+(\d{{4}})',text,re.I):
        candidate=f'{match[2]}-{MONTHS[match[1].casefold()]:02d}';kind='coarsened'
    elif match := re.fullmatch(r'(?:early|mid|late)\s+(?:spring|summer|autumn|fall)(?: of)?\s+(\d{4})',text,re.I):
        candidate=match[1];kind='coarsened'
    elif match := re.fullmatch(r'(\d{4})\s+(?:(?:early|mid|late)\s+)?(?:spring|summer|autumn|fall)',text,re.I):
        candidate=match[1];kind='coarsened'
    elif match := re.fullmatch(r'(?:one|a) night\s*\(([1-9]\d{3})\)',text,re.I):
        candidate=match[1];kind='coarsened'
    elif match := re.fullmatch(r'([1-9]\d{3})\s*\([^)]*\)',text):
        # A contextual parenthesis is not itself uncertainty; never extract a
        # publication year or ignore a second date/approximation inside it.
        if not re.search(r'\b(?:approximate|approximately|circa|before|after)\b|\?|\d{3,4}',text[4:],re.I):
            candidate=match[1];kind='coarsened'
    elif match := re.fullmatch(r'(?:early|mid|late|end of)\s+(\d{1,2})/(\d{4})',text,re.I):
        candidate=f'{match[2]}-{int(match[1]):02d}';kind='coarsened'
    elif match := re.fullmatch(r'(\d{1,2})/(\d{4})',text):
        candidate=f'{match[2]}-{int(match[1]):02d}'
    elif match := re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{4})',text):
        a,b,year=map(int,match.groups())
        options=set()
        for month,day in ((a,b),(b,a)):
            try:options.add(date(year,month,day).isoformat())
            except ValueError:pass
        if len(options)==1:candidate=options.pop()
    if candidate:
        try:
            date.fromisoformat(candidate + ('-01-01' if len(candidate)==4 else '-01' if len(candidate)==7 else ''))
        except ValueError:
            return {**result,'kind':'qualified'}
        year=int(candidate[:4])
        return {'kind':kind,'candidate':candidate,'year_min':year,'year_max':year}
    if re.search(r'\b(?:approximate|approximately|circa|winter|spring|summer|autumn|fall|early|mid|late)\b|\?',text,re.I):
        result['kind']='qualified'
    return result


def create_evidence(conn):
    conn.executescript('''
        CREATE TABLE temporal_evidence (
            sighting_id INTEGER PRIMARY KEY REFERENCES sighting(id),
            raw_value TEXT,
            interpretation TEXT NOT NULL CHECK(interpretation IN
                ('exact','coarsened','range','decade','qualified','unresolved','conflict')),
            candidate TEXT, year_min INTEGER, year_max INTEGER,
            applied INTEGER NOT NULL CHECK(applied IN (0,1)),
            CHECK((year_min IS NULL AND year_max IS NULL) OR
                  (year_min BETWEEN 1 AND 9999 AND year_max BETWEEN year_min AND 9999))
        );
        CREATE TABLE country_evidence (
            table_name TEXT NOT NULL, record_id TEXT NOT NULL,
            reported_value TEXT, coded_value TEXT,
            reported_iso2 TEXT, coded_iso2 TEXT,
            PRIMARY KEY(table_name,record_id)
        );
    ''')


def preserve_countries(conn, tables, countries):
    for table in tables:
        columns={row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
        if table not in ('location','crash_retrieval','nuclear_encounter') or 'country' not in columns:
            continue
        secondary='country_iso2' if 'country_iso2' in columns else 'NULL'
        rows=[]
        for key,reported,coded in conn.execute(f'SELECT id,country,{secondary} FROM "{table}"'):
            first=countries.lookup.get(str(reported).strip().casefold()) if reported is not None else None
            second=str(coded).strip().upper() if coded is not None else None
            second=second if second in countries.names else None
            rows.append((table,str(key),reported,coded,first,second))
        conn.executemany('INSERT INTO country_evidence VALUES (?,?,?,?,?,?)',rows)


def create_analytical_views(conn):
    columns={row[1] for row in conn.execute('PRAGMA table_info(sighting)')}
    proximity = "(s.coordinate_status='valid' AND s.distance_to_nearest_nuclear_site_km IS NOT NULL AND s.nearest_nuclear_site_name IS NOT NULL)" if {'distance_to_nearest_nuclear_site_km','nearest_nuclear_site_name'} <= columns else '0'
    conn.executescript(f'''
        CREATE VIEW silver_rescued_value AS
            SELECT table_name,record_id,column_name,old_value AS raw_value,rule_id
            FROM silver_change WHERE new_value='null' AND old_value!='null';
        CREATE VIEW sighting_analytical AS
            SELECT s.*,d.name AS source_name,m.canonical_event_id,
                (m.canonical_event_id=s.id) AS is_canonical,
                l.country AS canonical_country,l.country_iso2 AS canonical_country_iso2,
                COALESCE(l.country_status,'missing') AS country_status,
                e.reported_value AS country_reported,e.coded_value AS country_coded,
                e.reported_iso2,e.coded_iso2,
                (s.coordinate_status='valid') AS usable_for_map,
                {proximity} AS usable_for_nuclear_proximity,
                (s.date_status='valid' AND s.date_certainty IN ('source','coarsened')) AS usable_for_calendar,
                COALESCE((l.country_status='valid'),0) AS usable_for_country,
                t.year_min AS evidence_year_min,t.year_max AS evidence_year_max,
                t.interpretation AS raw_date_interpretation
            FROM sighting s JOIN source_database d ON d.id=s.source_db_id
            JOIN event_membership m ON m.sighting_id=s.id
            LEFT JOIN location l ON l.id=s.location_id
            LEFT JOIN country_evidence e ON e.table_name='location' AND e.record_id=CAST(l.id AS TEXT)
            LEFT JOIN temporal_evidence t ON t.sighting_id=s.id;
        CREATE VIEW sighting_reports_for_map AS
            SELECT * FROM sighting_analytical WHERE usable_for_map=1;
        CREATE VIEW sighting_reports_for_time_analysis AS
            SELECT * FROM sighting_analytical WHERE usable_for_calendar=1;
        DROP VIEW sighting_for_time_analysis;
        CREATE VIEW sighting_for_time_analysis AS
            SELECT * FROM sighting_canonical WHERE date_status='valid'
                AND date_certainty IN ('source','coarsened');
        CREATE VIEW quality_quarantine AS
            SELECT * FROM quality_issue WHERE action IN ('review','nullified');
        CREATE VIEW quality_summary AS
            SELECT table_name,rule_id,action,COUNT(*) AS affected_records
            FROM (SELECT DISTINCT table_name,record_id,rule_id,action FROM quality_issue)
            GROUP BY table_name,rule_id,action;
    ''')


def temporal_decision(original, parser, reference, suspect=False):
    raw=original.get('date_event_raw')
    evidence=interpret_raw_date(raw)
    initial=parser(original.get('date_event'),reference,suspect)
    overrides={}
    forced=None
    certainty='source' if initial[2]=='valid' else 'unknown'
    kind=evidence['kind']
    if kind in ('range','decade'):
        forced='range';certainty='interval'
        overrides={'date_event':None,'sighting_datetime':None}
    elif kind=='qualified':
        certainty='qualified'
    elif evidence['candidate']:
        candidate=evidence['candidate']
        parsed=parser(candidate,reference,suspect)
        if parsed[2]=='valid' and initial[2] in ('missing','valid'):
            # Compare only calendar components actually supplied by both fields.
            left=(initial[0] or '').split('T')[0]
            common=min(len(left),len(candidate))
            if left and left[:common]!=candidate[:common]:
                forced='review';certainty='qualified';evidence['kind']='conflict'
                overrides={'date_event':None,'sighting_datetime':None}
            elif initial[2]=='missing' or len(candidate)!=len(left):
                # Preserve a known time when the raw expression states the same day.
                overrides={'date_event':candidate,'sighting_datetime':candidate}
                certainty='coarsened' if kind=='coarsened' else 'source'
            elif kind=='coarsened':
                certainty='coarsened'
    relevant=bool(overrides) or kind in ('qualified','range','decade') or initial[2]!='valid'
    return evidence,overrides,forced,certainty,relevant


def validate_analytics(conn, countries):
    """Reconcile evidence to Bronze and assert report-grain/dimension contracts."""
    checks={}
    def zero(name,sql):
        actual=conn.execute(sql).fetchone()[0]
        checks[name]={'actual':actual,'expected':0,'passed':actual==0,'sql':sql}
    zero('analytics_report_coverage', '''SELECT COUNT(*) FROM sighting s
        LEFT JOIN sighting_analytical a ON a.id=s.id WHERE a.id IS NULL''')
    count=conn.execute('SELECT COUNT(*) FROM sighting_analytical').fetchone()[0]
    total=conn.execute('SELECT COUNT(*) FROM sighting').fetchone()[0]
    checks['analytics_report_grain']={'actual':count,'expected':total,'passed':count==total}
    zero('analytics_country_flags', '''SELECT COUNT(*) FROM sighting_analytical
        WHERE usable_for_country IS NOT (country_status='valid')''')
    zero('analytics_map_flags', '''SELECT COUNT(*) FROM sighting_analytical
        WHERE usable_for_map IS NOT (coordinate_status='valid')''')
    zero('analytics_calendar_flags', '''SELECT COUNT(*) FROM sighting_analytical
        WHERE usable_for_calendar IS NOT (date_status='valid' AND date_certainty IN ('source','coarsened'))''')
    columns={row[1] for row in conn.execute('PRAGMA table_info(sighting)')}
    for column in ('distance_to_nearest_nuclear_site_km','nearest_nuclear_site_name'):
        if column in columns:
            zero('analytics_geographic_dependency_'+column,
                f"SELECT COUNT(*) FROM sighting WHERE coordinate_status!='valid' AND {column} IS NOT NULL")
    zero('analytics_range_no_point_date', '''SELECT COUNT(*) FROM sighting
        WHERE date_status='range' AND (date_event IS NOT NULL OR event_year IS NOT NULL
        OR sighting_datetime IS NOT NULL OR date_certainty!='interval')''')
    zero('analytics_temporal_raw', '''SELECT COUNT(*) FROM temporal_evidence e
        JOIN bronze.sighting b ON b.id=e.sighting_id WHERE e.raw_value IS NOT b.date_event_raw''')
    zero('analytics_temporal_orphans', '''SELECT COUNT(*) FROM temporal_evidence e
        LEFT JOIN sighting s ON s.id=e.sighting_id WHERE s.id IS NULL''')
    zero('analytics_date_certainty', '''SELECT COUNT(*) FROM sighting WHERE date_certainty IS NULL
        OR date_certainty NOT IN ('source','coarsened','qualified','interval','unknown')''')
    zero('analytics_quarantine_map', '''SELECT COUNT(*) FROM quality_issue q
        JOIN sighting_reports_for_map s ON s.id=CAST(q.record_id AS INTEGER)
        WHERE q.table_name='sighting' AND q.rule_id='coordinate_country_conflict' ''')
    # Check original country values, independent codes and complete key coverage.
    for table in ('location','crash_retrieval','nuclear_encounter'):
        columns={r[1] for r in conn.execute(f'PRAGMA bronze.table_info("{table}")')}
        if 'country' not in columns:continue
        secondary='b.country_iso2' if 'country_iso2' in columns else 'NULL'
        zero(f'analytics_country_raw_{table}',f'''SELECT COUNT(*) FROM bronze."{table}" b
            LEFT JOIN country_evidence e ON e.table_name='{table}' AND e.record_id=CAST(b.id AS TEXT)
            WHERE e.record_id IS NULL OR e.reported_value IS NOT b.country OR e.coded_value IS NOT {secondary}''')
        expected=conn.execute(f'SELECT COUNT(*) FROM bronze."{table}"').fetchone()[0]
        actual=conn.execute('SELECT COUNT(*) FROM country_evidence WHERE table_name=?',(table,)).fetchone()[0]
        checks[f'analytics_country_count_{table}']={'actual':actual,'expected':expected,'passed':actual==expected}
    bad=0
    for reported,coded,first,second in conn.execute('SELECT reported_value,coded_value,reported_iso2,coded_iso2 FROM country_evidence'):
        expected=countries.lookup.get(str(reported).strip().casefold()) if reported is not None else None
        other=str(coded).strip().upper() if coded is not None else None
        other=other if other in countries.names else None
        bad+=first!=expected or second!=other
    checks['analytics_country_independent_codes']={'actual':bad,'expected':0,'passed':bad==0}
    return checks


def field_profile(conn, layouts):
    """One scan per table: denominators and completeness, not a quality score."""
    result={}
    for table,layout in layouts.items():
        names=[col[1] for col in layout]
        expressions=['COUNT(*)']
        for name in names:
            q='"'+name.replace('"','""')+'"'
            expressions.extend([f'COUNT({q})',f"SUM(CASE WHEN typeof({q})='text' AND trim({q},char(9)||char(10)||char(11)||char(12)||char(13)||' ')='' THEN 1 ELSE 0 END)"])
        row=conn.execute('SELECT '+','.join(expressions)+f' FROM "{table}"').fetchone()
        result[table]={'rows':row[0],'columns':{name:{'non_null':row[1+2*i],'null':row[0]-row[1+2*i],
            'blank_text':row[2+2*i] or 0} for i,name in enumerate(names)}}
    return result


def validate_temporal_evidence(conn, parser, policy):
    """Replay the declared grammar against every source row, including omissions."""
    evidence={row[0]:tuple(row[1:]) for row in conn.execute('SELECT * FROM temporal_evidence')}
    expected_keys=set()
    discrepancies=0
    sources=dict(conn.execute('SELECT id,name FROM source_database'))
    query='''SELECT b.id,b.date_event,b.sighting_datetime,b.date_event_raw,b.source_db_id,
        s.date_event,s.sighting_datetime,s.date_certainty,s.date_status,s.date_precision,s.event_year,
        s.datetime_precision,s.timezone_status FROM bronze.sighting b JOIN sighting s ON s.id=b.id'''
    for key,old,old_dt,raw,source,new,new_dt,certainty,status,precision,year,dt_precision,zone in conn.execute(query):
        original={'date_event':old,'sighting_datetime':old_dt,'date_event_raw':raw}
        suspect=sources.get(source)=='UFOCAT'
        detail,overrides,forced,expected_certainty,relevant=temporal_decision(original,parser,policy['reference_date'],suspect)
        if relevant:
            expected_keys.add(key)
            applied=any(original[name]!=value for name,value in overrides.items())
            expected=(raw,detail['kind'],detail['candidate'],detail['year_min'],detail['year_max'],int(applied))
            discrepancies+=evidence.get(key)!=expected
        discrepancies+=certainty!=expected_certainty
        parsed=parser(overrides.get('date_event',old),policy['reference_date'],suspect)
        clock=parser(overrides.get('sighting_datetime',old_dt),policy['reference_date'],suspect)
        if forced:
            point=(None,'year_range' if forced=='range' else 'unknown',forced,None)
            expected_clock=(None,'year_range' if forced=='range' else 'unknown','not_applicable')
        else:
            point=(parsed[0],parsed[1],parsed[2],parsed[4])
            expected_clock=(clock[0],clock[1],clock[3])
        discrepancies+=(new,precision,status,year)!=point
        discrepancies+=(new_dt,dt_precision,zone)!=expected_clock
    discrepancies+=len(set(evidence)^expected_keys)
    return {'analytics_temporal_replay':{'actual':discrepancies,'expected':0,'passed':discrepancies==0,
        'evidence_records':len(expected_keys),'scope':'Every Bronze sighting: evidence coverage, raw values, point dates, precision, certainty and intervals.'}}
