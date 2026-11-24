#!/usr/bin/env python3
"""Typed, bounded and parameterized query tools over the Gold serving cache.

The agent never writes SQL. It sends a ``Query`` (strict contract, unknown
fields rejected); every identifier is validated against the catalogs, every
value is bound as a parameter, ratios are recomputed from their numerator and
denominator, eligibility is enforced in code and each result carries its
readable query, provenance, exclusions and limitations. Certified queries are
looked up first; any other query is marked as composed.

CLI:
  gold_query.py run '<json query>'      run a query and print the result
  gold_query.py certified <id>          run a certified query
  gold_query.py certify                 record expected results of the approved load in
                                        config/gold/certified_queries.json (explicit update)
  gold_query.py search '<pregunta>'     find certified queries for a question
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from functools import lru_cache
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
import sys

if __package__:
    from .gold_common import ROOT, digest, load_json, normalize, text_digest
    from .pipeline_context import write_text
    from . import releases
else:
    from gold_common import ROOT, digest, load_json, normalize, text_digest
    from pipeline_context import write_text
    import releases

CACHE_VERSION = 1
DENSITY_MAX_CELLS = 20000  # density may draw every cell of the selection (1° worldwide is about 14.000)
POINTS_MAX_REPORTS = 20000  # above this, the map groups reports by identical coordinates (as the globe does)
STACKED_MAX_CATEGORIES = 12  # second dimension of stacked: top categories, the rest as "Otras"
OPS = ("eq", "ne", "in", "gte", "lte", "is_null")
MAX_CALENDAR_YEARS = 40
TIME_DIMENSIONS = ("event_year", "decade", "year_month", "event_date")
# Datasets added with the Silver registers and logs: every generic chart can group them.
EXTRA_DATASETS = ["report_behavior_tag", "report_hoax_flag", "candidate_pair", "quality_issue_summary", "silver_change_summary",
                  "fact_crash_retrieval", "fact_nuclear_encounter", "facility_catalog"]
VIEWS = {
    "table": {"label": "Cifras y tabla", "datasets": "*",
              "description": "Cifras exactas: un total se muestra como tarjetas; un listado o agrupación, como tabla."},
    "bars": {"label": "Barras", "datasets": ["fact_report", "report_model_output", "fact_event", "agg_year", "agg_month",
                                              "agg_weekday_hour", "agg_country", "agg_shape", "agg_source", "agg_nuclear_band", "agg_coverage", *EXTRA_DATASETS],
             "description": "Compara categorías (fuentes, formas, países, bandas). Requiere métricas y una o dos dimensiones."},
    "timeseries": {"label": "Serie temporal", "datasets": ["fact_report", "report_model_output", "fact_event", "agg_year", "agg_month", "report_behavior_tag", "report_hoax_flag", "fact_crash_retrieval", "fact_nuclear_encounter"],
                   "description": "Evolución por año, década, mes o día; la primera dimensión debe ser temporal."},
    "points": {"label": "Mapa de puntos", "datasets": ["fact_report", "fact_crash_retrieval", "fact_nuclear_encounter"],
               "description": "Todos los informes con coordenadas aptas, sin límite de filas: un punto por informe hasta "
                              f"{POINTS_MAX_REPORTS} informes y, por encima, un punto por coordenada con su número de informes. Sin métricas."},
    "density": {"label": "Densidad espacial", "datasets": ["agg_spatial_cell", "fact_report"],
                "description": "Informes (u otra métrica) por celda de la cuadrícula (1° o 5°). Admite limit hasta "
                               f"{DENSITY_MAX_CELLS} para dibujar todas las celdas. Cuenta informes, no área ni población."},
    "globe": {"label": "Globo 3D", "datasets": ["fact_report"],
              "description": "Vista global de todos los informes con coordenadas, en su ubicación exacta, sobre un globo. Sin "
                             "filtros: pide solo report_count, sin group_by y con eligibility map. Para un subconjunto "
                             "(país, año, forma…) usa points."},
    "choropleth": {"label": "Coropleta por país", "datasets": ["agg_country", "fact_report", "report_model_output", "report_behavior_tag", "report_hoax_flag", "fact_crash_retrieval", "fact_nuclear_encounter"],
                   "description": "Informes por país ISO2. No normaliza por población."},
    "hour_weekday": {"label": "Matriz hora × día de la semana", "datasets": ["agg_weekday_hour", "fact_report"],
                     "description": "Informes por día de la semana y hora local declarada; solo días y relojes fiables."},
    "month_calendar": {"label": "Calendario año × mes", "datasets": ["agg_month", "fact_report"],
                       "description": "Informes por año y mes, un año por fila. Exige filtrar event_year a un rango "
                                      f"de hasta {MAX_CALENDAR_YEARS} años y un limit de 12 filas por año."},
    "stacked": {"label": "Composición al 100 %", "datasets": ["fact_report", "report_model_output", "fact_event", "agg_year", "agg_month", "agg_weekday_hour", "agg_country", "agg_shape", "agg_source", "agg_nuclear_band", "agg_coverage", *EXTRA_DATASETS],
                "description": "Barras apiladas al 100 %: cómo se reparte la segunda dimensión (fuente, forma…) dentro de cada "
                               "valor de la primera (año, década…). Conserva los conteos detrás de cada porcentaje."},
    "matrix": {"label": "Matriz de dos dimensiones", "datasets": ["fact_report", "report_model_output", "fact_event", "agg_year", "agg_month", "agg_weekday_hour", "agg_country", "agg_shape", "agg_source", "agg_nuclear_band", "agg_coverage", *EXTRA_DATASETS],
               "description": "Matriz de conteos: filas por la primera dimensión (país, fuente…) y columnas por la segunda "
                              "(década, año…). Una métrica."},
    "dumbbell": {"label": "Cambio entre dos períodos", "datasets": ["fact_report", "agg_year", "agg_shape"],
                 "description": "Puntos unidos con la proporción de cada categoría en dos períodos. Agrupa por "
                                "[decade o event_year, categoría] y filtra el período con op in y exactamente dos valores."},
    "timeline": {"label": "Cronología de informes", "datasets": ["fact_report"],
                 "description": "Tarjetas de informes ordenadas por fecha con precisión diaria. Sin métricas; exige eligibility 'day'."},
    "histogram": {"label": "Histograma", "datasets": ["fact_report", "report_model_output"],
                  "description": "Informes por tramos de una medida (measure): duration (minutos hasta 60, por defecto), "
                                 "duration_tail (más de una hora, tramos logarítmicos), witnesses, nuclear_distance, sentiment, "
                                 "vader, roberta, richness, quality, hoax. Pide solo report_count; group_by opcional de una "
                                 "dimensión (por ejemplo source_code) para un panel por valor."},
    "ecdf": {"label": "Distribución acumulada", "datasets": ["fact_report"],
             "description": "Porcentaje acumulado de informes hasta cada valor de la medida: duration (0–60 min, por defecto) o "
                            "nuclear_distance (0–1.000 km). Pide solo report_count; group_by opcional de una dimensión."},
    "boxplot": {"label": "Cajas y cuantiles", "datasets": ["fact_report", "report_model_output"],
                "description": "Percentiles 5, 25, 50, 75 y 95 de una medida por grupo. Pide una métrica de cuantil "
                               "(median_duration_min, median_witnesses, median_nuclear_distance_km, median_sentiment_score, "
                               "median_richness_score) y group_by de una dimensión."},
    "scatter": {"label": "Dispersión agregada", "datasets": ["fact_report", "report_model_output"],
                "description": "Informes por celda de dos medidas (measure): duration_witnesses (fact_report, escalas "
                               "logarítmicas) o vader_roberta (report_model_output). Pide solo report_count, sin group_by."},
    # Views drawn by the analyses of gold_analysis.py (tool analyze); query_gold cannot request them.
    "waterfall": {"label": "Cascada de cambios", "datasets": [], "description": "Aporte de cada categoría al cambio entre dos períodos (analyze period_change)."},
    "bump": {"label": "Posiciones en el tiempo", "datasets": [], "description": "Ranking acumulado por año (analyze rank_over_time)."},
    "curve": {"label": "Curva de concentración", "datasets": [], "description": "Parte de los informes en la parte más concurrida de las celdas (analyze concentration)."},
    "clusters": {"label": "Agrupaciones espacio-temporales", "datasets": [], "description": "Grupos de informes cercanos en lugar y fecha, en mapa 2D/3D (analyze clusters)."},
    "links": {"label": "Enlaces con instalaciones", "datasets": [], "description": "Celdas unidas con su instalación más cercana (analyze facility_links)."},
    "funnel": {"label": "Embudo de cobertura", "datasets": [], "description": "Informes que conservan año, mes, día y hora (analyze funnel)."},
    "upset": {"label": "Combinaciones de datos faltantes", "datasets": [], "description": "Qué campos faltan juntos (analyze missing_combinations)."},
    "compare": {"label": "Comparación de dos informes", "datasets": [], "description": "Dos fichas alineadas campo a campo (analyze compare_reports)."},
}
ANALYSIS_VIEWS = ("waterfall", "bump", "curve", "clusters", "links", "funnel", "upset", "compare")
PERIOD_DIMENSIONS = ("decade", "event_year")
# Measures drawn by histogram, ecdf and scatter: column, dataset, unit, requirements and bin edges.
def _edges(start, stop, step):
    out, x = [], start
    while x <= stop + 1e-9:
        out.append(round(x, 6)); x += step
    return out
MEASURES = {
    "duration": {"dataset": "fact_report", "column": "duration_seconds", "scale": 1 / 60, "unit": "min", "label": "Duración declarada",
                 "edges": _edges(0, 60, 1), "positive_only": False},
    "duration_tail": {"dataset": "fact_report", "column": "duration_seconds", "scale": 1 / 3600, "unit": "h", "label": "Duración de más de una hora",
                      "edges": [1, 2, 4, 8, 24, 72, 168, 720, 8760], "positive_only": True, "min_exclusive": 1},
    "witnesses": {"dataset": "fact_report", "column": "num_witnesses", "scale": 1, "unit": "testigos", "label": "Testigos consignados",
                  "edges": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 21, 51], "integer": True},
    "nuclear_distance": {"dataset": "fact_report", "column": "nuclear_distance_km", "scale": 1, "unit": "km",
                         "label": "Distancia a la instalación más cercana", "edges": _edges(0, 1000, 25), "requires": ["nuclear_proximity"]},
    "sentiment": {"dataset": "report_model_output", "column": "sentiment_score", "scale": 1, "unit": "puntuación", "label": "Sentimiento heredado (modelo)",
                  "edges": _edges(-1, 1, 0.1), "model_output": True},
    "vader": {"dataset": "report_model_output", "column": "vader_compound", "scale": 1, "unit": "puntuación", "label": "VADER (modelo)",
              "edges": _edges(-1, 1, 0.1), "model_output": True},
    "roberta": {"dataset": "report_model_output", "column": "roberta_sentiment", "scale": 1, "unit": "puntuación", "label": "RoBERTa (modelo)",
                "edges": _edges(-1, 1, 0.1), "model_output": True},
    "richness": {"dataset": "report_model_output", "column": "richness_score", "scale": 1, "unit": "puntos", "label": "Riqueza del relato (heurística)",
                 "edges": _edges(0, 12, 1), "integer": True, "model_output": True},
    "quality": {"dataset": "report_model_output", "column": "quality_score", "scale": 1, "unit": "puntos", "label": "Calidad documental (heurística)",
                "edges": _edges(0, 100, 5), "model_output": True},
    "hoax": {"dataset": "report_model_output", "column": "hoax_likelihood", "scale": 1, "unit": "probabilidad", "label": "Probabilidad de engaño (modelo)",
             "edges": _edges(0, 1, 0.05), "model_output": True},
}
ECDF_MEASURES = ("duration", "nuclear_distance")
SCATTER_PAIRS = {
    "duration_witnesses": {"dataset": "fact_report", "x": "duration", "y": "witnesses", "positive_only": True,
                           "x_edges": [0, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120, 240, 720, 1440, 10080],
                           "y_edges": [1, 2, 3, 4, 5, 6, 8, 11, 16, 21, 51, 101]},
    "vader_roberta": {"dataset": "report_model_output", "x": "vader", "y": "roberta", "x_edges": _edges(-1, 1, 0.1), "y_edges": _edges(-1, 1, 0.1)},
}
QUANTILES = (0.05, 0.25, 0.5, 0.75, 0.95)
TIMELINE_COLUMNS = ["report_id", "event_date", "source_code", "shape_code", "country_iso2", "num_witnesses",
                    "duration_seconds", "uses_external_evidence"]
DURATION_MAX_MINUTES = 60
AREA_MAX_VERTICES = 400


@lru_cache(maxsize=32)
def _polygon(text: str) -> tuple:
    return tuple(tuple(p) for p in json.loads(text))


def in_area(lng, lat, polygon: str) -> int:
    """Ray casting in longitude/latitude: 1 if the point lies inside the drawn polygon.
    The globe may give longitudes beyond ±180 when the shape crosses the antimeridian."""
    if lng is None or lat is None:
        return 0
    poly = _polygon(polygon)
    hit = 0
    for shift in (0.0, 360.0, -360.0):
        x, inside = lng + shift, False
        j = len(poly) - 1
        for i in range(len(poly)):
            xi, yi = poly[i]
            xj, yj = poly[j]
            if (yi > lat) != (yj > lat) and x < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
        hit = hit or inside
    return int(hit)

FULL_FETCH = 100000  # row ceiling when every group is needed before sorting (still bounded by the instruction budget)
POINT_COLUMNS = ["report_id", "lat", "lng", "source_code", "date_key", "shape_code", "coordinate_basis",
                 "uses_external_evidence", "duplicate_status"]
DENSITY_GROUPS = {"agg_spatial_cell": [["cell_lat", "cell_lng"]],
                  "fact_report": [["cell1_lat", "cell1_lng"], ["cell5_lat", "cell5_lng"]]}
OP_SQL = {"eq": "=", "ne": "!=", "gte": ">=", "lte": "<="}
SUMMED_RATIO = re.compile(r"^(sum|total|avg|mean|promedio|suma)_(.+)$")


# Plain-language wording shown to people. The catalogs stay untouched because
# they are part of the Gold definitions hash.
PLAIN_LIMITATIONS = {
    "confirmed_events_only": "Los eventos existen solo para los duplicados confirmados por coincidencia exacta. "
                             "Los demás informes cuentan cada uno como un informe y no son eventos.",
}


OTHER = "__other__"


class QueryError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class GoldUnavailable(RuntimeError):
    pass


def _scalar(value) -> bool:
    if isinstance(value, bool) or value is None:
        return True
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    return isinstance(value, str) and len(value) <= 200


@dataclass(frozen=True)
class Filter:
    column: str
    op: str = "eq"
    value: object = None

    @staticmethod
    def parse(raw) -> "Filter":
        if not isinstance(raw, dict):
            raise QueryError("contract", "Cada filtro debe ser un objeto")
        extra = set(raw) - {"column", "op", "value"}
        if extra:
            raise QueryError("contract", f"Campos no admitidos en filtro: {sorted(extra)}")
        column, op, value = raw.get("column"), raw.get("op", "eq"), raw.get("value")
        if not isinstance(column, str) or not column:
            raise QueryError("contract", "El filtro requiere column")
        if op not in OPS:
            raise QueryError("contract", f"Operador no admitido: {op!r}")
        if isinstance(value, list):
            if op != "in" or not all(_scalar(v) and v is not None for v in value):
                raise QueryError("contract", "Solo el operador in admite una lista de valores escalares")
        elif not _scalar(value):
            raise QueryError("contract", "Valor de filtro no admitido")
        return Filter(column, op, value)

    def as_dict(self):
        return {"column": self.column, "op": self.op, "value": self.value}


@dataclass(frozen=True)
class Query:
    dataset: str
    filters: tuple = ()
    group_by: tuple = ()
    metrics: tuple = ()
    columns: tuple = ()
    eligibility: tuple = ()
    view: str = "table"
    title: str | None = None
    order_by: str | None = None
    descending: bool = True
    limit: int = 100
    rollup: bool = False
    area: tuple | None = None  # polygon [(lng, lat), …] drawn on a map; only reports inside it
    measure: str | None = None  # histogram, ecdf and scatter: what is binned (MEASURES / SCATTER_PAIRS)

    FIELDS = ("dataset", "filters", "group_by", "metrics", "columns", "eligibility", "view", "title",
              "order_by", "descending", "limit", "rollup", "area", "measure")

    @staticmethod
    def parse(raw, limits: dict) -> "Query":
        if isinstance(raw, Query):
            return raw
        if not isinstance(raw, dict):
            raise QueryError("contract", "La consulta debe ser un objeto JSON")
        extra = set(raw) - set(Query.FIELDS)
        if extra:
            raise QueryError("contract", f"Campos no admitidos: {sorted(extra)}. El agente no puede enviar SQL ni campos libres.")

        def strings(name, maximum):
            value = raw.get(name, [])
            if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
                raise QueryError("contract", f"{name} debe ser una lista de textos")
            if len(value) > maximum:
                raise QueryError("contract", f"{name} admite como máximo {maximum} elementos")
            if len(set(value)) != len(value):
                raise QueryError("contract", f"{name} tiene elementos repetidos")
            return tuple(value)

        dataset = raw.get("dataset")
        if not isinstance(dataset, str) or not dataset:
            raise QueryError("contract", "dataset es obligatorio")
        filters = raw.get("filters", [])
        if not isinstance(filters, list) or len(filters) > limits["max_filters"]:
            raise QueryError("contract", f"filters debe ser una lista de hasta {limits['max_filters']} filtros")
        view = raw.get("view", "table")
        if view not in VIEWS:
            raise QueryError("view_unknown", f"Vista desconocida: {view!r}. Vistas: {sorted(VIEWS)}")
        title = raw.get("title")
        if title is not None and (not isinstance(title, str) or len(title) > 120):
            raise QueryError("contract", "title debe ser un texto de hasta 120 caracteres")
        order_by = raw.get("order_by")
        if order_by is not None and not isinstance(order_by, str):
            raise QueryError("contract", "order_by debe ser un texto")
        descending, rollup = raw.get("descending", True), raw.get("rollup", False)
        if not isinstance(descending, bool) or not isinstance(rollup, bool):
            raise QueryError("contract", "descending y rollup deben ser booleanos")
        view_name = raw.get("view", "table")
        # A map of cells is complete or misleading: density may ask for every cell of the selection.
        maximum = DENSITY_MAX_CELLS if view_name == "density" else limits["max_limit"]
        limit = raw.get("limit", limits["default_limit"])
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= maximum:
            raise QueryError("limit", f"limit debe ser un entero entre 1 y {maximum}" + (" (density admite hasta "
                             f"{DENSITY_MAX_CELLS} celdas)" if view_name != "density" else ""))
        area = raw.get("area")
        if area is not None:
            if (not isinstance(area, list) or not 3 <= len(area) <= AREA_MAX_VERTICES
                    or not all(isinstance(p, list) and len(p) == 2 and all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in p)
                               and -540 <= p[0] <= 540 and -90 <= p[1] <= 90 for p in area)):
                raise QueryError("contract", f"area debe ser un polígono de 3 a {AREA_MAX_VERTICES} vértices [lng, lat]")
            area = tuple((float(p[0]), float(p[1])) for p in area)
        measure = raw.get("measure")
        if measure is not None and measure not in MEASURES and measure not in SCATTER_PAIRS:
            raise QueryError("contract", f"measure desconocida: {measure!r}. Medidas: {sorted(MEASURES)}; pares: {sorted(SCATTER_PAIRS)}")
        return Query(dataset=dataset, filters=tuple(Filter.parse(f) for f in filters), area=area, measure=measure,
                     group_by=strings("group_by", limits["max_group_by"]), metrics=strings("metrics", limits["max_metrics"]),
                     columns=strings("columns", 20), eligibility=tuple(sorted(strings("eligibility", 8))), view=view,
                     title=title, order_by=order_by, descending=descending, limit=limit, rollup=rollup)

    def canonical(self) -> dict:
        """Stable form used for hashing; the title is cosmetic and excluded."""
        return {"dataset": self.dataset,
                "filters": sorted((f.as_dict() for f in self.filters), key=lambda f: json.dumps(f, sort_keys=True)),
                "group_by": list(self.group_by), "metrics": list(self.metrics), "columns": list(self.columns),
                "eligibility": sorted(self.eligibility), "view": self.view, "order_by": self.order_by,
                "descending": self.descending, "limit": self.limit, "rollup": self.rollup,
                **({"area": [list(p) for p in self.area]} if self.area else {}),
                **({"measure": self.measure} if self.measure else {})}

    def as_dict(self) -> dict:
        return {**self.canonical(), "title": self.title}


def query_digest(query: dict | Query, limits: dict | None = None) -> str:
    q = query if isinstance(query, Query) else Query.parse(query, limits or load_json(ROOT / "config/gold/gold.json")["query"])
    return text_digest(q.canonical())


def rows_digest(rows: list) -> str:
    return text_digest(rows)


class Analytics:
    """Read-only access to the verified serving cache of one Gold load.

    Without ``serving`` it opens the load approved in the catalog
    (``<datos>/releases.sqlite3``) and refuses to start if there is none: files
    outside the catalog are never adopted as current. The serving path and the
    certified queries are fixed when the instance is created, so every query
    of this instance answers from the same load.
    """

    def __init__(self, root: Path = ROOT, serving: Path | None = None, certified_path: Path | None = None,
                 instruction_budget: int | None = None, progress_step: int | None = None, data: Path | None = None):
        self.root = Path(root)
        self.policy = load_json(self.root / "config/gold/gold.json")
        self.limits = self.policy["query"]
        if serving is None:
            try:
                layout, self.release = releases.open_approved_gold(Path(data or releases.data_root(self.root)))
            except (releases.ReleaseError, OSError, ValueError) as exc:
                raise GoldUnavailable(str(exc)) from exc
            serving = layout.serving
        else:
            layout = releases.GoldLayout.of_serving(serving)
            self.release = {"source": "override", "version": layout.directory.name if layout else None}
            if layout and layout.readiness.exists():
                try:
                    readiness = json.loads(layout.readiness.read_text(encoding="utf-8"))
                    self.release["readiness_load_id"] = readiness.get("load_id")
                    self.release["ready_for_agent"] = readiness.get("ready_for_agent")
                except (OSError, ValueError):
                    self.release["readiness_load_id"] = None
        self.layout = layout
        self.path = Path(serving)
        manifest_path = self.path.with_name(self.path.stem + ".manifest.json")
        try:
            cache = json.loads(manifest_path.read_text(encoding="utf-8"))
            if cache["cache_version"] != CACHE_VERSION or cache["cache_version"] != self.policy["serving"]["cache_version"]:
                raise ValueError("Versión de caché incompatible")
            if digest(self.path) != cache["sha256"]:
                raise ValueError("SHA-256 de la caché incorrecto")
        except (OSError, ValueError, KeyError) as exc:
            raise GoldUnavailable("Caché Gold ausente, corrupta o desactualizada. Ejecuta scripts/build_all.py --desde gold.") from exc
        self.cache = cache
        with closing(self.connect()) as con:
            self.meta = json.loads(con.execute("SELECT catalog FROM metadata").fetchone()[0])
        if self.meta["load_id"] != cache["load_id"] or self.meta["manifest"]["gold_sha256"] != cache["gold_sha256"]:
            raise GoldUnavailable("La caché no corresponde a la carga Gold que declara su manifiesto.")
        self.datasets = self.meta["dataset_catalog"]
        self.metrics = self.meta["metric_catalog"]
        self.dimensions = self.meta["dimension_catalog"]["dimensions"]
        self.eligibility = self.meta["dimension_catalog"]["eligibility"]
        self.labels = self.meta["labels"]
        self.values = self.meta["allowed_values"]
        self.limitations = {item["code"]: item for item in self.meta["limitations"]}
        self.engine_sha = digest(Path(__file__))
        self.budget = instruction_budget or self.limits["instruction_budget"]
        self.step = progress_step or self.limits["progress_step"]
        if certified_path is None:
            certified_path = layout.certified if layout and layout.certified.exists() else self.root / "config/gold/certified_queries.json"
        self.certified_path = Path(certified_path)
        try:
            self._certified = load_json(self.certified_path)
        except (OSError, ValueError) as exc:
            raise GoldUnavailable(f"Consultas certificadas ausentes o ilegibles: {self.certified_path}") from exc

    def coherence_problems(self) -> list[str]:
        """Why serving, certified queries and readiness are not one load (empty if they are)."""
        problems = []
        stale = [i.get("id") for i in self._certified.get("queries", [])
                 if (i.get("verification") or {}).get("load_id") != self.load_id]
        if stale:
            problems.append(f"las consultas certificadas de {self.certified_path} no se verificaron con la carga "
                            f"{self.load_id[:12]} ({len(stale)} de {len(self._certified.get('queries', []))})")
        readiness = self.release.get("readiness_load_id", self.load_id)
        if readiness != self.load_id:
            problems.append(f"el informe ready_for_agent corresponde a otra carga ({str(readiness)[:12]})")
        if self.release.get("ready_for_agent") is False:
            problems.append("la carga no está aprobada (ready_for_agent=false)")
        return problems

    # -- infrastructure -------------------------------------------------
    def connect(self):
        con = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=1")
        step = getattr(self, "step", self.policy["query"]["progress_step"])
        calls = [0]
        limit = max(1, getattr(self, "budget", self.policy["query"]["instruction_budget"]) // step)

        def progress():
            calls[0] += 1
            return int(calls[0] > limit)
        con.set_progress_handler(progress, step)
        con.create_function("in_area", 3, in_area, deterministic=True)
        return con

    def _execute(self, con, sql, params):
        try:
            return con.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            if "interrupt" in str(exc):
                raise QueryError("budget", "La consulta excede el presupuesto de instrucciones; usa un agregado o más filtros.") from exc
            raise

    @property
    def load_id(self):
        return self.meta["load_id"]

    # -- discovery tools ------------------------------------------------
    def describe(self, dataset: str | None = None) -> dict:
        if dataset is None:
            return {name: {"label": spec["label"], "grain": spec["grain"], "eligibility": spec["eligibility"],
                           "rows": self.meta["profiles"][name]["rows"]} for name, spec in self.datasets.items()}
        if dataset not in self.datasets:
            raise QueryError("dataset_unknown", f"Dataset desconocido: {dataset}")
        spec = self.datasets[dataset]
        metrics = {m: {k: self.metrics[m][k] for k in ("label", "type", "unit", "definition", "requires", "warnings")}
                   for m in self.metrics if dataset in self.metrics[m]["datasets"]}
        dims = {c: {k: self.dimensions[c].get(k) for k in ("label", "requires", "kind")} for c, r in spec["columns"].items() if r == "dimension"}
        return {"dataset": dataset, **spec, "metrics": metrics, "dimensions": dims, "profile": self.meta["profiles"][dataset]}

    def find_entities(self, text: str, kind: str | None = None, limit: int = 10) -> list:
        key = normalize(text)
        if not key:
            return []
        found = []
        for entity_kind, items in self.meta["entities"].items():
            if kind and entity_kind != kind:
                continue
            for item in items:
                names = [item["display_name"], item["canonical_name"], *item.get("aliases", []), str(item["id"])]
                keys = {normalize(n) for n in names if n}
                score = 3 if key in keys else 2 if any(k.startswith(key) for k in keys) else 1 if any(key in k for k in keys) else 0
                if score:
                    found.append((score, entity_kind, item))
        found.sort(key=lambda t: (-t[0], t[1], str(t[2]["id"])))
        best = [t for t in found if t[0] == found[0][0]] if found else []
        return [{"kind": k, "match": {3: "exact", 2: "prefix", 1: "partial"}[s], **item} for s, k, item in best[:limit]]

    # -- certified queries ----------------------------------------------
    def certified(self) -> dict:
        return self._certified

    def certification_status(self, item: dict) -> dict:
        reasons = []
        try:
            current = query_digest(item["query"], self.limits)
        except QueryError as exc:
            return {"valid": False, "reasons": [f"consulta inválida: {exc}"]}
        if current != item.get("query_sha256"):
            reasons.append("la consulta cambió desde su certificación")
        verification = item.get("verification") or {}
        if verification.get("load_id") != self.load_id:
            reasons.append("la carga Gold cambió desde su verificación")
        if not item.get("expected_result", {}).get("rows_sha256"):
            reasons.append("sin resultado esperado")
        return {"valid": not reasons, "reasons": reasons, "query_sha256": current,
                "verified_load_id": verification.get("load_id"), "verified_at": verification.get("verified_at")}

    def search_certified(self, question: str, limit: int = 3) -> list:
        """Lexical lookup with IDF weights over titles, descriptions and example questions."""
        items = self.certified()["queries"]
        vocab = {i["id"]: set(tokens(" ".join([i["title"], i["description"], *i["examples"]]))) for i in items}
        df = Counter(t for words in vocab.values() for t in words)
        idf = {t: math.log((1 + len(items)) / (1 + n)) + 1 for t, n in df.items()}
        asked = set(tokens(question))
        weight = sum(idf.get(t, math.log(1 + len(items)) + 1) for t in asked) or 1
        scored = []
        for item in items:
            hit = sum(idf[t] for t in asked & vocab[item["id"]])
            if hit:
                # Ties are common (short questions share every word with several queries): the
                # certified query whose example question is closest wins, not the first by id.
                closest = max((len(asked & set(tokens(e))) / len(asked | set(tokens(e))) for e in item["examples"]), default=0)
                scored.append((round(hit / weight, 3), round(closest, 3), item))
        scored.sort(key=lambda t: (-t[0], -t[1], t[2]["id"]))
        return [{"id": i["id"], "title": i["title"], "score": s, "example_similarity": e, "status": self.certification_status(i)}
                for s, e, i in scored[:limit]]

    def run_certified(self, certified_id: str) -> dict:
        items = {i["id"]: i for i in self.certified()["queries"]}
        if certified_id not in items:
            raise QueryError("certified_unknown", f"Consulta certificada desconocida: {certified_id}")
        return self.query(items[certified_id]["query"])

    def _certified_match(self, query_sha: str):
        for item in self.certified()["queries"]:
            if item.get("query_sha256") == query_sha:
                status = self.certification_status(item)
                return item, status
        return None, None

    # -- validation -----------------------------------------------------
    def _validate_value(self, dataset: str, column: str, value):
        spec = self.dimensions.get(column)
        if isinstance(value, bool):
            value = int(value)
        if spec is None:
            if not isinstance(value, (int, float, str)):
                raise QueryError("value", f"Valor no admitido para {column}")
            return value
        kind = spec["kind"]
        if kind in ("integer", "integer_enum", "flag"):
            if not isinstance(value, int):
                raise QueryError("value", f"{column} requiere un entero")
            if kind == "flag" and value not in (0, 1):
                raise QueryError("value", f"{column} es una bandera 0/1")
            if kind == "integer_enum" and str(value) not in spec["values"]:
                raise QueryError("value", f"Valor no permitido para {column}: {value}")
            if "range" in spec and not spec["range"][0] <= value <= spec["range"][1]:
                raise QueryError("value", f"{column} fuera de rango {spec['range']}")
            return value
        if not isinstance(value, str):
            raise QueryError("value", f"{column} requiere un texto")
        if kind == "enum" and value not in spec["values"]:
            raise QueryError("value", f"Valor no permitido para {column}: {value!r}. Permitidos: {sorted(spec['values'])}")
        if kind in ("categorical", "date_key") and column in self.values and value not in self.values[column]:
            raise QueryError("value", self._unknown_value(column, value))
        if kind == "text" and not re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", value):
            raise QueryError("value", f"{column} requiere el formato {spec.get('format')}")
        return value

    def _unknown_value(self, column: str, value) -> str:
        """Repair hint for an unknown categorical value: the allowed codes when they are few."""
        allowed = self.values[column]
        head = f"Valor desconocido para {column}: {value!r}."
        if column == "date_key":
            return head + " Usa una fecha AAAA-MM-DD presente en Gold o filtra por event_year."
        if len(allowed) <= 60:
            labels = self.labels.get(column) or {}
            listed = "; ".join(f"{v} ({labels[v]})" if labels.get(v) and labels[v] != v else str(v) for v in allowed)
            return head + f" Permitidos: {listed}."
        return head + " Usa find_entities para resolverlo."

    def _requirements(self, dataset: str, columns) -> set:
        spec = self.datasets[dataset]
        need = set()
        for column in columns:
            role = spec["columns"][column]
            if role == "dimension":
                need |= set(self.dimensions[column]["requires"])
            need |= set(spec.get("attribute_requires", {}).get(column, []))
        return need

    def _plan(self, q: Query) -> dict:
        if q.dataset not in self.datasets:
            raise QueryError("dataset_unknown", f"Dataset desconocido: {q.dataset}. Usa describe().")
        spec = self.datasets[q.dataset]
        schema = spec["columns"]
        view = VIEWS[q.view]
        if q.view in ANALYSIS_VIEWS:
            raise QueryError("view_contract", f"La vista {q.view} la produce un análisis: usa la herramienta analyze. {view['description']}")
        if view["datasets"] != "*" and q.dataset not in view["datasets"]:
            raise QueryError("view_incompatible", f"La vista {q.view} no admite el dataset {q.dataset}. Admite: {view['datasets']}")
        for column in (*q.group_by, *(f.column for f in q.filters), *q.columns):
            if column not in schema:
                raise QueryError("column_unknown", f"Columna desconocida en {q.dataset}: {column}")
        for column in q.group_by:
            if schema[column] != "dimension":
                raise QueryError("not_a_dimension", f"{column} no es una dimensión agrupable")
        metrics = []
        for code in q.metrics:
            if code not in self.metrics:
                summed = SUMMED_RATIO.match(code)
                if summed and summed.group(2) in self.metrics and self.metrics[summed.group(2)]["type"] == "ratio":
                    raise QueryError("ratio_not_summable", f"{summed.group(2)} es un porcentaje: no se suma ni se promedia; pide la métrica y se recalcula desde numerador y denominador.")
                raise QueryError("metric_unknown", f"Métrica desconocida: {code}. Los conteos son de informes; los eventos solo existen en fact_event.")
            if q.dataset not in self.metrics[code]["datasets"]:
                raise QueryError("metric_unavailable", f"La métrica {code} no está definida para {q.dataset}. Datasets: {sorted(self.metrics[code]['datasets'])}")
            metrics.append(code)
        if q.group_by and not metrics:
            raise QueryError("metrics_required", "Agrupar requiere al menos una métrica")
        if metrics and q.columns:
            raise QueryError("columns_with_metrics", "columns solo se admite en listados sin métricas")
        if not metrics and not spec.get("row_listing"):
            raise QueryError("metrics_required", f"{q.dataset} es un agregado: pide métricas")
        if q.rollup and not q.group_by:
            raise QueryError("rollup_without_groups", "rollup requiere group_by")
        # Partitioned aggregates must not be summed across their partitions.
        for column in spec.get("partition_columns", []):
            fixed = any(f.column == column and f.op == "eq" for f in q.filters)
            if not fixed and column not in q.group_by:
                raise QueryError("partition_required", f"{q.dataset} repite todos los informes en cada {column}: filtra un valor (op eq) o agrupa por {column}")
        declared_closure = set(q.eligibility) | {i for c in q.eligibility for i in self.eligibility.get(c, {}).get("implies", [])} | set(spec["eligibility"])
        for f in q.filters:
            if f.op == "is_null" and not self._requirements(q.dataset, [f.column]) <= declared_closure:
                raise QueryError("gated_null_filter", f"{f.column} es nulo cuando el informe no es elegible; declara su elegibilidad "
                                                      "o usa la columna *_exclusion para ver los motivos")
        # Eligibility, enforced in code.
        if q.area and not {"lat", "lng"} <= set(schema):
            raise QueryError("area_unavailable", f"{q.dataset} no tiene coordenadas: para limitar al área seleccionada usa fact_report")
        if q.area and q.view == "globe":
            raise QueryError("view_contract", "El globo es solo la vista global: con un área seleccionada usa points o density")
        used = [*q.group_by, *(f.column for f in q.filters), *q.columns, *(["lat"] if q.area else [])]
        need = self._requirements(q.dataset, used)
        for code in metrics:
            need |= set(self.metrics[code]["requires"])
            if self.metrics[code]["type"] == "ratio":
                for part in (self.metrics[code]["numerator"], self.metrics[code]["denominator"]):
                    need |= set(self.metrics[part]["requires"])
        inherent = set(spec["eligibility"])
        declared = set(q.eligibility)
        closure = lambda codes: set(codes) | {i for c in codes for i in self.eligibility.get(c, {}).get("implies", [])}
        unknown = declared - set(self.eligibility)
        if unknown:
            raise QueryError("eligibility_unknown", f"Elegibilidad desconocida: {sorted(unknown)}")
        if inherent:
            if not declared <= closure(inherent):
                raise QueryError("eligibility_unavailable", f"{q.dataset} ya aplica {sorted(inherent)}; para otra elegibilidad usa fact_report")
            if not need <= closure(inherent):
                raise QueryError("eligibility_unavailable", f"{q.dataset} no admite la elegibilidad {sorted(need - closure(inherent))}")
            applied = inherent
        else:
            missing = need - closure(declared)
            if missing:
                labels = ", ".join(f"{m} ({self.eligibility[m]['label']})" for m in sorted(missing))
                raise QueryError("eligibility_missing", f"Esta consulta exige declarar eligibility: {labels}. Por ejemplo, agrupar por día exige 'day' y excluye los marcadores de día.")
            for code in declared:
                if self.eligibility[code]["flag"] not in schema:
                    raise QueryError("eligibility_unavailable", f"{q.dataset} no contiene la bandera {self.eligibility[code]['flag']}")
            applied = declared
        # Filters.
        where, params, base_where, base_params = [], [], [], []
        if not inherent:
            for code in sorted(applied):
                where.append(f'"{self.eligibility[code]["flag"]}"=1')
        for f in q.filters:
            gated = bool(self._requirements(q.dataset, [f.column]))
            if f.op == "is_null":
                # Without its eligibility a gated column is null for every ineligible report: the filter would
                # count exclusions. Declared, null means the value is unknown among eligible reports.
                if gated and not self._requirements(q.dataset, [f.column]) <= closure(applied):
                    raise QueryError("gated_null_filter", f"{f.column} es nulo cuando el informe no es elegible; declara su elegibilidad "
                                                          "o usa la columna *_exclusion para ver los motivos")
                if f.value not in (None, True, False):
                    raise QueryError("value", "is_null admite value true/false")
                clause, values = f'"{f.column}"' + (" IS NOT NULL" if f.value is False else " IS NULL"), []
            elif f.op == "in":
                if not isinstance(f.value, list) or not 1 <= len(f.value) <= self.limits["max_in_values"]:
                    raise QueryError("value", f"in requiere entre 1 y {self.limits['max_in_values']} valores")
                values = [self._validate_value(q.dataset, f.column, v) for v in f.value]
                clause = f'"{f.column}" IN (' + ",".join("?" for _ in values) + ")"
            else:
                if f.value is None or isinstance(f.value, list):
                    raise QueryError("value", f"{f.op} requiere un valor escalar")
                values = [self._validate_value(q.dataset, f.column, f.value)]
                clause = f'"{f.column}" {OP_SQL[f.op]} ?'
            where.append(clause); params.extend(values)
            if not gated:
                base_where.append(clause); base_params.extend(values)
        if q.area:
            lats = [p[1] for p in q.area]
            where.append('"lat" BETWEEN ? AND ? AND in_area("lng", "lat", ?) = 1')
            params.extend([min(lats), max(lats), json.dumps([list(p) for p in q.area])])
        # View contracts.
        if q.view == "points":
            if metrics:
                raise QueryError("view_contract", "El mapa de puntos muestra informes sin agregar: no admite métricas")
            if "map" not in closure(applied):
                raise QueryError("eligibility_missing", "El mapa de puntos exige eligibility 'map'")
        if q.view == "timeseries" and (not q.group_by or q.group_by[0] not in TIME_DIMENSIONS or len(q.group_by) > 2):
            raise QueryError("view_contract", f"La serie temporal agrupa primero por una dimensión temporal {TIME_DIMENSIONS} y admite como máximo otra")
        if q.view == "choropleth" and list(q.group_by) != ["country_iso2"]:
            raise QueryError("view_contract", "La coropleta agrupa solo por country_iso2")
        if q.view == "hour_weekday" and list(q.group_by) != ["weekday", "event_hour"]:
            raise QueryError("view_contract", "La matriz agrupa exactamente por weekday y event_hour")
        if q.view == "month_calendar":
            self._check_calendar(q)
        if q.view in ("stacked", "matrix") and (len(metrics) != 1 or len(q.group_by) != 2):
            raise QueryError("view_contract", f"La vista {q.view} requiere una métrica y exactamente dos dimensiones")
        if q.view == "dumbbell":
            periods = [f for f in q.filters if f.column == (q.group_by[0] if q.group_by else None) and f.op == "in"]
            if (len(metrics) != 1 or len(q.group_by) != 2 or q.group_by[0] not in PERIOD_DIMENSIONS
                    or len(periods) != 1 or not isinstance(periods[0].value, list) or len(set(periods[0].value)) != 2):
                raise QueryError("view_contract", "El cambio entre períodos agrupa por [decade o event_year, categoría], "
                                                  "con una métrica, y filtra ese período con op in y exactamente dos valores")
        if q.view == "timeline" and metrics:
            raise QueryError("view_contract", f"La vista {q.view} lista informes: no admite métricas")
        if q.view == "timeline" and "day" not in closure(applied):
            raise QueryError("eligibility_missing", "La cronología solo admite fechas con precisión diaria: declara eligibility 'day'")
        if q.measure and q.view not in ("histogram", "ecdf", "scatter"):
            raise QueryError("view_contract", "measure solo se admite en histogram, ecdf y scatter")
        if q.view in ("histogram", "ecdf"):
            measure = q.measure or "duration"
            if measure not in MEASURES or (q.view == "ecdf" and measure not in ECDF_MEASURES):
                raise QueryError("view_contract", f"La vista {q.view} admite measure en {list(MEASURES) if q.view == 'histogram' else list(ECDF_MEASURES)}")
            if MEASURES[measure]["dataset"] != q.dataset:
                raise QueryError("view_contract", f"La medida {measure} está en {MEASURES[measure]['dataset']}")
            if list(metrics) != ["report_count"] or len(q.group_by) > 1:
                raise QueryError("view_contract", f"La vista {q.view} pide solo report_count y como mucho un group_by: el servidor agrupa la medida")
            missing = set(MEASURES[measure].get("requires", [])) - closure(applied)
            if missing:
                raise QueryError("eligibility_missing", f"La medida {measure} exige eligibility {sorted(missing)}")
        if q.view == "scatter":
            pair = SCATTER_PAIRS.get(q.measure or "")
            if pair is None or pair["dataset"] != q.dataset:
                raise QueryError("view_contract", f"La dispersión pide measure en {sorted(SCATTER_PAIRS)} con su dataset "
                                                  f"({', '.join(f'{k}: {v['dataset']}' for k, v in SCATTER_PAIRS.items())})")
            if list(metrics) != ["report_count"] or q.group_by:
                raise QueryError("view_contract", "La dispersión pide solo report_count y sin group_by")
        if q.view == "boxplot":
            if len(metrics) != 1 or self.metrics[metrics[0]]["datasets"][q.dataset].get("op") != "quantile" or len(q.group_by) > 1:
                raise QueryError("view_contract", "Las cajas piden una métrica de cuantil (median_…) y como mucho un group_by")
        if q.view == "density" and list(q.group_by) not in DENSITY_GROUPS.get(q.dataset, []):
            raise QueryError("view_contract", f"La densidad agrupa por {DENSITY_GROUPS.get(q.dataset)}")
        if q.view == "globe" and (list(metrics) != ["report_count"] or q.group_by):
            raise QueryError("view_contract", "El globo pide solo report_count y sin group_by: el servidor agrupa por ubicación")
        if q.view == "globe" and q.filters:
            raise QueryError("view_contract", "El globo es solo la vista global, sin filtros: para un subconjunto usa points")
        if q.view == "globe" and "map" not in closure(applied):
            raise QueryError("eligibility_missing", "El globo solo admite coordenadas aptas para mapa: declara eligibility 'map'")
        if q.view == "bars" and (not metrics or not 1 <= len(q.group_by) <= 2):
            raise QueryError("view_contract", "Las barras requieren métricas y una o dos dimensiones")
        if q.order_by is not None:
            valid = set(q.group_by) | set(metrics) if metrics else set(q.columns or spec.get("default_columns", schema))
            if q.order_by not in valid:
                raise QueryError("order_invalid", f"Orden inválido: {q.order_by}. Opciones: {sorted(valid)}")
        return {"spec": spec, "metrics": metrics, "applied": sorted(applied), "inherent": bool(inherent),
                "closure": sorted(closure(applied)),
                "where": where, "params": params, "base_where": base_where, "base_params": base_params}

    def _globe_locations(self, con, table: str, plan: dict) -> list[dict]:
        """Reports per exact coordinate pair, every location (no row limit): the globe draws
        each point where it was reported. Reports at identical coordinates share one point."""
        where = " WHERE " + " AND ".join(plan["where"]) if plan["where"] else ""
        sql = (f"SELECT lat, lng, COUNT(*) AS report_count FROM {table}{where} GROUP BY lat, lng "
               f"ORDER BY report_count DESC, lat, lng")
        return [dict(r) for r in self._execute(con, sql, plan["params"])]

    def _check_calendar(self, q: Query) -> None:
        """A year × month matrix must fit in one result: bounded years, every cell within limit."""
        if list(q.group_by) != ["event_year", "event_month"]:
            raise QueryError("view_contract", "El calendario agrupa exactamente por event_year y event_month")
        low = high = None
        for f in q.filters:
            if f.column != "event_year":
                continue
            values = f.value if f.op == "in" and isinstance(f.value, list) else [f.value]
            if not all(isinstance(v, int) and not isinstance(v, bool) for v in values):
                continue
            if f.op in ("eq", "in"):
                low = max(low, min(values)) if low is not None else min(values)
                high = min(high, max(values)) if high is not None else max(values)
            elif f.op == "gte":
                low = max(low, values[0]) if low is not None else values[0]
            elif f.op == "lte":
                high = min(high, values[0]) if high is not None else values[0]
        if low is None or high is None or high < low:
            raise QueryError("view_contract", "El calendario exige filtrar event_year con gte y lte (o eq/in) "
                                              f"a un rango de hasta {MAX_CALENDAR_YEARS} años")
        span = high - low + 1
        if span > MAX_CALENDAR_YEARS:
            raise QueryError("view_contract", f"El calendario admite hasta {MAX_CALENDAR_YEARS} años; "
                                              f"el filtro cubre {span} ({low}–{high})")
        if q.limit < span * 12:
            raise QueryError("limit", f"El calendario de {span} años necesita limit ≥ {span * 12}")

    def _metric_sql(self, dataset: str, code: str) -> str:
        metric = self.metrics[code]
        if metric["type"] == "ratio":
            num = self._metric_sql(dataset, metric["numerator"])
            den = self._metric_sql(dataset, metric["denominator"])
            return f"ROUND({metric['factor']}*1.0*({num})/NULLIF({den},0), 4)"
        expr = metric["datasets"][dataset]
        column = expr.get("column")
        if column is not None and column not in self.datasets[dataset]["columns"]:
            raise QueryError("catalog", f"Columna de métrica inexistente: {column}")
        col = f'"{column}"' if column else None
        op = expr["op"]
        if op == "quantile":
            return "NULL"  # computed after the grouped query (_fill_quantiles): SQLite has no percentile
        if op == "count":
            return f"COUNT({col})" if col else "COUNT(*)"
        if op == "sum":
            return f"COALESCE(SUM({col}=0),0)" if expr.get("negate_flag") else f"COALESCE(SUM({col}),0)"
        if op == "count_distinct":
            return f"COUNT(DISTINCT {col})"
        if op == "avg":
            return f"ROUND(AVG({col}), 4)"
        if op in ("min", "max"):
            return f"{op.upper()}({col})"
        raise QueryError("catalog", f"Operación de métrica no admitida: {op}")

    # -- execution ------------------------------------------------------
    def query(self, request) -> dict:
        result = self._query(request)
        return self._with_unknown_month(result) if result["view"] == "month_calendar" else result

    def _with_unknown_month(self, result: dict) -> dict:
        """Calendar: add, per year, the reports whose month cannot be known.

        Each year gets one extra row with event_month = null (“Mes desconocido”):
        reports of that year counted at year level (calendar eligibility) minus
        the ones with a reliable month. Both counts come from Gold with the same
        non-temporal filters, so the chart, the exact data and the totals agree.
        """
        q = result["query"]
        if "report_count" not in q["metrics"] or any(f["column"] in ("event_month", "year_month") for f in q["filters"]):
            return result
        yearly = {"dataset": "agg_year" if q["dataset"] == "agg_month" else q["dataset"], "filters": q["filters"],
                  "group_by": ["event_year"], "metrics": ["report_count"], "limit": self.limits["max_limit"],
                  "eligibility": [] if q["dataset"] == "agg_month" else
                                 sorted({e for e in q["eligibility"] if e not in ("month", "day", "hour")} | {"calendar"})}
        per_year = {r["event_year"]: r["report_count"] for r in self._query(yearly)["rows"]}
        known: dict = {}
        for row in result["rows"]:
            known[row["event_year"]] = known.get(row["event_year"], 0) + (row["report_count"] or 0)
        rows = []
        for year in sorted(set(per_year) | set(known)):
            rows += [r for r in result["rows"] if r["event_year"] == year]
            rows.append({"event_year": year, "event_month": None, "event_month_label": "Mes desconocido",
                         "report_count": max(0, per_year.get(year, 0) - known.get(year, 0))})
        with_month = sum(known.values())
        reports = sum(per_year.values())
        result.update(rows=rows, row_count=len(rows), empty=not rows,
                      calendar_totals={"reports": reports, "with_month": with_month, "without_month": max(0, reports - with_month)})
        result["limitations"] = [{"code": "unknown_month",
                                  "text": "“Mes desconocido” reúne los informes del año cuyo mes no es fiable (solo consignan el año, "
                                          "fecha aproximada o marcador de día); no se reparten entre los meses."}] + result["limitations"]
        return result

    def _query(self, request) -> dict:
        q = Query.parse(request, self.limits)
        plan = self._plan(q)
        spec, metrics = plan["spec"], plan["metrics"]
        table = f'"{q.dataset}"'
        where = " WHERE " + " AND ".join(plan["where"]) if plan["where"] else ""
        if metrics:
            groups = [f'"{g}"' for g in q.group_by]
            select = groups + [f'{self._metric_sql(q.dataset, m)} AS "{m}"' for m in metrics]
            group = " GROUP BY " + ", ".join(groups) if groups else ""
            if q.order_by:
                order = f' ORDER BY "{q.order_by}" {"DESC" if q.descending else "ASC"}'
            elif q.view in ("timeseries", "hour_weekday", "month_calendar", "density", "stacked", "matrix", "dumbbell") or not groups:
                order = " ORDER BY " + ", ".join(groups) if groups else ""
            else:
                order = f' ORDER BY "{metrics[0]}" DESC, ' + ", ".join(groups)
            if groups and q.order_by:
                order += ", " + ", ".join(groups)
        else:
            if q.columns:
                columns = list(q.columns)
            else:
                # Defaults never widen the eligibility the caller declared.
                defaults = (POINT_COLUMNS if q.view == "points" and q.dataset == "fact_report"
                            else TIMELINE_COLUMNS if q.view == "timeline"
                            else spec.get("default_columns", list(spec["columns"])))
                columns = [c for c in defaults if c in spec["columns"] and self._requirements(q.dataset, [c]) <= set(plan["closure"])]
            if q.view == "points":
                key = next(c for c, r in spec["columns"].items() if r == "key")
                columns = list(dict.fromkeys([key, "lat", "lng", *columns]))
            for column in columns:
                if column not in spec["columns"]:
                    raise QueryError("column_unknown", f"Columna desconocida: {column}")
            missing = self._requirements(q.dataset, columns) - set(plan["closure"])
            if missing:
                raise QueryError("eligibility_missing", f"Listar {columns} exige eligibility {sorted(missing)}")
            select = [f'"{c}"' for c in columns]
            group = ""
            key = next((c for c, r in spec["columns"].items() if r == "key"), columns[0])
            order = (f' ORDER BY "{q.order_by}" {"DESC" if q.descending else "ASC"}, "{key}"' if q.order_by
                     else f' ORDER BY "event_date", "{key}"' if q.view == "timeline" else f' ORDER BY "{key}"')
        sql = "SELECT " + ", ".join(select) + f" FROM {table}{where}{group}{order} LIMIT ?"
        limit = q.limit
        quantiles = [m for m in metrics if self._is_quantile(q.dataset, m)]
        # Post-processed results need every group before sorting and cutting.
        fetch = FULL_FETCH if quantiles or q.view == "stacked" else limit + 1
        matched_expr = "COALESCE(SUM(report_count),0)" if "report_count" in spec["columns"] else "COUNT(*)"
        external_expr = ("COALESCE(SUM(external_evidence_reports),0)" if "external_evidence_reports" in spec["columns"]
                         else "COALESCE(SUM(uses_external_evidence),0)" if "uses_external_evidence" in spec["columns"] else None)
        extra: dict = {}
        with closing(self.connect()) as con:
            matched = self._execute(con, f"SELECT {matched_expr} FROM {table}{where}", plan["params"])[0][0]
            if q.view == "points":
                rows, grouped = self._points(con, q, plan, columns, matched)
                extra["points"] = {"reports": matched, "grouped": grouped, "max_reports": POINTS_MAX_REPORTS}
            else:
                rows = [dict(r) for r in self._execute(con, sql, [*plan["params"], fetch])]
            if quantiles:
                self._fill_quantiles(con, q, plan, rows, quantiles, box=q.view == "boxplot")
            distribution = None
            if q.view in ("histogram", "ecdf"):
                distribution = self._distribution(con, q, plan)
            elif q.view == "scatter":
                distribution = self._scatter(con, q, plan)
            locations = self._globe_locations(con, table, plan) if q.view == "globe" else None
            external = self._execute(con, f"SELECT {external_expr} FROM {table}{where}", plan["params"])[0][0] if external_expr else None
            total_row = None
            if q.rollup:
                total = self._execute(con, "SELECT " + ", ".join(f'{self._metric_sql(q.dataset, m)} AS "{m}"' for m in metrics)
                                      + f" FROM {table}{where}", plan["params"])[0]
                total_row = dict(total)
                if quantiles:
                    total_q = Query(**{**q.__dict__, "group_by": ()})
                    holder = [total_row]
                    self._fill_quantiles(con, total_q, plan, holder, quantiles)
            exclusions = self._exclusions(con, q, plan)
        if quantiles and q.order_by in quantiles:
            known = [r for r in rows if r.get(q.order_by) is not None]
            rows = sorted(known, key=lambda r: r[q.order_by], reverse=q.descending) + [r for r in rows if r.get(q.order_by) is None]
        if q.view == "stacked":
            rows = self._collapse_categories(rows, q, metrics)
        truncated = len(rows) > limit and q.view != "points"
        if q.view != "points":
            rows = rows[:limit]
        if distribution:
            rows, truncated = distribution.pop("rows"), False
        if locations is not None:
            rows, truncated = locations, False
        label_columns = q.group_by if metrics else [c for c in rows[0]] if rows else []
        if q.view == "points":
            # Thousands of points: label only what the map shows (source and shape), not every column.
            label_columns = [c for c in ("source_code", "shape_code") if rows and c in rows[0]] if not extra["points"]["grouped"] else []
        if q.view in ("histogram", "ecdf") and q.group_by:
            label_columns = list(q.group_by)
        self._add_labels(rows, label_columns)
        query_sha = text_digest(q.canonical())
        certified, status = self._certified_match(query_sha)
        result_type = "certified" if certified and status["valid"] else "composed"
        limitations = self._limitations(q, plan, metrics, external)
        if certified and certified.get("limitation") and result_type == "certified":
            limitations.insert(0, {"code": "certified_note", "text": certified["limitation"]})
        return {
            "result_type": result_type,
            "certified_query_id": certified["id"] if result_type == "certified" else None,
            "certification": status if certified else None,
            "view": q.view, "view_label": VIEWS[q.view]["label"], "title": q.title,
            "rows": rows, "total": total_row, "truncated": truncated, "row_count": len(rows),
            "matched_source_rows": matched, "empty": not rows,
            "eligibility_applied": [{"code": c, "label": self.eligibility[c]["label"], "flag": self.eligibility[c]["flag"],
                                     "implied": c not in plan["applied"]} for c in plan["closure"]],
            "exclusions": exclusions,
            "external_evidence_reports": external,
            "readable_query": self._readable(q, plan, metrics),
            "query": q.as_dict(),
            "provenance": {"gold_load_id": self.load_id, "gold_sha256": self.cache["gold_sha256"],
                           "silver_sha256": self.meta["manifest"]["silver"]["sha256"],
                           "bronze_sha256": self.meta["manifest"]["bronze"]["sha256"],
                           "definitions_sha256": self.meta["manifest"]["definitions_sha256"],
                           "query_engine_sha256": self.engine_sha, "serving_sha256": self.cache["sha256"],
                           "dataset": q.dataset, "query_sha256": query_sha},
            "snapshot": {"gold_built_at": self.meta["manifest"]["built_at"],
                         "silver_reference_date": self.meta["manifest"]["silver"].get("reference_date"),
                         "label": f"Datos de la carga Gold {self.load_id[:12]} construida el {self.meta['manifest']['built_at'][:10]}"},
            "limitations": limitations,
            **({"distribution": distribution} if distribution else {}),
            **extra,
        }

    # -- post-processing helpers -----------------------------------------
    def _is_quantile(self, dataset: str, code: str) -> bool:
        return self.metrics[code]["datasets"].get(dataset, {}).get("op") == "quantile"

    def _values_by_group(self, con, q: Query, plan: dict, column: str, positive_only: bool, scale: float) -> dict:
        """Sorted values of ``column`` per group of ``q.group_by`` (same filters and eligibility)."""
        groups = [f'"{g}"' for g in q.group_by]
        where = plan["where"] + [f'"{column}" IS NOT NULL'] + ([f'"{column}" > 0'] if positive_only else [])
        sql = (f'SELECT {", ".join(groups + [chr(34) + column + chr(34)])} FROM "{q.dataset}" WHERE ' + " AND ".join(where)
               + " ORDER BY " + ", ".join(groups + [f'"{column}"']))
        out: dict = {}
        n = len(groups)
        for row in self._execute(con, sql, plan["params"]):
            out.setdefault(tuple(row[:n]), []).append(row[n] * scale)
        return out

    @staticmethod
    def _quantile(values: list, q: float):
        if not values:
            return None
        index = min(len(values) - 1, max(0, math.ceil(q * len(values)) - 1))
        return round(values[index], 4)

    def _fill_quantiles(self, con, q: Query, plan: dict, rows: list, metrics: list, box: bool = False) -> None:
        for code in metrics:
            expr = self.metrics[code]["datasets"][q.dataset]
            values = self._values_by_group(con, q, plan, expr["column"], bool(expr.get("positive_only")), expr.get("scale", 1))
            for row in rows:
                found = values.get(tuple(row.get(g) for g in q.group_by), [])
                row[code] = self._quantile(found, expr["q"])
                if box:
                    row["box"] = {"n": len(found), **{f"p{int(p * 100):02d}": self._quantile(found, p) for p in QUANTILES},
                                  "min": round(found[0], 4) if found else None, "max": round(found[-1], 4) if found else None}

    def _points(self, con, q: Query, plan: dict, columns: list, matched: int):
        """Every report of the selection: one row per report up to POINTS_MAX_REPORTS, else one per coordinate."""
        where = " WHERE " + " AND ".join(plan["where"]) if plan["where"] else ""
        spec = self.datasets[q.dataset]
        key = next(c for c, r in spec["columns"].items() if r == "key")
        if matched <= POINTS_MAX_REPORTS:
            sql = f'SELECT {", ".join(chr(34) + c + chr(34) for c in columns)} FROM "{q.dataset}"{where} ORDER BY "{key}" LIMIT ?'
            return [dict(r) for r in self._execute(con, sql, [*plan["params"], POINTS_MAX_REPORTS])], False
        shape = ', CASE WHEN COUNT(DISTINCT "shape_code") = 1 THEN MAX("shape_code") END AS shape_code' if "shape_code" in spec["columns"] else ""
        external = ', MAX("uses_external_evidence") AS uses_external_evidence' if "uses_external_evidence" in spec["columns"] else ""
        sql = (f'SELECT lat, lng, COUNT(*) AS report_count{shape}{external} FROM "{q.dataset}"{where} '
               "GROUP BY lat, lng ORDER BY report_count DESC, lat, lng")
        return [dict(r) for r in self._execute(con, sql, plan["params"])], True

    def _collapse_categories(self, rows: list, q: Query, metrics: list) -> list:
        """Stacked: keep the largest categories of the second dimension and join the rest as "Otras"."""
        if len(q.group_by) != 2 or not metrics or self.metrics[metrics[0]]["type"] != "additive":
            return rows
        first, second = q.group_by
        metric = metrics[0]
        totals = Counter()
        for r in rows:
            totals[r[second]] += r.get(metric) or 0
        if len(totals) <= STACKED_MAX_CATEGORIES:
            return rows
        keep = {k for k, _ in totals.most_common(STACKED_MAX_CATEGORIES - 1)}
        merged: dict = {}
        out = []
        for r in rows:
            if r[second] in keep:
                out.append(r)
            else:
                slot = merged.setdefault(r[first], {first: r[first], second: OTHER, metric: 0})
                slot[metric] += r.get(metric) or 0
        out += list(merged.values())
        order = {k: i for i, (k, _) in enumerate(totals.most_common())}
        return sorted(out, key=lambda r: (r[first] is None, r[first], order.get(r[second], len(order))))

    def _bin_case(self, expression: str, edges: list) -> str:
        """Index of the bin of each value: -1 below the first edge, len(edges)-1 at or above the last."""
        cases = " ".join(f"WHEN {expression} < {edges[i + 1]!r} THEN {i}" for i in range(len(edges) - 1))
        return f"CASE WHEN {expression} < {edges[0]!r} THEN -1 {cases} ELSE {len(edges) - 1} END"

    def _distribution(self, con, q: Query, plan: dict) -> dict:
        """Histogram / ECDF bins of one measure, optionally one series per value of one dimension."""
        code = q.measure or "duration"
        m = MEASURES[code]
        value = f'("{m["column"]}" * {m["scale"]!r})'
        valid = [f'"{m["column"]}" IS NOT NULL'] + ([f'"{m["column"]}" > 0'] if m.get("positive_only") else []) \
            + ([f"{value} > {m['min_exclusive']!r}"] if "min_exclusive" in m else [])
        where = plan["where"]
        facet = f'"{q.group_by[0]}"' if q.group_by else "NULL"
        base = f' FROM "{q.dataset}"' + (" WHERE " + " AND ".join(where) if where else "")
        sql = (f"SELECT {facet} AS facet, CASE WHEN NOT ({' AND '.join(valid)}) THEN NULL ELSE {self._bin_case(value, m['edges'])} END AS b, "
               f"COUNT(*) AS n{base} GROUP BY 1, 2")
        series: dict = {}
        for r in self._execute(con, sql, plan["params"]):
            item = series.setdefault(r["facet"], {"counts": [0] * (len(m["edges"]) - 1), "over_max": 0, "below_min": 0, "without_value": 0})
            if r["b"] is None:
                item["without_value"] += r["n"]
            elif r["b"] == -1:
                item["below_min"] += r["n"]
            elif r["b"] >= len(m["edges"]) - 1:
                item["over_max"] += r["n"]
            else:
                item["counts"][r["b"]] += r["n"]
        ordered = sorted(series.items(), key=lambda kv: -sum(kv[1]["counts"]) - kv[1]["over_max"])[:8]
        labels = self.labels.get(q.group_by[0], {}) if q.group_by else {}
        out_series = []
        for key, item in ordered:
            item["with_value"] = sum(item["counts"]) + item["over_max"]
            out_series.append({"key": key, "label": labels.get(str(key), "sin dato" if key is None else str(key)) if q.group_by else None, **item})
        fmt = lambda x: f"{x:g}".replace(".", ",")
        rows = []
        for item in out_series:
            facet_value = {q.group_by[0]: item["key"]} if q.group_by else {}
            for i, n in enumerate(item["counts"]):
                rows.append({**facet_value, "bin": f"{fmt(m['edges'][i])}–{fmt(m['edges'][i + 1])} {m['unit']}", "report_count": n})
            rows.append({**facet_value, "bin": f"{fmt(m['edges'][-1])} {m['unit']} o más", "report_count": item["over_max"]})
            rows.append({**facet_value, "bin": "Sin valor", "report_count": item["without_value"]})
        out = {"rows": rows, "measure": code, "label": m["label"], "unit": m["unit"], "edges": m["edges"], "series": out_series,
               "facet": q.group_by[0] if q.group_by else None}
        if code == "duration" and len(out_series) == 1 and not q.group_by:
            # Shape of the earlier contract (one-minute bins), kept for conversations already stored.
            item = out_series[0]
            out["rows"] = ([{"duration_bin": f"{i}–{i + 1} min", "report_count": n} for i, n in enumerate(item["counts"])]
                           + [{"duration_bin": f"Más de {DURATION_MAX_MINUTES} min", "report_count": item["over_max"]},
                              {"duration_bin": "Sin duración declarada", "report_count": item["without_value"]}])
            out.update(bins=[{"from_s": i * 60, "to_s": (i + 1) * 60, "report_count": n} for i, n in enumerate(item["counts"])],
                       over_max=item["over_max"], without_duration=item["without_value"], with_duration=item["with_value"],
                       max_minutes=DURATION_MAX_MINUTES)
        elif code == "duration" and not out_series:
            out.update(bins=[], over_max=0, without_duration=0, with_duration=0, max_minutes=DURATION_MAX_MINUTES)
        return out

    def _scatter(self, con, q: Query, plan: dict) -> dict:
        pair = SCATTER_PAIRS[q.measure]
        mx, my = MEASURES[pair["x"]], MEASURES[pair["y"]]
        vx, vy = f'("{mx["column"]}" * {mx["scale"]!r})', f'("{my["column"]}" * {my["scale"]!r})'
        where = plan["where"] + [f'"{mx["column"]}" IS NOT NULL', f'"{my["column"]}" IS NOT NULL']
        if pair.get("positive_only"):
            where += [f'"{mx["column"]}" > 0', f'"{my["column"]}" > 0']
        sql = (f"SELECT {self._bin_case(vx, pair['x_edges'])} AS bx, {self._bin_case(vy, pair['y_edges'])} AS by, COUNT(*) AS n "
               f'FROM "{q.dataset}" WHERE ' + " AND ".join(where) + " GROUP BY 1, 2")
        xe, ye = pair["x_edges"], pair["y_edges"]
        edge = lambda e, i: e[i] if 0 <= i < len(e) else None
        rows = [{"x_bin": r["bx"], "y_bin": r["by"], "x_from": edge(xe, r["bx"]), "x_to": edge(xe, r["bx"] + 1),
                 "y_from": edge(ye, r["by"]), "y_to": edge(ye, r["by"] + 1), "report_count": r["n"]}
                for r in self._execute(con, sql, plan["params"])]
        rows.sort(key=lambda r: (r["x_bin"], r["y_bin"]))
        return {"rows": rows, "measure": q.measure, "x": {"measure": pair["x"], "label": mx["label"], "unit": mx["unit"], "edges": xe},
                "y": {"measure": pair["y"], "label": my["label"], "unit": my["unit"], "edges": ye},
                "with_value": sum(r["report_count"] for r in rows)}

    def _exclusions(self, con, q: Query, plan: dict):
        if not plan["applied"]:
            return None
        flags = [self.eligibility[c]["flag"] for c in plan["applied"]]
        if plan["inherent"]:
            name = q.dataset
            source = [f for f in q.filters if f.column == "source_code"]
            scoped = all(f.column in ("source_code", "resolution_deg") for f in q.filters)
            where, params = ["aggregate_code=?"], [name]
            if scoped:
                for f in source:
                    values = f.value if isinstance(f.value, list) else [f.value]
                    if f.op == "ne":
                        where.append("source_code != ?")
                    else:
                        where.append("source_code IN (" + ",".join("?" for _ in values) + ")")
                    params.extend(values)
            rows = self._execute(con, f"""SELECT coverage_status, reason, SUM(report_count) FROM agg_coverage
                WHERE {' AND '.join(where)} GROUP BY 1,2 ORDER BY 1 DESC, 3 DESC""", params)
            included = sum(r[2] for r in rows if r[0] == "included")
            excluded = {r[1]: r[2] for r in rows if r[0] == "excluded"}
            return {"scope": "filtros de fuente" if scoped and source else "agregado completo" if not scoped else "todas las fuentes",
                    "base_reports": included + sum(excluded.values()), "eligible_reports": included,
                    "excluded_reports": sum(excluded.values()),
                    "excluded_by_reason": [{"reason": k, "label": self.labels["reason"].get(k, k), "reports": v} for k, v in excluded.items()]}
        table = f'"{q.dataset}"'
        base = " WHERE " + " AND ".join(plan["base_where"]) if plan["base_where"] else ""
        base_total = self._execute(con, f"SELECT COUNT(*) FROM {table}{base}", plan["base_params"])[0][0]
        eligible_where = plan["base_where"] + [f'"{f}"=1' for f in flags]
        eligible = self._execute(con, f"SELECT COUNT(*) FROM {table} WHERE " + " AND ".join(eligible_where), plan["base_params"])[0][0]
        reasons = []
        columns = self.datasets[q.dataset]["columns"]
        exclusion_columns = [self.policy["eligibility"][c]["exclusion"] for c in plan["applied"]]
        if all(c in columns for c in exclusion_columns):
            reason = "COALESCE(" + ", ".join(f'"{c}"' for c in exclusion_columns) + ")" if len(exclusion_columns) > 1 else f'"{exclusion_columns[0]}"'
            not_eligible = "NOT (" + " AND ".join(f'"{f}"=1' for f in flags) + ")"
            rows = self._execute(con, f"SELECT {reason}, COUNT(*) FROM {table} WHERE " + " AND ".join(plan["base_where"] + [not_eligible])
                                 + " GROUP BY 1 ORDER BY 2 DESC", plan["base_params"])
            reasons = [{"reason": r[0], "label": self.labels["reason"].get(r[0], r[0]), "reports": r[1]} for r in rows]
        return {"scope": "filtros no temporales ni geográficos de la consulta", "base_reports": base_total,
                "eligible_reports": eligible, "excluded_reports": base_total - eligible, "excluded_by_reason": reasons}

    def _add_labels(self, rows, columns):
        for row in rows:
            for column in columns:
                labels = self.labels.get(column)
                if column in row and row[column] == OTHER:
                    row[f"{column}_label"] = "Otras"
                elif labels is not None and column in row:
                    value = row[column]
                    row[f"{column}_label"] = labels.get(str(value), "sin dato" if value is None else str(value))

    def _limitations(self, q: Query, plan: dict, metrics: list, external) -> list:
        codes = ["reports_not_facts"]
        if q.dataset in ("fact_event", "event_report") or "event_count" in metrics:
            codes.append("confirmed_events_only")
        codes += [f"eligibility_{c}" for c in plan["applied"]]
        if "day" in plan["applied"] or "month" in plan["applied"] or "calendar" in plan["applied"]:
            codes.append("day_placeholders")
        if q.dataset == "report_model_output" or any(self.metrics[m].get("model_output") for m in metrics):
            codes.append("model_scores")
        codes.append("source_bias")
        out = [dict(self.limitations[c], **({"text": PLAIN_LIMITATIONS[c]} if c in PLAIN_LIMITATIONS else {}))
               for c in dict.fromkeys(codes) if c in self.limitations]
        if external:
            item = dict(self.limitations["external_evidence"])
            item["text"] += f" En esta consulta: {external} informes."
            out.append(item)
        return out

    def _readable(self, q: Query, plan: dict, metrics: list) -> dict:
        def label(column, value):
            labels = self.labels.get(column) or {}
            render = lambda v: labels.get(str(v), str(v))
            return ", ".join(render(v) for v in value) if isinstance(value, list) else render(value)
        ops = {"eq": "=", "ne": "≠", "in": "∈", "gte": "≥", "lte": "≤", "is_null": "sin dato" }
        filters = []
        for f in q.filters:
            name = self.dimensions.get(f.column, {}).get("label", f.column)
            if f.op == "is_null":
                filters.append(f"{name}: {'sin dato' if f.value is not False else 'con dato'}")
            else:
                filters.append(f"{name} {ops[f.op]} {label(f.column, f.value)}")
        if q.area:
            filters.append("Dentro del área seleccionada en el mapa")
        parts = {
            "dataset": f"{self.datasets[q.dataset]['label']} ({q.dataset})",
            "filtros": filters or ["ninguno"],
            "agrupado_por": [self.dimensions[g]["label"] for g in q.group_by] or ["sin agrupar"],
            "metricas": [self.metrics[m]["label"] for m in metrics] or ["listado de filas"],
            "elegibilidad": [f"{self.eligibility[c]['label']} ({self.eligibility[c]['flag']}=1)" for c in plan["applied"]] or ["ninguna"],
            "orden": f"{q.order_by} {'desc' if q.descending else 'asc'}" if q.order_by else "predeterminado",
            "limite": q.limit,
        }
        parts["texto"] = (f"{parts['dataset']}, filtros: {'; '.join(parts['filtros'])}, agrupado por: {', '.join(parts['agrupado_por'])}"
                          f", métricas: {', '.join(parts['metricas'])}, elegibilidad: {', '.join(parts['elegibilidad'])}"
                          f", límite {q.limit}")
        return parts


def stem(word: str) -> str:
    if word.endswith("es") and len(word) > 5:
        word = word[:-2]
    elif word.endswith("s") and len(word) > 3 and not word.endswith("is"):
        word = word[:-1]
    return word[:6]


def tokens(text: str) -> list:
    return [stem(w) for w in re.findall(r"[a-z0-9]+", normalize(text)) if w not in STOPWORDS]


STOPWORDS = {"de", "la", "el", "los", "las", "en", "y", "a", "por", "que", "un", "una", "del", "al", "se", "con", "para",
             "es", "hay", "cual", "cuales", "como", "mas", "muestra", "dame", "ver", "quiero", "me", "lo", "su", "sus",
             "ovni", "ovnis", "caso", "casos", "reporte", "reportes", "avistamiento", "avistamientos", "informe", "informes",
             "registro", "registros", "cuanto", "cuantos", "cuantas", "hubo", "son", "se", "ven", "qu"}


def certify(root: Path = ROOT, analytics: Analytics | None = None, source: Path | None = None) -> dict:
    """Record expected results of every certified query for the analytics' load.

    Reads the definitions from ``source`` (default: the analytics' certified
    file) and writes the results to the analytics' certified file. The build
    certifies a copy inside the candidate version; ``gold_query.py certify``
    is the explicit operation that rewrites config/gold/certified_queries.json.
    Verification against the independent recomputation is separate
    (scripts/verify_gold_independent.py); the gate requires both.
    """
    analytics = analytics or Analytics(root=root)
    path = analytics.certified_path
    data = load_json(source or path)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for item in data["queries"]:
        q = Query.parse(item["query"], analytics.limits)
        item["query"] = {k: v for k, v in q.as_dict().items() if k != "title" or v is not None}
        item["query_sha256"] = text_digest(q.canonical())
        item["verification"] = None
        result = analytics.query(item["query"])
        item["expected_result"] = {"rows_sha256": rows_digest(result["rows"]), "row_count": result["row_count"],
                                   "matched_source_rows": result["matched_source_rows"], "truncated": result["truncated"],
                                   "rows": result["rows"]}
        item["verification"] = {"load_id": analytics.load_id, "verified_at": now,
                                "query_engine_sha256": analytics.engine_sha,
                                "independent_check": "scripts/verify_gold_independent.py"}
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    analytics._certified = data
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run").add_argument("query")
    sub.add_parser("certified").add_argument("id")
    sub.add_parser("certify")
    sub.add_parser("search").add_argument("question")
    sub.add_parser("entities").add_argument("text")
    args = parser.parse_args()
    try:
        # ``certify`` is the explicit operation that updates the versioned
        # definitions file; every other command reads the approved load.
        analytics = Analytics(certified_path=ROOT / "config/gold/certified_queries.json") if args.command == "certify" else Analytics()
        if args.command == "run":
            out = analytics.query(json.loads(args.query))
        elif args.command == "certified":
            out = analytics.run_certified(args.id)
        elif args.command == "certify":
            data = certify(analytics=analytics)
            out = {"certified": len(data["queries"]), "load_id": analytics.load_id}
        elif args.command == "search":
            out = analytics.search_certified(args.question)
        else:
            out = analytics.find_entities(args.text)
    except (QueryError, GoldUnavailable) as exc:
        print(json.dumps({"error": getattr(exc, "code", "unavailable"), "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
