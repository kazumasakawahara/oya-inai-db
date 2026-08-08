"""Graph exploration endpoints for interactive knowledge graph UI."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.lib.db_operations import run_query
from app.schemas.graph import (
    GraphEdge,
    GraphExploreResponse,
    GraphLabelsResponse,
    GraphNode,
    GraphStatsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])

# Labels allowed for exploration
_ALLOWED_LABELS = {
    "Client",
    "Supporter",
    "NgAction",
    "CarePreference",
    "Condition",
    "KeyPerson",
    "Organization",
    "ServiceProvider",
    "Hospital",
    "Guardian",
    "Certificate",
    "SupportLog",
    "LifeHistory",
    "Wish",
    "MeetingRecord",
}


def _build_node(row: dict) -> GraphNode:
    """Convert a Cypher-level transformed node dict to GraphNode."""
    labels: list[str] = row.get("labels") or []
    label = labels[0] if labels else "Unknown"
    props: dict = row.get("properties") or {}
    name = (
        props.get("name")
        or props.get("action")
        or props.get("instruction")
        or props.get("title")
        or props.get("type")
        or "?"
    )
    return GraphNode(
        id=str(row.get("id") or ""),
        label=label,
        name=str(name)[:80],
        properties={k: str(v)[:200] for k, v in props.items()},
    )


def _build_edge(row: dict) -> GraphEdge:
    """Convert a Cypher-level transformed relationship dict to GraphEdge."""
    props: dict = row.get("properties") or {}
    return GraphEdge(
        id=str(row.get("id") or ""),
        source=str(row.get("source") or ""),
        target=str(row.get("target") or ""),
        type=str(row.get("type") or ""),
        properties={k: str(v)[:200] for k, v in props.items()},
    )


@router.get("/explore", response_model=GraphExploreResponse)
async def explore_graph(
    startLabel: str | None = Query(None, description="Starting node label"),
    startName: str | None = Query(None, description="Starting node name (for Client/KeyPerson)"),
    maxDepth: int = Query(2, ge=1, le=4, description="Graph traversal depth"),
    maxNodes: int = Query(100, ge=10, le=500, description="Max nodes to return"),
) -> GraphExploreResponse:
    """Fetch a subgraph for visualization.

    - If startLabel + startName: start from that specific node
    - If only startLabel: return sample of nodes with that label
    - If neither: return high-connectivity nodes across all labels
    """
    if startLabel and startLabel not in _ALLOWED_LABELS:
        raise HTTPException(400, detail=f"Unsupported label: {startLabel}")

    try:
        if startLabel and startName:
            # Specific node-centered exploration via APOC
            cypher = f"""
            MATCH (start:{startLabel} {{name: $name}})
            CALL apoc.path.subgraphAll(start, {{
                maxLevel: $depth,
                limit: $max_nodes
            }})
            YIELD nodes, relationships
            RETURN
                [n IN nodes | {{
                    id: elementId(n),
                    labels: labels(n),
                    properties: properties(n)
                }}] AS nodes,
                [r IN relationships | {{
                    id: elementId(r),
                    source: elementId(startNode(r)),
                    target: elementId(endNode(r)),
                    type: type(r),
                    properties: properties(r)
                }}] AS edges
            """
            params: dict = {"name": startName, "depth": maxDepth, "max_nodes": maxNodes}

        elif startLabel:
            # Label-based sample
            cypher = f"""
            MATCH (n:{startLabel})
            WITH n LIMIT $max_nodes
            OPTIONAL MATCH (n)-[r]-(m)
            WITH
                collect(DISTINCT n) + collect(DISTINCT m) AS all_nodes,
                collect(DISTINCT r) AS all_rels
            RETURN
                [n IN all_nodes WHERE n IS NOT NULL | {{
                    id: elementId(n),
                    labels: labels(n),
                    properties: properties(n)
                }}] AS nodes,
                [r IN all_rels WHERE r IS NOT NULL | {{
                    id: elementId(r),
                    source: elementId(startNode(r)),
                    target: elementId(endNode(r)),
                    type: type(r),
                    properties: properties(r)
                }}] AS edges
            """
            params = {"max_nodes": maxNodes}

        else:
            # Overview: highest-degree nodes across all allowed labels
            cypher = """
            MATCH (n)
            WHERE any(lbl IN labels(n) WHERE lbl IN $allowed)
            WITH n, size([(n)--() | 1]) AS degree
            ORDER BY degree DESC
            LIMIT $max_nodes
            OPTIONAL MATCH (n)-[r]-(m)
            WHERE any(lbl IN labels(m) WHERE lbl IN $allowed)
            WITH
                collect(DISTINCT n) + collect(DISTINCT m) AS all_nodes,
                collect(DISTINCT r) AS all_rels
            RETURN
                [n IN all_nodes WHERE n IS NOT NULL | {
                    id: elementId(n),
                    labels: labels(n),
                    properties: properties(n)
                }] AS nodes,
                [r IN all_rels WHERE r IS NOT NULL | {
                    id: elementId(r),
                    source: elementId(startNode(r)),
                    target: elementId(endNode(r)),
                    type: type(r),
                    properties: properties(r)
                }] AS edges
            """
            params = {"allowed": list(_ALLOWED_LABELS), "max_nodes": maxNodes}

        rows = run_query(cypher, params)

    except Exception as exc:
        logger.warning("Graph explore query failed: %s", exc)
        raise HTTPException(500, detail=f"Graph query failed: {exc}")

    if not rows:
        return GraphExploreResponse(nodes=[], edges=[])

    row = rows[0]
    raw_nodes: list[dict] = row.get("nodes") or []
    raw_edges: list[dict] = row.get("edges") or []

    nodes: list[GraphNode] = []
    seen_node_ids: set[str] = set()
    for n in raw_nodes:
        if not n:
            continue
        node_id = str(n.get("id") or "")
        if node_id in seen_node_ids:
            continue
        seen_node_ids.add(node_id)
        nodes.append(_build_node(n))

    edges: list[GraphEdge] = []
    seen_edge_ids: set[str] = set()
    for e in raw_edges:
        if not e:
            continue
        edge_id = str(e.get("id") or "")
        if edge_id in seen_edge_ids:
            continue
        seen_edge_ids.add(edge_id)
        edges.append(_build_edge(e))

    truncated = len(nodes) >= maxNodes
    return GraphExploreResponse(nodes=nodes, edges=edges, truncated=truncated)


@router.get("/labels", response_model=GraphLabelsResponse)
async def list_labels() -> GraphLabelsResponse:
    """List all node labels with counts."""
    try:
        rows = run_query(
            """
            MATCH (n)
            UNWIND labels(n) AS lbl
            WITH lbl, count(n) AS cnt
            WHERE lbl IN $allowed
            RETURN lbl AS label, cnt AS count
            ORDER BY cnt DESC
            """,
            {"allowed": list(_ALLOWED_LABELS)},
        )
        return GraphLabelsResponse(labels=[dict(r) for r in rows])
    except Exception as exc:
        logger.warning("labels query failed: %s", exc)
        return GraphLabelsResponse(labels=[])


@router.get("/stats", response_model=GraphStatsResponse)
async def graph_stats() -> GraphStatsResponse:
    """Return total node/edge counts."""
    try:
        node_rows = run_query("MATCH (n) RETURN count(n) AS c")
        rel_rows = run_query("MATCH ()-[r]->() RETURN count(r) AS c")
        return GraphStatsResponse(
            total_nodes=node_rows[0]["c"] if node_rows else 0,
            total_edges=rel_rows[0]["c"] if rel_rows else 0,
        )
    except Exception as exc:
        logger.warning("stats query failed: %s", exc)
        return GraphStatsResponse(total_nodes=0, total_edges=0)
