"""Comprehensive tests for /api/narratives endpoints.

Mocks Gemini extraction and Neo4j operations.
"""

import json
from unittest.mock import patch, AsyncMock, MagicMock


class TestExtract:
    """POST /api/narratives/extract"""

    def test_extract_success(self, client):
        mock_result = {
            "nodes": [
                {"temp_id": "c1", "label": "Client", "properties": {"name": "田中太郎"}},
                {"temp_id": "ng1", "label": "NgAction", "properties": {"action": "大声", "reason": "パニック", "riskLevel": "Panic"}},
            ],
            "relationships": [
                {"source_temp_id": "c1", "target_temp_id": "ng1", "type": "MUST_AVOID", "properties": {}},
            ],
        }
        with patch("app.routers.narratives.extract_from_text", new_callable=AsyncMock, return_value=mock_result):
            resp = client.post("/api/narratives/extract", json={
                "text": "田中太郎さんは大声を出すとパニックになります。",
                "client_name": "田中太郎",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 2
        assert data["nodes"][0]["label"] == "Client"

    def test_extract_failure_returns_422(self, client):
        """When Gemini extraction returns None, API returns 422 with error message."""
        with patch("app.routers.narratives.extract_from_text", new_callable=AsyncMock, return_value=None):
            resp = client.post("/api/narratives/extract", json={
                "text": "解析不能テキスト",
                "client_name": None,
            })

        assert resp.status_code == 422
        assert "抽出に失敗" in resp.json()["detail"]

    def test_extract_without_client_name(self, client):
        mock_result = {
            "nodes": [{"temp_id": "c1", "label": "Client", "properties": {"name": "不明"}}],
            "relationships": [],
        }
        with patch("app.routers.narratives.extract_from_text", new_callable=AsyncMock, return_value=mock_result):
            resp = client.post("/api/narratives/extract", json={
                "text": "テストテキスト",
            })

        assert resp.status_code == 200

    def test_extract_missing_text_field(self, client):
        """Missing text field should cause validation error."""
        resp = client.post("/api/narratives/extract", json={})
        assert resp.status_code == 422

    def test_extract_server_error(self, client):
        """Unexpected exception returns 500."""
        with patch("app.routers.narratives.extract_from_text", new_callable=AsyncMock, side_effect=RuntimeError("unexpected")):
            resp = client.post("/api/narratives/extract", json={
                "text": "テスト",
            })

        assert resp.status_code == 500


class TestValidate:
    """POST /api/narratives/validate"""

    def test_validate_valid_graph(self, client):
        graph = {
            "nodes": [
                {"temp_id": "c1", "label": "Client", "properties": {"name": "テスト太郎"}},
                {"temp_id": "ng1", "label": "NgAction", "properties": {"action": "走る"}},
            ],
            "relationships": [
                {"source_temp_id": "c1", "target_temp_id": "ng1", "type": "MUST_AVOID", "properties": {}},
            ],
        }
        resp = client.post("/api/narratives/validate", json=graph)

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is True
        assert data["errors"] == []

    def test_validate_invalid_label(self, client):
        graph = {
            "nodes": [{"temp_id": "x1", "label": "FakeLabel", "properties": {"name": "test"}}],
            "relationships": [],
        }
        resp = client.post("/api/narratives/validate", json=graph)

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is False
        assert any("FakeLabel" in e for e in data["errors"])

    def test_validate_invalid_rel_type(self, client):
        graph = {
            "nodes": [
                {"temp_id": "c1", "label": "Client", "properties": {"name": "テスト"}},
                {"temp_id": "n1", "label": "NgAction", "properties": {"action": "テスト"}},
            ],
            "relationships": [
                {"source_temp_id": "c1", "target_temp_id": "n1", "type": "FAKE_REL", "properties": {}},
            ],
        }
        resp = client.post("/api/narratives/validate", json=graph)

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is False
        assert any("FAKE_REL" in e for e in data["errors"])

    def test_validate_missing_merge_key(self, client):
        """Client without 'name' property should be invalid."""
        graph = {
            "nodes": [{"temp_id": "c1", "label": "Client", "properties": {"dob": "2000-01-01"}}],
            "relationships": [],
        }
        resp = client.post("/api/narratives/validate", json=graph)

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is False
        assert any("name" in e for e in data["errors"])

    def test_validate_missing_source_temp_id(self, client):
        """Relationship referencing non-existent source generates warning."""
        graph = {
            "nodes": [{"temp_id": "c1", "label": "Client", "properties": {"name": "テスト"}}],
            "relationships": [
                {"source_temp_id": "unknown", "target_temp_id": "c1", "type": "MUST_AVOID", "properties": {}},
            ],
        }
        resp = client.post("/api/narratives/validate", json=graph)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["warnings"]) >= 1
        assert any("unknown" in w for w in data["warnings"])

    def test_validate_empty_graph(self, client):
        graph = {"nodes": [], "relationships": []}
        resp = client.post("/api/narratives/validate", json=graph)

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is True


class TestRegister:
    """POST /api/narratives/register"""

    def test_register_success(self, client):
        mock_result = {
            "status": "success",
            "client_name": "田中太郎",
            "registered_count": 2,
            "registered_types": ["Client", "NgAction"],
        }
        with patch("app.routers.narratives.register_to_database", return_value=mock_result), \
             patch("app.routers.narratives.find_semantic_duplicates", new_callable=AsyncMock, return_value=[]):
            graph = {
                "nodes": [
                    {"temp_id": "c1", "label": "Client", "properties": {"name": "田中太郎"}},
                ],
                "relationships": [],
            }
            resp = client.post("/api/narratives/register", json=graph)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["client_name"] == "田中太郎"
        assert data["registered_count"] == 2

    def test_register_returns_empty_semantic_duplicates_by_default(self, client):
        """Register endpoint always returns semanticDuplicates field (empty list when no dups)."""
        mock_result = {
            "status": "success",
            "client_name": "佐藤花子",
            "registered_count": 1,
            "registered_types": ["Client"],
        }
        with patch("app.routers.narratives.register_to_database", return_value=mock_result), \
             patch("app.routers.narratives.find_semantic_duplicates", new_callable=AsyncMock, return_value=[]):
            graph = {
                "nodes": [
                    {"temp_id": "c1", "label": "Client", "properties": {"name": "佐藤花子"}},
                ],
                "relationships": [],
            }
            resp = client.post("/api/narratives/register", json=graph)

        assert resp.status_code == 200
        data = resp.json()
        assert "semanticDuplicates" in data
        assert data["semanticDuplicates"] == []

    def test_register_returns_semantic_duplicate_warnings_for_care_preference(self, client):
        """When semantically similar CarePreference exists, warnings are included (non-blocking)."""
        mock_result = {
            "status": "success",
            "client_name": "田中太郎",
            "registered_count": 2,
            "registered_types": ["Client", "CarePreference"],
        }
        mock_candidates = [
            {"text": "静かな環境を好む", "score": 0.92, "nodeId": "4:abc123:0"},
        ]
        with patch("app.routers.narratives.register_to_database", return_value=mock_result), \
             patch("app.routers.narratives.find_semantic_duplicates", new_callable=AsyncMock, return_value=mock_candidates):
            graph = {
                "nodes": [
                    {"temp_id": "c1", "label": "Client", "properties": {"name": "田中太郎"}},
                    {"temp_id": "cp1", "label": "CarePreference", "properties": {"instruction": "静かな場所が好き"}},
                ],
                "relationships": [],
            }
            resp = client.post("/api/narratives/register", json=graph)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["semanticDuplicates"]) == 1
        dup = data["semanticDuplicates"][0]
        assert dup["label"] == "CarePreference"
        assert dup["new_text"] == "静かな場所が好き"
        assert dup["existing_text"] == "静かな環境を好む"
        assert dup["similarity_score"] == 0.92
        assert dup["node_id"] == "4:abc123:0"

    def test_register_ngaction_confirmed_returns_warnings(self, client):
        """When NgAction duplicate is confirmed (confirmDuplicates=true), warnings in response."""
        mock_result = {
            "status": "success",
            "client_name": "田中太郎",
            "registered_count": 2,
            "registered_types": ["Client", "NgAction"],
        }
        mock_candidates = [
            {"text": "大声を出す", "score": 0.92, "nodeId": "4:abc123:0"},
        ]
        with patch("app.routers.narratives.register_to_database", return_value=mock_result), \
             patch("app.routers.narratives.find_semantic_duplicates", new_callable=AsyncMock, return_value=mock_candidates):
            graph = {
                "nodes": [
                    {"temp_id": "c1", "label": "Client", "properties": {"name": "田中太郎"}},
                    {"temp_id": "ng1", "label": "NgAction", "properties": {"action": "大声で叫ぶ", "riskLevel": "Panic"}},
                ],
                "relationships": [],
                "confirmDuplicates": True,
            }
            resp = client.post("/api/narratives/register", json=graph)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["semanticDuplicates"]) == 1
        dup = data["semanticDuplicates"][0]
        assert dup["label"] == "NgAction"
        assert dup["new_text"] == "大声で叫ぶ"
        assert dup["existing_text"] == "大声を出す"
        assert dup["similarity_score"] == 0.92
        assert dup["node_id"] == "4:abc123:0"

    def test_register_semantic_dedup_failure_does_not_break_registration(self, client):
        """If semantic dedup raises an exception, registration still succeeds (best effort)."""
        mock_result = {
            "status": "success",
            "client_name": "田中太郎",
            "registered_count": 2,
            "registered_types": ["Client", "NgAction"],
        }
        with patch("app.routers.narratives.register_to_database", return_value=mock_result), \
             patch("app.routers.narratives.find_semantic_duplicates", new_callable=AsyncMock, side_effect=RuntimeError("embedding service unavailable")):
            graph = {
                "nodes": [
                    {"temp_id": "c1", "label": "Client", "properties": {"name": "田中太郎"}},
                    {"temp_id": "ng1", "label": "NgAction", "properties": {"action": "大声", "riskLevel": "Panic"}},
                ],
                "relationships": [],
            }
            resp = client.post("/api/narratives/register", json=graph)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        # semanticDuplicates is empty because the check failed silently
        assert data["semanticDuplicates"] == []

    def test_register_db_error_returns_422(self, client):
        """When register_to_database returns error status, API returns 422."""
        mock_result = {
            "status": "error",
            "client_name": None,
            "registered_count": 0,
            "registered_types": [],
            "error": "Connection refused",
        }
        with patch("app.routers.narratives.register_to_database", return_value=mock_result):
            graph = {
                "nodes": [
                    {"temp_id": "c1", "label": "Client", "properties": {"name": "テスト"}},
                ],
                "relationships": [],
            }
            resp = client.post("/api/narratives/register", json=graph)

        assert resp.status_code == 422
        assert "Connection refused" in resp.json()["detail"]

    def test_register_server_error(self, client):
        """Unexpected exception returns 500."""
        with patch("app.routers.narratives.register_to_database", side_effect=RuntimeError("unexpected")):
            graph = {
                "nodes": [
                    {"temp_id": "c1", "label": "Client", "properties": {"name": "テスト"}},
                ],
                "relationships": [],
            }
            resp = client.post("/api/narratives/register", json=graph)

        assert resp.status_code == 500


