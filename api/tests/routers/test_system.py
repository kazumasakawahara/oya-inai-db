"""Comprehensive tests for /api/system endpoints."""

from unittest.mock import patch


class TestSystemStatus:
    """GET /api/system/status"""

    def test_system_status_all_fields_present(self, client):
        with patch("app.routers.system.is_db_available", return_value=True):
            resp = client.get("/api/system/status")

        assert resp.status_code == 200
        data = resp.json()
        assert "gemini_available" in data
        assert "claude_available" in data
        assert "neo4j_available" in data
        assert "chat_provider" in data
        assert "chat_model" in data
        assert "embedding_model" in data

    def test_system_status_neo4j_available(self, client):
        with patch("app.routers.system.is_db_available", return_value=True):
            resp = client.get("/api/system/status")

        assert resp.json()["neo4j_available"] is True

    def test_system_status_neo4j_unavailable(self, client):
        with patch("app.routers.system.is_db_available", return_value=False):
            resp = client.get("/api/system/status")

        assert resp.json()["neo4j_available"] is False

    def test_system_status_default_provider(self, client):
        with patch("app.routers.system.is_db_available", return_value=False):
            resp = client.get("/api/system/status")

        data = resp.json()
        # Provider is one of the supported options
        assert data["chat_provider"] in ("gemini", "claude", "openai", "ollama")

    def test_system_status_embedding_model(self, client):
        with patch("app.routers.system.is_db_available", return_value=False):
            resp = client.get("/api/system/status")

        data = resp.json()
        assert isinstance(data["embedding_model"], str)

    def test_system_status_has_ollama_field(self, client):
        """ollama_available field is present in system status response."""
        with patch("app.routers.system.is_db_available", return_value=False):
            resp = client.get("/api/system/status")

        data = resp.json()
        assert "ollama_available" in data

    def test_system_status_ollama_available_is_bool(self, client):
        """ollama_available field is a boolean value."""
        with patch("app.routers.system.is_db_available", return_value=False):
            resp = client.get("/api/system/status")

        data = resp.json()
        assert isinstance(data["ollama_available"], bool)


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
