
import os
import sys
import shutil

# ANSI colors for better UX (if supported)
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header():
    print(f"{Colors.HEADER}{Colors.BOLD}")
    print("=" * 60)
    print("   🛡️  Post-Parent Support System - Setup Wizard")
    print("=" * 60)
    print(f"{Colors.ENDC}")
    print("This wizard will help you configure the system.")
    print("You will need your API Keys (Gemini, LINE) ready.\n")

def get_input(prompt, required=True):
    while True:
        value = input(f"{Colors.GREEN}? {prompt}{Colors.ENDC}: ").strip()
        if value:
            return value
        if not required:
            return ""
        print(f"{Colors.WARNING}This field is required.{Colors.ENDC}")

def main():
    print_header()

    # Define paths
    base_dir = os.getcwd()
    env_path = os.path.join(base_dir, '.env')
    sos_env_path = os.path.join(base_dir, 'sos', '.env')
    example_env_path = os.path.join(base_dir, '.env.example')
    sos_example_env_path = os.path.join(base_dir, 'sos', '.env.example')

    # Step 1: Check existing configuration
    if os.path.exists(env_path) and os.path.exists(sos_env_path):
        print(f"{Colors.BLUE}Configuration files already exist.{Colors.ENDC}")
        overwrite = input("Do you want to re-configure? (y/N): ").strip().lower()
        if overwrite != 'y':
            print("Setup cancelled.")
            return

    # Step 2: Main Agent Configuration
    print(f"\n{Colors.BOLD}--- [1/2] Main Agent Configuration ---{Colors.ENDC}")
    gemini_key = get_input("Enter your Gemini API Key")
    
    # Neo4j details (defaults usually fine for local)
    print(f"\n{Colors.BLUE}Neo4j Database Settings (Press Enter for default){Colors.ENDC}")
    neo4j_uri = get_input("Neo4j URI [bolt://localhost:7687]", required=False) or "bolt://localhost:7687"
    neo4j_user = get_input("Neo4j Username [neo4j]", required=False) or "neo4j"
    neo4j_pass = get_input("Neo4j Password [password]", required=False) or "password"

    # Step 3: SOS/LINE Configuration
    print(f"\n{Colors.BOLD}--- [2/2] SOS & LINE Configuration ---{Colors.ENDC}")
    print("If you don't have LINE tokens yet, you can skip this part, but SOS alerts won't work.")
    line_token = get_input("LINE Channel Access Token", required=False)
    line_group = get_input("LINE Group ID", required=False)

    # Step 4: Write to files
    print(f"\n{Colors.BOLD}--- Saving Configuration ---{Colors.ENDC}")
    
    # Write main .env
    try:
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(f"GEMINI_API_KEY={gemini_key}\n")
            f.write(f"NEO4J_URI={neo4j_uri}\n")
            f.write(f"NEO4J_USERNAME={neo4j_user}\n")
            f.write(f"NEO4J_PASSWORD={neo4j_pass}\n")
            # If we add more vars later, add them here
        print(f"✅ Created {env_path}")
    except Exception as e:
        print(f"{Colors.FAIL}Error writing .env: {e}{Colors.ENDC}")

    # Write sos/.env
    try:
        # Ensure sos directory exists
        os.makedirs(os.path.join(base_dir, 'sos'), exist_ok=True)
        
        with open(sos_env_path, 'w', encoding='utf-8') as f:
            f.write(f"NEO4J_URI={neo4j_uri}\n")
            f.write(f"NEO4J_USERNAME={neo4j_user}\n")
            f.write(f"NEO4J_PASSWORD={neo4j_pass}\n")
            f.write(f"LINE_CHANNEL_ACCESS_TOKEN={line_token}\n")
            f.write(f"LINE_GROUP_ID={line_group}\n")
            f.write("CORS_ORIGINS=*\n") # Default for local easy setup
        print(f"✅ Created {sos_env_path}")
    except Exception as e:
        print(f"{Colors.FAIL}Error writing sos/.env: {e}{Colors.ENDC}")

    print(f"\n{Colors.BOLD}🎉 Setup Complete!{Colors.ENDC}")
    print("You can now run the start script to launch the system.")

if __name__ == "__main__":
    main()
