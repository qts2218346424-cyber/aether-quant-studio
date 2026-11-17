"""Market data, indicator telemetry, rankings, and system catalog routes."""

from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config import load_config
from src.api.context import get_trader

router = APIRouter(tags=["market"])


@router.get("/api/status")
async def get_status():
    return await get_trader().get_status()


@router.get("/api/systems")
async def get_systems():
    """可用交易系统目录；只读，不触发行情请求或订单操作。"""
    cfg = load_config()
    systems_cfg = cfg.get("systems", {}) if isinstance(cfg.get("systems"), dict) else {}
    active = systems_cfg.get("active", "trend_following")
    enabled = set(systems_cfg.get("enabled", ["trend_following"]))
    modules = [
        {
            "name": "trend_following",
            "label": "Trend Following",
            "category": "trend",
            "description": "EMA structure, HTF alignment and closed-candle confirmation.",
        },
        {
            "name": "breakout",
            "label": "Breakout Momentum",
            "category": "momentum",
            "description": "Range expansion, volume confirmation and volatility shift.",
        },
        {
            "name": "mean_reversion",
            "label": "Mean Reversion",
            "category": "range",
            "description": "RSI extremes, Bollinger deviation and reversion confirmation.",
        },
        {
            "name": "smart_money",
            "label": "Smart Flow",
            "category": "flow",
            "description": "Large-account positioning, OI, funding and crowding.",
        },
        {
            "name": "grid",
            "label": "Grid System",
            "category": "range",
            "description": "Range detection, ATR spacing and layered risk limits.",
        },
        {
            "name": "ensemble",
            "label": "Ensemble Vote",
            "category": "portfolio",
            "description": "Cross-system agreement, confidence aggregation and risk gating.",
        },
    ]
    for item in modules:
        item["active"] = item["name"] == active
        item["enabled"] = item["name"] in enabled
        item["read_only_preview"] = item["name"] != active
    return {
        "active": active,
        "enabled": sorted(enabled),
        "modules": modules,
        "orders_created": 0,
        "ts": datetime.now().isoformat(timespec="seconds"),
    }


@router.post("/api/systems/preview")
async def preview_systems(data: dict):
    """交易系统只读预览；绝不提交订单或修改持仓。"""
    requested = data.get("systems") or []
    if not isinstance(requested, list):
        return JSONResponse({"error": "systems must be a list"}, status_code=422)
    catalog = await get_systems()
    by_name = {item["name"]: item for item in catalog["modules"]}
    names = [str(name) for name in requested if str(name) in by_name]
    if not names:
        names = [catalog["active"]]
    symbol = str(data.get("symbol") or "").upper()
    t = get_trader()
    indicators = t.latest_indicators.get(symbol, {}) if symbol else {}
    results = []
    for name in names:
        item = dict(by_name[name])
        item.update({
            "signal": 0,
            "confidence": 0,
            "reason": "Preview only; waiting for a closed-candle evaluation.",
            "symbol": symbol or None,
            "has_live_indicators": bool(indicators),
        })
        results.append(item)
    return {
        "mode": "read_only",
        "closed_candle_only": True,
        "data_quality": 100 if indicators else 0,
        "orders_created": 0,
        "symbol": symbol or None,
        "interval": data.get("interval") or t.interval,
        "results": results,
        "ts": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/api/klines/{symbol}")
async def get_klines(symbol: str, interval: str = None, limit: int = 200):
    t = get_trader()
    iv = interval or t.interval
    data = await t.client.get_klines(symbol, iv, limit)
    return [{
        "time": k[0],
        "open": float(k[1]),
        "high": float(k[2]),
        "low": float(k[3]),
        "close": float(k[4]),
        "volume": float(k[5]),
    } for k in data]


@router.get("/api/indicators/{symbol}")
async def get_indicators(symbol: str):
    return get_trader().latest_indicators.get(symbol, {})


@router.get("/api/analysis/{symbol}")
async def get_analysis(symbol: str):
    """AI实时K线分析"""
    return await get_trader().get_analysis(symbol)


@router.get("/api/smart_money/{symbol}")
async def get_smart_money(symbol: str, force: bool = False):
    """聪明钱综合评分：大户持仓/账户、散户拥挤、OI、价格、成交量、资金费率。"""
    return await get_trader().get_smart_money(symbol.upper(), force=force)


@router.get("/api/news")
async def get_news():
    """新闻列表+情绪统计"""
    return await get_trader().get_news()


@router.get("/api/market_rankings")
async def get_market_rankings(max_price: float = 5, limit: int = 20):
    """Low-price USDT futures: 24h gainers, losers and quote-volume leaders."""
    t = get_trader()
    tickers = await t.client.get_all_tickers()
    result = t.build_market_rankings(tickers, max_price=max_price, limit=limit)
    result["ts"] = datetime.now().strftime("%H:%M:%S")
    return result


@router.get("/api/recommend")
async def get_recommend():
    """实时合约推荐 + 匹配总资产的杠杆/仓位"""
    return await get_trader().get_recommendations()
