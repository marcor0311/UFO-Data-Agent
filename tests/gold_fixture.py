"""Synthetic Silver and Bronze snapshots for Gold tests (no external data).

The fixture mimics the Silver v6 consumer surface that Gold reads:
sighting_analytical (as a table), the source tables, duplicate structures,
facility and silver_run. Values cover every eligibility path.
"""
from __future__ import annotations

import copy
import hashlib
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

SOURCES = [(1, "UFOCAT", 3), (2, "UPDB", 1), (3, "UFO-search", 2), (4, "Capella", 1)]
COLLECTIONS = [(1, "PUBLIUS"), (2, "GELDREICH"), (3, "UFOCAT")]
ORIGINS = [(1, "NUFORC"), (2, "MUFON"), (3, "BLUEBOOK")]
FACILITIES = [(1, "Hanford Site", "nuclear_base", 46.55, -119.49), (2, "Los Alamos National Laboratory", "national_lab", 35.84, -106.29),
              (3, "Los Alamos National Laboratory", "nuclear_base", 35.84, -106.29), (4, "Some Cemetery", "cemetery", 0.0, 0.0)]

COLUMNS = ["id", "source_db_id", "origin_id", "source_record_id", "source_name", "date_event", "date_status", "date_certainty",
           "raw_date_interpretation", "evidence_year_min", "evidence_year_max", "event_year", "calendar_precision",
           "usable_for_calendar", "usable_for_month_analysis", "usable_for_day_analysis", "day_placeholder_risk",
           "month_placeholder_risk", "sighting_datetime", "datetime_precision", "timezone_status", "time_basis", "clock_basis",
           "lat", "lng", "coordinate_status", "coordinate_basis", "usable_for_map", "canonical_country_iso2", "country_status",
           "country_basis", "usable_for_country", "standardized_shape", "primary_color", "duration_bucket", "duration_seconds",
           "movement_type", "hynek", "num_witnesses", "has_media", "has_description", "nearest_nuclear_site_name",
           "distance_to_nearest_nuclear_site_km", "usable_for_nuclear_proximity", "uses_external_evidence",
           "canonical_event_id", "is_canonical", "sentiment_score", "vader_compound", "roberta_sentiment",
           "emotion_7_dominant", "emotion_28_dominant", "emotion_28_group", "hoax_likelihood", "quality_score", "richness_score"]


def report(rid, source, **kw):
    """A report with day precision, clock, map, country and proximity unless overridden."""
    source_id = {s[1]: s[0] for s in SOURCES}[source]
    base = dict(id=rid, source_db_id=source_id, origin_id=None, source_record_id=f"r{rid}", source_name=source,
                date_event="1997-03-13T20:30", date_status="valid", date_certainty="source", raw_date_interpretation=None,
                evidence_year_min=None, evidence_year_max=None, event_year=1997, calendar_precision="day",
                usable_for_calendar=1, usable_for_month_analysis=1, usable_for_day_analysis=1, day_placeholder_risk=0,
                month_placeholder_risk=0, sighting_datetime="1997-03-13T20:30", datetime_precision="minute",
                timezone_status="unspecified", time_basis="bronze", clock_basis="bronze", lat=33.4, lng=-112.1,
                coordinate_status="valid", coordinate_basis="bronze", usable_for_map=1, canonical_country_iso2="US",
                country_status="valid", country_basis="location", usable_for_country=1, standardized_shape="Light",
                primary_color="orange", duration_bucket="minutes", duration_seconds=600, movement_type="hover", hynek="NL",
                num_witnesses=2, has_media=0, has_description=1, nearest_nuclear_site_name="Hanford Site",
                distance_to_nearest_nuclear_site_km=7.5, usable_for_nuclear_proximity=1, uses_external_evidence=0,
                canonical_event_id=rid, is_canonical=1, sentiment_score=0.1, vader_compound=0.2, roberta_sentiment=-0.1,
                emotion_7_dominant="surprise", emotion_28_dominant="curiosity", emotion_28_group="ambiguous",
                hoax_likelihood=0.05, quality_score=40, richness_score=8)
    base.update(kw)
    return base


NO_CLOCK = dict(datetime_precision="day", sighting_datetime=None, timezone_status="not_applicable", time_basis=None, clock_basis=None)
NO_MAP = dict(lat=None, lng=None, coordinate_status="missing", usable_for_map=0, nearest_nuclear_site_name=None,
              distance_to_nearest_nuclear_site_km=None, usable_for_nuclear_proximity=0)


