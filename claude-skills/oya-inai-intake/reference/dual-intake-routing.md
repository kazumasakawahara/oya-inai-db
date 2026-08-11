<!-- AUTO-GENERATED COPY — DO NOT EDIT.
  Synced from oya-inai-wiki docs/dual-intake-routing.md (正典).
  Edit the master there and run scripts/sync_skill_refs.py. (synced: 20260811-115147) -->

# 仕分け仕様 — 語り／文書はどこへ落ちるか

- 作成: 2026-08-10（Agent SOP。実装計画 Phase 0・2 の成果物）
- 上位文書: `docs/dual-intake-requirements.md`（R-2 正本表の**詳細版が本ファイル**）／`docs/dual-intake-adr.md`
- 相手系の正典: `oya-inai-db/docs/SCHEMA_CONVENTION.md` v3.4 ／ `SEMANTIC_MODEL.md` v1.6（**編集しない・参照のみ**。Agent SOP 鉄則12）
- 確認日: 2026-08-10（Neo4j 側のノード24種・リレーション30種を実物で確認済み）

---

## 0. Phase 0 で分かったこと（前提の更新）

要件書を書いた時点の想定と、実物を読んだ後で変わった点。

1. **Neo4j 側の受け口はすでに実装されている。** `POST /api/narrative/intake`（`api/app/routers/narrative_intake.py`）が存在し、**ノードとリレーションの断片**を受け取る。`dryRun`（検証のみ）・重複チェック・意味的重複の警告・安全チェック・監査コンテキストを備える。**直接 Cypher を書く必要はなく、この経路を使う**（実装計画 0-3 の答え）。**ただし `CONFIRMS` だけは例外——§0-6(a) を必ず併せて読むこと。**
2. **`auditContext.sourceHash` がある。** 出所の同一性を**内容をコピーせずに**両系で示せる。raw/ に保存した原本の sha256 を両系に持たせれば、「同じ語りから生まれた記録」を後から突き合わせられる。**これを両系の橋にする**（本仕様の要）。
3. **鮮度更新の作法が確定している。** 再確認は1トランザクションで「Review 作成 ＋ `CONFIRMS` ＋ 事実の `lastConfirmedAt` 更新」。`lastConfirmedAt` は常に「最新の CONFIRMS 元 Review の `reviewedAt`」と一致し、Guardian の整合検査対象。**Vault 側の `last_confirmed` はこの日付に合わせる**。
4. **Neo4j 側に「計画（サービス等利用計画）」に対応するノードがない。** ENT-01〜24 に該当なし。したがって**計画は Vault 正本で確定**する（→ §3 の 8）。
5. **想定より重複が多い。** 要件書 R-2 の9行では足りず、Neo4j 側の主要ラベルと Vault の型は12か所で意味が重なる。以下で1件ずつ正本を決める。

### 0-6 実際に通してみて分かったこと（2026-08-10・ダミー2名で検証）

上の1〜5は文書を読んで分かったこと。以下は**実際に語りを仕分けて両系に落とした結果**、分かったこと。

**(a) `CONFIRMS` は API 経由で書けなかった → 2026-08-10 に解消（マージ待ち）。**
検証時点では `POST /api/narrative/intake` の実行時 allowlist（`ALLOWED_REL_TYPES`）に `CONFIRMS` / `CONTRADICTS` が入っておらず、投げると `rel_type_not_allowed` で reject された。正典（SEMANTIC_MODEL v1.6・SCHEMA_CONVENTION v3.4）には 2026-08-08 に収載済みで、実装3か所が未追随だった（→ `docs/oya-inai-db_DRIFT-13_申し送り.md`）。

同日中に oya-inai-db 側で修正済み。ブランチ `fix/drift-13-confirms-contradicts`（55a40da・46787b0）。`dryRun` で CONFIRMS＋CONTRADICTS を含む intake の rejected が 0 件であることを確認済み。**main へのマージは河原さんのレビュー待ち。**

