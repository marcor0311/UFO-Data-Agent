#!/usr/bin/env python3
"""Build the Gold model from the approved, accepted Silver snapshot (read-only).

The build never writes to Silver or Bronze and never replaces a published
file. It checks the chain of custody Bronze → Silver, runs the Silver
acceptance gate on that exact snapshot (once per run, shared with the other
steps), writes a ``*.building`` database inside a fresh version directory,
validates it and renames it in place. Publishing that version as the current
load is a separate, transactional step (``scripts/build_all.py``). If either
input changes while it is read, the build aborts.

    build_gold.py                 build a new, unpromoted candidate and print its path
    build_gold.py --version DIR   build into an empty version directory
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import date, datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys

if __package__:
    from .gold_common import ROOT, definitions_digest, digest, silver_provenance, load_catalogs, load_id_for, load_policy, normalize
    from .pipeline_context import silver_acceptance, write_text
    from . import releases
else:
    from gold_common import ROOT, definitions_digest, digest, silver_provenance, load_catalogs, load_id_for, load_policy, normalize
    from pipeline_context import silver_acceptance, write_text
    import releases

AGG_MEASURES = ("report_count INTEGER NOT NULL, report_count_excl_candidates INTEGER NOT NULL, "
                "pending_candidate_reports INTEGER NOT NULL, external_evidence_reports INTEGER NOT NULL")
AGG_SELECT = ("COUNT(*), SUM(has_pending_candidate=0), SUM(has_pending_candidate), SUM(uses_external_evidence)")

# Aggregate code → (eligibility codes, key columns, source expression, WHERE).
AGGREGATES = {
    "agg_year": (["calendar"], "event_year INTEGER NOT NULL, decade INTEGER NOT NULL, source_code TEXT NOT NULL",
                 "event_year, decade, source_code", "usable_for_calendar=1"),
    "agg_month": (["month"], "event_year INTEGER NOT NULL, event_month INTEGER NOT NULL, year_month TEXT NOT NULL, source_code TEXT NOT NULL",
                  "event_year, event_month, year_month, source_code", "usable_for_month_analysis=1"),
    "agg_weekday_hour": (["day", "hour"], "weekday INTEGER NOT NULL, event_hour INTEGER NOT NULL, source_code TEXT NOT NULL",
                         "weekday, event_hour, source_code", "usable_for_day_analysis=1 AND usable_for_hour_analysis=1"),
    "agg_country": (["country"], "country_iso2 TEXT NOT NULL, source_code TEXT NOT NULL",
                    "country_iso2, source_code", "usable_for_country=1"),
    "agg_shape": ([], "shape_code TEXT, source_code TEXT NOT NULL", "shape_code, source_code", "1=1"),
    "agg_source": ([], "source_code TEXT NOT NULL, collection_code TEXT NOT NULL, origin_code TEXT",
                   "source_code, collection_code, origin_code", "1=1"),
    "agg_nuclear_band": (["nuclear_proximity"], "distance_band TEXT NOT NULL, nearest_facility_key TEXT NOT NULL, source_code TEXT NOT NULL",
                         "distance_band, nearest_facility_key, source_code", "usable_for_nuclear_proximity=1"),
}
SPATIAL = ("agg_spatial_cell", ["map"])
INDEXED = ("source_code", "origin_code", "country_iso2", "nearest_facility_key", "canonical_event_id", "duration_bucket", "event_year")

FACT_COLUMNS = [
    ("report_id", "INTEGER PRIMARY KEY"), ("source_code", "TEXT NOT NULL"), ("origin_code", "TEXT"),
    ("collection_code", "TEXT NOT NULL"), ("source_record_id", "TEXT"),
    ("date_key", "TEXT"), ("calendar_precision", "TEXT"), ("date_status", "TEXT NOT NULL"), ("date_certainty", "TEXT"),
    ("raw_date_interpretation", "TEXT"), ("evidence_year_min", "INTEGER"), ("evidence_year_max", "INTEGER"),
    ("event_year", "INTEGER"), ("decade", "INTEGER"), ("event_month", "INTEGER"), ("year_month", "TEXT"),
    ("event_date", "TEXT"), ("weekday", "INTEGER"), ("event_hour", "INTEGER"),
    ("clock_precision", "TEXT"), ("timezone_status", "TEXT"), ("time_basis", "TEXT"), ("clock_basis", "TEXT"),
    ("day_placeholder_risk", "INTEGER NOT NULL"), ("month_placeholder_risk", "INTEGER NOT NULL"),
    ("lat", "REAL"), ("lng", "REAL"), ("coordinate_status", "TEXT NOT NULL"), ("coordinate_basis", "TEXT NOT NULL"),
    ("cell1_lat", "INTEGER"), ("cell1_lng", "INTEGER"), ("cell5_lat", "INTEGER"), ("cell5_lng", "INTEGER"),
    ("country_iso2", "TEXT"), ("country_status", "TEXT NOT NULL"), ("country_basis", "TEXT NOT NULL"),
    ("shape_code", "TEXT"), ("color_code", "TEXT"), ("color_family", "TEXT"), ("duration_bucket", "TEXT"),
    ("duration_seconds", "INTEGER"), ("movement_type", "TEXT"), ("hynek", "TEXT"), ("num_witnesses", "INTEGER"),
    ("has_media", "INTEGER"), ("has_description", "INTEGER"),
    ("nearest_facility_key", "TEXT"), ("nuclear_distance_km", "REAL"), ("distance_band", "TEXT"),
    ("usable_for_calendar", "INTEGER NOT NULL"), ("usable_for_month_analysis", "INTEGER NOT NULL"),
    ("usable_for_day_analysis", "INTEGER NOT NULL"), ("usable_for_hour_analysis", "INTEGER NOT NULL"),
    ("usable_for_map", "INTEGER NOT NULL"), ("usable_for_country", "INTEGER NOT NULL"),
    ("usable_for_nuclear_proximity", "INTEGER NOT NULL"),
    ("calendar_exclusion", "TEXT"), ("month_exclusion", "TEXT"), ("day_exclusion", "TEXT"), ("hour_exclusion", "TEXT"),
    ("map_exclusion", "TEXT"), ("country_exclusion", "TEXT"), ("proximity_exclusion", "TEXT"),
    ("uses_external_evidence", "INTEGER NOT NULL"), ("canonical_event_id", "INTEGER NOT NULL"),
    ("is_canonical", "INTEGER NOT NULL"), ("in_confirmed_group", "INTEGER NOT NULL"),
    ("duplicate_status", "TEXT NOT NULL"), ("has_pending_candidate", "INTEGER NOT NULL"),
    ("pending_pair_count", "INTEGER NOT NULL"),
]
MODEL_COLUMNS = [
    ("report_id", "INTEGER PRIMARY KEY REFERENCES fact_report(report_id)"), ("source_code", "TEXT NOT NULL"),
    ("event_year", "INTEGER"), ("country_iso2", "TEXT"), ("shape_code", "TEXT"),
    ("usable_for_calendar", "INTEGER NOT NULL"), ("usable_for_country", "INTEGER NOT NULL"),
    ("sentiment_score", "REAL"), ("vader_compound", "REAL"), ("roberta_sentiment", "REAL"),
    ("emotion_7_dominant", "TEXT"), ("emotion_28_dominant", "TEXT"), ("emotion_28_group", "TEXT"),
    ("hoax_likelihood", "REAL"), ("quality_score", "INTEGER"), ("richness_score", "INTEGER"),
]

SILVER_QUERY = """
SELECT a.id, a.source_name, sc.name AS collection_name, o.name AS origin_name, a.source_record_id,
       a.date_event, a.date_status, a.date_certainty, a.raw_date_interpretation, a.evidence_year_min, a.evidence_year_max,
       a.event_year, a.calendar_precision, a.usable_for_calendar, a.usable_for_month_analysis, a.usable_for_day_analysis,
       a.day_placeholder_risk, a.month_placeholder_risk, a.sighting_datetime, a.datetime_precision, a.timezone_status,
       a.time_basis, a.clock_basis, a.lat, a.lng, a.coordinate_status, a.coordinate_basis, a.usable_for_map,
       a.canonical_country_iso2, a.country_status, a.country_basis, a.usable_for_country,
       a.standardized_shape, a.primary_color, a.duration_bucket, a.duration_seconds, a.movement_type, a.hynek,
       a.num_witnesses, a.has_media, a.has_description, a.nearest_nuclear_site_name,
       a.distance_to_nearest_nuclear_site_km, a.usable_for_nuclear_proximity, a.uses_external_evidence,
       a.canonical_event_id, a.is_canonical, m.match_status, COALESCE(p.pairs, 0) AS pending_pairs,
       a.sentiment_score, a.vader_compound, a.roberta_sentiment, a.emotion_7_dominant, a.emotion_28_dominant,
       a.emotion_28_group, a.hoax_likelihood, a.quality_score, a.richness_score
