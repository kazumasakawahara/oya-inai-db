"""Comprehensive tests for /api/dashboard endpoints.

All Neo4j queries are mocked — no running database required.
"""

from unittest.mock import patch


class TestGetStats:
    """GET /api/dashboard/stats"""

    def test_get_stats_success(self, client):
        side_effects = [
            [{"cnt": 15}],          # client count
            [{"cnt": 42}],          # log count this month
            [{"cnt": 3}],           # renewal alerts
        ]
        with patch("app.routers.dashboard.run_query", side_effect=side_effects):
            resp = client.get("/api/dashboard/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["client_count"] == 15
        assert data["log_count_this_month"] == 42
        assert data["renewal_alerts"] == 3

    def test_get_stats_empty_db(self, client):
        with patch("app.routers.dashboard.run_query", return_value=[]):
            resp = client.get("/api/dashboard/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["client_count"] == 0
        assert data["log_count_this_month"] == 0
        assert data["renewal_alerts"] == 0

    def test_get_stats_db_error_returns_500(self, client):
        with patch("app.routers.dashboard.run_query", side_effect=Exception("Connection refused")):
            resp = client.get("/api/dashboard/stats")

        assert resp.status_code == 500

    def test_get_stats_response_fields(self, client):
        side_effects = [[{"cnt": 0}], [{"cnt": 0}], [{"cnt": 0}]]
        with patch("app.routers.dashboard.run_query", side_effect=side_effects):
            resp = client.get("/api/dashboard/stats")

        data = resp.json()
        assert "client_count" in data
        assert "log_count_this_month" in data
        assert "renewal_alerts" in data


class TestGetAlerts:
    """GET /api/dashboard/alerts"""

    def test_get_alerts_success(self, client):
        mock_rows = [
            {
                "client_name": "田中太郎",
                "certificate_type": "療育手帳",
                "next_renewal_date": "2026-06-01",
            },
            {
                "client_name": "山田花子",
                "certificate_type": "受給者証",
                "next_renewal_date": "2026-05-15",
            },
        ]
        with patch("app.routers.dashboard.run_query", return_value=mock_rows):
            resp = client.get("/api/dashboard/alerts")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["client_name"] == "田中太郎"
        assert data[0]["certificate_type"] == "療育手帳"
        assert "days_remaining" in data[0]

    def test_get_alerts_empty(self, client):
        with patch("app.routers.dashboard.run_query", return_value=[]):
            resp = client.get("/api/dashboard/alerts")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_alerts_invalid_date_sets_zero_days(self, client):
        mock_rows = [
            {
                "client_name": "テスト",
                "certificate_type": "手帳",
                "next_renewal_date": "invalid-date",
            },
        ]
        with patch("app.routers.dashboard.run_query", return_value=mock_rows):
            resp = client.get("/api/dashboard/alerts")

        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["days_remaining"] == 0

    def test_get_alerts_db_error_returns_500(self, client):
        with patch("app.routers.dashboard.run_query", side_effect=Exception("Timeout")):
            resp = client.get("/api/dashboard/alerts")

        assert resp.status_code == 500


class TestGetActivity:
    """GET /api/dashboard/activity"""

    def test_get_activity_success(self, client):
        mock_rows = [
            {
                "date": "2026-04-01T10:00:00Z",
                "client_name": "田中太郎",
                "action": "register",
                "summary": "Registered 3 node(s)",
            },
        ]
        with patch("app.routers.dashboard.run_query", return_value=mock_rows):
            resp = client.get("/api/dashboard/activity")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["action"] == "register"
        assert data[0]["client_name"] == "田中太郎"

    def test_get_activity_empty(self, client):
        with patch("app.routers.dashboard.run_query", return_value=[]):
            resp = client.get("/api/dashboard/activity")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_activity_custom_limit(self, client):
        with patch("app.routers.dashboard.run_query", return_value=[]) as mock_rq:
            resp = client.get("/api/dashboard/activity?limit=5")

        assert resp.status_code == 200
        # Verify the limit parameter was passed to run_query
        call_args = mock_rq.call_args
        assert call_args[1]["limit"] == 5 if call_args[1] else call_args[0][1]["limit"] == 5

    def test_get_activity_handles_none_fields(self, client):
        mock_rows = [
            {"date": None, "client_name": None, "action": None, "summary": None},
        ]
        with patch("app.routers.dashboard.run_query", return_value=mock_rows):
            resp = client.get("/api/dashboard/activity")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        # All None values should be stringified
        assert data[0]["date"] == "None"
