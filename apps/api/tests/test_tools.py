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


# -- coverage of certified queries (issue #39) ---------------------------------

@pytest.fixture(scope="module")
def coverage_gold(gold, tmp_path_factory):
    """Same serving cache with certified queries by year, by decade and one stale certification."""
    import json
    import gold_query
    path = tmp_path_factory.mktemp("certified") / "certified_queries.json"
    year = {"dataset": "agg_year", "filters": [{"column": "event_year", "op": "gte", "value": 1900}],
            "group_by": ["event_year"], "metrics": ["report_count"], "view": "timeseries", "limit": 500}
    path.write_text(json.dumps({"queries": [
        {"id": "CQ_TEST_YEAR", "title": "Serie anual de informes desde 1900", "description": "Informes por año",
         "examples": ["¿Cómo evolucionan los informes por año?"], "limitation": "Elegibilidad de calendario.", "query": year},
        {"id": "CQ_TEST_DECADE", "title": "Informes por década", "description": "Informes por década",
         "examples": ["¿Cuántos informes hay por década?"], "limitation": "Elegibilidad de calendario.",
         "query": {"dataset": "agg_year", "group_by": ["decade"], "metrics": ["report_count"], "view": "timeseries", "limit": 500}},
        {"id": "CQ_TEST_STALE", "title": "Informes por fuente vencida", "description": "Conteo por fuente vencido",
         "examples": ["¿Cuántos informes tiene cada fuente vencida?"], "limitation": "Son informes.",
         "query": {"dataset": "agg_source", "group_by": ["source_code"], "metrics": ["report_count"], "view": "bars"}}]}))
    gold_query.certify(analytics=gold_query.Analytics(serving=gold.path, certified_path=path))
    data = json.loads(path.read_text())
    data["queries"][2]["verification"]["load_id"] = "otra-carga"
    path.write_text(json.dumps(data))
    return gold_query.Analytics(serving=gold.path, certified_path=path)


COUNTRY_SINCE = {"filters": [{"column": "country_iso2", "op": "eq", "value": "US"},
                             {"column": "event_year", "op": "gte", "value": 1990}], "group_by": ["event_year"]}


def test_candidates_expose_their_real_contract(coverage_gold):
    found = tools.execute(coverage_gold, "search_certified", {"question": "serie anual de informes", "needs": None}, [])
    top = next(c for c in found["candidates"] if c["id"] == "CQ_TEST_YEAR")
    assert top["certified_query"]["dataset"] == "agg_year"
    assert top["certified_query"]["filters"] == [{"column": "event_year", "op": "gte", "value": 1900}]
    assert "Año ≥ 1900" in top["readable_query"]
    assert found["decision"] is None and "coverage" not in top


def test_partial_candidate_leads_to_equivalent_composed_query(coverage_gold):
    found = tools.execute(coverage_gold, "search_certified",
                          {"question": "serie temporal de Estados Unidos desde 1990", "needs": COUNTRY_SINCE}, [])
    year = next(c for c in found["candidates"] if c["id"] == "CQ_TEST_YEAR")
    assert year["valid"] and year["coverage"] == "parcial"
    assert {(m["aspect"], m.get("column")) for m in year["missing"]} == {("filter", "country_iso2"), ("filter", "event_year")}
    assert year["dataset_lacks_columns"] == ["country_iso2"]
    decision = found["decision"]
    assert decision["tool"] == "query_gold"
    query = decision["query"]
    assert query["dataset"] == "fact_report" and query["view"] == "timeseries" and query["group_by"] == ["event_year"]
    assert {"calendar", "country"} <= set(query["eligibility"])
    assert {(f["column"], f["op"], f["value"]) for f in query["filters"]} == {("country_iso2", "eq", "US"), ("event_year", "gte", 1990)}
    visuals = []
    out = tools.execute(coverage_gold, "query_gold", {**query, "title": "Estados Unidos desde 1990"}, visuals)
    assert out["result_type"] == "composed"
    assert "País = Estados Unidos" in out["readable_query"] and "Año ≥ 1990" in out["readable_query"]
    assert out["rows"] and all(r["event_year"] >= 1990 for r in out["rows"])


def test_certified_filter_is_replaced_not_stacked(coverage_gold):
    needs = {"filters": [{"column": "event_year", "op": "gte", "value": 1990}], "group_by": ["event_year"]}
    found = tools.execute(coverage_gold, "search_certified", {"question": "serie anual de informes desde 1990", "needs": needs}, [])
    query = found["decision"]["query"]
    assert query["dataset"] == "agg_year" and query["filters"] == [{"column": "event_year", "op": "gte", "value": 1990}]


def test_full_match_keeps_the_certified_route(coverage_gold):
    found = tools.execute(coverage_gold, "search_certified",
                          {"question": "¿Cuántos informes hay por década?", "needs": {"group_by": ["decade"]}}, [])
    assert found["decision"] == {"tool": "run_certified", "id": "CQ_TEST_DECADE"}
    decade = next(c for c in found["candidates"] if c["id"] == "CQ_TEST_DECADE")
    assert decade["coverage"] == "total" and decade["missing"] == [] and "composed_query" not in decade
    out = tools.execute(coverage_gold, "run_certified", {"id": "CQ_TEST_DECADE"}, [])
    assert out["result_type"] == "certified"


def test_stale_certification_is_replaced_by_equivalent_composition(coverage_gold):
    found = tools.execute(coverage_gold, "search_certified",
                          {"question": "¿Cuántos informes tiene cada fuente vencida?", "needs": {"group_by": ["source_code"]}}, [])
    stale = next(c for c in found["candidates"] if c["id"] == "CQ_TEST_STALE")
    assert stale["valid"] is False and stale["coverage"] == "total"
    assert any("carga Gold" in r for r in stale["invalid_reasons"])
    assert found["decision"]["tool"] == "query_gold"
    assert found["decision"]["query"]["dataset"] == "agg_source" and found["decision"]["query"]["group_by"] == ["source_code"]


def test_needs_are_validated(coverage_gold):
    with pytest.raises(QueryError) as err:
        tools.execute(coverage_gold, "search_certified", {"question": "x", "needs": {"sql": "SELECT 1"}}, [])
    assert err.value.code == "contract"


def test_search_schema_requires_needs(gold):
    search = next(t for t in tools.schemas(gold) if t["name"] == "search_certified")
    assert search["parameters"]["required"] == ["question", "needs"]
    assert set(search["parameters"]["properties"]["needs"]["properties"]) == {"filters", "group_by", "metrics"}
