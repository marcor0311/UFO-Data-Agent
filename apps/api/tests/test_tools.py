"""Typed tools over the synthetic Gold cache."""
import pytest

from conftest import call, message  # noqa: F401
from app.agent import tools
from app.gold import QueryError


def test_query_schema_is_generated_from_the_contract(gold):
    schema = tools.query_schema(gold)
    assert schema["additionalProperties"] is False
    # area comes from the map selection in the web app; the server injects it, the model never sends it.
    assert set(schema["properties"]) == set(__import__("gold_query").Query.FIELDS) - {"area"}
    assert schema["properties"]["dataset"]["enum"] == sorted(gold.datasets)
    # The general ceiling is in the description; only density may ask for every cell.
    assert str(gold.limits["max_limit"]) in schema["properties"]["limit"]["description"]
    assert schema["properties"]["limit"]["maximum"] == __import__("gold_query").DENSITY_MAX_CELLS
    assert set(schema["properties"]["eligibility"]["items"]["enum"]) == set(gold.eligibility)


def test_tool_names_and_certified_enum(gold):
    names = [t["name"] for t in tools.schemas(gold)]
    assert names == ["search_certified", "run_certified", "query_gold", "analyze", "find_entities", "describe_data"]
    run = next(t for t in tools.schemas(gold) if t["name"] == "run_certified")
    assert run["parameters"]["properties"]["id"]["enum"] == ["CQ_TEST_SOURCES"]


def test_query_returns_compact_payload_and_full_visual(gold):
    visuals = []
    out = tools.execute(gold, "query_gold", {"dataset": "agg_source", "group_by": ["source_code"], "metrics": ["report_count"]}, visuals)
    assert len(visuals) == 1 and visuals[0]["provenance"]["gold_load_id"] == gold.load_id
    assert "reports_not_facts" in {l["code"] for l in out["limitations"]}
    assert "readable_query" in out and "provenance" not in out


def test_invalid_query_raises_repairable_error(gold):
    with pytest.raises(QueryError) as err:
        tools.execute(gold, "query_gold", {"dataset": "fact_report", "group_by": ["event_date"], "metrics": ["report_count"]}, [])
    assert err.value.code == "eligibility_missing"


@pytest.mark.parametrize("dataset, filters, eligibility, scope", [
    ("fact_report", [{"column": "country_iso2", "value": "US"}, {"column": "event_year", "value": 1997}],
     ["calendar", "country"], "filtros no temporales ni geográficos de la consulta"),
    ("agg_year", [{"column": "event_year", "value": 1997}], [], "agregado completo"),
    ("agg_year", [{"column": "source_code", "value": "UFOCAT"}], [], "filtros de fuente"),
    ("agg_year", [], [], "todas las fuentes"),
])
def test_model_receives_gold_exclusion_scope(gold, dataset, filters, eligibility, scope):
    """Eligibility populations can be broader than the country/year shown in the result."""
    visuals = []
    out = tools.execute(gold, "query_gold", {
        "dataset": dataset, "filters": filters, "eligibility": eligibility,
        "group_by": ["event_year"], "metrics": ["report_count"],
    }, visuals)
    full = visuals[0]["exclusions"]
    assert out["exclusions"]["scope"] == full["scope"] == scope
    for key in ("base_reports", "eligible_reports", "excluded_reports"):
        assert out["exclusions"][key] == full[key]
    if dataset == "fact_report":
        assert out["rows"][0]["report_count"] == 3
        assert full["base_reports"] == 12
        assert full["eligible_reports"] == 8
        assert full["excluded_reports"] == 4


def test_model_has_no_exclusions_without_eligibility(gold):
    visuals = []
    out = tools.execute(gold, "query_gold", {
        "dataset": "agg_source", "group_by": ["source_code"], "metrics": ["report_count"],
    }, visuals)
    assert out["exclusions"] is None and visuals[0]["exclusions"] is None


