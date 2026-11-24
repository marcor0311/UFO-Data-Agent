"""Tool loop with a scripted model stream, and the stream verifier itself."""
import json

from fastapi import HTTPException
import httpx
import pytest

from conftest import ScriptedStream, call, message
from app.agent import graph, runtime
from app.agent.runtime import DataAgent

ACCOUNT = {"access_token": "token"}


def test_direct_answer(gold):
    """A greeting answered without tools gets one nudge; the model may repeat its answer."""
    stream = ScriptedStream([message("Pide un dato concreto.")], [message("Pide un dato concreto.")])
    turn = DataAgent(gold, stream=stream).answer(ACCOUNT, "Hola", [], "model-a")
    assert turn["answer"] == "Pide un dato concreto." and turn["visualizations"] == [] and turn["load_id"] == gold.load_id
    assert turn["trace"] == [{"tool": "verificar", "ok": False, "code": "no_data_used"}]
    assert stream.payloads[1]["input"][-1]["content"] == graph.UNGROUNDED and "tool_choice" not in stream.payloads[1]
    payload = stream.payloads[0]
    assert payload["model"] == "model-a" and payload["parallel_tool_calls"] is True and "tool_choice" not in payload
    assert "search_certified" in payload["instructions"] and "CQ_TEST_SOURCES" in payload["instructions"]


def test_certified_first_then_answer(gold):
    stream = ScriptedStream(
        [call("search_certified", {"question": "informes por fuente"}, "a")],
        [call("run_certified", {"id": "CQ_TEST_SOURCES"}, "b")],
        [message("Hay 9 informes.")])
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


def test_spent_budget_forces_an_answer(gold):
    """Without charts the budget is BASE_ROUNDS model calls; the last one may not call tools."""
    stalls = [[call("describe_data", {"dataset": None}, f"c{i}")] for i in range(graph.BASE_ROUNDS - 1)]
    stream = ScriptedStream(*stalls, [call("describe_data", {"dataset": None}, "late"), message("No pude concretar la consulta.")])
    turn = DataAgent(gold, stream=stream).answer(ACCOUNT, "?", [], "model-a")
    assert turn["answer"] == "No pude concretar la consulta."
    last = stream.payloads[-1]
    assert len(stream.payloads) == graph.BASE_ROUNDS and last["tool_choice"] == "none"
    assert last["input"][-1]["content"] == graph.CLOSE
    # The ignored call never reaches the next request without its output.
    assert all(t["tool"] == "describe_data" for t in turn["trace"]) and len(turn["trace"]) == graph.BASE_ROUNDS - 1


def test_charts_extend_the_budget():
    assert graph.budget(0) == graph.BASE_ROUNDS
    assert graph.budget(2) == graph.BASE_ROUNDS + 2 * graph.ROUNDS_PER_CHART
    assert graph.budget(100) == graph.MAX_ROUNDS


def test_parallel_calls_run_in_one_step_and_credentials_stay_out_of_state(gold):
    stream = ScriptedStream(
        [call("query_gold", {"dataset": "agg_source", "group_by": ["source_code"], "metrics": ["report_count"], "view": "bars"}, "a"),
         call("query_gold", {"dataset": "agg_year", "group_by": ["event_year"], "metrics": ["report_count"], "view": "timeseries"}, "b")],
        [message("Hay 9 informes.")])
    agent = DataAgent(gold, stream=stream)
    turn = agent.answer({"access_token": "secreto"}, "Fuentes y años", [], "model-a")
    assert len(stream.payloads) == 2 and len(turn["visualizations"]) == 2
    outputs = [i["call_id"] for i in stream.payloads[1]["input"] if i.get("type") == "function_call_output"]
    assert outputs == ["a", "b"]
    assert "secreto" not in json.dumps(turn) and "account" not in graph.Work.__annotations__


def test_graph_and_instructions_are_built_once_per_load(gold):
    assert DataAgent(gold).graph is DataAgent(gold).graph
    from app.agent import instructions, tools
    assert instructions.build(gold) is instructions.build(gold) and tools.schemas(gold) is tools.schemas(gold)


def test_instructions_list_entity_ids(gold):
    from app.agent import instructions
    text = instructions.build(gold)
    assert "ENTIDADES" in text and "PAÍSES (id = nombre)" in text and "US = " in text


def test_unexpected_tool_failure_goes_back_to_the_model(gold, monkeypatch):
    from app.agent import tools

    def boom(*args, **kwargs):
        raise RuntimeError("disk")
    monkeypatch.setattr(tools, "execute", boom)
    stream = ScriptedStream([call("describe_data", {"dataset": None}, "a")], [message("No pude leer el catálogo.")])
    turn = DataAgent(gold, stream=stream).answer(ACCOUNT, "?", [], "model-a")
    assert turn["trace"][0]["code"] == "tool_failed"
    out = [i for i in stream.payloads[1]["input"] if i.get("type") == "function_call_output"][0]
    assert json.loads(out["output"])["code"] == "tool_failed"


