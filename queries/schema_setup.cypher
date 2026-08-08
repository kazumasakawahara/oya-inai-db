// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Neo4j スキーマセットアップ
// 親亡き後支援データベース - パフォーマンス最適化とデータ品質向上
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// ━━━ インデックス作成 ━━━

// クライアント名での高速検索
CREATE INDEX client_name_idx IF NOT EXISTS FOR (c:Client) ON (c.name);

// 禁忌事項のリスクレベル別検索
CREATE INDEX ng_action_risk_idx IF NOT EXISTS FOR (n:NgAction) ON (n.riskLevel);

// 推奨ケアのカテゴリ別検索
CREATE INDEX care_pref_category_idx IF NOT EXISTS FOR (cp:CarePreference) ON (cp.category);

// 手帳・受給者証の更新期限検索
CREATE INDEX certificate_renewal_idx IF NOT EXISTS FOR (cert:Certificate) ON (cert.nextRenewalDate);

// 支援記録の日付検索（NEW）
CREATE INDEX support_log_date_idx IF NOT EXISTS FOR (log:SupportLog) ON (log.date);

// 支援記録の効果別検索（NEW）
CREATE INDEX support_log_effectiveness_idx IF NOT EXISTS FOR (log:SupportLog) ON (log.effectiveness);

// ━━━ ユニーク制約 ━━━

// クライアント名の一意性保証
CREATE CONSTRAINT client_name_unique IF NOT EXISTS
FOR (c:Client) REQUIRE c.name IS UNIQUE;

// ━━━ ノード重複防止インデックス（Dedup） ━━━

// sourceHash による冪等性チェック
CREATE INDEX supportlog_sourcehash_idx IF NOT EXISTS FOR (log:SupportLog) ON (log.sourceHash);
CREATE INDEX meetingrecord_sourcehash_idx IF NOT EXISTS FOR (mr:MeetingRecord) ON (mr.sourceHash);
CREATE INDEX lifehistory_sourcehash_idx IF NOT EXISTS FOR (lh:LifeHistory) ON (lh.sourceHash);
CREATE INDEX wish_sourcehash_idx IF NOT EXISTS FOR (w:Wish) ON (w.sourceHash);

// ━━━ テストデータの投入（開発用） ━━━

// サンプル SupportLog ノード（既存データがない場合のみ）
MERGE (c:Client {name: 'サンプル太郎'})
ON CREATE SET
  c.dob = date('1990-01-01'),
  c.bloodType = 'A型'
WITH c
MERGE (s:Supporter {name: '田中ヘルパー'})
ON CREATE SET
  s.role = 'ホームヘルパー',
  s.experience = 5
WITH c, s
MERGE (log:SupportLog {
  date: date('2024-12-21'),
  situation: 'パニック時',
  action: '5分間静かに見守り、落ち着いてから声かけ',
  effectiveness: 'Effective',
  note: '予定変更時のパニック。5分後に自然に落ち着いた。'
})
MERGE (s)-[:LOGGED]->(log)-[:ABOUT]->(c);

// サンプル禁忌事項
MERGE (c:Client {name: 'サンプル太郎'})
WITH c
MERGE (ng:NgAction {
  action: '後ろから急に声をかける',
  reason: 'パニックを誘発し、自傷行為につながる可能性',
  riskLevel: 'Panic'
})
MERGE (c)-[:MUST_AVOID]->(ng);

// サンプル推奨ケア
MERGE (c:Client {name: 'サンプル太郎'})
WITH c
MERGE (cp:CarePreference {
  category: 'パニック時',
  instruction: '静かに見守り、5分待つ',
  priority: 'High'
})
MERGE (c)-[:REQUIRES]->(cp);

// ━━━ 統計情報の確認 ━━━

// インデックス一覧
SHOW INDEXES;

// ノード数の確認
MATCH (n)
RETURN labels(n)[0] as ノードタイプ, count(*) as 件数
ORDER BY 件数 DESC;
