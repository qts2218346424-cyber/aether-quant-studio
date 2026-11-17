"""Configuration loading and schema-v2 normalization.

The trading runtime still consumes the legacy top-level keys. The
normalization layer adds grouped sections without changing trading logic.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
import shutil
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG_PATH = os.path.join(str(PROJECT_ROOT), "config.json")
CONFIG_PATH = _DEFAULT_CONFIG_PATH
EXAMPLE_CONFIG_PATH = os.path.join(str(PROJECT_ROOT), "config.example.json")
CONFIG_SCHEMA_VERSION = 2

_CREDENTIAL_KEYS = ("api_key", "api_secret")
_MASKED_CREDENTIAL_MARKERS = (
    "***",
    "•••",
    "[REDACTED]",
    "[MASKED]",
    "REDACTED",
    "MASKED",
)

_DEFAULT_ACCOUNT = {
    "api_key": "",
    "api_secret": "",
    "base_url": "https://fapi.binance.com",
    "ws_url": "wss://fstream.binance.com",
    "proxy": "",
}
_DEFAULT_MARKET = {
    "symbols": [],
    "leverage": 1,
    "interval": "15m",
}
_DEFAULT_SYSTEMS = {
    "active": "trend_following",
    "enabled": ["trend_following"],
}
_DEFAULT_UI = {
    "theme": "dark",
    "language": "zh-CN",
    "refresh_interval_sec": 5,
    "compact_mode": False,
}
_DEFAULT_AI_COMMITTEE = {
    "enabled": False,
    "min_votes": 2,
    "min_confidence": 65,
    "require_unanimous": False,
    "timeout_seconds": 20,
    "providers": [],
}
_DEFAULT_TYPESAFE = {
    "enabled": False,
    "api_key": "",
    "api_key_env": "TYPESAFE_API_KEY",
    "model": "jev-latest",
    "timeout_seconds": 8.0,
    "min_confidence": 0.65,
    "max_risk_score": 2.5,
    "min_breakout_score": 1.8,
    "use_obsidian_playbook": True,
    "min_playbook_score": 1.5,
    "max_violation_prob": 0.45,
}
_DEFAULT_CREATOR_PROMOTION = {
    "enabled": True,
    "referral_code": "",
    "referral_url": "",
    "copy_trading_url": "",
    "fee_discount_pct": 20,
    "custom_hook": "注册即享最高 20% 手续费永久返还，主页同步实盘量化信号",
}


def _read_json(path: str | os.PathLike[str]) -> dict[str, Any]:
    target = Path(path)
    if (
        not target.exists()
        and os.path.abspath(str(target)) == os.path.abspath(_DEFAULT_CONFIG_PATH)
        and os.path.exists(EXAMPLE_CONFIG_PATH)
    ):
        shutil.copyfile(EXAMPLE_CONFIG_PATH, target)
    with open(target, "r", encoding="utf-8") as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise ValueError("configuration root must be a JSON object")
    return value


def _dict_copy(value: Any) -> dict[str, Any]:
    return copy.deepcopy(value) if isinstance(value, dict) else {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _is_masked_credential(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return True
    upper = text.upper()
    return any(marker.upper() in upper for marker in _MASKED_CREDENTIAL_MARKERS)


def _first_real_credential(*values: Any) -> str | None:
    for value in values:
        if not _is_masked_credential(value):
            return value
    return None


def _build_section(
    raw: dict[str, Any],
    name: str,
    defaults: dict[str, Any],
    *,
    legacy_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    section = copy.deepcopy(defaults)
    if legacy_values:
        section = _deep_merge(section, legacy_values)
    section = _deep_merge(section, _dict_copy(raw.get(name)))
    return section


def load_config() -> dict[str, Any]:
    """Load the legacy configuration unchanged for existing callers."""
    return _read_json(CONFIG_PATH)


def load_normalized_config() -> dict[str, Any]:
    """Load config.json and expose schema-v2 grouped sections."""
    raw = _read_json(CONFIG_PATH)
    normalized = copy.deepcopy(raw)

    account_legacy = {
        key: raw[key]
        for key in ("api_key", "api_secret", "base_url", "ws_url", "proxy")
        if key in raw
    }
    account = _build_section(
        raw, "account", _DEFAULT_ACCOUNT, legacy_values=account_legacy
    )

    market_legacy = {
        key: raw[key] for key in ("symbols", "leverage", "interval") if key in raw
    }
    market = _build_section(
        raw, "market", _DEFAULT_MARKET, legacy_values=market_legacy
    )

    signals = _build_section(
        raw, "signals", {}, legacy_values=_dict_copy(raw.get("strategy"))
    )
    risk = _build_section(raw, "risk", {}, legacy_values=_dict_copy(raw.get("risk")))
    execution = _build_section(
        raw, "execution", {}, legacy_values=_dict_copy(raw.get("execution"))
    )
    systems = _build_section(raw, "systems", _DEFAULT_SYSTEMS)
    ui = _build_section(raw, "ui", _DEFAULT_UI)
    ai_committee = _build_section(raw, "ai_committee", _DEFAULT_AI_COMMITTEE)
    typesafe = _build_section(raw, "typesafe", _DEFAULT_TYPESAFE)
    creator_promotion = _build_section(raw, "creator_promotion", _DEFAULT_CREATOR_PROMOTION)

    normalized.update(
        {
            "schema_version": CONFIG_SCHEMA_VERSION,
            "account": account,
            "market": market,
            "signals": signals,
            "systems": systems,
            "risk": risk,
            "execution": execution,
            "ui": ui,
            "ai_committee": ai_committee,
            "typesafe": typesafe,
            "creator_promotion": creator_promotion,
        }
    )

    # Keep legacy aliases synchronized with the normalized sections.
    normalized["api_key"] = account["api_key"]
    normalized["api_secret"] = account["api_secret"]
    normalized["base_url"] = account["base_url"]
    normalized["ws_url"] = account["ws_url"]
    normalized["proxy"] = account["proxy"]
    normalized["symbols"] = market["symbols"]
    normalized["leverage"] = market["leverage"]
    normalized["interval"] = market["interval"]
    normalized["strategy"] = signals
    normalized.setdefault("entry_decision_mode", "technical_first")
    return normalized


def _credential_from_mapping(mapping: Any, key: str) -> Any:
    return mapping.get(key) if isinstance(mapping, dict) else None


def _protect_credentials(candidate: dict[str, Any], existing: dict[str, Any]) -> None:
    """Resolve masked credential aliases without persisting a mask."""
    candidate_account = candidate.get("account")
    existing_account = existing.get("account")
    if not isinstance(candidate_account, dict):
        candidate_account = {}
        candidate["account"] = candidate_account

    for key in _CREDENTIAL_KEYS:
        incoming = _first_real_credential(
            _credential_from_mapping(candidate_account, key),
            candidate.get(key),
        )
        stored = _first_real_credential(
            _credential_from_mapping(existing_account, key),
            existing.get(key),
        )
        value = incoming or stored
        if value is None:
            raise ValueError(f"credential field {key} is masked or empty")
        candidate_account[key] = value
        candidate[key] = value

    cand_ts = candidate.get("typesafe")
    exist_ts = existing.get("typesafe")
    if isinstance(cand_ts, dict) and isinstance(exist_ts, dict):
        incoming_ts = _first_real_credential(cand_ts.get("api_key"))
        stored_ts = _first_real_credential(exist_ts.get("api_key"))
        cand_ts["api_key"] = incoming_ts or stored_ts or ""


def save_normalized_config(cfg: dict[str, Any]) -> None:
    """Persist a normalized config using a validated same-directory temp file."""
    if not isinstance(cfg, dict):
        raise TypeError("configuration must be a dict")

    target = Path(CONFIG_PATH)
    existing = _read_json(target) if target.exists() else {}
    candidate = copy.deepcopy(cfg)
    _protect_credentials(candidate, existing)

    candidate["schema_version"] = CONFIG_SCHEMA_VERSION
    if not isinstance(candidate.get("account"), dict):
        candidate["account"] = {}
    if not isinstance(candidate.get("market"), dict):
        candidate["market"] = {}
    if not isinstance(candidate.get("signals"), dict):
        candidate["signals"] = _dict_copy(candidate.get("strategy"))

    account = candidate["account"]
    market = candidate["market"]
    candidate["api_key"] = account["api_key"]
    candidate["api_secret"] = account["api_secret"]
    for key in ("base_url", "ws_url", "proxy"):
        if key in account:
            candidate[key] = account[key]
    for key in ("symbols", "leverage", "interval"):
        if key in market:
            candidate[key] = market[key]
    candidate["strategy"] = candidate["signals"]

    target.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(target.parent),
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp:
            temp_name = temp.name
            json.dump(candidate, temp, indent=2, ensure_ascii=False)
            temp.write("\n")
            temp.flush()
            os.fsync(temp.fileno())

        validated = _read_json(temp_name)
        for key in _CREDENTIAL_KEYS:
            if _is_masked_credential(validated.get(key)) or _is_masked_credential(
                validated.get("account", {}).get(key)
            ):
                raise ValueError(f"credential field {key} is masked or empty")

        os.replace(temp_name, target)
        temp_name = None
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def save_config(cfg: dict[str, Any]) -> None:
    """Legacy direct writer retained for callers outside the migration step."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
