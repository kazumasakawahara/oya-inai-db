"""
親亡き後支援データベース - 仮名化モジュール
個人識別情報（PII）を分離し、運用データと分けて管理

設計思想:
- Client ノードは clientId で識別（氏名を持たない）
- Identity ノードに氏名・生年月日を分離
- 表示時のみ結合（アクセス制御可能）
- 既存の関係はそのまま維持
"""

import os
import uuid
import sys
from datetime import datetime
from typing import Optional

# --- ログ出力 ---
def log(message: str, level: str = "INFO"):
    """ログ出力（標準エラー出力）"""
    sys.stderr.write(f"[Pseudonymization:{level}] {message}\n")
    sys.stderr.flush()


def generate_client_id() -> str:
    """
    クライアントIDを生成
    形式: c-{uuid4の先頭8文字}
    """
    return f"c-{uuid.uuid4().hex[:8]}"


def generate_display_code(sequence: int) -> str:
    """
    表示用コードを生成
    形式: A-001, A-002, ... (連番)
    """
    return f"A-{sequence:03d}"


# =============================================================================
# マイグレーション関連
# =============================================================================

def migrate_to_pseudonymized_schema(driver) -> dict:
    """
    既存データを仮名化スキーマに移行

    処理内容:
    1. 各Clientノードに clientId を付与
    2. Identity ノードを作成し、name/dob を移動
    3. HAS_IDENTITY 関係を作成
    4. Client ノードから name を削除（dob は Identity に移動）

    Returns:
        移行結果のサマリー
    """
    migrated_count = 0
    skipped_count = 0
    errors = []

    with driver.session() as session:
        # Step 1: clientId がない Client を取得
        clients = session.run("""
            MATCH (c:Client)
            WHERE c.clientId IS NULL
            RETURN c.name as name, c.dob as dob, c.bloodType as bloodType,
                   id(c) as nodeId
        """).data()

        if not clients:
            log("移行対象のClientがありません（既に移行済みまたはデータなし）")
            return {"migrated": 0, "skipped": 0, "errors": []}

        log(f"移行対象: {len(clients)} 件")

        # Step 2: 連番取得（既存の最大値から続ける）
        max_seq_result = session.run("""
            MATCH (c:Client)
            WHERE c.displayCode IS NOT NULL
            RETURN max(toInteger(substring(c.displayCode, 2))) as maxSeq
        """).single()
        current_seq = (max_seq_result['maxSeq'] or 0) + 1 if max_seq_result else 1

        # Step 3: 各 Client を移行
        for client in clients:
            try:
                client_id = generate_client_id()
                display_code = generate_display_code(current_seq)
                name = client['name']
                dob = client['dob']
                node_id = client['nodeId']

                # Client に clientId と displayCode を設定
                session.run("""
                    MATCH (c:Client)
                    WHERE id(c) = $nodeId
                    SET c.clientId = $clientId,
                        c.displayCode = $displayCode,
                        c.migratedAt = datetime()
                """, {
                    "nodeId": node_id,
                    "clientId": client_id,
                    "displayCode": display_code
                })

                # Identity ノードを作成
                session.run("""
                    MATCH (c:Client {clientId: $clientId})
                    CREATE (i:Identity {
                        clientId: $clientId,
                        name: $name,
                        dob: $dob,
                        createdAt: datetime()
                    })
                    CREATE (c)-[:HAS_IDENTITY]->(i)
                """, {
                    "clientId": client_id,
                    "name": name,
                    "dob": dob
                })

                log(f"移行完了: {name} → {display_code} ({client_id})")
                migrated_count += 1
                current_seq += 1

            except Exception as e:
                error_msg = f"移行エラー ({client['name']}): {str(e)}"
                log(error_msg, "ERROR")
                errors.append(error_msg)

        # Step 4: 移行完了後、Client から name を削除（オプション - コメントアウト）
        # 安全のため、最初は name を残しておく
        # session.run("""
        #     MATCH (c:Client)
        #     WHERE c.clientId IS NOT NULL
        #     REMOVE c.name, c.dob
        # """)

    log(f"移行完了: {migrated_count} 件, スキップ: {skipped_count} 件, エラー: {len(errors)} 件")

    return {
        "migrated": migrated_count,
        "skipped": skipped_count,
        "errors": errors
    }


def create_name_index(driver):
    """
    Identity.name にインデックスを作成（検索高速化）
    """
    with driver.session() as session:
        session.run("CREATE INDEX identity_name IF NOT EXISTS FOR (i:Identity) ON (i.name)")
        session.run("CREATE INDEX client_id IF NOT EXISTS FOR (c:Client) ON (c.clientId)")
        session.run("CREATE INDEX identity_client_id IF NOT EXISTS FOR (i:Identity) ON (i.clientId)")
    log("インデックス作成完了")


