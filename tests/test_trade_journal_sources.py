import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from trade_journal import TradeJournal


class DailyReportSourceAttributionTests(unittest.TestCase):
    def test_daily_report_separates_bot_and_external_account_activity(self):
        journal = TradeJournal()
        target_date = "2099-01-01"
        journal._cache[target_date] = [
            {
                "type": "open", "symbol": "BOTUSDT",
                "source": "local", "commission": 0.10,
            },
            {
                "type": "close", "symbol": "BOTUSDT", "source": "local+binance",
                "pnl": 1.00, "commission": 0.10,
            },
            {
                "type": "open", "symbol": "EXTUSDT",
                "source": "binance", "commission": 0.05,
            },
            {
                "type": "close", "symbol": "EXTUSDT", "source": "binance",
                "pnl": -0.50, "commission": 0.05,
            },
        ]

        report = journal.daily_report(target_date)

        self.assertEqual(report["by_source"]["bot"]["close_count"], 1)
        self.assertEqual(report["by_source"]["bot"]["net_pnl"], 0.8)
        self.assertEqual(report["by_source"]["external"]["close_count"], 1)
        self.assertEqual(report["by_source"]["external"]["net_pnl"], -0.6)


    def test_open_record_retains_entry_context_and_order_id(self):
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2099, 1, 2, 3, 4, 5)

        with TemporaryDirectory() as temp_dir:
            with patch("trade_journal.DATA_DIR", Path(temp_dir)), patch(
                "trade_journal.datetime", FixedDateTime
            ):
                journal = TradeJournal()
                journal.record_open(
                    "TESTUSDT", "LONG", 2, 10, leverage=4, margin=5, score=21,
                    order_id=99,
                    entry_context={"base_score": 20, "adjusted_score": 21},
                )
                record = journal.get_day_records("2099-01-02")[0]

        self.assertEqual(record["order_id"], 99)
        self.assertEqual(record["entry_context"]["base_score"], 20)


if __name__ == "__main__":
    unittest.main()
