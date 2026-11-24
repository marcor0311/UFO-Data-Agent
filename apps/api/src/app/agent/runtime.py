"""Responses tool loop: terminal-stream verification and Gold-only evidence.

The provider calls are isolated in ``model_catalog`` and ``response_stream`` so
another provider can replace them without touching the tools or the contract.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Callable

import httpx
from fastapi import HTTPException

from app.agent import instructions, tools
from app.gold import Analytics, QueryError

API = "https://api.openai.com/v1"
MAX_ROUNDS = 10
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
    def __init__(self, analytics: Analytics, stream: Callable[[dict, dict], dict] = response_stream):
        self.analytics = analytics
        self.stream = stream

    def answer(self, account: dict, question: str, history: list[dict], model: str) -> dict:
        prompt = instructions.build(self.analytics)
        inputs = [*history_inputs(history), {"role": "user", "content": question}]
        visuals: list[dict] = []
        trace: list[dict] = []
        definitions = tools.schemas(self.analytics)
        for _ in range(MAX_ROUNDS):
            response = self.stream(account, {"model": model, "instructions": prompt, "input": inputs,
                                             "tools": definitions, "parallel_tool_calls": False})
            outputs = response.get("output", [])
            inputs.extend(outputs)
            calls = [o for o in outputs if o.get("type") == "function_call"]
            if not calls:
                text = "\n".join(c["text"] for o in outputs if o.get("type") == "message"
                                 for c in o.get("content", []) if c.get("type") == "output_text").strip()
                if not text:
                    raise HTTPException(502, "El modelo no devolvió una respuesta legible.")
                return {"question": question, "answer": text, "visualizations": visuals, "trace": trace, "model": model,
                        "load_id": self.analytics.load_id,
                        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat()}
            for call in calls:
                try:
                    arguments = json.loads(call.get("arguments") or "{}")
                    result = tools.execute(self.analytics, call["name"], arguments, visuals)
                    trace.append({"tool": call["name"], "arguments": arguments, "ok": True})
                except QueryError as exc:
                    result = {"error": str(exc)[:1500], "code": exc.code, "repair": "Corrige los argumentos y vuelve a llamar."}
                    trace.append({"tool": call["name"], "ok": False, "code": exc.code, "error": str(exc)[:1500]})
                except (ValueError, KeyError, TypeError) as exc:
                    result = {"error": str(exc)[:1500], "code": "invalid_arguments"}
                    trace.append({"tool": call["name"], "ok": False, "code": "invalid_arguments", "error": str(exc)[:1500]})
                inputs.append({"type": "function_call_output", "call_id": call["call_id"],
                               "output": json.dumps(result, ensure_ascii=False)})
        raise HTTPException(422, "La consulta superó el límite de pasos; concreta la pregunta.")
