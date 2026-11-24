import { expect, test, type Page } from "@playwright/test";
import type { Turn } from "../../src/lib/contracts";
import { rollupCatalog, rollupResult } from "../fixtures/rollup";

function turn(index: number, long = false): Turn {
  const result = rollupResult(false);
  result.title = `Resultado ${index}`;
  result.view = result.query.view = "table";
  result.total = null;
  result.query.metrics = ["report_count"];
  result.query.rollup = false;
  result.rows = Array.from({ length: long ? 80 : 2 }, (_, i) => ({ source_code: `Fuente ${i + 1}`, report_count: index * 10 + i }));
  result.row_count = result.rows.length;
  return { question: `Pregunta ${index}`, answer: `Respuesta de prueba ${index}.`, visualizations: [result],
    trace: [], model: "test-model", load_id: "test-load", created_at: `2026-11-23T12:00:0${index}Z` };
}

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => { resolve = done; });
  return { promise, resolve };
}

async function setup(page: Page) {
  const replies: { requested: ReturnType<typeof deferred>; release: ReturnType<typeof deferred>; next: Turn; fail: boolean }[] = [];
  let nextRequest = 0;
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const send = (json: unknown, status = 200) => route.fulfill({ status, json });
    if (path === "/api/agent/catalog") return send(rollupCatalog);
    if (path === "/api/auth/status") return send({ authenticated: true, email: "prueba@example.com", account_id: "test-owner" });
    if (path === "/api/agent/models") return send({ models: [{ slug: "test-model", display_name: "Modelo de prueba" }], selected: "test-model" });
    if (path === "/api/agent/conversations") return send([
      { conversation_id: "history-1", title: "Historial de prueba", turns: 2, updated: 1 },
      { conversation_id: "history-2", title: "Otra conversación", turns: 1, updated: 2 },
    ]);
    if (path === "/api/agent/conversations/history-1") return send({ turns: [turn(1, true), turn(2)] });
    if (path === "/api/agent/conversations/history-2") return send({ turns: [turn(5)] });
    if (path === "/api/agent/chat") {
      const reply = replies[nextRequest++];
      if (!reply) return send({ detail: "No se preparó una respuesta de prueba" }, 500);
      reply.requested.resolve();
      await reply.release.promise;
      return reply.fail ? send({ detail: "Interrupción de prueba" }, 503) : send({ conversation_id: "history-1", turn: reply.next });
    }
    return send({ detail: `Ruta no simulada: ${path}` }, 404);
  });
  await page.goto("/agent");
  await expect(page.getByRole("button", { name: "Cerrar sesión", exact: true })).toBeVisible();
  const history = page.locator("summary").filter({ hasText: /^Historial$/ });
  await history.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "Historial de prueba (2)", exact: true })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Historial de prueba (2)", exact: true })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Respuesta 2 de 2", exact: true })).toBeVisible();
  return {
    queue(next: Turn, fail = false) {
      const reply = { next, fail, requested: deferred(), release: deferred() };
      replies.push(reply);
      return reply;
    },
  };
}

