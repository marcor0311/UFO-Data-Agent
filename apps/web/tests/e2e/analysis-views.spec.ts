import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import fixture from "../fixtures/analysis-results.json";

/* Every view added for the measures of query_gold and the analyses of analyze, rendered
   with results computed by the real engine (tests/fixtures/analysis-results.json). */
type Result = { title: string; view: string };
const results = fixture.results as unknown as Record<string, Result>;
const shots = process.env.ANALYSIS_SHOTS;

async function open(page: Page, id: string) {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = path === "/api/agent/catalog" ? fixture.catalog
      : path === "/api/auth/status" ? { authenticated: false }
      : path.startsWith("/api/agent/certified/") ? results[path.split("/").pop()!] : { detail: "Ruta no simulada" };
    await route.fulfill({ status: json && !("detail" in (json as object)) ? 200 : 404, json });
  });
  await page.route("https://**/*", (route) => route.abort());  // no map tiles in tests
  await page.goto("/agent#consultas-de-ejemplo");
  await page.getByRole("button", { name: results[id].title, exact: true }).click();
  await expect(page.locator(".result").first()).toBeVisible();
}

async function noViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).include(".results-body").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(violations.flatMap((v) => v.nodes.map((n) => `${v.id} ${n.target.join(" ")}`))).toEqual([]);
}

for (const [id, result] of Object.entries(results)) {
  test(`${result.view}: ${result.title}`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await open(page, id);
    const panel = page.locator(".result .viz, .result .stat-grid, .result .viz-table").first();
    await expect(panel).toBeVisible();
    await expect(page.locator(".result .viz-empty")).toHaveCount(0);
    const mark = page.locator(".result .mark").first();
    if (await mark.count()) {
      await mark.focus().catch(() => undefined);
    }
    if (shots) await page.locator(".result").first().screenshot({ path: `${shots}/${id.toLowerCase()}.png` });
    expect(errors).toEqual([]);
    await noViolations(page);
  });
}
