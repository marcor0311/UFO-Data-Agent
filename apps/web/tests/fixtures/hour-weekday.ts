import type { Catalog, GoldResult } from "../../src/lib/contracts";
import { rollupCatalog, rollupResult } from "./rollup";

export function hourWeekdayResult(): GoldResult {
  const result = rollupResult(false);
  return {
    ...result, view: "hour_weekday", view_label: "Matriz hora × día de la semana", title: "Matriz de prueba por día y hora",
    rows: [
      { weekday: 1, weekday_label: "lunes", event_hour: 0, report_count: 4 },
      { weekday: 1, weekday_label: "lunes", event_hour: 1, report_count: 0 },
      { weekday: 7, weekday_label: "domingo", event_hour: 23, report_count: 9 },
    ],
    total: null, truncated: false, row_count: 3, matched_source_rows: 13, external_evidence_reports: 0,
    query: { ...result.query, dataset: "agg_weekday_hour", filters: [], group_by: ["weekday", "event_hour"],
      metrics: ["report_count"], eligibility: [], view: "hour_weekday", rollup: false, limit: 500 },
    eligibility_applied: ["calendar", "month", "day", "hour"].map((code) => ({ code, label: code, flag: code, implied: true })),
    readable_query: { ...result.readable_query, dataset: "Día y hora", filtros: [], agrupado_por: ["Día de la semana", "Hora local declarada"],
      limite: 500, texto: "Informes por día de la semana y hora local declarada." },
    provenance: { ...result.provenance, dataset: "agg_weekday_hour", query_sha256: "hour-weekday" },
  };
}

export const hourWeekdayCatalog: Catalog = {
  ...rollupCatalog,
  datasets: { ...rollupCatalog.datasets, agg_weekday_hour: { label: "Informes por día y hora", grain: "día y hora", eligibility: ["hour"], rows: 3 } },
  dimensions: { ...rollupCatalog.dimensions, weekday: { label: "Día de la semana" }, event_hour: { label: "Hora local declarada" } },
  certified_queries: [{ id: "CQ_TEST_MATRIX", title: "Matriz de prueba por día y hora", description: "Muestra sintética de informes por día y hora.",
    examples: ["Informes por día y hora"], recommended_views: ["hour_weekday"], limitation: "Datos de prueba.", valid: true }],
};