def reports():
    r = []
    # Confirmed group 1–2 (canonical 1), both UFOCAT, with clock.
    r.append(report(1, "UFOCAT", origin_id=1))
    r.append(report(2, "UFOCAT", origin_id=1, canonical_event_id=1, is_canonical=0))
    r.append(report(3, "UFOCAT", date_event="1997-03-01", sighting_datetime=None, day_placeholder_risk=1, calendar_precision="month",
                    usable_for_day_analysis=0, **{k: v for k, v in NO_CLOCK.items() if k != "sighting_datetime"}))
    r.append(report(4, "UFOCAT", date_event="1965", event_year=1965, calendar_precision="year", usable_for_month_analysis=0,
                    usable_for_day_analysis=0, **{**NO_CLOCK, "datetime_precision": "year"}, standardized_shape="Disc", primary_color="red",
                    lat=51.5, lng=-0.1, canonical_country_iso2="GB", nearest_nuclear_site_name="Los Alamos National Laboratory",
                    distance_to_nearest_nuclear_site_km=8200.0))
    r.append(report(5, "UPDB", origin_id=2, date_event="2001-01-01", event_year=2001, month_placeholder_risk=1, day_placeholder_risk=1,
                    calendar_precision="year", usable_for_month_analysis=0, usable_for_day_analysis=0, **NO_CLOCK, **NO_MAP,
                    standardized_shape=None, primary_color=None, duration_bucket=None, duration_seconds=None, movement_type=None))
    r.append(report(6, "UPDB", origin_id=3, date_event="2001-07-15", event_year=2001, **NO_CLOCK, canonical_country_iso2="AR",
                    lat=-34.6, lng=-58.4, distance_to_nearest_nuclear_site_km=9800.0, standardized_shape="Triangle", primary_color="bright white"))
    r.append(report(7, "UPDB", date_event=None, date_status="missing", date_certainty="unknown", event_year=None, calendar_precision=None,
                    usable_for_calendar=0, usable_for_month_analysis=0, usable_for_day_analysis=0, **NO_CLOCK,
                    canonical_country_iso2=None, country_status="missing", usable_for_country=0, has_media=1))
    r.append(report(8, "UPDB", date_event="1952-07-14", event_year=1952, date_certainty="qualified", usable_for_calendar=0,
                    usable_for_month_analysis=0, usable_for_day_analysis=0, calendar_precision=None,
                    sighting_datetime="1952-07-14T13:00:00", datetime_precision="second", coordinate_status="review",
                    lat=None, lng=None, usable_for_map=0, nearest_nuclear_site_name=None, distance_to_nearest_nuclear_site_km=None,
                    usable_for_nuclear_proximity=0, coordinate_basis="source_conflict", canonical_country_iso2=None,
                    country_status="conflict", country_basis="source_conflict", usable_for_country=0))
    r.append(report(9, "UFO-search", date_event="1950", event_year=None, date_status="range", date_certainty="interval",
                    calendar_precision=None, usable_for_calendar=0, usable_for_month_analysis=0, usable_for_day_analysis=0,
                    evidence_year_min=1950, evidence_year_max=1959, raw_date_interpretation="decade",
                    **{**NO_CLOCK, "datetime_precision": "year_range"}, coordinate_basis="original_catalog_place",
                    uses_external_evidence=1, canonical_country_iso2="FR", lat=48.85, lng=2.35, country_basis="original_catalog"))
    r.append(report(10, "UFO-search", date_event="1978-11-02T21:15", sighting_datetime="1978-11-02T21:15", event_year=1978,
                    time_basis="original_catalog", clock_basis="original_catalog", uses_external_evidence=1, lat=90.0, lng=180.0,
                    canonical_country_iso2="CA", distance_to_nearest_nuclear_site_km=1000.0, standardized_shape="Sphere", primary_color="grey"))
    r.append(report(11, "Capella", date_event="1954-10-03", event_year=1954, **NO_CLOCK, coordinate_status="not_applicable",
                    lat=None, lng=None, usable_for_map=0, nearest_nuclear_site_name=None, distance_to_nearest_nuclear_site_km=None,
                    usable_for_nuclear_proximity=0, coordinate_basis="non_terrestrial", canonical_country_iso2=None,
                    country_status="not_applicable", country_basis="non_terrestrial", usable_for_country=0))
    r.append(report(12, "Capella", date_event="1954-10", event_year=1954, calendar_precision="month", usable_for_day_analysis=0,
                    date_certainty="coarsened", **{**NO_CLOCK, "datetime_precision": "month"}, canonical_country_iso2="IT",
                    lat=41.9, lng=12.5, distance_to_nearest_nuclear_site_km=24.99, standardized_shape="Cigar", primary_color="silver"))
    return r


