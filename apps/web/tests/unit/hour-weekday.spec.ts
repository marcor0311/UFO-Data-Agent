import { expect, test } from "@playwright/test";
import { createElement, Fragment } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { HourWeekdayView, RampLegend } from "../../src/components/views/charts";
import { hourWeekdayCatalog, hourWeekdayResult } from "../fixtures/hour-weekday";

const render = (result = hourWeekdayResult()) => renderToStaticMarkup(createElement(HourWeekdayView, { result, catalog: hourWeekdayCatalog }));
const cells = (html: string) => [...html.matchAll(/<rect\b[^>]*role="gridcell"[^>]*>/g)].map((match) => match[0]);
const cell = (html: string, day: number, hour: number) => cells(html).find((tag) => tag.includes(`data-weekday="${day}" data-hour="${hour}"`))!;
const fill = (tag: string) => tag.match(/fill="([^"]+)"/)?.[1];

test("lunes a las 00:00 y domingo a las 23:00 conservan sus valores", () => {
  const html = render();
  expect(cell(html, 1, 0)).toContain('aria-label="lunes, 0:00–0:59: 4"');
  expect(cell(html, 7, 23)).toContain('aria-label="domingo, 23:00–23:59: 9"');
  const rows = [...html.matchAll(/role="row" aria-rowindex="\d" aria-label="([^"]+)"/g)].map((match) => match[1]);
  expect(rows).toEqual(["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]);
});

test("el cero explícito y la celda ausente tienen etiquetas y rellenos distintos", () => {
  const html = render();
  const zero = cell(html, 1, 1), missing = cell(html, 2, 1);
  expect(zero).toContain('aria-label="lunes, 1:00–1:59: 0"');
  expect(missing).toContain('aria-label="martes, 1:00–1:59: Sin fila en este resultado"');
  expect(fill(missing)).toMatch(/^url\(#/);
  expect(fill(zero)).not.toEqual(fill(missing));
  expect(html).toContain("Sin fila o valor en este resultado");
  expect(html).toContain("no equivalen a cero");
});

test("un porcentaje nulo no se convierte en un porcentaje cero", () => {
  const result = hourWeekdayResult();
  result.query.metrics = ["external_evidence_pct"];
  result.rows = [{ weekday: 1, event_hour: 0, external_evidence_pct: null }, { weekday: 1, event_hour: 1, external_evidence_pct: 0 }];
  const html = render(result);
  expect(cell(html, 1, 0)).toContain("Sin valor disponible");
  expect(cell(html, 1, 1)).toContain("0 %");
  expect(fill(cell(html, 1, 0))).not.toEqual(fill(cell(html, 1, 1)));
});

test("la matriz conserva las 168 posiciones y un solo punto de entrada con Tab", () => {
  const html = render();
  expect(cells(html)).toHaveLength(168);
  expect(cells(html).filter((tag) => tag.includes('tabindex="0"'))).toHaveLength(1);
  expect(cell(html, 1, 0)).toContain('tabindex="0"');
  expect(html).toContain("hora local declarada");
});

test("el orden de las filas de origen no altera días, horas ni valores", () => {
  const result = hourWeekdayResult();
  result.rows.reverse();
  const before = structuredClone(result), html = render(result);
  expect(cell(html, 1, 0)).toContain("0:59: 4");
  expect(cell(html, 7, 23)).toContain("23:59: 9");
  expect(result).toEqual(before);
});

test("una consulta truncada no interpreta las filas no devueltas como ceros", () => {
  const result = hourWeekdayResult();
  result.truncated = true;
  expect(cell(render(result), 2, 1)).toContain("Sin fila en este resultado");
});

test("dos matrices en una respuesta tienen patrones independientes", () => {
  const props = { result: hourWeekdayResult(), catalog: hourWeekdayCatalog };
  const html = renderToStaticMarkup(createElement(Fragment, null, createElement(HourWeekdayView, props), createElement(HourWeekdayView, props)));
  const ids = [...html.matchAll(/<pattern id="([^"]+)"/g)].map((match) => match[1]);
  expect(ids).toHaveLength(2);
  expect(new Set(ids).size).toBe(2);
});

test("un resultado vacío conserva el aviso y las otras leyendas no incorporan la ausencia", () => {
  const result = hourWeekdayResult();
  result.rows = [];
  result.empty = true;
  expect(cells(render(result))).toHaveLength(0);
  expect(render(result)).toContain("La consulta no devolvió filas");
  expect(renderToStaticMarkup(createElement(RampLegend, { max: 9 }))).not.toContain("Sin fila o valor");
});
