from agent.prompts import build_system_prompt


def test_build_system_prompt_includes_context_and_guidance():
    context = {
        "current_balance": 1234.5,
        "total_in": 500.0,
        "total_out": 300.0,
        "net_flow": 200.0,
        "top_categories": "- Rent\n- Payroll",
        "forecast_days": 14,
        "projected_balance": 1500.0,
        "trend": "upward",
        "low_balance_alert": "None",
        "outstanding_invoices": 2500.0,
        "unpaid_bills": 1800.0,
        "data_as_of": "2026-07-03",
    }

    prompt = build_system_prompt(context)

    assert "You are a financial assistant for a small business owner." in prompt
    assert "Current liquid balance: $1,234.50" in prompt
    assert "Transaction summary (last 30 days):" in prompt
    assert "Top spending categories:" in prompt
    assert "- Rent" in prompt
    assert "Cash flow forecast (next 14 days):" in prompt
    assert "Projected ending balance: $1,500.00" in prompt
    assert "Data as of: 2026-07-03" in prompt
    assert "Answer the user's question based only on this context." in prompt
