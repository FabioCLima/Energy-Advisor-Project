FROM python:3.12-slim

# chromadb/hnswlib requires C++ build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (pinned to pyproject.toml lower bounds)
RUN pip install --no-cache-dir \
    "chromadb>=0.5.0" \
    "langchain>=0.3.0" \
    "langchain-chroma>=0.1.4" \
    "langchain-community>=0.3.0" \
    "langchain-openai>=0.2.0" \
    "langchain-text-splitters>=0.3.0" \
    "langgraph>=0.2.0" \
    "loguru>=0.7.2" \
    "numpy>=1.26.4" \
    "openai>=1.40.0" \
    "pandas>=2.2.3" \
    "plotly>=6.7.0" \
    "pydantic>=2.0.0" \
    "pydantic-settings>=2.0.0" \
    "python-dateutil>=2.8.2" \
    "python-dotenv>=1.0.0" \
    "requests>=2.31.0" \
    "sqlalchemy>=2.0.23" \
    "streamlit>=1.57.0" \
    "rank-bm25>=0.2.2" \
    "langchain-classic>=1.0.0"

# Copy application code (data/ excluded via .dockerignore — mounted as volume)
COPY ecohome_solution/ ./ecohome_solution/

WORKDIR /app/ecohome_solution

EXPOSE 8501

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
