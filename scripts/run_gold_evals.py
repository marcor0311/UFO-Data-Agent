#!/usr/bin/env python3
"""Run docs/GOLD_EVALS.json against the Gold tools and record results per load.

For each question:
  answer  → the certified lookup finds the expected certified query (frequent),
            the expected query runs, its view and mandatory limitations match and
            its rows equal the independent reference answer;
  reject  → the attempted query is refused with the expected error code;
  clarify → entity resolution is ambiguous or empty, as expected.
The questions and their reference answers come from the load's own copy
(<versión>/GOLD_EVALS.json, written by the independent verification), else
docs/GOLD_EVALS.json. The build writes results to <versión>/evals/<load_id>.json;
the CLI to <datos>/gold/evals/<load_id>.json. Answers whose result hash changed
with respect to earlier loads are reported as drift.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__:
    from .gold_common import ROOT, load_json, text_digest
    from .gold_query import Analytics, QueryError, query_digest
    from .pipeline_context import write_text
    from . import releases
else:
    from gold_common import ROOT, load_json, text_digest
    from gold_query import Analytics, QueryError, query_digest
    from pipeline_context import write_text
    import releases


def strip(rows):
    return [{k: v for k, v in r.items() if not k.endswith("_label")} for r in rows]


def close(a, b):
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and abs(a - b) <= 1e-3
    return a == b


def rows_equal(expected, actual):
    expected, actual = strip(expected), strip(actual)
    return len(expected) == len(actual) and all(set(e) == set(x) and all(close(e[k], x[k]) for k in e) for e, x in zip(expected, actual))


def evaluate(analytics: Analytics, item: dict) -> dict:
    checks = {}
    result_sha = None
    behavior = item["expected_behavior"]
    if behavior == "answer":
        if item.get("certified_query_id"):
            found = [r["id"] for r in analytics.search_certified(item["question"])]
            checks["certified_lookup"] = item["certified_query_id"] in found
            result = analytics.run_certified(item["certified_query_id"])
            checks["certified_result"] = result["result_type"] == "certified" and result["certified_query_id"] == item["certified_query_id"]
        else:
            result = analytics.query(item["expected_query"])
            checks["composed_result"] = result["result_type"] == "composed"
        checks["same_query"] = query_digest(result["query"], analytics.limits) == query_digest(item["expected_query"], analytics.limits)
        checks["view"] = result["view"] == item["expected_view"]
        codes = {l["code"] for l in result["limitations"]}
        checks["limitations"] = set(item["required_limitations"]) <= codes
        reference = item.get("reference_answer") or {}
        checks["reference_rows"] = rows_equal(reference.get("rows", [None]), result["rows"])
        checks["reference_matched"] = reference.get("matched_source_rows") == result["matched_source_rows"]
        if reference.get("total") is not None:
            checks["reference_total"] = all(close(v, (result["total"] or {}).get(k)) for k, v in reference["total"].items())
        checks["provenance"] = result["provenance"]["gold_load_id"] == analytics.load_id and bool(result["readable_query"]["texto"])
        result_sha = text_digest(strip(result["rows"]))
    elif behavior == "reject":
        try:
            analytics.query(item["attempted_query"])
            checks["rejected"] = False
        except QueryError as exc:
            checks["rejected"] = exc.code == item["expected_error"]
            result_sha = exc.code
    elif behavior == "clarify":
        spec = item["clarify"]
        found = analytics.find_entities(spec["entity_text"], kind=spec.get("kind"))
        ids = sorted(str(e["id"]) for e in found)
        checks["clarify"] = (len(found) >= 2 and ids == sorted(spec["candidates"])) if spec["expect"] == "ambiguous" else not found
        result_sha = text_digest(ids)
    else:
        checks["behavior_known"] = False
    return {"id": item["id"], "category": item["category"], "expected_behavior": behavior,
            "passed": all(checks.values()), "checks": checks, "result_sha256": result_sha}


def evals_for(analytics: Analytics, root: Path = ROOT) -> Path:
    """The load's evaluation set (with its references), else the versioned one."""
    layout = analytics.layout
    return layout.evals_spec if layout and layout.evals_spec.exists() else root / "docs/GOLD_EVALS.json"


def run(root: Path = ROOT, analytics: Analytics | None = None, evals_path: Path | None = None, write: bool = True,
        folder: Path | None = None, previous=None) -> dict:
    """Evaluate one load. ``previous``: folders with results of earlier loads (drift)."""
    analytics = analytics or Analytics(root=root)
    evals = load_json(evals_path or evals_for(analytics, root))
    results = []
    for item in evals["questions"]:
        try:
            results.append(evaluate(analytics, item))
        except (QueryError, KeyError, ValueError) as exc:
            results.append({"id": item["id"], "category": item["category"], "expected_behavior": item["expected_behavior"],
                            "passed": False, "checks": {"error": str(exc)}, "result_sha256": None})
    folder = Path(folder or releases.data_root(root) / "gold" / "evals")
    drift = []
    for source in [folder, *(previous or [])]:
        if not Path(source).exists():
            continue
        for other in sorted(Path(source).glob("*.json")):
            report = json.loads(other.read_text(encoding="utf-8"))
            if report.get("load_id") == analytics.load_id:
                continue
            before = {r["id"]: r["result_sha256"] for r in report.get("results", [])}
            drift += [{"id": r["id"], "previous_load_id": report["load_id"]} for r in results
                      if r["id"] in before and before[r["id"]] != r["result_sha256"]]
    reference_ok = (evals.get("reference_load") or {}).get("load_id") == analytics.load_id
    summary = {"questions": len(results), "passed": sum(r["passed"] for r in results),
               "by_category": {c: sum(1 for r in results if r["category"] == c) for c in ("frequent", "uncommon", "trap", "regression")},
               "references_for_current_load": reference_ok, "drift": len(drift)}
    report = {"load_id": analytics.load_id, "passed": reference_ok and all(r["passed"] for r in results),
              "summary": summary, "drift": drift, "results": results}
    if write:
        folder.mkdir(parents=True, exist_ok=True)
        write_text(folder / f"{analytics.load_id}.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def main() -> int:
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    report = run()
    for r in report["results"]:
        if not r["passed"]:
            print(f"FALLA {r['id']}: {r['checks']}", file=sys.stderr)
    s = report["summary"]
    print(f"Evaluación Gold {report['load_id'][:12]}: {s['passed']}/{s['questions']} aprobadas "
          f"({s['by_category']}); referencias de la carga actual: {s['references_for_current_load']}; deriva: {s['drift']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
