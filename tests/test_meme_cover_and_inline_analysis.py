from src.paths import load_frontend_bundle_text
import base64
from pathlib import Path
from unittest.mock import patch, AsyncMock
import pytest
from fastapi.testclient import TestClient

from app import app
from obsidian_bridge import ObsidianBridge
from blog_auto_publish import render_cover_data_url, build_auto_blog


client = TestClient(app)
html = load_frontend_bundle_text()


def test_frontend_has_inline_kline_analysis_and_meme_cover():
    """Verify frontend contains in-article professional analysis card and meme cover branding."""
    assert "blog-kline-preview-img" in html
    assert "loadKlineChartForSymbol" in html
    assert "copyKlineChartImage" in html
    assert "downloadKlineChartImage" in html
    assert "insertKlineChartToBody" in html
    assert "文章内嵌专业分析图" in html
    assert "搞笑梗图" in html


def test_render_cover_data_url_produces_valid_png():
    """Verify render_cover_data_url renders valid 16:9 PNG data URL."""
    items = [
        {
            "symbol": "BTCUSDT",
            "price": 65000.0,
            "side_en": "LONG",
            "score": 85.0,
            "change_24h": 3.2,
            "support": 64200.0,
            "resistance": 66800.0,
        }
    ]
    content = build_auto_blog(items)
    cover_data_url = render_cover_data_url(items, content)
    assert cover_data_url.startswith("data:image/png;base64,")
    raw = base64.b64decode(cover_data_url.split(",", 1)[1])
    assert len(raw) > 5000
    # PNG signature check
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"


def test_save_blog_note_with_meme_cover_and_inline_analysis(tmp_path, monkeypatch):
    """Verify save_blog_note embeds meme cover at top and professional analysis image in body."""
    bridge = ObsidianBridge()
    monkeypatch.setattr(bridge, "get_vault_path", lambda: tmp_path)

    dummy_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    dummy_cover = f"data:image/png;base64,{dummy_png_b64}"
    dummy_analysis = f"data:image/png;base64,{dummy_png_b64}"

    body_text = (
        "今天盘面多空博弈激烈，BTC在关键支撑位出现量价企稳信号。\n\n"
        "🧭 我的实盘计划：\n"
        "• 核心标的：BTCUSDT（偏多 ▲）\n"
        "• 关键支撑：64200 ｜ 关键阻力：66800\n"
        "• 止损防守：63800\n"
        "• 止盈目标：67500\n\n"
        "⚠️ 风控第一，切记控制仓位。"
    )

    res = bridge.save_blog_note(
        title="BTC晚盘突破推演",
        hook="这波位置值得盯一下",
        body=body_text,
        tags="#BTC #币安广场 #量化交易",
        platform="binance_square",
        tone="analytical",
        cover_data_url=dummy_cover,
        analysis_chart_data_url=dummy_analysis,
    )

    assert res["ok"] is True
    note_file = Path(res["note_path"])
    assert note_file.is_file()

    content = note_file.read_text(encoding="utf-8")
    # 验证封面为搞笑梗图
    assert "_cover.png" in content
    assert "博客封面 (搞笑梗图引流)" in content
    # 验证专业走势分析图内嵌在正文内容中
    assert "_analysis.png" in content
    assert "盘面专业走势分析图" in content
    # 验证草稿库与封面目录中镜像生成了对应的图片文件
    cover_dir = tmp_path / "00-原始资料与灵感库" / "行情简报与博客" / "封面"
    assert len(list(cover_dir.glob("*_cover.png"))) == 1
    assert len(list(cover_dir.glob("*_analysis.png"))) == 1


def test_api_save_blog_note_handles_analysis_chart(tmp_path, monkeypatch):
    """Verify POST /api/obsidian/save_blog_note accepts analysis_chart_data_url."""
    from config import load_config
    bridge = __import__("app").obsidian_bridge
    monkeypatch.setattr(bridge, "get_vault_path", lambda: tmp_path)

    dummy_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    payload = {
        "title": "SOL突破前高行情速递",
        "hook": "SOL今天冲劲十足",
        "body": "形态上看，SOL目前突破关键压力位。\n\n🧭 我的实盘计划：\n• 止损防守：138",
        "tags": "#SOL #涨幅榜",
        "platform": "binance_square",
        "tone": "conversational",
        "cover_data_url": f"data:image/png;base64,{dummy_png_b64}",
        "analysis_chart_data_url": f"data:image/png;base64,{dummy_png_b64}",
    }

    resp = client.post("/api/obsidian/save_blog_note", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    note_file = Path(data["note_path"])
    content = note_file.read_text(encoding="utf-8")
    assert "_analysis.png" in content
    assert "盘面专业走势分析图" in content
