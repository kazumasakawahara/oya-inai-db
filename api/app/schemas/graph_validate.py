"""Schemas for POST /api/graph/validate.

旧 /api/narrative/intake の payload 形式（temp_id / label / mergeKey /
properties）を踏襲する。検証専用のため dryRun は持たない。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NodeFragment(BaseModel):
    temp_id: str
    label: str
    mergeKey: dict[str, Any] | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class RelationshipFragment(BaseModel):
    source_temp_id: str
    target_temp_id: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphValidateRequest(BaseModel):
    nodes: list[NodeFragment] = Field(default_factory=list)
    relationships: list[RelationshipFragment] = Field(default_factory=list)
    # 互換のため受け取るが、検証では使わない（書き込みも監査もしない）
    auditContext: dict[str, Any] | None = None


class RejectedItem(BaseModel):
    path: str
    reason: str


class AcceptedGraph(BaseModel):
    nodes: list[NodeFragment] = Field(default_factory=list)
    relationships: list[RelationshipFragment] = Field(default_factory=list)


class GraphValidateResponse(BaseModel):
    accepted: AcceptedGraph
    rejected: list[RejectedItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
