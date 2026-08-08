import os
import json
import sys
from agno.tools import Toolkit
from dotenv import load_dotenv

# Ensure the project root is in path to import lib
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from lib.ai_extractor import extract_from_text, check_safety_compliance
except ImportError:
    # Fallback if path setup is tricky, logic might need adjustment
    print("WARNING: Could not import lib.ai_extractor")

load_dotenv()

class ExtractionToolkit(Toolkit):
    def __init__(self):
        super().__init__(name="extraction_toolkit")
        self.register(self.extract_narrative_data)
        self.register(self.check_safety)

    def extract_narrative_data(self, text: str, client_name: str = None) -> str:
        """
        Extracts structured data (JSON) from narrative text using AI.
        
        Args:
            text: The narrative text to process.
            client_name: Optional name of the client to associate or refine extraction.
            
        Returns:
            JSON string of extracted data structure.
        """
        try:
            result = extract_from_text(text, client_name)
            if result:
                return json.dumps(result, ensure_ascii=False, indent=2)
            else:
                return "Failed to extract data."
        except Exception as e:
            return f"Error in extraction: {e}"

    def check_safety(self, narrative: str, ng_actions_json: str) -> str:
        """
        Checks if the narrative violates any forbidden actions (NgActions).
        
        Args:
            narrative: The proposed action or narrative description.
            ng_actions_json: JSON string list of NgActions [{'action': '...', 'riskLevel': '...'}]
            
        Returns:
            JSON string with validation result: {"is_violation": bool, "warning": str}
        """
        try:
            ng_actions = json.loads(ng_actions_json)
            result = check_safety_compliance(narrative, ng_actions)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return "Error: ng_actions_json must be a valid JSON string."
        except Exception as e:
            return f"Error in safety check: {e}"
