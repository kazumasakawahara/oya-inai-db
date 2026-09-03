// ============================================================================
// 移行: 事実時間軸（Track A Phase 2）— SCHEMA_CONVENTION v3.5 §7.10
// ============================================================================
// 冪等。何度流しても2回目以降は 0 件更新・AuditLog も増えない。
// 実行前に必ずバックアップ（scripts/backup.sh）。実行は管理者が cypher-shell か
// Neo4j Browser で行う。実データの内容は出力しない（件数のみ）。
//
// 既存データの初期値（技術仕様 §3-1）:
//   registeredAt = coalesce(registeredAt, lastConfirmedAt, 移行実行日)
//   HAS_KEY_PERSON.status = 'Active', startDate = coalesce(startDate, 移行実行日)
// startDate の真の開始日は不明なので移行実行日を入れる。その旨を AuditLog に残す。

// --- 1. 事実ノードの registeredAt ------------------------------------------------
MATCH (n)
WHERE (n:NgAction OR n:CarePreference) AND n.registeredAt IS NULL
SET n.registeredAt = coalesce(date(n.lastConfirmedAt), date())
RETURN count(n) AS registeredAt_filled;

// --- 2. HAS_KEY_PERSON の status / startDate --------------------------------------
MATCH ()-[r:HAS_KEY_PERSON]->()
WHERE r.status IS NULL
SET r.status = 'Active', r.startDate = coalesce(date(r.startDate), date())
RETURN count(r) AS key_person_rels_initialized;

// --- 3. 移行の記録（AuditLog 1件・冪等）---------------------------------------------
MERGE (a:AuditLog {action: 'migration', details: 'valid-time-axis phase2'})
ON CREATE SET a.timestamp = datetime(),
              a.user = 'migration',
              a.targetType = 'Schema',
              a.targetName = 'NgAction / CarePreference / HAS_KEY_PERSON',
              a.note = 'registeredAt は lastConfirmedAt（無ければ移行実行日）で初期化。HAS_KEY_PERSON.startDate は真の開始日が不明のため移行実行日を仮置き'
RETURN a.timestamp AS migrated_at;
