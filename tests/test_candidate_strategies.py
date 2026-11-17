"""单元测试: 7大备选量化高胜率策略引擎 (candidate_strategies.py)"""
import numpy as np
import pytest

from candidate_strategies import (
    CANDIDATE_STRATEGIES_REGISTRY,
    get_candidate_strategy,
    BaseCandidateStrategy,
    DCAMartingaleStrategy,
    SMCOrderBlockStrategy,
    TTMSqueezeStrategy,
    VWAPReversionStrategy,
    TurtleBreakoutStrategy,
    EMARSIDivergenceStrategy,
    EMATrendStrategy,
)
from strategy_auto_improver import HistoricalDataLoader


@pytest.fixture
def sample_klines():
    """生成 300 根合成测试 K 线"""
    return HistoricalDataLoader.generate_synthetic_klines("BTCUSDT", "15m", 5)


def test_candidate_registry_has_all_12_strategies():
    expected_ids = {
        "grid_martingale",
        "smart_money",
        "ttm_squeeze",
        "vwap_reversion",
        "turtle_breakout",
        "ema_rsi_divergence",
        "trend_following",
        "wyckoff_spring",
        "ict_silver_bullet",
        "amd_asian_session",
        "volume_profile_poc",
        "momentum_flag_relay",
    }
    assert expected_ids.issubset(set(CANDIDATE_STRATEGIES_REGISTRY.keys()))
    assert len(CANDIDATE_STRATEGIES_REGISTRY) >= 12


@pytest.mark.parametrize("strat_id", [
    "grid_martingale", "smart_money", "ttm_squeeze",
    "vwap_reversion", "turtle_breakout", "ema_rsi_divergence", "trend_following",
    "wyckoff_spring", "ict_silver_bullet", "amd_asian_session", "volume_profile_poc", "momentum_flag_relay"
])
def test_strategy_instantiation_and_bounds(strat_id):
    strat = get_candidate_strategy(strat_id)
    assert isinstance(strat, BaseCandidateStrategy)
    assert strat.id == strat_id
    assert strat.title != ""
    assert strat.timeframe in ["15m", "1h", "4h"]

    defaults = strat.get_default_params()
    assert isinstance(defaults, dict) and len(defaults) > 0

    bounds = strat.get_param_bounds()
    assert isinstance(bounds, dict) and len(bounds) > 0

    # 验证每一个 bound 结构
    for k, b in bounds.items():
        assert "type" in b
        assert "min" in b and "max" in b
        assert b["min"] <= b["max"]


def test_strategy_alias_lookup():
    assert isinstance(get_candidate_strategy("dca"), DCAMartingaleStrategy)
    assert isinstance(get_candidate_strategy("martingale"), DCAMartingaleStrategy)
    assert isinstance(get_candidate_strategy("smc"), SMCOrderBlockStrategy)
    assert isinstance(get_candidate_strategy("squeeze"), TTMSqueezeStrategy)
    assert isinstance(get_candidate_strategy("vwap"), VWAPReversionStrategy)
    assert isinstance(get_candidate_strategy("turtle"), TurtleBreakoutStrategy)
    assert isinstance(get_candidate_strategy("divergence"), EMARSIDivergenceStrategy)
    assert isinstance(get_candidate_strategy("trend"), EMATrendStrategy)
    assert get_candidate_strategy("wyckoff").id == "wyckoff_spring"
    assert get_candidate_strategy("silver_bullet").id == "ict_silver_bullet"
    assert get_candidate_strategy("amd").id == "amd_asian_session"
    assert get_candidate_strategy("poc").id == "volume_profile_poc"
    assert get_candidate_strategy("flag").id == "momentum_flag_relay"


def test_strategy_signals_and_lifecycle(sample_klines):
    closes = np.array([float(k[4]) for k in sample_klines])
    highs = np.array([float(k[2]) for k in sample_klines])
    lows = np.array([float(k[3]) for k in sample_klines])
    volumes = np.array([float(k[5]) for k in sample_klines])

    from strategy import calc_atr
    atr_arr = calc_atr(highs, lows, closes, 14)

    for strat_id, strat_cls in CANDIDATE_STRATEGIES_REGISTRY.items():
        strat = strat_cls()
        signals = strat.generate_signals(closes, highs, lows, volumes)
        assert isinstance(signals, list)

        # 模拟生命周期
        exits, hold_bars, reason = strat.simulate_lifecycle(
            closes, highs, lows, volumes, atr_arr, start_idx=30, side="LONG"
        )
        assert isinstance(exits, list)
        assert len(exits) >= 1
        assert hold_bars >= 0
        assert isinstance(reason, str) and len(reason) > 0
