"""Typed tools the model may call. No SQL, no code, no filesystem access.

Each tool returns a compact payload for the model and, for data results, the
full Gold envelope for the interface. Validation errors go back to the model
with their code so it can repair the call; they never end the turn.
"""
from __future__ import annotations

from functools import lru_cache
import json

from app.gold import DENSITY_MAX_CELLS, MEASURES, OPS, SCATTER_PAIRS, VIEWS, Analytics, Query, QueryError, gold_analysis, query_digest

MAX_VISUALS = 4
MODEL_ROWS = 60
MODEL_CHARS = 30000
KINDS = ["sources", "origins", "collections", "countries", "regions", "shapes", "colors", "nuclear_facilities"]
QUERY_VIEWS = [v for v in VIEWS if v not in gold_analysis.ANALYSIS_VIEWS]


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
            "view": {"type": "string", "enum": QUERY_VIEWS},
            "measure": {"type": ["string", "null"], "enum": [*MEASURES, *SCATTER_PAIRS, None],
                        "description": "Solo histogram, ecdf y scatter: la medida que se agrupa en tramos."},
            "title": {"type": ["string", "null"], "maxLength": 120,
                      "description": "Título breve en español para la visualización, sin IDs ni nombres de columna."},
            "order_by": {"type": ["string", "null"]},
            "descending": {"type": "boolean"},
            "limit": {"type": "integer", "minimum": 1, "maximum": DENSITY_MAX_CELLS,
                      "description": f"Hasta {limits['max_limit']} filas; solo density admite hasta {DENSITY_MAX_CELLS} celdas."},
            "rollup": {"type": "boolean"},
        },
    }


def needs_schema(analytics: Analytics) -> dict:
    """What the question asks for, declared by the model so coverage is decided in code."""
    query = query_schema(analytics)["properties"]
    return {"type": ["object", "null"], "additionalProperties": False,
            "description": "Lo que pide la pregunta, con IDs reales de find_entities: filtros (país, año, fuente…), "
                           "agrupación y métricas. El código compara cada candidata con esto.",
            "properties": {"filters": query["filters"], "group_by": query["group_by"], "metrics": query["metrics"]}}


def _same(a, b) -> bool:
    norm = lambda v: sorted(map(_same_key, v)) if isinstance(v, list) else _same_key(v)
    return norm(a) == norm(b)


def _same_key(value) -> str:
    return str(int(value) if isinstance(value, bool) else value).strip().casefold()


def _plan_or_none(analytics: Analytics, raw: dict):
    try:
        q = Query.parse(raw, analytics.limits)
        return q, analytics._plan(q)
    except QueryError:
        return None, None


def _readable(analytics: Analytics, raw: dict) -> str | None:
    q, plan = _plan_or_none(analytics, raw)
    return analytics._readable(q, plan, plan["metrics"])["texto"] if plan else None


def _needs(raw) -> dict:
    if raw is None:
        return {}
    if not isinstance(raw, dict) or set(raw) - {"filters", "group_by", "metrics"}:
        raise QueryError("contract", "needs admite solo filters, group_by y metrics")
    filters = raw.get("filters") or []
    if not isinstance(filters, list) or not all(isinstance(f, dict) and isinstance(f.get("column"), str) for f in filters):
        raise QueryError("contract", "needs.filters debe ser una lista de filtros con column")
    for key in ("group_by", "metrics"):
        if raw.get(key) is not None and not (isinstance(raw[key], list) and all(isinstance(v, str) for v in raw[key])):
            raise QueryError("contract", f"needs.{key} debe ser una lista de textos")
    return {"filters": [{"column": f["column"], "op": f.get("op", "eq"), "value": f.get("value")} for f in filters],
            "group_by": raw.get("group_by"), "metrics": raw.get("metrics") or []}


