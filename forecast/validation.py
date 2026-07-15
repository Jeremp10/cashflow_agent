
import pandas as pd
import numpy as np
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
import logging

logging.getLogger("prophet").setLevel(logging.WARNING)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)


def run_cross_validation(cleaned_df: pd.DataFrame) -> pd.DataFrame:
    """
    Prophet's built-in cross validation.

    initial: how much history to train on first
    period:  how often to cut a new training window
    horizon: how far ahead to forecast each time

    With ~90 days of data, these settings are conservative but honest.
    """
    if len(cleaned_df) < 30:
        print("Not enough data for meaningful cross validation (need 30+ days)")
        return pd.DataFrame()

    model = Prophet()
    model.fit(cleaned_df)

    df_cv = cross_validation(
        model,
        initial="45 days",
        period="7 days",
        horizon="14 days",
        parallel=None
    )
    return df_cv


def get_performance_metrics(df_cv: pd.DataFrame) -> pd.DataFrame:
    """
    Compute standard time series error metrics from cross validation results.
    """
    if df_cv.empty:
        return pd.DataFrame()

    metrics = performance_metrics(df_cv)
    return metrics


def summarize_validation(cleaned_df: pd.DataFrame) -> dict:
    """
    Run full validation and return a plain-English summary.
    Call this from forecast.py or a standalone script.
    """
    df_cv = run_cross_validation(cleaned_df)
    if df_cv.empty:
        return {"error": "Insufficient data for validation"}

    metrics = get_performance_metrics(df_cv)

    # Key metrics to report
    mae = metrics["mae"].mean()
    rmse = metrics["rmse"].mean()
    mape = metrics["mape"].mean() * 100

    mape_display = min(mape, 999.0)
    mape_unreliable = mape > 200

    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape": round(mape_display, 1),
        "mape_unreliable": mape_unreliable,
        "interpretation": _interpret_metrics(mae, mape_display, mape_unreliable),
        "data_points": len(cleaned_df),
        "cv_windows": len(df_cv),
    }


def _interpret_metrics(mae: float, mape: float, mape_unreliable: bool = False) -> str:
    """
    Plain English interpretation of model accuracy.
    This is what you'd actually say in a demo or to a client.
    """
    if mape_unreliable:
        return (
            f"Error rate unreliable with current data — daily net flows are too "
            f"variable for percentage-based metrics to be meaningful. "
            f"Dollar error (MAE) of ${mae:,.0f}/day is the more useful signal here."
        )
    elif mape < 10:
        return f"Strong accuracy — forecast is off by {mape:.1f}% on average"
    elif mape < 25:
        return f"Moderate accuracy — forecast is off by {mape:.1f}% on average. Improves with more history."
    else:
        return f"Limited accuracy ({mape:.1f}% average error) — model needs more historical data."

if __name__ == "__main__":
    from database.repository import get_all_transactions
    from forecast.forecast import prepare_data

    df = get_all_transactions()
    cleaned = prepare_data(df)

    print(f"Running validation on {len(cleaned)} days of data...")
    summary = summarize_validation(cleaned)

    print("\n=== Validation Results ===")
    for key, value in summary.items():
        print(f"{key}: {value}")
