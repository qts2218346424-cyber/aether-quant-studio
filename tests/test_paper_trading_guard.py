"""单元测试: 纯模拟防实盘硬核安全拦截器 (test_paper_trading_guard.py)"""
import asyncio
from config import load_config
from binance_client import BinanceFuturesClient
from trader import Trader


def test_config_safety_locks():
    cfg = load_config()
    assert cfg.get("live_trading_enabled") is False, "实盘开关必须为 False"
    assert cfg.get("paper_trading") is True, "模拟开关必须为 True"


def test_client_market_order_interception():
    async def _inner():
        client = BinanceFuturesClient()
        assert client.live_trading_enabled is False
        assert client.paper_trading is True

        # 尝试市价下单，必须被模拟拦截
        res = await client.place_order("BTCUSDT", "BUY", "MARKET", quantity=0.01)
        assert res["status"] == "FILLED"
        assert res.get("_local_execution", {}).get("is_paper") is True
        assert "paper_" in res.get("clientOrderId", "")

    asyncio.run(_inner())


def test_client_limit_and_stop_interception():
    async def _inner():
        client = BinanceFuturesClient()

        # 尝试限价下单
        limit_res = await client.place_limit_order("ETHUSDT", "BUY", "LONG", 0.5, 3000.0)
        assert limit_res["status"] == "NEW"
        assert limit_res.get("_is_paper") is True

        # 尝试设置交易所保护止损
        stop_res = await client.place_protective_stop("ETHUSDT", "LONG", "STOP_MARKET", 2900.0, "SELL")
        assert stop_res["status"] == "NEW"
        assert stop_res.get("_is_paper") is True

        # 尝试撤单
        cancel_res = await client.cancel_order("ETHUSDT", order_id=12345)
        assert cancel_res["status"] == "CANCELED"
        assert cancel_res.get("_is_paper") is True

    asyncio.run(_inner())


def test_trader_safety_status():
    async def _inner():
        t = Trader()
        assert t.live_trading_enabled is False
        assert t.paper_trading is True
        assert t.auto_trade is False

        status = await t.get_status()
        assert status.get("live_trading_enabled") is False
        assert status.get("paper_trading") is True

    asyncio.run(_inner())
