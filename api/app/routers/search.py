from fastapi import APIRouter, Query

from app.lib.db_operations import run_query
from app.lib.embedding import embed_text, semantic_search
from app.schemas.search import SemanticSearchRequest, SemanticSearchResult

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/fulltext")
async def fulltext_search(q: str = Query(...), limit: int = Query(20)):
    records = run_query(
        """
        CALL db.index.fulltext.queryNodes('idx_supportlog_fulltext', $query)
        YIELD node, score
        OPTIONAL MATCH (node)-[:ABOUT]->(c:Client)
        RETURN node.date AS date, node.note AS note, node.situation AS situation,
               c.name AS client_name, score
        ORDER BY score DESC LIMIT $limit
        """,
        {"query": q, "limit": limit},
    )
    return records


@router.post("/semantic", response_model=list[SemanticSearchResult])
async def search_semantic(request: SemanticSearchRequest):
    query_embedding = await embed_text(request.query)
    if not query_embedding:
        return []
    results = semantic_search(
        query_embedding=query_embedding,
        index_name=request.index_name,
        top_k=request.top_k,
    )

    # Neo4j 固有型を文字列に変換、embedding ベクトルは除外
    EXCLUDE_KEYS = {"embedding", "summaryEmbedding", "textEmbedding"}

    def _sanitize(props: dict) -> dict:
        return {
            k: str(v) if v is not None and not isinstance(v, (str, int, float, bool)) else v
            for k, v in props.items()
            if k not in EXCLUDE_KEYS
        }

    return [
        SemanticSearchResult(
            score=r["score"],
            node_label=request.index_name.replace("_embedding", "").replace("_vector_index", "").replace("_", " ").title(),
            properties=_sanitize(r["node"]),
        )
        for r in results
    ]
