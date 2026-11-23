"""Loss-aware temporal evidence and report-grain analytical contracts for Silver."""
from __future__ import annotations

from datetime import date
from functools import lru_cache
import calendar
import re
import statistics

if __package__:
    from . import silver_evidence as source_evidence
else:
    import silver_evidence as source_evidence

MONTHS = {name.casefold(): number for number in range(1,13)
          for name in (calendar.month_name[number],calendar.month_abbr[number])}
MONTH = '|'.join(sorted(MONTHS,key=len,reverse=True))

# Italian catalogue layout used by Capella: "[weekday] DD MONTH YYYY time place
# (province) code". The leading date is complete; qualifiers after it concern
# the clock or the place, never the calendar date.
ITALIAN_MONTHS = {name: number for number, name in enumerate(
    ('gennaio','febbraio','marzo','aprile','maggio','giugno','luglio','agosto',
     'settembre','ottobre','novembre','dicembre'), 1)}
ITALIAN_MONTH = '|'.join(ITALIAN_MONTHS)
ITALIAN_DAY = re.compile(fr'(?:(?:lun|mar|mer|gio|ven|sab|dom)\.?\s+)?(\d{{1,2}})\s+({ITALIAN_MONTH})\s+(\d{{4}})(?=\s|$)', re.I)
ITALIAN_MONTH_YEAR = re.compile(fr'({ITALIAN_MONTH})\s+(\d{{4}})(?=\s|$)', re.I)
ITALIAN_SEASON = re.compile(r'(?:estate|primavera|autunno)\s+(\d{4})(?=\s|$)', re.I)
ITALIAN_YEAR = re.compile(r'anno\s+(\d{4})(?=\s|$)', re.I)
# Immediately after the date: an alternative ("o 1980"), addition, interval or
# doubt applies to the date itself. "TRA 17 E 18", "AL TRAMONTO" or "1845"
# after the date describe the clock. A parenthesis without digits or
# alternatives ("(fine)", "(metà)") only locates the event within the month.
ITALIAN_ALTERNATIVE = re.compile(r'\s*(?:(?:o|e|ed|oppure|inverno)\b|o\d{4}\b|[/?~–—-])', re.I)
ITALIAN_PARENTHESIS = re.compile(r'\s*\(([^)]*)\)?')

# Words that make a free-text date approximate, alternative, relative, a range
# or a report/publication date. Such text is never certified as calendar
# precision. "EST" is deliberately absent: it is a time-zone label.
QUALIFIER = re.compile(
    r"~|\?|±|\+/-|–|—|\b(?:approximate|approximately|approximated|approx|circa|ca|about|around|"
    r"estimated|estimate|or|and|to|before|after|prior|between|ago|since|unknown|"
    r"unspecified|undated|uncertain|unsure|probably|possibly|perhaps|maybe|might|"
    r"could|last|past|recent|recently|week|weeks|month|months|years|several|few|"
    r"couple|multiple|through|thru|until|till|within|following|earlier|later|"
    r"period|same|not|no|relative|referenced|context|reported|report|published|"
    r"publication|posted|listed|website|cover|page|interview|letter|received|"
    r"filed|dated|issue|winter|spring|summer|autumn|fall|early|mid|late|oppure|"
    r"prima|dopo|tra|fra|inverno|imprecisat[oa])\b", re.I)

