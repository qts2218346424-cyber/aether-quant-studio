from src.paths import load_frontend_bundle_text
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app import app


client = TestClient(app)
html = load_frontend_bundle_text()


def test_backtest_symbol_selection_has_holdings_and_custom_input():
    """Verify backtest symbol select supports user positions, watchlist, and custom input."""
    assert "populateEvolutionSymbols" in html
    assert "promptCustomBacktestSymbol" in html
    assert "💼 我的当前真实持仓" in html
    assert "🎯 当前看盘 / 终端自选" in html
    assert "🔥 主流高流动性标的" in html
    assert "➕ 自定义标的" in html
    assert "onEvolutionSymbolChange" in html


def test_blog_growth_studio_has_ai_writer_integration():
    """Verify blog growth studio has full AI generation controls and hooks."""
    assert "🤖 AI 智能解盘工坊" in html
    assert "blog-ai-model" in html
    assert "blog-ai-role" in html
    assert "blog-ai-extra" in html
    assert "btn-blog-ai-gen" in html
    assert "generateBlogWithAI" in html
    assert "🪄 AI 深度润色" in html
    assert "blog-ai-badge" in html


def test_api_blog_ai_generate_endpoint_mock():
    """Verify POST /api/blog/ai_generate endpoint structure."""
    payload = {
        "items": [
            {"symbol": "ZECUSDT", "score": 55, "direction": "SHORT", "price": 40.2, "change_24h": -3.2},
            {"symbol": "COTIUSDT", "score": 48, "direction": "SHORT", "price": 0.061, "change_24h": -2.1},
        ],
        "positions": [
            {"symbol": "ZECUSDT", "side": "SHORT", "qty": 0.112},
        ],
        "platform": "binance_square",
        "tone": "analytical",
        "length": "standard",
        "provider_index": "auto",
        "persona": "binance_top_creator",
    }
    response = client.post("/api/blog/ai_generate", json=payload)
    # The endpoint exists and responds with 200 JSON
    assert response.status_code == 200
    data = response.json()
    assert "ok" in data
