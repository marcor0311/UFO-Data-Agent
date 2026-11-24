"""Provider calls and conversation context for the LangGraph agent (``app.agent.graph``).

The provider calls are isolated in ``model_catalog`` and ``response_stream`` so
another provider can replace them without touching the tools or the contract.
"""
from __future__ import annotations

import json
from typing import Callable

import httpx
from fastapi import HTTPException

from app.agent import graph
from app.agent.graph import AREA_NOTE, history_inputs  # noqa: F401 - re-exported
from app.gold import Analytics

API = "https://api.openai.com/v1"
MODEL_UNAVAILABLE = "El modelo seleccionado ya no está disponible. Elige otro modelo y vuelve a enviar tu pregunta."


def inference_error(status: int, code: str, message: str) -> HTTPException:
    """An error the web can act on: ``code`` says which recovery to offer."""
    return HTTPException(status, {"code": code, "message": message})


def provider_model_unavailable(body: dict) -> bool:
    error = body.get("error", body)
    if not isinstance(error, dict):
        return False
    code = str(error.get("code") or error.get("type") or "").casefold()
    return code in {"model_not_found", "model_not_available", "unsupported_model"}


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
    """POST /responses with stream; accept the result only after response.completed.

    A dropped connection or a 5xx before any output is retried once: those are transient
    and the request has no side effects (``store: false``)."""
    for attempt in range(2):
        try:
            return _stream_once(account, payload)
        except _Transient as exc:
            if attempt:
                raise inference_error(502, "inference_interrupted", exc.message) from exc
    raise AssertionError("unreachable")


class _Transient(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _stream_once(account: dict, payload: dict) -> dict:
    completed = None
    try:
        with httpx.Client(timeout=httpx.Timeout(120, connect=20)) as client:
            with client.stream("POST", API + "/responses", headers={"Authorization": "Bearer " + account["access_token"]},
                               json={**payload, "store": False, "stream": True}) as response:
                if response.status_code >= 500:
                    response.read()
                    raise _Transient("La inferencia no pudo completarse. Puedes reintentar la pregunta.")
                if response.status_code >= 400:
                    response.read()
                    try:
                        body = response.json()
                    except ValueError:
                        body = {}
                    if provider_model_unavailable(body):
                        raise inference_error(422, "model_unavailable", MODEL_UNAVAILABLE)
                    if response.status_code in (408, 429):
                        raise inference_error(502, "inference_interrupted", "La inferencia no pudo completarse. Puedes reintentar la pregunta.")
                    raise inference_error(502, "inference_failed", f"La inferencia devolvió HTTP {response.status_code}. Revisa permisos y límites de tu plan.")
                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:]
                    if raw == "[DONE]":
                        continue
                    event = json.loads(raw)
                    kind = event.get("type")
                    if kind in ("response.failed", "response.incomplete", "error"):
                        details = event.get("response") or event
                        error = details.get("error", {}) if isinstance(details, dict) else {}
                        if isinstance(error, dict) and provider_model_unavailable({"error": error}):
                            raise inference_error(422, "model_unavailable", MODEL_UNAVAILABLE)
                        raise inference_error(502, "inference_interrupted", "La inferencia se interrumpió antes de completar la respuesta. Puedes reintentar la pregunta.")
                    if kind == "response.completed":
                        completed = event["response"]
        if completed is None:
            raise inference_error(502, "inference_interrupted", "La conexión terminó antes de completar la respuesta. Puedes reintentar la pregunta.")
        return completed
    except httpx.HTTPError as exc:
        raise _Transient("Se interrumpió la conexión con la inferencia. Puedes reintentar la pregunta.") from exc


class DataAgent:
    """Runs one turn through the LangGraph in ``app.agent.graph``.

    Cheap to create: the compiled graph, the instructions and the tool schemas are
    built once per Gold load and shared by every request."""

    def __init__(self, analytics: Analytics, stream: Callable[[dict, dict], dict] = response_stream):
        self.analytics = analytics
        self.stream = stream

    @property
    def graph(self):
        return graph.compiled(self.analytics)

    def answer(self, account: dict, question: str, history: list[dict], model: str, area: list | None = None) -> dict:
        return graph.run(self.analytics, self.stream, account, model, question, history, area)
