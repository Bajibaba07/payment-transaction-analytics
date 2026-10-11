import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import pandas as pd

from chatbots.ai_provider import (
    AIProviderError,
    OpenAIProvider,
    configured_api_key,
    redact_sensitive_input,
    validate_chat_input,
)
from chatbots.analytics import (
    SAFE_COLUMNS,
    AnalyticsDataError,
    answer_analytics,
    analytics_visualization,
    load_snapshot,
    snapshot_from_api,
    snapshot_from_dataframe,
)
from chatbots.support import (
    answer_support,
    find_article,
    load_knowledge_base,
)


def sample_transactions():
    return pd.DataFrame(
        [
            {
                "transaction_id": "T1",
                "customer_id": "PRIVATE-CUSTOMER",
                "card_id": "PRIVATE-CARD",
                "card_number": "4111111111111111",
                "cvv": "123",
                "merchant_category": "Retail",
                "merchant_name": "Shop One",
                "transaction_status": "Completed",
                "transaction_month": "2026-01",
                "amount": 100.0,
                "currency": "INR",
                "bank_name": "Example Bank",
                "is_successful": True,
                "is_failure": False,
            },
            {
                "transaction_id": "T2",
                "customer_id": "PRIVATE-CUSTOMER",
                "card_id": "PRIVATE-CARD",
                "card_number": "4111111111111111",
                "cvv": "123",
                "merchant_category": "Retail",
                "merchant_name": "Shop One",
                "transaction_status": "Failed",
                "transaction_month": "2026-01",
                "amount": 50.0,
                "currency": "INR",
                "bank_name": "Example Bank",
                "is_successful": False,
                "is_failure": True,
            },
            {
                "transaction_id": "T3",
                "customer_id": "ANOTHER-CUSTOMER",
                "card_id": "ANOTHER-CARD",
                "card_number": "5555555555554444",
                "cvv": "999",
                "merchant_category": "Grocery",
                "merchant_name": "Shop Two",
                "transaction_status": "Completed",
                "transaction_month": "2026-02",
                "amount": 75.0,
                "currency": "INR",
                "bank_name": "Other Bank",
                "is_successful": True,
                "is_failure": False,
            },
        ]
    )


class AnalyticsChatbotTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = snapshot_from_dataframe(sample_transactions())

    def test_calculates_verified_overall_bank_and_merchant_metrics(self):
        self.assertEqual(self.snapshot.total_transactions, 3)
        self.assertEqual(self.snapshot.completed_transactions, 2)
        self.assertEqual(self.snapshot.completed_amount, 175.0)
        self.assertAlmostEqual(self.snapshot.success_rate, 2 / 3)

        bank = next(item for item in self.snapshot.banks
                    if item.name == "Example Bank")
        self.assertEqual(bank.transaction_count, 2)
        self.assertEqual(bank.completed_transactions, 1)
        self.assertAlmostEqual(bank.success_rate, 0.5)

        merchant = next(
            item for item in self.snapshot.merchants
            if item.name == "Shop One"
        )
        self.assertEqual(merchant.transaction_count, 2)
        self.assertAlmostEqual(merchant.failure_rate, 0.5)
        self.assertEqual(merchant.completed_amount, 100.0)

    def test_answers_use_deterministic_calculations(self):
        response = answer_analytics(
            "What is the success rate?", self.snapshot
        )
        self.assertIn("66.67%", response)
        self.assertIn("2 of 3", response)

        bank_response = answer_analytics(
            "What is the success rate at Example Bank?", self.snapshot
        )
        self.assertIn("Example Bank", bank_response)
        self.assertIn("50.00%", bank_response)

    def test_answers_failed_payment_and_monthly_trend_questions(self):
        failed = answer_analytics("How many payments failed?", self.snapshot)
        self.assertIn("1 of 3", failed)
        self.assertIn("33.33%", failed)

        trends = answer_analytics("Show monthly transaction trends", self.snapshot)
        self.assertIn("2026-01", trends)
        self.assertIn("1 failed", trends)
        self.assertIn("2026-02", trends)

    def test_failure_metrics_are_answered_by_merchant_and_category(self):
        merchants = answer_analytics(
            "How many failed transactions were there by merchant?",
            self.snapshot,
        )
        self.assertIn("Shop One: 1 of 2", merchants)
        self.assertIn("Shop Two: 0 of 1", merchants)

        categories = answer_analytics(
            "Show failed payments by category", self.snapshot
        )
        self.assertIn("Retail: 1 of 2", categories)
        self.assertIn("Grocery: 0 of 1", categories)

        leading_merchant = answer_analytics(
            "Which merchant has the most failed transactions?",
            self.snapshot,
        )
        self.assertIn("Shop One", leading_merchant)
        self.assertIn("most failed transactions (1)", leading_merchant)

    def test_understands_paraphrases_rankings_and_contextual_followups(self):
        completed = answer_analytics(
            "How many payments went through?", self.snapshot
        )
        self.assertIn("2 of 3", completed)

        leading_bank = answer_analytics(
            "Which bank has the most?", self.snapshot
        )
        self.assertIn("Example Bank", leading_bank)
        self.assertIn("most transactions", leading_bank)

        follow_up = answer_analytics(
            "What about failed ones there?",
            self.snapshot,
            history=[
                {
                    "role": "assistant",
                    "content": "Example Bank has the most transactions.",
                }
            ],
        )
        self.assertIn("Example Bank", follow_up)
        self.assertIn("1 failed", follow_up)

    def test_answers_category_and_merchant_ranking_from_aggregate_data(self):
        merchant = answer_analytics(
            "Which merchant has the most transactions?", self.snapshot
        )
        self.assertIn("Shop One", merchant)

        category = answer_analytics(
            "Which category has the most transactions?", self.snapshot
        )
        self.assertIn("Retail", category)

    def test_understands_amount_paraphrases_and_entity_comparisons(self):
        amount = answer_analytics("How much was processed?", self.snapshot)
        self.assertIn("INR 175.00", amount)
        self.assertIn("2 successful transactions", amount)

        banks = answer_analytics(
            "Compare Example Bank and Other Bank", self.snapshot
        )
        self.assertIn("Example Bank", banks)
        self.assertIn("Other Bank", banks)
        self.assertIn("50.00% success", banks)

        category = answer_analytics(
            "How much was completed in Grocery?", self.snapshot
        )
        self.assertIn("Grocery", category)
        self.assertIn("INR 75.00", category)

        merchant = answer_analytics(
            "Which merchant has the highest spend?", self.snapshot
        )
        self.assertIn("Shop One", merchant)
        self.assertIn("INR 100.00", merchant)

        bank = answer_analytics(
            "Which bank has the most transaction value?", self.snapshot
        )
        self.assertIn("Example Bank", bank)
        self.assertIn("INR 100.00", bank)

        merchant_totals = answer_analytics(
            "Show merchant revenue totals", self.snapshot
        )
        self.assertIn("Shop One", merchant_totals)
        self.assertIn("INR 100.00", merchant_totals)

    def test_monthly_and_comparison_visualizations_use_aggregate_data(self):
        trend = analytics_visualization(
            "Show monthly transaction trends", self.snapshot
        )
        self.assertIsNotNone(trend)
        kind, table, chart = trend
        self.assertEqual(kind, "line")
        self.assertEqual(table["month"].tolist(), ["2026-01", "2026-02"])
        self.assertEqual(
            chart.columns.tolist(),
            [
                "transaction_count",
                "completed_transactions",
                "failed_transactions",
            ],
        )

        comparison = analytics_visualization(
            "Compare banks", self.snapshot
        )
        self.assertIsNotNone(comparison)
        kind, table, chart = comparison
        self.assertEqual(kind, "bar")
        self.assertEqual(set(table["bank"]), {"Example Bank", "Other Bank"})
        self.assertEqual(chart.columns.tolist(), ["transaction_count"])
        self.assertTrue(
            {"customer_id", "card_id", "card_number", "cvv"}.isdisjoint(
                table.columns
            )
        )

    def test_failed_payment_amount_and_api_metric_limits_are_explicit(self):
        failed_amount = answer_analytics(
            "How much money was debited for failed payments?", self.snapshot
        )
        self.assertIn("do not verify", failed_amount)

        with patch(
            "chatbots.analytics._get_json",
            side_effect=[
                {
                    "total_transactions": 3,
                    "completed_transactions": 2,
                    "completed_amount": 175.0,
                    "success_rate": 2 / 3,
                    "currency": "INR",
                },
                [
                    {
                        "bank_name": "Example Bank",
                        "transaction_count": 2,
                        "completed_transactions": 1,
                        "completed_amount": 100.0,
                    }
                ],
                [
                    {
                        "merchant_name": "Shop One",
                        "merchant_category": "Retail",
                        "transaction_count": 2,
                        "failure_rate": 0.5,
                        "completed_amount": 100.0,
                    }
                ],
                [
                    {
                        "category": "Retail",
                        "transaction_count": 2,
                        "completed_amount": 100.0,
                    }
                ],
            ],
        ):
            api_snapshot = snapshot_from_api("https://analytics.example.test")

        unavailable = answer_analytics(
            "Compare banks by failed payments", api_snapshot
        )
        self.assertIn("does not provide", unavailable)

    def test_provider_receives_only_selected_aggregate_context(self):
        captured = {}

        def fake_provider(topic, context):
            captured["topic"] = topic
            captured["context"] = context
            return "Here is the aggregate summary."

        result = answer_analytics(
            "How many transactions?", self.snapshot, provider=fake_provider
        )

        self.assertEqual(captured["topic"], "overall_summary")
        self.assertNotIn("customer_id", captured["context"])
        self.assertNotIn("card_id", captured["context"])
        self.assertNotIn("card_number", captured["context"])
        self.assertNotIn("cvv", captured["context"])
        self.assertIn("Verified calculation:", result)
        self.assertIn("3 total transactions", result)

    def test_unknown_analytics_question_is_not_sent_to_provider(self):
        def forbidden_provider(_topic, _context):
            self.fail("Unsupported question must not call the provider")

        result = answer_analytics(
            "Find my individual payment", self.snapshot,
            provider=forbidden_provider,
        )
        self.assertIn("cannot look up an individual", result)

    def test_local_loader_reads_only_allowlisted_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "transactions.csv"
            sample_transactions().to_csv(path, index=False)
            snapshot = load_snapshot(data_path=path)

        self.assertEqual(snapshot.total_transactions, 3)
        self.assertTrue(
            {"customer_id", "card_id", "card_number", "cvv"}.isdisjoint(
                SAFE_COLUMNS
            )
        )

    def test_rejects_invalid_amounts_and_success_flags(self):
        invalid_amount = sample_transactions()
        invalid_amount["amount"] = invalid_amount["amount"].astype("string")
        invalid_amount.loc[0, "amount"] = "not-a-number"
        with self.assertRaises(AnalyticsDataError):
            snapshot_from_dataframe(invalid_amount)

        invalid_status = sample_transactions()
        invalid_status["is_successful"] = (
            invalid_status["is_successful"].astype("string")
        )
        invalid_status.loc[0, "is_successful"] = "unknown"
        with self.assertRaises(AnalyticsDataError):
            snapshot_from_dataframe(invalid_status)

    def test_api_snapshot_uses_aggregate_endpoints_and_marks_missing_metrics(self):
        responses = {
            "/api/v1/summary": {
                "total_transactions": 3,
                "completed_transactions": 2,
                "completed_amount": 175.0,
                "success_rate": 2 / 3,
                "currency": "INR",
            },
            "/api/v1/banks": [
                {
                    "bank_name": "Example Bank",
                    "transaction_count": 2,
                    "completed_transactions": 1,
                    "completed_amount": 100.0,
                }
            ],
            "/api/v1/merchants?limit=100": [
                {
                    "merchant_name": "Shop One",
                    "merchant_category": "Retail",
                    "transaction_count": 2,
                    "failure_rate": 0.5,
                    "completed_amount": 100.0,
                }
            ],
            "/api/v1/categories": [
                {
                    "category": "Retail",
                    "transaction_count": 2,
                    "completed_amount": 100.0,
                }
            ],
        }

        with patch(
            "chatbots.analytics._get_json",
            side_effect=lambda _base, path: responses[path],
        ):
            snapshot = snapshot_from_api("https://analytics.example.test")

        self.assertEqual(snapshot.failed_transactions, None)
        unavailable = answer_analytics(
            "How many payments failed?", snapshot
        )
        self.assertIn("does not provide an exact failed-payment count", unavailable)
        self.assertIsNone(snapshot.monthly_trends)
        failed_bank_rank = answer_analytics(
            "Which bank has the most failed transactions?", snapshot
        )
        self.assertIn("does not provide failed-payment totals by bank", failed_bank_rank)


