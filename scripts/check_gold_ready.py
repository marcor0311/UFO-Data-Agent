#!/usr/bin/env python3
"""Acceptance gate for the agent: ``ready_for_agent=true`` only if every check passes.

``model_checks`` validates a Gold database against Silver and the catalogs; the
builder runs it on the ``*.building`` file before publishing. The full gate adds
the manifest, the chain of custody of its inputs, the Silver acceptance of that
exact snapshot, the serving cache, certified queries, the independent
verification and the evaluation set, all from the same version directory.

    check_gold_ready.py                 gate the approved load; report in <datos>/gold/
    check_gold_ready.py --version DIR   gate one version directory
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

if __package__:
    from .gold_common import ROOT, definitions_digest, digest, silver_provenance, load_catalogs, load_id_for, load_policy, text_digest
    from .pipeline_context import write_text
    from . import releases
else:
    from gold_common import ROOT, definitions_digest, digest, silver_provenance, load_catalogs, load_id_for, load_policy, text_digest
    from pipeline_context import write_text
    import releases

AGG_KEYS = {
    "agg_year": ("event_year, decade, source_code", "usable_for_calendar=1"),
    "agg_month": ("event_year, event_month, year_month, source_code", "usable_for_month_analysis=1"),
    "agg_weekday_hour": ("weekday, event_hour, source_code", "usable_for_day_analysis=1 AND usable_for_hour_analysis=1"),
    "agg_country": ("country_iso2, source_code", "usable_for_country=1"),
    "agg_shape": ("shape_code, source_code", "1=1"),
    "agg_source": ("source_code, collection_code, origin_code", "1=1"),
    "agg_nuclear_band": ("distance_band, nearest_facility_key, source_code", "usable_for_nuclear_proximity=1"),
}
MEASURES = "COUNT(*), SUM(has_pending_candidate=0), SUM(has_pending_candidate), SUM(uses_external_evidence)"
AGG_MEASURES = "report_count, report_count_excl_candidates, pending_candidate_reports, external_evidence_reports"
# Gated column → eligibility flag that must hold whenever the column is published.
GATED = {
    "date_key": "usable_for_calendar", "event_year": "usable_for_calendar", "decade": "usable_for_calendar",
    "calendar_precision": "usable_for_calendar", "event_month": "usable_for_month_analysis",
    "year_month": "usable_for_month_analysis", "event_date": "usable_for_day_analysis", "weekday": "usable_for_day_analysis",
    "event_hour": "usable_for_hour_analysis", "lat": "usable_for_map", "lng": "usable_for_map", "cell1_lat": "usable_for_map",
    "cell1_lng": "usable_for_map", "cell5_lat": "usable_for_map", "cell5_lng": "usable_for_map",
    "country_iso2": "usable_for_country", "nearest_facility_key": "usable_for_nuclear_proximity",
    "nuclear_distance_km": "usable_for_nuclear_proximity", "distance_band": "usable_for_nuclear_proximity",
}
SILVER_FLAGS = ("usable_for_calendar", "usable_for_month_analysis", "usable_for_day_analysis", "usable_for_map",
                "usable_for_country", "usable_for_nuclear_proximity", "uses_external_evidence", "is_canonical",
                "canonical_event_id", "day_placeholder_risk", "month_placeholder_risk", "calendar_precision",
                "coordinate_basis", "country_basis", "time_basis", "clock_basis")
LABELLED = {"source_code": ("dim_source", "source_code"), "origin_code": ("dim_origin", "origin_code"),
            "collection_code": ("dim_collection", "collection_code"), "country_iso2": ("dim_country", "country_iso2"),
            "shape_code": ("dim_shape", "shape_code"), "color_code": ("dim_color", "color_code"),
            "duration_bucket": ("dim_duration_bucket", "duration_bucket"), "movement_type": ("dim_movement", "movement_type"),
            "nearest_facility_key": ("dim_nuclear_facility", "nearest_facility_key"),
            "distance_band": ("dim_distance_band", "distance_band"), "date_key": ("dim_date", "date_key"),
            "duplicate_status": ("dim_duplicate_status", "duplicate_status")}


def check(results: list, name: str, passed: bool, detail=None):
    results.append({"check": name, "passed": bool(passed), "detail": detail})
    return passed


def derived_compatibility(catalogs: dict) -> dict:
    """Metrics compatible with each dimension: they share a dataset."""
    metrics = catalogs["metrics"]
    out = {}
    for code, dim in catalogs["dimensions"]["dimensions"].items():
        out[code] = sorted(m for m, spec in metrics.items() if set(spec["datasets"]) & set(dim["datasets"]))
    return out


def catalog_checks(conn, catalogs: dict, results: list):
    datasets, metrics = catalogs["datasets"], catalogs["metrics"]
    dimensions = catalogs["dimensions"]["dimensions"]
    eligibility = set(catalogs["dimensions"]["eligibility"])
    for name, spec in datasets.items():
        actual = [r[1] for r in conn.execute(f'PRAGMA table_info("{name}")')]
        check(results, f"catalog.columns.{name}", set(actual) == set(spec["columns"]),
              {"missing_in_table": sorted(set(spec["columns"]) - set(actual)), "missing_in_catalog": sorted(set(actual) - set(spec["columns"]))})
        check(results, f"catalog.eligibility.{name}", set(spec["eligibility"]) <= eligibility, spec["eligibility"])
        for column, role in spec["columns"].items():
            if role == "dimension":
                ok = column in dimensions and name in dimensions[column]["datasets"]
                check(results, f"catalog.dimension_declared.{name}.{column}", ok)
    for code, dim in dimensions.items():
        for dataset in dim["datasets"]:
            ok = dataset in datasets and datasets[dataset]["columns"].get(code) == "dimension"
            check(results, f"catalog.dimension_present.{code}.{dataset}", ok)
        check(results, f"catalog.dimension_requires.{code}", set(dim["requires"]) <= eligibility, dim["requires"])
    compatibility = derived_compatibility(catalogs)
    declared = {code: sorted(dim.get("compatible_metrics", [])) for code, dim in dimensions.items()}
    check(results, "catalog.dimension_compatible_metrics", declared == compatibility,
          {k: v for k, v in compatibility.items() if declared.get(k) != v} or None)
    for code, metric in metrics.items():
        check(results, f"catalog.metric_requires.{code}", set(metric["requires"]) <= eligibility)
        for dataset, expr in metric["datasets"].items():
            ok = dataset in datasets
            if ok and metric["type"] == "ratio":
                ok = all(dataset in metrics[metric[k]]["datasets"] for k in ("numerator", "denominator"))
            elif ok:
                ok = expr.get("op") in ("count", "sum", "count_distinct", "avg", "min", "max") and (
                    "column" not in expr or expr["column"] in datasets[dataset]["columns"])
            check(results, f"catalog.metric_dataset.{code}.{dataset}", ok, expr)
        bound = metric.get("duplicate_bound")
        if bound:
            pair = metrics.get(bound["pair"], {})
            check(results, f"catalog.duplicate_bound.{code}",
                  pair.get("duplicate_bound", {}).get("pair") == code and set(pair.get("datasets", {})) >= set(metric["datasets"]) - {"report_model_output"})
    used = {c for spec in datasets.values() for c, role in spec["columns"].items() if role == "dimension"}
    check(results, "catalog.no_orphan_dimensions", set(dimensions) == used, sorted(set(dimensions) ^ used))


def model_checks(gold_path: Path, silver_path: Path, bronze_path: Path, policy: dict, catalogs: dict) -> list:
    results: list = []
    uri = lambda p: Path(p).resolve().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri(gold_path), uri=True)) as conn:
        conn.execute("ATTACH DATABASE ? AS silver", (uri(silver_path),))
        conn.execute("ATTACH DATABASE ? AS bronze", (uri(bronze_path),))
        one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]
        check(results, "sqlite.integrity", one("PRAGMA main.integrity_check") == "ok")
        fk = conn.execute("PRAGMA main.foreign_key_check").fetchall()
        check(results, "sqlite.foreign_keys", not fk, fk[:5])
        total = one("SELECT COUNT(*) FROM fact_report")
        silver_total = one("SELECT COUNT(*) FROM silver.sighting")
        bronze_total = one("SELECT COUNT(*) FROM bronze.sighting")
        check(results, "reconcile.total", total == silver_total == bronze_total, {"gold": total, "silver": silver_total, "bronze": bronze_total})
        check(results, "reconcile.ids_silver", one("SELECT COUNT(*) FROM (SELECT report_id FROM fact_report EXCEPT SELECT id FROM silver.sighting)") == 0
              and one("SELECT COUNT(*) FROM (SELECT id FROM silver.sighting EXCEPT SELECT report_id FROM fact_report)") == 0)
        check(results, "reconcile.ids_bronze", one("SELECT COUNT(*) FROM (SELECT report_id FROM fact_report EXCEPT SELECT id FROM bronze.sighting)") == 0
              and one("SELECT COUNT(*) FROM (SELECT id FROM bronze.sighting EXCEPT SELECT report_id FROM fact_report)") == 0)
        by_source = conn.execute("""SELECT COUNT(*) FROM (
            SELECT source_code, COUNT(*) FROM fact_report GROUP BY 1
            EXCEPT SELECT d.name, COUNT(*) FROM silver.sighting s JOIN silver.source_database d ON d.id=s.source_db_id GROUP BY 1)""").fetchone()[0]
        check(results, "reconcile.by_source", by_source == 0,
              dict(conn.execute("SELECT source_code, COUNT(*) FROM fact_report GROUP BY 1").fetchall()))
        mismatch = one("SELECT COUNT(*) FROM fact_report f JOIN silver.sighting_analytical a ON a.id=f.report_id WHERE " +
                       " OR ".join(f"f.{c} IS NOT a.{c}" for c in SILVER_FLAGS) +
                       " OR f.lat IS NOT a.lat OR f.lng IS NOT a.lng OR f.country_iso2 IS NOT (CASE WHEN a.usable_for_country=1 THEN a.canonical_country_iso2 END)")
        check(results, "reconcile.flags_and_values_per_report", mismatch == 0, mismatch)
        pending_silver = one("""SELECT COUNT(*) FROM (SELECT c.sighting_id_a FROM silver.duplicate_candidate c JOIN silver.duplicate_resolution r
            ON r.candidate_id=c.id WHERE r.decision=? UNION SELECT c.sighting_id_b FROM silver.duplicate_candidate c
            JOIN silver.duplicate_resolution r ON r.candidate_id=c.id WHERE r.decision=?)""",
                             policy["duplicates"]["pending_decision"], policy["duplicates"]["pending_decision"])
        pending_gold = one("SELECT SUM(has_pending_candidate) FROM fact_report")
        check(results, "duplicates.pending_reports", pending_gold == pending_silver, {"gold": pending_gold, "silver": pending_silver})
        pairs = one("SELECT SUM(pending_pair_count) FROM fact_report")
        pending_pairs = one("SELECT COUNT(*) FROM silver.duplicate_resolution WHERE decision=?", policy["duplicates"]["pending_decision"])
        check(results, "duplicates.pending_pairs_twice", pairs == 2 * pending_pairs, {"endpoints": pairs, "pairs": pending_pairs})
        check(results, "duplicates.status_consistent", one("""SELECT COUNT(*) FROM fact_report WHERE
            (duplicate_status='confirmed_canonical') IS NOT (in_confirmed_group=1 AND is_canonical=1)
            OR (duplicate_status='confirmed_member') IS NOT (in_confirmed_group=1 AND is_canonical=0)
            OR (duplicate_status='pending_candidate') IS NOT (in_confirmed_group=0 AND has_pending_candidate=1)
            OR (duplicate_status='unique') IS NOT (in_confirmed_group=0 AND has_pending_candidate=0)""") == 0)
        # Gated values exist exactly when their eligibility holds.
        for column, flag in GATED.items():
            leaked = one(f'SELECT COUNT(*) FROM fact_report WHERE {flag}=0 AND "{column}" IS NOT NULL')
            missing = one(f'SELECT COUNT(*) FROM fact_report WHERE {flag}=1 AND "{column}" IS NULL')
            check(results, f"eligibility.gated.{column}", leaked == 0 and missing == 0, {"leaked": leaked, "missing": missing})
        for code, spec in policy["eligibility"].items():
            bad = one(f"SELECT COUNT(*) FROM fact_report WHERE ({spec['flag']}=1) = ({spec['exclusion']} IS NOT NULL)")
            check(results, f"eligibility.exclusion_reason.{code}", bad == 0, bad)
        for code, spec in catalogs["dimensions"]["eligibility"].items():
            for implied in spec.get("implies", []):
                flag, other = spec["flag"], catalogs["dimensions"]["eligibility"][implied]["flag"]
                broken = one(f"SELECT COUNT(*) FROM fact_report WHERE {flag}=1 AND {other}=0")
                check(results, f"eligibility.implies.{code}.{implied}", broken == 0, broken)
        hour_rule = one("""SELECT COUNT(*) FROM fact_report WHERE usable_for_hour_analysis IS NOT
            (usable_for_calendar=1 AND clock_precision IN ('minute','second','fractional_second'))""")
        check(results, "eligibility.hour_rule", hour_rule == 0, hour_rule)
        # Aggregates: per group equal to fact_report under their eligibility, both directions.
        for name, (keys, where) in AGG_KEYS.items():
            expected = f"SELECT {keys}, {MEASURES} FROM fact_report WHERE {where} GROUP BY {keys}"
            actual = f"SELECT {keys}, {AGG_MEASURES} FROM {name}"
            diff = one(f"SELECT COUNT(*) FROM ({expected} EXCEPT {actual})") + one(f"SELECT COUNT(*) FROM ({actual} EXCEPT {expected})")
            check(results, f"aggregate.reconcile.{name}", diff == 0, diff)
            check(results, f"aggregate.total.{name}", one(f"SELECT SUM(report_count) FROM {name}") == one(f"SELECT COUNT(*) FROM fact_report WHERE {where}"))
        for resolution in policy["spatial_cells"]["resolutions_deg"]:
            keys = f"cell{resolution}_lat, cell{resolution}_lng, source_code"
            expected = f"SELECT {resolution}, {keys}, {MEASURES} FROM fact_report WHERE usable_for_map=1 GROUP BY {keys}"
            actual = f"SELECT resolution_deg, cell_lat, cell_lng, source_code, {AGG_MEASURES} FROM agg_spatial_cell WHERE resolution_deg={resolution}"
            diff = one(f"SELECT COUNT(*) FROM ({expected} EXCEPT {actual})") + one(f"SELECT COUNT(*) FROM ({actual} EXCEPT {expected})")
            check(results, f"aggregate.reconcile.agg_spatial_cell.{resolution}", diff == 0, diff)
        check(results, "aggregate.spatial_resolutions", sorted(r[0] for r in conn.execute("SELECT DISTINCT resolution_deg FROM agg_spatial_cell")) ==
              sorted(policy["spatial_cells"]["resolutions_deg"]))
        for name, column in (("agg_year", "event_year"), ("agg_month", "year_month"), ("agg_weekday_hour", "weekday"),
                             ("agg_country", "country_iso2"), ("agg_nuclear_band", "distance_band"), ("agg_spatial_cell", "cell_lat")):
            check(results, f"aggregate.no_ineligible_keys.{name}", one(f"SELECT COUNT(*) FROM {name} WHERE {column} IS NULL") == 0)
        # Coverage: included + excluded = total, included = eligible.
        for (aggregate,) in conn.execute("SELECT DISTINCT aggregate_code FROM agg_coverage").fetchall():
            inc = one("SELECT COALESCE(SUM(report_count),0) FROM agg_coverage WHERE aggregate_code=? AND coverage_status='included'", aggregate)
            exc = one("SELECT COALESCE(SUM(report_count),0) FROM agg_coverage WHERE aggregate_code=? AND coverage_status='excluded'", aggregate)
            agg_total = one(f"SELECT SUM(report_count) FROM {aggregate}") if aggregate != "agg_spatial_cell" else \
                one("SELECT SUM(report_count) FROM agg_spatial_cell WHERE resolution_deg=?", policy["spatial_cells"]["resolutions_deg"][0])
            check(results, f"coverage.{aggregate}", inc + exc == total and inc == agg_total,
                  {"included": inc, "excluded": exc, "total": total, "aggregate": agg_total})
        check(results, "coverage.reasons", one("""SELECT COUNT(*) FROM agg_coverage WHERE (coverage_status='included') = (reason IS NOT NULL)""") == 0)
        expected_aggregates = sorted(list(AGG_KEYS) + ["agg_spatial_cell"])
        check(results, "coverage.all_aggregates", sorted(r[0] for r in conn.execute("SELECT DISTINCT aggregate_code FROM agg_coverage")) == expected_aggregates)
        # Duplicate bounds per aggregate row.
        for name in list(AGG_KEYS) + ["agg_spatial_cell", "agg_coverage"]:
            bad = one(f"""SELECT COUNT(*) FROM {name} WHERE report_count_excl_candidates > report_count
                OR report_count - report_count_excl_candidates != pending_candidate_reports OR report_count <= 0""")
            check(results, f"bounds.{name}", bad == 0, bad)
        # Events.
        groups = one("SELECT COUNT(*) FROM silver.duplicate_group")
        check(results, "events.count", one("SELECT COUNT(*) FROM fact_event") == groups, groups)
        members = one("SELECT SUM(member_count) FROM silver.duplicate_group")
        check(results, "events.members", one("SELECT SUM(member_count) FROM fact_event") == one("SELECT COUNT(*) FROM event_report")
              == one("SELECT SUM(in_confirmed_group) FROM fact_report") == members, members)
        check(results, "events.one_canonical", one("""SELECT COUNT(*) FROM (SELECT canonical_event_id FROM event_report
            GROUP BY canonical_event_id HAVING SUM(is_canonical)!=1 OR COUNT(*)<2)""") == 0)
        check(results, "events.member_count", one("""SELECT COUNT(*) FROM fact_event e WHERE member_count !=
            (SELECT COUNT(*) FROM event_report r WHERE r.canonical_event_id=e.canonical_event_id)""") == 0)
        # Referential integrity of labels and unique keys.
        for column, (table, key) in LABELLED.items():
            orphans = one(f'SELECT COUNT(*) FROM (SELECT DISTINCT "{column}" v FROM fact_report WHERE "{column}" IS NOT NULL) WHERE v NOT IN (SELECT "{key}" FROM {table})')
            check(results, f"refs.{column}", orphans == 0, orphans)
        for name, key in (("dim_source", "source_code"), ("dim_country", "country_iso2"), ("dim_date", "date_key"),
                          ("fact_event", "canonical_event_id"), ("event_report", "report_id"), ("report_model_output", "report_id")):
            check(results, f"keys.unique.{name}", one(f"SELECT COUNT(*) - COUNT(DISTINCT {key}) FROM {name}") == 0)
        check(results, "model_output.one_per_report", one("SELECT COUNT(*) FROM report_model_output") == total)
        catalog_checks(conn, catalogs, results)
    return results


def full_gate(root: Path = ROOT, run_silver_gate: bool = True, layout=None, silver_path: Path | None = None,
              bronze_path: Path | None = None, bronze_manifest: Path | None = None, data: Path | None = None) -> dict:
    """Gate one Gold version (default: the approved one) over the Silver it used."""
    policy = load_policy(root)
    catalogs = load_catalogs(root)
    results: list = []
    data = Path(data or releases.data_root(root))
    if layout is None:
        current = releases.approved(data, "gold")
        if current is None:
            raise ValueError("No hay una carga Gold aprobada; indica --version DIR")
        layout = releases.GoldLayout(current["path"])
        if silver_path is None and current["parent_version"]:
            silver_path = releases.SilverLayout(data / "silver" / "versions" / current["parent_version"]).database
    gold_path = layout.database
    manifest = json.loads(layout.manifest.read_text(encoding="utf-8"))
    if silver_path is None:
        stored = Path(manifest["silver"]["path"])
        silver_path = stored if stored.is_absolute() else data / stored
    bronze_path = Path(bronze_path or data / policy["inputs"]["bronze"]["path"])
    bronze_manifest = Path(bronze_manifest or root / policy["inputs"]["bronze"]["manifest"])
    silver_sha, bronze_sha = digest(silver_path), digest(bronze_path)
    check(results, "manifest.gold_sha256", digest(gold_path) == manifest["gold_sha256"])
    custody = silver_provenance(silver_path, bronze_path, bronze_manifest)
    check(results, "inputs.silver_provenance", custody["passed"], custody["problems"])
    check(results, "inputs.match_gold_manifest", silver_sha == manifest["silver"]["sha256"]
          and bronze_sha == manifest["bronze"]["sha256"], {"silver": silver_sha, "bronze": bronze_sha})
    definitions_sha, _ = definitions_digest(policy, root)
    check(results, "manifest.definitions_current", definitions_sha == manifest["definitions_sha256"], definitions_sha)
    load_id = load_id_for(policy, silver_sha, bronze_sha, definitions_sha)
    check(results, "manifest.load_id", load_id == manifest["load_id"], load_id)
    if run_silver_gate:
        if __package__:
            from .build_gold import silver_gate
        else:
            from build_gold import silver_gate
        readiness = silver_gate(silver_path, bronze_path)
        check(results, "silver.ready_for_exact_snapshot", readiness["ready_for_gold"] and readiness["silver_sha256"] == silver_sha
              and readiness["bronze_sha256"] == bronze_sha, readiness.get("verification"))
    results.extend(model_checks(gold_path, silver_path, bronze_path, policy, catalogs))
    # Serving cache, generated catalog and entities of this version.
    serving_manifest = json.loads(layout.serving_manifest.read_text(encoding="utf-8"))
    serving = layout.serving
    check(results, "serving.manifest", serving_manifest["cache_version"] == policy["serving"]["cache_version"]
          and serving_manifest["sha256"] == digest(serving) and serving_manifest["load_id"] == load_id
          and serving_manifest["gold_sha256"] == manifest["gold_sha256"])
    generated = json.loads((layout.docs / "GOLD_CATALOG.json").read_text(encoding="utf-8"))
    check(results, "docs.catalog_load", generated["load_id"] == load_id)
    entities = json.loads((layout.docs / "GOLD_ENTITIES.json").read_text(encoding="utf-8"))
    check(results, "docs.entities_load", entities["load_id"] == load_id)
    # Certified queries of this load: valid, unchanged and reproducing their expected result.
    sys.path.insert(0, str(root / "scripts"))
    if __package__:
        from . import gold_query
    else:
        import gold_query
    analytics = gold_query.Analytics(root=root, serving=serving, certified_path=layout.certified)
    certified = json.loads(layout.certified.read_text(encoding="utf-8"))
    for item in certified["queries"]:
        try:
            status = analytics.certification_status(item)
            result = analytics.run_certified(item["id"])
            ok = status["valid"] and result["result_type"] == "certified" and \
                gold_query.rows_digest(result["rows"]) == item["expected_result"]["rows_sha256"]
            check(results, f"certified.{item['id']}", ok, status)
        except (ValueError, KeyError) as exc:
            check(results, f"certified.{item['id']}", False, str(exc))
    # Independent verification and evaluation for this exact load.
    verification = json.loads(layout.verification.read_text(encoding="utf-8")) if layout.verification.exists() else {}
    check(results, "verification.independent", verification.get("load_id") == load_id and verification.get("passed") is True,
          {"load_id": verification.get("load_id"), "passed": verification.get("passed")})
    references = json.loads(layout.evals_spec.read_text(encoding="utf-8")) if layout.evals_spec.exists() else {}
    check(results, "evals.references_for_load", (references.get("reference_load") or {}).get("load_id") == load_id)
    evals_path = layout.evals_dir / f"{load_id}.json"
    evals = json.loads(evals_path.read_text(encoding="utf-8")) if evals_path.exists() else {}
    check(results, "evals.current_load", evals.get("load_id") == load_id and evals.get("passed") is True,
          {"passed": evals.get("passed"), "summary": evals.get("summary")})
    check(results, "inputs.unchanged_after_gate", digest(silver_path) == silver_sha and digest(bronze_path) == bronze_sha)
    failed = [r for r in results if not r["passed"]]
    return {"ready_for_agent": not failed, "load_id": load_id, "version": layout.directory.name,
            "gold_sha256": manifest["gold_sha256"],
            "silver_sha256": silver_sha, "bronze_sha256": bronze_sha, "definitions_sha256": definitions_sha,
            "checks": len(results), "failed": failed, "results": results,
            "interpretation": "Aceptación del contrato Gold implementado. No certifica que los informes sean hechos verificados."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", type=Path, help="Directorio de versión Gold (por defecto, la aprobada)")
    parser.add_argument("--output", type=Path, help="Informe (por defecto: <datos>/gold/ufo_gold.readiness.json; "
                                                     "nunca reescribe el de una versión publicada)")
    args = parser.parse_args()
    try:
        result = full_gate(layout=releases.GoldLayout(args.version) if args.version else None)
    except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
        print(f"GOLD NO APTA PARA EL AGENTE: {exc}", file=sys.stderr)
        return 1
    output = args.output or releases.data_root() / "gold" / "ufo_gold.readiness.json"
    write_text(output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    if not result["ready_for_agent"]:
        for item in result["failed"]:
            print(f"FALLA {item['check']}: {item['detail']}", file=sys.stderr)
        print(f"GOLD NO APTA PARA EL AGENTE: {len(result['failed'])} de {result['checks']} controles fallaron", file=sys.stderr)
        return 1
    print(f"Gold apta para el agente: {result['checks']} controles; load_id {result['load_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
