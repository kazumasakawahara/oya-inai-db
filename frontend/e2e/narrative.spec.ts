import { test, expect } from "@playwright/test";

test("narrative page shows wizard step 1", async ({ page }) => {
  await page.goto("/narrative");
  await expect(page.locator("h2")).toContainText("ナラティブ入力");
  await expect(page.locator("textarea")).toBeVisible();
  await expect(page.locator("text=ここを押してファイルを選ぶ")).toBeVisible();
});

test("narrative page shows step progress", async ({ page }) => {
  await page.goto("/narrative");
  await expect(page.getByText("入力", { exact: true })).toBeVisible();
  await expect(page.getByText("確認", { exact: true })).toBeVisible();
  await expect(page.getByText("完了", { exact: true })).toBeVisible();
});
