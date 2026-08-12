"""System router — Neo4j availability status."""
from fastapi import APIRouter

from app.lib.db_operations import is_db_available
from app.schemas.agent import SystemStatus

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    return SystemStatus(
        neo4j_available=is_db_available(),
    )
