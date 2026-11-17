"""TypeSafe Jev (System One) and AI Committee connectivity/gating routes."""

from __future__ import annotations

import json
import os
import time
import aiohttp
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ai_committee import AICommittee
from config import load_config, save_config
from openai_image_client import openai_image_client
from src.api.context import get_trader

router = APIRouter(tags=["ai"])


@router.get("/api/ai_reviews")
async def get_ai_reviews():
    """多AI入场评审已停用(策略直连模式)"""
    return {
        "entry_decision_mode": "strategy_direct",
        "enabled": False,
        "min_votes": 0,
        "min_confidence": 0,
        "providers": [],
        "reviews": [],
    }


@router.get("/api/typesafe/status")
async def get_typesafe_status():
    """获取 TypeSafe Jev 决策引擎运行状态与审查历史"""
    t = get_trader()
    cfg = load_config()
    ts_cfg = cfg.get("typesafe", {})
    api_key_configured = bool(
        ts_cfg.get("api_key") or os.getenv(ts_cfg.get("api_key_env", "TYPESAFE_API_KEY"))
    )
    bridge = getattr(t.typesafe_engine, "obsidian_bridge", None)
    vault_path = str(bridge.get_vault_path()) if bridge and bridge.get_vault_path() else None
    return {
        "ok": True,
        "entry_decision_mode": getattr(t, "entry_decision_mode", "strategy_direct"),
        "enabled": bool(ts_cfg.get("enabled", False)),
        "api_key_configured": api_key_configured,
        "model": ts_cfg.get("model", "jev-latest"),
        "min_confidence": ts_cfg.get("min_confidence", 0.65),
        "max_risk_score": ts_cfg.get("max_risk_score", 2.5),
        "min_breakout_score": ts_cfg.get("min_breakout_score", 1.8),
        "use_obsidian_playbook": bool(ts_cfg.get("use_obsidian_playbook", True)),
        "min_playbook_score": ts_cfg.get("min_playbook_score", 1.5),
        "max_violation_prob": ts_cfg.get("max_violation_prob", 0.45),
        "autonomous_hunter": ts_cfg.get("autonomous_hunter", {}),
        "autonomous_hunter_enabled": (
            getattr(t, "entry_decision_mode", "") in ("typesafe_hybrid", "typesafe_autonomous", "hybrid")
            and bool(ts_cfg.get("autonomous_hunter", {}).get("enabled", False))
        ),
        "obsidian_vault_connected": bool(vault_path),
        "obsidian_vault_path": vault_path,
        "recent_reviews": getattr(t, "typesafe_reviews_log", [])[-20:],
    }


@router.post("/api/typesafe/test")
async def test_typesafe(data: dict = None):
    """测试 TypeSafe Jev API 连通性与响应时间"""
    data = data or {}
    api_key = str(data.get("api_key", "")).strip()
    return await get_trader().typesafe_engine.test_connection(api_key=api_key)


@router.post("/api/typesafe/toggle")
async def toggle_typesafe(data: dict = None):
    """快捷开关 TypeSafe Jev 决策模式"""
    t = get_trader()
    cfg = load_config()
    ts = cfg.setdefault("typesafe", {})
    data = data or {}
    mode = data.get("mode")
    if mode in ("typesafe_hybrid", "typesafe_jev", "typesafe_evaluator", "strategy_direct"):
        new_mode = mode
        new_state = mode != "strategy_direct"
    elif "enabled" in data:
        new_state = bool(data["enabled"])
        new_mode = "typesafe_hybrid" if new_state else "strategy_direct"
    else:
        new_state = not bool(ts.get("enabled", False))
        new_mode = "typesafe_hybrid" if new_state else "strategy_direct"

    ts["enabled"] = new_state
    cfg["entry_decision_mode"] = new_mode
    save_config(cfg)
    t.cfg = cfg
    t.entry_decision_mode = cfg["entry_decision_mode"]
    t.typesafe_engine.enabled = new_state
    return {
        "ok": True,
        "enabled": new_state,
        "entry_decision_mode": cfg["entry_decision_mode"],
        "message": f"TypeSafe Jev 模式已切换为: {new_mode}",
    }


