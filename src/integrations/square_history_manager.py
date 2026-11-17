"""Square Post History & Social Media Analytics Manager.

负责存储币安广场已发布作品记录，提供自媒体每日运营复盘数据统计与币种轮换冷却分析。
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
HISTORY_FILE = DATA_DIR / "square_posts_history.json"


def _read_history() -> list[dict[str, Any]]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not HISTORY_FILE.is_file():
        # 尝试从 square_auto_publish.json 导入初始记录
        auto_state_file = DATA_DIR / "square_auto_publish.json"
        if auto_state_file.is_file():
            try:
                state_data = json.loads(auto_state_file.read_text(encoding="utf-8"))
                succ = state_data.get("last_success")
                if succ and succ.get("id"):
                    init_item = [{
                        "id": str(succ.get("id")),
                        "published_at": state_data.get("last_success_at") or datetime.now().isoformat(timespec="seconds"),
                        "date": (state_data.get("last_success_at") or datetime.now().isoformat())[:10],
                        "symbol": str(succ.get("symbol") or state_data.get("last_symbol") or "TAKEUSDT").upper(),
                        "sentiment": str(succ.get("sentiment") or "BULLISH").upper(),
                        "post_type": "spot_analysis",
                        "title": succ.get("title") or "短线异动与量化分析",
                        "summary": "【看涨 · 做多 BULLISH】$TAKE 实盘量价共振与支撑防守",
                        "link": succ.get("link") or "",
                        "cover_type": state_data.get("last_cover_type") or "ai",
                        "images_count": int(succ.get("images_count") or 2),
                        "publish_mode": succ.get("publish_mode") or "post",
                    }]
                    _write_history(init_item)
                    return init_item
            except Exception:
                pass
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_history(posts: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".sq-hist-", suffix=".tmp", dir=DATA_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(posts, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, HISTORY_FILE)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def record_published_post(post_info: dict[str, Any]) -> dict[str, Any]:
    """记录一篇新发布的广场作品到自媒体作品库。"""
    now = datetime.now()
    item = {
        "id": str(post_info.get("id") or ""),
        "published_at": post_info.get("published_at") or now.isoformat(timespec="seconds"),
        "date": post_info.get("date") or now.strftime("%Y-%m-%d"),
        "symbol": str(post_info.get("symbol") or "BTCUSDT").upper(),
        "sentiment": str(post_info.get("sentiment") or "BULLISH").upper(),
        "post_type": str(post_info.get("post_type") or "spot_analysis"),
        "title": str(post_info.get("title") or ""),
        "summary": str(post_info.get("summary") or "")[:150],
        "link": str(post_info.get("link") or ""),
        "cover_type": str(post_info.get("cover_type") or "canvas"),
        "images_count": int(post_info.get("images_count", 0)),
        "publish_mode": str(post_info.get("publish_mode") or "post"),
    }
    history = _read_history()
    # 避免相同 id 重复记录
    if item["id"]:
        history = [p for p in history if str(p.get("id")) != item["id"]]
    history.insert(0, item)
    # 保留最近 500 篇作品记录
    if len(history) > 500:
        history = history[:500]
    _write_history(history)
    return item


def get_published_posts(limit: int = 50) -> list[dict[str, Any]]:
    """获取最近已发布的广场作品流水。"""
    history = _read_history()
    return history[:limit]


def get_daily_analytics() -> dict[str, Any]:
    """汇总自媒体每日运营与作品表现复盘数据。"""
    history = _read_history()
    today_str = datetime.now().strftime("%Y-%m-%d")

    today_posts = [p for p in history if p.get("date") == today_str]
    total_count = len(history)
    today_count = len(today_posts)

    # 币种分布统计（全部与今日）
    symbol_dist: dict[str, int] = {}
    today_symbol_dist: dict[str, int] = {}
    for p in history:
        sym = p.get("symbol") or "UNKNOWN"
        symbol_dist[sym] = symbol_dist.get(sym, 0) + 1
    for p in today_posts:
        sym = p.get("symbol") or "UNKNOWN"
        today_symbol_dist[sym] = today_symbol_dist.get(sym, 0) + 1

    # 情绪分布（看多 vs 看空）
    bullish_cnt = sum(1 for p in history if p.get("sentiment") == "BULLISH")
    bearish_cnt = sum(1 for p in history if p.get("sentiment") == "BEARISH")

    # 最近已发布的币种（用于轮换冷却）
    recent_symbols = []
    seen = set()
    for p in history:
        sym = p.get("symbol")
        if sym and sym not in seen:
            recent_symbols.append(sym)
            seen.add(sym)
            if len(recent_symbols) >= 8:
                break

    # 今日是否已发布“每日大盘复盘作品”
    has_daily_review_today = any(
        p.get("post_type") == "daily_review" or "每日复盘" in p.get("title", "")
        for p in today_posts
    )

    # 最近 7 天的每日发帖篇数
    daily_trend: dict[str, int] = {}
    for p in history[:100]:
        d = p.get("date")
        if d:
            daily_trend[d] = daily_trend.get(d, 0) + 1

    return {
        "today_str": today_str,
        "today_posts_count": today_count,
        "total_posts_count": total_count,
        "recent_symbols": recent_symbols,
        "symbol_distribution": symbol_dist,
        "today_symbol_distribution": today_symbol_dist,
        "bullish_count": bullish_cnt,
        "bearish_count": bearish_cnt,
        "has_daily_review_today": has_daily_review_today,
        "daily_trend": daily_trend,
        "latest_posts": history[:15],
    }
