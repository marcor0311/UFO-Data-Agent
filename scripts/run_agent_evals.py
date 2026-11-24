#!/usr/bin/env python3
"""Run docs/GOLD_EVALS.json through the full agent with a live model.

Unlike run_gold_evals.py (tools and data only), this measures the agent:
  answer  → frequent questions use search_certified and the expected certified
            query; any question passes if one of its visualizations reproduces the
            independent reference rows; mandatory limitations are present in that
            result; no forbidden phrase appears in the text;
  reject  → the agent answers (explaining the limit) without forbidden phrases;
  clarify → no visualization; the agent resolved entities and asked.
Results go to data/agent/evals/<load_id>__<model>.json. Requires a signed-in
ChatGPT account stored by the API (root .env), selected with --account.

  python3.14 scripts/run_agent_evals.py --model gpt-6.1-sol [--ids E001 E021] [--account <id>]

The report also counts answers whose figures match the reference with another shape
(figures_correct, informative) and keeps each turn's trace with arguments and errors.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps/api/src"))

from gold_common import normalize, text_digest  # noqa: E402
from gold_query import query_digest  # noqa: E402
from run_gold_evals import close, rows_equal  # noqa: E402


def forbidden_hits(text: str, phrases: list[str]) -> list[str]:
    plain = normalize(text)
    hits = []
    for phrase in phrases:
        pattern = re.escape(normalize(phrase)).replace(re.escape("{n}"), r"\d[\d ,]*")
        if re.search(pattern, plain):
            hits.append(phrase)
    return hits


def _key(row: dict, columns: list[str]) -> tuple:
    return tuple((c, round(row[c], 2) if isinstance(row[c], float) else row[c]) for c in columns)


def figures_match(reference: list[dict], rows: list[dict]) -> bool:
    """The reference figures reappear in ``rows`` even when the result is shaped differently.

    On the reference columns, the two row sets coincide in any order or one contains the
    other (a top 15 against a top 10, one NUFORC row against the breakdown by origin); or
    ``rows`` is a single total equal to the sum of a reference metric. An equivalent answer for ``reference_rows`` (issue #43)."""
    if not reference or not rows:
        return False
    columns = sorted(reference[0])
    if all(set(columns) <= set(r) for r in rows):
        expected, actual = {_key(r, columns) for r in reference}, {_key(r, columns) for r in rows}
        return expected <= actual or actual <= expected
    metrics = [c for c in columns if isinstance(reference[0][c], (int, float)) and not isinstance(reference[0][c], bool)]
    # Fewer columns: the dimensions and the metrics shown coincide (a share without its count).
    shared = [c for c in columns if all(c in r for r in rows)]
    if set(columns) - set(metrics) <= set(shared) and set(shared) & set(metrics):
        expected, actual = {_key(r, shared) for r in reference}, {_key(r, shared) for r in rows}
        if expected <= actual or actual <= expected:
            return True
    if len(rows) == len(reference) and _same_values(reference, rows, metrics):
        return True
    return len(rows) == 1 and any(m in rows[0] and close(sum(r[m] or 0 for r in reference), rows[0][m]) for m in metrics)


def _values(rows: list[dict], column: str) -> list:
    return sorted(round(r[column], 2) if isinstance(r[column], float) else r[column] for r in rows if r.get(column) is not None)


def _same_values(reference: list[dict], rows: list[dict], metrics: list[str]) -> bool:
    """Every reference metric reappears, value by value, in some column of ``rows``
    (renamed columns: a month as ``event_month`` instead of ``year_month``, ``report_count``
    under a ``has_media`` filter instead of ``media_reports``)."""
    columns = {c for r in rows for c in r}
    return bool(metrics) and all(any(_values(reference, m) == _values(rows, c) for c in columns
                                     if all(c in r for r in rows)) for m in metrics)


def grade(item: dict, turn: dict, limits: dict) -> dict:
    checks = {}
    visuals = turn["visualizations"]
    tools = [t["tool"] for t in turn["trace"] if t["ok"]]
    checks["no_forbidden_phrases"] = not forbidden_hits(turn["answer"], item.get("forbidden_phrases", []))
    if item["expected_behavior"] == "answer":
        reference = item.get("reference_answer") or {}
        rows = reference.get("rows", [None])
        # Same figures with another order, limit or columns are an equivalent answer (issue #43).
        matching = [v for v in visuals if rows_equal(rows, v["rows"])] or [v for v in visuals if figures_match(rows, v["rows"])]
        checks["reference_rows"] = bool(matching)
        if item.get("certified_query_id"):
            checks["searched_certified_first"] = bool(tools) and tools[0] == "search_certified"
            checks["used_certified"] = any(v.get("certified_query_id") == item["certified_query_id"] for v in visuals)
        expected = query_digest(item["expected_query"], limits)
        checks["expected_query_or_equivalent"] = any(query_digest(v["query"], limits) == expected for v in visuals) or bool(matching)
        if matching:
            codes = {l["code"] for l in matching[0]["limitations"]}
            checks["limitations_present"] = set(item["required_limitations"]) <= codes
    elif item["expected_behavior"] == "reject":
        # The contract refuses the attempted query, so it can never be a visualization here;
        # what remains to check is that the agent answered and did not use a forbidden phrase.
        checks["answered"] = bool(turn["answer"].strip())
    else:
        checks["no_visualization"] = not visuals
        checks["resolved_entities"] = "find_entities" in tools
    figures = None
    if item["expected_behavior"] == "answer":
        reference = (item.get("reference_answer") or {}).get("rows", [])
        figures = checks.get("reference_rows") or any(figures_match(reference, v["rows"]) for v in visuals)
    return {"id": item["id"], "category": item["category"], "expected_behavior": item["expected_behavior"],
            "passed": all(checks.values()), "checks": checks, "figures_match": figures, "answer": turn["answer"],
            "tools": [t["tool"] for t in turn["trace"]], "trace": turn["trace"],
            "visualization_queries": [v["query"] for v in visuals], "answer_sha256": text_digest(turn["answer"])}


def run(agent, account: dict, model: str, questions: list[dict], limits: dict, load_id: str) -> dict:
    results = []
    for item in questions:
        try:
            turn = agent.answer(account, item["question"], [], model)
            results.append(grade(item, turn, limits))
        except Exception as exc:  # a failed turn is a failed evaluation, not a crash
            results.append({"id": item["id"], "category": item["category"], "expected_behavior": item["expected_behavior"],
                            "passed": False, "checks": {"error": f"{type(exc).__name__}: {getattr(exc, 'detail', exc)}"}})
    return {"load_id": load_id, "model": model, "run_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "passed": all(r["passed"] for r in results),
            "summary": {"questions": len(results), "passed": sum(r["passed"] for r in results),
                        # Correct figures although shaped differently (order, limit, extra columns), forbidden phrases aside.
                        "figures_correct": sum(bool(r["passed"] or (r.get("figures_match") and r["checks"].get("no_forbidden_phrases")))
                                               for r in results)},
            "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True)
    parser.add_argument("--account", help="ID de cuenta de /api/auth/accounts; por defecto la primera con sesión")
    parser.add_argument("--ids", nargs="*")
    args = parser.parse_args()
    from app.agent.auth import Auth
    from app.agent.runtime import DataAgent
    from app.gold import get_analytics
    analytics = get_analytics()
    auth = Auth()
    key = args.account or next((k for k, a in auth.state["accounts"].items() if a.get("access_token")), None)
    if key is None:
        print("No hay una cuenta con sesión. Inicia sesión en /agent primero.", file=sys.stderr)
        return 1
    _, account = auth.account_by_key(key)
    # The load's own evaluation set carries reference answers for that load.
    layout = getattr(analytics, "layout", None)
    evals_path = layout.evals_spec if layout and layout.evals_spec.exists() else ROOT / "docs/GOLD_EVALS.json"
    questions = json.loads(evals_path.read_text(encoding="utf-8"))["questions"]
    if args.ids:
        questions = [q for q in questions if q["id"] in set(args.ids)]
    report = run(DataAgent(analytics), account, args.model, questions, analytics.limits, analytics.load_id)
    out = ROOT / "data/agent/evals" / f"{analytics.load_id}__{re.sub(r'[^A-Za-z0-9._-]', '_', args.model)}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    s = report["summary"]
    print(f"Evaluación del agente ({args.model}): {s['passed']}/{s['questions']} aprobadas, "
          f"{s['figures_correct']}/{s['questions']} con cifras correctas → {out}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