@router.post("/api/ai_test")
async def test_ai_provider(data: dict):
    """测试单个AI供应商或图像生成模型，不触发交易，也不保存临时密钥。"""
    cfg = load_config()
    target_type = data.get("type") or ("image" if str(data.get("index")) == "image" else "text")
    if target_type == "image":
        img_cfg = data.get("provider", {}) or {}
        api_key = (img_cfg.get("api_key") or "").strip()
        base_url = (img_cfg.get("base_url") or "").strip()
        if not api_key:
            cur_cfg = openai_image_client.get_config()
            api_key = cur_cfg.get("_api_key", "")
            if not base_url:
                base_url = cur_cfg.get("base_url", "https://api.openai.com/v1")
        if not api_key:
            return {"success": False, "status": "missing_api_key", "reason": "未配置或输入 OpenAI API Key"}

        test_url = base_url.rstrip("/")
        if test_url.endswith("/v1") or test_url.endswith("/codex"):
            candidate_urls = [f"{test_url}/models"]
        else:
            candidate_urls = [f"{test_url}/v1/models", f"{test_url}/models"]

        headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
        }
        start_t = time.perf_counter()
        proxy = cfg.get("proxy")
        try:
            timeout = aiohttp.ClientTimeout(total=8)
            kw = {"headers": headers, "timeout": timeout}
            if proxy:
                kw["proxy"] = proxy
            async with aiohttp.ClientSession() as session:
                for c_idx, models_url in enumerate(candidate_urls):
                    async with session.get(models_url, **kw) as resp:
                        body_t = await resp.text()
                        latency = round((time.perf_counter() - start_t) * 1000)
                        if resp.status in (200, 201):
                            try:
                                m_data = json.loads(body_t)
                                m_list = [str(x.get("id", "")).lower() for x in m_data.get("data", []) if isinstance(x, dict)]
                                req_model = (img_cfg.get("model") or "dall-e-3").lower()
                                if m_list and req_model not in m_list and not any(req_model in m for m in m_list):
                                    has_any_image = any(
                                        any(k in m for k in ("dall", "flux", "midjourney", "image", "sd"))
                                        for m in m_list
                                    )
                                    if not has_any_image:
                                        return {
                                            "success": False,
                                            "status": "no_image_channel",
                                            "reason": f"网关连通，但该站点未开放绘图：当前渠道全为文本模型，无 {req_model} 绘图渠道",
                                            "latency_ms": latency,
                                        }
                                    return {
                                        "success": False,
                                        "status": "model_not_supported",
                                        "reason": f"网关连通但未找到模型 {req_model} (支持: {', '.join(m_list[:4])})",
                                        "latency_ms": latency,
                                    }
                            except Exception:
                                pass
                            return {"success": True, "latency_ms": latency, "status": "ok", "message": f"连接正常 ({latency}ms)"}
                        elif resp.status in (401, 403):
                            return {"success": False, "status": "auth_failed", "reason": f"API Key 鉴权失败 (HTTP {resp.status})", "latency_ms": latency}
                        elif resp.status == 404 and c_idx + 1 < len(candidate_urls):
                            continue
                        elif "<html" in body_t.lower() or "<!doctype" in body_t.lower():
                            sugg = f"{test_url}/v1" if "/v1" not in test_url else test_url
                            return {"success": False, "status": "html_error", "reason": f"接口返回网页(HTML)而非API：请检查是否缺少 /v1 路径 (建议改为: {sugg})", "latency_ms": latency}
                        else:
                            return {"success": True, "latency_ms": latency, "status": "ok", "message": f"网关响应正常 (HTTP {resp.status}, {latency}ms)"}
        except Exception as e:
            return {"success": False, "status": "error", "reason": f"连接异常: {str(e)}"}

    providers = cfg.get("ai_committee", {}).get("providers", [])
    try:
        index = int(data.get("index", -1))
    except (ValueError, TypeError):
        index = -1
    if index < 0 or index >= len(providers):
        return JSONResponse(
            {"success": False, "status": "invalid_provider", "reason": "模型索引无效"},
            status_code=400,
        )

    provider = dict(providers[index])
    overrides = data.get("provider", {}) or {}
    for key in ("name", "model", "base_url", "api_key_env", "temperature", "json_mode"):
        if key in overrides:
            provider[key] = overrides[key]
    api_key = str(overrides.get("api_key", "") or "")
    tester = AICommittee({
        "enabled": True,
        "providers": [provider],
        "proxy": cfg.get("proxy"),
        "timeout_seconds": data.get("timeout_seconds", cfg.get("ai_committee", {}).get("timeout_seconds", 12)),
    })
    return await tester.test_provider(provider, api_key=api_key)
