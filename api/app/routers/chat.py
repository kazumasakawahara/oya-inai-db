"""Chat router -- WebSocket chat with intake mode, emergency routing, and dynamic LLM switching.

Provider-agnostic: Gemini / Claude / OpenAI / Ollama switchable at runtime.
Session-aware: Agno InMemoryDb keeps conversation history across turns.
Intake mode: 7-pillar guided intake via ``mode: "intake"`` in message payload.
"""

import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agents.gemini_agent import (
    CHAT_SYSTEM_PROMPT,
    TOOLS,
    _create_model,
    chat,
    create_session_agent,
)
from app.agents.intake_agent import cleanup_session, handle_intake_message
from app.agents.model_switch import detect_model_switch
from app.agents.safety_first import handle_emergency, is_emergency
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

_PROVIDER_LABELS = {
    "gemini": "Gemini",
    "claude": "Claude",
    "openai": "OpenAI",
    "ollama": "Ollama (ローカル)",
}


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    current_provider: str = settings.chat_provider
    agent = None  # Lazily initialised; recreated on provider switch

    # Conversation history for Safety First client-name extraction
    message_history: list[str] = []

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                user_text: str = msg.get("content", "")
                mode: str = msg.get("mode", "chat")
                # session_id はサーバー生成のみ使用（クライアント指定は無視）

                # 入力長制限（10,000文字）
                if len(user_text) > 10000:
                    user_text = user_text[:10000]

                if not user_text:
                    await websocket.send_json({"type": "done", "session_id": session_id})
                    continue

                # -----------------------------------------------------------
                # 1. Model switch detection (checked on every message)
                # -----------------------------------------------------------
                switch = detect_model_switch(user_text)
                if switch:
                    provider, display_name = switch
                    current_provider = provider
                    agent = None  # Force recreation with new provider
                    await websocket.send_json({
                        "type": "model_switched",
                        "provider": provider,
                        "model": display_name,
                    })
                    await websocket.send_json({
                        "type": "stream",
                        "content": f"{display_name} に切り替えました。",
                        "agent": provider,
                    })
                    await websocket.send_json({"type": "done", "session_id": session_id})
                    continue

                # -----------------------------------------------------------
                # 2. Intake mode
                # -----------------------------------------------------------
                if mode == "intake":
                    result = await handle_intake_message(session_id, user_text)

                    # Progress update
                    if result.get("progress"):
                        await websocket.send_json({
                            "type": "intake_progress",
                            **result["progress"],
                        })

                    # Stream response text in chunks
                    response_text = result.get("response", "")
                    for i in range(0, len(response_text), 30):
                        await websocket.send_json({
                            "type": "stream",
                            "content": response_text[i : i + 30],
                            "agent": "intake",
                        })

                    # Graph preview (after safety-critical phases or final)
                    if result.get("preview"):
                        await websocket.send_json({
                            "type": "intake_preview",
                            "nodes": result["preview"].get("nodes", []),
                            "relationships": result["preview"].get("relationships", []),
                        })

                    # Registration complete
                    if result.get("complete"):
                        await websocket.send_json({
                            "type": "intake_complete",
                            "registered_count": result.get("registered_count", 0),
                        })

                    await websocket.send_json({"type": "done", "session_id": session_id})
                    continue

                # -----------------------------------------------------------
                # 3. Emergency routing (Safety First -- bypasses LLM)
                # -----------------------------------------------------------
                if is_emergency(user_text):
                    await websocket.send_json({
                        "type": "routing",
                        "agent": "safety_first",
                        "decision": "emergency_search",
                        "reason": "現在進行中の危機を検知",
                    })
                    response = handle_emergency(user_text, message_history)
                else:
                    # -------------------------------------------------------
                    # 4. Normal chat (with session-aware agent)
                    # -------------------------------------------------------
                    label = _PROVIDER_LABELS.get(current_provider, current_provider)
                    await websocket.send_json({
                        "type": "routing",
                        "agent": current_provider,
                        "decision": "chat",
                        "reason": f"{label}（DB検索ツール付き）",
                    })

                    # Create or reuse session agent
                    if agent is None:
                        agent = _create_session_agent_for_provider(
                            session_id, current_provider
                        )

                    response = await chat(user_text, agent=agent)

                # Record message for Safety First history
                message_history.append(user_text)

                # Stream response text in chunks
                for i in range(0, len(response), 30):
                    await websocket.send_json({
                        "type": "stream",
                        "content": response[i : i + 30],
                        "agent": current_provider,
                    })

                await websocket.send_json({"type": "done", "session_id": session_id})

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "stream",
                    "content": "無効なメッセージ形式です。",
                    "agent": "system",
                })
                await websocket.send_json({"type": "done", "session_id": session_id})
            except Exception as e:
                logger.error("Chat processing error: %s", e, exc_info=True)
                await websocket.send_json({
                    "type": "stream",
                    "content": "エラーが発生しました。もう一度お試しください。",
                    "agent": "system",
                })
                await websocket.send_json({"type": "done", "session_id": session_id})

    except WebSocketDisconnect:
        logger.info("Chat session %s disconnected", session_id)
        cleanup_session(session_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_session_agent_for_provider(session_id: str, provider: str):
    """Create a session-aware Agno Agent for the given provider."""
    from agno.agent import Agent
    from agno.db.in_memory import InMemoryDb

    model = _create_model(provider)

    return Agent(
        model=model,
        tools=TOOLS,
        instructions=[CHAT_SYSTEM_PROMPT],
        markdown=True,
        db=InMemoryDb(),
        session_id=session_id,
        add_history_to_context=True,
        num_history_runs=6,
    )
