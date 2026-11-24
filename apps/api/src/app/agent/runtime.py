"""Provider calls and conversation context for the LangGraph agent (``app.agent.graph``).

The provider calls are isolated in ``model_catalog`` and ``response_stream`` so
another provider can replace them without touching the tools or the contract.
"""
from __future__ import annotations

import json
from typing import Callable

import httpx
from fastapi import HTTPException

from app.agent.graph import RECURSION_LIMIT, build_graph
from app.gold import Analytics

API = "https://api.openai.com/v1"
HISTORY_TURNS = 12
HISTORY_CHARS = 45000


def model_catalog(account: dict) -> list[dict]:
    """Models listed for this account, in the official catalog order."""
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(API + "/models", headers={"Authorization": "Bearer " + account["access_token"]})
            response.raise_for_status()
        body = response.json()
        models = [m for m in body.get("models", body.get("data", [])) if m.get("visibility", "list") == "list"]
        if not models:
            raise ValueError("Catálogo vacío")
        return [{"slug": m.get("slug") or m["id"], "display_name": m.get("display_name") or m.get("slug") or m["id"]} for m in models]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(502, "No se pudo descubrir el catálogo de modelos de esta cuenta.") from exc


def response_stream(account: dict, payload: dict) -> dict:
    """POST /responses with stream; accept the result only after response.completed."""
    completed = None
    try:
        with httpx.Client(timeout=httpx.Timeout(120, connect=20)) as client:
            with client.stream("POST", API + "/responses", headers={"Authorization": "Bearer " + account["access_token"]},
                               json={**payload, "store": False, "stream": True}) as response:
                if response.status_code >= 400:
                    response.read()
                    raise HTTPException(502, f"La inferencia devolvió HTTP {response.status_code}. Revisa permisos y límites de tu plan.")
                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:]
                    if raw == "[DONE]":
                        continue
                    event = json.loads(raw)
                    kind = event.get("type")
                    if kind in ("response.failed", "response.incomplete", "error"):
                        raise HTTPException(502, "La inferencia no se completó. Revisa los límites de tu plan o vuelve a intentarlo.")
                    if kind == "response.completed":
                        completed = event["response"]
        if completed is None:
            raise HTTPException(502, "El stream terminó sin response.completed.")
        return completed
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Conexión con la inferencia interrumpida; puedes reintentar.") from exc


AREA_NOTE = ("Contexto de la interfaz: la persona tiene un área seleccionada en el mapa. Mientras esté activa, el servidor "
             "limita automáticamente cada query_gold a los informes dentro de esa área; no hace falta filtrar por país ni por "
             "coordenadas. Usa fact_report (el área exige coordenadas aptas: eligibility map) y aplica solo los filtros "
             "que pida la pregunta, como el año o la forma. No uses run_certified ni la vista globe. Menciona que el "
             "resultado se limita al área seleccionada.")


def history_inputs(history: list[dict]) -> list[dict]:
    """Recent turns plus their verified evidence, for follow-up questions."""
    inputs = []
    for turn in history[-HISTORY_TURNS:]:
        inputs += [{"role": "user", "content": turn["question"]}, {"role": "assistant", "content": turn["answer"]}]
        evidence = [{"query": v["query"], "readable_query": v["readable_query"]["texto"], "rows": v["rows"][:30],
                     "result_type": v["result_type"]}
                    for v in turn.get("visualizations", [])]
        if evidence:
            inputs.append({"role": "user", "content": "Evidencia verificada del turno anterior (no se vuelve a mostrar): "
                           + json.dumps(evidence, ensure_ascii=False)[:HISTORY_CHARS // HISTORY_TURNS]})
    return inputs


class DataAgent:
    """Runs one turn through the LangGraph in ``app.agent.graph``."""

    def __init__(self, analytics: Analytics, stream: Callable[[dict, dict], dict] = response_stream):
        self.analytics = analytics
        self.stream = stream
        self.graph = build_graph(analytics, stream, history_inputs, AREA_NOTE)

    def answer(self, account: dict, question: str, history: list[dict], model: str, area: list | None = None) -> dict:
        work = self.graph.invoke({"account": account, "model": model, "question": question, "history": history, "area": area},
                                 {"recursion_limit": RECURSION_LIMIT})
        return work["turn"]
