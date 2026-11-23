"""Pinned factual source fields; no network access or narrative redistribution."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re


def policy_times(policy):
    path = policy.get('source_time_reference')
    return load_times(Path(__file__).resolve().parents[1] / path if path else None)


def load_times(path):
    if path is None:
        return {}, None
    document = json.loads(Path(path).read_text(encoding='utf-8'))
    if document['version'] != 1 or document['source_name'] != 'UFO-search':
        raise ValueError('Referencia temporal externa no soportada')
    entries = {}
    for item in document['times']:
        key = item['source_record_id']
        if not isinstance(key, str) or not key or key in entries:
            raise ValueError('Identificador externo vacío o duplicado')
        if not all(isinstance(item[name], str) for name in ('date_event_raw', 'time_raw')):
            raise ValueError('Campos de evidencia temporal inválidos')
        if type(item['single_date']) is not bool:
            raise ValueError('La evidencia debe declarar si hay fechas alternativas')
        entries[key] = item
    return entries, document['source']


def time_overrides(original, temporal, evidence, parser, reference):
    """Restore a source clock only on its own valid day, never on a partial date."""
    if evidence is None:
        return {}
    if original.get('date_event_raw') != evidence['date_event_raw']:
        raise ValueError('La fecha original difiere de la evidencia externa')
    raw_time = evidence['time_raw']
    existing = original.get('time_raw')
    if existing is not None and existing != raw_time:
        raise ValueError('La hora original difiere de la evidencia externa')
    overrides = {'time_raw': raw_time}
    _, calendar_overrides, forced, certainty, _ = temporal
    point = calendar_overrides.get('date_event', original.get('date_event'))
    parsed = parser(point, reference)
    if (forced or certainty not in ('source', 'coarsened') or parsed[1] != 'day'
            or parsed[2] != 'valid' or not evidence['single_date']
            or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?', raw_time)):
        return overrides
    candidate = parsed[0] + 'T' + raw_time
    old_clock = calendar_overrides.get('sighting_datetime', original.get('sighting_datetime'))
    old_parsed = parser(old_clock, reference)
    if old_parsed[1] in ('minute', 'second', 'fractional_second') and old_parsed[0] != candidate:
        raise ValueError('El timestamp existente contradice la hora de la fuente')
    overrides['sighting_datetime'] = candidate
    return overrides


def create_time_evidence(conn, entries):
    conn.execute('''CREATE TABLE source_time_evidence (
        sighting_id INTEGER PRIMARY KEY REFERENCES sighting(id),
        source_record_id TEXT NOT NULL UNIQUE,
        date_event_raw TEXT NOT NULL, time_raw TEXT NOT NULL,
        single_date INTEGER NOT NULL CHECK(single_date IN (0,1)),
        clock_applied INTEGER NOT NULL CHECK(clock_applied IN (0,1)))''')
    if not entries:
        return
    seen = set()
    for key, source_id, raw in conn.execute('''SELECT s.id,s.source_record_id,s.date_event_raw
            FROM sighting s JOIN source_database d ON d.id=s.source_db_id
            WHERE d.name='UFO-search' '''):
        item = entries.get(source_id)
        if item is None:
            continue
        if source_id in seen or raw != item['date_event_raw']:
            raise ValueError('Enlace externo ambiguo o fecha original distinta')
        seen.add(source_id)
        conn.execute('INSERT INTO source_time_evidence VALUES (?,?,?,?,?,0)',
                     (key,source_id,raw,item['time_raw'],int(item['single_date'])))


def policy_geography(policy):
    path = policy.get('source_geography_reference')
    if not path:
        return {}, None
    document = json.loads((Path(__file__).resolve().parents[1] / path).read_text(encoding='utf-8'))
    if document['version'] != 1 or document['source_name'] != 'UFO-search':
        raise ValueError('Referencia geográfica externa no soportada')
    entries = {}
    for item in document['geography']:
        key = item['source_record_id']
        if not isinstance(key,str) or not key or key in entries:
            raise ValueError('Identificador geográfico externo vacío o duplicado')
        if not isinstance(item['date_event_raw'],str) or not isinstance(item['country'],str):
            raise ValueError('Evidencia geográfica inválida')
        if any(type(item[name]) not in (int,float) or not math.isfinite(item[name])
               for name in ('latitude','longitude')):
            raise ValueError('Coordenada externa no finita')
        entries[key] = item
    return entries, document['source']


def valid_source_coordinates(item):
    # Out-of-range values (including the source's 90.000004 placeholder)
    # stay evidence. Never clamp them to a pole.
    return (not non_terrestrial(item) and -90 <= item['latitude'] <= 90
            and -180 <= item['longitude'] <= 180)


def non_terrestrial(item):
    return item['country'] in ('The Moon','Mars','Neptune','Pluto',
                              'Earth Orbit or seen from space stations/capsules')


def geography_settings(policy, countries):
    """Corroboration distance and multi-country catalogue labels (comparison only)."""
    settings = policy.get('source_geography_policy') or {}
    threshold = settings.get('corroboration_km')
    if threshold is None or not isinstance(threshold,(int,float)) or threshold <= 0:
        raise ValueError('La política geográfica externa requiere corroboration_km positivo')
    regions = {}
    for label, codes in (settings.get('region_members') or {}).items():
        if not codes or any(code not in countries.names for code in codes):
            raise ValueError(f'Región de catálogo con códigos desconocidos: {label}')
        regions[label] = frozenset(codes)
    return float(threshold), regions


def haversine_km(lat1, lng1, lat2, lng2):
    delta_lat = math.radians(lat2-lat1)
    delta_lng = math.radians(lng2-lng1)
    a = (math.sin(delta_lat/2)**2 + math.cos(math.radians(lat1))
         *math.cos(math.radians(lat2))*math.sin(delta_lng/2)**2)
    a = max(0.0, min(1.0, a))
    return 6371.0*2*math.atan2(math.sqrt(a), math.sqrt(1-a))


def bronze_pair(lat, lng):
    """Same completeness and range contract as Silver coordinates."""
    try:
        if lat is None or lng is None:
            return None
        left, right = float(lat), float(lng)
    except (TypeError, ValueError, OverflowError):
        return None
    if not (math.isfinite(left) and math.isfinite(right) and -90 <= left <= 90 and -180 <= right <= 180):
        return None
    return left, right


def geography_decision(item, pair, location_status, location_code, quarantined, countries, regions, threshold):
    """Compare a catalogue place with Bronze before it may enter canonical fields.

    External evidence only fills what Bronze lacks or corroborates what Bronze
    states. A contradiction is never resolved in favour of either side, and it
    never lifts a Bronze quarantine.
    """
    if non_terrestrial(item):
        return {'country_check':'non_terrestrial','coordinate_check':'non_terrestrial','distance':None}
    _, code, _ = countries.resolve(item['country'], None)
    members = frozenset([code]) if code else regions.get(item['country'])
    if not members:
        country = 'no_evidence'
    elif location_status == 'valid':
        country = 'corroborated' if location_code in members else 'conflict'
    elif location_status == 'conflict':
        country = 'bronze_conflict'
    else:
        country = 'fill' if code else 'no_evidence'
    distance = None
    if not valid_source_coordinates(item):
        coordinates = 'not_applied'
    elif pair is not None:
        distance = round(haversine_km(pair[0], pair[1], item['latitude'], item['longitude']), 1)
        if quarantined:
            coordinates = 'quarantined'
        else:
            coordinates = 'corroborated' if distance <= threshold else 'conflict'
    else:
        coordinates = 'conflict' if country == 'conflict' else 'fill'
    return {'country_check':country,'coordinate_check':coordinates,'distance':distance}


GEOGRAPHY_CHECKS = {
    'country_check': ('no_evidence','corroborated','conflict','bronze_conflict','fill','non_terrestrial'),
    'coordinate_check': ('not_applied','quarantined','corroborated','conflict','fill','non_terrestrial'),
}


def create_geography_evidence(conn, entries, countries):
    checks = {name: ','.join(f"'{value}'" for value in values) for name, values in GEOGRAPHY_CHECKS.items()}
    conn.execute(f'''CREATE TABLE source_geography_evidence (
        sighting_id INTEGER PRIMARY KEY REFERENCES sighting(id),
        source_record_id TEXT NOT NULL UNIQUE,date_event_raw TEXT NOT NULL,
        latitude REAL NOT NULL,longitude REAL NOT NULL,
        country_reported TEXT NOT NULL,country TEXT,country_iso2 TEXT,
        coordinate_domain TEXT NOT NULL CHECK(coordinate_domain IN ('terrestrial','non_terrestrial')),
        coordinates_applied INTEGER NOT NULL CHECK(coordinates_applied IN (0,1)),
        country_check TEXT CHECK(country_check IN ({checks['country_check']})),
        coordinate_check TEXT CHECK(coordinate_check IN ({checks['coordinate_check']})),
        bronze_distance_km REAL)''')
    if not entries:
        return
    seen=set()
    for key,source_id,raw in conn.execute('''SELECT s.id,s.source_record_id,s.date_event_raw
            FROM sighting s JOIN source_database d ON d.id=s.source_db_id
            WHERE d.name='UFO-search' '''):
        item=entries.get(source_id)
        if item is None:
            continue
        if source_id in seen or raw != item['date_event_raw']:
            raise ValueError('Enlace geográfico ambiguo o fecha original distinta')
        seen.add(source_id)
        name,code,_=countries.resolve(item['country'],None)
        conn.execute('INSERT INTO source_geography_evidence VALUES (?,?,?,?,?,?,?,?,?,0,NULL,NULL,NULL)',
                     (key,source_id,raw,item['latitude'],item['longitude'],item['country'],name,code,
                      'non_terrestrial' if non_terrestrial(item) else 'terrestrial'))


def decide_geography(conn, entries, countries, policy, quarantine, schema='main'):
    """Decision per linked report from Bronze coordinates and cleaned location country.

    Requires ``location`` to be cleaned already. ``quarantine`` holds the report
    IDs whose Bronze pair copies a location in country conflict.
    """
    if not entries:
        return {}
    threshold, regions = geography_settings(policy, countries)
    decisions = {}
    for key, source_id, lat, lng, status, code in conn.execute(f'''SELECT b.id,b.source_record_id,b.lat,b.lng,
            l.country_status,l.country_iso2 FROM bronze.sighting b
            JOIN source_database d ON d.id=b.source_db_id
            LEFT JOIN {schema}.location l ON l.id=b.location_id WHERE d.name='UFO-search' '''):
        item = entries.get(source_id)
        if item is None:
            continue
        decisions[key] = geography_decision(item, bronze_pair(lat, lng), status, code,
                                            key in quarantine, countries, regions, threshold)
    return decisions


def record_geography_decisions(conn, decisions):
    conn.executemany('''UPDATE source_geography_evidence SET coordinates_applied=?,country_check=?,
        coordinate_check=?,bronze_distance_km=? WHERE sighting_id=?''',
        [(int(item['coordinate_check']=='fill'),item['country_check'],item['coordinate_check'],item['distance'],key)
         for key,item in decisions.items()])


NUCLEAR_TYPES = ('military_base','national_lab','nuclear_test_site','test_range','nuclear_base')


def nuclear_facilities(conn):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='facility'").fetchone():
        return []
    return list(conn.execute('''SELECT id,name,latitude,longitude FROM facility
        WHERE facility_type IN (?,?,?,?,?) ORDER BY id''', NUCLEAR_TYPES))


def nearest_facility(latitude,longitude,facilities):
    """Same spherical distance, 6371 km radius and 0.1 km rounding as origin."""
    best=None
    for key,name,lat,lng in facilities:
        delta_lat=math.radians(lat-latitude)
        delta_lng=math.radians(lng-longitude)
        a=(math.sin(delta_lat/2)**2 + math.cos(math.radians(latitude))
           *math.cos(math.radians(lat))*math.sin(delta_lng/2)**2)
        a=max(0.0,min(1.0,a))
        distance=6371.0*2*math.atan2(math.sqrt(a),math.sqrt(1-a))
        candidate=(distance,key,name)
        if best is None or candidate[:2]<best[:2]:
            best=candidate
    return (round(best[0],1),best[2]) if best else (None,None)


COORDINATE_BASIS = {'non_terrestrial':'non_terrestrial','fill':'original_catalog_place',
                    'conflict':'source_conflict','corroborated':'bronze_corroborated'}


def validate_geography(conn, policy, countries, quarantine):
    """Replay every catalogue decision from Bronze, location and the pinned reference."""
    entries,_=policy_geography(policy)
    actual={r[0]:tuple(r[1:]) for r in conn.execute('SELECT * FROM source_geography_evidence')}
    decisions=decide_geography(conn,entries,countries,policy,quarantine)
    bad=0
    facilities=nuclear_facilities(conn)
    columns={r[1] for r in conn.execute('PRAGMA table_info(sighting)')}
    proximity={'distance_to_nearest_nuclear_site_km','nearest_nuclear_site_name'} <= columns
    distance_columns='s.distance_to_nearest_nuclear_site_km,s.nearest_nuclear_site_name' if proximity else 'NULL,NULL'
    query=f'''SELECT b.id,b.source_record_id,b.date_event_raw,b.lat,b.lng,s.lat,s.lng,s.coordinate_status,
        {distance_columns},a.canonical_country,a.canonical_country_iso2,a.country_status,a.country_basis,
        a.usable_for_country,a.coordinate_basis,l.country,l.country_iso2,l.country_status
        FROM bronze.sighting b JOIN source_database d ON d.id=b.source_db_id
        JOIN sighting s ON s.id=b.id JOIN sighting_analytical a ON a.id=s.id
        LEFT JOIN location l ON l.id=s.location_id WHERE d.name='UFO-search' '''
    counts={}
    for (key,source_id,raw,old_lat,old_lng,lat,lng,status,distance,site,country,code,country_status,
         basis,usable,coordinate_basis,location_country,location_code,location_status) in conn.execute(query):
        item=entries.get(source_id)
        if item is None:
            continue
        decision=decisions[key]
        counts[(decision['country_check'],decision['coordinate_check'])]=counts.get((decision['country_check'],decision['coordinate_check']),0)+1
        name,resolved,_=countries.resolve(item['country'],None)
        expected=(source_id,raw,item['latitude'],item['longitude'],item['country'],name,resolved,
                  'non_terrestrial' if non_terrestrial(item) else 'terrestrial',
                  int(decision['coordinate_check']=='fill'),decision['country_check'],
                  decision['coordinate_check'],decision['distance'])
        bad+=raw!=item['date_event_raw'] or actual.get(key)!=expected
        check=decision['coordinate_check']
        if check in ('non_terrestrial','conflict','quarantined'):
            bad+=(lat,lng,status)!=(None,None,'not_applicable' if check=='non_terrestrial' else 'review')
        elif check=='fill':
            bad+=(lat,lng,status)!=(item['latitude'],item['longitude'],'valid')
            if proximity:
                bad+=(distance,site)!=nearest_facility(lat,lng,facilities)
        elif check=='corroborated':
            bad+=(lat,lng,status)!=(*bronze_pair(old_lat,old_lng),'valid')
        bad+=coordinate_basis!=COORDINATE_BASIS.get(check,'bronze')
        country_check=decision['country_check']
        if country_check=='non_terrestrial':
            expected_country=(None,None,'not_applicable','non_terrestrial',0)
        elif country_check=='fill':
            expected_country=(name,resolved,'valid','original_catalog',1)
        elif country_check=='conflict':
            expected_country=(None,None,'conflict','source_conflict',0)
        else:
            state=location_status or 'missing'
            expected_country=(location_country,location_code,state,
                              'location_corroborated' if country_check=='corroborated' else 'location',int(state=='valid'))
        bad+=(country,code,country_status,basis,usable)!=expected_country
    bad+=len(set(actual)^set(decisions))
    return {'analytics_source_geography_replay':{'actual':bad,'expected':0,'passed':bad==0,
            'evidence_records':len(decisions),
            'decisions':{f'{country}/{coordinates}':count for (country,coordinates),count in sorted(counts.items())}}}
