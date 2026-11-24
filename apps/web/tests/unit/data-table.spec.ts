import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { Catalog, GoldResult } from "../../src/lib/contracts";
import { DataTable } from "../../src/components/views/shared";
import { rollupCatalog, rollupResult } from "../fixtures/rollup";

const render = (result = rollupResult(), catalog: Catalog | null = rollupCatalog, caption?: string) =>
  renderToStaticMarkup(createElement(DataTable, { result, catalog, caption }));
const totalRow = (html: string) => html.match(/<tr class="total">(.*?)<\/tr>/)?.[1] ?? "";

test("una tabla truncada distingue filas visibles, universo del total y denominador", () => {
  const html = render();
  expect(html).toContain("Se muestran 2 filas de datos; hay más filas no mostradas.");
  expect(html).toContain("todos los grupos que cumplen los filtros y la elegibilidad de la consulta, incluidos los no mostrados");
  expect(html).toContain("Denominador de «% de informes con evidencia externa»: 8 informes.");
  expect(totalRow(html)).toContain("Total del universo consultado");
});

for (const truncated of [true, false]) {
  test(`conserva el porcentaje ponderado y el recuento distinto de Gold (${truncated ? "truncada" : "completa"})`, () => {
    const html = render(rollupResult(truncated));
    const total = totalRow(html);
    // 100 * 2 / 8 = 25, rather than the visible mean (50) or full mean (33.33).
    expect(total).toContain('class="num">25 %</td>');
    expect(total).toContain('class="num">8</td>');
    // Five countries in the population; the three groups count 2 + 2 + 2.
    expect(total).toContain('class="num">5</td>');
    expect(total).not.toContain('class="num">6</td>');
    expect(html).toContain("no se suman ni se promedian los porcentajes de las filas");
  });
}

test("una tabla completa declara las tres filas sin insinuar grupos ocultos", () => {
  const html = render(rollupResult(false));
  expect(html).toContain("Se muestran 3 filas de datos; resultado completo.");
  expect(html).not.toContain("no mostrados");
  expect(html).not.toContain("más filas");
});

test("una consulta solo de porcentaje usa la población completa como denominador", () => {
  const result = rollupResult();
  result.query.metrics = ["external_evidence_pct"];
  result.rows = result.rows.map((row) => ({ source_code: row.source_code, external_evidence_pct: row.external_evidence_pct }));
  result.total = { external_evidence_pct: 25 };
  expect(render(result)).toContain("Denominador de «% de informes con evidencia externa»: 8 informes.");
});

test("prefiere el denominador explícito del total de Gold", () => {
  const result = rollupResult();
  result.matched_source_rows = 999;
  expect(render(result)).toContain("Denominador de «% de informes con evidencia externa»: 8 informes.");
});

test("no inventa un denominador si el catálogo no lo declara", () => {
  const catalog = structuredClone(rollupCatalog);
  delete catalog.metrics.external_evidence_pct.denominator;
  expect(render(rollupResult(), catalog)).not.toContain("Denominador de");
  expect(render(rollupResult(), null)).not.toContain("Denominador de");
});

test("un denominador desconocido solo se muestra si Gold devuelve su valor", () => {
  const catalog = structuredClone(rollupCatalog);
  catalog.metrics.external_evidence_pct.denominator = "scored_reports";
  catalog.metrics.scored_reports = { label: "Informes con puntuación", type: "additive", unit: "informes" };
  const result = rollupResult();
  expect(render(result, catalog)).not.toContain("Denominador de");
  result.total!.scored_reports = 7;
  expect(render(result, catalog)).toContain("Denominador de «% de informes con evidencia externa»: 7 informes con puntuación.");
});

test("preserva un denominador cero y un porcentaje nulo", () => {
  const result = rollupResult();
  result.total = { report_count: 0, external_evidence_pct: null, distinct_country_count: 0 };
  result.matched_source_rows = 0;
  const html = render(result);
  expect(html).toContain("Denominador de «% de informes con evidencia externa»: 0 informes.");
  expect(totalRow(html)).toContain('class="num">—</td>');
  expect(totalRow(html)).not.toContain("0 %");
});

test("sin rollup no fabrica un total ni un denominador", () => {
  const result = rollupResult();
  result.total = null;
  result.query.rollup = false;
  const html = render(result);
  expect(html).toContain("hay más filas no mostradas");
  expect(html).not.toContain("Total del universo consultado");
  expect(html).not.toContain("Denominador de");
});

test("el número visible corresponde a las filas de datos y excluye el total", () => {
  const result = rollupResult();
  result.rows = result.rows.slice(0, 1);
  expect(render(result)).toContain("Se muestra 1 fila de datos");
});

test("el encabezado del total abarca las columnas de agrupación", () => {
  const result = rollupResult();
  result.query.group_by = ["source_code", "country_iso2"];
  expect(totalRow(render(result))).toContain('<th scope="row" colSpan="2">Total del universo consultado</th>');
});

test("conserva un caption proporcionado y no modifica el resultado", () => {
  const result = rollupResult(), before = structuredClone(result);
  expect(render(result, rollupCatalog, "Comparación por fuente")).toContain("Comparación por fuente");
  expect(result).toEqual(before);
});
