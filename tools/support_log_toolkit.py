"""
SupportLogToolkit - 支援記録・知識更新用ツールキット

書込み操作を提供:
- analyze_narrative: 物語形式のテキストから構造化データを抽出（確認用プレビュー）
- register_support_data: 確認済みの構造化データを一括登録
- add_ng_action: 禁忌事項の追加（単体登録用）
- add_care_preference: 推奨ケアの追加（単体登録用）

【重要な処理フロー】
1. 支援者がナラティブを報告 → analyze_narrative で構造化
2. 構造化結果をユーザーに提示して確認
3. 確認後 → register_support_data で一括登録

この順序を守ることで、重複登録を防ぎます。
"""

import json
from typing import Optional
from datetime import datetime
from agno.tools import Toolkit
from lib.db_new_operations import run_query, resolve_client, create_audit_log
from lib.ai_extractor import extract_from_text, graph_to_tree


class SupportLogToolkit(Toolkit):
    def __init__(self):
        super().__init__(
            name="support_log_toolkit",
            instructions=(
                "支援記録を登録し、ケア知識を更新するためのツールキットです。\n\n"
                "【重要】登録の前に必ず analyze_narrative を使用してください！\n"
                "1. analyze_narrative: まず物語形式のテキストを構造化データに変換\n"
                "2. ユーザーに抽出結果を提示して確認を取る\n"
                "3. register_support_data: 確認後に一括登録\n\n"
                "単体登録ツール（analyze_narrative不要の場合のみ使用）:\n"
                "- add_ng_action: 明確な禁忌事項を単体で登録\n"
                "- add_care_preference: 明確なケア方法を単体で登録"
            ),
            tools=[
                self.analyze_narrative,
                self.register_support_data,
                self.add_ng_action,
                self.add_care_preference,
            ],
        )

    def analyze_narrative(
        self,
        narrative_text: str,
        client_name: str = "",
        supporter_name: str = "AIエージェント"
    ) -> str:
        """
        物語形式のテキストから支援記録・禁忌事項・ケア推奨を抽出します。
        ※ このツールはデータベースに登録しません。確認用のプレビューを返します。

        【重要】支援者から出来事の報告を受けたら、最初にこのツールを呼び出してください。

        Args:
            narrative_text: 支援者からの報告テキスト（例: 「サイレンでパニックになったので静かな部屋に移動した」）
            client_name: クライアント名（省略時はテキストから自動検出を試みます）
            supporter_name: 記録者の名前

        Returns:
            抽出結果のJSON（support_logs, ng_actions, care_preferences）
            ユーザーに提示して確認を取り、register_support_data で登録してください。
        """
        if not narrative_text or not narrative_text.strip():
            return json.dumps({
                "status": "error",
                "message": "テキストが入力されていません"
            }, ensure_ascii=False)

        # AIで構造化データを抽出
        extracted = extract_from_text(narrative_text, client_name if client_name else None)

        if not extracted:
            return json.dumps({
                "status": "error",
                "message": "テキストから情報を抽出できませんでした。"
            }, ensure_ascii=False)

        # グラフ形式→ツリー形式に変換（プレビュー用）
        tree_data = graph_to_tree(extracted)

        # クライアント名の確定
        detected_client = tree_data.get("client", {}).get("name", "")
        final_client_name = client_name if client_name else detected_client

        if not final_client_name:
            return json.dumps({
                "status": "needs_client",
                "message": "クライアント名を特定できませんでした。名前を指定して再度お試しください。",
                "extracted_preview": tree_data
            }, ensure_ascii=False)

        # クライアントの存在確認
        client = resolve_client(final_client_name)
        if not client:
            return json.dumps({
                "status": "client_not_found",
                "message": f"クライアント「{final_client_name}」が見つかりません。",
                "extracted_preview": tree_data
            }, ensure_ascii=False)

        # 抽出結果を整理
        support_logs = tree_data.get("supportLogs", [])
        ng_actions = tree_data.get("ngActions", [])
        care_prefs = tree_data.get("carePreferences", [])

        # supporter_name を設定
        for log in support_logs:
            if not log.get("supporter"):
                log["supporter"] = supporter_name

        result = {
            "status": "preview",
            "message": "以下の内容を登録します。よろしければ register_support_data を呼び出してください。",
            "client_name": client.get("name"),
            "data": {
                "support_logs": support_logs,
                "ng_actions": ng_actions,
                "care_preferences": care_prefs
            },
            "summary": {
                "support_logs_count": len(support_logs),
                "ng_actions_count": len(ng_actions),
                "care_preferences_count": len(care_prefs)
            }
        }

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    def register_support_data(
        self,
        client_name: str,
        extracted_data_json: str,
        supporter_name: str = "AIエージェント"
    ) -> str:
        """
        analyze_narrative で抽出・確認済みのデータを一括登録します。

        【重要】このツールを直接呼び出さないでください！
        必ず先に analyze_narrative でデータを抽出し、ユーザー確認を取ってから呼び出してください。

        Args:
            client_name: クライアントの正式名称
            extracted_data_json: analyze_narrativeの出力のdataフィールド（JSON文字列）
                例: {"support_logs": [...], "ng_actions": [...], "care_preferences": [...]}
            supporter_name: 記録者の名前

        Returns:
            登録結果のJSON
        """
        # JSONをパース
        try:
            data = json.loads(extracted_data_json) if isinstance(extracted_data_json, str) else extracted_data_json
            support_logs = data.get("support_logs", [])
            ng_actions = data.get("ng_actions", [])
            care_preferences = data.get("care_preferences", [])
        except json.JSONDecodeError:
            return json.dumps({
                "status": "error",
                "message": "extracted_data_json のパースに失敗しました。JSON形式で渡してください。"
            }, ensure_ascii=False)

        # クライアントの存在確認
        client = resolve_client(client_name)
        if not client:
            return json.dumps({
                "status": "error",
                "message": f"クライアント「{client_name}」が見つかりません。"
            }, ensure_ascii=False)

        official_name = client.get("name")
        today = datetime.now().strftime("%Y-%m-%d")
        results = {"support_logs": 0, "ng_actions": 0, "care_preferences": 0, "errors": []}

        # Supporter ノードを作成/取得
        run_query("""
            MERGE (s:Supporter {name: $supporter})
        """, {"supporter": supporter_name})

        # 1. 支援記録の登録
        if support_logs:
            for log in support_logs:
                try:
                    log_date = log.get("date", today)
                    situation = log.get("situation", "")
                    action = log.get("action", "")
                    effectiveness = log.get("effectiveness", "Neutral")
                    note = log.get("note", "")
                    log_supporter = log.get("supporter", supporter_name)

                    result = run_query("""
                        MATCH (c:Client {name: $client_name})
                        MATCH (s:Supporter {name: $supporter})

                        CREATE (log:SupportLog {
                            date: date($date),
                            situation: $situation,
                            action: $action,
                            effectiveness: $effectiveness,
                            note: $note,
                            createdAt: datetime()
                        })

                        CREATE (s)-[:LOGGED]->(log)-[:ABOUT]->(c)

                        RETURN log.date AS date
                    """, {
                        "client_name": official_name,
                        "supporter": log_supporter,
                        "date": log_date,
                        "situation": situation,
                        "action": action,
                        "effectiveness": effectiveness,
                        "note": note
                    })

                    if result:
                        results["support_logs"] += 1
                        create_audit_log(
                            user_name=log_supporter,
                            action="CREATE",
                            target_type="SupportLog",
                            target_name=f"{situation[:30]}...",
                            details=f"対応: {action[:50]}, 効果: {effectiveness}",
                            client_name=official_name
                        )
                except Exception as e:
                    results["errors"].append(f"SupportLog登録エラー: {str(e)}")

        # 2. 禁忌事項の登録
        if ng_actions:
            for ng in ng_actions:
                try:
                    action = ng.get("action", "")
                    reason = ng.get("reason", "")
                    risk_level = ng.get("riskLevel", "High")

                    if not action:
                        continue

                    # 重複チェック
                    existing = run_query("""
                        MATCH (c:Client {name: $client_name})-[:MUST_AVOID]->(ng:NgAction)
                        WHERE ng.action = $action
                        RETURN ng
                    """, {"client_name": official_name, "action": action})

                    if existing:
                        continue  # 重複はスキップ

                    result = run_query("""
                        MATCH (c:Client {name: $client_name})

                        CREATE (ng:NgAction {
                            action: $action,
                            reason: $reason,
                            riskLevel: $risk_level,
                            createdAt: datetime()
                        })

                        CREATE (c)-[:MUST_AVOID]->(ng)

                        RETURN ng.action AS action
                    """, {
                        "client_name": official_name,
                        "action": action,
                        "reason": reason,
                        "risk_level": risk_level
                    })

                    if result:
                        results["ng_actions"] += 1
                        create_audit_log(
                            user_name=supporter_name,
                            action="CREATE",
                            target_type="NgAction",
                            target_name=action,
                            details=f"理由: {reason}, リスク: {risk_level}",
                            client_name=official_name
                        )
                except Exception as e:
                    results["errors"].append(f"NgAction登録エラー: {str(e)}")

        # 3. ケア推奨の登録
        if care_preferences:
            for pref in care_preferences:
                try:
                    category = pref.get("category", "その他")
                    instruction = pref.get("instruction", "")
                    priority = pref.get("priority", "Medium")

                    if not instruction:
                        continue

                    result = run_query("""
                        MATCH (c:Client {name: $client_name})

                        MERGE (cp:CarePreference {
                            category: $category,
                            instruction: $instruction
                        })
                        SET cp.priority = $priority,
                            cp.updatedAt = datetime()

                        MERGE (c)-[:REQUIRES]->(cp)

                        RETURN cp.instruction AS instruction
                    """, {
                        "client_name": official_name,
                        "category": category,
                        "instruction": instruction,
                        "priority": priority
                    })

                    if result:
                        results["care_preferences"] += 1
                        create_audit_log(
                            user_name=supporter_name,
                            action="CREATE",
                            target_type="CarePreference",
                            target_name=f"{category}: {instruction[:30]}...",
                            details=f"優先度: {priority}",
                            client_name=official_name
                        )
                except Exception as e:
                    results["errors"].append(f"CarePreference登録エラー: {str(e)}")

        # 結果サマリ
        total = results["support_logs"] + results["ng_actions"] + results["care_preferences"]

        return json.dumps({
            "status": "success" if total > 0 else "no_data",
            "message": f"登録完了: 支援記録 {results['support_logs']}件、禁忌事項 {results['ng_actions']}件、ケア推奨 {results['care_preferences']}件",
            "client": official_name,
            "registered": results,
            "errors": results["errors"] if results["errors"] else None
        }, ensure_ascii=False, indent=2)

    def add_ng_action(
        self,
        client_name: str,
        action: str,
        reason: str,
        risk_level: str = "High"
    ) -> str:
        """
        禁忌事項（避けるべき行動・状況）を登録します。
        これは安全に関わる重要な情報です。

        Args:
            client_name: クライアントの正式名称
            action: 避けるべき行動・状況（例: 「大きな音」「牛乳を与える」）
            reason: 理由（例: 「パニックの原因になる」「アレルギーがある」）
            risk_level: リスクレベル（'High'=高, 'Medium'=中, 'Low'=低）

        Returns:
            登録結果のJSON
        """
        # クライアントの存在確認
        client = resolve_client(client_name)
        if not client:
            return json.dumps({
                "status": "error",
                "message": f"クライアント「{client_name}」が見つかりません。"
            }, ensure_ascii=False)

        official_name = client.get("name")

        # NgAction を作成（重複チェック付き）
        existing = run_query("""
            MATCH (c:Client {name: $client_name})-[:MUST_AVOID]->(ng:NgAction)
            WHERE ng.action = $action
            RETURN ng
        """, {"client_name": official_name, "action": action})

        if existing:
            return json.dumps({
                "status": "exists",
                "message": f"禁忌事項「{action}」は既に登録されています。"
            }, ensure_ascii=False)

        result = run_query("""
            MATCH (c:Client {name: $client_name})

            CREATE (ng:NgAction {
                action: $action,
                reason: $reason,
                riskLevel: $risk_level,
                createdAt: datetime()
            })

            CREATE (c)-[:MUST_AVOID]->(ng)

            RETURN ng.action AS action
        """, {
            "client_name": official_name,
            "action": action,
            "reason": reason,
            "risk_level": risk_level
        })

        if result:
            # 監査ログを記録（安全に関わる重要データ）
            create_audit_log(
                user_name="AIエージェント",
                action="CREATE",
                target_type="NgAction",
                target_name=action,
                details=f"理由: {reason}, リスク: {risk_level}",
                client_name=official_name
            )

            return json.dumps({
                "status": "success",
                "message": f"禁忌事項を登録しました: 「{action}」を避けてください。",
                "data": {
                    "client": official_name,
                    "action": action,
                    "reason": reason,
                    "risk_level": risk_level
                }
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "status": "error",
                "message": "禁忌事項の登録に失敗しました。"
            }, ensure_ascii=False)

    def add_care_preference(
        self,
        client_name: str,
        category: str,
        instruction: str,
        priority: str = "Medium",
        reason: str = ""
    ) -> str:
        """
        効果的なケア方法・推奨事項を登録します。
        成功したケアパターンを記録し、他の支援者と共有します。

        Args:
            client_name: クライアントの正式名称
            category: カテゴリ（例: 「パニック時」「食事」「入浴」「外出」）
            instruction: 具体的な方法（例: 「静かな部屋に移動して5分待つ」）
            priority: 優先度（'High'=高, 'Medium'=中, 'Low'=低）
            reason: この方法が効果的な理由（任意）

        Returns:
            登録結果のJSON
        """
        # クライアントの存在確認
        client = resolve_client(client_name)
        if not client:
            return json.dumps({
                "status": "error",
                "message": f"クライアント「{client_name}」が見つかりません。"
            }, ensure_ascii=False)

        official_name = client.get("name")

        # CarePreference を作成
        result = run_query("""
            MATCH (c:Client {name: $client_name})

            MERGE (cp:CarePreference {
                category: $category,
                instruction: $instruction
            })
            SET cp.priority = $priority,
                cp.reason = $reason,
                cp.updatedAt = datetime()

            MERGE (c)-[:REQUIRES]->(cp)

            RETURN cp.instruction AS instruction
        """, {
            "client_name": official_name,
            "category": category,
            "instruction": instruction,
            "priority": priority,
            "reason": reason
        })

        if result:
            # 監査ログを記録
            create_audit_log(
                user_name="AIエージェント",
                action="CREATE",
                target_type="CarePreference",
                target_name=f"{category}: {instruction[:30]}...",
                details=f"優先度: {priority}",
                client_name=official_name
            )

            return json.dumps({
                "status": "success",
                "message": f"ケア推奨事項を登録しました。",
                "data": {
                    "client": official_name,
                    "category": category,
                    "instruction": instruction,
                    "priority": priority
                }
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "status": "error",
                "message": "ケア推奨事項の登録に失敗しました。"
            }, ensure_ascii=False)
