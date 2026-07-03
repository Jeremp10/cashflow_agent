import pandas as pd
from datetime import date, timedelta
from database.repository import get_all_transactions
from forecast.forecast import prepare_data, run_forecast, flag_low_balance
from config.settings import FORECAST_HORIZON_DAYS, LOW_BALANCE_THRESHOLD


def get_transaction_summary(days_back: int = 30) -> dict:
    """
    Summarize recent transactions into a context dict.
    """
    df = get_all_transactions()
    if df.empty:
        return {
            "total_in": 0,
            "total_out": 0,
            "net_flow": 0,
            "top_categories": "No transactions found",
        }

    df["date"] = pd.to_datetime(df["date"])
    cutoff = pd.Timestamp(date.today() - timedelta(days=days_back))
    recent = df[df["date"] >= cutoff]

    total_in = recent[recent["type"] == "in"]["amount"].sum()
    total_out = recent[recent["type"] == "out"]["amount"].sum()
    net_flow = total_in - total_out

    top_cats = (
        recent[recent["type"] == "out"]
        .groupby("category")["amount"]
        .sum()
        .sort_values(ascending=False)
        .head(5)
    )
    top_categories = "\n".join(
        f"  - {cat}: ${amt:,.2f}" for cat, amt in top_cats.items()
    ) or "No spending data"

    return {
        "total_in": round(total_in, 2),
        "total_out": round(total_out, 2),
        "net_flow": round(net_flow, 2),
        "top_categories": top_categories,
    }


def get_forecast_summary(starting_balance: float) -> dict:
    """
    Run forecast and summarize key outputs.
    """
    df = get_all_transactions()
    if df.empty:
        return {
            "projected_balance": starting_balance,
            "trend": "unknown",
            "low_balance_alert": "Insufficient data",
            "forecast_days": FORECAST_HORIZON_DAYS,
        }

    cleaned = prepare_data(df)
    forecast_df = run_forecast(
        cleaned,
        days_ahead=FORECAST_HORIZON_DAYS,
        starting_balance=starting_balance
    )

    projected_balance = forecast_df["projected_balance"].iloc[-1]
    trend = "positive" if projected_balance > starting_balance else "negative"

    flagged = flag_low_balance(forecast_df, threshold=LOW_BALANCE_THRESHOLD)
    if flagged:
        low_balance_alert = f"Balance may drop below ${LOW_BALANCE_THRESHOLD:,.0f} starting {flagged[0].date()}"
    else:
        low_balance_alert = f"Balance stays above ${LOW_BALANCE_THRESHOLD:,.0f} for the next {FORECAST_HORIZON_DAYS} days"

    return {
        "projected_balance": round(projected_balance, 2),
        "trend": trend,
        "low_balance_alert": low_balance_alert,
        "forecast_days": FORECAST_HORIZON_DAYS,
    }


def get_qbo_summary() -> dict:
    """
    Summarize outstanding invoices and unpaid bills from DB.
    """
    df = get_all_transactions()
    if df.empty:
        return {"outstanding_invoices": 0, "unpaid_bills": 0}

    invoices = df[(df["source"] == "qbo") & (df["type"] == "in")]["amount"].sum()
    bills = df[(df["source"] == "qbo") & (df["type"] == "out")]["amount"].sum()

    return {
        "outstanding_invoices": round(invoices, 2),
        "unpaid_bills": round(bills, 2),
    }


def build_full_context(current_balance: float) -> dict:
    """
    Assemble the complete context dict for the system prompt.
    Called once per conversation turn.
    """
    txn_summary = get_transaction_summary()
    forecast_summary = get_forecast_summary(current_balance)
    qbo_summary = get_qbo_summary()

    return {
        "current_balance": current_balance,
        "data_as_of": str(date.today()),
        **txn_summary,
        **forecast_summary,
        **qbo_summary,
    }
