"""POST /api/graph/validate — Guardian Layer による書き込み前検証。

LLM を呼ばない・外部に送らない・DB に書かない検証専用エンドポイント。
Claude（スキル層）が MCP で直接書き込む前に、ここで機械検証を通す。

検証本体はリポジトリルートの Guardian Layer（lib/schema_validator.py）を
そのまま使う。api パッケージからは import パスが通らず、また
lib/__init__.py の import 連鎖を避けるため、check_semantic_drift.py と
同じくファイル直読みでロードする。
"""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from fastapi import APIRouter

from app.lib.db_operations import MERGE_KEYS
from app.schemas.graph_validate import (
    AcceptedGraph,
    GraphValidateRequest,
    GraphValidateResponse,
    NodeFragment,
    RejectedItem,
    RelationshipFragment,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])

_SV_PATH = Path(__file__).resolve().parents[3] / "lib" / "schema_validator.py"
_spec = importlib.util.spec_from_file_location("guardian_schema_validator", _SV_PATH)
_sv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sv)


def _validate_node(
    node: NodeFragment, index: int, warnings: list[str]
) -> tuple[NodeFragment | None, RejectedItem | None]:
    path = f"nodes[{index}] {node.label} (temp_id={node.temp_id})"

    is_valid, msg = _sv.validate_node_label(node.label)
    if not is_valid:
        return None, RejectedItem(path=path, reason=msg)

    props = _sv.normalize_properties(dict(node.properties), node.label)
    renamed = set(node.properties) - set(props)
    if renamed:
        warnings.append(
            f"{path}: プロパティ名を camelCase に補正しました: {sorted(renamed)}"
        )

    if isinstance(props.get("riskLevel"), str):
        corrected = _sv.normalize_risk_level(props["riskLevel"])
        if corrected != props["riskLevel"]:
            warnings.append(
                f"{path}: riskLevel を補正しました: {props['riskLevel']} → {corrected}"
            )
            props["riskLevel"] = corrected

    for prop_name, value in props.items():
        if not isinstance(value, str):
            continue
        is_valid, msg = _sv.validate_enum_value(prop_name, value)
        if not is_valid:
            return None, RejectedItem(path=path, reason=msg)
        is_valid, msg = _sv.validate_label_scoped_enum(node.label, prop_name, value)
        if not is_valid:
            return None, RejectedItem(path=path, reason=msg)

    missing = [k for k in MERGE_KEYS.get(node.label, []) if not props.get(k)]
    if missing:
        return None, RejectedItem(
            path=path,
            reason=(
                f"MERGE キーの値が properties にありません: {missing}。"
                " キー値は mergeKey だけでなく properties 側にも必ず入れてください。"
            ),
        )

    return node.model_copy(update={"properties": props}), None


@router.post("/validate", response_model=GraphValidateResponse)
def validate_graph(request: GraphValidateRequest) -> GraphValidateResponse:
    """登録前のノード・リレーション断片を Guardian Layer で検証する。

    rejected が 1 件でもあれば書き込みに進んではならない。
    accepted には補正済み（camelCase・廃止リレ・riskLevel 別名）の断片を返す。
    """
    warnings: list[str] = []
    rejected: list[RejectedItem] = []
    accepted_nodes: list[NodeFragment] = []
    seen_temp_ids: set[str] = set()

    for i, node in enumerate(request.nodes):
        if node.temp_id in seen_temp_ids:
            rejected.append(RejectedItem(
                path=f"nodes[{i}] {node.label} (temp_id={node.temp_id})",
                reason=f"temp_id が重複しています: {node.temp_id}",
            ))
            continue
        validated, rejection = _validate_node(node, i, warnings)
        if rejection:
            rejected.append(rejection)
            continue
        seen_temp_ids.add(node.temp_id)
        accepted_nodes.append(validated)

    accepted_ids = {n.temp_id for n in accepted_nodes}
    accepted_rels: list[RelationshipFragment] = []

    for i, rel in enumerate(request.relationships):
        path = f"relationships[{i}] {rel.type} ({rel.source_temp_id}→{rel.target_temp_id})"

        is_valid, msg, corrected = _sv.validate_relationship_type(rel.type)
        if not is_valid:
            rejected.append(RejectedItem(path=path, reason=msg))
            continue
        if msg:
            warnings.append(f"{path}: {msg}")

        missing_ends = [t for t in (rel.source_temp_id, rel.target_temp_id)
                        if t not in accepted_ids]
        if missing_ends:
            rejected.append(RejectedItem(
                path=path,
                reason=f"参照先の temp_id が有効ノードにありません: {missing_ends}",
            ))
            continue

        props = _sv.normalize_properties(dict(rel.properties), f"rel:{corrected}")
        accepted_rels.append(rel.model_copy(update={"type": corrected, "properties": props}))

    return GraphValidateResponse(
        accepted=AcceptedGraph(nodes=accepted_nodes, relationships=accepted_rels),
        rejected=rejected,
        warnings=warnings,
    )