class TestUploadFile:
    """POST /api/narratives/upload"""

    def test_upload_text_file(self, client):
        content = "田中太郎さんの支援記録です。".encode("utf-8")
        with patch("app.routers.narratives.read_file", return_value="田中太郎さんの支援記録です。"):
            resp = client.post(
                "/api/narratives/upload",
                files={"file": ("test.txt", content, "text/plain")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "test.txt"
        assert "田中太郎" in data["text"]

    def test_upload_unsupported_extension(self, client):
        """Unsupported file extensions are rejected with 400."""
        resp = client.post(
            "/api/narratives/upload",
            files={"file": ("test.jpg", b"fake image", "image/jpeg")},
        )
        assert resp.status_code == 400
        assert "未対応" in resp.json()["detail"]


class TestRegisterNgActionBlocking:
    """POST /api/narratives/register — NgAction semantic duplicate blocking"""

    def test_ngaction_duplicate_returns_409(self, client):
        """When semantic duplicate found for NgAction, returns 409."""
        mock_candidates = [{"text": "大きな音", "score": 0.92, "nodeId": "4:abc:1"}]
        with patch("app.routers.narratives.find_semantic_duplicates", new_callable=AsyncMock, return_value=mock_candidates):
            response = client.post("/api/narratives/register", json={
                "nodes": [{"temp_id": "ng1", "label": "NgAction", "properties": {"action": "騒音"}}],
                "relationships": [],
            })
        assert response.status_code == 409
        data = response.json()["detail"]
        assert data["status"] == "duplicate_confirmation_required"
        assert len(data["duplicates"]) == 1
        assert data["duplicates"][0]["label"] == "NgAction"
        assert data["duplicates"][0]["new_text"] == "騒音"
        assert data["duplicates"][0]["existing_text"] == "大きな音"
        assert data["duplicates"][0]["similarity_score"] == 0.92

    def test_ngaction_duplicate_with_confirm_proceeds(self, client):
        """When confirmDuplicates=true, proceeds despite duplicates."""
        mock_result = {
            "status": "success",
            "registered_count": 1,
            "registered_types": ["NgAction"],
            "client_name": None,
        }
        with patch("app.routers.narratives.find_semantic_duplicates", new_callable=AsyncMock, return_value=[]), \
             patch("app.routers.narratives.register_to_database", return_value=mock_result):
            response = client.post("/api/narratives/register", json={
                "nodes": [{"temp_id": "ng1", "label": "NgAction", "properties": {"action": "騒音"}}],
                "relationships": [],
                "confirmDuplicates": True,
            })
        assert response.status_code == 200

    def test_no_ngaction_no_blocking(self, client):
        """When no NgAction in graph, no blocking check happens."""
        mock_result = {
            "status": "success",
            "registered_count": 1,
            "registered_types": ["Client"],
            "client_name": "テスト",
        }
        with patch("app.routers.narratives.register_to_database", return_value=mock_result), \
             patch("app.routers.narratives.find_semantic_duplicates", new_callable=AsyncMock, return_value=[]):
            response = client.post("/api/narratives/register", json={
                "nodes": [{"temp_id": "c1", "label": "Client", "properties": {"name": "テスト"}}],
                "relationships": [],
            })
        assert response.status_code == 200

    def test_ngaction_exact_text_match_not_blocked(self, client):
        """Exact text match (same action text) is not blocked — MERGE handles it."""
        mock_candidates = [{"text": "騒音", "score": 1.0, "nodeId": "4:abc:1"}]
        mock_result = {
            "status": "success",
            "registered_count": 1,
            "registered_types": ["NgAction"],
            "client_name": None,
        }
        with patch("app.routers.narratives.find_semantic_duplicates", new_callable=AsyncMock, return_value=mock_candidates), \
             patch("app.routers.narratives.register_to_database", return_value=mock_result):
            response = client.post("/api/narratives/register", json={
                "nodes": [{"temp_id": "ng1", "label": "NgAction", "properties": {"action": "騒音"}}],
                "relationships": [],
            })
        # Exact match (text == "騒音") is skipped → no blocking → 200
        assert response.status_code == 200

    def test_ngaction_blocking_skipped_when_no_action_property(self, client):
        """NgAction without 'action' property is not checked."""
        mock_result = {
            "status": "success",
            "registered_count": 1,
            "registered_types": ["NgAction"],
            "client_name": None,
        }
        with patch("app.routers.narratives.register_to_database", return_value=mock_result), \
             patch("app.routers.narratives.find_semantic_duplicates", new_callable=AsyncMock, return_value=[]):
            response = client.post("/api/narratives/register", json={
                "nodes": [{"temp_id": "ng1", "label": "NgAction", "properties": {"riskLevel": "Panic"}}],
                "relationships": [],
            })
        assert response.status_code == 200

    def test_ngaction_blocking_check_failure_passes_through(self, client):
        """If dedup check raises exception, registration proceeds (best effort)."""
        mock_result = {
            "status": "success",
            "registered_count": 1,
            "registered_types": ["NgAction"],
            "client_name": None,
        }
        with patch("app.routers.narratives.find_semantic_duplicates", new_callable=AsyncMock, side_effect=RuntimeError("embedding service down")), \
             patch("app.routers.narratives.register_to_database", return_value=mock_result):
            response = client.post("/api/narratives/register", json={
                "nodes": [{"temp_id": "ng1", "label": "NgAction", "properties": {"action": "騒音"}}],
                "relationships": [],
            })
        assert response.status_code == 200


class TestExtractStream:
    """POST /api/narratives/extract-stream"""

    def test_extract_stream_returns_sse(self, client, mock_db):
        mock_result = {
            "nodes": [{"label": "Client", "properties": {"name": "テスト"}}],
            "relationships": [],
        }
        with patch("app.routers.narratives.extract_from_text", new_callable=AsyncMock, return_value=mock_result), \
             patch("app.routers.narratives.validate_schema", return_value={"is_valid": True}), \
             patch("app.routers.narratives.find_semantic_duplicates", new_callable=AsyncMock, return_value=[]):
            response = client.post(
                "/api/narratives/extract-stream",
                json={"text": "テストテキスト", "client_name": None},
            )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        body = response.text
        assert "stage" in body
        assert "started" in body
        assert "complete" in body

    def test_extract_stream_handles_extraction_failure(self, client, mock_db):
        with patch("app.routers.narratives.extract_from_text", new_callable=AsyncMock, return_value=None):
            response = client.post(
                "/api/narratives/extract-stream",
                json={"text": "テスト", "client_name": None},
            )
        assert response.status_code == 200  # SSE always returns 200
        body = response.text
        assert "error" in body

    def test_extract_stream_handles_extraction_exception(self, client, mock_db):
        with patch("app.routers.narratives.extract_from_text", new_callable=AsyncMock, side_effect=RuntimeError("Gemini down")):
            response = client.post(
                "/api/narratives/extract-stream",
                json={"text": "テスト", "client_name": None},
            )
        assert response.status_code == 200
        body = response.text
        assert "error" in body
        assert "抽出失敗" in body

    def test_extract_stream_progress_stages_in_order(self, client, mock_db):
        mock_result = {
            "nodes": [
                {"label": "Client", "properties": {"name": "田中"}},
                {"label": "NgAction", "properties": {"action": "大声"}},
            ],
            "relationships": [],
        }
        with patch("app.routers.narratives.extract_from_text", new_callable=AsyncMock, return_value=mock_result), \
             patch("app.routers.narratives.validate_schema", return_value={"is_valid": True}), \
             patch("app.routers.narratives.find_semantic_duplicates", new_callable=AsyncMock, return_value=[]):
            response = client.post(
                "/api/narratives/extract-stream",
                json={"text": "田中さんは大声が禁忌です", "client_name": "田中"},
            )
        assert response.status_code == 200
        body = response.text
        # Verify all expected stages are present
        for stage in ("started", "chunking", "extracting", "validating", "dedup_check", "complete"):
            assert stage in body, f"Stage '{stage}' not found in SSE body"

    def test_extract_stream_complete_event_includes_graph(self, client, mock_db):
        mock_result = {
            "nodes": [{"label": "Client", "properties": {"name": "花子"}}],
            "relationships": [],
        }
        with patch("app.routers.narratives.extract_from_text", new_callable=AsyncMock, return_value=mock_result), \
             patch("app.routers.narratives.validate_schema", return_value={"is_valid": True}), \
             patch("app.routers.narratives.find_semantic_duplicates", new_callable=AsyncMock, return_value=[]):
            response = client.post(
                "/api/narratives/extract-stream",
                json={"text": "花子さんの支援記録", "client_name": None},
            )
        assert response.status_code == 200
        # The complete event must contain graph data
        lines = [line for line in response.text.split("\n") if line.startswith("data:")]
        complete_event = None
        for line in lines:
            payload = json.loads(line[len("data:"):].strip())
            if payload.get("stage") == "complete":
                complete_event = payload
                break
        assert complete_event is not None
        assert "data" in complete_event
        assert "graph" in complete_event["data"]
        assert complete_event["progress"] == 100

    def test_extract_stream_includes_semantic_warnings(self, client, mock_db):
        mock_result = {
            "nodes": [
                {"label": "NgAction", "properties": {"action": "騒音"}},
            ],
            "relationships": [],
        }
        mock_candidates = [{"text": "大きな音", "score": 0.91, "nodeId": "4:abc:1"}]
        with patch("app.routers.narratives.extract_from_text", new_callable=AsyncMock, return_value=mock_result), \
             patch("app.routers.narratives.validate_schema", return_value={"is_valid": True}), \
             patch("app.routers.narratives.find_semantic_duplicates", new_callable=AsyncMock, return_value=mock_candidates):
            response = client.post(
                "/api/narratives/extract-stream",
                json={"text": "騒音が禁忌", "client_name": None},
            )
        assert response.status_code == 200
        lines = [line for line in response.text.split("\n") if line.startswith("data:")]
        complete_event = None
        for line in lines:
            payload = json.loads(line[len("data:"):].strip())
            if payload.get("stage") == "complete":
                complete_event = payload
                break
        assert complete_event is not None
        warnings = complete_event["data"]["semanticWarnings"]
        assert len(warnings) == 1
        assert warnings[0]["new_text"] == "騒音"
        assert warnings[0]["existing_text"] == "大きな音"


class TestSafetyCheck:
    """POST /api/narratives/safety-check"""

    def test_safety_check_no_client(self, client):
        """Without client_name, no ng_actions are fetched."""
        mock_result = {"is_violation": False, "warning": None, "risk_level": "None"}
        with patch("app.routers.narratives.check_safety_compliance", new_callable=AsyncMock, return_value=mock_result):
            resp = client.post("/api/narratives/safety-check", json={
                "text": "���歩に行きました",
                "client_name": None,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_violation"] is False

    def test_safety_check_with_client_name(self, client):
        """With client_name, run_query is called inside the handler (local import)."""
        ng_records = [{"ng": {"action": "大声", "reason": "パニック", "riskLevel": "Panic"}}]
        mock_result = {"is_violation": True, "warning": "禁忌事項に抵触", "risk_level": "Panic"}

        with patch("app.lib.db_operations.run_query", return_value=ng_records), \
             patch("app.routers.narratives.check_safety_compliance", new_callable=AsyncMock, return_value=mock_result):
            resp = client.post("/api/narratives/safety-check", json={
                "text": "大声で呼びかけました",
                "client_name": "田中太郎",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_violation"] is True
        assert data["risk_level"] == "Panic"

    def test_safety_check_no_ng_actions_in_db(self, client):
        """Client exists but has no NgAction nodes."""
        mock_result = {"is_violation": False, "warning": None, "risk_level": "None"}

        with patch("app.lib.db_operations.run_query", return_value=[]), \
             patch("app.routers.narratives.check_safety_compliance", new_callable=AsyncMock, return_value=mock_result):
            resp = client.post("/api/narratives/safety-check", json={
                "text": "テスト",
                "client_name": "田中太郎",
            })

        assert resp.status_code == 200
        assert resp.json()["is_violation"] is False
