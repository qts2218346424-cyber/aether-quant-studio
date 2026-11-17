"""Test and Calibration CLI for TypeSafe Jev (System One) Decision Engine.

Usage:
    python test_typesafe.py --test-conn
    python test_typesafe.py --mock-signal
    python test_typesafe.py --replay
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from config import load_config
from typesafe_engine import TypeSafeDecisionEngine, TypeSafeStateBuilder


async def run_test_connection(api_key: str = ""):
    print("=" * 60)
    print("Testing TypeSafe Jev (System One) API Connection...")
    print("=" * 60)
    cfg = load_config()
    engine = TypeSafeDecisionEngine(cfg.get("typesafe", {}), proxy=cfg.get("proxy"))

    key_to_use = api_key or engine.get_api_key()
    if not key_to_use:
        print("[-] Error: No TypeSafe API Key found.")
        print("    Please set the TYPESAFE_API_KEY environment variable or pass --api-key <KEY>.")
        sys.exit(1)

    print(f"[*] Target Model: {engine.model}")
    print(f"[*] Proxy: {engine.proxy or 'Direct (no proxy)'}")
    masked_key = key_to_use[:6] + "..." + key_to_use[-4:] if len(key_to_use) > 10 else "***"
    print(f"[*] API Key: {masked_key}")

    result = await engine.test_connection(api_key=key_to_use)
    if result["success"]:
        print(f"[+] SUCCESS! {result['message']}")
        print(f"[+] Roundtrip Latency: {result['latency_ms']} ms")
        print(f"[+] Responded Model: {result['model']}")
    else:
        print(f"[-] FAILED! {result['message']}")
        print(f"[-] Latency: {result['latency_ms']} ms")
        sys.exit(1)


async def run_mock_signals(api_key: str = ""):
    print("=" * 60)
    print("Simulating Market Scenarios with TypeSafe Jev Decision Engine...")
    print("=" * 60)
    cfg = load_config()
    engine = TypeSafeDecisionEngine(cfg.get("typesafe", {}), proxy=cfg.get("proxy"))
    if api_key:
        engine.configured_api_key = api_key

    scenarios = [
        {
            "name": "Scenario A: High-Conviction Bullish Breakout (BTCUSDT)",
            "symbol": "BTCUSDT",
            "signal": 1,
            "price": 93250.0,
            "recent_closes": [92100.0, 92300.0, 92450.0, 92600.0, 92900.0, 93250.0],
            "funding_rate": 0.0001,
            "candidate_context": {
                "base_score": 68.5,
                "pattern": "连续阳线(强势上攻)",
                "strategy_factors": ["EMA ribbon bullish stack", "Volume expansion > 2.5x", "HTF 1h aligned"],
                "htf_aligned": True,
                "indicators": {"rsi": 63.5, "macd_hist": 45.2, "atr": 450.0},
                "smart_money": {"intent": "拉升", "score": 26.0},
                "liquidity": {"quote_volume_24h": 4500000000.0, "spread_bps": 0.5},
            },
        },
        {
            "name": "Scenario B: Bearish Breakdown on Heavy Volume (ETHUSDT)",
            "symbol": "ETHUSDT",
            "signal": -1,
            "price": 3120.0,
            "recent_closes": [3210.0, 3190.0, 3175.0, 3150.0, 3130.0, 3120.0],
            "funding_rate": -0.0002,
            "candidate_context": {
                "base_score": -62.0,
                "pattern": "连续阴线(弱势下行)",
                "strategy_factors": ["Break below 24h support", "MACD bearish divergence", "HTF trend down"],
                "htf_aligned": True,
                "indicators": {"rsi": 32.0, "macd_hist": -12.5, "atr": 28.0},
                "smart_money": {"intent": "出货", "score": -22.0},
                "liquidity": {"quote_volume_24h": 2200000000.0, "spread_bps": 1.2},
            },
        },
        {
            "name": "Scenario C: Exhausted Bull Trap into Resistance (SOLUSDT)",
            "symbol": "SOLUSDT",
            "signal": 1,
            "price": 185.0,
            "recent_closes": [178.0, 182.0, 184.5, 185.2, 185.1, 185.0],
            "funding_rate": 0.0008,  # Overheated funding
            "candidate_context": {
                "base_score": 46.0,
                "pattern": "长上影线(上方抛压重)",
                "strategy_factors": ["Testing overhead resistance", "Declining volume", "Funding overheated"],
                "htf_aligned": False,
                "indicators": {"rsi": 78.5, "macd_hist": 0.05, "atr": 3.8},
                "smart_money": {"intent": "出货", "score": -15.0},
                "liquidity": {"quote_volume_24h": 850000000.0, "spread_bps": 2.5},
            },
        },
    ]

    for sc in scenarios:
        print(f"\n--- {sc['name']} ---")
        res = await engine.evaluate_entry(
            symbol=sc["symbol"],
            candidate_signal=sc["signal"],
            price=sc["price"],
            candidate_context=sc["candidate_context"],
            recent_closes=sc["recent_closes"],
            funding_rate=sc["funding_rate"],
        )

        def _fmt(val: Any, decimals: int = 2) -> str:
            return f"{float(val):.{decimals}f}" if val is not None else "N/A"

        status_tag = "[APPROVED]" if res.get("approved") else "[REJECTED]"
        print(f"Outcome: {status_tag} {res.get('reason')}")
        print(f"Decision: Jev Action = {res.get('jev_action')} (Confidence: {_fmt(res.get('confidence'))})")
        print(f"Action Probabilities: {res.get('action_probabilities')}")
        print(f"Market Regime: {res.get('market_regime')}")
        print(f"Breakout Quality Score: {_fmt(res.get('breakout_quality_score'))}/4.0")
        print(f"Risk Level Score: {_fmt(res.get('risk_level_score'))}/4.0 (Conf: {_fmt(res.get('risk_confidence'))})")
        print(f"Trend Continuation Prob: {_fmt(res.get('trend_continuation_prob'), 3)}")
        if res.get("obsidian_playbook"):
            pb = res["obsidian_playbook"]
            print(f"Obsidian Strategy: {pb.get('matched_strategy')} ({pb.get('strategy_type')}) [Vault Match: {pb.get('vault_match_score')}%]")
            print(f"Playbook Adherence Score: {_fmt(res.get('playbook_score'))}/4.0")
            print(f"Discipline Violation Risk: {_fmt(res.get('discipline_violation_prob'), 3)}")
        print(f"Composite Score: {_fmt(res.get('composite_score'), 1)}/100.0")
        print(f"Latency: {res.get('latency_ms')} ms")
        if res.get("risk_flags"):
            print(f"Risk Flags: {res.get('risk_flags')}")


async def run_replay(api_key: str = "", limit: int = 5):
    print("=" * 60)
    print("Replaying Historical Signals with TypeSafe Jev...")
    print("=" * 60)
    analysis_file = Path("trade_analysis.json")
    if not analysis_file.exists():
        print("[-] No trade_analysis.json found to replay.")
        return

    try:
        with open(analysis_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[-] Failed to read trade_analysis.json: {e}")
        return

    trades = data.get("recent_trades", []) or data.get("trades", [])
    if not trades:
        print("[-] No trades found in analysis file.")
        return

    cfg = load_config()
    engine = TypeSafeDecisionEngine(cfg.get("typesafe", {}), proxy=cfg.get("proxy"))
    if api_key:
        engine.configured_api_key = api_key

    print(f"[*] Found {len(trades)} historical trades. Replaying the most recent {min(limit, len(trades))}...")

    for trade in trades[:limit]:
        sym = trade.get("symbol", "UNKNOWN")
        side = trade.get("side", "LONG")
        sig = 1 if side == "LONG" else -1
        price = float(trade.get("entry_price") or trade.get("price", 100.0))
        pnl = float(trade.get("pnl") or trade.get("profit", 0.0))

        context = {
            "base_score": trade.get("score", 50.0),
            "strategy_factors": trade.get("factors", ["Historical entry"]),
            "indicators": {"rsi": 55.0, "atr": price * 0.015},
            "smart_money": {"intent": "观望", "score": 10.0},
        }

        res = await engine.evaluate_entry(
            symbol=sym,
            candidate_signal=sig,
            price=price,
            candidate_context=context,
        )

        real_outcome = f"Real PnL: {pnl:+.2f} USDT"
        jev_outcome = "PASS" if res.get("approved") else "BLOCK"
        print(f"\nTrade: {sym} {side} @ {price} | {real_outcome}")
        print(f"-> Jev Verdict: {jev_outcome} ({res.get('reason')}) | Conf: {res.get('confidence', 0):.2f}")


def main():
    parser = argparse.ArgumentParser(description="TypeSafe Jev System One Evaluation CLI")
    parser.add_argument("--test-conn", "-c", action="store_true", help="Test API key connection and latency")
    parser.add_argument("--mock-signal", "-m", action="store_true", help="Run simulated market scenarios through Jev")
    parser.add_argument("--replay", "-r", action="store_true", help="Replay recent trades from trade_analysis.json")
    parser.add_argument("--api-key", "-k", type=str, default="", help="Override TypeSafe API Key")
    args = parser.parse_args()

    if not (args.test_conn or args.mock_signal or args.replay):
        parser.print_help()
        sys.exit(0)

    if args.test_conn:
        asyncio.run(run_test_connection(api_key=args.api_key))
    elif args.mock_signal:
        asyncio.run(run_mock_signals(api_key=args.api_key))
    elif args.replay:
        asyncio.run(run_replay(api_key=args.api_key))


if __name__ == "__main__":
    main()
