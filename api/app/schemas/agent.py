from pydantic import BaseModel


class SystemStatus(BaseModel):
    gemini_available: bool
    claude_available: bool = False
    ollama_available: bool = False
    neo4j_available: bool
    chat_provider: str = "gemini"
    chat_model: str = ""
    embedding_model: str = ""
