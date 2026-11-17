import asyncio
import base64

import binance_square_publisher as publisher
from blog_auto_publish import build_auto_blog, render_cover_data_url


def test_parse_success_output():
    result = publisher._parse_publish_output(
        "Success!\nID: 123456\nLink: https://www.binance.com/square/post/123456\n"
    )
    assert result["id"] == "123456"
    assert result["link"].endswith("/123456")
    assert result["raw_status"] == "success"


def test_parse_timeout_success_output():
    result = publisher._parse_publish_output(
        "Success!\nID: unavailable\nLink: unavailable\n"
    )
    assert result["id"] is None
    assert result["link"] is None
    assert result["raw_status"] == "success_without_post_id"


def test_auto_blog_contains_analysis_sections():
    content = build_auto_blog(
        [
            {
                "symbol": "ARBUSDT",
                "side_en": "LONG",
                "score": 84,
                "atr_pct": 2.4,
                "change_24h": 6.8,
                "price": 0.42,
                "support": 0.39,
                "resistance": 0.46,
                "sl": 0.40,
                "tp1": 0.45,
                "factors": ["EMA", "Volume"],
                "recent_closes": [0.4, 0.41, 0.42],
            }
        ]
    )
    assert "$ARB" in content["title"]
    assert "$ARB" in content["body"]
    assert "0.42" in content["body"]
    assert "0.4" in content["body"]
    assert "0.45" in content["body"]


def test_auto_cover_is_png_data_url():
    items = [{
        "symbol": "ARBUSDT",
        "side_en": "LONG",
        "score": 84,
        "price": 0.42,
        "recent_closes": [0.4, 0.41, 0.42],
    }]
    content = build_auto_blog(items)
    cover = render_cover_data_url(items, content)
    assert cover.startswith("data:image/png;base64,")
    assert base64.b64decode(cover.split(",", 1)[1]).startswith(b"\x89PNG")


def test_publish_passes_key_through_environment_not_argv(monkeypatch, tmp_path):
    captured = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return (
                b"Success!\nID: 42\nLink: https://example.test/42\n",
                b"",
            )

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs["env"]
        return FakeProcess()

    monkeypatch.setenv("BINANCE_SQUARE_OPENAPI_KEY", "fixture-secret")
    monkeypatch.setattr(publisher.shutil, "which", lambda _: "node")
    monkeypatch.setattr(publisher.asyncio, "create_subprocess_exec", fake_exec)
    script = tmp_path / "post-text.mjs"
    script.write_text("// fixture", encoding="utf-8")
    monkeypatch.setattr(publisher, "SCRIPT", script)

    result = asyncio.run(
        publisher.publish_blog(
            "标题",
            "正文",
            "#标签",
            "data:image/png;base64," + ("A" * 128),
        )
    )

    assert result["id"] == "42"
    assert result["content_type"] == "article_with_cover"
    assert result["cover_uploaded"] is False
    assert captured["env"]["BINANCE_SQUARE_OPENAPI_KEY"] == "fixture-secret"
    assert "fixture-secret" not in captured["args"]
    assert captured["args"][-3] == "标题"
    assert "--cover" in captured["args"]


def test_extract_images_from_body():
    dummy_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    body = (
        "第一段文字分析\n\n"
        f"![📊 BTC走势分析图](data:image/png;base64,{dummy_b64})\n\n"
        "第二段文字分析\n\n"
        "![本地截图](https://example.com/screenshot.png)\n\n"
        "第三段分析"
    )
    clean, extracted = publisher._extract_images_from_body(body)
    assert "data:image/png;base64" not in clean
    assert "【📊 BTC走势分析图】" in clean
    assert "【本地截图】" in clean
    assert len(extracted) == 1
    assert extracted[0].startswith(b"\x89PNG")


def test_publish_passes_images_argument(monkeypatch, tmp_path):
    captured = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return (
                b"Cover uploaded.\nImages uploaded: 2.\nArticle submitted.\nSuccess!\nID: 99\nLink: https://example.test/99\n",
                b"",
            )

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs["env"]
        return FakeProcess()

    monkeypatch.setenv("BINANCE_SQUARE_OPENAPI_KEY", "fixture-secret")
    monkeypatch.setattr(publisher.shutil, "which", lambda _: "node")
    monkeypatch.setattr(publisher.asyncio, "create_subprocess_exec", fake_exec)
    script = tmp_path / "post-image.mjs"
    script.write_text("// fixture", encoding="utf-8")
    monkeypatch.setattr(publisher, "SCRIPT", script)

    dummy_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    result = asyncio.run(
        publisher.publish_blog(
            title="多图文章测试",
            body="正文分析内容",
            tags="#测试",
            cover_data_url=dummy_b64,
            images=[dummy_b64, dummy_b64]
        )
    )

    assert result["id"] == "99"
    assert result["content_type"] == "article_with_cover"
    assert result["cover_uploaded"] is True
    assert "--cover" in captured["args"]
    assert "--images" in captured["args"]
    # 验证提取并打包了 2 张 extra-image
    images_idx = captured["args"].index("--images")
    img_arg = captured["args"][images_idx + 1]
    assert "extra-image-1.png" in img_arg
    assert "extra-image-2.png" in img_arg

