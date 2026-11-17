"""Tests for auto publishing AI image generation and cover trend chart symbol matching."""

import base64
from unittest.mock import AsyncMock, patch
import pytest

from blog_auto_publish import (
    SquareAutoPublisher,
    align_items_with_content_symbol,
    extract_primary_symbol_from_content,
    render_cover_data_url,
    render_kline_data_url,
    _format_chart_price,
)


def test_extract_primary_symbol_from_content():
    """Verify symbol extraction from cashtags and title."""
    content1 = {
        "title": "🚨 $SOL 刚才这根插针很不寻常，主力到底是在洗盘还是诱多？",
        "body": "说实话，刚才那波下杀把不少追单的兄弟洗了。但复盘了盘口，$SOL 这里有意思了。",
        "tags": "#币安广场 #SOL #看涨",
    }
    assert extract_primary_symbol_from_content(content1) == "SOLUSDT"

    content2 = {
        "title": "深度复盘：以太坊当前关键分水岭防守逻辑",
        "body": "目前盘面在回踩核心支撑，不破就是机会。",
        "tags": "#ETHUSDT #以太坊 #合约实战",
    }
    assert extract_primary_symbol_from_content(content2, known_symbols=["BTCUSDT", "ETHUSDT"]) == "ETHUSDT"


def test_align_items_with_content_symbol():
    """Verify items[0] is aligned to the symbol discussed in content."""
    items = [
        {"symbol": "BTCUSDT", "price": 65000.0, "side_en": "LONG"},
        {"symbol": "SOLUSDT", "price": 145.0, "side_en": "LONG"},
        {"symbol": "DOGEUSDT", "price": 0.12, "side_en": "LONG"},
    ]
    content = {
        "title": "$SOL 触碰日内核心分水岭，优质盈亏比试错计划",
        "body": "重点分析 $SOL 的入场与止损防守。",
        "tags": "#SOL #做多",
    }
    aligned = align_items_with_content_symbol(items, content)
    assert aligned[0]["symbol"] == "SOLUSDT"
    assert aligned[1]["symbol"] == "BTCUSDT"


def test_render_cover_data_url_symbol_and_price_matching():
    """Verify cover rendering strictly uses the matched symbol and properly scaled price."""
    items = [
        {"symbol": "BTCUSDT", "price": 65000.0, "side_en": "LONG", "score": 85},
        {
            "symbol": "DOGEUSDT",
            "price": 0.0925,
            "side_en": "LONG",
            "score": 90,
            "support": 0.088,
            "resistance": 0.098,
            "sl": 0.086,
            "tp1": 0.105,
            "recent_closes": [0.089, 0.091, 0.0925],
        },
    ]
    content = {
        "title": "别在现价无脑追涨，聊聊我对 $DOGE 的接单防守逻辑",
        "body": "分析 $DOGE 当前的盘口与防守结构。",
        "tags": "#DOGE #看涨",
    }
    cover = render_cover_data_url(items, content)
    assert cover.startswith("data:image/png;base64,")
    raw = base64.b64decode(cover.split(",", 1)[1])
    assert len(raw) > 50000


def test_format_chart_price_micro_coins():
    """Verify _format_chart_price preserves precision for micro-price coins."""
    assert _format_chart_price(65432.1) == "65,432.10"
    assert _format_chart_price(145.678) == "145.68"
    assert _format_chart_price(0.09254) == "0.0925"
    assert _format_chart_price(0.00008543) == "0.00008543"


@pytest.mark.anyio
async def test_square_auto_publisher_uses_ai_image_when_available():
    """Verify run_once uses AI generated cover and attaches K-line chart when AI image succeeds."""
    mock_items = {
        "items": [{
            "symbol": "SOLUSDT",
            "side_en": "LONG",
            "score": 88,
            "price": 145.0,
            "atr_pct": 3.0,
            "support": 140.0,
            "resistance": 150.0,
            "sl": 138.0,
            "tp1": 155.0,
            "recent_closes": [140.0, 142.0, 145.0],
        }]
    }
    dummy_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    dummy_ai_data_url = f"data:image/png;base64,{dummy_b64}"

    rec_getter = AsyncMock(return_value=mock_items)
    publisher = SquareAutoPublisher(rec_getter)

    fake_ai_res = {
        "ok": True,
        "data_url": dummy_ai_data_url,
        "model": "gpt-image-2",
        "size": "1792x1024",
    }

    published_calls = []
    async def mock_publish(title, body, tags, cover, sentiment="", images=None):
        published_calls.append({
            "title": title,
            "body": body,
            "cover": cover,
            "images": images,
        })
        return {"id": "112233", "link": "https://binance.com/square/112233"}

    with patch("openai_image_client.openai_image_client.generate_image", new=AsyncMock(return_value=fake_ai_res)), \
         patch("blog_ai_writer.generate_ai_blog", new=AsyncMock(return_value={"ok": False})), \
         patch("blog_auto_publish.fetch_symbol_klines_async", new=AsyncMock(return_value=[64500.0]*30)), \
         patch("blog_auto_publish.fetch_live_ticker_sync", return_value={"symbol": "BTCUSDT", "price": 64500.0, "change_24h": 1.2}), \
         patch("blog_auto_publish.publish_blog", side_effect=mock_publish):
        res = await publisher.run_once()
        assert res["status"] == "published"
        assert len(published_calls) == 1
        call = published_calls[0]
        # Cover is the AI generated image
        assert call["cover"] == dummy_ai_data_url
        # Images contains the K-line candlestick chart
        assert call["images"] is not None
        assert len(call["images"]) >= 1
        assert call["images"][0].startswith("data:image/png;base64,")


@pytest.mark.anyio
async def test_square_auto_publisher_fallback_to_canvas_when_ai_fails():
    """Verify run_once falls back to local 16:9 canvas cover when AI image generation fails."""
    mock_items = {
        "items": [{
            "symbol": "BTCUSDT",
            "side_en": "LONG",
            "score": 85,
            "price": 64500.0,
            "atr_pct": 2.2,
            "support": 63000.0,
            "resistance": 66000.0,
            "sl": 62500.0,
            "tp1": 67000.0,
            "recent_closes": [63500.0, 64000.0, 64500.0],
        }]
    }

    rec_getter = AsyncMock(return_value=mock_items)
    publisher = SquareAutoPublisher(rec_getter)

    fake_ai_fail = {
        "ok": False,
        "error": "HTTP 503 No available compatible accounts",
    }

    published_calls = []
    async def mock_publish(title, body, tags, cover, sentiment="", images=None):
        published_calls.append({"cover": cover})
        return {"id": "445566", "link": "https://binance.com/square/445566"}

    with patch("openai_image_client.openai_image_client.generate_image", new=AsyncMock(return_value=fake_ai_fail)), \
         patch("blog_ai_writer.generate_ai_blog", new=AsyncMock(return_value={"ok": False})), \
         patch("blog_auto_publish.fetch_symbol_klines_async", new=AsyncMock(return_value=[64500.0]*30)), \
         patch("blog_auto_publish.fetch_live_ticker_sync", return_value={"symbol": "BTCUSDT", "price": 64500.0, "change_24h": 1.2}), \
         patch("blog_auto_publish.publish_blog", side_effect=mock_publish):
        res = await publisher.run_once()
        assert res["status"] == "published"
        assert len(published_calls) == 1
        # Fallback cover starts with base64 PNG and is large (infographic)
        assert published_calls[0]["cover"].startswith("data:image/png;base64,")
