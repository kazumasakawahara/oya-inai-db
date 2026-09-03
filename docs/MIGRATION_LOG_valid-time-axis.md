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

## 2026-09-03 — nest-support-neo4j（本番 support-db・port 7687）

河原さん承認のうえ実施。追加条件「再起動ループから復旧した場合は、統合テスト・移行の前に
ノード総数とラベル別件数がバックアップ直前と一致することを件数のみで確認」を履行。

| 手順 | 結果 |
|---|---|
| oya-inai-db-neo4j 停止 → nest-support-neo4j 起動 | 起動直後に stale PID で再起動ループ → force-recreate で復旧 |
| バックアップ直前の基準値 | 総数 136・ラベル 16 種（AuditLog 15 / CarePreference 21 / Certificate 8 / Client 6 / Condition 11 / Doctor 7 / Guardian 2 / Hospital 13 / KeyPerson 10 / LifeHistory 6 / NgAction 11 / PublicAssistance 3 / Review 2 / SupportLog 6 / Supporter 5 / Wish 10） |
| バックアップ `oya-inai-db/scripts/backup.sh` | 停止コピー方式。`oya-inai-db/neo4j_backup/backup_20260903_200541/`（530MB） |
| バックアップ後 | 再び再起動ループ（restarts=7・"already running"）→ force-recreate で復旧 |
| 復旧後の突合 | **総数 136 / ラベル別 16 種すべて一致** |
| 統合テスト `api/tests/integration`（合成データのみ） | 7 passed。残留ノード 0。総数 136 のまま |
| 適用前 | NgAction+CarePreference 32件中 registeredAt null 32 / HAS_KEY_PERSON 10件中 status null 10 / migration AuditLog 0 |
| 適用 | registeredAt_filled 32 / key_person_rels_initialized 10 / AuditLog 1件（timestamp 2026-09-03T11:06:59Z） |
| 適用後 | registeredAt null 0 / status null 0 / migration AuditLog 1 / 保存型 DATE / 総数 137（= 136 + AuditLog 1） |
| 再実行（冪等確認） | null 0 / 0・AuditLog 1件のまま |
| 正典写し | `shared-schema/sync-schema.sh --write-prod` で nest-support の写しを v3.5 / v1.8 に更新 |

注: registeredAt の初期値は lastConfirmedAt（Phase 1 移行で 2026-08-08 に一括設定）に揃う。
HAS_KEY_PERSON.startDate は真の開始日が不明なため移行実行日（2026-09-03）を仮置き（AuditLog の note に記載）。
