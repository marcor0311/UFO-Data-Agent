"""The Data Agent as a LangGraph state machine.

    contexto → modelo ⇄ herramientas
                 ↓
             verificar → componer
                 ↺ modelo (one rewrite when the answer breaks a product rule)

- contexto: recent turns with their verified evidence and the active map area. The
  instructions (rules, Gold catalog and every entity id) and the tool schemas are built
  once per Gold load, so a turn only adds its own messages.
- modelo: one Responses call. The model may ask for several tools in one step
  (``parallel_tool_calls``). When the step budget is spent, or during a rewrite, it is
  called with ``tool_choice: none`` so the turn always ends with an answer.
- herramientas: runs every tool call of the step over Gold; data results become
  visualizations. Tool errors go back to the model with their code for repair.
- verificar: deterministic checks on the final text (PRODUCT.md and the agent rules):
  readable, one figure without ranges, no forbidden phrases, no Markdown and no column
  names or codes. One chance to rewrite, then the answer is accepted. An answer given
  without any tool, previous evidence or question back gets one nudge to consult Gold
  (tools allowed): a model answering from memory is never evidence.
- componer: the turn stored and returned by the API, with ``visualization_action``.

State lists use reducers (``operator.add``): each node returns only what it adds.
The account and the inference transport travel in the run config, never in the state,
so a checkpointer could never persist credentials. One compiled graph serves every turn
of a Gold load.

The model never writes SQL and never sees more than the compact payloads of the tools.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import json
import operator
import re
from typing import Annotated, Callable, TypedDict

from fastapi import HTTPException
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agent import instructions, tools
from app.gold import Analytics, QueryError

# Model calls per turn: the base covers entity lookups, the certified search, one chart and
# the answer; each chart produced earns more room, so dashboards fit and stalled loops stop.
BASE_ROUNDS = 10
ROUNDS_PER_CHART = 2
MAX_ROUNDS = 18
MAX_REWRITES = 1

# “entre 8 y 12 informes”, “de 8 a 12 informes”, “8–12 informes”: PRODUCT.md asks for one figure.
RANGE = re.compile(r"\b(entre\s+[\d.,]+\s+y\s+[\d.,]+|de\s+[\d.,]+\s+a\s+[\d.,]+|[\d.,]+\s*[–-]\s*[\d.,]+)\s+(informes|reportes|eventos)\b", re.I)
# The agent rules and docs/GOLD_EVALS.json forbid these phrases, even negated (“no está comprobado”).
FORBIDDEN = [
    ("hubo N avistamientos", re.compile(r"\bhubo\s+[\d.,\s]+avistamientos\b", re.I)),
    ("está comprobado", re.compile(r"\best[aá]\s+comprobado\b", re.I)),
    ("se demuestra / demuestra", re.compile(r"\bdemuestra(n)?\b", re.I)),
    ("prueba que", re.compile(r"\bprueba(n)?\s+que\b", re.I)),
    ("eventos únicos", re.compile(r"\beventos\s+[uú]nicos\b", re.I)),
    ("sin duplicados hay", re.compile(r"\bsin\s+duplicados\s+hay\b", re.I)),
    ("ovnis reales / avistamientos reales", re.compile(r"\b(ovnis|avistamientos)\s+reales\b", re.I)),
    ("es un engaño / engaños confirmados", re.compile(r"\b(es\s+un\s+engaño|engaños\s+confirmados)\b", re.I)),
    ("son falsos", re.compile(r"\bson\s+falsos\b", re.I)),
    ("prefieren", re.compile(r"\bprefiere(n)?\b", re.I)),
    ("los testigos sintieron", re.compile(r"\blos\s+testigos\s+sintieron\b", re.I)),
]
MARKDOWN = re.compile(r"(^\s{0,3}(#{1,6}\s|[-*+]\s|\d+\.\s|\|)|\*\*|__|`)", re.M)
CODE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b|\bCQ\d+_[A-Z0-9_]+\b")


class Work(TypedDict, total=False):
    model: str
    question: str
    history: list[dict]
    area: list | None
    inputs: Annotated[list[dict], operator.add]
    visuals: Annotated[list[dict], operator.add]
    trace: Annotated[list[dict], operator.add]
    calls: list[dict]
    text: str
    rounds: Annotated[int, operator.add]
    charts: Annotated[int, operator.add]
    rewrites: Annotated[int, operator.add]
    nudges: Annotated[int, operator.add]
    turn: dict


def budget(charts: int) -> int:
    return min(MAX_ROUNDS, BASE_ROUNDS + ROUNDS_PER_CHART * charts)


def closing(work: Work) -> bool:
    """The model may no longer ask for tools: the budget is spent or the answer is being rewritten."""
    return work.get("rewrites", 0) > 0 or work.get("rounds", 0) + 1 >= budget(work.get("charts", 0))


UNGROUNDED = ("Revisión automática: respondiste sin consultar Gold. Si la pregunta pide datos o cómo son los datos "
              "(cifras, fuentes, coordenadas, fechas, cobertura), consulta Gold con las herramientas y responde con esos "
              "resultados. Si no pide datos (un saludo, una petición fuera del alcance), repite tu respuesta tal cual.")


def ungrounded(work: Work) -> bool:
    """An answer without any tool call, any previous evidence or a question back to the person."""
    return not work.get("trace") and not work.get("history") and "?" not in work["text"]


CLOSE = ("Límite de pasos: no puedes llamar más herramientas. Responde ya con los resultados verificados que tienes "
         "en esta conversación; si no bastan, di qué falta y propón una pregunta más concreta.")


def problems(text: str, codes: frozenset[str]) -> list[tuple[str, str]]:
    """What the final text breaks, as (code, instruction for the rewrite); empty when it is fine."""
    found = []
    if RANGE.search(text):
        found.append(("range_in_answer", "da un rango de informes: usa una sola cifra, la del resultado verificado, con su unidad"))
    hits = [name for name, pattern in FORBIDDEN if pattern.search(text)]
    if hits:
        found.append(("forbidden_phrase", "usa frases prohibidas (" + ", ".join(hits) + "), ni siquiera negadas: di, por "
                      "ejemplo, “estos datos no permiten afirmar…” o “X informes”"))
    if MARKDOWN.search(text):
        found.append(("markdown", "usa Markdown: escribe texto plano, sin títulos, listas, negritas ni tablas"))
    leaked = sorted({m for m in CODE.findall(text) if m in codes or m.startswith("CQ")})
    if leaked:
        found.append(("code_in_answer", "menciona nombres de columna, datasets o códigos (" + ", ".join(leaked[:6])
                      + "): usa nombres en español"))
    return found


def rewrite_request(found: list[tuple[str, str]]) -> str:
    return ("Revisión automática: la respuesta " + "; ".join(text for _, text in found) + ". Reescríbela corrigiendo solo eso, con las mismas "
            "cifras verificadas. No llames herramientas: usa los resultados que ya tienes.")


def codes_of(analytics: Analytics) -> frozenset[str]:
    """Identifiers of Gold that must never reach the answer text."""
    from app.gold import MEASURES, SCATTER_PAIRS, gold_analysis
    names = {*analytics.datasets, *analytics.metrics, *analytics.dimensions, *gold_analysis.ANALYSES, *MEASURES, *SCATTER_PAIRS}
    for spec in analytics.datasets.values():
        names |= set(spec["columns"])
    return frozenset(n for n in names if "_" in n)


AREA_NOTE = ("Contexto de la interfaz: la persona tiene un área seleccionada en el mapa. Mientras esté activa, el servidor "
             "limita automáticamente cada query_gold y cada analyze a los informes dentro de esa área; no hace falta filtrar por país ni por "
             "coordenadas. Usa fact_report (el área exige coordenadas aptas: eligibility map) y aplica solo los filtros "
             "que pida la pregunta, como el año o la forma. No uses run_certified ni la vista globe. Menciona que el "
             "resultado se limita al área seleccionada.")
HISTORY_TURNS = 12
# Follow-ups mostly refine the previous turn: it keeps most of its evidence, older turns a summary.
LAST_TURN_CHARS = 20000
OLDER_TURN_CHARS = 2500


def history_inputs(history: list[dict]) -> list[dict]:
    """Recent turns plus their verified evidence, for follow-up questions."""
    inputs = []
    recent = history[-HISTORY_TURNS:]
    for i, turn in enumerate(recent):
        last = i == len(recent) - 1
        inputs += [{"role": "user", "content": turn["question"]}, {"role": "assistant", "content": turn["answer"]}]
        evidence = [{"title": v.get("title"), "query": v["query"], "readable_query": v["readable_query"]["texto"],
                     "rows": v["rows"][:60 if last else 15], "row_count": v.get("row_count"), "result_type": v["result_type"]}
                    for v in turn.get("visualizations", [])]
        if evidence:
            inputs.append({"role": "user", "content": "Evidencia verificada del turno anterior (no se vuelve a mostrar): "
                           + json.dumps(evidence, ensure_ascii=False)[:LAST_TURN_CHARS if last else OLDER_TURN_CHARS]})
    return inputs


def build_graph(analytics: Analytics):
    codes = codes_of(analytics) if analytics is not None else frozenset()

    def contexto(work: Work) -> Work:
        inputs = [*history_inputs(work.get("history") or []), {"role": "user", "content": work["question"]}]
        if work.get("area"):
            inputs.append({"role": "user", "content": AREA_NOTE})
        return {"inputs": inputs}

    def modelo(work: Work, config: RunnableConfig) -> Work:
        settings = config["configurable"]
        final = closing(work)
        extra = [{"role": "user", "content": CLOSE}] if final and not work.get("rewrites") else []
        payload = {"model": work["model"], "instructions": instructions.build(analytics), "input": [*work["inputs"], *extra],
                   "tools": tools.schemas(analytics), "parallel_tool_calls": True}
        if final:
            payload["tool_choice"] = "none"
        response = settings["stream"](settings["account"], payload)
        outputs = response.get("output", [])
        calls = [] if final else [o for o in outputs if o.get("type") == "function_call"]
        text = "\n".join(c["text"] for o in outputs if o.get("type") == "message"
                         for c in o.get("content", []) if c.get("type") == "output_text").strip()
        kept = [o for o in outputs if o.get("type") != "function_call"] if final else outputs
        return {"inputs": [*extra, *kept], "calls": calls, "text": text, "rounds": 1}

    def herramientas(work: Work) -> Work:
        shown = list(work.get("visuals") or [])
        before = len(shown)
        inputs, trace = [], []
        for call in work["calls"]:
            try:
                arguments = json.loads(call.get("arguments") or "{}")
                result = tools.execute(analytics, call["name"], arguments, shown, work.get("area"))
                trace.append({"tool": call["name"], "arguments": arguments, "ok": True})
                done = (result.get("decision") or {}) if call["name"] == "search_certified" else {}
                if done.get("executed"):
                    trace.append({"tool": "run_certified", "arguments": {"id": done["id"]}, "ok": True, "auto": True})
            except QueryError as exc:
                result = {"error": str(exc)[:1500], "code": exc.code, "repair": "Corrige los argumentos y vuelve a llamar."}
                trace.append({"tool": call["name"], "ok": False, "code": exc.code, "error": str(exc)[:1500]})
            except (ValueError, KeyError, TypeError) as exc:
                result = {"error": str(exc)[:1500], "code": "invalid_arguments"}
                trace.append({"tool": call["name"], "ok": False, "code": "invalid_arguments", "error": str(exc)[:1500]})
            except Exception as exc:  # noqa: BLE001 - a failing tool must not end the turn
                result = {"error": "Error interno de la herramienta; prueba otra consulta.", "code": "tool_failed"}
                trace.append({"tool": call["name"], "ok": False, "code": "tool_failed", "error": type(exc).__name__})
            inputs.append({"type": "function_call_output", "call_id": call["call_id"], "output": json.dumps(result, ensure_ascii=False)})
        added = shown[before:]
        return {"inputs": inputs, "visuals": added, "trace": trace, "calls": [], "charts": len(added)}

    def verificar(work: Work) -> Work:
        if not work["text"]:
            raise HTTPException(502, {"code": "inference_interrupted",
                                      "message": "El modelo no devolvió una respuesta completa. Puedes reintentar la pregunta."})
        if ungrounded(work) and not work.get("nudges") and not closing(work):
            # The only check that may call tools again: an answer from memory is never evidence.
            return {"inputs": [{"role": "user", "content": UNGROUNDED}], "nudges": 1, "text": "",
                    "trace": [{"tool": "verificar", "ok": False, "code": "no_data_used"}]}
        found = problems(work["text"], codes)
        if found and work.get("rewrites", 0) < MAX_REWRITES:
            return {"inputs": [{"role": "user", "content": rewrite_request(found)}], "rewrites": 1, "text": "",
                    "trace": [{"tool": "verificar", "ok": False, "code": code} for code, _ in found]}
        return {}

    def componer(work: Work) -> Work:
        visuals = work.get("visuals") or []
        turn = {"question": work["question"], "answer": work["text"], "visualizations": visuals, "trace": work.get("trace") or [],
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


@lru_cache(maxsize=4)
def compiled(analytics: Analytics):
    """One compiled graph per Gold load (the Analytics instance is fixed for the process)."""
    return build_graph(analytics)


def run(analytics: Analytics, stream: Callable[[dict, dict], dict], account: dict, model: str, question: str,
        history: list[dict], area: list | None = None) -> dict:
    work = compiled(analytics).invoke(
        {"model": model, "question": question, "history": history, "area": area,
         "inputs": [], "visuals": [], "trace": [], "calls": [], "text": "", "rounds": 0, "charts": 0, "rewrites": 0,
         "nudges": 0},
        {"recursion_limit": RECURSION_LIMIT, "configurable": {"account": account, "stream": stream}})
    return work["turn"]


# Enough for MAX_ROUNDS model calls, their tool steps and one rewrite.
RECURSION_LIMIT = 2 * MAX_ROUNDS + 10