> **運用の切り替え**
> - **マージ前**: 鮮度更新（Review＋CONFIRMS＋`lastConfirmedAt`）のみ直接 Cypher。迂回であって設計ではない——門番・重複検査・安全検査・監査コンテキストをすべて飛ばしている自覚を持って使う
> - **マージ後**: §4 の手順を **`/api/narrative/intake` の1リクエストで表現できる**（`ON MATCH SET n += $extra_props` があるため、mergeKey つきで NgAction を送れば `lastConfirmedAt` を更新できる）。直接 Cypher はやめる
> - **なお残るもの**: Track A Phase 1 ③ の本体（チャット承認・裁定フロー、`Pending` の二段階承認）は未実装。書き込みの仕組みは通るが、**承認の UX 層は当面こちらの人間ゲート（黙認方式と review 起票）が代替する**

**(b) Vault の `confirms` と Neo4j の `CONFIRMS` は1対1にならない。**
検証では Vault 側が3ページ（trigger / protocol / person）を挙げたのに対し、Neo4j 側の `CONFIRMS` は2件（NgAction / CarePreference）だった。protocol や person に対応する事実ノードが Neo4j に存在しないためで、これは設計の欠陥ではなく**両系の粒度が違うことの当然の帰結**である。

> **担保のしかた**: 個々の対応を1対1にしようとしない。かわりに、**同じ「確認という出来事」から生じたことを、日付と情報源の一致で担保する**。すなわち Vault の `last_confirmed` = Neo4j の `Review.reviewedAt`、Vault の `confirmed_by` = `Review.source`。この2つが揃っていれば、後から突き合わせられる。

**(c) 他方の正本を参照するときは、1行以内・正本表記とセットで。**
「対応は構造化DB側の CarePreference が正本」のように短く書く。検証では推奨ケアの本文が Vault 側に2か所現れたが、いずれも正本表記つきの1行参照だったため許容範囲だった。

> **なぜ短さが要るか**: 参照が長くなると実質的な二重管理に化ける。読み手には参照か正本か区別がつかず、片方だけが古くなったときに**どちらが本当か分からない**という、ADR-D2 が避けようとしたまさにその状態になる。長い説明を書きたくなったら、それは正本の置き場所を間違えている合図である。

---

## 1. 橋のかけ方（コピーせずに繋ぐ3点）

| 橋 | Vault 側 | Neo4j 側 | 役割 |
|---|---|---|---|
| 本人 | `person_id: "P_001"` | `Client.clientId`（または `displayCode`） | 同一人物の同定 |
| 出所 | raw/ の原本ファイル＋その sha256 | `auditContext.sourceHash` | **同じ語りから生まれた記録**の突合 |
| 相互位置 | frontmatter の `person_id` | `Client.wiki_path`（CLAUDE.md §9-2） | 双方向に辿る |

> 本文のコピーは一切しない。橋は**識別子だけ**で架ける。

## 2. 正本の判定原則（迷ったときの3つの問い）

1. **機械が漏れなく拾う必要があるか**（全員分・期限・悉皆性）→ **Neo4j**
2. **「なぜ」「どう変わってきたか」を書きたいか**（理由・経緯・仮説）→ **Vault**
3. **実名・連絡先・番号を含むか** → **Neo4j**（Vault は仮名のみ。ADR-D2／要件書 R-4）

## 3. 事実の型ごとの正本表（確定版）

