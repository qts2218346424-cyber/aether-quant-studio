import json
import unittest
from pathlib import Path

from trader import Trader


class StrategyMarginOptimizationTests(unittest.TestCase):
    def test_margin_multiplier_applies_after_exchange_minimum(self):
        trader = Trader.__new__(Trader)
        trader.cfg = {"risk": {"entry_margin_multiplier": 1.5}}

        # The account is small enough that the 5U exchange minimum dominates.
        self.assertEqual(
            trader._planned_entry_notional(
                balance=4.41887622, size_pct=0.126, leverage=6
            ),
            7.5,
        )

    def test_margin_multiplier_scales_normal_sizing(self):
        trader = Trader.__new__(Trader)
        trader.cfg = {"risk": {"entry_margin_multiplier": 1.5}}

        self.assertAlmostEqual(
            trader._planned_entry_notional(
                balance=100, size_pct=0.126, leverage=6
            ),
            113.4,
        )

    def test_invalid_or_missing_multiplier_defaults_to_one(self):
        trader = Trader.__new__(Trader)
        trader.cfg = {"risk": {}}
        self.assertEqual(
            trader._planned_entry_notional(
                balance=100, size_pct=0.126, leverage=6
            ),
            75.6,
        )

    def test_config_contains_strategy_and_risk_guards(self):
        cfg = json.loads(
            Path("config.json").read_text(encoding="utf-8")
        )
        strategy = cfg["strategy"]
        risk = cfg["risk"]
        self.assertEqual(strategy["signal_threshold"], 45)
        self.assertEqual(strategy["scan_threshold"], 45)
        self.assertEqual(strategy["long_threshold"], 55)
        self.assertEqual(strategy["short_threshold"], 50)
        self.assertIn("BANKUSDT", strategy["blacklist"])
        self.assertIn("BLESSUSDT", strategy["blacklist"])
        self.assertEqual(risk["entry_margin_multiplier"], 1.5)
        self.assertEqual(risk["max_positions"], 3)
        self.assertEqual(
            strategy["position_management"]["max_entry_margin_pct"], 25
        )


if __name__ == "__main__":
    unittest.main()
