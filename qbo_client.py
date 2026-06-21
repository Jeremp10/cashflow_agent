import os
from dotenv import load_dotenv
from intuitlib.client import AuthClient
from quickbooks import QuickBooks
from quickbooks.objects.invoice import Invoice
from quickbooks.objects.bill import Bill

load_dotenv()
QBO_CLIENT_ID = os.getenv("QBO_CLIENT_ID")
QBO_CLIENT_SECRET = os.getenv("QBO_CLIENT_SECRET")
QBO_REDIRECT_URI = os.getenv("QBO_REDIRECT_URI")
QBO_ENVIRONMENT = os.getenv("QBO_ENVIRONMENT", "sandbox")
QBO_SCOPES = ["com.intuit.quickbooks.accounting"]


def get_auth_url(state: str = "state123") -> str:
    """
    Generate the QuickBooks OAuth2 authorization URL.
    """
    auth_client = AuthClient(
        client_id=QBO_CLIENT_ID,
        client_secret=QBO_CLIENT_SECRET,
        environment=QBO_ENVIRONMENT,
        redirect_uri=QBO_REDIRECT_URI,
    )
    return auth_client.get_authorization_url(scopes=QBO_SCOPES, state=state)


def exchange_auth_code(auth_code: str, realm_id: str) -> dict:
    """
    Exchange the authorization code for access and refresh tokens.

    Returns a dict containing access_token, refresh_token, expires_in, and realm_id.
    """
    auth_client = AuthClient(
        client_id=QBO_CLIENT_ID,
        client_secret=QBO_CLIENT_SECRET,
        environment=QBO_ENVIRONMENT,
        redirect_uri=QBO_REDIRECT_URI,
    )

    try:
        auth_client.get_bearer_token(auth_code, realm_id=realm_id)
        credentials = {
            "access_token": auth_client.access_token,
            "refresh_token": auth_client.refresh_token,
            "expires_in": auth_client.expires_in,
            "realm_id": realm_id,
        }
        _save_qbo_tokens(credentials)
        return credentials
    except Exception as e:
        print(f"Error exchanging auth code: {e}")
        return {}


def _build_client(access_token: str, refresh_token: str, realm_id: str) -> QuickBooks:
    """
    Build an authenticated QuickBooks client.

    This SDK requires an AuthClient with access_token/refresh_token already set,
    passed via auth_client=, so it can start an internal OAuth2 session.
    Passing access_token= directly to QuickBooks() is not enough on this version.
    """
    auth_client = AuthClient(
        client_id=QBO_CLIENT_ID,
        client_secret=QBO_CLIENT_SECRET,
        environment=QBO_ENVIRONMENT,
        redirect_uri=QBO_REDIRECT_URI,
        access_token=access_token,
        refresh_token=refresh_token,
    )

    client = QuickBooks(
        auth_client=auth_client,
        refresh_token=refresh_token,
        company_id=realm_id,
        minorversion=75,
    )
    return client


def get_invoices(access_token: str, refresh_token: str, realm_id: str) -> list:
    """
    Retrieve Invoice objects from QuickBooks.
    """
    try:
        client = _build_client(access_token, refresh_token, realm_id)
        invoices = Invoice.query("SELECT * FROM Invoice", qb=client)
        return [
            {
                "amount": float(inv.TotalAmt) if inv.TotalAmt is not None else 0.0,
                "due_date": inv.DueDate,
                "customer": inv.CustomerRef.name if inv.CustomerRef else None,
                "status": inv.Balance if hasattr(inv, "Balance") else getattr(inv, "DocNumber", None),
            }
            for inv in invoices
        ]
    except Exception as e:
        print(f"Error retrieving invoices: {e}")
        return []


def get_bills(access_token: str, refresh_token: str, realm_id: str) -> list:
    """
    Retrieve Bill objects from QuickBooks.
    """
    try:
        client = _build_client(access_token, refresh_token, realm_id)
        bills = Bill.query("SELECT * FROM Bill", qb=client)
        return [
            {
                "amount": float(bill.TotalAmt) if bill.TotalAmt is not None else 0.0,
                "due_date": bill.DueDate,
                "vendor": bill.VendorRef.name if bill.VendorRef else None,
                "status": bill.Balance if hasattr(bill, "Balance") else getattr(bill, "DocNumber", None),
            }
            for bill in bills
        ]
    except Exception as e:
        print(f"Error retrieving bills: {e}")
        return []


def _save_qbo_tokens(tokens: dict):
    """
    Save QuickBooks tokens to a local .env file.
    """
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    existing = {}

    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    key, value = line.strip().split("=", 1)
                    existing[key] = value

    existing["QBO_ACCESS_TOKEN"] = tokens["access_token"]
    existing["QBO_REFRESH_TOKEN"] = tokens["refresh_token"]
    existing["QBO_REALM_ID"] = tokens["realm_id"]

    with open(env_path, "w") as f:
        for key, value in existing.items():
            f.write(f"{key}={value}\n")


if __name__ == "__main__":
    access_token = os.getenv("QBO_ACCESS_TOKEN")
    refresh_token = os.getenv("QBO_REFRESH_TOKEN")
    realm_id = os.getenv("QBO_REALM_ID")

    invoices = get_invoices(access_token, refresh_token, realm_id)
    print(f"Got {len(invoices)} invoices")
    print(invoices[:3])

    bills = get_bills(access_token, refresh_token, realm_id)
    print(f"Got {len(bills)} bills")
    print(bills[:3])
