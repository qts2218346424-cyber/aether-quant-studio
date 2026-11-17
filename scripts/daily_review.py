"""每日自动复盘: 读当天实盘交易记录, 生成结构化复盘报告

用法:
  python daily_review.py                  # 复盘今天(默认)
  python daily_review.py --date 2026-08-06  # 复盘指定日期
  python daily_review.py --out report.md  # 指定输出文件

输出: artifacts/daily_review/YYYY-MM-DD.md (默认) 或指定路径
"""
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
import src  # noqa: F401
import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "artifacts" / "daily_review"


def load_trades(date_str: str) -> list:
    path = DATA_DIR / f"trades_{date_str}.json"
    if not path.exists():
        print(f"[复盘] 找不到 {path}")
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt_pnl(u: float) -> str:
    return f"{u:+.2f}U"


def _reason_bucket(reason: str) -> str:
    """把带具体百分比/分数的平仓原因归并成大类, 便于统计"""
    if not reason:
        return "未知"
    r = str(reason)
    if "手动" in r or "manual" in r.lower():
        return "手动平仓"
    if "硬止损" in r or "hard" in r.lower():
        return "硬止损"
    if "结构止损" in r or "软止损" in r or "soft" in r.lower():
        return "结构止损"
    if "长线结构反转" in r:
        return "长线反转"
    if "跟踪止损" in r:
        return "跟踪止损"
    if "止盈" in r or "tp" in r.lower():
        return "分批止盈"
    if "结构预警" in r:
        return "结构预警"
    if "同向" in r or "网格" in r:
        return "网格/同向"
    return r[:20]


