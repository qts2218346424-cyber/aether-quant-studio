from src.paths import load_frontend_bundle_text
import unittest
from unittest.mock import patch
from pathlib import Path
from decimal import Decimal
from types import SimpleNamespace

from binance_client import BinanceFuturesClient
from trader import Trader


class QuantitySizingTests(unittest.IsolatedAsyncioTestCase):
    async def test_quantity_for_notional_rounds_up_to_market_step(self):
        client = BinanceFuturesClient({
            "api_key": "",
            "api_secret": "",
            "base_url": "https://example.invalid",
            "ws_url": "wss://example.invalid",
        })

        async def fake_rule(symbol):
            return Decimal("1"), Decimal("1"), Decimal("1000"), Decimal("5")

        client._quantity_rule = fake_rule
        # quantity_for_notional keeps a 6% cushion when targeting the exchange minimum.
        self.assertEqual(
            await client.quantity_for_notional("TESTUSDT", 0.047, 5),
            113.0,
        )

    async def test_normalize_quantity_still_rounds_closes_down(self):
        client = BinanceFuturesClient({
            "api_key": "",
            "api_secret": "",
            "base_url": "https://example.invalid",
            "ws_url": "wss://example.invalid",
        })

        async def fake_rule(symbol):
            return Decimal("1"), Decimal("1"), Decimal("1000"), Decimal("5")

        client._quantity_rule = fake_rule
        self.assertEqual(await client.normalize_quantity("TESTUSDT", 55.5), 55.0)

    async def test_minimum_notional_above_market_maximum_is_rejected(self):
        client = BinanceFuturesClient({
            "api_key": "",
            "api_secret": "",
            "base_url": "https://example.invalid",
            "ws_url": "wss://example.invalid",
        })

        async def fake_rule(symbol):
            return Decimal("1"), Decimal("1"), Decimal("100"), Decimal("50")

        client._quantity_rule = fake_rule
        with self.assertRaisesRegex(ValueError, "above market maximum"):
            await client.quantity_for_notional("TESTUSDT", 0.047, 5)

    async def test_open_quantity_below_minimum_notional_is_rejected(self):
        client = BinanceFuturesClient({
            "api_key": "",
            "api_secret": "",
            "base_url": "https://example.invalid",
            "ws_url": "wss://example.invalid",
        })

        async def fake_rule(symbol):
            return Decimal("1"), Decimal("1"), Decimal("1000"), Decimal("5")

        client._quantity_rule = fake_rule
        with self.assertRaisesRegex(ValueError, "below the market minimum"):
            await client.validate_market_open_quantity("TESTUSDT", 0.047, 55)


class LeverageCapTests(unittest.IsolatedAsyncioTestCase):
    async def test_requested_leverage_is_clamped_to_symbol_cap(self):
        client = BinanceFuturesClient({
            "api_key": "",
            "api_secret": "",
            "base_url": "https://example.invalid",
            "ws_url": "wss://example.invalid",
        })

        async def fake_request(method, path, params=None, signed=False):
            self.assertEqual(("GET", "/fapi/v1/leverageBracket", True), (method, path, signed))
            return [{
                "symbol": "TESTUSDT",
                "brackets": [{"initialLeverage": 5}, {"initialLeverage": 10}],
            }]

        client._request = fake_request
        self.assertEqual(await client.clamp_leverage("TESTUSDT", 20), (10, 10))

    def test_recommendation_uses_symbol_leverage_cap(self):
        trader = Trader.__new__(Trader)
        leverage, *_ = trader._calc_recommendation(
            balance=100,
            price=1,
            atr_pct=0.4,
            side_en="LONG",
            max_leverage=10,
        )
        self.assertEqual(leverage, 10)


class AutomaticEntryGuardTests(unittest.TestCase):
    def test_auto_entry_requires_base_score_above_weighted_threshold_floor(self):
        trader = Trader.__new__(Trader)
        trader.strategy = SimpleNamespace(cfg={}, threshold=15)

        self.assertEqual(trader._auto_entry_min_base_score(), 20.0)

    def test_exchange_minimum_cannot_lift_swing_trade_above_strategy_cap(self):
        plan = Trader._minimum_notional_leverage_plan(
            planned_notional=53,
            balance=6.63,
            starting_leverage=4,
            leverage_cap=6,
            max_entry_margin_pct=25,
        )

        self.assertFalse(plan["allowed"])
        self.assertGreater(plan["required_leverage"], plan["leverage_cap"])

    def test_recommendation_drops_current_forming_candle(self):
        rows = [["closed-1"], ["closed-2"], ["forming"]]

        self.assertEqual(
            Trader._closed_kline_rows(rows),
            [["closed-1"], ["closed-2"]],
        )

    def test_zero_technical_signal_is_a_final_veto(self):
        result = {
            "signal": 0,
            "score": 70,
            "factors": ["resistance too close; cancel long"],
        }

        self.assertEqual(Trader._technical_recommendation_signal(result), 0)

    def test_profit_bet_uses_only_a_fraction_of_daily_profit(self):
        plan = Trader._profit_bet_plan(
            balance=10,
            daily_profit=2,
            atr_pct=1.5,
            cfg={
                "allocation_pct": 25,
                "max_wallet_risk_pct": 3,
                "stop_atr": 1.5,
                "min_stop_pct": 1.2,
                "max_stop_pct": 3,
                "max_notional_multiple": 1.5,
            },
        )

        self.assertEqual(plan["allocation"], 0.5)
        self.assertEqual(plan["risk_budget"], 0.3)
        self.assertAlmostEqual(plan["stop_pct"], 2.25)
        self.assertAlmostEqual(plan["target_notional"], 13.3333333333)


