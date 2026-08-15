import pandas as pd
from faker import Faker
import random
from pathlib import Path

# Create Faker object
fake = Faker("en_IN")

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

    phone_digits = ''.join(ch for ch in fake.phone_number() if ch.isdigit())[:10]

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
            start_date="-3y",
            end_date="today"
        )
    }

    customers.append(customer)

df = pd.DataFrame(customers)

output_path = Path(__file__).resolve().parents[1] / "data" / "raw" / "customers.csv"
df.to_csv(output_path, index=False)

print(f"✅ {len(customers)} customers saved to {output_path}")