def analyze(trades: list, date_str: str) -> dict:
    opens = [t for t in trades if t.get("type") == "open"]
    closes = [t for t in trades if t.get("type") == "close"]

    rpt = {
        "date": date_str,
        "opens": len(opens),
        "closes": len(closes),
        "total_pnl": sum(float(t.get("pnl", 0) or 0) for t in closes),
        "total_commission": sum(float(t.get("commission", 0) or 0)
                                for t in opens + closes),
        "reasons": Counter(_reason_bucket(t.get("reason", "?"))
                           for t in closes),
        "symbols": Counter(t.get("symbol") for t in closes),
        "hours": Counter(
            datetime.fromtimestamp(int(t["timestamp"])).hour
            for t in closes if t.get("timestamp")),
    }

    wins = [t for t in closes if float(t.get("pnl", 0) or 0) > 0]
    losses = [t for t in closes if float(t.get("pnl", 0) or 0) < 0]
    rpt["win_rate"] = len(wins) / len(closes) * 100 if closes else 0.0
    rpt["avg_win"] = (sum(float(t["pnl"]) for t in wins) / len(wins)
                      if wins else 0.0)
    rpt["avg_loss"] = (sum(float(t["pnl"]) for t in losses) / len(losses)
                       if losses else 0.0)
    rpt["profit_factor"] = (
        abs(sum(float(t["pnl"]) for t in wins) /
            sum(float(t["pnl"]) for t in losses))
        if losses and sum(float(t["pnl"]) for t in losses) != 0 else float("inf")
    )

    # 最大连亏
    max_streak = cur = 0
    for t in closes:
        if float(t.get("pnl", 0) or 0) < 0:
            cur += 1
            max_streak = max(max_streak, cur)
        else:
            cur = 0
    rpt["max_loss_streak"] = max_streak

    # 每笔持仓时长(开→平配对, 用timestamp)
    open_ts = {}
    for t in opens:
        open_ts.setdefault(t.get("symbol"), []).append(int(t.get("timestamp", 0)))
    holds = []
    for t in closes:
        ts = int(t.get("timestamp", 0))
        if not ts:
            continue
        sym = t.get("symbol")
        cands = [o for o in open_ts.get(sym, []) if o <= ts]
        if cands:
            holds.append(ts - max(cands))
    holds.sort()
    rpt["hold_seconds_median"] = (
        holds[len(holds) // 2] if holds else None)
    rpt["hold_seconds_avg"] = (sum(holds) / len(holds) if holds else None)

    # 按开仓模式分(从 entry_context.mode / tp_state)
    mode_pnl = Counter()
    for t in closes:
        mode_pnl[t.get("source", "?")] += float(t.get("pnl", 0) or 0)
    rpt["source_pnl"] = dict(mode_pnl)

    # 方向盈亏
    dir_pnl = Counter()
    for t in closes:
        dir_pnl[t.get("side")] += float(t.get("pnl", 0) or 0)
    rpt["dir_pnl"] = dict(dir_pnl)

    # 手续费占毛利比
    gross_win = sum(float(t.get("pnl", 0) or 0) for t in wins)
    gross_loss = abs(sum(float(t.get("pnl", 0) or 0) for t in losses))
    rpt["commission_pct_of_gross"] = (
        rpt["total_commission"] / (gross_win + gross_loss) * 100
        if (gross_win + gross_loss) > 0 else 0.0)

    return rpt


def render(rpt: dict) -> str:
    date = rpt["date"]
    closes = rpt["closes"]
    if closes == 0:
        return f"# {date} 复盘\n\n今天没有平仓记录。\n"
    hold_med = (f"{rpt['hold_seconds_median']}s"
                if rpt["hold_seconds_median"] else "-")
    hold_avg = (f"{rpt['hold_seconds_avg']:.0f}s"
                if rpt["hold_seconds_avg"] else "-")
    pf = ("∞" if rpt["profit_factor"] == float("inf")
          else f"{rpt['profit_factor']:.2f}")

    lines = [
        f"# {date} 每日复盘",
        "",
        f"- 开仓 {rpt['opens']} 笔 / 平仓 {closes} 笔",
        f"- 净盈亏: **{fmt_pnl(rpt['total_pnl'])}** | 手续费 {rpt['total_commission']:.3f}U"
        f" (占毛利 {rpt['commission_pct_of_gross']:.1f}%)",
        f"- 胜率 {rpt['win_rate']:.1f}% | 均盈 {fmt_pnl(rpt['avg_win'])} / "
        f"均亏 {fmt_pnl(rpt['avg_loss'])} | 盈亏比 {pf}",
        f"- 最大连亏 **{rpt['max_loss_streak']} 笔** | "
        f"持仓中位 {hold_med} / 平均 {hold_avg}",
        "",
        "## 平仓原因分布",
        "",
        "| 原因 | 笔数 |",
        "| --- | --- |",
    ]
    for reason, cnt in rpt["reasons"].most_common():
        lines.append(f"| {reason} | {cnt} |")
    lines += ["", "## 币种盈亏(前10)", "",
              "| 币种 | 笔数 |", "| --- | --- |"]
    for sym, cnt in rpt["symbols"].most_common(10):
        lines.append(f"| {sym} | {cnt} |")
    lines += ["", "## 时段分布", "", "| 时段 | 平仓数 |", "| --- | --- |"]
    for h in sorted(rpt["hours"]):
        lines.append(f"| {h}点 | {rpt['hours'][h]} |")
    if rpt["dir_pnl"]:
        lines += ["", "## 方向盈亏", ""]
        for side, pnl in sorted(rpt["dir_pnl"].items()):
            lines.append(f"- {side}: {fmt_pnl(pnl)}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="每日交易复盘")
    ap.add_argument("--date", default=None, help="日期 YYYY-MM-DD, 默认今天")
    ap.add_argument("--out", default=None, help="输出markdown路径")
    args = ap.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    trades = load_trades(date_str)
    if not trades:
        print(f"[复盘] {date_str} 无交易记录")
        return
    rpt = analyze(trades, date_str)
    md = render(rpt)

    out = args.out
    if not out:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / f"{date_str}.md"
    else:
        out = Path(out)
    out.write_text(md, encoding="utf-8")
    print(md)
    print(f"\n[复盘] 报告已写入 {out}")


if __name__ == "__main__":
    main()
