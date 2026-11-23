"""Typed tools over the synthetic Gold cache."""
import pytest

from conftest import call, message  # noqa: F401
from app.agent import tools
from app.gold import QueryError


def test_query_schema_is_generated_from_the_contract(gold):
    schema = tools.query_schema(gold)
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == set(__import__("gold_query").Query.FIELDS)
    assert schema["properties"]["dataset"]["enum"] == sorted(gold.datasets)
    assert schema["properties"]["limit"]["maximum"] == gold.limits["max_limit"]
    assert set(schema["properties"]["eligibility"]["items"]["enum"]) == set(gold.eligibility)


def test_tool_names_and_certified_enum(gold):
    names = [t["name"] for t in tools.schemas(gold)]
    assert names == ["search_certified", "run_certified", "query_gold", "find_entities", "describe_data"]
    run = next(t for t in tools.schemas(gold) if t["name"] == "run_certified")
    assert run["parameters"]["properties"]["id"]["enum"] == ["CQ_TEST_SOURCES"]


def test_query_returns_compact_payload_and_full_visual(gold):
    visuals = []
    out = tools.execute(gold, "query_gold", {"dataset": "agg_source", "group_by": ["source_code"], "metrics": ["report_count"]}, visuals)
    assert len(visuals) == 1 and visuals[0]["provenance"]["gold_load_id"] == gold.load_id
    assert out["duplicate_bounds"]["lower"] == "report_count_excl_candidates"
    assert {"reports_not_facts", "pending_duplicates"} <= {l["code"] for l in out["limitations"]}
    assert "readable_query" in out and "provenance" not in out


def test_invalid_query_raises_repairable_error(gold):
    with pytest.raises(QueryError) as err:
        tools.execute(gold, "query_gold", {"dataset": "fact_report", "group_by": ["event_date"], "metrics": ["report_count"]}, [])
    assert err.value.code == "eligibility_missing"


def test_visual_limit(gold):
    visuals = [{}] * tools.MAX_VISUALS
    with pytest.raises(QueryError) as err:
        tools.execute(gold, "run_certified", {"id": "CQ_TEST_SOURCES"}, visuals)
    assert err.value.code == "visual_limit"


def test_certified_lookup_and_run(gold):
    found = tools.execute(gold, "search_certified", {"question": "¿Cuántos informes tiene cada fuente?"}, [])
    assert found["candidates"][0]["id"] == "CQ_TEST_SOURCES" and found["candidates"][0]["valid"]
    visuals = []
    out = tools.execute(gold, "run_certified", {"id": "CQ_TEST_SOURCES"}, visuals)
    assert out["result_type"] == "certified" and out["certified_query_id"] == "CQ_TEST_SOURCES"


def test_entities_ambiguous_and_missing(gold):
    assert tools.execute(gold, "find_entities", {"text": "Congo", "kind": "countries"}, [])["ambiguous"] is True
    assert tools.execute(gold, "find_entities", {"text": "Narnia", "kind": None}, [])["not_found"] is True
    with pytest.raises(QueryError):
        tools.execute(gold, "find_entities", {"text": "x", "kind": "planets"}, [])


def test_describe_and_unknown_tool(gold):
    assert "fact_report" in tools.execute(gold, "describe_data", {"dataset": None}, [])["datasets"]
    assert "metrics" in tools.execute(gold, "describe_data", {"dataset": "agg_year"}, [])
    with pytest.raises(QueryError) as err:
        tools.execute(gold, "run_sql", {"sql": "SELECT 1"}, [])
    assert err.value.code == "tool_unknown"
