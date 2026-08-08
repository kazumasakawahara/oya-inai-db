"""Comprehensive tests for /api/ecomap endpoints."""

from unittest.mock import patch

from app.schemas.ecomap import EcomapData, EcomapEdge, EcomapNode


class TestListTemplates:
    """GET /api/ecomap/templates"""

    def test_list_templates(self, client):
        resp = client.get("/api/ecomap/templates")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4
        ids = [t["id"] for t in data]
        assert "full_view" in ids
        assert "emergency" in ids
        assert "support_meeting" in ids
        assert "handover" in ids

    def test_templates_have_required_fields(self, client):
        resp = client.get("/api/ecomap/templates")

        for tmpl in resp.json():
            assert "id" in tmpl
            assert "name" in tmpl
            assert "description" in tmpl
            assert isinstance(tmpl["name"], str)
            assert len(tmpl["name"]) > 0


class TestGetColors:
    """GET /api/ecomap/colors"""

    def test_get_colors(self, client):
        resp = client.get("/api/ecomap/colors")

        assert resp.status_code == 200
        colors = resp.json()
        assert "client" in colors
        assert "ngActions" in colors
        assert "carePreferences" in colors
        assert "keyPersons" in colors

    def test_colors_are_hex(self, client):
        resp = client.get("/api/ecomap/colors")

        for key, color in resp.json().items():
            assert color.startswith("#"), f"Color for {key} is not hex: {color}"
            assert len(color) == 7, f"Color for {key} has wrong length: {color}"


class TestGetEcomap:
    """GET /api/ecomap/{client_name}"""

    def test_get_ecomap_success(self, client):
        mock_data = EcomapData(
            client_name="テスト太郎",
            template="full_view",
            nodes=[
                EcomapNode(
                    id="client", label="テスト太郎", node_label="Client",
                    category="client", color="#569480", properties={},
                ),
                EcomapNode(
                    id="ng-1", label="大声を出す", node_label="NgAction",
                    category="ngActions", color="#df4b26",
                    properties={"action": "大声を出す", "riskLevel": "Panic"},
                ),
            ],
            edges=[
                EcomapEdge(source="client", target="ng-1", label="MUST_AVOID"),
            ],
        )
        with patch("app.routers.ecomap.fetch_ecomap_data", return_value=mock_data):
            resp = client.get("/api/ecomap/テスト太郎?template=full_view")

        assert resp.status_code == 200
        data = resp.json()
        assert data["client_name"] == "テスト太郎"
        assert data["template"] == "full_view"
        assert len(data["nodes"]) == 2
        assert data["nodes"][0]["category"] == "client"
        assert len(data["edges"]) == 1

    def test_get_ecomap_default_template(self, client):
        mock_data = EcomapData(
            client_name="テスト",
            template="full_view",
            nodes=[EcomapNode(
                id="client", label="テスト", node_label="Client",
                category="client", color="#569480", properties={},
            )],
            edges=[],
        )
        with patch("app.routers.ecomap.fetch_ecomap_data", return_value=mock_data) as mock_fetch:
            resp = client.get("/api/ecomap/テスト")

        assert resp.status_code == 200
        # Default template should be full_view
        mock_fetch.assert_called_once_with("テスト", "full_view")

    def test_get_ecomap_emergency_template(self, client):
        mock_data = EcomapData(
            client_name="テスト",
            template="emergency",
            nodes=[EcomapNode(
                id="client", label="テスト", node_label="Client",
                category="client", color="#569480", properties={},
            )],
            edges=[],
        )
        with patch("app.routers.ecomap.fetch_ecomap_data", return_value=mock_data):
            resp = client.get("/api/ecomap/テスト?template=emergency")

        assert resp.status_code == 200
        assert resp.json()["template"] == "emergency"

    def test_get_ecomap_client_node_always_present(self, client):
        """Even with no related nodes, the client node should always be present."""
        mock_data = EcomapData(
            client_name="孤立テスト",
            template="full_view",
            nodes=[EcomapNode(
                id="client", label="孤立テスト", node_label="Client",
                category="client", color="#569480", properties={},
            )],
            edges=[],
        )
        with patch("app.routers.ecomap.fetch_ecomap_data", return_value=mock_data):
            resp = client.get("/api/ecomap/孤立テスト")

        data = resp.json()
        assert len(data["nodes"]) >= 1
        assert data["nodes"][0]["id"] == "client"
        assert data["nodes"][0]["category"] == "client"
