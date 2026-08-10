"""Tests for narrative_intake_service.validate_graph (allowlist 二重検証).

DRIFT-13 の再発防止: 証拠・鮮度モデルの CONFIRMS / CONTRADICTS が
正規の書き込み経路 (POST /api/narrative/intake) で reject されないこと。
DB もモックも不要 — validate_graph は純粋な検証ロジック。
"""

from app.schemas.narrative_intake import (
    NarrativeAuditContext,
    NarrativeIntakeRequest,
    NarrativeNode,
    NarrativeRelationship,
)
from app.services.narrative_intake_service import validate_graph


def _audit_context() -> NarrativeAuditContext:
    return NarrativeAuditContext(
        user="テスト支援員",
        sessionId="test-session",
        sourceType="narrative",
        sourceHash="0" * 64,
        clientName="田中太郎",
    )


class TestEvidenceFreshnessRelationships:
    def test_confirms_relationship_passes_validation(self):
        """Review → 既存事実 の CONFIRMS が rejected にならない (BRS-13)。"""
        req = NarrativeIntakeRequest(
            nodes=[
                NarrativeNode(
                    temp_id="rv1",
                    label="Review",
                    properties={"reviewedAt": "2026-08-10", "reviewedBy": "テスト支援員"},
                ),
                NarrativeNode(
                    temp_id="ng1",
                    label="NgAction",
                    properties={"action": "大声を出す", "reason": "パニック誘発", "riskLevel": "Panic"},
                ),
            ],
            relationships=[
                NarrativeRelationship(
                    source_temp_id="rv1", target_temp_id="ng1", type="CONFIRMS",
                ),
            ],
            auditContext=_audit_context(),
            dryRun=True,
        )

        validated, rejected = validate_graph(req)

        assert rejected["nodes"] == []
        assert rejected["relationships"] == []
        assert len(validated["relationships"]) == 1
        assert validated["relationships"][0].type == "CONFIRMS"

    def test_contradicts_relationship_passes_with_properties(self):
        """CONTRADICTS がプロパティ (claim / raisedAt / source) ごと通る (BRS-13)。"""
        props = {
            "claim": "最近は大声でもパニックにならない",
            "raisedAt": "2026-08-10",
            "source": "面談記録",
        }
        req = NarrativeIntakeRequest(
            nodes=[
                NarrativeNode(
                    temp_id="mt1",
                    label="MeetingRecord",
                    properties={"date": "2026-08-10", "summary": "定期面談"},
                ),
                NarrativeNode(
                    temp_id="ng1",
                    label="NgAction",
                    properties={"action": "大声を出す", "reason": "パニック誘発", "riskLevel": "Panic"},
                ),
            ],
            relationships=[
                NarrativeRelationship(
                    source_temp_id="mt1", target_temp_id="ng1",
                    type="CONTRADICTS", properties=props,
                ),
            ],
            auditContext=_audit_context(),
            dryRun=True,
        )

        validated, rejected = validate_graph(req)

        assert rejected["relationships"] == []
        assert validated["relationships"][0].properties == props