def test_costa_rica_1997_keeps_exclusions_separate_from_the_filtered_count(tmp_path, monkeypatch):
    import gold_fixture

    rows = [*gold_fixture.reports(), gold_fixture.report(13, "UFOCAT", canonical_country_iso2="CR")]
    monkeypatch.setattr(gold_fixture, "reports", lambda: rows)
    gold, _, _ = gold_fixture.serving_fixture(tmp_path)
    visuals = []
    out = tools.execute(gold, "query_gold", {
        "dataset": "fact_report", "filters": [{"column": "country_iso2", "value": "CR"},
                                                 {"column": "event_year", "value": 1997}],
        "eligibility": ["calendar", "country"], "metrics": ["report_count"],
    }, visuals)
    assert out["rows"][0]["report_count"] == 1
    assert "Costa Rica" in out["readable_query"] and "1997" in out["readable_query"]
    assert out["exclusions"]["scope"] == visuals[0]["exclusions"]["scope"]
    assert out["exclusions"]["base_reports"] == 13
    assert out["exclusions"]["eligible_reports"] == 9
    assert out["exclusions"]["excluded_reports"] == 4


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
    decision = found["decision"]
    assert (decision["tool"], decision["id"], decision["executed"]) == ("run_certified", "CQ_TEST_DECADE", True)
    decade = next(c for c in found["candidates"] if c["id"] == "CQ_TEST_DECADE")
    assert decade["coverage"] == "total" and decade["missing"] == [] and "composed_query" not in decade
    out = tools.execute(coverage_gold, "run_certified", {"id": "CQ_TEST_DECADE"}, [])
    assert out["result_type"] == "certified"


def test_certified_with_total_coverage_runs_in_the_search_step(coverage_gold):
    """One round trip less: the search that finds a full match already shows it."""
    visuals = []
    found = tools.execute(coverage_gold, "search_certified",
                          {"question": "¿Cuántos informes hay por década?", "needs": {"group_by": ["decade"]}}, visuals)
    assert len(visuals) == 1 and visuals[0]["certified_query_id"] == "CQ_TEST_DECADE"
    assert found["decision"]["result"]["result_type"] == "certified" and found["decision"]["result"]["rows"]
    again = tools.execute(coverage_gold, "run_certified", {"id": "CQ_TEST_DECADE"}, visuals)
    assert len(visuals) == 1 and "ya se muestra" in again["note"]


def test_partial_coverage_is_not_executed(coverage_gold):
    visuals = []
    needs = {"filters": [{"column": "event_year", "op": "gte", "value": 1990}], "group_by": ["event_year"]}
    found = tools.execute(coverage_gold, "search_certified", {"question": "serie anual desde 1990", "needs": needs}, visuals)
    assert found["decision"]["tool"] == "query_gold" and "executed" not in found["decision"] and visuals == []


def test_repeated_query_is_not_run_or_shown_twice(gold):
    visuals = []
    query = {"dataset": "agg_source", "group_by": ["source_code"], "metrics": ["report_count"], "view": "bars"}
    tools.execute(gold, "query_gold", {**query, "title": "Fuentes"}, visuals)
    out = tools.execute(gold, "query_gold", {**query, "title": "Otra vez"}, visuals)
    assert len(visuals) == 1 and out["rows"] and "ya se muestra" in out["note"]


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


def test_report_count_is_a_single_figure(gold):
    """Each report is one unit: asking for report_count returns one number, not a range."""
    visuals = []
    out = tools.execute(gold, "query_gold", {"dataset": "agg_year", "group_by": ["event_year"], "metrics": ["report_count"]}, visuals)
    assert out["rows"] and all(set(r) - {"event_year", "event_year_label"} == {"report_count"} for r in out["rows"])
    assert "duplicate_bounds" not in out and "duplicate_bounds" not in visuals[0]
    texts = " ".join(l["text"] for l in out["limitations"])
    assert "rango" not in texts and "cota" not in texts and "posibles duplicados" not in texts