class UserTradeWindowTests(unittest.IsolatedAsyncioTestCase):
    async def test_long_user_trade_range_is_split_into_exchange_valid_windows(self):
        client = BinanceFuturesClient({
            "api_key": "",
            "api_secret": "",
            "base_url": "https://example.invalid",
            "ws_url": "wss://example.invalid",
        })
        calls = []

        async def fake_request(method, path, params=None, signed=False):
            calls.append(dict(params))
            start = int(params["startTime"])
            return [{"id": start + 1, "time": start, "realizedPnl": "0.1"}]

        client._request = fake_request
        rows, truncated = await client.get_user_trades_time_range(
            "TESTUSDT", 0, 19, limit=1000, window_ms=10)

        self.assertEqual(len(calls), 2)
        self.assertEqual([row["id"] for row in rows], [1, 11])
        self.assertEqual(truncated, [])


class FillResponseTests(unittest.TestCase):
    def test_filled_result_uses_real_quantity(self):
        result = Trader._order_execution({
            "orderId": 7,
            "status": "FILLED",
            "executedQty": "55",
            "avgPrice": "0.0475",
            "_local_execution": {"requested_qty": 55.5, "normalized_qty": 55},
        })
        self.assertTrue(result["completed"])
        self.assertFalse(result["partial"])
        self.assertEqual(result["executed_qty"], 55.0)
        self.assertEqual(result["normalized_qty"], 55.0)

    def test_partial_result_does_not_count_as_completed(self):
        result = Trader._order_execution({
            "orderId": 8,
            "status": "PARTIALLY_FILLED",
            "executedQty": "12",
            "_local_execution": {"requested_qty": 55.5, "normalized_qty": 55},
        })
        self.assertFalse(result["completed"])
        self.assertTrue(result["partial"])
        self.assertEqual(result["executed_qty"], 12.0)


class CloseAccountingTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_uses_fresh_exit_context_instead_of_stale_position_cache(self):
        class FakeClient:
            async def normalize_quantity(self, symbol, quantity):
                return 2.0

            async def market_close_long(self, symbol, quantity):
                return {
                    "orderId": 99,
                    "status": "FILLED",
                    "executedQty": "2",
                    "avgPrice": "110",
                    "_local_execution": {
                        "requested_qty": quantity,
                        "normalized_qty": quantity,
                    },
                }

        class FakeRisk:
            def __init__(self):
                self.recorded = []

            def record_realized_pnl(self, pnl):
                self.recorded.append(pnl)

        trader = Trader.__new__(Trader)
        trader.client = FakeClient()
        trader.positions_cache = {
            "TESTUSDT": {"entry_price": 50, "mark_price": 51},
        }
        trader.latest_klines = {}
        trader.trades_log = []
        trader.execution_events = []
        trader.risk = FakeRisk()

        with patch("trader.journal.record_close") as record_close:
            result = await trader._close_pos(
                "TESTUSDT", "LONG", 2, "test close",
                entry_price=100, exit_price=105,
            )

        self.assertTrue(result["ok"])
        args = record_close.call_args.args
        self.assertEqual(args[3], 100)
        self.assertEqual(args[4], 110)
    async def test_long_user_trade_range_is_split_into_exchange_valid_windows(self):
        client = BinanceFuturesClient({
            "api_key": "",
            "api_secret": "",
            "base_url": "https://example.invalid",
            "ws_url": "wss://example.invalid",
        })
        calls = []

        async def fake_request(method, path, params=None, signed=False):
            calls.append(dict(params))
            start = int(params["startTime"])
            return [{"id": start + 1, "time": start, "realizedPnl": "0.1"}]

        client._request = fake_request
        rows, truncated = await client.get_user_trades_time_range(
            "TESTUSDT", 0, 19, limit=1000, window_ms=10)

        self.assertEqual(len(calls), 2)
        self.assertEqual([row["id"] for row in rows], [1, 11])
        self.assertEqual(truncated, [])