class SupportChatbotTests(unittest.TestCase):
    def test_knowledge_base_answers_failed_pending_and_refund_questions(self):
        knowledge_base = load_knowledge_base()
        cases = (
            ("My payment failed", "failed_payment", "failed"),
            ("My payment is pending", "pending_payment", "pending"),
            ("How do I get a refund?", "refund", "refund"),
        )
        for question, topic, expected in cases:
            with self.subTest(topic=topic):
                article = find_article(question, knowledge_base)
                self.assertIsNotNone(article)
                self.assertEqual(article.topic, topic)
                self.assertIn(expected, article.answer.casefold())
                self.assertIn("CVV", article.answer)
                self.assertIn("OTP", article.answer)

    def test_knowledge_base_answers_troubleshooting_and_complaint_questions(self):
        cases = (
            ("How can I troubleshoot this payment?", "troubleshooting"),
            ("How do I make a complaint?", "complaint"),
        )
        for question, topic in cases:
            with self.subTest(topic=topic):
                article = find_article(question)
                self.assertIsNotNone(article)
                self.assertEqual(article.topic, topic)
                self.assertIn("official support channel", article.answer)
                self.assertIn("CVV", article.answer)
                self.assertIn("OTP", article.answer)

    def test_local_support_fallback_does_not_need_provider(self):
        response = answer_support("My payment was declined.")
        self.assertIn("failed", response.casefold())
        self.assertIn("official support channel", response)

        unsupported = answer_support("Tell me something unrelated.")
        self.assertIn("Which of these best describes", unsupported)

    def test_support_matches_debit_refund_and_followup_variations(self):
        debited = answer_support(
            "My account was charged but the order did not go through."
        )
        self.assertIn("debited", debited.casefold())
        self.assertIn("avoid", debited.casefold())
        self.assertIn("official support channel", debited)

        refund = answer_support("When will I get my money back?")
        self.assertIn("timing depends", refund)

        follow_up = answer_support(
            "And what should I do next?",
            history=[{"role": "user", "content": "My payment is pending."}],
        )
        self.assertIn("pending", follow_up.casefold())

    def test_support_handles_followup_actions_and_unrelated_topics_safely(self):
        retry = answer_support(
            "Should I retry?",
            history=[
                {"role": "user", "content": "My payment is still pending."}
            ],
        )
        self.assertIn("pending", retry.casefold())
        self.assertIn("before retrying", retry)

        unrelated = answer_support(
            "Tell me a joke and explain outer space.",
            history=[{"role": "user", "content": "How do refunds work?"}],
        )
        self.assertIn("Which of these best describes", unrelated)

        refund_action = answer_support("Can you issue my refund?")
        self.assertIn("cannot initiate or issue a refund", refund_action)

    def test_support_detects_common_debit_and_complaint_paraphrases(self):
        duplicate_charge = answer_support(
            "My card was charged twice but I only ordered once."
        )
        self.assertIn("debited", duplicate_charge.casefold())
        self.assertIn("avoid", duplicate_charge.casefold())

        missing_order = answer_support(
            "The merchant did not receive my order, although I was charged."
        )
        self.assertIn("debited", missing_order.casefold())
        self.assertIn("official support channel", missing_order)

        unrecognized = answer_support(
            "I see an unrecognized charge on my statement."
        )
        self.assertIn("complaint", unrecognized.casefold())
        self.assertIn("cannot file complaints", unrecognized)

    def test_provider_receives_curated_article_not_raw_question(self):
        captured = {}

        def fake_provider(topic, context):
            captured["topic"] = topic
            captured["context"] = context
            return "General payment guidance."

        answer_support(
            "My payment failed, my email is private@example.test, CVV 123",
            provider=fake_provider,
        )

        self.assertEqual(captured["topic"], "support_failed_payment")
        serialized = json.dumps(captured["context"])
        self.assertNotIn("private@example.test", serialized)
        self.assertNotIn("123", serialized)
        self.assertIn("approved_guidance", captured["context"])
        self.assertIn("failed", captured["context"]["question"].casefold())


