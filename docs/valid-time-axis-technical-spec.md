# 事実時間軸（Track A Phase 2）技術仕様 兼 Claude Code 実装指示

作成: 2026-09-03（Claude Desktop での検討結果。河原さん決定 2026-09-03）
状態: **承認済み・未実装**
前提: Track A Phase 1（証拠・鮮度モデル。SCHEMA_CONVENTION v3.4 / SEMANTIC_MODEL v1.6〜1.7a）は完了している

---

## 0. 一言でいうと

support-db は「こちらが知った時間」（lastConfirmedAt・Review/CONFIRMS・CONTRADICTS・AuditLog）は充実しているが、**「事実が有効だった期間」を持っていない**。データがほぼ空の今のうちに、後者の軸を最小構成で追加する。既存の軸には一切手を触れない。

答えられるようになる問い: 「2025年9月時点で有効だった禁忌は何か」「去年9月のキーパーソンは誰だったか」。

## 1. 変更内容（これ以外は変えない）

### 1-1. NgAction / CarePreference（事実ノード）

| プロパティ | 型 | 必須 | 意味 |
|---|---|---|---|
| `registeredAt` | date | ✅（CREATE 時に自動付与） | DB に最初に登録された日。**不変**。lastConfirmedAt は再確認で上書きされるので別に持つ |
| `validFrom` | date | — | その事実が現実に有効になった日。多くは不明なので任意。空なら registeredAt を下限の代用とする |
| `validTo` | date | 条件付き✅ | 有効でなくなった日。**status が Inactive のとき必須、Active / Pending のとき null 必須**。管理者裁定で Inactive 化する時に同一トランザクションで記入 |

非対称ルール（BRS-13）は不変: validTo を書けるのは管理者裁定による Inactive 化の経路だけ。期限超過や矛盾で自動的に validTo が入ることはない。

### 1-2. HAS_KEY_PERSON（Client → KeyPerson）

現状は `rank` のみ。以下を追加する。

| プロパティ | 型 | 必須 | 意味 |
|---|---|---|---|
| `startDate` | date | ✅（CREATE 時に自動付与） | その人がキーパーソンになった日 |
| `endDate` | date | 条件付き✅ | 終わった日。status が Inactive のとき必須 |
| `status` | string | ✅ | `Active` / `Inactive` の2値（ENU-05 の部分集合） |

**交代の規則**: リレーションを張り替えない・削除しない。旧リレーションに `endDate` と `status: Inactive` を書き、新しいリレーションを CREATE する。USES_SERVICE と同型。

### 1-3. PublicAssistance

`endDate`（date、任意）を追加。startDate と対になる。

### 1-4. 変えないもの

lastConfirmedAt / staleAfter / source / sourceDetail / Review / CONFIRMS / CONTRADICTS / AuditLog / freshnessDefaults / restrictedStatus。KeyPerson ノード自体のプロパティも変えない。

## 2. 時点照会の標準クエリ（queries/ に置く）

```cypher
// 指定日 $asOf に有効だった禁忌（事実時間軸で引く）
MATCH (c:Client {name: $name})-[:MUST_AVOID]->(n:NgAction)
WHERE coalesce(n.validFrom, n.registeredAt) <= date($asOf)
  AND (n.validTo IS NULL OR n.validTo > date($asOf))
RETURN n.action, n.riskLevel, n.status, n.validFrom, n.validTo, n.registeredAt
ORDER BY n.riskLevel;

// 指定日 $asOf のキーパーソン
MATCH (c:Client {name: $name})-[r:HAS_KEY_PERSON]->(kp:KeyPerson)
WHERE r.startDate <= date($asOf)
  AND (r.endDate IS NULL OR r.endDate > date($asOf))
RETURN kp.name, kp.relationship, r.rank, r.startDate, r.endDate
ORDER BY r.rank;
```

「その時点で何を知っていたか」（知得軸）は既存の Review / CONFIRMS / AuditLog を reviewedAt / timestamp で絞れば出るので、新規クエリは不要。

