import { expect, test } from "@playwright/test";
import type { GoldResult } from "../../src/lib/contracts";
import { groupResults } from "../../src/lib/result-groups";

function ranking(): GoldResult {
  return {
    result_type: "composed", certified_query_id: null, certification: null,
    view: "bars", view_label: "Barras", title: "Informes de Costa Rica en 1997 por fuente",
    rows: [{ source_code: "UFOCAT", report_count: 3 }, { source_code: "UPDB", report_count: 2 }],
    total: null, truncated: false, row_count: 2, matched_source_rows: 5, empty: false,
    eligibility_applied: [
      { code: "calendar", label: "Calendario", flag: "usable_for_calendar", implied: false },
      { code: "country", label: "País", flag: "usable_for_country", implied: false },
    ],
    exclusions: null, external_evidence_reports: null,
    query: {
      dataset: "fact_report", filters: [{ column: "country_iso2", value: "CR" }, { column: "event_year", op: "eq", value: 1997 }],
      group_by: ["source_code"], metrics: ["report_count"], columns: [], eligibility: ["calendar", "country"],
      view: "bars", title: null, order_by: null, descending: true, limit: 100, rollup: true,
    },
    readable_query: { dataset: "Informes", filtros: [], agrupado_por: [], metricas: [], elegibilidad: [], orden: "", limite: 100, texto: "Costa Rica en 1997" },
    provenance: { dataset: "fact_report", gold_load_id: "load-1", gold_sha256: "gold", silver_sha256: "silver", bronze_sha256: "bronze",
      definitions_sha256: "definitions", query_engine_sha256: "engine", serving_sha256: "serving", query_sha256: "ranking" },
    snapshot: { gold_built_at: "2026-11-23", silver_reference_date: null, label: "Datos de prueba" }, limitations: [],
  };
}

function summary(base = ranking()): GoldResult {
  return { ...base, view: "table", view_label: "Tabla", title: "Total",
    query: { ...base.query, view: "table", group_by: [] }, rows: [{ report_count: 5 }], row_count: 1,
    provenance: { ...base.provenance, query_sha256: "summary" } };
}

const indexes = (results: GoldResult[]) => groupResults(results).map((group) => group.map((entry) => entry.index));

test("agrupa un ranking con el total de su población", () => {
  expect(indexes([ranking(), summary()])).toEqual([[0, 1]]);
});

test("separa el ranking de Costa Rica del total de EE. UU.", () => {
  const total = summary();
  total.query.filters[0] = { column: "country_iso2", value: "US" };
  expect(indexes([ranking(), total])).toEqual([[0], [1]]);
});

test("el orden de filtros y la omisión de eq no cambian el alcance", () => {
  const total = summary();
  total.query.filters = [{ value: 1997, column: "event_year" }, { value: "CR", op: "eq", column: "country_iso2" }];
  expect(indexes([ranking(), total])).toEqual([[0, 1]]);
});

for (const change of ["año", "operador", "filtro adicional"] as const) {
  test(`separa un total con distinto ${change}`, () => {
    const total = summary();
    if (change === "año") total.query.filters[1] = { column: "event_year", value: 1998 };
    if (change === "operador") total.query.filters[1] = { column: "event_year", op: "gte", value: 1997 };
    if (change === "filtro adicional") total.query.filters.push({ column: "source_code", value: "UFOCAT" });
    expect(indexes([ranking(), total])).toEqual([[0], [1]]);
  });
}

test("compara los valores de in como un conjunto sin perder el tipo", () => {
  const chart = ranking(), total = summary();
  chart.query.filters = [{ column: "country_iso2", op: "in", value: ["CR", "US"] }];
  total.query.filters = [{ column: "country_iso2", op: "in", value: ["US", "CR", "CR"] }];
  expect(indexes([chart, total])).toEqual([[0, 1]]);
  total.query.filters = [{ column: "country_iso2", op: "in", value: ["CR"] }];
  expect(indexes([chart, total])).toEqual([[0], [1]]);
  chart.query.filters = [{ column: "event_year", value: 1997 }];
  total.query.filters = [{ column: "event_year", value: "1997" }];
  expect(indexes([chart, total])).toEqual([[0], [1]]);
});

