import hashlib
import importlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

clean_data_module = importlib.import_module("clean_data")
validate_data_module = importlib.import_module("validate_data")
clean_transactions = clean_data_module.clean_transactions
validate_data = validate_data_module.validate_data


def valid_validation_data():
    return {
        "customers": pd.DataFrame(
            [
                {
                    "customer_id": "C1",
                    "age": 30,
                    "annual_income": 500_000,
                    "registration_date": "2025-01-01",
                }
            ]
        ),
        "cards": pd.DataFrame(
            [
                {
                    "card_id": "CARD1",
                    "customer_id": "C1",
                    "card_status": "Active",
                    "issue_date": "2024-01-01",
                    "expiry_date": "2028-01-01",
                }
            ]
        ),
        "merchants": pd.DataFrame(
            [
                {
                    "merchant_id": "M1",
                    "merchant_category": "Retail",
                    "merchant_status": "Active",
                    "registration_date": "2024-01-01",
                }
            ]
        ),
        "transactions": pd.DataFrame(
            [
                {
                    "transaction_id": "T1",
                    "card_id": "CARD1",
                    "customer_id": "C1",
                    "merchant_id": "M1",
                    "amount": 25.0,
                    "transaction_date": "2025-01-02",
                    "transaction_status": "Completed",
                    "merchant_category": "Retail",
                }
            ]
        ),
    }