class AIProviderTests(unittest.TestCase):
    def test_api_key_comes_only_from_runtime_sources(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            self.assertEqual(configured_api_key({}), "env-key")
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                configured_api_key({"OPENAI_API_KEY": "secret-key"}),
                "secret-key",
            )
            self.assertIsNone(configured_api_key({}))

    def test_chat_input_is_validated_before_routing(self):
        self.assertEqual(validate_chat_input("  What failed?  "), "What failed?")
        for question in ("", "   ", "x" * 501, None):
            with self.subTest(question=question):
                with self.assertRaises(ValueError):
                    validate_chat_input(question)
        with self.assertRaises(ValueError):
            answer_support(" " * 3)
        with self.assertRaises(ValueError):
            answer_analytics("", snapshot_from_dataframe(sample_transactions()))

    def test_provider_uses_fixed_endpoint_and_never_sends_raw_user_text(self):
        provider = OpenAIProvider("test-secret-key")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(
                    {"choices": [{"message": {"content": "Safe answer."}}]}
                ).encode("utf-8")

        with patch(
            "chatbots.ai_provider.urlopen", return_value=FakeResponse()
        ) as open_url:
            answer = provider.answer(
                "overall_summary",
                {"total_transactions": 3, "completed_transactions": 2},
            )

        request = open_url.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, "https://api.openai.com/v1/chat/completions")
        self.assertEqual(answer, "Safe answer.")
        self.assertNotIn("test-secret-key", request.data.decode("utf-8"))
        self.assertEqual(request.get_header("Authorization"), "Bearer test-secret-key")
        self.assertIn("overall_summary", body["messages"][1]["content"])

    def test_provider_sanitizes_question_and_history_before_sending(self):
        provider = OpenAIProvider("test-secret-key")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(
                    {"choices": [{"message": {"content": "Safe answer."}}]}
                ).encode("utf-8")

        with patch(
            "chatbots.ai_provider.urlopen", return_value=FakeResponse()
        ) as open_url:
            provider.answer(
                "support_failed_payment",
                {
                    "approved_guidance": "Check the final status.",
                    "customer_name": "Jane Doe",
                    "phone_number": "+1 212 555 0199",
                    "question": "My payment failed, CVV 123",
                    "history": [
                        {"role": "user", "content": "My PIN is 9876"},
                        {"role": "assistant", "content": "Check status."},
                    ],
                },
            )

        body = json.loads(open_url.call_args.args[0].data)
        message_content = body["messages"][1]["content"]
        self.assertNotIn("CVV 123", message_content)
        self.assertNotIn("PIN is 9876", message_content)
        self.assertNotIn("Jane Doe", message_content)
        self.assertNotIn("+1 212 555 0199", message_content)
        self.assertIn("[REDACTED]", message_content)

    def test_provider_uses_configured_model_in_request(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(
                    {"choices": [{"message": {"content": "Safe answer."}}]}
                ).encode("utf-8")

        provider = OpenAIProvider("unit-test-key", model="configured-model")
        with patch(
            "chatbots.ai_provider.urlopen", return_value=FakeResponse()
        ) as open_url:
            provider.answer("overall_summary", {"total_transactions": 3})

        body = json.loads(open_url.call_args.args[0].data)
        self.assertEqual(body["model"], "configured-model")

    def test_no_key_and_provider_failure_leave_local_support_available(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(configured_api_key({}))

        def failed_provider(_topic, _context):
            raise AIProviderError("The AI provider request failed.")

        with self.assertRaises(AIProviderError):
            answer_support("My payment was declined.", provider=failed_provider)
        local = answer_support("My payment was declined.")
        self.assertIn("failed", local.casefold())

    def test_provider_errors_are_explicit_and_do_not_return_fallback_answers(self):
        provider = OpenAIProvider("test-secret-key")
        with patch(
            "chatbots.ai_provider.urlopen",
            side_effect=URLError("private network detail"),
        ):
            with self.assertRaises(AIProviderError) as error:
                provider.answer("refund", {"approved_guidance": "safe text"})
        self.assertEqual(str(error.exception), "The AI provider request failed.")

    def test_sensitive_chat_input_is_redacted_before_display_or_routing(self):
        text = (
            "Check this card 4111 1111 1111 1111, CVV 123, "
            "PIN is 5678, password is abc123, name is Jane Doe, "
            "transaction reference is TX-1234, email me at person@example.test, "
            "or call +1 (212) 555-0199."
        )
        redacted = redact_sensitive_input(text)

        for sensitive_value in (
            "4111 1111 1111 1111",
            "123",
            "5678",
            "abc123",
            "Jane Doe",
            "TX-1234",
            "person@example.test",
            "+1 (212) 555-0199",
        ):
            self.assertNotIn(sensitive_value, redacted)
        self.assertIn("[REDACTED]", redacted)
        self.assertIn("[REDACTED EMAIL]", redacted)
        self.assertIn("[REDACTED PHONE]", redacted)


if __name__ == "__main__":
    unittest.main()
