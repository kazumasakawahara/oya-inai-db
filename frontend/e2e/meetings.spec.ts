import { test, expect } from "@playwright/test";

test("meetings upload guides the user step by step", async ({ page }) => {
  await page.goto("/meetings");
  await expect(page.locator("h2")).toContainText("面談記録");

  // 未入力の状態: ボタンは押せず、足りないものが日本語で示される
  const submit = page.getByRole("button", { name: "アップロードする" });
  await expect(submit).toBeDisabled();
  await expect(page.getByText("あと「① 利用者を選ぶ」と「② 音声ファイルを選ぶ」を済ませると押せます")).toBeVisible();

  // ① クライアントを選ぶとヒントが減る
  await page.locator("select").first().selectOption({ index: 1 });
  await expect(page.getByText("あと「② 音声ファイルを選ぶ」を済ませると押せます")).toBeVisible();

  // ② ファイルを選ぶとボタンが押せるようになる
  const fileInput = page.locator('input[type="file"]').first();
  await fileInput.setInputFiles({
    name: "test.mp3",
    mimeType: "audio/mpeg",
    buffer: Buffer.from("dummy audio content"),
  });
  await expect(page.getByText("選べました", { exact: false })).toBeVisible();
  await expect(submit).toBeEnabled();
});
