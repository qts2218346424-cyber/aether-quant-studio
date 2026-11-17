"""Unit tests for Binance Square Symbol Rotation and Daily Review Analytics."""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest

from blog_auto_publish import (
    rotate_candidate_items,
    build_daily_review_blog,
    SquareAutoPublisher,
)
import square_history_manager


def test_rotate_candidate_items_cools_down_recently_published_symbol():
    """Verify that recently published symbol is placed behind fresh candidate symbols."""
    raw_candidates = [
        {"symbol": "TAKEUSDT", "quote_volume": 5000000, "score": 90},
        {"symbol": "BTCUSDT", "quote_volume": 4000000, "score": 85},
        {"symbol": "ETHUSDT", "quote_volume": 3000000, "score": 80},
        {"symbol": "SOLUSDT", "quote_volume": 2000000, "score": 75},
    ]

    # TAKEUSDT was just published in the last post
    recent = ["TAKEUSDT"]
    rotated = rotate_candidate_items(raw_candidates, recent_symbols=recent, limit=4, cooldown_count=3)

    # BTCUSDT should now be the primary candidate (at index 0), NOT TAKEUSDT
    assert rotated[0]["symbol"] == "BTCUSDT"
    assert rotated[1]["symbol"] == "ETHUSDT"
    assert rotated[2]["symbol"] == "SOLUSDT"
    # TAKEUSDT cooled down to the last position
    assert rotated[3]["symbol"] == "TAKEUSDT"


def test_rotate_candidate_items_lru_fallback_when_all_in_recent():
    """When all candidates have been published recently, LRU (oldest published) should take priority."""
    raw_candidates = [
        {"symbol": "TAKEUSDT"},
        {"symbol": "BTCUSDT"},
        {"symbol": "SOLUSDT"},
    ]
    # Recent order: TAKE (most recent), then BTC, then SOL (oldest)
    recent = ["TAKEUSDT", "BTCUSDT", "SOLUSDT"]
    rotated = rotate_candidate_items(raw_candidates, recent_symbols=recent, limit=3, cooldown_count=5)

    # SOLUSDT should be at the top because it was published the longest time ago
    assert rotated[0]["symbol"] == "SOLUSDT"
    assert rotated[1]["symbol"] == "BTCUSDT"
    assert rotated[2]["symbol"] == "TAKEUSDT"


def test_square_history_manager_record_and_analytics(tmp_path, monkeypatch):
    """Verify square_history_manager records posts and computes daily analytics metrics correctly."""
    fake_history_file = tmp_path / "square_posts_history.json"
    monkeypatch.setattr(square_history_manager, "HISTORY_FILE", fake_history_file)
    monkeypatch.setattr(square_history_manager, "DATA_DIR", tmp_path)

    # Record 2 posts for today
    p1 = square_history_manager.record_published_post({
        "id": "1001",
        "symbol": "BTCUSDT",
        "sentiment": "BULLISH",
        "post_type": "spot_analysis",
        "title": "BTC 看涨突破",
        "summary": "BTC 回踩确认，准备上冲",
        "link": "https://binance.com/square/1001",
    })
    assert p1["id"] == "1001"

    p2 = square_history_manager.record_published_post({
        "id": "1002",
        "symbol": "SOLUSDT",
        "sentiment": "BEARISH",
        "post_type": "daily_review",
        "title": "每日大盘全景复盘",
        "summary": "大盘冲高回落，注意防守",
        "link": "https://binance.com/square/1002",
    })
    assert p2["id"] == "1002"

    analytics = square_history_manager.get_daily_analytics()
    assert analytics["today_posts_count"] == 2
    assert analytics["total_posts_count"] == 2
    assert analytics["symbol_distribution"]["BTCUSDT"] == 1
    assert analytics["symbol_distribution"]["SOLUSDT"] == 1
    assert analytics["bullish_count"] == 1
    assert analytics["bearish_count"] == 1
    assert analytics["has_daily_review_today"] is True
    assert "SOLUSDT" in analytics["recent_symbols"]
    assert "BTCUSDT" in analytics["recent_symbols"]


