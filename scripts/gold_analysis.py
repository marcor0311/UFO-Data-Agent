#!/usr/bin/env python3
"""Typed multi-step analyses over the Gold serving cache (the ``analyze`` tool).

Some questions are not one grouped count: the change of each source between two
decades, days far above their local level, ranks over the years, spatio-temporal
groups, K-means profiles, the comparison of two reports… Each analysis here has a
closed set of typed parameters, validates its filters with the same contract as
``query_gold`` (columns, values and eligibility) and returns the same result
envelope, so the interface, the history and the provenance work unchanged. No SQL
or code comes from the model.

CLI:
  gold_analysis.py '<json request>'   e.g. '{"analysis": "period_change", "params": {"period": "decade", "from": 2000, "to": 2010}}'
"""
from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import closing
from contextvars import ContextVar
from datetime import date, timedelta
import itertools
import json
import math
import random
import sys

if __package__:
    from .gold_common import text_digest
    from .gold_query import (ANALYSIS_VIEWS, OTHER, QUANTILES, SCATTER_PAIRS, VIEWS, Analytics, GoldUnavailable, Query, QueryError)
else:
    from gold_common import text_digest
    from gold_query import (ANALYSIS_VIEWS, OTHER, QUANTILES, SCATTER_PAIRS, VIEWS, Analytics, GoldUnavailable, Query, QueryError)

R = "fact_report"
MAX_YEARS = 120
CLUSTER_MAX_POINTS = 150000
FUNNEL_STAGES = [("all", "Todos los informes", "1=1"), ("calendar", "Con año", "usable_for_calendar=1"),
                 ("month", "Con mes", "usable_for_month_analysis=1"), ("day", "Con día", "usable_for_day_analysis=1"),
                 ("day_hour", "Con día y hora", "usable_for_day_analysis=1 AND usable_for_hour_analysis=1")]
MISSING_FIELDS = [("day", "Día", "usable_for_day_analysis"), ("hour", "Hora", "usable_for_hour_analysis"),
                  ("country", "País", "usable_for_country"), ("map", "Coordenadas", "usable_for_map"),
                  ("shape", "Forma", "has_known_shape"), ("duration", "Duración", "has_positive_duration"),
                  ("witnesses", "Testigos", "has_witnesses")]
COMPARE_FIELDS = ["source_code", "origin_code", "source_record_id", "date_key", "calendar_precision", "date_raw", "time_raw",
                  "event_hour", "country_iso2", "region_code", "city_name", "lat", "lng", "shape_code", "color_code",
                  "duration_seconds", "duration_bucket", "movement_type", "num_witnesses", "hynek", "vallee_code", "sound_type",
                  "direction_code", "has_description", "has_media", "duplicate_status", "pending_pair_count", "uses_external_evidence"]
COMPARE_MODEL = ["hoax_likelihood", "quality_score", "richness_score", "vader_compound", "roberta_sentiment", "emotion_7_dominant"]
COMPARE_LABELS = {"source_record_id": "ID en el archivo de la fuente", "date_raw": "Fecha original (texto)", "time_raw": "Hora original (texto)",
                  "lat": "Latitud", "lng": "Longitud", "duration_seconds": "Duración declarada (s)", "num_witnesses": "Testigos consignados",
                  "pending_pair_count": "Coincidencias por revisar", "hoax_likelihood": "Probabilidad de engaño",
                  "quality_score": "Calidad documental", "richness_score": "Riqueza del relato", "vader_compound": "Sentimiento VADER",
                  "roberta_sentiment": "Sentimiento RoBERTa"}


# -- parameters -------------------------------------------------------------
def P(kind, default=None, **kw):
    return {"kind": kind, "default": default, **kw}


ANALYSES = {
    "period_change": {
        "label": "Aporte de cada categoría al cambio entre dos períodos", "view": "waterfall",
        "params": {"period": P("enum", "decade", values=["decade", "event_year"]), "from": P("int", None, required=True),
                   "to": P("int", None, required=True), "category": P("dimension", "source_code"), "filters": P("filters", []),
                   "top": P("int", 12, min=3, max=25)}},
    "dominant_share": {
        "label": "Categoría dominante dentro de cada grupo", "view": "bars",
        "params": {"group": P("dimension", "origin_code"), "within": P("dimension", "source_code"), "filters": P("filters", [])}},
    "daily_anomalies": {
        "label": "Fechas por encima de su nivel local", "view": "timeseries",
        "params": {"from_year": P("int", 1990, min=1900, max=2030), "to_year": P("int", 2022, min=1900, max=2030),
                   "window_days": P("int", 28, min=6, max=120), "filters": P("filters", []), "top": P("int", 20, min=5, max=60)}},
    "yoy_change": {
        "label": "Cambio interanual por mes", "view": "timeseries",
        "params": {"from_year": P("int", 1991, min=1900, max=2030), "to_year": P("int", 2022, min=1900, max=2030), "filters": P("filters", [])}},
    "daily_distribution_by_month": {
        "label": "Informes por día típico de cada mes", "view": "boxplot",
        "params": {"from_year": P("int", 1990, min=1900, max=2030), "to_year": P("int", 2022, min=1900, max=2030), "filters": P("filters", [])}},
    "hour_month_deviation": {
        "label": "Desvío de la hora consignada en cada mes", "view": "matrix",
        "params": {"filters": P("filters", [])}},
    "rank_over_time": {
        "label": "Posiciones acumuladas en el tiempo", "view": "bump",
        "params": {"dimension": P("enum", "country_iso2", values=["country_iso2", "shape_code", "source_code", "color_family", "region_code"]),
                   "from_year": P("int", 1940, min=1800, max=2030), "to_year": P("int", 2022, min=1800, max=2030),
                   "top": P("int", 10, min=3, max=15), "cumulative": P("bool", True), "filters": P("filters", [])}},
    "concentration": {
        "label": "Concentración de informes en celdas", "view": "curve",
        "params": {"resolution": P("enum", 1, values=[1, 5]), "filters": P("filters", [])}},
    "cell_change": {
        "label": "Cambio de informes por celda entre dos períodos", "view": "density",
        "params": {"resolution": P("enum", 5, values=[1, 5]), "period": P("enum", "decade", values=["decade", "event_year"]),
                   "from": P("int", None, required=True), "to": P("int", None, required=True), "filters": P("filters", [])}},
    "first_appearance": {
        "label": "Primer año con informes en cada celda", "view": "density",
        "params": {"resolution": P("enum", 1, values=[1, 5]), "from_year": P("int", 1940, min=1800, max=2030), "filters": P("filters", [])}},
    "clusters": {
        "label": "Agrupaciones espacio-temporales de informes", "view": "clusters",
        "params": {"method": P("enum", "radius", values=["radius", "week_cell"]), "radius_km": P("number", 25, min=1, max=200),
                   "days": P("int", 7, min=1, max=60), "min_reports": P("int", 4, min=2, max=500),
                   "from_year": P("int", None, min=1800, max=2030), "to_year": P("int", None, min=1800, max=2030),
                   "filters": P("filters", []), "top": P("int", 500, min=10, max=2000)}},
    "facility_links": {
        "label": "Celdas unidas con su instalación más cercana", "view": "links",
        "params": {"max_km": P("number", 500, min=1, max=2000), "resolution": P("enum", 5, values=[1, 5]),
                   "filters": P("filters", []), "top": P("int", 300, min=10, max=1000)}},
    "funnel": {
        "label": "Embudo de cobertura temporal", "view": "funnel",
        "params": {"by": P("enum", "source_code", values=["source_code", "origin_code", None]), "filters": P("filters", [])}},
    "missing_combinations": {
        "label": "Combinaciones de datos que faltan juntos", "view": "upset",
        "params": {"filters": P("filters", []), "top": P("int", 20, min=5, max=60)}},
    "compare_reports": {
        "label": "Comparación de dos informes", "view": "compare",
        "params": {"report_ids": P("int_pair", None, required=True)}},
    "kmeans_profiles": {
        "label": "Perfiles exploratorios de duración y testigos (K-means)", "view": "scatter",
        "params": {"k": P("int", 4, min=2, max=6), "seed": P("int", 7, min=0, max=10000), "filters": P("filters", [])}},
    "retention": {
        "label": "Celdas que se vuelven a observar en la década siguiente", "view": "timeseries",
        "params": {"resolution": P("enum", 5, values=[1, 5]), "from_decade": P("int", 1940, min=1800, max=2020), "filters": P("filters", [])}},
    "source_overlap": {
        "label": "Países compartidos entre fuentes", "view": "matrix",
        "params": {"filters": P("filters", [])}},
    "diversity": {
        "label": "Diversidad efectiva de cada categoría", "view": "bars",
        "params": {"category": P("dimension", "shape_code"), "over": P("dimension", "country_iso2"), "filters": P("filters", [])}},
    "obs_expected": {
        "label": "Combinaciones sobrerrepresentadas (observado / esperado)", "view": "matrix",
        "params": {"rows": P("dimension", "shape_code"), "columns": P("dimension", "color_family"),
                   "min_reports": P("int", 30, min=1, max=10000), "filters": P("filters", [])}},
}


