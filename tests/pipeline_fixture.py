"""A complete, tiny data directory for pipeline tests (no external data).

``pipeline_env`` writes Bronze and an approved Silver version (synthetic
fixtures from gold_fixture.py) into ``<folder>/data``, a Bronze manifest and
small certified queries and evaluations, so ``build_all.run(["--solo", "gold"])``
exercises the real Gold chain: model, serving cache, certification,
independent verification, evaluations, ready_for_agent and promotion.
The official Silver acceptance is replaced by ``FakeAcceptance``.

Run as a script it is the worker of the multi-process tests:
    pipeline_fixture.py FOLDER hold-lock      hold the build lock until stdin closes
    pipeline_fixture.py FOLDER gold           run --solo gold and exit with its code
    pipeline_fixture.py FOLDER gold-stall     run --solo gold, stall right before promotion
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
for path in (TESTS, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gold_fixture import reports, sha, write_bronze, write_provenance, write_silver  # noqa: E402
import releases  # noqa: E402

CERTIFIED = {"queries": [
    {"id": "CQ_TEST_SOURCES", "title": "Informes por fuente", "description": "Conteo por fuente",
     "examples": ["¿Cuántos informes tiene cada fuente?", "Informes de cada fuente"], "limitation": "Son informes.",
     "query": {"dataset": "agg_source", "group_by": ["source_code"], "metrics": ["report_count"], "view": "bars"}}]}
EVALS = {"description": "Set mínimo para pruebas del pipeline.", "questions": [
    {"id": "E001", "category": "frequent", "question": "¿Cuántos informes tiene cada fuente?", "expected_behavior": "answer",
     "certified_query_id": "CQ_TEST_SOURCES",
     "expected_query": {"dataset": "agg_source", "group_by": ["source_code"], "metrics": ["report_count"], "view": "bars"},
     "expected_view": "bars", "required_limitations": ["reports_not_facts"], "forbidden_phrases": []},
    {"id": "E002", "category": "trap", "question": "Suma los porcentajes de evidencia externa", "expected_behavior": "reject",
     "attempted_query": {"dataset": "agg_source", "metrics": ["sum_external_evidence_pct"]}, "expected_error": "ratio_not_summable"},
    {"id": "E003", "category": "trap", "question": "¿Informes en el Congo?", "expected_behavior": "clarify",
     "clarify": {"entity_text": "Congo", "kind": "countries", "expect": "ambiguous", "candidates": ["CD", "CG"]}}]}


class FakeAcceptance:
    """Stands in for check_silver_ready.readiness and counts how often it runs."""

    def __init__(self):
        self.calls = []

    def __call__(self, silver: Path, bronze: Path) -> dict:
        self.calls.append((str(silver), str(bronze)))
        return {"ready_for_gold": True, "silver_sha256": sha(silver), "bronze_sha256": sha(bronze), "policy_version": 6,
                "verification": {"passed": True, "checks": 0, "run_id": "fixture"}}


def quiet(*args, **kwargs):
    pass


def promote_silver(env: dict, rows=None, **override) -> str:
    """Register a new approved Silver version built from ``rows``."""
    data = env["data"]
    directory = releases.new_candidate(data, "silver", owner="pipeline")
    layout = releases.SilverLayout(directory)
    write_silver(layout.database, rows)
    write_provenance(env["folder"], None, layout.database, releases.bronze_path(data), manifest=env["manifest"], **override)
    releases.write_release(directory, "silver", sha(layout.database))
    releases.promote(data, "silver", directory, sha(layout.database))
    return directory.name


def pipeline_env(folder: Path, rows=None) -> dict:
    folder = Path(folder)
    data = folder / "data"
    bronze = releases.bronze_path(data)
    bronze.parent.mkdir(parents=True, exist_ok=True)
    write_bronze(bronze, rows)
    env = {"folder": folder, "data": data, "manifest": folder / "bronze.json",
           "certified": folder / "certified_queries.json", "evals": folder / "GOLD_EVALS.json"}
    env["certified"].write_text(json.dumps(CERTIFIED, ensure_ascii=False, indent=2), encoding="utf-8")
    env["evals"].write_text(json.dumps(EVALS, ensure_ascii=False, indent=2), encoding="utf-8")
    env["silver_version"] = promote_silver(env, rows)
    (folder / "env.json").write_text(json.dumps({k: str(v) for k, v in env.items()}), encoding="utf-8")
    return env


def changed_rows():
    """Different Silver contents → different Silver SHA → a different load_id."""
    rows = reports()
    rows[0]["num_witnesses"] = 9
    return rows


def run_gold(env: dict, acceptance=None, before_promote=None, extra=()) -> int:
    import build_all
    return build_all.run(["--solo", "gold", "--datos", str(env["data"]), *extra], bronze_manifest=env["manifest"],
                         certified_source=env["certified"], evals_source=env["evals"],
                         acceptance=acceptance or FakeAcceptance(), before_promote=before_promote, out=quiet)


def _worker(folder: str, mode: str) -> int:
    env = {k: Path(v) if k != "silver_version" else v
           for k, v in json.loads((Path(folder) / "env.json").read_text(encoding="utf-8")).items()}
    if mode == "hold-lock":
        with releases.build_lock(env["data"]):
            print("locked", flush=True)
            sys.stdin.read()
        return 0
    if mode == "gold":
        return run_gold(env)
    if mode == "gold-stall":
        def stall(layer, candidate):
            print(f"ready {candidate.directory}", flush=True)
            time.sleep(120)
        return run_gold(env, before_promote=stall)
    raise SystemExit(f"modo desconocido: {mode}")


if __name__ == "__main__":
    raise SystemExit(_worker(sys.argv[1], sys.argv[2]))
