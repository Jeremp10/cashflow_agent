import os
from dotenv import load_dotenv

load_dotenv()

# Plaid
PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID")
PLAID_SECRET = os.getenv("PLAID_SECRET")
PLAID_ENV = os.getenv("PLAID_ENV", "sandbox")

# QuickBooks
QBO_CLIENT_ID = os.getenv("QBO_CLIENT_ID")
QBO_CLIENT_SECRET = os.getenv("QBO_CLIENT_SECRET")
QBO_REDIRECT_URI = os.getenv("QBO_REDIRECT_URI")
QBO_ENVIRONMENT = os.getenv("QBO_ENVIRONMENT", "sandbox")
QBO_REALM_ID = os.getenv("QBO_REALM_ID")
QBO_ACCESS_TOKEN = os.getenv("QBO_ACCESS_TOKEN")
QBO_REFRESH_TOKEN = os.getenv("QBO_REFRESH_TOKEN")

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///cashflow.db")

# App
FORECAST_HORIZON_DAYS = int(os.getenv("FORECAST_HORIZON_DAYS", "30"))
LOW_BALANCE_THRESHOLD = float(os.getenv("LOW_BALANCE_THRESHOLD", "1000.0"))
