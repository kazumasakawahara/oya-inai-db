"""Multi-provider chat agent using Agno framework.

Supports Gemini, Claude, OpenAI, and any future provider via Agno's
unified Agent interface. Tools (DB search functions) work identically
across all providers — Agno handles the protocol differences.

Provider is selected by CHAT_PROVIDER in .env.
"""
import json
import logging
import re
from pathlib import Path
from typing import Iterator

from agno.agent import Agent, RunEvent, RunOutputEvent

from app.config import settings

logger = logging.getLogger(__name__)
PROMPT_DIR = Path(__file__).parent / "prompts"

# ---------------------------------------------------------------------------
# DB Search Tools (provider-agnostic — Agno wraps them automatically)
# ---------------------------------------------------------------------------


def _resolve_client_name(client_name: str) -> tuple[str, str | None]:
    """クライアント名を解決する。

    Returns:
        (resolved_name, suggestion_note):
        - 完全一致 → (名前, None)
        - 部分一致 → (候補名, "「〇〇」さんは見つかりませんでしたが、「△△」さんが登録されています。...")
        - 該当なし → (元の名前, None)
    """
    from app.lib.db_operations import run_query

    exact = run_query(
        "MATCH (c:Client {name: $name}) RETURN c.name AS name LIMIT 1",
        {"name": client_name},
    )
    if exact:
        return exact[0]["name"], None

    # 姓（先頭2文字）で部分一致フォールバック
    partial = run_query(
        "MATCH (c:Client) WHERE c.name CONTAINS $partial RETURN c.name AS name LIMIT 5",
        {"partial": client_name[:2]},
    )
    if partial:
        candidates = [r["name"] for r in partial]
        note = (
            f"「{client_name}」さんは登録されていません。"
            f"もしかして「{'」「'.join(candidates)}」さんのことですか？"
            f" 以下は「{candidates[0]}」さんの情報です。"
        )
        return candidates[0], note

    return client_name, None


def search_client_info(client_name: str) -> str:
    """クライアントの基本情報（名前、生年月日、血液型、障害・状態）を検索します。

    Args:
        client_name: クライアント名
    """
    from app.lib.db_operations import run_query

    client_name, suggestion = _resolve_client_name(client_name)
    records = run_query("""
        MATCH (c:Client {name: $name})
        OPTIONAL MATCH (c)-[:HAS_CONDITION]->(cond:Condition)
        RETURN c.name AS name, c.dob AS dob, c.bloodType AS bloodType,
               collect(DISTINCT cond.name) AS conditions
    """, {"name": client_name})
    if not records:
        return json.dumps({"error": f"「{client_name}」さんの情報が見つかりません。"}, ensure_ascii=False)
    r = records[0]
    result = {k: str(v) if v is not None else None for k, v in r.items()}
    if suggestion:
        result["_suggestion"] = suggestion
    return json.dumps(result, ensure_ascii=False)


def search_emergency_contacts(client_name: str) -> str:
    """クライアントの緊急連絡先（キーパーソン：家族・親族等）を検索します。

    Args:
        client_name: クライアント名
    """
    from app.lib.db_operations import run_query
    client_name, suggestion = _resolve_client_name(client_name)

    records = run_query("""
        MATCH (c:Client {name: $name})-[rel:HAS_KEY_PERSON]->(kp:KeyPerson)
        RETURN kp.name AS name, kp.relationship AS relationship,
               kp.phone AS phone, rel.rank AS rank
        ORDER BY rel.rank ASC
    """, {"name": client_name})
    result = {"client_name": client_name, "contacts": [dict(r) for r in records]}
    if suggestion:
        result["_suggestion"] = suggestion
    return json.dumps(result, ensure_ascii=False, default=str)


