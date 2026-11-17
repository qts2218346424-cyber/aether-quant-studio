"""Order execution, position control, trade journal, and report export routes."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, Response

from obsidian_bridge import obsidian_bridge
from src.api.context import get_trader
from src.paths import DATA_DIR
from trade_journal import journal

logger = logging.getLogger("app.trading")
router = APIRouter(tags=["trading"])


@router.get("/api/rank_preview")
async def rank_preview(symbol: str, max_price: float = None, leverage: int = None, margin: float = None, side: str = None):
    """榜单一键下单预览(支持自定义杠杆、仓位保证金、方向)"""
    return await get_trader().rank_order_preview(
        symbol, max_price=max_price, leverage=leverage, margin=margin, side=side
    )


@router.post("/api/rank_one_click")
async def rank_one_click(data: dict = None):
    """榜单一键下单(支持自定义杠杆、仓位保证金、方向、止损止盈)"""
    data = data or {}
    return await get_trader().rank_one_click_open(
        data.get("symbol", ""),
        max_price=data.get("max_price"),
        leverage=data.get("leverage"),
        margin=data.get("margin"),
        side=data.get("side"),
        sl=data.get("sl"),
        tp=data.get("tp"),
    )


@router.post("/api/chart_limit_order")
async def chart_limit_order(data: dict):
    """K线图票据提交GTC限价开仓；不执行平仓、自动交易或保护单。"""
    try:
        return await get_trader().manual_limit_open(
            symbol=data.get("symbol", ""),
            side=data.get("side", ""),
            quantity=data.get("quantity"),
            price=data.get("price"),
        )
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=422)
    except (RuntimeError, asyncio.TimeoutError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)


@router.get("/api/signals")
async def get_signals():
    return get_trader().signals_log[-50:]


@router.get("/api/trades")
async def get_trades(
    limit: int = 500,
    symbol: str = None,
    date_str: str = None,
    time_range: str = "7d",
    start_date: str = None,
    end_date: str = None,
):
    """获取成交记录: 综合持久化实盘账单(journal)与实时成交记录(trades_log)，支持多时间段与自定义日期筛选"""
    t = get_trader()
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    today_date = now.date()

    all_files = sorted(DATA_DIR.glob("trades_*.json"), reverse=True)
    all_file_dates = [f.stem.replace("trades_", "") for f in all_files]

    target_dates = None
    min_timestamp = None

    if date_str:
        target_dates = {date_str}
    elif time_range == "today":
        target_dates = {today_str}
    elif time_range == "24h":
        yesterday_str = (today_date - timedelta(days=1)).strftime("%Y-%m-%d")
        target_dates = {today_str, yesterday_str}
        min_timestamp = int((now - timedelta(hours=24)).timestamp())
    elif time_range == "3d":
        target_dates = {(today_date - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(3)}
    elif time_range == "7d":
        target_dates = {(today_date - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)}
    elif time_range == "30d":
        target_dates = {(today_date - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)}
    elif time_range == "custom":
        target_dates = set()
        s_date = start_date or "2020-01-01"
        e_date = end_date or today_str
        for fd in all_file_dates:
            if s_date <= fd <= e_date:
                target_dates.add(fd)
    elif time_range == "all":
        target_dates = None

    raw_records = []
    for f in all_files:
        d_str = f.stem.replace("trades_", "")
        if target_dates is None or d_str in target_dates:
            try:
                day_recs = journal.get_day_records(d_str)
                for r in day_recs:
                    r_copy = dict(r)
                    r_copy["date"] = d_str
                    r_copy["datetime"] = f"{d_str} {r.get('time', '')}".strip()
                    raw_records.append(r_copy)
            except Exception:
                pass

    if min_timestamp:
        raw_records = [r for r in raw_records if (int(r.get("timestamp") or 0) >= min_timestamp or not r.get("timestamp"))]

    existing_ids = {r.get("order_id") for r in raw_records if r.get("order_id")}
    combined = list(raw_records)
    for rec in getattr(t, "trades_log", []):
        if rec.get("order_id") and rec.get("order_id") in existing_ids:
            continue
        t_copy = dict(rec)
        t_time = rec.get("time", "")
        t_ts = int(rec.get("timestamp") or 0)
        t_date = today_str
        if t_ts:
            try:
                t_date = datetime.fromtimestamp(t_ts).strftime("%Y-%m-%d")
            except Exception:
                pass
        t_copy["date"] = t_date
        t_copy["datetime"] = f"{t_date} {t_time}".strip()

        if target_dates is not None and t_date not in target_dates:
            continue
        if min_timestamp and t_ts and t_ts < min_timestamp:
            continue
        combined.append(t_copy)

    if symbol:
        norm_sym = symbol.strip().upper().replace("/", "")
        combined = [r for r in combined if str(r.get("symbol") or "").upper().replace("/", "") == norm_sym]

    combined.sort(key=lambda r: int(r.get("timestamp") or 0), reverse=True)
    limited = combined[:limit]

    total_trades = len(limited)
    close_trades = [r for r in limited if r.get("type") in ("close", "partial_close") or r.get("pnl") is not None]
    total_pnl = sum(float(r.get("pnl") or 0) for r in close_trades)
    win_count = sum(1 for r in close_trades if float(r.get("pnl") or 0) > 0)
    loss_count = sum(1 for r in close_trades if float(r.get("pnl") or 0) < 0)
    win_rate = round((win_count / len(close_trades) * 100), 1) if close_trades else 0.0
    total_fee = sum(float(r.get("commission") or 0) for r in limited)

    summary = {
        "time_range": time_range,
        "total_trades": total_trades,
        "close_count": len(close_trades),
        "total_pnl": round(total_pnl, 4),
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": win_rate,
        "total_commission": round(total_fee, 4),
    }

    unique_symbols = sorted(list({str(r.get("symbol") or "").upper() for r in combined if r.get("symbol")}))

    return {
        "ok": True,
        "status": "ok",
        "time_range": time_range,
        "summary": summary,
        "symbols": unique_symbols,
        "trades": limited,
    }


@router.get("/api/daily_report")
async def daily_report(date: str = None, sync: bool = True, force: bool = False):
    """每日交易报告: 统计+明细+AI总结"""
    sync_result = None
    if sync:
        sync_result = await get_trader().sync_trade_journal(date, force=force)
    rpt = journal.daily_report(date)
    rpt["ai_summary"] = journal.ai_summary(date)
    rpt["sync"] = sync_result
    return rpt


@router.post("/api/sync_trades")
async def sync_trades(data: dict = None):
    data = data or {}
    return await get_trader().sync_trade_journal(
        data.get("date"), force=bool(data.get("force", True))
    )


@router.get("/api/export_trades")
async def export_trades(date: str = None):
    """导出当日交易记录为CSV下载"""
    await get_trader().sync_trade_journal(date)
    csv_content = journal.export_csv(date)
    date_str = date or dt.date.today().strftime("%Y-%m-%d")
    return Response(
        content="\ufeff" + csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=trades_{date_str}.csv"},
    )


@router.get("/api/export_trades_html")
async def export_trades_html(date: str = None):
    """导出当日交易记录为HTML图表(每笔收益 + K线买卖点)，同时自动归档至 Obsidian 知识库"""
    html = await get_trader().export_html_report(date)
    date_str = date or dt.date.today().strftime("%Y-%m-%d")
    try:
        obsidian_bridge.save_html_report(date_str, html)
    except Exception as e:
        logger.warning(f"Failed to auto save HTML report to Obsidian: {e}")
    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": f"inline; filename=trades_{date_str}.html"},
    )


@router.get("/api/export_trades_md")
async def export_trades_md(date: str = None):
    """导出每日总结为Markdown(可导入知识库)，同时自动归档至 Obsidian 知识库"""
    md = await get_trader().export_md_report(date)
    date_str = date or dt.date.today().strftime("%Y-%m-%d")
    try:
        obsidian_bridge.save_md_report(date_str, md)
    except Exception as e:
        logger.warning(f"Failed to auto save MD report to Obsidian: {e}")
    return Response(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=summary_{date_str}.md"},
    )


@router.post("/api/close")
async def close_position(data: dict):
    """平仓 {symbol}"""
    return await get_trader().close_position(data["symbol"])


@router.post("/api/auto_trade")
async def toggle_auto(data: dict):
    """开关自动交易 {enabled: bool}"""
    t = get_trader()
    t.auto_trade = data.get("enabled", not t.auto_trade)
    return {"auto_trade": t.auto_trade}


@router.post("/api/mode/switch")
async def switch_trading_mode(data: dict):
    """切换交易分级模式: READONLY / SHADOW / PAPER / MICRO_LIVE / LIVE"""
    mode = str(data.get("mode", "")).upper()
    return get_trader().set_trading_mode(mode)
