from src.paths import load_frontend_bundle_text
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app import app
from trader import Trader


client = TestClient(app)
html = load_frontend_bundle_text()


def test_frontend_has_ranking_creation_and_candidate_source_controls():
    """Verify frontend HTML contains candidate source dropdown and ranking creation button."""
    assert "blog-candidate-source" in html
    assert "onBlogCandidateSourceChange" in html
    assert "generateBlogForSymbol" in html
    assert "✍️ 创作" in html
    assert "🔥 24H 涨幅榜" in html
    assert "💥 24H 跌幅榜" in html


@pytest.mark.anyio
async def test_trader_evaluate_symbol_for_blog_candidate():
    """Verify Trader.evaluate_symbol_for_blog_candidate computes technical levels."""
    trader = Trader()
    mock_klines = [
        [1700000000000, "100.0", "105.0", "98.0", "102.0", "5000", 1700000060000]
        for _ in range(65)
    ]
    with patch.object(trader.client, "get_klines", new=AsyncMock(return_value=mock_klines)):
        ticker = {
            "symbol": "SOLUSDT",
            "lastPrice": "102.0",
            "priceChangePercent": "14.5",
            "quoteVolume": "500000000",
        }
        cand = await trader.evaluate_symbol_for_blog_candidate("SOLUSDT", ticker=ticker, default_side="LONG")
        assert cand["symbol"] == "SOLUSDT"
        assert cand["price"] == 102.0
        assert cand["change_24h"] == 14.5
        assert cand["side_en"] == "LONG"
        assert cand["sl"] is not None
        assert cand["tp1"] is not None
        assert len(cand["factors"]) > 0
        assert len(cand["recent_closes"]) > 0


@pytest.mark.anyio
async def test_trader_get_blog_candidates_gainers_and_losers():
    """Verify Trader.get_blog_candidates correctly ranks tickers for gainers and losers."""
    trader = Trader()
    mock_tickers = [
        {"symbol": "PUMPUSDT", "lastPrice": "1.5", "priceChangePercent": "25.0", "quoteVolume": "10000000"},
        {"symbol": "DUMPUSDT", "lastPrice": "0.8", "priceChangePercent": "-18.5", "quoteVolume": "8000000"},
        {"symbol": "MIDUSDT", "lastPrice": "2.0", "priceChangePercent": "2.1", "quoteVolume": "5000000"},
    ]
    mock_klines = [
        [1700000000000, "1.0", "1.2", "0.9", "1.1", "1000", 1700000060000]
        for _ in range(40)
    ]
    with patch.object(trader.client, "get_all_tickers", new=AsyncMock(return_value=mock_tickers)), \
         patch.object(trader.client, "get_klines", new=AsyncMock(return_value=mock_klines)):
        
        # Test gainers
        res_gainers = await trader.get_blog_candidates(source="gainers", limit=2)
        assert res_gainers["ok"] is True
        assert res_gainers["source"] == "gainers"
        assert len(res_gainers["items"]) == 2
        assert res_gainers["items"][0]["symbol"] == "PUMPUSDT"
        assert res_gainers["items"][0]["side_en"] == "LONG"

        # Test losers
        res_losers = await trader.get_blog_candidates(source="losers", limit=2)
        assert res_losers["ok"] is True
        assert res_losers["source"] == "losers"
        assert len(res_losers["items"]) == 2
        assert res_losers["items"][0]["symbol"] == "DUMPUSDT"
        assert res_losers["items"][0]["side_en"] == "SHORT"


def test_api_blog_candidates_endpoint():
    """Verify GET /api/blog/candidates endpoint."""
    mock_tickers = [
        {"symbol": "HOTUSDT", "lastPrice": "5.0", "priceChangePercent": "30.0", "quoteVolume": "20000000"},
    ]
    mock_klines = [
        [1700000000000, "4.8", "5.2", "4.7", "5.0", "1000", 1700000060000]
        for _ in range(35)
    ]
    with patch.object(__import__('app').trader.client, 'get_all_tickers', new=AsyncMock(return_value=mock_tickers)), \
         patch.object(__import__('app').trader.client, 'get_klines', new=AsyncMock(return_value=mock_klines)):
        resp = client.get("/api/blog/candidates?source=gainers&limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert len(data.get("items", [])) >= 1
        assert data["items"][0]["symbol"] == "HOTUSDT"


def test_api_blog_kline_chart_endpoint():
    """Verify GET /api/blog/kline_chart renders chart for candidate."""
    mock_item = {
        "symbol": "BTCUSDT",
        "price": 65000.0,
        "side_en": "LONG",
        "recent_closes": [64000.0, 64500.0, 65000.0, 65200.0, 65000.0],
    }
    with patch.object(__import__('app').trader, 'get_blog_candidates', new=AsyncMock(return_value={"ok": True, "items": [mock_item]})):
        resp = client.get("/api/blog/kline_chart?symbol=BTCUSDT")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("symbol") == "BTCUSDT"
        assert str(data.get("data_url", "")).startswith("data:image/png;base64,")
