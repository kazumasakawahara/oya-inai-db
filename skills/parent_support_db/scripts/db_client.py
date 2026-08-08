
"""
Script used by the parent_support_db skill to interact with Neo4j.
Refactored from server.py to be script-callable.
"""

import os
import sys
import json
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Add project root to sys.path to allow importing from lib if needed
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

# --- Helpers ---
def calculate_age(birth_date) -> int | None:
    if birth_date is None:
        return None
    if hasattr(birth_date, 'to_native'):
        birth_date = birth_date.to_native()
    elif isinstance(birth_date, str):
        try:
            birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None
    if not isinstance(birth_date, date):
        return None
    today = date.today()
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age if age >= 0 else None

def format_dob_with_age(dob) -> str:
    if dob is None:
        return "不明"
    if hasattr(dob, 'to_native'):
        dob = dob.to_native()
    age = calculate_age(dob)
    if isinstance(dob, date):
        dob_str = dob.strftime("%Y-%m-%d")
    else:
        dob_str = str(dob)
    if age is not None:
        return f"{dob_str}（{age}歳）"
    return dob_str

# --- DB Connection ---
def get_driver():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    return GraphDatabase.driver(uri, auth=(user, password))

# --- Main Functions (ported from server.py) ---

def run_cypher_query(cypher: str) -> str:
    driver = get_driver()
    try:
        with driver.session() as session:
            result = session.run(cypher)
            data = [record.data() for record in result]
            if not data:
                return "検索結果: 0件"
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return f"Cypher実行エラー: {e}"

