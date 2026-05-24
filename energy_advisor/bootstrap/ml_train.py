"""Bootstrap step: Train local ML models for usage forecasting.

This step is optional. It produces a scikit-learn model artifact under Settings.models_dir.

Usage:
    python -m energy_advisor.bootstrap.ml_train
    python -m energy_advisor.bootstrap.ml_train --device-type ev
    python -m energy_advisor.bootstrap.ml_train --force
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime

from loguru import logger

from ..config import Settings
from ..services.database import DatabaseManager, EnergyUsage
from ..services.usage_forecasting import load_hourly_usage_series
from ..services.usage_forecasting_ml import (
    SklearnForecasterConfig,
    save_forecaster,
    train_usage_forecaster,
)


def _list_device_types(db: DatabaseManager) -> list[str]:
    session = db.get_session()
    try:
        rows = (
            session.query(EnergyUsage.device_type)
            .distinct()
            .order_by(EnergyUsage.device_type)
            .all()
        )
        return [r[0] for r in rows if r and r[0]]
    finally:
        session.close()


def train_models(
    settings: Settings,
    device_types: list[str] | None = None,
    force: bool = False,
) -> list[str]:
    """Train forecast models and return list of paths written."""
    db = DatabaseManager(db_path=settings.db_path)
    db.create_tables()

    if device_types is None:
        device_types = _list_device_types(db)

    targets: list[str | None] = [None] + device_types
    written: list[str] = []

    for device_type in targets:
        model_path = settings.usage_forecast_model_path(device_type)
        if os.path.exists(model_path) and not force:
            logger.info("Model already exists, skipping: {}", model_path)
            continue

        series = load_hourly_usage_series(db, device_type=device_type)
        if series.empty:
            logger.warning("No data found for device_type={}, skipping.", device_type)
            continue

        artifact = train_usage_forecaster(series, config=SklearnForecasterConfig())
        artifact["device_type"] = device_type
        artifact["trained_end_time"] = series.index.max().to_pydatetime().isoformat(timespec="minutes")
        artifact["trained_samples"] = int(len(series))

        save_forecaster(artifact, model_path)
        written.append(model_path)
        logger.success("Trained usage forecaster → {}", model_path)

    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Train EcoHome usage forecasting models (sklearn).")
    parser.add_argument(
        "--device-type",
        action="append",
        default=None,
        help="Train only for a specific device_type (repeatable).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing model artifacts.",
    )

    args = parser.parse_args()
    settings = Settings()

    logger.info(
        "Starting ML training | db={} models_dir={} device_types={} force={} at {}",
        settings.db_path,
        settings.models_dir,
        args.device_type,
        args.force,
        datetime.now().isoformat(timespec="seconds"),
    )

    written = train_models(settings=settings, device_types=args.device_type, force=args.force)
    logger.info("Training complete | artifacts_written={}", len(written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
