#!/usr/bin/env python3
"""Record a confirmed error and turn it into a regression question.

Appends the correction to config/gold/corrections.json and a question with
category ``regression`` to docs/GOLD_EVALS.json. The new question has no
reference answer yet: run verify_gold_independent.py --write-references and
run_gold_evals.py afterwards (the Gold gate fails until both pass).

Example:
  record_gold_correction.py --question "¿Cuántos informes hay en 1997?" \
      --wrong "Hubo 9.000 avistamientos" --correct "Entre 4.100 y 9.000 informes" \
      --cause agent_wording --layer agent \
      --query '{"dataset":"agg_year","filters":[{"column":"event_year","op":"eq","value":1997}],"metrics":["report_count"]}' \
      --limitations reports_not_facts pending_duplicates
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

if __package__:
    from .gold_common import ROOT, load_json
    from .gold_query import Analytics
else:
    from gold_common import ROOT, load_json
    from gold_query import Analytics


def record(args, root: Path = ROOT) -> dict:
    corrections_path = root / "config/gold/corrections.json"
    evals_path = root / "docs/GOLD_EVALS.json"
    corrections, evals = load_json(corrections_path), load_json(evals_path)
    if args.cause not in corrections["causes"]:
        raise ValueError(f"Causa desconocida: {args.cause}. Opciones: {corrections['causes']}")
    analytics = Analytics(root=root)
    eval_id = f"E{len(evals['questions']) + 1:03d}"
    question = {"id": eval_id, "category": "regression", "question": args.question,
                "expected_behavior": args.behavior, "certified_query_id": args.certified, "expected_query": None,
                "expected_view": None, "required_limitations": args.limitations, "forbidden_phrases": args.forbidden,
                "note": f"Regresión de la corrección C{len(corrections['corrections']) + 1:03d}: {args.cause}"}
    if args.behavior == "answer":
        if args.query:
            query = json.loads(args.query)
        else:
            query = {i["id"]: i for i in analytics.certified()["queries"]}[args.certified]["query"]
        result = analytics.query(query)          # must be valid in the current contract
        expected = {k: v for k, v in result["query"].items() if k != "title" or v is not None}
        question.update(expected_query=expected, expected_view=result["view"], reference_answer=None)
    elif args.behavior == "reject":
        question.update(attempted_query=json.loads(args.query), expected_error=args.expected_error)
    else:
        question["clarify"] = json.loads(args.clarify)
    correction = {"id": f"C{len(corrections['corrections']) + 1:03d}",
                  "reported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                  "question": args.question, "wrong_answer": args.wrong, "correct_answer": args.correct,
                  "cause": args.cause, "layer": args.layer, "gold_load_id": analytics.load_id,
                  "eval_id": eval_id, "fix": args.fix}
    corrections["corrections"].append(correction)
    evals["questions"].append(question)
    corrections_path.write_text(json.dumps(corrections, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    evals_path.write_text(json.dumps(evals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return correction


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--question", required=True)
    parser.add_argument("--wrong", required=True)
    parser.add_argument("--correct", required=True)
    parser.add_argument("--cause", required=True)
    parser.add_argument("--layer", choices=("agent", "gold", "silver"), required=True)
    parser.add_argument("--behavior", choices=("answer", "reject", "clarify"), default="answer")
    parser.add_argument("--query", help="Consulta tipada (JSON) esperada o intentada")
    parser.add_argument("--certified", help="ID de la consulta certificada esperada")
    parser.add_argument("--expected-error")
    parser.add_argument("--clarify", help='JSON: {"entity_text": "...", "kind": "countries", "expect": "ambiguous", "candidates": [...]}')
    parser.add_argument("--limitations", nargs="*", default=["reports_not_facts"])
    parser.add_argument("--forbidden", nargs="*", default=["está comprobado"])
    parser.add_argument("--fix", default="pendiente")
    args = parser.parse_args()
    try:
        correction = record(args)
    except (ValueError, KeyError, OSError) as exc:
        print(f"CORRECCIÓN NO REGISTRADA: {exc}", file=sys.stderr)
        return 1
    print(f"Registrada {correction['id']} → {correction['eval_id']}. Ejecuta verify_gold_independent.py --write-references y run_gold_evals.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
