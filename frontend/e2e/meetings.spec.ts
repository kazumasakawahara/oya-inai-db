import { test, expect } from "@playwright/test";

test("meetings form guides through mode selection (audio)", async ({ page }) => {
  await page.goto("/meetings");
  await expect(page.locator("h2")).toContainText("面談記録");

  // 未入力の状態: ボタンは押せず、足りないものが日本語で示される
  const submit = page.getByRole("button", { name: "記録を保存する" });
  await expect(submit).toBeDisabled();
  await expect(page.getByText("あと「① 利用者を選ぶ」と「② 記録のかたちを選ぶ」を済ませると押せます")).toBeVisible();

  // ① クライアントを選ぶとヒントが減る
  await page.getByLabel("利用者を選ぶ").first().selectOption({ index: 1 });
  await expect(page.getByText("あと「② 記録のかたちを選ぶ」を済ませると押せます")).toBeVisible();

  // ② 音声モードを選ぶと③のヒントに変わる
  await page.getByRole("button", { name: /音声ファイルを添付/ }).click();
  await expect(page.getByText("あと「③ 音声ファイルを選ぶ」を済ませると押せます")).toBeVisible();

  // ③ ファイルを選ぶとボタンが押せるようになる
  const fileInput = page.locator('input[type="file"]').first();
  await fileInput.setInputFiles({
    name: "test.mp3",
    mimeType: "audio/mpeg",
    buffer: Buffer.from("dummy audio content"),
  });
  await expect(page.getByText("選べました", { exact: false })).toBeVisible();
  await expect(submit).toBeEnabled();
});

test("meetings form supports direct text input mode", async ({ page }) => {
  await page.goto("/meetings");

  await page.getByLabel("利用者を選ぶ").first().selectOption({ index: 1 });
  await page.getByRole("button", { name: /その場で文字で入力/ }).click();
  await expect(page.getByText("あと「③ 面談の内容を書く」を済ませると押せます")).toBeVisible();

  await page.getByPlaceholder(/4月10日、ご本人・お母様と面談/).fill("面談メモのテスト本文");
  await expect(page.getByRole("button", { name: "記録を保存する" })).toBeEnabled();
});

test("meetings form supports document attachment mode", async ({ page }) => {
  await page.goto("/meetings");

  await page.getByLabel("利用者を選ぶ").first().selectOption({ index: 1 });
  await page.getByRole("button", { name: /文書ファイルを添付/ }).click();
  await expect(page.getByText("あと「③ 文書ファイルを選ぶ」を済ませると押せます")).toBeVisible();

  const fileInput = page.locator('input[type="file"]').first();
  await fileInput.setInputFiles({
    name: "kiroku.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("dummy document content"),
  });
  await expect(page.getByText("選べました", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "記録を保存する" })).toBeEnabled();
});
