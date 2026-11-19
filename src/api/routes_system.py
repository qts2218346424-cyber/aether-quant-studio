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
from src.integrations.env_detector import detect_full_environment
from src.integrations.obsidian_bridge import obsidian_bridge
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

    if "ai_committee" in data or "ai_routing" in data or "proxy" in data:
        ai_cfg = dict(cfg.get("ai_committee", {}) or {})
        if cfg.get("ai_routing"):
            ai_cfg["ai_routing"] = cfg.get("ai_routing")
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


CURRENT_APP_VERSION = "v2.3.0"
GITHUB_REPO = "qts2218346424-cyber/aether-quant-studio"


def _parse_version_tuple(ver: str) -> tuple[int, ...]:
    cleaned = ver.strip().lstrip("vV")
    parts = []
    for seg in cleaned.split("."):
        digits = "".join(ch for ch in seg if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


@router.get("/api/system/check_update")
async def check_update_endpoint():
    """检查 GitHub Releases 最新软件版本"""
    cfg = load_config()
    proxy = (cfg.get("proxy") or "").strip() or None
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        timeout = aiohttp.ClientTimeout(total=8)
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "AetherQuantStudio/2.3",
        }
        kw = {"proxy": proxy} if proxy else {}
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url, headers=headers, **kw) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    latest_tag = str(data.get("tag_name") or "").strip()
                    release_url = str(data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases")
                    notes = str(data.get("body") or "").strip()
                    download_url = ""
                    for asset in data.get("assets") or []:
                        name = str(asset.get("name") or "").lower()
                        if name.endswith(".exe"):
                            download_url = str(asset.get("browser_download_url") or "")
                            break
                    has_update = bool(
                        latest_tag and _parse_version_tuple(latest_tag) > _parse_version_tuple(CURRENT_APP_VERSION)
                    )
                    return {
                        "ok": True,
                        "current_version": CURRENT_APP_VERSION,
                        "latest_version": latest_tag or CURRENT_APP_VERSION,
                        "has_update": has_update,
                        "release_url": release_url,
                        "download_url": download_url or release_url,
                        "release_notes": notes[:1200],
                    }

            # 若 GitHub API 遇到 403 限流，则走 Releases 页面 302 重定向检测（无速率限制）
            web_latest = f"https://github.com/{GITHUB_REPO}/releases/latest"
            async with session.get(web_latest, allow_redirects=True, **kw) as web_resp:
                final_url = str(web_resp.url)
                latest_tag = final_url.rstrip("/").split("/")[-1] if "/tag/" in final_url else ""
                if latest_tag:
                    has_update = _parse_version_tuple(latest_tag) > _parse_version_tuple(CURRENT_APP_VERSION)
                    return {
                        "ok": True,
                        "current_version": CURRENT_APP_VERSION,
                        "latest_version": latest_tag,
                        "has_update": has_update,
                        "release_url": final_url,
                        "download_url": f"https://github.com/{GITHUB_REPO}/releases/download/{latest_tag}/AetherQuantStudio-{latest_tag}.exe",
                        "release_notes": "",
                    }
            return {
                "ok": False,
                "current_version": CURRENT_APP_VERSION,
                "error": "无法获取最新版本信息，请稍后再试",
            }
    except Exception as e:
        return {
            "ok": False,
            "current_version": CURRENT_APP_VERSION,
            "error": f"无法连接 GitHub 检查更新: {str(e)}",
        }


@router.get("/api/env/detect")
async def detect_environment_endpoint():
    """自动探测本机 Antigravity 网关、Obsidian 知识库列表与代理配置"""
    return {"ok": True, "current_version": CURRENT_APP_VERSION, **detect_full_environment()}


@router.post("/api/env/test_antigravity")
async def test_antigravity_endpoint(data: dict):
    """仿知识库双轨桥接测试：优先探测本地 Antigravity 网关，若未开启则自动测试本机安装状态与云端 API 兜底通道"""
    from src.integrations.env_detector import probe_local_antigravity

    cfg = load_config()
    local_cfg = (cfg.get("ai_routing") or {}).get("local_antigravity") or {}
    base_url = str(data.get("base_url") or local_cfg.get("base_url") or "http://127.0.0.1:8045/v1").strip().rstrip("/")
    raw_key = str(data.get("api_key") or "").strip()
    api_key = raw_key if (raw_key and "***" not in raw_key) else (local_cfg.get("api_key") or "antigravity-local")
    model = str(data.get("model") or local_cfg.get("model") or "gemini-2.5-flash").strip()

    endpoint = base_url if base_url.endswith("/chat/completions") else (f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions")
    start_ts = time.time()
    local_err = ""

    # 1. 尝试本地 Antigravity OpenAI 兼容网关
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with OK"}],
            "max_tokens": 12,
            "temperature": 0,
        }
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(endpoint, headers=headers, json=payload) as resp:
                latency = int((time.time() - start_ts) * 1000)
                text = await resp.text()
                if resp.status == 200:
                    return {
                        "ok": True,
                        "mode": "local_gateway",
                        "latency_ms": latency,
                        "message": f"本地 Antigravity 网关直连成功，延迟 {latency}ms (模型: {model})",
                    }
                local_err = f"HTTP {resp.status}: {text[:80]}"
    except Exception as e:
        local_err = str(e)[:80]

    # 2. 本地网关未开启时，参照知识库项目检测本机 Antigravity 安装与云端高可用兜底通道
    ag_probe = probe_local_antigravity(base_url)
    providers = (cfg.get("ai_committee") or {}).get("providers") or []
    cloud_fallback_ok = False
    cloud_name = ""

    for prov in providers:
        p_key = os.getenv(prov.get("api_key_env", "")) or str(prov.get("api_key", "")).strip()
        p_url = str(prov.get("base_url", "")).strip().rstrip("/")
        p_model = str(prov.get("model", "")).strip()
        if p_key and p_url and p_model:
            try:
                t_start = time.time()
                p_ep = f"{p_url}/chat/completions" if p_url.endswith("/v1") else f"{p_url}/v1/chat/completions"
                kw = {"proxy": cfg.get("proxy")} if cfg.get("proxy") else {}
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=6)) as session:
                    async with session.post(
                        p_ep,
                        headers={"Authorization": f"Bearer {p_key}", "Content-Type": "application/json"},
                        json={"model": p_model, "messages": [{"role": "user", "content": "OK"}], "max_tokens": 8},
                        **kw,
                    ) as c_resp:
                        if c_resp.status == 200:
                            cloud_fallback_ok = True
                            cloud_name = f"{prov.get('name', p_model)} ({int((time.time() - t_start) * 1000)}ms)"
                            break
            except Exception:
                continue

    if ag_probe.get("installed") and cloud_fallback_ok:
        return {
            "ok": True,
            "mode": "hybrid_fallback",
            "message": f"本机 Antigravity 已就绪；本地网关未开启 ({local_err})，已自动切换云端兜底引擎: {cloud_name}",
        }
    if cloud_fallback_ok:
        return {
            "ok": True,
            "mode": "cloud_fallback",
            "message": f"本地网关不可用 ({local_err})，已验证云端兜底引擎可用: {cloud_name}",
        }

    if ag_probe.get("installed"):
        return {
            "ok": False,
            "error": f"已检测到本机 Antigravity，但本地网关反代未开启 ({local_err})，且尚未配置可用的云端 API 兜底。",
        }
    return {"ok": False, "error": f"本地 Antigravity 网关不可用 ({local_err})，且无可用云端 API"}


@router.post("/api/obsidian/configure")
async def configure_obsidian_endpoint(data: dict):
    """绑定并初始化本机 Obsidian 知识库路径"""
    vault_path = str(data.get("vault_path") or "").strip()
    auto_sync = bool(data.get("auto_sync", True))
    init_templates = bool(data.get("init_templates", True))

    if not vault_path:
        return {"ok": False, "error": "请提供有效的 Obsidian 知识库文件夹路径"}

    res = obsidian_bridge.set_vault_path(vault_path, auto_sync=auto_sync)
    if init_templates:
        try:
            obsidian_bridge.init_templates(overwrite=False)
            obsidian_bridge.compile_vault()
        except Exception:
            pass
    return res
