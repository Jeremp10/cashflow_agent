from datetime import date, timedelta
from database.repository import init_db, save_transactions
from database.db import Session
from database.models import Transaction

def clear_transactions():
    session = Session()
    session.query(Transaction).delete()
    session.commit()
    session.close()
    print("Cleared existing transactions")

def seed_demo_data():
    init_db()
    clear_transactions()

    today = date.today()
    transactions = []

    # ── 6 months of Plaid history ─────────────────────────────────────────────

    # Payroll every 2 weeks — consistent, predictable
    for weeks_ago in [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24]:
        transactions.append({
            "date": today - timedelta(weeks=weeks_ago),
            "amount": 18000.0,
            "category": "PAYROLL",
            "source": "plaid",
            "type": "out"
        })

    # Monthly rent — first of every month
    for months_ago in [1, 2, 3, 4, 5, 6]:
        transactions.append({
            "date": today - timedelta(days=30 * months_ago),
            "amount": 4200.0,
            "category": "RENT",
            "source": "plaid",
            "type": "out"
        })

    # Client payments coming in — roughly monthly, varied amounts
    client_payments = [
        (today - timedelta(days=5),   22000.0, "CLIENT_PAYMENT"),
        (today - timedelta(days=18),  11500.0, "CLIENT_PAYMENT"),
        (today - timedelta(days=33),  18000.0, "CLIENT_PAYMENT"),
        (today - timedelta(days=47),   9500.0, "CLIENT_PAYMENT"),
        (today - timedelta(days=62),  24000.0, "CLIENT_PAYMENT"),
        (today - timedelta(days=78),  15000.0, "CLIENT_PAYMENT"),
        (today - timedelta(days=91),  11000.0, "CLIENT_PAYMENT"),
        (today - timedelta(days=105), 19500.0, "CLIENT_PAYMENT"),
        (today - timedelta(days=118),  8500.0, "CLIENT_PAYMENT"),
        (today - timedelta(days=132), 22000.0, "CLIENT_PAYMENT"),
        (today - timedelta(days=148), 13000.0, "CLIENT_PAYMENT"),
        (today - timedelta(days=162), 17500.0, "CLIENT_PAYMENT"),
    ]
    for d, amt, cat in client_payments:
        transactions.append({
            "date": d, "amount": amt,
            "category": cat, "source": "plaid", "type": "in"
        })

    # Weekly operating expenses — software, contractors, utilities
    operating = []
    for weeks_ago in range(1, 27):
        d = today - timedelta(weeks=weeks_ago)
        operating.extend([
            (d, 450.0, "SOFTWARE_SUBSCRIPTIONS"),
            (d + timedelta(days=2), 280.0, "UTILITIES"),
        ])
        if weeks_ago % 2 == 0:
            operating.append((d + timedelta(days=3), 1200.0, "CONTRACTORS"))
        if weeks_ago % 4 == 0:
            operating.append((d + timedelta(days=4), 850.0, "MARKETING"))

    for d, amt, cat in operating:
        transactions.append({
            "date": d, "amount": amt,
            "category": cat, "source": "plaid", "type": "out"
        })

    # ── QBO: upcoming invoices (money IN — but arriving too late) ────────────
    qbo_invoices = [
        (today + timedelta(days=28), 22000.0, "Acme Corp - Project Invoice"),
        (today + timedelta(days=35), 11500.0, "Globex Ltd - Monthly Retainer"),
        (today + timedelta(days=42),  6800.0, "Initech - Design Services"),
    ]
    for d, amt, cat in qbo_invoices:
        transactions.append({
            "date": d, "amount": amt,
            "category": cat, "source": "qbo", "type": "in"
        })

    # ── QBO: upcoming bills (money OUT — arriving before the invoices) ───────
    # This is the tension: bills due before invoices arrive
    qbo_bills = [
        (today + timedelta(days=6),  3200.0, "Contractor Payment - Due"),
        (today + timedelta(days=8),  4200.0, "Office Rent - Monthly"),
        (today + timedelta(days=11), 18000.0, "Payroll - Biweekly"),
        (today + timedelta(days=14),  450.0, "Software Subscriptions"),
        (today + timedelta(days=14),  280.0, "Utilities"),
        (today + timedelta(days=17),  850.0, "Marketing Agency"),
    ]
    for d, amt, cat in qbo_bills:
        transactions.append({
            "date": d, "amount": amt,
            "category": cat, "source": "qbo", "type": "out"
        })

    save_transactions(transactions)
    print(f"\nSeeded {len(transactions)} transactions")
    print("\n── Demo narrative ───────────────────────────────────────")
    print(f"Current balance:          $12,400 (set in /balance endpoint)")
    print(f"Bills due next 14 days:   $26,980")
    print(f"Cash gap:                -$14,580")
    print(f"Biggest invoice (Acme):   $22,000 due day 28 — 17 days after payroll")
    print(f"This is the tension your app is designed to catch.")

if __name__ == "__main__":
    seed_demo_data()