def search_ng_actions(client_name: str) -> str:
    """クライアントの禁忌事項（絶対にしてはいけないこと）を検索します。パニック時・危険時に重要。

    Args:
        client_name: クライアント名
    """
    from app.lib.db_operations import run_query
    client_name, suggestion = _resolve_client_name(client_name)

    records = run_query("""
        MATCH (c:Client {name: $name})-[:MUST_AVOID]->(ng:NgAction)
        RETURN ng.action AS action, ng.reason AS reason, ng.riskLevel AS riskLevel
        ORDER BY CASE ng.riskLevel
            WHEN 'LifeThreatening' THEN 1 WHEN 'Panic' THEN 2 ELSE 3 END
    """, {"name": client_name})
    result = {"client_name": client_name, "ng_actions": [dict(r) for r in records]}
    if suggestion:
        result["_suggestion"] = suggestion
    return json.dumps(result, ensure_ascii=False)


def search_care_preferences(client_name: str) -> str:
    """クライアントの推奨ケア（こうすると落ち着く、こうするとよい）を検索します。

    Args:
        client_name: クライアント名
    """
    from app.lib.db_operations import run_query
    client_name, suggestion = _resolve_client_name(client_name)

    records = run_query("""
        MATCH (c:Client {name: $name})-[:REQUIRES]->(cp:CarePreference)
        RETURN cp.category AS category, cp.instruction AS instruction, cp.priority AS priority
    """, {"name": client_name})
    result = {"client_name": client_name, "care_preferences": [dict(r) for r in records]}
    if suggestion:
        result["_suggestion"] = suggestion
    return json.dumps(result, ensure_ascii=False)


def search_hospital(client_name: str) -> str:
    """クライアントのかかりつけ病院・医療機関を検索します。体調不良時に必要。

    Args:
        client_name: クライアント名
    """
    from app.lib.db_operations import run_query
    client_name, suggestion = _resolve_client_name(client_name)

    records = run_query("""
        MATCH (c:Client {name: $name})-[:TREATED_AT]->(h:Hospital)
        RETURN h.name AS name, h.phone AS phone, h.address AS address
    """, {"name": client_name})
    result = {"client_name": client_name, "hospitals": [dict(r) for r in records]}
    if suggestion:
        result["_suggestion"] = suggestion
    return json.dumps(result, ensure_ascii=False, default=str)


def search_guardian(client_name: str) -> str:
    """クライアントの後見人・法的代理人を検索します。金銭トラブルや法的問題時に必要。

    Args:
        client_name: クライアント名
    """
    from app.lib.db_operations import run_query
    client_name, suggestion = _resolve_client_name(client_name)

    records = run_query("""
        MATCH (c:Client {name: $name})-[:HAS_LEGAL_REP]->(g:Guardian)
        RETURN g.name AS name, g.type AS type, g.phone AS phone, g.organization AS organization
    """, {"name": client_name})
    result = {"client_name": client_name, "guardians": [dict(r) for r in records]}
    if suggestion:
        result["_suggestion"] = suggestion
    return json.dumps(result, ensure_ascii=False, default=str)


def search_support_logs(client_name: str, limit: int = 5) -> str:
    """クライアントの最近の支援記録を検索します。最近の様子や支援傾向の確認に使用。

    Args:
        client_name: クライアント名
        limit: 取得件数（デフォルト5）
    """
    from app.lib.db_operations import run_query
    client_name, suggestion = _resolve_client_name(client_name)

    records = run_query("""
        MATCH (s:Supporter)-[:LOGGED]->(sl:SupportLog)-[:ABOUT]->(c:Client {name: $name})
        RETURN sl.date AS date, sl.situation AS situation, sl.action AS action,
               sl.effectiveness AS effectiveness, sl.note AS note, s.name AS supporter
        ORDER BY sl.date DESC LIMIT $limit
    """, {"name": client_name, "limit": limit})
    result = {"client_name": client_name, "logs": [{k: str(v) if v else None for k, v in r.items()} for r in records]}
    if suggestion:
        result["_suggestion"] = suggestion
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 高度なツール（分析・予測・可視化）
# ---------------------------------------------------------------------------


