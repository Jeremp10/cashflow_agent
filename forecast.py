import pandas as pd
from prophet import Prophet
import logging
logging.getLogger("prophet").setLevel(logging.WARNING)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)


def prepare_data(transactions_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate raw transactions into daily net cash flow for Prophet."""
    if transactions_df.empty:
        return pd.DataFrame(columns=["ds", "y"])

    df = transactions_df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date

    df["signed_amount"] = df.apply(
        lambda row: row["amount"] if str(row.get("type", "")).lower() == "in" else -row["amount"],
        axis=1,
    )

    daily = (
        df.groupby("date")["signed_amount"]
        .sum()
        .reset_index()
        .rename(columns={"date": "ds", "signed_amount": "y"})
    )

    daily = daily.sort_values("ds").reset_index(drop=True)
    return daily


def run_forecast(cleaned_df: pd.DataFrame, days_ahead: int = 90, starting_balance: float = 0.0) -> pd.DataFrame:
    if cleaned_df.empty:
        return pd.DataFrame(columns=["ds", "yhat", "yhat_lower", "yhat_upper", "projected_balance"])

    model = Prophet()
    model.fit(cleaned_df)

    future = model.make_future_dataframe(periods=days_ahead)
    forecast = model.predict(future)

    result = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    result["projected_balance"] = starting_balance + result["yhat"].cumsum()
    return result


def flag_low_balance(forecast_df: pd.DataFrame, threshold: float) -> list:
    if forecast_df.empty:
        return []
    return forecast_df.loc[forecast_df["projected_balance"] < threshold, "ds"].tolist()

if __name__ == "__main__":
    from db import get_all_transactions

    df = get_all_transactions()
    cleaned = prepare_data(df)
    print("Cleaned data:")
    print(cleaned)

    forecast = run_forecast(cleaned, days_ahead=90, starting_balance=5000.0)
    print("\nForecast (last 10 rows):")
    print(forecast.tail(10))

    flagged = flag_low_balance(forecast, threshold=1000.0)
    print(f"\n{len(flagged)} days flagged below threshold:")
    print(flagged[:5])
