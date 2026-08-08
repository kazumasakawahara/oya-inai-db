"""Comprehensive tests for the graph schema validator.

No external dependencies — tests pure validation logic.
"""

from app.agents.validator import validate_schema
from app.lib.db_operations import ALLOWED_LABELS, ALLOWED_REL_TYPES, MERGE_KEYS


class TestValidateSchemaNodes:
    """Test node validation."""

    def test_valid_single_client(self):
        graph = {
            "nodes": [{"temp_id": "c1", "label": "Client", "properties": {"name": "テスト太郎"}}],
            "relationships": [],
        }
        result = validate_schema(graph)
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_valid_multiple_node_types(self):
        graph = {
            "nodes": [
                {"temp_id": "c1", "label": "Client", "properties": {"name": "テスト"}},
                {"temp_id": "ng1", "label": "NgAction", "properties": {"action": "大声"}},
                {"temp_id": "cp1", "label": "CarePreference", "properties": {"category": "コミュ", "instruction": "ゆっくり"}},
                {"temp_id": "sl1", "label": "SupportLog", "properties": {"date": "2026-04-01"}},
            ],
            "relationships": [],
        }
        result = validate_schema(graph)
        assert result.is_valid is True

    def test_invalid_label(self):
        graph = {
            "nodes": [{"temp_id": "x1", "label": "FakeLabel", "properties": {"name": "test"}}],
            "relationships": [],
        }
        result = validate_schema(graph)
        assert result.is_valid is False
        assert any("FakeLabel" in e for e in result.errors)

    def test_multiple_invalid_labels(self):
        graph = {
            "nodes": [
                {"temp_id": "x1", "label": "BadLabel1", "properties": {}},
                {"temp_id": "x2", "label": "BadLabel2", "properties": {}},
            ],
            "relationships": [],
        }
        result = validate_schema(graph)
        assert result.is_valid is False
        assert len(result.errors) == 2

    def test_missing_merge_key_client_name(self):
        graph = {
            "nodes": [{"temp_id": "c1", "label": "Client", "properties": {"dob": "2000-01-01"}}],
            "relationships": [],
        }
        result = validate_schema(graph)
        assert result.is_valid is False
        assert any("name" in e for e in result.errors)

    def test_missing_merge_key_ng_action(self):
        graph = {
            "nodes": [{"temp_id": "ng1", "label": "NgAction", "properties": {"reason": "test"}}],
            "relationships": [],
        }
        result = validate_schema(graph)
        assert result.is_valid is False
        assert any("action" in e for e in result.errors)

    def test_missing_merge_key_care_preference(self):
        """CarePreference requires both category and instruction."""
        graph = {
            "nodes": [{"temp_id": "cp1", "label": "CarePreference", "properties": {"category": "テスト"}}],
            "relationships": [],
        }
        result = validate_schema(graph)
        assert result.is_valid is False
        assert any("instruction" in e for e in result.errors)

    def test_empty_merge_key_value(self):
        """Empty string for merge key should be treated as missing."""
        graph = {
            "nodes": [{"temp_id": "c1", "label": "Client", "properties": {"name": ""}}],
            "relationships": [],
        }
        result = validate_schema(graph)
        assert result.is_valid is False

    def test_create_only_labels_no_merge_key_required(self):
        """CREATE-only labels (SupportLog, AuditLog) don't need merge keys."""
        graph = {
            "nodes": [
                {"temp_id": "sl1", "label": "SupportLog", "properties": {"date": "2026-04-01", "note": "ok"}},
            ],
            "relationships": [],
        }
        result = validate_schema(graph)
        assert result.is_valid is True

    def test_empty_graph(self):
        result = validate_schema({"nodes": [], "relationships": []})
        assert result.is_valid is True


