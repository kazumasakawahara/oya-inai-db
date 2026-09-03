"""API 門番（app/lib/db_operations.py）の事実時間軸（Track A Phase 2 / v3.5・v1.8）。

MERGE の ON CREATE / ON MATCH で registeredAt の不変性と既定値を担う唯一の場所。
管理者裁定（Inactive + validTo + AuditLog）とキーパーソン交代（張り替え禁止）も
ここで 1 トランザクションにまとめる。すべて Neo4j をモックして検証する。
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.lib.db_operations import (
    IMMUTABLE_PROPERTIES,
    _register_node,
    _register_relationship,
    deactivate_fact,
    replace_key_person,
)


def _run_args(session, index=0):
    cypher, params = session.run.call_args_list[index][0]
    return cypher, params


# ---------------------------------------------------------------------------
# 正典との対応（DRIFT-12 様式）
# ---------------------------------------------------------------------------

class TestImmutableConstant:
    def test_registered_at_is_immutable_for_fact_labels(self):
        assert IMMUTABLE_PROPERTIES == {
            "NgAction": ["registeredAt"],
            "CarePreference": ["registeredAt"],
        }


# ---------------------------------------------------------------------------
# (a) registeredAt が更新で変わらない / CREATE で自動付与
# ---------------------------------------------------------------------------

class TestRegisterNodeFactTime:
    def test_update_does_not_overwrite_registered_at(self):
        session = MagicMock()
        ok = _register_node(session, "NgAction", {
            "action": "大声を出す", "registeredAt": "2020-01-01",
            "source": "本人", "status": "Active", "lastConfirmedAt": "2026-01-01",
        })
        assert ok is True
        cypher, params = _run_args(session)
        assert "ON CREATE SET n += $create_props" in cypher
        assert "ON MATCH SET n += $update_props" in cypher
        assert "registeredAt" not in params["update_props"]
        assert params["create_props"]["registeredAt"] == date(2020, 1, 1)

    def test_create_defaults_registered_at_to_today(self):
        session = MagicMock()
        _register_node(session, "CarePreference", {"category": "食事", "instruction": "刻み食"})
        _, params = _run_args(session)
        assert params["create_props"]["registeredAt"] == date.today()
        assert "registeredAt" not in params["update_props"]

    def test_date_strings_are_stored_as_dates(self):
        session = MagicMock()
        _register_node(session, "NgAction", {
            "action": "x", "status": "Inactive", "validFrom": "2025-04-01", "validTo": "2026-03-31",
        })
        _, params = _run_args(session)
        assert params["create_props"]["validFrom"] == date(2025, 4, 1)
        assert params["update_props"]["validTo"] == date(2026, 3, 31)

    def test_non_fact_label_gets_no_registered_at(self):
        session = MagicMock()
        _register_node(session, "Condition", {"name": "自閉スペクトラム症"})
        _, params = _run_args(session)
        assert "registeredAt" not in params["create_props"]


# ---------------------------------------------------------------------------
# (b)(c) 規則違反は書き込まない
# ---------------------------------------------------------------------------

class TestRegisterNodeRejects:
    def test_inactive_without_valid_to_is_not_written(self):
        session = MagicMock()
        ok = _register_node(session, "NgAction", {"action": "x", "status": "Inactive"})
        assert ok is False
        session.run.assert_not_called()

    def test_active_with_valid_to_is_not_written(self):
        session = MagicMock()
        ok = _register_node(session, "NgAction", {"action": "x", "status": "Active", "validTo": "2026-01-01"})
        assert ok is False
        session.run.assert_not_called()

    def test_status_outside_three_values_is_not_written(self):
        session = MagicMock()
        ok = _register_node(session, "CarePreference", {"category": "a", "instruction": "b", "status": "Completed"})
        assert ok is False
        session.run.assert_not_called()


# ---------------------------------------------------------------------------
# HAS_KEY_PERSON: CREATE 時の既定値と値域
# ---------------------------------------------------------------------------

def _key_person_rel(props):
    return {
        "type": "HAS_KEY_PERSON",
        "from_label": "Client", "from_key": "name", "from_value": "テスト太郎",
        "to_label": "KeyPerson", "to_key": "name", "to_value": "テスト花子",
        "properties": props,
    }


class TestRegisterKeyPersonRelationship:
    def test_create_gets_start_date_and_active_status(self):
        session = MagicMock()
        ok = _register_relationship(session, _key_person_rel({"rank": 1}))
        assert ok is True
        cypher, params = _run_args(session)
        assert "ON CREATE SET r += $create_props" in cypher
        assert "ON MATCH SET r += $props" in cypher
        assert params["create_props"]["startDate"] == date.today()
        assert params["create_props"]["status"] == "Active"
        assert params["props"] == {"rank": 1}

    def test_explicit_start_date_is_kept_as_date(self):
        session = MagicMock()
        _register_relationship(session, _key_person_rel({"rank": 1, "startDate": "2024-04-01"}))
        _, params = _run_args(session)
        assert params["create_props"]["startDate"] == date(2024, 4, 1)

    def test_bad_status_is_not_written(self):
        session = MagicMock()
        ok = _register_relationship(session, _key_person_rel({"rank": 1, "status": "Ended"}))
        assert ok is False
        session.run.assert_not_called()

    def test_inactive_without_end_date_is_not_written(self):
        session = MagicMock()
        ok = _register_relationship(session, _key_person_rel({"rank": 1, "status": "Inactive"}))
        assert ok is False
        session.run.assert_not_called()


# ---------------------------------------------------------------------------
# 裁定経路: Inactive 化 + validTo + AuditLog を 1 トランザクションで
# ---------------------------------------------------------------------------

def _make_tx_driver():
    """driver.session() → session.execute_write(fn) が fn(tx) を同期実行するモック。"""
    tx = MagicMock()
    tx.run.return_value.single.return_value = {"n": {"action": "x"}}
    session = MagicMock()
    session.execute_write.side_effect = lambda fn, *a, **kw: fn(tx, *a, **kw)
    driver = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    return driver, session, tx


def _cyphers(tx):
    return [call[0][0] for call in tx.run.call_args_list]


def _params_of(tx, needle):
    for call in tx.run.call_args_list:
        if needle in call[0][0]:
            return call[0][1]
    raise AssertionError(f"no tx.run call containing {needle!r}")


class TestDeactivateFact:
    def test_requires_approved_by(self):
        with pytest.raises(ValueError):
            deactivate_fact("NgAction", {"action": "x"}, client_name="テスト太郎", approved_by="")

    def test_rejects_labels_outside_fact_labels(self):
        with pytest.raises(ValueError):
            deactivate_fact("Condition", {"name": "x"}, client_name="テスト太郎", approved_by="管理者")

    def test_sets_inactive_and_valid_to_in_one_transaction(self):
        driver, session, tx = _make_tx_driver()
        with patch("app.lib.db_operations.get_driver", return_value=driver):
            result = deactivate_fact(
                "NgAction", {"action": "x"}, client_name="テスト太郎",
                approved_by="管理者", valid_to="2026-01-15", reason="母親より解除を聴取",
            )
        assert result["status"] == "success"
        assert session.execute_write.call_count == 1
        params = _params_of(tx, "SET n.status = 'Inactive'")
        assert params["valid_to"] == date(2026, 1, 15)

    def test_valid_to_defaults_to_today(self):
        driver, _, tx = _make_tx_driver()
        with patch("app.lib.db_operations.get_driver", return_value=driver):
            deactivate_fact("CarePreference", {"category": "a", "instruction": "b"},
                            client_name="テスト太郎", approved_by="管理者")
        params = _params_of(tx, "SET n.status = 'Inactive'")
        assert params["valid_to"] == date.today()

    def test_audit_log_is_written_in_the_same_transaction(self):
        driver, _, tx = _make_tx_driver()
        with patch("app.lib.db_operations.get_driver", return_value=driver):
            deactivate_fact("NgAction", {"action": "x"}, client_name="テスト太郎",
                            approved_by="管理者", reason="解除")
        params = _params_of(tx, "CREATE (a:AuditLog")
        assert params["action"] == "deactivate"
        assert params["user_name"] == "管理者"
        assert "validTo" in params["details"]

    def test_missing_fact_is_reported_not_silently_ignored(self):
        driver, _, tx = _make_tx_driver()
        tx.run.return_value.single.return_value = None
        with patch("app.lib.db_operations.get_driver", return_value=driver):
            result = deactivate_fact("NgAction", {"action": "無い"}, client_name="テスト太郎",
                                     approved_by="管理者")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# (d) キーパーソン交代: 旧リレーションは残し endDate + Inactive、新規を CREATE
# ---------------------------------------------------------------------------

class TestReplaceKeyPerson:
    def test_old_relationship_is_closed_not_deleted(self):
        driver, session, tx = _make_tx_driver()
        with patch("app.lib.db_operations.get_driver", return_value=driver):
            result = replace_key_person(
                client_name="テスト太郎", old_name="テスト花子", new_name="テスト次郎",
                rank=1, changed_on="2026-08-31", user_name="管理者",
            )
        assert result["status"] == "success"
        assert session.execute_write.call_count == 1
        for cypher in _cyphers(tx):
            assert "DELETE" not in cypher.upper()
        params = _params_of(tx, "SET old.endDate = $end_date, old.status = 'Inactive'")
        assert params["end_date"] == date(2026, 8, 31)

    def test_new_relationship_starts_on_change_date_as_active(self):
        driver, _, tx = _make_tx_driver()
        with patch("app.lib.db_operations.get_driver", return_value=driver):
            replace_key_person("テスト太郎", "テスト花子", "テスト次郎", rank=1,
                               changed_on="2026-08-31", user_name="管理者")
        params = _params_of(tx, "CREATE (c)-[:HAS_KEY_PERSON")
        assert params["start_date"] == date(2026, 8, 31)
        assert params["rank"] == 1

    def test_change_date_defaults_to_today(self):
        driver, _, tx = _make_tx_driver()
        with patch("app.lib.db_operations.get_driver", return_value=driver):
            replace_key_person("テスト太郎", "テスト花子", "テスト次郎", rank=1, user_name="管理者")
        params = _params_of(tx, "SET old.endDate = $end_date, old.status = 'Inactive'")
        assert params["end_date"] == date.today()

    def test_audit_log_is_written(self):
        driver, _, tx = _make_tx_driver()
        with patch("app.lib.db_operations.get_driver", return_value=driver):
            replace_key_person("テスト太郎", "テスト花子", "テスト次郎", rank=1, user_name="管理者")
        params = _params_of(tx, "CREATE (a:AuditLog")
        assert params["action"] == "replace_key_person"