def analyze_support_trends(client_name: str, months: int = 3) -> str:
    """直近N ヶ月の支援記録を集計し、状況別の出現頻度と有効性（Effective/Ineffective/Neutral）を分析します。
    支援方針の見直しや傾向把握に使用してください。

    Args:
        client_name: クライアント名
        months: 集計対象の月数（デフォルト3ヶ月）
    """
    from datetime import datetime, timedelta
    from app.lib.db_operations import run_query

    cutoff = (datetime.now() - timedelta(days=months * 30)).strftime("%Y-%m-%d")
    records = run_query("""
        MATCH (s:Supporter)-[:LOGGED]->(sl:SupportLog)-[:ABOUT]->(c:Client {name: $name})
        WHERE sl.date >= $cutoff
        RETURN sl.situation AS situation, sl.effectiveness AS effectiveness,
               sl.date AS date, sl.action AS action, s.name AS supporter
        ORDER BY sl.date DESC
    """, {"name": client_name, "cutoff": cutoff})

    if not records:
        return json.dumps({"client_name": client_name, "message": f"直近{months}ヶ月の支援記録がありません。"}, ensure_ascii=False)

    # 状況別の集計
    situation_counts: dict[str, int] = {}
    effectiveness_counts: dict[str, dict[str, int]] = {}
    for r in records:
        sit = str(r.get("situation") or "不明")
        eff = str(r.get("effectiveness") or "Unknown")
        situation_counts[sit] = situation_counts.get(sit, 0) + 1
        if sit not in effectiveness_counts:
            effectiveness_counts[sit] = {}
        effectiveness_counts[sit][eff] = effectiveness_counts[sit].get(eff, 0) + 1

    return json.dumps({
        "client_name": client_name,
        "period": f"直近{months}ヶ月",
        "total_logs": len(records),
        "situation_frequency": dict(sorted(situation_counts.items(), key=lambda x: -x[1])),
        "effectiveness_by_situation": effectiveness_counts,
        "recent_logs": [{k: str(v) if v else None for k, v in r.items()} for r in records[:5]],
    }, ensure_ascii=False, default=str)


def check_renewal_deadlines(days_ahead: int = 90) -> str:
    """指定日数以内に更新期限が来る手帳・受給者証を全クライアント横断で一覧します。
    更新漏れの防止や事務手続きの計画に使用してください。

    Args:
        days_ahead: 何日先までチェックするか（デフォルト90日）
    """
    from datetime import datetime, timedelta
    from app.lib.db_operations import run_query

    today = datetime.now().strftime("%Y-%m-%d")
    cutoff = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    records = run_query("""
        MATCH (c:Client)-[:HAS_CERTIFICATE]->(cert:Certificate)
        WHERE cert.nextRenewalDate IS NOT NULL
          AND cert.nextRenewalDate >= $today
          AND cert.nextRenewalDate <= $cutoff
        RETURN c.name AS client_name, cert.type AS certificate_type,
               cert.nextRenewalDate AS renewal_date
        ORDER BY cert.nextRenewalDate ASC
    """, {"today": today, "cutoff": cutoff})

    results = []
    for r in records:
        renewal = str(r["renewal_date"])
        try:
            days_remaining = (datetime.strptime(renewal, "%Y-%m-%d") - datetime.now()).days
        except (ValueError, TypeError):
            days_remaining = -1
        results.append({
            "client_name": r["client_name"],
            "certificate_type": str(r["certificate_type"]),
            "renewal_date": renewal,
            "days_remaining": days_remaining,
            "urgency": "緊急" if days_remaining <= 30 else "注意" if days_remaining <= 60 else "予定",
        })

    return json.dumps({
        "check_range": f"今日から{days_ahead}日以内",
        "total": len(results),
        "deadlines": results,
    }, ensure_ascii=False, default=str)