test("distingue filtros de nulos y no nulos", () => {
  const chart = ranking(), total = summary();
  chart.query.filters = [{ column: "standardized_shape", op: "is_null" }];
  total.query.filters = [{ column: "standardized_shape", op: "is_null", value: true }];
  expect(indexes([chart, total])).toEqual([[0, 1]]);
  total.query.filters[0].value = false;
  expect(indexes([chart, total])).toEqual([[0], [1]]);
});

test("separa elegibilidad efectiva distinta aunque coincida la declaración", () => {
  const total = summary();
  total.eligibility_applied = [total.eligibility_applied[0]];
  expect(indexes([ranking(), total])).toEqual([[0], [1]]);
});

test("acepta elegibilidad equivalente con otro orden o declarada implícitamente", () => {
  const total = summary();
  total.eligibility_applied = total.eligibility_applied.toReversed().map((item) => ({ ...item, implied: true }));
  total.query.eligibility = [];
  expect(indexes([ranking(), total])).toEqual([[0, 1]]);
});

test("separa métricas distintas", () => {
  const total = summary();
  total.query.metrics = ["quality_mean"];
  total.rows = [{ quality_mean: 40 }];
  expect(indexes([ranking(), total])).toEqual([[0], [1]]);
});

test("acepta las mismas métricas en distinto orden", () => {
  const chart = ranking(), total = summary();
  chart.query.metrics = ["report_count", "quality_mean"];
  total.query.metrics = ["quality_mean", "report_count"];
  expect(indexes([chart, total])).toEqual([[0, 1]]);
});

for (const load of ["load-2", ""]) {
  test(`separa un total con carga Gold diferente o ausente (${load || "vacía"})`, () => {
    const total = summary();
    total.provenance.gold_load_id = load;
    expect(indexes([ranking(), total])).toEqual([[0], [1]]);
  });
}

test("no vincula resultados si ambos carecen de carga Gold", () => {
  const chart = ranking(), total = summary();
  chart.provenance.gold_load_id = total.provenance.gold_load_id = "";
  expect(indexes([chart, total])).toEqual([[0], [1]]);
});

test("separa datasets distintos en la consulta o la procedencia", () => {
  const queryTotal = summary(), provenanceTotal = summary();
  queryTotal.query.dataset = "agg_source";
  provenanceTotal.provenance.dataset = "agg_source";
  expect(indexes([ranking(), queryTotal])).toEqual([[0], [1]]);
  expect(indexes([ranking(), provenanceTotal])).toEqual([[0], [1]]);
});

test("busca un total compatible después de otro incompatible sin perder resultados", () => {
  const other = summary();
  other.query.filters[0] = { column: "country_iso2", value: "US" };
  expect(indexes([ranking(), other, summary()])).toEqual([[0, 2], [1]]);
});

test("conserva los índices originales cuando el total llega primero", () => {
  expect(indexes([summary(), ranking()])).toEqual([[1, 0]]);
});

test("no usa como total una tabla vacía, agrupada o con varias filas", () => {
  const empty = summary(), grouped = summary(), multiple = summary();
  empty.rows = [];
  grouped.query.group_by = ["source_code"];
  multiple.rows = [{ report_count: 3 }, { report_count: 2 }];
  expect(indexes([ranking(), empty, grouped, multiple])).toEqual([[0], [1], [2], [3]]);
});

test("títulos, límites y orden de presentación no cambian la población", () => {
  const total = summary();
  total.query.limit = 1;
  total.query.descending = false;
  total.query.order_by = "report_count";
  total.query.rollup = false;
  total.title = "Otro título";
  expect(indexes([ranking(), total])).toEqual([[0, 1]]);
});

test("maneja una lista vacía y no modifica los resultados de entrada", () => {
  expect(indexes([])).toEqual([]);
  const results = [ranking(), summary()], before = structuredClone(results);
  groupResults(results);
  expect(results).toEqual(before);
});
