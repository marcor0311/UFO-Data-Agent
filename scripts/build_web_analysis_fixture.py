#!/usr/bin/env python3
"""Genera apps/web/tests/fixtures/analysis-results.json para el e2e analysis-views.spec.ts.

Cada entrada es el resultado real del motor (query_gold o analyze) sobre la carga Gold
aprobada, publicado en el catálogo como una consulta certificada simulada para que la
web lo abra sin API. Se regenera cuando cambia el contrato de una vista o de un análisis.

Uso (desde la raíz):
  apps/api/.venv/bin/python scripts/build_web_analysis_fixture.py
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))
OUT = ROOT / "apps/web/tests/fixtures/analysis-results.json"
US = {"column": "country_iso2", "op": "eq", "value": "US"}
SHAPES = ["Triangle", "Disc", "Light", "Sphere", "Fireball", "Cigar"]

# (clave, petición, filas que se conservan). Una petición con "analysis" va a analyze.
CASES = [
    ("points_grouped", {"dataset": "fact_report", "view": "points", "filters": [US], "eligibility": ["map", "country"], "title": "Informes de Estados Unidos en el mapa"}, 400),
    ("points_cases", {"dataset": "fact_nuclear_encounter", "view": "points", "eligibility": ["map"], "title": "Encuentros en instalaciones nucleares"}, None),
    ("boxplot", {"dataset": "fact_report", "view": "boxplot", "group_by": ["shape_code"], "metrics": ["median_duration_min"], "filters": [{"column": "shape_code", "op": "in", "value": SHAPES}], "title": "Duración por forma"}, None),
    ("hist_witnesses", {"dataset": "fact_report", "view": "histogram", "metrics": ["report_count"], "measure": "witnesses", "group_by": ["source_code"], "title": "Testigos por fuente"}, None),
    ("hist_tail", {"dataset": "fact_report", "view": "histogram", "metrics": ["report_count"], "measure": "duration_tail", "title": "Duraciones de más de una hora"}, None),
    ("ecdf_distance", {"dataset": "fact_report", "view": "ecdf", "metrics": ["report_count"], "measure": "nuclear_distance", "group_by": ["source_code"], "eligibility": ["nuclear_proximity"], "title": "Distancia acumulada por fuente"}, None),
    ("scatter", {"dataset": "fact_report", "view": "scatter", "metrics": ["report_count"], "measure": "duration_witnesses", "title": "Duración y testigos"}, None),
    ("scatter_sentiment", {"dataset": "report_model_output", "view": "scatter", "metrics": ["report_count"], "measure": "vader_roberta", "title": "VADER frente a RoBERTa"}, None),
    ("kmeans", {"analysis": "kmeans_profiles", "params": {"k": 4}, "title": "Perfiles K-means"}, None),
    ("waterfall", {"analysis": "period_change", "params": {"period": "decade", "from": 2000, "to": 2010}, "title": "Cambio por fuente 2000s a 2010s"}, None),
    ("bump", {"analysis": "rank_over_time", "params": {"from_year": 1990, "to_year": 2022}, "title": "Top 10 de países"}, None),
    ("curve", {"analysis": "concentration", "params": {"resolution": 1}, "title": "Concentración en celdas"}, None),
    ("cell_change", {"analysis": "cell_change", "params": {"from": 2000, "to": 2010, "filters": [US]}, "title": "Cambio por celda en EE. UU."}, None),
    ("first_appearance", {"analysis": "first_appearance", "params": {"resolution": 5}, "title": "Primera aparición por celda"}, None),
    ("clusters", {"analysis": "clusters", "params": {"method": "week_cell", "top": 200}, "title": "Agrupaciones semanales"}, None),
    ("links", {"analysis": "facility_links", "params": {"top": 150}, "title": "Enlaces con instalaciones"}, None),
    ("funnel", {"analysis": "funnel", "params": {}, "title": "Embudo de cobertura"}, None),
    ("upset", {"analysis": "missing_combinations", "params": {"top": 15}, "title": "Datos que faltan juntos"}, None),
    ("compare", {"analysis": "compare_reports", "params": {"report_ids": [8137, 8138]}, "title": "Informes 8137 y 8138"}, None),
    ("yoy", {"analysis": "yoy_change", "params": {"from_year": 2000, "to_year": 2015}, "title": "Cambio interanual"}, None),
    ("anomalies", {"analysis": "daily_anomalies", "params": {"from_year": 1999, "to_year": 2000}, "title": "Picos diarios"}, None),
    ("deviation", {"analysis": "hour_month_deviation", "params": {}, "title": "Desvío de la hora por mes"}, None),
    ("obs_expected", {"analysis": "obs_expected", "params": {"filters": [{"column": "source_code", "op": "eq", "value": "UFOCAT"}, {"column": "shape_code", "op": "in", "value": SHAPES + ["Oval", "Star"]}]}, "title": "Forma y color observado frente a esperado"}, None),
    ("daily_box", {"analysis": "daily_distribution_by_month", "params": {}, "title": "Día típico por mes"}, None),
    ("regions", {"dataset": "fact_report", "view": "bars", "group_by": ["region_code"], "metrics": ["report_count"], "eligibility": ["country"], "filters": [US, {"column": "region_code", "op": "is_null", "value": False}], "order_by": "report_count", "limit": 12, "title": "Estados de EE. UU."}, None),
    ("pct_choropleth", {"dataset": "fact_report", "view": "choropleth", "group_by": ["country_iso2"], "metrics": ["within_10km_pct"], "eligibility": ["country"], "limit": 300, "title": "% a menos de 10 km por país"}, None),
    ("stacked_other", {"dataset": "fact_report", "view": "stacked", "group_by": ["decade", "shape_code"], "metrics": ["report_count"], "eligibility": ["calendar"], "filters": [{"column": "decade", "op": "gte", "value": 1940}], "limit": 500, "title": "Formas por década"}, None),
]


def main() -> None:
    from app.agent import routes
    from app.gold import get_analytics, gold_analysis

    analytics = get_analytics()
    catalog = routes.catalog(analytics)
    results = {}
    for key, request, keep in CASES:
        result = gold_analysis.analyze(analytics, request) if "analysis" in request else analytics.query(request)
        if keep:
            result["rows"] = result["rows"][:keep]
            result["row_count"] = len(result["rows"])
        result["title"] = result.get("title") or key
        results[f"CQ_{key.upper()}"] = result
    catalog["certified_queries"] = [
        {"id": cq, "title": r["title"], "description": "Vista nueva", "examples": [r["title"]],
         "recommended_views": [r["view"]], "limitation": "", "valid": True}
        for cq, r in results.items()
    ]
    OUT.write_text(json.dumps({"catalog": catalog, "results": results}, ensure_ascii=False, separators=(",", ":"), default=str))
    print(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size / 1e6:.2f} MB, {len(results)} resultados")


if __name__ == "__main__":
    main()
