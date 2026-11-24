import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { monthCalendarCatalog, monthCalendarResult } from "../fixtures/month-calendar";

async function showCalendar(page: Page) {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = path === "/api/agent/catalog" ? monthCalendarCatalog
      : path === "/api/auth/status" ? { authenticated: false }
      : path === "/api/agent/certified/CQ_TEST_CALENDAR" ? monthCalendarResult() : { detail: "Ruta no simulada" };
    await route.fulfill({ status: "detail" in json ? 404 : 200, json });
  });
  await page.goto("/agent#consultas-de-ejemplo");
  await page.getByRole("button", { name: "Calendario de prueba por año y mes", exact: true }).click();
  const grid = page.getByRole("grid", { name: /Calendario de/ });
  await expect(grid).toBeVisible();
  return grid;
}

for (const viewport of [{ width: 1440, height: 800 }, { width: 1920, height: 1080 }]) {
  test(`calendario año × mes a ${viewport.width}×${viewport.height}: teclado, ceros y años sin filas`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    const grid = await showCalendar(page);
    await expect(grid.getByRole("row")).toHaveCount(3);               // 1996, 1997 (sin filas) y 1998
    await expect(grid.getByRole("gridcell")).toHaveCount(42);              // 12 meses + “Sin mes” + “Total”
    const totals = page.locator(".calendar-totals");
    await expect(totals.locator(".stat").nth(0)).toContainText("Informes en el período19");
    await expect(totals.locator(".stat").nth(1)).toContainText("Con mes conocido17");
    await expect(totals.locator(".stat").nth(2)).toContainText("Mes desconocido2");
    await expect(page.locator("figcaption").filter({ hasText: "(1996–1998)" })).toBeVisible();

    const january = grid.getByRole("gridcell", { name: "enero de 1996: 5", exact: true });
    await january.focus();
    await expect(page.locator(".viz-tip strong")).toHaveText("5");
    await page.keyboard.press("ArrowRight");
    const zero = grid.getByRole("gridcell", { name: "febrero de 1996: 0", exact: true });
    await expect(zero).toBeFocused();
    await page.keyboard.press("ArrowDown");
    const missing = grid.getByRole("gridcell", { name: "febrero de 1997: Sin fila en este resultado", exact: true });
    await expect(missing).toBeFocused();
    expect(await missing.getAttribute("fill")).not.toEqual(await zero.getAttribute("fill"));
    await page.keyboard.press("Control+End");
    await expect(grid.getByRole("gridcell", { name: "Total de 1998: 12", exact: true })).toBeFocused();
    await page.keyboard.press("ArrowLeft");
    await expect(grid.getByRole("gridcell", { name: "Mes desconocido en 1998: 0 (no se puede calcular su mes)", exact: true })).toBeFocused();
    await page.keyboard.press("ArrowUp");
    await page.keyboard.press("ArrowUp");
    await expect(grid.getByRole("gridcell", { name: "Mes desconocido en 1996: 2 (no se puede calcular su mes)", exact: true })).toBeFocused();
    await page.keyboard.press("ArrowRight");
    await expect(grid.getByRole("gridcell", { name: "Total de 1996: 7", exact: true })).toBeFocused();
    await page.keyboard.press("Control+Home");
    await expect(january).toBeFocused();

    await expect(page.getByText(/cuyo mes no se puede calcular/)).toBeVisible();
    await page.getByRole("button", { name: "Datos exactos", exact: true }).click();
    await expect(page.getByRole("cell", { name: "12", exact: true })).toBeVisible();
    await expect(page.getByRole("cell", { name: "1998", exact: true }).first()).toBeVisible();
    await expect(page.getByRole("cell", { name: "Mes desconocido", exact: true })).toHaveCount(2);   // un año no lleva separador de miles

    const { violations } = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    expect(violations.flatMap((v) => v.nodes.map((n) => `${v.id} ${n.target.join(" ")} ${n.failureSummary}`))).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath("calendar.png"), fullPage: true });
  });
}
