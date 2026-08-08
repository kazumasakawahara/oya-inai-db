import os
import google.generativeai as genai
from agno.tools import Toolkit
from tools.neo4j_toolkit import Neo4jToolkit
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

class LogToolkit(Toolkit):
    def __init__(self):
        super().__init__(name="log_toolkit")
        self.register(self.create_support_log)

    def _get_embedding(self, text: str):
        if not GOOGLE_API_KEY:
            return None
        try:
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            print(f"Embedding Error: {e}")
            return None

    def create_support_log(self, client_name: str, situation: str, action: str, effectiveness: int) -> str:
        """
        Creates a structured SupportLog node in Neo4j with an automatic Vector Embedding.
        Use this WHENEVER you propose an action or record a decision.
        
        Args:
            client_name: Name of the client.
            situation: The context/problem (e.g. "Refused bath").
            action: The solution proposed/taken (e.g. "Wait 10 mins").
            effectiveness: 1-5 rating of expected/actual outcome (3=Unknown/Average).
            
        Returns:
            Confirmation message string.
        """
        print(f"📝 Logging action for {client_name}...")
        
        # 1. Generate ID and Timestamp
        timestamp = datetime.now().isoformat()
        log_id = f"log_{int(datetime.now().timestamp())}"
        
        # 2. Generate Embedding
        context_text = f"Situation: {situation}\nAction: {action}\nEffectiveness: {effectiveness}"
        embedding = self._get_embedding(context_text)
        
        # 3. Cypher Query
        cypher = """
        MATCH (c:Client) WHERE c.name CONTAINS $name
        CREATE (log:SupportLog {
            id: $id,
            date: datetime($timestamp),
            situation: $situation,
            action: $action,
            effectiveness: $effectiveness,
            embedding: $embedding
        })
        CREATE (log)-[:ABOUT]->(c)
        RETURN log.id as id
        """
        
        try:
            # Instantiate toolkit
            neo4j = Neo4jToolkit()
            with neo4j.driver.session() as session:
                result = session.run(cypher, name=client_name, id=log_id, timestamp=timestamp, situation=situation, action=action, effectiveness=effectiveness, embedding=embedding)
                record = result.single()
            if record:
                return f"✅ Log recorded (ID: {log_id}) with Memory Embedding."
            return "Failed to save log."

        except Exception as e:
            return f"Error creating log: {str(e)}"
