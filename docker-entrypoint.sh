#!/bin/bash
set -e

# ── Step 1: Database + sample data ───────────────────────────────────
if [ ! -f "data/energy_data.db" ]; then
    echo "[entrypoint] First run — bootstrapping João's energy database (~10s)..."
    python -m energy_advisor.bootstrap.db_setup
    python -m energy_advisor.bootstrap.sample_data
    echo "[entrypoint] Database ready."
fi

# ── Step 2: RAG vectorstore ───────────────────────────────────────────
if [ ! -f "data/vectorstore/chroma.sqlite3" ]; then
    echo "[entrypoint] Building RAG vectorstore (requires OPENAI_API_KEY)..."
    python -m energy_advisor.bootstrap.rag_setup
    echo "[entrypoint] Vectorstore ready."
fi

echo "[entrypoint] Starting EcoHome Energy Advisor on port 8501..."
exec streamlit run app/streamlit_app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