def search_emergency_info(client_name: str, situation: str = "") -> str:
    driver = get_driver()
    try:
        query = """
        // 1. 禁忌事項（最優先）
        MATCH (c:Client)
        WHERE c.name CONTAINS $name
        OPTIONAL MATCH (c)-[:MUST_AVOID]->(ng:NgAction)
        WHERE $situation = '' OR ng.action CONTAINS $situation
        OPTIONAL MATCH (ng)-[:IN_CONTEXT]->(ngCon:Condition)
        WITH c, collect(DISTINCT {
            action: ng.action,
            reason: ng.reason,
            riskLevel: ng.riskLevel,
            context: ngCon.name
        }) AS ngActions

        // 2. 推奨ケア
        OPTIONAL MATCH (c)-[:REQUIRES]->(cp:CarePreference)
        WHERE $situation = '' OR cp.category CONTAINS $situation
        OPTIONAL MATCH (cp)-[:ADDRESSES]->(cpCon:Condition)
        WITH c, ngActions, collect(DISTINCT {
            category: cp.category,
            instruction: cp.instruction,
            priority: cp.priority,
            forCondition: cpCon.name
        }) AS carePrefs

        // 3. 緊急連絡先（ランク順）
        OPTIONAL MATCH (c)-[kpRel:HAS_KEY_PERSON]->(kp:KeyPerson)
        WITH c, ngActions, carePrefs, collect(DISTINCT {
            rank: kpRel.rank,
            name: kp.name,
            relationship: kp.relationship,
            phone: kp.phone,
            role: kp.role
        }) AS keyPersons

        // 4. かかりつけ医
        OPTIONAL MATCH (c)-[:TREATED_AT]->(h:Hospital)
        WITH c, ngActions, carePrefs, keyPersons, collect(DISTINCT {
            name: h.name,
            specialty: h.specialty,
            phone: h.phone,
            doctor: h.doctor
        }) AS hospitals

        // 5. 法的代理人
        OPTIONAL MATCH (c)-[:HAS_LEGAL_REP]->(g:Guardian)

        RETURN
            c.name AS client,
            c.dob AS dob,
            c.bloodType AS bloodType,
            ngActions AS 禁忌事項_最優先,
            carePrefs AS 推奨ケア,
            keyPersons AS 緊急連絡先,
            hospitals AS かかりつけ医,
            collect(DISTINCT {
                name: g.name,
                type: g.type,
                phone: g.phone
            }) AS 法的代理人
        """
        with driver.session() as session:
            result = session.run(query, name=client_name, situation=situation or '')
            data = [record.data() for record in result]
            
            if not data or not data[0].get('client'):
                return f"'{client_name}' に該当するクライアントが見つかりませんでした。"

            dob = data[0].get('dob')
            dob_with_age = format_dob_with_age(dob)

            response = {
                "⚠️ 緊急対応情報": data[0].get('client'),
                "生年月日（年齢）": dob_with_age,
                "血液型": data[0].get('bloodType'),
                "🚫 1. 禁忌事項（絶対にしないこと）": [x for x in data[0].get('禁忌事項_最優先', []) if x.get('action')],
                "✅ 2. 推奨ケア（こうすると落ち着く）": [x for x in data[0].get('推奨ケア', []) if x.get('instruction')],
                "📞 3. 緊急連絡先": sorted([x for x in data[0].get('緊急連絡先', []) if x.get('name')], key=lambda x: x.get('rank', 99)),
                "🏥 4. かかりつけ医": [x for x in data[0].get('かかりつけ医', []) if x.get('name')],
                "⚖️ 5. 法的代理人": [x for x in data[0].get('法的代理人', []) if x.get('name')]
            }
            return json.dumps(response, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return f"エラーが発生しました: {e}"

def get_client_profile(client_name: str) -> str:
    driver = get_driver()
    try:
        query = """
        MATCH (c:Client)
        WHERE c.name CONTAINS $name
        
        OPTIONAL MATCH (c)-[:HAS_HISTORY]->(h:LifeHistory)
        OPTIONAL MATCH (c)-[:HAS_WISH]->(w:Wish)
        
        OPTIONAL MATCH (c)-[:HAS_CONDITION]->(con:Condition)
        OPTIONAL MATCH (c)-[:REQUIRES]->(cp:CarePreference)
        OPTIONAL MATCH (c)-[:MUST_AVOID]->(ng:NgAction)
        
        OPTIONAL MATCH (c)-[:HAS_CERTIFICATE]->(cert:Certificate)
        OPTIONAL MATCH (c)-[:RECEIVES]->(pa:PublicAssistance)
        
        OPTIONAL MATCH (c)-[kpRel:HAS_KEY_PERSON]->(kp:KeyPerson)
        OPTIONAL MATCH (c)-[:HAS_LEGAL_REP]->(g:Guardian)
        OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(s:Supporter)
        OPTIONAL MATCH (c)-[:TREATED_AT]->(hosp:Hospital)
        
        RETURN 
            c.name AS 氏名,
            c.dob AS 生年月日,
            c.bloodType AS 血液型,
            collect(DISTINCT {era: h.era, episode: h.episode}) AS 生育歴,
            collect(DISTINCT {content: w.content, status: w.status}) AS 願い,
            collect(DISTINCT {name: con.name, status: con.status}) AS 特性_診断,
            collect(DISTINCT {category: cp.category, instruction: cp.instruction, priority: cp.priority}) AS 配慮事項,
            collect(DISTINCT {action: ng.action, reason: ng.reason, riskLevel: ng.riskLevel}) AS 禁忌事項,
            collect(DISTINCT {type: cert.type, grade: cert.grade, nextRenewalDate: cert.nextRenewalDate}) AS 手帳_受給者証,
            collect(DISTINCT {type: pa.type, grade: pa.grade}) AS 公的扶助,
            collect(DISTINCT {rank: kpRel.rank, name: kp.name, relationship: kp.relationship, phone: kp.phone, role: kp.role}) AS キーパーソン,
            collect(DISTINCT {name: g.name, type: g.type, phone: g.phone}) AS 後見人等,
            collect(DISTINCT {name: s.name, role: s.role, organization: s.organization}) AS 支援者,
            collect(DISTINCT {name: hosp.name, specialty: hosp.specialty, phone: hosp.phone}) AS 医療機関
        """
        with driver.session() as session:
            result = session.run(query, name=client_name)
            data = [record.data() for record in result]
            
            if not data or not data[0].get('氏名'):
                return f"'{client_name}' に該当するクライアントが見つかりませんでした。"
            
            profile = data[0]
            dob_with_age = format_dob_with_age(profile.get('生年月日'))

            clean_profile = {
                "【基本情報】": {
                    "氏名": profile.get('氏名'),
                    "生年月日（年齢）": dob_with_age,
                    "血液型": profile.get('血液型')
                },
                "【第1の柱：本人性】": {
                    "生育歴": [x for x in profile.get('生育歴', []) if x.get('episode')],
                    "願い": [x for x in profile.get('願い', []) if x.get('content')]
                },
                "【第2の柱：ケアの暗黙知】": {
                    "特性・診断": [x for x in profile.get('特性_診断', []) if x.get('name')],
                    "配慮事項": [x for x in profile.get('配慮事項', []) if x.get('instruction')],
                    "🚫 禁忌事項": [x for x in profile.get('禁忌事項', []) if x.get('action')]
                },
                "【第3の柱：法的基盤】": {
                    "手帳・受給者証": [x for x in profile.get('手帳_受給者証', []) if x.get('type')],
                    "公的扶助": [x for x in profile.get('公的扶助', []) if x.get('type')]
                },
                "【第4の柱：危機管理ネットワーク】": {
                    "キーパーソン": sorted([x for x in profile.get('キーパーソン', []) if x.get('name')], key=lambda x: x.get('rank', 99)),
                    "後見人等": [x for x in profile.get('後見人等', []) if x.get('name')],
                    "支援者": [x for x in profile.get('支援者', []) if x.get('name')],
                    "医療機関": [x for x in profile.get('医療機関', []) if x.get('name')]
                }
            }
            return json.dumps(clean_profile, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return f"エラーが発生しました: {e}"

def check_renewal_dates(days_ahead: int = 90) -> str:
    driver = get_driver()
    try:
        query = """
        MATCH (c:Client)-[:HAS_CERTIFICATE]->(cert:Certificate)
        WHERE cert.nextRenewalDate IS NOT NULL
        WITH c, cert, duration.inDays(date(), cert.nextRenewalDate).days AS daysUntilRenewal
        WHERE daysUntilRenewal <= $days AND daysUntilRenewal >= 0
        RETURN
            c.name AS クライアント,
            cert.type AS 証明書種類,
            cert.grade AS 等級,
            cert.nextRenewalDate AS 更新期限,
            daysUntilRenewal AS 残り日数
        ORDER BY daysUntilRenewal ASC
        """
        with driver.session() as session:
            result = session.run(query, days=days_ahead)
            data = [record.data() for record in result]
            if not data:
                return f"{days_ahead}日以内に更新期限を迎える証明書はありません。"
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return f"エラー: {e}"

# --- CLI Handling ---

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python db_client.py <command> [args...]")
        sys.exit(1)

    command = sys.argv[1]
    
    if command == "run_cypher":
        if len(sys.argv) < 3:
            print("Usage: run_cypher <query>")
            sys.exit(1)
        print(run_cypher_query(sys.argv[2]))

    elif command == "search_emergency":
        if len(sys.argv) < 3:
            print("Usage: search_emergency <client_name> [situation]")
            sys.exit(1)
        situation = sys.argv[3] if len(sys.argv) > 3 else ""
        print(search_emergency_info(sys.argv[2], situation))
    
    elif command == "get_profile":
        if len(sys.argv) < 3:
            print("Usage: get_profile <client_name>")
            sys.exit(1)
        print(get_client_profile(sys.argv[2]))
        
    elif command == "check_renewal":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
        print(check_renewal_dates(days))
        
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
