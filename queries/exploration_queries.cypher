// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Neo4jブラウザ探索用クエリ集
// 親亡き後支援データベース - Living Database Edition
//
// 使い方: このファイルをNeo4j Browserで開き、
//         クエリをコピー＆実行してください。
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 基本探索
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// 【1】クライアント全体像の可視化（2ホップ）
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 使い方: 'クライアント名' を実際の名前に置き換えてください
MATCH path = (c:Client {name: 'クライアント名'})-[*1..2]-()
RETURN path
LIMIT 100;

// 例: 山田健太さんの全体像
MATCH path = (c:Client {name: '山田健太'})-[*1..2]-()
RETURN path
LIMIT 100;


// 【2】すべてのクライアント一覧
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Client)
RETURN c.name as 名前,
       c.dob as 生年月日,
       c.bloodType as 血液型
ORDER BY c.name;


// 【3】データベース全体の構造を可視化
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH path = ()-[]-()
RETURN path
LIMIT 300;


// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 安全管理（禁忌事項）
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// 【4】禁忌事項マップ（最重要）
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Client)-[:PROHIBITED|MUST_AVOID]->(ng:NgAction)
OPTIONAL MATCH (ng)-[:RELATES_TO|IN_CONTEXT]->(cond:Condition)
RETURN c, ng, cond;


// 【5】リスクレベル別の禁忌事項
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Client)-[:PROHIBITED|MUST_AVOID]->(ng:NgAction)
RETURN ng.riskLevel as リスクレベル,
       collect({
         クライアント: c.name,
         禁忌: ng.action,
         理由: ng.reason
       }) as 詳細
ORDER BY
  CASE ng.riskLevel
    WHEN 'LifeThreatening' THEN 1
    WHEN 'Panic' THEN 2
    WHEN 'Discomfort' THEN 3
  END;


// 【6】特定クライアントの禁忌事項詳細
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Client {name: 'クライアント名'})-[:PROHIBITED|MUST_AVOID]->(ng:NgAction)
RETURN ng.action as 禁忌事項,
       ng.reason as 理由,
       ng.riskLevel as リスクレベル
ORDER BY
  CASE ng.riskLevel
    WHEN 'LifeThreatening' THEN 1
    WHEN 'Panic' THEN 2
    WHEN 'Discomfort' THEN 3
  END;


// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// ケア推奨
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// 【7】推奨ケアの可視化
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Client)-[:PREFERS|REQUIRES]->(cp:CarePreference)
RETURN c, cp;


// 【8】カテゴリ別の推奨ケア
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Client {name: 'クライアント名'})-[:PREFERS|REQUIRES]->(cp:CarePreference)
RETURN cp.category as カテゴリ,
       cp.instruction as 具体的方法,
       cp.priority as 優先度
ORDER BY
  CASE cp.priority
    WHEN 'High' THEN 1
    WHEN 'Medium' THEN 2
    WHEN 'Low' THEN 3
  END;


// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 支援記録分析（Living Database）
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// 【9】支援記録の可視化（時系列）
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (s:Supporter)-[:LOGGED]->(log:SupportLog)-[:ABOUT]->(c:Client)
RETURN s, log, c
ORDER BY log.date DESC
LIMIT 50;


// 【10】効果的だった支援記録（頻度順）
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Client)<-[:ABOUT]-(log:SupportLog)
WHERE log.effectiveness = 'Effective'
WITH c, log.situation as 状況, log.action as 対応, count(*) as 頻度
WHERE 頻度 >= 2
RETURN c.name as クライアント, 状況, 対応, 頻度
ORDER BY 頻度 DESC;


// 【11】特定クライアントの支援記録履歴
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (s:Supporter)-[:LOGGED]->(log:SupportLog)-[:ABOUT]->(c:Client {name: 'クライアント名'})
RETURN log.date as 日付,
       s.name as 支援者,
       log.situation as 状況,
       log.action as 対応,
       log.effectiveness as 効果,
       log.note as メモ
ORDER BY log.date DESC
LIMIT 20;


// 【12】支援者別の記録数
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (s:Supporter)-[:LOGGED]->(log:SupportLog)
RETURN s.name as 支援者,
       s.role as 役割,
       count(log) as 記録数
ORDER BY 記録数 DESC;


// 【13】効果別の支援記録統計
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (log:SupportLog)
RETURN log.effectiveness as 効果,
       count(*) as 件数
ORDER BY 件数 DESC;


// 【14】最近1週間の支援記録
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (s:Supporter)-[:LOGGED]->(log:SupportLog)-[:ABOUT]->(c:Client)
WHERE log.date >= date() - duration({days: 7})
RETURN log.date as 日付,
       c.name as クライアント,
       s.name as 支援者,
       log.situation as 状況,
       log.effectiveness as 効果
ORDER BY log.date DESC;


// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 緊急連絡網
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// 【15】緊急連絡網の可視化
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH path = (c:Client)-[:EMERGENCY_CONTACT|HAS_KEY_PERSON|HAS_GUARDIAN|HAS_LEGAL_REP*1..2]->()
RETURN path;


// 【16】優先度順の緊急連絡先
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Client {name: 'クライアント名'})-[r:EMERGENCY_CONTACT|HAS_KEY_PERSON]->(kp:KeyPerson)
RETURN kp.name as 氏名,
       kp.relationship as 続柄,
       kp.phone as 電話番号,
       r.priority as 優先度,
       r.rank as ランク
ORDER BY coalesce(r.priority, r.rank);


// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 法的基盤
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// 【17】更新期限が近い証明書（3ヶ月以内）
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Client)-[:HOLDS|HAS_CERTIFICATE]->(cert:Certificate)
WHERE cert.nextRenewalDate <= date() + duration({months: 3})
RETURN c.name as クライアント,
       cert.type as 種別,
       cert.grade as 等級,
       cert.nextRenewalDate as 更新期限,
       duration.between(date(), cert.nextRenewalDate).days as 残日数
ORDER BY cert.nextRenewalDate;


// 【18】手帳・受給者証の一覧
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Client)-[:HOLDS|HAS_CERTIFICATE]->(cert:Certificate)
RETURN c.name as クライアント,
       cert.type as 種別,
       cert.grade as 等級,
       cert.nextRenewalDate as 次回更新日
ORDER BY c.name, cert.type;


// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// パターン発見と分析
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// 【19】複数クライアント間の共通特性
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c1:Client)-[:HAS_CONDITION]->(cond:Condition)<-[:HAS_CONDITION]-(c2:Client)
WHERE c1 <> c2 AND id(c1) < id(c2)
RETURN c1.name as クライアント1,
       c2.name as クライアント2,
       cond.name as 共通特性;


// 【20】特性と禁忌の関連性
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Client)-[:HAS_CONDITION]->(cond:Condition)
MATCH (c)-[:PROHIBITED|MUST_AVOID]->(ng:NgAction)-[:RELATES_TO|IN_CONTEXT]->(cond)
RETURN cond.name as 特性,
       collect(DISTINCT ng.action) as 関連する禁忌事項,
       count(DISTINCT c) as 該当クライアント数
ORDER BY 該当クライアント数 DESC;


// 【21】状況別の効果的な対応パターン
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (log:SupportLog)
WHERE log.effectiveness = 'Effective'
WITH log.situation as 状況, log.action as 対応, count(*) as 頻度
WHERE 頻度 >= 2
RETURN 状況, 対応, 頻度
ORDER BY 状況, 頻度 DESC;


// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// データ品質チェック
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// 【22】禁忌事項が登録されていないクライアント
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Client)
WHERE NOT (c)-[:PROHIBITED|MUST_AVOID]->(:NgAction)
RETURN c.name as クライアント名,
       '⚠️ 禁忌事項未登録' as 注意;


// 【23】緊急連絡先が登録されていないクライアント
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Client)
WHERE NOT (c)-[:EMERGENCY_CONTACT|HAS_KEY_PERSON]->(:KeyPerson)
  AND NOT (c)-[:HAS_GUARDIAN|HAS_LEGAL_REP]->(:Guardian)
RETURN c.name as クライアント名,
       '⚠️ 緊急連絡先未登録' as 注意;


// 【24】支援記録がまだないクライアント
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Client)
WHERE NOT (c)<-[:ABOUT]-(:SupportLog)
RETURN c.name as クライアント名,
       '📝 支援記録未登録' as 注意;


// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 統計情報
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// 【25】データベース全体統計
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (n)
RETURN labels(n)[0] as ノードタイプ,
       count(*) as 件数
ORDER BY 件数 DESC;


// 【26】リレーションシップ統計
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH ()-[r]->()
RETURN type(r) as リレーションシップタイプ,
       count(*) as 件数
ORDER BY 件数 DESC;


// 【27】クライアント別データ充実度
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Client)
OPTIONAL MATCH (c)-[:PROHIBITED|MUST_AVOID]->(ng:NgAction)
OPTIONAL MATCH (c)-[:PREFERS|REQUIRES]->(cp:CarePreference)
OPTIONAL MATCH (c)<-[:ABOUT]-(log:SupportLog)
OPTIONAL MATCH (c)-[:EMERGENCY_CONTACT|HAS_KEY_PERSON]->(kp:KeyPerson)
RETURN c.name as クライアント,
       count(DISTINCT ng) as 禁忌事項数,
       count(DISTINCT cp) as 推奨ケア数,
       count(DISTINCT log) as 支援記録数,
       count(DISTINCT kp) as 緊急連絡先数
ORDER BY c.name;


// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 高度な分析クエリ
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// 【28】支援者の経験値分析
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (s:Supporter)-[:LOGGED]->(log:SupportLog)
WITH s,
     count(log) as 総記録数,
     sum(CASE WHEN log.effectiveness = 'Effective' THEN 1 ELSE 0 END) as 効果的だった回数
RETURN s.name as 支援者,
       総記録数,
       効果的だった回数,
       round(toFloat(効果的だった回数) / 総記録数 * 100, 1) as 効果率
ORDER BY 効果率 DESC;


// 【29】時系列でみる支援の改善
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Client {name: 'クライアント名'})<-[:ABOUT]-(log:SupportLog)
RETURN log.date as 日付,
       log.situation as 状況,
       log.effectiveness as 効果,
       log.action as 対応
ORDER BY log.date ASC;


// 【30】禁忌事項と推奨ケアの対応関係
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Client)-[:PROHIBITED|MUST_AVOID]->(ng:NgAction)
MATCH (c)-[:PREFERS|REQUIRES]->(cp:CarePreference)
OPTIONAL MATCH (ng)-[:RELATES_TO|IN_CONTEXT]->(cond:Condition)<-[:ADDRESSES]-(cp)
RETURN c.name as クライアント,
       ng.action as 禁忌事項,
       cp.instruction as 推奨ケア,
       cond.name as 関連特性;
