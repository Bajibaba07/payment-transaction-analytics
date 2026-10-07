"""Flag unusually large synthetic transactions for analyst review."""

from pathlib import Path

from clean_data import clean_transactions, load_raw_data


ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"


def detect_amount_anomalies(transactions, z_threshold=3.0):
    result = transactions.copy()
    mean_amount = result["amount"].mean()
    standard_deviation = result["amount"].std()
    result["amount_z_score"] = (
        result["amount"] - mean_amount
    ) / standard_deviation
    result["amount_anomaly"] = result["amount_z_score"].abs().ge(z_threshold)
    return result[result["amount_anomaly"]].sort_values(
        "amount", ascending=False
    )


if __name__ == "__main__":
    transactions = clean_transactions(load_raw_data()["transactions"])
    anomalies = detect_amount_anomalies(transactions)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    anomalies.to_csv(REPORTS_DIR / "amount_anomalies.csv", index=False)
    print(f"Flagged {len(anomalies)} amount anomalies for review")
