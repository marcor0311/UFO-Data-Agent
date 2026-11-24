import type { Catalog, GoldResult, Row, ViewCode } from "../../src/lib/contracts";
import { rollupCatalog, rollupResult } from "./rollup";

function make(view: ViewCode, title: string, rows: Row[], query: Partial<GoldResult["query"]>, extra: Partial<GoldResult> = {}): GoldResult {
  const base = rollupResult(false);
  return { ...base, view, view_label: title, title, rows, total: null, truncated: false, row_count: rows.length,
    matched_source_rows: rows.length, external_evidence_reports: 0,
    query: { ...base.query, filters: [], group_by: [], metrics: [], eligibility: [], rollup: false, limit: 100, ...query, view },
    provenance: { ...base.provenance, query_sha256: view }, ...extra };
}

const bins = Array.from({ length: 60 }, (_, m) => ({ from_s: m * 60, to_s: (m + 1) * 60, report_count: m < 5 ? 10 : m === 30 ? 5 : 0 }));
const distribution = { bins, over_max: 5, without_duration: 40, with_duration: 60, max_minutes: 60 };
const durationRows = [...bins.map((b, m) => ({ duration_bin: `${m}–${m + 1} min`, report_count: b.report_count })),
  { duration_bin: "Más de 60 min", report_count: 5 }, { duration_bin: "Sin duración declarada", report_count: 40 }];

export const proposalResults: Record<string, GoldResult> = {
  stacked: make("stacked", "Prueba apilada", [
    { decade: 1990, source_code: "A", report_count: 30 }, { decade: 1990, source_code: "B", report_count: 10 },
    { decade: 2000, source_code: "A", report_count: 5 }, { decade: 2000, source_code: "B", report_count: 15 },
  ], { dataset: "agg_year", group_by: ["decade", "source_code"], metrics: ["report_count"] }),
  matrix: make("matrix", "Prueba matriz", [
    { country_iso2: "US", country_iso2_label: "Estados Unidos", decade: 1990, report_count: 100 },
    { country_iso2: "US", country_iso2_label: "Estados Unidos", decade: 2000, report_count: 0 },
    { country_iso2: "CA", country_iso2_label: "Canadá", decade: 1990, report_count: 7 },
  ], { dataset: "fact_report", group_by: ["country_iso2", "decade"], metrics: ["report_count"] }),
  dumbbell: make("dumbbell", "Prueba períodos", [
    { decade: 1970, shape_code: "Disc", shape_code_label: "Disco", report_count: 60 },
    { decade: 1970, shape_code: "Light", shape_code_label: "Luz", report_count: 20 },
    { decade: 1970, shape_code: null, shape_code_label: "sin dato", report_count: 20 },
    { decade: 2010, shape_code: "Disc", shape_code_label: "Disco", report_count: 10 },
    { decade: 2010, shape_code: "Light", shape_code_label: "Luz", report_count: 90 },
  ], { dataset: "fact_report", group_by: ["decade", "shape_code"], metrics: ["report_count"], filters: [{ column: "decade", op: "in", value: [1970, 2010] }] }),
  timeline: make("timeline", "Prueba cronología", Array.from({ length: 10 }, (_, i) => ({
    report_id: 100 + i, event_date: `1997-03-${String(10 + i).padStart(2, "0")}`, source_code: "UFOCAT", source_code_label: "UFOCAT",
    shape_code: "Triangle", shape_code_label: "Triángulo", country_iso2: "US", country_iso2_label: "Estados Unidos",
    num_witnesses: i === 0 ? 3 : null, duration_seconds: i === 0 ? 120 : null,
  })), { dataset: "fact_report", eligibility: ["day"] }),
  histogram: make("histogram", "Prueba histograma", durationRows, { dataset: "fact_report", metrics: ["report_count"] }, { distribution }),
  ecdf: make("ecdf", "Prueba acumulada", durationRows, { dataset: "fact_report", metrics: ["report_count"] }, { distribution }),
};

export const proposalCatalog: Catalog = {
  ...rollupCatalog,
  dimensions: { ...rollupCatalog.dimensions, decade: { label: "Década" }, source_code: { label: "Fuente" }, country_iso2: { label: "País" },
    shape_code: { label: "Forma estandarizada" } },
  certified_queries: Object.entries(proposalResults).map(([view, r]) => ({ id: `CQ_${view.toUpperCase()}`, title: r.title!, description: "Datos sintéticos.",
    examples: [r.title!], recommended_views: [view as ViewCode], limitation: "Datos de prueba.", valid: true })),
};
