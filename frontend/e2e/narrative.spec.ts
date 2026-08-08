import { test, expect } from "@playwright/test";

test("narrative page shows wizard step 1", async ({ page }) => {
  await page.goto("/narrative");
  await expect(page.locator("h2")).toContainText("ナラティブ入力");
  await expect(page.locator("textarea")).toBeVisible();
  await expect(page.locator("text=ファイルを選択")).toBeVisible();
});

test("narrative page shows step progress", async ({ page }) => {
  await page.goto("/narrative");
  await expect(page.locator("text=入力")).toBeVisible();
  await expect(page.locator("text=確認")).toBeVisible();
  await expect(page.locator("text=完了")).toBeVisible();
});
