import pandas as pd
from database.db import Session, engine
from database.models import Base, Transaction


def init_db():
    """Create tables if they don't exist."""
    Base.metadata.create_all(engine)


def save_transactions(list_of_transactions: list):
    """Insert transactions, skipping duplicates."""
    session = Session()
    try:
        for transaction_data in list_of_transactions:
            existing = session.query(Transaction).filter(
                Transaction.date == transaction_data['date'],
                Transaction.amount == transaction_data['amount'],
                Transaction.source == transaction_data['source'],
                Transaction.type == transaction_data['type']
            ).first()

            if not existing:
                transaction = Transaction(**transaction_data)
                session.add(transaction)

        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error saving transactions: {e}")
    finally:
        session.close()


def get_all_transactions() -> pd.DataFrame:
    """Retrieve all transactions as a DataFrame."""
    session = Session()
    try:
        transactions = session.query(Transaction).all()
        data = [
            {
                'id': t.id,
                'date': t.date,
                'amount': t.amount,
                'category': t.category,
                'source': t.source,
                'type': t.type
            }
            for t in transactions
        ]
        return pd.DataFrame(data)
    except Exception as e:
        print(f"Error retrieving transactions: {e}")
        return pd.DataFrame()
    finally:
        session.close()
