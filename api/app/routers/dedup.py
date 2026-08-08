"""Router for pre-registration duplicate detection."""
from __future__ import annotations

import logging
from fastapi import APIRouter

from app.schemas.dedup import DedupCheckRequest, DedupCheckResponse
from app.services.dedup_service import check_duplicates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dedup", tags=["dedup"])


@router.post("/check", response_model=DedupCheckResponse)
async def check_dedup(request: DedupCheckRequest) -> DedupCheckResponse:
    """Pre-registration duplicate candidate check.

    Combines exact match, kana fuzzy match, and semantic similarity
    to find potential duplicates before node creation.
    """
    return await check_duplicates(request.label, request.properties)