class TestValidateSchemaRelationships:
    """Test relationship validation."""

    def test_valid_relationship(self):
        graph = {
            "nodes": [
                {"temp_id": "c1", "label": "Client", "properties": {"name": "テスト"}},
                {"temp_id": "ng1", "label": "NgAction", "properties": {"action": "テスト"}},
            ],
            "relationships": [
                {"source_temp_id": "c1", "target_temp_id": "ng1", "type": "MUST_AVOID", "properties": {}},
            ],
        }
        result = validate_schema(graph)
        assert result.is_valid is True

    def test_invalid_relationship_type(self):
        graph = {
            "nodes": [
                {"temp_id": "c1", "label": "Client", "properties": {"name": "テスト"}},
                {"temp_id": "n1", "label": "NgAction", "properties": {"action": "テスト"}},
            ],
            "relationships": [
                {"source_temp_id": "c1", "target_temp_id": "n1", "type": "INVALID_REL", "properties": {}},
            ],
        }
        result = validate_schema(graph)
        assert result.is_valid is False
        assert any("INVALID_REL" in e for e in result.errors)

    def test_deprecated_relationship_types_are_invalid(self):
        """Deprecated relationship types should not be in ALLOWED_REL_TYPES."""
        deprecated = ["PROHIBITED", "PREFERS", "EMERGENCY_CONTACT", "RELATES_TO"]
        for rel_type in deprecated:
            assert rel_type not in ALLOWED_REL_TYPES, f"Deprecated {rel_type} is still allowed"

    def test_missing_source_temp_id(self):
        graph = {
            "nodes": [{"temp_id": "c1", "label": "Client", "properties": {"name": "テスト"}}],
            "relationships": [
                {"source_temp_id": "unknown", "target_temp_id": "c1", "type": "MUST_AVOID", "properties": {}},
            ],
        }
        result = validate_schema(graph)
        assert len(result.warnings) >= 1
        assert any("unknown" in w for w in result.warnings)

    def test_missing_target_temp_id(self):
        graph = {
            "nodes": [{"temp_id": "c1", "label": "Client", "properties": {"name": "テスト"}}],
            "relationships": [
                {"source_temp_id": "c1", "target_temp_id": "missing", "type": "MUST_AVOID", "properties": {}},
            ],
        }
        result = validate_schema(graph)
        assert len(result.warnings) >= 1
        assert any("missing" in w for w in result.warnings)

    def test_both_source_and_target_missing(self):
        graph = {
            "nodes": [],
            "relationships": [
                {"source_temp_id": "a", "target_temp_id": "b", "type": "MUST_AVOID", "properties": {}},
            ],
        }
        result = validate_schema(graph)
        assert len(result.warnings) >= 2

    def test_multiple_valid_relationships(self):
        graph = {
            "nodes": [
                {"temp_id": "c1", "label": "Client", "properties": {"name": "テスト"}},
                {"temp_id": "ng1", "label": "NgAction", "properties": {"action": "テスト1"}},
                {"temp_id": "cp1", "label": "CarePreference", "properties": {"category": "テスト", "instruction": "テスト"}},
            ],
            "relationships": [
                {"source_temp_id": "c1", "target_temp_id": "ng1", "type": "MUST_AVOID", "properties": {}},
                {"source_temp_id": "c1", "target_temp_id": "cp1", "type": "REQUIRES", "properties": {}},
            ],
        }
        result = validate_schema(graph)
        assert result.is_valid is True


class TestValidateSchemaAllLabels:
    """Verify all allowed labels pass validation."""

    def test_all_merge_labels_valid(self):
        for label, keys in MERGE_KEYS.items():
            props = {k: f"test_{k}" for k in keys}
            graph = {
                "nodes": [{"temp_id": "t1", "label": label, "properties": props}],
                "relationships": [],
            }
            result = validate_schema(graph)
            assert result.is_valid is True, f"Label {label} should be valid but got errors: {result.errors}"

    def test_all_rel_types_valid(self):
        for rel_type in ALLOWED_REL_TYPES:
            graph = {
                "nodes": [
                    {"temp_id": "c1", "label": "Client", "properties": {"name": "テスト"}},
                    {"temp_id": "n1", "label": "Supporter", "properties": {"name": "テスト2"}},
                ],
                "relationships": [
                    {"source_temp_id": "c1", "target_temp_id": "n1", "type": rel_type, "properties": {}},
                ],
            }
            result = validate_schema(graph)
            # rel type should be valid (there may be warnings about temp_id but no rel type errors)
            rel_errors = [e for e in result.errors if rel_type in e]
            assert len(rel_errors) == 0, f"Rel type {rel_type} should be valid"
