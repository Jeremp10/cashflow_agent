import logging
import pandas as pd
from datetime import date
from prophet import Prophet


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
    """Fit Prophet on daily net flow, then convert to a projected running balance."""
    if cleaned_df.empty:
        return pd.DataFrame(columns=["ds", "yhat", "yhat_lower", "yhat_upper", "projected_balance"])

    model = Prophet()
    model.fit(cleaned_df)

    future = model.make_future_dataframe(periods=days_ahead)
    forecast = model.predict(future)

    result = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()

    today = pd.Timestamp(date.today())
    result = result[result["ds"] >= today].copy()
    result = result.reset_index(drop=True)

    result["projected_balance"] = starting_balance + result["yhat"].cumsum()

    return result

def flag_low_balance(forecast_df: pd.DataFrame, threshold: float) -> list:
    """Return dates where projected running balance drops below threshold."""
    if forecast_df.empty:
        return []
    flagged = forecast_df.loc[forecast_df["projected_balance"] < threshold, "ds"].tolist()
    return flagged


if __name__ == "__main__":
    import sys
    sys.path.append(".")
    from db import get_all_transactions
    from sync import get_starting_balance

    df = get_all_transactions()
    print(f"Loaded {len(df)} transactions from db")

    cleaned = prepare_data(df)
    print("\nDaily net cash flow (last 10 days):")
    print(cleaned.tail(10))

    starting_balance = get_starting_balance()

    forecast = run_forecast(cleaned, days_ahead=30, starting_balance=starting_balance)

    print("\nForecast (next 30 days, last 10 rows):")
    print(forecast.tail(10))

    flagged = flag_low_balance(forecast, threshold=1000.0)
    if flagged:
        print(f"\n  Balance projected to drop below $1,000 starting: {flagged[0].date()}")
    else:
        print("\n Balance stays above $1,000 for the next 30 days")
