#!/bin/bash
set -e

# Bootstrap the database with João's synthetic data on first run
if [ ! -f "data/energy_data.db" ]; then
    echo "First run — bootstrapping database with João's data (this takes ~10s)..."
    python -m energy_advisor.bootstrap.sample_data
    echo "Bootstrap complete."
fi

echo "Starting EcoHome Energy Advisor on port 8501..."
exec streamlit run app/streamlit_app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
