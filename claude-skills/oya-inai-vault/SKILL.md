---
name: oya-inai-vault
description: 仕分け済みの語りを Obsidian Vault（oya-inai-wiki 系）へ落とす子スキル。raw/ への原本保存（append-only・sha256 算出）、templates/ に沿ったページ生成、okf_lint.py の関所、log.md への追記までを手続きとして担う。親スキル oya-inai-intake から仕分け YAML を受けて呼ばれるほか、「Obsidian に書いて」「Vault に保存して」「ページにして」などの発言時に単独でも必ずこのスキルを使用すること。
---

# oya-inai-vault — Obsidian への手続き（子）

## 最上位規則 — No Fabrication（親から継承）

**語りに無いことをページに書かない。空欄は空欄のまま残す。**「たぶんこうだろう」で埋めた1行が、後から事実として引き継がれる。テンプレートの項目が埋まらないことは失敗ではない。

## 役割と境界

**本スキルは手続きだけを持つ。**どの事実がどこへ落ちるかの判断は親（`oya-inai-intake`）と、その参照先 `reference/dual-intake-routing.md` が担う。

- 入力: 親スキルの仕分け YAML（`person` / `source` / `to_vault`）、または人の直接指示
- 単独起動で判断が必要になったら、自分で判断せず**親スキルの手順を先に通す**
- 実名を扱わない: ページ本文・frontmatter・ファイル名のいずれにも**実名を書かない**（仮名と `person_id` のみ。実名が要る事実は Neo4j 側 `oya-inai-neo4j` の領分）

## 書き込み前の安全確認（毎回）

1. **Obsidian が起動していないことを確認する**: `pgrep -x Obsidian`。起動中に外部から Vault へ書き込むと**サイレントに巻き戻る**事故が実発生している（Vault log.md 2026-07-27）。起動中なら人に閉じてもらってから進む
2. 対象 Vault のルート（`schema.md` と `scripts/okf_lint.py` がある場所）を確認する

## 手順

### Step 1 — raw/ への原本保存（append-only）

1. 親 YAML の `source.shelf` の棚へ原本を保存する
2. **append-only を厳守**: 既存ファイルの書き換え・削除は絶対にしない。同名ファイルが既にある場合は、既存に触れず**別名**（`_2` 等の連番付与）で保存する
3. ファイル名は `YYYY-MM-DD_種類_person_id.md` の形を基本とし、**実名を入れない**
4. 添付ファイル（.docx .pdf 等）は**変換せず元ファイルのまま**保存する（Markdown 化した写しを追加で置くのは可。ただし原本はあくまで元ファイル）
5. **sha256 は「保存した原本ファイルのバイト列」に対して算出する**（`shasum -a 256` 相当）。テキスト抽出後・文字コード変換後・整形後の内容をハッシュしてはならない。ハッシュは保存直後に算出し、以後この値を `source_hash` として使う
6. **複数本人が登場する語りでも、原本の保存は1回だけ**（1ファイル・1ハッシュ）。person ごとに raw/ へ複製しない。各 person のページには**同じ `source_hash`** を書く
7. 算出した sha256 を親の YAML（`source.sha256`）へ反映する

### Step 2 — 型に沿ったページ生成

1. `templates/` の該当型の雛形から生成する（自作の構成にしない）
2. frontmatter は `schema.md` §1・§2 に従う。最低限:
   - 必須7項目（`type` `created` `updated` `sources` `tags` `status` `sensitivity`）
   - `sources` に Step 1 で保存した raw/ ファイルへの参照
   - `source_hash` に Step 1 の sha256（**任意フィールドだが、本スキル経由の生成では必ず書く**——両系突合の橋）
   - `provided_by` / `share_scope`（親 YAML の値）
   - 型別の必須（`person_id`、meeting は `person_ids`、日付フィールド、sensitive 以上は `sensitive_purpose`）
3. 既存ページの更新（手順書＝protocol の変化など）は、**旧記述を消さず「変化の記録」として残す**形で追記する
4. 本文は語りにある表現だけで書く。要約はしてよいが、**補完はしない**

### Step 3 — lint の関所（ERROR なら完了としない）

1. Vault ルートで `python3 scripts/okf_lint.py --gate` を実行する
2. 出力の「N ページを検査」で**検査が実際に走ったこと**を確認する（0件検査は合格ではない）
3. **終了コードが 0 以外（ERROR あり）の間は、書き込みを「完了」と報告しない。**ERROR の内容を示し、修正して再実行するか、人の指示を仰ぐ
4. WARN は作業を止めないが、報告に含める

### Step 4 — log.md への追記

1. Vault の `log.md` 末尾に、既存の書式（`## 日付 | 種別 | 見出し`）で1エントリ追記する
2. **振り分けの判断根拠を1行含める**（例:「支援者の行為を禁じる言い方のため禁忌側、本人の反応は trigger 側」）
3. **raw/ の実ファイル名はチャットに出さない**（既存ファイル名は実名を含みうる）。チャットへの報告は**棚と件数**で行う

### 完了報告の形式（黙認方式）

```
Vault へ保存しました。
　原本 → raw/10_本人・家族から/（1件、sha256: 83c8464…）
　生成 → trigger 2枚・手順書（protocol）1枚（P_900）
　lint → 14 ページ検査・ERROR 0（WARN 1: 鮮度）
　log.md → 1行追記
訂正があれば教えてください。
```

宣言して進み、訂正があれば従う（質問は最大1点）。**Neo4j 側と違い、人の事前承認は不要**（実名を扱わないため。承認の非対称は親スキル参照）。

## 禁止事項（再掲）

- raw/ の既存ファイルの書き換え・削除（append-only）
- 語りに無い内容の補完
- 実名の記入（本文・frontmatter・ファイル名）
- ERROR が残った状態での完了報告
- Obsidian 起動中の書き込み

## 関連

- 親スキル: `oya-inai-intake`（仕分けの判断・YAML の出所）
- 兄弟スキル: `oya-inai-neo4j`（Neo4j への構造化登録・人の確認必須）
- 構造の正典: Vault の `schema.md`／棚構成は `CLAUDE.md` §1／検査は `scripts/okf_lint.py`
