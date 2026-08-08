"""Comprehensive tests for /api/search endpoints."""

from unittest.mock import patch, AsyncMock


class TestFulltextSearch:
    """GET /api/search/fulltext"""

    def test_fulltext_search_success(self, client):
        mock_records = [
            {
                "date": "2026-04-01",
                "note": "パニック対応: 静かな部屋に移動",
                "situation": "パニック",
                "client_name": "田中太郎",
                "score": 2.5,
            },
        ]
        with patch("app.routers.search.run_query", return_value=mock_records):
            resp = client.get("/api/search/fulltext?q=パニック")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["client_name"] == "田中太郎"
        assert data[0]["score"] == 2.5

    def test_fulltext_search_empty_results(self, client):
        with patch("app.routers.search.run_query", return_value=[]):
            resp = client.get("/api/search/fulltext?q=存在しないテキスト")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_fulltext_search_custom_limit(self, client):
        with patch("app.routers.search.run_query", return_value=[]) as mock_rq:
            resp = client.get("/api/search/fulltext?q=テスト&limit=5")

        assert resp.status_code == 200
        # Verify limit was passed
        call_params = mock_rq.call_args[0][1]
        assert call_params["limit"] == 5

    def test_fulltext_search_missing_query(self, client):
        resp = client.get("/api/search/fulltext")
        assert resp.status_code == 422


class TestSemanticSearch:
    """POST /api/search/semantic"""

    def test_semantic_search_success(self, client):
        mock_embedding = [0.1] * 768
        mock_results = [
            {
                "node": {
                    "date": "2026-04-01",
                    "note": "散歩同行",
                    "situation": "日常",
                },
                "score": 0.95,
            },
        ]
        with patch("app.routers.search.embed_text", new_callable=AsyncMock, return_value=mock_embedding), \
             patch("app.routers.search.semantic_search", return_value=mock_results):
            resp = client.post("/api/search/semantic", json={
                "query": "散歩に関する記録",
                "index_name": "support_log_vector_index",
                "top_k": 5,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["score"] == 0.95
        assert "note" in data[0]["properties"]

    def test_semantic_search_no_embedding(self, client):
        """If embed_text returns None, return empty list."""
        with patch("app.routers.search.embed_text", new_callable=AsyncMock, return_value=None):
            resp = client.post("/api/search/semantic", json={
                "query": "テスト",
            })

        assert resp.status_code == 200
        assert resp.json() == []

    def test_semantic_search_excludes_embedding_vectors(self, client):
        """Embedding vectors should be excluded from response properties."""
        mock_embedding = [0.1] * 768
        mock_results = [
            {
                "node": {
                    "note": "テスト",
                    "embedding": [0.1] * 768,
                    "summaryEmbedding": [0.2] * 768,
                    "textEmbedding": [0.3] * 768,
                },
                "score": 0.9,
            },
        ]
        with patch("app.routers.search.embed_text", new_callable=AsyncMock, return_value=mock_embedding), \
             patch("app.routers.search.semantic_search", return_value=mock_results):
            resp = client.post("/api/search/semantic", json={"query": "テスト"})

        assert resp.status_code == 200
        data = resp.json()
        props = data[0]["properties"]
        assert "embedding" not in props
        assert "summaryEmbedding" not in props
        assert "textEmbedding" not in props
        assert "note" in props

    def test_semantic_search_default_index_name(self, client):
        with patch("app.routers.search.embed_text", new_callable=AsyncMock, return_value=None):
            resp = client.post("/api/search/semantic", json={"query": "テスト"})

        assert resp.status_code == 200

    def test_semantic_search_sanitizes_neo4j_types(self, client):
        """Non-standard types in node properties should be stringified."""
        mock_embedding = [0.1] * 768
        from unittest.mock import MagicMock
        neo4j_date_mock = MagicMock()
        neo4j_date_mock.__str__ = MagicMock(return_value="2026-04-01")

        mock_results = [
            {
                "node": {
                    "date": neo4j_date_mock,
                    "note": "テスト",
                    "count": 5,
                    "active": True,
                },
                "score": 0.8,
            },
        ]
        with patch("app.routers.search.embed_text", new_callable=AsyncMock, return_value=mock_embedding), \
             patch("app.routers.search.semantic_search", return_value=mock_results):
            resp = client.post("/api/search/semantic", json={"query": "テスト"})

        assert resp.status_code == 200
        data = resp.json()
        props = data[0]["properties"]
        # date was a mock object, should be stringified
        assert isinstance(props["date"], str)
        # native types should pass through
        assert props["count"] == 5
        assert props["active"] is True
