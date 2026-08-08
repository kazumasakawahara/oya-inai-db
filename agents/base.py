import os
from agno.agent import Agent
from agno.models.google import Gemini
from dotenv import load_dotenv

load_dotenv()

# Manifesto: The 5 Pillars of Post-Parent Support
MANIFESTO = """
【Post-Parent Support & Advocacy Graph Manifesto】
WE COMMIT TO THE 5 PILLARS:

1. **Dignity (尊厳)**: 
   Respect the client as an individual with their own history, narrative, and will.
   Never treat them as just a case or a set of symptoms.

2. **Safety (安全)**:
   Prioritize physical and psychological safety above all else.
   Strictly adhere to NgActions (Contraindications) to prevent harm and panic.
   "Safety First" protocol must be followed in emergencies.

3. **Continuity (継続性)**:
   Ensure care quality persists even when supporters change.
   Formalize tacit knowledge (CarePreferences) so it can be passed on.

4. **Advocacy (権利擁護)**:
   Connect the client's voiceless needs to legal frameworks (Certificates, Guardians).
   Ensure they receive all benefits and protections they are entitled to.

5. **Resilience (代替支援)**:
   Prepare for the "Function of the Parent" to fail or be absent.
   Always have a Plan B (Alternative Support) ready.
   When the primary caregiver cannot function, the system must autonomously activate the safety net.
"""

class BaseSupportAgent(Agent):
    def __init__(self, name: str, instructions: list = None, **kwargs):
        base_instructions = [
            MANIFESTO,
            "You are an AI agent dedicated to the well-being of the client.",
            "Always act according to the 5 Pillars.",
        ]
        if instructions:
            base_instructions.extend(instructions)
            
        # Configure logging to file
        # Agno agents print to console by default, we'll need to capture or redirect for file logging
        # For now, we rely on the framework's debug/monitoring if available, 
        # or we assume 'reasoning.log' will be handled by wrapper/runner script.
        
        super().__init__(
            model=Gemini(id="gemini-2.0-flash", api_key=os.getenv("GEMINI_API_KEY")),
            name=name,
            instructions=base_instructions,
            markdown=True,
            **kwargs
        )

    def log_reasoning(self, message: str):
        """
        Logs reasoning steps to agents/reasoning.log
        """
        log_path = os.path.join("agents", "reasoning.log")
        with open(log_path, "a") as f:
            from datetime import datetime
            timestamp = datetime.now().isoformat()
            f.write(f"[{timestamp}] [{self.name}] {message}\n")
