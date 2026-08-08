FROM python:3.12-slim

# Install utilities
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync

# Copy source code
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Run the application
CMD ["uv", "run", "streamlit", "run", "app.py", "--server.address=0.0.0.0"]
