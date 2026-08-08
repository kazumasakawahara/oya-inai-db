from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    temp_id: str
    label: str
    properties: dict


class GraphRelationship(BaseModel):
    source_temp_id: str
    target_temp_id: str
    type: str
    properties: dict = {}


class ExtractedGraph(BaseModel):
    nodes: list[GraphNode] = []
    relationships: list[GraphRelationship] = []
    confirmDuplicates: bool = Field(
        False,
        description="True の場合、NgAction のセマンティック重複確認済みとして登録を続行する",
    )


class ExtractionRequest(BaseModel):
    text: str
    client_name: str | None = None


class ValidationResult(BaseModel):
    is_valid: bool
    errors: list[str] = []
    warnings: list[str] = []
    corrected_graph: ExtractedGraph | None = None


class SafetyCheckResult(BaseModel):
    is_violation: bool
    warning: str | None = None
    risk_level: str = "None"


class SemanticDuplicateWarning(BaseModel):
    """Warning about a semantically similar existing node."""

    new_text: str
    existing_text: str
    similarity_score: float
    label: str
    node_id: str


class RegistrationResult(BaseModel):
    status: str
    client_name: str | None = None
    registered_count: int = 0
    registered_types: list[str] = []
    message: str | None = None
    semanticDuplicates: list[SemanticDuplicateWarning] = Field(default_factory=list)


class QuickLogRequest(BaseModel):
    client_name: str
    note: str
    situation: str | None = None
    supporter_name: str = "system"
