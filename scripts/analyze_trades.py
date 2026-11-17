"""交易记录胜率分析 - 拉取币安真实历史成交, 统计胜率/盈亏比/方向/币种/时段分布"""
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
import src  # noqa: F401
import asyncio
import json
import time
from collections import defaultdict
from datetime import datetime

from binance_client import BinanceFuturesClient
from config import load_config


def rows_in_time_window(rows: list[dict], start_ms: int, end_ms: int) -> list[dict]:
    """Keep only exchange rows whose timestamp belongs to the requested analysis window."""
    result = []
    for row in rows or []:
        try:
            timestamp = int(row.get("time", 0) or 0)
        except (TypeError, ValueError):
            continue
        if start_ms <= timestamp <= end_ms:
            result.append(row)
    return result


async def main(period_days: int = 30):
    cfg = load_config()
    client = BinanceFuturesClient(cfg)
    await client.sync_time()
    period_days = max(1, int(period_days))
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - period_days * 86400 * 1000

    # 1) 收益流水(30天): 已实现盈亏 + 手续费 + 资金费
    print("[1/3] 拉取收益流水...", flush=True)
    pnl_rows, fee_rows, fund_rows = await asyncio.gather(
        client.get_income_history(
            "REALIZED_PNL", start_time=start_ms, end_time=end_ms),
        client.get_income_history(
            "COMMISSION", start_time=start_ms, end_time=end_ms),
        client.get_income_history(
            "FUNDING_FEE", start_time=start_ms, end_time=end_ms),
    )
    # The income endpoint should already honor the interval. Filter again so
    # analytics stays correct if a proxy/exchange returns an out-of-window row.
    pnl_rows = rows_in_time_window(pnl_rows, start_ms, end_ms)
    fee_rows = rows_in_time_window(fee_rows, start_ms, end_ms)
    fund_rows = rows_in_time_window(fund_rows, start_ms, end_ms)

    symbols = sorted({r["symbol"] for r in pnl_rows if r.get("symbol")})
    print(f"  已实现盈亏笔数={len(pnl_rows)} 涉及币种={len(symbols)} {symbols}", flush=True)

    # 2) 每个币种成交流水 -> 提取平仓事件(带方向/数量/时间)
    print("[2/3] 拉取各币种成交流水...", flush=True)
    close_events = []  # {symbol, side, pnl, qty, price, time, hour}
    truncated_windows = {}
    for sym in symbols:
        try:
            trades, truncated = await client.get_user_trades_time_range(
                sym, start_time=start_ms, end_time=end_ms, limit=1000)
            if truncated:
                truncated_windows[sym] = truncated
        except Exception as e:
            print(f"  {sym} userTrades失败: {e}", flush=True)
            continue
        for t in rows_in_time_window(trades, start_ms, end_ms):
            rpnl = float(t.get("realizedPnl", 0))
            if rpnl == 0:
                continue  # 开仓成交, 跳过
            ts = int(t["time"])
            close_events.append({
                "symbol": sym,
                "side": t.get("positionSide", "?"),  # LONG/SHORT(对冲模式)
                "pnl": rpnl,
                "qty": float(t.get("qty", 0)),
                "price": float(t.get("price", 0)),
                "time": ts,
                "hour": datetime.fromtimestamp(ts / 1000).hour,
                "date": datetime.fromtimestamp(ts / 1000).strftime("%m-%d"),
            })
        await asyncio.sleep(0.1)

    # 3) 统计
    print("[3/3] 统计...", flush=True)
    total_pnl_income = sum(float(r["income"]) for r in pnl_rows)
    total_fee = sum(float(r["income"]) for r in fee_rows)
    total_fund = sum(float(r["income"]) for r in fund_rows)
    user_trade_pnl = sum(e["pnl"] for e in close_events)

    def stats(events):
        if not events:
            return None
        wins = [e for e in events if e["pnl"] > 0]
        losses = [e for e in events if e["pnl"] < 0]
        gross_win = sum(e["pnl"] for e in wins)
        gross_loss = abs(sum(e["pnl"] for e in losses))
        n = len(events)
        return {
            "trades": n,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / n * 100, 1),
            "total_pnl": round(sum(e["pnl"] for e in events), 3),
            "avg_win": round(gross_win / len(wins), 3) if wins else 0,
            "avg_loss": round(-gross_loss / len(losses), 3) if losses else 0,
            "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else float("inf"),
            "max_win": round(max((e["pnl"] for e in events), default=0), 3),
            "max_loss": round(min((e["pnl"] for e in events), default=0), 3),
        }

    overall = stats(close_events)
    by_symbol = {s: stats([e for e in close_events if e["symbol"] == s]) for s in symbols}
    by_side = {sd: stats([e for e in close_events if e["side"] == sd]) for sd in ["LONG", "SHORT"]}
    by_hour = {h: stats([e for e in close_events if e["hour"] == h]) for h in sorted({e["hour"] for e in close_events})}

    # 持仓时长近似: 同一symbol按时间排序, 相邻平仓间隔(粗略)
    result = {
        "period_days": period_days,
        "analysis_window": {
            "start_ms": start_ms,
            "end_ms": end_ms,
            "start": datetime.fromtimestamp(start_ms / 1000).isoformat(timespec="seconds"),
            "end": datetime.fromtimestamp(end_ms / 1000).isoformat(timespec="seconds"),
        },
        "income_summary": {
            "realized_pnl": round(total_pnl_income, 3),
            "commission": round(total_fee, 3),
            "funding_fee": round(total_fund, 3),
            "net": round(total_pnl_income + total_fee + total_fund, 3),
        },
        "reconciliation": {
            "user_trades_realized_pnl": round(user_trade_pnl, 3),
            "income_realized_pnl": round(total_pnl_income, 3),
            "difference": round(user_trade_pnl - total_pnl_income, 3),
            "within_tolerance": abs(user_trade_pnl - total_pnl_income) <= 0.01,
            "truncated_windows": truncated_windows,
            "note": (
                "Statistics below are realized-PnL fill events, not position round trips. "
                "Use income_summary.net as the account-level result."
            ),
        },
        "close_event_count": len(close_events),
        "overall": overall,
        "by_symbol": by_symbol,
        "by_side": by_side,
        "by_hour": by_hour,
    }
    with open("trade_analysis.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
