import json
from agno.agent import Agent
from agno.tools import Toolkit
from lib.db_new_operations import run_query

class ResilienceToolkit(Toolkit):
    def __init__(self):
        super().__init__(name="resilience_toolkit")
        self.register(self.analyze_transition_impact)
        self.register(self.suggest_alternatives)

    def analyze_transition_impact(self, key_person_name: str) -> str:
        """
        Analyze what roles are impacted if a specific KeyPerson becomes unavailable (e.g., hospitalized or deceased).
        Crucial for the 'Resilience' pillar (Plan B).
        
        Args:
            key_person_name: The name of the key person (e.g., 'Mother', 'Yamada Hanako') who is unavailable.
            
        Returns:
            JSON string containing the impact report, affected client, impacted roles, and advice.
        """
        print(f"🔍 Analyzing impact for: {key_person_name}...")
        
        # 0. Identify the Client associated with this KeyPerson
        client_res = run_query("""
            MATCH (kp:KeyPerson {name: $name})<-[:HAS_KEY_PERSON]-(c:Client)
            RETURN c.name as name
        """, {"name": key_person_name})
        
        client_name = client_res[0]['name'] if client_res else None
        
        # 1. Find roles fulfilled by this person
        roles = run_query("""
            MATCH (kp:KeyPerson {name: $name})-[:FULFILLS]->(role:CareRole)
            RETURN role.name as role_name, role.category as category
        """, {"name": key_person_name})
        
        if not roles:
            return json.dumps({"status": "no_roles_found", "message": f"{key_person_name} is not currently assigned any specific Care Roles in the graph."})
        
        impact_report = {
            "unavailable_person": key_person_name,
            "affected_client": client_name,
            "impacted_roles": [],
            "immediate_action_required": False
        }
        
        # 2. For each role, find potential alternatives
        for r in roles:
            role_name = r['role_name']
            category = r.get('category', '')
            
            role_info = {
                "role": role_name,
                "category": category,
                "alternatives": [],
                "advice": []
            }
            
            # --- SPECIAL LOGIC: Finance / Asset Management ---
            if category == 'Finance' or role_name in ['金銭管理', '財産管理']:
                # Check for existing Guardian
                guardians = []
                if client_name:
                    guardians = run_query("""
                        MATCH (c:Client {name: $name})-[:HAS_GUARDIAN]->(g:Guardian)
                        RETURN g.name as name, g.type as type, g.phone as phone
                    """, {"name": client_name})
                
                if guardians:
                    for g in guardians:
                        role_info["alternatives"].append({
                            "service_name": g['name'],
                            "type": f"Adult Guardian ({g['type']})",
                            "phone": g.get('phone', 'N/A'),
                            "priority": "High"
                        })
                    role_info["advice"].append("成年後見人が登録されています。直ちに連絡を取り、業務を引き継いでください。")
                else:
                    impact_report["immediate_action_required"] = True
                    role_info["alternatives"].append({
                        "service_name": "社会福祉協議会",
                        "type": "日常生活自立支援事業",
                        "priority": "Medium (Fallback)"
                    })
                    
                    core_agencies = run_query("""
                        MATCH (s:Service {type: 'CoreAgency'})
                        RETURN s.name as name, s.phone as phone
                    """)
                    
                    agency_text = "お住まいの自治体の「中核機関（成年後見支援センター）」"
                    if core_agencies:
                         agency = core_agencies[0]
                         agency_text = f"中核機関である **{agency['name']}（{agency.get('phone', '連絡先登録なし')}）**"
    
                    role_info["advice"].append("成年後見人が不在です。社会福祉協議会による「日常生活自立支援事業」の利用を検討してください。")
                    role_info["advice"].append(f"並行して、{agency_text} へ相談してください。")
            
            else:
                # --- Generic Logic ---
                alternatives = run_query("""
                    MATCH (s:Service)-[:CAN_FULFILL]->(role:CareRole {name: $role})
                    RETURN s.name as service_name, s.type as type, s.phone as phone
                """, {"role": role_name})
                
                for alt in alternatives:
                    role_info["alternatives"].append(alt)
                    
                if len(role_info["alternatives"]) == 0:
                    impact_report["immediate_action_required"] = True
                    role_info["advice"].append("代替サービスが見つかりません。相談支援専門員に至急相談してください。")
    
            impact_report["impacted_roles"].append(role_info)
            
        return json.dumps(impact_report, indent=2, ensure_ascii=False)

    def suggest_alternatives(self, role_name: str) -> str:
        """
        Suggest specific alternative services for a given care role.
        
        Args:
            role_name: The name of the role (e.g., 'Mornign Care', 'Transport').
        """
        candidates = run_query("""
            MATCH (s:Service)-[:CAN_FULFILL]->(r:CareRole {name: $role})
            RETURN s.name as name, s.type as type, s.location as location, s.capacity as capacity
        """, {"role": role_name})
        return json.dumps(candidates, indent=2, ensure_ascii=False)
