from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    neo4j_uri: str = "neo4j://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "password"

    gemini_api_key: str = ""
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    embedding_model: str = "gemini-embedding-2-preview"

    anthropic_api_key: str = ""
    claude_model: str = "claude-haiku-4-5-20251001"

    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma4:26b"

    # チャットで使用するプロバイダー: "gemini" / "claude" / "openai" / "ollama"
    chat_provider: str = "gemini"

    backend_port: int = 8001
    frontend_port: int = 3001

    model_config = {
        "env_file": str(Path(__file__).resolve().parents[2] / ".env"),
        "extra": "ignore",
    }


settings = Settings()
