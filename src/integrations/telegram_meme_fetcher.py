"""Telegram Meme Fetcher

Fetches funny images and memes from Telegram channels (e.g. @woshadiao / -1001341930464)
via public preview and caches them locally for blog cover composition and Obsidian archiving.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import random
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import load_config

logger = logging.getLogger(__name__)

DATA_MEMES_DIR = Path(__file__).resolve().parents[2] / "data" / "memes"
INDEX_FILE = DATA_MEMES_DIR / "index.json"


def _get_proxy_url() -> Optional[str]:
    cfg = load_config()
    return cfg.get("proxy") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or "http://127.0.0.1:7897"


def _get_obsidian_meme_dir() -> Optional[Path]:
    try:
        from obsidian_bridge import obsidian_bridge
        vp = obsidian_bridge.get_vault_path()
        if vp and vp.exists():
            target = vp / "04-币安广场与个人博客" / "梗图库"
            target.mkdir(parents=True, exist_ok=True)
            return target
    except Exception:
        pass
    return None


def _read_index() -> List[Dict[str, Any]]:
    if not INDEX_FILE.is_file():
        return []
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write_index(records: List[Dict[str, Any]]) -> None:
    DATA_MEMES_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_memes_from_telegram(channel: str = "woshadiao", limit: int = 15) -> List[Dict[str, Any]]:
    """Fetch recent images from a public Telegram channel."""
    DATA_MEMES_DIR.mkdir(parents=True, exist_ok=True)
    ob_dir = _get_obsidian_meme_dir()
    proxy = _get_proxy_url()

    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    opener.addheaders = [
        ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"),
        ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8"),
    ]

    clean_channel = channel.strip().lstrip("@")
    if "-1001341930464" in clean_channel or "1341930464" in clean_channel:
        clean_channel = "woshadiao"

    url = f"https://t.me/s/{clean_channel}"
    try:
        with opener.open(url, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        logger.warning("Failed to fetch Telegram channel %s: %s", channel, exc)
        return []

    photo_urls = re.findall(r"background-image:url\('(https://[^'\s]+telesco\.pe/file/[^'\s]+)'\)", html)
    if not photo_urls:
        photo_urls = re.findall(r"background-image:url\('(https://[^'\"\s]+\.(?:jpg|jpeg|png|webp)[^'\"\s]*)'\)", html)

    existing_records = _read_index()
    existing_urls = {r.get("source_url") for r in existing_records}
    existing_ids = {r.get("id") for r in existing_records}

    new_items: List[Dict[str, Any]] = []

    for photo_url in reversed(photo_urls):
        if photo_url in existing_urls:
            continue
        url_hash = hashlib.md5(photo_url.encode("utf-8")).hexdigest()[:12]
        if url_hash in existing_ids:
            continue

        try:
            with opener.open(photo_url, timeout=12) as img_resp:
                img_bytes = img_resp.read()
            if len(img_bytes) < 4096:
                continue

            filename = f"meme_{clean_channel}_{url_hash}.jpg"
            local_path = DATA_MEMES_DIR / filename
            local_path.write_bytes(img_bytes)

            if ob_dir and ob_dir.exists():
                try:
                    (ob_dir / filename).write_bytes(img_bytes)
                except Exception:
                    pass

            item = {
                "id": url_hash,
                "filename": filename,
                "local_path": str(local_path),
                "source_url": photo_url,
                "channel": clean_channel,
                "downloaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "size_bytes": len(img_bytes),
            }
            new_items.append(item)
            existing_records.insert(0, item)
            existing_urls.add(photo_url)
            existing_ids.add(url_hash)

            if len(new_items) >= limit:
                break
        except Exception as exc:
            logger.debug("Failed downloading image %s: %s", photo_url, exc)
            continue

    if new_items:
        _write_index(existing_records[:100])

    return new_items


def get_recent_memes(limit: int = 15, auto_fetch: bool = True) -> List[Dict[str, Any]]:
    """Return recent cached memes. If fewer than 5 exist, auto fetch."""
    records = _read_index()
    valid_records = []
    for r in records:
        fpath = Path(r.get("local_path", ""))
        if fpath.is_file():
            valid_records.append(r)

    if (len(valid_records) < 5 or not valid_records) and auto_fetch:
        try:
            fetch_memes_from_telegram(channel="woshadiao", limit=15)
            records = _read_index()
            valid_records = [r for r in records if Path(r.get("local_path", "")).is_file()]
        except Exception:
            pass

    results = []
    for r in valid_records[:limit]:
        fpath = Path(r.get("local_path", ""))
        try:
            b64 = base64.b64encode(fpath.read_bytes()).decode("ascii")
            ext = fpath.suffix.lstrip(".").lower() or "jpeg"
            data_url = f"data:image/{ext};base64,{b64}"
            results.append({
                **r,
                "data_url": data_url,
            })
        except Exception:
            continue
    return results


def get_random_meme(channel: str = "woshadiao") -> Optional[Dict[str, Any]]:
    """Get a random meme from the cached pool or fetch a fresh one."""
    memes = get_recent_memes(limit=30, auto_fetch=True)
    if not memes:
        return None
    return random.choice(memes)
