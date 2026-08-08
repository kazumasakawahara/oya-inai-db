"""Schema validation for extracted graph data (no LLM needed)."""
from app.lib.db_operations import ALLOWED_LABELS, ALLOWED_REL_TYPES, MERGE_KEYS
from app.schemas.narrative import ValidationResult


def validate_schema(graph: dict) -> ValidationResult:
    errors = []
    warnings = []
    nodes = graph.get("nodes", [])
    relationships = graph.get("relationships", [])
    temp_ids = {n["temp_id"] for n in nodes}

    for node in nodes:
        label = node.get("label", "")
        if label not in ALLOWED_LABELS:
            errors.append(f"Invalid node label: {label}")
        if label in MERGE_KEYS:
            for key in MERGE_KEYS[label]:
                if key not in node.get("properties", {}) or not node["properties"][key]:
                    errors.append(f"{label} missing required property: {key}")

    for rel in relationships:
        if rel.get("type", "") not in ALLOWED_REL_TYPES:
            errors.append(f"Invalid relationship type: {rel['type']}")
        if rel["source_temp_id"] not in temp_ids:
            warnings.append(f"Source '{rel['source_temp_id']}' not found")
        if rel["target_temp_id"] not in temp_ids:
            warnings.append(f"Target '{rel['target_temp_id']}' not found")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
