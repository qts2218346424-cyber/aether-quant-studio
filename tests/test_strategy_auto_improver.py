"""单元测试: 策略回测模拟与自动进化优化器 (strategy_auto_improver.py)"""
import pytest
import asyncio
from candidate_strategies import get_candidate_strategy
from strategy_auto_improver import (
    HistoricalDataLoader,
    CandidateBacktestEngine,
    StrategyAutoImprover,
    AutoEvolutionObsidianSync,
    BacktestMetrics
)


def test_synthetic_klines_generation():
    klines = HistoricalDataLoader.generate_synthetic_klines("BTCUSDT", "15m", 3)
    assert len(klines) >= 288
    # 验证字段格式
    first = klines[0]
    assert len(first) >= 6
    assert float(first[1]) > 0  # open
    assert float(first[2]) >= float(first[3])  # high >= low
    assert float(first[5]) > 0  # volume


def test_candidate_backtest_engine_run():
    klines = HistoricalDataLoader.generate_synthetic_klines("BTCUSDT", "15m", 10)
    strat = get_candidate_strategy("grid_martingale")
    m = CandidateBacktestEngine.run(strat, klines, "15m")

    assert isinstance(m, BacktestMetrics)
    assert m.total_trades >= 0
    assert 0.0 <= m.win_rate <= 100.0
    assert m.max_drawdown >= 0.0
    assert len(m.equity_curve) >= 1
    assert m.equity_curve[0]["equity"] == 100.0

    d = m.to_dict()
    assert "total_trades" in d
    assert "win_rate" in d
    assert "equity_curve" in d


def test_evaluate_fitness_function():
    m1 = BacktestMetrics(total_trades=1, win_rate=100.0, profit_factor=2.0)
    assert StrategyAutoImprover.evaluate_fitness(m1) == -999.0  # 笔数过少被过滤

    m2 = BacktestMetrics(total_trades=10, win_rate=70.0, net_pnl=15.0, profit_factor=2.5, max_drawdown=4.0, calmar_ratio=3.75)
    f2 = StrategyAutoImprover.evaluate_fitness(m2)
    assert f2 > 0.0

    m3 = BacktestMetrics(total_trades=10, win_rate=40.0, net_pnl=-10.0, profit_factor=0.6, max_drawdown=25.0, calmar_ratio=-0.4)
    f3 = StrategyAutoImprover.evaluate_fitness(m3)
    assert f2 > f3  # 优质策略适应度必定高于劣质策略


def test_sample_param_candidates():
    strat = get_candidate_strategy("trend_following")
    bounds = strat.get_param_bounds()
    base_params = strat.get_default_params()

    candidates = StrategyAutoImprover.sample_param_candidates(bounds, base_params, n_samples=16)
    assert len(candidates) == 17  # 1 基线 + 16 采样
    assert candidates[0] == base_params

    for cand in candidates[1:]:
        for k in bounds.keys():
            assert k in cand
            b = bounds[k]
            assert b["min"] <= cand[k] <= b["max"]


def test_strategy_auto_improve_workflow():
    klines = HistoricalDataLoader.generate_synthetic_klines("BTCUSDT", "15m", 15)
    res = asyncio.run(StrategyAutoImprover.auto_improve("trend_following", klines, "15m"))

    assert res["strategy_id"] == "trend_following"
    assert "baseline" in res
    assert "improved" in res
    assert "uplift" in res

    uplift = res["uplift"]
    assert "win_rate_delta" in uplift
    assert "net_pnl_delta" in uplift
    assert "drawdown_reduction" in uplift
    assert "is_genuine" in uplift

    # 验证指标与曲线
    assert len(res["baseline"]["metrics"]["equity_curve"]) >= 1
    assert len(res["improved"]["metrics"]["equity_curve"]) >= 1


def test_presets_saving_and_retrieval(tmp_path, monkeypatch):
    import strategy_auto_improver
    dummy_file = tmp_path / "presets.json"
    monkeypatch.setattr(strategy_auto_improver, "PRESETS_FILE", dummy_file)

    saved = AutoEvolutionObsidianSync.save_preset_to_config(
        "ttm_squeeze", {"trail_atr": 2.5}, {"win_rate_delta": 5.0}
    )
    assert saved["params"]["trail_atr"] == 2.5

    all_presets = AutoEvolutionObsidianSync.get_presets()
    assert "ttm_squeeze" in all_presets
    assert all_presets["ttm_squeeze"]["params"]["trail_atr"] == 2.5