async function selectEarlier(page: Page) {
  await page.getByRole("button", { name: "Pregunta 1 (ver resultado)", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Respuesta 1 de 2", exact: true })).toBeFocused();
  const exact = page.getByRole("button", { name: "Datos exactos", exact: true });
  await exact.focus();
  await page.keyboard.press("Enter");
  await expect(exact).toHaveAttribute("aria-expanded", "true");
  await page.locator(".results-body").evaluate((element) => {
    const stack = element.querySelector<HTMLElement>(".results-stack")!;
    stack.dataset.readingMarker = "preserved";
  });
}

async function readingPosition(page: Page, move = false) {
  return page.locator(".results-body").evaluate((element, move) => {
    if (getComputedStyle(element).overflowY === "visible") {
      const anchor = element.querySelector("tbody tr:nth-child(12)")!;
      if (move) anchor.scrollIntoView({ block: "center", behavior: "instant" });
      return anchor.getBoundingClientRect().top;
    }
    if (move) element.scrollTop = 450;
    return element.scrollTop;
  }, move);
}

for (const zoom of [1, 2]) {
  test.describe(`Portátil 1280×720 al ${zoom * 100} %`, () => {
    // At 200%, the same physical window has a 640×360 CSS viewport.
    test.use({ viewport: { width: 1280 / zoom, height: 720 / zoom }, deviceScaleFactor: zoom });
    for (const selection of ["antes", "durante"] as const) {
      test(`conserva selección, evidencia y lectura (${selection === "antes" ? "selección antes de consultar" : "selección durante la consulta"})`, async ({ page }, testInfo) => {
        const mock = await setup(page);
        const reply = mock.queue(turn(3));
        if (selection === "antes") await selectEarlier(page);
        await page.getByRole("textbox", { name: "Pregunta", exact: true }).fill("Nueva consulta");
        await page.keyboard.press("Enter");
        await reply.requested.promise;
        if (selection === "durante") await selectEarlier(page);
        const reading = await readingPosition(page, true);
        expect(reading).toBeGreaterThan(0);
        await expect(page.locator(".results-stack")).toHaveAttribute("data-reading-marker", "preserved");
        expect(await readingPosition(page)).toBeCloseTo(reading, 0);
        reply.release.resolve();
        const heading = page.getByRole("heading", { name: "Respuesta 1 de 3", exact: true });
        await expect(heading).toBeVisible();
        await expect(page.getByRole("button", { name: "Pregunta 1 (ver resultado)", exact: true })).toHaveAttribute("aria-pressed", "true");
        await expect(page.locator(".results-stack")).toHaveAttribute("data-reading-marker", "preserved");
        await expect(page.getByRole("button", { name: "Datos exactos", exact: true })).toHaveAttribute("aria-expanded", "true");
        expect(await readingPosition(page)).toBeCloseTo(reading, 0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        await page.screenshot({ path: testInfo.outputPath("history-selection.png"), fullPage: true });

        // Continue entirely by keyboard: previous result -> latest -> question.
        await heading.focus();
        await page.screenshot({ path: testInfo.outputPath("history-controls.png") });
        await page.keyboard.press("Tab");
        await expect(page.getByRole("button", { name: "Volver al último resultado", exact: true })).toBeFocused();
        await page.keyboard.press("Enter");
        await expect(page.getByRole("heading", { name: "Respuesta 3 de 3", exact: true })).toBeFocused();
        await expect(page.getByRole("button", { name: "Pregunta 3 (ver resultado)", exact: true })).toHaveAttribute("aria-pressed", "true");
        expect(await page.locator(".results-body").evaluate((el) => el.scrollTop)).toBe(0);
        await page.keyboard.press("Tab");
        await expect(page.getByRole("button", { name: "Ir a la pregunta", exact: true })).toBeFocused();
        await page.keyboard.press("Enter");
        await expect(page.getByRole("textbox", { name: "Pregunta", exact: true })).toBeFocused();
        const followUp = mock.queue(turn(4));
        await page.keyboard.type("Seguimiento automático");
        await page.keyboard.press("Enter");
        await followUp.requested.promise;
        followUp.release.resolve();
        await expect(page.getByRole("heading", { name: "Respuesta 4 de 4", exact: true })).toBeVisible();
      });
    }
  });
}

test("un error conserva el resultado anterior y su posición de lectura", async ({ page }) => {
  const mock = await setup(page);
  await selectEarlier(page);
  const reply = mock.queue(turn(3), true);
  await page.getByRole("textbox", { name: "Pregunta", exact: true }).fill("Consulta fallida");
  await page.keyboard.press("Enter");
  await reply.requested.promise;
  const reading = await readingPosition(page, true);
  reply.release.resolve();
  await expect(page.getByRole("alert").filter({ hasText: "Interrupción de prueba" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Respuesta 1 de 2", exact: true })).toBeVisible();
  await expect(page.locator(".results-stack")).toHaveAttribute("data-reading-marker", "preserved");
  expect(await page.locator(".results-body").evaluate((el) => el.scrollTop)).toBeCloseTo(reading, 0);
});

test("abrir otra conversación restablece el seguimiento del último resultado", async ({ page }) => {
  await setup(page);
  await selectEarlier(page);
  await page.locator("summary").filter({ hasText: /^Historial$/ }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Otra conversación (1)", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Respuesta 1 de 1", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Volver al último resultado", exact: true })).toHaveCount(0);
  expect(await page.locator(".results-body").evaluate((el) => el.scrollTop)).toBe(0);
});
