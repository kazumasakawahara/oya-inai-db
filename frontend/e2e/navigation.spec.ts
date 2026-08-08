import { test, expect } from "@playwright/test";

test("sidebar navigation works", async ({ page }) => {
  await page.goto("/");

  await page.click("text=クライアント一覧");
  await expect(page).toHaveURL("/clients");
  await expect(page.locator("h2")).toContainText("クライアント一覧");

  await page.click("text=ナラティブ入力");
  await expect(page).toHaveURL("/narrative");
  await expect(page.locator("h2")).toContainText("ナラティブ入力");

  await page.click("text=AIチャット");
  await expect(page).toHaveURL("/chat");
  await expect(page.locator("h2")).toContainText("AIチャット");

  await page.click("text=LLM設定");
  await expect(page).toHaveURL("/settings");
  await expect(page.locator("h2")).toContainText("LLM設定");
});

test("sidebar shows system status", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("text=Ollama")).toBeVisible();
  await expect(page.locator("text=Neo4j")).toBeVisible();
});
