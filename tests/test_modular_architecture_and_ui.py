"""单元测试: 验证 v2.0 分层模块化架构、UI 现代化增强与开源配置安全性。"""

from __future__ import annotations

import json
from pathlib import Path
from fastapi.testclient import TestClient

from app import app
from src.paths import PROJECT_ROOT


def test_layered_backend_package_layout():
    for pkg in ("core", "strategies", "ai", "integrations", "api", "desktop"):
        pkg_dir = PROJECT_ROOT / "src" / pkg
        assert pkg_dir.is_dir(), f"Missing layered subpackage: src/{pkg}"
    assert (PROJECT_ROOT / "scripts").is_dir()


def test_modular_frontend_static_assets_served():
    client = TestClient(app)
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    html = root_resp.text
    assert '<meta name="color-scheme" content="light dark">' in html
    assert 'id="cmd-palette-trigger"' in html
    assert 'id="cmd-palette-overlay"' in html
    assert "AETHER" in html

    for css_name in (
        "01-base-and-tokens.css",
        "02-layout-and-header.css",
        "03-chart-and-panels.css",
        "04-modals-and-obsidian.css",
        "05-theme-light-and-safety.css",
        "06-aether-ui-polish.css",
    ):
        resp = client.get(f"/static/css/{css_name}")
        assert resp.status_code == 200, f"CSS asset failed: {css_name}"

    for js_name in (
        "01-core-i18n-theme.js",
        "02-chart-and-indicators.js",
        "03-ws-orders-diagnostics.js",
        "04-blog-and-settings.js",
        "05-obsidian-and-runtime.js",
        "06-command-palette.js",
    ):
        resp = client.get(f"/static/js/{js_name}")
        assert resp.status_code == 200, f"JS asset failed: {js_name}"


def test_modern_web_guidance_css_patterns_present():
    tokens_css = (PROJECT_ROOT / "static" / "css" / "01-base-and-tokens.css").read_text(encoding="utf-8")
    polish_css = (PROJECT_ROOT / "static" / "css" / "06-aether-ui-polish.css").read_text(encoding="utf-8")
    assert "color-scheme: light dark;" in tokens_css
    assert "@supports not (scrollbar-color: auto)" in tokens_css
    assert "accent-color: var(--brand-accent);" in tokens_css
    assert "border-block-end: 2px solid" in polish_css


def test_config_example_is_sanitized_for_public_repo():
    example_path = PROJECT_ROOT / "config.example.json"
    assert example_path.is_file()
    cfg = json.loads(example_path.read_text(encoding="utf-8"))
    assert cfg.get("api_key") == ""
    assert cfg.get("api_secret") == ""
    assert cfg.get("proxy") == ""
    assert cfg.get("live_trading_enabled") is False
    assert cfg.get("paper_trading") is True
    assert cfg.get("typesafe", {}).get("api_key") == ""
    for provider in cfg.get("ai_committee", {}).get("providers", []):
        assert provider.get("api_key") == ""