def coverage(analytics: Analytics, item: dict, needs: dict) -> dict:
    """Compare a certified query with what the question needs; list every gap.

    Two gaps are not gaps, because the certified result already holds the figure:
    - a total (``group_by: []``) asked of a breakdown that carries its total row (``rollup``);
    - an ``eq`` filter on a column the certified query groups by (“¿cuántos vienen de
      NUFORC?” over the breakdown by origin): it goes to ``in_breakdown`` and ``search``
      checks that the row is really in the result before accepting it.
    """
    query = item["query"]
    grouped = set(query.get("group_by", []))
    missing, in_breakdown = [], []
    for need in needs.get("filters", []):
        if any(f["column"] == need["column"] and f.get("op", "eq") == need["op"] and _same(f.get("value"), need["value"])
               for f in query.get("filters", [])):
            continue
        if need["op"] == "eq" and need["column"] in grouped and not isinstance(need["value"], list):
            in_breakdown.append(need)
        else:
            missing.append({"aspect": "filter", **need})
    asked = needs.get("group_by")
    if asked is not None and sorted(asked) != sorted(grouped):
        breakdown = {f["column"] for f in in_breakdown}
        if not (asked == [] and query.get("rollup")) and set(asked) | breakdown != grouped:
            missing.append({"aspect": "group_by", "asked": asked, "certified": query.get("group_by", [])})
    for metric in needs.get("metrics", []):
        if metric not in query.get("metrics", []):
            missing.append({"aspect": "metric", "metric": metric})
    columns = analytics.datasets[query["dataset"]]["columns"]
    unsupported = sorted({m.get("column") for m in missing if m["aspect"] == "filter" and m["column"] not in columns}
                         | {c for m in missing if m["aspect"] == "group_by" for c in m["asked"] if c not in columns})
    return {"coverage": "total" if not missing else "parcial", "missing": missing, "in_breakdown": in_breakdown,
            "dataset_lacks_columns": unsupported}


def _focus(result: dict, in_breakdown: list[dict]) -> list[dict] | None:
    """Rows of a certified result that answer the ``eq`` filters asked over its breakdown."""
    rows = [r for r in result["rows"] if all(_same(r.get(f["column"]), f["value"]) for f in in_breakdown)]
    return rows or None


def compose_from(analytics: Analytics, item: dict, needs: dict) -> dict | None:
    """A valid query equivalent to the certified one plus what the question adds.

    Keeps the certified dataset when it has every needed column; otherwise moves to
    the first dataset that does, declaring the eligibility its columns require.
    """
    base = item["query"]
    asked = {(f["column"], f["op"]) for f in needs.get("filters", [])}
    filters = [f for f in base.get("filters", []) if (f["column"], f.get("op", "eq")) not in asked] + needs.get("filters", [])
    group_by = needs["group_by"] if needs.get("group_by") is not None else list(base.get("group_by", []))
    metrics = list(dict.fromkeys([*base.get("metrics", []), *needs.get("metrics", [])]))
    used = {*group_by, *(f["column"] for f in filters)}
    candidates = [base["dataset"]] + sorted(d for d in analytics.datasets if d != base["dataset"])
    for dataset in candidates:
        spec = analytics.datasets[dataset]
        if not used <= set(spec["columns"]) or not all(dataset in analytics.metrics.get(m, {}).get("datasets", []) for m in metrics):
            continue
        eligibility = [] if spec["eligibility"] else sorted(
            analytics._requirements(dataset, used) | {r for m in metrics for r in analytics.metrics[m]["requires"]})
        for view in dict.fromkeys([base.get("view", "table"), "table"]):
            raw = {**{k: v for k, v in base.items() if k != "title"}, "dataset": dataset, "filters": filters,
                   "group_by": group_by, "metrics": metrics, "eligibility": eligibility, "view": view}
            if dataset != base["dataset"] and not spec.get("row_listing"):
                raw["columns"] = []
            if _plan_or_none(analytics, raw)[1]:
                return raw
    return None


