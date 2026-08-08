---
name: parent_support_db
description: Access the Post-Parent Support Database (Neo4j) to manage client profiles, check safety, and orchestrate support.
---

# Parent Support DB Skill

This skill allows you to interact with the "Post-Parent Support System" (Neo4j Graph Database).
Use this skill to answer questions about clients, check for emergency info (NG Actions), and manage deadlines.

## Tools

### 1. `search_emergency_info` (Safety First)
Search for critical safety information.
**Protocol**: ALWAYS use this first if the user mentions "panic", "emergency", "accident", or "hospital".
It prioritizes `NgAction` (Things to Avoid) and `CarePreference` (How to calm them down).

```bash
python skills/parent_support_db/scripts/db_client.py search_emergency "CLIENT_NAME" "SITUATION_KEYWORD"
```
*   `CLIENT_NAME`: Name of the person.
*   `SITUATION_KEYWORD`: Optional context (e.g., "panic", "meal", "bath").

### 2. `get_client_profile`
Retrieve the full profile of a client based on the 5 Pillars of the Manifesto.
Use this for general inquiries like "Tell me about Client X" or "Who is their guardian?".

```bash
python skills/parent_support_db/scripts/db_client.py get_profile "CLIENT_NAME"
```

### 3. `check_renewal_dates`
Check for upcoming expiration dates of Certificates (Techo) or Public Assistance.
Use this proactively to warn about administrative deadlines.

```bash
python skills/parent_support_db/scripts/db_client.py check_renewal [DAYS_AHEAD_INT]
```
*   `DAYS_AHEAD_INT`: Default is 90 days.

### 4. `run_cypher_query`
Run an arbitrary Read-Only Cypher query.
Use this ONLY if the other tools cannot answer the specific question (e.g., complex statistical aggregation).

```bash
python skills/parent_support_db/scripts/db_client.py run_cypher "MATCH (n:Client) RETURN n LIMIT 5"
```
**Schema Awareness**:
*   `(:Client)-[:MUST_AVOID]->(:NgAction)`
*   `(:Client)-[:REQUIRES]->(:CarePreference)`
*   `(:Client)-[:HAS_KEY_PERSON]->(:KeyPerson)`

## Usage Guidelines

1.  **Safety First**: If the request implies immediate risk, prioritize `search_emergency_info`.
2.  **Privacy**: Do not display PII (Phone numbers) unless explicitly asked in an authorized context.
3.  **Advocacy**: When reporting on a client, always mention their "Wishes" if available, to respect their autonomy.
