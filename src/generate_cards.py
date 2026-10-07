import pandas as pd
from faker import Faker
import random
from pathlib import Path
from datetime import timedelta

from generation_config import CARD_SEED, REFERENCE_DATE

# Create Faker object
fake = Faker("en_IN")
random.seed(CARD_SEED)
fake.seed_instance(CARD_SEED)

# Read customer dataset
customers_df = pd.read_csv(Path(__file__).resolve().parents[1] / "data" / "raw" / "customers.csv")

cards = []

banks = [
    "HDFC Bank",
    "ICICI Bank",
    "State Bank of India",
    "Axis Bank",
    "Kotak Mahindra Bank"
]

card_types = [
    "Debit",
    "Credit"
]

card_status = [
    "Active",
    "Blocked",
    "Expired"
]

card_number = 1

for _, customer in customers_df.iterrows():
    number_of_cards = random.randint(1, 3)  # Each customer can have 1 to 3 cards
    for _ in range(number_of_cards):
        card = {
            "card_id": f"CARD{card_number:06}",
            "customer_id": customer["customer_id"],
            "card_type": random.choice(card_types),
            "bank_name": random.choice(banks),
            "card_network": "Visa",
            "issue_date": fake.date_between(
                start_date=REFERENCE_DATE - timedelta(days=365 * 3),
                end_date=REFERENCE_DATE,
            ),
            "expiry_date": fake.date_between(
                start_date=REFERENCE_DATE + timedelta(days=365),
                end_date=REFERENCE_DATE + timedelta(days=365 * 6),
            ),
            "card_status": random.choice(card_status)
        }
        cards.append(card)
        card_number += 1

# Create DataFrame and save to CSV
output_path = Path(__file__).resolve().parents[1] / "data" / "raw" / "cards.csv"
df = pd.DataFrame(cards)
df.to_csv(output_path, index=False)

print(f"{len(cards)} cards saved to {output_path}")
