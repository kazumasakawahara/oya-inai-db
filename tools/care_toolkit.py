import json
from datetime import datetime, timedelta
from agno.tools import Toolkit
from lib.db_new_operations import resolve_client, run_query

class CareToolkit(Toolkit):
    def __init__(self):
        super().__init__(name="care_toolkit")
        self.register(self.analyze_feedback)
        self.register(self.add_care_preference)
        self.register(self.add_ng_action)

    def analyze_feedback(self, client_name: str, days_lookback: int = 30) -> str:
        """
        Analyze recent support logs to discover effective care strategies ('Excellent' or 'Good' outcomes)
        and suggest new CarePreferences.
        
        Args:
            client_name: Name of the client.
            days_lookback: How many days back to analyze (default 30).
        """
        client = resolve_client(client_name)
        if not client:
            return "Client not found."

        name = client.get('name')
        start_date = (datetime.now() - timedelta(days=days_lookback)).strftime("%Y-%m-%d")
        
        query = """
        MATCH (s:Supporter)-[:LOGGED]->(log:SupportLog)-[:ABOUT]->(c:Client)
        WHERE (c.name = $name OR c.clientId = $name)
          AND log.date >= date($start_date)
          AND (log.effectiveness CONTAINS 'Excellent' OR log.effectiveness CONTAINS 'Good' OR log.effectiveness CONTAINS '◎' OR log.effectiveness CONTAINS '○')
        RETURN 
            log.situation AS situation,
            log.action AS action,
            log.effectiveness AS effectiveness,
            s.name AS supporter
        ORDER BY log.date DESC
        """
        logs = run_query(query, {"name": name, "start_date": start_date})
        
        if not logs:
            return "No high-effectiveness logs found in the period."
            
        suggestions = []
        for log in logs:
            suggestions.append({
                "instruction": f"When {log['situation']}, try: {log['action']}",
                "reason": f"Proven effective by {log['supporter']} (Effect: {log['effectiveness']})"
            })
            
        return json.dumps({
            "client": name,
            "found_logs": len(logs),
            "suggestions": suggestions
        }, ensure_ascii=False, indent=2)

    def add_care_preference(self, client_name: str, situation: str, instruction: str, reason: str = "") -> str:
        """
        Registers a new CarePreference (tacit knowledge) to the database.
        Use this when you discover a success pattern or effective strategy.
        
        Args:
            client_name: Name of the client.
            situation: When to do this (e.g. "When panic occurs", "Before bath").
            instruction: What to do (e.g. "Wait 5 mins", "Show picture card").
            reason: Why effective or source (e.g. "Mother said so", "Proven effective in log").
        """
        client = resolve_client(client_name)
        if not client:
            return "Client not found."
            
        name = client.get('name')
        
        # Simple/Safe Cypher execution
        query = """
        MATCH (c:Client) WHERE c.name = $name
        MERGE (cp:CarePreference {category: $situation, instruction: $instruction})
        SET cp.priority = 'High', cp.reason = $reason, cp.updatedAt = datetime()
        MERGE (c)-[:REQUIRES]->(cp)
        RETURN cp
        """
        
        try:
            run_query(query, {
                "name": name,
                "situation": situation,
                "instruction": instruction,
                "reason": reason
            })
            return f"✅ Registered effective care: [{situation}] -> {instruction}"
        except Exception as e:
            return f"Error registering preference: {e}"

    def add_ng_action(self, client_name: str, action: str, reason: str, risk_level: str = "High") -> str:
        """
        Registers a new NgAction (Contraindication/Risk) to the database.
        Use this when a negative outcome occurs to prevent recurrence.
        
        Args:
            client_name: Name of the client.
            action: The action or situation to avoid (e.g. "Loud noises", "Giving milk").
            reason: Why it's bad (e.g. "Causes panic", "Allergy").
            risk_level: 'High', 'Medium', or 'Low' (default 'High').
        """
        client = resolve_client(client_name)
        if not client:
            return "Client not found."
        
        name = client.get('name')
        
        query = """
        MATCH (c:Client) WHERE c.name = $name
        MERGE (ng:NgAction {action: $action})
        SET ng.reason = $reason, ng.riskLevel = $risk_level, ng.updatedAt = datetime()
        MERGE (c)-[:MUST_AVOID]->(ng)
        RETURN ng
        """
        
        try:
            run_query(query, {
                "name": name,
                "action": action,
                "reason": reason,
                "risk_level": risk_level
            })
            return f"✅ Registered risk factor: Avoid [{action}] (Reason: {reason})"
        except Exception as e:
            return f"Error registering NgAction: {e}"

    def add_support_log(self, client_name: str, situation: str, action: str, effectiveness: str, note: str = "") -> str:
        """
        Registers a support log (Event/Intervention) to the database.
        Use this to record what happened and how it was handled.
        
        Args:
            client_name: Name of the client.
            situation: The situation or trigger (e.g. "Panic due to loud noise").
            action: The action taken (e.g. "Moved to quiet room").
            effectiveness: 'Effective', 'Ineffective', or 'Unknown'.
            note: Additional details.
        """
        # Create log data structure compatible with lib.db_operations
        log_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "situation": situation,
            "action": action,
            "effectiveness": effectiveness,
            "note": note,
            "supporter": "ClinicalAdvisor" # Auto-sign as AI Agent
        }
        
        from lib.db_new_operations import register_support_log
        result = register_support_log(log_data, client_name)
        
        if result['status'] == 'success':
            return f"✅ Logged: {situation} -> {action} ({effectiveness})"
        else:
            return f"Error logging: {result['message']}"