@pytest.mark.parametrize("text,code", [
    ("No está comprobado que haya relación: hay 9 informes.", "forbidden_phrase"),
    ("**Hallazgo**: hay 9 informes.", "markdown"),
    ("La métrica report_count da 9 informes.", "code_in_answer"),
])
def test_rule_breaking_answers_are_rewritten_once(gold, text, code):
    stream = ScriptedStream([call("run_certified", {"id": "CQ_TEST_SOURCES"}, "a")], [message(text)], [message("Hay 9 informes.")])
    turn = DataAgent(gold, stream=stream).answer(ACCOUNT, "?", [], "model-a")
    assert turn["answer"] == "Hay 9 informes." and {"tool": "verificar", "ok": False, "code": code} in turn["trace"]
    assert stream.payloads[2]["tool_choice"] == "none"


def test_clean_answers_pass_the_checks(gold):
    codes = graph.codes_of(gold)
    assert graph.problems("Hay 9 informes; según un modelo heredado del origen, la mitad tiene baja calidad.", codes) == []
    assert graph.problems("En 1997 hubo 1.234 informes en Estados Unidos.", codes) == []


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


def test_range_answer_is_rewritten_once(gold):
    stream = ScriptedStream(
        [call("run_certified", {"id": "CQ_TEST_SOURCES"}, "a")],
        [message("Hay entre 8 y 12 informes.")],
        [message("Hay 9 informes.")])
    turn = DataAgent(gold, stream=stream).answer(ACCOUNT, "¿Cuántos?", [], "model-a")
    assert turn["answer"] == "Hay 9 informes."
    assert turn["trace"][-1] == {"tool": "verificar", "ok": False, "code": "range_in_answer"}
    assert "una sola cifra" in stream.payloads[2]["input"][-1]["content"]


def test_ungrounded_answer_is_sent_back_to_gold(gold):
    stream = ScriptedStream([message("Las coordenadas vienen de las fuentes.")],
                            [call("run_certified", {"id": "CQ_TEST_SOURCES"}, "a")], [message("Hay 9 informes.")])
    turn = DataAgent(gold, stream=stream).answer(ACCOUNT, "¿De dónde vienen las coordenadas?", [], "model-a")
    assert turn["answer"] == "Hay 9 informes." and len(turn["visualizations"]) == 1
    assert [t["tool"] for t in turn["trace"]] == ["verificar", "run_certified"]


def test_clarifications_and_follow_ups_are_not_nudged(gold):
    asked = ScriptedStream([message("¿Te refieres a la República del Congo o a la República Democrática del Congo?")])
    assert DataAgent(gold, stream=asked).answer(ACCOUNT, "Congo", [], "model-a")["trace"] == []
    first = DataAgent(gold, stream=ScriptedStream([call("run_certified", {"id": "CQ_TEST_SOURCES"})], [message("Uno.")])).answer(
        ACCOUNT, "Primera", [], "model-a")
    follow = ScriptedStream([message("UFOCAT es la mayor.")])
    assert DataAgent(gold, stream=follow).answer(ACCOUNT, "¿Y la mayor?", [first], "model-a")["answer"] == "UFOCAT es la mayor."


def test_second_range_is_accepted_to_avoid_loops(gold):
    stream = ScriptedStream([call("run_certified", {"id": "CQ_TEST_SOURCES"}, "a")],
                            [message("Entre 8 y 12 informes.")], [message("De 8 a 12 informes.")])
    assert DataAgent(gold, stream=stream).answer(ACCOUNT, "?", [], "model-a")["answer"] == "De 8 a 12 informes."


def test_visualization_action(gold):
    created = DataAgent(gold, stream=ScriptedStream([call("run_certified", {"id": "CQ_TEST_SOURCES"}, "a")], [message("Hay 9 informes.")]))
    assert created.answer(ACCOUNT, "?", [], "model-a")["visualization_action"] == "create"
    kept = DataAgent(gold, stream=ScriptedStream([message("¿A qué país te refieres?")]))
    assert kept.answer(ACCOUNT, "?", [], "model-a")["visualization_action"] == "retain"


def test_documented_graph_matches_the_compiled_one():
    from pathlib import Path
    import re
    compiled = graph.build_graph(None).get_graph()
    edges = {(e.source, e.target) for e in compiled.edges}
    doc = (Path(__file__).resolve().parents[3] / "docs/agente-langgraph.md").read_text()
    block = doc.split("```mermaid")[1].split("```")[0]
    documented = {(a.split("(")[0], b.split("(")[0]) for a, b in re.findall(r"(\w+)(?:\([^)]*\))?\s*-\.?->\s*(\w+)", block)}
    assert documented == edges


def test_stream_retries_a_transient_failure_once(transport):
    seen = []

    def handler(request):
        seen.append(1)
        if len(seen) == 1:
            return httpx.Response(503, text="")
        return httpx.Response(200, text=sse({"type": "response.completed", "response": {"output": []}}))
    transport["handler"] = handler
    assert runtime.response_stream(ACCOUNT, {"model": "m"}) == {"output": []} and len(seen) == 2
    transport["handler"] = lambda r: httpx.Response(503, text="")
    with pytest.raises(HTTPException) as err:
        runtime.response_stream(ACCOUNT, {"model": "m"})
    assert err.value.status_code == 502


def test_instructions_carry_the_domain_guide_and_allowed_values(gold):
    from app.agent import instructions
    text = instructions.build(gold)
    assert "GUÍA DE DOMINIO" in text and "Cómo responder las preguntas típicas" in text
    assert "VALORES PERMITIDOS" in text and "color_family" in text