## 3. 正典への追記文案

### 3-1. SCHEMA_CONVENTION.md → v3.5

**§3 ノード表**
- `NgAction` の列挙に `registeredAt, validFrom, validTo` を追加
- `CarePreference` 同上
- `PublicAssistance`: `type, grade, startDate, endDate`

**§4 リレーション表**
- `HAS_KEY_PERSON` | Client → KeyPerson | `rank, startDate, endDate, status` | キーパーソン（rank で優先順位。**交代は張り替えず endDate + Inactive を記入して新規追加**。§7.10）

**§7.10 新設「事実時間軸プロパティ（NgAction / CarePreference / HAS_KEY_PERSON・v3.5 / 2026-09-03）」**

> Track A Phase 2。技術仕様は oya-inai-db/docs/valid-time-axis-technical-spec.md。
>
> support-db は2本の時間軸を持つ。**知得時間**（いつ知り・確認し・裁定したか）は lastConfirmedAt / Review / CONTRADICTS / AuditLog が担う（§7.9）。**事実時間**（その事実が現実に有効だった期間）は本節のプロパティが担う。両者を混ぜない。
>
> | プロパティ | 型 | 必須 | 意味 |
> |---|---|---|---|
> | `registeredAt` | date | ✅ | 初回登録日。不変。lastConfirmedAt とは別（後者は再確認で更新される） |
> | `validFrom` | date | — | 事実が有効になった日。不明なら空。照会時は `coalesce(validFrom, registeredAt)` |
> | `validTo` | date | 条件付き✅ | 有効でなくなった日。status=Inactive で必須・Active/Pending で null 必須。管理者裁定の Inactive 化と同一トランザクションで記入 |
>
> HAS_KEY_PERSON は `startDate`（✅）/ `endDate`（Inactive で必須）/ `status`（Active/Inactive）を持つ。交代は張り替えず、旧リレーションに endDate + Inactive を書いて新規 CREATE する。
>
> 既存データの初期値: `registeredAt = coalesce(registeredAt, lastConfirmedAt)`、`HAS_KEY_PERSON.status = 'Active'`、`startDate = 移行実行日`（不明のため。注記を AuditLog に残す）。

**§変更履歴**
| 2026-09-03 | **v3.5** | **事実時間軸（Track A Phase 2）の正典収載**（河原氏決定 2026-09-03・技術仕様は oya-inai-db/docs/valid-time-axis-technical-spec.md）。(1) §3 NgAction/CarePreference に `registeredAt`（不変）/`validFrom`/`validTo`、PublicAssistance に `endDate` を追加、(2) §4 HAS_KEY_PERSON に `startDate`/`endDate`/`status` を追加し交代規則（張り替え禁止）を明記、(3) §7.10 に知得時間と事実時間の2軸と値域を収載。知得時間側（§7.9）は不変。**要追従**: Guardian・API 門番・agno allowlist・check_semantic_drift（同日実施） |

### 3-2. SEMANTIC_MODEL.md → v1.8

**BRS-14 新設「事実時間軸（Track A Phase 2）」**

> 「DB の中身は賞味期限つきの観測である」（BRS-13）に、「観測と事実の時間は別物である」を加える。BRS-13 の lastConfirmedAt は**こちらが知った時間**、本項の validFrom/validTo は**事実が有効だった期間**。後から入った訂正で「その時に正しかったこと」と「その時に知っていたこと」が混ざらないよう、2軸を分けて持つ。
> **不変の登録日**: registeredAt は CREATE 時に自動付与し、以後どの経路でも書き換えない（Guardian が更新時に破棄する）。
> **validFrom は任意**: 禁忌の多くは「いつから真だったか」が誰にも分からない。分からないものを埋めさせない。照会は coalesce(validFrom, registeredAt)。
> **validTo は裁定と同時**: 非対称ルール（BRS-13）を弱めない。validTo が入る唯一の経路は管理者裁定による Inactive 化で、AuditLog 必須。
> **リレーションの交代は履歴にする**: HAS_KEY_PERSON は張り替えず endDate + Inactive を書いて新規追加する（USES_SERVICE と同型）。親なき後に最も変わりやすい関係だからこそ、誰がいつまで担っていたかを消さない。
> `source: 2026-09-03 河原氏決定` `values: [Continuity, Safety]`

