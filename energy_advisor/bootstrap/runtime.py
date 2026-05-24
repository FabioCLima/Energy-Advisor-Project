from __future__ import annotations

import os

from loguru import logger

from ..config import Settings
from ..services.database import DatabaseManager
from .db_setup import setup_database
from .ml_train import train_models
from .rag_setup import setup_vectorstore
from .sample_data import load_sample_data


def ensure_demo_assets(
    settings: Settings | None = None,
    *,
    ensure_vectorstore_index: bool = False,
) -> None:
    """Provision demo assets idempotently for fresh environments.

    This keeps Streamlit Cloud and simple container targets reproducible:
    database tables, sample data, and local ML artifacts are created on first boot.
    The RAG index is optional because it depends on embedding credentials.
    """
    settings = settings or Settings()
    db = setup_database(settings)

    if db.count_usage_records() == 0:
        logger.info("No usage records found. Loading sample data for the demo environment.")
        load_sample_data(settings=settings)
        db = DatabaseManager(db_path=settings.db_path)

    models_dir = settings.models_dir
    os.makedirs(models_dir, exist_ok=True)

    expected = [settings.usage_forecast_model_path(None)]
    if not all(os.path.exists(path) for path in expected):
        logger.info("ML artifacts missing. Training local forecast models for the demo environment.")
        train_models(settings=settings, force=False)

    if not ensure_vectorstore_index:
        logger.info("Vectorstore bootstrap skipped for this surface.")
        return

    if not settings.selected_api_key():
        logger.warning("Skipping vectorstore bootstrap because no OpenAI-compatible API key is configured.")
        return

    try:
        setup_vectorstore(settings=settings)
    except Exception as exc:
        logger.warning("Vectorstore bootstrap failed: {}", exc)