def find_similar_clients(client_name: str, top_k: int = 3) -> str:
    """支援内容や特性が似ているクライアントを検索します。
    過去の類似事例から有効だった支援方法を参考にするために使用してください。
    ベクトル類似度検索（Embedding）を使用します。

    Args:
        client_name: 基準となるクライアント名
        top_k: 返す類似クライアント数（デフォルト3）
    """
    from app.lib.db_operations import run_query

    # まず対象クライアントの summaryEmbedding を取得
    client_records = run_query("""
        MATCH (c:Client {name: $name})
        RETURN c.summaryEmbedding AS embedding
    """, {"name": client_name})

    if not client_records or not client_records[0].get("embedding"):
        # Embedding がなければテキストベースで類似検索（条件マッチ）
        condition_records = run_query("""
            MATCH (c:Client {name: $name})-[:HAS_CONDITION]->(cond:Condition)
            RETURN collect(cond.name) AS conditions
        """, {"name": client_name})

        if not condition_records or not condition_records[0].get("conditions"):
            return json.dumps({"client_name": client_name, "message": "類似検索に必要なデータ（状態・Embedding）がありません。"}, ensure_ascii=False)

        conditions = condition_records[0]["conditions"]
        similar = run_query("""
            MATCH (c:Client)-[:HAS_CONDITION]->(cond:Condition)
            WHERE c.name <> $name AND cond.name IN $conditions
            WITH c, count(cond) AS shared_conditions
            ORDER BY shared_conditions DESC LIMIT $top_k
            OPTIONAL MATCH (c)-[:HAS_CONDITION]->(all_cond:Condition)
            RETURN c.name AS name, shared_conditions,
                   collect(DISTINCT all_cond.name) AS conditions
        """, {"name": client_name, "conditions": conditions, "top_k": top_k})

        return json.dumps({
            "client_name": client_name,
            "method": "条件マッチ（Embedding未設定のためフォールバック）",
            "similar_clients": [dict(r) for r in similar],
        }, ensure_ascii=False, default=str)

    # ベクトル類似度検索
    embedding = client_records[0]["embedding"]
    similar = run_query("""
        CALL db.index.vector.queryNodes('client_summary_embedding', $top_k_plus, $embedding)
        YIELD node, score
        WHERE node.name <> $name
        RETURN node.name AS name, score
        LIMIT $top_k
    """, {"embedding": embedding, "name": client_name, "top_k_plus": top_k + 1, "top_k": top_k})

    # 類似クライアントの詳細を取得
    results = []
    for r in similar:
        detail = run_query("""
            MATCH (c:Client {name: $name})
            OPTIONAL MATCH (c)-[:HAS_CONDITION]->(cond:Condition)
            RETURN collect(DISTINCT cond.name) AS conditions
        """, {"name": r["name"]})
        results.append({
            "name": r["name"],
            "similarity_score": round(r["score"], 3),
            "conditions": detail[0]["conditions"] if detail else [],
        })

    return json.dumps({
        "client_name": client_name,
        "method": "ベクトル類似度検索（summaryEmbedding）",
        "similar_clients": results,
    }, ensure_ascii=False, default=str)


def get_support_network(client_name: str) -> str:
    """クライアントの支援ネットワーク全体像（エコマップデータ）を取得します。
    誰がどのような関係で支援に関わっているかを俯瞰するために使用してください。

    Args:
        client_name: クライアント名
    """
    from app.lib.ecomap import fetch_ecomap_data

    try:
        data = fetch_ecomap_data(client_name, "full_view")
        summary = {
            "client_name": client_name,
            "total_nodes": len(data.nodes),
            "total_edges": len(data.edges),
            "categories": {},
        }
        for node in data.nodes:
            cat = node.category
            if cat not in summary["categories"]:
                summary["categories"][cat] = []
            summary["categories"][cat].append(node.label)
        return json.dumps(summary, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"client_name": client_name, "error": str(e)}, ensure_ascii=False)


# All tools available to the agent
TOOLS = [
    # 基本検索
    search_client_info,
    search_emergency_contacts,
    search_ng_actions,
    search_care_preferences,
    search_hospital,
    search_guardian,
    search_support_logs,
    # 分析・予測・可視化
    analyze_support_trends,
    check_renewal_deadlines,
    find_similar_clients,
    get_support_network,
]