FROM silver.sighting_analytical a
JOIN silver.source_database sd ON sd.id = a.source_db_id
JOIN silver.source_collection sc ON sc.id = sd.collection_id
JOIN silver.event_membership m ON m.sighting_id = a.id
LEFT JOIN silver.source_origin o ON o.id = a.origin_id
LEFT JOIN temp.pending p ON p.sighting_id = a.id
ORDER BY a.id
"""


class GoldBuildError(RuntimeError):
    pass


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize(text)).strip("-")


def cell(value: float, resolution: int, upper: int) -> int:
    """South-west corner of the cell; the closing edge (90°, 180°) joins the last cell."""
    return min(int(math.floor(value / resolution)) * resolution, upper - resolution)


def band_for(distance: float, bands: list) -> str:
    for band in bands:
        if distance >= band["min"] and (band["max"] is None or distance < band["max"]):
            return band["code"]
    raise GoldBuildError(f"Distancia sin banda: {distance}")


def official_acceptance(silver_path: Path, bronze_path: Path) -> dict:
    """The Silver acceptance gate (check_silver_ready.readiness) on one snapshot."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_silver
    import check_silver_ready
    return check_silver_ready.readiness(bronze_path, silver_path,
                                        json.loads(build_silver.MANIFEST.read_text(encoding="utf-8")),
                                        json.loads(build_silver.POLICY.read_text(encoding="utf-8")))