def schema() -> dict:
    """JSON Schema of the analyze tool, from ANALYSES."""
    props = {}
    for spec in ANALYSES.values():
        for name, p in spec["params"].items():
            kind = p["kind"]
            props[name] = ({"type": "integer"} if kind == "int" else {"type": "number"} if kind == "number"
                           else {"type": "boolean"} if kind == "bool" else {"type": "array", "items": {"type": "object"}} if kind == "filters"
                           else {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2} if kind == "int_pair"
                           else {"type": ["string", "integer", "null"]})
    return {"type": "object", "additionalProperties": False, "required": ["analysis"],
            "properties": {"analysis": {"type": "string", "enum": list(ANALYSES)},
                           "params": {"type": "object", "properties": props, "additionalProperties": False},
                           "title": {"type": ["string", "null"], "maxLength": 120}}}


def parse(a: Analytics, raw) -> tuple[str, dict, str | None]:
    if not isinstance(raw, dict) or set(raw) - {"analysis", "params", "title"}:
        raise QueryError("contract", "analyze admite solo analysis, params y title")
    kind = raw.get("analysis")
    if kind not in ANALYSES:
        raise QueryError("contract", f"Análisis desconocido: {kind!r}. Análisis: {sorted(ANALYSES)}")
    given = raw.get("params") or {}
    if not isinstance(given, dict):
        raise QueryError("contract", "params debe ser un objeto")
    spec = ANALYSES[kind]["params"]
    extra = set(given) - set(spec)
    if extra:
        raise QueryError("contract", f"{kind} no admite {sorted(extra)}. Parámetros: {sorted(spec)}")
    out = {}
    for name, p in spec.items():
        value = given.get(name, p["default"])
        if value is None:
            if p.get("required"):
                raise QueryError("contract", f"{kind} requiere {name}")
            out[name] = None
            continue
        kind_ = p["kind"]
        if kind_ in ("int", "number"):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or (kind_ == "int" and int(value) != value):
                raise QueryError("contract", f"{name} debe ser {'un entero' if kind_ == 'int' else 'un número'}")
            value = int(value) if kind_ == "int" else float(value)
            if ("min" in p and value < p["min"]) or ("max" in p and value > p["max"]):
                raise QueryError("contract", f"{name} debe estar entre {p.get('min')} y {p.get('max')}")
        elif kind_ == "bool":
            if not isinstance(value, bool):
                raise QueryError("contract", f"{name} debe ser booleano")
        elif kind_ == "enum":
            if value not in p["values"]:
                raise QueryError("contract", f"{name} admite {p['values']}")
        elif kind_ == "dimension":
            if a.datasets[R]["columns"].get(value) != "dimension":
                raise QueryError("not_a_dimension", f"{name}: {value!r} no es una dimensión de fact_report")
        elif kind_ == "filters":
            if not isinstance(value, list):
                raise QueryError("contract", "filters debe ser una lista")
        elif kind_ == "int_pair":
            if not (isinstance(value, list) and len(value) == 2 and all(isinstance(v, int) and not isinstance(v, bool) for v in value)
                    and value[0] != value[1]):
                raise QueryError("contract", f"{name} debe tener dos IDs de informe distintos")
        out[name] = value
    for low, high in (("from_year", "to_year"), ("from", "to")):
        if out.get(low) is not None and out.get(high) is not None and out[high] - out[low] > MAX_YEARS and low == "from_year":
            raise QueryError("contract", f"El período admite hasta {MAX_YEARS} años")
        if low == "from_year" and out.get(low) is not None and out.get(high) is not None and out[high] < out[low]:
            raise QueryError("contract", "to_year debe ser mayor o igual que from_year")
    title = raw.get("title")
    if title is not None and (not isinstance(title, str) or len(title) > 120):
        raise QueryError("contract", "title debe ser un texto de hasta 120 caracteres")
    return kind, out, title


# -- base plan and envelope --------------------------------------------------
AREA: ContextVar = ContextVar("analysis_area", default=None)  # map selection active during one analyze() call


def plan_for(a: Analytics, filters: list, columns: list, dataset: str = R, eligibility=()):
    """The validated WHERE of the analysis: filters checked like query_gold, eligibility of every column used,
    and the area selected on a map when there is one."""
    raw_columns = [f.get("column") for f in filters if isinstance(f, dict)]
    known = [c for c in [*columns, *raw_columns] if c in a.datasets[dataset]["columns"]]
    need = a._requirements(dataset, known) | set(eligibility) | ({"map"} if AREA.get() else set())
    area = {"area": AREA.get()} if AREA.get() else {}
    q = Query.parse({"dataset": dataset, "filters": filters, "eligibility": sorted(need), "metrics": ["report_count"],
                     "view": "table", **area}, a.limits)
    plan = a._plan(q)
    return q, plan


def where_sql(plan: dict, extra: list | None = None) -> str:
    parts = plan["where"] + (extra or [])
    return (" WHERE " + " AND ".join(parts)) if parts else ""


