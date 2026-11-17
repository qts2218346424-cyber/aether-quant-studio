from src.paths import load_frontend_bundle_text
import asyncio
from pathlib import Path
from fastapi.testclient import TestClient

from app import app
from openai_image_client import OpenAIImageClient, openai_image_client


client = TestClient(app)
html = load_frontend_bundle_text()


def test_openai_image_client_config():
    """Verify OpenAIImageClient reads config and normalizes endpoints."""
    img_client = OpenAIImageClient()
    cfg = img_client.get_config()
    assert "model" in cfg
    assert "size" in cfg
    assert "base_url" in cfg
    assert "has_api_key" in cfg

    # Test endpoint normalization
    assert img_client._normalize_endpoint("https://api.openai.com/v1") == "https://api.openai.com/v1/images/generations"
    assert img_client._normalize_endpoint("https://api.openai.com") == "https://api.openai.com/v1/images/generations"
    assert img_client._normalize_endpoint("https://new.sharedchat.cc/codex") == "https://new.sharedchat.cc/codex/images/generations"
    assert img_client._normalize_endpoint("https://api.openai.com/v1/images/generations") == "https://api.openai.com/v1/images/generations"


def test_openai_image_client_generate_simulate():
    """Verify generate_image handles simulation mode cleanly."""
    img_client = OpenAIImageClient()
    res = asyncio.run(img_client.generate_image(
        prompt="A futuristic crypto trading chart",
        symbol="BTCUSDT",
        simulate=True
    ))
    assert res["ok"] is True
    assert res["data_url"].startswith("data:image/png;base64,")
    assert res["model"] == img_client.get_config()["model"]
    assert res["size"] == "1792x1024"


def test_api_generate_blog_image_simulate():
    """Verify POST /api/blog/generate_image endpoint."""
    payload = {
        "prompt": "Neon crypto trading chart with candlestick patterns for ETHUSDT",
        "symbol": "ETHUSDT",
        "simulate": True
    }
    resp = client.post("/api/blog/generate_image", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["data_url"].startswith("data:image/png;base64,")
    assert "ETH" in data.get("prompt", "") or "ETH" in data.get("revised_prompt", "")


def test_api_openai_image_alias_simulate():
    """Verify alias POST /api/openai/generate_image works identically."""
    payload = {
        "prompt": "Cyberpunk quant trading robot",
        "symbol": "SOLUSDT",
        "simulate": True
    }
    resp = client.post("/api/openai/generate_image", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["data_url"].startswith("data:image/png;base64,")


def test_api_image_config_endpoint():
    """Verify GET /api/blog/image_config returns proper schema."""
    resp = client.get("/api/blog/image_config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "config" in data
    assert "model" in data["config"]


def test_frontend_has_openai_image_generation_ui():
    """Verify Blog Studio UI has OpenAI image generation controls."""
    assert "btn-blog-openai-img" in html
    assert "btn-blog-openai-cover" in html
    assert "blog-ai-gen-img" in html
    assert "generateOpenAIBlogImage" in html
    assert "OpenAI 智能生图" in html
    assert "OpenAI 绘制封面" in html