def test_report_listing_becomes_map_timeline_and_shapes():
    """Runs on the real approved load; skipped where none is approved (CI, fresh clone)."""
    from app.agent import tools
    from app.gold import GoldUnavailable, get_analytics
    try:
        analytics = get_analytics()
    except GoldUnavailable as exc:
        pytest.skip(f"Sin carga Gold aprobada local: {exc}")
    visuals = []
    out = tools.execute(analytics, "query_gold", {
        "dataset": "fact_report", "filters": [{"column": "country_iso2", "op": "eq", "value": "CR"}],
        "eligibility": ["country"], "title": "Informes de Costa Rica", "limit": 500}, visuals)
    assert [v["view"] for v in visuals] == ["points", "timeseries", "bars"]
    assert "visualizations" in out
    assert all(r["shape_code"] is not None for r in visuals[2]["rows"])


def test_selected_area_limits_every_query(gold):
    world = [[-200, -80], [200, -80], [200, 80], [-200, 80]]
    phoenix = [[-113, 33], [-111, 33], [-111, 34], [-113, 34]]      # 4 informes en 33.4, -112.1
    nowhere = [[0, 0], [0.001, 0], [0.001, 0.001]]
    base = {"dataset": "fact_report", "metrics": ["report_count"], "eligibility": ["map"]}
    visuals = []
    out = tools.execute(gold, "query_gold", base, visuals, area=phoenix)
    assert out["rows"][0]["report_count"] == 4
    assert "Dentro del área seleccionada en el mapa" in visuals[0]["readable_query"]["filtros"]
    assert visuals[0]["query"]["area"] == phoenix
    assert tools.execute(gold, "query_gold", base, [], area=nowhere)["rows"][0]["report_count"] == 0
    with pytest.raises(QueryError) as certified:
        tools.execute(gold, "run_certified", {"id": "CQ_TEST_SOURCES"}, [], area=world)
    assert certified.value.code == "area_active"
    with pytest.raises(QueryError) as aggregate:
        tools.execute(gold, "query_gold", {"dataset": "agg_source", "group_by": ["source_code"], "metrics": ["report_count"]}, [], area=world)
    assert aggregate.value.code == "area_unavailable"


def test_eq_filter_over_a_certified_breakdown_is_covered_when_its_row_exists(coverage_gold):
    years = [r["event_year"] for r in coverage_gold.run_certified("CQ_TEST_YEAR")["rows"]]
    visuals = []
    needs = {"filters": [{"column": "event_year", "op": "eq", "value": years[0]}], "group_by": []}
    found = tools.execute(coverage_gold, "search_certified", {"question": "serie anual de informes", "needs": needs}, visuals)
    year = next(c for c in found["candidates"] if c["id"] == "CQ_TEST_YEAR")
    assert year["coverage"] == "total" and year["focus_rows"][0]["event_year"] == years[0]
    assert found["decision"]["executed"] and len(visuals) == 1
    absent = {"filters": [{"column": "event_year", "op": "eq", "value": 1901 if 1901 not in years else 1899}]}
    found = tools.execute(coverage_gold, "search_certified", {"question": "serie anual de informes", "needs": absent}, [])
    year = next(c for c in found["candidates"] if c["id"] == "CQ_TEST_YEAR")
    assert year["coverage"] == "parcial" and "no está en el resultado" in year["missing"][0]["reason"]


def test_a_total_is_covered_by_a_breakdown_with_its_total_row(gold):
    item = {"query": {"dataset": "agg_source", "group_by": ["source_code"], "metrics": ["report_count"], "rollup": True}}
    assert tools.coverage(gold, item, {"filters": [], "group_by": [], "metrics": []})["coverage"] == "total"
    item["query"]["rollup"] = False
    assert tools.coverage(gold, item, {"filters": [], "group_by": [], "metrics": []})["coverage"] == "parcial"


