"""Typed tools the model may call. No SQL, no code, no filesystem access.

Each tool returns a compact payload for the model and, for data results, the
full Gold envelope for the interface. Validation errors go back to the model
with their code so it can repair the call; they never end the turn.
"""
from __future__ import annotations

import json

from app.gold import OPS, VIEWS, Analytics, Query, QueryError

MAX_VISUALS = 4
MODEL_ROWS = 60
MODEL_CHARS = 30000
KINDS = ["sources", "origins", "collections", "countries", "shapes", "colors", "nuclear_facilities"]


def query_schema(analytics: Analytics) -> dict:
    """JSON Schema of the Gold query contract, generated from the catalogs."""
    limits = analytics.limits
    scalar = {"type": ["string", "number", "boolean", "null"]}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["dataset"],
        "properties": {
            "dataset": {"type": "string", "enum": sorted(analytics.datasets)},
            "filters": {"type": "array", "maxItems": limits["max_filters"], "items": {
                "type": "object", "additionalProperties": False, "required": ["column"],
                "properties": {"column": {"type": "string"}, "op": {"type": "string", "enum": list(OPS)},
                               "value": {"anyOf": [scalar, {"type": "array", "items": scalar, "maxItems": limits["max_in_values"]}]}}}},
            "group_by": {"type": "array", "items": {"type": "string"}, "maxItems": limits["max_group_by"]},
            "metrics": {"type": "array", "items": {"type": "string", "enum": sorted(analytics.metrics)}, "maxItems": limits["max_metrics"]},
            "columns": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
            "eligibility": {"type": "array", "items": {"type": "string", "enum": sorted(analytics.eligibility)}},
            "view": {"type": "string", "enum": list(VIEWS)},
            "title": {"type": ["string", "null"], "maxLength": 120,
                      "description": "Título breve en español para la visualización, sin IDs ni nombres de columna."},
            "order_by": {"type": ["string", "null"]},
            "descending": {"type": "boolean"},
            "limit": {"type": "integer", "minimum": 1, "maximum": limits["max_limit"]},
            "rollup": {"type": "boolean"},
        },
    }


def schemas(analytics: Analytics) -> list[dict]:
    certified = [q["id"] for q in analytics.certified()["queries"]]

    def fn(name, description, properties, required):
        return {"type": "function", "strict": False, "name": name, "description": description,
                "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}
    return [
        fn("search_certified", "Busca consultas certificadas para la pregunta. Úsala SIEMPRE antes de componer una consulta.",
           {"question": {"type": "string", "maxLength": 500}}, ["question"]),
        fn("run_certified", "Ejecuta una consulta certificada válida por su ID y devuelve su visualización.",
           {"id": {"type": "string", "enum": certified}}, ["id"]),
        {"type": "function", "strict": False, "name": "query_gold",
         "description": "Ejecuta una consulta validada sobre Gold y devuelve una visualización lista. Sin SQL. "
                        "Declara eligibility cuando uses año, mes, día, hora, mapa, país o proximidad en fact_report. "
                        "Los ratios se recalculan; los porcentajes no se suman. report_count llega siempre con su cota inferior.",
         "parameters": query_schema(analytics)},
        fn("find_entities", "Resuelve el ID real de fuentes, orígenes, colecciones, países, formas, colores o instalaciones nucleares por su nombre o alias.",
           {"text": {"type": "string", "maxLength": 120}, "kind": {"type": ["string", "null"], "enum": [*KINDS, None]}}, ["text", "kind"]),
        fn("describe_data", "Describe datasets, columnas, dimensiones, métricas y elegibilidad. Sin dataset, lista todos.",
           {"dataset": {"type": ["string", "null"]}}, ["dataset"]),
    ]


def compact(result: dict) -> dict:
    """What the model reads: rows with labels and the caveats it must mention."""
    exclusions = result.get("exclusions")
    payload = {
        "result_type": result["result_type"], "certified_query_id": result.get("certified_query_id"),
        "view": result["view"], "title": result.get("title"), "rows": result["rows"][:MODEL_ROWS],
        "rows_shown_to_model": min(len(result["rows"]), MODEL_ROWS), "row_count": result["row_count"],
        "truncated": result["truncated"], "matched_source_rows": result["matched_source_rows"], "total": result.get("total"),
        "duplicate_bounds": result.get("duplicate_bounds"),
        "eligibility_applied": [e["code"] for e in result.get("eligibility_applied", [])],
        "exclusions": None if not exclusions else {
            "base_reports": exclusions["base_reports"], "eligible_reports": exclusions["eligible_reports"],
            "excluded_reports": exclusions["excluded_reports"],
            "top_reasons": exclusions["excluded_by_reason"][:5]},
        "external_evidence_reports": result.get("external_evidence_reports"),
        "limitations": [{"code": l["code"], "text": l["text"]} for l in result["limitations"]],
        "readable_query": result["readable_query"]["texto"],
        "load_id": result["provenance"]["gold_load_id"],
    }
    text = json.dumps(payload, ensure_ascii=False)
    while len(text) > MODEL_CHARS and payload["rows"]:
        payload["rows"] = payload["rows"][: max(1, len(payload["rows"]) // 2)]
        payload["rows_shown_to_model"] = len(payload["rows"])
        text = json.dumps(payload, ensure_ascii=False)
    return payload


def execute(analytics: Analytics, name: str, arguments: dict, visuals: list) -> dict:
    """Run one tool call. Data results are appended to ``visuals`` (full envelope)."""
    if not isinstance(arguments, dict):
        raise QueryError("contract", "Los argumentos deben ser un objeto JSON")
    if name in ("query_gold", "run_certified"):
        if len(visuals) >= MAX_VISUALS:
            raise QueryError("visual_limit", f"Máximo {MAX_VISUALS} visualizaciones por respuesta; responde con las que ya tienes.")
        if name == "query_gold":
            result = analytics.query(arguments)
        else:
            if set(arguments) != {"id"} or not isinstance(arguments["id"], str):
                raise QueryError("contract", "run_certified requiere solo id")
            result = analytics.run_certified(arguments["id"])
        visuals.append(result)
        return compact(result)
    if name == "search_certified":
        question = arguments.get("question")
        if not isinstance(question, str) or not question.strip():
            raise QueryError("contract", "search_certified requiere question")
        found = analytics.search_certified(question)
        items = {i["id"]: i for i in analytics.certified()["queries"]}
        return {"candidates": [{"id": f["id"], "title": f["title"], "score": f["score"], "valid": f["status"]["valid"],
                                "description": items[f["id"]]["description"], "examples": items[f["id"]]["examples"],
                                "limitation": items[f["id"]]["limitation"]} for f in found],
                "rule": "Si un candidato válido responde la pregunta, ejecútalo con run_certified; si no, compón con query_gold."}
    if name == "find_entities":
        text, kind = arguments.get("text"), arguments.get("kind")
        if not isinstance(text, str) or (kind is not None and kind not in KINDS):
            raise QueryError("contract", f"find_entities requiere text y kind en {KINDS} o null")
        found = analytics.find_entities(text, kind=kind)
        return {"matches": [{k: e.get(k) for k in ("kind", "id", "display_name", "canonical_name", "match", "report_count")} for e in found],
                "ambiguous": len(found) > 1, "not_found": not found}
    if name == "describe_data":
        dataset = arguments.get("dataset")
        if dataset is None:
            return {"datasets": analytics.describe(), "views": {k: v["description"] for k, v in VIEWS.items()}}
        info = analytics.describe(dataset)
        info.pop("profile", None)
        return info
    raise QueryError("tool_unknown", f"Herramienta desconocida: {name}")
