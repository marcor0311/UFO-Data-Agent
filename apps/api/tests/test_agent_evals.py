"""Live evaluation runner, exercised with a scripted model."""
import sys
from pathlib import Path

from conftest import ScriptedStream, call, message

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import run_agent_evals  # noqa: E402
from app.agent.runtime import DataAgent


def item(gold, **kw):
    reference = gold.run_certified("CQ_TEST_SOURCES")
    base = {"id": "E1", "category": "frequent", "question": "¿Cuántos informes tiene cada fuente?", "expected_behavior": "answer",
            "certified_query_id": "CQ_TEST_SOURCES", "expected_query": gold.certified()["queries"][0]["query"],
            "required_limitations": ["reports_not_facts"], "forbidden_phrases": ["hubo {n} avistamientos", "está comprobado"],
            "reference_answer": {"rows": reference["rows"], "matched_source_rows": reference["matched_source_rows"]}}
    return {**base, **kw}


def test_forbidden_phrase_detection():
    assert run_agent_evals.forbidden_hits("Hubo 1.234 avistamientos en 1997", ["hubo {n} avistamientos"]) == ["hubo {n} avistamientos"]
    assert run_agent_evals.forbidden_hits("Hay entre 10 y 20 informes", ["hubo {n} avistamientos", "Está comprobado"]) == []


def test_frequent_question_passes_with_certified_flow(gold):
    stream = ScriptedStream([call("search_certified", {"question": "fuentes"})], [call("run_certified", {"id": "CQ_TEST_SOURCES"})],
                            [message("Hay 9 informes por fuente.")])
    report = run_agent_evals.run(DataAgent(gold, stream=stream), {}, "m", [item(gold)], gold.limits, gold.load_id)
    assert report["passed"], report["results"][0]["checks"]


def test_wording_and_routing_failures_are_caught(gold):
    stream = ScriptedStream([call("query_gold", {"dataset": "agg_source", "group_by": ["source_code"], "metrics": ["report_count"], "view": "table"})],
                            # verificar asks for one rewrite; a model that repeats the phrase is still caught by the grader.
                            [message("Hubo 12 avistamientos.")], [message("Hubo 12 avistamientos.")])
    result = run_agent_evals.run(DataAgent(gold, stream=stream), {}, "m", [item(gold)], gold.limits, gold.load_id)["results"][0]
    assert not result["passed"]
    assert result["checks"]["no_forbidden_phrases"] is False and result["checks"]["searched_certified_first"] is False
    assert result["checks"]["reference_rows"] is True


def test_clarify_and_errors(gold):
    clarify = item(gold, id="E2", category="trap", expected_behavior="clarify", question="¿Informes en el Congo?")
    stream = ScriptedStream([call("find_entities", {"text": "Congo", "kind": "countries"})], [message("¿Te refieres a la República del Congo o a la República Democrática del Congo?")])
    assert run_agent_evals.run(DataAgent(gold, stream=stream), {}, "m", [clarify], gold.limits, gold.load_id)["passed"]
    broken = ScriptedStream()
    report = run_agent_evals.run(DataAgent(gold, stream=broken), {}, "m", [item(gold)], gold.limits, gold.load_id)
    assert not report["passed"] and "error" in report["results"][0]["checks"]
