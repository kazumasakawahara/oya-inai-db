"""queries/as_of_queries.cypher の時点照会を実 DB で検証する（技術仕様 §4-1 テスト (e)）。

NEO4J_TEST_URI が無ければ skip する（本番 DB に向けないこと。合成データのみ使い、
終了時に自分が作ったノードだけを DETACH DELETE する）。

  NEO4J_TEST_URI=bolt://localhost:7687 NEO4J_TEST_USER=neo4j NEO4J_TEST_PASSWORD=... \
      uv run pytest tests/integration/test_as_of_queries.py
"""

import os
import uuid
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
QUERY_FILE = REPO_ROOT / "queries" / "as_of_queries.cypher"

pytestmark = pytest.mark.skipif(
    not os.environ.get("NEO4J_TEST_URI"),
    reason="NEO4J_TEST_URI 未設定（実 DB テストは明示的に接続先を与えたときだけ走らせる）",
)


def _queries() -> dict[str, str]:
    text = QUERY_FILE.read_text(encoding="utf-8")
    # コメント行を落としてから ";" で分割する（コメント中の ";" で割らない）
    code = "\n".join(l for l in text.splitlines() if not l.strip().startswith("//"))
    found = {}
    for part in code.split(";"):
        body = part.strip()
        if not body:
            continue
        if "NgAction" in body:
            found["ng"] = body
        elif "HAS_KEY_PERSON" in body:
            found["kp"] = body
    assert set(found) == {"ng", "kp"}, "as_of_queries.cypher の構成が変わっています"
    return found


@pytest.fixture(scope="module")
def driver():
    from neo4j import GraphDatabase

    d = GraphDatabase.driver(
        os.environ["NEO4J_TEST_URI"],
        auth=(os.environ.get("NEO4J_TEST_USER", "neo4j"), os.environ.get("NEO4J_TEST_PASSWORD", "")),
    )
    d.verify_connectivity()
    yield d
    d.close()


@pytest.fixture
def synthetic_client(driver):
    """合成データのクライアント1名。禁忌1件（2025-01-10 登録・2025-12-01 で解除）と
    キーパーソン交代1回（2025-10-01）。"""
    name = f"合成テスト_{uuid.uuid4().hex[:8]}"
    with driver.session() as s:
        s.run(
            """
            CREATE (c:Client {name: $name})
            CREATE (c)-[:MUST_AVOID]->(:NgAction {
                action: '合成禁忌', riskLevel: 'Panic', status: 'Inactive', source: '記録のみ',
                lastConfirmedAt: date('2025-12-01'), registeredAt: date('2025-01-10'),
                validTo: date('2025-12-01')})
            CREATE (c)-[:HAS_KEY_PERSON {rank: 1, startDate: date('2025-01-01'),
                                         endDate: date('2025-10-01'), status: 'Inactive'}]
                   ->(:KeyPerson {name: $old_kp, relationship: '母'})
            CREATE (c)-[:HAS_KEY_PERSON {rank: 1, startDate: date('2025-10-01'), status: 'Active'}]
                   ->(:KeyPerson {name: $new_kp, relationship: '兄'})
            """,
            {"name": name, "old_kp": f"{name}_旧KP", "new_kp": f"{name}_新KP"},
        )
    yield name
    with driver.session() as s:
        s.run(
            "MATCH (c:Client {name: $name}) OPTIONAL MATCH (c)-->(x) DETACH DELETE c, x",
            {"name": name},
        )


def _run(driver, cypher, **params):
    with driver.session() as s:
        return [r.data() for r in s.run(cypher, params)]


class TestEmptyDatabase:
    def test_ng_query_returns_nothing_for_unknown_client(self, driver):
        rows = _run(driver, _queries()["ng"], name=f"存在しない_{uuid.uuid4().hex}", asOf="2025-09-01")
        assert rows == []

    def test_kp_query_returns_nothing_for_unknown_client(self, driver):
        rows = _run(driver, _queries()["kp"], name=f"存在しない_{uuid.uuid4().hex}", asOf="2025-09-01")
        assert rows == []


class TestOneRecord:
    def test_ng_valid_on_as_of_date_is_returned(self, driver, synthetic_client):
        rows = _run(driver, _queries()["ng"], name=synthetic_client, asOf="2025-09-01")
        assert [r["action"] for r in rows] == ["合成禁忌"]

    def test_ng_before_registration_is_not_returned(self, driver, synthetic_client):
        assert _run(driver, _queries()["ng"], name=synthetic_client, asOf="2024-12-31") == []

    def test_ng_after_valid_to_is_not_returned(self, driver, synthetic_client):
        assert _run(driver, _queries()["ng"], name=synthetic_client, asOf="2026-01-01") == []

    def test_kp_before_replacement_is_the_old_person(self, driver, synthetic_client):
        rows = _run(driver, _queries()["kp"], name=synthetic_client, asOf="2025-09-01")
        assert [r["relationship"] for r in rows] == ["母"]

    def test_kp_after_replacement_is_the_new_person(self, driver, synthetic_client):
        rows = _run(driver, _queries()["kp"], name=synthetic_client, asOf="2025-11-01")
        assert [r["relationship"] for r in rows] == ["兄"]
