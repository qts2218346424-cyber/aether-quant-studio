"""Binance Square publishing, AI blog studio, meme gallery, and creator promotion routes."""

from __future__ import annotations

import asyncio
import base64
import io
import re
import time
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from PIL import Image

import binance_square_publisher
import square_history_manager
from blog_ai_writer import generate_ai_blog
from blog_auto_publish import (
    _enrich_with_realtime_price,
    render_kline_data_url,
    sanitize_and_verify_prices,
)
from config import load_config, save_config
from obsidian_bridge import obsidian_bridge
from openai_image_client import openai_image_client
from src.api.context import get_trader, square_auto_publisher
from telegram_meme_fetcher import fetch_memes_from_telegram, get_random_meme, get_recent_memes

router = APIRouter(tags=["square"])


@router.get("/api/square/status")
async def get_square_status():
    """Binance Square 发布依赖状态；绝不返回密钥内容。"""
    return binance_square_publisher.square_status()


@router.post("/api/square/publish")
async def publish_square_blog(data: dict):
    """发布当前博客草稿到 Binance Square，绝不修改持仓。"""
    try:
        result = await binance_square_publisher.publish_blog(
            title=data.get("title", ""),
            body=data.get("body", ""),
            tags=data.get("tags", ""),
            cover_data_url=data.get("cover_data_url", ""),
            sentiment=data.get("sentiment", ""),
            images=data.get("images", []),
            symbol=data.get("symbol", ""),
        )
        try:
            obsidian_bridge.sync_published_square_post({
                "title": data.get("title", ""),
                "body": data.get("body", ""),
                "tags": data.get("tags", ""),
                "symbol": data.get("symbol", "") or result.get("symbol", ""),
                "sentiment": data.get("sentiment", "") or result.get("sentiment", "BULLISH"),
                "post_type": data.get("post_type", "spot_analysis"),
                "square_id": result.get("id"),
                "square_link": result.get("link"),
                "cover_data_url": data.get("cover_data_url", ""),
                "images": data.get("images", []),
                "publish_mode": "post" if not data.get("title") else "article",
            })
        except Exception:
            pass

        try:
            square_history_manager.record_published_post({
                "id": result.get("id"),
                "symbol": data.get("symbol", "") or result.get("symbol", ""),
                "sentiment": data.get("sentiment", "") or result.get("sentiment", "BULLISH"),
                "post_type": data.get("post_type", "spot_analysis"),
                "title": data.get("title", ""),
                "summary": data.get("body", "")[:140],
                "link": result.get("link"),
                "cover_type": "canvas",
                "images_count": len(data.get("images", [])) + (1 if data.get("cover_data_url") else 0),
                "publish_mode": "post" if not data.get("title") else "article",
            })
        except Exception:
            pass

        return {"ok": True, **result}
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=422)
    except (RuntimeError, asyncio.TimeoutError) as exc:
        message = "发布超时，请查看服务端日志" if isinstance(exc, asyncio.TimeoutError) else str(exc)
        return JSONResponse({"ok": False, "error": message}, status_code=503)


@router.post("/api/blog/upload_image")
async def upload_blog_image(data: dict):
    """接收用户在博客工作台上传的本地图片（base64 data URL），校验并返回标准化图片数据。"""
    data_url = str(data.get("data_url", "") or "").strip()
    if not data_url or not data_url.startswith("data:image/"):
        return JSONResponse({"ok": False, "error": "无效的图片数据格式，必须为 data:image/ 开头"}, status_code=400)
    try:
        encoded = data_url.split(",", 1)[1]
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) < 64:
            return JSONResponse({"ok": False, "error": "图片数据过小"}, status_code=400)
        if len(raw) > 10 * 1024 * 1024:
            return JSONResponse({"ok": False, "error": "图片过大，单张请小于 10MB"}, status_code=400)

        width, height, fmt = 0, 0, "PNG"
        try:
            with Image.open(io.BytesIO(raw)) as im:
                width, height = im.size
                fmt = im.format or "PNG"
        except Exception:
            pass

        return {
            "ok": True,
            "data_url": data_url,
            "width": width,
            "height": height,
            "size_bytes": len(raw),
            "format": fmt,
            "filename": data.get("filename", f"upload_{int(time.time())}.png"),
            "message": "图片上传并解析成功",
        }
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"图片解析失败: {str(exc)}"}, status_code=400)


@router.post("/api/blog/ai_generate")
async def api_generate_blog(data: dict):
    """结合系统量化指标与配置的AI主笔，智能撰写高转化币安广场研报与图文。"""
    t = get_trader()
    items = data.get("items", [])
    try:
        klines_cache = getattr(t, "klines_cache", {}) if t else {}
        latest_ind = getattr(t, "latest_indicators", {}) if t else {}
        items = _enrich_with_realtime_price(items, klines_cache, latest_ind)
    except Exception:
        pass

    result = await generate_ai_blog(
        items=items,
        positions=data.get("positions", []),
        platform=data.get("platform", "binance_square"),
        tone=data.get("tone", "analytical"),
        length=data.get("length", "standard"),
        provider_index=data.get("provider_index", "auto"),
        persona=data.get("persona", "binance_top_creator"),
        format_style=data.get("format_style", "auto"),
        custom_instruction=data.get("custom_instruction", ""),
        generate_image=bool(data.get("generate_image", False)),
        include_red_packet=bool(data.get("include_red_packet", False)),
    )

    if result.get("ok") and result.get("data"):
        try:
            target_item = items[0] if items else {}
            result["data"] = sanitize_and_verify_prices(result["data"], target_item)
            body = result["data"].get("body", "")
            body = re.sub(r"(?m)^#{1,6}\s+", "", body)
            body = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"【\1】", body)
            body = re.sub(r"【\s*】", "", body)
            body = re.sub(r"\n{3,}", "\n\n", body).strip()
            result["data"]["body"] = body
        except Exception:
            pass

    return result


