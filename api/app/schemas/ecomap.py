from pydantic import BaseModel


class EcomapNode(BaseModel):
    id: str
    label: str
    node_label: str     # Neo4j label (Client, NgAction, etc.)
    category: str
    color: str          # hex color
    properties: dict


class EcomapEdge(BaseModel):
    source: str
    target: str
    label: str          # relationship name


class EcomapData(BaseModel):
    client_name: str
    template: str
    nodes: list[EcomapNode]
    edges: list[EcomapEdge]


class EcomapTemplate(BaseModel):
    id: str
    name: str
    description: str
