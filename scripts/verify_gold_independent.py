#!/usr/bin/env python3
"""Independent verification of Gold, recomputed from Silver.

This script deliberately imports no Gold module (gold_common, build_gold,
gold_query, check_gold_ready). It reads Silver directly, derives every report
attribute with its own code, evaluates the certified queries and the evaluation
questions with its own interpreter and compares the results with Gold.

  verify_gold_independent.py                    verify and write the report
  verify_gold_independent.py --write-references also store reference answers in docs/GOLD_EVALS.json
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
import datetime as dt
import hashlib
import json
import random
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOCK = ("minute", "second", "fractional_second")
# Attributes kept in the virtual rows of partitioned aggregates.
LIGHT = ("source_code", "has_pending_candidate", "uses_external_evidence", "usable_for_map")
FLAG_OF = {"calendar": "usable_for_calendar", "month": "usable_for_month_analysis", "day": "usable_for_day_analysis",
           "hour": "usable_for_hour_analysis", "map": "usable_for_map", "country": "usable_for_country",
           "nuclear_proximity": "usable_for_nuclear_proximity"}
EXCLUSION_OF = {"calendar": "calendar_exclusion", "month": "month_exclusion", "day": "day_exclusion", "hour": "hour_exclusion",
                "map": "map_exclusion", "country": "country_exclusion", "nuclear_proximity": "proximity_exclusion"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def plain(text: str) -> str:
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower()
    return "-".join(re.findall(r"[a-z0-9]+", text))


def ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)


# ---------------------------------------------------------------- Silver records
def load_reports(silver: Path, config: dict, labels: dict) -> list[dict]:
    """One dict per report, computed only from Silver and the Gold policy data."""
    bands = config["distance_bands_km"]
    with closing(ro(silver)) as conn:
        pending = Counter()
        for a, b in conn.execute("""SELECT c.sighting_id_a, c.sighting_id_b FROM duplicate_candidate c, duplicate_resolution r
                                    WHERE r.candidate_id = c.id AND r.decision = 'needs_review'"""):
            pending[a] += 1
            pending[b] += 1
        cursor = conn.execute("""
            SELECT a.id, a.source_name, (SELECT name FROM source_origin WHERE id = a.origin_id),
                   (SELECT c.name FROM source_database d JOIN source_collection c ON c.id = d.collection_id WHERE d.id = a.source_db_id),
                   a.date_event, a.date_status, a.date_certainty, a.usable_for_calendar, a.usable_for_month_analysis,
                   a.usable_for_day_analysis, a.day_placeholder_risk, a.month_placeholder_risk, a.calendar_precision,
                   CAST(strftime('%w', substr(a.date_event, 1, 10)) AS INTEGER), a.datetime_precision,
                   substr(a.sighting_datetime, 12, 2), a.lat, a.lng, a.coordinate_status, a.usable_for_map,
                   a.canonical_country_iso2, a.country_status, a.usable_for_country, a.standardized_shape, a.primary_color,
                   a.duration_bucket, a.movement_type, a.hynek, a.has_media, a.nearest_nuclear_site_name,
                   a.distance_to_nearest_nuclear_site_km, a.usable_for_nuclear_proximity, a.uses_external_evidence,
                   a.canonical_event_id, a.is_canonical, m.match_status, a.hoax_likelihood, a.quality_score,
                   a.vader_compound, a.roberta_sentiment, a.emotion_7_dominant, a.emotion_28_group, a.event_year,
                   a.coordinate_basis, a.country_basis
            FROM sighting_analytical a JOIN event_membership m ON m.sighting_id = a.id""")
        reports = []
        for row in cursor:
            (rid, source, origin, collection, date_event, date_status, certainty, cal, month_ok, day_ok, day_ph, month_ph,
             precision, sqlite_weekday, clock, hour_text, lat, lng, coord_status, map_ok, iso2, country_status, country_ok,
             shape, color, duration, movement, hynek, media, facility, distance, prox_ok, external, canonical, is_canonical,
             match, hoax, quality, vader, roberta, emo7, emo28, year, coordinate_basis, country_basis) = row
            r = {"report_id": rid, "source_code": source, "origin_code": origin, "collection_code": collection,
                 "shape_code": shape, "color_code": color, "duration_bucket": duration, "movement_type": movement,
                 "hynek": hynek, "has_media": media, "uses_external_evidence": external, "is_canonical": is_canonical,
                 "canonical_event_id": canonical, "calendar_precision": precision, "date_status": date_status,
                 "date_certainty": certainty, "coordinate_status": coord_status, "country_status": country_status,
                 "clock_precision": clock, "hoax_likelihood": hoax, "quality_score": quality, "vader_compound": vader,
                 "roberta_sentiment": roberta, "emotion_7_dominant": emo7, "emotion_28_group": emo28,
                 "coordinate_basis": coordinate_basis, "country_basis": country_basis}
            r["color_family"] = labels["color_code"][color][1] if color else None
            r["usable_for_calendar"], r["usable_for_month_analysis"], r["usable_for_day_analysis"] = cal, month_ok, day_ok
            r["usable_for_map"], r["usable_for_country"], r["usable_for_nuclear_proximity"] = map_ok, country_ok, prox_ok
            hour_ok = int(cal == 1 and clock in CLOCK)
            r["usable_for_hour_analysis"] = hour_ok
            r["event_year"] = year if cal else None
            r["decade"] = year - year % 10 if cal else None
            r["date_key"] = None if not cal else date_event[:4] if precision == "year" else date_event[:7] if precision == "month" else date_event[:10]
            r["event_month"] = int(date_event[5:7]) if month_ok else None
            r["year_month"] = date_event[:7] if month_ok else None
            r["event_date"] = date_event[:10] if day_ok else None
            # SQLite %w: Sunday=0 … Saturday=6 → ISO Monday=1 … Sunday=7.
            r["weekday"] = (7 if sqlite_weekday == 0 else sqlite_weekday) if day_ok else None
            r["event_hour"] = int(hour_text) if hour_ok else None
            r["lat"], r["lng"] = (lat, lng) if map_ok else (None, None)
            for res in config["spatial_cells"]["resolutions_deg"]:
                if map_ok:
                    r[f"cell{res}_lat"] = min(int(lat // res) * res, 90 - res)
                    r[f"cell{res}_lng"] = min(int(lng // res) * res, 180 - res)
                else:
                    r[f"cell{res}_lat"] = r[f"cell{res}_lng"] = None
            r["country_iso2"] = iso2 if country_ok else None
            r["nearest_facility_key"] = plain(facility) if prox_ok else None
            r["nuclear_distance_km"] = distance if prox_ok else None
            r["distance_band"] = None
            if prox_ok:
                for band in bands:
                    upper = band["max"] if band["max"] is not None else float("inf")
                    if band["min"] <= distance < upper:
                        r["distance_band"] = band["code"]
            r["pending_pair_count"] = pending.get(rid, 0)
            r["has_pending_candidate"] = int(rid in pending)
            r["in_confirmed_group"] = int(match == "confirmed_exact")
            r["duplicate_status"] = ("confirmed_canonical" if is_canonical else "confirmed_member") if match == "confirmed_exact" \
                else "pending_candidate" if rid in pending else "unique"
            # Exclusion reasons, from the Silver fields.
            size = len(date_event or "")
            if cal:
                calendar = None
            else:
                calendar = "date_qualified" if date_status == "valid" else f"date_{date_status}"
            def temporal(include_day):
                if calendar:
                    return calendar
                if size == 4:
                    return "precision_year"
                if include_day and size == 7:
                    return "precision_month"
                if month_ph:
                    return "month_day_placeholder"
                return "day_placeholder"
            r["calendar_exclusion"] = calendar
            r["month_exclusion"] = None if month_ok else temporal(False)
            r["day_exclusion"] = None if day_ok else temporal(True)
            r["hour_exclusion"] = None if hour_ok else calendar or f"clock_precision_{clock or 'unknown'}"
            r["map_exclusion"] = None if map_ok else f"coordinates_{coord_status}"
            r["country_exclusion"] = None if country_ok else f"country_{country_status}"
            r["proximity_exclusion"] = None if prox_ok else (r["map_exclusion"] or "proximity_missing")
            reports.append(r)
    return reports


def load_events(silver: Path, reports_by_id: dict) -> list[dict]:
    with closing(ro(silver)) as conn:
        groups = conn.execute("SELECT canonical_event_id, member_count FROM duplicate_group").fetchall()
        members = defaultdict(list)
        for sid, cid in conn.execute("SELECT sighting_id, canonical_event_id FROM event_membership WHERE match_status='confirmed_exact'"):
            members[cid].append(sid)
    events = []
    for cid, count in groups:
        canonical = reports_by_id[cid]
        events.append({"canonical_event_id": cid, "member_count": count,
                       "distinct_source_count": len({reports_by_id[m]["source_code"] for m in members[cid]}),
                       "event_year": canonical["event_year"], "country_iso2": canonical["country_iso2"],
                       "shape_code": canonical["shape_code"], "usable_for_calendar": canonical["usable_for_calendar"],
                       "usable_for_country": canonical["usable_for_country"], "_members": members[cid]})
    return events


# ---------------------------------------------------------------- interpreter
class Interpreter:
    """Evaluate the typed query JSON independently of the Gold engine."""

    def __init__(self, reports, events, datasets, config):
        self.reports, self.events, self.datasets, self.config = reports, events, datasets, config
        self.coverage_plan = {"agg_year": ["calendar"], "agg_month": ["month"], "agg_weekday_hour": ["day", "hour"],
                              "agg_country": ["country"], "agg_shape": [], "agg_source": [],
                              "agg_spatial_cell": ["map"], "agg_nuclear_band": ["nuclear_proximity"]}

    def rows_for(self, dataset, filters):
        if dataset == "fact_event":
            return self.events
        if dataset == "event_report":
            return [{"canonical_event_id": e["canonical_event_id"], "report_id": m, "is_canonical": int(m == e["canonical_event_id"])}
                    for e in self.events for m in e["_members"]]
        if dataset == "agg_spatial_cell":
            fixed = [f["value"] for f in filters if f["column"] == "resolution_deg" and f.get("op", "eq") == "eq"]
            resolutions = fixed or self.config["spatial_cells"]["resolutions_deg"]
            return [{"resolution_deg": res, "cell_lat": r[f"cell{res}_lat"], "cell_lng": r[f"cell{res}_lng"],
                     **{k: r[k] for k in LIGHT}} for res in resolutions for r in self.reports if r["usable_for_map"]]
        if dataset == "agg_coverage":
            out = []
            for name, eligibility in self.coverage_plan.items():
                for r in self.reports:
                    ok = all(r[FLAG_OF[e]] for e in eligibility)
                    reason = None if ok else next(r[EXCLUSION_OF[e]] for e in eligibility if r[EXCLUSION_OF[e]])
                    out.append({"aggregate_code": name, "eligibility_code": "+".join(eligibility) or "none",
                                "coverage_status": "included" if ok else "excluded", "reason": reason, **{k: r[k] for k in LIGHT}})
            return out
        return self.reports

    @staticmethod
    def match(row, f):
        value, op, target = row.get(f["column"]), f.get("op", "eq"), f.get("value")
        if isinstance(target, bool):
            target = int(target)
        if op == "is_null":
            return (value is None) if target is not False else (value is not None)
        if value is None:
            return False
        if op == "eq":
            return value == target
        if op == "ne":
            return value != target
        if op == "in":
            return value in target
        if op == "gte":
            return value >= target
        if op == "lte":
            return value <= target
        raise ValueError(op)

    def metric(self, code, rows, dataset):
        count = len(rows)
        def total(key):
            return sum(r[key] or 0 for r in rows)
        if code == "report_count":
            return count
        if code == "report_count_excl_candidates":
            return sum(1 for r in rows if not r["has_pending_candidate"])
        if code == "pending_candidate_reports":
            return total("has_pending_candidate")
        if code == "external_evidence_reports":
            return total("uses_external_evidence")
        if code == "confirmed_group_reports":
            return total("in_confirmed_group")
        if code == "canonical_representative_reports":
            return total("is_canonical")
        if code == "media_reports":
            return total("has_media")
        if code == "event_count":
            return count
        if code == "event_member_reports":
            return total("member_count") if dataset == "fact_event" else count
        ratios = {"external_evidence_pct": "external_evidence_reports", "pending_candidate_pct": "pending_candidate_reports",
                  "media_pct": "media_reports"}
        if code in ratios:
            num, den = self.metric(ratios[code], rows, dataset), count
            return None if den == 0 else round(100.0 * num / den, 4)
        if code == "distinct_country_count":
            return len({r["country_iso2"] for r in rows if r["country_iso2"] is not None})
        if code in ("first_year", "last_year"):
            years = [r["event_year"] for r in rows if r["event_year"] is not None]
            return (min(years) if code == "first_year" else max(years)) if years else None
        averages = {"avg_nuclear_distance_km": "nuclear_distance_km", "avg_hoax_likelihood": "hoax_likelihood",
                    "avg_quality_score": "quality_score", "avg_vader_compound": "vader_compound",
                    "avg_roberta_sentiment": "roberta_sentiment"}
        if code in averages:
            values = [r[averages[code]] for r in rows if r[averages[code]] is not None]
            return round(sum(values) / len(values), 4) if values else None
        if code == "scored_reports":
            return sum(1 for r in rows if r["hoax_likelihood"] is not None)
        raise ValueError(f"Métrica sin implementación independiente: {code}")

    def evaluate(self, query: dict) -> dict:
        dataset = query["dataset"]
        filters = query.get("filters", [])
        eligibility = set(self.datasets[dataset]["eligibility"]) | set(query.get("eligibility", []))
        rows = [r for r in self.rows_for(dataset, filters)
                if all(r[FLAG_OF[e]] for e in eligibility) and all(self.match(r, f) for f in filters)]
        group_by = query.get("group_by", [])
        metrics = list(query.get("metrics", []))
        if "report_count" in metrics and "report_count_excl_candidates" not in metrics and dataset not in ("report_model_output",):
            metrics.append("report_count_excl_candidates")
        if "report_count_excl_candidates" in metrics and "report_count" not in metrics:
            metrics.append("report_count")
        matched = len(rows)
        limit = query.get("limit", self.config["query"]["default_limit"])
        if not metrics:
            columns = query.get("columns") or self.datasets[dataset]["default_columns"]
            key = next(c for c, role in self.datasets[dataset]["columns"].items() if role == "key")
            ordered = sorted(rows, key=lambda r: r[key])
            return {"rows": [{c: r[c] for c in columns} for r in ordered[:limit]], "matched_source_rows": matched,
                    "truncated": len(rows) > limit, "total": None}
        groups = defaultdict(list)
        for r in rows:
            groups[tuple(r[g] for g in group_by)].append(r)
        out = [{**dict(zip(group_by, key)), **{m: self.metric(m, members, dataset) for m in metrics}} for key, members in groups.items()]
        nulls_first = lambda v: (0, 0) if v is None else (1, v)
        for g in reversed(group_by):
            out.sort(key=lambda row: nulls_first(row[g]))
        order_by, descending = query.get("order_by"), query.get("descending", True)
        if order_by:
            out.sort(key=lambda row: nulls_first(row[order_by]), reverse=descending)
        elif group_by and query.get("view", "table") not in ("timeseries", "hour_weekday", "density"):
            out.sort(key=lambda row: nulls_first(row[metrics[0]]), reverse=True)
        total = {m: self.metric(m, rows, dataset) for m in metrics} if query.get("rollup") else None
        return {"rows": out[:limit], "matched_source_rows": matched if dataset != "fact_event" else len(rows),
                "truncated": len(out) > limit, "total": total}


def strip_labels(rows):
    return [{k: v for k, v in row.items() if not k.endswith("_label")} for row in rows]


def same(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and abs(a - b) <= 1e-3
    return a == b


def same_rows(expected, actual) -> bool:
    expected, actual = strip_labels(expected), strip_labels(actual)
    return len(expected) == len(actual) and all(
        set(e) == set(a) and all(same(e[k], a[k]) for k in e) for e, a in zip(expected, actual))


# ---------------------------------------------------------------- verification
def verify(root: Path = ROOT, write_references: bool = False) -> dict:
    config = json.loads((root / "config/gold/gold.json").read_text())
    datasets = json.loads((root / "config/gold/dataset_catalog.json").read_text())["datasets"]
    labels = json.loads((root / "config/gold/dimension_catalog.json").read_text())["labels"]
    silver = root / config["inputs"]["silver"]["path"]
    gold = root / config["outputs"]["database"]
    manifest = json.loads(gold.with_name(gold.stem + ".manifest.json").read_text())
    checks = []

    def record(name, passed, detail=None):
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    silver_sha = sha256_file(silver)
    record("silver.pinned", silver_sha == config["inputs"]["silver"]["sha256"] == manifest["silver"]["sha256"], silver_sha)
    record("gold.manifest_sha256", sha256_file(gold) == manifest["gold_sha256"])
    reports = load_reports(silver, config, labels)
    by_id = {r["report_id"]: r for r in reports}
    events = load_events(silver, by_id)
    with closing(ro(gold)) as g:
        one = lambda sql, *a: g.execute(sql, a).fetchone()[0]
        record("totals.reports", len(reports) == one("SELECT COUNT(*) FROM fact_report"), len(reports))
        independent = {
            "by_source": Counter(r["source_code"] for r in reports),
            "by_year": Counter(r["event_year"] for r in reports if r["usable_for_calendar"]),
            "by_country": Counter(r["country_iso2"] for r in reports if r["usable_for_country"]),
            "by_shape": Counter(r["shape_code"] for r in reports),
        }
        gold_side = {
            "by_source": dict(g.execute("SELECT source_code, SUM(report_count) FROM agg_source GROUP BY 1")),
            "by_year": dict(g.execute("SELECT event_year, SUM(report_count) FROM agg_year GROUP BY 1")),
            "by_country": dict(g.execute("SELECT country_iso2, SUM(report_count) FROM agg_country GROUP BY 1")),
            "by_shape": dict(g.execute("SELECT shape_code, SUM(report_count) FROM agg_shape GROUP BY 1")),
        }
        for name in independent:
            diff = {str(k): (independent[name].get(k), gold_side[name].get(k)) for k in set(independent[name]) | set(gold_side[name])
                    if independent[name].get(k) != gold_side[name].get(k)}
            record(f"totals.{name}", not diff, dict(list(diff.items())[:10]) or {"groups": len(independent[name])})
        pending = sum(r["has_pending_candidate"] for r in reports)
        record("bounds.pending_reports", pending == one("SELECT SUM(has_pending_candidate) FROM fact_report"), pending)
        upper = Counter(r["event_year"] for r in reports if r["usable_for_calendar"])
        lower = Counter(r["event_year"] for r in reports if r["usable_for_calendar"] and not r["has_pending_candidate"])
        gold_bounds = {y: (u, l) for y, u, l in g.execute("SELECT event_year, SUM(report_count), SUM(report_count_excl_candidates) FROM agg_year GROUP BY 1")}
        bad = [y for y in upper if gold_bounds.get(y) != (upper[y], lower[y]) or lower[y] > upper[y]]
        record("bounds.by_year", not bad, bad[:10])
        record("events.count", len(events) == one("SELECT COUNT(*) FROM fact_event"), len(events))
        record("events.members", sum(e["member_count"] for e in events) == one("SELECT COUNT(*) FROM event_report"),
               sum(e["member_count"] for e in events))
        # Sample of individual reports (fixed seed, plus the extremes of the ID range).
        ids = sorted(by_id)
        sample = sorted(set(random.Random(20261122).sample(ids, 2000)) | {ids[0], ids[-1]})
        columns = [c for c in ("source_code", "origin_code", "collection_code", "date_key", "event_year", "decade", "event_month",
                               "year_month", "event_date", "weekday", "event_hour", "lat", "lng", "cell1_lat", "cell1_lng",
                               "cell5_lat", "cell5_lng", "country_iso2", "shape_code", "color_code", "color_family",
                               "duration_bucket", "movement_type", "hynek", "has_media", "nearest_facility_key",
                               "nuclear_distance_km", "distance_band", "usable_for_calendar", "usable_for_month_analysis",
                               "usable_for_day_analysis", "usable_for_hour_analysis", "usable_for_map", "usable_for_country",
                               "usable_for_nuclear_proximity", "calendar_exclusion", "month_exclusion", "day_exclusion",
                               "hour_exclusion", "map_exclusion", "country_exclusion", "proximity_exclusion",
                               "uses_external_evidence", "canonical_event_id", "is_canonical", "in_confirmed_group",
                               "duplicate_status", "has_pending_candidate", "pending_pair_count", "calendar_precision")]
        mismatches = []
        for rid in sample:
            row = g.execute("SELECT " + ",".join(f'"{c}"' for c in columns) + " FROM fact_report WHERE report_id=?", (rid,)).fetchone()
            for column, value in zip(columns, row):
                if not same(by_id[rid][column], value):
                    mismatches.append({"report_id": rid, "column": column, "silver_derived": by_id[rid][column], "gold": value})
        record("sample.reports", not mismatches, {"sampled": len(sample), "columns": len(columns), "mismatches": mismatches[:10]})
    interpreter = Interpreter(reports, events, datasets, config)
    certified = json.loads((root / "config/gold/certified_queries.json").read_text())
    for item in certified["queries"]:
        expected = item.get("expected_result") or {}
        result = interpreter.evaluate(item["query"])
        ok = (item.get("verification") or {}).get("load_id") == manifest["load_id"] and same_rows(result["rows"], expected.get("rows", [])) \
            and result["matched_source_rows"] == expected.get("matched_source_rows") and result["truncated"] == expected.get("truncated")
        record(f"certified.{item['id']}", ok, {"independent_rows": len(result["rows"]), "gold_rows": len(expected.get("rows", []))})
    evals_path = root / "docs/GOLD_EVALS.json"
    evals = json.loads(evals_path.read_text())
    for item in evals["questions"]:
        if item["expected_behavior"] != "answer":
            continue
        result = interpreter.evaluate(item["expected_query"])
        reference = {"rows": strip_labels(result["rows"]), "matched_source_rows": result["matched_source_rows"],
                     "truncated": result["truncated"], "total": result["total"]}
        if write_references:
            item["reference_answer"] = reference
        else:
            stored = item.get("reference_answer") or {}
            ok = same_rows(reference["rows"], stored.get("rows", [])) and reference["matched_source_rows"] == stored.get("matched_source_rows")
            record(f"evals.reference.{item['id']}", ok)
    if write_references:
        evals["reference_load"] = {"load_id": manifest["load_id"], "silver_sha256": silver_sha,
                                   "computed_by": "scripts/verify_gold_independent.py",
                                   "computed_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}
        evals_path.write_text(json.dumps(evals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record("silver.unchanged", sha256_file(silver) == silver_sha)
    passed = all(c["passed"] for c in checks)
    report = {"load_id": manifest["load_id"], "silver_sha256": silver_sha, "gold_sha256": manifest["gold_sha256"],
              "passed": passed, "checks": len(checks), "failed": [c for c in checks if not c["passed"]], "results": checks,
              "independent_totals": {"reports": len(reports), "pending_candidate_reports": pending,
                                     "reports_excl_candidates": len(reports) - pending, "confirmed_events": len(events),
                                     "by_source": dict(sorted(independent["by_source"].items()))},
              "method": "Recalculado desde Silver sin importar código Gold: lectura directa de sighting_analytical, duplicate_candidate/"
                        "duplicate_resolution y event_membership; día de la semana por strftime de SQLite; celdas y bandas con aritmética propia."}
    out = gold.with_name(gold.stem + ".verification.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write-references", action="store_true")
    args = parser.parse_args()
    try:
        report = verify(write_references=args.write_references)
    except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
        print(f"VERIFICACIÓN INDEPENDIENTE FALLIDA: {exc}", file=sys.stderr)
        return 1
    for item in report["failed"]:
        print(f"FALLA {item['check']}: {item['detail']}", file=sys.stderr)
    print(f"Verificación independiente: {'aprobada' if report['passed'] else 'RECHAZADA'} — {report['checks']} controles; "
          f"{report['independent_totals']['reports']} informes")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
