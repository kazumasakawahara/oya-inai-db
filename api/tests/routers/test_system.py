"""Comprehensive tests for /api/system endpoints."""

from unittest.mock import patch


class TestSystemStatus:
    """GET /api/system/status"""

    def test_system_status_all_fields_present(self, client):
        with patch("app.routers.system.is_db_available", return_value=True):
            resp = client.get("/api/system/status")

        assert resp.status_code == 200
        data = resp.json()
        assert "neo4j_available" in data

    def test_system_status_neo4j_available(self, client):
        with patch("app.routers.system.is_db_available", return_value=True):
            resp = client.get("/api/system/status")

        assert resp.json()["neo4j_available"] is True

    def test_system_status_neo4j_unavailable(self, client):
        with patch("app.routers.system.is_db_available", return_value=False):
            resp = client.get("/api/system/status")

        assert resp.json()["neo4j_available"] is False


class TestHealth:
    """GET /api/health"""

    def test_health_ok(self, client):
        resp = client.get("/api/health")

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_health_is_always_available(self, client):
        """Health endpoint should work even when Neo4j is down."""
        with patch("app.lib.db_operations.is_db_available", return_value=False):
            resp = client.get("/api/health")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
