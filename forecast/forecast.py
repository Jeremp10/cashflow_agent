import logging
import pandas as pd
from datetime import date
from prophet import Prophet

logging.getLogger("prophet").setLevel(logging.WARNING)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)


def prepare_data(transactions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate raw transactions into daily net cash flow.
    Used by Prophet cross validation in validation.py.
    """
    if transactions_df.empty:
        return pd.DataFrame(columns=["ds", "y"])

    df = transactions_df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date

    df["signed_amount"] = df.apply(
        lambda row: row["amount"] if str(row.get("type", "")).lower() == "in"
        else -row["amount"],
        axis=1,
    )

    daily = (
        df.groupby("date")["signed_amount"]
        .sum()
        .reset_index()
        .rename(columns={"date": "ds", "signed_amount": "y"})
    )

    daily["ds"] = pd.to_datetime(daily["ds"])
    daily = daily.sort_values("ds").reset_index(drop=True)
    return daily


def run_cash_schedule(
    transactions_df: pd.DataFrame,
    starting_balance: float,
    days_ahead: int = 30,
) -> pd.DataFrame:
    """
    Direct cash position schedule — replaces Prophet for balance projection.

    More accurate than statistical forecasting for short-term cash flow because
    it uses actual known obligations (QBO invoices/bills by due date) combined
    with estimated recurring spend learned from Plaid history.

    Logic per day:
      known QBO inflows on that date
    - known QBO outflows on that date
    + estimated daily recurring net from Plaid history
    = daily net change → cumulative running balance
    """
    if transactions_df.empty:
        return pd.DataFrame(columns=["ds", "projected_balance", "qbo_in", "qbo_out", "daily_net"])

    df = transactions_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    today = pd.Timestamp(date.today())

    # Known future QBO obligations — exact dates, exact amounts
    future_qbo = df[
        (df["source"] == "qbo") &
        (df["date"] > today)
    ].copy()

    # Historical Plaid data — learn recurring patterns
    historical_plaid = df[
        (df["source"] == "plaid") &
        (df["date"] <= today)
    ].copy()

    # Average daily net from Plaid history
    # This represents recurring spend/income patterns beyond known obligations
    if not historical_plaid.empty:
        plaid_in = float(historical_plaid[historical_plaid["type"] == "in"]["amount"].sum())
        plaid_out = float(historical_plaid[historical_plaid["type"] == "out"]["amount"].sum())
        days_of_history = max((today - historical_plaid["date"].min()).days, 1)
        avg_daily_net = (plaid_in - plaid_out) / days_of_history
    else:
        avg_daily_net = 0.0

    # Build day-by-day schedule
    rows = []
    running_balance = starting_balance

    for i in range(1, days_ahead + 1):
        future_date = today + pd.Timedelta(days=i)

        # Known QBO flows on this exact date
        day_qbo = future_qbo[
            future_qbo["date"].dt.date == future_date.date()
        ]
        qbo_in = float(day_qbo[day_qbo["type"] == "in"]["amount"].sum())
        qbo_out = float(day_qbo[day_qbo["type"] == "out"]["amount"].sum())

        # Estimated recurring from historical Plaid average
        daily_net = qbo_in - qbo_out + avg_daily_net
        running_balance += daily_net

        rows.append({
            "ds": future_date,
            "qbo_in": round(qbo_in, 2),
            "qbo_out": round(qbo_out, 2),
            "estimated_recurring": round(avg_daily_net, 2),
            "daily_net": round(daily_net, 2),
            "projected_balance": round(running_balance, 2),
        })

    return pd.DataFrame(rows)


def flag_low_balance(forecast_df: pd.DataFrame, threshold: float) -> list:
    """Return dates where projected running balance drops below threshold."""
    if forecast_df.empty:
        return []
    return forecast_df.loc[
        forecast_df["projected_balance"] < threshold, "ds"
    ].tolist()
