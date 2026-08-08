"""Shared test fixtures for the API test suite.

All fixtures mock external dependencies (Neo4j, Gemini) so tests
run without any running services.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """TestClient with Neo4j driver mocked out during app lifespan."""
    with patch("app.lib.db_operations.get_driver") as mock_get_driver:
        mock_driver = MagicMock()
        mock_driver.verify_connectivity = MagicMock()
        mock_get_driver.return_value = mock_driver

        from app.main import app
        with TestClient(app) as c:
            yield c


@pytest.fixture
def mock_db():
    """Mock run_query to return empty results by default."""
    with patch("app.lib.db_operations.run_query", return_value=[]) as mock:
        yield mock


@pytest.fixture
def mock_db_unavailable():
    """Mock is_db_available to return False."""
    with patch("app.lib.db_operations.is_db_available", return_value=False):
        yield


@pytest.fixture
def sample_client_row():
    """Minimal client row as returned by a list query."""
    return {
        "name": "田中太郎",
        "dob": "1990-01-01",
        "blood_type": "A",
        "kana": "たなかたろう",
        "conditions": ["自閉スペクトラム症"],
    }


@pytest.fixture
def sample_client_detail_row():
    """Full client detail row as returned by the detail query."""
    return {
        "name": "田中太郎",
        "dob": "1990-01-01",
        "blood_type": "A",
        "conditions": [{"name": "自閉スペクトラム症", "diagnosedDate": "2010-01-01"}],
        "ng_actions": [
            {"action": "大声を出す", "reason": "パニック誘発", "riskLevel": "Panic"},
        ],
        "care_preferences": [
            {"category": "コミュニケーション", "instruction": "ゆっくり話す", "priority": "高"},
        ],
        "key_persons": [
            {"name": "田中花子", "relationship": "母", "phone": "090-1234-5678", "rank": 1},
        ],
        "certificates": [{"type": "療育手帳", "nextRenewalDate": "2026-06-01"}],
        "hospital": {"name": "中央病院", "phone": "03-1234-5678"},
        "guardian": {"name": "山田法律事務所", "type": "成年後見人"},
    }


@pytest.fixture
def sample_support_log_rows():
    """Support log rows as returned by the logs query."""
    return [
        {
            "date": "2026-04-01",
            "situation": "パニック",
            "action": "静かな部屋に移動",
            "effectiveness": "Effective",
            "note": "5分で落ち着いた",
            "supporter_name": "佐藤",
        },
        {
            "date": "2026-03-28",
            "situation": "日常記録",
            "action": "散歩同行",
            "effectiveness": "Neutral",
            "note": None,
            "supporter_name": "鈴木",
        },
    ]


@pytest.fixture
def mock_neo4j_driver():
    """Create a fully mocked Neo4j driver with session context manager."""
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.run = MagicMock(return_value=[])
    mock_driver = MagicMock()
    mock_driver.session = MagicMock(return_value=mock_session)
    return mock_driver
