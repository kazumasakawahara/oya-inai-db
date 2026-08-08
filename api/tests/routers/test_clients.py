"""Comprehensive tests for /api/clients endpoints.

All Neo4j queries are mocked — no running database required.
"""

from unittest.mock import patch, call


class TestListClients:
    """GET /api/clients"""

    def test_list_clients_success(self, client, sample_client_row):
        with patch("app.routers.clients.run_query", return_value=[sample_client_row]):
            resp = client.get("/api/clients")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "田中太郎"
        assert data[0]["blood_type"] == "A"
        assert "自閉スペクトラム症" in data[0]["conditions"]

    def test_list_clients_empty(self, client):
        with patch("app.routers.clients.run_query", return_value=[]):
            resp = client.get("/api/clients")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_clients_kana_filter_ta(self, client, sample_client_row):
        """た行フィルタで田中太郎（たなかたろう）がマッチする。"""
        with patch("app.routers.clients.run_query", return_value=[sample_client_row]):
            resp = client.get("/api/clients?kana_prefix=た")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "田中太郎"

    def test_list_clients_kana_filter_no_match(self, client, sample_client_row):
        """あ行フィルタで田中太郎はマッチしない。"""
        with patch("app.routers.clients.run_query", return_value=[sample_client_row]):
            resp = client.get("/api/clients?kana_prefix=あ")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 0

    def test_list_clients_abc_filter_matches_alpha_name(self, client):
        """ABCフィルタでアルファベット名がマッチする。"""
        alpha_row = {
            "name": "M・K",
            "dob": "2000-01-01",
            "blood_type": "O",
            "kana": None,
            "conditions": [],
        }
        with patch("app.routers.clients.run_query", return_value=[alpha_row]):
            resp = client.get("/api/clients?kana_prefix=ABC")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "M・K"

    def test_list_clients_abc_filter_excludes_kanji_name(self, client, sample_client_row):
        """ABCフィルタで漢字名は除外される。"""
        with patch("app.routers.clients.run_query", return_value=[sample_client_row]):
            resp = client.get("/api/clients?kana_prefix=ABC")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 0

    def test_list_clients_calculates_age(self, client):
        row = {
            "name": "テスト",
            "dob": "2000-01-01",
            "blood_type": None,
            "kana": "てすと",
            "conditions": [],
        }
        with patch("app.routers.clients.run_query", return_value=[row]):
            resp = client.get("/api/clients")

        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["age"] is not None
        assert data[0]["age"] >= 25  # born 2000, test run >= 2025

    def test_list_clients_null_dob_no_age(self, client):
        row = {
            "name": "テスト",
            "dob": None,
            "blood_type": None,
            "kana": "てすと",
            "conditions": [],
        }
        with patch("app.routers.clients.run_query", return_value=[row]):
            resp = client.get("/api/clients")

        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["age"] is None
        assert data[0]["dob"] is None

    def test_list_clients_filters_empty_conditions(self, client):
        row = {
            "name": "テスト",
            "dob": None,
            "blood_type": None,
            "kana": "てすと",
            "conditions": [None, "", "自閉症"],
        }
        with patch("app.routers.clients.run_query", return_value=[row]):
            resp = client.get("/api/clients")

        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["conditions"] == ["自閉症"]

    def test_list_clients_db_error_returns_500(self, client):
        with patch("app.routers.clients.run_query", side_effect=Exception("DB error")):
            resp = client.get("/api/clients")

        assert resp.status_code == 500


