"""Guardian（lib/schema_validator.py）の事実時間軸ルール（Track A Phase 2 / v3.5・v1.8）。

DRIFT-12 と同じ様式で「正典の規則が実装に固定されていること」をここで守る。
DB には触れない。
"""

from datetime import date

import pytest

from app.lib.guardian import guardian as sv


# ---------------------------------------------------------------------------
# 正典との対応（machine-check v1.8）— 値そのものを固定する
# ---------------------------------------------------------------------------

class TestCanonConstants:
    def test_registered_at_is_immutable_on_fact_labels(self):
        for label in ("NgAction", "CarePreference"):
            assert set(sv.IMMUTABLE_PROPERTIES[label]) == {"registeredAt"}

    def test_registered_at_is_required_on_fact_labels(self):
        for label in ("NgAction", "CarePreference"):
            assert "registeredAt" in sv.REQUIRED_PROPERTIES[label]
            # Phase 1 の必須（v1.6）も同じ定数に載る
            assert {"source", "status", "lastConfirmedAt"} <= set(sv.REQUIRED_PROPERTIES[label])

    def test_has_key_person_status_is_two_valued(self):
        assert set(sv.RELATIONSHIP_PROPERTIES["HAS_KEY_PERSON"]["status"]) == {"Active", "Inactive"}


# ---------------------------------------------------------------------------
# (a) registeredAt は更新で変わらない
# ---------------------------------------------------------------------------

class TestImmutableProperties:
    def test_update_discards_registered_at_with_warning(self):
        props, warnings = sv.strip_immutable_properties(
            "NgAction", {"action": "大声", "registeredAt": "2020-01-01"}
        )
        assert "registeredAt" not in props
        assert props == {"action": "大声"}
        assert any("registeredAt" in w for w in warnings)

    def test_update_without_immutable_is_untouched(self):
        props, warnings = sv.strip_immutable_properties("NgAction", {"action": "大声"})
        assert props == {"action": "大声"}
        assert warnings == []

    def test_other_labels_are_untouched(self):
        props, warnings = sv.strip_immutable_properties(
            "Condition", {"name": "x", "registeredAt": "2020-01-01"}
        )
        assert props == {"name": "x", "registeredAt": "2020-01-01"}
        assert warnings == []


class TestFactTimeDefaults:
    def test_create_fills_registered_at_with_today(self):
        props = sv.apply_fact_time_defaults(
            "CarePreference", {"category": "食事", "instruction": "x"}, today=date(2026, 9, 3)
        )
        assert props["registeredAt"] == date(2026, 9, 3)

    def test_create_keeps_explicit_registered_at(self):
        props = sv.apply_fact_time_defaults(
            "NgAction", {"action": "x", "registeredAt": "2025-04-01"}, today=date(2026, 9, 3)
        )
        assert props["registeredAt"] == date(2025, 4, 1)

    def test_other_labels_get_no_registered_at(self):
        props = sv.apply_fact_time_defaults("Condition", {"name": "x"}, today=date(2026, 9, 3))
        assert "registeredAt" not in props


# ---------------------------------------------------------------------------
# (b)(c) validTo と status の連動、validFrom <= validTo
# ---------------------------------------------------------------------------

