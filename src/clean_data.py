"""Create typed, dashboard-safe datasets from the synthetic raw CSV files."""

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"


def load_raw_data():
    return {
        name: pd.read_csv(RAW_DIR / f"{name}.csv")
        for name in ("customers", "cards", "merchants", "transactions")
    }


def clean_transactions(transactions):
    result = transactions.copy()
    result["transaction_date"] = pd.to_datetime(result["transaction_date"])
    result["amount"] = pd.to_numeric(result["amount"], errors="coerce")
    result = result.drop_duplicates(subset="transaction_id")
    result = result[
        result["amount"].gt(0) & np.isfinite(result["amount"])
    ].copy()
    result["transaction_month"] = (
        result["transaction_date"].dt.to_period("M").astype(str)
    )
    result["is_successful"] = result["transaction_status"].eq("Completed")
    result["is_failure"] = result["transaction_status"].eq("Failed")
    return result


def build_processed_data():
    data = load_raw_data()
    customers = data["customers"].copy()
    cards = data["cards"].copy()
    merchants = data["merchants"].copy()
    transactions = clean_transactions(data["transactions"])

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    customers.to_csv(PROCESSED_DIR / "customers_clean.csv", index=False)
    merchants.to_csv(PROCESSED_DIR / "merchants_clean.csv", index=False)
    transactions.to_csv(PROCESSED_DIR / "transactions_clean.csv", index=False)

    public_cards = cards.drop(columns=["card_number", "cvv"], errors="ignore")
    public_cards.to_csv(PROCESSED_DIR / "cards_public.csv", index=False)

    customer_summary = (
        transactions[transactions["is_successful"]]
        .groupby("customer_id", as_index=False)
        .agg(
            successful_transactions=("transaction_id", "count"),
            successful_spend=("amount", "sum"),
            average_transaction_value=("amount", "mean"),
        )
    )
    merchant_summary = (
        transactions.groupby(
            ["merchant_id", "merchant_name", "merchant_category"],
            as_index=False,
        )
        .agg(
            transaction_count=("transaction_id", "count"),
            total_amount=("amount", "sum"),
            completed_amount=(
                "amount",
                lambda values: values[
                    transactions.loc[values.index, "is_successful"]
                ].sum(),
            ),
            failed_transactions=("is_failure", "sum"),
        )
        .sort_values("completed_amount", ascending=False)
    )
    customer_summary.to_csv(
        PROCESSED_DIR / "customer_summary.csv", index=False
    )
    merchant_summary.to_csv(
        PROCESSED_DIR / "merchant_summary.csv", index=False
    )

    return transactions


if __name__ == "__main__":
    cleaned = build_processed_data()
    print(
        f"Created dashboard-safe processed data for {len(cleaned)} "
        "transactions"
    )
