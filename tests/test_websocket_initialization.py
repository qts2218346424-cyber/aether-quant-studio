from src.paths import load_frontend_bundle_text
from pathlib import Path


html = load_frontend_bundle_text()


def test_early_theme_dependencies_are_declared_before_initialization():
    init_call = html.index("initTheme();")
    assert html.index("let habitRadarChart = null;") < init_call
    assert html.index("let toolToastTimer = null;") < init_call
    assert html.count("let habitRadarChart = null;") == 1
    assert html.count("let toolToastTimer = null;") == 1


def test_websocket_connection_runs_after_theme_initialization():
    assert html.index("initTheme();") < html.index("connectWS();")
    assert "ws.onerror = () =>" in html
    assert "WebSocket message error" in html
