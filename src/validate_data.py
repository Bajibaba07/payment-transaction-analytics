"""Validate row-level quality and relationships in the synthetic datasets."""

from pathlib import Path

import numpy as np
import pandas as pd

from generation_config import REFERENCE_DATE


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"

MERCHANT_CATEGORIES = {
    "Retail",
    "Electronics",
    "Grocery",
    "Restaurants",
    "Travel",
    "Health & Wellness",
    "Fashion",
    "Entertainment",
    "Education",
    "Online Services",
}

ALLOWED_VALUES = {
    ("cards", "card_status"): {"Active", "Blocked", "Expired"},
    ("merchants", "merchant_category"): MERCHANT_CATEGORIES,
    ("merchants", "merchant_status"): {"Active", "Pending", "Suspended"},
    ("transactions", "transaction_status"): {
        "Completed",
        "Pending",
        "Failed",
        "Refunded",
        "Disputed",
    },
    ("transactions", "merchant_category"): MERCHANT_CATEGORIES,
}

DATE_COLUMNS = {
    "customers": ("registration_date",),
    "cards": ("issue_date", "expiry_date"),
    "merchants": ("registration_date",),
    "transactions": ("transaction_date",),
}


def load_data():
    data = {}
    for name in ("customers", "cards", "merchants", "transactions"):
        path = RAW_DIR / f"{name}.csv"
        try:
            data[name] = pd.read_csv(path)
        except FileNotFoundError as error:
            raise FileNotFoundError(
                f"Required {name} dataset not found at {path}."
            ) from error
        except (pd.errors.EmptyDataError, pd.errors.ParserError) as error:
            raise ValueError(
                f"Could not read {name} dataset at {path}: {error}"
            ) from error
    return data


