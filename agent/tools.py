import pandas as pd
from datetime import date, timedelta
from database.repository import get_all_transactions
from forecast.forecast import prepare_data, run_cash_schedule, flag_low_balance
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
    forecast_df = run_cash_schedule(
    df,
    starting_balance=starting_balance,
    days_ahead=FORECAST_HORIZON_DAYS,
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
    Summarize QBO invoices and bills with individual detail
    so Claude can reason over specific amounts, customers, and due dates.
    """
    from datetime import date
    import pandas as pd

    df = get_all_transactions()
    if df.empty:
        return {
            "outstanding_invoices": 0,
            "unpaid_bills": 0,
            "invoice_detail": "No invoice data available",
            "bill_detail": "No bill data available",
        }

    df["date"] = pd.to_datetime(df["date"])
    today = pd.Timestamp(date.today())

    # Future QBO inflows — outstanding invoices
    invoices = df[
        (df["source"] == "qbo") &
        (df["type"] == "in") &
        (df["date"] >= today)
    ].sort_values("date")

    # Future QBO outflows — unpaid bills
    bills = df[
        (df["source"] == "qbo") &
        (df["type"] == "out") &
        (df["date"] >= today)
    ].sort_values("date")

    # Build readable invoice list for Claude
    if not invoices.empty:
        invoice_lines = []
        for _, row in invoices.iterrows():
            days_until = (row["date"] - today).days
            invoice_lines.append(
                f"  - {row['category']}: ${row['amount']:,.0f} due in {days_until} days ({row['date'].strftime('%b %d')})"
            )
        invoice_detail = "\n".join(invoice_lines)
    else:
        invoice_detail = "No outstanding invoices"

    # Build readable bill list for Claude
    if not bills.empty:
        bill_lines = []
        for _, row in bills.iterrows():
            days_until = (row["date"] - today).days
            bill_lines.append(
                f"  - {row['category']}: ${row['amount']:,.0f} due in {days_until} days ({row['date'].strftime('%b %d')})"
            )
        bill_detail = "\n".join(bill_lines)
    else:
        bill_detail = "No upcoming bills"

    return {
        "outstanding_invoices": round(float(invoices["amount"].sum()), 2),
        "unpaid_bills": round(float(bills["amount"].sum()), 2),
        "invoice_detail": invoice_detail,
        "bill_detail": bill_detail,
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
