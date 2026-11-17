"""Server-side bridge for publishing the current blog draft to Binance Square."""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import base64
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "binance_square" / "post-image.mjs"
KEY_FILE = Path.home() / ".config" / "binance-square" / "openapi-key"
_PUBLISH_LOCK = asyncio.Lock()


def _parse_publish_output(stdout: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": None,
        "link": None,
        "raw_status": "success",
        "cover_uploaded": "Cover uploaded." in stdout,
        "article_submitted": "Article submitted." in stdout,
    }
    for line in stdout.splitlines():
        match = re.match(r"^\s*ID:\s*(.+?)\s*$", line)
        if match:
            result["id"] = None if match.group(1) == "unavailable" else match.group(1)
        match = re.match(r"^\s*Link:\s*(.+?)\s*$", line)
        if match:
            result["link"] = None if match.group(1) == "unavailable" else match.group(1)
    if result["id"] is None and result["link"] is None:
        result["raw_status"] = "success_without_post_id"
    return result


def square_status() -> dict[str, Any]:
    key = os.getenv("BINANCE_SQUARE_OPENAPI_KEY", "").strip()
    return {
        "configured": bool(key or (KEY_FILE.is_file() and KEY_FILE.read_text(encoding="utf-8").strip())),
        "node_available": bool(shutil.which("node")),
        "script_available": SCRIPT.is_file(),
    }


def _limit_hashtags(body: str, tags: str, max_total: int = 5) -> str:
    """严格限制全文中的 Hashtag 数量不超过 max_total（币安广场上限5个）。
    自动保留前 max_total 个标签，超出的标签自动去除 # 或丢弃，防止 API 220094 错误。
    """
    # 提取 tags 字符串中的独立标签
    tag_tokens = [t.strip() for t in tags.replace(",", " ").replace("，", " ").split() if t.strip()]
    cleaned_tags: list[str] = []
    for t in tag_tokens:
        clean_t = t if t.startswith("#") else f"#{t}"
        if clean_t not in cleaned_tags:
            cleaned_tags.append(clean_t)

    # 检查正文中已存在的 hashtag (注意排除 markdown 标题如 '# ' 或 '## ')
    body_hashtags = re.findall(r'(?<!\S)#([^\s#]+)', body)

    # 可分配给末尾 tags 的配额
    remaining_quota = max(0, max_total - len(body_hashtags))
    safe_tags = cleaned_tags[:remaining_quota]

    tags_str = " ".join(safe_tags)
    if tags_str:
        return f"{body}\n\n{tags_str}"
    return body


def _limit_cashtags(text: str, max_total: int = 3) -> str:
    """严格限制全文中的 Cashtag ($币种) 数量不超过 max_total（币安广场上限3个）。
    自动保留前 max_total 个独立币种的 $Cashtag，超出的自动去除前导 $，防止 API 220095 错误。
    """
    seen_symbols: set[str] = set()
    count = 0

    def _replace_cashtag(match: re.Match) -> str:
        nonlocal count
        coin = match.group(1).upper()
        # 若是重复出现的同一个币种，算同一种币对，保留 $
        if coin in seen_symbols:
            return match.group(0)
        if count < max_total:
            seen_symbols.add(coin)
            count += 1
            return match.group(0)
        # 超出上限的币种，去除前导 $
        return coin

    # 匹配独立的 $SYMBOL（如 $BTC, $ETH, $1000PEPE，支持前导标点或中文）
    return re.sub(r'(?<![A-Za-z0-9_])\$([A-Za-z0-9_]+)', _replace_cashtag, text)