@router.post("/api/blog/generate_image")
@router.post("/api/openai/generate_image")
async def api_generate_blog_image(data: dict):
    """OpenAI DALL-E / 兼容模型图片生成接口"""
    return await openai_image_client.generate_image(
        prompt=data.get("prompt", ""),
        symbol=data.get("symbol", ""),
        model=data.get("model"),
        size=data.get("size"),
        quality=data.get("quality"),
        api_key=data.get("api_key"),
        base_url=data.get("base_url"),
        simulate=bool(data.get("simulate", False)),
    )


@router.get("/api/blog/image_config")
async def api_get_image_config():
    return {"ok": True, "config": openai_image_client.get_config()}


@router.post("/api/blog/image_config")
async def api_save_image_config(data: dict):
    return {"ok": True, "config": openai_image_client.update_config(data)}


@router.get("/api/blog/promotion")
async def get_blog_promotion_api():
    cfg = load_config()
    promo = cfg.get("creator_promotion") or {}
    return {
        "ok": True,
        "promotion": {
            "enabled": bool(promo.get("enabled", True)),
            "referral_code": str(promo.get("referral_code", "")),
            "referral_url": str(promo.get("referral_url", "")),
            "copy_trading_url": str(promo.get("copy_trading_url", "")),
            "fee_discount_pct": int(promo.get("fee_discount_pct", 20)),
            "custom_hook": str(promo.get("custom_hook", "注册即享最高 20% 手续费永久返还，主页同步实盘量化信号")),
        },
    }


@router.post("/api/blog/promotion")
async def update_blog_promotion_api(data: dict):
    cfg = load_config()
    promo = cfg.setdefault("creator_promotion", {})
    if "enabled" in data:
        promo["enabled"] = bool(data["enabled"])
    for key in ("referral_code", "referral_url", "copy_trading_url", "custom_hook"):
        if key in data:
            promo[key] = str(data[key]).strip()
    if "fee_discount_pct" in data:
        try:
            promo["fee_discount_pct"] = max(0, min(50, int(data["fee_discount_pct"])))
        except (TypeError, ValueError):
            pass
    save_config(cfg)
    return {"ok": True, "promotion": promo}


@router.get("/api/blog/candidates")
async def get_blog_candidates_api(source: str = "recommend", limit: int = 5, symbol: str = ""):
    return await get_trader().get_blog_candidates(source=source, limit=limit, symbol=symbol)


@router.get("/api/blog/kline_chart")
async def get_blog_kline_chart(symbol: str = "BTC"):
    rec = await get_trader().get_blog_candidates(symbol=symbol)
    items = rec.get("items", [])
    target = items[0] if items else {"symbol": symbol, "price": 65000.0, "side_en": "LONG"}
    return {"ok": True, "symbol": target.get("symbol", symbol), "data_url": render_kline_data_url(target)}


@router.get("/api/memes/recent")
async def get_recent_memes_api(limit: int = 15):
    memes = get_recent_memes(limit=limit, auto_fetch=True)
    return {"ok": True, "memes": memes, "count": len(memes)}


@router.get("/api/memes/random")
async def get_random_meme_api(channel: str = "woshadiao"):
    return {"ok": True, "meme": get_random_meme(channel=channel)}


@router.post("/api/memes/fetch")
async def fetch_memes_api(data: dict = None):
    data = data or {}
    items = fetch_memes_from_telegram(channel=data.get("channel", "woshadiao"), limit=int(data.get("limit", 15)))
    return {"ok": True, "new_items": items, "count": len(items)}


@router.get("/api/square/auto/status")
async def get_square_auto_status():
    return square_auto_publisher.status(load_config())


@router.post("/api/square/auto")
async def update_square_auto(data: dict):
    cfg = load_config()
    section = cfg.setdefault("square_auto_publish", {})
    if "enabled" in data:
        section["enabled"] = bool(data["enabled"])
    if "interval_sec" in data:
        section["interval_sec"] = max(300, int(data["interval_sec"]))
    if "publish_mode" in data:
        section["publish_mode"] = str(data["publish_mode"])
    if "publish_on_start" in data:
        section["publish_on_start"] = bool(data["publish_on_start"])
    save_config(cfg)
    run_now = bool(data.get("run_now", False))
    if section.get("enabled"):
        await square_auto_publisher.start(run_immediately=run_now)
    else:
        await square_auto_publisher.stop()
    return {"ok": True, **square_auto_publisher.status(cfg)}


@router.post("/api/square/auto/run_now")
async def trigger_square_auto_run_now():
    try:
        result = await square_auto_publisher.run_once()
        return {"ok": True, "result": result, **square_auto_publisher.status(load_config())}
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.get("/api/square/posts/history")
async def get_square_posts_history(limit: int = 50):
    try:
        posts = square_history_manager.get_published_posts(limit=limit)
        return {"ok": True, "posts": posts, "count": len(posts)}
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.get("/api/square/analytics/daily")
async def get_square_daily_analytics():
    try:
        analytics = square_history_manager.get_daily_analytics()
        analytics["publisher_status"] = square_auto_publisher.status(load_config())
        return {"ok": True, **analytics}
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.post("/api/square/daily_review/generate")
async def generate_square_daily_review(data: dict | None = None):
    try:
        data = data or {}
        return await square_auto_publisher.generate_daily_review(publish_now=bool(data.get("publish_now", False)))
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