def envelope(a: Analytics, con, kind: str, params: dict, title: str | None, view: str, rows: list, q: Query, plan: dict,
             group_by: list, metrics: list, metric_labels: dict, matched: int, notes: list | None = None, meta: dict | None = None,
             label_columns: list | None = None) -> dict:
    a._add_labels(rows, label_columns if label_columns is not None else group_by)
    request = {"analysis": kind, "params": params}
    request_sha = text_digest(request)
    codes = ["reports_not_facts", *[f"eligibility_{c}" for c in plan["applied"]], "source_bias"]
    if any(c in plan["applied"] for c in ("calendar", "month", "day")):
        codes.append("day_placeholders")
    limitations = [dict(a.limitations[c]) for c in dict.fromkeys(codes) if c in a.limitations]
    limitations = [{"code": f"analysis_{i}", "text": t} for i, t in enumerate(notes or [])] + limitations
    filters = [f.as_dict() for f in q.filters]
    text_params = ", ".join(f"{k}={v}" for k, v in params.items() if k != "filters" and v is not None)
    readable_filters = a._readable(q, plan, ["report_count"])["filtros"]
    texto = f"Análisis {ANALYSES[kind]['label'].lower()} ({text_params}), filtros: {'; '.join(readable_filters)}"
    return {
        "result_type": "composed", "certified_query_id": None, "certification": None,
        "view": view, "view_label": VIEWS[view]["label"], "title": title or ANALYSES[kind]["label"],
        "rows": rows, "total": None, "truncated": False, "row_count": len(rows), "matched_source_rows": matched, "empty": not rows,
        "eligibility_applied": [{"code": c, "label": a.eligibility[c]["label"], "flag": a.eligibility[c]["flag"],
                                 "implied": c not in plan["applied"]} for c in plan["closure"]],
        "exclusions": a._exclusions(con, q, plan), "external_evidence_reports": None,
        "readable_query": {"dataset": a.datasets[q.dataset]["label"], "filtros": readable_filters, "agrupado_por": group_by,
                           "metricas": [metric_labels.get(m, m) for m in metrics],
                           "elegibilidad": [a.eligibility[c]["label"] for c in plan["applied"]] or ["ninguna"],
                           "orden": "predeterminado", "limite": len(rows), "texto": texto},
        "query": {"dataset": q.dataset, "filters": filters, "group_by": group_by, "metrics": metrics, "columns": [],
                  "eligibility": sorted(plan["applied"]), "view": view, "title": title, "order_by": None, "descending": True,
                  "limit": len(rows), "rollup": False, "analysis": kind, "params": params},
        "provenance": {"gold_load_id": a.load_id, "gold_sha256": a.cache["gold_sha256"], "silver_sha256": a.meta["manifest"]["silver"]["sha256"],
                       "bronze_sha256": a.meta["manifest"]["bronze"]["sha256"], "definitions_sha256": a.meta["manifest"]["definitions_sha256"],
                       "query_engine_sha256": a.engine_sha, "serving_sha256": a.cache["sha256"], "dataset": q.dataset, "query_sha256": request_sha},
        "snapshot": {"gold_built_at": a.meta["manifest"]["built_at"], "silver_reference_date": a.meta["manifest"]["silver"].get("reference_date"),
                     "label": f"Datos de la carga Gold {a.load_id[:12]} construida el {a.meta['manifest']['built_at'][:10]}"},
        "limitations": limitations, "metric_labels": metric_labels, "analysis": {"kind": kind, **(meta or {})},
    }


def year_filters(column: str, low, high) -> list:
    out = []
    if low is not None:
        out.append({"column": column, "op": "gte", "value": low})
    if high is not None:
        out.append({"column": column, "op": "lte", "value": high})
    return out


def label_of(a: Analytics, column: str, value) -> str:
    if value == OTHER:
        return "Otras"
    return (a.labels.get(column) or {}).get(str(value), "sin dato" if value is None else str(value))


# -- analyses ----------------------------------------------------------------
def period_change(a, con, p, title):
    period, cat = p["period"], p["category"]
    q, plan = plan_for(a, [*p["filters"], {"column": period, "op": "in", "value": [p["from"], p["to"]]}], [period, cat])
    rows = a._execute(con, f'SELECT "{cat}" AS c, SUM("{period}" = ?) AS a, SUM("{period}" = ?) AS b FROM {R}'
                      + where_sql(plan) + " GROUP BY 1", [p["from"], p["to"], *plan["params"]])
    items = [{cat: r["c"], "count_from": r["a"], "count_to": r["b"], "change": r["b"] - r["a"]} for r in rows]
    items.sort(key=lambda r: -abs(r["change"]))
    if len(items) > p["top"]:
        rest = items[p["top"] - 1:]
        items = items[:p["top"] - 1] + [{cat: OTHER, "count_from": sum(r["count_from"] for r in rest),
                                          "count_to": sum(r["count_to"] for r in rest), "change": sum(r["change"] for r in rest)}]
    total_from, total_to = sum(r["count_from"] for r in items), sum(r["count_to"] for r in items)
    unit = "década de " if period == "decade" else ""
    return dict(view="waterfall", rows=items, q=q, plan=plan, group_by=[cat], metrics=["change", "count_from", "count_to"],
                metric_labels={"change": "Cambio de informes", "count_from": f"Informes {unit}{p['from']}", "count_to": f"Informes {unit}{p['to']}"},
                matched=total_from + total_to, meta={"total_from": total_from, "total_to": total_to, "total_change": total_to - total_from,
                                                     "from": p["from"], "to": p["to"], "period": period},
                notes=["Las barras suman el cambio total de informes entre los dos períodos; no es el cambio de un fenómeno."])


def dominant_share(a, con, p, title):
    g, w = p["group"], p["within"]
    q, plan = plan_for(a, p["filters"], [g, w])
    rows = a._execute(con, f'SELECT "{g}" AS g, "{w}" AS w, COUNT(*) AS n FROM {R}' + where_sql(plan, [f'"{g}" IS NOT NULL', f'"{w}" IS NOT NULL'])
                      + " GROUP BY 1, 2", plan["params"])
    groups = defaultdict(dict)
    for r in rows:
        groups[r["g"]][r["w"]] = r["n"]
    items = []
    for key, counts in groups.items():
        base = sum(counts.values())
        top = max(counts.values())
        leaders = sorted(k for k, n in counts.items() if n == top)
        items.append({g: key, "dominant": leaders[0], "dominant_label": label_of(a, w, leaders[0]), "ties": len(leaders) - 1,
                      "dominant_share_pct": round(100 * top / base, 2), "base_reports": base})
    items.sort(key=lambda r: -r["dominant_share_pct"])
    return dict(view="bars", rows=items, q=q, plan=plan, group_by=[g], metrics=["dominant_share_pct"],
                metric_labels={"dominant_share_pct": f"% de la {a.dimensions[w]['label'].lower()} dominante"},
                matched=sum(r["base_reports"] for r in items), notes=[f"Base: informes con {a.dimensions[g]['label'].lower()} y {a.dimensions[w]['label'].lower()} consignados."])


