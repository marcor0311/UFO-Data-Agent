import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { proposalCatalog, proposalResults } from "../fixtures/proposals";

async function open(page: Page, view: string) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = path === "/api/agent/catalog" ? proposalCatalog
      : path === "/api/auth/status" ? { authenticated: false }
      : path === `/api/agent/certified/CQ_${view.toUpperCase()}` ? proposalResults[view] : { detail: "Ruta no simulada" };
    await route.fulfill({ status: "detail" in json ? 404 : 200, json });
  });
  await page.goto("/agent#consultas-de-ejemplo");
  await page.getByRole("button", { name: proposalResults[view].title!, exact: true }).click();
  await expect(page.locator(".result").first()).toBeVisible();
}

async function noViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).include(".results-body").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(violations.flatMap((v) => v.nodes.map((n) => `${v.id} ${n.target.join(" ")}`))).toEqual([]);
}

test("composición al 100 %: porcentaje y conteo por teclado", async ({ page }) => {
  await open(page, "stacked");
  const segment = page.getByRole("group", { name: /Barras apiladas/ }).locator(".mark").first();
  await segment.focus();
  await expect(segment).toHaveAttribute("aria-label", "1990, A: 75 % (30 de 40)");
  await expect(page.locator(".viz-tip strong")).toHaveText("75 %");
  await noViolations(page);
});

test("matriz: ausencia distinta de cero y flechas", async ({ page }) => {
  await open(page, "matrix");
  const grid = page.getByRole("grid");
  await expect(grid.getByRole("gridcell")).toHaveCount(4);
  await grid.getByRole("gridcell", { name: "Estados Unidos, 1990: 100", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  const zero = grid.getByRole("gridcell", { name: "Estados Unidos, 2000: 0", exact: true });
  await expect(zero).toBeFocused();
  await page.keyboard.press("ArrowDown");
  const missing = grid.getByRole("gridcell", { name: "Canadá, 2000: Sin fila en este resultado", exact: true });
  await expect(missing).toBeFocused();
  expect(await missing.getAttribute("fill")).not.toEqual(await zero.getAttribute("fill"));
  await noViolations(page);
});

test("cambio entre períodos: proporciones sobre el total de cada período", async ({ page }) => {
  await open(page, "dumbbell");
  const marks = page.locator(".viz-panel .mark");
  await expect(marks.first()).toHaveAttribute("aria-label", "Luz: 20 % en 1970s, 90 % en 2010s (+70 pp)");   // el mayor cambio primero
  await expect(marks.nth(1)).toHaveAttribute("aria-label", "Disco: 60 % en 1970s, 10 % en 2010s (−50 pp)");
  await expect(page.locator(".dumbbell-help")).toContainText("Por ejemplo, Luz +70 pp: pasó de 20 % a 90 % de los informes. En conclusión, Luz aumenta su aparición en 2010s comparado con 1970s.");
  await expect(page.locator(".dumbbell-help p")).toHaveCount(2);
  await expect(page.locator(".dumbbell-help")).toContainText("No se dibujan los informes sin forma estandarizada (20 % en 1970s y 0 % en 2010s).");
  await expect(page.locator(".viz-panel .mark")).toHaveCount(2);                     // “sin dato” no se dibuja
  await noViolations(page);
});

test("cronología: tarjetas paginadas de ocho", async ({ page }) => {
  await open(page, "timeline");
  const items = page.locator(".timeline-item");
  await expect(items).toHaveCount(8);
  await expect(items.first()).toContainText("10 de marzo de 1997");
  await expect(items.first()).toContainText("2 min, 3 testigos, ID 100");
  await page.getByRole("button", { name: "Siguientes" }).click();
  await expect(items).toHaveCount(2);
  await expect(page.getByText("Página 2 de 2")).toBeVisible();
  await noViolations(page);
});

test("histograma: tramos de 5, 10 y 15 minutos sin perder la cola ni los faltantes", async ({ page }) => {
  await open(page, "histogram");
  await expect(page.locator(".calendar-totals .stat").nth(2)).toContainText("Sin duración declarada40");
  const bars = page.getByRole("group", { name: /Histograma/ }).locator(".mark");
  await expect(bars).toHaveCount(13);
  await expect(bars.first()).toHaveAttribute("aria-label", "0–5 min: 50 informes");
  await page.getByRole("radio", { name: "15 min" }).click();
  await expect(bars).toHaveCount(5);
  await expect(bars.last()).toHaveAttribute("aria-label", "Más de 60 min: 5 informes");
  await noViolations(page);
});

test("duración acumulada: responde el porcentaje hasta cada umbral", async ({ page }) => {
  await open(page, "ecdf");
  await expect(page.locator(".ecdf-answer")).toContainText("83,3 % de los informes con duración declarada duran 5 min o menos (50 de 60)");
  await page.getByRole("radio", { name: "60 min" }).click();
  await expect(page.locator(".ecdf-answer")).toContainText("91,7 %");
  await noViolations(page);
});

test("globo: total por ubicaciones, zoom y pausa del giro", async ({ page }) => {
  await open(page, "globe");
  await expect(page.locator("figcaption").first()).toContainText("1.050 informes con coordenadas aptas en 3 ubicaciones");
  await expect(page.getByRole("img", { name: "Globo con 1.050 informes en 3 ubicaciones" })).toBeVisible();
  await expect(page.locator(".globe-canvas canvas")).toBeVisible();
  await page.getByRole("button", { name: "Acercar" }).click();
  await noViolations(page);
});

test("globo: un rectángulo abre en el mapa 2D y 3D solo lo que queda dentro", async ({ page }) => {
  await open(page, "globe");
  await page.getByRole("button", { name: "Rectángulo" }).click();
  await expect(page.getByRole("button", { name: "Reanudar giro" })).toBeVisible();
  const box = (await page.locator(".globe-canvas").boundingBox())!;
  const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
  await page.mouse.move(cx - 60, cy - 60);
  await page.mouse.down();
  await page.mouse.move(cx + 60, cy + 60, { steps: 6 });
  await page.mouse.up();
  await expect(page.locator(".globe-area figcaption")).toContainText("Área seleccionada: 900 informes en 1 ubicación");
  await expect(page.locator(".globe-area").getByRole("button", { name: "Lazo" })).toBeVisible();
  await page.getByRole("button", { name: "Cerrar área" }).click();
  await expect(page.locator(".globe-area")).toHaveCount(0);
});