class TestGetClient:
    """GET /api/clients/{name}"""

    def test_get_client_success(self, client, sample_client_detail_row):
        with patch("app.routers.clients.run_query", return_value=[sample_client_detail_row]):
            resp = client.get("/api/clients/田中太郎")

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "田中太郎"
        assert data["blood_type"] == "A"
        assert len(data["conditions"]) == 1
        assert data["conditions"][0]["name"] == "自閉スペクトラム症"
        assert len(data["ng_actions"]) == 1
        assert data["ng_actions"][0]["action"] == "大声を出す"
        assert data["ng_actions"][0]["risk_level"] == "Panic"
        assert len(data["care_preferences"]) == 1
        assert len(data["key_persons"]) == 1
        assert data["key_persons"][0]["rank"] == 1
        assert data["hospital"]["name"] == "中央病院"
        assert data["guardian"]["name"] == "山田法律事務所"

    def test_get_client_not_found(self, client):
        with patch("app.routers.clients.run_query", return_value=[]):
            resp = client.get("/api/clients/存在しない人")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    def test_get_client_ng_actions_sorted_by_risk(self, client):
        """NgActions are sorted: LifeThreatening > Panic > Discomfort."""
        row = {
            "name": "テスト",
            "dob": None,
            "blood_type": None,
            "conditions": [],
            "ng_actions": [
                {"action": "低リスク", "reason": "", "riskLevel": "Discomfort"},
                {"action": "生命危機", "reason": "", "riskLevel": "LifeThreatening"},
                {"action": "パニック", "reason": "", "riskLevel": "Panic"},
            ],
            "care_preferences": [],
            "key_persons": [],
            "certificates": [],
            "hospital": None,
            "guardian": None,
        }
        with patch("app.routers.clients.run_query", return_value=[row]):
            resp = client.get("/api/clients/テスト")

        data = resp.json()
        risk_levels = [ng["risk_level"] for ng in data["ng_actions"]]
        assert risk_levels == ["LifeThreatening", "Panic", "Discomfort"]

    def test_get_client_filters_null_entries(self, client):
        """Null entries from OPTIONAL MATCH are filtered out."""
        row = {
            "name": "テスト",
            "dob": None,
            "blood_type": None,
            "conditions": [{"name": None, "diagnosedDate": None}, {"name": "知的障害", "diagnosedDate": "2020-01-01"}],
            "ng_actions": [{"action": None, "reason": None, "riskLevel": None}],
            "care_preferences": [{"category": None, "instruction": None, "priority": None}],
            "key_persons": [{"name": None, "relationship": None, "phone": None, "rank": None}],
            "certificates": [],
            "hospital": None,
            "guardian": None,
        }
        with patch("app.routers.clients.run_query", return_value=[row]):
            resp = client.get("/api/clients/テスト")

        data = resp.json()
        assert len(data["conditions"]) == 1
        assert data["conditions"][0]["name"] == "知的障害"
        assert len(data["ng_actions"]) == 0
        assert len(data["care_preferences"]) == 0
        assert len(data["key_persons"]) == 0


class TestGetEmergency:
    """GET /api/clients/{name}/emergency"""

    def test_get_emergency_success(self, client):
        row = {
            "name": "田中太郎",
            "ng_actions": [
                {"action": "大声を出す", "reason": "パニック誘発", "riskLevel": "Panic"},
            ],
            "care_preferences": [
                {"category": "落ち着かせ方", "instruction": "静かな部屋に移動", "priority": "高"},
            ],
            "key_persons": [
                {"name": "田中花子", "relationship": "母", "phone": "090-1234-5678", "rank": 1},
            ],
            "hospital": {"name": "中央病院", "phone": "03-1234-5678"},
            "guardian": {"name": "山田法律事務所", "type": "成年後見人"},
        }
        with patch("app.routers.clients.run_query", return_value=[row]):
            resp = client.get("/api/clients/田中太郎/emergency")

        assert resp.status_code == 200
        data = resp.json()
        assert data["client_name"] == "田中太郎"
        assert len(data["ng_actions"]) == 1
        assert len(data["key_persons"]) == 1
        assert data["hospital"]["name"] == "中央病院"

    def test_get_emergency_not_found(self, client):
        with patch("app.routers.clients.run_query", return_value=[]):
            resp = client.get("/api/clients/存在しない人/emergency")

        assert resp.status_code == 404

    def test_get_emergency_minimal_data(self, client):
        """Client exists but has no related nodes."""
        row = {
            "name": "最小テスト",
            "ng_actions": [],
            "care_preferences": [],
            "key_persons": [],
            "hospital": None,
            "guardian": None,
        }
        with patch("app.routers.clients.run_query", return_value=[row]):
            resp = client.get("/api/clients/最小テスト/emergency")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ng_actions"] == []
        assert data["key_persons"] == []
        assert data["hospital"] is None


class TestGetLogs:
    """GET /api/clients/{name}/logs"""

    def test_get_logs_success(self, client, sample_support_log_rows):
        side_effects = [
            [{"n": "田中太郎"}],         # existence check
            sample_support_log_rows,       # actual logs
        ]
        with patch("app.routers.clients.run_query", side_effect=side_effects):
            resp = client.get("/api/clients/田中太郎/logs")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["situation"] == "パニック"
        assert data[0]["supporter_name"] == "佐藤"

    def test_get_logs_not_found(self, client):
        with patch("app.routers.clients.run_query", return_value=[]):
            resp = client.get("/api/clients/存在しない人/logs")

        assert resp.status_code == 404

    def test_get_logs_empty_logs(self, client):
        side_effects = [
            [{"n": "田中太郎"}],  # exists
            [],                     # no logs
        ]
        with patch("app.routers.clients.run_query", side_effect=side_effects):
            resp = client.get("/api/clients/田中太郎/logs")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_logs_custom_limit(self, client):
        side_effects = [
            [{"n": "テスト"}],
            [],
        ]
        with patch("app.routers.clients.run_query", side_effect=side_effects):
            resp = client.get("/api/clients/テスト/logs?limit=5")

        assert resp.status_code == 200

    def test_get_logs_limit_validation(self, client):
        """limit must be >= 1 and <= 200."""
        resp = client.get("/api/clients/テスト/logs?limit=0")
        assert resp.status_code == 422

        resp = client.get("/api/clients/テスト/logs?limit=201")
        assert resp.status_code == 422
