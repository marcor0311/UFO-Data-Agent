"""The Data Agent as a LangGraph state machine.

    contexto → modelo ⇄ herramientas
                 ↓
             verificar → componer
                 ↺ modelo (one rewrite when the answer breaks a product rule)

- contexto: instructions, recent turns with their verified evidence, the active map area.
- modelo: one Responses call (``stream``); routes to herramientas when it asks for tools.
- herramientas: runs the typed tools over Gold; every data result becomes a visualization.
- verificar: deterministic checks on the final text (readable answer, a single figure with
  no ranges); one chance to rewrite, then the answer is accepted as is.
- componer: the turn stored and returned by the API, with ``visualization_action``.

The model never writes SQL and never sees more than the compact payloads of the tools.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Callable, TypedDict

from fastapi import HTTPException
from langgraph.graph import END, START, StateGraph

from app.agent import instructions, tools
from app.gold import Analytics, QueryError

MAX_ROUNDS = 10
MAX_REWRITES = 1
# “entre 8 y 12 informes”, “de 8 a 12 informes”, “8–12 informes”: PRODUCT.md asks for one figure.
RANGE = re.compile(r"\b(entre\s+[\d.,]+\s+y\s+[\d.,]+|de\s+[\d.,]+\s+a\s+[\d.,]+|[\d.,]+\s*[–-]\s*[\d.,]+)\s+(informes|reportes|eventos)\b", re.I)
RANGE_FIX = ("Revisión automática: la respuesta da un rango de informes. Reescríbela con una sola cifra, la del resultado "
             "verificado, y su unidad. No llames herramientas: usa los resultados que ya tienes.")


class Work(TypedDict, total=False):
    account: dict
    model: str
    question: str
    history: list[dict]
    area: list | None
    prompt: str
    definitions: list[dict]
    inputs: list[dict]
    calls: list[dict]
    text: str
    visuals: list[dict]
    trace: list[dict]
    rounds: int
    rewrites: int
    turn: dict


def build_graph(analytics: Analytics, stream: Callable[[dict, dict], dict], history_inputs: Callable[[list[dict]], list[dict]],
                area_note: str):
    def contexto(work: Work) -> Work:
        inputs = [*history_inputs(work["history"]), {"role": "user", "content": work["question"]}]
        if work.get("area"):
            inputs.append({"role": "user", "content": area_note})
        return {"prompt": instructions.build(analytics), "definitions": tools.schemas(analytics), "inputs": inputs,
                "visuals": [], "trace": [], "rounds": 0, "rewrites": 0, "text": ""}

    def modelo(work: Work) -> Work:
        if work["rounds"] >= MAX_ROUNDS:
            raise HTTPException(422, "La consulta superó el límite de pasos; concreta la pregunta.")
        response = stream(work["account"], {"model": work["model"], "instructions": work["prompt"], "input": work["inputs"],
                                            "tools": work["definitions"], "parallel_tool_calls": False})
        outputs = response.get("output", [])
        calls = [o for o in outputs if o.get("type") == "function_call"]
        text = "\n".join(c["text"] for o in outputs if o.get("type") == "message"
                         for c in o.get("content", []) if c.get("type") == "output_text").strip()
        return {"inputs": [*work["inputs"], *outputs], "calls": calls, "text": text, "rounds": work["rounds"] + 1}

    def herramientas(work: Work) -> Work:
        inputs, visuals, trace = list(work["inputs"]), list(work["visuals"]), list(work["trace"])
        for call in work["calls"]:
            try:
                arguments = json.loads(call.get("arguments") or "{}")
                result = tools.execute(analytics, call["name"], arguments, visuals, work.get("area"))
                trace.append({"tool": call["name"], "arguments": arguments, "ok": True})
            except QueryError as exc:
                result = {"error": str(exc)[:1500], "code": exc.code, "repair": "Corrige los argumentos y vuelve a llamar."}
                trace.append({"tool": call["name"], "ok": False, "code": exc.code, "error": str(exc)[:1500]})
            except (ValueError, KeyError, TypeError) as exc:
                result = {"error": str(exc)[:1500], "code": "invalid_arguments"}
                trace.append({"tool": call["name"], "ok": False, "code": "invalid_arguments", "error": str(exc)[:1500]})
            inputs.append({"type": "function_call_output", "call_id": call["call_id"], "output": json.dumps(result, ensure_ascii=False)})
        return {"inputs": inputs, "visuals": visuals, "trace": trace, "calls": []}

    def verificar(work: Work) -> Work:
        if not work["text"]:
            raise HTTPException(502, "El modelo no devolvió una respuesta legible.")
        if RANGE.search(work["text"]) and work["rewrites"] < MAX_REWRITES:
            trace = [*work["trace"], {"tool": "verificar", "ok": False, "code": "range_in_answer"}]
            return {"inputs": [*work["inputs"], {"role": "user", "content": RANGE_FIX}], "rewrites": work["rewrites"] + 1,
                    "trace": trace, "text": ""}
        return {}

    def componer(work: Work) -> Work:
        visuals = work["visuals"]
        turn = {"question": work["question"], "answer": work["text"], "visualizations": visuals, "trace": work["trace"],
                "model": work["model"],
                # As in the Messi contract: a turn without new results keeps the previous ones on screen.
                "visualization_action": "create" if visuals else "retain",
                **({"area": work["area"]} if work.get("area") else {}),
                "load_id": analytics.load_id,
                "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat()}
        return {"turn": turn}

    def after_model(work: Work) -> str:
        return "herramientas" if work["calls"] else "verificar"

    def after_check(work: Work) -> str:
        return "modelo" if not work["text"] else "componer"

    graph = StateGraph(Work)
    for name, node in (("contexto", contexto), ("modelo", modelo), ("herramientas", herramientas),
                       ("verificar", verificar), ("componer", componer)):
        graph.add_node(name, node)
    graph.add_edge(START, "contexto")
    graph.add_edge("contexto", "modelo")
    graph.add_conditional_edges("modelo", after_model, ["herramientas", "verificar"])
    graph.add_edge("herramientas", "modelo")
    graph.add_conditional_edges("verificar", after_check, ["modelo", "componer"])
    graph.add_edge("componer", END)
    return graph.compile()


# Enough for MAX_ROUNDS model calls, their tool steps and one rewrite.
RECURSION_LIMIT = 4 * MAX_ROUNDS + 10