def silver_gate(silver_path: Path, bronze_path: Path, output: Path | None = None) -> dict:
    """Run the official Silver acceptance on the exact snapshot (read-only).

    The result is shared through the run context: within one invocation the
    full acceptance runs once per exact (Silver, Bronze) pair, however many
    steps ask for it. ``output`` receives a copy of the report.
    """
    result = silver_acceptance(silver_path, bronze_path, official_acceptance)
    if output is not None:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        write_text(output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def exclusion_reasons(r: dict, clock: set) -> dict:
    """Why a report is outside each eligibility. None means eligible."""
    date_event = r["date_event"] or ""
    length = len(date_event)
    if r["usable_for_calendar"]:
        calendar = None
    elif r["date_status"] != "valid":
        calendar = "date_" + r["date_status"]
    elif r["date_certainty"] not in ("source", "coarsened"):
        calendar = "date_qualified"
    else:
        raise GoldBuildError(f"Informe {r['id']}: fecha válida y cierta fuera de calendario")

    def finer(day: bool):
        if calendar:
            return calendar
        if length == 4:
            return "precision_year"
        if day and length == 7:
            return "precision_month"
        if length >= 10 and r["month_placeholder_risk"]:
            return "month_day_placeholder"
        if day and length >= 10 and r["day_placeholder_risk"]:
            return "day_placeholder"
        raise GoldBuildError(f"Informe {r['id']}: exclusión temporal sin motivo")

    month = None if r["usable_for_month_analysis"] else finer(False)
    day = None if r["usable_for_day_analysis"] else finer(True)
    hour_ok = bool(r["usable_for_calendar"]) and r["datetime_precision"] in clock
    hour = None if hour_ok else (calendar or "clock_precision_" + (r["datetime_precision"] or "unknown"))
    coordinates = None if r["usable_for_map"] else "coordinates_" + r["coordinate_status"]
    country = None if r["usable_for_country"] else "country_" + r["country_status"]
    proximity = None if r["usable_for_nuclear_proximity"] else (coordinates or "proximity_missing")
    return {"calendar_exclusion": calendar, "month_exclusion": month, "day_exclusion": day, "hour_exclusion": hour,
            "map_exclusion": coordinates, "country_exclusion": country, "proximity_exclusion": proximity,
            "usable_for_hour_analysis": int(hour_ok)}


def derive(r: dict, policy: dict, labels: dict, facilities: dict) -> tuple[dict, dict]:
    clock = set(policy["clock_precisions"])
    reasons = exclusion_reasons(r, clock)
    date_event = r["date_event"]
    out = {"report_id": r["id"], "source_code": r["source_name"], "origin_code": r["origin_name"],
           "collection_code": r["collection_name"], "source_record_id": r["source_record_id"],
           "calendar_precision": r["calendar_precision"], "date_status": r["date_status"],
           "date_certainty": r["date_certainty"], "raw_date_interpretation": r["raw_date_interpretation"],
           "evidence_year_min": r["evidence_year_min"], "evidence_year_max": r["evidence_year_max"],
           "clock_precision": r["datetime_precision"], "timezone_status": r["timezone_status"],
           "time_basis": r["time_basis"], "clock_basis": r["clock_basis"],
           "day_placeholder_risk": int(r["day_placeholder_risk"] or 0),
           "month_placeholder_risk": int(r["month_placeholder_risk"] or 0),
           "coordinate_status": r["coordinate_status"], "coordinate_basis": r["coordinate_basis"],
           "country_status": r["country_status"], "country_basis": r["country_basis"],
           "shape_code": r["standardized_shape"], "color_code": r["primary_color"],
           "duration_bucket": r["duration_bucket"], "duration_seconds": r["duration_seconds"],
           "movement_type": r["movement_type"], "hynek": r["hynek"], "num_witnesses": r["num_witnesses"],
           "has_media": r["has_media"], "has_description": r["has_description"],
           "usable_for_calendar": int(r["usable_for_calendar"]), "usable_for_month_analysis": int(r["usable_for_month_analysis"]),
           "usable_for_day_analysis": int(r["usable_for_day_analysis"]), "usable_for_map": int(r["usable_for_map"]),
           "usable_for_country": int(r["usable_for_country"]), "usable_for_nuclear_proximity": int(r["usable_for_nuclear_proximity"]),
           "uses_external_evidence": int(r["uses_external_evidence"]), "canonical_event_id": r["canonical_event_id"],
           "is_canonical": int(r["is_canonical"]), "pending_pair_count": int(r["pending_pairs"]), **reasons}
    # Calendar values are published only where the matching eligibility holds.
    out.update(date_key=None, event_year=None, decade=None, event_month=None, year_month=None,
               event_date=None, weekday=None, event_hour=None)
    if out["usable_for_calendar"]:
        width = {"day": 10, "month": 7, "year": 4}[r["calendar_precision"]]
        if int(date_event[:4]) != r["event_year"]:
            raise GoldBuildError(f"Informe {r['id']}: año incoherente con la fecha")
        out.update(date_key=date_event[:width], event_year=r["event_year"], decade=r["event_year"] // 10 * 10)
    elif r["calendar_precision"] is not None:
        raise GoldBuildError(f"Informe {r['id']}: precisión sin calendario")
    if out["usable_for_month_analysis"]:
        out.update(event_month=int(date_event[5:7]), year_month=date_event[:7])
    if out["usable_for_day_analysis"]:
        out.update(event_date=date_event[:10], weekday=date.fromisoformat(date_event[:10]).isoweekday())
    if out["usable_for_hour_analysis"]:
        stamp = r["sighting_datetime"] or ""
        if len(stamp) < 16 or stamp[10] != "T" or len(date_event) < 10 or stamp[:10] != date_event[:10]:
            raise GoldBuildError(f"Informe {r['id']}: timestamp incoherente")
        out["event_hour"] = int(stamp[11:13])
        if not 0 <= out["event_hour"] <= 23:
            raise GoldBuildError(f"Informe {r['id']}: hora fuera de rango")
    # Geography.
    out.update(lat=None, lng=None, cell1_lat=None, cell1_lng=None, cell5_lat=None, cell5_lng=None, country_iso2=None)
    if out["usable_for_map"]:
        lat, lng = r["lat"], r["lng"]
        if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise GoldBuildError(f"Informe {r['id']}: coordenadas aptas fuera de rango")
        out.update(lat=lat, lng=lng, cell1_lat=cell(lat, 1, 90), cell1_lng=cell(lng, 1, 180),
                   cell5_lat=cell(lat, 5, 90), cell5_lng=cell(lng, 5, 180))
    if out["usable_for_country"]:
        out["country_iso2"] = r["canonical_country_iso2"]
        if not out["country_iso2"]:
            raise GoldBuildError(f"Informe {r['id']}: país apto sin código")
    out.update(nearest_facility_key=None, nuclear_distance_km=None, distance_band=None)
    if out["usable_for_nuclear_proximity"]:
        key = slug(r["nearest_nuclear_site_name"])
        if key not in facilities:
            raise GoldBuildError(f"Informe {r['id']}: instalación cercana fuera del catálogo")
        distance = r["distance_to_nearest_nuclear_site_km"]
        out.update(nearest_facility_key=key, nuclear_distance_km=distance,
                   distance_band=band_for(distance, policy["distance_bands_km"]))
    # Closed vocabularies: an unknown value stops the build instead of being relabelled.
    for column, vocabulary in (("shape_code", "shape_code"), ("color_code", "color_code"),
                               ("duration_bucket", "duration_bucket"), ("movement_type", "movement_type"),
                               ("source_code", "source_code"), ("origin_code", "origin_code"),
                               ("collection_code", "collection_code")):
        if out[column] is not None and out[column] not in labels[vocabulary]:
            raise GoldBuildError(f"Valor sin etiqueta en {column}: {out[column]!r}")
    out["color_family"] = labels["color_code"][out["color_code"]][1] if out["color_code"] else None
    confirmed = r["match_status"] == "confirmed_exact"
    out["in_confirmed_group"] = int(confirmed)
    out["has_pending_candidate"] = int(out["pending_pair_count"] > 0)
    out["duplicate_status"] = (("confirmed_canonical" if out["is_canonical"] else "confirmed_member") if confirmed
                               else "pending_candidate" if out["has_pending_candidate"] else "unique")
    if not confirmed and not out["is_canonical"]:
        raise GoldBuildError(f"Informe {r['id']}: no canónico fuera de un grupo confirmado")
    model = {"report_id": r["id"], "source_code": out["source_code"], "event_year": out["event_year"],
             "country_iso2": out["country_iso2"], "shape_code": out["shape_code"],
             "usable_for_calendar": out["usable_for_calendar"], "usable_for_country": out["usable_for_country"],
             **{k: r[k] for k in ("sentiment_score", "vader_compound", "roberta_sentiment", "emotion_7_dominant",
                                  "emotion_28_dominant", "emotion_28_group", "hoax_likelihood", "quality_score",
                                  "richness_score")}}
    return out, model


def create_table(conn, name, columns):
    conn.execute(f'CREATE TABLE "{name}" (' + ", ".join(f'"{c}" {t}' for c, t in columns) + ")")


def insert_rows(conn, name, columns, rows):
    names = [c for c, _ in columns]
    conn.executemany(f'INSERT INTO "{name}" (' + ",".join(f'"{n}"' for n in names) + ") VALUES (" +
                     ",".join("?" for _ in names) + ")", ([row[n] for n in names] for row in rows))


def build_dimensions(conn, policy, catalogs, facilities):
    dims = catalogs["dimensions"]
    labels = dims["labels"]
    conn.executescript("""
        CREATE TABLE dim_source (source_code TEXT PRIMARY KEY, source_id INTEGER NOT NULL, label_es TEXT NOT NULL,
            collection_code TEXT NOT NULL, description TEXT, url TEXT, copyright TEXT, report_count INTEGER NOT NULL,
            calendar_year_min INTEGER, calendar_year_max INTEGER);
        CREATE TABLE dim_origin (origin_code TEXT PRIMARY KEY, origin_id INTEGER NOT NULL, label_es TEXT NOT NULL, report_count INTEGER NOT NULL);
        CREATE TABLE dim_collection (collection_code TEXT PRIMARY KEY, label_es TEXT NOT NULL, description TEXT, url TEXT);
        CREATE TABLE dim_date (date_key TEXT PRIMARY KEY, precision TEXT NOT NULL, year INTEGER NOT NULL, month INTEGER,
            day INTEGER, weekday INTEGER, decade INTEGER NOT NULL, month_label_es TEXT, weekday_label_es TEXT);
        CREATE TABLE dim_country (country_iso2 TEXT PRIMARY KEY, alpha3 TEXT, m49 TEXT, name_en TEXT NOT NULL,
            name_es TEXT NOT NULL, report_count INTEGER NOT NULL);
        CREATE TABLE dim_shape (shape_code TEXT PRIMARY KEY, label_es TEXT NOT NULL);
        CREATE TABLE dim_color (color_code TEXT PRIMARY KEY, label_es TEXT NOT NULL, family_code TEXT NOT NULL, family_label_es TEXT NOT NULL);
        CREATE TABLE dim_duration_bucket (duration_bucket TEXT PRIMARY KEY, label_es TEXT NOT NULL, ordinal INTEGER NOT NULL,
            min_seconds_observed INTEGER, max_seconds_observed INTEGER);
        CREATE TABLE dim_movement (movement_type TEXT PRIMARY KEY, label_es TEXT NOT NULL);
        CREATE TABLE dim_nuclear_facility (nearest_facility_key TEXT PRIMARY KEY, name TEXT NOT NULL, facility_ids TEXT NOT NULL,
            facility_types TEXT NOT NULL, latitude REAL NOT NULL, longitude REAL NOT NULL, nearest_reports INTEGER NOT NULL);
        CREATE TABLE dim_distance_band (distance_band TEXT PRIMARY KEY, label_es TEXT NOT NULL, min_km REAL NOT NULL, max_km REAL, ordinal INTEGER NOT NULL);
        CREATE TABLE dim_weekday (weekday INTEGER PRIMARY KEY, label_es TEXT NOT NULL);
        CREATE TABLE dim_month (event_month INTEGER PRIMARY KEY, label_es TEXT NOT NULL);
        CREATE TABLE dim_duplicate_status (duplicate_status TEXT PRIMARY KEY, label_es TEXT NOT NULL);
        CREATE TABLE dim_exclusion_reason (reason TEXT PRIMARY KEY, label_es TEXT NOT NULL);
        CREATE TABLE dim_eligibility (eligibility_code TEXT PRIMARY KEY, label_es TEXT NOT NULL, flag TEXT NOT NULL, definition TEXT NOT NULL);
    """)
    for code, (label, _aliases) in labels["source_code"].items():
        row = conn.execute("""SELECT d.id, c.name, d.description, d.url, d.copyright FROM silver.source_database d
                              JOIN silver.source_collection c ON c.id=d.collection_id WHERE d.name=?""", (code,)).fetchone()
        stats = conn.execute("SELECT COUNT(*), MIN(event_year), MAX(event_year) FROM fact_report WHERE source_code=?", (code,)).fetchone()
        if row is None or not stats[0]:
            raise GoldBuildError(f"Fuente etiquetada sin informes: {code}")
        conn.execute("INSERT INTO dim_source VALUES (?,?,?,?,?,?,?,?,?,?)", (code, row[0], label, row[1], row[2], row[3], row[4], *stats))
    missing = conn.execute("SELECT DISTINCT source_code FROM fact_report WHERE source_code NOT IN (SELECT source_code FROM dim_source)").fetchall()
    if missing:
        raise GoldBuildError(f"Fuentes sin etiqueta: {missing}")
    for origin_id, name in conn.execute("SELECT id, name FROM silver.source_origin ORDER BY id").fetchall():
        count = conn.execute("SELECT COUNT(*) FROM fact_report WHERE origin_code=?", (name,)).fetchone()[0]
        if count:
            conn.execute("INSERT INTO dim_origin VALUES (?,?,?,?)", (name, origin_id, labels["origin_code"][name], count))
    for name, description, url in conn.execute("SELECT name, description, url FROM silver.source_collection ORDER BY id").fetchall():
        conn.execute("INSERT INTO dim_collection VALUES (?,?,?,?)", (name, labels["collection_code"][name], description, url))
    months = dims["dimensions"]["event_month"]["values"]
    weekdays = dims["dimensions"]["weekday"]["values"]
    for (key,) in conn.execute("SELECT DISTINCT date_key FROM fact_report WHERE date_key IS NOT NULL").fetchall():
        year = int(key[:4]); month = int(key[5:7]) if len(key) >= 7 else None; day = int(key[8:10]) if len(key) == 10 else None
        weekday = date.fromisoformat(key).isoweekday() if day else None
        conn.execute("INSERT INTO dim_date VALUES (?,?,?,?,?,?,?,?,?)",
                     (key, {4: "year", 7: "month", 10: "day"}[len(key)], year, month, day, weekday, year // 10 * 10,
                      months[str(month)] if month else None, weekdays[str(weekday)] if weekday else None))
    countries = json.loads((ROOT / "config/countries.json").read_text(encoding="utf-8"))
    names_es = catalogs["countries_es"]["names"]
    for entry in countries["countries"] + countries["additional_iso_entries"]:
        code = entry["alpha2"]
        count = conn.execute("SELECT COUNT(*) FROM fact_report WHERE country_iso2=?", (code,)).fetchone()[0]
        if code not in names_es:
            raise GoldBuildError(f"País sin nombre en español: {code}")
        conn.execute("INSERT INTO dim_country VALUES (?,?,?,?,?,?)", (code, entry.get("alpha3"), entry.get("m49"), entry["name"], names_es[code], count))
    for code, label in labels["shape_code"].items():
        conn.execute("INSERT INTO dim_shape VALUES (?,?)", (code, label))
    for code, (label, family) in labels["color_code"].items():
        conn.execute("INSERT INTO dim_color VALUES (?,?,?,?)", (code, label, family, labels["color_family"][family]))
    for code, (label, ordinal) in labels["duration_bucket"].items():
        low, high = conn.execute("SELECT MIN(duration_seconds), MAX(duration_seconds) FROM fact_report WHERE duration_bucket=?", (code,)).fetchone()
        conn.execute("INSERT INTO dim_duration_bucket VALUES (?,?,?,?,?)", (code, label, ordinal, low, high))
    for code, label in labels["movement_type"].items():
        conn.execute("INSERT INTO dim_movement VALUES (?,?)", (code, label))
    for key, info in facilities.items():
        nearest = conn.execute("SELECT COUNT(*) FROM fact_report WHERE nearest_facility_key=?", (key,)).fetchone()[0]
        conn.execute("INSERT INTO dim_nuclear_facility VALUES (?,?,?,?,?,?,?)",
                     (key, info["name"], json.dumps(info["ids"]), json.dumps(info["types"]), info["latitude"], info["longitude"], nearest))
    for ordinal, band in enumerate(policy["distance_bands_km"], 1):
        conn.execute("INSERT INTO dim_distance_band VALUES (?,?,?,?,?)", (band["code"], band["label"], band["min"], band["max"], ordinal))
    conn.executemany("INSERT INTO dim_weekday VALUES (?,?)", [(int(k), v) for k, v in weekdays.items()])
    conn.executemany("INSERT INTO dim_month VALUES (?,?)", [(int(k), v) for k, v in months.items()])
    conn.executemany("INSERT INTO dim_duplicate_status VALUES (?,?)", list(dims["dimensions"]["duplicate_status"]["values"].items()))
    conn.executemany("INSERT INTO dim_exclusion_reason VALUES (?,?)", list(dims["exclusion_reasons"].items()))
    conn.executemany("INSERT INTO dim_eligibility VALUES (?,?,?,?)",
                     [(k, v["label"], v["flag"], v["definition"]) for k, v in dims["eligibility"].items()])
    unknown = conn.execute("""SELECT 'reason', x FROM (
        SELECT calendar_exclusion x FROM fact_report UNION SELECT month_exclusion FROM fact_report
        UNION SELECT day_exclusion FROM fact_report UNION SELECT hour_exclusion FROM fact_report
        UNION SELECT map_exclusion FROM fact_report UNION SELECT country_exclusion FROM fact_report
        UNION SELECT proximity_exclusion FROM fact_report) WHERE x IS NOT NULL AND x NOT IN (SELECT reason FROM dim_exclusion_reason)""").fetchall()
    if unknown:
        raise GoldBuildError(f"Motivos de exclusión sin etiqueta: {unknown}")


def build_events(conn):
    conn.executescript("""
        CREATE TABLE fact_event (canonical_event_id INTEGER PRIMARY KEY REFERENCES fact_report(report_id),
            member_count INTEGER NOT NULL, distinct_source_count INTEGER NOT NULL, source_codes TEXT NOT NULL,
            rule_id TEXT NOT NULL, fingerprint TEXT NOT NULL, date_key TEXT, event_year INTEGER, country_iso2 TEXT,
            shape_code TEXT, members_with_pending_candidate INTEGER NOT NULL,
            usable_for_calendar INTEGER NOT NULL, usable_for_country INTEGER NOT NULL);
        CREATE TABLE event_report (canonical_event_id INTEGER NOT NULL REFERENCES fact_event(canonical_event_id),
            report_id INTEGER PRIMARY KEY REFERENCES fact_report(report_id), is_canonical INTEGER NOT NULL, source_code TEXT NOT NULL);
        INSERT INTO event_report SELECT canonical_event_id, report_id, is_canonical, source_code
            FROM fact_report WHERE in_confirmed_group=1 ORDER BY report_id;
        INSERT INTO fact_event
        SELECT g.canonical_event_id, g.member_count,
               (SELECT COUNT(DISTINCT source_code) FROM event_report e WHERE e.canonical_event_id=g.canonical_event_id),
               (SELECT json_group_array(source_code) FROM (SELECT DISTINCT source_code FROM event_report e
                    WHERE e.canonical_event_id=g.canonical_event_id ORDER BY source_code)),
               g.rule_id, g.fingerprint, f.date_key, f.event_year, f.country_iso2, f.shape_code,
               (SELECT SUM(r.has_pending_candidate) FROM fact_report r WHERE r.canonical_event_id=g.canonical_event_id AND r.in_confirmed_group=1),
               f.usable_for_calendar, f.usable_for_country
        FROM silver.duplicate_group g JOIN fact_report f ON f.report_id=g.canonical_event_id
        ORDER BY g.canonical_event_id;
    """)


def build_aggregates(conn, policy):
    for name, (eligibility, keys, columns, where) in AGGREGATES.items():
        conn.execute(f"CREATE TABLE {name} ({keys}, {AGG_MEASURES})")
        conn.execute(f"INSERT INTO {name} SELECT {columns}, {AGG_SELECT} FROM fact_report WHERE {where} GROUP BY {columns} ORDER BY {columns}")
    conn.execute(f"CREATE TABLE agg_spatial_cell (resolution_deg INTEGER NOT NULL, cell_lat INTEGER NOT NULL, cell_lng INTEGER NOT NULL, source_code TEXT NOT NULL, {AGG_MEASURES})")
    for resolution in policy["spatial_cells"]["resolutions_deg"]:
        lat, lng = f"cell{resolution}_lat", f"cell{resolution}_lng"
        conn.execute(f"""INSERT INTO agg_spatial_cell SELECT {resolution}, {lat}, {lng}, source_code, {AGG_SELECT}
                         FROM fact_report WHERE usable_for_map=1 GROUP BY {lat}, {lng}, source_code ORDER BY {lat}, {lng}, source_code""")
    conn.execute(f"""CREATE TABLE agg_coverage (aggregate_code TEXT NOT NULL, eligibility_code TEXT NOT NULL,
        coverage_status TEXT NOT NULL CHECK(coverage_status IN ('included','excluded')), reason TEXT,
        source_code TEXT NOT NULL, {AGG_MEASURES})""")
    flags = {code: spec["flag"] for code, spec in policy["eligibility"].items()}
    exclusions = {code: spec["exclusion"] for code, spec in policy["eligibility"].items()}
    for name, eligibility in coverage_plan().items():
        label = "+".join(eligibility) or "none"
        if eligibility:
            included = " AND ".join(f"{flags[e]}=1" for e in eligibility)
            reason = "COALESCE(" + ", ".join(exclusions[e] for e in eligibility) + ")" if len(eligibility) > 1 else exclusions[eligibility[0]]
            conn.execute(f"""INSERT INTO agg_coverage SELECT ?, ?, 'excluded', {reason}, source_code, {AGG_SELECT}
                             FROM fact_report WHERE NOT ({included}) GROUP BY {reason}, source_code ORDER BY 4, 5""", (name, label))
        else:
            included = "1=1"
        conn.execute(f"""INSERT INTO agg_coverage SELECT ?, ?, 'included', NULL, source_code, {AGG_SELECT}
                         FROM fact_report WHERE {included} GROUP BY source_code ORDER BY source_code""", (name, label))


def coverage_plan() -> dict:
    plan = {name: spec[0] for name, spec in AGGREGATES.items()}
    plan[SPATIAL[0]] = SPATIAL[1]
    return dict(sorted(plan.items()))


def nuclear_facilities(conn, policy) -> dict:
    types = policy["nuclear_facility_types"]
    rows = conn.execute(f"""SELECT id, name, facility_type, latitude, longitude FROM silver.facility
        WHERE facility_type IN ({",".join("?" for _ in types)}) ORDER BY id""", types).fetchall()
    facilities = {}
    for fid, name, ftype, lat, lng in rows:
        item = facilities.setdefault(slug(name), {"name": name, "ids": [], "types": [], "latitude": lat, "longitude": lng})
        item["ids"].append(fid)
        if ftype not in item["types"]:
            item["types"].append(ftype)
    return facilities


def populate(conn, policy, catalogs):
    """Read Silver once and write fact_report and report_model_output."""
    conn.execute(f"""CREATE TEMP TABLE pending AS
        SELECT sighting_id, COUNT(*) AS pairs FROM (
            SELECT c.sighting_id_a AS sighting_id FROM silver.duplicate_candidate c JOIN silver.duplicate_resolution r ON r.candidate_id=c.id WHERE r.decision=?
            UNION ALL
            SELECT c.sighting_id_b FROM silver.duplicate_candidate c JOIN silver.duplicate_resolution r ON r.candidate_id=c.id WHERE r.decision=?)
        GROUP BY sighting_id""", (policy["duplicates"]["pending_decision"],) * 2)
    conn.execute("CREATE UNIQUE INDEX temp.idx_pending ON pending(sighting_id)")
    facilities = nuclear_facilities(conn, policy)
    labels = catalogs["dimensions"]["labels"]
    create_table(conn, "fact_report", FACT_COLUMNS)
    create_table(conn, "report_model_output", MODEL_COLUMNS)
    cursor = conn.execute(SILVER_QUERY)
    names = [d[0] for d in cursor.description]
    facts, models = [], []
    while True:
        batch = cursor.fetchmany(20000)
        if not batch:
            break
        for raw in batch:
            fact, model = derive(dict(zip(names, raw)), policy, labels, facilities)
            facts.append(fact); models.append(model)
        insert_rows(conn, "fact_report", FACT_COLUMNS, facts)
        insert_rows(conn, "report_model_output", MODEL_COLUMNS, models)
        facts.clear(); models.clear()
    return facilities


def build_database(path: Path, silver_path: Path, policy: dict, catalogs: dict) -> None:
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA journal_mode=OFF")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("ATTACH DATABASE ? AS silver", (silver_path.resolve().as_uri() + "?mode=ro&immutable=1",))
        facilities = populate(conn, policy, catalogs)
        for column in INDEXED:
            conn.execute(f'CREATE INDEX "idx_fact_report_{column}" ON fact_report ("{column}")')
        build_dimensions(conn, policy, catalogs, facilities)
        build_events(conn)
        build_aggregates(conn, policy)
        conn.commit()
        conn.execute("DETACH DATABASE silver")


def stored_path(path: Path, data: Path) -> str:
    try:
        return releases.relative(data, path)
    except ValueError:
        return str(Path(path).resolve())


def build(root: Path = ROOT, policy: dict | None = None, gate=silver_gate, silver_path: Path | None = None,
          bronze_path: Path | None = None, output: Path | None = None, validate=None,
          provenance=silver_provenance, readiness_path: Path | None = None, data: Path | None = None,
          bronze_manifest: Path | None = None) -> dict:
    """Build Gold into ``output``, which must not exist (default: a new candidate)."""
    policy = policy or load_policy(root)
    catalogs = load_catalogs(root)
    data = Path(data or releases.data_root(root))
    if silver_path is None:
        current = releases.layout(data, "silver")
        if current is None:
            raise GoldBuildError("No hay una Silver aprobada en el catálogo. Ejecuta `python scripts/build_all.py --desde silver`.")
        silver_path = current.database
    bronze_path = Path(bronze_path or data / policy["inputs"]["bronze"]["path"])
    bronze_manifest = Path(bronze_manifest or root / policy["inputs"]["bronze"]["manifest"])
    output = Path(output or releases.GoldLayout(releases.new_candidate(data, "gold")).database)
    manifest_path = output.with_name(output.stem + ".manifest.json")
    readiness_path = Path(readiness_path or output.with_name("silver.readiness.json"))
    building = output.with_name(output.name + ".building")
    for existing in (output, manifest_path):
        if existing.exists():
            raise GoldBuildError(f"Se conserva {existing}: Gold se construye siempre en una versión nueva, "
                                 "nunca sobre una base publicada que pueda tener lectores.")
    custody = provenance(silver_path, bronze_path, bronze_manifest)
    if not custody["passed"]:
        raise GoldBuildError("Silver no es apta para Gold: " + "; ".join(custody["problems"])
                             + ". Ejecuta `python scripts/build_all.py` (o `--desde silver`).")
    silver_sha, bronze_sha = custody["silver_sha256"], custody["bronze_sha256"]
    readiness = gate(silver_path, bronze_path, readiness_path)
    with closing(sqlite3.connect(Path(silver_path).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
        runs = [json.loads(m) for (m,) in conn.execute("SELECT metadata FROM silver_run").fetchall()]
    silver_reference_date = runs[0].get("reference_date") if len(runs) == 1 else None
    if not readiness.get("ready_for_gold") or readiness.get("silver_sha256") != silver_sha or readiness.get("bronze_sha256") != bronze_sha:
        raise GoldBuildError("La puerta de Silver no aprobó este snapshot exacto")
    definitions_sha, definition_files = definitions_digest(policy, root)
    load_id = load_id_for(policy, silver_sha, bronze_sha, definitions_sha)
    output.parent.mkdir(parents=True, exist_ok=True)
    building.unlink(missing_ok=True)
    try:
        build_database(building, Path(silver_path), policy, catalogs)
        if validate is None:
            if __package__:
                from .check_gold_ready import model_checks
            else:
                from check_gold_ready import model_checks
            validate = model_checks
        checks = validate(building, silver_path, bronze_path, policy, catalogs)
        failed = [c for c in checks if not c["passed"]]
        if failed:
            raise GoldBuildError("Validación Gold fallida: " + "; ".join(c["check"] + " → " + str(c.get("detail")) for c in failed[:10]))
        if digest(silver_path) != silver_sha or digest(bronze_path) != bronze_sha:
            raise GoldBuildError("Silver o Bronze cambiaron durante la lectura")
        with closing(sqlite3.connect(building)) as conn:
            tables = {name: conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for (name,) in
                      conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()}
            totals = dict(zip(("reports", "reports_excl_candidates", "pending_candidate_reports", "external_evidence_reports",
                               "confirmed_events", "confirmed_group_reports"),
                              conn.execute("""SELECT COUNT(*), SUM(has_pending_candidate=0), SUM(has_pending_candidate),
                                  SUM(uses_external_evidence), (SELECT COUNT(*) FROM fact_event), SUM(in_confirmed_group)
                                  FROM fact_report""").fetchone()))
        if output.exists():
            raise GoldBuildError(f"Otro proceso escribió {output} durante la construcción")
        os.replace(building, output)
    except BaseException:
        building.unlink(missing_ok=True)
        raise
    manifest = {
        "gold_version": policy["gold_version"], "load_id": load_id,
        "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "silver": {"path": stored_path(silver_path, data), "sha256": silver_sha,
                   "policy_version": readiness.get("policy_version"), "reference_date": silver_reference_date,
                   "run_id": readiness.get("verification", {}).get("run_id"),
                   "readiness": {"ready_for_gold": readiness["ready_for_gold"],
                                 "checks": readiness.get("verification", {}).get("checks"),
                                 "report": readiness_path.name}},
        "bronze": {"path": stored_path(bronze_path, data), "sha256": bronze_sha},
        "silver_run_id": custody["silver_run_id"],
        "definitions_sha256": definitions_sha, "definitions": definition_files,
        "gold_sha256": digest(output), "tables": tables, "totals": totals,
        "validation": {"checks": len(checks), "passed": True},
    }
    write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", type=Path, help="Directorio de versión vacío (por defecto, un candidato nuevo)")
    args = parser.parse_args()
    try:
        output = None
        if args.version:
            args.version.mkdir(parents=True, exist_ok=True)
            output = releases.GoldLayout(args.version).database
        manifest = build(output=output)
    except (OSError, ValueError, sqlite3.Error, GoldBuildError) as exc:
        print(f"GOLD NO CONSTRUIDA: {exc}", file=sys.stderr)
        return 1
    print(f"Gold construida (candidato sin promover): load_id {manifest['load_id']}; {manifest['totals']['reports']} informes; "
          f"{manifest['validation']['checks']} controles. Para publicarla usa `python scripts/build_all.py --desde gold`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
