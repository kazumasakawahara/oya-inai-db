from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    neo4j_uri: str = "neo4j://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "password"

    backend_port: int = 8001
    frontend_port: int = 3001

    model_config = {
        "env_file": str(Path(__file__).resolve().parents[2] / ".env"),
        "extra": "ignore",
    }


settings = Settings()
