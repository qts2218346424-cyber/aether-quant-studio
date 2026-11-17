import base64
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app import app
from blog_auto_publish import SquareAutoPublisher, build_auto_blog, render_cover_data_url


client = TestClient(app)


def test_api_blog_promotion_get_and_post():
    """Verify GET and POST /api/blog/promotion."""
    get_res = client.get("/api/blog/promotion")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["ok"] is True
    assert "promotion" in data

    post_payload = {
        "enabled": True,
        "referral_code": "PRO_TRADER_888",
        "referral_url": "https://accounts.binance.com/register?ref=PRO_TRADER_888",
        "copy_trading_url": "https://www.binance.com/copy-trading/pro",
        "fee_discount_pct": 20,
    }
    post_res = client.post("/api/blog/promotion", json=post_payload)
    assert post_res.status_code == 200
    res_data = post_res.json()
    assert res_data["ok"] is True
    assert res_data["promotion"]["referral_code"] == "PRO_TRADER_888"

    verify_res = client.get("/api/blog/promotion")
    assert verify_res.json()["promotion"]["referral_code"] == "PRO_TRADER_888"


def test_build_auto_blog_with_promotion():
    """Verify build_auto_blog includes referral code and CTA hook."""
    items = [{
        "symbol": "SOLUSDT",
        "side_en": "LONG",
        "score": 88,
        "price": 142.5,
        "atr_pct": 3.1,
        "support": 138.0,
        "resistance": 148.0,
        "sl": 136.5,
        "tp1": 152.0,
        "factors": ["突破大单流入"],
        "recent_closes": [138, 140, 142.5],
    }]
    promo = {
        "red_packet_hook": "关注我每天抽红包，欢迎评论区留言参与！",
    }
    content = build_auto_blog(items, promo=promo)
    assert "$SOL" in content["title"]
    assert "红包" in content["body"]
    assert "止损防守" in content["body"]
    # 确保旧邀请码内容已不再出现
    assert "VIP_DISCOUNT_20" not in content["body"]
    assert "邀请码" not in content["body"]


def test_render_pro_cover_with_referral_code():
    """Verify render_cover_data_url renders valid 16:9 PNG containing promotion watermark."""
    items = [{
        "symbol": "SOLUSDT",
        "side_en": "LONG",
        "score": 88,
        "price": 142.5,
        "atr_pct": 3.1,
        "support": 138.0,
        "resistance": 148.0,
        "sl": 136.5,
        "tp1": 152.0,
        "recent_closes": [138, 140, 142.5],
    }]
    promo = {
        "referral_code": "VIP_DISCOUNT_20",
        "fee_discount_pct": 20,
    }
    content = build_auto_blog(items, promo=promo)
    cover_data_url = render_cover_data_url(items, content, promo=promo)
    assert cover_data_url.startswith("data:image/png;base64,")
    raw = base64.b64decode(cover_data_url.split(",", 1)[1])
    assert len(raw) > 50000
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.anyio
async def test_square_auto_publisher_run_once_with_ai():
    """Verify SquareAutoPublisher.run_once invokes generator and produces article."""
    mock_items = {
        "items": [{
            "symbol": "DOGEUSDT",
            "side_en": "LONG",
            "score": 75,
            "price": 0.125,
            "atr_pct": 3.5,
            "support": 0.12,
            "resistance": 0.135,
            "sl": 0.118,
            "tp1": 0.14,
            "recent_closes": [0.12, 0.122, 0.125],
        }]
    }
    rec_getter = AsyncMock(return_value=mock_items)
    publisher = SquareAutoPublisher(rec_getter)

    fake_ai_data = {
        "ok": True,
        "data": {
            "title": "$DOGE 关键支撑位放量反弹",
            "body": "🟢【看涨 · 做多】 $DOGE\n\n测试正文内容",
            "tags": "#DOGE #加密货币",
            "sentiment": "BULLISH",
            "prompt": "doge coin chart",
        }
    }
    with patch("blog_auto_publish.publish_blog", new=AsyncMock(return_value={"id": "999888", "link": "https://binance.com/square/999888"})), \
         patch("blog_ai_writer.generate_ai_blog", new=AsyncMock(return_value=fake_ai_data)), \
         patch("openai_image_client.openai_image_client.generate_image", new=AsyncMock(return_value={"ok": False})), \
         patch("blog_auto_publish.fetch_symbol_klines_async", new=AsyncMock(return_value=[0.125]*30)), \
         patch("blog_auto_publish.fetch_live_ticker_sync", return_value={"symbol": "DOGEUSDT", "price": 0.125, "change_24h": 2.0}):
        result = await publisher.run_once()
        assert result["status"] == "published"
        assert result["id"] == "999888"
