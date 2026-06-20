from sqlalchemy import create_engine, text, Column, Integer, String, Float, DateTime, Date
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import pandas as pd
from datetime import datetime, timezone

# Database connection
DATABASE_URL = "sqlite:///cashflow.db"
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

# Table definitions
Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=True)
    source = Column(String, nullable=False)  # 'plaid' or 'qbo'
    type = Column(String, nullable=False)  # 'in' or 'out'


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    predicted_balance = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


def init_db():
    """Create tables if they don't exist."""
    Base.metadata.create_all(engine)


def save_transactions(list_of_transactions):
    """
    Insert transactions into the database, skipping duplicates.

    Args:
        list_of_transactions: List of transaction dictionaries with keys:
            date, amount, category, source, type
    """
    session = Session()
    try:
        for transaction_data in list_of_transactions:
            # Check for duplicates (same date, amount, source, type)
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


def get_all_transactions():
    """
    Retrieve all transactions from the database.

    Returns:
        pandas.DataFrame with columns: id, date, amount, category, source, type
    """
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
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        print(f"Error retrieving transactions: {e}")
        return pd.DataFrame()
    finally:
        session.close()


if __name__ == "__main__":
    init_db()
    save_transactions([
        {"date": datetime(2026, 6, 1).date(), "amount": 500.0, "category": "sales", "source": "qbo", "type": "in"},
        {"date": datetime(2026, 6, 2).date(), "amount": -150.0, "category": "rent", "source": "plaid", "type": "out"}
    ])
    df = get_all_transactions()
    print(df)
