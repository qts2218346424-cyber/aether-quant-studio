from src.paths import load_frontend_bundle_text
import asyncio
import base64
from pathlib import Path
import pytest

from blog_auto_publish import build_auto_blog, _cashtag
import binance_square_publisher as publisher


def test_cashtag_helper():
    assert _cashtag('BTCUSDT') == '$BTC'
    assert _cashtag('ETHUSDT') == '$ETH'
    assert _cashtag('SKHYUSDT') == '$SKHY'
    assert _cashtag('HYPE') == '$HYPE'
    assert _cashtag('') == ''


def test_auto_blog_long_sentiment_and_cashtags():
    items = [
        {
            'symbol': 'BTCUSDT',
            'side_en': 'LONG',
            'score': 85,
            'change_24h': 3.5,
            'price': 65000.0,
            'support': 64200.0,
            'resistance': 66800.0,
            'sl': 63800.0,
            'tp1': 67500.0,
            'factors': ['放量突破', '均线多头'],
        }
    ]
    blog = build_auto_blog(items)
    assert blog['sentiment'] == 'BULLISH'
    assert '$BTC' in blog['title']
    assert '$BTC' in blog['body']
    assert '63,800' in blog['body']
    assert '#看涨' in blog['tags']
    tag_count = len(blog['tags'].split())
    assert tag_count <= 5


def test_auto_blog_short_sentiment_and_cashtags():
    items = [
        {
            'symbol': 'SKHYUSDT',
            'side_en': 'SHORT',
            'score': -70,
            'change_24h': -5.2,
            'price': 181.63,
            'support': 176.0,
            'resistance': 186.0,
            'sl': 186.0,
            'tp1': 176.0,
            'factors': ['顶背离', '大单撤离'],
        }
    ]
    blog = build_auto_blog(items)
    assert blog['sentiment'] == 'BEARISH'
    assert '$SKHY' in blog['title']
    assert '$SKHY' in blog['body']
    assert '186' in blog['body']
    assert '#看跌' in blog['tags']
    tag_count = len(blog['tags'].split())
    assert tag_count <= 5


def test_publish_blog_passes_sentiment_argument(monkeypatch, tmp_path):
    captured = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return (
                b"Success!\nID: 999\nLink: https://example.test/999\n",
                b"",
            )

    async def fake_exec(*args, **kwargs):
        captured['args'] = args
        captured['env'] = kwargs['env']
        return FakeProcess()

    monkeypatch.setenv('BINANCE_SQUARE_OPENAPI_KEY', 'test-key-123')
    monkeypatch.setattr(publisher.shutil, 'which', lambda _: 'node')
    monkeypatch.setattr(publisher.asyncio, 'create_subprocess_exec', fake_exec)
    script = tmp_path / 'post-image.mjs'
    script.write_text('// test', encoding='utf-8')
    monkeypatch.setattr(publisher, 'SCRIPT', script)

    result = asyncio.run(
        publisher.publish_blog(
            title='测试标题',
            body='正文内容',
            tags='#测试',
            cover_data_url='data:image/png;base64,' + ('A' * 128),
            sentiment='BEARISH',
        )
    )

    assert result['id'] == '999'
    assert result['sentiment'] == 'BEARISH'
    args_list = list(captured['args'])
    assert '--sentiment' in args_list
    sentiment_idx = args_list.index('--sentiment')
    assert args_list[sentiment_idx + 1] == 'BEARISH'


def test_frontend_has_sentiment_controls_and_cashtag():
    html = load_frontend_bundle_text()
    assert 'blog-sentiment' in html
    assert 'blog-sentiment-badge' in html
    assert 'toCashtag' in html
    assert 'syncBlogSentimentBadge' in html
    assert 'BULLISH' in html
    assert 'BEARISH' in html
    assert '看涨' in html
    assert '看跌' in html


def test_obsidian_knowledge_base_sop_and_templates(tmp_path):
    from obsidian_bridge import ObsidianBridge

    bridge = ObsidianBridge()
    bridge.init_templates(tmp_path)
    sop_file = tmp_path / '04-币安广场与个人博客/01-币安广场爆款写作指南与SOP.md'
    assert sop_file.is_file()
    sop_content = sop_file.read_text(encoding='utf-8')
    assert '看涨 / 看跌' in sop_content
    assert 'Cashtag' in sop_content

    template_file = tmp_path / '04-币安广场与个人博客/02-爆款文章模板库.md'
    assert template_file.is_file()
    tpl_content = template_file.read_text(encoding='utf-8')
    assert "${币种}" in tpl_content
    assert '看涨' in tpl_content
    assert '看跌' in tpl_content
