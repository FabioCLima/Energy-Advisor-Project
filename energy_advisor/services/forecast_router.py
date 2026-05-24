from __future__ import annotations

import os

from ..config import Settings
from .usage_forecasting import UsageForecastParams, forecast_energy_usage


def route_usage_forecast(
    db_path: str,
    device_type: str | None,
    params: UsageForecastParams,
) -> dict:
    settings = Settings()
    mode = settings.usage_forecast_mode
    model_path = settings.usage_forecast_model_path(device_type)

    if mode in {"ml", "auto"} and os.path.exists(model_path):
        from .usage_forecasting_ml import forecast_energy_usage_ml

        return forecast_energy_usage_ml(
            db_path=db_path,
            model_path=model_path,
            device_type=device_type,
            params=params,
        )

    if mode == "ml" and not os.path.exists(model_path):
        raise FileNotFoundError(
            f"ML model not found at {model_path}. "
            "Train it with: python -m energy_advisor.bootstrap.ml_train"
        )

    return forecast_energy_usage(
        db_path=db_path,
        device_type=device_type,
        params=params,
    )
