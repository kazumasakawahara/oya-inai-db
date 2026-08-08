"""
ClientQueryToolkit - クライアント情報取得用ツールキット

読取専用の操作を提供:
- verify_client: クライアント名の検証（曖昧検索対応）
- get_emergency_info: 緊急情報取得（禁忌事項、緊急連絡先）
- get_client_profile: クライアント詳細プロフィール
- list_clients: 登録クライアント一覧
"""

import json
from agno.tools import Toolkit
from lib.db_new_operations import run_query, resolve_client


class ClientQueryToolkit(Toolkit):
    def __init__(self):
        super().__init__(
            name="client_query_toolkit",
            instructions=(
                "クライアント情報を検索・取得するためのツールキットです。\n"
                "- verify_client: 名前からクライアントを特定（曖昧な場合は確認が必要）\n"
                "- get_emergency_info: 緊急時に必要な禁忌事項・連絡先を取得\n"
                "- get_client_profile: クライアントの詳細情報を取得\n"
                "- list_clients: 登録済みクライアント一覧を取得"
            ),
            tools=[
                self.verify_client,
                self.get_emergency_info,
                self.get_client_profile,
                self.list_clients,
            ],
        )

    def verify_client(self, name_input: str) -> str:
        """
        入力された名前からクライアントを特定します。
        曖昧な一致の場合は確認が必要なことを示します。

        Args:
            name_input: ユーザーが入力した名前（例: '山田さん', 'まりちゃん', '佐々木'）

        Returns:
            JSON形式の結果:
            - match_type='exact': 完全一致。そのまま処理を続行してOK
            - match_type='fuzzy': 曖昧一致。ユーザーに「〇〇さんのことでよろしいですか？」と確認必須
            - match_type='not_found': 該当なし。正しい名前を聞き直す
        """
        if not name_input or not name_input.strip():
            return json.dumps({
                "match_type": "not_found",
                "message": "名前が入力されていません"
            }, ensure_ascii=False)

        # 敬称を除去して正規化
        clean_name = name_input.strip()
        for suffix in ["さん", "くん", "ちゃん", "様", "氏", "殿", "San", "-san"]:
            if clean_name.endswith(suffix):
                clean_name = clean_name[:-len(suffix)].strip()
                break

        # 姓の抽出（日本語名の先頭2-3文字を姓と推定）
        # 例: "佐々木まり" → "佐々木"、"山田健太" → "山田"
        surname_candidates = []
        if len(clean_name) >= 2:
            surname_candidates.append(clean_name[:2])  # 2文字の姓
        if len(clean_name) >= 3:
            surname_candidates.append(clean_name[:3])  # 3文字の姓

        # スコアベースのマッチングクエリ
        # 姓の先頭一致も追加（「佐々木まり」→「佐々木真理」のケース対応）
        query = """
        MATCH (c:Client)
        OPTIONAL MATCH (c)-[:HAS_IDENTITY]->(i:Identity)
        WITH c, i, $input AS inputName, $clean AS cleanName, $surnames AS surnames

        // マッチスコアを計算
        WITH c, i, inputName, cleanName, surnames,
            CASE
                // 完全一致（最高優先度）
                WHEN COALESCE(i.name, c.name) = inputName THEN 100
                WHEN COALESCE(i.name, c.name) = cleanName THEN 100
                WHEN c.kana = inputName THEN 95
                WHEN c.kana = cleanName THEN 95
                // エイリアス完全一致
                WHEN inputName IN COALESCE(c.aliases, []) THEN 90
                WHEN cleanName IN COALESCE(c.aliases, []) THEN 90
                // 部分一致（曖昧）
                WHEN COALESCE(i.name, c.name) CONTAINS cleanName THEN 50
                WHEN cleanName CONTAINS COALESCE(i.name, c.name) THEN 50
                WHEN c.kana CONTAINS cleanName THEN 40
                WHEN cleanName CONTAINS c.kana THEN 40
                WHEN ANY(alias IN COALESCE(c.aliases, []) WHERE alias CONTAINS cleanName OR cleanName CONTAINS alias) THEN 30
                // 姓の先頭一致（「佐々木まり」→「佐々木真理」のケース）
                WHEN ANY(surname IN surnames WHERE
                    COALESCE(i.name, c.name) STARTS WITH surname AND size(surname) >= 2) THEN 25
                ELSE 0
            END AS score

        WHERE score > 0
        RETURN
            COALESCE(i.name, c.name) AS official_name,
            c.kana AS kana,
            COALESCE(c.aliases, []) AS aliases,
            score,
            CASE
                WHEN score >= 90 THEN 'exact'
                ELSE 'fuzzy'
            END AS match_type
        ORDER BY score DESC
        LIMIT 3
        """

        results = run_query(query, {
            "input": name_input,
            "clean": clean_name,
            "surnames": surname_candidates
        })

        if not results:
            return json.dumps({
                "match_type": "not_found",
                "input": name_input,
                "message": f"「{name_input}」に該当するクライアントが見つかりません。正しい氏名を確認してください。"
            }, ensure_ascii=False)

        best_match = results[0]

        if best_match["match_type"] == "exact":
            return json.dumps({
                "match_type": "exact",
                "official_name": best_match["official_name"],
                "input": name_input,
                "message": f"クライアント「{best_match['official_name']}」を特定しました。"
            }, ensure_ascii=False)
        else:
            # 曖昧一致の場合、候補を返す
            candidates = [r["official_name"] for r in results]
            return json.dumps({
                "match_type": "fuzzy",
                "suggested_name": best_match["official_name"],
                "candidates": candidates,
                "input": name_input,
                "message": f"「{best_match['official_name']}」のことでよろしいでしょうか？"
            }, ensure_ascii=False)

    def get_emergency_info(self, client_name: str) -> str:
        """
        緊急時に必要な情報を優先度順に取得します。

        取得順序（Safety First プロトコル）:
        1. NgAction（禁忌事項）- 最重要
        2. CarePreference（推奨ケア）
        3. KeyPerson（緊急連絡先）
        4. Hospital（かかりつけ医療機関）
        5. Guardian（後見人）

        Args:
            client_name: クライアントの正式名称

        Returns:
            緊急情報のJSON（禁忌事項、連絡先等）
        """
        query = """
        MATCH (c:Client)
        WHERE c.name = $name

        // 1. 禁忌事項（NgAction）- 最重要
        OPTIONAL MATCH (c)-[:MUST_AVOID]->(ng:NgAction)
        WITH c, collect(DISTINCT {
            action: ng.action,
            reason: ng.reason,
            riskLevel: ng.riskLevel
        }) AS ngActions

        // 2. 推奨ケア（CarePreference）
        OPTIONAL MATCH (c)-[:REQUIRES]->(cp:CarePreference)
        WITH c, ngActions, collect(DISTINCT {
            category: cp.category,
            instruction: cp.instruction,
            priority: cp.priority
        }) AS carePrefs

        // 3. 緊急連絡先（KeyPerson）
        OPTIONAL MATCH (c)-[kpRel:HAS_KEY_PERSON]->(kp:KeyPerson)
        WITH c, ngActions, carePrefs, collect(DISTINCT {
            rank: kpRel.rank,
            name: kp.name,
            relationship: kp.relationship,
            phone: kp.phone,
            role: kp.role
        }) AS keyPersons

        // 4. 医療機関（Hospital）
        OPTIONAL MATCH (c)-[:TREATED_AT]->(h:Hospital)
        WITH c, ngActions, carePrefs, keyPersons, collect(DISTINCT {
            name: h.name,
            specialty: h.specialty,
            phone: h.phone,
            doctor: h.doctor
        }) AS hospitals

        // 5. 後見人（Guardian）
        OPTIONAL MATCH (c)-[:HAS_LEGAL_REP]->(g:Guardian)

        RETURN
            c.name AS client_name,
            c.dob AS dob,
            c.bloodType AS bloodType,
            ngActions AS forbidden_actions,
            carePrefs AS recommended_care,
            keyPersons AS emergency_contacts,
            hospitals AS hospitals,
            collect(DISTINCT {
                name: g.name,
                type: g.type,
                phone: g.phone
            }) AS guardians
        """

        results = run_query(query, {"name": client_name})

        if not results or not results[0].get("client_name"):
            # フォールバック: 部分一致で検索
            fallback_query = query.replace("WHERE c.name = $name", "WHERE c.name CONTAINS $name")
            results = run_query(fallback_query, {"name": client_name})

            if not results or not results[0].get("client_name"):
                return json.dumps({
                    "error": f"クライアント「{client_name}」が見つかりません。",
                    "suggestion": "verify_client ツールで正しい名前を確認してください。"
                }, ensure_ascii=False)

        data = results[0]

        # null値を除去
        for key in ["forbidden_actions", "recommended_care", "emergency_contacts", "hospitals", "guardians"]:
            if data.get(key):
                data[key] = [item for item in data[key] if item.get("name") or item.get("action") or item.get("instruction")]

        return json.dumps(data, ensure_ascii=False, indent=2, default=str)

    def get_client_profile(self, client_name: str) -> str:
        """
        クライアントの詳細プロフィールを取得します（4つの柱に基づく）。

        Args:
            client_name: クライアントの正式名称

        Returns:
            詳細プロフィールのJSON
        """
        query = """
        MATCH (c:Client)
        WHERE c.name = $name OR c.name CONTAINS $name

        // 基本情報
        OPTIONAL MATCH (c)-[:HAS_IDENTITY]->(i:Identity)

        // Pillar 1: アイデンティティ
        OPTIONAL MATCH (c)-[:HAS_HISTORY]->(h:LifeHistory)
        OPTIONAL MATCH (c)-[:HAS_WISH]->(w:Wish)

        // Pillar 2: ケア情報
        OPTIONAL MATCH (c)-[:HAS_CONDITION]->(con:Condition)
        OPTIONAL MATCH (c)-[:REQUIRES]->(cp:CarePreference)
        OPTIONAL MATCH (c)-[:MUST_AVOID]->(ng:NgAction)

        // Pillar 3: 法的基盤
        OPTIONAL MATCH (c)-[:HAS_CERTIFICATE]->(cert:Certificate)

        // Pillar 4: 支援ネットワーク
        OPTIONAL MATCH (c)-[:HAS_KEY_PERSON]->(kp:KeyPerson)
        OPTIONAL MATCH (c)-[:HAS_LEGAL_REP]->(g:Guardian)
        OPTIONAL MATCH (c)-[:TREATED_AT]->(hosp:Hospital)

        RETURN
            COALESCE(i.name, c.name) AS name,
            c.dob AS dob,
            c.bloodType AS bloodType,
            c.kana AS kana,
            collect(DISTINCT {era: h.era, episode: h.episode}) AS life_history,
            collect(DISTINCT w.content) AS wishes,
            collect(DISTINCT con.name) AS conditions,
            collect(DISTINCT {category: cp.category, instruction: cp.instruction, priority: cp.priority}) AS care_preferences,
            collect(DISTINCT {action: ng.action, reason: ng.reason, riskLevel: ng.riskLevel}) AS ng_actions,
            collect(DISTINCT {type: cert.type, grade: cert.grade, renewal: cert.nextRenewalDate}) AS certificates,
            collect(DISTINCT {name: kp.name, relationship: kp.relationship, phone: kp.phone}) AS key_persons,
            collect(DISTINCT {name: g.name, type: g.type}) AS guardians,
            collect(DISTINCT {name: hosp.name, specialty: hosp.specialty}) AS hospitals
        LIMIT 1
        """

        results = run_query(query, {"name": client_name})

        if not results or not results[0].get("name"):
            return json.dumps({
                "error": f"クライアント「{client_name}」が見つかりません。"
            }, ensure_ascii=False)

        data = results[0]

        # null/空データをクリーンアップ
        for key in list(data.keys()):
            if isinstance(data[key], list):
                data[key] = [item for item in data[key] if item and (
                    isinstance(item, str) or
                    any(v for v in item.values() if v)
                )]

        return json.dumps(data, ensure_ascii=False, indent=2, default=str)

    def list_clients(self) -> str:
        """
        登録済みクライアントの一覧を取得します。

        Returns:
            クライアント名のリスト（JSON形式）
        """
        query = """
        MATCH (c:Client)
        OPTIONAL MATCH (c)-[:HAS_IDENTITY]->(i:Identity)
        RETURN
            COALESCE(i.name, c.name) AS name,
            c.kana AS kana,
            c.dob AS dob
        ORDER BY name
        """

        results = run_query(query)

        return json.dumps({
            "count": len(results),
            "clients": results
        }, ensure_ascii=False, indent=2, default=str)
