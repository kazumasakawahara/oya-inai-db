"""System router — AI provider and Neo4j availability status."""
from fastapi import APIRouter

from app.config import settings
from app.lib.db_operations import is_db_available
from app.schemas.agent import SystemStatus

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    provider = settings.chat_provider
    if provider == "claude":
        chat_model = settings.claude_model
    elif provider == "ollama":
        chat_model = settings.ollama_model
    else:
        chat_model = settings.gemini_model

    # Ollama 接続チェック
    ollama_available = False
    if settings.ollama_host:
        try:
            import httpx
            resp = httpx.get(f"{settings.ollama_host}/api/tags", timeout=2)
            ollama_available = resp.status_code == 200
        except Exception:
            pass

    return SystemStatus(
        gemini_available=bool(settings.gemini_api_key or settings.google_api_key),
        claude_available=bool(settings.anthropic_api_key),
        ollama_available=ollama_available,
        neo4j_available=is_db_available(),
        chat_provider=provider,
        chat_model=chat_model,
        embedding_model=settings.embedding_model,
    )
