import pandas as pd
from faker import Faker
import random
from pathlib import Path
from datetime import timedelta

from generation_config import MERCHANT_SEED, REFERENCE_DATE

# Create Faker object
fake = Faker("en_IN")
random.seed(MERCHANT_SEED)
fake.seed_instance(MERCHANT_SEED)

merchants = []

cities = [
    ("Hyderabad", "Telangana"),
    ("Bengaluru", "Karnataka"),
    ("Mumbai", "Maharashtra"),
    ("Chennai", "Tamil Nadu"),
    ("Delhi", "Delhi"),
    ("Pune", "Maharashtra"),
    ("Kolkata", "West Bengal"),
    ("Ahmedabad", "Gujarat"),
    ("Jaipur", "Rajasthan"),
    ("Lucknow", "Uttar Pradesh")
]

merchant_categories = [
    "Retail",
    "Electronics",
    "Grocery",
    "Restaurants",
    "Travel",
    "Health & Wellness",
    "Fashion",
    "Entertainment",
    "Education",
    "Online Services"
]

merchant_status = [
    "Active",
    "Pending",
    "Suspended"
]

for i in range(1, 101):
    city, state = random.choice(cities)

    phone_digits = "".join(
        character
        for character in fake.phone_number()
        if character.isdigit()
    )[:10]

    merchant = {
        "merchant_id": f"M{i:06}",
        "merchant_name": fake.company(),
        "merchant_category": random.choice(merchant_categories),
        "city": city,
        "state": state,
        "contact_person": fake.name(),
        "email": fake.email(),
        "phone": phone_digits,
        "registration_date": fake.date_between(
            start_date=REFERENCE_DATE - timedelta(days=365 * 5),
            end_date=REFERENCE_DATE,
        ),
        "merchant_status": random.choice(merchant_status)
    }

    merchants.append(merchant)

output_path = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "raw"
    / "merchants.csv"
)
output_path.parent.mkdir(parents=True, exist_ok=True)
df = pd.DataFrame(merchants)
df.to_csv(output_path, index=False)
print(f"{len(merchants)} merchants saved to {output_path}")
