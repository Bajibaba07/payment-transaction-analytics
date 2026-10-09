import pandas as pd
from faker import Faker
import random
from pathlib import Path
from datetime import timedelta

from generation_config import CUSTOMER_SEED, REFERENCE_DATE

# Create Faker object
fake = Faker("en_IN")
random.seed(CUSTOMER_SEED)
fake.seed_instance(CUSTOMER_SEED)

customers = []

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

occupations = [
    "Software Engineer",
    "Doctor",
    "Teacher",
    "Data Analyst",
    "Bank Manager",
    "Student",
    "Business Owner",
    "Accountant",
    "Civil Engineer",
    "Marketing Executive"
]

for i in range(1, 101):

    city, state = random.choice(cities)

    phone_digits = "".join(
        character
        for character in fake.phone_number()
        if character.isdigit()
    )[:10]

    customer = {
        "customer_id": f"C{i:06}",
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "gender": random.choice(["Male", "Female"]),
        "age": random.randint(18, 70),
        "email": fake.email(),
        "phone": phone_digits,
        "city": city,
        "state": state,
        "occupation": random.choice(occupations),
        "annual_income": random.randint(300000, 3000000),
        "registration_date": fake.date_between(
            start_date=REFERENCE_DATE - timedelta(days=365 * 3),
            end_date=REFERENCE_DATE,
        )
    }

    customers.append(customer)

df = pd.DataFrame(customers)

output_path = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "raw"
    / "customers.csv"
)
output_path.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(output_path, index=False)

print(f"{len(customers)} customers saved to {output_path}")
