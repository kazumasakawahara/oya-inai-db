"""Pydantic schemas for /api/dedup endpoints."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class DedupCheckRequest(BaseModel):
    """Pre-registration duplicate check request."""
    label: str = Field(..., description="Node label (e.g. Client, NgAction)")
    properties: dict[str, Any] = Field(..., description="Node properties to check")


class DedupCandidate(BaseModel):
    """A potential duplicate candidate."""
    name: str | None = None
    text: str | None = None
    similarity: float
    matchType: str = Field(..., description="exact | kana | semantic")
    nodeId: str


class DedupCheckResponse(BaseModel):
    """Duplicate check results."""
    hasCandidates: bool = False
    candidates: list[DedupCandidate] = Field(default_factory=list)
    checkedLabel: str
    checksPerformed: list[str] = Field(default_factory=list)