| # | 事実の型 | 正本 | Neo4j 側 | Vault 側 | 他方の扱い・判断規則 |
|---|---|---|---|---|---|
| 1 | 本人の識別・属性（氏名・生年月日・血液型） | **Neo4j** | `Client{name, dob, kana, clientId, displayCode}` | — | Vault は `person_id` のみを持ち、実名を持たない |
| 2 | 特性・診断 | **Neo4j** | `Condition{name, diagnosisDate, status}` ← `HAS_CONDITION` | person の `diagnosis_summary` は**1行要約のみ** | 詳細を Vault に書かない |
| 3 | **してはいけない行為**（禁忌） | **Neo4j** | `NgAction{action, reason, riskLevel, source, lastConfirmedAt}` ← `MUST_AVOID` | — | 判断規則: **支援者の行為を禁じる言い方**なら NgAction |
| 4 | **本人に起きる反応の引き金** | **Vault** | （`NgAction.reason` から参照） | `trigger`（joy / distress） | 判断規則: **本人の側に起きる反応**の記述なら trigger。3と4はリンクで結ぶ |
| 5 | 単文で言い切れる関わり方 | **Neo4j** | `CarePreference{category, instruction, priority, lastConfirmedAt}` ← `REQUIRES` | — | 「静かな部屋で背中をさする」のような**1文の指示** |
| 6 | 手順・段取り・例外処理とその理由 | **Vault** | （`CarePreference` を参照） | `protocol` | 「朝の流れ」のように**順序と分岐**があるもの |
| 7 | 日々の観察・対応の記録（量で意味が出る） | **Neo4j** | `SupportLog{date, situation, action, effectiveness, emotion, triggerTag, context}` | 原本は raw/30_事業所から/ | 予兆検知の原料。CSW は自分で書かず**事業所提供分を受け取る** |
| 8 | 試行錯誤と**学び**（仮説の更新） | **Vault** | （必要なら SupportLog から参照） | `trial` | 判断規則: **「次に同じ場面が来たらどうするか」を書きたくなったら trial** |
| 9 | **サービス等利用計画** | **Vault** | 対応ノードなし（§0-4） | `plan` | 様式の写しは raw/70_自分の作成物/。Neo4j へは `USES_SERVICE` 等の関係のみ落ちる |
| 10 | モニタリングの要点と判断の過程 | **Vault** | 鮮度更新は `Review`（→ §4） | `monitoring` | 実施の事実と確認結果は Neo4j Review に、判断の過程は Vault に |
| 11 | 会議の音声・逐語・開催の事実 | **Neo4j** | `MeetingRecord{date, title, transcript, filePath}` | 原本は raw/20_会議/ | — |
| 12 | 会議で**何が決まり、なぜそう決まったか** | **Vault** | （MeetingRecord を参照） | `meeting` | 11と12を混ぜない |
| 13 | 手帳・受給者証・公的扶助 | **Neo4j** | `Certificate{type, grade, nextRenewalDate}` / `PublicAssistance` | — | **期限管理は生命線**。Vault は期限を持たない |
| 14 | キーパーソン・後見人・医療機関・医師 | **Neo4j** | `KeyPerson{rank}` / `Guardian` / `Hospital` / `Doctor` | — | 実名・連絡先を含むため一律 Neo4j |
| 15 | 関係機関・事業所（実在組織） | **Neo4j** | `Organization` / `ServiceProvider` / `ProviderFeedback` | `entity` は**公開情報としての解説**のみ | 契約状況・担当者は Neo4j |
| 16 | 支援ネットワークの**その時点の姿** | **Vault** | （関係の現在値は Neo4j） | `ecomap`（月単位スナップショット） | ecomap は**過去の姿を保存する**ためのもので、現在の関係の正本ではない |
| 17 | 家族・親が担っている機能 | **Neo4j** | `Relative` / `CareRole` ← `PERFORMS`・`CAN_BE_PERFORMED_BY` | 移行の経緯は `trial`/`protocol` | レジリエンス診断の単位。**本人・担当者配下スコープで作成**（同名統合は誤診断を招く） |
| 18 | 本人・家族が言葉にした願い | **Neo4j** | `Wish{content, status, date}` ← `HAS_WISH` | 意思決定支援の**過程**は Vault | 願いそのものは構造化して残す |
| 19 | 生育歴 | **Vault** | （本連携では `LifeHistory` を使わない） | person の「ライフストーリー」節 | 2026-08-10 に一本化（→ §5・ADR-D9）。判定原則3つすべてが Vault を指すため |
| 20 | 制度・概念の一般知識 | **Vault** | — | `public-system` / `concept` | 個人に紐づかない。Neo4j は扱わない |
| 21 | 確認の記録（「無いことを確認した」を含む） | **Neo4j** | `Review{domain, reviewedAt, source}`・`CONFIRMS` | `last_confirmed` / `confirmed_by` は同じ日付・同じ情報源を写す | → §4 |
| 22 | 矛盾の保留 | **両系**（同じ語彙） | `CONTRADICTS{claim, raisedAt, resolvedAt}` | `contradicts` | 追記専用・裁定しても消さない。**未解決＝ `resolvedAt IS NULL`** |

