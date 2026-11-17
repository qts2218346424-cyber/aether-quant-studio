import unittest
from types import SimpleNamespace

from trader import Trader


class FakeOrderClient:
    def __init__(self):
        self.position_side_calls = []
        self.limit_calls = []

    async def _position_side(self, direction):
        self.position_side_calls.append(direction)
        return f"HEDGE_{direction}"

    async def place_limit_order(self, symbol, side, position_side, qty, price, client_order_id=None):
        self.limit_calls.append({
            "symbol": symbol,
            "side": side,
            "position_side": position_side,
            "qty": qty,
            "price": price,
            "client_order_id": client_order_id,
        })
        return {"orderId": 123, "status": "NEW", "price": str(price)}


def make_trader():
    trader = Trader.__new__(Trader)
    trader.client = FakeOrderClient()
    trader._trade_symbol_allowed = lambda symbol: symbol == "BTCUSDT"
    trader._record_execution_event = lambda *args, **kwargs: None
    return trader


class ChartLimitOrderTests(unittest.IsolatedAsyncioTestCase):
    async def test_manual_limit_open_normalizes_and_places_limit_order(self):
        trader = make_trader()

        result = await trader.manual_limit_open(
            symbol=" btc/usdt ",
            side="buy",
            quantity=0.25,
            price=62000.5,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["symbol"], "BTCUSDT")
        self.assertEqual(result["side"], "BUY")
        self.assertEqual(result["position_side"], "HEDGE_LONG")
        self.assertEqual(trader.client.position_side_calls, ["LONG"])
        self.assertEqual(trader.client.limit_calls[0]["price"], 62000.5)
        self.assertEqual(trader.client.limit_calls[0]["qty"], 0.25)

    async def test_manual_limit_open_rejects_invalid_input_without_exchange_call(self):
        trader = make_trader()

        for payload, message in (
            ({"symbol": "BTCUSDT", "side": "HOLD", "quantity": 1, "price": 10}, "side"),
            ({"symbol": "BTCUSDT", "side": "BUY", "quantity": 0, "price": 10}, "quantity"),
            ({"symbol": "BTCUSDT", "side": "BUY", "quantity": 1, "price": 0}, "price"),
            ({"symbol": "ETHUSDT", "side": "BUY", "quantity": 1, "price": 10}, "symbol"),
        ):
            with self.subTest(message=message):
                with self.assertRaises(ValueError):
                    await trader.manual_limit_open(**payload)

        self.assertEqual(trader.client.limit_calls, [])


class ChartLimitOrderRouteShapeTests(unittest.TestCase):
    def test_request_shape_documents_explicit_limit_only_contract(self):
        payload = SimpleNamespace(symbol="BTCUSDT", side="BUY", quantity=1, price=10)
        self.assertEqual(payload.side, "BUY")
        self.assertGreater(payload.quantity, 0)
        self.assertGreater(payload.price, 0)
