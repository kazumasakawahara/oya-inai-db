"""POST /api/graph/validate の事実時間軸ルール（Track A Phase 2）。DB に触れない。"""


def _payload(nodes=None, relationships=None):
    return {"nodes": nodes or [], "relationships": relationships or []}


def _client_node(temp_id="c1", name="テスト太郎"):
    return {"temp_id": temp_id, "label": "Client",
            "mergeKey": {"name": name}, "properties": {"name": name}}


def _ng(props):
    return {"temp_id": "ng1", "label": "NgAction",
            "mergeKey": {"action": props["action"]}, "properties": props}


class TestValidTimeReject:
    def test_inactive_without_valid_to_is_rejected(self, client):
        data = client.post("/api/graph/validate", json=_payload(
            nodes=[_ng({"action": "大声", "status": "Inactive"})])).json()
        assert data["accepted"]["nodes"] == []
        assert any("validTo" in r["reason"] for r in data["rejected"])

    def test_active_with_valid_to_is_rejected(self, client):
        data = client.post("/api/graph/validate", json=_payload(
            nodes=[_ng({"action": "大声", "status": "Active", "validTo": "2026-01-01"})])).json()
        assert data["accepted"]["nodes"] == []
        assert any("validTo" in r["reason"] for r in data["rejected"])

    def test_valid_from_after_valid_to_is_rejected(self, client):
        data = client.post("/api/graph/validate", json=_payload(
            nodes=[_ng({"action": "大声", "status": "Inactive",
                        "validFrom": "2026-05-01", "validTo": "2026-01-01"})])).json()
        assert any("validFrom" in r["reason"] for r in data["rejected"])

    def test_key_person_status_outside_two_values_is_rejected(self, client):
        data = client.post("/api/graph/validate", json=_payload(
            nodes=[_client_node(),
                   {"temp_id": "kp1", "label": "KeyPerson",
                    "mergeKey": {"name": "テスト花子"}, "properties": {"name": "テスト花子"}}],
            relationships=[{"source_temp_id": "c1", "target_temp_id": "kp1",
                            "type": "HAS_KEY_PERSON", "properties": {"rank": 1, "status": "Ended"}}],
        )).json()
        assert data["accepted"]["relationships"] == []
        assert any("status" in r["reason"] for r in data["rejected"])


class TestValidTimeAccept:
    def test_inactive_with_valid_to_is_accepted(self, client):
        data = client.post("/api/graph/validate", json=_payload(
            nodes=[_ng({"action": "大声", "status": "Inactive", "validTo": "2026-01-01"})])).json()
        assert data["rejected"] == []

    def test_missing_required_properties_is_a_warning_not_rejection(self, client):
        data = client.post("/api/graph/validate", json=_payload(
            nodes=[_ng({"action": "大声"})])).json()
        assert data["rejected"] == []
        assert any("registeredAt" in w for w in data["warnings"])

    def test_registered_at_is_not_injected_by_validate(self, client):
        """既定値は書き込み経路の ON CREATE で付与する。validate が補うと MCP 経由の
        MERGE で既存ノードの registeredAt を上書きしてしまう。"""
        data = client.post("/api/graph/validate", json=_payload(
            nodes=[_ng({"action": "大声"})])).json()
        assert "registeredAt" not in data["accepted"]["nodes"][0]["properties"]
