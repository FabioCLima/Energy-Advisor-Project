#!/bin/bash
set -euo pipefail

SERVICE_MODE="${SERVICE_MODE:-streamlit}"
PORT="${PORT:-8501}"
BOOTSTRAP_VECTORSTORE="${ENERGY_ADVISOR_BOOTSTRAP_VECTORSTORE:-false}"

echo "[entrypoint] service_mode=${SERVICE_MODE} port=${PORT}"

python - <<'PY'
import os
from energy_advisor.bootstrap.runtime import ensure_demo_assets
from energy_advisor.config import Settings

settings = Settings()
ensure_demo_assets(
    settings=settings,
    ensure_vectorstore_index=os.getenv("ENERGY_ADVISOR_BOOTSTRAP_VECTORSTORE", "false").lower() == "true",
)
PY

if [ "${SERVICE_MODE}" = "api" ]; then
    echo "[entrypoint] Starting FastAPI + LangServe on port ${PORT}..."
    exec uvicorn energy_advisor.api.app:app --host 0.0.0.0 --port "${PORT}"
fi

echo "[entrypoint] Starting Streamlit on port ${PORT}..."
exec streamlit run app/streamlit_app.py \
    --server.port="${PORT}" \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
