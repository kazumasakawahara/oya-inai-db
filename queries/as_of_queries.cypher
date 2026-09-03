// ============================================================================
// 時点照会（事実時間軸・Track A Phase 2）— SCHEMA_CONVENTION v3.5 §7.10 / BRS-14
// ============================================================================
// 「2025年9月時点で有効だった禁忌は何か」「去年9月のキーパーソンは誰だったか」に
// 事実時間軸（validFrom / validTo・startDate / endDate）で答える。
// 「その時点で何を知っていたか」（知得軸）は既存の Review / CONFIRMS / AuditLog を
// reviewedAt / timestamp で絞れば出るので、ここには置かない。
//
// パラメータ: $name（Client.name）, $asOf（"YYYY-MM-DD"）
// 各クエリは ";" で区切る（api/tests/integration/test_as_of_queries.py が分割して実行する）。
// 日付プロパティは date 型で保存されている前提（文字列だと比較が null になり静かに漏れる。
// 書き込み経路が date に揃える）。

// --- Q1: 指定日 $asOf に有効だった禁忌（事実時間軸で引く）--------------------------
MATCH (c:Client {name: $name})-[:MUST_AVOID]->(n:NgAction)
WHERE coalesce(n.validFrom, n.registeredAt) <= date($asOf)
  AND (n.validTo IS NULL OR n.validTo > date($asOf))
RETURN n.action AS action, n.riskLevel AS riskLevel, n.status AS status,
       n.validFrom AS validFrom, n.validTo AS validTo, n.registeredAt AS registeredAt
ORDER BY n.riskLevel;

// --- Q2: 指定日 $asOf のキーパーソン ------------------------------------------------
MATCH (c:Client {name: $name})-[r:HAS_KEY_PERSON]->(kp:KeyPerson)
WHERE r.startDate <= date($asOf)
  AND (r.endDate IS NULL OR r.endDate > date($asOf))
RETURN kp.name AS name, kp.relationship AS relationship, r.rank AS rank,
       r.startDate AS startDate, r.endDate AS endDate
ORDER BY r.rank;