CHAT_SYSTEM_PROMPT = """あなたは障害福祉支援の専門アシスタントです。
利用者（クライアント）の支援情報がNeo4jグラフデータベースに格納されており、
ツール（関数）を使ってデータベースから情報を取得できます。

## 最も重要なルール

**ツールを積極的に使い、具体的な情報で回答すること。**
質問を返す前に、まずツールで検索して回答できないか判断してください。
不必要な確認質問はユーザーの時間を奪います。

## 行動指針

1. **明確な質問にはすぐツールを呼んで回答する**:
   - 「更新期限が近い手帳を確認して」→ すぐに check_renewal_deadlines() を呼ぶ（デフォルト90日）
   - 「〇〇さんの基本情報」→ すぐに search_client_info() を呼ぶ
   - 「〇〇さんの支援記録を見せて」→ すぐに search_support_logs() を呼ぶ
   - 「更新期限が一番近い人は？」→ すぐに check_renewal_deadlines() を呼び、最も近い人を回答する

2. **緊急連絡先を聞かれたら、状況を確認してから最適な情報を提供する**:
   「〇〇さんの緊急連絡先を教えて」と言われた場合のみ、
   「何かありましたか？状況を教えていただけますか？」と確認してください。
   状況に応じて連絡すべき相手が変わるためです:
   - パニック・行動障害 → search_ng_actions + search_care_preferences + search_emergency_contacts
   - 体調不良・怪我 → search_hospital + search_emergency_contacts
   - 金銭トラブル・法的問題 → search_guardian + search_emergency_contacts

3. **切迫した状況では質問せず即座に全情報を提供する**:
   「パニックになっている」「倒れた」「発作が起きた」など緊急性の高い状況報告には、
   確認質問をせずに禁忌事項・推奨ケア・緊急連絡先・かかりつけ病院を全て提供してください。

4. **パラメータが不明でも合理的なデフォルトで回答する**:
   - 期間を指定されなければ「90日」「3ヶ月」など合理的な範囲で検索する
   - 件数を指定されなければデフォルト値で検索する
   - ユーザーに聞き返すのは最後の手段

5. **日本語で回答**: 常に日本語で、わかりやすく回答してください。

6. **データにない情報は推測しない**: データベースに存在しない情報は「登録されていません」と回答してください。

7. **名前の候補提示**: ツールの戻り値に `_suggestion` フィールドがある場合、それはユーザーが入力した名前と実際の登録名が異なることを意味します。必ずその内容を回答の冒頭でユーザーに伝えてから、情報を提供してください。例: 「佐々木真里さんは登録されていませんが、佐々木真理さんが見つかりました。佐々木真理さんの情報をお伝えします。」
"""


# ---------------------------------------------------------------------------
# Agent Factory — provider selection via config
# ---------------------------------------------------------------------------

def _create_model(provider: str | None = None):
    """Create the appropriate model. If provider is None, use config default."""
    if provider is None:
        provider = settings.chat_provider

    if provider == "claude":
        from agno.models.anthropic import Claude
        return Claude(
            id=settings.claude_model,
            api_key=settings.anthropic_api_key,
        )
    elif provider == "openai":
        from agno.models.openai import OpenAIChat
        return OpenAIChat(
            id=settings.openai_model if hasattr(settings, "openai_model") else "gpt-4.1-mini",
            api_key=settings.openai_api_key if hasattr(settings, "openai_api_key") else "",
        )
    elif provider == "ollama":
        from agno.models.ollama import Ollama
        return Ollama(
            id=settings.ollama_model,
            host=settings.ollama_host,
        )
    else:  # default: gemini
        from agno.models.google import Gemini
        return Gemini(
            id=settings.gemini_model,
            api_key=settings.gemini_api_key or settings.google_api_key,
        )


def _get_chat_agent() -> Agent:
    """Create a chat agent with the configured model and DB tools (stateless)."""
    return Agent(
        model=_create_model(),
        tools=TOOLS,
        instructions=[CHAT_SYSTEM_PROMPT],
        markdown=True,
    )


