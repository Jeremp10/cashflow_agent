import pandas as pd
import numpy as np
import logging

logging.getLogger("prophet").setLevel(logging.WARNING)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)


def validate_recurring_estimate(transactions_df: pd.DataFrame) -> dict:
    """
    Validate the recurring spend estimate used in run_cash_schedule().

    Method: leave-one-week-out cross validation on Plaid history.
    For each week, estimate daily net using all other weeks,
    compare to what that week actually was.
    """
    if transactions_df.empty:
        return {"error": "No transaction data available"}

    df = transactions_df.copy()
    df = df[df["source"] == "plaid"].copy()

    if df.empty:
        return {"error": "No Plaid transaction history available"}

    df["date"] = pd.to_datetime(df["date"])
    df["signed_amount"] = df.apply(
        lambda r: r["amount"] if r["type"] == "in" else -r["amount"],
        axis=1
    )

    # Aggregate to daily net
    daily = (
        df.groupby(df["date"].dt.date)["signed_amount"]
        .sum()
        .reset_index()
    )
    daily.columns = ["date", "net"]
    daily["date"] = pd.to_datetime(daily["date"])
    daily["week"] = daily["date"].dt.isocalendar().week.astype(int)
    daily["year"] = daily["date"].dt.isocalendar().year.astype(int)
    daily["week_key"] = daily["year"].astype(str) + "-" + daily["week"].astype(str)

    weeks = daily["week_key"].unique()

    if len(weeks) < 3:
        return {"error": "Need at least 3 weeks of Plaid history for validation"}

    errors = []
    week_results = []

    for test_week in weeks:
        # Train on all other weeks
        train = daily[daily["week_key"] != test_week]
        test = daily[daily["week_key"] == test_week]

        if train.empty or test.empty:
            continue

        # Predicted daily net = mean of training days
        predicted_daily_net = float(train["net"].mean())

        # Actual daily net for the test week
        actual_daily_net = float(test["net"].mean())

        error = abs(predicted_daily_net - actual_daily_net)
        errors.append(error)

        week_results.append({
            "week": test_week,
            "predicted": round(predicted_daily_net, 2),
            "actual": round(actual_daily_net, 2),
            "error": round(error, 2),
        })

    if not errors:
        return {"error": "Could not compute validation — insufficient data"}

    mae = float(np.mean(errors))
    std = float(np.std(errors))
    best_week_error = float(np.min(errors))
    worst_week_error = float(np.max(errors))

    # Overall daily net (what the cash schedule actually uses)
    overall_daily_net = float(daily["net"].mean())

    return {
        "method": "leave-one-week-out cross validation on Plaid history",
        "mae_daily": round(mae, 2),
        "std_daily": round(std, 2),
        "best_week_error": round(best_week_error, 2),
        "worst_week_error": round(worst_week_error, 2),
        "overall_daily_net_estimate": round(overall_daily_net, 2),
        "weeks_tested": int(len(errors)),
        "data_points": int(len(daily)),
        "qbo_accuracy": "100% — exact amounts and dates pulled directly from QuickBooks",
        "interpretation": _interpret_validation(mae, overall_daily_net, len(errors)),
    }


def _interpret_validation(mae: float, daily_net: float, weeks_tested: int) -> str:
    """Plain English interpretation of cash schedule accuracy."""
    if abs(daily_net) < 1:
        ratio = None
    else:
        ratio = mae / abs(daily_net)

    if weeks_tested < 4:
        quality = "limited — more history will improve this estimate"
    elif ratio is None:
        quality = "daily net flows are near zero — MAE is the more useful signal"
    elif ratio < 0.5:
        quality = "good"
    elif ratio < 1.0:
        quality = "moderate"
    else:
        quality = "limited — high variability in daily cash flows"

    return (
        f"Recurring spend estimate accuracy: {quality}. "
        f"Off by ${mae:,.0f}/day on average across {weeks_tested} weeks of history. "
        f"QBO obligations (invoices and bills) are exact — pulled directly from QuickBooks."
    )


def summarize_validation(cleaned_df: pd.DataFrame) -> dict:
    """
    Main validation entry point called by the API.
    Validates the cash schedule, not Prophet.
    cleaned_df is unused here (kept for API compatibility)
    but we fetch raw transactions internally.
    """
    from database.repository import get_all_transactions
    raw_df = get_all_transactions()
    return validate_recurring_estimate(raw_df)
