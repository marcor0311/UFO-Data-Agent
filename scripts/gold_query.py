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
  gold_query.py certify                 record expected results for the current load
  gold_query.py search '<pregunta>'     find certified queries for a question
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
import sys

if __package__:
    from .gold_common import ROOT, digest, load_json, normalize, text_digest
else:
    from gold_common import ROOT, digest, load_json, normalize, text_digest

CACHE_VERSION = 1
OPS = ("eq", "ne", "in", "gte", "lte", "is_null")
TIME_DIMENSIONS = ("event_year", "decade", "year_month", "event_date")
VIEWS = {
    "table": {"label": "Cifras y tabla", "datasets": "*",
              "description": "Cifras exactas: un total se muestra como tarjetas; un listado o agrupación, como tabla."},
    "bars": {"label": "Barras", "datasets": ["fact_report", "report_model_output", "fact_event", "agg_year", "agg_month",
                                              "agg_weekday_hour", "agg_country", "agg_shape", "agg_source", "agg_nuclear_band", "agg_coverage"],
             "description": "Compara categorías (fuentes, formas, países, bandas). Requiere métricas y una o dos dimensiones."},
    "timeseries": {"label": "Serie temporal", "datasets": ["fact_report", "report_model_output", "fact_event", "agg_year", "agg_month"],
                   "description": "Evolución por año, década, mes o día; la primera dimensión debe ser temporal."},
    "points": {"label": "Mapa de puntos", "datasets": ["fact_report"],
               "description": "Un punto por informe con coordenadas aptas para mapa. Sin métricas."},
    "density": {"label": "Densidad espacial", "datasets": ["agg_spatial_cell", "fact_report"],
                "description": "Informes por celda de la cuadrícula (1° o 5°). Cuenta informes, no área ni población."},
    "choropleth": {"label": "Coropleta por país", "datasets": ["agg_country", "fact_report", "report_model_output"],
                   "description": "Informes por país ISO2. No normaliza por población."},
    "hour_weekday": {"label": "Matriz hora × día de la semana", "datasets": ["agg_weekday_hour", "fact_report"],
                     "description": "Informes por día de la semana y hora local declarada; solo días y relojes fiables."},
}
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

    FIELDS = ("dataset", "filters", "group_by", "metrics", "columns", "eligibility", "view", "title",
              "order_by", "descending", "limit", "rollup")

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
        limit = raw.get("limit", limits["default_limit"])
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= limits["max_limit"]:
            raise QueryError("limit", f"limit debe ser un entero entre 1 y {limits['max_limit']}")
        return Query(dataset=dataset, filters=tuple(Filter.parse(f) for f in filters),
                     group_by=strings("group_by", limits["max_group_by"]), metrics=strings("metrics", limits["max_metrics"]),
                     columns=strings("columns", 20), eligibility=tuple(sorted(strings("eligibility", 8))), view=view,
                     title=title, order_by=order_by, descending=descending, limit=limit, rollup=rollup)

    def canonical(self) -> dict:
        """Stable form used for hashing; the title is cosmetic and excluded."""
        return {"dataset": self.dataset,
                "filters": sorted((f.as_dict() for f in self.filters), key=lambda f: json.dumps(f, sort_keys=True)),
                "group_by": list(self.group_by), "metrics": list(self.metrics), "columns": list(self.columns),
                "eligibility": sorted(self.eligibility), "view": self.view, "order_by": self.order_by,
                "descending": self.descending, "limit": self.limit, "rollup": self.rollup}

    def as_dict(self) -> dict:
        return {**self.canonical(), "title": self.title}


def query_digest(query: dict | Query, limits: dict | None = None) -> str:
    q = query if isinstance(query, Query) else Query.parse(query, limits or load_json(ROOT / "config/gold/gold.json")["query"])
    return text_digest(q.canonical())


def rows_digest(rows: list) -> str:
    return text_digest(rows)


