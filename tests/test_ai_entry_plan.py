import numpy as np

from ai_analyst import AIAnalyst


def test_long_entry_plan_uses_pullback_zone_and_valid_risk_order():
    plan = AIAnalyst()._build_entry_plan(
        action="偏多",
        confidence=80,
        price=100.0,
        atr=2.0,
        supports=[96.0, 92.0],
        resistances=[106.0, 112.0],
        htf_trend=1,
    )

    assert plan["status"] == "READY"
    assert plan["side"] == "LONG"
    assert plan["entry_low"] < plan["entry_high"] < 100.0
    assert plan["stop_loss"] < plan["entry_low"]
    assert plan["tp1"] > plan["entry_high"]
    assert plan["tp2"] > plan["tp1"]
    assert plan["rr"] >= 1.5


def test_short_entry_plan_never_places_stop_below_entry_zone():
    plan = AIAnalyst()._build_entry_plan(
        action="偏空",
        confidence=78,
        price=100.0,
        atr=2.0,
        supports=[88.0],
        resistances=[104.0, 110.0],
        htf_trend=-1,
    )

    assert plan["status"] == "READY"
    assert plan["side"] == "SHORT"
    assert 100.0 < plan["entry_low"] < plan["entry_high"]
    assert plan["stop_loss"] > plan["entry_high"]
    assert plan["tp1"] < plan["entry_low"]
    assert plan["tp2"] < plan["tp1"]


def test_neutral_entry_plan_is_waiting_not_market_entry():
    plan = AIAnalyst()._build_entry_plan(
        action="观望",
        confidence=40,
        price=100.0,
        atr=2.0,
        supports=[96.0],
        resistances=[104.0],
        htf_trend=0,
    )

    assert plan["status"] == "WAIT"
    assert plan["entry_price"] is None


def test_analyze_exposes_numeric_entry_plan():
    closes = np.linspace(90.0, 100.0, 100)
    highs = closes + 1.0
    lows = closes - 1.0
    volumes = np.full(100, 1000.0)

    result = AIAnalyst().analyze(closes, highs, lows, volumes)

    assert "entry_plan" in result
    assert set(("status", "side", "entry_price", "stop_loss", "tp1", "tp2")).issubset(
        result["entry_plan"]
    )