def _extract_images_from_body(body: str) -> tuple[str, list[bytes]]:
    """从正文中提取 base64 图片，将其替换为干净的图注文本，并返回提取出的图片二进制数据列表。"""
    extracted_bytes: list[bytes] = []

    def _replace_b64(match: re.Match) -> str:
        alt = match.group(1).strip()
        data_url = match.group(2).strip()
        try:
            if "," in data_url:
                b64_part = data_url.split(",", 1)[1]
                raw = base64.b64decode(b64_part, validate=False)
                if len(raw) >= 32:
                    extracted_bytes.append(raw)
        except Exception:
            pass
        return f"【{alt}】" if alt else "【走势分析图】"

    # 匹配 ![alt](data:image/...;base64,...)
    clean = re.sub(r'!\[([^\]]*)\]\((data:image\/[^)]+)\)', _replace_b64, body)
    # 匹配普通非 base64 的 Markdown 图片地址（如已导出的 URL 或路径），保留图注，去除纯链接
    clean = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'【\1】', clean)
    # 去除空图注 【】
    clean = re.sub(r'【\s*】', '', clean)
    clean = re.sub(r'\n{3,}', '\n\n', clean).strip()
    return clean, extracted_bytes


async def publish_blog(
    title: str = "",
    body: str = "",
    tags: str = "",
    cover_data_url: str = "",
    sentiment: str = "",
    images: list[str] | None = None,
    symbol: str = "",
) -> dict[str, Any]:
    title = str(title or "").strip()
    body = str(body or "").strip()
    tags = str(tags or "").strip()
    sentiment = str(sentiment or "").strip().upper()
    symbol = str(symbol or "").strip().upper()
    if not body:
        raise ValueError("正文不能为空")
    
    # 标题存在时为长文模式，必须有封面或至少一张图片
    has_cover = bool(cover_data_url and cover_data_url.startswith("data:image/"))
    if title and not has_cover and not images:
        # 若有标题但未传封面，检查正文是否内嵌图片
        pass
    elif not title and not has_cover and not images:
        raise ValueError("封面或正文附图不能为空")
    elif title and not has_cover and not (images and len(images) > 0):
        # 兼容性检查：若没有封面且没有图片，抛出封面不能为空异常保持向后兼容
        raise ValueError("封面 PNG 数据不能为空")

    env_key = os.getenv("BINANCE_SQUARE_OPENAPI_KEY", "").strip()
    file_key = KEY_FILE.read_text(encoding="utf-8").strip() if KEY_FILE.is_file() else ""
    if not env_key and not file_key:
        raise RuntimeError("未配置 Binance Square OpenAPI 密钥")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("未找到 Node.js 运行时")
    if not SCRIPT.is_file():
        raise RuntimeError(f"发布脚本不存在: {SCRIPT}")

    # 1. 从正文中提取所有内嵌 base64 图片，并替换为整洁图注
    clean_body, inline_img_bytes = _extract_images_from_body(body)

    # 2. 严格限制标签数量 <= 5 (API 220094)，币种代币标签 <= 3 (API 220095)
    text = _limit_hashtags(clean_body, tags, max_total=5)
    text = _limit_cashtags(text, max_total=3)

    # 若未显式传入 symbol，尝试从正文 $SYMBOL 或 tags 提取
    if not symbol:
        sym_match = re.search(r'\$([A-Za-z0-9]+)', text)
        if sym_match:
            symbol = sym_match.group(1).upper()

    env = os.environ.copy()
    env["NODE_OPTIONS"] = (env.get("NODE_OPTIONS", "") + " --use-env-proxy").strip()

    cover_bytes = None
    if has_cover:
        try:
            encoded = cover_data_url.split(",", 1)[1]
            cover_bytes = base64.b64decode(encoded, validate=True)
        except (IndexError, ValueError, base64.binascii.Error) as exc:
            raise ValueError("封面 PNG 数据格式无效") from exc
        if len(cover_bytes) < 64:
            raise ValueError("封面 PNG 数据过小")

    # 收集需要上传的所有额外图片（最多 4 张）
    extra_images_bytes: list[bytes] = list(inline_img_bytes)
    if images:
        for img_item in images:
            if isinstance(img_item, str) and img_item.startswith("data:image/"):
                try:
                    b_part = img_item.split(",", 1)[1]
                    raw = base64.b64decode(b_part, validate=False)
                    if len(raw) >= 64:
                        extra_images_bytes.append(raw)
                except Exception:
                    pass
            elif isinstance(img_item, str) and os.path.isfile(img_item):
                try:
                    extra_images_bytes.append(Path(img_item).read_bytes())
                except Exception:
                    pass

    with tempfile.TemporaryDirectory(prefix="square-publish-") as temp_dir:
        temp_dir_path = Path(temp_dir)
        cmd = [node, str(SCRIPT), "--text", text]
        if title:
            cmd.extend(["--title", title])

        if cover_bytes:
            cover_path = temp_dir_path / "blog-cover.png"
            cover_path.write_bytes(cover_bytes)
            cmd.extend(["--cover", str(cover_path)])
        elif extra_images_bytes and title:
            # 若长文未显式传封面，用第一张附图作为封面
            cover_path = temp_dir_path / "blog-cover.png"
            cover_path.write_bytes(extra_images_bytes.pop(0))
            cmd.extend(["--cover", str(cover_path)])

        image_paths: list[str] = []
        for idx, img_b in enumerate(extra_images_bytes[:4], 1):
            p = temp_dir_path / f"extra-image-{idx}.png"
            p.write_bytes(img_b)
            image_paths.append(str(p))

        if image_paths:
            cmd.extend(["--images", ",".join(image_paths)])

        if sentiment:
            cmd.extend(["--sentiment", sentiment])

        if symbol:
            cmd.extend(["--symbol", symbol])

        async with _PUBLISH_LOCK:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(SCRIPT.parent),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=120
            )

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    if process.returncode != 0:
        detail = stderr.strip() or stdout.strip() or f"exit={process.returncode}"
        raise RuntimeError(detail[:1200])
    result = _parse_publish_output(stdout)
    result["title"] = title
    result["content_type"] = "article_with_cover" if title else "post_with_images"
    result["images_count"] = len(image_paths) + (1 if cover_bytes else 0)
    if sentiment:
        result["sentiment"] = sentiment
    if symbol:
        result["symbol"] = symbol
    return result


