import os
from dotenv import load_dotenv

# Import the new unified agent
from agents.unified_support_agent import UnifiedSupportAgent

load_dotenv()

def main():
    print("============================================================")
    print("🛡️  Post-Parent Support Agent - Unified CLI Mode 🛡️")
    print("============================================================")
    print("WARNING: This system provides AI-based suggestions, NOT medical advice.")
    print("ALWAYS consult with a qualified professional for medical decisions.")
    print("============================================================")
    print("Type 'exit' to quit.\n")
    
    # Initialize the single, unified agent
    agent = UnifiedSupportAgent()
    
    # Simple conversation history
    history = []
    
    while True:
        try:
            user_input = input("📝 Enter your request or report (or 'exit'):\n>> ")
            if user_input.lower() in ['exit', 'quit']:
                print("Shutting down agent.")
                break
            
            if not user_input.strip():
                continue

            print("\n🔄 Agent is thinking...")

            # Add user input to history
            history.append(f"user: {user_input}")
            
            # Prepare context for the agent
            history_for_agent = "\n".join(history)
            
            # Run the unified agent
            response = agent.run(history_for_agent, stream=False)
            
            response_content = response.content
            print(f"\n[🤖 Agent Response]:\n{response_content}\n")
            
            # Add agent response to history
            history.append(f"assistant: {response_content}")

        except KeyboardInterrupt:
            print("\nShutting down.")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            # Optionally, reset history on error or handle differently
            # history = [] 

if __name__ == "__main__":
    main()
