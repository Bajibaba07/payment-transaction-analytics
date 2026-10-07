import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


class DashboardTests(unittest.TestCase):
    def test_dashboard_data_is_available_and_public_card_data_is_safe(self):
        data_dir = ROOT / "data" / "processed"
        transactions = pd.read_csv(data_dir / "transactions_clean.csv")
        cards = pd.read_csv(data_dir / "cards_public.csv")
        raw_cards = pd.read_csv(ROOT / "data" / "raw" / "cards.csv")

        self.assertGreater(len(transactions), 0)
        self.assertTrue(
            {
                "transaction_date",
                "transaction_id",
                "merchant_category",
                "transaction_status",
                "bank_name",
                "is_successful",
                "is_failure",
            }.issubset(transactions.columns)
        )
        self.assertTrue(
            {"card_number", "cvv"}.isdisjoint(cards.columns)
        )
        self.assertTrue(
            {"card_number", "cvv"}.isdisjoint(raw_cards.columns)
        )


if __name__ == "__main__":
    unittest.main()