class FillResponseTests(unittest.TestCase):
    def test_filled_result_uses_real_quantity(self):
        result = Trader._order_execution({
            "orderId": 7,
            "status": "FILLED",
            "executedQty": "55",
            "avgPrice": "0.0475",
            "_local_execution": {"requested_qty": 55.5, "normalized_qty": 55},
        })
        self.assertTrue(result["completed"])
        self.assertFalse(result["partial"])
        self.assertEqual(result["executed_qty"], 55.0)
        self.assertEqual(result["normalized_qty"], 55.0)

    def test_partial_result_does_not_count_as_completed(self):
        result = Trader._order_execution({
            "orderId": 8,
            "status": "PARTIALLY_FILLED",
            "executedQty": "12",
            "_local_execution": {"requested_qty": 55.5, "normalized_qty": 55},
        })
        self.assertFalse(result["completed"])
        self.assertTrue(result["partial"])
        self.assertEqual(result["executed_qty"], 12.0)


class CloseAccountingTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_uses_fresh_exit_context_instead_of_stale_position_cache(self):
        class FakeClient:
            async def normalize_quantity(self, symbol, quantity):
                return 2.0

            async def market_close_long(self, symbol, quantity):
                return {
                    "orderId": 99,
                    "status": "FILLED",
                    "executedQty": "2",
                    "avgPrice": "110",
                    "_local_execution": {
                        "requested_qty": quantity,
                        "normalized_qty": quantity,
                    },
                }

        class FakeRisk:
            def __init__(self):
                self.recorded = []

            def record_realized_pnl(self, pnl):
                self.recorded.append(pnl)

        trader = Trader.__new__(Trader)
        trader.client = FakeClient()
        trader.positions_cache = {
            "TESTUSDT": {"entry_price": 50, "mark_price": 51},
        }
        trader.latest_klines = {}
        trader.trades_log = []
        trader.execution_events = []
        trader.risk = FakeRisk()

        with patch("trader.journal.record_close") as record_close:
            result = await trader._close_pos(
                "TESTUSDT", "LONG", 2, "test close",
                entry_price=100, exit_price=105,
            )

        self.assertTrue(result["ok"])
        args = record_close.call_args.args
        self.assertEqual(args[3], 100)
        self.assertEqual(args[4], 110)
        self.assertEqual(args[6], 20)
        self.assertEqual(trader.risk.recorded, [20])


class TraderInitializationTests(unittest.TestCase):
    def test_status_dependencies_are_initialized(self):
        trader = Trader()

        self.assertIn(trader.entry_decision_mode, {
            "strategy_direct", "committee", "typesafe_hybrid",
            "typesafe_jev", "typesafe_evaluator", "typesafe_autonomous", "hybrid",
        })
        self.assertIsNotNone(trader.ai_committee)
        self.assertIsInstance(trader.ai_reviews_log, list)


class DashboardContractTests(unittest.TestCase):
    def test_dashboard_contains_execution_diagnostic_tab(self):
        html = load_frontend_bundle_text()

        self.assertIn('data-tab="execution"', html)
        self.assertIn("renderExecutionEvents", html)
        self.assertIn("set-trail-after-tp", html)
        self.assertIn("Bot-managed", html)
        self.assertIn("set-max-daily-loss", html)
        self.assertIn("execution_rejections", html)
        self.assertIn("set-candidate-scan-limit", html)
        self.assertIn('data-tab="rankings"', html)
        self.assertIn("loadMarketRankings", html)
        self.assertNotIn("manualOrder(", html)
        self.assertNotIn("recommendBuy(", html)

    def test_low_price_market_rankings_return_three_top_lists(self):
        rankings = Trader.build_market_rankings([
            {"symbol": "AAAUSDT", "lastPrice": "1", "priceChangePercent": "5",
             "quoteVolume": "100", "volume": "1000"},
            {"symbol": "BBBUSDT", "lastPrice": "4.9", "priceChangePercent": "-8",
             "quoteVolume": "300", "volume": "2000"},
            {"symbol": "EXPENSIVEUSDT", "lastPrice": "5", "priceChangePercent": "99",
             "quoteVolume": "999", "volume": "1"},
        ], max_price=5, limit=20)

        self.assertEqual(rankings["matched"], 2)
        self.assertEqual(rankings["gainers"][0]["symbol"], "AAAUSDT")
        self.assertEqual(rankings["losers"][0]["symbol"], "BBBUSDT")
        self.assertEqual(rankings["volume"][0]["symbol"], "BBBUSDT")


if __name__ == "__main__":
    unittest.main()
