"""Tests for Dual-Engine Hybrid Mode (Gatekeeper + Autonomous Hunter) in Trader."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from trader import Trader


class TestTypesafeHybridExecution(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Create trader with mocked dependencies
        with patch("trader.load_config") as mock_cfg, \
             patch("trader.BinanceFuturesClient") as mock_client:
            mock_cfg.return_value = {
                "api_key": "dummy",
                "api_secret": "dummy",
                "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
                "entry_decision_mode": "typesafe_hybrid",
                "typesafe": {
                    "enabled": True,
                    "model": "jev-latest",
                    "autonomous_hunter": {
                        "enabled": True,
                        "min_confidence": 0.68,
                        "min_playbook_score": 2.5,
                        "scan_interval_sec": 0.0,  # no throttle for tests
                    },
                },
                "strategy": {"market_selection": {"allow_all_symbols": True, "max_price": 250000.0}},
                "risk": {},
            }
            self.trader = Trader()
            self.trader.client.get_positions = AsyncMock(return_value=[])
            self.trader.auto_trade = True
            self.trader.running = True

    async def test_hybrid_mode_autonomous_hunter_pre_reviewed_passthrough(self):
        """When Autonomous Hunter discovers an S-tier setup, _execute_signal accepts review directly."""
        hunter_review = {
            "approved": True,
            "action": "LONG",
            "confidence": 0.86,
            "composite_score": 88.5,
            "breakout_quality": 3.4,
            "risk_level": 1.2,
            "playbook_score": 3.8,
            "discipline_violation": 0.05,
            "latency_ms": 15,
            "reason": "Jev Autonomous Hunter S-tier LONG (conf=0.86, pb=3.8)",
        }

        # Mock position opening
        mock_order = {
            "orderId": "12345",
            "status": "FILLED",
            "executedQty": "1.0",
            "avgPrice": "245.0",
            "origQty": "1.0",
        }
        self.trader._open_position_maker_first = AsyncMock(return_value=mock_order)
        self.trader._liquidity_snapshot = AsyncMock(return_value={"allowed": True})
        self.trader._smart_money_snapshot = AsyncMock(return_value={"score": 25.0})
        self.trader._prepare_new_position = AsyncMock(return_value=(10, 20))
        self.trader.client.get_balance = AsyncMock(return_value=1000.0)
        self.trader.client.set_leverage = AsyncMock(return_value={"leverage": 10})
        self.trader.client.get_account = AsyncMock(return_value={"totalWalletBalance": "1000.0"})
        self.trader.client.quantity_for_notional = AsyncMock(return_value=1.0)
        self.trader.client.clamp_leverage = AsyncMock(return_value=(10, 20))
        self.trader.risk.can_open = MagicMock(return_value=(True, "ok"))

        # Pre-reviewed candidate context from Autonomous Hunter
        candidate_context = {
            "score": 60,
            "base_score": 60,
            "is_autonomous": True,
            "typesafe_review": hunter_review,
            "indicators": {"rsi": 55.0, "atr_pct": 2.0},
            "smart_money": {"score": 25.0, "intent": "拉升"},
            "smart_money_decision": {"pass": True, "reason": "ok"},
        }

        with patch.object(self.trader.typesafe_engine, "evaluate_entry", new_callable=AsyncMock) as mock_eval:
            await self.trader._execute_signal(
                symbol="SOLUSDT",
                signal=1,
                price=245.0,
                mode="aggressive",
                candidate_context=candidate_context,
            )

            # verify that evaluate_entry was NOT called again (reuse hunter review)
            mock_eval.assert_not_called()
            # verify position opened
            self.trader._open_position_maker_first.assert_called_once()

    async def test_hybrid_mode_gatekeeper_vetoes_bad_candidate(self):
        """When baseline strategy produces a candidate, Gatekeeper vetoes low quality setup."""
        veto_review = {
            "approved": False,
            "status": "rejected",
            "confidence": 0.52,
            "risk_level_score": 3.8,
            "breakout_quality_score": 1.1,
            "playbook_score": 0.8,
            "discipline_violation_prob": 0.45,
            "latency_ms": 20,
            "reason": "Rejected by Jev: high_risk_score, poor_breakout_quality",
        }

        self.trader._open_position_maker_first = AsyncMock()
        self.trader._liquidity_snapshot = AsyncMock(return_value={"allowed": True})
        self.trader._smart_money_snapshot = AsyncMock(return_value={"score": 20.0})
        self.trader.client.get_account = AsyncMock(return_value={"totalWalletBalance": "1000.0"})
        self.trader.client.quantity_for_notional = AsyncMock(return_value=0.001)
        self.trader.client.clamp_leverage = AsyncMock(return_value=(10, 20))
        self.trader._prepare_new_position = AsyncMock(return_value=(10, 20))
        self.trader.risk.can_open = MagicMock(return_value=(True, "ok"))

        with patch.object(self.trader.typesafe_engine, "evaluate_entry", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = veto_review

            # Candidate without pre-review (from traditional strategy scanner, reaches score >= 60)
            await self.trader._execute_signal(
                symbol="BTCUSDT",
                signal=1,
                price=90000.0,
                mode="conservative",
                candidate_context={
                    "score": 62,
                    "base_score": 62,
                    "smart_money": {"score": 20.0, "intent": "拉升"},
                    "smart_money_decision": {"pass": True, "reason": "ok"},
                },
            )

            # verify gatekeeper was called
            mock_eval.assert_called_once()
            # verify position was NOT opened
            self.trader._open_position_maker_first.assert_not_called()

    async def test_autonomous_hunter_sweep_triggers_execution(self):
        """_run_jev_autonomous_hunter_sweep scans unheld coins and triggers _execute_signal."""
        self.trader.symbols = ["AVAXUSDT"]
        self.trader.position_symbols = []
        self.trader.latest_klines = {"AVAXUSDT": {"close": 35.0}}
        self.trader.klines_cache = {"AVAXUSDT": {"closes": [33.0, 34.0, 35.0]}}
        self.trader.latest_result = {"AVAXUSDT": {"score": 52, "indicators": {"rsi": 58.0}}}

        s_tier_review = {
            "approved": True,
            "action": "LONG",
            "confidence": 0.89,
            "playbook_score": 3.5,
            "breakout_quality": 3.1,
            "risk_level": 1.2,
            "discipline_violation": 0.05,
            "latency_ms": 12,
            "playbook": {"strategy_title": "ICT银弹模型"},
        }

        with patch.object(self.trader.typesafe_engine, "scan_autonomous_hunter", new_callable=AsyncMock) as mock_scan, \
             patch.object(self.trader, "_execute_signal", new_callable=AsyncMock) as mock_exec, \
             patch.object(self.trader, "_smart_money_snapshot", new_callable=AsyncMock) as mock_sm, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            mock_sm.return_value = {"score": 25.0}
            mock_scan.return_value = s_tier_review

            held = set()
            await self.trader._run_jev_autonomous_hunter_sweep(held)

            mock_scan.assert_called_once()
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args
            self.assertEqual(call_args[0][0], "AVAXUSDT")
            self.assertEqual(call_args[0][1], 1)  # LONG
            self.assertTrue(call_args[1]["candidate_context"]["is_autonomous"])
            self.assertIn("AVAXUSDT", held)

    async def test_typesafe_evaluator_mode_strictly_gatekeeper_only(self):
        """In typesafe_evaluator mode, traditional strategy coarse-screens and Jev evaluates with veto power."""
        self.trader.entry_decision_mode = "typesafe_evaluator"
        self.trader.symbols = ["BTCUSDT"]

        # 1. Verify gatekeeper vetoes poor candidate from traditional strategy
        veto_review = {
            "approved": False,
            "action": "HOLD",
            "confidence": 0.45,
            "reason": "Rejected by Jev: low_confidence",
            "latency_ms": 15,
        }
        self.trader._open_position_maker_first = AsyncMock()
        self.trader._liquidity_snapshot = AsyncMock(return_value={"allowed": True})
        self.trader._smart_money_snapshot = AsyncMock(return_value={"score": 10.0})

        with patch.object(self.trader.typesafe_engine, "evaluate_entry", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = veto_review
            await self.trader._execute_signal(
                symbol="BTCUSDT",
                signal=1,
                price=65000.0,
                mode="aggressive",
                candidate_context={"score": 60, "base_score": 60, "smart_money_decision": {"pass": True}},
            )
            # Gatekeeper evaluated and rejected -> position was NOT opened
            mock_eval.assert_called_once()
            self.trader._open_position_maker_first.assert_not_called()


if __name__ == "__main__":
    unittest.main()
