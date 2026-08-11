# HANDOVER — 2026-08-10 単一インテーク・スキル層（実装フェーズ）

> **このファイルは Claude Code が最初に読むもの**です。oya-inai-db の既存 `HANDOVER.md`（Track A Phase 1 の続き）とは**別件**なので、混同しないでください。両方が並行します。

## 再開コマンド（コピペで動く）

```bash
# 主作業ディレクトリ
cd ~/Dev-Work/oya-inai-db

# 設計文書はすべて oya-inai-wiki の docs/ にある（正典・編集しない、読むだけ）
ls ~/Obsidian/oya-inai-wiki/docs/ | grep -E 'dual-intake|skill-layer'

# 四者一致チェッカー（DRIFT-13 で修正済み。素の python3 でも完走する）
python3 scripts/check_semantic_drift.py     # 期待: OK=30 KNOWN=0 FAIL=0 WARN=1

# テスト
./.venv/bin/python -m pytest api/tests -q   # 期待: 450 passed, 1 failed
# ↑ 落ちる1件 test_meetings.py::test_upload_unsupported_format は main でも落ちる既存負債。触らない

# Neo4j 検証台（本番 nest-support とは port 7687 を共有し同時起動できない）
docker compose up -d neo4j
docker exec -e LC_ALL=C.UTF-8 oya-inai-db-neo4j cypher-shell -u neo4j -p password 'RETURN 1;'
# 終わったら: docker compose stop neo4j

# Vault 側の検証台（配布テンプレートのクローン）
cd ~/Dev-Work/sandbox-dual-intake && python3 scripts/okf_lint.py    # 期待: 違反なし
```

## 作業ディレクトリの指定

**主**: `~/Dev-Work/oya-inai-db`

理由——実装の主戦場（スキル3本の設置先）であり、`.venv`・テスト・`CLAUDE.md`・git remote が揃っている。Obsidian Vault を作業ディレクトリにすると、Vault の CLAUDE.md（**相談支援専門員の運用マニュアル**であって開発の指示書ではない）が読み込まれ、文脈が噛み合わない。

**追加で許可が要るディレクトリ**（`--add-dir` 等で）:

| パス | 用途 | 権限 |
|---|---|---|
| `~/Obsidian/oya-inai-wiki` | **設計文書の正典**（docs/）。Phase A で `schema.md` と `scripts/okf_lint.py` を改修 | 読み書き |
| `~/Dev-Work/oya-inai-keikaku-soudan` | 配布テンプレート。Phase A の改修を写す | 読み書き |
| `~/Dev-Work/sandbox-dual-intake` | 検証台（配布版のクローン）。壊してよい | 読み書き |
| `~/Dev-Work/project/nest-support` | **移植元**（`claude-skills/narrative-extractor`） | **読み取りのみ。本番なので書かない** |

## 現在地

- **目標**: 「人が語りを渡し、AI が Obsidian と Neo4j へ仕分け、人がチャットで答えを引き出す」——これをスキル3本として実装し、oya-inai-db から配布する
- **進捗**:
  - [x] 設計完了（要件書 v1.0・技術仕様 v1.0・実装計画 A〜G・ADR-D1〜D11）。**すべて河原さん承認済み**
  - [x] DRIFT-13 解消（oya-inai-db main `e5ed2a6`、shared-schema 台帳登録 `6bafc6f`）
  - [x] 検証の教材（架空の語り5本＋仕分け宣言5本）が `oya-inai-keikaku-soudan/記入例/語りの例/` にある
  - [x] **Phase A**（`source_hash` の器を用意。後方互換を壊さない）— 2026-08-11 完了。本家 Vault `3ab738b`・配布テンプレート `10feab3`（未 push）。記入例14枚の lint 通過（後方互換）・テスト23ケース green を確認済み
  - [x] Phase B（親スキル `oya-inai-intake`）— 2026-08-11 完了。`claude-skills/oya-inai-intake/SKILL.md`（oya-inai-db `94a17f9`）。語り5本で棚推定5/5・仕分け宣言との突合一致（差分3点は下記「Phase B の発見」）。B-4（採番の実挙動）は Neo4j 起動を伴うため Phase E で検証
  - [ ] Phase C（子 `oya-inai-vault`・新規）← **ここから**
  - [ ] Phase D（子 `oya-inai-neo4j`・移植＋**削る**）
  - [ ] Phase E（通し検証）／F（配布物）／G（記録）

## 必読（この順に）

1. `~/Obsidian/oya-inai-wiki/docs/skill-layer-plan.md` — **実装計画。タスクと検証方法**
2. `~/Obsidian/oya-inai-wiki/docs/skill-layer-tech-spec.md` — 技術仕様。スキル3本の責務境界
3. `~/Obsidian/oya-inai-wiki/docs/dual-intake-routing.md` — **仕分けの判断規則（最上位）**。正本表22行
4. `~/Obsidian/oya-inai-wiki/docs/dual-intake-adr.md` — ADR-D1〜D11。**未決論点は末尾**
5. `~/Dev-Work/project/nest-support/claude-skills/narrative-extractor/SKILL.md` — 移植元337行

## グレーな判断（河原さんの事前承認なしに私が決めたもの）

いずれも技術仕様 §0 に根拠を残してあります。**違和感があれば戻してください。**

1. **`source_hash` は frontmatter の任意フィールド**にした（必須にすると連携しない単独運用者に書けない値を要求する／raw/ の記録だけでは git 管理外で突合できない、の両立点）
2. **配布は `oya-inai-db/claude-skills/` を新設**（既存の `skills/` は agno スタック用。性質の違うものを同じ名前に混ぜない）
3. **`clientId` の後付けは手順書＋確認クエリまで**。一括スクリプトは作らない（support-db-write-gate §4 の完全一致原則）

