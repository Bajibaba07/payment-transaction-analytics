import unittest
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest


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

    def test_streamlit_dashboard_is_default_and_chatbots_are_navigable(self):
        app = AppTest.from_file(
            str(ROOT / "dashboard" / "app.py"), default_timeout=30
        ).run()

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.radio(key="application_page").value, "Dashboard")
        self.assertTrue(
            any(
                element.value == "Payment Transaction Analytics"
                for element in app.title
            )
        )
        self.assertTrue(app.multiselect)

        category_filter = app.multiselect[0]
        category_filter.set_value([category_filter.options[0]]).run()
        self.assertEqual(len(app.exception), 0)
        self.assertGreaterEqual(
            sum(element.type == "vega_lite_chart" for element in app),
            4,
        )
        self.assertGreaterEqual(len(app.dataframe), 3)

        app.radio(key="application_page").set_value(
            "Analytics Chatbot"
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(
            any(
                element.value == "Transaction Analytics Chatbot"
                for element in app.title
            )
        )
        self.assertTrue(app.chat_input(key="integrated_analytics_prompt"))

        app.radio(key="application_page").set_value(
            "Payment Support Chatbot"
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(
            any(
                element.value == "Payment Support Chatbot"
                for element in app.title
            )
        )
        self.assertTrue(app.chat_input(key="integrated_support_prompt"))

    def test_integrated_analytics_chat_answers_from_processed_data(self):
        app = AppTest.from_file(
            str(ROOT / "dashboard" / "app.py"), default_timeout=30
        ).run()
        app.radio(key="application_page").set_value(
            "Analytics Chatbot"
        ).run()

        transaction_count = len(
            pd.read_csv(
                ROOT / "data" / "processed" / "transactions_clean.csv"
            )
        )
        app.chat_input(key="integrated_analytics_prompt").set_value(
            "How many transactions?"
        ).run()

        self.assertEqual(len(app.exception), 0)
        self.assertTrue(
            any(
                f"{transaction_count:,} total transactions" in item.value
                for item in app.markdown
            )
        )
        self.assertIn("analytics_messages", app.session_state)
        self.assertNotIn("support_messages", app.session_state)

    def test_integrated_support_chat_uses_local_faq_without_api_key(self):
        app = AppTest.from_file(
            str(ROOT / "dashboard" / "app.py"), default_timeout=30
        ).run()
        app.radio(key="application_page").set_value(
            "Payment Support Chatbot"
        ).run()
        app.chat_input(key="integrated_support_prompt").set_value(
            "My payment is pending"
        ).run()

        self.assertEqual(len(app.exception), 0)
        self.assertIn("support_messages", app.session_state)
        self.assertNotIn("analytics_messages", app.session_state)
        self.assertTrue(
            any("pending" in item.value.casefold() for item in app.markdown)
        )


if __name__ == "__main__":
    unittest.main()