**ENU-05 に追記**: HAS_KEY_PERSON.status は `Active` / `Inactive` の2値に制限。

**ENT-11（KeyPerson）または該当 ENT に追記**: 「現在のキーパーソン」は `status = Active` かつ `endDate IS NULL` のリレーションで定義する。rank は Active なものの間の順位。

**§6 machine-check JSON に追加**（既存キーは変えない）:

```json
"requiredProperties": {
  "NgAction": ["source", "status", "lastConfirmedAt", "registeredAt"],
  "CarePreference": ["source", "status", "lastConfirmedAt", "registeredAt"]
},
"immutableProperties": {
  "NgAction": ["registeredAt"],
  "CarePreference": ["registeredAt"]
},
"conditionalRequired": {
  "NgAction":       {"when": {"status": "Inactive"}, "require": ["validTo"], "forbidWhen": {"status": ["Active", "Pending"]}, "forbid": ["validTo"]},
  "CarePreference": {"when": {"status": "Inactive"}, "require": ["validTo"], "forbidWhen": {"status": ["Active", "Pending"]}, "forbid": ["validTo"]}
},
"relationshipProperties": {
  "HAS_KEY_PERSON": {"required": ["rank", "startDate", "status"], "optional": ["endDate"],
                     "status": ["Active", "Inactive"], "requireWhenInactive": ["endDate"]},
  "USES_SERVICE":   {"required": ["startDate", "status"], "optional": ["endDate"]}
}
```

**変更履歴**: v1.8 として BRS-14 新設・ENU-05 追記・§6 に immutableProperties / conditionalRequired / relationshipProperties を追加、と記す。

### 3-3. 配布

shared-schema で編集後 `./sync-schema.sh` を流す（4配布先）。§7-2 の適用状況表を v1.8 で更新する。

## 4. Claude Code への実装指示

### 4-0. 起動

```bash
cd ~/Dev-Work/oya-inai-db
claude --add-dir ~/Dev-Work/shared-schema
```

oya-inai-db を cwd にする理由: Guardian（lib/schema_validator.py）・API 門番（api/app/lib/db_operations.py）・agno allowlist（lib/db_new_operations.py）・検出器（scripts/check_semantic_drift.py）の4つが全部この中にあり、テストもここで回る。shared-schema は正典編集のためだけに add-dir で見せる。

最初に読ませるもの: 本ファイル、docs/evidence-freshness-technical-spec.md（Phase 1 の書き方に揃える）、scripts/check_semantic_drift.py、HANDOVER.md 第0章（Gemini 撤去済みの現状確認）。

### 4-1. 作業順序（RED → GREEN、Phase 1 と同じ流儀）

1. **正典を先に直す**（shared-schema）。§3 で書いた文案を SCHEMA_CONVENTION v3.5 / SEMANTIC_MODEL v1.8 に反映。machine-check JSON を更新。まだ sync しない。
2. **検出器を先に拡張する**（scripts/check_semantic_drift.py）。machine-check の新キー（requiredProperties の追加分・immutableProperties・conditionalRequired・relationshipProperties）を ②③④ に照合する検査を追加。**この時点で実行して FAIL が出ることを確認する**（RED）。FAIL が出ないなら検査が効いていない。
3. **Guardian**（lib/schema_validator.py）
   - NgAction/CarePreference の CREATE: registeredAt が無ければ today を付与
   - UPDATE: 入力に registeredAt が含まれていたら**破棄して警告**（変更させない）
   - status=Inactive への遷移: validTo 必須（無ければ reject）。Active/Pending で validTo 非 null なら reject
   - validFrom と validTo が両方あるとき validFrom <= validTo
   - HAS_KEY_PERSON: CREATE 時 startDate 既定 today・status 既定 Active。Inactive で endDate 必須。status の値域2値
   - PublicAssistance.endDate は型検証のみ
