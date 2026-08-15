import random
from pathlib import Path

import pandas as pd
from faker import Faker


fake = Faker("en_IN")
random.seed(42)

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


customers_df = pd.read_csv(RAW_DIR / "customers.csv")
cards_df = pd.read_csv(RAW_DIR / "cards.csv")
merchants_df = pd.read_csv(RAW_DIR / "merchants.csv")


def get_customer_map():
    return customers_df.set_index("customer_id").to_dict("index")


customer_map = get_customer_map()
merchant_records = merchants_df.to_dict("records")


def generate_amount(merchant_category):
    if merchant_category in {"Grocery", "Restaurants", "Retail"}:
        return round(random.uniform(80, 3500), 2)
    if merchant_category in {"Education", "Online Services", "Health & Wellness"}:
        return round(random.uniform(200, 6000), 2)
    return round(random.uniform(300, 10000), 2)


def pick_status(merchant_category):
    weights = {
        "Completed": 72,
        "Pending": 12,
        "Failed": 8,
        "Refunded": 6,
        "Disputed": 2,
    }
    if merchant_category in {"Travel", "Entertainment"}:
        weights["Completed"] = 68
        weights["Failed"] = 10
        weights["Pending"] = 14
    return random.choices(list(weights.keys()), weights=list(weights.values()), k=1)[0]


def pick_transaction_type():
    return random.choices(
        ["Purchase", "Refund", "Bill Payment", "Wallet Top-up", "Merchant Payment"],
        weights=[70, 12, 8, 5, 5],
        k=1,
    )[0]


def pick_payment_method(card_type):
    if card_type == "Credit":
        return random.choice(["Chip", "Contactless", "Online", "EMV"])
    return random.choice(["Chip", "Contactless", "Online", "ATM"])


transactions = []

for index, card in cards_df.iterrows():
    customer = customer_map.get(card["customer_id"])
    if customer is None:
        continue

    card_status = str(card["card_status"]).strip()
    if card_status == "Blocked":
        txn_count = random.randint(0, 4)
    elif card_status == "Expired":
        txn_count = random.randint(0, 2)
    else:
        txn_count = random.randint(4, 18)

    for _ in range(txn_count):
        merchant = random.choice(merchant_records)
        merchant_category = merchant["merchant_category"]
        amount = generate_amount(merchant_category)
        txn_type = pick_transaction_type()
        status = pick_status(merchant_category)
        transaction_date = fake.date_between(start_date="-18m", end_date="today")

        if txn_type == "Refund" and status == "Completed":
            amount = round(amount * random.uniform(0.1, 0.6), 2)

        transaction = {
            "transaction_id": f"TXN{index + 1:06}{random.randint(100, 999)}",
            "card_id": card["card_id"],
            "customer_id": card["customer_id"],
            "merchant_id": merchant["merchant_id"],
            "merchant_name": merchant["merchant_name"],
            "merchant_category": merchant_category,
            "transaction_date": transaction_date,
            "amount": amount,
            "currency": "INR",
            "transaction_type": txn_type,
            "transaction_status": status,
            "payment_method": pick_payment_method(card["card_type"]),
            "merchant_city": merchant["city"],
            "merchant_state": merchant["state"],
            "bank_name": card["bank_name"],
            "card_type": card["card_type"],
            "customer_city": customer["city"],
            "customer_state": customer["state"],
            "description": fake.catch_phrase(),
        }
        transactions.append(transaction)

output_path = RAW_DIR / "transactions.csv"
pd.DataFrame(transactions).to_csv(output_path, index=False)
print(f"✅ {len(transactions)} transactions saved to {output_path}")
