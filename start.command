#!/bin/bash

# Navigate to script directory
cd "$(dirname "$0")"

echo "🚀 Starting Post-Parent Support System..."

# Check python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python is not installed. Please install Python first."
    exit 1
fi

# Check uv
if ! command -v uv &> /dev/null; then
    echo "📦 Installing 'uv' package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# Sync dependencies
echo "📦 Installing dependencies..."
uv sync

# Check .env
if [ ! -f .env ]; then
    echo "⚠️  Configuration not found. Launching Setup Wizard..."
    uv run python setup_wizard.py
fi

# Check Docker
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    read -p "Press Enter to exit..."
    exit 1
fi

# Start Neo4j
echo "🗄️  Starting Database..."
docker-compose up -d neo4j

# Wait for Neo4j to be ready (max 30 seconds)
echo "⏳ Waiting for database to be ready..."
for i in $(seq 1 30); do
    if docker exec support-db-neo4j cypher-shell -u neo4j -p password "RETURN 1" > /dev/null 2>&1; then
        echo "✅ Database is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "⚠️  Database may not be ready yet. App will retry automatically."
    fi
    sleep 1
done

# Start Streamlit in background
echo "📊 Starting Dashboard (http://localhost:8501)..."
uv run streamlit run app.py &
STREAMLIT_PID=$!

# Start Main Agent
echo "🤖 Starting Agent Team..."
uv run python main.py

# Cleanup on exit
echo "🛑 Stopping Dashboard..."
kill $STREAMLIT_PID