> **同じ事実が2行に現れないことを確認済み。** 意味が近い対（3と4、5と6、7と8、11と12、15と16）は、いずれも**判断規則で排他**にしてある。
>
> **例外はゼロ。** 2026-08-10 に19（生育歴）を Vault へ一本化したことで、「運用形態によって正本が変わる行」は無くなった（→ §5）。

## 4. 鮮度の同時更新（本設計の心臓部）

モニタリングを実施したとき、次の順で1回だけ書く。

1. Vault に `monitoring` を作成し、`confirms:` に「今回確かめたページ」を列挙する
2. Neo4j へ **Review を1件作成**（`domain` = 確認した領域、`reviewedAt` = 実施日、`source` = 情報源）
3. 確かめた個々の事実へ `CONFIRMS` を張り、その事実の `lastConfirmedAt` を `reviewedAt` に更新（**1トランザクション**）
4. Vault 側の該当ページの `last_confirmed` を**同じ日付**に、`confirmed_by` を**同じ情報源**に更新

守ること。

- **確かめていないものを確認済みにしない。** `confirms` に挙がっていないページの日付は動かさない
- **両系の対応づけは1対1にしない。** 揃えるのは**日付と情報源**（`last_confirmed` = `Review.reviewedAt`、`confirmed_by` = `Review.source`）。ページと事実ノードの個数は一致しなくてよい（→ §0-6(b)）
- **手順2〜3の書き込み経路**は DRIFT-13 のマージ前後で切り替える（→ §0-6(a)）。マージ後は `/api/narrative/intake` の1リクエストにまとめる（Review は CREATE 専用ラベル、NgAction / CarePreference は mergeKey つきで `lastConfirmedAt` を更新）。**トランザクション境界が1リクエスト内で閉じているかは、マージ後の実地確認項目**
- **0件の意味を潰さない。** 「確認したうえで無い」は `CONFIRMS` を持たない Review で表す。Vault 側にこれを表す手段はないため、**0件確認は Neo4j が正本**
- **NgAction の警告は自動で消えない。** 期限超過は「要再確認」への降格であって非表示ではなく、停止は管理者裁定（`status: Inactive`＋AuditLog）のみ

## 5. 生育歴の正本 — 2026-08-10 に Vault へ一本化

### かつての規定（2026-08-10 まで）

配布テンプレートは Neo4j なしで完結しなければならない（ADR-D7）。生育歴は両系に器があるため、当初は次のようにしていた。

- **単独運用**: Vault の person「ライフストーリー」節が正本
- **連携運用**: Neo4j `LifeHistory` が正本。Vault 側は**リンクと解釈のみ**に痩せる

### なぜやめたか

ダミー検証で**実際に両系へ入れてみたところ、単に二重に持っただけ**になった。加えて §2 の判定原則3つを当てると、生育歴は**すべてが Vault を指す**。

| 問い | 生育歴の場合 |
|---|---|
| 機械が漏れなく拾う必要があるか | **ない**。期限がなく、全員分を悉皆で突き合わせる場面もない |
| 「なぜ」「どう変わってきたか」を書きたいか | **それしか書くことがない**。価値は出来事の並びではなく**因果の解釈**にある |
| 実名・連絡先・番号を含むか | **含まない**。仮名のまま十分に書ける（P_900 の記入例が実例） |

そして実利として大きいのは、**正本表から「運用形態で正本が変わる行」という例外が消えること**である。この種のルールは書いた本人以外は覚えない。**ルールは覚えられる数しか守られない**ため、例外を1つ消せるなら多少の機能を諦める価値がある。

### 決定

**生育歴の正本は Vault の person「ライフストーリー」節。本連携では Neo4j の `LifeHistory` を使わない**（ノード自体を廃止するわけではない。他の使い手が使うのは自由）。

### 諦めたもの・撤退線

oya-inai-db の ENT-02 は「施設探しで、空き状況だけでなく**この物語と特性に適合するか**を照合する」機能（BRS-10）を前提に設計されている。生育歴が Vault にしかないと、この照合は機械にはできない。`LifeHistory.emotion` を分析に使う道も閉じる。

