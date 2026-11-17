"""OpenAI Image Generation Client for Blog & Social Media.

Provides seamless integration with OpenAI's DALL-E 3 / DALL-E 2 Image Generation APIs,
enabling AI models and trading workflows to generate high-converting 16:9 covers
and in-article visual illustrations for Binance Square and social platforms.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp
from config import load_config


class OpenAIImageClient:
    """Client for generating blog images and 16:9 covers via OpenAI DALL-E API."""

    def __init__(self, config_or_path: Optional[Any] = None) -> None:
        self.config_or_path = config_or_path
        self._output_dir = Path(__file__).resolve().parents[2] / "data" / "generated_images"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def get_config(self) -> Dict[str, Any]:
        """Load image generation configuration from config.json and environment."""
        cfg = load_config() if self.config_or_path is None else self.config_or_path
        if isinstance(cfg, str) or isinstance(cfg, Path):
            with open(cfg, "r", encoding="utf-8") as f:
                cfg = json.load(f)

        img_cfg = dict(cfg.get("ai_committee", {}).get("image_generation", {}) or {})
        
        # If not explicitly configured, fallback to OpenAI provider in ai_committee
        providers = cfg.get("ai_committee", {}).get("providers", [])
        openai_p = next(
            (p for p in providers if "openai" in str(p.get("name", "")).lower() or "gpt" in str(p.get("model", "")).lower()),
            None,
        )

        api_key = (
            img_cfg.get("api_key")
            or os.getenv("OPENAI_IMAGE_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or (openai_p.get("api_key") if openai_p else "")
        )
        base_url = (
            img_cfg.get("base_url")
            or os.getenv("OPENAI_IMAGE_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or (openai_p.get("base_url") if openai_p else "https://api.openai.com/v1")
        )
        model = img_cfg.get("model") or "gpt-image-2"
        size = img_cfg.get("size") or "1792x1024"
        quality = img_cfg.get("quality") or "standard"
        enabled = img_cfg.get("enabled", True)

        return {
            "enabled": enabled,
            "model": model,
            "size": size,
            "quality": quality,
            "base_url": str(base_url).rstrip("/"),
            "has_api_key": bool(api_key),
            "_api_key": str(api_key or "").strip(),
            "proxy": cfg.get("proxy", ""),
        }

    def update_config(self, new_cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Update image generation configuration in config.json."""
        config_path = Path("config.json")
        data: Dict[str, Any] = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

        if "ai_committee" not in data:
            data["ai_committee"] = {}

        current_img = data["ai_committee"].get("image_generation", {})
        for k in ("enabled", "model", "size", "quality", "base_url", "api_key"):
            if k in new_cfg:
                current_img[k] = new_cfg[k]

        data["ai_committee"]["image_generation"] = current_img

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return self.get_config()

    def _normalize_endpoint(self, base_url: str) -> str:
        """Construct standard /images/generations endpoint from base_url."""
        url = base_url.rstrip("/")
        if url.endswith("/chat/completions"):
            url = url[:-17]
        if not url.endswith("/images/generations"):
            if url.endswith("/v1"):
                url = f"{url}/images/generations"
            elif "/v1" not in url and not url.endswith("/codex"):
                url = f"{url}/v1/images/generations"
            else:
                url = f"{url}/images/generations"
        return url

    def build_default_prompt(self, symbol: Optional[str] = None, theme: str = "quant_trading") -> str:
        """Build an optimized visual prompt for cryptocurrency market articles."""
        sym = (symbol or "CRYPTO").upper().replace("USDT", "")
        return (
            f"A high-tech cinematic 16:9 dark-mode cryptocurrency trading desk visual for ${sym}. "
            "Features futuristic holographic neon candlestick chart, glowing green and cyan momentum vectors, "
            "depth of field, subtle cyber-quant aesthetic, professional trading terminal interface, "
            "ultra-clean composition, 8k resolution, photorealistic studio lighting."
        )

    async def generate_image(
        self,
        prompt: Optional[str] = None,
        symbol: Optional[str] = None,
        model: Optional[str] = None,
        size: Optional[str] = None,
        quality: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        proxy: Optional[str] = None,
        timeout_seconds: float = 60.0,
        simulate: bool = False,
    ) -> Dict[str, Any]:
        """Generate an image using OpenAI DALL-E or compatible image generation API.
        
        Returns:
            Dict containing:
                - ok (bool): True if generation succeeded
                - data_url (str): Base64 data URL ('data:image/png;base64,...')
                - revised_prompt (str): OpenAI revised prompt if provided
                - model (str): Model name used
                - size (str): Resolution size
                - latency_ms (int): Request latency in milliseconds
                - local_path (str): Saved local PNG path
                - error (str): Error message if failed
        """
        cfg = self.get_config()
        effective_key = api_key or cfg["_api_key"]
        effective_base = base_url or cfg["base_url"]
        effective_model = model or cfg["model"]
        effective_size = size or cfg["size"]
        effective_quality = quality or cfg["quality"]
        effective_proxy = proxy if proxy is not None else cfg.get("proxy")

        # Fallback to square size for dall-e-2
        if "dall-e-2" in effective_model.lower() and effective_size not in ("256x256", "512x512", "1024x1024"):
            effective_size = "1024x1024"

        final_prompt = (prompt or "").strip()
        if not final_prompt:
            final_prompt = self.build_default_prompt(symbol)

        # Simulation mode for testing / mock runs
        if simulate:
            # 1x1 transparent PNG or simple test block
            dummy_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            return {
                "ok": True,
                "data_url": f"data:image/png;base64,{dummy_png}",
                "revised_prompt": final_prompt,
                "model": effective_model,
                "size": effective_size,
                "latency_ms": 10,
                "prompt": final_prompt,
                "simulated": True,
            }

        if not effective_key:
            return {
                "ok": False,
                "error": "未配置 OpenAI API Key。请在系统设置中配置 OpenAI Key 或设置环境变量 OPENAI_API_KEY。",
                "prompt": final_prompt,
            }

        endpoint_url = self._normalize_endpoint(effective_base)
        headers = {
            "Authorization": f"Bearer {effective_key}",
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
        }

        payload: Dict[str, Any] = {
            "model": effective_model,
            "prompt": final_prompt,
            "n": 1,
            "size": effective_size,
            "response_format": "b64_json",
        }
        if "dall-e-3" in effective_model.lower():
            payload["quality"] = effective_quality

        started = time.perf_counter()
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)

        async with aiohttp.ClientSession() as session:
            try:
                post_kwargs: Dict[str, Any] = {
                    "headers": headers,
                    "json": payload,
                    "timeout": timeout,
                }
                if effective_proxy:
                    post_kwargs["proxy"] = effective_proxy

                async with session.post(endpoint_url, **post_kwargs) as resp:
                    status = resp.status
                    body_text = await resp.text()
                    latency_ms = round((time.perf_counter() - started) * 1000)

                    if status >= 400:
                        # If failed because response_format=b64_json was rejected, retry with url
                        if "response_format" in body_text:
                            payload.pop("response_format", None)
                            async with session.post(endpoint_url, headers=headers, json=payload, timeout=timeout) as retry_resp:
                                status = retry_resp.status
                                body_text = await retry_resp.text()

                        if status >= 400:
                            body_lower = body_text.lower()
                            if "<html" in body_lower or "<!doctype" in body_lower:
                                err_msg = f"接口返回网页(HTML)而非API (HTTP {status})：请检查接口地址是否缺少 /v1 (请求地址: {endpoint_url})"
                            else:
                                try:
                                    ej = json.loads(body_text)
                                    em = ej.get("error", {})
                                    if isinstance(em, dict):
                                        msg = em.get("message") or ""
                                        code = em.get("code") or ""
                                        msg_lower = msg.lower()
                                        if (
                                            "无可用渠道" in msg
                                            or "distributor" in msg_lower
                                            or code == "model_not_found"
                                            or "requires an image model" in msg_lower
                                            or "no available compatible accounts" in msg_lower
                                            or "no available channels" in msg_lower
                                            or "no available" in msg_lower
                                            or status == 503
                                        ):
                                            err_msg = (
                                                f"中转站绘图上游暂无可用账号/渠道 (HTTP {status}): "
                                                f"当前中转站后台【{effective_model}】模型上游逆向/绘图账号池暂时离线或配额耗尽（返回: {msg or 'No available compatible accounts'}）。"
                                                f"系统已自动为您无缝回退至本地 16:9 高清量化科技盘面封面生成！"
                                            )
                                        else:
                                            err_msg = f"OpenAI 接口错误 (HTTP {status}): {msg or body_text[:200]}"
                                    else:
                                        err_msg = f"OpenAI 接口 HTTP {status}: {body_text[:250]}"
                                except Exception:
                                    err_msg = f"OpenAI 接口 HTTP {status}: {body_text[:250]}"
                            return {
                                "ok": False,
                                "error": err_msg,
                                "latency_ms": latency_ms,
                                "prompt": final_prompt,
                            }

                    try:
                        res_json = json.loads(body_text)
                    except Exception:
                        body_lower = body_text.lower()
                        if "<html" in body_lower or "<!doctype" in body_lower:
                            err_msg = f"接口返回网页(HTML)而非API：缺少 /v1 路径 (请求地址: {endpoint_url})"
                        else:
                            err_msg = f"OpenAI 接口返回非 JSON 数据: {body_text[:200]}"
                        return {
                            "ok": False,
                            "error": err_msg,
                            "latency_ms": latency_ms,
                            "prompt": final_prompt,
                        }

                    # Check gateway error format {"code": 0, "msg": "..."}
                    if res_json.get("code") == 0 and not res_json.get("data") and res_json.get("msg"):
                        return {
                            "ok": False,
                            "error": f"网关错误: {res_json.get('msg')}",
                            "latency_ms": latency_ms,
                            "prompt": final_prompt,
                        }

                    data_list = res_json.get("data") or []
                    if not data_list or not isinstance(data_list, list):
                        return {
                            "ok": False,
                            "error": f"OpenAI 未返回有效图片数据: {body_text[:200]}",
                            "latency_ms": latency_ms,
                            "prompt": final_prompt,
                        }

                    first_item = data_list[0]
                    revised_prompt = first_item.get("revised_prompt") or final_prompt
                    data_url = ""

                    if "b64_json" in first_item:
                        b64_data = first_item["b64_json"]
                        data_url = f"data:image/png;base64,{b64_data}"
                    elif "url" in first_item:
                        img_url = first_item["url"]
                        # Fetch image and convert to data_url
                        try:
                            async with session.get(img_url, timeout=aiohttp.ClientTimeout(total=25.0)) as img_resp:
                                if img_resp.status == 200:
                                    img_bytes = await img_resp.read()
                                    b64_str = base64.b64encode(img_bytes).decode("ascii")
                                    data_url = f"data:image/png;base64,{b64_str}"
                                else:
                                    data_url = img_url
                        except Exception:
                            data_url = img_url

                    # Save to local file if base64 data available
                    local_path_str = ""
                    if data_url.startswith("data:image/"):
                        try:
                            raw_b64 = data_url.split(",", 1)[1]
                            raw_bytes = base64.b64decode(raw_b64)
                            ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                            sym_tag = f"_{symbol}" if symbol else ""
                            fn = self._output_dir / f"blog_ai_img{sym_tag}_{ts_str}.png"
                            with open(fn, "wb") as f:
                                f.write(raw_bytes)
                            local_path_str = str(fn)
                        except Exception:
                            pass

                    return {
                        "ok": True,
                        "data_url": data_url,
                        "revised_prompt": revised_prompt,
                        "model": effective_model,
                        "size": effective_size,
                        "latency_ms": latency_ms,
                        "local_path": local_path_str,
                        "prompt": final_prompt,
                    }

            except asyncio.TimeoutError:
                return {
                    "ok": False,
                    "error": f"OpenAI 图片生成请求超时 ({timeout_seconds}s)",
                    "prompt": final_prompt,
                }
            except Exception as e:
                return {
                    "ok": False,
                    "error": f"OpenAI 图片生成异常: {str(e)}",
                    "prompt": final_prompt,
                }


# Global instance
openai_image_client = OpenAIImageClient()
