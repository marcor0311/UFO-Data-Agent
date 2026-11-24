import { expect, test } from "@playwright/test";
import type { Turn } from "../../src/lib/contracts";
import { countryMapCatalog, countryMapResult } from "../fixtures/country-map";

/* With a session, an example is saved in the conversation, so the next question carries it as context. */
test("con sesión, el ejemplo entra en la conversación y la siguiente pregunta continúa en ella", async ({ page }) => {
  const seeded: unknown[] = [];
  const chats: { conversation_id?: string; question: string }[] = [];
  const example: Turn = { question: "Mapa de prueba por país", answer: "Ejemplo.", visualizations: [countryMapResult()],
    trace: [{ tool: "run_certified", ok: true }], model: "", load_id: "test-load", created_at: "2026-11-24T12:00:00Z" };
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const send = (json: unknown) => route.fulfill({ status: 200, json });
    if (path === "/api/agent/catalog") return send(countryMapCatalog);
    if (path === "/api/auth/status") return send({ authenticated: true, email: "prueba@example.com", account_id: "test-owner" });
    if (path === "/api/agent/models") return send({ models: [{ slug: "test-model", display_name: "Modelo de prueba" }], selected: "test-model" });
    if (path === "/api/agent/conversations") return send([]);
    if (path === "/api/agent/conversations/examples/CQ_TEST_COUNTRY_MAP") {
      seeded.push(route.request().postDataJSON());
      return send({ conversation_id: "ejemplo-1", turns: [example] });
    }
    if (path === "/api/agent/chat") {
      chats.push(route.request().postDataJSON());
      return send({ conversation_id: "ejemplo-1", turn: { ...example, question: "¿Y solo en Costa Rica?", answer: "Seguimiento.", visualizations: [] } });
    }
    return route.fulfill({ status: 404, json: { detail: "Ruta no simulada" } });
  });

  await page.goto("/agent#consultas-de-ejemplo");
  await page.getByRole("button", { name: "Mapa de prueba por país", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Respuesta 1 de 1", exact: true })).toBeVisible();
  expect(seeded).toEqual([{ conversation_id: null }]);

  const input = page.getByLabel("Pregunta", { exact: true });
  await input.fill("¿Y solo en Costa Rica?");
  await page.keyboard.press("Enter");
  await expect(page.getByText("Seguimiento.", { exact: true })).toBeVisible();
  expect(chats).toEqual([expect.objectContaining({ question: "¿Y solo en Costa Rica?", conversation_id: "ejemplo-1" })]);
});
