"""Safety First: emergency keyword detection + direct DB search (no LLM).

一刻を争う危機（「助けて」「倒れた」等）のみ発動し、直接DBから情報を返す。
「パニックになっています」等の状況報告はエージェント（LLM）に任せ、
エージェントが場面に応じて適切な情報を判断・提供する。
"""
import re
from app.lib.db_operations import run_query

# LLM を介さず直接DBから情報を返す「最後の砦」
# ここに該当するのは、一刻を争い LLM の判断を待てない場面のみ。
# 「パニックになっています」等の状況報告はエージェント（LLM）が判断すべきなので含めない。
CRISIS_KEYWORDS = {
    "パニック中",      # 今まさにパニック状態
    "倒れた", "倒れている",
    "SOS",
    "発作が",          # 発作が起きている
    "救急車",
    "助けて",
    "意識がない",
}

# 情報照会としてエージェント（LLM）に回すべきキーワード（Safety First を発動しない）
INQUIRY_INDICATORS = {"教えて", "調べて", "確認", "一覧", "リスト", "知りたい"}


def is_emergency(text: str) -> bool:
    """一刻を争う危機かどうかを判定。情報照会・状況報告は除外しエージェントに任せる。"""
    # まず情報照会かどうかを確認
    if any(kw in text for kw in INQUIRY_INDICATORS):
        return False
    return any(kw in text for kw in CRISIS_KEYWORDS)


def extract_client_name(text: str) -> str | None:
    """テキストからクライアント名（漢字2〜4文字 + さん）を抽出する。"""
    match = re.search(r"([一-龯]{2,4})\s?さん", text)
    return match.group(1) if match else None


def _find_client_name(text: str, message_history: list[str] | None = None) -> str | None:
    """現在のテキストまたは会話履歴からクライアント名を探す。"""
    # まず現在のメッセージから探す
    name = extract_client_name(text)
    if name:
        return name
    # 履歴を逆順（新しい順）に検索
    if message_history:
        for prev_msg in reversed(message_history):
            name = extract_client_name(prev_msg)
            if name:
                return name
    return None


def handle_emergency(text: str, message_history: list[str] | None = None) -> str:
    """緊急情報を直接DBから取得して返す。

    現在のメッセージにクライアント名がない場合、会話履歴から探す。
    """
    client_name = _find_client_name(text, message_history)
    if not client_name:
        return "クライアント名を特定できません。「〇〇さんの緊急情報」のように指定してください。"

    records = run_query("""
        MATCH (c:Client {name: $name})
        OPTIONAL MATCH (c)-[:MUST_AVOID]->(ng:NgAction)
        OPTIONAL MATCH (c)-[:REQUIRES]->(cp:CarePreference)
        OPTIONAL MATCH (c)-[kpRel:HAS_KEY_PERSON]->(kp:KeyPerson)
        OPTIONAL MATCH (c)-[:TREATED_AT]->(h:Hospital)
        OPTIONAL MATCH (c)-[:HAS_LEGAL_REP]->(g:Guardian)
        RETURN c, collect(DISTINCT ng) AS ng_actions,
               collect(DISTINCT cp) AS care_prefs,
               collect(DISTINCT kp {.*, rank: kpRel.rank}) AS key_persons,
               collect(DISTINCT h) AS hospitals, collect(DISTINCT g) AS guardians
    """, {"name": client_name})
    if not records:
        return f"「{client_name}」さんの情報が見つかりません。"

    r = records[0]
    parts = [f"## {client_name}さんの緊急情報\n"]

    # 禁忌事項
    ng_actions = r.get("ng_actions", [])
    if ng_actions:
        parts.append("### ⚠️ 禁忌事項（絶対にしてはいけないこと）")
        for ng in ng_actions:
            ng = dict(ng)
            parts.append(f"- **{ng.get('action','')}** [{ng.get('riskLevel','')}]: {ng.get('reason','')}")
    else:
        parts.append("### 禁忌事項\n登録されていません。")

    # 推奨ケア
    care_prefs = r.get("care_prefs", [])
    if care_prefs:
        parts.append("\n### 推奨ケア")
        for cp in care_prefs:
            cp = dict(cp)
            parts.append(f"- {cp.get('category','')}: {cp.get('instruction','')}")

    # 緊急連絡先
    key_persons = r.get("key_persons", [])
    if key_persons:
        parts.append("\n### 緊急連絡先")
        # rankでソート
        sorted_kps = sorted(key_persons, key=lambda kp: dict(kp).get("rank", 99))
        for kp in sorted_kps:
            kp = dict(kp)
            parts.append(f"- {kp.get('name','')} ({kp.get('relationship','')}): {kp.get('phone','N/A')}")

    # かかりつけ病院
    hospitals = r.get("hospitals", [])
    if hospitals:
        parts.append("\n### かかりつけ病院")
        for h in hospitals:
            h = dict(h)
            parts.append(f"- {h.get('name','')} TEL: {h.get('phone','N/A')}")

    return "\n".join(parts)