def search(analytics: Analytics, question: str, needs: dict, ran: dict | None = None) -> dict:
    """Certified candidates for the question, their coverage and the decision.

    ``decision.explicit`` is true when the coverage rests on declared filters or a declared
    grouping; empty needs “cover” anything, so only explicit decisions are run by the server.
    ``ran`` collects the certified results this search had to execute (to check a breakdown).
    """
    ran = {} if ran is None else ran
    found = analytics.search_certified(question)
    items = {i["id"]: i for i in analytics.certified()["queries"]}
    explicit = bool(needs.get("filters")) or needs.get("group_by") is not None
    candidates, decision = [], None
    for f in found:
        item = items[f["id"]]
        entry = {"id": f["id"], "title": f["title"], "score": f["score"], "valid": f["status"]["valid"],
                 "invalid_reasons": f["status"]["reasons"], "description": item["description"],
                 "examples": item["examples"], "limitation": item["limitation"],
                 "certified_query": {k: item["query"].get(k) for k in ("dataset", "filters", "group_by", "metrics", "view")},
                 "readable_query": _readable(analytics, item["query"])}
        if needs:
            entry.update(coverage(analytics, item, needs))
            if entry["coverage"] == "total" and entry["valid"] and entry["in_breakdown"]:
                result = ran.get(f["id"]) or analytics.run_certified(f["id"])
                ran[f["id"]] = result
                focus = _focus(result, entry["in_breakdown"])
                if focus:
                    entry["focus_rows"] = focus[:5]
                else:
                    entry["coverage"] = "parcial"
                    entry["missing"] = [{"aspect": "filter", **n, "reason": "la fila no está en el resultado certificado"}
                                        for n in entry["in_breakdown"]]
            if entry["coverage"] == "total" and entry["valid"]:
                decision = decision or {"tool": "run_certified", "id": f["id"], "explicit": explicit}
            else:
                composed = compose_from(analytics, item, needs)
                entry["composed_query"] = composed
                entry["composed_readable_query"] = _readable(analytics, composed) if composed else None
        candidates.append(entry)
    if needs and decision is None:
        composed = next((c["composed_query"] for c in candidates if c.get("composed_query")), None)
        decision = {"tool": "query_gold", "query": composed} if composed else {"tool": "query_gold", "query": None}
    return {"candidates": candidates, "decision": decision,
            "rule": ("Si decision trae executed, la certificada ya se ejecutó y se muestra: no la vuelvas a llamar; "
                     "focus_rows son las filas que responden a lo pedido. Si decision no es explicit, comprueba que "
                     "la certificada responde de verdad la pregunta antes de llamar a run_certified. "
                     "Con coverage parcial o certificación inválida, usa query_gold con composed_query "
                     "(añade title) o compón otra que cubra todos los filtros, la agrupación y las métricas pedidas. "
                     "Si no declaraste needs, compara tú certified_query con la pregunta antes de decidir.")}


