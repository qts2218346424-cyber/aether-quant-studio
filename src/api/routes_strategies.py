"""Candidate strategy simulation, historical backtesting, and parameter auto-evolution routes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from candidate_strategies import CANDIDATE_STRATEGIES_REGISTRY, get_candidate_strategy
from config import load_config, save_config
from src.api.context import get_trader
from strategy_auto_improver import (
    AutoEvolutionObsidianSync,
    CandidateBacktestEngine,
    HistoricalDataLoader,
    StrategyAutoImprover,
)

router = APIRouter(tags=["strategies"])


@router.get("/api/strategies/candidates")
async def get_strategy_candidates():
    """获取所有备选量化策略列表、参数空间与最新进化预设"""
    presets = AutoEvolutionObsidianSync.get_presets()
    candidates = []
    for sid, cls in CANDIDATE_STRATEGIES_REGISTRY.items():
        preset_info = presets.get(sid, {})
        candidates.append({
            "id": sid,
            "name": cls.name,
            "title": cls.title,
            "description": cls.description,
            "timeframe": cls.timeframe,
            "category": cls.category,
            "default_symbols": cls.default_symbols,
            "default_params": cls.get_default_params(),
            "param_bounds": cls.get_param_bounds(),
            "optimized_params": preset_info.get("params"),
            "uplift": preset_info.get("uplift"),
            "last_optimized": preset_info.get("updated_at"),
        })
    return {"ok": True, "count": len(candidates), "candidates": candidates}


@router.post("/api/strategies/backtest")
async def run_strategy_backtest(data: dict):
    """在历史数据上模拟运行备选策略"""
    strategy_id = data.get("strategy_id", "trend_following")
    symbol = data.get("symbol", "BTCUSDT").upper().strip()
    interval = data.get("interval", "15m").strip()
    days = int(data.get("days", 15))
    custom_params = data.get("params")

    strat = get_candidate_strategy(strategy_id, custom_params)
    klines = await HistoricalDataLoader.load_klines(
        client=get_trader().client, symbol=symbol, interval=interval, days=days
    )
    metrics = CandidateBacktestEngine.run(strat, klines, interval=interval)
    return {
        "ok": True,
        "strategy_id": strategy_id,
        "symbol": symbol,
        "interval": interval,
        "days": days,
        "params": strat.params,
        "metrics": metrics.to_dict(),
    }


@router.post("/api/strategies/auto_improve")
async def run_strategy_auto_improve(data: dict):
    """启动备选策略自动改进与参数自进化引擎 (70%训练搜索 + 30%防过拟合检验)"""
    strategy_id = data.get("strategy_id", "grid_martingale")
    symbol = data.get("symbol", "BTCUSDT").upper().strip()
    interval = data.get("interval", "15m").strip()
    days = int(data.get("days", 20))
    custom_params = data.get("params")
    auto_sync = data.get("auto_sync_obsidian", True)

    klines = await HistoricalDataLoader.load_klines(
        client=get_trader().client, symbol=symbol, interval=interval, days=days
    )
    res = await StrategyAutoImprover.auto_improve(
        strategy_id=strategy_id,
        klines=klines,
        interval=interval,
        custom_params=custom_params,
    )
    res["symbol"] = symbol
    res["days"] = days

    if auto_sync:
        try:
            res["obsidian_sync"] = AutoEvolutionObsidianSync.sync_to_obsidian_note(res)
        except Exception as e:
            res["obsidian_sync"] = {"ok": False, "error": str(e)}

    return {"ok": True, **res}


@router.post("/api/strategies/apply_preset")
async def apply_strategy_preset(data: dict):
    """将进化后的最佳参数热应用到当前量化交易系统运行时配置"""
    strategy_id = data.get("strategy_id")
    params = data.get("params")
    if not strategy_id or not params:
        return JSONResponse({"ok": False, "error": "缺少 strategy_id 或 params"}, status_code=422)

    cfg = load_config()
    if "strategy" not in cfg:
        cfg["strategy"] = {}
    cfg["strategy"][f"candidate_{strategy_id}"] = params
    save_config(cfg)
    get_trader().cfg = cfg
    return {"ok": True, "message": f"策略【{strategy_id}】优化参数已成功热加载至系统运行时！"}


@router.post("/api/strategies/sync_obsidian")
async def sync_strategy_to_obsidian(data: dict):
    """将回测与进化报告主动写入 Obsidian 知识库对应策略笔记"""
    return AutoEvolutionObsidianSync.sync_to_obsidian_note(data)
