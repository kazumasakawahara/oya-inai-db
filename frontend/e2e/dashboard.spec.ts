import { test, expect } from "@playwright/test";

test("dashboard loads with title", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("h2")).toContainText("ダッシュボード");
});

test("dashboard shows stat cards", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("text=利用者数")).toBeVisible();
  await expect(page.locator("text=今月の記録")).toBeVisible();
  await expect(page.locator("text=更新期限")).toBeVisible();
});
