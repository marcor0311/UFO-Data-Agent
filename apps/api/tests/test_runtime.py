"""Tool loop with a scripted model stream, and the stream verifier itself."""
import json

from fastapi import HTTPException
import httpx
import pytest

from conftest import ScriptedStream, call, message
from app.agent import runtime
from app.agent.runtime import DataAgent

ACCOUNT = {"access_token": "token"}


def test_direct_answer(gold):
    stream = ScriptedStream([message("Pide un dato concreto.")])
    turn = DataAgent(gold, stream=stream).answer(ACCOUNT, "Hola", [], "model-a")
    assert turn["answer"] == "Pide un dato concreto." and turn["visualizations"] == [] and turn["load_id"] == gold.load_id
    payload = stream.payloads[0]
    assert payload["model"] == "model-a" and payload["parallel_tool_calls"] is False
    assert "search_certified" in payload["instructions"] and "CQ_TEST_SOURCES" in payload["instructions"]


def test_certified_first_then_answer(gold):
    stream = ScriptedStream(
        [call("search_certified", {"question": "informes por fuente"}, "a")],
        [call("run_certified", {"id": "CQ_TEST_SOURCES"}, "b")],
        [message("Hay entre 8 y 12 informes.")])
    turn = DataAgent(gold, stream=stream).answer(ACCOUNT, "¿Cuántos informes por fuente?", [], "model-a")
    assert [t["tool"] for t in turn["trace"]] == ["search_certified", "run_certified"]
    assert turn["visualizations"][0]["result_type"] == "certified"
    outputs = [i for i in stream.payloads[2]["input"] if i.get("type") == "function_call_output"]
    assert json.loads(outputs[-1]["output"])["certified_query_id"] == "CQ_TEST_SOURCES"


def test_tool_error_is_returned_for_repair(gold):
    stream = ScriptedStream(
        [call("query_gold", {"dataset": "fact_report", "group_by": ["weekday"], "metrics": ["report_count"]}, "a")],
        [call("query_gold", {"dataset": "fact_report", "group_by": ["weekday"], "metrics": ["report_count"], "eligibility": ["day"]}, "b")],
        [message("Listo.")])
    turn = DataAgent(gold, stream=stream).answer(ACCOUNT, "Por día de la semana", [], "model-a")
    assert turn["trace"][0] == {"tool": "query_gold", "ok": False, "code": "eligibility_missing", "error": turn["trace"][0]["error"]}
    assert turn["trace"][1]["ok"] and len(turn["visualizations"]) == 1
    repaired = [i for i in stream.payloads[1]["input"] if i.get("type") == "function_call_output"][0]
    assert json.loads(repaired["output"])["code"] == "eligibility_missing"


def test_round_limit(gold):
    stream = ScriptedStream(*[[call("describe_data", {"dataset": None}, f"c{i}")] for i in range(runtime.MAX_ROUNDS)])
    with pytest.raises(HTTPException) as err:
        DataAgent(gold, stream=stream).answer(ACCOUNT, "?", [], "model-a")
    assert err.value.status_code == 422
    assert err.value.detail["code"] == "step_limit"
    assert "Acota la pregunta" in err.value.detail["message"]


def test_empty_model_text_fails(gold):
    with pytest.raises(HTTPException) as err:
        DataAgent(gold, stream=ScriptedStream([message("   ")])).answer(ACCOUNT, "?", [], "model-a")
    assert err.value.status_code == 502
    assert err.value.detail["code"] == "inference_interrupted"


def test_history_carries_previous_evidence(gold):
    first = DataAgent(gold, stream=ScriptedStream([call("run_certified", {"id": "CQ_TEST_SOURCES"})], [message("Uno.")])).answer(
        ACCOUNT, "Primera", [], "model-a")
    stream = ScriptedStream([message("Dos.")])
    DataAgent(gold, stream=stream).answer(ACCOUNT, "¿Y sin UPDB?", [first], "model-a")
    texts = [i["content"] for i in stream.payloads[0]["input"] if isinstance(i.get("content"), str)]
    assert texts[0] == "Primera" and texts[1] == "Uno." and "Evidencia verificada" in texts[2] and texts[-1] == "¿Y sin UPDB?"


def sse(*events):
    return "".join("data: " + json.dumps(e) + "\n\n" for e in events) + "data: [DONE]\n\n"


@pytest.fixture
def transport(monkeypatch):
    holder = {}
    real = httpx.Client

    def factory(*args, **kwargs):
        kwargs.pop("timeout", None)
        return real(transport=httpx.MockTransport(holder["handler"]))
    monkeypatch.setattr(runtime.httpx, "Client", factory)
    return holder


def test_stream_accepts_only_completed(transport):
    transport["handler"] = lambda r: httpx.Response(200, text=sse({"type": "response.output_text.delta"},
                                                                     {"type": "response.completed", "response": {"output": []}}))
    assert runtime.response_stream(ACCOUNT, {"model": "m"}) == {"output": []}


@pytest.mark.parametrize("body,status", [(sse({"type": "response.failed"}), 200), (sse({"type": "response.output_text.delta"}), 200),
                                         ("", 429)])
def test_stream_failures(transport, body, status):
    transport["handler"] = lambda r: httpx.Response(status, text=body)
    with pytest.raises(HTTPException) as err:
        runtime.response_stream(ACCOUNT, {"model": "m"})
    assert err.value.status_code == 502
    assert err.value.detail["code"] == "inference_interrupted"


def test_unavailable_provider_model_is_actionable(transport):
    transport["handler"] = lambda r: httpx.Response(
        404, json={"error": {"code": "model_not_found"}})
    with pytest.raises(HTTPException) as err:
        runtime.response_stream(ACCOUNT, {"model": "retired-model"})
    assert err.value.status_code == 422
    assert err.value.detail["code"] == "model_unavailable"


def test_stream_sends_store_false(transport):
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, text=sse({"type": "response.completed", "response": {"output": []}}))
    transport["handler"] = handler
    runtime.response_stream(ACCOUNT, {"model": "m"})
    assert seen["store"] is False and seen["stream"] is True


def test_model_catalog(transport):
    transport["handler"] = lambda r: httpx.Response(200, json={"models": [{"slug": "a", "display_name": "A", "visibility": "list"},
                                                                          {"slug": "h", "display_name": "H", "visibility": "hide"}]})
    assert runtime.model_catalog(ACCOUNT) == [{"slug": "a", "display_name": "A"}]
    transport["handler"] = lambda r: httpx.Response(200, json={"models": []})
    with pytest.raises(HTTPException):
        runtime.model_catalog(ACCOUNT)
