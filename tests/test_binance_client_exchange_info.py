import unittest
from unittest.mock import AsyncMock

from binance_client import BinanceFuturesClient


class BinanceClientExchangeInfoTests(unittest.IsolatedAsyncioTestCase):
    def make_client(self):
        return BinanceFuturesClient({
            "api_key": "test",
            "api_secret": "test",
            "base_url": "https://example.invalid",
        })

    async def test_rules_select_requested_symbol_from_full_exchange_info(self):
        client = self.make_client()
        client._request = AsyncMock(return_value={
            "symbols": [
                {
                    "symbol": "FIRSTUSDT",
                    "filters": [
                        {"filterType": "MARKET_LOT_SIZE", "stepSize": "0.001",
                         "minQty": "0.001", "maxQty": "120"},
                        {"filterType": "MIN_NOTIONAL", "notional": "50"},
                        {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                    ],
                },
                {
                    "symbol": "TARGETUSDT",
                    "filters": [
                        {"filterType": "MARKET_LOT_SIZE", "stepSize": "1",
                         "minQty": "1", "maxQty": "9000000"},
                        {"filterType": "MIN_NOTIONAL", "notional": "5"},
                        {"filterType": "PRICE_FILTER", "tickSize": "0.0001"},
                    ],
                },
            ],
        })

        step, min_qty, max_qty, min_notional = await client._quantity_rule("TARGETUSDT")
        tick = await client._price_tick("TARGETUSDT")

        self.assertEqual(str(step), "1")
        self.assertEqual(str(min_qty), "1")
        self.assertEqual(str(max_qty), "9000000")
        self.assertEqual(str(min_notional), "5")
        self.assertEqual(str(tick), "0.0001")
        client._request.assert_awaited_once()

    async def test_missing_symbol_raises_clear_error(self):
        client = self.make_client()
        client._request = AsyncMock(return_value={"symbols": []})

        with self.assertRaisesRegex(ValueError, "exchange rules missing for MISSINGUSDT"):
            await client._quantity_rule("MISSINGUSDT")


if __name__ == "__main__":
    unittest.main()
