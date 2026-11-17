"""Obsidian knowledge vault synchronization, Karpathy compiler, and habit tracking routes."""

from __future__ import annotations

import datetime as dt
import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config import load_config
from obsidian_bridge import obsidian_bridge
from src.api.context import get_trader

logger = logging.getLogger("app.obsidian")
router = APIRouter(tags=["obsidian"])


@router.get("/api/obsidian/status")
async def get_obsidian_status():
    """获取 Obsidian 知识库连接状态与概览"""
    cfg = load_config()
    obs_cfg = cfg.get("obsidian", {})
    vault_path = obsidian_bridge.get_vault_path()
    strategies = obsidian_bridge.scan_strategies() if vault_path else []
    habits = obsidian_bridge.analyze_habits(days=7)
    moc_exists = bool(vault_path and (vault_path / "00-知识库索引_MOC.md").exists())
    return {
        "ok": True,
        "connected": bool(vault_path and vault_path.exists()),
        "vault_path": str(vault_path) if vault_path else None,
        "configured_path": obs_cfg.get("vault_path"),
        "auto_sync": obs_cfg.get("auto_sync", True),
        "strategy_count": len(strategies),
        "moc_exists": moc_exists,
        "habit_score": habits.get("overall_score", 85),
        "habit_stage": habits.get("stage", "待评估"),
        "ts": datetime.now().isoformat(timespec="seconds"),
    }


@router.post("/api/obsidian/config")
async def set_obsidian_config(data: dict):
    """设置或修改 Obsidian Vault 路径与自动同步开关"""
    vault_path = data.get("vault_path", "").strip()
    auto_sync = data.get("auto_sync", True)
    if not vault_path:
        return JSONResponse({"ok": False, "error": "Vault 路径不能为空"}, status_code=422)
    return obsidian_bridge.set_vault_path(vault_path, auto_sync=auto_sync)


@router.post("/api/obsidian/init_templates")
async def init_obsidian_templates(data: dict = None):
    """在当前 Vault 初始化交易知识库架构与策略模板"""
    data = data or {}
    path_str = data.get("vault_path")
    target_path = Path(path_str).expanduser().resolve() if path_str else None
    overwrite = bool(data.get("overwrite", False))
    return obsidian_bridge.init_templates(target_path, overwrite=overwrite)


@router.post("/api/obsidian/sync_square_guidelines")
async def sync_obsidian_square_guidelines(data: dict = None):
    """将最新广场写作规范、4大人设与4大流派实战模板强制同步至 Obsidian 知识库"""
    data = data or {}
    path_str = data.get("vault_path")
    target_path = Path(path_str).expanduser().resolve() if path_str else None
    return obsidian_bridge.sync_square_guidelines(target_path)


@router.post("/api/obsidian/compile")
async def compile_obsidian_vault(data: dict = None):
    """手动触发卡帕西 (Karpathy) LLM-Wiki 自维护编译与知识地图刷新"""
    data = data or {}
    path_str = data.get("vault_path")
    target_path = Path(path_str).expanduser().resolve() if path_str else None
    return obsidian_bridge.compile_vault(target_path)


@router.get("/api/obsidian/strategies")
async def get_obsidian_strategies(force: bool = False):
    """获取知识库中所有的交易策略笔记与规则"""
    strategies = obsidian_bridge.scan_strategies(force_refresh=force)
    return {"ok": True, "count": len(strategies), "strategies": strategies}


@router.get("/api/obsidian/habits")
async def get_obsidian_habits(days: int = 7):
    """获取最近周期的量化交易习惯与行为金融学雷达分析"""
    habits = obsidian_bridge.analyze_habits(days=days)
    return {"ok": True, "habits": habits}


@router.post("/api/obsidian/sync")
async def sync_to_obsidian(data: dict = None):
    """手动或实时同步交易复盘日记与交易习惯至 Obsidian，同时生成并保存最新 HTML 图表报告"""
    data = data or {}
    date_str = data.get("date")
    try:
        html = await get_trader().export_html_report(date_str)
        obsidian_bridge.save_html_report(date_str or dt.date.today().strftime("%Y-%m-%d"), html)
    except Exception as e:
        logger.warning(f"Failed to auto generate HTML report during sync: {e}")
    return obsidian_bridge.sync_to_obsidian(date_str)


@router.post("/api/obsidian/save_blog_note")
async def save_obsidian_blog_note(data: dict = None):
    """将博客工作室生成的行情简报与 1280x720 封面大图保存至 Obsidian 知识库"""
    data = data or {}
    title = data.get("title", "").strip()
    if not title:
        return JSONResponse({"ok": False, "error": "简报标题不能为空"}, status_code=422)
    res = obsidian_bridge.save_blog_note(
        title=title,
        hook=data.get("hook", "").strip(),
        body=data.get("body", "").strip(),
        tags=data.get("tags", "").strip(),
        platform=data.get("platform", "general").strip(),
        tone=data.get("tone", "analytical").strip(),
        cover_data_url=data.get("cover_data_url", "").strip(),
        target_date=data.get("date"),
        analysis_chart_data_url=(data.get("analysis_chart_data_url") or data.get("kline_chart_data_url") or "").strip(),
    )
    if not res.get("ok"):
        return JSONResponse(res, status_code=400)
    return res


@router.get("/api/obsidian/square_blogs")
async def get_obsidian_square_blogs(force: bool = False):
    """扫描并获取 04-币安广场与个人博客 目录下的所有草稿、排期与已发布文章"""
    blogs = obsidian_bridge.scan_square_blogs(force_refresh=force)
    return {"ok": True, "count": len(blogs), "blogs": blogs}


@router.post("/api/obsidian/publish_square_note")
async def publish_obsidian_square_note(data: dict = None):
    """从 Obsidian 笔记一键发布文章与封面大图至币安广场，并自动归档更新"""
    data = data or {}
    rel_path = data.get("relative_path", "").strip()
    if not rel_path:
        return JSONResponse({"ok": False, "error": "请提供笔记相对路径 relative_path"}, status_code=422)
    res = await obsidian_bridge.publish_square_blog_from_obsidian(rel_path)
    if not res.get("ok"):
        return JSONResponse(res, status_code=400)
    return res


@router.post("/api/obsidian/capture_note")
async def capture_obsidian_note(data: dict = None):
    """一键截取图表并追加记录至 Obsidian 当日复盘笔记"""
    data = data or {}
    image_base64 = data.get("image_base64", "").strip()
    if not image_base64:
        return JSONResponse({"ok": False, "error": "快照图片数据不能为空"}, status_code=422)
    res = obsidian_bridge.append_chart_snapshot(
        symbol=data.get("symbol", "").strip(),
        interval=data.get("interval", "15m").strip(),
        note_text=data.get("note", "").strip(),
        image_base64=image_base64,
        target_date=data.get("date"),
    )
    if not res.get("ok"):
        return JSONResponse(res, status_code=400)
    return res


@router.get("/api/obsidian/match/{symbol}")
async def get_obsidian_strategy_match(symbol: str):
    """根据 Obsidian 知识库策略规则，动态评估指定币种的达成度与交易建议"""
    t = get_trader()
    sym = symbol.upper().strip()
    ind = t.latest_indicators.get(sym, {})
    price = ind.get("price")
    if not price:
        pos = t.positions_cache.get(sym)
        if pos:
            price = float(pos.get("entry_price", 0))
    return obsidian_bridge.match_strategies_for_symbol(
        symbol=sym,
        current_price=price,
        indicators=ind,
    )
