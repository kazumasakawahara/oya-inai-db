import json
from agno.tools import Toolkit
from duckduckgo_search import DDGS

class ResearchToolkit(Toolkit):
    def __init__(self):
        super().__init__(name="research_toolkit")
        self.register(self.search_pbs_strategies)

    def search_pbs_strategies(self, behavior_issue: str) -> str:
        """
        Search for Positive Behavior Support (PBS) strategies and evidence-based interventions 
        for a specific behavioral issue.
        
        Args:
            behavior_issue: The behavior to research (e.g., "food refusal in autism", "panic attack sensory overload").
            
        Returns:
            JSON string containing a summary of found strategies and sources.
        """
        print(f"🔎 Researching external evidence for: {behavior_issue}...")
        
        try:
            results = []
            with DDGS() as ddgs:
                # Search for academic/clinical advice
                query = f"Positive Behavior Support strategies for {behavior_issue} evidence based"
                search_res = list(ddgs.text(query, max_results=5))
                
                for r in search_res:
                    results.append({
                        "title": r.get('title'),
                        "snippet": r.get('body'),
                        "source": r.get('href')
                    })
            
            if not results:
                return json.dumps({"status": "no_results", "message": "No specific research found."}, ensure_ascii=False)

            return json.dumps({
                "topic": behavior_issue,
                "findings": results
            }, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