def _daily_grid(a, con, p, extra_columns=()):
    filters = [*p["filters"], *year_filters("event_year", p["from_year"], p["to_year"])]
    q, plan = plan_for(a, filters, ["event_date", *extra_columns])
    counts = {r[0]: r[1] for r in a._execute(con, f"SELECT event_date, COUNT(*) FROM {R}" + where_sql(plan) + " GROUP BY 1", plan["params"])}
    first, last = date(p["from_year"], 1, 1), date(p["to_year"], 12, 31)
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    return q, plan, days, [counts.get(d.isoformat(), 0) for d in days]


def daily_anomalies(a, con, p, title):
    q, plan, days, values = _daily_grid(a, con, p)
    half = p["window_days"] // 2
    rows = []
    for i, d in enumerate(days):
        window = values[max(0, i - half):i] + values[i + 1:i + 1 + half]
        if len(window) < 2 * half:
            continue  # margin of observation: the window must be complete
        ordered = sorted(window)
        median = (ordered[len(ordered) // 2 - 1] + ordered[len(ordered) // 2]) / 2
        rows.append({"event_date": d.isoformat(), "report_count": values[i], "local_median": median,
                     "excess": round(values[i] - median, 2)})
    top = sorted(rows, key=lambda r: -r["excess"])[:p["top"]]
    return dict(view="timeseries", rows=rows, q=q, plan=plan, group_by=["event_date"], metrics=["report_count", "local_median", "excess"],
                metric_labels={"report_count": "Informes del día", "local_median": f"Mediana de los {p['window_days']} días vecinos",
                               "excess": "Informes por encima de la mediana local"},
                matched=sum(values), meta={"highlights": top, "overlay": {"report_count": "local_median"}},
                notes=["Referencia: mediana de los días anteriores y posteriores, sin el propio día; los días sin informes cuentan como cero.",
                       "Un pico de informes no prueba un evento: puede reflejar una campaña de reporte o una fecha marcadora."])


def yoy_change(a, con, p, title):
    filters = [*p["filters"], *year_filters("event_year", p["from_year"] - 1, p["to_year"])]
    q, plan = plan_for(a, filters, ["year_month"])
    counts = {r[0]: r[1] for r in a._execute(con, f"SELECT year_month, COUNT(*) FROM {R}" + where_sql(plan) + " GROUP BY 1", plan["params"])}
    rows = []
    for year in range(p["from_year"], p["to_year"] + 1):
        for month in range(1, 13):
            key, prev = f"{year}-{month:02d}", f"{year - 1}-{month:02d}"
            n, b = counts.get(key, 0), counts.get(prev, 0)
            rows.append({"year_month": key, "report_count": n, "previous_year_reports": b,
                         "yoy_pct": round(100 * (n - b) / b, 2) if b else None})
    return dict(view="timeseries", rows=rows, q=q, plan=plan, group_by=["year_month"], metrics=["yoy_pct"],
                metric_labels={"yoy_pct": "Cambio respecto del mismo mes del año anterior (%)", "report_count": "Informes",
                               "previous_year_reports": "Informes del año anterior"},
                matched=sum(r["report_count"] for r in rows),
                notes=["Sin cambio calculado cuando el mismo mes del año anterior no tiene informes."])


def daily_distribution_by_month(a, con, p, title):
    q, plan, days, values = _daily_grid(a, con, p)
    by_month = defaultdict(list)
    for d, n in zip(days, values):
        by_month[d.month].append(n)
    rows = []
    for month in range(1, 13):
        found = sorted(by_month[month])
        box = {"n": len(found), **{f"p{int(x * 100):02d}": Analytics._quantile(found, x) for x in QUANTILES},
               "min": found[0] if found else None, "max": found[-1] if found else None,
               "mean": round(sum(found) / len(found), 3) if found else None}
        rows.append({"event_month": month, "median_daily_reports": box["p50"], "mean_daily_reports": box["mean"], "box": box})
    return dict(view="boxplot", rows=rows, q=q, plan=plan, group_by=["event_month"], metrics=["median_daily_reports"],
                metric_labels={"median_daily_reports": "Mediana de informes por día", "mean_daily_reports": "Media de informes por día"},
                matched=sum(values), notes=["Cada caja reparte los días del mes, incluidos los días sin informes, entre los años del período."])


def hour_month_deviation(a, con, p, title):
    q, plan = plan_for(a, p["filters"], ["event_month", "event_hour"])
    rows = a._execute(con, f"SELECT event_month, event_hour, COUNT(*) FROM {R}" + where_sql(plan) + " GROUP BY 1, 2", plan["params"])
    by_month, by_hour = Counter(), Counter()
    for m, h, n in rows:
        by_month[m] += n
        by_hour[h] += n
    total = sum(by_hour.values())
    items = []
    for month in range(1, 13):
        for hour in range(24):
            n = next((r[2] for r in rows if r[0] == month and r[1] == hour), 0)
            share = 100 * n / by_month[month] if by_month[month] else 0
            items.append({"event_month": month, "event_hour": hour, "report_count": n,
                          "deviation_pp": round(share - 100 * by_hour[hour] / total, 3) if total else 0})
    return dict(view="matrix", rows=items, q=q, plan=plan, group_by=["event_month", "event_hour"], metrics=["deviation_pp"],
                metric_labels={"deviation_pp": "Puntos de diferencia con el peso global de la hora"}, matched=total,
                meta={"scale": "diverging"},
                notes=["Cada celda resta la proporción de esa hora en todo el archivo de su proporción dentro del mes, en puntos porcentuales."])


def rank_over_time(a, con, p, title):
    dim = p["dimension"]
    q, plan = plan_for(a, [*p["filters"], *year_filters("event_year", p["from_year"] if not p["cumulative"] else None, p["to_year"])],
                       ["event_year", dim])
    rows = a._execute(con, f'SELECT event_year, "{dim}", COUNT(*) FROM {R}' + where_sql(plan, [f'"{dim}" IS NOT NULL'])
                      + " GROUP BY 1, 2", plan["params"])
    yearly = defaultdict(Counter)
    before = Counter()
    for year, key, n in rows:
        if year < p["from_year"]:
            before[key] += n
        else:
            yearly[year][key] += n
    running = Counter(before)
    ranks = {}
    for year in range(p["from_year"], p["to_year"] + 1):
        if p["cumulative"]:
            running.update(yearly[year])
            score = running
        else:
            score = yearly[year]
        ordered = sorted((k for k, v in score.items() if v), key=lambda k: (-score[k], str(k)))
        ranks[year] = {k: (i + 1, score[k]) for i, k in enumerate(ordered)}
    ever = {k for r in ranks.values() for k, (rank, _) in r.items() if rank <= p["top"]}
    items = [{"event_year": year, dim: key, "rank": ranks[year][key][0] if key in ranks[year] and ranks[year][key][0] <= p["top"] else None,
              "reports": ranks[year].get(key, (None, 0))[1]} for year in ranks for key in sorted(ever, key=str)]
    first = {k for k, (r, _) in ranks[p["from_year"]].items() if r <= p["top"]} if p["from_year"] in ranks else set()
    last = {k for k, (r, _) in ranks[p["to_year"]].items() if r <= p["top"]} if p["to_year"] in ranks else set()
    return dict(view="bump", rows=items, q=q, plan=plan, group_by=["event_year", dim], metrics=["rank"],
                metric_labels={"rank": "Posición", "reports": "Informes acumulados" if p["cumulative"] else "Informes del año"},
                matched=sum(n for _, _, n in rows),
                meta={"entered": sorted(map(str, last - first)), "left": sorted(map(str, first - last)), "top": p["top"],
                      "entered_labels": [label_of(a, dim, k) for k in sorted(last - first, key=str)],
                      "left_labels": [label_of(a, dim, k) for k in sorted(first - last, key=str)]},
                notes=["Desempate estable por código. " + ("Acumulado desde el primer informe con año." if p["cumulative"] else "Conteo de cada año.")])


def concentration(a, con, p, title):
    lat, lng = f'cell{p["resolution"]}_lat', f'cell{p["resolution"]}_lng'
    q, plan = plan_for(a, p["filters"], [lat, lng])
    counts = sorted((r[0] for r in a._execute(con, f"SELECT COUNT(*) FROM {R}" + where_sql(plan) + f" GROUP BY {lat}, {lng}", plan["params"])),
                    reverse=True)
    total, cells = sum(counts), len(counts)
    rows, acc = [{"cell_share_pct": 0.0, "report_share_pct": 0.0}], 0
    marks = {max(1, round(cells * i / 200)) for i in range(1, 201)} if cells else set()
    for i, n in enumerate(counts, 1):
        acc += n
        if i in marks:
            rows.append({"cell_share_pct": round(100 * i / cells, 3), "report_share_pct": round(100 * acc / total, 3)})
    top = math.ceil(cells * 0.01) if cells else 0
    top_share = round(100 * sum(counts[:top]) / total, 2) if total else None
    return dict(view="curve", rows=rows, q=q, plan=plan, group_by=[], metrics=["report_share_pct"],
                metric_labels={"report_share_pct": "% acumulado de informes", "cell_share_pct": f"% de celdas de {p['resolution']}° ocupadas"},
                matched=total, meta={"cells": cells, "top1pct_cells": top, "top1pct_share": top_share, "resolution": p["resolution"]},
                notes=["Celdas ocupadas, de la más concurrida a la menos; el 1 % se redondea hacia arriba. Cuenta informes, no población."])


def cell_change(a, con, p, title):
    lat, lng, period = f'cell{p["resolution"]}_lat', f'cell{p["resolution"]}_lng', p["period"]
    q, plan = plan_for(a, [*p["filters"], {"column": period, "op": "in", "value": [p["from"], p["to"]]}], [lat, lng, period])
    rows = a._execute(con, f'SELECT {lat}, {lng}, SUM("{period}" = ?), SUM("{period}" = ?) FROM {R}' + where_sql(plan)
                      + f" GROUP BY 1, 2", [p["from"], p["to"], *plan["params"]])
    items = [{lat: r[0], lng: r[1], "count_from": r[2], "count_to": r[3], "change": r[3] - r[2]} for r in rows]
    items.sort(key=lambda r: -abs(r["change"]))
    return dict(view="density", rows=items, q=q, plan=plan, group_by=[lat, lng], metrics=["change"],
                metric_labels={"change": f"Cambio de informes ({p['from']} → {p['to']})", "count_from": f"Informes {p['from']}", "count_to": f"Informes {p['to']}"},
                matched=sum(r["count_from"] + r["count_to"] for r in items), meta={"scale": "diverging", "resolution": p["resolution"]},
                notes=["Incluye las celdas con informes en cualquiera de los dos períodos; una celda sin informes en uno cuenta como cero."],
                label_columns=[])


def first_appearance(a, con, p, title):
    lat, lng = f'cell{p["resolution"]}_lat', f'cell{p["resolution"]}_lng'
    q, plan = plan_for(a, [*p["filters"], *year_filters("event_year", p["from_year"], None)], [lat, lng, "event_year"])
    rows = a._execute(con, f"SELECT {lat}, {lng}, MIN(event_year), COUNT(*) FROM {R}" + where_sql(plan) + " GROUP BY 1, 2", plan["params"])
    items = [{lat: r[0], lng: r[1], "first_year": r[2], "report_count": r[3]} for r in rows]
    per_year = Counter(r["first_year"] for r in items)
    cumulative, acc = [], 0
    for year in sorted(per_year):
        acc += per_year[year]
        cumulative.append({"event_year": year, "new_cells": per_year[year], "cells": acc})
    return dict(view="density", rows=items, q=q, plan=plan, group_by=[lat, lng], metrics=["first_year"],
                metric_labels={"first_year": "Primer año con informes", "report_count": "Informes"},
                matched=sum(r["report_count"] for r in items), meta={"scale": "years", "resolution": p["resolution"], "cumulative": cumulative},
                notes=["La primera aparición depende de la cobertura de las fuentes, no de cuándo empezó un fenómeno."], label_columns=[])


def _haversine(lat1, lng1, lat2, lng2):
    rad = math.radians
    dlat, dlng = rad(lat2 - lat1), rad(lng2 - lng1)
    h = math.sin(dlat / 2) ** 2 + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(dlng / 2) ** 2
    return 2 * 6371 * math.asin(min(1, math.sqrt(h)))


def clusters(a, con, p, title):
    filters = [*p["filters"], *year_filters("event_year", p["from_year"], p["to_year"])]
    q, plan = plan_for(a, filters, ["lat", "lng", "event_date", "cell1_lat"], eligibility=["map", "day"])
    if p["method"] == "week_cell":
        week = "date(event_date, '-' || ((CAST(strftime('%w', event_date) AS INTEGER) + 6) % 7) || ' days')"
        rows = a._execute(con, f"""SELECT cell1_lat, cell1_lng, {week} AS week, COUNT(*) AS n, AVG(lat), AVG(lng), MIN(event_date), MAX(event_date),
                MIN(report_id) FROM {R}""" + where_sql(plan) + f" GROUP BY 1, 2, 3 HAVING COUNT(*) >= ? ORDER BY n DESC LIMIT ?",
                               [*plan["params"], p["min_reports"], p["top"]])
        items = [{"cluster_id": i + 1, "lat": round(r[4], 4), "lng": round(r[5], 4), "report_count": r[3], "start_date": r[6], "end_date": r[7],
                  "week_start": r[2], "cell": f"{r[0]}, {r[1]}", "report_id": r[8]} for i, r in enumerate(rows)]
        population = a._execute(con, f"SELECT COUNT(*) FROM {R}" + where_sql(plan), plan["params"])[0][0]
        notes = [f"Celdas de 1° con al menos {p['min_reports']} informes en una semana que empieza en lunes, según la fecha consignada."]
    else:
        points = a._execute(con, f"SELECT report_id, lat, lng, julianday(event_date), shape_code FROM {R}" + where_sql(plan), plan["params"])
        population = len(points)
        if population > CLUSTER_MAX_POINTS:
            raise QueryError("budget", f"{population} informes con mapa y día: el agrupamiento por radio admite hasta {CLUSTER_MAX_POINTS}. "
                                       "Acota el período (from_year/to_year) o filtra un país.")
        radius, days = p["radius_km"], p["days"]
        size = radius / 111.0
        buckets = defaultdict(list)
        for i, (_, lat, lng, day, _) in enumerate(points):
            buckets[(int(lat // size), int(lng // size), int(day // days))].append(i)
        parent = list(range(len(points)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for (bx, by, bt), members in buckets.items():
            near = [j for dx in (-1, 0, 1) for dy in (-2, -1, 0, 1, 2) for dt in (-1, 0, 1)
                    for j in buckets.get((bx + dx, by + dy, bt + dt), ())]
            for i in members:
                _, lat, lng, day, _ = points[i]
                for j in near:
                    if j <= i or find(i) == find(j):
                        continue
                    _, lat2, lng2, day2, _ = points[j]
                    if abs(day - day2) <= days and _haversine(lat, lng, lat2, lng2) <= radius:
                        parent[find(i)] = find(j)
        groups = defaultdict(list)
        for i in range(len(points)):
            groups[find(i)].append(i)
        found = sorted((m for m in groups.values() if len(m) >= p["min_reports"]), key=len, reverse=True)[:p["top"]]
        items = []
        for k, members in enumerate(found, 1):
            lat = sum(points[i][1] for i in members) / len(members)
            lng = sum(points[i][2] for i in members) / len(members)
            day0, day1 = min(points[i][3] for i in members), max(points[i][3] for i in members)
            shape = Counter(points[i][4] for i in members if points[i][4]).most_common(1)
            items.append({"cluster_id": k, "lat": round(lat, 4), "lng": round(lng, 4), "report_count": len(members),
                          "start_date": _jd(day0), "end_date": _jd(day1), "span_days": int(round(day1 - day0)),
                          "radius_km": round(max(_haversine(lat, lng, points[i][1], points[i][2]) for i in members), 1),
                          "top_shape": shape[0][0] if shape else None, "report_id": min(points[i][0] for i in members),
                          "report_ids": sorted(points[i][0] for i in members)[:20]})
        notes = [f"Componentes de informes unidos por cadenas de vecinos a menos de {radius:g} km y {days} días; mínimo {p['min_reports']} informes. "
                 "Exploratorio: muchas coordenadas son centros de ciudad y una agrupación no prueba un evento común."]
    return dict(view="clusters", rows=items, q=q, plan=plan, group_by=[], metrics=["report_count"],
                metric_labels={"report_count": "Informes del grupo"}, matched=population,
                meta={"method": p["method"], "clusters": len(items), "clustered_reports": sum(r["report_count"] for r in items)},
                notes=notes, label_columns=["top_shape"] if p["method"] == "radius" else [])


def _jd(value):
    return (date(2000, 1, 1) + timedelta(days=int(round(value - 2451544.5)))).isoformat()


def facility_links(a, con, p, title):
    res = p["resolution"]
    lat, lng = f"cell{res}_lat", f"cell{res}_lng"
    q, plan = plan_for(a, [*p["filters"], {"column": "nuclear_distance_km", "op": "lte", "value": p["max_km"]}],
                       [lat, lng, "nearest_facility_key"], eligibility=["nuclear_proximity", "map"])
    rows = a._execute(con, f"""SELECT r.{lat}, r.{lng}, r.nearest_facility_key, COUNT(*) AS n, AVG(r.nuclear_distance_km),
            f.name, f.latitude, f.longitude FROM {R} r JOIN dim_nuclear_facility f ON f.nearest_facility_key = r.nearest_facility_key"""
                           + where_sql({"where": [w.replace('"', 'r."', 1) if w.startswith('"') else w for w in plan["where"]]})
                           + " GROUP BY 1, 2, 3 ORDER BY n DESC LIMIT ?", [*plan["params"], p["top"]])
    items = [{"cell_lat": r[0] + res / 2, "cell_lng": r[1] + res / 2, "nearest_facility_key": r[2], "report_count": r[3],
              "avg_distance_km": round(r[4], 1), "facility_name": r[5], "facility_lat": r[6], "facility_lng": r[7]} for r in rows]
    matched = a._execute(con, f"SELECT COUNT(*) FROM {R}" + where_sql(plan), plan["params"])[0][0]
    return dict(view="links", rows=items, q=q, plan=plan, group_by=["nearest_facility_key"], metrics=["report_count"],
                metric_labels={"report_count": "Informes", "avg_distance_km": "Distancia media (km)"}, matched=matched,
                notes=["Cada línea une el centro de una celda con la instalación del catálogo más cercana a sus informes. Cercanía no implica relación."],
                label_columns=[])


def funnel(a, con, p, title):
    by = p["by"]
    q, plan = plan_for(a, p["filters"], [by] if by else [])
    sums = ", ".join(f"SUM({cond})" for _, _, cond in FUNNEL_STAGES)
    group = f'"{by}"' if by else "NULL"
    rows = a._execute(con, f"SELECT {group}, {sums} FROM {R}" + where_sql(plan) + " GROUP BY 1 ORDER BY 2 DESC", plan["params"])
    items = []
    for r in rows:
        for i, (code, label, _) in enumerate(FUNNEL_STAGES):
            items.append({**({by: r[0]} if by else {}), "stage": code, "stage_label": label, "report_count": r[i + 1],
                          "pct_of_all": round(100 * r[i + 1] / r[1], 2) if r[1] else None})
    return dict(view="funnel", rows=items, q=q, plan=plan, group_by=[*([by] if by else []), "stage"], metrics=["report_count", "pct_of_all"],
                metric_labels={"report_count": "Informes", "pct_of_all": "% del total"}, matched=sum(r[1] for r in rows),
                notes=["Cada etapa conserva los informes de la anterior que además tienen esa precisión."], label_columns=[by] if by else [])


def missing_combinations(a, con, p, title):
    q, plan = plan_for(a, p["filters"], [])
    flags = [f for _, _, f in MISSING_FIELDS]
    rows = a._execute(con, f"SELECT {', '.join(flags)}, COUNT(*) FROM {R}" + where_sql(plan) + f" GROUP BY {', '.join(flags)}", plan["params"])
    total = sum(r[-1] for r in rows)
    items = []
    for r in sorted(rows, key=lambda r: -r[-1])[:p["top"]]:
        missing = [label for (code, label, _), v in zip(MISSING_FIELDS, r[:-1]) if not v]
        present = [label for (code, label, _), v in zip(MISSING_FIELDS, r[:-1]) if v]
        items.append({"combination": " + ".join(missing) if missing else "Nada falta", "missing": missing, "present": present,
                      "missing_count": len(missing), "report_count": r[-1], "pct": round(100 * r[-1] / total, 2) if total else None})
    fields = [{"field": label, "missing_reports": sum(r[-1] for r in rows if not r[i])} for i, (_, label, _) in enumerate(MISSING_FIELDS)]
    return dict(view="upset", rows=items, q=q, plan=plan, group_by=["combination"], metrics=["report_count"],
                metric_labels={"report_count": "Informes con exactamente esta combinación", "pct": "% de los informes"}, matched=total,
                meta={"fields": fields, "field_labels": [l for _, l, _ in MISSING_FIELDS]},
                notes=["Intersecciones exclusivas: cada informe cuenta en una sola combinación. Forma desconocida, duración cero y cero testigos cuentan como faltantes."],
                label_columns=[])


def compare_reports(a, con, p, title):
    ids = p["report_ids"]
    q, plan = plan_for(a, [{"column": "report_id", "op": "in", "value": ids}], [])
    columns = [c for c in COMPARE_FIELDS if c in a.datasets[R]["columns"]]
    found = {r["report_id"]: dict(r) for r in a._execute(con, f"SELECT report_id, {', '.join(columns)} FROM {R} WHERE report_id IN (?, ?)", ids)}
    missing = [i for i in ids if i not in found]
    if missing:
        raise QueryError("value", f"No existen los informes {missing} en Gold")
    model = {r["report_id"]: dict(r) for r in a._execute(con, f"SELECT report_id, {', '.join(COMPARE_MODEL)} FROM report_model_output WHERE report_id IN (?, ?)", ids)}
    pair = a._execute(con, """SELECT match_method, similarity_score, decision FROM candidate_pair WHERE (report_id_a = ? AND report_id_b = ?)
                              OR (report_id_a = ? AND report_id_b = ?)""", [ids[0], ids[1], ids[1], ids[0]])
    rows = []
    for column in columns + COMPARE_MODEL:
        source = model if column in COMPARE_MODEL else found
        va, vb = source.get(ids[0], {}).get(column), source.get(ids[1], {}).get(column)
        label = COMPARE_LABELS.get(column) or (a.dimensions.get(column) or {}).get("label") or column
        rows.append({"field": column, "field_label": label, "a": va, "b": vb, "a_label": label_of(a, column, va) if a.labels.get(column) else va,
                     "b_label": label_of(a, column, vb) if a.labels.get(column) else vb,
                     "same": None if va is None or vb is None else va == vb, "model_output": column in COMPARE_MODEL})
    same = sum(1 for r in rows if r["same"])
    return dict(view="compare", rows=rows, q=q, plan=plan, group_by=[], metrics=[], metric_labels={}, matched=2,
                meta={"report_ids": ids, "same_fields": same, "compared_fields": sum(1 for r in rows if r["same"] is not None),
                      "candidate_pair": dict(pair[0]) if pair else None},
                notes=["Coincidir en campos no prueba que sean el mismo evento; las puntuaciones de modelo son salidas heredadas."],
                label_columns=[])


def _kmeans(points, k, seed, iterations=60):
    rng = random.Random(seed)
    centers = [points[rng.randrange(len(points))]]
    while len(centers) < k:  # k-means++
        dist = [min((x - cx) ** 2 + (y - cy) ** 2 for cx, cy in centers) for x, y in points]
        total = sum(dist)
        pick, acc = rng.random() * total, 0.0
        for i, d in enumerate(dist):
            acc += d
            if acc >= pick:
                centers.append(points[i])
                break
    labels = [0] * len(points)
    for _ in range(iterations):
        moved = False
        for i, (x, y) in enumerate(points):
            best = min(range(k), key=lambda c: (x - centers[c][0]) ** 2 + (y - centers[c][1]) ** 2)
            if best != labels[i]:
                labels[i], moved = best, True
        sums = [[0.0, 0.0, 0] for _ in range(k)]
        for (x, y), c in zip(points, labels):
            sums[c][0] += x; sums[c][1] += y; sums[c][2] += 1
        centers = [(s[0] / s[2], s[1] / s[2]) if s[2] else centers[c] for c, s in enumerate(sums)]
        if not moved:
            break
    order = sorted(range(k), key=lambda c: (centers[c][0], centers[c][1]))  # stable names: by duration
    rename = {old: new for new, old in enumerate(order)}
    return [rename[c] for c in labels], [centers[c] for c in order]


def kmeans_profiles(a, con, p, title):
    q, plan = plan_for(a, p["filters"], [])
    raw = a._execute(con, f"SELECT duration_seconds, num_witnesses FROM {R}" + where_sql(plan, ["duration_seconds > 0", "num_witnesses > 0"]), plan["params"])
    if len(raw) < p["k"] * 10:
        raise QueryError("value", f"Solo {len(raw)} informes con duración y testigos positivos: no alcanza para {p['k']} perfiles")
    logs = [(math.log10(d / 60), math.log10(w)) for d, w in raw]
    mean = [sum(v[i] for v in logs) / len(logs) for i in (0, 1)]
    sd = [math.sqrt(sum((v[i] - mean[i]) ** 2 for v in logs) / len(logs)) or 1 for i in (0, 1)]
    points = [((x - mean[0]) / sd[0], (y - mean[1]) / sd[1]) for x, y in logs]
    labels, centers = _kmeans(points, p["k"], p["seed"])
    agreements = []
    for other in (p["seed"] + 1, p["seed"] + 2):
        alt, _ = _kmeans(points, p["k"], other)
        best = max(sum(1 for x, y in zip(labels, alt) if perm[y] == x) for perm in itertools.permutations(range(p["k"])))
        agreements.append(round(100 * best / len(points), 1))
    pair = SCATTER_PAIRS["duration_witnesses"]
    xe, ye = pair["x_edges"], pair["y_edges"]
    def bin_of(v, edges):
        for i in range(len(edges) - 1):
            if v < edges[i + 1]:
                return i if v >= edges[0] else -1
        return len(edges) - 1
    cells = defaultdict(Counter)
    for (d, w), c in zip(raw, labels):
        cells[(bin_of(d / 60, xe), bin_of(w, ye))][c] += 1
    edge = lambda e, i: e[i] if 0 <= i < len(e) else None
    rows = [{"x_bin": bx, "y_bin": by, "x_from": edge(xe, bx), "x_to": edge(xe, bx + 1), "y_from": edge(ye, by), "y_to": edge(ye, by + 1),
             "report_count": sum(cnt.values()), "cluster": cnt.most_common(1)[0][0] + 1, "cluster_counts": {str(k + 1): v for k, v in sorted(cnt.items())}}
            for (bx, by), cnt in sorted(cells.items())]
    sizes = Counter(labels)
    profiles = []
    for c, (cx, cy) in enumerate(centers):
        minutes, witnesses = 10 ** (cx * sd[0] + mean[0]), 10 ** (cy * sd[1] + mean[1])
        profiles.append({"cluster": c + 1, "reports": sizes[c], "center_duration_min": round(minutes, 2), "center_witnesses": round(witnesses, 2)})
    return dict(view="scatter", rows=rows, q=q, plan=plan, group_by=[], metrics=["report_count"],
                metric_labels={"report_count": "Informes"}, matched=len(raw),
                meta={"profiles": profiles, "stability_pct": agreements, "k": p["k"], "seed": p["seed"],
                      "x": {"measure": "duration", "label": "Duración declarada", "unit": "min", "edges": xe},
                      "y": {"measure": "witnesses", "label": "Testigos consignados", "unit": "testigos", "edges": ye}},
                notes=["K-means sobre el logaritmo estandarizado de duración y testigos (ambos positivos). Perfiles exploratorios, no tipos de fenómeno; "
                       "la estabilidad compara la asignación con otras dos semillas."])


def retention(a, con, p, title):
    lat, lng = f'cell{p["resolution"]}_lat', f'cell{p["resolution"]}_lng'
    q, plan = plan_for(a, [*p["filters"], *year_filters("event_year", p["from_decade"], None)], [lat, lng, "decade", "source_code"])
    cells = defaultdict(set)
    for source, decade, la, ln in a._execute(con, f"SELECT DISTINCT source_code, decade, {lat}, {lng} FROM {R}" + where_sql(plan), plan["params"]):
        cells[(source, decade)].add((la, ln))
    items = []
    for (source, decade), occupied in sorted(cells.items()):
        following = cells.get((source, decade + 10))
        if following is None or decade + 10 > date.today().year // 10 * 10 - 10:
            continue
        items.append({"decade": decade, "source_code": source, "retention_pct": round(100 * len(occupied & following) / len(occupied), 2),
                      "cells": len(occupied)})
    return dict(view="timeseries", rows=items, q=q, plan=plan, group_by=["decade", "source_code"], metrics=["retention_pct"],
                metric_labels={"retention_pct": "% de celdas observadas otra vez la década siguiente", "cells": "Celdas ocupadas"},
                matched=sum(r["cells"] for r in items), notes=["Solo pares de décadas completas con informes de la fuente en ambas."])


def source_overlap(a, con, p, title):
    q, plan = plan_for(a, p["filters"], ["country_iso2", "source_code"])
    sets = defaultdict(set)
    for source, country in a._execute(con, f"SELECT DISTINCT source_code, country_iso2 FROM {R}" + where_sql(plan), plan["params"]):
        sets[source].add(country)
    items = []
    for x, y in itertools.product(sorted(sets), repeat=2):
        union = sets[x] | sets[y]
        items.append({"source_code_a": x, "source_code_b": y, "jaccard_pct": round(100 * len(sets[x] & sets[y]) / len(union), 2) if union else None,
                      "shared_countries": len(sets[x] & sets[y])})
    return dict(view="matrix", rows=items, q=q, plan=plan, group_by=["source_code_a", "source_code_b"], metrics=["jaccard_pct"],
                metric_labels={"jaccard_pct": "% de países compartidos (Jaccard)", "shared_countries": "Países en ambas"},
                matched=sum(len(v) for v in sets.values()), meta={"scale": "percent"},
                notes=["Países en ambas fuentes sobre países en cualquiera de las dos; no pondera por informes."])


def diversity(a, con, p, title):
    cat, over = p["category"], p["over"]
    q, plan = plan_for(a, p["filters"], [cat, over])
    rows = a._execute(con, f'SELECT "{cat}", "{over}", COUNT(*) FROM {R}' + where_sql(plan, [f'"{cat}" IS NOT NULL', f'"{over}" IS NOT NULL'])
                      + " GROUP BY 1, 2", plan["params"])
    groups = defaultdict(list)
    for c, _, n in rows:
        groups[c].append(n)
    items = []
    for c, counts in groups.items():
        total = sum(counts)
        items.append({cat: c, "effective_count": round(1 / sum((n / total) ** 2 for n in counts), 2), "distinct_count": len(counts), "base_reports": total})
    items.sort(key=lambda r: -r["effective_count"])
    return dict(view="bars", rows=items, q=q, plan=plan, group_by=[cat], metrics=["effective_count"],
                metric_labels={"effective_count": f"Número efectivo de {a.dimensions[over]['label'].lower()}", "distinct_count": "Distintos"},
                matched=sum(r["base_reports"] for r in items),
                notes=["Número efectivo = 1 / suma de las participaciones al cuadrado (inverso de Herfindahl)."])


def obs_expected(a, con, p, title):
    rd, cd = p["rows"], p["columns"]
    q, plan = plan_for(a, p["filters"], [rd, cd])
    rows = a._execute(con, f'SELECT "{rd}", "{cd}", COUNT(*) FROM {R}' + where_sql(plan, [f'"{rd}" IS NOT NULL', f'"{cd}" IS NOT NULL'])
                      + " GROUP BY 1, 2", plan["params"])
    total = sum(n for *_, n in rows)
    by_r, by_c = Counter(), Counter()
    for r, c, n in rows:
        by_r[r] += n; by_c[c] += n
    items = []
    for r, c, n in rows:
        expected = by_r[r] * by_c[c] / total
        items.append({rd: r, cd: c, "observed": n, "expected": round(expected, 2),
                      "obs_expected_ratio": round(n / expected, 3) if n >= p["min_reports"] and expected else None})
    return dict(view="matrix", rows=items, q=q, plan=plan, group_by=[rd, cd], metrics=["obs_expected_ratio"],
                metric_labels={"obs_expected_ratio": "Observado / esperado", "observed": "Informes", "expected": "Esperado si fueran independientes"},
                matched=total, meta={"scale": "ratio"},
                notes=[f"Esperado = total de la fila × total de la columna / total. Celdas con menos de {p['min_reports']} informes sin cociente."])


HANDLERS = {"period_change": period_change, "dominant_share": dominant_share, "daily_anomalies": daily_anomalies,
            "yoy_change": yoy_change, "daily_distribution_by_month": daily_distribution_by_month,
            "hour_month_deviation": hour_month_deviation, "rank_over_time": rank_over_time, "concentration": concentration,
            "cell_change": cell_change, "first_appearance": first_appearance, "clusters": clusters,
            "facility_links": facility_links, "funnel": funnel, "missing_combinations": missing_combinations,
            "compare_reports": compare_reports, "kmeans_profiles": kmeans_profiles, "retention": retention,
            "source_overlap": source_overlap, "diversity": diversity, "obs_expected": obs_expected}


def analyze(a: Analytics, raw: dict, area=None) -> dict:
    kind, params, title = parse(a, raw)
    token = AREA.set(area or None)
    try:
        with closing(a.connect()) as con:
            out = HANDLERS[kind](a, con, params, title)
            result = envelope(a, con, kind, params, title, out["view"], out["rows"], out["q"], out["plan"], out["group_by"], out["metrics"],
                              out["metric_labels"], out["matched"], out.get("notes"), out.get("meta"), out.get("label_columns"))
    finally:
        AREA.reset(token)
    if area:
        result["query"]["area"] = area
    return result


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        out = analyze(Analytics(), json.loads(sys.argv[1]))
    except (QueryError, GoldUnavailable) as exc:
        print(json.dumps({"error": getattr(exc, "code", "unavailable"), "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
