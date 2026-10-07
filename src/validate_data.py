"""Validate row-level quality and relationships in the synthetic datasets."""

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


def load_data():
    return {
        name: pd.read_csv(RAW_DIR / f"{name}.csv")
        for name in ("customers", "cards", "merchants", "transactions")
    }


def validate_data(data):
    customers, cards = data["customers"], data["cards"]
    merchants, transactions = data["merchants"], data["transactions"]
    errors = []
    required_columns = {
        "customers": {"customer_id", "age"},
        "cards": {"card_id", "customer_id"},
        "merchants": {"merchant_id"},
        "transactions": {
            "transaction_id",
            "card_id",
            "customer_id",
            "merchant_id",
            "amount",
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
        if frame.isna().any().any():
            errors.append(f"{name} contains missing values")
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
    if not customers["age"].between(18, 100).all():
        errors.append("customer ages must be between 18 and 100")
    amounts = pd.to_numeric(transactions["amount"], errors="coerce")
    if not (amounts.gt(0) & np.isfinite(amounts)).all():
        errors.append("transaction amounts must be positive")
    return errors


if __name__ == "__main__":
    data = load_data()
    errors = validate_data(data)
    for name, frame in data.items():
        print(f"{name.title()}: {len(frame):,} rows")
    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(
        "Validation passed: keys, completeness, relationships, ages, "
        "and amounts are valid."
    )