def test_build_daily_review_blog():
    """Verify build_daily_review_blog constructs professional daily overview content."""
    items = [
        {"symbol": "BTCUSDT", "price": 84200.0, "change_24h": 3.2, "side_en": "LONG", "support": 82000, "resistance": 86000},
        {"symbol": "ETHUSDT", "price": 3150.0, "change_24h": 1.5, "side_en": "LONG", "support": 3050, "resistance": 3250},
        {"symbol": "SOLUSDT", "price": 142.0, "change_24h": -2.0, "side_en": "SHORT", "support": 136, "resistance": 148},
    ]
    report = {
        "close_count": 3,
        "total_pnl": 12.8,
        "win_rate": 66.7,
    }

    blog = build_daily_review_blog(items, today_report=report)
    assert blog["post_type"] == "daily_review"
    assert "【每日复盘 · 盘面全景】" in blog["title"]
    assert "$BTC" in blog["body"]
    assert "$ETH" in blog["body"]
    assert "今日大盘全景复盘" in blog["body"]
    assert "量化雷达与策略复盘" in blog["body"]
    assert "已交割 3 单" in blog["body"]
    assert "#每日复盘" in blog["tags"]


@pytest.mark.anyio
async def test_square_auto_publisher_rotates_away_from_last_symbol():
    """Verify SquareAutoPublisher automatically rotates away from last published symbol in run_once."""
    mock_items = {
        "items": [
            # TAKEUSDT is #1 by hotness / score
            {"symbol": "TAKEUSDT", "quote_volume": 5000000, "score": 95, "price": 0.5, "recent_closes": [0.5]*10},
            # ETHUSDT is #2
            {"symbol": "ETHUSDT", "quote_volume": 4000000, "score": 85, "price": 3100.0, "recent_closes": [3100.0]*10},
        ]
    }

    publisher_inst = SquareAutoPublisher(AsyncMock(return_value=mock_items))
    # State has last_symbol = TAKEUSDT
    publisher_inst._state["last_symbol"] = "TAKEUSDT"
    publisher_inst._state["recent_symbols"] = ["TAKEUSDT"]

    captured_call = {}
    async def mock_publish(title, body, tags, cover, sentiment="", images=None, symbol="", **kwargs):
        captured_call["symbol"] = symbol
        return {"id": "9999", "link": "https://binance.com/square/9999"}

    with patch("config.load_config", return_value={"square_auto_publish": {"enabled": True}}), \
         patch("blog_auto_publish.publish_blog", side_effect=mock_publish), \
         patch("blog_ai_writer.generate_ai_blog", new=AsyncMock(return_value={"ok": False})), \
         patch("openai_image_client.openai_image_client.generate_image", new=AsyncMock(return_value={"ok": False})), \
         patch("blog_auto_publish.fetch_symbol_klines_async", new=AsyncMock(return_value=[3100.0]*30)):
        res = await publisher_inst.run_once()
        assert res["status"] == "published"
        # The published symbol must have rotated to ETHUSDT, NOT TAKEUSDT!
        assert captured_call["symbol"] == "ETHUSDT"
        assert publisher_inst._state["last_symbol"] == "ETHUSDT"
        assert "ETHUSDT" in publisher_inst._state["recent_symbols"]


def test_obsidian_sync_published_square_post(tmp_path, monkeypatch):
    """Verify that published Square posts are synchronized and archived to Obsidian vault."""
    from obsidian_bridge import ObsidianBridge

    fake_vault = tmp_path / "Vault"
    fake_vault.mkdir()
    bridge = ObsidianBridge()
    monkeypatch.setattr(bridge, "get_vault_path", lambda: fake_vault)

    sample_post = {
        "id": "88888",
        "symbol": "BTCUSDT",
        "sentiment": "BULLISH",
        "post_type": "spot_analysis",
        "title": "BTC 多头量价共振",
        "body": "这里重点关注支撑位放量突破信号。",
        "tags": "#BTC #看涨 #币安广场",
        "square_link": "https://binance.com/square/88888",
        "cover_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
    }

    res = bridge.sync_published_square_post(sample_post)
    assert res["ok"] is True
    assert "04-币安广场与个人博客/已发布归档" in res["relative_path"]

    # Check file exists on disk in vault
    archived_file = fake_vault / res["relative_path"]
    assert archived_file.exists()
    content = archived_file.read_text(encoding="utf-8")
    assert "status: published" in content
    assert "square_post_id: \"88888\"" in content
    assert "symbol: BTCUSDT" in content
    assert "sentiment: BULLISH" in content

    # Check cover saved in 04-币安广场与个人博客/封面/
    cover_dir = fake_vault / "04-币安广场与个人博客" / "封面"
    assert cover_dir.exists()
    assert len(list(cover_dir.glob("*.png"))) == 1