# =============================================================================
# クエリヘルパー（仮名化対応）
# =============================================================================

def get_client_with_identity(driver, client_id: str) -> Optional[dict]:
    """
    clientId から Client + Identity 情報を取得

    Returns:
        {
            "clientId": "c-xxxx",
            "displayCode": "A-001",
            "name": "山田健太",
            "dob": "1990-01-15",
            "bloodType": "A"
        }
    """
    with driver.session() as session:
        result = session.run("""
            MATCH (c:Client {clientId: $clientId})-[:HAS_IDENTITY]->(i:Identity)
            RETURN c.clientId as clientId,
                   c.displayCode as displayCode,
                   c.bloodType as bloodType,
                   i.name as name,
                   i.dob as dob
        """, {"clientId": client_id}).single()

        return dict(result) if result else None


def get_client_by_name(driver, name: str) -> Optional[dict]:
    """
    氏名から Client + Identity 情報を取得（後方互換性）

    注: 本番運用では氏名検索を制限することを推奨
    """
    with driver.session() as session:
        result = session.run("""
            MATCH (c:Client)-[:HAS_IDENTITY]->(i:Identity)
            WHERE i.name CONTAINS $name
            RETURN c.clientId as clientId,
                   c.displayCode as displayCode,
                   c.bloodType as bloodType,
                   i.name as name,
                   i.dob as dob
            LIMIT 1
        """, {"name": name}).single()

        return dict(result) if result else None


def get_client_id_by_name(driver, name: str) -> Optional[str]:
    """
    氏名から clientId を取得
    """
    with driver.session() as session:
        result = session.run("""
            MATCH (c:Client)-[:HAS_IDENTITY]->(i:Identity {name: $name})
            RETURN c.clientId as clientId
        """, {"name": name}).single()

        return result['clientId'] if result else None


def resolve_client_identifier(driver, identifier: str) -> Optional[dict]:
    """
    様々な識別子から Client を解決

    対応する識別子:
    - clientId (c-xxxx)
    - displayCode (A-001)
    - name (山田健太) ← 後方互換性

    Returns:
        {"clientId": "c-xxxx", "name": "山田健太", ...}
    """
    with driver.session() as session:
        # clientId で検索
        if identifier.startswith("c-"):
            result = session.run("""
                MATCH (c:Client {clientId: $id})-[:HAS_IDENTITY]->(i:Identity)
                RETURN c.clientId as clientId, c.displayCode as displayCode,
                       c.bloodType as bloodType, i.name as name, i.dob as dob
            """, {"id": identifier}).single()
            if result:
                return dict(result)

        # displayCode で検索
        if identifier.startswith("A-"):
            result = session.run("""
                MATCH (c:Client {displayCode: $code})-[:HAS_IDENTITY]->(i:Identity)
                RETURN c.clientId as clientId, c.displayCode as displayCode,
                       c.bloodType as bloodType, i.name as name, i.dob as dob
            """, {"code": identifier}).single()
            if result:
                return dict(result)

        # 氏名で検索（後方互換性）
        result = session.run("""
            MATCH (c:Client)-[:HAS_IDENTITY]->(i:Identity)
            WHERE i.name = $name OR c.name = $name
            RETURN c.clientId as clientId, c.displayCode as displayCode,
                   c.bloodType as bloodType, i.name as name, i.dob as dob
        """, {"name": identifier}).single()

        return dict(result) if result else None


def list_clients_with_identity(driver, include_pii: bool = True) -> list:
    """
    クライアント一覧を取得

    Args:
        include_pii: True の場合は氏名を含む、False の場合は displayCode のみ

    Returns:
        [{"clientId": "c-xxx", "displayCode": "A-001", "name": "山田健太"}, ...]
    """
    with driver.session() as session:
        if include_pii:
            results = session.run("""
                MATCH (c:Client)
                OPTIONAL MATCH (c)-[:HAS_IDENTITY]->(i:Identity)
                RETURN c.clientId as clientId,
                       c.displayCode as displayCode,
                       COALESCE(i.name, c.name) as name
                ORDER BY c.displayCode
            """).data()
        else:
            results = session.run("""
                MATCH (c:Client)
                RETURN c.clientId as clientId,
                       c.displayCode as displayCode
                ORDER BY c.displayCode
            """).data()

        return results


# =============================================================================
# 新規クライアント登録（仮名化対応）
# =============================================================================

