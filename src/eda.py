"""Create reproducible summary tables used by the BI report."""

from pathlib import Path

from clean_data import clean_transactions, load_raw_data


ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"


def build_eda_outputs():
    transactions = clean_transactions(load_raw_data()["transactions"])
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    monthly = (
        transactions.groupby("transaction_month", as_index=False)
        .agg(
            transaction_count=("transaction_id", "count"),
            completed_amount=(
                "amount",
                lambda values: values[
                    transactions.loc[values.index, "is_successful"]
                ].sum(),
            ),
            failure_rate=("is_failure", "mean"),
        )
        .sort_values("transaction_month")
    )
    category = (
        transactions.groupby("merchant_category", as_index=False)
        .agg(
            transaction_count=("transaction_id", "count"),
            total_amount=("amount", "sum"),
            completed_amount=(
                "amount",
                lambda values: values[
                    transactions.loc[values.index, "is_successful"]
                ].sum(),
            ),
            failure_rate=("is_failure", "mean"),
        )
        .sort_values("completed_amount", ascending=False)
    )
    status = (
        transactions["transaction_status"]
        .value_counts()
        .rename_axis("status")
        .reset_index(name="transaction_count")
    )
    monthly.to_csv(REPORTS_DIR / "monthly_performance.csv", index=False)
    category.to_csv(REPORTS_DIR / "category_performance.csv", index=False)
    status.to_csv(REPORTS_DIR / "status_distribution.csv", index=False)
    return monthly, category, status


if __name__ == "__main__":
    monthly, category, status = build_eda_outputs()
    print(
        f"Created EDA outputs: {len(monthly)} months, "
        f"{len(category)} categories, {len(status)} statuses"
    )