SUPPORT_MONTHS = {**MONTHS, 'sept': 9, 'jne': 6, **ITALIAN_MONTHS}
SUPPORT_MONTH = '|'.join(sorted(SUPPORT_MONTHS, key=len, reverse=True))
SUPPORT_PATTERNS = (
    # (regex, (year group, month group or name, day group))
    (re.compile(r'(?<!\d)(\d{1,4})\s*([/.\-])\s*(\d{1,4})(?:\s*\2\s*(\d{1,4}))?(?!\d)'), 'numeric'),
    (re.compile(fr'(?<!\d)(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:of\s+)?({SUPPORT_MONTH})\b\.?,?\s*\[?(\d{{4}}|\d{{2}}(?!\d))?'), 'day_month'),
    (re.compile(fr'\b({SUPPORT_MONTH})\b\.?\s*(\d{{1,2}})(?:st|nd|rd|th)?(?!\d)\s*,?\s*\[?(\d{{4}}|\d{{2}}(?!\d))?'), 'month_day'),
    (re.compile(fr'\b({SUPPORT_MONTH})\b\.?,?\s*(?:of\s+)?\[?(\d{{4}}|\d{{2}})(?!\d)'), 'month_year'),
    (re.compile(fr'(?<!\d)(\d{{4}})\s+({SUPPORT_MONTH})\b\.?\s*(\d{{1,2}})?(?!\d)'), 'year_month'),
    (re.compile(r'(?<!\d)(\d{6}|\d{8})(?!\d)'), 'compact'),
    # Military date-time group: DDHHMM[Z|GMT] MON YY.
    (re.compile(fr'(?<!\d)(\d{{2}})\d{{4}}\s*(?:z|gmt)?\s*({SUPPORT_MONTH})\b\.?\s*(\d{{2}}|\d{{4}})(?!\d)'), 'dtg'),
)
# Several days of one month ("21-22 July", "1, 2, 3 March"): only the month is certain.
MULTIPLE_DAYS = re.compile(
    fr'(?<!\d)\d{{1,2}}(?:st|nd|rd|th)?\s*(?:-|/|&|,)\s*\d{{1,2}}(?:st|nd|rd|th)?\s*,?\s+(?:of\s+)?(?:{SUPPORT_MONTH})\b'
    fr'|\b(?:{SUPPORT_MONTH})\b\.?\s*\d{{1,2}}\s*(?:-|/|&)\s*\d{{1,2}}(?!\d)(?!\s*:)', re.I)


def _year_matches(token, year):
    if token is None:
        return False
    if len(token) in (3, 4):
        return int(token) == year
    # A two-digit year can only corroborate the origin's century, never create it.
    return len(token) == 2 and int(token) == year % 100


@lru_cache(maxsize=262144)
def supported_date(raw, point):
    """Finest prefix of ``point`` (YYYY[-MM[-DD]]) whose components appear in raw text.

    Components must be adjacent in an explicit date expression: a stray number
    (hour, file code) cannot support a day. Returns None when even the year is
    absent, i.e. the origin took it from outside the date field.
    """
    text = ' '.join(raw.casefold().split())
    year = int(point[:4])
    month = int(point[5:7]) if len(point) >= 7 else None
    day = int(point[8:10]) if len(point) >= 10 else None
    numbers = re.findall(r'\d+', text)
    free_year = any(_year_matches(token, year) for token in numbers if len(token) <= 4)
    best = 0

    def take(y, m, d, year_required=True):
        nonlocal best
        if not (_year_matches(y, year) or (y is None and not year_required and free_year)):
            return
        best = max(best, 1)
        if month is not None and m is not None and int(m) == month:
            best = max(best, 2)
            if day is not None and d is not None and int(d) == day:
                best = 3

    for pattern, layout in SUPPORT_PATTERNS:
        for match in pattern.finditer(text):
            if layout == 'numeric':
                a, _, b, c = match.groups()
                if c is None:
                    if len(a) >= 3:
                        take(a, b, None)
                    elif len(b) >= 2:
                        take(b, a, None)
                elif len(a) >= 3:
                    take(a, b, c)
                else:
                    take(c, a, b)
                    take(c, b, a)
            elif layout == 'day_month':
                take(match[3], SUPPORT_MONTHS[match[2]], match[1], False)
            elif layout == 'month_day':
                take(match[3], SUPPORT_MONTHS[match[1]], match[2], False)
            elif layout == 'month_year':
                take(match[2], SUPPORT_MONTHS[match[1]], None)
            elif layout == 'year_month':
                take(match[1], SUPPORT_MONTHS[match[2]], match[3])
            elif layout == 'compact':
                token = match[1]
                if len(token) == 6:
                    take(token[:2], token[2:4], token[4:])
                    take(token[4:], token[:2], token[2:4])
                    take(token[4:], token[2:4], token[:2])
                else:
                    take(token[:4], token[4:6], token[6:])
                    take(token[4:], token[:2], token[2:4])
                    take(token[4:], token[2:4], token[:2])
            else:
                take(match[3], SUPPORT_MONTHS[match[2]], match[1])
    if best == 0 and free_year:
        best = 1
    if best == 3 and MULTIPLE_DAYS.search(text):
        best = 2
    return (None, point[:4], point[:7], point[:10])[best]


