import unittest
from unittest.mock import patch

from risk_manager import RiskManager
from trader import Trader


class DailyLossGateTests(unittest.TestCase):
    def test_daily_loss_gate_uses_realized_account_currency_pnl(self):
        risk = RiskManager({
            "max_positions": 3,
            "max_daily_loss_pct": 10,
        })

        allowed, _ = risk.can_open(0, balance=100)
        self.assertTrue(allowed)

        risk.record_realized_pnl(-9.99)
        allowed, _ = risk.can_open(0, balance=95)
        self.assertTrue(allowed)

        risk.record_realized_pnl(-0.01)
        allowed, reason = risk.can_open(0, balance=90)
        self.assertFalse(allowed)
        self.assertIn("10%", reason)

    def test_position_limit_still_has_priority(self):
        risk = RiskManager({
            "max_positions": 2,
            "max_daily_loss_pct": 10,
        })

        allowed, reason = risk.can_open(2, balance=100)

        self.assertFalse(allowed)
        self.assertIn("最大持仓", reason)

    def test_restart_seed_uses_only_bot_records_and_includes_commission(self):
        trader = Trader.__new__(Trader)
        trader.risk = RiskManager({
            "max_positions": 3,
            "max_daily_loss_pct": 1,
        })
        records = [
            {"type": "close", "source": "local+binance", "pnl": -0.80, "commission": 0.10},
            {"type": "open", "source": "local", "commission": 0.10},
            {"type": "close", "source": "binance", "pnl": -99, "commission": 0},
        ]

        with patch("trader.journal.get_day_records", return_value=records):
            trader._seed_daily_risk_from_journal()

        allowed, _ = trader.risk.can_open(0, balance=100)
        self.assertFalse(allowed)


if __name__ == "__main__":
    unittest.main()
