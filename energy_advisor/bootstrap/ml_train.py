"""Bootstrap step: train local ML models and persist validation metrics.

MLflow tracking is enabled automatically when mlflow is installed.
Runs are stored in ./mlruns (default) or at MLFLOW_TRACKING_URI.
View them with: mlflow ui
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
    evaluate_holdout_window,
    save_forecaster,
    train_usage_forecaster,
)

_HOLDOUT_HOURS = 24 * 7

try:
    import mlflow
    import mlflow.sklearn
    _MLFLOW_AVAILABLE = True
except ImportError:
    _MLFLOW_AVAILABLE = False


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


def _log_to_mlflow(
    device_type: str | None,
    config: SklearnForecasterConfig,
    artifact: dict,
    validation: dict | None,
) -> None:
    """Log a training run to MLflow — no-op when mlflow is not installed."""
    if not _MLFLOW_AVAILABLE:
        return

    run_name = f"usage_forecaster_{device_type or 'all'}"
    mlflow.set_experiment("ecohome-usage-forecasting")

    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({
            "device_type":    device_type or "all",
            "lags":           str(list(config.lags)),
            "max_iter":       config.max_iter,
            "learning_rate":  config.learning_rate,
            "max_depth":      config.max_depth,
            "random_state":   config.random_state,
        })
        mlflow.set_tags({
            "trained_at":    artifact.get("trained_at", ""),
            "data_start":    artifact.get("trained_start_time", ""),
            "data_end":      artifact.get("trained_end_time", ""),
            "n_samples":     str(artifact.get("trained_samples", 0)),
            "framework":     "sklearn",
            "model_type":    "HistGradientBoostingRegressor",
        })
        if validation:
            mlflow.log_metrics({
                "model_mae":             validation["model_mae"],
                "model_rmse":            validation["model_rmse"],
                "baseline_mae":          validation["baseline_mae"],
                "baseline_rmse":         validation["baseline_rmse"],
                "mae_improvement_pct":   validation["mae_improvement_pct"],
                "rmse_improvement_pct":  validation["rmse_improvement_pct"],
            })
        if artifact.get("model") is not None:
            mlflow.sklearn.log_model(artifact["model"], name="model")

    logger.info("MLflow run logged | experiment=ecohome-usage-forecasting run={}", run_name)


def train_models(
    settings: Settings,
    device_types: list[str] | None = None,
    force: bool = False,
) -> list[str]:
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

        config = SklearnForecasterConfig()
        validation: dict | None = None
        try:
            validation = evaluate_holdout_window(series, config, holdout_hours=_HOLDOUT_HOURS)
            logger.info(
                "Validation | device_type={} rmse(model={:.4f}, baseline={:.4f}) mae(model={:.4f}, baseline={:.4f})",
                device_type or "all",
                validation["model_rmse"],
                validation["baseline_rmse"],
                validation["model_mae"],
                validation["baseline_mae"],
            )
        except ValueError as exc:
            logger.warning("Skipping hold-out validation for device_type={}: {}", device_type, exc)

        artifact = train_usage_forecaster(series, config=config)
        artifact["device_type"] = device_type
        artifact["trained_start_time"] = series.index.min().to_pydatetime().isoformat(timespec="minutes")
        artifact["trained_end_time"] = series.index.max().to_pydatetime().isoformat(timespec="minutes")
        artifact["trained_samples"] = int(len(series))
        artifact["validation"] = validation

        _log_to_mlflow(device_type, config, artifact, validation)
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
