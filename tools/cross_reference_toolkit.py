import json
from agno.tools import Toolkit
from lib.db_new_operations import resolve_client, run_query

class CrossReferenceToolkit(Toolkit):
    def __init__(self):
        super().__init__(name="cross_reference_toolkit")
        self.register(self.get_internal_context)

    def get_internal_context(self, client_name: str, behavior_keyword: str) -> str:
        """
        Retrieve internal context from Neo4j to cross-reference with external research.
        Fetches:
        1. Past SupportLogs related to similar situations (Success/Failures).
        2. Relevant CarePreferences (Preferences).
        3. Relevant NgActions (Contraindications).
        
        Args:
            client_name: Name of the client.
            behavior_keyword: Keyword related to the behavior (e.g., "food", "panic", "refusal").
            
        Returns:
            JSON string containing the internal context.
        """
        print(f"🏥 Retrieving internal context for: {client_name} (Keyword: {behavior_keyword})...")
        
        client = resolve_client(client_name)
        if not client:
            return "Client not found."
            
        name = client.get('name')
        
        # 1. Relevant Logs
        logs = run_query("""
            MATCH (s:Supporter)-[:LOGGED]->(log:SupportLog)-[:ABOUT]->(c:Client)
            WHERE (c.name = $name OR c.clientId = $name)
              AND (log.situation CONTAINS $keyword OR log.action CONTAINS $keyword)
            RETURN log.date, log.situation, log.action, log.effectiveness, log.note
            ORDER BY log.date DESC
            LIMIT 5
        """, {"name": name, "keyword": behavior_keyword})
        
        # 2. Care Preferences
        prefs = run_query("""
            MATCH (c:Client)-[:REQUIRES]->(cp:CarePreference)
            WHERE (c.name = $name OR c.clientId = $name)
              AND (cp.category CONTAINS $keyword OR cp.instruction CONTAINS $keyword)
            RETURN cp.category, cp.instruction, cp.priority
        """, {"name": name, "keyword": behavior_keyword})
        
        # 3. NgActions
        ngs = run_query("""
            MATCH (c:Client)-[:MUST_AVOID]->(ng:NgAction)
            WHERE (c.name = $name OR c.clientId = $name)
              AND (ng.action CONTAINS $keyword OR ng.reason CONTAINS $keyword)
            RETURN ng.action, ng.reason, ng.riskLevel
        """, {"name": name, "keyword": behavior_keyword})
        
        context = {
            "client": name,
            "keyword": behavior_keyword,
            "past_experiences": logs,
            "preferences": prefs,
            "contraindications": ngs
        }
        
        return json.dumps(context, ensure_ascii=False, indent=2, default=str)
