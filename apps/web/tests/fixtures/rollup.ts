import type { Catalog, GoldResult } from "../../src/lib/contracts";

// Same populations verified against independent SQL in the API rollup test:
// groups of 4, 2 and 2 reports, two external reports, five distinct countries.
export function rollupResult(truncated = true): GoldResult {
  const rows = [
    { source_code: "UFOCAT", report_count: 4, external_evidence_pct: 0, distinct_country_count: 2 },
    { source_code: "UFO-search", report_count: 2, external_evidence_pct: 100, distinct_country_count: 2 },
    { source_code: "UPDB", report_count: 2, external_evidence_pct: 0, distinct_country_count: 2 },
  ];
  return {
    result_type: "composed", certified_query_id: null, certification: null, view: "bars", view_label: "Barras", title: null,
    rows: truncated ? rows.slice(0, 2) : rows,
    total: { report_count: 8, external_evidence_pct: 25, distinct_country_count: 5 },
    truncated, row_count: truncated ? 2 : 3, matched_source_rows: 8, empty: false,
    eligibility_applied: [{ code: "country", label: "País", flag: "usable_for_country", implied: false }],
    exclusions: null, external_evidence_reports: 2,
    query: { dataset: "fact_report", filters: [{ column: "source_code", op: "in", value: ["UFOCAT", "UPDB", "UFO-search"] }],
      group_by: ["source_code"], metrics: ["report_count", "external_evidence_pct", "distinct_country_count"],
      columns: [], eligibility: ["country"], view: "bars", title: null, order_by: null, descending: true,
      limit: truncated ? 2 : 10, rollup: true },
    readable_query: { dataset: "Informes", filtros: [], agrupado_por: ["Fuente"], metricas: [], elegibilidad: ["País"],
      orden: "Informes", limite: truncated ? 2 : 10, texto: "Informes de UFOCAT, UPDB y UFO-search aptos para país, por fuente." },
    provenance: { dataset: "fact_report", gold_load_id: "test-load", gold_sha256: "gold", silver_sha256: "silver", bronze_sha256: "bronze",
      definitions_sha256: "definitions", query_engine_sha256: "engine", serving_sha256: "serving", query_sha256: "rollup" },
    snapshot: { gold_built_at: "2026-11-23", silver_reference_date: null, label: "Datos sintéticos" }, limitations: [],
  };
}

const view = { label: "Tabla", datasets: "*" as const, description: "Datos de prueba" };
export const rollupCatalog: Catalog = {
  load_id: "test-load", datasets: { fact_report: { label: "Informes", grain: "informe", eligibility: [], rows: 12 } },
  views: { table: view, bars: view, timeseries: view, points: view, density: view, choropleth: view, hour_weekday: view },
  metrics: {
    report_count: { label: "Informes", type: "additive", unit: "informes" },
    external_evidence_pct: { label: "% de informes con evidencia externa", type: "ratio", unit: "%", denominator: "report_count" },
    distinct_country_count: { label: "Países distintos", type: "non_additive", unit: "países" },
  },
  dimensions: { source_code: { label: "Fuente" } }, eligibility: { country: "País" },
  certified_queries: [], limitations: [], country_m49: {},
};
