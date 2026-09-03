"""agno 実行時 allowlist 側の書き込み経路（lib/db_new_operations.py）の事実時間軸。

四者一致の③。lib/__init__.py は streamlit を巻き込むため、`lib` パッケージを
空の名前空間として先に登録し、モジュールをファイル直読みする。
"""

import importlib.util
import sys
import types
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def agno():
    if "lib" not in sys.modules:
        pkg = types.ModuleType("lib")
        pkg.__path__ = [str(REPO_ROOT / "lib")]
        sys.modules["lib"] = pkg
    path = REPO_ROOT / "lib" / "db_new_operations.py"
    spec = importlib.util.spec_from_file_location("_agno_db_new_operations", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _capture(agno):
    calls = []

    def fake_run_query(query, params=None):
        calls.append((query, params or {}))
        return [{"internal_id": f"id{len(calls)}"}]

    return calls, fake_run_query


class TestImmutableConstant:
    def test_registered_at_is_immutable_for_fact_labels(self, agno):
        assert agno.IMMUTABLE_PROPERTIES == {
            "NgAction": ["registeredAt"],
            "CarePreference": ["registeredAt"],
        }


class TestRegisterFactTime:
    def test_update_does_not_overwrite_registered_at(self, agno):
        calls, fake = _capture(agno)
        graph = {"nodes": [{"temp_id": "n1", "label": "NgAction",
                            "properties": {"action": "大声", "registeredAt": "2020-01-01"}}],
                 "relationships": []}
        with patch.object(agno, "run_query", fake), patch.object(agno, "create_audit_log"):
            agno.register_to_database(graph)
        cypher, params = calls[0]
        assert "ON CREATE SET n += $create_props" in cypher
        assert "ON MATCH SET n += $update_props" in cypher
        assert "registeredAt" not in params["update_props"]
        assert params["create_props"]["registeredAt"] == date(2020, 1, 1)

    def test_create_defaults_registered_at_to_today(self, agno):
        calls, fake = _capture(agno)
        graph = {"nodes": [{"temp_id": "n1", "label": "CarePreference",
                            "properties": {"category": "食事", "instruction": "刻み食"}}],
                 "relationships": []}
        with patch.object(agno, "run_query", fake):
            agno.register_to_database(graph)
        _, params = calls[0]
        assert params["create_props"]["registeredAt"] == date.today()

    def test_inactive_without_valid_to_is_skipped(self, agno):
        calls, fake = _capture(agno)
        graph = {"nodes": [{"temp_id": "n1", "label": "NgAction",
                            "properties": {"action": "大声", "status": "Inactive"}}],
                 "relationships": []}
        with patch.object(agno, "run_query", fake), patch.object(agno, "create_audit_log"):
            result = agno.register_to_database(graph)
        assert calls == []
        assert result["registered_count"] == 0


class TestKeyPersonRelationship:
    def test_create_gets_start_date_and_active_status(self, agno):
        calls, fake = _capture(agno)
        graph = {
            "nodes": [
                {"temp_id": "c1", "label": "Client", "properties": {"name": "テスト太郎"}},
                {"temp_id": "k1", "label": "KeyPerson", "properties": {"name": "テスト花子"}},
            ],
            "relationships": [{"source_temp_id": "c1", "target_temp_id": "k1",
                               "type": "HAS_KEY_PERSON", "properties": {"rank": 1}}],
        }
        with patch.object(agno, "run_query", fake), patch.object(agno, "create_audit_log"):
            agno.register_to_database(graph)
        cypher, params = [c for c in calls if "HAS_KEY_PERSON" in c[0]][0]
        assert "ON CREATE SET r += $create_props" in cypher
        assert params["create_props"]["startDate"] == date.today()
        assert params["create_props"]["status"] == "Active"

    def test_bad_status_is_skipped(self, agno):
        calls, fake = _capture(agno)
        graph = {
            "nodes": [
                {"temp_id": "c1", "label": "Client", "properties": {"name": "テスト太郎"}},
                {"temp_id": "k1", "label": "KeyPerson", "properties": {"name": "テスト花子"}},
            ],
            "relationships": [{"source_temp_id": "c1", "target_temp_id": "k1",
                               "type": "HAS_KEY_PERSON", "properties": {"rank": 1, "status": "Ended"}}],
        }
        with patch.object(agno, "run_query", fake), patch.object(agno, "create_audit_log"):
            agno.register_to_database(graph)
        assert not any("HAS_KEY_PERSON" in c[0] for c in calls)
