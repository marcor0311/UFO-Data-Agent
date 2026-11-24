import type { Catalog, GoldResult } from "../../src/lib/contracts";
import { rollupCatalog, rollupResult } from "./rollup";

export function countryMapResult(): GoldResult {
  const result = rollupResult(false);
  return {
    ...result, view: "choropleth", view_label: "Mapa por país", title: "Mapa de prueba por país",
    rows: [
      { country_iso2: "GI", country_iso2_label: "Gibraltar", report_count: 7 },
      { country_iso2: "CR", country_iso2_label: "Costa Rica", report_count: 4 },
      { country_iso2: "US", country_iso2_label: "Estados Unidos", report_count: 0 },
    ],
    total: null, truncated: false, row_count: 3, matched_source_rows: 11, external_evidence_reports: 0,
    query: { ...result.query, dataset: "agg_country", filters: [], group_by: ["country_iso2"], metrics: ["report_count"],
      eligibility: [], view: "choropleth", rollup: false, limit: 500 },
    eligibility_applied: [{ code: "country", label: "País", flag: "usable_for_country", implied: true }],
    readable_query: { ...result.readable_query, dataset: "Países", filtros: [], agrupado_por: ["País"],
      limite: 500, texto: "Informes por país, entre los informes aptos para país." },
    provenance: { ...result.provenance, dataset: "agg_country", query_sha256: "country-map" },
  };
}

export const countryMapCatalog: Catalog = {
  ...rollupCatalog,
  datasets: { ...rollupCatalog.datasets, agg_country: { label: "Informes por país", grain: "país", eligibility: ["country"], rows: 3 } },
  dimensions: { ...rollupCatalog.dimensions, country_iso2: { label: "País" } },
  country_m49: { CR: "188", US: "840", CA: "124", GI: "292" },
  certified_queries: [{ id: "CQ_TEST_COUNTRY_MAP", title: "Mapa de prueba por país", description: "Muestra sintética de informes por país.",
    examples: ["Informes por país"], recommended_views: ["choropleth"], limitation: "Datos de prueba.", valid: true }],
};
