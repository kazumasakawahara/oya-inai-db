"""Comprehensive tests for db_operations module.

Tests cover constants validation, sanitization, node registration,
and relationship handling — all with mocked Neo4j driver.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.lib.db_operations import (
    MERGE_KEYS,
    ALLOWED_CREATE_LABELS,
    ALLOWED_LABELS,
    ALLOWED_REL_TYPES,
    _sanitize_value,
    _sanitize_record,
    register_to_database,
)


# ---------------------------------------------------------------------------
# Constants: ALLOWED_LABELS
# ---------------------------------------------------------------------------

class TestAllowedLabels:
    def test_allowed_labels_include_core_types(self):
        core_types = {"Client", "Supporter", "NgAction", "CarePreference", "Condition"}
        assert core_types.issubset(ALLOWED_LABELS)

    def test_allowed_labels_include_support_network(self):
        network_types = {"KeyPerson", "Hospital", "Guardian", "Organization", "ServiceProvider"}
        assert network_types.issubset(ALLOWED_LABELS)

    def test_allowed_labels_include_create_only_types(self):
        create_only = {"SupportLog", "AuditLog", "MeetingRecord", "LifeHistory", "Wish", "PublicAssistance"}
        assert create_only.issubset(ALLOWED_LABELS)

    def test_allowed_labels_is_union_of_merge_and_create(self):
        expected = set(MERGE_KEYS.keys()) | ALLOWED_CREATE_LABELS
        assert ALLOWED_LABELS == expected

    def test_no_overlap_between_merge_and_create(self):
        overlap = set(MERGE_KEYS.keys()) & ALLOWED_CREATE_LABELS
        assert overlap == set(), f"Labels in both MERGE_KEYS and ALLOWED_CREATE_LABELS: {overlap}"


# ---------------------------------------------------------------------------
# Constants: ALLOWED_REL_TYPES
# ---------------------------------------------------------------------------

class TestAllowedRelTypes:
    def test_allowed_rel_types_include_core_types(self):
        core_rels = {
            "HAS_CONDITION", "MUST_AVOID", "REQUIRES", "HAS_KEY_PERSON",
            "HAS_LEGAL_REP", "HAS_CERTIFICATE", "TREATED_AT", "LOGGED",
            "ABOUT", "RECORDED", "FOLLOWS", "IN_CONTEXT",
        }
        assert core_rels.issubset(ALLOWED_REL_TYPES)

    def test_allowed_rel_types_are_upper_snake_case(self):
        for rel in ALLOWED_REL_TYPES:
            assert rel == rel.upper(), f"Relation type {rel!r} is not UPPER_SNAKE_CASE"
            assert " " not in rel, f"Relation type {rel!r} contains a space"

    def test_deprecated_types_not_in_allowed(self):
        deprecated = {"PROHIBITED", "PREFERS", "EMERGENCY_CONTACT", "RELATES_TO"}
        for dep in deprecated:
            assert dep not in ALLOWED_REL_TYPES, f"Deprecated type {dep} still in ALLOWED_REL_TYPES"

    def test_rel_types_is_a_set(self):
        assert isinstance(ALLOWED_REL_TYPES, (set, frozenset))


# ---------------------------------------------------------------------------
# Constants: MERGE_KEYS
# ---------------------------------------------------------------------------

class TestMergeKeys:
    def test_merge_keys_defined_for_core_labels(self):
        core_labels = {
            "Client", "Supporter", "NgAction", "CarePreference", "Condition",
            "KeyPerson", "Organization", "ServiceProvider", "Hospital",
            "Guardian", "Certificate",
        }
        assert core_labels.issubset(set(MERGE_KEYS.keys()))

    def test_merge_keys_values_are_nonempty_string_lists(self):
        for label, keys in MERGE_KEYS.items():
            assert isinstance(keys, list), f"MERGE_KEYS[{label!r}] is not a list"
            assert len(keys) >= 1, f"MERGE_KEYS[{label!r}] is empty"
            for k in keys:
                assert isinstance(k, str), f"Key {k!r} in MERGE_KEYS[{label!r}] is not a str"

    def test_client_merges_on_name(self):
        assert MERGE_KEYS["Client"] == ["name"]

    def test_care_preference_merges_on_category_and_instruction(self):
        assert set(MERGE_KEYS["CarePreference"]) == {"category", "instruction"}

    def test_ng_action_merges_on_action(self):
        assert MERGE_KEYS["NgAction"] == ["action"]

    def test_certificate_merges_on_type_and_grade(self):
        assert MERGE_KEYS["Certificate"] == ["type", "grade"]


# ---------------------------------------------------------------------------
# _sanitize_value / _sanitize_record
# ---------------------------------------------------------------------------

class TestSanitizeValue:
    def test_string_passthrough(self):
        assert _sanitize_value("hello") == "hello"

    def test_int_passthrough(self):
        assert _sanitize_value(42) == 42

    def test_float_passthrough(self):
        assert _sanitize_value(3.14) == 3.14

    def test_bool_passthrough(self):
        assert _sanitize_value(True) is True

    def test_none_passthrough(self):
        assert _sanitize_value(None) is None

    def test_neo4j_date_to_string(self):
        from neo4j.time import Date as Neo4jDate
        neo4j_date = Neo4jDate(2026, 4, 5)
        result = _sanitize_value(neo4j_date)
        assert isinstance(result, str)
        assert "2026" in result

    def test_neo4j_datetime_to_string(self):
        from neo4j.time import DateTime as Neo4jDateTime
        neo4j_dt = Neo4jDateTime(2026, 4, 5, 10, 30, 0)
        result = _sanitize_value(neo4j_dt)
        assert isinstance(result, str)
        assert "2026" in result

    def test_dict_recursive_sanitize(self):
        from neo4j.time import Date as Neo4jDate
        data = {"date": Neo4jDate(2026, 1, 1), "name": "test"}
        result = _sanitize_value(data)
        assert isinstance(result["date"], str)
        assert result["name"] == "test"

    def test_list_recursive_sanitize(self):
        from neo4j.time import Date as Neo4jDate
        data = [Neo4jDate(2026, 1, 1), "hello", 42]
        result = _sanitize_value(data)
        assert isinstance(result[0], str)
        assert result[1] == "hello"
        assert result[2] == 42


class TestSanitizeRecord:
    def test_sanitize_record_basic(self):
        record = {"name": "テスト", "count": 5}
        result = _sanitize_record(record)
        assert result == {"name": "テスト", "count": 5}

    def test_sanitize_record_with_neo4j_types(self):
        from neo4j.time import Date as Neo4jDate
        record = {"date": Neo4jDate(2026, 4, 5), "value": "ok"}
        result = _sanitize_record(record)
        assert isinstance(result["date"], str)
        assert result["value"] == "ok"


# ---------------------------------------------------------------------------
# register_to_database
# ---------------------------------------------------------------------------

def _make_mock_driver():
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.run = MagicMock(return_value=[])
    mock_driver = MagicMock()
    mock_driver.session = MagicMock(return_value=mock_session)
    return mock_driver


class TestRegisterToDatabaseValidation:
    """Test input validation without a real Neo4j connection."""

    def test_empty_graph_returns_success(self):
        mock_driver = _make_mock_driver()
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database({"nodes": [], "relationships": []})
        assert result["status"] == "success"
        assert result["registered_count"] == 0

    def test_missing_nodes_key_returns_success(self):
        mock_driver = _make_mock_driver()
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database({})
        assert result["status"] == "success"

    def test_none_nodes_returns_success(self):
        mock_driver = _make_mock_driver()
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database({"nodes": None, "relationships": None})
        assert result["status"] == "success"
        assert result["registered_count"] == 0

    def test_invalid_label_is_skipped(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "INVALID_LABEL", "properties": {"name": "test"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert result["status"] == "success"
        assert result["registered_count"] == 0

    def test_valid_client_node_is_registered(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "Client", "properties": {"name": "田中太郎"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert result["status"] == "success"
        assert result["registered_count"] >= 1
        assert result["client_name"] == "田中太郎"

    def test_multiple_nodes_registered(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [
                {"temp_id": "c1", "label": "Client", "properties": {"name": "テスト"}},
                {"temp_id": "ng1", "label": "NgAction", "properties": {"action": "大声"}},
                {"temp_id": "cp1", "label": "CarePreference", "properties": {"category": "コミュ", "instruction": "ゆっくり"}},
            ],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert result["registered_count"] == 3
        assert "Client" in result["registered_types"]
        assert "NgAction" in result["registered_types"]

    def test_missing_merge_key_skips_node(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "Client", "properties": {"dob": "2000-01-01"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert result["registered_count"] == 0

    def test_result_contains_registered_types(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "Client", "properties": {"name": "山田花子"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert "registered_types" in result
        assert isinstance(result["registered_types"], list)

    def test_driver_error_returns_error_status(self):
        mock_driver = MagicMock()
        mock_driver.session.side_effect = Exception("Connection refused")
        graph = {
            "nodes": [{"label": "Client", "properties": {"name": "エラーテスト"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert result["status"] == "error"
        assert "Connection refused" in result.get("error", "")


# ---------------------------------------------------------------------------
# ServiceProvider wamnetId-first MERGE strategy
# ---------------------------------------------------------------------------

class TestServiceProviderWamnetIdMerge:
    def test_with_wamnetid_merges_by_wamnetid(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "ServiceProvider", "properties": {
                "name": "テスト事業所",
                "wamnetId": "1234567890",
            }}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert result["status"] == "success"
        mock_session = mock_driver.session.return_value.__enter__.return_value
        calls = mock_session.run.call_args_list
        merge_call = [c for c in calls if "ServiceProvider" in str(c.args[0]) and "MERGE" in str(c.args[0])][0]
        cypher = merge_call.args[0]
        # MERGE should use wamnetId, not name
        assert "wamnetId" in cypher
        assert merge_call.args[1]["wamnetId"] == "1234567890"
        # name should be in extra_props, not merge props
        assert "name" in merge_call.args[1]["extra_props"]

    def test_without_wamnetid_falls_back_to_name(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "ServiceProvider", "properties": {"name": "テスト事業所"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert result["status"] == "success"
        mock_session = mock_driver.session.return_value.__enter__.return_value
        calls = mock_session.run.call_args_list
        merge_call = [c for c in calls if "ServiceProvider" in str(c.args[0]) and "MERGE" in str(c.args[0])][0]
        cypher = merge_call.args[0]
        assert "name" in cypher
        assert merge_call.args[1]["name"] == "テスト事業所"

    def test_wamnetid_is_normalized(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "ServiceProvider", "properties": {
                "name": "テスト", "wamnetId": "  １２３４  ",
            }}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            register_to_database(graph)
        mock_session = mock_driver.session.return_value.__enter__.return_value
        calls = mock_session.run.call_args_list
        merge_call = [c for c in calls if "ServiceProvider" in str(c.args[0]) and "MERGE" in str(c.args[0])][0]
        assert merge_call.args[1]["wamnetId"] == "1234"

    def test_create_only_label_registered(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"temp_id": "sl1", "label": "SupportLog", "properties": {"date": "2026-04-01", "note": "ok"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert result["registered_count"] == 1
        assert "SupportLog" in result["registered_types"]


class TestRegisterToDatabaseRelationships:
    """Test relationship registration with temp_id resolution."""

    def test_relationships_with_temp_ids(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [
                {"temp_id": "c1", "label": "Client", "properties": {"name": "テスト"}},
                {"temp_id": "ng1", "label": "NgAction", "properties": {"action": "テスト行動"}},
            ],
            "relationships": [
                {"source_temp_id": "c1", "target_temp_id": "ng1", "type": "MUST_AVOID", "properties": {}},
            ],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)

        assert result["status"] == "success"
        # session.run should have been called for nodes + relationships + audit log
        mock_session = mock_driver.session.return_value.__enter__.return_value
        assert mock_session.run.call_count >= 3  # 2 nodes + 1 relationship (+ audit)

    def test_relationship_with_invalid_type_skipped(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [
                {"temp_id": "c1", "label": "Client", "properties": {"name": "テスト"}},
                {"temp_id": "n1", "label": "Supporter", "properties": {"name": "サポーター"}},
            ],
            "relationships": [
                {
                    "type": "FAKE_TYPE",
                    "from_label": "Client",
                    "from_key": "name",
                    "from_value": "テスト",
                    "to_label": "Supporter",
                    "to_key": "name",
                    "to_value": "サポーター",
                    "properties": {},
                },
            ],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)

        assert result["status"] == "success"

    def test_unresolvable_temp_ids_skipped(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"temp_id": "c1", "label": "Client", "properties": {"name": "テスト"}}],
            "relationships": [
                {"source_temp_id": "c1", "target_temp_id": "nonexistent", "type": "MUST_AVOID", "properties": {}},
            ],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)

        # Should succeed — unresolvable relationships are silently skipped
        assert result["status"] == "success"


class TestRegisterNodeNormalization:
    def test_client_name_strips_whitespace(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "Client", "properties": {"name": "  田中太郎  "}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert result["status"] == "success"
        assert result["client_name"] == "田中太郎"

    def test_client_name_strips_honorific(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "Client", "properties": {"name": "田中太郎さん"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert result["client_name"] == "田中太郎"

    def test_condition_alias_resolved(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "Condition", "properties": {"name": "ASD"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert result["status"] == "success"
        mock_session = mock_driver.session.return_value.__enter__.return_value
        calls = mock_session.run.call_args_list
        merge_call = [c for c in calls if "Condition" in str(c.args[0]) and "MERGE" in str(c.args[0])][0]
        assert merge_call.args[1]["name"] == "自閉症スペクトラム障害"

    def test_ngaction_text_normalized(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "NgAction", "properties": {"action": "  大きな\u3000音  "}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert result["status"] == "success"
        mock_session = mock_driver.session.return_value.__enter__.return_value
        calls = mock_session.run.call_args_list
        merge_call = [c for c in calls if "NgAction" in str(c.args[0]) and "MERGE" in str(c.args[0])][0]
        assert merge_call.args[1]["action"] == "大きな 音"

    def test_care_preference_normalized(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "CarePreference", "properties": {"category": " パニック時 ", "instruction": " 静かに見守る "}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert result["status"] == "success"
        mock_session = mock_driver.session.return_value.__enter__.return_value
        calls = mock_session.run.call_args_list
        merge_call = [c for c in calls if "CarePreference" in str(c.args[0]) and "MERGE" in str(c.args[0])][0]
        assert merge_call.args[1]["category"] == "パニック時"
        assert merge_call.args[1]["instruction"] == "静かに見守る"


class TestRegisterToDatabaseAuditLog:
    """Test audit log creation during registration."""

    def test_audit_log_created_when_client_present(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"temp_id": "c1", "label": "Client", "properties": {"name": "監査テスト"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph, user_name="test_user")

        assert result["status"] == "success"
        mock_session = mock_driver.session.return_value.__enter__.return_value
        # Find the audit log call (contains AuditLog in the cypher)
        audit_calls = [
            c for c in mock_session.run.call_args_list
            if "AuditLog" in str(c)
        ]
        assert len(audit_calls) >= 1

    def test_no_audit_log_without_client(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"temp_id": "s1", "label": "Supporter", "properties": {"name": "テスト"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)

        assert result["status"] == "success"
        mock_session = mock_driver.session.return_value.__enter__.return_value
        # No audit log should be created (no client_name)
        audit_calls = [
            c for c in mock_session.run.call_args_list
            if "AuditLog" in str(c)
        ]
        assert len(audit_calls) == 0


class TestSourceHashAutoGeneration:
    def test_supportlog_gets_sourcehash(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "SupportLog", "properties": {"date": "2026-04-14", "note": "テスト"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert result["status"] == "success"
        mock_session = mock_driver.session.return_value.__enter__.return_value
        calls = mock_session.run.call_args_list
        create_call = [c for c in calls if "CREATE" in str(c.args[0]) and "SupportLog" in str(c.args[0])][0]
        props = create_call.args[1]["props"]
        assert "sourceHash" in props
        assert len(props["sourceHash"]) == 64  # SHA256 hex

    def test_supportlog_preserves_existing_sourcehash(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "SupportLog", "properties": {"date": "2026-04-14", "sourceHash": "existinghash123"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            register_to_database(graph)
        mock_session = mock_driver.session.return_value.__enter__.return_value
        calls = mock_session.run.call_args_list
        create_call = [c for c in calls if "CREATE" in str(c.args[0]) and "SupportLog" in str(c.args[0])][0]
        assert create_call.args[1]["props"]["sourceHash"] == "existinghash123"

    def test_meetingrecord_gets_sourcehash(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "MeetingRecord", "properties": {"date": "2026-04-14", "title": "面談"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            register_to_database(graph)
        mock_session = mock_driver.session.return_value.__enter__.return_value
        calls = mock_session.run.call_args_list
        create_call = [c for c in calls if "CREATE" in str(c.args[0]) and "MeetingRecord" in str(c.args[0])][0]
        assert "sourceHash" in create_call.args[1]["props"]

    def test_auditlog_does_not_get_sourcehash(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "AuditLog", "properties": {"action": "test", "userName": "user"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            register_to_database(graph)
        mock_session = mock_driver.session.return_value.__enter__.return_value
        calls = mock_session.run.call_args_list
        create_call = [c for c in calls if "CREATE" in str(c.args[0]) and "AuditLog" in str(c.args[0])][0]
        assert "sourceHash" not in create_call.args[1]["props"]

    def test_same_props_produce_same_hash(self):
        """Deterministic: identical properties → identical sourceHash."""
        mock_driver1 = _make_mock_driver()
        mock_driver2 = _make_mock_driver()
        props = {"date": "2026-04-14", "situation": "パニック", "action": "見守り"}
        graph = {"nodes": [{"label": "SupportLog", "properties": dict(props)}], "relationships": []}

        hashes = []
        for md in [mock_driver1, mock_driver2]:
            with patch("app.lib.db_operations.get_driver", return_value=md):
                register_to_database({"nodes": [{"label": "SupportLog", "properties": dict(props)}], "relationships": []})
            session = md.session.return_value.__enter__.return_value
            call = [c for c in session.run.call_args_list if "CREATE" in str(c.args[0]) and "SupportLog" in str(c.args[0])][0]
            hashes.append(call.args[1]["props"]["sourceHash"])

        assert hashes[0] == hashes[1]


# ---------------------------------------------------------------------------
# Client kana auto-generation
# ---------------------------------------------------------------------------

class TestClientKanaAutoGeneration:
    def test_client_gets_kana_auto_generated(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "Client", "properties": {"name": "田中太郎"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert result["status"] == "success"
        mock_session = mock_driver.session.return_value.__enter__.return_value
        calls = mock_session.run.call_args_list
        merge_call = [c for c in calls if "Client" in str(c.args[0]) and "MERGE" in str(c.args[0])][0]
        extra_props = merge_call.args[1]["extra_props"]
        assert "kana" in extra_props
        assert extra_props["kana"] == "たなかたろう"

    def test_client_preserves_existing_kana(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "Client", "properties": {"name": "田中太郎", "kana": "カスタムかな"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        mock_session = mock_driver.session.return_value.__enter__.return_value
        calls = mock_session.run.call_args_list
        merge_call = [c for c in calls if "Client" in str(c.args[0]) and "MERGE" in str(c.args[0])][0]
        extra_props = merge_call.args[1]["extra_props"]
        assert extra_props["kana"] == "カスタムかな"

    def test_supporter_does_not_get_kana(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "Supporter", "properties": {"name": "鈴木"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            register_to_database(graph)
        mock_session = mock_driver.session.return_value.__enter__.return_value
        calls = mock_session.run.call_args_list
        merge_call = [c for c in calls if "Supporter" in str(c.args[0]) and "MERGE" in str(c.args[0])][0]
        extra_props = merge_call.args[1]["extra_props"]
        assert "kana" not in extra_props


# ---------------------------------------------------------------------------
# Certificate composite MERGE key [type, grade]
# ---------------------------------------------------------------------------

class TestCertificateCompositeMerge:
    def test_certificate_merges_on_type_and_grade(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "Certificate", "properties": {"type": "療育手帳", "grade": "A"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert result["status"] == "success"
        mock_session = mock_driver.session.return_value.__enter__.return_value
        calls = mock_session.run.call_args_list
        merge_call = [c for c in calls if "Certificate" in str(c.args[0]) and "MERGE" in str(c.args[0])][0]
        params = merge_call.args[1]
        assert params["type"] == "療育手帳"
        assert params["grade"] == "A"

    def test_certificate_defaults_grade_when_missing(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "Certificate", "properties": {"type": "身体障害者手帳"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)
        assert result["status"] == "success"
        mock_session = mock_driver.session.return_value.__enter__.return_value
        calls = mock_session.run.call_args_list
        merge_call = [c for c in calls if "Certificate" in str(c.args[0]) and "MERGE" in str(c.args[0])][0]
        params = merge_call.args[1]
        assert params["grade"] == "不明"

    def test_certificate_normalizes_type_text(self):
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "Certificate", "properties": {"type": "  療育手帳  ", "grade": "B"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            register_to_database(graph)
        mock_session = mock_driver.session.return_value.__enter__.return_value
        calls = mock_session.run.call_args_list
        merge_call = [c for c in calls if "Certificate" in str(c.args[0]) and "MERGE" in str(c.args[0])][0]
        assert merge_call.args[1]["type"] == "療育手帳"
