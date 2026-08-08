import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import dashboard, clients, narratives, narrative_intake, quicklog, chat, search, ecomap, meetings, system, dedup, graph

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.lib.db_operations import is_db_available

    if is_db_available():
        logger.info("Neo4j connected: %s", settings.neo4j_uri)
        # ベクトルインデックスの存在を確認・作成
        try:
            from app.lib.embedding import ensure_vector_indexes
            ensure_vector_indexes()
            logger.info("Vector indexes verified")
        except Exception as e:
            logger.warning("Vector index setup failed: %s", e)
    else:
        logger.warning("Neo4j not available at %s", settings.neo4j_uri)

    if settings.gemini_api_key or settings.google_api_key:
        logger.info("Gemini API key configured")
    else:
        logger.warning("GEMINI_API_KEY not set")

    yield

    from app.lib.db_operations import close_driver
    close_driver()


app = FastAPI(
    title="neo4j-agno-agent API",
    description="親亡き後支援データベース API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{settings.frontend_port}",
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(dashboard.router)
app.include_router(clients.router)
app.include_router(narratives.router)
app.include_router(narrative_intake.router)
app.include_router(quicklog.router)
app.include_router(chat.router)
app.include_router(search.router)
app.include_router(ecomap.router)
app.include_router(meetings.router)
app.include_router(system.router)
app.include_router(dedup.router)
app.include_router(graph.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
