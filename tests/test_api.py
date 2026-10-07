import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException

from api import app as payment_api


def sample_transactions():
    return pd.DataFrame(
        [
            {
                "transaction_id": "T1",
                "customer_id": "C1",
                "card_id": "CARD1",
                "merchant_id": "M1",
                "merchant_name": "Shop One",
                "merchant_category": "Retail",
                "transaction_date": "2026-01-01",
                "amount": 100.0,
                "currency": "INR",
                "transaction_type": "Purchase",
                "transaction_status": "Completed",
                "payment_method": "Online",
                "merchant_city": "Mumbai",
                "merchant_state": "Maharashtra",
                "bank_name": "Example Bank",
                "card_type": "Debit",
                "is_successful": True,
                "is_failure": False,
                "card_number": "synthetic-private-field",
                "cvv": "synthetic-private-field",
            },
            {
                "transaction_id": "T2",
                "customer_id": "C1",
                "card_id": "CARD1",
                "merchant_id": "M1",
                "merchant_name": "Shop One",
                "merchant_category": "Retail",
                "transaction_date": "2026-01-02",
                "amount": 50.0,
                "currency": "INR",
                "transaction_type": "Purchase",
                "transaction_status": "Completed",
                "payment_method": "Chip",
                "merchant_city": "Mumbai",
                "merchant_state": "Maharashtra",
                "bank_name": "Example Bank",
                "card_type": "Debit",
                "is_successful": True,
                "is_failure": False,
                "card_number": "synthetic-private-field",
                "cvv": "synthetic-private-field",
            },
            {
                "transaction_id": "T3",
                "customer_id": "C2",
                "card_id": "CARD2",
                "merchant_id": "M2",
                "merchant_name": "Shop Two",
                "merchant_category": "Grocery",
                "transaction_date": "2026-01-03",
                "amount": 30.0,
                "currency": "INR",
                "transaction_type": "Purchase",
                "transaction_status": "Failed",
                "payment_method": "Chip",
                "merchant_city": "Delhi",
                "merchant_state": "Delhi",
                "bank_name": "Another Bank",
                "card_type": "Credit",
                "is_successful": False,
                "is_failure": True,
                "card_number": "synthetic-private-field",
                "cvv": "synthetic-private-field",
            },
        ]
    )


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        data_path = Path(self.temp_dir.name) / "transactions.csv"
        sample_transactions().to_csv(data_path, index=False)
        self.data_path_patch = patch.object(
            payment_api, "TRANSACTIONS_PATH", data_path
        )
        self.data_path_patch.start()
        payment_api._load_transactions.cache_clear()

    def tearDown(self):
        payment_api._load_transactions.cache_clear()
        self.data_path_patch.stop()
        self.temp_dir.cleanup()

    def test_summary_reports_expected_metrics(self):
        summary = payment_api.get_summary()

        self.assertEqual(summary.total_transactions, 3)
        self.assertEqual(summary.completed_transactions, 2)
        self.assertEqual(summary.completed_amount, 150.0)
        self.assertEqual(summary.active_customers, 2)

    def test_transactions_are_paginated_filtered_and_exclude_sensitive_fields(self):
        page = payment_api.get_transactions(limit=1, offset=1)
        filtered = payment_api.get_transactions(
            limit=10, offset=0, category="retail", status="completed"
        )

        self.assertEqual(page.total, 3)
        self.assertEqual(len(page.items), 1)
        self.assertEqual(filtered.total, 2)
        self.assertTrue(
            all(item.merchant_category == "Retail" for item in filtered.items)
        )
        returned_fields = set(page.items[0].model_dump())
        self.assertFalse(
            {"customer_id", "card_id", "card_number", "cvv"} & returned_fields
        )

    def test_aggregate_endpoints_return_expected_results(self):
        categories = payment_api.get_categories()
        banks = payment_api.get_banks()
        merchants = payment_api.get_merchants(limit=1)

        self.assertEqual(len(categories), 2)
        self.assertEqual(len(banks), 2)
        self.assertEqual(len(merchants), 1)
        self.assertEqual(merchants[0].merchant_id, "M1")
        self.assertEqual(merchants[0].failure_rate, 0.0)

    def test_health_fails_explicitly_when_processed_data_is_missing(self):
        with patch.object(
            payment_api,
            "TRANSACTIONS_PATH",
            Path(self.temp_dir.name) / "missing.csv",
        ):
            payment_api._load_transactions.cache_clear()
            with self.assertRaises(HTTPException) as error:
                payment_api.health()
            self.assertEqual(error.exception.status_code, 503)

    def test_processed_data_reload_invalidates_cache_after_pipeline_run(self):
        self.assertEqual(payment_api.get_summary().total_transactions, 3)
        updated = pd.concat([sample_transactions(), sample_transactions().iloc[:1]])
        updated["transaction_id"] = [
            f"T{index}" for index in range(1, len(updated) + 1)
        ]
        updated.to_csv(payment_api.TRANSACTIONS_PATH, index=False)

        self.assertEqual(payment_api.get_summary().total_transactions, 4)


if __name__ == "__main__":
    unittest.main()