def create_session_agent(session_id: str) -> Agent:
    """セッション対応のチャットエージェントを作成。

    InMemoryDb を使って会話履歴を自動管理し、
    前のターンのコンテキスト（クライアント名など）を保持する。
    """
    from agno.db.in_memory import InMemoryDb

    db = InMemoryDb()
    return Agent(
        model=_create_model(),
        tools=TOOLS,
        instructions=[CHAT_SYSTEM_PROMPT],
        markdown=True,
        db=db,
        session_id=session_id,
        add_history_to_context=True,
        num_history_runs=6,  # 直近6ターン分を保持
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_extraction_prompt() -> str:
    return (PROMPT_DIR / "extraction.md").read_text(encoding="utf-8")


def parse_json_from_response(response_text: str) -> dict | None:
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


async def extract_from_text(text: str, client_name: str | None = None) -> dict | None:
    """Extract structured graph data from narrative text.

    Uses Gemini directly (not Agno) for extraction since this requires
    a specific JSON schema prompt, not conversational tools.
    """
    import google.generativeai as genai

    prompt = get_extraction_prompt()
    user_message = text
    if client_name:
        user_message = f"【対象クライアント: {client_name}】\n\n{text}"
    try:
        genai.configure(api_key=settings.gemini_api_key or settings.google_api_key)
        model = genai.GenerativeModel(settings.gemini_model)
        response = model.generate_content(
            [{"role": "user", "parts": [prompt + "\n\n" + user_message]}],
            generation_config={"temperature": 0},
        )
        return parse_json_from_response(response.text)
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return None


async def chat(message: str, history: list[dict] | None = None, agent: Agent | None = None) -> str:
    """Chat using Agno Agent with the configured provider.

    Agno handles function calling / tool_use protocol differences
    automatically — same tools work with Gemini, Claude, OpenAI, etc.

    agent を渡すとセッション対応のエージェント（履歴保持）を使用する。
    """
    try:
        _agent = agent or _get_chat_agent()

        # Run agent（セッション対応エージェントの場合、履歴は自動管理される）
        response = _agent.run(message)

        # テキストコンテンツの抽出
        if response and response.content:
            return response.content
        return "回答を生成できませんでした。"

    except Exception as e:
        logger.error(f"Chat failed ({settings.chat_provider}): {e}", exc_info=True)
        return f"エラーが発生しました: {e}"


async def chat_stream(message: str) -> Iterator[str]:
    """Stream chat response using Agno Agent.

    Yields text chunks as they arrive from the model.
    """
    try:
        agent = _get_chat_agent()
        stream: Iterator[RunOutputEvent] = agent.run(message, stream=True)
        for chunk in stream:
            if chunk.event == RunEvent.run_content and chunk.content:
                yield chunk.content
    except Exception as e:
        logger.error(f"Stream chat failed: {e}", exc_info=True)
        yield f"エラーが発生しました: {e}"


async def check_safety_compliance(narrative: str, ng_actions: list) -> dict:
    """Check if narrative violates existing NgActions.

    Uses Gemini directly (simple prompt, no tools needed).
    """
    if not ng_actions:
        return {"is_violation": False, "warning": None, "risk_level": "None"}

    import google.generativeai as genai

    safety_prompt = (PROMPT_DIR / "safety.md").read_text(encoding="utf-8")
    safety_prompt = safety_prompt.replace("{ng_actions}", json.dumps(ng_actions, ensure_ascii=False))
    safety_prompt = safety_prompt.replace("{narrative}", narrative)
    try:
        genai.configure(api_key=settings.gemini_api_key or settings.google_api_key)
        model = genai.GenerativeModel(settings.gemini_model)
        response = model.generate_content(
            [{"role": "user", "parts": [safety_prompt]}],
            generation_config={"temperature": 0},
        )
        match = re.search(r"\{[^}]+\}", response.text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        logger.warning(f"Safety check failed: {e}")
    return {"is_violation": False, "warning": None, "risk_level": "None"}
