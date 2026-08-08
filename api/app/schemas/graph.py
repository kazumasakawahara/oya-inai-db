"""Pydantic schemas for graph exploration endpoints."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    label: str
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphExploreResponse(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    truncated: bool = False


class LabelCount(BaseModel):
    label: str
    count: int


class GraphLabelsResponse(BaseModel):
    labels: list[dict[str, Any]] = Field(default_factory=list)


class GraphStatsResponse(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
