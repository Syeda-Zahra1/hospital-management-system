import unittest
from datetime import date
from decimal import Decimal

from flask import Flask

from blueprints.hr import _is_full_payroll_month, _money
from blueprints.reports import _csv_text, _date_range


class ERPModuleValidationTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_report_date_range_accepts_valid_dates(self):
        with self.app.test_request_context(
            "/reports/?start_date=2026-02-01&end_date=2026-02-28"
        ):
            self.assertEqual(_date_range(), (date(2026, 2, 1), date(2026, 2, 28)))

    def test_report_date_range_rejects_reversed_and_excessive_ranges(self):
        for query in (
            "?start_date=2026-03-01&end_date=2026-02-28",
            "?start_date=2010-01-01&end_date=2021-01-01",
        ):
            with self.subTest(query=query), self.app.test_request_context("/reports/" + query):
                with self.assertRaises(ValueError):
                    _date_range()

    def test_csv_text_neutralizes_spreadsheet_formulas(self):
        self.assertEqual(_csv_text("=SUM(A1:A2)"), "'=SUM(A1:A2)")
        self.assertEqual(_csv_text("-1"), "'-1")
        self.assertEqual(_csv_text("Medicine"), "Medicine")
        self.assertEqual(_csv_text(12), 12)

    def test_payroll_requires_a_complete_calendar_month(self):
        self.assertTrue(_is_full_payroll_month(date(2024, 2, 1), date(2024, 2, 29)))
        self.assertFalse(_is_full_payroll_month(date(2024, 2, 1), date(2024, 2, 28)))
        self.assertFalse(_is_full_payroll_month(date(2024, 2, 2), date(2024, 2, 29)))

    def test_salary_component_amount_is_limited_to_cents(self):
        self.assertEqual(_money("1200.50", "component"), Decimal("1200.50"))
        self.assertEqual(_money("1200.500", "component"), Decimal("1200.500"))
        with self.assertRaisesRegex(ValueError, "two decimal places"):
            _money("1200.501", "component")


if __name__ == "__main__":
    unittest.main()
