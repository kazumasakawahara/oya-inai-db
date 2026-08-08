"""Ecomap data from Neo4j. No draw.io — frontend renders with React Flow."""
import logging
from app.lib.db_operations import run_query
from app.schemas.ecomap import EcomapData, EcomapEdge, EcomapNode

logger = logging.getLogger(__name__)

TEMPLATES = {
    "full_view": {
        "name": "全体像", "description": "クライアントの全支援ネットワーク",
        "categories": ["conditions", "ngActions", "carePreferences", "keyPersons", "guardians", "hospitals", "certificates", "supporters", "services"],
    },
    "support_meeting": {
        "name": "支援会議用", "description": "支援者・機関を中心に表示",
        "categories": ["keyPersons", "supporters", "services", "guardians"],
    },
    "emergency": {
        "name": "緊急時", "description": "禁忌事項・緊急連絡先を優先表示",
        "categories": ["ngActions", "carePreferences", "keyPersons", "hospitals", "guardians"],
    },
    "handover": {
        "name": "引き継ぎ用", "description": "ケア指示・医療情報を中心に表示",
        "categories": ["conditions", "ngActions", "carePreferences", "hospitals", "certificates", "keyPersons"],
    },
}

# Neo4j Browser palette
CATEGORY_COLORS = {
    "client": "#569480",
    "ngActions": "#df4b26",
    "carePreferences": "#57c7e3",
    "keyPersons": "#f79767",
    "guardians": "#c990c0",
    "hospitals": "#4c8eda",
    "certificates": "#ffc454",
    "conditions": "#d9c8ae",
    "supporters": "#8dcc93",
    "services": "#ecb5c9",
}

CATEGORY_QUERIES = {
    "conditions":      ("(c)-[:HAS_CONDITION]->(n:Condition)",                   "n", "Condition",       "HAS_CONDITION"),
    "ngActions":       ("(c)-[:MUST_AVOID]->(n:NgAction)",                       "n", "NgAction",        "MUST_AVOID"),
    "carePreferences": ("(c)-[:REQUIRES]->(n:CarePreference)",                   "n", "CarePreference",  "REQUIRES"),
    "keyPersons":      ("(c)-[:HAS_KEY_PERSON]->(n:KeyPerson)",                  "n", "KeyPerson",       "HAS_KEY_PERSON"),
    "guardians":       ("(c)-[:HAS_LEGAL_REP]->(n:Guardian)",                    "n", "Guardian",        "HAS_LEGAL_REP"),
    "hospitals":       ("(c)-[:TREATED_AT]->(n:Hospital)",                        "n", "Hospital",        "TREATED_AT"),
    "certificates":    ("(c)-[:HAS_CERTIFICATE]->(n:Certificate)",               "n", "Certificate",     "HAS_CERTIFICATE"),
    "supporters":      ("(s:Supporter)-[:LOGGED]->(:SupportLog)-[:ABOUT]->(c)",  "s", "Supporter",       "SUPPORTS"),
    "services":        ("(c)-[:USES_SERVICE]->(n:ServiceProvider)",               "n", "ServiceProvider", "USES_SERVICE"),
}


def _sanitize_id(element_id: str) -> str:
    """Neo4j elementId のコロンをハイフンに置換（React Flow の ID 互換性のため）"""
    return element_id.replace(":", "-")


def _sanitize_properties(props: dict) -> dict:
    """Neo4j 固有型（Date, DateTime 等）を文字列に変換し JSON シリアライズ可能にする"""
    result = {}
    for k, v in props.items():
        if v is None:
            result[k] = None
        elif isinstance(v, (str, int, float, bool)):
            result[k] = v
        elif isinstance(v, list):
            result[k] = [str(item) for item in v]
        else:
            result[k] = str(v)
    return result


def fetch_ecomap_data(client_name: str, template: str = "full_view") -> EcomapData:
    tmpl = TEMPLATES.get(template, TEMPLATES["full_view"])
    nodes = [EcomapNode(
        id="client",
        label=client_name,
        node_label="Client",
        category="client",
        color=CATEGORY_COLORS["client"],
        properties={},
    )]
    edges = []
    seen_ids: set[str] = set()

    for cat in tmpl["categories"]:
        if cat not in CATEGORY_QUERIES:
            continue
        pattern, var, neo4j_label, rel_label = CATEGORY_QUERIES[cat]
        query = f"MATCH {pattern} WHERE c.name = $name RETURN DISTINCT {var} AS node, elementId({var}) AS eid"
        records = run_query(query, {"name": client_name})
        for r in records:
            raw_id = r["eid"]
            nid = _sanitize_id(raw_id)
            # 重複ノードをスキップ
            if nid in seen_ids:
                continue
            seen_ids.add(nid)

            nd = _sanitize_properties(dict(r["node"]))
            display = nd.get("name") or nd.get("action") or nd.get("instruction") or nd.get("type") or str(nd)
            nodes.append(EcomapNode(
                id=nid,
                label=str(display)[:30],
                node_label=neo4j_label,
                category=cat,
                color=CATEGORY_COLORS.get(cat, "#888"),
                properties=nd,
            ))
            edges.append(EcomapEdge(source="client", target=nid, label=rel_label))
    return EcomapData(client_name=client_name, template=template, nodes=nodes, edges=edges)
