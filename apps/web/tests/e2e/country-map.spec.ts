import { expect, test, type Page } from "@playwright/test";
import type { Catalog, GoldResult } from "../../src/lib/contracts";
import { countryMapCatalog, countryMapResult } from "../fixtures/country-map";

async function showMap(page: Page, result: GoldResult = countryMapResult(), catalog: Catalog = countryMapCatalog) {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = path === "/api/agent/catalog" ? catalog
      : path === "/api/auth/status" ? { authenticated: false }
      : path === "/api/agent/certified/CQ_TEST_COUNTRY_MAP" ? result : { detail: "Ruta no simulada" };
    await route.fulfill({ status: "detail" in json ? 404 : 200, json });
  });
  await page.goto("/agent#consultas-de-ejemplo");
  await page.getByRole("button", { name: "Mapa de prueba por país", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Respuesta 1 de 1", exact: true })).toBeVisible();
  return page.getByRole("group", { name: "Mapa de informes por país", exact: true });
}

for (const zoom of [1, 2]) {
  test.describe(`Mapa en portátil 1280×720 al ${zoom * 100} %`, () => {
    test.use({ viewport: { width: 1280 / zoom, height: 720 / zoom }, deviceScaleFactor: zoom });
    test("distingue cero y ausencia, permite leer países con teclado y conserva Gibraltar en la tabla", async ({ page }, testInfo) => {
      const map = await showMap(page);
      const zero = map.getByRole("img", { name: "Estados Unidos: 0", exact: true });
      const missing = map.locator('[data-m49="124"]');
      await expect(zero).toBeVisible();
      await expect(missing).toHaveAttribute("aria-label", "Canada: Sin fila en este resultado");
      await expect(missing).toHaveAttribute("tabindex", "-1");
      expect(await missing.getAttribute("fill")).toMatch(/^url\(#/);
      expect(await missing.getAttribute("fill")).not.toEqual(await zero.getAttribute("fill"));
      await missing.hover();
      await expect(page.locator(".viz-tip strong")).toHaveText("Sin fila en este resultado");
      await expect(map.getByRole("img")).toHaveCount(2);

      await page.getByRole("heading", { name: "Respuesta 1 de 1", exact: true }).focus();
      await page.keyboard.press("Tab");
      await expect(page.getByRole("button", { name: "Ir a la pregunta", exact: true })).toBeFocused();
      const labels = await map.getByRole("img").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("aria-label")));
      expect(labels).toEqual(expect.arrayContaining(["Estados Unidos: 0", "Costa Rica: 4"]));
      for (const label of labels) {
        await page.keyboard.press("Tab");
        const country = map.getByRole("img", { name: label!, exact: true });
        await expect(country).toBeFocused();
        await expect(page.locator(".viz-tip")).toContainText(label!.split(": ")[0]);
        await expect(page.locator(".viz-tip strong")).toHaveText(label!.split(": ")[1]);
        expect(await country.evaluate((element) => getComputedStyle(element).strokeWidth)).toBe("2px");
      }
      await page.screenshot({ path: testInfo.outputPath("country-map-coverage.png"), fullPage: true });
      await page.keyboard.press("Tab");
      const exact = page.getByRole("button", { name: "Datos exactos", exact: true });
      await expect(exact).toBeFocused();
      await page.keyboard.press("Enter");
      const rows = page.locator(".evidence tbody tr");
      await expect(rows).toHaveCount(3);
      await expect(rows.nth(0).locator("td")).toHaveText(["Gibraltar", "7"]);
      await expect(rows.nth(1).locator("td")).toHaveText(["Costa Rica", "4"]);
      await expect(rows.nth(2).locator("td")).toHaveText(["Estados Unidos", "0"]);
      await expect(page.getByText("1 país o territorio de este resultado no tiene geometría", { exact: false })).toBeVisible();
      await expect(page.getByText("Sin fila o valor en este resultado", { exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
  });
}

for (const count of [4, 0]) {
  test(`un filtro a Costa Rica conserva su valor ${count} y no presenta otros países como cero`, async ({ page }) => {
    const result = countryMapResult();
    result.rows = [{ country_iso2: "CR", country_iso2_label: "Costa Rica", report_count: count }];
    result.row_count = 1;
    result.matched_source_rows = count;
    result.query.filters = [{ column: "country_iso2", value: "CR" }];
    const map = await showMap(page, result);
    await expect(map.getByRole("img", { name: `Costa Rica: ${count}`, exact: true })).toBeVisible();
    await expect(map.getByRole("img")).toHaveCount(1);
    await expect(map.locator('[data-m49="840"]')).toHaveAttribute("aria-label", "United States of America: Sin fila en este resultado");
    await page.getByRole("button", { name: "Datos exactos", exact: true }).click();
    await expect(page.locator(".evidence tbody tr")).toHaveCount(1);
    await expect(page.locator(".evidence tbody tr td")).toHaveText(["Costa Rica", String(count)]);
  });
}

test("un ranking truncado no convierte en cero los países que quedan fuera", async ({ page }) => {
  const result = countryMapResult();
  result.rows = result.rows.slice(0, 2);
  result.row_count = 2;
  result.truncated = true;
  result.query.limit = 2;
  const map = await showMap(page, result);
  await expect(map.getByRole("img")).toHaveCount(1);
  const missing = map.locator('[data-m49="840"]');
  await expect(missing).toHaveAttribute("aria-label", "United States of America: Sin fila en este resultado");
  await missing.hover();
  await expect(page.locator(".viz-tip strong")).toHaveText("Sin fila en este resultado");
  await expect(page.getByText("El mapa muestra solo los países devueltos por el resultado truncado.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Datos exactos", exact: true }).click();
  await expect(page.locator(".evidence caption")).toContainText("2 filas de datos; hay más filas no mostradas");
  await expect(page.locator(".evidence tbody tr")).toHaveCount(2);
});

test("un porcentaje nulo se distingue de cero y no se suman porcentajes sin geometría", async ({ page }) => {
  const result = countryMapResult();
  result.query.metrics = ["external_evidence_pct"];
  result.rows = [
    { country_iso2: "GI", country_iso2_label: "Gibraltar", external_evidence_pct: 50 },
    { country_iso2: "CR", country_iso2_label: "Costa Rica", external_evidence_pct: null },
    { country_iso2: "US", country_iso2_label: "Estados Unidos", external_evidence_pct: 0 },
  ];
  await showMap(page, result);
  const map = page.getByRole("group", { name: "Mapa de % de informes con evidencia externa por país", exact: true });
  const missing = map.getByRole("img", { name: "Costa Rica: Sin valor disponible", exact: true });
  const zero = map.getByRole("img", { name: "Estados Unidos: 0 %", exact: true });
  await missing.focus();
  await expect(page.locator(".viz-tip strong")).toHaveText("Sin valor disponible");
  expect(await missing.getAttribute("fill")).not.toEqual(await zero.getAttribute("fill"));
  await page.getByRole("button", { name: "Datos exactos", exact: true }).click();
  await expect(page.locator(".evidence tbody tr").nth(0).locator("td")).toHaveText(["Gibraltar", "50 %"]);
  await expect(page.getByText("1 país o territorio de este resultado no tiene geometría", { exact: false })).not.toContainText("suman");
});

test("si falta la correspondencia geográfica, se conservan todas las filas en Datos exactos", async ({ page }) => {
  const catalog = structuredClone(countryMapCatalog);
  catalog.country_m49 = {};
  const map = await showMap(page, countryMapResult(), catalog);
  await expect(map.getByRole("img")).toHaveCount(0);
  await expect(page.getByText("3 países o territorios de este resultado no tienen geometría", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Datos exactos", exact: true }).click();
  await expect(page.locator(".evidence tbody tr")).toHaveCount(3);
});

test("una consulta vacía conserva su aviso y no dibuja un mundo de ceros", async ({ page }) => {
  const result = countryMapResult();
  result.rows = [];
  result.row_count = result.matched_source_rows = 0;
  result.empty = true;
  const map = await showMap(page, result);
  await expect(map).toHaveCount(0);
  await expect(page.getByText("La consulta no devolvió filas", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Datos exactos", exact: true })).toHaveCount(0);
});
