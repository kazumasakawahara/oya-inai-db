from pydantic import BaseModel


class ChatMessage(BaseModel):
    type: str
    content: str | None = None
    agent: str | None = None
    session_id: str | None = None


class ChatRequest(BaseModel):
    content: str
    session_id: str


class SystemStatus(BaseModel):
    gemini_available: bool
    claude_available: bool = False
    ollama_available: bool = False
    neo4j_available: bool
    chat_provider: str = "gemini"
    chat_model: str = ""
    embedding_model: str = ""
