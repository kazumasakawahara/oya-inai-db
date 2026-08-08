import json
from agno.tools import Toolkit
from skills.sos_orchestrator.smart_sos import smart_sos_decision

class SOSToolkit(Toolkit):
    def __init__(self):
        super().__init__(name="sos_toolkit")
        self.register(self.analyze_sos_context)

    def analyze_sos_context(self, client_name: str, context: str) -> str:
        """
        Analyze an emergency context to determine the classification (Medical vs Behavioral)
        and generate a targeted SOS message plan with appropriate recipients.
        
        Args:
            client_name: Name of the client.
            context: Description of the emergency (e.g., 'Seizure started 5 mins ago', 'Panic attack at park').
            
        Returns:
            JSON string with 'classification', 'recipients', and 'message'.
        """
        decision = smart_sos_decision(client_name, context)
        return json.dumps(decision, ensure_ascii=False, indent=2)
