"""Tests for /api/graph endpoints."""
from unittest.mock import patch


class TestGraphExplore:
    """GET /api/graph/explore"""

    def test_explore_without_params_returns_response(self, client, mock_db):
        response = client.get("/api/graph/explore")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert "truncated" in data

    def test_explore_with_invalid_label_returns_400(self, client, mock_db):
        response = client.get("/api/graph/explore?startLabel=InvalidLabel")
        assert response.status_code == 400
        assert "Unsupported label" in response.json()["detail"]

    def test_explore_with_valid_label_returns_200(self, client, mock_db):
        mock_result = [{"nodes": [], "edges": []}]
        with patch("app.routers.graph.run_query", return_value=mock_result):
            response = client.get("/api/graph/explore?startLabel=Client")
        assert response.status_code == 200

    def test_explore_with_start_label_and_name(self, client, mock_db):
        mock_result = [{"nodes": [], "edges": []}]
        with patch("app.routers.graph.run_query", return_value=mock_result):
            response = client.get("/api/graph/explore?startLabel=Client&startName=田中太郎")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    def test_explore_returns_nodes_and_edges(self, client, mock_db):
        mock_result = [
            {
                "nodes": [
                    {
                        "id": "4:abc:1",
                        "labels": ["Client"],
                        "properties": {"name": "田中太郎", "dob": "1990-01-01"},
                    },
                    {
                        "id": "4:abc:2",
                        "labels": ["NgAction"],
                        "properties": {"action": "大声を出す", "riskLevel": "Panic"},
                    },
                ],
                "edges": [
                    {
                        "id": "5:abc:1",
                        "source": "4:abc:1",
                        "target": "4:abc:2",
                        "type": "MUST_AVOID",
                        "properties": {},
                    }
                ],
            }
        ]
        with patch("app.routers.graph.run_query", return_value=mock_result):
            response = client.get("/api/graph/explore?startLabel=Client")
        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1
        assert data["nodes"][0]["id"] == "4:abc:1"
        assert data["nodes"][0]["label"] == "Client"
        assert data["nodes"][0]["name"] == "田中太郎"
        assert data["edges"][0]["type"] == "MUST_AVOID"
        assert data["edges"][0]["source"] == "4:abc:1"
        assert data["edges"][0]["target"] == "4:abc:2"

    def test_explore_deduplicates_nodes(self, client, mock_db):
        """Duplicate node IDs in the result should be deduplicated."""
        dup_node = {"id": "4:abc:1", "labels": ["Client"], "properties": {"name": "dup"}}
        mock_result = [{"nodes": [dup_node, dup_node], "edges": []}]
        with patch("app.routers.graph.run_query", return_value=mock_result):
            response = client.get("/api/graph/explore?startLabel=Client")
        assert response.status_code == 200
        assert len(response.json()["nodes"]) == 1

    def test_explore_empty_result_returns_empty_lists(self, client, mock_db):
        with patch("app.routers.graph.run_query", return_value=[]):
            response = client.get("/api/graph/explore")
        assert response.status_code == 200
        data = response.json()
        assert data["nodes"] == []
        assert data["edges"] == []

    def test_explore_node_with_no_name_falls_back_to_question_mark(self, client, mock_db):
        mock_result = [
            {
                "nodes": [
                    {"id": "4:abc:9", "labels": ["Certificate"], "properties": {}},
                ],
                "edges": [],
            }
        ]
        with patch("app.routers.graph.run_query", return_value=mock_result):
            response = client.get("/api/graph/explore?startLabel=Certificate")
        assert response.status_code == 200
        assert response.json()["nodes"][0]["name"] == "?"

    def test_explore_db_error_returns_500(self, client, mock_db):
        with patch("app.routers.graph.run_query", side_effect=Exception("Connection refused")):
            response = client.get("/api/graph/explore")
        assert response.status_code == 500

    def test_explore_maxDepth_param_respected(self, client, mock_db):
        mock_result = [{"nodes": [], "edges": []}]
        with patch("app.routers.graph.run_query", return_value=mock_result) as mock_rq:
            response = client.get(
                "/api/graph/explore?startLabel=Client&startName=田中太郎&maxDepth=3"
            )
        assert response.status_code == 200
        call_kwargs = mock_rq.call_args[0][1] if mock_rq.call_args[0] else mock_rq.call_args[1]
        assert call_kwargs.get("depth") == 3

    def test_explore_maxDepth_out_of_range_returns_422(self, client, mock_db):
        response = client.get("/api/graph/explore?maxDepth=10")
        assert response.status_code == 422

    def test_explore_maxNodes_out_of_range_returns_422(self, client, mock_db):
        response = client.get("/api/graph/explore?maxNodes=1000")
        assert response.status_code == 422

    def test_explore_truncated_flag_set_when_at_limit(self, client, mock_db):
        # Generate exactly maxNodes nodes to trigger truncated=True
        nodes = [
            {"id": f"4:abc:{i}", "labels": ["Client"], "properties": {"name": f"client{i}"}}
            for i in range(10)  # maxNodes minimum is 10
        ]
        mock_result = [{"nodes": nodes, "edges": []}]
        with patch("app.routers.graph.run_query", return_value=mock_result):
            response = client.get("/api/graph/explore?maxNodes=10")
        assert response.status_code == 200
        assert response.json()["truncated"] is True


class TestGraphLabels:
    """GET /api/graph/labels"""

    def test_list_labels_returns_200(self, client, mock_db):
        mock_result = [
            {"label": "Client", "count": 10},
            {"label": "NgAction", "count": 50},
        ]
        with patch("app.routers.graph.run_query", return_value=mock_result):
            response = client.get("/api/graph/labels")
        assert response.status_code == 200
        data = response.json()
        assert "labels" in data
        assert len(data["labels"]) == 2
        assert data["labels"][0]["label"] == "Client"
        assert data["labels"][0]["count"] == 10

    def test_list_labels_empty_db_returns_empty_list(self, client, mock_db):
        with patch("app.routers.graph.run_query", return_value=[]):
            response = client.get("/api/graph/labels")
        assert response.status_code == 200
        assert response.json()["labels"] == []

    def test_list_labels_db_error_returns_empty_gracefully(self, client, mock_db):
        """Labels endpoint should not raise 500 — it returns empty list on error."""
        with patch("app.routers.graph.run_query", side_effect=Exception("Timeout")):
            response = client.get("/api/graph/labels")
        assert response.status_code == 200
        assert response.json()["labels"] == []


class TestGraphStats:
    """GET /api/graph/stats"""

    def test_stats_returns_counts(self, client, mock_db):
        response = client.get("/api/graph/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_nodes" in data
        assert "total_edges" in data
        assert isinstance(data["total_nodes"], int)
        assert isinstance(data["total_edges"], int)

    def test_stats_returns_correct_values(self, client, mock_db):
        with patch(
            "app.routers.graph.run_query",
            side_effect=[[{"c": 42}], [{"c": 123}]],
        ):
            response = client.get("/api/graph/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_nodes"] == 42
        assert data["total_edges"] == 123

    def test_stats_db_error_returns_zeros_gracefully(self, client, mock_db):
        """Stats endpoint should not raise 500 — it returns zeros on error."""
        with patch("app.routers.graph.run_query", side_effect=Exception("Connection refused")):
            response = client.get("/api/graph/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_nodes"] == 0
        assert data["total_edges"] == 0

    def test_stats_empty_db_returns_zeros(self, client, mock_db):
        with patch("app.routers.graph.run_query", return_value=[]):
            response = client.get("/api/graph/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_nodes"] == 0
        assert data["total_edges"] == 0