async def post_comment(post_id: str, text: str) -> dict[str, Any]:
    """在币安广场指定帖子下发表评论（用于止盈/止损触达时自动追踪回复）。
    
    如果评论 API 未对当前账号开放，会优雅降级并返回 ok=False 而不抛出异常。
    """
    post_id = str(post_id or "").strip()
    text = str(text or "").strip()
    if not post_id or not text:
        return {"ok": False, "error": "post_id 和 text 不能为空"}

    node = shutil.which("node")
    if not node:
        return {"ok": False, "error": "未找到 Node.js 运行时"}
    
    comment_script = ROOT / "tools" / "binance_square" / "post-comment.mjs"
    if not comment_script.is_file():
        return {"ok": False, "error": f"评论脚本不存在: {comment_script}"}

    env = os.environ.copy()
    env["NODE_OPTIONS"] = (env.get("NODE_OPTIONS", "") + " --use-env-proxy").strip()

    try:
        process = await asyncio.create_subprocess_exec(
            node, str(comment_script),
            "--post-id", post_id,
            "--text", text,
            cwd=str(comment_script.parent),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(), timeout=30
        )
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        
        if process.returncode != 0:
            detail = stderr.strip() or stdout.strip() or f"exit={process.returncode}"
            return {"ok": False, "error": detail[:500]}
        
        comment_id = None
        for line in stdout.splitlines():
            m = re.match(r"Comment ID:\s*(.+)", line)
            if m:
                val = m.group(1).strip()
                comment_id = None if val == "unavailable" else val
        
        return {"ok": True, "comment_id": comment_id, "post_id": post_id}
    except asyncio.TimeoutError:
        return {"ok": False, "error": "评论请求超时 (30s)"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:500]}
