from pydantic import BaseModel


class SemanticSearchRequest(BaseModel):
    query: str
    index_name: str = "support_log_embedding"
    top_k: int = 10


class SemanticSearchResult(BaseModel):
    score: float
    node_label: str
    properties: dict