class TestValidateFactTime:
    def test_inactive_without_valid_to_is_rejected(self):
        errors = sv.validate_fact_time("NgAction", {"action": "x", "status": "Inactive"})
        assert any("validTo" in e for e in errors)

    def test_active_with_valid_to_is_rejected(self):
        errors = sv.validate_fact_time(
            "NgAction", {"action": "x", "status": "Active", "validTo": "2026-01-01"}
        )
        assert any("validTo" in e for e in errors)

    def test_pending_with_valid_to_is_rejected(self):
        errors = sv.validate_fact_time(
            "CarePreference", {"status": "Pending", "validTo": "2026-01-01"}
        )
        assert any("validTo" in e for e in errors)

    def test_inactive_with_valid_to_is_accepted(self):
        errors = sv.validate_fact_time(
            "NgAction", {"action": "x", "status": "Inactive", "validTo": "2026-01-01"}
        )
        assert errors == []

    def test_valid_from_after_valid_to_is_rejected(self):
        errors = sv.validate_fact_time(
            "NgAction", {"status": "Inactive", "validFrom": "2026-05-01", "validTo": "2026-01-01"}
        )
        assert any("validFrom" in e for e in errors)

    def test_valid_from_before_valid_to_is_accepted(self):
        errors = sv.validate_fact_time(
            "NgAction", {"status": "Inactive", "validFrom": "2025-05-01", "validTo": "2026-01-01"}
        )
        assert errors == []

    def test_status_outside_restricted_three_values_is_rejected(self):
        errors = sv.validate_fact_time("NgAction", {"status": "Completed"})
        assert any("status" in e for e in errors)

    def test_malformed_date_is_rejected(self):
        errors = sv.validate_fact_time("NgAction", {"status": "Active", "validFrom": "去年の春"})
        assert any("validFrom" in e for e in errors)

    def test_non_fact_label_is_not_checked(self):
        assert sv.validate_fact_time("Condition", {"status": "Monitoring"}) == []

    def test_public_assistance_end_date_type_only(self):
        assert sv.validate_fact_time("PublicAssistance", {"endDate": "2026-03-31"}) == []
        errors = sv.validate_fact_time("PublicAssistance", {"endDate": "年度末"})
        assert any("endDate" in e for e in errors)


# ---------------------------------------------------------------------------
# HAS_KEY_PERSON のプロパティ規則
# ---------------------------------------------------------------------------

class TestRelationshipProperties:
    def test_status_outside_two_values_is_rejected(self):
        errors, _ = sv.validate_relationship_properties(
            "HAS_KEY_PERSON", {"rank": 1, "startDate": "2026-01-01", "status": "Ended"}
        )
        assert any("status" in e for e in errors)

    def test_inactive_without_end_date_is_rejected(self):
        errors, _ = sv.validate_relationship_properties(
            "HAS_KEY_PERSON", {"rank": 1, "startDate": "2026-01-01", "status": "Inactive"}
        )
        assert any("endDate" in e for e in errors)

    def test_inactive_with_end_date_is_accepted(self):
        errors, _ = sv.validate_relationship_properties(
            "HAS_KEY_PERSON",
            {"rank": 1, "startDate": "2026-01-01", "status": "Inactive", "endDate": "2026-08-31"},
        )
        assert errors == []

    def test_missing_required_is_warning_not_error(self):
        errors, warnings = sv.validate_relationship_properties("HAS_KEY_PERSON", {"rank": 1})
        assert errors == []
        assert any("startDate" in w for w in warnings)

    def test_unlisted_relationship_is_not_checked(self):
        assert sv.validate_relationship_properties("MUST_AVOID", {}) == ([], [])

    def test_create_defaults_start_date_and_status(self):
        props = sv.apply_relationship_defaults("HAS_KEY_PERSON", {"rank": 1}, today=date(2026, 9, 3))
        assert props["startDate"] == date(2026, 9, 3)
        assert props["status"] == "Active"

    def test_create_defaults_keep_explicit_values(self):
        props = sv.apply_relationship_defaults(
            "HAS_KEY_PERSON",
            {"rank": 2, "startDate": "2024-04-01", "status": "Inactive", "endDate": "2025-03-31"},
            today=date(2026, 9, 3),
        )
        assert props["startDate"] == date(2024, 4, 1)
        assert props["status"] == "Inactive"
        assert props["endDate"] == date(2025, 3, 31)

    def test_defaults_do_not_touch_other_relationships(self):
        assert sv.apply_relationship_defaults("MUST_AVOID", {}, today=date(2026, 9, 3)) == {}


# ---------------------------------------------------------------------------
# validate_and_normalize_graph への組み込み（警告として出る）
# ---------------------------------------------------------------------------

class TestGraphIntegration:
    def test_inactive_fact_without_valid_to_warns(self):
        _, warnings = sv.validate_and_normalize_graph({
            "nodes": [{"label": "NgAction", "properties": {"action": "x", "status": "Inactive"}}],
            "relationships": [],
        })
        assert any("validTo" in w for w in warnings)

    def test_has_key_person_bad_status_warns(self):
        _, warnings = sv.validate_and_normalize_graph({
            "nodes": [],
            "relationships": [{"type": "HAS_KEY_PERSON", "properties": {"status": "Ended"}}],
        })
        assert any("status" in w for w in warnings)
