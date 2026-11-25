import unittest

from werkzeug.datastructures import MultiDict

from blueprints.finance import _entry_lines, _parse_amount
from erp_common import active_branch


class RecordingCursor:
    def __init__(self, row):
        self.row = row
        self.query = None
        self.params = None

    def execute(self, query, params):
        self.query = query
        self.params = params

    def fetchone(self):
        return self.row


class FinanceValidationTests(unittest.TestCase):
    def test_accepts_balanced_journal_lines(self):
        form = MultiDict([
            ("account_id", "1"),
            ("account_id", "2"),
            ("line_description", "Cash received"),
            ("line_description", "Service revenue"),
            ("debit", "1250.00"),
            ("debit", "0"),
            ("credit", "0"),
            ("credit", "1250.00"),
        ])

        lines = _entry_lines(form)

        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0][2], _parse_amount("1250.00"))
        self.assertEqual(lines[1][3], _parse_amount("1250.00"))

    def test_rejects_unbalanced_journal_lines(self):
        form = MultiDict([
            ("account_id", "1"),
            ("account_id", "2"),
            ("line_description", ""),
            ("line_description", ""),
            ("debit", "100.00"),
            ("debit", "0"),
            ("credit", "0"),
            ("credit", "99.99"),
        ])

        with self.assertRaisesRegex(ValueError, "must be equal"):
            _entry_lines(form)

    def test_rejects_a_line_with_both_sides_or_neither_side(self):
        for debit, credit in (("5", "5"), ("0", "0")):
            form = MultiDict([
                ("account_id", "1"),
                ("account_id", "2"),
                ("line_description", ""),
                ("line_description", ""),
                ("debit", debit),
                ("debit", "0"),
                ("credit", credit),
                ("credit", "5"),
            ])
            with self.subTest(debit=debit, credit=credit):
                with self.assertRaisesRegex(ValueError, "either a debit or a credit"):
                    _entry_lines(form)

    def test_rejects_amounts_with_more_than_two_decimal_places(self):
        with self.assertRaisesRegex(ValueError, "two decimal places"):
            _parse_amount("1.001")

    def test_rejects_non_finite_amounts(self):
        with self.assertRaisesRegex(ValueError, "between 0"):
            _parse_amount("NaN")


class BranchScopeTests(unittest.TestCase):
    def test_selected_branch_must_be_granted_and_active(self):
        cursor = RecordingCursor({"branch_id": 4, "branch_name": "North"})

        branch = active_branch(cursor, user_id=9, selected_branch_id=4)

        self.assertEqual(branch["branch_id"], 4)
        self.assertIn("JOIN user_branch_access", cursor.query)
        self.assertIn("b.is_active = TRUE", cursor.query)
        self.assertEqual(cursor.params, (9, 4))


if __name__ == "__main__":
    unittest.main()


