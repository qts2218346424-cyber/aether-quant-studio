import unittest

from analyze_trades import rows_in_time_window


class TradeAnalysisWindowTests(unittest.TestCase):
    def test_rows_in_time_window_keeps_boundaries_and_excludes_old_rows(self):
        rows = [
            {"time": 99, "income": "1"},
            {"time": 100, "income": "2"},
            {"time": "150", "income": "3"},
            {"time": 200, "income": "4"},
            {"time": 201, "income": "5"},
            {"time": "bad", "income": "6"},
        ]

        result = rows_in_time_window(rows, 100, 200)

        self.assertEqual([row["income"] for row in result], ["2", "3", "4"])


if __name__ == "__main__":
    unittest.main()
