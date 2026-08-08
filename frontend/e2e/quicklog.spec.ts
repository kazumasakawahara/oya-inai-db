import { test, expect } from "@playwright/test";

test("quicklog guides through emotion and scene selection", async ({ page }) => {
  await page.goto("/quicklog");
  await expect(page.locator("h2")).toContainText("出来事の記録");

  // 未入力の状態: ボタンは押せず、足りないものが日本語で示される
  const submit = page.getByRole("button", { name: "記録する" });
  await expect(submit).toBeDisabled();
  await expect(
    page.getByText(
      "あと「① 利用者を選ぶ」と「② 本人の様子を選ぶ」と「③ 場面を選ぶ」と「④ くわしく書く」を済ませると押せます"
    )
  ).toBeVisible();

  // ① 利用者を選ぶ（一覧の読み込み完了を aria-label 付き select で待つ）
  await page.getByLabel("利用者を選ぶ").selectOption({ index: 1 });

  // ② 本人の様子を大ボタンで選ぶ（平常状態の選択肢は無い）
  await expect(page.getByText("落ち着いていた")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /固まってしまった・動けなくなった/ })).toBeVisible();
  await page.getByRole("button", { name: /パニックになった・強くおびえていた/ }).click();

  // ③ 場面を選ぶ
  await page.getByLabel("場面を選ぶ").selectOption({ label: "食事のとき" });
  await expect(page.getByText("あと「④ くわしく書く」を済ませると押せます")).toBeVisible();

  // ④ くわしく書くとボタンが押せるようになる
  await page.getByPlaceholder(/昼食の配膳が遅れたとき/).fill("テスト記録の本文");
  await expect(submit).toBeEnabled();
});

test("quicklog shows optional staff response step", async ({ page }) => {
  await page.goto("/quicklog");
  await expect(page.getByText("職員はどう対応しましたか")).toBeVisible();
  await expect(page.getByRole("button", { name: "うまくいった" })).toBeVisible();
  await expect(page.getByRole("button", { name: "どちらともいえない" })).toBeVisible();
  await expect(page.getByRole("button", { name: "うまくいかなかった" })).toBeVisible();
});
