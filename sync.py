from datetime import date, datetime
from plaid_client import create_sandbox_public_token, exchange_public_token, get_transactions
from qbo_client import get_invoices, get_bills, refresh_access_token,_save_qbo_tokens
from db import init_db, save_transactions
import time
import os
from dotenv import load_dotenv

load_dotenv()


def sync_plaid_transactions(access_token: str, start_date, end_date):
    """
    Pull transactions from Plaid and convert them into db.py's schema.
    Plaid convention: positive amount = money leaving the account.
    """
    raw_transactions = get_transactions(access_token, start_date, end_date)

    converted = []
    for txn in raw_transactions:
        converted.append({
            "date": txn["date"],
            "amount": abs(txn["amount"]),
            "category": txn["category"],
            "source": "plaid",
            "type": "out" if txn["amount"] > 0 else "in",
        })

    save_transactions(converted)
    print(f"Synced {len(converted)} Plaid transactions")


def sync_qbo_invoices(access_token: str, refresh_token: str, realm_id: str):
    """
    Pull invoices from QBO (money owed to the business = future cash IN).
    """
    raw_invoices = get_invoices(access_token, refresh_token, realm_id)

    converted = []
    for inv in raw_invoices:
        if not inv["due_date"]:
            continue
        converted.append({
            "date": datetime.strptime(inv["due_date"], "%Y-%m-%d").date(),
            "amount": inv["amount"],
            "category": "invoice",
            "source": "qbo",
            "type": "in",
        })

    save_transactions(converted)
    print(f"Attempted  {len(converted)} QBO invoices")


def sync_qbo_bills(access_token: str, refresh_token: str, realm_id: str):
    """
    Pull bills from QBO (money the business owes = future cash OUT).
    """
    raw_bills = get_bills(access_token, refresh_token, realm_id)

    converted = []
    for bill in raw_bills:
        if not bill["due_date"]:
            continue
        converted.append({
            "date": datetime.strptime(bill["due_date"], "%Y-%m-%d").date(),
            "amount": bill["amount"],
            "category": "bill",
            "source": "qbo",
            "type": "out",
        })

    save_transactions(converted)
    print(f"Synced {len(converted)} QBO bills")


if __name__ == "__main__":
    init_db()

    # --- Plaid ---
    public_token = create_sandbox_public_token()
    plaid_access_token = exchange_public_token(public_token)
    time.sleep(5)
    sync_plaid_transactions(plaid_access_token, date(2026, 1, 1), date(2026, 6, 20))

    # --- QuickBooks ---

    refreshed = refresh_access_token(os.getenv("QBO_REFRESH_TOKEN"))
    qbo_access_token = refreshed["access_token"]
    qbo_refresh_token = refreshed["refresh_token"]
    qbo_realm_id = os.getenv("QBO_REALM_ID")

    _save_qbo_tokens({
    "access_token": qbo_access_token,
    "refresh_token": qbo_refresh_token,
    "realm_id": qbo_realm_id,
    })

    sync_qbo_invoices(qbo_access_token, qbo_refresh_token, qbo_realm_id)
    sync_qbo_bills(qbo_access_token, qbo_refresh_token, qbo_realm_id)
