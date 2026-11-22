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


def create_geography_evidence(conn, entries, countries):
    conn.execute('''CREATE TABLE source_geography_evidence (
        sighting_id INTEGER PRIMARY KEY REFERENCES sighting(id),
        source_record_id TEXT NOT NULL UNIQUE,date_event_raw TEXT NOT NULL,
        latitude REAL NOT NULL,longitude REAL NOT NULL,
        country_reported TEXT NOT NULL,country TEXT,country_iso2 TEXT,
        coordinate_domain TEXT NOT NULL CHECK(coordinate_domain IN ('terrestrial','non_terrestrial')),
        coordinates_applied INTEGER NOT NULL CHECK(coordinates_applied IN (0,1)))''')
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
        conn.execute('INSERT INTO source_geography_evidence VALUES (?,?,?,?,?,?,?,?,?,?)',
                     (key,source_id,raw,item['latitude'],item['longitude'],item['country'],name,code,
                      'non_terrestrial' if non_terrestrial(item) else 'terrestrial',
                      int(valid_source_coordinates(item))))


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


def validate_geography(conn, policy, countries):
    entries,_=policy_geography(policy)
    actual={r[0]:tuple(r[1:]) for r in conn.execute('SELECT * FROM source_geography_evidence')}
    expected_keys=set()
    bad=0
    facilities=nuclear_facilities(conn)
    columns={r[1] for r in conn.execute('PRAGMA table_info(sighting)')}
    proximity={'distance_to_nearest_nuclear_site_km','nearest_nuclear_site_name'} <= columns
    query='''SELECT b.id,b.source_record_id,b.date_event_raw,s.lat,s.lng,s.coordinate_status,
        a.canonical_country,a.canonical_country_iso2,a.country_status,a.country_basis,a.usable_for_country
        FROM bronze.sighting b JOIN source_database d ON d.id=b.source_db_id
        JOIN sighting s ON s.id=b.id JOIN sighting_analytical a ON a.id=s.id WHERE d.name='UFO-search' '''
    for key,source_id,raw,lat,lng,status,actual_name,actual_code,country_status,basis,usable in conn.execute(query):
        item=entries.get(source_id)
        if item is None:
            continue
        expected_keys.add(key)
        name,code,_=countries.resolve(item['country'],None)
        applied=valid_source_coordinates(item)
        expected=(source_id,raw,item['latitude'],item['longitude'],item['country'],name,code,
                  'non_terrestrial' if non_terrestrial(item) else 'terrestrial',int(applied))
        bad+=raw!=item['date_event_raw'] or actual.get(key)!=expected
        if non_terrestrial(item):
            bad+=(lat,lng,status)!=(None,None,'not_applicable')
            bad+=(actual_name,actual_code,country_status,basis,usable)!=(None,None,'not_applicable','original_catalog',0)
        elif item['country']:
            expected_status='valid' if code else 'unrecognized'
            bad+=(actual_name,actual_code,country_status,basis,usable)!=(name,code,expected_status,'original_catalog',int(code is not None))
        if applied:
            bad+=(lat,lng,status)!=(item['latitude'],item['longitude'],'valid')
            if proximity:
                current=conn.execute('SELECT distance_to_nearest_nuclear_site_km,nearest_nuclear_site_name FROM sighting WHERE id=?',(key,)).fetchone()
                bad+=current!=nearest_facility(lat,lng,facilities)
    bad+=len(set(actual)^expected_keys)
    return {'analytics_source_geography_replay':{'actual':bad,'expected':0,'passed':bad==0,
            'evidence_records':len(expected_keys)}}