def interpret_raw_date(value, source=None):
    """Only anchored, unambiguous expressions. No two-digit years or fuzzy parser.

    A season or early/mid/late marker supplies a year/month, never a synthetic
    day. Winter, approximate, relative and multi-date prose stay qualified.
    Explicit ranges and decades are intervals, not a representative date.
    """
    if not isinstance(value,str) or not value.strip():
        return {'kind':'unresolved','candidate':None,'year_min':None,'year_max':None}
    text=' '.join(value.strip().split())
    result={'kind':'unresolved','candidate':None,'year_min':None,'year_max':None}
    if source == 'UFOCAT':
        # Codebook 2023, p.16: final YEAR character . / E / M / L is an
        # uncertain year within the decade. Keep its full envelope, never
        # turn 'late' into an invented 1968-1969 range.
        match = re.fullmatch(r'(\d{3})[.EML]-(?:\d{2}|[EFMLSW])?-(?:\d{2}|[EML])?', text.replace(' ', ''))
        if match and int(match[1]) > 0:
            lower = int(match[1]) * 10
            return {**result, 'kind':'decade', 'year_min':lower, 'year_max':lower+9}
        match = re.fullmatch(r'([1-9]\d{3})-[EFMLSW]-(?:\d{2}|[EML])?', text.replace(' ', ''))
        if match:
            year = int(match[1])
            return {**result, 'kind':'coarsened', 'candidate':match[1], 'year_min':year, 'year_max':year}
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
    elif match := re.fullmatch(r'(\d{4}-\d{2}-\d{2})[ T]\d{2}:\d{2}(?::\d{2})?',text):
        # Database timestamp text: the calendar part is explicit.
        candidate=match[1]
    elif (match := ITALIAN_DAY.match(text) or ITALIAN_MONTH_YEAR.match(text)
          or ITALIAN_YEAR.match(text) or ITALIAN_SEASON.match(text)):
        note=ITALIAN_PARENTHESIS.match(text,match.end())
        if ITALIAN_ALTERNATIVE.match(text,match.end()) or note and re.search(
                r'\d|\?|\b(?:o|e|oppure|circa|ca)\b',note[1],re.I):
            return {**result,'kind':'qualified'}
        if note and match.re is not ITALIAN_DAY:
            kind='coarsened'
        if match.re is ITALIAN_DAY:
            candidate=f'{match[3]}-{ITALIAN_MONTHS[match[2].casefold()]:02d}-{int(match[1]):02d}'
        elif match.re is ITALIAN_MONTH_YEAR:
            candidate=f'{match[2]}-{ITALIAN_MONTHS[match[1].casefold()]:02d}'
        else:
            candidate=match[1]
            if match.re is ITALIAN_SEASON:
                kind='coarsened'
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
    elif match := re.fullmatch(r'([1-9]\d{3})\s*\(([^)]*)\)',text):
        # A contextual parenthesis is not itself uncertainty; never extract a
        # publication year or ignore a second date/approximation inside it.
        inner=match[2].strip().rstrip('.').casefold()
        if inner in MONTHS:
            candidate=f'{match[1]}-{MONTHS[inner]:02d}'
        elif not (QUALIFIER.search(match[2]) or re.search(r'\d{3,4}',match[2])):
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
    if QUALIFIER.search(text):
        result['kind']='qualified'
    return result


