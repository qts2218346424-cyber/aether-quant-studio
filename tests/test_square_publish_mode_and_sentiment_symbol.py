"""Tests for Binance Square publish_mode (short post vs article), sentiment, and symbol support."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

import binance_square_publisher as publisher
from blog_auto_publish import SquareAutoPublisher


def test_publish_blog_passes_symbol_and_sentiment(monkeypatch, tmp_path):
    """Verify publish_blog passes --symbol and --sentiment CLI flags and sets NODE_OPTIONS."""
    captured = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return (
                b"Cover uploaded.\nArticle submitted.\nSuccess!\nID: 8888\nLink: https://binance.com/square/8888\n",
                b"",
            )

    async def fake_exec(*args, **kwargs):
        captured['args'] = args
        captured['env'] = kwargs['env']
        return FakeProcess()

    monkeypatch.setenv('BINANCE_SQUARE_OPENAPI_KEY', 'test-key-abc')
    monkeypatch.setattr(publisher.shutil, 'which', lambda _: 'node')
    monkeypatch.setattr(publisher.asyncio, 'create_subprocess_exec', fake_exec)
    script = tmp_path / 'post-image.mjs'
    script.write_text('// fixture', encoding='utf-8')
    monkeypatch.setattr(publisher, 'SCRIPT', script)

    result = asyncio.run(
        publisher.publish_blog(
            title='',  # Short post mode
            body='🔴【看跌 · 做空 BEARISH】$BTC 现价 83800\n入场 83800-84500\n止损 85000\n止盈 83200',
            tags='#BTC #看跌',
            cover_data_url='data:image/png;base64,' + ('A' * 128),
            sentiment='BEARISH',
            symbol='BTCUSDT',
        )
    )

    assert result['id'] == '8888'
    assert result['content_type'] == 'post_with_images'
    assert result['sentiment'] == 'BEARISH'
    assert result['symbol'] == 'BTCUSDT'

    args_list = list(captured['args'])
    assert '--title' not in args_list  # Short post has no title flag
    assert '--sentiment' in args_list
    assert args_list[args_list.index('--sentiment') + 1] == 'BEARISH'
    assert '--symbol' in args_list
    assert args_list[args_list.index('--symbol') + 1] == 'BTCUSDT'
    assert '--use-env-proxy' in captured['env']['NODE_OPTIONS']


def test_publish_blog_auto_extracts_symbol_from_cashtag(monkeypatch, tmp_path):
    """Verify publish_blog automatically extracts symbol from $CASHTAG if not explicitly provided."""
    captured = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return (b"Success!\nID: 7777\nLink: https://binance.com/square/7777\n", b"")

    async def fake_exec(*args, **kwargs):
        captured['args'] = args
        captured['env'] = kwargs['env']
        return FakeProcess()

    monkeypatch.setenv('BINANCE_SQUARE_OPENAPI_KEY', 'test-key-abc')
    monkeypatch.setattr(publisher.shutil, 'which', lambda _: 'node')
    monkeypatch.setattr(publisher.asyncio, 'create_subprocess_exec', fake_exec)
    script = tmp_path / 'post-image.mjs'
    script.write_text('// fixture', encoding='utf-8')
    monkeypatch.setattr(publisher, 'SCRIPT', script)

    result = asyncio.run(
        publisher.publish_blog(
            title='',
            body='这里看好 $ETH 的回踩支撑。',
            tags='#ETH',
            cover_data_url='data:image/png;base64,' + ('A' * 128),
            sentiment='BULLISH',
        )
    )

    assert result['symbol'] == 'ETH'
    args_list = list(captured['args'])
    assert '--symbol' in args_list
    assert args_list[args_list.index('--symbol') + 1] == 'ETH'


@pytest.mark.anyio
async def test_square_auto_publisher_defaults_to_post_mode_with_sentiment_header():
    """Verify SquareAutoPublisher defaults to 'post' mode with empty title and sentiment cashtag in body."""
    mock_items = {
        "items": [{
            "symbol": "BTCUSDT",
            "side_en": "SHORT",
            "score": 90,
            "price": 84000.0,
            "atr_pct": 2.5,
            "support": 83000.0,
            "resistance": 85000.0,
            "sl": 85500.0,
            "tp1": 82000.0,
            "recent_closes": [84500.0, 84200.0, 84000.0],
        }]
    }

    rec_getter = AsyncMock(return_value=mock_items)
    publisher_inst = SquareAutoPublisher(rec_getter)

    captured_call = {}
    async def mock_publish(title, body, tags, cover, sentiment="", images=None, symbol="", **kwargs):
        captured_call.update({
            "title": title,
            "body": body,
            "sentiment": sentiment,
            "symbol": symbol,
            "images": images,
        })
        return {"id": "5555", "link": "https://binance.com/square/5555"}

    with patch("blog_auto_publish.publish_blog", side_effect=mock_publish), \
         patch("openai_image_client.openai_image_client.generate_image", new=AsyncMock(return_value={"ok": False})):
        res = await publisher_inst.run_once()
        assert res["status"] == "published"
        assert res["id"] == "5555"
        # In default 'post' mode, title should be empty
        assert captured_call["title"] == ""
        # Body should start with sentiment tag and Cashtag
        assert "🔴【看跌 · 做空 BEARISH】" in captured_call["body"]
        assert "$BTC" in captured_call["body"]
        assert captured_call["sentiment"] == "BEARISH"
        assert captured_call["symbol"] == "BTCUSDT"
        assert publisher_inst._state["last_publish_mode"] == "post"


@pytest.mark.anyio
async def test_square_auto_publisher_respects_article_mode():
    """Verify SquareAutoPublisher uses title when publish_mode is explicitly set to 'article'."""
    mock_items = {
        "items": [{
            "symbol": "SOLUSDT",
            "side_en": "LONG",
            "score": 85,
            "price": 140.0,
            "atr_pct": 3.0,
            "support": 135.0,
            "resistance": 145.0,
            "sl": 132.0,
            "tp1": 150.0,
            "recent_closes": [135.0, 138.0, 140.0],
        }]
    }

    rec_getter = AsyncMock(return_value=mock_items)
    publisher_inst = SquareAutoPublisher(rec_getter)

    captured_call = {}
    async def mock_publish(title, body, tags, cover, sentiment="", images=None, symbol="", **kwargs):
        captured_call.update({
            "title": title,
            "body": body,
            "sentiment": sentiment,
            "symbol": symbol,
        })
        return {"id": "6666", "link": "https://binance.com/square/6666"}

    with patch("config.load_config", return_value={"square_auto_publish": {"publish_mode": "article"}}), \
         patch("blog_auto_publish.publish_blog", side_effect=mock_publish), \
         patch("openai_image_client.openai_image_client.generate_image", new=AsyncMock(return_value={"ok": False})):
        res = await publisher_inst.run_once()
        assert res["status"] == "published"
        # In article mode, title must be present
        assert captured_call["title"] != ""
        assert captured_call["sentiment"] == "BULLISH"
        assert captured_call["symbol"] == "SOLUSDT"
        assert publisher_inst._state["last_publish_mode"] == "article"


def test_limit_cashtags_strict_cap():
    """Verify _limit_cashtags restricts distinct $Cashtags to at most 3 to avoid API 220095."""
    text = "当前市场 $BTC 领涨，带动了 $ETH 和 $SOL，同时 $BNB 也跟随，$DOGE 有异动，再次关注 $BTC 动向。"
    cleaned = publisher._limit_cashtags(text, max_total=3)
    # First 3 unique ($BTC, $ETH, $SOL) retain $
    assert "$BTC" in cleaned
    assert "$ETH" in cleaned
    assert "$SOL" in cleaned
    # $BNB and $DOGE stripped leading $
    assert "$BNB" not in cleaned
    assert "BNB" in cleaned
    assert "$DOGE" not in cleaned
    assert "DOGE" in cleaned
    # Repeated $BTC still keeps $
    assert cleaned.count("$BTC") == 2


@pytest.mark.anyio
async def test_square_auto_publisher_share_positions_throttling():
    """Verify that user holdings are throttled (occasional) and not spammed in every post."""
    mock_items = {
        "items": [{
            "symbol": "BTCUSDT",
            "side_en": "LONG",
            "score": 90,
            "price": 84000.0,
            "atr_pct": 2.5,
            "support": 83000.0,
            "resistance": 85000.0,
            "sl": 82000.0,
            "tp1": 88000.0,
            "recent_closes": [83000.0, 83500.0, 84000.0],
        }]
    }

    rec_getter = AsyncMock(return_value=mock_items)
    publisher_inst = SquareAutoPublisher(rec_getter)

    fake_client = AsyncMock()
    fake_client.get_positions = AsyncMock(return_value=[{
        "symbol": "BTCUSDT",
        "positionAmt": "0.5",
        "entryPrice": "82000",
        "markPrice": "84000",
        "unRealizedProfit": "1000",
        "leverage": 10,
    }])

    class FakeTrader:
        client = fake_client
        klines_cache = {}
        latest_indicators = {}

    publisher_inst.trader = FakeTrader()

    # Case 1: pub_cnt = 1 (occasional mode -> should NOT share holdings)
    publisher_inst._state["published_count"] = 1
    captured = {}
    async def mock_publish(title, body, tags, cover, sentiment="", images=None, symbol="", **kwargs):
        captured["body"] = body
        return {"id": "1111", "link": "https://binance.com/square/1111"}

    with patch("config.load_config", return_value={"square_auto_publish": {"share_positions_frequency": "occasional"}}), \
         patch("blog_auto_publish.publish_blog", side_effect=mock_publish), \
         patch("blog_ai_writer.generate_ai_blog", new=AsyncMock(return_value={"ok": False})), \
         patch("openai_image_client.openai_image_client.generate_image", new=AsyncMock(return_value={"ok": False})), \
         patch("blog_auto_publish.fetch_symbol_klines_async", new=AsyncMock(return_value=[83000.0] * 30)):
        res = await publisher_inst.run_once()
        assert res["status"] == "published"
        assert "个人实盘随笔" not in captured["body"]
        assert "实盘持仓公开" not in captured["body"]

    # Case 2: pub_cnt = 5 (occasional mode, 5th post -> SHOULD share brief footnote)
    publisher_inst._state["published_count"] = 5
    captured.clear()
    with patch("config.load_config", return_value={"square_auto_publish": {"share_positions_frequency": "occasional"}}), \
         patch("blog_auto_publish.publish_blog", side_effect=mock_publish), \
         patch("blog_ai_writer.generate_ai_blog", new=AsyncMock(return_value={"ok": False})), \
         patch("openai_image_client.openai_image_client.generate_image", new=AsyncMock(return_value={"ok": False})), \
         patch("blog_auto_publish.fetch_symbol_klines_async", new=AsyncMock(return_value=[83000.0] * 30)):
        res = await publisher_inst.run_once()
        assert res["status"] == "published"
        assert "个人实盘随笔" in captured["body"]


