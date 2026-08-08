"""Comprehensive tests for /api/quicklog endpoints."""

from unittest.mock import patch


class TestCreateQuicklog:
    """POST /api/quicklog"""

    def test_create_quicklog_success(self, client):
        mock_result = {
            "status": "success",
            "client_name": "田中太郎",
            "registered_count": 3,
            "registered_types": ["Client", "Supporter", "SupportLog"],
        }
        with patch("app.routers.quicklog.register_to_database", return_value=mock_result):
            resp = client.post("/api/quicklog", json={
                "client_name": "田中太郎",
                "note": "今日は穏やかに過ごされた",
                "situation": "日常記録",
                "supporter_name": "佐藤",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["client_name"] == "田中太郎"
        assert data["registered_count"] == 3

    def test_create_quicklog_minimal(self, client):
        """Only required fields: client_name and note."""
        mock_result = {
            "status": "success",
            "client_name": "田中太郎",
            "registered_count": 3,
            "registered_types": ["Client", "Supporter", "SupportLog"],
        }
        with patch("app.routers.quicklog.register_to_database", return_value=mock_result):
            resp = client.post("/api/quicklog", json={
                "client_name": "田中太郎",
                "note": "特記事項なし",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    def test_create_quicklog_graph_structure(self, client):
        """Verify the graph passed to register_to_database has correct structure."""
        with patch("app.routers.quicklog.register_to_database", return_value={
            "status": "success", "client_name": "テスト", "registered_count": 3, "registered_types": [],
        }) as mock_reg:
            client.post("/api/quicklog", json={
                "client_name": "テスト",
                "note": "テストメモ",
                "situation": "パニック対応",
                "supporter_name": "鈴木",
            })

        # Verify the graph structure passed to register_to_database
        call_args = mock_reg.call_args
        graph = call_args[0][0] if call_args[0] else call_args[1].get("extracted_graph", call_args[0][0])

        # Should have 3 nodes: Client, Supporter, SupportLog
        assert len(graph["nodes"]) == 3
        labels = {n["label"] for n in graph["nodes"]}
        assert labels == {"Client", "Supporter", "SupportLog"}

        # Should have 2 relationships: LOGGED and ABOUT
        assert len(graph["relationships"]) == 2
        rel_types = {r["type"] for r in graph["relationships"]}
        assert rel_types == {"LOGGED", "ABOUT"}

    def test_create_quicklog_missing_required_fields(self, client):
        """Missing client_name or note should fail validation."""
        resp = client.post("/api/quicklog", json={"note": "テスト"})
        assert resp.status_code == 422

        resp = client.post("/api/quicklog", json={"client_name": "テスト"})
        assert resp.status_code == 422

    def test_create_quicklog_default_supporter_name(self, client):
        """Default supporter_name should be 'system'."""
        with patch("app.routers.quicklog.register_to_database", return_value={
            "status": "success", "client_name": "テスト", "registered_count": 3, "registered_types": [],
        }) as mock_reg:
            client.post("/api/quicklog", json={
                "client_name": "テスト",
                "note": "テストメモ",
            })

        graph = mock_reg.call_args[0][0]
        supporter_node = next(n for n in graph["nodes"] if n["label"] == "Supporter")
        assert supporter_node["properties"]["name"] == "system"

    def test_create_quicklog_db_error(self, client):
        mock_result = {
            "status": "error",
            "client_name": "テスト",
            "registered_count": 0,
            "registered_types": [],
        }
        with patch("app.routers.quicklog.register_to_database", return_value=mock_result):
            resp = client.post("/api/quicklog", json={
                "client_name": "テスト",
                "note": "テスト",
            })

        assert resp.status_code == 200
        assert resp.json()["status"] == "error"
