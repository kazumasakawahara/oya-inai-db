import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    dashboard, clients, quicklog, ecomap, meetings, system, dedup, graph, graph_validate,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.lib.db_operations import is_db_available

    if is_db_available():
        logger.info("Neo4j connected: %s", settings.neo4j_uri)
    else:
        logger.warning("Neo4j not available at %s", settings.neo4j_uri)

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
app.include_router(quicklog.router)
app.include_router(ecomap.router)
app.include_router(meetings.router)
app.include_router(system.router)
app.include_router(dedup.router)
app.include_router(graph.router)
app.include_router(graph_validate.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