4. **API 門番**（api/app/lib/db_operations.py）と **agno allowlist**（lib/db_new_operations.py）: プロパティ許可リストがあれば新プロパティを追加。HAS_KEY_PERSON の「交代」操作を追加する場合は、旧リレーションの DELETE を禁止し endDate+Inactive の SET のみ許す。
5. **裁定経路の連動**: Phase 1 で作った「管理者裁定 → status Inactive + AuditLog」の関数に validTo の記入を同一トランザクションで追加。validTo 未指定なら裁定日を既定値にする。
6. **テスト**: DRIFT-12 様式でテスト固定。最低限 (a) registeredAt が更新で変わらない (b) Inactive で validTo 無しは reject (c) Active で validTo 有りは reject (d) キーパーソン交代で旧リレーションが残り endDate が入る (e) §2 の as-of クエリが空 DB と1件 DB の両方で期待どおり返る。
7. **移行 Cypher**（scripts/ に置き、冪等にする）:
   ```cypher
   MATCH (n) WHERE (n:NgAction OR n:CarePreference) AND n.registeredAt IS NULL
   SET n.registeredAt = coalesce(n.lastConfirmedAt, date());
   MATCH ()-[r:HAS_KEY_PERSON]->() WHERE r.status IS NULL
   SET r.status = 'Active', r.startDate = coalesce(r.startDate, date());
   ```
   実行を AuditLog に1件残す（action: 'migration', details: 'valid-time-axis phase2'）。
8. **check_semantic_drift.py --strict で FAIL 0**（GREEN）。これが完了条件。
9. `~/Dev-Work/shared-schema/sync-schema.sh` を流し、4配布先の同期を確認。§7-2 適用状況表を更新。
10. HANDOVER.md に Track A Phase 2 完了として追記。commit は正典・検出器・Guardian/門番・テスト・移行の単位で分ける（`git add -u` は使わない。第0章の注意参照）。

### 4-2. やらないこと

- 知得時間側（lastConfirmedAt / Review / CONFIRMS / CONTRADICTS）のロジック変更
- validFrom の必須化・自動推定
- validTo の自動記入（期限超過や矛盾から入れない）
- KeyPerson ノード自体へのプロパティ追加
- スキル側（neo4j-support-db / visit-prep / data-quality-agent）の改修。これは別セッション（下記）

### 4-3. 後続（別セッション）

- data-quality-agent に検査を追加: Inactive なのに validTo 無し／Active なのに validTo 有り／HAS_KEY_PERSON が rank 重複で複数 Active
- neo4j-support-db スキルに §2 の as-of クエリを T-番号で収載
- visit-prep は「現在有効」の定義を `validTo IS NULL` に揃える（現状 status=Active 判定のままでも同義だが明示する）
- 他3配布先（neo4j-agno-agent / nest-support / oyagami-local）の Guardian 相当が v1.8 に追従しているか（DRIFT-13 型の再発防止）

## 5. 判断の記録（なぜこうしたか）

- **今やる理由**: データが空なので遡及処理が不要。後からだと全件に registeredAt を推定で埋めることになり、その推定が事実時間軸そのものを汚す
- **validFrom を任意にした理由**: 禁忌の「いつから真か」は生来のこともあり不明が普通。埋めさせると捏造になる。registeredAt を下限の代用にすれば時点照会は成立する
- **リレーションを張り替えない理由**: 「去年9月のキーパーソンは誰か」は張り替えた瞬間に構造的に答えられなくなる。AuditLog から再生するのは時点型に答えられないことと同じ
- **四者一致を先に RED にする理由**: DRIFT-13 は検出器の死角が原因だった。検査を足す前に実装すると同じ死角ができる
