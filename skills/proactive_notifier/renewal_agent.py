
import os
import sys
import json
from datetime import datetime, date, timedelta
from neo4j.time import Date as Neo4jDate

# Add parent directory to path to import lib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib.db_new_operations import run_query

LOG_FILE = "notifications.log"

def check_renewals(days_ahead=90):
    """
    Check for certificates expiring within `days_ahead`.
    """
    print(f"[{datetime.now()}] Running Renewal Check (Target: {days_ahead} days)...")
    
    query = """
    MATCH (c:Client)-[:HAS_CERTIFICATE]->(cert:Certificate)
    WHERE cert.nextRenewalDate IS NOT NULL
    WITH c, cert, cert.nextRenewalDate AS deadline
    WHERE deadline <= date($target_date) AND deadline >= date()
    RETURN 
        c.name AS client,
        cert.type AS cert_type,
        cert.grade AS grade,
        cert.nextRenewalDate AS deadline,
        duration.inDays(date(), cert.nextRenewalDate).days AS days_left
    ORDER BY days_left ASC
    """
    
    target_date = (date.today() + timedelta(days=days_ahead)).isoformat()
    
    results = run_query(query, {"target_date": target_date})
    
    alerts = []
    
    if not results:
        print("No upcoming renewals found.")
        return []

    for row in results:
        days_left = row['days_left']
        alert_level = "NOTICE"
        if days_left <= 30:
            alert_level = "CRITICAL"
        elif days_left <= 60:
            alert_level = "WARNING"
            
        # Handle Neo4j Date object
        deadline = row['deadline']
        if hasattr(deadline, 'iso_format'):
            deadline = deadline.iso_format()
        else:
            deadline = str(deadline)

        alert = {
            "timestamp": datetime.now().isoformat(),
            "level": alert_level,
            "title": f"更新期限アラート: {row['client']}",
            "body": f"「{row['cert_type']}」の期限が{days_left}日後({deadline})に迫っています。手続きの準備をしてください。",
            "data": row
        }
        alerts.append(alert)
        
    # Dispatch Alerts
    dispatch_alerts(alerts)
    return alerts

def dispatch_alerts(alerts):
    """
    Simulate Push Notification by writing to log and printing to console.
    """
    for alert in alerts:
        # Console output (Simulating Mobile Push)
        icon = "🔴" if alert['level'] == "CRITICAL" else "🟡" if alert['level'] == "WARNING" else "🟢"
        print(f"\n{icon} [PUSH NOTIFICATION] {alert['title']}")
        print(f"   {alert['body']}")
        
        # Log to file
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(alert, ensure_ascii=False, default=str) + "\n")
            
    if alerts:
        print(f"\nTotal {len(alerts)} alerts generated. Logged to {LOG_FILE}.")

if __name__ == "__main__":
    check_renewals()