class PipelineTests(unittest.TestCase):

    def test_clean_transactions_deduplicates_and_removes_invalid_amounts(
        self,
    ):
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

        self.assertEqual(
            result["transaction_id"].tolist(),
            ["T1"],
        )
        self.assertEqual(
            result.loc[0, "transaction_month"],
            "2026-01",
        )
        self.assertTrue(
            result.loc[0, "is_successful"]
        )
        self.assertFalse(
            result.loc[0, "is_failure"]
        )

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
        self.assertEqual(
            validate_data(valid_validation_data()),
            [],
        )

    def test_validate_data_rejects_duplicate_primary_keys(self):
        for dataset_name, key in (
            ("customers", "customer_id"),
            ("cards", "card_id"),
            ("merchants", "merchant_id"),
            ("transactions", "transaction_id"),
        ):
            with self.subTest(dataset=dataset_name):
                data = valid_validation_data()
                data[dataset_name] = pd.concat(
                    [data[dataset_name], data[dataset_name]],
                    ignore_index=True,
                )

                errors = validate_data(data)

                self.assertTrue(
                    any(f"duplicate {key}" in error for error in errors)
                )

    def test_validate_data_rejects_missing_values(self):
        data = valid_validation_data()
        data["customers"].loc[0, "age"] = pd.NA
        data["merchants"].loc[0, "merchant_status"] = "   "

        errors = validate_data(data)

        self.assertTrue(
            any(
                "customers contains missing values" in error
                for error in errors
            )
        )
        self.assertTrue(
            any(
                "merchants contains missing values" in error
                for error in errors
            )
        )

    def test_validate_data_reports_missing_columns(self):
        data = {
            "customers": pd.DataFrame(
                [{"customer_id": "C1"}]
            ),
            "cards": pd.DataFrame(
                [{"card_id": "CARD1"}]
            ),
            "merchants": pd.DataFrame(
                [{"merchant_id": "M1"}]
            ),
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

        self.assertTrue(
            any(
                "customers is missing required columns" in error
                for error in errors
            )
        )

        self.assertTrue(
            any(
                "cards is missing required columns" in error
                for error in errors
            )
        )

    def test_validation_reports_missing_input_without_traceback(self):
        output = StringIO()
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.object(
                validate_data_module,
                "RAW_DIR",
                Path(temporary_directory),
            ), redirect_stdout(output):
                result = validate_data_module.main()

        self.assertEqual(result, 1)
        self.assertIn("Validation could not run:", output.getvalue())
        self.assertIn("Required customers dataset not found", output.getvalue())

    def test_validate_data_reports_invalid_ages_and_nonfinite_amounts(
        self,
    ):
        data = valid_validation_data()

        data["customers"].loc[0, "age"] = 17
        data["customers"]["annual_income"] = data["customers"][
            "annual_income"
        ].astype(float)
        data["customers"].loc[0, "annual_income"] = float("inf")
        data["transactions"].loc[0, "amount"] = float("inf")

        errors = validate_data(data)

        self.assertTrue(
            any("age" in error for error in errors)
        )

        self.assertTrue(
            any("annual_income" in error for error in errors)
        )

        self.assertTrue(
            any("positive" in error for error in errors)
        )

    def test_validate_data_rejects_transaction_with_another_customers_card(
        self,
    ):
        data = valid_validation_data()

        data["customers"].loc[1] = {
            "customer_id": "C2",
            "age": 30,
            "annual_income": 500_000,
            "registration_date": "2025-01-01",
        }

        data["transactions"].loc[0, "customer_id"] = "C2"

        errors = validate_data(data)

        self.assertTrue(
            any(
                "ownership mismatches" in error
                for error in errors
            )
        )

    def test_validate_data_rejects_invalid_dates_statuses_and_categories(
        self,
    ):
        data = valid_validation_data()

        data["cards"].loc[0, "expiry_date"] = "2024-01-01"
        data["transactions"].loc[
            0,
            "transaction_date",
        ] = "not-a-date"
        data["transactions"].loc[
            0,
            "transaction_status",
        ] = "Unknown"
        data["transactions"].loc[
            0,
            "merchant_category",
        ] = "Unknown"

        errors = validate_data(data)

        self.assertTrue(
            any(
                "invalid dates" in error
                for error in errors
            )
        )

        self.assertTrue(
            any(
                "issue_date must be before expiry_date" in error
                for error in errors
            )
        )

        self.assertTrue(
            any(
                "transaction_status" in error
                for error in errors
            )
        )

        self.assertTrue(
            any(
                "merchant_category" in error
                for error in errors
            )
        )

    def test_validate_data_rejects_future_dates_and_category_mismatches(
        self,
    ):
        data = valid_validation_data()

        data["transactions"].loc[
            0,
            "transaction_date",
        ] = "2026-10-08"

        data["cards"].loc[
            0,
            "issue_date",
        ] = "2026-10-08"

        data["cards"].loc[
            0,
            "expiry_date",
        ] = "2026-10-06"

        data["transactions"].loc[
            0,
            "merchant_category",
        ] = "Grocery"

        errors = validate_data(data)

        self.assertTrue(
            any(
                "must not be in the future" in error
                for error in errors
            )
        )

        self.assertTrue(
            any(
                "expiry_date must be after" in error
                for error in errors
            )
        )

        self.assertTrue(
            any(
                "category mismatches" in error
                for error in errors
            )
        )

    def test_validate_data_rejects_invalid_foreign_keys(self):
        data = valid_validation_data()

        data["cards"].loc[
            0,
            "customer_id",
        ] = "C404"

        data["transactions"].loc[
            0,
            "merchant_id",
        ] = "M404"

        errors = validate_data(data)

        self.assertTrue(
            any(
                "card -> customer" in error
                for error in errors
            )
        )

        self.assertTrue(
            any(
                "transaction -> merchant" in error
                for error in errors
            )
        )

    def test_generators_produce_identical_outputs_on_repeated_runs(
        self,
    ):
        generator_names = (
            "generate_customers.py",
            "generate_cards.py",
            "generate_merchants.py",
            "generate_transactions.py",
        )

        raw_names = (
            "customers.csv",
            "cards.csv",
            "merchants.csv",
            "transactions.csv",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            shutil.copytree(
                ROOT / "src",
                root / "src",
            )

            outputs = []

            for _ in range(2):
                for generator_name in generator_names:
                    subprocess.run(
                        [
                            sys.executable,
                            str(
                                root
                                / "src"
                                / generator_name
                            ),
                        ],
                        cwd=root,
                        check=True,
                        capture_output=True,
                        text=True,
                    )

                outputs.append(
                    {
                        name: hashlib.sha256(
                            (
                                root
                                / "data"
                                / "raw"
                                / name
                            ).read_bytes()
                        ).hexdigest()
                        for name in raw_names
                    }
                )

            self.assertEqual(
                outputs[0],
                outputs[1],
            )

    def test_sql_import_maps_merchant_contact_columns_to_discarded_variables(
        self,
    ):
        import csv

        merchant_path = (
            ROOT
            / "data"
            / "processed"
            / "merchants_clean.csv"
        )

        with merchant_path.open(
            encoding="utf-8",
            newline="",
        ) as merchant_file:
            merchant_columns = next(
                csv.reader(merchant_file)
            )

        sql = (
            ROOT
            / "sql"
            / "03_load_processed_data.sql"
        ).read_text(
            encoding="utf-8"
        )

        self.assertEqual(
            len(merchant_columns),
            10,
        )

        self.assertIn(
            "@contact_person",
            sql,
        )

        self.assertIn(
            "@email",
            sql,
        )

        self.assertIn(
            "@phone",
            sql,
        )

        self.assertIn(
            "merchant_status = TRIM(@merchant_status)",
            sql,
        )


if __name__ == "__main__":
    unittest.main()
