import { test, expect } from "@playwright/test";

test("dashboard loads with title", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("h2")).toContainText("ダッシュボード");
});

test("dashboard shows stat cards", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("利用者数", { exact: true })).toBeVisible();
  await expect(page.getByText("今月の記録", { exact: true })).toBeVisible();
  await expect(page.getByText("更新期限", { exact: true })).toBeVisible();
});