それでも一本化を採ったのは、**BRS-10 の照合が現時点で実際には使われていない**ため。使われていない機能のために全導入者が覚えるルールを増やすのは割に合わない。

> **撤退線**: 将来この照合を本当に使いたくなったら、「**Vault の生育歴から要約を Neo4j へ流す**」派生を作る。正本は Vault のまま、Neo4j 側は導出物として扱う。先に汎用性を用意しない、という本設計を通じての方針に沿う。

## 6. 仕分け宣言の定型文（Step 0 の拡張）

AI は次の形で**宣言して進む**（質問しない）。訂正があれば従う。

```
〈出所〉からの〈種類〉として受け取りました。
　原本 → raw/〈棚〉（sha256: xxxxxxx）
　〈事実A〉→ Neo4j の〈ラベル〉
　〈事実B〉→ Vault の〈型〉
違っていたら教えてください。
```

### 例1 — 家族からの聴き取り

> 「大きな音が苦手で、パニックになると頭を叩きます。無理に触ると悪化します。静かな部屋で背中をさすると落ち着きます。」

```
本人・家族からの聴き取りとして受け取りました。
　原本 → raw/10_本人・家族から/（sha256: a1b2c3d）
　「パニック時に無理に触れない」→ Neo4j の NgAction（riskLevel: High、source: 家族）
　「静かな部屋で背中をさする」→ Neo4j の CarePreference
　「大きな音が引き金になる」→ Vault の trigger（distress / auditory / high）
```

### 例2 — 事業所からの支援記録

> 「先週の外出で、店内が混んでいて落ち着かない様子。早めに切り上げたら回復した。」

```
事業所からの支援記録として受け取りました。
　原本 → raw/30_事業所から/〈事業所名〉/（sha256: e4f5g6h）
　出来事そのもの → Neo4j の SupportLog（effectiveness、triggerTag: 混雑）
　「混雑時は早めに切り上げる」という次への申し送り → Vault の trial（学びつき）
```

### 例3 — モニタリング

> 「訪問。禁忌は変わりなし。入浴の手順は今も有効。就労の希望が出てきた。」

```
モニタリングとして受け取りました。
　要点と判断の過程 → Vault の monitoring（monitored_on: 2026-08-10）
　確認できた事実 → Neo4j に Review 1件＋CONFIRMS（NgAction / CarePreference）→ lastConfirmedAt 更新
　同じ日付を Vault の該当ページの last_confirmed にも反映
　新しく出た希望 → Neo4j の Wish
```

## 7. 検証の結果（2026-08-10・ダミー2名 P_900 / P_901）

### 確かめられたこと

- **3と4（NgAction / trigger）の判断規則は機能した。**「支援者の行為を禁じる言い方か、本人の側に起きる反応の記述か」で、5本の語りすべてを迷いなく振り分けられた
- **7と8（SupportLog / trial）の切り分けも成立した。**事業所提供の3件の記録は、出来事そのものが SupportLog、「次に同じ場面が来たらこうする」の部分だけが trial に切り出せた
- **鮮度の同時更新が両系で成立した。**モニタリング1件から Review 3件（CONFIRMS 付き2件＋0件確認1件）が生まれ、両系の日付が 2026-08-05 で一致。**確認していない P_901 は両系とも動かなかった**
- **疎結合が成立した。**Neo4j を停止しても Vault の lint と日常運用は通る
- 逆テスト5本（日付欠落・person_ids 欠落・機微偽装・public 偽装・PII 混入）はすべて検出され、ゲートが終了コード2で止まった

### まだ確かめられていないこと

- **19（生育歴）の二重性**が運用上の混乱を生まないか。今回は単独運用側（Vault の person）にのみ置き、Neo4j にも LifeHistory を作ったため、**実は二重に持ってしまっている**。連携運用に入る時点でどちらかに寄せる判断が要る
- `sourceHash` を Vault 側のどこに書くか（frontmatter の新フィールドか、raw/ の移動記録か）。今回は算出しただけで、Vault には書いていない
- **実務適合**（問いの立て方・語彙・周期への乗り方）は、ダミー検証では原理的に分からない（ADR-D8）。現役の相談支援専門員のレビューを待つ
