import os
import google.generativeai as genai
from agno.tools import Toolkit
from tools.neo4j_toolkit import Neo4jToolkit
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

class VectorMemoryToolkit(Toolkit):
    def __init__(self):
        super().__init__(name="vector_memory_toolkit")
        self.register(self.search_similar_logs)

    def _get_embedding(self, text: str):
        """Generate embedding using Gemini"""
        if not GOOGLE_API_KEY:
            return None
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_query"
        )
        return result['embedding']

    def search_similar_logs(self, query: str) -> str:
        """
        Search for past support logs that are semantically similar to the query.
        Useful for finding precedents for vague situations or "has this happened before?" questions.
        
        Args:
            query: The situation or question to search for (e.g. "He shouted when I touched his shoulder").
            
        Returns:
            JSON string of top 3 similar logs.
        """
        print(f"🧠 Recalling similar memories for: {query}...")
        
        if not GOOGLE_API_KEY:
            return "Error: GOOGLE_API_KEY not found. Cannot perform vector search."

        # 1. Generate Embedding
        embedding = self._get_embedding(query)
        if not embedding:
            return "Error: Failed to generate embedding."

        # 2. Vector Search Query
        cypher = """
        CALL db.index.vector.queryNodes('support_log_vector_index', 3, $embedding)
        YIELD node, score
        MATCH (node)-[:ABOUT]->(c:Client)
        RETURN node.date as date, node.situation as situation, node.action as action, node.effectiveness as effectiveness, c.name as client, score
        """
        
        try:
            # Instantiate toolkit to use its method
            neo4j = Neo4jToolkit()
            params_str = f"{{embedding: {embedding}}}" # Neo4j driver handles list natively, but toolkit expects string query mostly. 
            # Actually, Neo4jToolkit.run_cypher_query doesn't support params dict argument currently based on previous read.
            # We need to modify Neo4jToolkit or use driver directly here. 
            # Let's use the driver directly for vector search to handle embedding list correctly.
            
            with neo4j.driver.session() as session:
                result = session.run(cypher, embedding=embedding)
                results = [record.data() for record in result]
            
            if not results:
                return "No similar memories found."
            
            # Format output
            formatted = []
            for r in results:
                formatted.append({
                    "date": str(r.get('date', 'Unknown')),
                    "client": r.get('client', 'Unknown'),
                    "situation": r.get('situation', 'Unknown'),
                    "action": r.get('action', 'Unknown'),
                    "effectiveness": r.get('effectiveness', 'Unknown'),
                    "similarity": f"{r.get('score', 0):.2f}"
                })
                
            import json
            return json.dumps(formatted, ensure_ascii=False, indent=2)

        except Exception as e:
            return f"Error executing vector search: {str(e)}"
