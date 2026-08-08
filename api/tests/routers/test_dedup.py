"""Tests for /api/dedup endpoints."""
import pytest
from unittest.mock import patch, AsyncMock


class TestDedupCheck:
    def test_check_returns_valid_response(self, client, mock_db):
        response = client.post("/api/dedup/check", json={
            "label": "Client",
            "properties": {"name": "田中太郎"},
        })
        assert response.status_code == 200
        data = response.json()
        assert "hasCandidates" in data
        assert "candidates" in data
        assert "checkedLabel" in data
        assert data["checkedLabel"] == "Client"

    def test_check_includes_exact_check(self, client, mock_db):
        response = client.post("/api/dedup/check", json={
            "label": "Client",
            "properties": {"name": "田中太郎"},
        })
        data = response.json()
        assert "exact" in data["checksPerformed"]

    def test_check_includes_kana_for_client(self, client, mock_db):
        response = client.post("/api/dedup/check", json={
            "label": "Client",
            "properties": {"name": "田中太郎"},
        })
        data = response.json()
        assert "kana" in data["checksPerformed"]

    def test_check_includes_semantic_for_ngaction(self, client, mock_db):
        with patch("app.services.dedup_service.find_semantic_duplicates", new_callable=AsyncMock, return_value=[]):
            response = client.post("/api/dedup/check", json={
                "label": "NgAction",
                "properties": {"action": "大きな音を出す"},
            })
        data = response.json()
        assert "semantic" in data["checksPerformed"]

    def test_check_no_kana_for_ngaction(self, client, mock_db):
        with patch("app.services.dedup_service.find_semantic_duplicates", new_callable=AsyncMock, return_value=[]):
            response = client.post("/api/dedup/check", json={
                "label": "NgAction",
                "properties": {"action": "test"},
            })
        data = response.json()
        assert "kana" not in data["checksPerformed"]