def test_sanitize_and_verify_prices_corrects_btc_hallucinations():
    """验证价格巡检门禁能够自动纠正大模型关于 BTC 的历史幻觉数字（如 98k/103k/65k）并对齐多空标签。"""
    from blog_auto_publish import sanitize_and_verify_prices

    target_item = {
        "symbol": "BTCUSDT",
        "price": 84000.0,
        "side_en": "LONG",
        "support": 82500.0,
        "resistance": 85500.0,
    }

    mock_ai_content = {
        "title": "【看跌 · 做空】$BTC 冲击 104,500 关口受阻，主力资金暗中出货？",
        "body": (
            "🔴【看跌 · 做空 BEARISH】 $BTC\n\n"
            "回顾近两日盘面，昨天在 98,200 插针洗盘后迅速反弹，目前在 103,000-104,500 箱体震荡。\n"
            "主力在 101,800-102,300 密集吸筹，上方阻力看 105,800，突破直奔 108,500，下破 99,800 止损认亏离场。\n"
            "此前抄底成本大约在 65,000 附近。"
        ),
        "sentiment": "BULLISH",  # 模型元数据为看涨，但首行写了看跌
        "tags": "#BTC #看涨 #币安广场",
        "hook": "昨天在 98,200 插针洗盘，你被洗下车了吗？",
    }

    cleaned = sanitize_and_verify_prices(mock_ai_content, target_item)

    # 1. 验证多空标签矛盾已彻底纠偏
    assert "🔴【看跌 · 做空" not in cleaned["body"]
    assert "🟢【看涨 · 做多 BULLISH】" in cleaned["body"]
    assert "【看跌 · 做空】" not in cleaned["title"]
    assert "【看涨 · 做多】" in cleaned["title"]

    # 2. 验证 BTC 历史价格幻觉（98k/103k/104k/65k 等）已被纠偏为当前 84,000 真实盘面区间
    assert "98,200" not in cleaned["body"]
    assert "103,000-104,500" not in cleaned["body"]
    assert "104,500" not in cleaned["title"]
    assert "98,200" not in cleaned["hook"]
    assert "65,000" not in cleaned["body"]

    # 3. 验证真实价格数字已成功注入
    assert "84,000" in cleaned["body"]
    assert "82,320" in cleaned["body"]  # 84000 * 0.98
    assert "86,940" in cleaned["body"]  # 84000 * 1.035 (tp)


def test_enrich_with_realtime_price_aligns_key_levels():
    """验证 _enrich_with_realtime_price 覆盖现价并动态校准支撑/阻力/止损/止盈。"""
    from blog_auto_publish import _enrich_with_realtime_price

    items = [
        {
            "symbol": "BTCUSDT",
            "price": 65000.0,  # 假数据/旧缓存
            "support": 63000.0,
            "resistance": 67000.0,
            "sl": 62000.0,
            "tp1": 69000.0,
            "side_en": "LONG",
        }
    ]

    with patch("blog_auto_publish.fetch_live_ticker_sync", return_value={"symbol": "BTCUSDT", "price": 84100.0, "change_24h": 1.5}):
        enriched = _enrich_with_realtime_price(items)
        btc = enriched[0]
        # 现价必须已被币安官方行情覆盖
        assert btc["price"] == 84100.0
        assert btc["change_24h"] == 1.5
        # 支撑/阻力/止损/止盈必须动态围绕 84100 计算，不再是 63000/67000
        assert abs(btc["support"] - 84100 * 0.988) < 1.0
        assert abs(btc["resistance"] - 84100 * 1.015) < 1.0
        assert abs(btc["sl"] - 84100 * 0.982) < 1.0
        assert abs(btc["tp1"] - 84100 * 1.035) < 1.0


def test_build_auto_blog_varieties_and_no_ai_cliche():
    """验证自动文案生成引擎支持多样化人类语气与流派形态，且彻底杜绝机械公式化模板。"""
    from blog_auto_publish import build_auto_blog

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "BNBUSDT", "AVAXUSDT"]
    results = []

    for sym in symbols:
        items = [{
            "symbol": sym,
            "side_en": "LONG",
            "score": 85,
            "price": 100.0,
            "atr_pct": 2.5,
            "support": 97.0,
            "resistance": 104.0,
            "sl": 96.0,
            "tp1": 108.0,
            "factors": ["资金流入"],
            "recent_closes": [98.0, 99.0, 100.0],
        }]
        res = build_auto_blog(items)
        results.append(res)

        # 1. 彻底杜绝 AI 工业套词与机械列表
        body = res["body"]
        assert "下面逐一拆解核心逻辑与我的操作思路" not in body
        assert "• 交易标的：" not in body
        assert "• 核心标的：" not in body
        assert "• 关键价位：" not in body
        assert "做多 $" in body or "止损防守" in body

    # 2. 验证多币种生成不同标题与不同开场白，千篇千面
    titles = [r["title"] for r in results]
    unique_titles = set(titles)
    # 至少应有 4 种以上完全不同的独特标题句式，证明已彻底打破单一模版
    assert len(unique_titles) >= 4



