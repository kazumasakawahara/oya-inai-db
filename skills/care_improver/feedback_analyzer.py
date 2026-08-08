
import os
import sys
import json
from datetime import datetime, timedelta

# Add parent directory to path to import lib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib.db_new_operations import resolve_client, run_query

def analyze_feedback(client_identifier: str, days_lookback: int = 30):
    """
    Analyze effective support logs to suggest care improvements.
    """
    client = resolve_client(client_identifier)
    if not client:
        print(f"Client not found: {client_identifier}")
        return

    client_name = client.get('name')
    print(f"[{datetime.now()}] Analyzing Feedback for: {client_name} (Last {days_lookback} days)...")

    # 1. Fetch Effective Logs
    # effectiveness: 'Excellent' (◎) or 'Good' (○)
    # Using simple string matching for now as per schema
    query = """
    MATCH (s:Supporter)-[:LOGGED]->(log:SupportLog)-[:ABOUT]->(c:Client)
    WHERE (c.name = $name OR c.clientId = $name)
      AND log.date >= date($start_date)
      AND (log.effectiveness CONTAINS 'Excellent' OR log.effectiveness CONTAINS 'Good' OR log.effectiveness CONTAINS '◎' OR log.effectiveness CONTAINS '○')
    RETURN 
        log.date AS date,
        log.situation AS situation,
        log.action AS action,
        log.effectiveness AS effectiveness,
        log.note AS note,
        s.name AS supporter
    ORDER BY log.date DESC
    """
    
    start_date = (datetime.now() - timedelta(days=days_lookback)).strftime("%Y-%m-%d")
    
    logs = run_query(query, {"name": client_name, "start_date": start_date})
    
    if not logs:
        print("No high-effectiveness logs found in the period.")
        return

    print(f"Found {len(logs)} effective support logs.")
    
    # 2. Generate Suggestions (Simple Heuristic: Just list them as candidates)
    # In a real agent, we would use LLM to clustering similar actions.
    # Here, we format them as a report.
    
    suggestions = []
    for log in logs:
        # Check if Date object needs conversion
        log_date = log['date']
        if hasattr(log_date, 'iso_format'):
            log_date = log_date.iso_format()
        else:
            log_date = str(log_date)

        suggestion = {
            "source_log_date": log_date,
            "category": "Suggested Care (Auto)", 
            "instruction": f"When {log['situation']}, try: {log['action']}",
            "reason": f"Proven effective by {log['supporter']} (Effect: {log['effectiveness']})",
            "priority": "Medium"
        }
        suggestions.append(suggestion)

    # 3. Output Report
    report = {
        "client": client_name,
        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
        "suggestions": suggestions
    }
    
    print("\n---------------------------------------------------")
    print(f"💡 Care Improvement Suggestions for {client_name}")
    print("---------------------------------------------------")
    
    for idx, item in enumerate(suggestions, 1):
        print(f"\n[Candidate {idx}]")
        print(f"  Situation: {item['instruction']}")
        print(f"  Evidence : {item['reason']}")
    
    print("\n---------------------------------------------------")
    print("To formalize these, register them as 'CarePreference' nodes.")
    
    return report

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze_feedback(sys.argv[1])
    else:
        print("Usage: python feedback_analyzer.py <ClientName>")
