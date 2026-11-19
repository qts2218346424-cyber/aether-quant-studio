"""System configuration hot-reloading and network proxy diagnostics routes."""

from __future__ import annotations

import asyncio
import os
import time
import aiohttp
from fastapi import APIRouter

from ai_committee import AICommittee
from binance_client import BinanceFuturesClient
from config import load_config, save_config
from openai_image_client import openai_image_client
from risk_manager import RiskManager
from src.api.context import get_trader
from strategy import StrategyEngine
from typesafe_engine import TypeSafeDecisionEngine

router = APIRouter(tags=["system"])


@router.get("/api/config")
async def get_config():
    cfg = load_config()
    raw_key = str(cfg.get("api_key", "") or "").strip()
    raw_secret = str(cfg.get("api_secret", "") or "").strip()
    is_placeholder = (
        not raw_key
        or not raw_secret
        or "YOUR_" in raw_key.upper()
        or "YOUR_" in raw_secret.upper()
        or "***" in raw_key
        or "***" in raw_secret
    )
    cfg["binance_api_configured"] = not is_placeholder
    cfg["api_key"] = raw_key[:8] + "***" if len(raw_key) > 8 and not is_placeholder else "***"
    cfg["api_secret"] = "***"
    for provider in cfg.get("ai_committee", {}).get("providers", []):
        provider["api_key_configured"] = bool(
            provider.get("api_key") or os.getenv(provider.get("api_key_env", ""))
        )
        if provider.get("api_key"):
            provider["api_key"] = "***"
    ts = cfg.setdefault("typesafe", {})
    ts["api_key_configured"] = bool(
        ts.get("api_key") or os.getenv(ts.get("api_key_env", "TYPESAFE_API_KEY"))
    )
    if ts.get("api_key"):
        ts["api_key"] = "***"
    img_gen = cfg.setdefault("ai_committee", {}).setdefault("image_generation", {})
    img_gen["api_key_configured"] = bool(
        img_gen.get("api_key") or os.getenv("OPENAI_IMAGE_API_KEY") or os.getenv("OPENAI_API_KEY")
    )
    if img_gen.get("api_key"):
        img_gen["api_key"] = "***"
    return cfg


@router.post("/api/config")
async def update_config(data: dict):
    """更新配置(不覆盖api_key/secret除非明确提供)"""
    t = get_trader()
    cfg = load_config()

    def merge_dict(current: dict, incoming: dict):
        for key, value in incoming.items():
            if key in ("api_key", "api_secret") and (not value or "***" in str(value)):
                continue
            if isinstance(value, dict) and isinstance(current.get(key), dict):
                merge_dict(current[key], value)
            else:
                current[key] = value

    for k, v in data.items():
        if k in ("api_key", "api_secret") and ("***" in str(v) or v == ""):
            continue
        if k == "ai_committee" and isinstance(v, dict):
            incoming = dict(v)
            incoming_providers = incoming.pop("providers", None)
            incoming_img = incoming.pop("image_generation", None)
            if "ai_committee" not in cfg:
                cfg["ai_committee"] = {}
            merge_dict(cfg["ai_committee"], incoming)
            if incoming_providers is not None:
                old_providers = cfg["ai_committee"].get("providers", [])
                merged_providers = []
                for index, provider in enumerate(incoming_providers):
                    old = dict(old_providers[index]) if index < len(old_providers) else {}
                    merge_dict(old, provider)
                    merged_providers.append(old)
                cfg["ai_committee"]["providers"] = merged_providers
            if incoming_img is not None:
                old_img = cfg["ai_committee"].setdefault("image_generation", {})
                if incoming_img.get("api_key") in ("***", ""):
                    incoming_img.pop("api_key", None)
                merge_dict(old_img, incoming_img)
        elif isinstance(v, dict) and isinstance(cfg.get(k), dict):
            merge_dict(cfg[k], v)
        else:
            cfg[k] = v

    # 如果提交了真实的 api_key / api_secret / base_url，则同步更新并热加载到 client
    binance_creds_updated = False
    account_node = cfg.setdefault("account", {})
    for cred_key in ("api_key", "api_secret"):
        val = str(data.get(cred_key, "") or "").strip()
        if val and "***" not in val:
            cfg[cred_key] = val
            account_node[cred_key] = val
            binance_creds_updated = True

    if "base_url" in data and str(data["base_url"] or "").strip():
        base_url_val = str(data["base_url"]).strip().rstrip("/")
        cfg["base_url"] = base_url_val
        account_node["base_url"] = base_url_val
        if "testnet" in base_url_val:
            cfg["ws_url"] = "wss://stream.binancefuture.com"
        else:
            cfg["ws_url"] = "wss://fstream.binance.com"
        account_node["ws_url"] = cfg["ws_url"]
        binance_creds_updated = True

    save_config(cfg)
    t.cfg = cfg
    openai_image_client.config_or_path = cfg

    if binance_creds_updated and hasattr(t, "client") and t.client:
        t.client.cfg = cfg
        t.client.api_key = cfg.get("api_key", "")
        t.client.api_secret = cfg.get("api_secret", "")
        t.client.base_url = cfg.get("base_url", "https://fapi.binance.com")
        t.client.ws_url = cfg.get("ws_url", "wss://fstream.binance.com")
        if t.client._session and not t.client._session.closed:
            asyncio.create_task(t.client._session.close())

    if "ai_committee" in data or "proxy" in data:
        ai_cfg = dict(cfg.get("ai_committee", {}) or {})
        if "proxy" not in ai_cfg and cfg.get("proxy"):
            ai_cfg["proxy"] = cfg.get("proxy")
        t.ai_committee = AICommittee(ai_cfg)

    if "typesafe" in data or "entry_decision_mode" in data:
        t.typesafe_engine = TypeSafeDecisionEngine(cfg.get("typesafe", {}), proxy=cfg.get("proxy"))
        t.entry_decision_mode = cfg.get("entry_decision_mode", "strategy_direct")

    if "symbols" in data:
        t.symbols = t._normalize_symbols(cfg.get("symbols", []))
        t._recommend_cache = None

    if "strategy" in data:
        t.strategy = StrategyEngine(cfg["strategy"])
        new_swing_interval = t._position_management_cfg().get("swing_interval", "1h")
        if new_swing_interval != t.swing_interval:
            t.swing_interval = new_swing_interval
            t.swing_cache.clear()
            t.swing_ohlc_cache.clear()

    if "proxy" in data:
        proxy_val = (data.get("proxy") or "").strip()
        cfg["proxy"] = proxy_val if proxy_val else None
        if hasattr(t, "client") and t.client:
            t.client.proxy = cfg["proxy"]
            if t.client._session and not t.client._session.closed:
                asyncio.create_task(t.client._session.close())

    if "risk" in data:
        t.risk = RiskManager(cfg["risk"])

    return {"ok": True, "entry_decision_mode": cfg.get("entry_decision_mode", "strategy_direct")}


