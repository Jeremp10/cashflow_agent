from sqlalchemy import Column, Integer, String, Float, DateTime, Date
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone

Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=True)
    source = Column(String, nullable=False)
    type = Column(String, nullable=False)


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    predicted_balance = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
