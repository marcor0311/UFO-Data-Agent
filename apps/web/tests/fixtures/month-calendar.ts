import type { Catalog, GoldResult } from "../../src/lib/contracts";
import { rollupCatalog, rollupResult } from "./rollup";

/* 1996–1998: 1997 has no rows at all, so its row must render as missing, not zero. */
export function monthCalendarResult(): GoldResult {
  const result = rollupResult(false);
  return {
    ...result, view: "month_calendar", view_label: "Calendario año × mes", title: "Calendario de prueba por año y mes",
    rows: [
      { event_year: 1996, event_month: 1, event_month_label: "enero", report_count: 5 },
      { event_year: 1996, event_month: 2, event_month_label: "febrero", report_count: 0 },
      { event_year: 1996, event_month: null, event_month_label: "Mes desconocido", report_count: 2 },
      { event_year: 1998, event_month: 12, event_month_label: "diciembre", report_count: 12 },
      { event_year: 1998, event_month: null, event_month_label: "Mes desconocido", report_count: 0 },
    ],
    calendar_totals: { reports: 19, with_month: 17, without_month: 2 },
    total: null, truncated: false, row_count: 5, matched_source_rows: 17, external_evidence_reports: 0,
    query: { ...result.query, dataset: "agg_month", group_by: ["event_year", "event_month"], metrics: ["report_count"], eligibility: [],
      filters: [{ column: "event_year", op: "gte", value: 1996 }, { column: "event_year", op: "lte", value: 1998 }],
      view: "month_calendar", rollup: false, limit: 36 },
    eligibility_applied: ["calendar", "month"].map((code) => ({ code, label: code, flag: code, implied: true })),
    readable_query: { ...result.readable_query, dataset: "Serie mensual", filtros: ["Año ≥ 1996", "Año ≤ 1998"], agrupado_por: ["Año", "Mes"],
      limite: 36, texto: "Informes por año y mes entre 1996 y 1998." },
    provenance: { ...result.provenance, dataset: "agg_month", query_sha256: "month-calendar" },
  };
}

export const monthCalendarCatalog: Catalog = {
  ...rollupCatalog,
  datasets: { ...rollupCatalog.datasets, agg_month: { label: "Serie mensual de informes", grain: "año y mes", eligibility: ["month"], rows: 3 } },
  dimensions: { ...rollupCatalog.dimensions, event_year: { label: "Año" }, event_month: { label: "Mes" } },
  certified_queries: [{ id: "CQ_TEST_CALENDAR", title: "Calendario de prueba por año y mes", description: "Muestra sintética de informes por año y mes.",
    examples: ["Informes por año y mes"], recommended_views: ["month_calendar"], limitation: "Datos de prueba.", valid: true }],
};
