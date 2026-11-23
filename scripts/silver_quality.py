"""Deterministic Silver cleaning, issue tracking and conservative event grouping."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import hashlib
import json
import math
import re
import sqlite3

if __package__:
    from . import silver_analytics as analytics
    from . import silver_evidence as source_evidence
else:
    import silver_analytics as analytics
    import silver_evidence as source_evidence


RULES = {
    "source_coordinates_recovered": ("info", "Coordenadas del catálogo original del mismo informe, solo donde Bronze no tiene un par utilizable; enlace por ID único y fecha original."),
    "source_country_conflict": ("warning", "El país del catálogo original contradice el país de la ubicación de Bronze; país analítico desconocido."),
    "source_coordinate_conflict": ("warning", "El catálogo original contradice el par o el país de Bronze; ninguna representación se publica y ambas se conservan."),
    "source_proximity_recomputed": ("info", "Proximidad recalculada con coordenadas recuperadas y el catálogo nuclear conservado."),
    "source_time_recovered": ("info", "Hora recuperada por ID único y fecha original idéntica; timestamp solo con día y hora exactos."),
    "geographic_dependency": ("warning", "Medida derivada de coordenadas no utilizables; conservar original y retirar del campo canónico."),
    "temporal_recovered": ("info", "Recuperar únicamente precisión explícita en date_event_raw; no imputar días."),
    "temporal_range": ("info", "Intervalo explícito conservado sin elegir una fecha representativa."),
    "temporal_conflict": ("warning", "Representaciones temporales contradictorias o calificadas; conservar evidencia."),
    "temporal_unsupported": ("warning", "El año canónico no aparece en date_event_raw; fecha conservada fuera del calendario."),
    "text_whitespace": ("info", "Recortar espacios exteriores; texto vacío pasa a NULL."),
    "missing_token": ("info", "Marcador de ausencia explícito de una columna pasa a NULL."),
    "date_missing": ("warning", "Fecha desconocida; no se imputa."),
    "date_invalid": ("error", "Fecha no interpretable o imposible en el calendario."),
    "date_suspect": ("warning", "Fecha centinela UFOCAT 0019 o posterior a la referencia; requiere revisión."),
    "date_format": ("info", "Normalizar formato sin inventar precisión ni zona horaria."),
    "coordinate_invalid": ("error", "Par de coordenadas incompleto, no numérico o fuera de rango."),
    "coordinate_country_conflict": ("warning", "Representaciones del país contradictorias; coordenadas en revisión."),
    "country_conflict": ("warning", "Las dos representaciones del país discrepan; país canónico desconocido."),
    "country_unrecognized": ("warning", "País ambiguo, histórico o fuera del catálogo; requiere revisión."),
    "country_normalized": ("info", "País normalizado mediante catálogo y alias explícitos."),
    "numeric_invalid": ("error", "Valor incompatible con el tipo, la unidad o el rango permitido."),
    "numeric_cast": ("info", "Conversión numérica exacta sin pérdida de información."),
    "size_estimate": ("warning", "Medida aproximada; se conserva la marca de incertidumbre."),
    "json_invalid": ("error", "JSON mal formado, tipo incorrecto o valores de emoción inválidos."),
    "enum_invalid": ("warning", "Categoría fuera del contrato declarado."),
    "duplicate_exact": ("info", "Coincidencia estricta de fecha/hora, coordenadas, forma y descriptores."),
    "duplicate_review": ("warning", "Candidato sin evidencia suficiente para confirmar equivalencia."),
}


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def encoded(value):
    if isinstance(value, float) and not math.isfinite(value):
        value = str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def same(left, right):
    return type(left) is type(right) and left == right


def table_columns(conn, table):
    return {row[1]: row for row in conn.execute(f"PRAGMA table_info({quote(table)})")}


def create_audit(conn, lineage):
    conn.executescript("""
        CREATE TABLE quality_rule (
            rule_id TEXT PRIMARY KEY, severity TEXT NOT NULL,
            description TEXT NOT NULL
        );
        CREATE TABLE quality_issue (
            table_name TEXT NOT NULL, record_id TEXT NOT NULL,
            column_name TEXT NOT NULL, rule_id TEXT NOT NULL REFERENCES quality_rule(rule_id),
            action TEXT NOT NULL CHECK(action IN ('normalized','nullified','review','flagged')),
            raw_value TEXT NOT NULL CHECK(json_valid(raw_value)),
            message TEXT NOT NULL,
            PRIMARY KEY(table_name,record_id,column_name,rule_id)
        );
        CREATE TABLE silver_change (
            table_name TEXT NOT NULL, record_id TEXT NOT NULL, column_name TEXT NOT NULL,
            old_value TEXT NOT NULL CHECK(json_valid(old_value)),
            new_value TEXT NOT NULL CHECK(json_valid(new_value)),
            rule_id TEXT NOT NULL REFERENCES quality_rule(rule_id),
            PRIMARY KEY(table_name,record_id,column_name)
        );
        CREATE TABLE silver_run (run_id TEXT PRIMARY KEY, metadata TEXT NOT NULL CHECK(json_valid(metadata)));
        CREATE INDEX idx_quality_issue_rule ON quality_issue(rule_id,action);
        CREATE INDEX idx_quality_issue_record ON quality_issue(table_name,record_id);
    """)
    conn.executemany("INSERT INTO quality_rule VALUES (?,?,?)", [(rule, *detail) for rule, detail in RULES.items()])
    conn.execute("INSERT INTO silver_run VALUES (?,?)", (lineage["run_id"], encoded(lineage)))


class Audit:
    def __init__(self, conn):
        self.conn = conn
        self.issues = []
        self.changes = []

    def issue(self, table, key, column, rule, value, message, action="review"):
        self.issues.append((table, str(key), column, rule, action, encoded(value), message))

    def change(self, table, key, column, old, new, rule):
        if not same(old, new):
            self.changes.append((table, str(key), column, encoded(old), encoded(new), rule))

    def flush(self):
        self.conn.executemany("INSERT OR IGNORE INTO quality_issue VALUES (?,?,?,?,?,?,?)", self.issues)
        self.conn.executemany("INSERT INTO silver_change VALUES (?,?,?,?,?,?)", self.changes)
        self.issues.clear()
        self.changes.clear()


@lru_cache(maxsize=65536)
def parse_date(value, reference, suspect_century=False):
    """Return canonical value, precision, status, timezone status and year.

    Partial dates stay partial. Timezone offsets are retained, never inferred.
    """
    if value is None or isinstance(value, str) and not value.strip():
        return None, "unknown", "missing", "unknown", None
    text = str(value).strip()
    try:
        if re.fullmatch(r"\d{4}", text):
            year = int(text)
            date(year, 1, 1)
            normalized, precision, temporal = text, "year", date(year, 1, 1)
            zone = "not_applicable"
        elif re.fullmatch(r"\d{4}-\d{2}", text):
            temporal = date.fromisoformat(text + "-01")
            year, normalized, precision, zone = temporal.year, text, "month", "not_applicable"
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            temporal = date.fromisoformat(text)
            year, normalized, precision, zone = temporal.year, temporal.isoformat(), "day", "not_applicable"
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})?", text):
            offset = re.search(r'[+-](\d{2}):(\d{2})$',text)
            if offset and (int(offset[1])>23 or int(offset[2])>59):
                raise ValueError('invalid UTC offset')
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            temporal, year = parsed.date(), parsed.year
            clock = re.split(r"Z|[+-]", text[11:])[0]
            precision = "fractional_second" if "." in clock else "second" if clock.count(":") == 2 else "minute"
            normalized = parsed.isoformat(timespec={"fractional_second": "microseconds", "second": "seconds", "minute": "minutes"}[precision])
            if precision=='fractional_second':
                digits=len(clock.split('.')[1])
                normalized=re.sub(r'\.(\d{6})',lambda m:'.'+m[1][:digits],normalized,count=1)
            zone = "offset_known" if parsed.utcoffset() is not None else "unspecified"
        else:
            raise ValueError("unsupported format")
        # Compare at the precision actually supplied: no synthetic day/hour.
        limit = date.fromisoformat(reference)
        future = year > limit.year if precision == "year" else (year, temporal.month) > (limit.year, limit.month) if precision == "month" else temporal > limit
        if future or suspect_century and text.startswith("0019-"):
            # No canonical value: a precision label without a value is not information.
            return None, "unknown", "review", "unknown", None
        return normalized, precision, "valid", zone, year
    except (ValueError, TypeError, OverflowError):
        return None, "unknown", "invalid", "unknown", None


def coordinate_pair(lat, lng):
    if lat is None and lng is None:
        return None, None, "missing"
    if lat is None or lng is None:
        return None, None, "partial"
    try:
        left, right = float(lat), float(lng)
        if not math.isfinite(left) or not math.isfinite(right) or not (-90 <= left <= 90 and -180 <= right <= 180):
            raise ValueError()
        return left, right, "valid"
    except (ValueError, TypeError, OverflowError):
        return None, None, "invalid"


class Countries:
    def __init__(self, reference):
        self.names = {}
        self.lookup = {}
        for country in reference["countries"] + reference.get("additional_iso_entries", []):
            code = country["alpha2"]
            self.names[code] = country["name"]
            for value in (code, country["name"], country["alpha3"]):
                self.lookup[value.casefold()] = code
        for alias, code in reference.get("aliases", {}).items():
            if code not in self.names:
                raise ValueError(f"Alias de país sin referencia: {alias}={code}")
            self.lookup[alias.casefold()] = code

    def resolve(self, country, iso2):
        raw = country.strip() if isinstance(country, str) else country
        secondary = iso2.strip().upper() if isinstance(iso2, str) else iso2
        # NA is Namibia, not a missing-value marker. Historical countries are not
        # assigned to a modern successor without record-specific evidence.
        missing = raw is None or str(raw).casefold() in ("", "null", "unknown", "n/a", "none")
        primary = self.lookup.get(str(raw).casefold()) if not missing else None
        valid_secondary = secondary if secondary in self.names else None
        if not missing and not primary:
            return None, None, "unrecognized"
        if secondary and not valid_secondary:
            return None, None, "unrecognized"
        if primary and valid_secondary and primary != valid_secondary:
            return None, None, "conflict"
        code = primary or valid_secondary
        return (self.names[code], code, "valid") if code else (None, None, "missing")


def numeric_specs(table, names):
    specs = {}
    if table == "sighting":
        specs.update({name: (0, None, True) for name in names if name.startswith("nrc_")})
        specs.update({name: (0, 1, False) for name in names if name.startswith("emotion_7_") and name != "emotion_7_dominant"})
        specs.update({"duration_seconds": (0, None, True), "num_witnesses": (0, None, True),
                      "quality_score": (0, 100, True), "richness_score": (0, None, True),
                      "hoax_likelihood": (0, 1, False), "sentiment_score": (-1, 1, False),
                      "vader_compound": (-1, 1, False), "roberta_sentiment": (-1, 1, False),
                      "distance_to_nearest_nuclear_site_km": (0, None, False)})
        specs.update({name: (0, 1, True) for name in ("has_description", "has_media", "has_movement_mentioned")})
    elif table == "nuclear_encounter":
        specs["missiles_affected"] = (0, None, True)
    elif table == "crash_retrieval":
        specs["has_biologics"] = (0, 1, True)
    return {name: spec for name, spec in specs.items() if name in names}


def number(value, low, high, integer):
    if value is None:
        return None, True
    try:
        result = Decimal(str(value)) if integer else float(value)
        finite = result.is_finite() if integer else math.isfinite(result)
        if not finite or result < low or high is not None and result > high or integer and (result != result.to_integral_value() or result > 2**63-1):
            raise ValueError()
        return (int(result) if integer else result), True
    except (ValueError, TypeError, OverflowError, InvalidOperation):
        return None, False


JSON_FIELDS = {
    "sighting": {"movement_categories": list, "audit_location_fix": dict},
    "sighting_analysis": {"behavior_tags": list, "color_list": list, "emotion_scores": dict, "hoax_flags": list},
    "crash_retrieval": {"raw_json": dict},
    "nuclear_encounter": {"sensor_confirmation": list, "raw_json": dict},
}


@lru_cache(maxsize=8192)
def valid_json(value, expected, emotion=False):
    try:
        parsed = json.loads(value, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        if not isinstance(parsed, expected):
            return False
        if expected is list and not all(isinstance(item, str) for item in parsed):
            return False
        if emotion:
            return all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in parsed.values())
        return True
    except (ValueError, TypeError):
        return False


def clean_table(conn, table, policy, countries, source_names, coordinate_reviews=None, source_times=None, source_geography=None, geography_decisions=None):
    names = table_columns(conn, table)
    original_names = list(names)
    key_names = [name for name, col in names.items() if col[5]]
    if len(key_names) != 1:
        raise ValueError(f"La limpieza exige una clave simple estable: {table}")
    key_name = key_names[0]
    extra = {}
    if "date_event" in names:
        extra.update(date_precision="TEXT", date_status="TEXT", event_year="INTEGER")
    if table == "sighting" and policy.get("analytical_contract"):
        extra["date_certainty"] = "TEXT"
    if "sighting_datetime" in names:
        extra.update(datetime_precision="TEXT", timezone_status="TEXT")
    lat_name, lng_name = ("lat", "lng") if table == "sighting" else ("latitude", "longitude")
    has_coords = lat_name in names and lng_name in names
    if has_coords:
        extra["coordinate_status"] = "TEXT"
    if table in ("location", "crash_retrieval", "nuclear_encounter") and "country" in names:
        extra["country_status"] = "TEXT"
        if "country_iso2" not in names:
            extra["country_iso2"] = "TEXT"
    if table == "crash_retrieval" and "craft_size_m" in names:
        extra["craft_size_status"] = "TEXT"
    for name, kind in extra.items():
        conn.execute(f"ALTER TABLE {quote(table)} ADD COLUMN {quote(name)} {kind}")
    text_columns = set(policy["text_columns"].get(table, [])) & names.keys()
    missing_tokens = policy.get("missing_tokens", {}).get(table, {})
    text_columns |= missing_tokens.keys() & names.keys()
    if table == "sighting":
        text_columns |= policy.get("enums", {}).keys() & names.keys()
    specs = numeric_specs(table, names)
    json_fields = {name: kind for name, kind in JSON_FIELDS.get(table, {}).items() if name in names}
    writable = [name for name in original_names if name in text_columns or name in specs or name in json_fields or name in ("date_event", "sighting_datetime", lat_name, lng_name, "craft_size_m")]
    if table == 'sighting' and 'time_raw' in names and 'time_raw' not in writable:
        writable.append('time_raw')
    if "country" in names and "country_status" in extra:
        writable += [name for name in ("country", "country_iso2") if name in names and name not in writable]
    geographic_dependencies = [name for name in ('distance_to_nearest_nuclear_site_km','nearest_nuclear_site_name') if table=='sighting' and name in names]
    writable += [name for name in geographic_dependencies if name not in writable]
    writable += list(extra)
    sql_update = f"UPDATE {quote(table)} SET " + ",".join(f"{quote(name)}=?" for name in writable) + f" WHERE {quote(key_name)}=?"
    cursor = conn.execute(f"SELECT * FROM {quote(table)} ORDER BY {quote(key_name)}")
    row_names = [col[0] for col in cursor.description]
    audit = Audit(conn)
    facilities = source_evidence.nuclear_facilities(conn) if table=='sighting' and geography_decisions else []
    processed = changed_rows = 0
    while batch := cursor.fetchmany(2048):
        updates = []
        for values in batch:
            original = dict(zip(row_names, values))
            row = original.copy()
            key = row[key_name]
            rules = {}
            for name in sorted(text_columns):
                if isinstance(row[name], str):
                    row[name] = row[name].strip() or None
                    if not same(row[name], original[name]):
                        rules[name] = "text_whitespace"
                        audit.issue(table, key, name, "text_whitespace", original[name], "Texto exterior normalizado.", "normalized")
            for name, tokens in missing_tokens.items():
                if name in names and isinstance(row[name], str) and row[name].casefold() in tokens:
                    row[name] = None
                    rules[name] = "missing_token"
                    audit.issue(table, key, name, "missing_token", original[name], "Marcador de ausencia reconocido para esta columna.", "normalized")
            for name, spec in specs.items():
                row[name], valid = number(row[name], *spec)
                if not valid:
                    rules[name] = "numeric_invalid"
                    audit.issue(table, key, name, "numeric_invalid", original[name], "Valor fuera del contrato numérico.", "nullified")
                elif not same(row[name], original[name]):
                    rules[name] = "numeric_cast"
            for name, expected in json_fields.items():
                if row[name] is not None and not valid_json(row[name], expected, name == "emotion_scores"):
                    row[name] = None
                    rules[name] = "json_invalid"
                    audit.issue(table, key, name, "json_invalid", original[name], "JSON no utilizable según su contrato.", "nullified")
            for name, allowed in policy.get("enums", {}).items():
                if table == "sighting" and name in names and row[name] is not None and row[name] not in allowed:
                    row[name] = None
                    rules[name] = "enum_invalid"
                    audit.issue(table, key, name, "enum_invalid", original[name], "Categoría desconocida; revisar fuente.", "nullified")
            temporal = None
            if table == 'sighting' and policy.get('analytical_contract'):
                suspect = source_names.get(row.get('source_db_id')) == 'UFOCAT'
                temporal = analytics.temporal_decision(original, parse_date, policy['reference_date'], suspect)
                evidence, overrides, forced, certainty, relevant = temporal
                row.update(overrides)
                row['date_certainty'] = certainty
                if relevant:
                    applied = any(not same(original.get(name),value) for name,value in overrides.items())
                    conn.execute('INSERT INTO temporal_evidence VALUES (?,?,?,?,?,?,?)',
                        (key,original.get('date_event_raw'),evidence['kind'],evidence['candidate'],
                         evidence['year_min'],evidence['year_max'],int(applied)))
                source_item = (source_times or {}).get(original.get('source_record_id')) if source_names.get(row.get('source_db_id')) == 'UFO-search' else None
                source_overrides = source_evidence.time_overrides(original, temporal, source_item, parse_date, policy['reference_date'])
                row.update(source_overrides)
                if source_overrides:
                    rules['time_raw'] = 'source_time_recovered'
                    conn.execute('UPDATE source_time_evidence SET clock_applied=? WHERE sighting_id=?',
                                 (int('sighting_datetime' in source_overrides),key))
                    audit.issue(table,key,'time_raw','source_time_recovered',original.get('time_raw'),
                                'Hora del registro original, enlazado por identificador y fecha sin cambios.', 'normalized')
            else:
                source_overrides = {}
            for name in ("date_event", "sighting_datetime"):
                if name not in names:
                    continue
                suspect = source_names.get(row.get("source_db_id")) == "UFOCAT"
                normalized, precision, status, zone, year = parse_date(row[name], policy["reference_date"], suspect)
                if temporal and temporal[2]:
                    status = temporal[2]
                    normalized, year, zone = None, None, 'not_applicable'
                    precision = 'year_range' if status=='range' else 'unknown'
                row[name] = normalized
                if name == "date_event":
                    row.update(date_precision=precision, date_status=status, event_year=year)
                else:
                    row.update(datetime_precision=precision, timezone_status=zone)
                if name in source_overrides:
                    rules[name] = 'source_time_recovered'
                    audit.issue(table,key,name,'source_time_recovered',original[name],
                                'Día válido y hora exacta del mismo registro original; zona no inferida.', 'normalized')
                elif temporal and (name in temporal[1] or temporal[0]['kind'] in ('qualified','unsupported')):
                    kind = temporal[0]['kind']
                    rule = 'temporal_range' if status=='range' else 'temporal_unsupported' if kind=='unsupported' else 'temporal_conflict' if kind in ('conflict','qualified') else 'temporal_recovered'
                    rules[name] = rule
                    audit.issue(table,key,name,rule,original[name],
                                encoded({'date_event_raw':original.get('date_event_raw'),'interpretation':temporal[0]}),
                                'review' if rule in ('temporal_conflict','temporal_unsupported') else 'flagged')
                elif status != "valid":
                    rule = {"missing": "date_missing", "invalid": "date_invalid", "review": "date_suspect", "range":"temporal_range"}[status]
                    audit.issue(table, key, name, rule, original[name], "No se infiere ni corrige una fecha sin evidencia.", "flagged" if status == "missing" else "review")
                    rules[name] = rule
                elif not same(row[name], original[name]):
                    rules[name] = "date_format"
            if has_coords:
                source_place = (source_geography or {}).get(original.get('source_record_id')) if table=='sighting' and source_names.get(row.get('source_db_id'))=='UFO-search' else None
                decision = (geography_decisions or {}).get(key) if source_place is not None else None
                if source_place is not None and decision is None:
                    raise ValueError(f'Evidencia geográfica sin decisión: {table}.{key}')
                check = decision['coordinate_check'] if decision else None
                geography_applied = check == 'fill'
                source_nonterrestrial = check == 'non_terrestrial'
                if geography_applied:
                    if source_place['date_event_raw'] != original.get('date_event_raw'):
                        raise ValueError('La fecha difiere de la evidencia geográfica')
                    row[lat_name],row[lng_name]=source_place['latitude'],source_place['longitude']
                elif source_nonterrestrial:
                    row[lat_name],row[lng_name]=None,None
                row[lat_name], row[lng_name], status = coordinate_pair(row[lat_name], row[lng_name])
                if source_nonterrestrial:
                    status='not_applicable'
                row["coordinate_status"] = status
                if status in ("invalid", "partial"):
                    if names[lat_name][3] or names[lng_name][3]:
                        raise ValueError(f"Coordenadas obligatorias inválidas: {table}.{key}")
                    audit.issue(table, key, f"{lat_name},{lng_name}", "coordinate_invalid", [original[lat_name], original[lng_name]], "El par no es apto para análisis geográfico.", "nullified")
                    rules.update({lat_name: "coordinate_invalid", lng_name: "coordinate_invalid"})
                else:
                    rules.update({lat_name: "numeric_cast", lng_name: "numeric_cast"})
                if geography_applied or source_nonterrestrial:
                    rules.update({lat_name:'source_coordinates_recovered',lng_name:'source_coordinates_recovered'})
                    audit.issue(table,key,f'{lat_name},{lng_name}','source_coordinates_recovered',
                                [original[lat_name],original[lng_name]],
                                'Localización del catálogo original: '+('fuera de la superficie terrestre; mapa no aplicable.' if source_nonterrestrial else 'lugar catalogado donde Bronze no tenía un par utilizable; no acredita una posición exacta del testigo.'), 'normalized')
                elif check == 'conflict':
                    row[lat_name], row[lng_name], row["coordinate_status"] = None, None, "review"
                    rules.update({lat_name:'source_coordinate_conflict',lng_name:'source_coordinate_conflict'})
                    audit.issue(table,key,f'{lat_name},{lng_name}','source_coordinate_conflict',
                                [original[lat_name],original[lng_name]],
                                encoded({'catalog_latitude':source_place['latitude'],'catalog_longitude':source_place['longitude'],
                                         'catalog_country':source_place['country'],'distance_km':decision['distance'],
                                         'country_check':decision['country_check']}), 'review')
                if decision and decision['country_check'] == 'conflict':
                    audit.issue(table,key,'source_catalog_country','source_country_conflict',source_place['country'],
                                'País del catálogo original incompatible con el país de la ubicación de Bronze; no se elige ninguno.', 'review')
            else:
                geography_applied = False
            if has_coords and not geography_applied and row["coordinate_status"] == "valid" and key in (coordinate_reviews or {}):
                if names[lat_name][3] or names[lng_name][3]:
                    raise ValueError(f"Coordenadas obligatorias en conflicto: {table}.{key}")
                row[lat_name], row[lng_name], row["coordinate_status"] = None, None, "review"
                rule = "coordinate_country_conflict"
                rules.update({lat_name: rule, lng_name: rule})
                audit.issue(table, key, f"{lat_name},{lng_name}", rule,
                            [original[lat_name], original[lng_name]],
                            coordinate_reviews[key], "review")
            if geographic_dependencies and row['coordinate_status']!='valid':
                for name in geographic_dependencies:
                    if row[name] is not None:
                        row[name]=None
                        rules[name]='geographic_dependency'
                        audit.issue(table,key,name,'geographic_dependency',original[name],
                            'Medida de origen dependiente de un par de coordenadas no utilizable: '+row['coordinate_status'],'review')
            if geography_applied and geographic_dependencies:
                distance,site=source_evidence.nearest_facility(row[lat_name],row[lng_name],facilities)
                for name,value in (('distance_to_nearest_nuclear_site_km',distance),('nearest_nuclear_site_name',site)):
                    if name in geographic_dependencies:
                        row[name]=value
                        rules[name]='source_proximity_recomputed'
                        audit.issue(table,key,name,'source_proximity_recomputed',original[name],
                                    'Haversine, radio 6371 km, catálogo nuclear local y redondeo a 0,1 km.', 'normalized')
            if "country_status" in extra:
                row["country"], row["country_iso2"], status = countries.resolve(row["country"], row.get("country_iso2"))
                row["country_status"] = status
                rule = "country_conflict" if status == "conflict" else "country_unrecognized" if status == "unrecognized" else "country_normalized"
                rules.update(country=rule, country_iso2=rule)
                if status in ("conflict", "unrecognized"):
                    audit.issue(table, key, "country,country_iso2", rule, [original["country"], original.get("country_iso2")], "País canónico pendiente de evidencia adicional.")
            if "craft_size_status" in extra:
                value = original["craft_size_m"]
                if isinstance(value, str) and value.strip().startswith("~"):
                    match = re.match(r"~\s*(\d+(?:\.\d+)?)(?:\s|$|\()", value.strip())
                    if match:
                        row["craft_size_m"] = float(match.group(1))
                        row["craft_size_status"] = "approximate"
                        rules["craft_size_m"] = "size_estimate"
                        audit.issue(table, key, "craft_size_m", "size_estimate", value, "Estimación en metros; no tratar como medida exacta.", "flagged")
                    else:
                        row["craft_size_m"], row["craft_size_status"] = None, "unquantified"
                        rules["craft_size_m"] = "numeric_invalid"
                elif value is None or isinstance(value, str) and not value.strip():
                    row["craft_size_m"], row["craft_size_status"] = None, "missing"
                    rules["craft_size_m"] = "text_whitespace"
                else:
                    row["craft_size_m"], valid = number(value, 0, None, False)
                    row["craft_size_status"] = "exact" if valid else "unquantified"
                    rules["craft_size_m"] = "numeric_cast" if valid else "numeric_invalid"
                if row["craft_size_status"] == "unquantified":
                    audit.issue(table, key, "craft_size_m", "numeric_invalid", value, "Descripción sin una magnitud cuantificable; se conserva en la incidencia.", "review")
            changed = False
            for name in original_names:
                if name in writable and not same(row[name], original[name]):
                    audit.change(table, key, name, original[name], row[name], rules[name])
                    changed = True
            if changed or extra:
                updates.append(tuple(row[name] for name in writable) + (key,))
            processed += 1
            changed_rows += changed
        conn.executemany(sql_update, updates)
        audit.flush()
    print(f"Calidad {table}: {processed:,} registros; {changed_rows:,} con campos normalizados.", flush=True)
    return {"rows": processed, "changed_rows": changed_rows, "added_columns": list(extra)}


def group_duplicates(conn, policy):
    """Create reversible event membership; never delete reports or source IDs."""
    conn.executescript("""
        CREATE TEMP TABLE dedup_key (sighting_id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL);
        CREATE TABLE duplicate_group (
            canonical_event_id INTEGER PRIMARY KEY REFERENCES sighting(id),
            fingerprint TEXT NOT NULL UNIQUE, member_count INTEGER NOT NULL CHECK(member_count>1),
            rule_id TEXT NOT NULL REFERENCES quality_rule(rule_id)
        );
        CREATE TABLE event_membership (
            sighting_id INTEGER PRIMARY KEY REFERENCES sighting(id),
            canonical_event_id INTEGER NOT NULL REFERENCES sighting(id),
            match_status TEXT NOT NULL CHECK(match_status IN ('unique','confirmed_exact'))
        );
        CREATE INDEX idx_event_membership_canonical ON event_membership(canonical_event_id);
        CREATE TABLE duplicate_resolution (
            candidate_id INTEGER PRIMARY KEY REFERENCES duplicate_candidate(id),
            decision TEXT NOT NULL CHECK(decision IN ('confirmed_exact','needs_review','invalid_pair')),
            rule_id TEXT NOT NULL REFERENCES quality_rule(rule_id),
            reason TEXT NOT NULL
        );
    """)
    descriptors = ["color", "duration_seconds", "num_witnesses", "sound", "direction", "hynek", "vallee", "event_type", "weather", "terrain"]
    existing = table_columns(conn, "sighting")
    descriptors = [name for name in descriptors if name in existing]
    requested = ["id", "sighting_datetime", "datetime_precision", "coordinate_status", "lat", "lng", "standardized_shape", "time_raw"] + descriptors
    if "date_certainty" in existing:
        requested.append("date_certainty")
    if set(requested) - existing.keys():
        raise ValueError("Faltan campos para la deduplicación conservadora")
    def meaningful(value):
        return value is not None and str(value).strip().casefold() not in ("", "unknown", "other", "n/a", "?", "unidentified")
    def normalized(value):
        return value.strip().casefold() if isinstance(value, str) else value
    cursor = conn.execute("SELECT " + ",".join(quote(name) for name in requested) + " FROM sighting ORDER BY id")
    eligible = 0
    while batch := cursor.fetchmany(4096):
        keys = []
        for values in batch:
            row = dict(zip(requested, values))
            if row["datetime_precision"] not in ("minute", "second", "fractional_second") or not row["sighting_datetime"]:
                continue
            if row.get("date_certainty","source") not in ("source","coarsened"):
                continue
            if row["coordinate_status"] != "valid" or not meaningful(row["standardized_shape"]):
                continue
            if policy.get("require_time_raw", True) and not meaningful(row["time_raw"]):
                continue
            if sum(meaningful(row[name]) for name in descriptors) < policy["minimum_additional_descriptors"]:
                continue
            # Include every descriptor, including missingness, to avoid merging
            # records with contradictory detail. Similarity scores alone never merge.
            fingerprint = encoded([row["sighting_datetime"], row["lat"], row["lng"], normalized(row["standardized_shape"])] + [normalized(row[name]) for name in descriptors])
            keys.append((row["id"], hashlib.sha256(fingerprint.encode()).hexdigest()))
        conn.executemany("INSERT INTO dedup_key VALUES (?,?)", keys)
        eligible += len(keys)
    conn.execute("CREATE INDEX temp.idx_dedup_key ON dedup_key(fingerprint)")
    conn.execute("""INSERT INTO duplicate_group
        SELECT MIN(sighting_id),fingerprint,COUNT(*),'duplicate_exact'
        FROM dedup_key GROUP BY fingerprint HAVING COUNT(*)>1""")
    conn.execute("""INSERT INTO event_membership
        SELECT s.id,COALESCE(g.canonical_event_id,s.id),
               CASE WHEN g.canonical_event_id IS NULL THEN 'unique' ELSE 'confirmed_exact' END
        FROM sighting s LEFT JOIN dedup_key k ON k.sighting_id=s.id
        LEFT JOIN duplicate_group g ON g.fingerprint=k.fingerprint""")
    conn.execute("""INSERT INTO duplicate_resolution
        SELECT c.id,
            CASE WHEN c.sighting_id_a=c.sighting_id_b THEN 'invalid_pair'
                 WHEN a.canonical_event_id=b.canonical_event_id THEN 'confirmed_exact'
                 ELSE 'needs_review' END,
            CASE WHEN c.sighting_id_a!=c.sighting_id_b AND a.canonical_event_id=b.canonical_event_id
                 THEN 'duplicate_exact' ELSE 'duplicate_review' END,
            CASE WHEN c.sighting_id_a=c.sighting_id_b THEN 'El candidato enlaza el mismo registro.'
                 WHEN a.canonical_event_id=b.canonical_event_id THEN 'Coincidencia estricta verificable; informes originales conservados.'
                 ELSE 'Evidencia insuficiente o descriptores distintos; no se fusiona.' END
        FROM duplicate_candidate c
        JOIN event_membership a ON a.sighting_id=c.sighting_id_a
        JOIN event_membership b ON b.sighting_id=c.sighting_id_b""")
    audit = Audit(conn)
    cursor = conn.execute("""SELECT c.id,c.status,c.sighting_id_a,c.sighting_id_b,r.decision,r.rule_id,r.reason
        FROM duplicate_candidate c JOIN duplicate_resolution r ON r.candidate_id=c.id ORDER BY c.id""")
    while batch := cursor.fetchmany(4096):
        changes = []
        for key, old, left, right, decision, rule, reason in batch:
            if decision == "confirmed_exact":
                changes.append((decision, key))
                audit.change("duplicate_candidate", key, "status", old, decision, rule)
            audit.issue("duplicate_candidate", key, "sighting_id_a,sighting_id_b", rule, [left, right], reason, "flagged" if decision == "confirmed_exact" else "review")
        conn.executemany("UPDATE duplicate_candidate SET status=? WHERE id=?", changes)
        audit.flush()
    groups = conn.execute("SELECT COUNT(*),COALESCE(SUM(member_count-1),0) FROM duplicate_group").fetchone()
    decisions = dict(conn.execute("SELECT decision,COUNT(*) FROM duplicate_resolution GROUP BY decision"))
    conn.executescript("""
        CREATE VIEW sighting_canonical AS
            SELECT s.* FROM sighting s JOIN event_membership m ON m.sighting_id=s.id
            WHERE m.canonical_event_id=s.id;
        CREATE VIEW sighting_for_map AS SELECT * FROM sighting_canonical WHERE coordinate_status='valid';
        CREATE VIEW sighting_for_time_analysis AS SELECT * FROM sighting_canonical WHERE date_status='valid';
        CREATE VIEW duplicate_review AS
            SELECT c.*,r.decision,r.reason FROM duplicate_candidate c
            JOIN duplicate_resolution r ON r.candidate_id=c.id WHERE r.decision!='confirmed_exact';
        CREATE VIEW quality_review AS SELECT * FROM quality_issue WHERE action='review';
        CREATE VIEW reused_source_key AS
            SELECT source_db_id,source_record_id,COUNT(*) AS record_count FROM sighting
            WHERE source_record_id IS NOT NULL GROUP BY source_db_id,source_record_id HAVING COUNT(*)>1;
    """)
    return {"eligible_records": eligible, "confirmed_groups": groups[0], "reports_grouped": groups[1], "candidate_decisions": decisions, "method": policy["method"]}


def verify_change_ledger(conn, layouts):
    """Independently reconcile every changed source field with its old/new values."""
    expected = {}
    for table, key, column, old, new in conn.execute("SELECT table_name,record_id,column_name,old_value,new_value FROM silver_change"):
        expected[(table, key, column)] = (json.loads(old), json.loads(new))
    seen = set()
    for table, layout in layouts.items():
        names = [col[1] for col in layout]
        keys = [col[1] for col in layout if col[5]]
        if len(keys) != 1:
            raise ValueError(f"Clave no soportada para reconciliar {table}")
        key = keys[0]
        missing = conn.execute(f"SELECT 1 FROM bronze.{quote(table)} b LEFT JOIN main.{quote(table)} s ON s.{quote(key)}=b.{quote(key)} WHERE s.{quote(key)} IS NULL LIMIT 1").fetchone()
        extra = conn.execute(f"SELECT 1 FROM main.{quote(table)} s LEFT JOIN bronze.{quote(table)} b ON b.{quote(key)}=s.{quote(key)} WHERE b.{quote(key)} IS NULL LIMIT 1").fetchone()
        if missing or extra:
            raise ValueError(f"Identificadores distintos de Bronze: {table}")
        compare = " AND ".join(f"(s.{quote(name)} IS b.{quote(name)} AND typeof(s.{quote(name)})=typeof(b.{quote(name)}))" for name in names)
        select = ",".join(f"{alias}.{quote(name)}" for alias in ("b", "s") for name in names)
        query = f"SELECT {select} FROM bronze.{quote(table)} b JOIN main.{quote(table)} s ON s.{quote(key)}=b.{quote(key)} WHERE NOT ({compare})"
        for values in conn.execute(query):
            before, after = values[:len(names)], values[len(names):]
            row_key = str(before[names.index(key)])
            for name, old, new in zip(names, before, after):
                if same(old, new):
                    continue
                ledger_key = (table, row_key, name)
                if ledger_key not in expected or not same(old, expected[ledger_key][0]) or not same(new, expected[ledger_key][1]):
                    raise ValueError(f"Cambio sin trazabilidad o discrepante: {ledger_key}")
                seen.add(ledger_key)
    if seen != expected.keys():
        raise ValueError("El registro de cambios contiene entradas que no coinciden con los datos")
    return len(seen)


def validate_quality(conn, policy, countries):
    checks = {}
    def zero(name, sql):
        value = conn.execute(sql).fetchone()[0]
        checks[name] = {"actual": value, "expected": 0, "passed": value == 0, "sql": sql}
    names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    for table in names:
        cols = table_columns(conn, table)
        if "coordinate_status" in cols:
            lat, lng = ("lat", "lng") if table == "sighting" else ("latitude", "longitude")
            zero(f"quality_coords_{table}", f"SELECT COUNT(*) FROM {quote(table)} WHERE ({quote(lat)} IS NULL)!=({quote(lng)} IS NULL) OR {quote(lat)} NOT BETWEEN -90 AND 90 OR {quote(lng)} NOT BETWEEN -180 AND 180 OR (coordinate_status='valid')!=({quote(lat)} IS NOT NULL AND {quote(lng)} IS NOT NULL)")
            zero(f"quality_coordinate_status_{table}", f"SELECT COUNT(*) FROM {quote(table)} WHERE coordinate_status IS NULL OR coordinate_status NOT IN ('valid','missing','invalid','partial','review','not_applicable')")
        for column, spec in numeric_specs(table, cols).items():
            low, high, integer = spec
            predicate = f"typeof({quote(column)}) NOT IN ('integer','real') OR {quote(column)}<{low}"
            if high is not None:
                predicate += f" OR {quote(column)}>{high}"
            if integer:
                predicate += f" OR {quote(column)}!=CAST({quote(column)} AS INTEGER)"
            zero(f"quality_numeric_{table}_{column}", f"SELECT COUNT(*) FROM {quote(table)} WHERE {quote(column)} IS NOT NULL AND ({predicate})")
        if "country_status" in cols:
            invalid = 0
            for name, code, status in conn.execute(f"SELECT country,country_iso2,country_status FROM {quote(table)}"):
                if status == "valid":
                    invalid += code not in countries.names or countries.names.get(code) != name
                else:
                    invalid += name is not None or code is not None
            checks[f"quality_country_{table}"] = {"actual": invalid, "expected": 0, "passed": invalid == 0}
            zero(f"quality_country_status_{table}", f"SELECT COUNT(*) FROM {quote(table)} WHERE country_status IS NULL OR country_status NOT IN ('valid','missing','conflict','unrecognized')")
        if "date_event" in cols:
            invalid = 0
            for value, precision, status, year in conn.execute(f"SELECT date_event,date_precision,date_status,event_year FROM {quote(table)}"):
                if status == "valid":
                    parsed = parse_date(value, policy["reference_date"])
                    invalid += parsed[0] != value or parsed[1] != precision or parsed[2] != "valid" or parsed[4] != year
                else:
                    invalid += value is not None or year is not None
            checks[f"quality_date_{table}"] = {"actual": invalid, "expected": 0, "passed": invalid == 0}
            zero(f"quality_date_status_{table}", f"SELECT COUNT(*) FROM {quote(table)} WHERE date_status IS NULL OR date_status NOT IN ('valid','missing','invalid','review','range')")
        if "sighting_datetime" in cols:
            invalid = 0
            for value, precision, zone in conn.execute(f"SELECT sighting_datetime,datetime_precision,timezone_status FROM {quote(table)}"):
                if value is not None:
                    parsed = parse_date(value, policy["reference_date"])
                    invalid += parsed[0] != value or parsed[1] != precision or parsed[2] != 'valid' or parsed[3] != zone
            checks[f"quality_datetime_{table}"] = {"actual": invalid, "expected": 0, "passed": invalid == 0}
        for column in policy.get("text_columns", {}).get(table, []):
            if column in cols:
                invalid = sum(isinstance(value, str) and (value != value.strip() or not value) for (value,) in conn.execute(f"SELECT {quote(column)} FROM {quote(table)} WHERE {quote(column)} IS NOT NULL"))
                checks[f"quality_text_{table}_{column}"] = {"actual": invalid, "expected": 0, "passed": invalid == 0}
        for column, tokens in policy.get("missing_tokens", {}).get(table, {}).items():
            if column in cols:
                invalid = sum(isinstance(value, str) and value.casefold() in tokens for (value,) in conn.execute(f"SELECT {quote(column)} FROM {quote(table)} WHERE {quote(column)} IS NOT NULL"))
                checks[f"quality_missing_tokens_{table}_{column}"] = {"actual": invalid, "expected": 0, "passed": invalid == 0}
        for column, expected in JSON_FIELDS.get(table, {}).items():
            if column in cols:
                invalid = sum(not valid_json(value, expected, column == "emotion_scores") for (value,) in conn.execute(f"SELECT {quote(column)} FROM {quote(table)} WHERE {quote(column)} IS NOT NULL"))
                checks[f"quality_json_{table}_{column}"] = {"actual": invalid, "expected": 0, "passed": invalid == 0}
    for column, allowed in policy.get("enums", {}).items():
        found = conn.execute(f"SELECT COUNT(*) FROM sighting WHERE {quote(column)} IS NOT NULL AND {quote(column)} NOT IN ({','.join('?' for _ in allowed)})", allowed).fetchone()[0]
        checks[f"quality_enum_{column}"] = {"actual": found, "expected": 0, "passed": found == 0}
    zero("quality_event_membership", "SELECT COUNT(*) FROM sighting s LEFT JOIN event_membership m ON m.sighting_id=s.id WHERE m.sighting_id IS NULL")
    zero("quality_event_representatives", "SELECT COUNT(*) FROM event_membership m LEFT JOIN event_membership p ON p.sighting_id=m.canonical_event_id WHERE p.sighting_id IS NULL OR p.canonical_event_id!=p.sighting_id")
    zero("quality_group_sizes", "SELECT COUNT(*) FROM duplicate_group g WHERE g.member_count!=(SELECT COUNT(*) FROM event_membership m WHERE m.canonical_event_id=g.canonical_event_id)")
    zero("quality_group_minimum_representative", "SELECT COUNT(*) FROM duplicate_group g WHERE g.canonical_event_id!=(SELECT MIN(m.sighting_id) FROM event_membership m WHERE m.canonical_event_id=g.canonical_event_id)")
    zero("quality_candidate_resolution", "SELECT COUNT(*) FROM duplicate_candidate c LEFT JOIN duplicate_resolution r ON r.candidate_id=c.id WHERE r.candidate_id IS NULL")
    zero("quality_confirmed_pairs", "SELECT COUNT(*) FROM duplicate_resolution r JOIN duplicate_candidate c ON c.id=r.candidate_id JOIN event_membership a ON a.sighting_id=c.sighting_id_a JOIN event_membership b ON b.sighting_id=c.sighting_id_b WHERE r.decision='confirmed_exact' AND (a.canonical_event_id!=b.canonical_event_id OR c.sighting_id_a=c.sighting_id_b)")
    integrity = [row[0] for row in conn.execute("PRAGMA main.integrity_check")]
    checks["quality_sqlite_integrity"] = {"result": integrity, "passed": integrity == ["ok"]}
    violations = sum(1 for _ in conn.execute("PRAGMA main.foreign_key_check"))
    checks["quality_foreign_keys"] = {"violations": violations, "passed": violations == 0}
    if policy.get('analytical_contract'):
        checks.update(analytics.validate_analytics(conn,countries,policy))
        checks.update(analytics.validate_temporal_evidence(conn,parse_date,policy))
        expected=coordinate_conflicts(conn,countries,policy.get('coordinate_conflict_scope','city_only'),'bronze')
        checks.update(source_evidence.validate_geography(conn,policy,countries,set(expected['sighting'])))
        # Only an explicit off-Earth catalogue record replaces a Bronze quarantine;
        # catalogue contradictions are reviewed separately.
        recovered={r[0] for r in conn.execute("SELECT sighting_id FROM source_geography_evidence WHERE coordinate_check='non_terrestrial'")}
        source_conflicts={r[0] for r in conn.execute("SELECT sighting_id FROM source_geography_evidence WHERE coordinate_check='conflict'")}
        expected['sighting']={key:value for key,value in expected['sighting'].items() if key not in recovered}
        for table in ('location','sighting'):
            actual={row[0] for row in conn.execute(f"SELECT id FROM {quote(table)} WHERE coordinate_status='review'")}
            if table=='sighting':
                actual-=source_conflicts
            issues={row[0] for row in conn.execute("SELECT record_id FROM quality_issue WHERE table_name=? AND rule_id='coordinate_country_conflict'",(table,))}
            passed=actual==set(expected[table]) and issues=={str(key) for key in expected[table]}
            checks[f'quality_coordinate_quarantine_{table}']={'actual':len(actual),'expected':len(expected[table]),'passed':passed}
    return checks


def coordinate_conflicts(conn, countries, scope="city_only", schema="main"):
    """Snapshot complete conflicting pairs; never infer replacement coordinates."""
    if scope not in ('city_only','all') or schema not in ('main','bronze'):
        raise ValueError('Política de cuarentena geográfica no soportada')
    reviews = {"location": {}, "sighting": {}}
    columns={row[1] for row in conn.execute(f'PRAGMA {schema}.table_info(location)')}
    if 'country_iso2' not in columns or ('geocode_src' not in columns and scope=='city_only'):
        return reviews
    predicate = "1=1" if scope=='all' else "geocode_src='geonames_city_only'"
    geocoder_column='geocode_src' if 'geocode_src' in columns else 'NULL'
    for key, country, code, geocoder, lat, lng in conn.execute(
            f"SELECT id,country,country_iso2,{geocoder_column},latitude,longitude FROM {schema}.location WHERE "+predicate):
        if countries.resolve(country, code)[2] != "conflict" or coordinate_pair(lat,lng)[2]!='valid':
            continue
        reviews["location"][key] = encoded({"location_id": key, "country": country,
            "country_iso2": code, "geocode_src": geocoder,
            "reason": "Países contradictorios; no se acredita ubicación ni se elige un país."})
    report_columns={row[1] for row in conn.execute(f'PRAGMA {schema}.table_info(sighting)')}
    if "location_id" in report_columns:
        for key, location in conn.execute(f"""SELECT s.id,l.id FROM {schema}.sighting s
                JOIN {schema}.location l ON l.id=s.location_id
                WHERE s.lat=l.latitude AND s.lng=l.longitude"""):
            if location in reviews["location"]:
                reviews["sighting"][key] = reviews["location"][location]
    return reviews


def apply_quality(conn, policy, reference, lineage, layouts):
    if policy.get('analytical_contract') not in (None,1):
        raise ValueError('Versión de contrato analítico no soportada')
    countries = Countries(reference)
    create_audit(conn, lineage)
    source_names = dict(conn.execute("SELECT id,name FROM source_database"))
    tables = {}
    if policy.get('analytical_contract'):
        analytics.create_evidence(conn)
        analytics.preserve_countries(conn, layouts, countries)
    source_times, _ = source_evidence.policy_times(policy)
    source_evidence.create_time_evidence(conn, source_times)
    source_geography, _ = source_evidence.policy_geography(policy)
    source_evidence.create_geography_evidence(conn, source_geography, countries)
    coordinate_reviews = coordinate_conflicts(conn, countries, policy.get("coordinate_conflict_scope","city_only"))
    decisions = None
    with conn:
        for table in layouts:
            names = table_columns(conn, table)
            if table == "sighting" and source_geography:
                # Catalogue places are compared with Bronze and the cleaned location.
                if "location" in layouts and "location" not in tables:
                    raise ValueError("La ubicación debe depurarse antes de comparar la geografía externa")
                decisions = source_evidence.decide_geography(conn, source_geography, countries, policy,
                                                             set(coordinate_reviews.get("sighting", {})))
                source_evidence.record_geography_decisions(conn, decisions)
            if table in policy["text_columns"] or table in JSON_FIELDS or "date_event" in names:
                tables[table] = clean_table(conn, table, policy, countries, source_names, coordinate_reviews.get(table), source_times, source_geography, decisions)
        deduplication = group_duplicates(conn, policy["deduplication"])
        if policy.get('analytical_contract'):
            analytics.create_analytical_views(conn, policy)
    changed = verify_change_ledger(conn, layouts)
    checks = validate_quality(conn, policy, countries)
    checks["quality_change_ledger"] = {"verified_fields": changed, "passed": True}
    counts = [dict(zip(("rule_id", "action", "count"), row)) for row in conn.execute("SELECT rule_id,action,COUNT(*) FROM quality_issue GROUP BY rule_id,action ORDER BY rule_id,action")]
    return {"tables": tables, "changed_fields": changed, "issue_counts": counts, "deduplication": deduplication}, checks
