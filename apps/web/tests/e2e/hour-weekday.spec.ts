import { expect, test, type Page } from "@playwright/test";
import type { GoldResult } from "../../src/lib/contracts";
import { hourWeekdayCatalog, hourWeekdayResult } from "../fixtures/hour-weekday";

async function showMatrix(page: Page, result: GoldResult = hourWeekdayResult()) {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = path === "/api/agent/catalog" ? hourWeekdayCatalog
      : path === "/api/auth/status" ? { authenticated: false }
      : path === "/api/agent/certified/CQ_TEST_MATRIX" ? result : { detail: "Ruta no simulada" };
    await route.fulfill({ status: "detail" in json ? 404 : 200, json });
  });
  await page.goto("/agent#consultas-de-ejemplo");
  await page.getByRole("button", { name: "Matriz de prueba por día y hora", exact: true }).click();
  await expect(page.getByRole("grid")).toBeVisible();
  return page.getByRole("grid");
}

for (const zoom of [1, 2]) {
  test.describe(`Matriz en portátil 1280×720 al ${zoom * 100} %`, () => {
    test.use({ viewport: { width: 1280 / zoom, height: 720 / zoom }, deviceScaleFactor: zoom });
    test("recorre valores, cero y ausencia por teclado y concuerda con los datos exactos", async ({ page }, testInfo) => {
      const grid = await showMatrix(page);
      await expect(grid.getByRole("row")).toHaveCount(7);
      await expect(grid.getByRole("gridcell")).toHaveCount(168);
      await page.getByRole("heading", { name: "Respuesta 1 de 1", exact: true }).focus();
      await page.keyboard.press("Tab");
      await expect(page.getByRole("button", { name: "Ir a la pregunta", exact: true })).toBeFocused();
      await page.keyboard.press("Tab");
      const monday = grid.getByRole("gridcell", { name: "lunes, 0:00–0:59: 4", exact: true });
      await expect(monday).toBeFocused();
      await expect(page.locator(".viz-tip")).toContainText("lunes, 0:00–0:59");
      await expect(page.locator(".viz-tip strong")).toHaveText("4");
      await page.keyboard.press("ArrowRight");
      const zero = grid.getByRole("gridcell", { name: "lunes, 1:00–1:59: 0", exact: true });
      await expect(zero).toBeFocused();
      await expect(page.locator(".viz-tip strong")).toHaveText("0");
      await page.keyboard.press("ArrowDown");
      const missing = grid.getByRole("gridcell", { name: "martes, 1:00–1:59: Sin fila en este resultado", exact: true });
      await expect(missing).toBeFocused();
      await expect(page.locator(".viz-tip strong")).toHaveText("Sin fila en este resultado");
      expect(await missing.getAttribute("fill")).not.toEqual(await zero.getAttribute("fill"));
      expect(await missing.evaluate((element) => getComputedStyle(element).stroke)).not.toBe("none");
      await page.screenshot({ path: testInfo.outputPath("matrix-missing.png"), fullPage: true });
      await page.keyboard.press("Control+End");
      const sunday = grid.getByRole("gridcell", { name: "domingo, 23:00–23:59: 9", exact: true });
      await expect(sunday).toBeFocused();
      await expect(page.locator(".viz-tip strong")).toHaveText("9");
      await page.keyboard.press("ArrowRight");
      await expect(sunday).toBeFocused();
      await page.keyboard.press("Home");
      await expect(grid.getByRole("gridcell", { name: "domingo, 0:00–0:59: Sin fila en este resultado", exact: true })).toBeFocused();
      await page.keyboard.press("Control+Home");
      await expect(monday).toBeFocused();
      await page.keyboard.press("ArrowLeft");
      await page.keyboard.press("ArrowUp");
      await expect(monday).toBeFocused();
      await page.keyboard.press("Tab");
      const exact = page.getByRole("button", { name: "Datos exactos", exact: true });
      await expect(exact).toBeFocused();
      await page.keyboard.press("Enter");
      const rows = page.locator(".evidence tbody tr");
      await expect(rows).toHaveCount(3);
      await expect(rows.nth(0).locator("td")).toHaveText(["lunes", "0", "4"]);
      await expect(rows.nth(1).locator("td")).toHaveText(["lunes", "1", "0"]);
      await expect(rows.nth(2).locator("td")).toHaveText(["domingo", "23", "9"]);
      await expect(page.getByText("Sin fila o valor en este resultado", { exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
  });
}

test("una comparación truncada mantiene explícita la ausencia de filas", async ({ page }) => {
  const result = hourWeekdayResult();
  result.truncated = true;
  const grid = await showMatrix(page, result);
  const missing = grid.getByRole("gridcell", { name: "martes, 1:00–1:59: Sin fila en este resultado", exact: true });
  await missing.hover();
  await expect(page.locator(".viz-tip strong")).toHaveText("Sin fila en este resultado");
  await expect(page.getByText("Las celdas rayadas", { exact: false })).toContainText("no equivalen a cero");
});

test("un porcentaje sin valor conserva su estado distinto del cero explícito", async ({ page }) => {
  const result = hourWeekdayResult();
  result.query.metrics = ["external_evidence_pct"];
  result.rows = [{ weekday: 1, event_hour: 0, external_evidence_pct: null }, { weekday: 1, event_hour: 1, external_evidence_pct: 0 }];
  result.row_count = 2;
  const grid = await showMatrix(page, result);
  const missing = grid.getByRole("gridcell", { name: "lunes, 0:00–0:59: Sin valor disponible", exact: true });
  await missing.focus();
  await expect(page.locator(".viz-tip strong")).toHaveText("Sin valor disponible");
  await page.keyboard.press("ArrowRight");
  await expect(grid.getByRole("gridcell", { name: "lunes, 1:00–1:59: 0 %", exact: true })).toBeFocused();
  await expect(page.locator(".viz-tip strong")).toHaveText("0 %");
});
