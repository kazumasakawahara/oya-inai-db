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
  - [x] Phase C（子 `oya-inai-vault`・新規）— 2026-08-11 完了（oya-inai-db `bed97fd`）。C-1〜C-4 を sandbox で実地検証: バイト列 sha256 が宣言①の記録値 `83c84643…` を**再現**／append-only 確認／わざと違反→gate exit 2 で停止／log.md 追記。あわせて routing の機械配布（`scripts/sync_skill_refs.py`・同期点 SP-2/SP-3 を shared-schema 台帳 §7-2 へ登録 `f4ec13e`）
  - [x] Phase D（子 `oya-inai-neo4j`・移植＋**削る**）— 2026-08-11 完了（oya-inai-db `a07d349`）。**D-2 関所を移植直後に通過**: 語り1の抽出ドライランで LifeHistory が出ないこと・`HAS_HISTORY` と `lifeHistories` 定義の不在を機械確認。削る対象は**固定リスト**（生育歴／trial の学び／計画／判断の過程）としてスキル内に確定記録。承認必須（D-3）・API 第一＋MCP 代替警告（D-4）・AuditLog／MERGE／DELETE 禁止／Pending・CONTRADICTS 継承（D-5）を明文化。routing の写しは増やさず隣の `oya-inai-intake/reference/` を参照。**D-4 の実挙動（API 分岐・dryRun）と D-3 の実操作は Phase E で検証**
  - [x] Phase E（通し検証）— 2026-08-11 実施。**E-1**: Phase B の突合で充足（棚5/5・宣言一致・教材側差分3点は記録済み）。**E-2 合格**: 曖昧な語りを新規作成（sandbox raw/30、sha 3a6dcd5…）→ 両系とも登録0件・空欄のまま（No Fabrication）。**E-3 合格**: 合同支援会議を新規作成（sha 1ad413d…）→ 原本保存は1回・meeting の `person_ids` に2名・lint 0。**E-4 合格**: claude-skills/ へのコード参照ゼロ・drift OK=30 FAIL=0・pytest 450 passed（既知の1件のみ失敗）。**E-5 条件付き合格**: API dryRun→本登録が通り（rejected 0）、**clientId 突合を実証**（3分岐「一致」で送らず・既存 P_900 無傷・`MATCH (c:Client {clientId:'P_900'})` で新事実へ到達）。Guardian drift 0・sandbox lint 0。鮮度同日更新は設計セッションの検証済み範囲（今回は非対象）
  - [x] Phase F（配布物）— 2026-08-11 に F-1・F-3・F-4 完了＋F-2 草稿。**F-1**: `claude-skills/README.md`（導入手順・前提・撤退線。模擬ターゲットでコピー検証済み・bak 混入 0）。**F-3**: README に「二層の提供」節を追加。**F-4**: `docs/clientid-backfill.md`（未採番一覧→次番確認→1件ずつ付与＋AuditLog→0件確認。一括禁止を明記）。**F-2**: `docs/mcp-setup.md` を**草稿**として作成（QUICK_START からは未リンク・河原さんレビュー待ち 🙋）。**F-5（公開の実地確認）は実務者レビュー一巡後**
  - [ ] Phase G（記録）← **ここから**

## Phase E の発見 — 2026-08-11 裁定・解消済み

1. **sourceHash の片橋 → (a) 案で解消。**正典を先に改訂（SCHEMA_CONVENTION **v3.4.1**・SEMANTIC_MODEL **v1.7** BRS-11 拡張、shared-schema `40d95f8`）し、AuditLog に `sourceHash`＋`correlationId` を実装（oya-inai-db `1d1fc52`。RED→GREEN テスト2件・452 passed・四者一致 OK=30 FAIL=0）。実地確認済み——API の auditLogId `sessionId:hash12桁` が実在の AuditLog ノードへ解決でき、sourceHash も載る。(b) 案（事実ノードへの出所スカラー）は不採用とし、**ADR 未決論点9**「事実ごとの出所は Review／CONFIRMS 側に持たせるか」として記録（後の語りが先の出所を上書きするため・§0-6(b) と同型）
2. **mergeKey の doc/実装齟齬 → DRIFT-14 として台帳登録・解消。**「実装が正しく docstring が古い」と書き分け、docstring を修正
3. **CONFIRMS / CONTRADICTS を現行 main の API で再確認済み**（rejected 0）。8001 に DRIFT-13 マージ前の旧プロセスが残っていたため過去の確認が古い方に当たっていた可能性があったが、現行コードで通ることを実測
4. 罠2（stop→start の再起動ループ）を2回踏んだ。**この検証台は必ず down→up で起動する**

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
7. **`sync-schema.sh` は実行前に `--check` で上書き被害を確認する**（2026-08-11 修正済み: バナー剥がし比較になり `--check` の DIFF は本物だけ。本番 nest-support 向けは通常実行では書かず、書くには `--write-prod` の明示が要る）。**旧世代の残骸（掃除候補）は67件**——配布先の docs/ 直下に旧方式が残した `.bak-*`（neo4j-agno-agent 29・本番 nest-support 19・oyagami-local 19）。退避先を `shared-schema/.sync-backups/` へ変更済みのため今後は増えない。nest-support の19件は `docs/*.bak-*` が gitignore 済みで git 追跡外につき、掃除は急がない（河原さん判断 2026-08-11）。**これとは別に oya-inai-db の `.sync-backups/` に2件あるが、これは指定退避先への正常な退避（sync_skill_refs.py の 2026-08-11 分）であり掃除対象ではない**
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