def test_empty_needs_never_run_a_certified_query(coverage_gold):
    """Empty needs “cover” any candidate: the server leaves the choice to the model."""
    visuals = []
    found = tools.execute(coverage_gold, "search_certified", {"question": "¿Cuántos informes hay por década?", "needs": {}}, visuals)
    assert found["decision"]["tool"] == "run_certified" and found["decision"]["explicit"] is False
    assert "executed" not in found["decision"] and visuals == []


def test_reading_shown_data_sorted_is_not_drawn_again(gold):
    visuals = []
    base = {"dataset": "agg_year", "group_by": ["event_year"], "metrics": ["report_count"], "view": "timeseries", "limit": 500}
    first = tools.execute(gold, "query_gold", base, visuals)
    top = tools.execute(gold, "query_gold", {**base, "view": "table", "order_by": "report_count", "limit": 1}, visuals)
    assert len(visuals) == 1 and len(top["rows"]) == 1 and "no se dibuja" in top["note"]
    best = max(r["report_count"] for r in visuals[0]["rows"])
    assert first["extremes"]["report_count"]["max"][0]["report_count"] == best
    tools.execute(gold, "query_gold", {**base, "view": "bars"}, visuals)  # another full view is a new chart
    assert len(visuals) == 2


def test_unknown_small_category_lists_its_allowed_values(gold):
    with pytest.raises(QueryError) as err:
        tools.execute(gold, "query_gold", {"dataset": "agg_source", "filters": [{"column": "source_code", "value": "NOPE"}],
                                           "group_by": ["source_code"], "metrics": ["report_count"]}, [])
    assert "Permitidos:" in str(err.value) and "UFOCAT" in str(err.value) and "find_entities" not in str(err.value)


def test_search_ties_go_to_the_closest_example(coverage_gold):
    found = coverage_gold.search_certified("¿Cuántos informes hay por década?")
    assert found[0]["id"] == "CQ_TEST_DECADE" and found[0]["example_similarity"] == 1.0


def test_analyze_tool_runs_dedupes_and_counts_as_a_visualization(gold):
    schema = next(t for t in tools.schemas(gold) if t["name"] == "analyze")["parameters"]
    assert set(schema["properties"]["analysis"]["enum"]) == set(tools.gold_analysis.ANALYSES)
    visuals = []
    request = {"analysis": "period_change", "params": {"period": "decade", "from": 1950, "to": 1990}, "title": "Cambio"}
    first = tools.execute(gold, "analyze", request, visuals)
    assert first["view"] == "waterfall" and first["analysis"]["kind"] == "period_change"
    assert first["metric_labels"]["change"] == "Cambio de informes"
    again = tools.execute(gold, "analyze", {**request, "title": "Otro título"}, visuals)
    assert "no se repite" in again["note"] and len(visuals) == 1
    for kind in ("funnel", "missing_combinations", "source_overlap"):
        tools.execute(gold, "analyze", {"analysis": kind}, visuals)
    with pytest.raises(QueryError) as exc:
        tools.execute(gold, "analyze", {"analysis": "diversity"}, visuals)
    assert exc.value.code == "visual_limit"


def test_measures_and_new_views_reach_the_model(gold):
    schema = tools.query_schema(gold)["properties"]
    assert "waterfall" not in schema["view"]["enum"] and "boxplot" in schema["view"]["enum"]
    assert "duration_witnesses" in schema["measure"]["enum"]
    visuals = []
    out = tools.execute(gold, "query_gold", {"dataset": "fact_report", "view": "histogram", "metrics": ["report_count"],
                                             "measure": "witnesses", "title": "Testigos"}, visuals)
    assert out["distribution"]["measure"] == "witnesses" and "series" in out["distribution"]
    points = tools.execute(gold, "query_gold", {"dataset": "fact_report", "view": "points", "eligibility": ["map"], "limit": 1}, visuals)
    assert points["points"]["reports"] == points["row_count"] and not points["truncated"]


def test_analysis_codes_never_reach_the_answer(gold):
    from app.agent.graph import codes_of
    codes = codes_of(gold)
    assert {"period_change", "kmeans_profiles", "duration_witnesses", "region_code", "behavior_tag"} <= codes
