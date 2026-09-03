# MIGRATION LOG — 事実時間軸（Track A Phase 2）

移行 Cypher: `scripts/migrate_valid_time_axis.cypher`（冪等）。技術仕様: `docs/valid-time-axis-technical-spec.md`。
実データの中身は記録しない（件数のみ）。

## 2026-09-03 — oya-inai-db-neo4j（本リポジトリのスタック・port 7687）

| 手順 | 結果 |
|---|---|
| コンテナ起動 | stale PID で再起動ループ → `docker compose up -d --force-recreate neo4j` で復旧 |
| バックアップ `scripts/backup.sh` | オンライン dump 不可（CE）→ 停止コピー方式。`neo4j_backup/backup_20260903_195806/`（541MB）。復旧後に再度 force-recreate が必要だった |
| 統合テスト `api/tests/integration`（合成データのみ） | 7 passed。残留ノード 0 |
| 適用前 | NgAction+CarePreference 19件中 registeredAt null 19 / HAS_KEY_PERSON 4件中 status null 4 / migration AuditLog 0 |
| 適用 | registeredAt_filled 19 / key_person_rels_initialized 4 / AuditLog 1件（timestamp 2026-09-03T11:00:24Z） |
| 適用後 | registeredAt null 0 / status null 0 / migration AuditLog 1 / 保存型 DATE |
| 再実行（冪等確認） | 0 / 0 / AuditLog 1件のまま |

## 未実施

- nest-support-neo4j（本番 support-db）: 河原さんの確認後に同じ手順で実施する。