class Analytics:
    """Read-only access to the verified serving cache."""

    def __init__(self, root: Path = ROOT, serving: Path | None = None, certified_path: Path | None = None,
                 instruction_budget: int | None = None, progress_step: int | None = None):
        self.root = Path(root)
        self.policy = load_json(self.root / "config/gold/gold.json")
        self.limits = self.policy["query"]
        self.path = Path(serving or self.root / self.policy["serving"]["database"])
        manifest_path = self.path.with_name(self.path.stem + ".manifest.json")
        try:
            cache = json.loads(manifest_path.read_text())
            if cache["cache_version"] != CACHE_VERSION or cache["cache_version"] != self.policy["serving"]["cache_version"]:
                raise ValueError("Versión de caché incompatible")
            if digest(self.path) != cache["sha256"]:
                raise ValueError("SHA-256 de la caché incorrecto")
        except (OSError, ValueError, KeyError) as exc:
            raise GoldUnavailable("Caché Gold ausente, corrupta o desactualizada. Ejecuta scripts/discover_gold.py.") from exc
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
        self.certified_path = Path(certified_path or self.root / "config/gold/certified_queries.json")

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
        return load_json(self.certified_path)

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
                scored.append((hit / weight, item))
        scored.sort(key=lambda t: (-t[0], t[1]["id"]))
        return [{"id": i["id"], "title": i["title"], "score": round(s, 3), "status": self.certification_status(i)}
                for s, i in scored[:limit]]

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
            raise QueryError("value", f"Valor desconocido para {column}: {value!r}. Usa find_entities para resolverlo.")
        if kind == "text" and not re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", value):
            raise QueryError("value", f"{column} requiere el formato {spec.get('format')}")
        return value

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
        for f in q.filters:
            if f.op == "is_null" and self._requirements(q.dataset, [f.column]):
                raise QueryError("gated_null_filter", f"{f.column} es nulo cuando el informe no es elegible; usa la columna *_exclusion para ver los motivos")
        # Eligibility, enforced in code.
        used = [*q.group_by, *(f.column for f in q.filters), *q.columns]
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
                if gated:
                    raise QueryError("gated_null_filter", f"{f.column} es nulo cuando el informe no es elegible; usa la columna *_exclusion para ver los motivos")
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
        if q.view == "density" and list(q.group_by) not in DENSITY_GROUPS.get(q.dataset, []):
            raise QueryError("view_contract", f"La densidad agrupa por {DENSITY_GROUPS.get(q.dataset)}")
        if q.view == "bars" and (not metrics or not 1 <= len(q.group_by) <= 2):
            raise QueryError("view_contract", "Las barras requieren métricas y una o dos dimensiones")
        if q.order_by is not None:
            valid = set(q.group_by) | set(metrics) if metrics else set(q.columns or spec.get("default_columns", schema))
            if q.order_by not in valid:
                raise QueryError("order_invalid", f"Orden inválido: {q.order_by}. Opciones: {sorted(valid)}")
        return {"spec": spec, "metrics": metrics, "applied": sorted(applied), "inherent": bool(inherent),
                "closure": sorted(closure(applied)),
                "where": where, "params": params, "base_where": base_where, "base_params": base_params}

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
            elif q.view in ("timeseries", "hour_weekday", "density") or not groups:
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
                defaults = POINT_COLUMNS if q.view == "points" else spec.get("default_columns", list(spec["columns"]))
                columns = [c for c in defaults if self._requirements(q.dataset, [c]) <= set(plan["closure"])]
            if q.view == "points":
                columns = list(dict.fromkeys(["report_id", "lat", "lng", *columns]))
            for column in columns:
                if column not in spec["columns"]:
                    raise QueryError("column_unknown", f"Columna desconocida: {column}")
            missing = self._requirements(q.dataset, columns) - set(plan["closure"])
            if missing:
                raise QueryError("eligibility_missing", f"Listar {columns} exige eligibility {sorted(missing)}")
            select = [f'"{c}"' for c in columns]
            group = ""
            key = next((c for c, r in spec["columns"].items() if r == "key"), columns[0])
            order = (f' ORDER BY "{q.order_by}" {"DESC" if q.descending else "ASC"}, "{key}"' if q.order_by else f' ORDER BY "{key}"')
        sql = "SELECT " + ", ".join(select) + f" FROM {table}{where}{group}{order} LIMIT ?"
        matched_expr = "COALESCE(SUM(report_count),0)" if "report_count" in spec["columns"] else "COUNT(*)"
        external_expr = ("COALESCE(SUM(external_evidence_reports),0)" if "external_evidence_reports" in spec["columns"]
                         else "COALESCE(SUM(uses_external_evidence),0)" if "uses_external_evidence" in spec["columns"] else None)
        with closing(self.connect()) as con:
            rows = [dict(r) for r in self._execute(con, sql, [*plan["params"], q.limit + 1])]
            matched = self._execute(con, f"SELECT {matched_expr} FROM {table}{where}", plan["params"])[0][0]
            external = self._execute(con, f"SELECT {external_expr} FROM {table}{where}", plan["params"])[0][0] if external_expr else None
            total_row = None
            if q.rollup:
                total = self._execute(con, "SELECT " + ", ".join(f'{self._metric_sql(q.dataset, m)} AS "{m}"' for m in metrics)
                                      + f" FROM {table}{where}", plan["params"])[0]
                total_row = dict(total)
            exclusions = self._exclusions(con, q, plan)
        truncated = len(rows) > q.limit
        rows = rows[:q.limit]
        self._add_labels(rows, q.group_by if metrics else [c for c in rows[0]] if rows else [])
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
        }

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
                if labels is not None and column in row:
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
        parts = {
            "dataset": f"{self.datasets[q.dataset]['label']} ({q.dataset})",
            "filtros": filters or ["ninguno"],
            "agrupado_por": [self.dimensions[g]["label"] for g in q.group_by] or ["sin agrupar"],
            "metricas": [self.metrics[m]["label"] for m in metrics] or ["listado de filas"],
            "elegibilidad": [f"{self.eligibility[c]['label']} ({self.eligibility[c]['flag']}=1)" for c in plan["applied"]] or ["ninguna"],
            "orden": f"{q.order_by} {'desc' if q.descending else 'asc'}" if q.order_by else "predeterminado",
            "limite": q.limit,
        }
        parts["texto"] = (f"{parts['dataset']} · filtros: {'; '.join(parts['filtros'])} · agrupado por: {', '.join(parts['agrupado_por'])}"
                          f" · métricas: {', '.join(parts['metricas'])} · elegibilidad: {', '.join(parts['elegibilidad'])}"
                          f" · límite {q.limit}")
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


def certify(root: Path = ROOT, analytics: Analytics | None = None) -> dict:
    """Record expected results of every certified query for the current load.

    Verification against the independent recomputation is separate
    (scripts/verify_gold_independent.py); the gate requires both.
    """
    analytics = analytics or Analytics(root=root)
    path = analytics.certified_path
    data = load_json(path)
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
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
        analytics = Analytics()
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