@lru_cache(maxsize=4)
def schemas(analytics: Analytics) -> list[dict]:
    """Tool definitions, built once per Gold load (the Analytics instance)."""
    certified = [q["id"] for q in analytics.certified()["queries"]]

    def fn(name, description, properties, required):
        return {"type": "function", "strict": False, "name": name, "description": description,
                "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}
    return [
        fn("search_certified", "Busca consultas certificadas para la pregunta. Úsala SIEMPRE antes de componer una consulta. "
                               "Declara en needs los filtros, la agrupación y las métricas que pide la pregunta: el código "
                               "devuelve la cobertura de cada candidata y, si es parcial, una consulta compuesta equivalente.",
           {"question": {"type": "string", "maxLength": 500}, "needs": needs_schema(analytics)}, ["question", "needs"]),
        fn("run_certified", "Ejecuta una consulta certificada válida por su ID y devuelve su visualización. "
                            "Solo cuando search_certified indicó coverage total: no admite filtros adicionales.",
           {"id": {"type": "string", "enum": certified}}, ["id"]),
        {"type": "function", "strict": False, "name": "query_gold",
         "description": "Ejecuta una consulta validada sobre Gold y devuelve una visualización lista. Sin SQL. "
                        "Declara eligibility cuando uses año, mes, día, hora, mapa, país o proximidad en fact_report. "
                        "Los ratios se recalculan; los porcentajes no se suman. report_count cuenta cada informe como una unidad.",
         "parameters": query_schema(analytics)},
        {"type": "function", "strict": False, "name": "analyze",
         "description": "Análisis de varias etapas que una consulta agrupada no expresa, con parámetros tipados y la misma "
                        "validación de filtros que query_gold: " + "; ".join(f"{k} ({v['label'].lower()}, vista {v['view']})"
                                                                           for k, v in gold_analysis.ANALYSES.items())
                        + ". La elegibilidad la declara el servidor. Devuelve una visualización lista.",
         "parameters": gold_analysis.schema()},
        fn("find_entities", "Resuelve el ID real de fuentes, orígenes, colecciones, países, estados o provincias (regions), formas, colores o instalaciones nucleares por su nombre o alias.",
           {"text": {"type": "string", "maxLength": 120}, "kind": {"type": ["string", "null"], "enum": [*KINDS, None]}}, ["text", "kind"]),
        fn("describe_data", "Describe datasets, columnas, dimensiones, métricas y elegibilidad. Sin dataset, lista todos.",
           {"dataset": {"type": ["string", "null"]}}, ["dataset"]),
    ]


def extremes(result: dict) -> dict | None:
    """Highest and lowest rows of each metric over ALL rows of the result.

    The model reads at most MODEL_ROWS rows; a 120-year series cut at 60 would hide its peak
    and send the model to query again. Calendar rows for an unknown month are left out."""
    query = result.get("query") or {}
    metrics, rows = query.get("metrics") or [], [r for r in result["rows"] if r.get("event_month_label") != "Mes desconocido"]
    if not metrics or not query.get("group_by") or len(rows) < 2:
        return None
    out = {}
    for metric in metrics[:4]:
        valued = [r for r in rows if isinstance(r.get(metric), (int, float)) and not isinstance(r.get(metric), bool)]
        if valued:
            ranked = sorted(valued, key=lambda r: r[metric], reverse=True)
            out[metric] = {"max": ranked[:3], "min": ranked[-1:]}
    return out or None


def _trim(value, items: int = 25, depth: int = 0):
    """Analysis details for the model: long lists cut, nested structures kept small."""
    if isinstance(value, list):
        return [_trim(v, items, depth + 1) for v in value[:items]]
    if isinstance(value, dict):
        return {k: _trim(v, items, depth + 1) for k, v in value.items()}
    return value


def _distribution_summary(d: dict) -> dict:
    """Histogram, ECDF and scatter bins: the shape of the distribution without every bin twice."""
    keys = ("measure", "label", "unit", "facet", "over_max", "without_duration", "with_duration", "with_value", "x", "y")
    out = {k: d[k] for k in keys if k in d}
    if d.get("series"):
        out["series"] = [{k: s[k] for k in ("key", "label", "with_value", "over_max", "without_value", "below_min") if k in s} for s in d["series"]]
    return out


def compact(result: dict) -> dict:
    """What the model reads: rows with labels and the caveats it must mention."""
    exclusions = result.get("exclusions")
    payload = {
        "extremes": extremes(result),
        "result_type": result["result_type"], "certified_query_id": result.get("certified_query_id"),
        "view": result["view"], "title": result.get("title"), "rows": result["rows"][:MODEL_ROWS],
        "rows_shown_to_model": min(len(result["rows"]), MODEL_ROWS), "row_count": result["row_count"],
        "truncated": result["truncated"], "matched_source_rows": result["matched_source_rows"], "total": result.get("total"),
        "eligibility_applied": [e["code"] for e in result.get("eligibility_applied", [])],
        "exclusions": None if not exclusions else {
            "scope": exclusions["scope"],
            "base_reports": exclusions["base_reports"], "eligible_reports": exclusions["eligible_reports"],
            "excluded_reports": exclusions["excluded_reports"],
            "top_reasons": exclusions["excluded_by_reason"][:5]},
        "external_evidence_reports": result.get("external_evidence_reports"),
        "limitations": [{"code": l["code"], "text": l["text"]} for l in result["limitations"]],
        "readable_query": result["readable_query"]["texto"],
        "load_id": result["provenance"]["gold_load_id"],
        **({"metric_labels": result["metric_labels"]} if result.get("metric_labels") else {}),
        **({"analysis": _trim(result["analysis"])} if result.get("analysis") else {}),
        **({"points": result["points"]} if result.get("points") else {}),
        **({"distribution": _distribution_summary(result["distribution"])} if result.get("distribution") else {}),
    }
    text = json.dumps(payload, ensure_ascii=False)
    while len(text) > MODEL_CHARS and payload["rows"]:
        payload["rows"] = payload["rows"][: max(1, len(payload["rows"]) // 2)]
        payload["rows_shown_to_model"] = len(payload["rows"])
        text = json.dumps(payload, ensure_ascii=False)
    return payload


def _is_listing(raw: dict) -> bool:
    """A request for individual report rows: the agent never answers with that table."""
    return (raw.get("dataset") == "fact_report" and raw.get("view", "table") == "table"
            and not raw.get("group_by") and not raw.get("metrics"))


def visual_pack(analytics: Analytics, raw: dict, room: int) -> list[dict]:
    """Deterministic visuals for "show me the reports in X": map, timeline, shapes.

    Same filters as the listing the model asked for, so the evidence is the same
    selection seen as a map (2D/3D), an evolution by year and a shape comparison.
    """
    filters = raw.get("filters") or []
    base = set(raw.get("eligibility") or [])
    title = (raw.get("title") or "").strip()
    plans = [
        {"view": "points", "eligibility": sorted(base | {"map"}), "limit": analytics.limits["max_limit"],
         "title": f"{title or 'Informes'} en el mapa"},
        {"view": "timeseries", "group_by": ["event_year"], "metrics": ["report_count"], "order_by": "event_year",
         "eligibility": sorted(base | {"calendar"}), "limit": analytics.limits["max_limit"], "title": "Informes por año"},
        {"view": "bars", "group_by": ["shape_code"], "metrics": ["report_count"], "order_by": "report_count",
         "descending": True, "eligibility": sorted(base), "limit": 13, "title": "Formas reportadas"},
    ]
    results = []
    for plan in plans[:room]:
        try:
            area = {"area": raw["area"]} if raw.get("area") else {}
            result = analytics.query({"dataset": "fact_report", "filters": filters, **area, **plan})
        except QueryError:
            continue
        if plan.get("group_by") == ["shape_code"]:
            unknown = sum(r["report_count"] for r in result["rows"] if r.get("shape_code") is None)
            result["rows"] = [r for r in result["rows"] if r.get("shape_code") is not None][:12]
            result["row_count"] = len(result["rows"])
            if unknown:
                result["limitations"] = [*result["limitations"], {"code": "shape_unknown",
                                         "text": f"{unknown} informes no registran forma y no aparecen en este gráfico."}]
        if result["rows"]:
            results.append(result)
    return results


def _already_shown(analytics: Analytics, name: str, arguments: dict, visuals: list) -> dict | None:
    """The visualization of this answer that already runs the same query (titles aside)."""
    try:
        if name == "run_certified":
            items = {i["id"]: i for i in analytics.certified()["queries"]}
            if arguments.get("id") not in items:
                return None
            raw = items[arguments["id"]]["query"]
        else:
            raw = arguments
        wanted = query_digest(raw, analytics.limits)
    except QueryError:
        return None
    for visual in visuals:
        try:
            if query_digest(visual["query"], analytics.limits) == wanted:
                return visual
        except (QueryError, KeyError):
            continue
    return None


def _content(analytics: Analytics, raw: dict):
    """What a query selects and measures, ignoring how it is drawn, sorted or cut."""
    canonical = Query.parse(raw, analytics.limits).canonical()
    return json.dumps({k: canonical.get(k) for k in ("dataset", "filters", "group_by", "metrics", "eligibility", "area")},
                      sort_keys=True)


def _lookup_of_shown(analytics: Analytics, raw: dict, visuals: list) -> bool:
    """True when ``raw`` re-reads a visualization already shown: same data and either the same
    view or a sorted top-k cut of it. A different full view (map next to ranking) is not one."""
    try:
        wanted = _content(analytics, raw)
        q = Query.parse(raw, analytics.limits)
    except QueryError:
        return False
    for visual in visuals:
        try:
            if _content(analytics, visual["query"]) != wanted:
                continue
        except (QueryError, KeyError):
            continue
        if q.view == visual["view"] or (q.order_by and q.limit < visual["row_count"]):
            return True
    return False


def execute(analytics: Analytics, name: str, arguments: dict, visuals: list, area: list | None = None) -> dict:
    """Run one tool call. Data results are appended to ``visuals`` (full envelope).

    ``area`` is the selection drawn on a map in the web app. While it is active every
    query is limited to it by the server, whatever the model sends."""
    if not isinstance(arguments, dict):
        raise QueryError("contract", "Los argumentos deben ser un objeto JSON")
    if area and name == "run_certified":
        raise QueryError("area_active", "Hay un área seleccionada: las consultas certificadas no la aplican. Usa query_gold sobre fact_report.")
    if area and name == "query_gold":
        arguments = {**arguments, "area": area}
    if name in ("query_gold", "run_certified"):
        if name == "query_gold" and isinstance(arguments.get("metrics"), list):
            # One figure per question: never a second "excluding pending matches" count.
            kept = [m for m in arguments["metrics"] if m != "report_count_excl_candidates"]
            arguments = {**arguments, "metrics": kept or ["report_count"]}
        if name == "run_certified" and (set(arguments) != {"id"} or not isinstance(arguments["id"], str)):
            raise QueryError("contract", "run_certified requiere solo id")
        repeated = _already_shown(analytics, name, arguments, visuals)
        if repeated is not None:
            return {**compact(repeated), "note": "Esta misma consulta ya se muestra en esta respuesta; no se repite. "
                                                 "Usa estas filas o pide otra visualización distinta."}
        if name == "query_gold" and _lookup_of_shown(analytics, arguments, visuals):
            # Re-sorting or cutting data already on screen (“which year had most?”) answers the
            # model, but drawing it again would show the user the same data twice.
            return {**compact(analytics.query(arguments)),
                    "note": "Estos datos ya se muestran en otra visualización de esta respuesta; esta consulta solo "
                            "te sirve para leerlos ordenados y no se dibuja. Usa extremes para máximos y mínimos."}
        if len(visuals) >= MAX_VISUALS:
            raise QueryError("visual_limit", f"Máximo {MAX_VISUALS} visualizaciones por respuesta; responde con las que ya tienes.")
        if name == "query_gold" and _is_listing(arguments):
            pack = visual_pack(analytics, arguments, MAX_VISUALS - len(visuals))
            if pack:
                visuals.extend(pack)
                return {"note": "Un listado de informes se muestra como mapa (2D/3D), evolución por año y formas. "
                                "Describe estas visualizaciones; no menciones tablas.",
                        "visualizations": [compact(r) for r in pack]}
        result = analytics.query(arguments) if name == "query_gold" else analytics.run_certified(arguments["id"])
        visuals.append(result)
        return compact(result)
    if name == "analyze":
        try:
            wanted = gold_analysis.parse(analytics, arguments)
        except QueryError:
            wanted = None
        if wanted is not None:
            digest = json.dumps([wanted[0], wanted[1], area], sort_keys=True, default=str)
            for visual in visuals:
                q = visual.get("query") or {}
                if q.get("analysis") and json.dumps([q["analysis"], q["params"], q.get("area")], sort_keys=True, default=str) == digest:
                    return {**compact(visual), "note": "Este mismo análisis ya se muestra en esta respuesta; no se repite."}
        if len(visuals) >= MAX_VISUALS:
            raise QueryError("visual_limit", f"Máximo {MAX_VISUALS} visualizaciones por respuesta; responde con las que ya tienes.")
        result = gold_analysis.analyze(analytics, arguments, area)
        visuals.append(result)
        return compact(result)
    if name == "search_certified":
        question = arguments.get("question")
        if not isinstance(question, str) or not question.strip():
            raise QueryError("contract", "search_certified requiere question")
        ran: dict = {}
        found = search(analytics, question, _needs(arguments.get("needs")), ran)
        decision = found.get("decision") or {}
        # A valid certified query that explicitly covers the whole question runs in the same
        # step: the model would only call run_certified with it, one more round trip.
        if decision.get("tool") == "run_certified" and decision.get("explicit") and not area and len(visuals) < MAX_VISUALS:
            result = _already_shown(analytics, "run_certified", {"id": decision["id"]}, visuals)
            if result is None:
                result = ran.get(decision["id"]) or analytics.run_certified(decision["id"])
                visuals.append(result)
            found["decision"] = {**decision, "executed": True, "result": compact(result)}
        return found
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
