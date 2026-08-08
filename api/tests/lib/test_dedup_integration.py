"""Integration tests for the full deduplication pipeline.

Verifies that register_to_database() correctly applies normalization
(normalize_name, normalize_condition, normalize_text) and auto-generates
sourceHash — all the way from input graph dict through to Neo4j session calls.

These tests use the same mocked-driver pattern as test_db_operations.py so no
real Neo4j connection is required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.lib.db_operations import register_to_database


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_mock_driver():
    """Create a MagicMock Neo4j driver whose session records every run() call."""
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.run = MagicMock(return_value=[])
    mock_driver = MagicMock()
    mock_driver.session = MagicMock(return_value=mock_session)
    return mock_driver


def _get_session(mock_driver):
    """Return the inner mock session from a mock driver."""
    return mock_driver.session.return_value.__enter__.return_value


def _find_merge_call(calls, label: str):
    """Return the first session.run() call that MERGEs a node with the given label."""
    for call in calls:
        cypher = call.args[0] if call.args else ""
        if "MERGE" in cypher and label in cypher:
            return call
    return None


def _find_create_call(calls, label: str):
    """Return the first session.run() call that CREATEs a node with the given label."""
    for call in calls:
        cypher = call.args[0] if call.args else ""
        if "CREATE" in cypher and label in cypher and "AuditLog" not in cypher:
            return call
    return None


# ---------------------------------------------------------------------------
# Full pipeline integration tests
# ---------------------------------------------------------------------------

class TestDedupPipeline:

    def test_fullwidth_name_normalized_before_merge(self):
        """Fullwidth ASCII chars in client name are converted to halfwidth before MERGE."""
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "Client", "properties": {"name": "ＡＢＣ太郎"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)

        assert result["status"] == "success"
        session = _get_session(mock_driver)
        merge_call = _find_merge_call(session.run.call_args_list, "Client")
        assert merge_call is not None, "Expected a MERGE call for Client"
        # The $name parameter passed to session.run must be normalized
        assert merge_call.args[1]["name"] == "ABC太郎"

    def test_condition_alias_resolved_in_pipeline(self):
        """Condition alias 'ADHD' is resolved to '注意欠如多動症' before MERGE."""
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [
                {"temp_id": "c1", "label": "Client", "properties": {"name": "田中太郎"}},
                {"temp_id": "cond1", "label": "Condition", "properties": {"name": "ADHD"}},
            ],
            "relationships": [
                {
                    "source_temp_id": "c1",
                    "target_temp_id": "cond1",
                    "type": "HAS_CONDITION",
                    "properties": {},
                }
            ],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)

        assert result["status"] == "success"
        session = _get_session(mock_driver)
        merge_call = _find_merge_call(session.run.call_args_list, "Condition")
        assert merge_call is not None, "Expected a MERGE call for Condition"
        assert merge_call.args[1]["name"] == "注意欠如多動症"

    def test_supportlog_gets_auto_sourcehash(self):
        """SupportLog without an explicit sourceHash receives one automatically."""
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [
                {
                    "label": "SupportLog",
                    "properties": {
                        "date": "2026-04-14",
                        "situation": "食事中に騒いでいた",
                        "action": "静かに話しかけた",
                    },
                }
            ],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)

        assert result["status"] == "success"
        session = _get_session(mock_driver)
        create_call = _find_create_call(session.run.call_args_list, "SupportLog")
        assert create_call is not None, "Expected a CREATE call for SupportLog"
        props = create_call.args[1]["props"]
        assert "sourceHash" in props
        assert len(props["sourceHash"]) == 64  # SHA-256 hex digest

    def test_same_supportlog_props_produce_same_hash(self):
        """Identical SupportLog properties deterministically produce the same sourceHash."""
        props = {
            "date": "2026-04-14",
            "situation": "パニック発生",
            "action": "見守り対応",
        }
        graph = {
            "nodes": [{"label": "SupportLog", "properties": dict(props)}],
            "relationships": [],
        }

        hashes = []
        for _ in range(2):
            md = _make_mock_driver()
            with patch("app.lib.db_operations.get_driver", return_value=md):
                register_to_database(
                    {"nodes": [{"label": "SupportLog", "properties": dict(props)}], "relationships": []}
                )
            session = _get_session(md)
            create_call = _find_create_call(session.run.call_args_list, "SupportLog")
            hashes.append(create_call.args[1]["props"]["sourceHash"])

        assert hashes[0] == hashes[1], "sourceHash must be deterministic for identical props"

    def test_honorific_stripped_from_supporter_name(self):
        """Supporter '鈴木さん' is MERGE'd under the normalized key '鈴木'."""
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "Supporter", "properties": {"name": "鈴木さん"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)

        assert result["status"] == "success"
        session = _get_session(mock_driver)
        merge_call = _find_merge_call(session.run.call_args_list, "Supporter")
        assert merge_call is not None, "Expected a MERGE call for Supporter"
        assert merge_call.args[1]["name"] == "鈴木"

    def test_ngaction_whitespace_normalized(self):
        """NgAction with extra and ideographic whitespace is collapsed before MERGE."""
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [
                {
                    "label": "NgAction",
                    "properties": {"action": "  後ろから\u3000急に\u3000声をかける  "},
                }
            ],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)

        assert result["status"] == "success"
        session = _get_session(mock_driver)
        merge_call = _find_merge_call(session.run.call_args_list, "NgAction")
        assert merge_call is not None, "Expected a MERGE call for NgAction"
        assert merge_call.args[1]["action"] == "後ろから 急に 声をかける"

    def test_mixed_graph_normalization(self):
        """Full graph with multiple node types — all normalized correctly.

        Client(name='田中太郎さん') → '田中太郎'
        Condition(name='ASD')       → '自閉症スペクトラム障害'
        NgAction(action='  大声  ') → '大声'
        SupportLog                  → has sourceHash
        """
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [
                {"temp_id": "c1",   "label": "Client",     "properties": {"name": "田中太郎さん"}},
                {"temp_id": "cd1",  "label": "Condition",  "properties": {"name": "ASD"}},
                {"temp_id": "ng1",  "label": "NgAction",   "properties": {"action": "  大声  "}},
                {
                    "temp_id": "sl1",
                    "label": "SupportLog",
                    "properties": {"date": "2026-04-14", "note": "落ち着いた"},
                },
            ],
            "relationships": [
                {"source_temp_id": "c1", "target_temp_id": "cd1", "type": "HAS_CONDITION",  "properties": {}},
                {"source_temp_id": "c1", "target_temp_id": "ng1", "type": "MUST_AVOID",     "properties": {}},
            ],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)

        assert result["status"] == "success"
        assert result["registered_count"] == 4

        session = _get_session(mock_driver)
        calls = session.run.call_args_list

        # Client: honorific stripped
        client_merge = _find_merge_call(calls, "Client")
        assert client_merge is not None
        assert client_merge.args[1]["name"] == "田中太郎"

        # Condition: alias resolved
        cond_merge = _find_merge_call(calls, "Condition")
        assert cond_merge is not None
        assert cond_merge.args[1]["name"] == "自閉症スペクトラム障害"

        # NgAction: whitespace collapsed
        ng_merge = _find_merge_call(calls, "NgAction")
        assert ng_merge is not None
        assert ng_merge.args[1]["action"] == "大声"

        # SupportLog: sourceHash auto-generated
        sl_create = _find_create_call(calls, "SupportLog")
        assert sl_create is not None
        assert "sourceHash" in sl_create.args[1]["props"]
        assert len(sl_create.args[1]["props"]["sourceHash"]) == 64

    def test_keyperson_honorific_stripped(self):
        """KeyPerson (another _NAME_NORMALIZED_LABELS member) strips honorific."""
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "KeyPerson", "properties": {"name": "佐藤先生"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)

        assert result["status"] == "success"
        session = _get_session(mock_driver)
        merge_call = _find_merge_call(session.run.call_args_list, "KeyPerson")
        assert merge_call is not None
        assert merge_call.args[1]["name"] == "佐藤"

    def test_meetingrecord_gets_auto_sourcehash(self):
        """MeetingRecord (another _HASHABLE_CREATE_LABELS member) also gets sourceHash."""
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [
                {
                    "label": "MeetingRecord",
                    "properties": {"date": "2026-04-14", "title": "家族面談"},
                }
            ],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)

        assert result["status"] == "success"
        session = _get_session(mock_driver)
        create_call = _find_create_call(session.run.call_args_list, "MeetingRecord")
        assert create_call is not None
        assert "sourceHash" in create_call.args[1]["props"]

    def test_existing_sourcehash_not_overwritten(self):
        """A SupportLog that already has sourceHash must not have it replaced."""
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [
                {
                    "label": "SupportLog",
                    "properties": {
                        "date": "2026-04-14",
                        "sourceHash": "deadbeef" * 8,  # 64 hex chars
                    },
                }
            ],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            register_to_database(graph)

        session = _get_session(mock_driver)
        create_call = _find_create_call(session.run.call_args_list, "SupportLog")
        assert create_call is not None
        assert create_call.args[1]["props"]["sourceHash"] == "deadbeef" * 8

    def test_condition_alias_case_insensitive(self):
        """Condition alias lookup is case-insensitive ('asd' → canonical)."""
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "Condition", "properties": {"name": "asd"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)

        assert result["status"] == "success"
        session = _get_session(mock_driver)
        merge_call = _find_merge_call(session.run.call_args_list, "Condition")
        assert merge_call is not None
        assert merge_call.args[1]["name"] == "自閉症スペクトラム障害"

    def test_fullwidth_name_in_supporter_with_honorific(self):
        """Fullwidth chars are converted AND honorific is stripped in one pass."""
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "Supporter", "properties": {"name": "ＡＢＣさん"}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)

        assert result["status"] == "success"
        session = _get_session(mock_driver)
        merge_call = _find_merge_call(session.run.call_args_list, "Supporter")
        assert merge_call is not None
        assert merge_call.args[1]["name"] == "ABC"

    def test_care_preference_merge_keys_normalized(self):
        """CarePreference category and instruction are whitespace-trimmed before MERGE."""
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [
                {
                    "label": "CarePreference",
                    "properties": {
                        "category": "  パニック時 ",
                        "instruction": " 静かに見守る ",
                    },
                }
            ],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)

        assert result["status"] == "success"
        session = _get_session(mock_driver)
        merge_call = _find_merge_call(session.run.call_args_list, "CarePreference")
        assert merge_call is not None
        assert merge_call.args[1]["category"] == "パニック時"
        assert merge_call.args[1]["instruction"] == "静かに見守る"

    def test_pipeline_result_client_name_is_normalized(self):
        """register_to_database() returns the normalized client_name in the result dict."""
        mock_driver = _make_mock_driver()
        graph = {
            "nodes": [{"label": "Client", "properties": {"name": "  山田花子様  "}}],
            "relationships": [],
        }
        with patch("app.lib.db_operations.get_driver", return_value=mock_driver):
            result = register_to_database(graph)

        assert result["status"] == "success"
        # normalize_name strips whitespace and honorific
        assert result["client_name"] == "山田花子"