def validate_data(data):
    customers, cards = data["customers"], data["cards"]
    merchants, transactions = data["merchants"], data["transactions"]
    errors = []
    required_columns = {
        "customers": {
            "customer_id",
            "age",
            "annual_income",
            "registration_date",
        },
        "cards": {
            "card_id",
            "customer_id",
            "card_status",
            "issue_date",
            "expiry_date",
        },
        "merchants": {
            "merchant_id",
            "merchant_category",
            "merchant_status",
            "registration_date",
        },
        "transactions": {
            "transaction_id",
            "card_id",
            "customer_id",
            "merchant_id",
            "amount",
            "transaction_date",
            "transaction_status",
            "merchant_category",
        },
    }
    datasets = (
        ("customers", customers, "customer_id"),
        ("cards", cards, "card_id"),
        ("merchants", merchants, "merchant_id"),
        ("transactions", transactions, "transaction_id"),
    )
    for name, frame, key in datasets:
        missing_columns = required_columns[name].difference(frame.columns)
        if missing_columns:
            errors.append(
                f"{name} is missing required columns: "
                f"{', '.join(sorted(missing_columns))}"
            )
            continue
        if frame[key].duplicated().any():
            errors.append(f"{name} has duplicate {key} values")
        has_blank_strings = frame.select_dtypes(
            include=["object", "string"]
        ).apply(
            lambda column: column.astype("string").str.strip().eq("").any()
        ).any()
        if frame.isna().any().any() or has_blank_strings:
            errors.append(f"{name} contains missing values")
        if frame[key].astype("string").str.strip().eq("").any():
            errors.append(f"{name} contains blank {key} values")
    if any(
        required_columns[name].difference(data[name].columns)
        for name in required_columns
    ):
        return errors
    relationships = (
        (cards, "customer_id", customers, "customer_id", "card -> customer"),
        (transactions, "card_id", cards, "card_id", "transaction -> card"),
        (
            transactions,
            "customer_id",
            customers,
            "customer_id",
            "transaction -> customer",
        ),
        (
            transactions,
            "merchant_id",
            merchants,
            "merchant_id",
            "transaction -> merchant",
        ),
    )
    for child, child_key, parent, parent_key, label in relationships:
        missing = (~child[child_key].isin(parent[parent_key])).sum()
        if missing:
            errors.append(f"{label} has {missing} invalid foreign keys")
    if not cards["card_id"].duplicated().any():
        card_customers = cards.set_index("card_id")["customer_id"]
        mismatched_card_owners = (
            transactions["customer_id"]
            != transactions["card_id"].map(card_customers)
        ).sum()
        if mismatched_card_owners:
            errors.append(
                "transaction -> card has "
                f"{mismatched_card_owners} customer/card ownership mismatches"
            )

    if not merchants["merchant_id"].duplicated().any():
        merchant_categories = merchants.set_index("merchant_id")[
            "merchant_category"
        ]
        mismatched_merchant_categories = (
            transactions["merchant_category"]
            != transactions["merchant_id"].map(merchant_categories)
        ).sum()
        if mismatched_merchant_categories:
            errors.append(
                "transaction -> merchant has "
                f"{mismatched_merchant_categories} category mismatches"
            )

    for (dataset_name, column), allowed_values in ALLOWED_VALUES.items():
        values = data[dataset_name][column].astype("string").str.strip()
        invalid_values = set(values.dropna().unique()) - allowed_values
        if invalid_values:
            errors.append(
                f"{dataset_name}.{column} has invalid values: "
                f"{', '.join(sorted(invalid_values))}"
            )

    parsed_dates = {}
    for dataset_name, columns in DATE_COLUMNS.items():
        for column in columns:
            parsed = pd.to_datetime(
                data[dataset_name][column], errors="coerce"
            )
            invalid_count = int(parsed.isna().sum())
            if invalid_count:
                errors.append(
                    f"{dataset_name}.{column} has "
                    f"{invalid_count} invalid dates"
                )
            parsed_dates[(dataset_name, column)] = parsed

    issue_dates = parsed_dates[("cards", "issue_date")]
    expiry_dates = parsed_dates[("cards", "expiry_date")]
    valid_card_dates = issue_dates.notna() & expiry_dates.notna()
    if (valid_card_dates & (issue_dates >= expiry_dates)).any():
        errors.append("card issue_date must be before expiry_date")

    for dataset_name, column in (
        ("customers", "registration_date"),
        ("cards", "issue_date"),
        ("merchants", "registration_date"),
        ("transactions", "transaction_date"),
    ):
        future_dates = (
            parsed_dates[(dataset_name, column)]
            > pd.Timestamp(REFERENCE_DATE)
        )
        if future_dates.any():
            errors.append(f"{dataset_name}.{column} must not be in the future")

    if (
        parsed_dates[("cards", "expiry_date")]
        <= pd.Timestamp(REFERENCE_DATE)
    ).any():
        errors.append("cards.expiry_date must be after the reference date")

    annual_income = pd.to_numeric(
        customers["annual_income"], errors="coerce"
    )
    if not (
        annual_income.between(300_000, 3_000_000)
        & np.isfinite(annual_income)
    ).all():
        errors.append(
            "customer annual_income must be finite and between "
            "300000 and 3000000"
        )

    ages = pd.to_numeric(customers["age"], errors="coerce")
    if not ages.between(18, 100).all():
        errors.append("customer ages must be between 18 and 100")
    amounts = pd.to_numeric(transactions["amount"], errors="coerce")
    if not (amounts.gt(0) & np.isfinite(amounts)).all():
        errors.append("transaction amounts must be positive")
    return errors


def main():
    try:
        data = load_data()
    except (FileNotFoundError, ValueError) as error:
        print(f"Validation could not run: {error}")
        return 1

    errors = validate_data(data)
    for name, frame in data.items():
        print(f"{name.title()}: {len(frame):,} rows")
    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "Validation passed: keys, completeness, relationships, ages, "
        "and amounts are valid."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
