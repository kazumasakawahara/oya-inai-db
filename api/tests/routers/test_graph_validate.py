"""Tests for POST /api/graph/validate (Guardian-backed, no DB access)."""


def _payload(nodes=None, relationships=None):
    return {"nodes": nodes or [], "relationships": relationships or []}


def _client_node(temp_id="c1", name="テスト太郎"):
    return {
        "temp_id": temp_id,
        "label": "Client",
        "mergeKey": {"name": name},
        "properties": {"name": name},
    }


class TestGraphValidateAccept:
    def test_valid_graph_is_accepted(self, client):
        response = client.post("/api/graph/validate", json=_payload(
            nodes=[
                _client_node(),
                {
                    "temp_id": "ng1",
                    "label": "NgAction",
                    "mergeKey": {"action": "大きな音を立てる"},
                    "properties": {
                        "action": "大きな音を立てる",
                        "reason": "パニック誘発",
                        "riskLevel": "Panic",
                    },
                },
            ],
            relationships=[
                {"source_temp_id": "c1", "target_temp_id": "ng1",
                 "type": "MUST_AVOID", "properties": {}},
            ],
        ))
        assert response.status_code == 200
        data = response.json()
        assert data["rejected"] == []
        assert len(data["accepted"]["nodes"]) == 2
        assert len(data["accepted"]["relationships"]) == 1

    def test_snake_case_property_is_normalized_with_warning(self, client):
        response = client.post("/api/graph/validate", json=_payload(
            nodes=[{
                "temp_id": "ng1",
                "label": "NgAction",
                "mergeKey": {"action": "体に触る"},
                "properties": {"action": "体に触る", "risk_level": "Panic"},
            }],
        ))
        data = response.json()
        assert data["rejected"] == []
        props = data["accepted"]["nodes"][0]["properties"]
        assert "riskLevel" in props and "risk_level" not in props
        assert any("risk_level" in w for w in data["warnings"])

    def test_deprecated_relationship_is_corrected_with_warning(self, client):
        response = client.post("/api/graph/validate", json=_payload(
            nodes=[
                _client_node(),
                {"temp_id": "kp1", "label": "KeyPerson",
                 "mergeKey": {"name": "テスト花子"},
                 "properties": {"name": "テスト花子"}},
            ],
            relationships=[
                {"source_temp_id": "c1", "target_temp_id": "kp1",
                 "type": "EMERGENCY_CONTACT", "properties": {}},
            ],
        ))
        data = response.json()
        assert data["rejected"] == []
        assert data["accepted"]["relationships"][0]["type"] == "HAS_KEY_PERSON"
        assert any("EMERGENCY_CONTACT" in w for w in data["warnings"])

    def test_risk_level_alias_is_corrected(self, client):
        response = client.post("/api/graph/validate", json=_payload(
            nodes=[{
                "temp_id": "ng1",
                "label": "NgAction",
                "mergeKey": {"action": "後ろから声をかける"},
                "properties": {"action": "後ろから声をかける", "riskLevel": "High"},
            }],
        ))
        data = response.json()
        assert data["rejected"] == []
        assert data["accepted"]["nodes"][0]["properties"]["riskLevel"] == "LifeThreatening"


class TestGraphValidateReject:
    def test_unknown_label_is_rejected(self, client):
        response = client.post("/api/graph/validate", json=_payload(
            nodes=[{"temp_id": "x1", "label": "Sibling",
                    "properties": {"name": "誰か"}}],
        ))
        data = response.json()
        assert data["accepted"]["nodes"] == []
        assert len(data["rejected"]) == 1
        assert "x1" in data["rejected"][0]["path"]
        assert "Sibling" in data["rejected"][0]["reason"]

    def test_invalid_enum_value_is_rejected(self, client):
        response = client.post("/api/graph/validate", json=_payload(
            nodes=[{
                "temp_id": "ng1",
                "label": "NgAction",
                "mergeKey": {"action": "急かす"},
                "properties": {"action": "急かす", "riskLevel": "Dangerous"},
            }],
        ))
        data = response.json()
        assert data["accepted"]["nodes"] == []
        assert any("riskLevel" in r["reason"] for r in data["rejected"])

    def test_missing_merge_key_value_is_rejected(self, client):
        response = client.post("/api/graph/validate", json=_payload(
            nodes=[{
                "temp_id": "ng1",
                "label": "NgAction",
                "mergeKey": {"action": "触る"},
                "properties": {"reason": "理由のみでキー値なし"},
            }],
        ))
        data = response.json()
        assert data["accepted"]["nodes"] == []
        assert any("action" in r["reason"] for r in data["rejected"])

    def test_unknown_relationship_type_is_rejected(self, client):
        response = client.post("/api/graph/validate", json=_payload(
            nodes=[_client_node(), _client_node("c2", "テスト次郎")],
            relationships=[
                {"source_temp_id": "c1", "target_temp_id": "c2",
                 "type": "KNOWS", "properties": {}},
            ],
        ))
        data = response.json()
        assert data["accepted"]["relationships"] == []
        assert any("KNOWS" in r["reason"] for r in data["rejected"])

    def test_relationship_to_rejected_node_is_rejected(self, client):
        response = client.post("/api/graph/validate", json=_payload(
            nodes=[
                _client_node(),
                {"temp_id": "x1", "label": "Sibling", "properties": {}},
            ],
            relationships=[
                {"source_temp_id": "c1", "target_temp_id": "x1",
                 "type": "FAMILY_OF", "properties": {}},
            ],
        ))
        data = response.json()
        assert data["accepted"]["relationships"] == []
        assert any("x1" in r["reason"] for r in data["rejected"])

    def test_duplicate_temp_id_is_rejected(self, client):
        response = client.post("/api/graph/validate", json=_payload(
            nodes=[_client_node("c1"), _client_node("c1", "テスト次郎")],
        ))
        data = response.json()
        assert len(data["accepted"]["nodes"]) == 1
        assert any("temp_id" in r["reason"] for r in data["rejected"])


class TestGraphValidateContract:
    def test_does_not_touch_database(self, client, mock_db):
        client.post("/api/graph/validate", json=_payload(nodes=[_client_node()]))
        mock_db.assert_not_called()

    def test_audit_context_is_accepted_and_ignored(self, client):
        response = client.post("/api/graph/validate", json={
            **_payload(nodes=[_client_node()]),
            "auditContext": {"user": "検証者", "sessionId": "s1"},
        })
        assert response.status_code == 200