def create_evidence(conn):
    conn.executescript('''
        CREATE TABLE temporal_evidence (
            sighting_id INTEGER PRIMARY KEY REFERENCES sighting(id),
            raw_value TEXT,
            interpretation TEXT NOT NULL CHECK(interpretation IN
                ('exact','coarsened','range','decade','qualified','unresolved','conflict','unsupported')),
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


PLACEHOLDER_BASELINE_DAYS = tuple(f'{day:02d}' for day in range(2,29))


def placeholder_profile(rows, policy):
    """Per source, how often conventional placeholder values occur in calendar dates.

    ``rows`` yields (source_db_id, date_event) for calendar-eligible dates with a
    day. A day is compared with the median of days 02-28 that are not
    themselves candidates; 01-01 is compared with the first day of the other
    months. The comparison flags a statistical excess; it cannot say which
    individual report used the placeholder.
    """
    settings=policy.get('temporal_placeholders') or {}
    candidates=settings.get('candidates',{})
    threshold=settings.get('ratio_threshold')
    days={}
    for source,value in rows:
        counts=days.setdefault(source,{})
        counts[value[8:10]]=counts.get(value[8:10],0)+1
        counts[value[5:10]]=counts.get(value[5:10],0)+1
    profile=[]
    for source in sorted(days):
        counts=days[source]
        for pattern,values in sorted(candidates.items()):
            for value in sorted(values):
                if pattern=='day':
                    baseline=statistics.median(counts.get(d,0) for d in PLACEHOLDER_BASELINE_DAYS if d not in values)
                elif pattern=='month_day' and value.endswith('-01'):
                    baseline=statistics.median(counts.get(f'{m:02d}-01',0) for m in range(1,13) if f'{m:02d}-01'!=value)
                else:
                    raise ValueError(f'Patrón de marcador temporal no soportado: {pattern}:{value}')
                observed=counts.get(value,0)
                ratio=round(observed/baseline,4) if baseline else None
                flagged=int(ratio is not None and threshold is not None and ratio>=threshold)
                profile.append((source,pattern,value,observed,float(baseline),ratio,flagged))
    return profile


def calendar_rows(conn):
    return conn.execute('''SELECT source_db_id,date_event FROM sighting
        WHERE date_status='valid' AND date_certainty IN ('source','coarsened') AND length(date_event)>=10''')


def create_placeholder_profile(conn, policy):
    conn.execute('''CREATE TABLE temporal_placeholder_profile (
        source_db_id INTEGER NOT NULL REFERENCES source_database(id),
        pattern TEXT NOT NULL CHECK(pattern IN ('day','month_day')), value TEXT NOT NULL,
        observed INTEGER NOT NULL, baseline REAL NOT NULL, ratio REAL,
        flagged INTEGER NOT NULL CHECK(flagged IN (0,1)),
        PRIMARY KEY(source_db_id,pattern,value))''')
    conn.executemany('INSERT INTO temporal_placeholder_profile VALUES (?,?,?,?,?,?,?)',
                     placeholder_profile(calendar_rows(conn),policy))


def create_analytical_views(conn, policy=None):
    columns={row[1] for row in conn.execute('PRAGMA table_info(sighting)')}
    proximity = "(s.coordinate_status='valid' AND s.distance_to_nearest_nuclear_site_km IS NOT NULL AND s.nearest_nuclear_site_name IS NOT NULL)" if {'distance_to_nearest_nuclear_site_km','nearest_nuclear_site_name'} <= columns else '0'
    create_placeholder_profile(conn, policy or {})
    calendar = "(s.date_status='valid' AND s.date_certainty IN ('source','coarsened'))"
    month_risk = f"({calendar} AND length(s.date_event)>=10 AND pm.flagged IS 1)"
    day_risk = f"({calendar} AND length(s.date_event)>=10 AND (pd.flagged IS 1 OR pm.flagged IS 1))"
    conn.executescript(f'''
        CREATE VIEW silver_rescued_value AS
            SELECT table_name,record_id,column_name,old_value AS raw_value,rule_id
            FROM silver_change
            WHERE (new_value='null' AND old_value!='null'
                   AND NOT (json_type(old_value)='text' AND trim(json_extract(old_value,'$'))=''))
               OR rule_id='size_estimate';
        CREATE VIEW sighting_analytical AS
            SELECT s.*,d.name AS source_name,m.canonical_event_id,
                (m.canonical_event_id=s.id) AS is_canonical,
                CASE WHEN g.country_check='fill' THEN g.country
                    WHEN g.country_check IN ('non_terrestrial','conflict') THEN NULL
                    ELSE l.country END AS canonical_country,
                CASE WHEN g.country_check='fill' THEN g.country_iso2
                    WHEN g.country_check IN ('non_terrestrial','conflict') THEN NULL
                    ELSE l.country_iso2 END AS canonical_country_iso2,
                CASE WHEN g.country_check='non_terrestrial' THEN 'not_applicable'
                    WHEN g.country_check='fill' THEN 'valid'
                    WHEN g.country_check='conflict' THEN 'conflict'
                    ELSE COALESCE(l.country_status,'missing') END AS country_status,
                g.country_reported AS source_catalog_country,
                CASE WHEN g.country_check='non_terrestrial' THEN 'non_terrestrial'
                    WHEN g.country_check='fill' THEN 'original_catalog'
                    WHEN g.country_check='conflict' THEN 'source_conflict'
                    WHEN g.country_check='corroborated' THEN 'location_corroborated'
                    ELSE 'location' END AS country_basis,
                CASE WHEN g.coordinate_check='non_terrestrial' THEN 'non_terrestrial'
                    WHEN g.coordinate_check='fill' THEN 'original_catalog_place'
                    WHEN g.coordinate_check='conflict' THEN 'source_conflict'
                    WHEN g.coordinate_check='corroborated' THEN 'bronze_corroborated'
                    ELSE 'bronze' END AS coordinate_basis,
                g.bronze_distance_km AS source_catalog_distance_km,
                CASE WHEN te.sighting_id IS NOT NULL THEN 'original_catalog'
                    WHEN s.time_raw IS NOT NULL THEN 'bronze' END AS time_basis,
                CASE WHEN te.clock_applied=1 THEN 'original_catalog'
                    WHEN s.datetime_precision IN ('minute','second','fractional_second') THEN 'bronze' END AS clock_basis,
                (g.coordinate_check='fill' OR g.country_check='fill' OR te.sighting_id IS NOT NULL) IS 1 AS uses_external_evidence,
                e.reported_value AS country_reported,e.coded_value AS country_coded,
                e.reported_iso2,e.coded_iso2,
                (s.coordinate_status='valid') AS usable_for_map,
                {proximity} AS usable_for_nuclear_proximity,
                {calendar} AS usable_for_calendar,
                {day_risk} AS day_placeholder_risk,
                {month_risk} AS month_placeholder_risk,
                CASE WHEN NOT {calendar} THEN NULL
                    WHEN {month_risk} THEN 'year'
                    WHEN {day_risk} THEN 'month'
                    WHEN length(s.date_event)>=10 THEN 'day'
                    WHEN length(s.date_event)=7 THEN 'month'
                    ELSE 'year' END AS calendar_precision,
                ({calendar} AND length(s.date_event)>=10 AND NOT {day_risk}) AS usable_for_day_analysis,
                ({calendar} AND length(s.date_event)>=7 AND NOT {month_risk}) AS usable_for_month_analysis,
                (CASE WHEN g.country_check='non_terrestrial' THEN 0
                    WHEN g.country_check='fill' THEN 1
                    WHEN g.country_check='conflict' THEN 0
                    ELSE COALESCE((l.country_status='valid'),0) END) AS usable_for_country,
                t.year_min AS evidence_year_min,t.year_max AS evidence_year_max,
                t.interpretation AS raw_date_interpretation
            FROM sighting s JOIN source_database d ON d.id=s.source_db_id
            JOIN event_membership m ON m.sighting_id=s.id
            LEFT JOIN location l ON l.id=s.location_id
            LEFT JOIN country_evidence e ON e.table_name='location' AND e.record_id=CAST(l.id AS TEXT)
            LEFT JOIN source_geography_evidence g ON g.sighting_id=s.id
            LEFT JOIN source_time_evidence te ON te.sighting_id=s.id
            LEFT JOIN temporal_evidence t ON t.sighting_id=s.id
            LEFT JOIN temporal_placeholder_profile pd ON pd.source_db_id=s.source_db_id
                AND pd.pattern='day' AND pd.value=substr(s.date_event,9,2)
            LEFT JOIN temporal_placeholder_profile pm ON pm.source_db_id=s.source_db_id
                AND pm.pattern='month_day' AND pm.value=substr(s.date_event,6,5);
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
    evidence=interpret_raw_date(raw, 'UFOCAT' if suspect else None)
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
        elif initial[2]=='valid':
            # The explicit raw date is future or a sentinel ("GIUGNO 3003"):
            # the origin's corrected year is not evidenced by the text.
            certainty='qualified';evidence['kind']='unsupported'
    elif kind=='unresolved' and initial[2]=='valid' and isinstance(raw,str) and raw.strip():
        # Free text outside the grammar: every canonical component must appear
        # in the original date text. The origin's synthetic day/month is
        # withdrawn; a year taken from outside the field is not certified.
        point=initial[0][:10]
        supported=supported_date(raw,point)
        if supported is None:
            certainty='qualified';evidence['kind']='unsupported'
        elif len(supported)<len(point):
            year=int(supported[:4])
            evidence.update(kind='coarsened',candidate=supported,year_min=year,year_max=year)
            overrides={'date_event':supported,'sighting_datetime':supported}
            certainty='coarsened'
    # The original importer accepted numeric prefixes, including incomplete
    # minutes or trailing corrupt characters, as precise times. The codebook
    # requires all four HHMM digits for minute precision.
    if suspect and not forced and original.get('time_raw') is not None:
        raw_time = str(original['time_raw']).strip()
        match = re.fullmatch(r'((?:[01]\d|2[0-3])):?([0-5]\d)', raw_time)
        for name in ('date_event', 'sighting_datetime'):
            value = overrides.get(name, original.get(name))
            parsed = parser(value, reference, suspect)
            if parsed[2]=='valid' and parsed[1] in ('minute','second','fractional_second'):
                if not match or parsed[0][11:16] != ':'.join(match.groups()):
                    overrides[name] = parsed[0][:10]
                    certainty = 'qualified' if certainty=='qualified' else 'coarsened'
                    if evidence['kind'] not in ('qualified','conflict','unsupported'):
                        evidence['kind']='coarsened'
    relevant=bool(overrides) or evidence['kind'] in ('qualified','range','decade','unsupported') or initial[2]!='valid'
    return evidence,overrides,forced,certainty,relevant


def validate_analytics(conn, countries, policy=None):
    """Reconcile evidence to Bronze and assert report-grain/dimension contracts."""
    checks={}
    def zero(name,sql):
        actual=conn.execute(sql).fetchone()[0]
        checks[name]={'actual':actual,'expected':0,'passed':actual==0,'sql':sql}
    expected_profile=placeholder_profile(calendar_rows(conn),policy or {})
    actual_profile=list(conn.execute('SELECT * FROM temporal_placeholder_profile ORDER BY source_db_id,pattern,value'))
    checks['analytics_placeholder_profile']={'actual':len(actual_profile),'expected':len(expected_profile),
        'passed':actual_profile==expected_profile,'flagged':[row[:3] for row in expected_profile if row[6]]}
    zero('analytics_calendar_precision', '''SELECT COUNT(*) FROM sighting_analytical WHERE
        usable_for_day_analysis IS NOT (calendar_precision IS 'day')
        OR usable_for_month_analysis IS NOT COALESCE(calendar_precision IN ('day','month'),0)
        OR (calendar_precision IS NULL) IS NOT (usable_for_calendar=0)
        OR (calendar_precision='day' AND date_precision NOT IN ('day','minute','second','fractional_second'))
        OR (calendar_precision='month' AND date_precision NOT IN ('month','day','minute','second','fractional_second'))
        OR (day_placeholder_risk=1 AND calendar_precision='day')
        OR (month_placeholder_risk=1 AND calendar_precision!='year')
        OR (month_placeholder_risk=1 AND day_placeholder_risk=0)''')
    zero('analytics_placeholder_flags', '''SELECT COUNT(*) FROM sighting_analytical a WHERE
        a.day_placeholder_risk IS NOT (a.usable_for_calendar=1 AND length(a.date_event)>=10 AND EXISTS(
            SELECT 1 FROM temporal_placeholder_profile p WHERE p.source_db_id=a.source_db_id AND p.flagged=1
            AND ((p.pattern='day' AND p.value=substr(a.date_event,9,2))
              OR (p.pattern='month_day' AND p.value=substr(a.date_event,6,5)))))
        OR a.month_placeholder_risk IS NOT (a.usable_for_calendar=1 AND length(a.date_event)>=10 AND EXISTS(
            SELECT 1 FROM temporal_placeholder_profile p WHERE p.source_db_id=a.source_db_id AND p.flagged=1
            AND p.pattern='month_day' AND p.value=substr(a.date_event,6,5)))''')
    zero('analytics_external_flags', '''SELECT COUNT(*) FROM sighting_analytical
        WHERE uses_external_evidence IS NOT (coordinate_basis IS 'original_catalog_place'
            OR country_basis IS 'original_catalog' OR time_basis IS 'original_catalog')''')
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
    zero('analytics_unknown_date_precision', '''SELECT COUNT(*) FROM sighting WHERE date_event IS NULL
        AND (date_precision NOT IN ('unknown','year_range') OR (sighting_datetime IS NULL
             AND datetime_precision NOT IN ('unknown','year_range')))''')
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
    source_times, _ = source_evidence.policy_times(policy)
    actual_source = {row[0]:tuple(row[1:]) for row in conn.execute('SELECT * FROM source_time_evidence')}
    expected_source = set()
    source_discrepancies = 0
    query='''SELECT b.id,b.date_event,b.sighting_datetime,b.date_event_raw,b.source_db_id,
        s.date_event,s.sighting_datetime,s.date_certainty,s.date_status,s.date_precision,s.event_year,
        s.datetime_precision,s.timezone_status,b.source_record_id,b.time_raw,s.time_raw
        FROM bronze.sighting b JOIN sighting s ON s.id=b.id'''
    for key,old,old_dt,raw,source,new,new_dt,certainty,status,precision,year,dt_precision,zone,source_id,old_time,new_time in conn.execute(query):
        original={'date_event':old,'sighting_datetime':old_dt,'date_event_raw':raw,'time_raw':old_time}
        suspect=sources.get(source)=='UFOCAT'
        detail,overrides,forced,expected_certainty,relevant=temporal_decision(original,parser,policy['reference_date'],suspect)
        if relevant:
            expected_keys.add(key)
            applied=any(original[name]!=value for name,value in overrides.items())
            expected=(raw,detail['kind'],detail['candidate'],detail['year_min'],detail['year_max'],int(applied))
            discrepancies+=evidence.get(key)!=expected
        discrepancies+=certainty!=expected_certainty
        item=source_times.get(source_id) if sources.get(source)=='UFO-search' else None
        time_changes=source_evidence.time_overrides(original,(detail,overrides,forced,expected_certainty,relevant),item,parser,policy['reference_date'])
        if item:
            expected_source.add(key)
            expected=(source_id,raw,item['time_raw'],int(item['single_date']),int('sighting_datetime' in time_changes))
            source_discrepancies+=actual_source.get(key)!=expected
        source_discrepancies+=new_time!=time_changes.get('time_raw',old_time)
        overrides.update(time_changes)
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
    source_discrepancies+=len(set(actual_source)^expected_source)
    return {'analytics_temporal_replay':{'actual':discrepancies,'expected':0,'passed':discrepancies==0,
        'evidence_records':len(expected_keys),'scope':'Every Bronze sighting: evidence coverage, raw values, point dates, precision, certainty and intervals.'},
        'analytics_source_time_replay':{'actual':source_discrepancies,'expected':0,'passed':source_discrepancies==0,
        'evidence_records':len(expected_source)}}
