import { expect, test } from "@playwright/test";
import { proposalCatalog, proposalResults } from "../fixtures/proposals";

test("un área seleccionada en el globo acompaña las preguntas siguientes", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const chats: { question: string; area?: number[][] }[] = [];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const send = (json: unknown) => route.fulfill({ json });
    if (path === "/api/agent/catalog") return send(proposalCatalog);
    if (path === "/api/auth/status") return send({ authenticated: true, email: "prueba@example.com", account_id: "test-owner" });
    if (path === "/api/agent/models") return send({ models: [{ slug: "model-a", display_name: "Modelo A" }], selected: "model-a" });
    if (path === "/api/agent/conversations") return send([]);
    if (path === "/api/agent/certified/CQ_GLOBE") return send(proposalResults.globe);
    if (path === "/api/agent/chat") {
      const body = route.request().postDataJSON();
      chats.push(body);
      return send({ conversation_id: "c-1", turn: { question: body.question, answer: "En el área hay 900 informes.", visualizations: [],
        trace: [], model: "model-a", load_id: "test-load", created_at: "2026-11-24T12:00:00Z", area: body.area } });
    }
    return route.fulfill({ status: 404, json: { detail: "Ruta no simulada" } });
  });
  await page.goto("/agent#consultas-de-ejemplo");
  await page.getByRole("button", { name: "Prueba globo", exact: true }).click();
  await expect(page.locator(".globe-canvas canvas")).toBeVisible();

  await page.getByRole("button", { name: "Rectángulo" }).click();
  const box = (await page.locator(".globe-canvas").boundingBox())!;
  const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
  await page.mouse.move(cx - 60, cy - 60);
  await page.mouse.down();
  await page.mouse.move(cx + 60, cy + 60, { steps: 6 });
  await page.mouse.up();
  const chip = page.locator(".area-chip");
  await expect(chip).toContainText("Área seleccionada activa");
  await expect(chip).toContainText("900 informes del globo");

  const input = page.getByLabel("Pregunta", { exact: true });
  await input.fill("Filtra de 1995 a 1999");
  await page.keyboard.press("Enter");
  await expect(page.locator(".turn-area")).toHaveText("Limitada al área seleccionada en el mapa");
  // The answer brought no new results (retain): the globe stays on screen.
  await expect(page.locator(".globe-canvas canvas")).toBeVisible();
  expect(chats[0].area!.length).toBeGreaterThanOrEqual(4);

  await chip.getByRole("button", { name: "Quitar área" }).click();
  await expect(chip).toHaveCount(0);
  await input.fill("Y en total");
  await page.keyboard.press("Enter");
  await expect.poll(() => chats.length).toBe(2);
  expect(chats[1].area).toBeUndefined();
});
