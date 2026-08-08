"""
親亡き後支援データベース - AI構造化モジュール
テキストからの情報抽出、JSON構造化処理
"""

import os
import re
import json
import sys
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.google import Gemini

load_dotenv()


# --- ログ出力 ---
def log(message: str, level: str = "INFO"):
    """ログ出力（標準エラー出力）"""
    sys.stderr.write(f"[AI_Extractor:{level}] {message}\n")
    sys.stderr.flush()

# =============================================================================
# AI抽出用プロンプト（マニフェスト準拠）
# =============================================================================

EXTRACTION_PROMPT = """
あなたは障害福祉支援および生活保護受給者支援における専門的な「ナレッジグラフ抽出エージェント」です。
提供されたテキスト（支援記録、経過説明書、利用契約など）から、エンティティ（ノード）とそれらの関係性（リレーションシップ）を抽出し、厳格なJSONフォーマットで出力してください。

【最重要ルール - 厳守】
⚠️ 絶対に入力テキストにない情報を創作・推測しないでください ⚠️
- テキストに明示的に書かれていない情報は、絶対に出力しない
- 「一般的にこうだろう」という推測は禁止
- 入力テキストから直接引用できる情報のみを抽出する

【抽出の姿勢】
- 暗黙知を見逃さない：「〜すると落ち着く」「〜は嫌がる」を必ず拾う
- 禁忌事項（NgAction）は最優先：「絶対に〜しないで」「〜するとパニック」を漏らさない
- 支援記録（日報・レポート）も抽出：「今日〜した」「〜の対応で落ち着いた」
- テキスト内にクライアント（支援対象者）の名前がある場合は、必ず Client ノードを含めること

【日付の変換ルール - 重要】
元号（和暦）で入力された日付は必ず西暦（YYYY-MM-DD形式）に変換してください：
- 明治元年=1868年、大正元年=1912年、昭和元年=1926年、平成元年=1989年、令和元年=2019年
- 例: 「昭和50年3月15日」→「1975-03-15」、「令和5年1月10日」→「2023-01-10」

【厳守すべき命名規則】
以下のルールに違反した出力はシステムエラーを引き起こすため、例外なく厳守すること。

■ ノードラベル (PascalCase) - 許可されるラベルのみ使用:
Client, Condition, NgAction, CarePreference, KeyPerson, Guardian, Hospital, Certificate, PublicAssistance, Organization, Supporter, SupportLog, AuditLog, LifeHistory, Wish, ServiceProvider

■ リレーションシップタイプ (UPPER_SNAKE_CASE) - 許可されるタイプのみ使用:
HAS_CONDITION, MUST_AVOID, IN_CONTEXT, REQUIRES, ADDRESSES, HAS_KEY_PERSON, HAS_LEGAL_REP, HAS_CERTIFICATE, RECEIVES, REGISTERED_AT, TREATED_AT, SUPPORTED_BY, LOGGED, ABOUT, FOLLOWS, USES_SERVICE, HAS_HISTORY, HAS_WISH
※禁止: PROHIBITED, PREFERS などの旧名は絶対に使用しないこと。

■ プロパティ名 (camelCase):
name, dob, bloodType, riskLevel, date, situation, action, effectiveness, note, type, duration, nextAction, clientId

■ 列挙値:
- NgAction.riskLevel: "LifeThreatening", "Panic", "Discomfort"
- SupportLog.effectiveness: "Effective", "Ineffective", "Neutral", "Unknown"
- SupportLog.situation や CarePreference.category は日本語許容（例: "食事", "パニック時"）

【モデリングのルール】
- 支援記録は必ず SupportLog ノードとして独立させる
- 「誰が記録したか」は (Supporter)-[:LOGGED]->(SupportLog) で表現
- 「誰についての記録か」は (SupportLog)-[:ABOUT]->(Client) で表現

【出力形式】
以下のJSONスキーマに従い、JSONのみを出力すること。Markdownの ```json などのブロック記法は含めないこと。

{
  "nodes": [
    {
      "temp_id": "内部リンク用のユニークな仮ID（例: c1, s1, log1）",
      "label": "許可されたノードラベル",
      "properties": { "キー": "値" }
    }
  ],
  "relationships": [
    {
      "source_temp_id": "起点となるノードのtemp_id",
      "target_temp_id": "終点となるノードのtemp_id",
      "type": "許可されたリレーションシップタイプ",
      "properties": { "キー": "値" }
    }
  ]
}

【抽出例】
入力: "2026年3月9日、山田太郎さんの支援記録。鈴木支援員が対応。昼食の際、外で大きな工事音が鳴りパニックになった。パニック時は静かな別室に移動させることが効果的だった。今後は突然の大きな音を避けるよう配慮が必要（リスク：パニック）。"

出力:
{
  "nodes": [
    { "temp_id": "c1", "label": "Client", "properties": { "name": "山田太郎" } },
    { "temp_id": "s1", "label": "Supporter", "properties": { "name": "鈴木" } },
    { "temp_id": "log1", "label": "SupportLog", "properties": { "date": "2026-03-09", "situation": "食事", "action": "静かな別室に移動させた", "effectiveness": "Effective", "note": "昼食の際、外で大きな工事音が鳴りパニックになった。" } },
    { "temp_id": "ng1", "label": "NgAction", "properties": { "action": "突然の大きな音", "reason": "パニックを誘発するため", "riskLevel": "Panic" } },
    { "temp_id": "cp1", "label": "CarePreference", "properties": { "category": "パニック時", "instruction": "静かな別室に移動させる", "priority": "High" } }
  ],
  "relationships": [
    { "source_temp_id": "s1", "target_temp_id": "log1", "type": "LOGGED", "properties": {} },
    { "source_temp_id": "log1", "target_temp_id": "c1", "type": "ABOUT", "properties": {} },
    { "source_temp_id": "c1", "target_temp_id": "ng1", "type": "MUST_AVOID", "properties": {} },
    { "source_temp_id": "c1", "target_temp_id": "cp1", "type": "REQUIRES", "properties": {} }
  ]
}

【抽出ルール】
1. 「〜すると落ち着く」「〜が好き」→ CarePreference ノード + REQUIRES リレーション
2. 「〜は嫌がる」「〜するとパニック」→ NgAction ノード + MUST_AVOID リレーション（最重要！）
3. 「今日〜した」「〜の対応で効果があった」→ SupportLog ノード + LOGGED/ABOUT リレーション
4. 「〜に連絡して」「〜が後見人」→ KeyPerson + HAS_KEY_PERSON または Guardian + HAS_LEGAL_REP
5. 「来年の○月に更新」→ Certificate ノード + HAS_CERTIFICATE リレーション
6. 「かかりつけは○○病院」→ Hospital ノード + TREATED_AT リレーション

【最終確認】
出力前に必ず確認：この情報は入力テキストに明示的に書かれているか？
書かれていなければ、その項目は出力しないこと。
"""

