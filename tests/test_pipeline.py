import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clean_data import clean_transactions
from validate_data import validate_data


class PipelineTests(unittest.TestCase):
    def test_clean_transactions_deduplicates_and_removes_invalid_amounts(self):
        transactions = pd.DataFrame(
            [
                {
                    "transaction_id": "T1",
                    "transaction_date": "2026-01-01",
                    "amount": "10.50",
                    "transaction_status": "Completed",
                },
                {
                    "transaction_id": "T1",
                    "transaction_date": "2026-01-01",
                    "amount": "10.50",
                    "transaction_status": "Completed",
                },
                {
                    "transaction_id": "T2",
                    "transaction_date": "2026-01-02",
                    "amount": "0",
                    "transaction_status": "Failed",
                },
                {
                    "transaction_id": "T3",
                    "transaction_date": "2026-01-03",
                    "amount": "inf",
                    "transaction_status": "Failed",
                },
            ]
        )

        result = clean_transactions(transactions)

        self.assertEqual(result["transaction_id"].tolist(), ["T1"])
        self.assertEqual(result.loc[0, "transaction_month"], "2026-01")
        self.assertTrue(result.loc[0, "is_successful"])
        self.assertFalse(result.loc[0, "is_failure"])

    def test_clean_transactions_removes_infinite_amounts(self):
        transactions = pd.DataFrame(
            [
                {
                    "transaction_id": "T1",
                    "transaction_date": "2026-01-01",
                    "amount": float("inf"),
                    "transaction_status": "Completed",
                }
            ]
        )

        result = clean_transactions(transactions)

        self.assertTrue(result.empty)

    def test_validate_data_accepts_valid_relationships(self):
        data = {
            "customers": pd.DataFrame(
                [{"customer_id": "C1", "age": 30}]
            ),
            "cards": pd.DataFrame(
                [{"card_id": "CARD1", "customer_id": "C1"}]
            ),
            "merchants": pd.DataFrame([{"merchant_id": "M1"}]),
            "transactions": pd.DataFrame(
                [
                    {
                        "transaction_id": "T1",
                        "card_id": "CARD1",
                        "customer_id": "C1",
                        "merchant_id": "M1",
                        "amount": 25.0,
                    }
                ]
            ),
        }

        self.assertEqual(validate_data(data), [])

    def test_validate_data_reports_missing_columns(self):
        data = {
            "customers": pd.DataFrame([{"customer_id": "C1"}]),
            "cards": pd.DataFrame([{"card_id": "CARD1"}]),
            "merchants": pd.DataFrame([{"merchant_id": "M1"}]),
            "transactions": pd.DataFrame(
                [
                    {
                        "transaction_id": "T1",
                        "card_id": "CARD1",
                        "customer_id": "C1",
                        "merchant_id": "M1",
                        "amount": float("inf"),
                    }
                ]
            ),
        }

        errors = validate_data(data)

        self.assertTrue(any("customers is missing required columns" in e for e in errors))
        self.assertTrue(any("cards is missing required columns" in e for e in errors))

    def test_validate_data_reports_invalid_ages_and_nonfinite_amounts(self):
        data = {
            "customers": pd.DataFrame(
                [{"customer_id": "C1", "age": 17}]
            ),
            "cards": pd.DataFrame(
                [{"card_id": "CARD1", "customer_id": "C1"}]
            ),
            "merchants": pd.DataFrame([{"merchant_id": "M1"}]),
            "transactions": pd.DataFrame(
                [
                    {
                        "transaction_id": "T1",
                        "card_id": "CARD1",
                        "customer_id": "C1",
                        "merchant_id": "M1",
                        "amount": float("inf"),
                    }
                ]
            ),
        }

        errors = validate_data(data)

        self.assertTrue(any("age" in e for e in errors))
        self.assertTrue(any("positive" in e for e in errors))

    def test_validate_data_rejects_transaction_with_another_customers_card(self):
        data = {
            "customers": pd.DataFrame(
                [
                    {"customer_id": "C1", "age": 30},
                    {"customer_id": "C2", "age": 30},
                ]
            ),
            "cards": pd.DataFrame(
                [{"card_id": "CARD1", "customer_id": "C1"}]
            ),
            "merchants": pd.DataFrame([{"merchant_id": "M1"}]),
            "transactions": pd.DataFrame(
                [
                    {
                        "transaction_id": "T1",
                        "card_id": "CARD1",
                        "customer_id": "C2",
                        "merchant_id": "M1",
                        "amount": 25.0,
                    }
                ]
            ),
        }

        errors = validate_data(data)

        self.assertTrue(any("ownership mismatches" in error for error in errors))

    def test_sql_import_maps_merchant_contact_columns_to_discarded_variables(self):
        import csv

        merchant_path = ROOT / "data" / "processed" / "merchants_clean.csv"
        with merchant_path.open(encoding="utf-8", newline="") as merchant_file:
            merchant_columns = next(csv.reader(merchant_file))

        sql = (ROOT / "sql" / "03_load_processed_data.sql").read_text(
            encoding="utf-8"
        )

        self.assertEqual(len(merchant_columns), 10)
        self.assertIn("@contact_person", sql)
        self.assertIn("@email", sql)
        self.assertIn("@phone", sql)
        self.assertIn("merchant_status = TRIM(@merchant_status)", sql)


if __name__ == "__main__":
    unittest.main()