@router.post("/api/test_proxy")
async def test_proxy_endpoint(data: dict):
    proxy = (data.get("proxy") or "").strip() or None
    start_time = time.time()
    try:
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            binance_url = "https://fapi.binance.com/fapi/v1/time"
            kw = {"proxy": proxy} if proxy else {}
            async with session.get(binance_url, **kw) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    return {"ok": False, "error": f"币安接口响应异常 HTTP {resp.status}: {text[:100]}"}
            latency = int((time.time() - start_time) * 1000)

            ip_str = "未知"
            try:
                async with session.get("https://api.ipify.org?format=json", **kw) as ip_resp:
                    if ip_resp.status == 200:
                        ip_json = await ip_resp.json()
                        ip_str = ip_json.get("ip", "未知")
            except Exception:
                pass

            return {
                "ok": True,
                "latency_ms": latency,
                "ip": ip_str,
                "message": f"连接正常！延迟 {latency}ms，出口 IP: {ip_str}",
            }
    except Exception as e:
        return {"ok": False, "error": f"连接测试失败: {str(e)}"}


@router.post("/api/test_binance_api")
async def test_binance_api_endpoint(data: dict):
    """测试币安期货 API Key / Secret 鉴权与余额读取权限"""
    cfg = load_config()
    raw_key = str(data.get("api_key", "") or "").strip()
    raw_secret = str(data.get("api_secret", "") or "").strip()
    base_url = str(data.get("base_url") or cfg.get("base_url") or "https://fapi.binance.com").strip().rstrip("/")
    proxy_val = data.get("proxy")
    proxy = (str(proxy_val).strip() or None) if proxy_val is not None else (cfg.get("proxy") or None)

    api_key = raw_key if (raw_key and "***" not in raw_key) else str(cfg.get("api_key", "") or "").strip()
    api_secret = raw_secret if (raw_secret and "***" not in raw_secret) else str(cfg.get("api_secret", "") or "").strip()

    if not api_key or not api_secret or "YOUR_" in api_key.upper() or "YOUR_" in api_secret.upper():
        return {"ok": False, "error": "请先填入有效的币安 API Key 与 Secret Key"}

    test_cfg = {
        **cfg,
        "api_key": api_key,
        "api_secret": api_secret,
        "base_url": base_url,
        "proxy": proxy,
    }
    client = BinanceFuturesClient(test_cfg)
    try:
        await client.sync_time()
        account = await client.get_account()
        total_wallet = float(account.get("totalWalletBalance", 0) or 0)
        avail_balance = float(account.get("availableBalance", 0) or 0)
        return {
            "ok": True,
            "total_wallet_balance": total_wallet,
            "available_balance": avail_balance,
            "message": f"鉴权成功！账户总权益: {total_wallet:.2f} USDT (可用: {avail_balance:.2f} USDT)",
        }
    except Exception as e:
        return {"ok": False, "error": f"API 鉴权失败: {str(e)}"}
    finally:
        if client._session and not client._session.closed:
            await client._session.close()
