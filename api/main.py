import time
import logging
from datetime import date
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database.repository import init_db, get_all_transactions
from integrations.plaid_client import (
    create_sandbox_public_token,
    exchange_public_token,
    get_balances,
)
from integrations.qbo_client import refresh_access_token, _save_qbo_tokens
from integrations.sync import (
    sync_plaid_transactions,
    sync_qbo_invoices,
    sync_qbo_bills,
)
from forecast.forecast import prepare_data, run_forecast, flag_low_balance
from agent.financial_agent import ask, reset_conversation
from config.settings import (
    QBO_REFRESH_TOKEN,
    QBO_REALM_ID,
    FORECAST_HORIZON_DAYS,
    LOW_BALANCE_THRESHOLD,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Cashflow Agent API",
    description="AI-powered cash flow forecasting and conversational finance assistant",
    version="0.1.0",
)

# CORS — allows Streamlit frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB on startup
@app.on_event("startup")
async def startup():
    init_db()
    logger.info("Database initialized")


# --- Request/Response models ---

class AskRequest(BaseModel):
    question: str
    current_balance: float = 320.0


class AskResponse(BaseModel):
    answer: str
    question: str


class ForecastResponse(BaseModel):
    current_balance: float
    projected_balance: float
    trend: str
    low_balance_alert: str
    forecast_days: int


class SyncResponse(BaseModel):
    status: str
    plaid_synced: bool
    qbo_synced: bool
    message: str


# --- Helper: get current liquid balance from Plaid ---

def _get_plaid_balance() -> tuple[float, str]:
    """
    Creates a fresh sandbox token and returns liquid balance + access token.
    In production: store access token in DB, reuse it.
    """
    public_token = create_sandbox_public_token()
    access_token = exchange_public_token(public_token)
    time.sleep(3)

    accounts = get_balances(access_token)
    liquid_types = {"checking", "savings"}
    balance = sum(
        acc["balance"] for acc in accounts
        if str(acc["subtype"]).lower() in liquid_types
        and acc["balance"] is not None
    )
    return round(balance, 2), access_token


# --- Routes ---

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/balance")
async def get_balance():
    """Return current liquid balance from Plaid."""
    try:
        balance, _ = _get_plaid_balance()
        return {"current_balance": balance}
    except Exception as e:
        logger.error(f"Balance fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sync", response_model=SyncResponse)
async def sync():
    """
    Pull fresh data from Plaid and QuickBooks, save to DB.
    In sandbox: creates a new Plaid item each time.
    In production: reuses stored access token.
    """
    plaid_ok = False
    qbo_ok = False
    messages = []

    # --- Plaid sync ---
    try:
        balance, access_token = _get_plaid_balance()
        sync_plaid_transactions(
            access_token,
            date(2026, 1, 1),
            date.today()
        )
        plaid_ok = True
        messages.append(f"Plaid synced (balance: ${balance:,.2f})")
    except Exception as e:
        messages.append(f"Plaid sync failed: {e}")
        logger.error(f"Plaid sync error: {e}")

    # --- QBO sync ---
    try:
        refreshed = refresh_access_token(QBO_REFRESH_TOKEN)
        if not refreshed:
            raise ValueError("Token refresh returned empty")

        qbo_access = refreshed["access_token"]
        qbo_refresh = refreshed["refresh_token"]

        _save_qbo_tokens({
            "access_token": qbo_access,
            "refresh_token": qbo_refresh,
            "realm_id": QBO_REALM_ID,
        })

        sync_qbo_invoices(qbo_access, qbo_refresh, QBO_REALM_ID)
        sync_qbo_bills(qbo_access, qbo_refresh, QBO_REALM_ID)
        qbo_ok = True
        messages.append("QuickBooks synced (invoices + bills)")
    except Exception as e:
        messages.append(f"QBO sync failed: {e}")
        logger.error(f"QBO sync error: {e}")

    return SyncResponse(
        status="ok" if (plaid_ok and qbo_ok) else "partial",
        plaid_synced=plaid_ok,
        qbo_synced=qbo_ok,
        message=" | ".join(messages),
    )


@app.get("/forecast", response_model=ForecastResponse)
async def get_forecast():
    """Run Prophet forecast and return summary."""
    try:
        balance, _ = _get_plaid_balance()

        df = get_all_transactions()
        if df.empty:
            raise HTTPException(status_code=404, detail="No transactions found. Run /sync first.")

        cleaned = prepare_data(df)
        forecast_df = run_forecast(
            cleaned,
            days_ahead=FORECAST_HORIZON_DAYS,
            starting_balance=balance
        )

        projected_balance = round(forecast_df["projected_balance"].iloc[-1], 2)
        trend = "positive" if projected_balance > balance else "negative"

        flagged = flag_low_balance(forecast_df, threshold=LOW_BALANCE_THRESHOLD)
        if flagged:
            alert = f"Balance may drop below ${LOW_BALANCE_THRESHOLD:,.0f} starting {flagged[0].date()}"
        else:
            alert = f"Balance stays above ${LOW_BALANCE_THRESHOLD:,.0f} for {FORECAST_HORIZON_DAYS} days"

        return ForecastResponse(
            current_balance=balance,
            projected_balance=projected_balance,
            trend=trend,
            low_balance_alert=alert,
            forecast_days=FORECAST_HORIZON_DAYS,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Forecast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    """
    Main conversational endpoint.
    Takes a plain English question, returns Claude's answer
    grounded in real financial data.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        answer = ask(request.question, request.current_balance)
        return AskResponse(answer=answer, question=request.question)
    except Exception as e:
        logger.error(f"Agent error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reset")
async def reset():
    """Clear conversation history between sessions."""
    reset_conversation()
    return {"status": "conversation reset"}

@app.get("/forecast/validation")
async def get_validation():
    """Run cross validation and return accuracy metrics."""
    try:
        from forecast.validation import summarize_validation
        df = get_all_transactions()
        if df.empty:
            return {"error": "No transactions found."}
        cleaned = prepare_data(df)
        return summarize_validation(cleaned)
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return {"error": "Validation unavailable at the moment."}
