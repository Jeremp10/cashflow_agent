import pandas as pd

from forecast.validation import summarize_validation


def test_summarize_validation_handles_short_history_gracefully():
    dates = pd.date_range("2024-01-01", periods=40, freq="D")
    df = pd.DataFrame({"ds": dates, "y": range(40)})

    summary = summarize_validation(df)

    assert summary["error"] == "Insufficient data for validation"