def write_silver(path: Path, rows=None):
    rows = rows if rows is not None else reports()
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript("""
            CREATE TABLE source_collection (id INTEGER PRIMARY KEY, name TEXT, display_name TEXT, description TEXT, url TEXT);
            CREATE TABLE source_database (id INTEGER PRIMARY KEY, name TEXT, collection_id INTEGER, description TEXT, url TEXT, copyright TEXT);
            CREATE TABLE source_origin (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE sighting (id INTEGER PRIMARY KEY, source_db_id INTEGER, location_id INTEGER, sound TEXT, direction TEXT,
                weather TEXT, terrain TEXT, vallee TEXT, event_type TEXT, date_event_raw TEXT, time_raw TEXT,
                nrc_joy REAL, nrc_fear REAL, nrc_anger REAL, nrc_sadness REAL, nrc_surprise REAL, nrc_disgust REAL, nrc_trust REAL,
                nrc_anticipation REAL, emotion_7_surprise REAL, emotion_7_fear REAL, emotion_7_neutral REAL, emotion_7_anger REAL,
                emotion_7_disgust REAL, emotion_7_sadness REAL, emotion_7_joy REAL);
            CREATE TABLE location (id INTEGER PRIMARY KEY, raw_text TEXT, city TEXT, state TEXT, country TEXT, latitude REAL,
                longitude REAL, geocode_src TEXT, country_iso2 TEXT, coordinate_status TEXT, country_status TEXT);
            CREATE TABLE sighting_analysis (id INTEGER PRIMARY KEY, sighting_id INTEGER, behavior_tags TEXT, color_list TEXT,
                emotion_scores TEXT, hoax_flags TEXT, raw_shape_matched_via TEXT, created_at TEXT);
            CREATE TABLE quality_rule (rule_id TEXT PRIMARY KEY, severity TEXT, description TEXT);
            CREATE TABLE quality_issue (table_name TEXT, record_id TEXT, column_name TEXT, rule_id TEXT, action TEXT, raw_value TEXT, message TEXT);
            CREATE TABLE silver_change (table_name TEXT, record_id TEXT, column_name TEXT, old_value TEXT, new_value TEXT, rule_id TEXT);
            CREATE TABLE crash_retrieval (id TEXT PRIMARY KEY, page_name TEXT, year INTEGER, date_event TEXT, city TEXT, region TEXT,
                country TEXT, latitude REAL, longitude REAL, precision TEXT, craft_type TEXT, craft_size_m REAL, recovery_status TEXT,
                has_biologics INTEGER, crew_count TEXT, short_summary TEXT, raw_json TEXT, date_precision TEXT, date_status TEXT,
                event_year INTEGER, coordinate_status TEXT, country_status TEXT, country_iso2 TEXT, craft_size_status TEXT);
            CREATE TABLE nuclear_encounter (id INTEGER PRIMARY KEY, page_name TEXT, year INTEGER, date_event TEXT, base TEXT, city TEXT,
                region TEXT, country TEXT, latitude REAL, longitude REAL, weapon_system TEXT, incident_type TEXT, missiles_affected INTEGER,
                sensor_confirmation TEXT, witness_credibility TEXT, evidence_quality TEXT, source_confidence TEXT, summary TEXT,
                raw_json TEXT, date_precision TEXT, date_status TEXT, event_year INTEGER, coordinate_status TEXT, country_status TEXT,
                country_iso2 TEXT);
            CREATE TABLE event_membership (sighting_id INTEGER PRIMARY KEY, canonical_event_id INTEGER, match_status TEXT);
            CREATE TABLE duplicate_group (canonical_event_id INTEGER PRIMARY KEY, fingerprint TEXT, member_count INTEGER, rule_id TEXT);
            CREATE TABLE duplicate_candidate (id INTEGER PRIMARY KEY, sighting_id_a INTEGER, sighting_id_b INTEGER, similarity_score REAL, match_method TEXT, status TEXT);
            CREATE TABLE duplicate_resolution (candidate_id INTEGER PRIMARY KEY, decision TEXT, rule_id TEXT, reason TEXT);
            CREATE TABLE facility (id INTEGER PRIMARY KEY, name TEXT, facility_type TEXT, latitude REAL, longitude REAL, source TEXT, coordinate_status TEXT);
            CREATE TABLE silver_run (run_id TEXT PRIMARY KEY, metadata TEXT);
        """)
        conn.execute(f"CREATE TABLE sighting_analytical ({', '.join(COLUMNS)})")
        conn.executemany("INSERT INTO source_collection (id, name) VALUES (?,?)", COLLECTIONS)
        conn.executemany("INSERT INTO source_database (id, name, collection_id) VALUES (?,?,?)", SOURCES)
        conn.executemany("INSERT INTO source_origin VALUES (?,?)", ORIGINS)
        conn.executemany("INSERT INTO facility (id, name, facility_type, latitude, longitude) VALUES (?,?,?,?,?)", FACILITIES)
        conn.executemany(f"INSERT INTO sighting_analytical VALUES ({','.join('?' for _ in COLUMNS)})", [[r[c] for c in COLUMNS] for r in rows])
        extras = {1: ("silent", "NE", "clear", "rural", "CE1", "2", "Albuquerque", "NM"),
                  2: ("humming", "north", "cloudy", "residential backyard", "FB1", "3H", "Albuquerque", "New Mexico"),
                  6: ("unk", "up", None, None, None, None, "Buenos Aires", None)}
        for r in rows:
            sound, direction, weather, terrain, vallee, event_type, city, state = extras.get(r["id"], (None,) * 8)
            conn.execute("INSERT INTO location (id, city, state, country_iso2) VALUES (?,?,?,?)",
                         (r["id"], city, state, r["canonical_country_iso2"]))
            conn.execute("""INSERT INTO sighting (id, source_db_id, location_id, sound, direction, weather, terrain, vallee, event_type,
                date_event_raw, time_raw, nrc_fear, emotion_7_fear) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (r["id"], r["source_db_id"], r["id"], sound, direction, weather, terrain, vallee, event_type,
                          r["date_event"], None, 0.1 * (r["id"] % 3), 0.2))
            tags = ["bright", "hovering"] if r["id"] in (1, 2, 4) else ["silent"] if r["id"] == 6 else []
            conn.execute("INSERT INTO sighting_analysis (sighting_id, behavior_tags, hoax_flags) VALUES (?,?,?)",
                         (r["id"], json.dumps(tags), json.dumps(["very_short_text"] if r["id"] == 7 else [])))
        conn.execute("INSERT INTO quality_rule VALUES ('date_missing', 'warning', 'Fecha faltante')")
        conn.executemany("INSERT INTO quality_issue (table_name, record_id, column_name, rule_id, action) VALUES (?,?,?,?,?)",
                         [("sighting", "7", "date_event", "date_missing", "flagged"), ("location", "3", "country", "country_conflict", "review")])
        conn.execute("INSERT INTO silver_change (table_name, record_id, column_name, rule_id) VALUES ('sighting', '9', 'lat', 'source_coordinates_recovered')")
        conn.execute("""INSERT INTO crash_retrieval (id, page_name, date_event, latitude, longitude, craft_type, recovery_status, has_biologics,
            crew_count, date_precision, date_status, event_year, coordinate_status, country_status, country_iso2)
            VALUES ('1947-roswell', '1947 Roswell', '1947-07-08', 33.39, -104.52, 'disc', 'alleged_recovered', 1, '3-4', 'day', 'valid', 1947, 'valid', 'valid', 'US')""")
        conn.execute("""INSERT INTO nuclear_encounter (id, page_name, date_event, base, latitude, longitude, incident_type, missiles_affected,
            date_precision, date_status, event_year, coordinate_status, country_status, country_iso2)
            VALUES (1, '1967 Malmstrom', '1967-03-16', 'Malmstrom AFB', 47.5, -111.18, 'shutdown', 10, 'day', 'valid', 1967, 'valid', 'valid', 'US')""")
        confirmed = {r["canonical_event_id"] for r in rows if not r["is_canonical"]}
        conn.executemany("INSERT INTO event_membership VALUES (?,?,?)",
                         [(r["id"], r["canonical_event_id"], "confirmed_exact" if r["canonical_event_id"] in confirmed else "unique") for r in rows])
        for cid in confirmed:
            members = sum(1 for r in rows if r["canonical_event_id"] == cid)
            conn.execute("INSERT INTO duplicate_group VALUES (?,?,?,?)", (cid, f"fp{cid}", members, "duplicate_exact_match"))
        pairs = [(1, 2, 6), (2, 6, 10), (3, 1, 6)]
        conn.executemany("INSERT INTO duplicate_candidate (id, sighting_id_a, sighting_id_b, similarity_score, match_method) VALUES (?,?,?,0.9,'tier3_desc_fuzzy')", [p for p in pairs if {p[1], p[2]} <= {r["id"] for r in rows}])
        conn.executemany("INSERT INTO duplicate_resolution (candidate_id, decision, rule_id, reason) VALUES (?,?,?,?)",
                         [(p[0], "needs_review", "duplicate_pending", "x") for p in pairs if {p[1], p[2]} <= {r["id"] for r in rows}])
        conn.execute("INSERT INTO silver_run VALUES ('run', ?)", (json.dumps({"reference_date": "2026-11-21"}),))
        conn.commit()


def write_bronze(path: Path, rows=None):
    rows = rows if rows is not None else reports()
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE sighting (id INTEGER PRIMARY KEY)")
        conn.executemany("INSERT INTO sighting VALUES (?)", [(r["id"],) for r in rows])
        conn.commit()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_provenance(folder: Path, gold_policy: dict | None, silver: Path, bronze: Path, manifest: Path | None = None, **override):
    """Write what the official Bronze/Silver builds leave behind: the Bronze
    manifest (size and SHA-256) and a passed Silver validation report with the
    current lineage, source and policy. Returns the manifest path."""
    import json
    import build_silver
    manifest = manifest or folder / "bronze.json"
    manifest.write_text(json.dumps({"sha256": sha(bronze), "size_bytes": bronze.stat().st_size}))
    if gold_policy is not None:
        gold_policy["inputs"]["bronze"]["manifest"] = str(manifest)
    silver_policy = json.loads(build_silver.POLICY.read_text(encoding="utf-8"))
    lineage, _ = build_silver.lineage_for(sha(bronze), silver_policy)
    report = {"layer": "silver", "passed": True, "policy": silver_policy,
              "source": {"database": str(bronze), "sha256": sha(bronze), "size_bytes": bronze.stat().st_size},
              "lineage": lineage, "size_bytes": silver.stat().st_size, "sha256": sha(silver), **override}
    silver.with_suffix(".validation.json").write_text(json.dumps(report))
    return manifest


def environment(folder: Path, rows=None, *, progress=None):
    """Write fixtures and return (policy, silver, bronze, output) for build()."""
    from gold_common import load_policy
    silver, bronze = folder / "silver.db", folder / "bronze.db"
    if progress:
        progress("Creando la base Silver sintética...")
    write_silver(silver, rows)
    if progress:
        progress("Creando la base Bronze sintética...")
    write_bronze(bronze, rows)
    policy = copy.deepcopy(load_policy())
    write_provenance(folder, policy, silver, bronze)
    return policy, silver, bronze, folder / "gold" / "ufo_gold.db"


def fake_gate(silver, bronze, output):
    return {"ready_for_gold": True, "silver_sha256": sha(silver), "bronze_sha256": sha(bronze),
            "policy_version": 6, "verification": {"checks": 0, "run_id": "fixture"}}


def build_fixture(folder: Path, rows=None, *, progress=None, **kw):
    import build_gold
    policy, silver, bronze, output = environment(folder, rows, progress=progress)
    if progress:
        progress("Construyendo Gold a partir de las bases sintéticas...")
    manifest = build_gold.build(policy=policy, gate=kw.pop("gate", fake_gate), silver_path=silver, bronze_path=bronze,
                                output=output, data=folder, bronze_manifest=Path(policy["inputs"]["bronze"]["manifest"]), **kw)
    return manifest, policy, silver, bronze, output


def serving_fixture(folder: Path, *, progress=None):
    """Build Gold and its serving cache from the fixture; return an Analytics instance."""
    import discover_gold
    import gold_query
    manifest, policy, silver, bronze, output = build_fixture(folder, progress=progress)
    serving = folder / "serving" / "ufo_gold_serving.db"
    if progress:
        progress("Generando la caché de servicio Gold...")
    discover_gold.discover(gold=output, serving=serving, docs=folder / "docs")
    certified = folder / "certified_queries.json"
    certified.write_text(json.dumps({"queries": [
        {"id": "CQ_TEST_SOURCES", "title": "Informes por fuente", "description": "Conteo por fuente",
         "examples": ["¿Cuántos informes tiene cada fuente?"], "limitation": "Son informes.",
         "query": {"dataset": "agg_source", "group_by": ["source_code"], "metrics": ["report_count"], "view": "bars"}}]}))
    analytics = gold_query.Analytics(serving=serving, certified_path=certified)
    if progress:
        progress("Certificando la consulta de ejemplo Informes por fuente...")
    gold_query.certify(analytics=analytics)
    return gold_query.Analytics(serving=serving, certified_path=certified), manifest, (policy, silver, bronze, output)
