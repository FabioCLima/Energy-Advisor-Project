FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

# chromadb/hnswlib requires C++ build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-bake demo assets (SQLite + sample data + ML model artifacts) at build time.
# Eliminates the 8-minute cold-start training on every fresh container.
# No API key needed: vectorstore bootstrap is skipped (requires embeddings at runtime).
RUN python - <<'EOF'
from energy_advisor.bootstrap.runtime import ensure_demo_assets
from energy_advisor.config import Settings
ensure_demo_assets(Settings(), ensure_vectorstore_index=False)
EOF

EXPOSE 8501 8000

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