def create_client_with_identity(
    driver,
    name: str,
    dob: str = None,
    blood_type: str = None
) -> dict:
    """
    新規クライアントを仮名化スキーマで作成

    Returns:
        {"clientId": "c-xxxx", "displayCode": "A-001", "name": "山田健太"}
    """
    client_id = generate_client_id()

    with driver.session() as session:
        # 連番取得
        max_seq_result = session.run("""
            MATCH (c:Client)
            WHERE c.displayCode IS NOT NULL
            RETURN max(toInteger(substring(c.displayCode, 2))) as maxSeq
        """).single()
        current_seq = (max_seq_result['maxSeq'] or 0) + 1 if max_seq_result else 1
        display_code = generate_display_code(current_seq)

        # Client ノード作成
        session.run("""
            CREATE (c:Client {
                clientId: $clientId,
                displayCode: $displayCode,
                bloodType: $bloodType,
                createdAt: datetime()
            })
        """, {
            "clientId": client_id,
            "displayCode": display_code,
            "bloodType": blood_type
        })

        # Identity ノード作成
        session.run("""
            MATCH (c:Client {clientId: $clientId})
            CREATE (i:Identity {
                clientId: $clientId,
                name: $name,
                dob: CASE WHEN $dob IS NOT NULL THEN date($dob) ELSE null END,
                createdAt: datetime()
            })
            CREATE (c)-[:HAS_IDENTITY]->(i)
        """, {
            "clientId": client_id,
            "name": name,
            "dob": dob
        })

        log(f"クライアント作成: {name} → {display_code} ({client_id})")

        return {
            "clientId": client_id,
            "displayCode": display_code,
            "name": name
        }


# =============================================================================
# 出力マスキング機能
# =============================================================================

# マスク対象となるフィールド名のデフォルト定義
_DEFAULT_MASK_FIELDS = {
    "name": "name",
    "クライアント": "name",
    "支援者": "name",
    "操作者": "name",
}


class Pseudonymizer:
    """
    クエリ結果の PII をマスクする出力フィルター

    enabled=False の場合はすべてパススルーする（ダミーモード）。
    Neo4j 内のデータは一切変更せず、Python 側の表示レイヤーでのみ適用。
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    # ----- 単一値マスク -----

    def mask_name(self, name: str) -> str:
        """
        氏名をマスクする（姓のみ表示 + 伏字）

        例: "山田健太" → "山田●●"
            "田中"     → "田●"
            1文字      → "●"
        """
        if not self.enabled or not name:
            return name

        if len(name) <= 1:
            return "●"
        # 姓＝先頭1文字、名＝残りを伏字
        return name[0] + "●" * (len(name) - 1)

    def mask_phone(self, phone: str) -> str:
        """
        電話番号をマスクする（下4桁を伏字）

        例: "090-1234-5678" → "090-1234-****"
        """
        if not self.enabled or not phone:
            return phone

        digits_only = phone.replace("-", "").replace(" ", "")
        if len(digits_only) <= 4:
            return "****"
        return phone[:-4] + "****"

    # ----- レコード一括マスク -----

    def mask_records(
        self,
        records: list[dict],
        field_rules: dict | None = None,
    ) -> list[dict]:
        """
        クエリ結果のレコードリストにマスクを適用

        Args:
            records: run_query() の戻り値（dict のリスト）
            field_rules: フィールド名 → マスク種別 のマッピング
                         None の場合はデフォルトルールを使用
                         例: {"name": "name", "phone": "phone"}

        Returns:
            マスク済みレコードのリスト（元のリストは変更しない）
        """
        if not self.enabled or not records:
            return records

        rules = field_rules or _DEFAULT_MASK_FIELDS
        masked = []

        for record in records:
            row = dict(record)  # shallow copy
            for field, mask_type in rules.items():
                if field in row and row[field]:
                    if mask_type == "name":
                        row[field] = self.mask_name(str(row[field]))
                    elif mask_type == "phone":
                        row[field] = self.mask_phone(str(row[field]))
            masked.append(row)

        return masked


# シングルトンインスタンス
_pseudonymizer_instance: Pseudonymizer | None = None


def get_pseudonymizer() -> Pseudonymizer:
    """
    Pseudonymizer のシングルトンインスタンスを取得

    PSEUDONYMIZATION_ENABLED 環境変数に基づいて enabled を設定。
    """
    global _pseudonymizer_instance
    if _pseudonymizer_instance is None:
        enabled = os.getenv(
            "PSEUDONYMIZATION_ENABLED", "false"
        ).lower() == "true"
        _pseudonymizer_instance = Pseudonymizer(enabled=enabled)
    return _pseudonymizer_instance
