import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import type { Turn } from "../../src/lib/contracts";
import { rollupCatalog, rollupResult } from "../fixtures/rollup";

const models = [
  { slug: "model-a", display_name: "Modelo A" },
  { slug: "model-b", display_name: "Modelo B" },
];

function turn(question: string, model: string): Turn {
  const result = rollupResult(false);
  result.title = "Informes por fuente";
  return { question, answer: "Respuesta de prueba.", visualizations: [result], trace: [{ tool: "run_certified", ok: true }],
    model, load_id: "test-load", created_at: "2026-11-23T12:00:00Z" };
}

async function mockApi(page: Page, authenticated: boolean) {
  const chats: { question: string; model: string | null }[] = [];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const send = (json: unknown, status = 200) => route.fulfill({ status, json });
    if (path === "/api/agent/catalog") return send(rollupCatalog);
    if (path === "/api/auth/status") return send(authenticated
      ? { authenticated: true, email: "prueba@example.com", account_id: "test-owner" } : { authenticated: false });
    if (path === "/api/agent/models") return send({ models, selected: "model-a" });
    if (path === "/api/agent/conversations") return send([]);
    if (path === "/api/agent/chat") {
      const body = route.request().postDataJSON() as { question: string; model: string | null };
      chats.push(body);
      return send({ conversation_id: "c-1", turn: turn(body.question, body.model ?? "") });
    }
    return send({ detail: `Ruta no simulada: ${path}` }, 404);
  });
  return chats;
}

async function expectNoViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
}

for (const viewport of [{ width: 1440, height: 800 }, { width: 1440, height: 1000 }, { width: 1920, height: 1080 }]) {
  test(`portada sin infracciones WCAG AA a ${viewport.width}×${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await mockApi(page, false);
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Entrar al Data Agent" })).toBeVisible();
    await expectNoViolations(page);
  });
}

test("agente sin sesión: sin infracciones y acceso visible", async ({ page }) => {
  await mockApi(page, false);
  await page.goto("/agent");
  await expect(page.getByRole("link", { name: "Continuar con ChatGPT" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Enviar pregunta" })).toBeDisabled();
  await expectNoViolations(page);
});

test("el modelo elegido viaja con cada pregunta y el resultado es accesible", async ({ page }) => {
  const chats = await mockApi(page, true);
  await page.goto("/agent");
  const input = page.getByLabel("Pregunta", { exact: true });
  const select = page.getByLabel("Modelo");
  await expect(select).toHaveValue("model-a");

  await input.fill("Primera pregunta");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: /Primera pregunta/ })).toBeVisible();

  await select.selectOption("model-b");
  await input.fill("Segunda pregunta");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: /Segunda pregunta/ })).toBeVisible();

  expect(chats).toEqual([
    expect.objectContaining({ question: "Primera pregunta", model: "model-a" }),
    expect.objectContaining({ question: "Segunda pregunta", model: "model-b" }),
  ]);
  await expectNoViolations(page);
});

test("Shift+Enter añade una línea sin enviar", async ({ page }) => {
  const chats = await mockApi(page, true);
  await page.goto("/agent");
  const input = page.getByLabel("Pregunta", { exact: true });
  await expect(page.getByLabel("Modelo")).toHaveValue("model-a");
  await input.fill("Línea uno");
  await page.keyboard.press("Shift+Enter");
  await page.keyboard.type("Línea dos");
  await expect(input).toHaveValue("Línea uno\nLínea dos");
  expect(chats).toEqual([]);
});
