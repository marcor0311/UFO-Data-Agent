"""HTTP routes with an isolated app, a scripted model and a local session."""
import uuid
from contextlib import closing

import pytest

from conftest import ScriptedStream, call, login, message
from app.agent import routes
from app.main import app


def use_stream(*outputs):
    stream = ScriptedStream(*outputs)
    app.dependency_overrides[routes.get_stream] = lambda: stream
    return stream


def test_health_and_catalog(client, gold):
    assert client.get("/api/health").json()["gold_load_id"] == gold.load_id
    catalog = client.get("/api/agent/catalog").json()
    assert catalog["certified_queries"][0] == {**catalog["certified_queries"][0], "id": "CQ_TEST_SOURCES", "valid": True}
    assert set(catalog["views"]) == {"table", "bars", "timeseries", "points", "density", "choropleth", "hour_weekday", "month_calendar",
                                     "stacked", "matrix", "dumbbell", "timeline", "histogram", "ecdf"}
    assert catalog["country_m49"]["US"] == "840" and catalog["dimensions"]["country_iso2"]["label"] == "País"
    for code, metric in gold.metrics.items():
        if metric["type"] == "ratio":
            assert catalog["metrics"][code]["denominator"] == metric["denominator"]
        else:
            assert "denominator" not in catalog["metrics"][code]


@pytest.mark.parametrize("limit, truncated", [(2, True), (10, False)])
def test_rollup_retains_the_filtered_population_for_ratios_and_distinct_counts(client, gold, limit, truncated):
    sources = ["UFOCAT", "UPDB", "UFO-search"]
    response = client.post("/api/agent/query", json={
        "dataset": "fact_report", "filters": [{"column": "source_code", "op": "in", "value": sources}],
        "group_by": ["source_code"], "metrics": ["report_count", "external_evidence_pct", "distinct_country_count"],
        "eligibility": ["country"], "rollup": True, "limit": limit,
    })
    assert response.status_code == 200
    result = response.json()
    with closing(gold.connect()) as conn:
        expected = conn.execute("""SELECT COUNT(*), ROUND(100.0 * SUM(uses_external_evidence) / COUNT(*), 4),
                                          COUNT(DISTINCT country_iso2)
                                   FROM fact_report
                                   WHERE usable_for_country = 1 AND source_code IN (?, ?, ?)""", sources).fetchone()
    assert result["truncated"] is truncated
    assert result["row_count"] == len(result["rows"]) == (2 if truncated else 3)
    assert result["matched_source_rows"] == expected[0] == 8
    assert result["total"] == {"report_count": expected[0], "external_evidence_pct": expected[1],
                               "distinct_country_count": expected[2]}
    assert expected[1] == 25 and expected[2] == 5
    percentages = [row["external_evidence_pct"] for row in result["rows"]]
    assert result["total"]["external_evidence_pct"] != sum(percentages) / len(percentages)
    assert result["total"]["distinct_country_count"] != sum(row["distinct_country_count"] for row in result["rows"])


def test_deterministic_query_and_certified(client):
    ok = client.post("/api/agent/query", json={"dataset": "agg_source", "group_by": ["source_code"], "metrics": ["report_count"]})
    assert ok.status_code == 200 and ok.json()["result_type"] == "composed"
    bad = client.post("/api/agent/query", json={"dataset": "fact_report", "metrics": ["report_count"], "sql": "x"})
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "contract"
    assert client.get("/api/agent/certified/CQ_TEST_SOURCES").json()["result_type"] == "certified"
    assert client.get("/api/agent/certified/NOPE").status_code == 404


def test_post_requires_allowed_origin(client):
    r = client.post("/api/agent/query", json={"dataset": "agg_source", "metrics": ["report_count"]}, headers={"origin": "https://evil.example"})
    assert r.status_code == 403


def test_chat_requires_session(client):
    assert client.post("/api/agent/chat", json={"question": "Hola"}).status_code == 401
    assert client.get("/api/auth/status").json()["authenticated"] is False


def test_oauth_callback_requires_cookie_from_loopback_host(client, monkeypatch):
    callback = "http://127.0.0.1:8010/auth/callback"
    monkeypatch.setenv("AGENT_CALLBACK", callback)
    start = client.get("http://127.0.0.1:8010/api/auth/start", follow_redirects=False)
    assert start.status_code == 307
    state = start.cookies["ufo_oauth"]

    missing_cookie = client.get("http://localhost:8010/auth/callback", params={"state": state})
    assert missing_cookie.status_code == 400
    assert missing_cookie.headers["content-type"] == "application/json; charset=utf-8"
    assert missing_cookie.json()["detail"].startswith("Estado OAuth inválido.")

    # A provider denial exercises the state check without a network request.
    denied = client.get(callback, params={"state": state, "error": "access_denied"})
    assert denied.status_code == 400
    assert denied.json()["detail"] == "Autorización rechazada: access_denied"


def test_chat_stores_owner_scoped_history(client):
    login(client)
    use_stream([call("run_certified", {"id": "CQ_TEST_SOURCES"})], [message("Hay entre 8 y 12 informes.")])
    r = client.post("/api/agent/chat", json={"question": "¿Cuántos informes por fuente?"})
    assert r.status_code == 200
    cid = r.json()["conversation_id"]
    turn = r.json()["turn"]
    assert turn["answer"].startswith("Hay entre") and turn["visualizations"][0]["result_type"] == "certified"
    history = client.get(f"/api/agent/conversations/{cid}").json()
    assert len(history["turns"]) == 1
    assert client.get("/api/agent/conversations").json()[0]["conversation_id"] == cid
    login(client, owner="intruso", email="otra@example.com")
    assert client.get(f"/api/agent/conversations/{cid}").status_code == 404
    use_stream([message("no")])
    assert client.post("/api/agent/chat", json={"question": "x", "conversation_id": cid}).status_code == 404


def test_follow_up_appends_turn(client):
    login(client)
    use_stream([message("Uno.")])
    cid = client.post("/api/agent/chat", json={"question": "Uno"}).json()["conversation_id"]
    use_stream([message("Dos.")])
    r = client.post("/api/agent/chat", json={"question": "Dos", "conversation_id": cid})
    assert len(client.get(f"/api/agent/conversations/{cid}").json()["turns"]) == 2 and r.json()["turn"]["answer"] == "Dos."


def test_model_must_belong_to_account(client):
    login(client)
    use_stream([message("x")])
    assert client.post("/api/agent/chat", json={"question": "x", "model": "otro"}).status_code == 422
    assert client.get("/api/agent/models").json()["selected"] == "model-a"


def test_one_query_at_a_time(client):
    login(client)
    routes._chat_lock.acquire()
    try:
        assert client.post("/api/agent/chat", json={"question": "x"}).status_code == 409
    finally:
        routes._chat_lock.release()


def test_unknown_fields_rejected(client):
    login(client)
    assert client.post("/api/agent/chat", json={"question": "x", "sql": "SELECT 1"}).status_code == 422
    assert client.get(f"/api/agent/conversations/{uuid.uuid4()}").status_code == 404
