import random
from datetime import timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

from generation_config import CARD_SEED, REFERENCE_DATE

ROOT = Path(__file__).resolve().parents[1]

CUSTOMERS_PATH = ROOT / "data" / "raw" / "customers.csv"
OUTPUT_PATH = ROOT / "data" / "raw" / "cards.csv"

fake = Faker("en_IN")

random.seed(CARD_SEED)
fake.seed_instance(CARD_SEED)

if not CUSTOMERS_PATH.exists():
    raise FileNotFoundError(
        f"Customer dataset not found: {CUSTOMERS_PATH}"
    )

customers_df = pd.read_csv(CUSTOMERS_PATH)

required_customer_columns = {"customer_id"}
missing_columns = required_customer_columns - set(customers_df.columns)

if missing_columns:
    raise ValueError(
        f"Missing required customer columns: {sorted(missing_columns)}"
    )

if customers_df["customer_id"].isna().any():
    raise ValueError("Customer dataset contains missing customer_id values.")

if customers_df["customer_id"].duplicated().any():
    raise ValueError("Customer dataset contains duplicate customer_id values.")

banks = [
    "HDFC Bank",
    "ICICI Bank",
    "State Bank of India",
    "Axis Bank",
    "Kotak Mahindra Bank",
]

card_types = [
    "Debit",
    "Credit",
]

card_statuses = [
    "Active",
    "Blocked",
    "Expired",
]

cards = []
card_number = 1

for _, customer in customers_df.iterrows():
    customer_id = customer["customer_id"]
    number_of_cards = random.randint(1, 3)

    for _ in range(number_of_cards):
        issue_date = fake.date_between(
            start_date=REFERENCE_DATE - timedelta(days=365 * 3),
            end_date=REFERENCE_DATE,
        )

        expiry_date = fake.date_between(
            start_date=REFERENCE_DATE + timedelta(days=365),
            end_date=REFERENCE_DATE + timedelta(days=365 * 6),
        )

        card = {
            "card_id": f"CARD{card_number:06}",
            "customer_id": customer_id,
            "card_type": random.choice(card_types),
            "bank_name": random.choice(banks),
            "card_network": "Visa",
            "issue_date": issue_date,
            "expiry_date": expiry_date,
            "card_status": random.choice(card_statuses),
        }

        cards.append(card)
        card_number += 1

cards_df = pd.DataFrame(cards)

if cards_df.empty:
    raise ValueError("No cards were generated.")

if cards_df["card_id"].duplicated().any():
    raise ValueError("Duplicate card_id values were generated.")

if cards_df["customer_id"].isna().any():
    raise ValueError("Generated cards contain missing customer_id values.")

cards_df["issue_date"] = pd.to_datetime(cards_df["issue_date"])
cards_df["expiry_date"] = pd.to_datetime(cards_df["expiry_date"])

if cards_df["issue_date"].isna().any():
    raise ValueError("Generated cards contain missing issue_date values.")

if cards_df["expiry_date"].isna().any():
    raise ValueError("Generated cards contain missing expiry_date values.")

reference_date = pd.Timestamp(REFERENCE_DATE)

if (cards_df["issue_date"] >= cards_df["expiry_date"]).any():
    raise ValueError(
        "Invalid card dates: issue_date must be before expiry_date."
    )

if (cards_df["issue_date"] > reference_date).any():
    raise ValueError(
        "Invalid card dates: issue_date cannot be after REFERENCE_DATE."
    )

if (cards_df["expiry_date"] <= reference_date).any():
    raise ValueError(
        "Invalid card dates: expiry_date must be after REFERENCE_DATE."
    )

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

cards_df.to_csv(OUTPUT_PATH, index=False)

print(f"{len(cards_df)} cards saved to {OUTPUT_PATH}")
