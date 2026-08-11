# clientId 後付けの手順書（既存利用者向け）

- 作成: 2026-08-11（スキル層 Phase F-4・技術仕様 決定4）
- 対象: `clientId` が空のまま運用してきた既存の Client ノード
- 方針: **確認クエリ＋1件ずつの付与のみ。一括スクリプトは作らない**（support-db-write-gate §4「更新対象は完全一致で特定する」。一括処理は取り違えの経路を作る）
- この手順書は、oya-inai-neo4j スキルの禁止事項「**clientId のない Client を作らない**」の**機械側の担保**でもある——スキルの規律が破れても、未採番は手順1のクエリで検出できる

## 前提

- `clientId` は両系の橋の Neo4j 側（正本表1）。Obsidian Vault の `person_id` はこの値の写し
- **氏名から推測できる番号にしない**（S-5）。既存の最大番号の次番を使う
- 実行は `cypher-shell`（**必ず `docker exec -e LC_ALL=C.UTF-8`**。付けないと日本語が壊れる）または neo4j MCP の `execute_query`

## 手順

### 1. 未採番の一覧を取る（確認クエリ）

```cypher
MATCH (c:Client)
WHERE c.clientId IS NULL
RETURN c.name AS 氏名, c.displayCode AS 表示コード
ORDER BY c.name;
```

0件ならこの手順書の出番はない。**0件であることも記録する**（「確認したうえで無い」）。

### 2. 使用済み番号を確認し、次番を決める

```cypher
MATCH (c:Client)
WHERE c.clientId IS NOT NULL
RETURN c.clientId AS 採番済み
ORDER BY c.clientId DESC
LIMIT 5;
```

例: `P_901` まで使用済みなら次は `P_902`。

### 3. 1件ずつ付与する（完全一致・空の場合のみ）

氏名は手順1の結果を**そのままコピー**して使う（手打ちしない）。`WHERE c.clientId IS NULL` を必ず残す——既存値の上書きをクエリの形で防ぐ。

```cypher
MATCH (c:Client {name: '（手順1の氏名を完全一致で）'})
WHERE c.clientId IS NULL
SET c.clientId = 'P_902'
RETURN c.name AS 氏名, c.clientId AS 付与した番号;
```

続けて監査記録を残す（BRS-11）:

```cypher
CREATE (a:AuditLog {
  userName: '（実施者名）',
  action: 'clientId-backfill',
  targetType: 'Client',
  targetName: '（同じ氏名）',
  details: 'clientId 後付け採番（docs/clientid-backfill.md 手順3）',
  createdAt: datetime()
})
WITH a
MATCH (c:Client {name: '（同じ氏名）'})
MERGE (a)-[:AUDIT_FOR]->(c);
```

### 4. Vault 側の `person_id` を同じ値にする

該当する本人の Vault ページ（`wiki/persons/` ほか）の frontmatter `person_id` に**同じ値**を書く。橋は識別子だけで架ける（本文のコピーはしない）。

### 5. 締めの確認（0件になったこと）

手順1のクエリを再実行し、**未採番が0件になったこと**を確認して終了する。

## してはいけないこと

- 一括採番（`MATCH (c:Client) WHERE c.clientId IS NULL SET ...` のような全件更新）
- `clientId` が入っているノードへの再付与・変更（衝突の裁定は人の判断。oya-inai-neo4j スキルの3分岐「不一致」と同じ扱い）
- 氏名の部分一致・曖昧一致での特定
