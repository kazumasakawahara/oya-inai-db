import os
import json
import sys
from typing import List, Optional, Dict, Any
from datetime import datetime, date

from agno.agent import Agent
from agno.tools import Toolkit
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

class Neo4jToolkit(Toolkit):
    def __init__(self):
        super().__init__(name="neo4j_toolkit")
        
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USERNAME")
        password = os.getenv("NEO4J_PASSWORD")
        
        if not all([uri, user, password]):
            # Fallback or error logging
            print("❌ Neo4j connection details missing in .env")
        
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.register(self.run_cypher_query)
        self.register(self.search_emergency_info)
        self.register(self.check_renewal_dates)
        self.register(self.get_client_profile)
        self.register(self.list_clients)
        self.register(self.verify_client_identity)
        # self.register(self.register_knowledge) # Complex object handling might need wrapper

    def run_cypher_query(self, cypher: str) -> str:
        """
        Executes a Cypher query against the Neo4j database.
        Use this to search, verify data, or retrieve specific information not covered by other tools.
        
        Args:
            cypher: Valid Cypher query string.
            
        Returns:
            JSON string of results.
        """
        try:
            with self.driver.session() as session:
                result = session.run(cypher)
                data = [record.data() for record in result]
                if not data:
                    return "Search results: 0 records"
                return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            return f"Cypher Execution Error: {e}"

    def search_emergency_info(self, client_name: str, situation: str = "") -> str:
        """
        [EMERGENCY ONLY] Retrieves safety-critical information with priority sorting.
        Follows 'Safety First' protocol:
        1. NgAction (Contraindications) - TOP PRIORITY
        2. CarePreference (Recommended Actions)
        3. KeyPerson (Emergency Contacts)
        4. Hospital
        5. Guardian
        
        Args:
            client_name: Name of the client (partial match allowed).
            situation: Optional context keyword (e.g., 'panic', 'meal').
            
        Returns:
            JSON string of emergency info.
        """
        try:
            # Reusing the optimized query from server.py logic
            query = """
            MATCH (c:Client)
            WHERE c.name CONTAINS $name
            
            // 1. NgAction (Always return ALL safety risks)
            OPTIONAL MATCH (c)-[:MUST_AVOID]->(ng:NgAction)
            OPTIONAL MATCH (ng)-[:IN_CONTEXT]->(ngCon:Condition)
            WITH c, collect(DISTINCT {
                action: ng.action,
                reason: ng.reason,
                riskLevel: ng.riskLevel,
                context: ngCon.name
            }) AS ngActions
            
            // 2. CarePreference (Always return ALL preferences)
            OPTIONAL MATCH (c)-[:REQUIRES]->(cp:CarePreference)
            OPTIONAL MATCH (cp)-[:ADDRESSES]->(cpCon:Condition)
            WITH c, ngActions, collect(DISTINCT {
                category: cp.category,
                instruction: cp.instruction,
                priority: cp.priority,
                forCondition: cpCon.name
            }) AS carePrefs

            OPTIONAL MATCH (c)-[kpRel:HAS_KEY_PERSON]->(kp:KeyPerson)
            WITH c, ngActions, carePrefs, collect(DISTINCT {
                rank: kpRel.rank,
                name: kp.name,
                relationship: kp.relationship,
                phone: kp.phone,
                role: kp.role
            }) AS keyPersons

            OPTIONAL MATCH (c)-[:TREATED_AT]->(h:Hospital)
            WITH c, ngActions, carePrefs, keyPersons, collect(DISTINCT {
                name: h.name,
                specialty: h.specialty,
                phone: h.phone,
                doctor: h.doctor
            }) AS hospitals

            OPTIONAL MATCH (c)-[:HAS_LEGAL_REP]->(g:Guardian)

            RETURN
                c.name AS client,
                c.dob AS dob,
                c.bloodType AS bloodType,
                ngActions AS forbidden_actions,
                carePrefs AS recommended_care,
                keyPersons AS emergency_contacts,
                hospitals AS hospitals,
                collect(DISTINCT {
                    name: g.name,
                    type: g.type,
                    phone: g.phone
                }) AS legal_guardians
            """
            
            with self.driver.session() as session:
                result = session.run(query, name=client_name, situation=situation)
                data = [record.data() for record in result]
                
                if not data or not data[0].get('client'):
                    return f"Client '{client_name}' not found."
                
                return json.dumps(data[0], ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            return f"Error in search_emergency_info: {e}"

    def check_renewal_dates(self, days_ahead: int = 90, client_name: str = "") -> str:
        """
        Checks for certificates (Disability handbook, beneficiary certs) expiring soon.
        
        Args:
            days_ahead: Number of days to check ahead (default 90).
            client_name: Optional client name filter.
            
        Returns:
            JSON list of expiring certificates.
        """
        try:
            query = """
            MATCH (c:Client)-[:HAS_CERTIFICATE]->(cert:Certificate)
            WHERE cert.nextRenewalDate IS NOT NULL
              AND ($client_name = '' OR c.name CONTAINS $client_name)
            WITH c, cert,
                 duration.inDays(date(), cert.nextRenewalDate).days AS daysUntilRenewal
            WHERE daysUntilRenewal <= $days AND daysUntilRenewal >= 0
            RETURN
                c.name AS client,
                cert.type AS certificate_type,
                cert.grade AS grade,
                cert.nextRenewalDate AS renewal_date,
                daysUntilRenewal AS days_remaining
            ORDER BY daysUntilRenewal ASC
            """
            
            with self.driver.session() as session:
                result = session.run(query, days=days_ahead, client_name=client_name)
                data = [record.data() for record in result]
                
                if not data:
                    return f"No certificates expiring within {days_ahead} days."
                    
                return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            return f"Error in check_renewal_dates: {e}"

    def get_client_profile(self, client_name: str) -> str:
        """
        Retrieves the full profile of a client covering all 4 Pillars.
        
        Args:
            client_name: Name of the client.
            
        Returns:
            JSON object of the full profile.
        """
        try:
            # Robust Client Resolution Logic
            clean_name = client_name.strip()
            for suffix in ["さん", "くん", "ちゃん", "様", "氏", "San", "-san"]:
                if clean_name.endswith(suffix):
                    clean_name = clean_name[:-len(suffix)].strip()
                    break

            query = """
            MATCH (c:Client)
            OPTIONAL MATCH (c)-[:HAS_IDENTITY]->(i:Identity)
            WHERE 
               (i.name IN [$raw, $clean]) OR
               (c.name IN [$raw, $clean]) OR 
               (c.kana IN [$raw, $clean]) OR 
               ANY(alias IN c.aliases WHERE alias IN [$raw, $clean]) OR
               (c.name CONTAINS $clean OR $clean CONTAINS c.name) OR
               (c.kana CONTAINS $clean OR $clean CONTAINS c.kana) OR
               ANY(alias IN c.aliases WHERE alias CONTAINS $clean OR $clean CONTAINS alias)

            OPTIONAL MATCH (c)-[:HAS_HISTORY]->(h:LifeHistory)
            OPTIONAL MATCH (c)-[:HAS_WISH]->(w:Wish)
            OPTIONAL MATCH (c)-[:HAS_CONDITION]->(con:Condition)
            OPTIONAL MATCH (c)-[:REQUIRES]->(cp:CarePreference)
            OPTIONAL MATCH (c)-[:MUST_AVOID]->(ng:NgAction)
            OPTIONAL MATCH (c)-[:HAS_CERTIFICATE]->(cert:Certificate)
            OPTIONAL MATCH (c)-[:RECEIVES]->(pa:PublicAssistance)
            OPTIONAL MATCH (c)-[:HAS_KEY_PERSON]->(kp:KeyPerson)
            OPTIONAL MATCH (c)-[:HAS_LEGAL_REP]->(g:Guardian)
            OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(s:Supporter)
            OPTIONAL MATCH (c)-[:TREATED_AT]->(hosp:Hospital)
            
            RETURN 
                COALESCE(i.name, c.name) AS name,
                c.dob AS dob,
                collect(DISTINCT h) AS history,
                collect(DISTINCT w) AS wishes,
                collect(DISTINCT con) AS conditions,
                collect(DISTINCT cp) AS care_preferences,
                collect(DISTINCT ng) AS ng_actions,
                collect(DISTINCT cert) AS certificates,
                collect(DISTINCT kp) AS key_persons,
                collect(DISTINCT g) AS guardians,
                collect(DISTINCT hosp) AS hospitals
            """
            
            with self.driver.session() as session:
                result = session.run(query, raw=client_name, clean=clean_name)
                data = [record.data() for record in result]
                if not data or not data[0].get('name'):
                    return f"Client '{client_name}' not found."
                return json.dumps(data[0], ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            return f"Error in get_client_profile: {e}"

    def list_clients(self) -> str:
        """
        Lists all registered clients.
        
        Returns:
            JSON list of client names and basic info.
        """
        try:
            query = "MATCH (c:Client) RETURN c.name as name, c.dob as dob ORDER BY c.name"
            with self.driver.session() as session:
                result = session.run(query)
                data = [record.data() for record in result]
                return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            return f"Error listing clients: {e}"

    def verify_client_identity(self, name_input: str) -> str:
        """
        Check if a client exists and return the official name and match type.
        This uses a scoring system to find the best possible match.
        
        Args:
            name_input: The name provided by the user (e.g., 'Mari-chan').
            
        Returns:
            JSON object: {"status": "found"|"not_found", "official_name": "...", "match_type": "exact"|"alias"|"fuzzy"}
        """
        try:
            clean_name = name_input.strip()
            if not clean_name:
                return json.dumps({"status": "error", "message": "Empty input"})

            # New scoring-based query for robust matching
            query = """
            MATCH (c:Client)
            OPTIONAL MATCH (c)-[:HAS_IDENTITY]->(i:Identity)
            WITH c, i, $name AS inputName
            
            // Calculate a score based on match quality
            WITH c, i, inputName,
                CASE
                    WHEN COALESCE(i.name, c.name) = inputName THEN 100 // Exact official name
                    WHEN c.kana = inputName THEN 90                   // Exact kana match
                    WHEN inputName IN c.aliases THEN 80              // Exact alias match
                    WHEN COALESCE(i.name, c.name) CONTAINS inputName THEN 20 // Partial name match
                    WHEN c.kana CONTAINS inputName THEN 10           // Partial kana match
                    ELSE 0
                END AS score
            
            // Filter out non-matches and order by the best score
            WHERE score > 0
            RETURN
                COALESCE(i.name, c.name) AS name,
                score,
                CASE
                    WHEN score >= 100 THEN 'exact'
                    WHEN score >= 80 THEN 'alias'
                    ELSE 'fuzzy'
                END AS type
            ORDER BY score DESC
            LIMIT 1
            """

            with self.driver.session() as session:
                result = session.run(query, name=clean_name)
                record = result.single()

                if not record:
                    return json.dumps({"status": "not_found", "input": name_input})

                return json.dumps({
                    "status": "found",
                    "official_name": record['name'],
                    "match_type": record['type'],
                    "score": record['score'],
                    "input": name_input
                }, ensure_ascii=False)
                
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})
