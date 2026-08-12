from pydantic import BaseModel


class SystemStatus(BaseModel):
    neo4j_available: bool
