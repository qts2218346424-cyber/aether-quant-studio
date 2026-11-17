from src.paths import load_frontend_bundle_text
import pytest
import re
from pathlib import Path
from starlette.testclient import TestClient
from app import app
from config import load_config, save_config

@pytest.fixture
def client():
    return TestClient(app)

def test_static_index_presets_and_ai_matrix():
    index_path = Path("static/index.html")
    assert index_path.exists()
    content = load_frontend_bundle_text()

    # Verify 4 Presets
    assert "STRATEGY_PRESETS" in content
    assert "conservative" in content
    assert "trend_swing" in content
    assert "aggressive" in content
    assert "ai_evolved" in content

    # Verify Core 3 Sliders
    assert "settings-core-strip" in content
    assert "set-leverage-range" in content
    assert "set-position-size-range" in content
    assert "set-max-daily-loss-range" in content
    assert "syncCoreSlider" in content

    # Verify Collapsible Advanced Parameters
    assert "settings-advanced-details" in content
    assert "advancedQuantTitle" in content

    # Verify AI Multi-Model Matrix & Roles
    assert "aiMatrixTitle" in content
    assert "aiCommitteeGateToggle" in content
    assert "set-ai-committee-enabled" in content
    assert "首席风控官" in content
    assert "数据精算师" in content
    assert "行情解盘师" in content

def test_api_config_ai_committee_toggle(client):
    cfg_before = load_config()
    orig_enabled = cfg_before.get("ai_committee", {}).get("enabled", False)

    # Test toggling ai_committee enabled
    resp = client.post("/api/config", json={
        "ai_committee": {"enabled": True}
    })
    assert resp.status_code == 200
    cfg_after = load_config()
    assert cfg_after.get("ai_committee", {}).get("enabled") is True

    # Restore
    client.post("/api/config", json={
        "ai_committee": {"enabled": orig_enabled}
    })
    cfg_restored = load_config()
    assert cfg_restored.get("ai_committee", {}).get("enabled") == orig_enabled