# --- AIエージェント ---
_agent = None

def get_agent():
    """AIエージェントを取得（シングルトン）"""
    global _agent
    if _agent is None:
        _agent = Agent(
            model=Gemini(id="gemini-2.0-flash", api_key=os.getenv("GEMINI_API_KEY")),
            description="ナラティブから構造化データを抽出する専門家",
            instructions=[EXTRACTION_PROMPT],
            markdown=True
        )
    return _agent


def parse_json_from_response(response_text: str) -> dict | None:
    """
    AIレスポンスからJSONを抽出
    
    Args:
        response_text: AIからのレスポンステキスト
        
    Returns:
        パースされたdict、または失敗時はNone
    """
    try:
        # そのままJSONとしてパース試行（新プロンプトは生JSON出力を指示）
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    try:
        # フォールバック: ```json ... ``` を抽出（LLMが付与した場合）
        pattern = r'```json\s*(.*?)\s*```'
        match = re.search(pattern, response_text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except json.JSONDecodeError:
        pass
    return None


def _find_client_name_in_graph(extracted: dict) -> str:
    """グラフ形式の抽出結果からクライアント名を取得"""
    for node in extracted.get("nodes", []):
        if node.get("label") == "Client":
            return node.get("properties", {}).get("name", "不明")
    return "不明"


def _set_client_name_in_graph(extracted: dict, client_name: str) -> None:
    """グラフ形式の抽出結果でクライアント名を設定（追記モード用）"""
    for node in extracted.get("nodes", []):
        if node.get("label") == "Client":
            node["properties"]["name"] = client_name
            return
    # Client ノードがない場合は追加
    extracted.setdefault("nodes", []).insert(0, {
        "temp_id": "c1",
        "label": "Client",
        "properties": {"name": client_name}
    })


def extract_from_text(text: str, client_name: str = None) -> dict | None:
    """
    テキストから構造化データを抽出

    Args:
        text: 入力テキスト（ナラティブ、面談記録など）
        client_name: 既存クライアント名（追記モードの場合）

    Returns:
        グラフ形式の dict {nodes: [...], relationships: [...]}、または失敗時は None
    """
    agent = get_agent()

    # 追記モードの場合、クライアント名を追加
    prompt_text = text
    if client_name:
        prompt_text = f"【対象クライアント: {client_name}】\n\n{text}"

    try:
        log(f"テキスト抽出開始（{len(text)}文字）")
        response = agent.run(
            f"以下のテキストから情報を抽出してJSON形式で出力してください：\n\n{prompt_text}"
        )

        extracted = parse_json_from_response(response.content)

        if extracted:
            # 追記モードの場合、クライアント名を設定
            if client_name:
                _set_client_name_in_graph(extracted, client_name)
            log(f"抽出成功: クライアント={_find_client_name_in_graph(extracted)}")
            return extracted

        log("JSONパース失敗: AIレスポンスからJSONを抽出できませんでした", "WARN")
        return None

    except Exception as e:
        log(f"抽出エラー: {type(e).__name__}: {e}", "ERROR")
        return None


# =============================================================================
# 安全性チェック（Rule 1）
# =============================================================================

SAFETY_CHECK_PROMPT = """
あなたは「親亡き後支援データベース」の安全管理責任者です。
入力された「ナラティブ（行動）」と、登録されている「禁忌事項（NgAction）」を照合し、
**安全性違反（コンプライアンス違反）**がないかを判定してください。

【入力情報】
1. ナラティブ: {narrative}
2. 禁忌事項リスト: {ng_actions}

【判定ルール】
- ナラティブの内容が、禁忌事項（してはいけないこと）に抵触していないか？
- 抵触している場合は `is_violation: true` とし、警告メッセージを作成する。
- 抵触していない場合は `is_violation: false` とする。
- "Peanuts allergy" vs "Ate peanuts" -> Violation
- "Loud noise panic" vs "Went to rock concert" -> Violation

【出力形式】
JSONのみ出力してください。

```json
{{
  "is_violation": true/false,
  "warning": "深刻な違反です。禁忌事項「〜」に抵触しています。（違反がない場合はnull）",
  "risk_level": "High/Medium/Low/None"
}}
```
"""

def check_safety_compliance(narrative: str, ng_actions: list) -> dict:
    """
    ナラティブと禁忌事項を照合して安全性をチェック
    
    Args:
        narrative: 入力されたナラティブテキスト
        ng_actions: 禁忌事項のリスト [{'action': '...', 'riskLevel': '...'}]
        
    Returns:
        {"is_violation": bool, "warning": str, "risk_level": str}
    """
    if not ng_actions:
        return {"is_violation": False, "warning": None, "risk_level": "None"}
        
    agent = get_agent()
    
    # 禁忌事項をテキスト化
    ng_text = "\n".join([f"- {item.get('action')} (Risk: {item.get('riskLevel')})" for item in ng_actions])
    
    try:
        response = agent.run(
            SAFETY_CHECK_PROMPT.format(narrative=narrative, ng_actions=ng_text)
        )
        log("安全性チェック完了")
        result = parse_json_from_response(response.content)
        return result if result else {"is_violation": False, "warning": None, "risk_level": "None"}
    except Exception as e:
        import traceback
        log(f"安全性チェックエラー: {e}\n{traceback.format_exc()}", "ERROR")
        return {"is_violation": False, "warning": "チェック中にエラーが発生しました", "risk_level": "Unknown"}


# =============================================================================
# グラフ形式 ↔ ツリー形式 変換ユーティリティ
# =============================================================================

# ノードラベル → ツリーキー + リレーションタイプのマッピング
_LABEL_TO_TREE_KEY = {
    "Condition": "conditions",
    "NgAction": "ngActions",
    "CarePreference": "carePreferences",
    "SupportLog": "supportLogs",
    "Certificate": "certificates",
    "KeyPerson": "keyPersons",
    "Guardian": "guardians",
    "Hospital": "hospitals",
    "LifeHistory": "lifeHistories",
    "Wish": "wishes",
    "Supporter": "_supporters",  # ツリーでは独立キーにしない（内部用）
}


def graph_to_tree(graph: dict) -> dict:
    """
    グラフ形式 {nodes, relationships} → 旧ツリー形式に変換

    UI編集画面など、ツリー形式を期待するコードとの互換性のために使用。

    Args:
        graph: {"nodes": [...], "relationships": [...]}

    Returns:
        {"client": {...}, "conditions": [...], "ngActions": [...], ...}
    """
    tree = {
        "client": {"name": None, "dob": None, "bloodType": None},
        "conditions": [],
        "ngActions": [],
        "carePreferences": [],
        "supportLogs": [],
        "certificates": [],
        "keyPersons": [],
        "guardians": [],
        "hospitals": [],
        "lifeHistories": [],
        "wishes": [],
    }

    # temp_id → label のマップ（リレーション解決用）
    id_label_map = {}
    supporter_map = {}  # temp_id → supporter name

    for node in graph.get("nodes", []):
        label = node.get("label", "")
        props = node.get("properties", {})
        temp_id = node.get("temp_id", "")
        id_label_map[temp_id] = label

        if label == "Client":
            tree["client"] = {
                "name": props.get("name"),
                "dob": props.get("dob"),
                "bloodType": props.get("bloodType"),
                "kana": props.get("kana"),
                "aliases": props.get("aliases", []),
            }
        elif label == "Supporter":
            supporter_map[temp_id] = props.get("name", "")
        elif label in _LABEL_TO_TREE_KEY:
            key = _LABEL_TO_TREE_KEY[label]
            if not key.startswith("_"):
                tree[key].append(dict(props))

    # SupportLog に supporter 名を埋め込む（リレーションから解決）
    log_supporter = {}  # log_temp_id → supporter_name
    for rel in graph.get("relationships", []):
        if rel.get("type") == "LOGGED":
            src = rel.get("source_temp_id", "")
            tgt = rel.get("target_temp_id", "")
            if src in supporter_map:
                log_supporter[tgt] = supporter_map[src]

    for i, node in enumerate(graph.get("nodes", [])):
        if node.get("label") == "SupportLog":
            temp_id = node.get("temp_id", "")
            if temp_id in log_supporter:
                # supportLogs 内の対応する要素に supporter を設定
                props = node.get("properties", {})
                for sl in tree["supportLogs"]:
                    if sl.get("situation") == props.get("situation") and sl.get("date") == props.get("date"):
                        sl["supporter"] = log_supporter[temp_id]
                        break

    return tree


def tree_to_graph(tree: dict) -> dict:
    """
    旧ツリー形式 → グラフ形式 {nodes, relationships} に変換

    UI で編集されたツリー形式データを DB 登録用のグラフ形式に戻すために使用。

    Args:
        tree: {"client": {...}, "conditions": [...], ...}

    Returns:
        {"nodes": [...], "relationships": [...]}
    """
    nodes = []
    relationships = []
    counter = {"n": 0}

    def next_id(prefix="n"):
        counter["n"] += 1
        return f"{prefix}{counter['n']}"

    # Client
    client_id = next_id("c")
    client_props = {k: v for k, v in tree.get("client", {}).items() if v is not None}
    nodes.append({"temp_id": client_id, "label": "Client", "properties": client_props})

    # ラベル → (ツリーキー, リレーションタイプ, 方向) のマッピング
    mappings = [
        ("conditions", "Condition", "HAS_CONDITION", "client_to_node"),
        ("ngActions", "NgAction", "MUST_AVOID", "client_to_node"),
        ("carePreferences", "CarePreference", "REQUIRES", "client_to_node"),
        ("certificates", "Certificate", "HAS_CERTIFICATE", "client_to_node"),
        ("keyPersons", "KeyPerson", "HAS_KEY_PERSON", "client_to_node"),
        ("guardians", "Guardian", "HAS_LEGAL_REP", "client_to_node"),
        ("hospitals", "Hospital", "TREATED_AT", "client_to_node"),
        ("lifeHistories", "LifeHistory", "HAS_HISTORY", "client_to_node"),
        ("wishes", "Wish", "HAS_WISH", "client_to_node"),
    ]

    for tree_key, label, rel_type, direction in mappings:
        for item in tree.get(tree_key, []):
            if not item:
                continue
            node_id = next_id()
            props = {k: v for k, v in item.items() if v is not None and k != "relatedCondition"}
            nodes.append({"temp_id": node_id, "label": label, "properties": props})
            relationships.append({
                "source_temp_id": client_id,
                "target_temp_id": node_id,
                "type": rel_type,
                "properties": {},
            })

    # SupportLog（supporter → LOGGED → log → ABOUT → client）
    for sl in tree.get("supportLogs", []):
        if not sl or not sl.get("action"):
            continue
        supporter_name = sl.pop("supporter", None) or sl.pop("supporter", "不明")
        log_id = next_id("log")
        supporter_id = next_id("s")

        nodes.append({"temp_id": supporter_id, "label": "Supporter", "properties": {"name": supporter_name}})
        sl_props = {k: v for k, v in sl.items() if v is not None}
        nodes.append({"temp_id": log_id, "label": "SupportLog", "properties": sl_props})
        relationships.append({"source_temp_id": supporter_id, "target_temp_id": log_id, "type": "LOGGED", "properties": {}})
        relationships.append({"source_temp_id": log_id, "target_temp_id": client_id, "type": "ABOUT", "properties": {}})

    return {"nodes": nodes, "relationships": relationships}