## Phase B の発見と追加判断（2026-08-11・要追認）

**実装中に決めた判断3件**（技術仕様 §7「実装中に決める」の消し込み。違和感があれば戻す）:

1. **出力 YAML は会話上のみ**（ファイルに落とさない）。訂正は会話で行われるため、会話に見えていることが訂正可能性の担保。ファイルは正典と乖離しうる第2のコピーになる
2. **添付ファイルは親が読む**。仕分けの判断に内容が要るため。raw/ への原本保存と sha256 算出は oya-inai-vault の手続き
3. **複数本人は person ごとに YAML を分ける**。meeting ページのみ `person_ids` 複数可（実挙動の検証は E-3）

**教材との差分3点**（いずれもスキルの欠陥ではなく教材側の記録の性質）:

- 仕分け宣言①の生育歴行が一本化決定**前**の記録（LifeHistory 併記）→ 現行規則の注記を追加済み（テンプレート `f810f09`・**未 push**）
- 仕分け宣言④に「原本 → raw/」の行がない（定型の省略）。スキルは raw/70_自分の作成物/ を出す
- 仕分け宣言④が語り末尾の受給者証（10月末期限・更新案内）に触れていない。スキルは正本表13で Certificate の確認として拾う

**配布上の発見**: `dual-intake-routing.md` が配布テンプレートに**未同梱**（本家 Vault docs/ にのみ存在）。親スキルは判断規則を参照で使うため、**Phase F-1 で同梱が必須**（正典は本家・配布は写し。schema.md と同じ方式）

## 未決論点
- ADR 末尾の未決論点（鮮度同時更新の実装形／port 7687 の共存／担当者交代の移管手順／nest-webpage 導線／共有パッケージ）

## 既知の罠・注意（**実地で踏んだもの**）

1. **`cypher-shell -f` は UTF-8 を壊す。** コンテナの locale のせいで日本語がすべて文字化けする。**必ず `docker exec -e LC_ALL=C.UTF-8` を付ける**（付けないと `size("みなと（架空）")` が 7 でなく 21 になる）
2. **`docker stop` → `docker start` は Neo4j が再起動ループに入る**（pid ファイルが残る）。**`docker compose down` → `up -d` で作り直す**
3. **検査スクリプトは「0件で合格」にしない担保を必ず入れる。** 実際に偽の合格が出た。対象が0件なら不合格にする
4. **Obsidian 起動中に Vault へ外部から書き込まない**（サイレントに巻き戻る。Vault の log.md 2026-07-27 の記録）。`pgrep -x Obsidian` で確認する
5. **Vault への git 操作はデバイスブリッジ経由でなくネイティブに行う**（ブリッジは lock ファイルを消せず、次の git 操作が失敗する）
6. **移植で `LifeHistory` を削り忘れない**（ADR-D9。削り忘れると解消したばかりの二重持ちが復活する。Phase D-2 が関所）
7. **`sync-schema.sh` は実行前に `--check` と本文 diff で上書き被害を確認する**
8. **本番 nest-support には接続しない。** port 7687 を共有しており、2026-08-08 に本番を奪う事故が実発生している
9. **raw/ の実ファイル名は実名を含みうる。チャットにも git にも載せない**（件数のみで報告する）

## 次タスク（優先度順）

### A（必須・これをやらないと価値が出ない）

- **A-1〜A-4: Phase A を完了する。** `schema.md` に `source_hash`（任意）を1行、`okf_lint.py` に形式検査（64桁16進・**無ければ何もしない**）、テスト2件、本家 Vault と配布テンプレート両方へ反映
  - **検証の関所**: **既存の記入例14枚がすべて lint を通ること**（後方互換の確認）。ここが崩れたら設計に戻る
  - Phase A は**独立に価値があり、ここで止めても負債が出ない**。まず A を終えて河原さんに報告するのが安全
- **Phase D-2（削る移植）**: 実装計画のなかで最も間違えやすい。移植したら真っ先に「語り1（生育歴を含む）で `LifeHistory` が出ないこと」を確認する

### B（推奨）

- Phase B・C・D を計画どおり。**親スキルに判断規則を書き写さない**こと（`dual-intake-routing.md` が上位。写すと二重管理になり必ず乖離する）
- Phase E の通し検証。**わざと曖昧な語りを1本新規作成**して No Fabrication を試す（既存5本では試せない）

### C（余裕があれば）

- Phase F-2（**MCP 設定の章**）。ただしこれは**河原さんの目が要る**——書き手が「分かっている人」だと、福祉職が詰まる箇所が見えない
- ADR 末尾の未決論点のうち、実装中に自然に決まるものを潰す

## 河原さんへの確認が必要な場面

- **グレーな判断3件**（上記）に違和感がないか、着手前に一言もらう
- **Neo4j への書き込みを伴う検証**の前（support-db-write-gate。DELETE は明示の承認が要る）
- **配布リポジトリへの push** の前
- 設計を変える判断が要るとき（ADR に書いてある決定を覆す場合）

## 支援体制

この設計を担当した Cowork セッション（Claude）が、**問い合わせに対応できます**。設計の意図・却下した選択肢・実地で踏んだ罠について、ADR に書ききれていない文脈を持っています。判断に迷ったら聞いてください。

---
*作成: 2026-08-10 / 設計セッションより*
