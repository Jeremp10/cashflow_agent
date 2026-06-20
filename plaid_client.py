import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
import time
from dotenv import load_dotenv
import os
from datetime import datetime, date

# Load environment variables
load_dotenv()

PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID")
PLAID_SECRET = os.getenv("PLAID_SECRET")
PLAID_ENV = os.getenv("PLAID_ENV", "sandbox")  # sandbox or production

# Configure Plaid client
configuration = plaid.Configuration(
    host=getattr(plaid.Environment, PLAID_ENV.capitalize()),
    api_key={
        "clientId": PLAID_CLIENT_ID,
        "secret": PLAID_SECRET,
    }
)
api_client = plaid.ApiClient(configuration)
plaid_client = plaid_api.PlaidApi(api_client)


def create_link_token(user_id: str = "user123"):
    """
    Create a Plaid Link token for connecting a bank account.

    Args:
        user_id: Unique identifier for the user

    Returns:
        str: Plaid Link token
    """
    try:
        request = LinkTokenCreateRequest(
            products=[Products("transactions")],
            client_name="Cashflow Agent",
            user=LinkTokenCreateRequestUser(
                client_user_id=user_id
            ),
            country_codes=["US", "CA"],
            language="en",
        )
        response = plaid_client.link_token_create(request)
        return response.link_token
    except Exception as e:
        print(f"Error creating link token: {e}")
        return None


def create_sandbox_public_token(institution_id: str = "ins_109508"):
    """
    SANDBOX ONLY: Simulates a user connecting their bank via Plaid Link.
    Returns a public_token without needing the actual Link UI.
    """
    try:
        request = SandboxPublicTokenCreateRequest(
            institution_id=institution_id,
            initial_products=[Products("transactions")]
        )
        response = plaid_client.sandbox_public_token_create(request)
        return response.public_token
    except Exception as e:
        print(f"Error creating sandbox public token: {e}")
        return None


def exchange_public_token(public_token: str):
    """
    Exchange a public token from Plaid Link for an access token.

    Args:
        public_token: Public token returned by Plaid Link

    Returns:
        str: Access token (permanent key for the connected account)
    """
    try:
        request = ItemPublicTokenExchangeRequest(public_token=public_token)
        response = plaid_client.item_public_token_exchange(request)
        # Save this access token for future use
        return response.access_token
    except Exception as e:
        print(f"Error exchanging public token: {e}")
        return None


def get_transactions(access_token: str, start_date, end_date):
    """
    Retrieve transactions for an account within a date range.

    Args:
        access_token: Access token for the account
        start_date: Start date (date, datetime, or string "YYYY-MM-DD")
        end_date: End date (date, datetime, or string "YYYY-MM-DD")

    Returns:
        list: List of transactions with keys: date, amount, name, category
    """
    try:
        # Normalize all input types to a plain date object
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        elif isinstance(start_date, datetime):
            start_date = start_date.date()

        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        elif isinstance(end_date, datetime):
            end_date = end_date.date()

        request = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
        )
        response = plaid_client.transactions_get(request)

        transactions = []
        for txn in response.transactions:
            transactions.append({
                "date": txn.date,
                "amount": txn.amount,
                "name": txn.name,
                "category": txn.personal_finance_category.primary if txn.personal_finance_category else None,
            })

        return transactions
    except Exception as e:
        print(f"Error retrieving transactions: {e}")
        return []


def get_balances(access_token: str):
    """
    Retrieve current account balances.

    Args:
        access_token: Access token for the account

    Returns:
        list: List of accounts with balance info: account_id, name, balance, subtype
    """
    try:
        request = AccountsBalanceGetRequest(access_token=access_token)
        response = plaid_client.accounts_balance_get(request)

        balances = []
        for account in response.accounts:
            balances.append({
                "account_id": account.account_id,
                "name": account.name,
                "balance": account.balances.current,
                "subtype": account.subtype,
            })

        return balances
    except Exception as e:
        print(f"Error retrieving balances: {e}")
        return []


if __name__ == "__main__":
    public_token = create_sandbox_public_token()
    print("Public token:", public_token)

    access_token = exchange_public_token(public_token)
    print("Access token:", access_token)

    print("Waiting for sandbox transactions to be ready...")
    time.sleep(5)

    transactions = get_transactions(access_token, date(2026, 1, 1), date(2026, 6, 20))
    print(f"Got {len(transactions)} transactions")
    print(transactions[:3])

    balances = get_balances(access_token)
    print(balances)
