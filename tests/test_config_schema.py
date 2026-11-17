import json
from pathlib import Path

import config


def test_normalized_config_has_versioned_sections():
    normalized = config.load_normalized_config()

    assert normalized["schema_version"] == config.CONFIG_SCHEMA_VERSION == 2
    for key in (
        "account",
        "market",
        "signals",
        "systems",
        "risk",
        "execution",
        "ui",
        "ai_committee",
    ):
        assert key in normalized


def test_legacy_aliases_survive_normalization():
    normalized = config.load_normalized_config()

    assert normalized["symbols"] == normalized["market"]["symbols"]
    assert normalized["leverage"] == normalized["market"]["leverage"]
    assert normalized["interval"] == normalized["market"]["interval"]
    assert normalized["strategy"] == normalized["signals"]
    assert normalized["risk"]["max_positions"] >= 1
    assert normalized["execution"] is normalized["execution"]


def test_normalization_does_not_mutate_the_source_file():
    source = Path(config.CONFIG_PATH).read_bytes()

    config.load_normalized_config()

    assert Path(config.CONFIG_PATH).read_bytes() == source


def test_save_uses_atomic_replace_and_preserves_masked_credentials(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    original = {
        "api_key": "real-key",
        "api_secret": "real-secret",
        "symbols": ["BTCUSDT"],
        "leverage": 2,
        "interval": "15m",
        "strategy": {},
        "risk": {"max_positions": 1},
        "execution": {},
    }
    config_path.write_text(
        json.dumps(original, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "CONFIG_PATH", str(config_path))

    normalized = config.load_normalized_config()
    normalized["account"]["api_key"] = "***"
    normalized["account"]["api_secret"] = "***"
    normalized["market"]["interval"] = "1h"
    normalized["interval"] = "1h"
    config.save_normalized_config(normalized)

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["api_key"] == original["api_key"]
    assert saved["api_secret"] == original["api_secret"]
    assert saved["account"]["api_key"] == original["api_key"]
    assert saved["account"]["api_secret"] == original["api_secret"]
    assert saved["market"]["interval"] == "1h"
    assert saved["interval"] == "1h"
    assert not list(tmp_path.glob("*.tmp"))


def test_save_rejects_masked_credentials_without_existing_values(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"account": {"api_key": "***"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "CONFIG_PATH", str(config_path))

    normalized = config.load_normalized_config()

    try:
        config.save_normalized_config(normalized)
    except ValueError as exc:
        assert "credential" in str(exc).lower()
    else:
        raise AssertionError("masked credentials must not be persisted")
