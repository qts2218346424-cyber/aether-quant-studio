from src.paths import load_frontend_bundle_text
"""单元测试: 策略回测与自进化 FastAPI 接口与前端元素 (test_strategy_evolution_api.py)"""
import asyncio
from pathlib import Path
from app import (
    get_strategy_candidates,
    run_strategy_backtest,
    run_strategy_auto_improve,
    apply_strategy_preset
)


def test_api_strategies_candidates():
    data = asyncio.run(get_strategy_candidates())
    assert data["ok"] is True
    assert data["count"] >= 7
    candidates = data["candidates"]
    cand_ids = [c["id"] for c in candidates]
    assert "grid_martingale" in cand_ids
    assert "trend_following" in cand_ids
    assert "ttm_squeeze" in cand_ids
    assert "param_bounds" in candidates[0]
    assert "default_params" in candidates[0]


def test_api_strategies_backtest():
    payload = {
        "strategy_id": "trend_following",
        "symbol": "BTCUSDT",
        "interval": "15m",
        "days": 5
    }
    data = asyncio.run(run_strategy_backtest(payload))
    assert data["ok"] is True
    assert data["strategy_id"] == "trend_following"
    assert "metrics" in data
    assert "win_rate" in data["metrics"]
    assert "equity_curve" in data["metrics"]


def test_api_strategies_auto_improve():
    payload = {
        "strategy_id": "ttm_squeeze",
        "symbol": "ETHUSDT",
        "interval": "15m",
        "days": 5,
        "auto_sync_obsidian": False
    }
    data = asyncio.run(run_strategy_auto_improve(payload))
    assert data["ok"] is True
    assert data["strategy_id"] == "ttm_squeeze"
    assert "baseline" in data
    assert "improved" in data
    assert "uplift" in data


def test_api_strategies_apply_preset():
    payload = {
        "strategy_id": "trend_following",
        "params": {"ema_fast": 8, "ema_slow": 22}
    }
    data = asyncio.run(apply_strategy_preset(payload))
    assert data["ok"] is True


def test_frontend_evolution_elements_in_html():
    html = load_frontend_bundle_text()
    assert 'data-obs-tab="evolution"' in html
    assert 'id="obs-tab-evolution"' in html
    assert 'id="btn-evo-backtest"' in html
    assert 'id="btn-evo-auto"' in html
    assert 'id="evo-strat-select"' in html
    assert 'id="evo-equity-chart"' in html
    assert 'id="evo-params-tbody"' in html
    assert 'id="evo-quick-btn"' in html
    assert 'function runStrategyBacktestUI()' in html
    assert 'function runStrategyAutoImproveUI()' in html
    assert 'function syncEvolvedResultToObsidian()' in html
    assert 'function applyEvolvedPresetToSystem()' in html
