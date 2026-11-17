"""Multi-model committee used as a gate before automatic entries.

The committee is deliberately separate from the local indicator strategy. The
strategy proposes a direction; configured model providers independently review
the same snapshot and vote LONG, SHORT, or HOLD.
"""
import asyncio
import json
import os
import re
import time
from typing import Any

import aiohttp


class AICommittee:
    def __init__(self, cfg: dict):
        self.cfg = cfg or {}
        self.enabled = bool(self.cfg.get("enabled", False))
        self.min_votes = int(self.cfg.get("min_votes", 2))
        self.min_confidence = int(self.cfg.get("min_confidence", 65))
        self.require_unanimous = bool(self.cfg.get("require_unanimous", False))
        self.timeout_seconds = float(self.cfg.get("timeout_seconds", 12))
        self.providers = self.cfg.get("providers", []) or []
        self.proxy = self.cfg.get("proxy") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")

    @staticmethod
    def _direction(value: Any) -> str:
        value = str(value or "HOLD").strip().upper()
        aliases = {"BUY": "LONG", "SELL": "SHORT", "NEUTRAL": "HOLD", "WAIT": "HOLD"}
        return aliases.get(value, value if value in {"LONG", "SHORT", "HOLD"} else "HOLD")

    @staticmethod
    def _extract_json(text: str) -> dict:
        text = (text or "").strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
        try:
            value = json.loads(text)
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.S)
            if not match:
                return {}
            try:
                value = json.loads(match.group(0))
                return value if isinstance(value, dict) else {}
            except json.JSONDecodeError:
                return {}

    def _prompt(self, provider: dict, context: dict) -> str:
        role = provider.get("role", "independent crypto futures reviewer")
        return (
            "You are one member of a quantitative trading review committee. "
            f"Your role is {role}. Review the candidate trade using only the supplied snapshot. "
            "Do not invent missing data. Vote independently and be conservative about leverage, "
            "thin liquidity, conflicting signals, and stale/incomplete candles. "
            "Return JSON only with exactly these fields: "
            '{"vote":"LONG|SHORT|HOLD","confidence":0,"reason":"short reason",'
            '"risk_flags":["..."]}. Confidence is an integer from 0 to 100. '
            "HOLD is preferred when evidence is mixed.\n\n"
            + json.dumps(context, ensure_ascii=False, separators=(",", ":"))
        )

    def _normalize_chat_endpoints(self, base_url: str) -> list[str]:
        """Generate candidate OpenAI chat completion endpoints from base_url."""
        url = (base_url or "").strip().rstrip("/")
        if not url:
            return []
        if url.endswith("/chat/completions"):
            return [url]
        if url.endswith("/v1") or url.endswith("/codex") or url.endswith("/v1beta"):
            return [f"{url}/chat/completions"]
        if "api.deepseek.com" in url:
            return [f"{url}/chat/completions", f"{url}/v1/chat/completions"]
        # For OpenAI-compatible relay gateways or custom domains, prioritize /v1
        return [f"{url}/v1/chat/completions", f"{url}/chat/completions"]

    def _clean_error_message(self, status: int, body: str, base_url: str) -> str:
        body_clean = body.strip().lower()
        if "<html" in body_clean or "<!doctype" in body_clean:
            clean_base = base_url.rstrip("/")
            sugg = f"{clean_base}/v1" if "/v1" not in clean_base else clean_base
            if status == 404:
                return f"接口返回 404 网页：请确认接口地址是否缺少 /v1 (通常应为 {sugg})"
            if status in (403, 521, 503):
                return f"接口受到 Cloudflare / 网页防火墙拦截 (HTTP {status})，请检查代理网关或域名有效性"
            return f"接口返回了网页(HTML)而非API数据 (HTTP {status})，请检查接口地址是否缺少 /v1 (建议改为 {sugg})"
        return body[:250]

    async def _call_provider(self, session: aiohttp.ClientSession, provider: dict, context: dict) -> dict:
        name = provider.get("name", provider.get("model", "provider"))
        api_key = os.getenv(provider.get("api_key_env", "")) or str(provider.get("api_key", "")).strip()
        if not api_key:
            return {"name": name, "status": "missing_key", "vote": "HOLD", "confidence": 0,
                    "reason": "provider API key environment variable is missing", "risk_flags": ["missing_key"]}

        base_url = str(provider.get("base_url", "")).rstrip("/")
        if not base_url:
            return {"name": name, "status": "invalid_config", "vote": "HOLD", "confidence": 0,
                    "reason": "provider base_url is missing", "risk_flags": ["invalid_config"]}

        endpoints = self._normalize_chat_endpoints(base_url)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
        }
        payload = {
            "model": provider.get("model"),
            "messages": [
                {"role": "system", "content": "Return strict JSON. You are a trade reviewer, not an order executor."},
                {"role": "user", "content": self._prompt(provider, context)},
            ],
            "temperature": float(provider.get("temperature", 0.1)),
            "max_tokens": int(provider.get("max_tokens", 240)),
        }
        if provider.get("json_mode", True):
            payload["response_format"] = {"type": "json_object"}

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)

        for ep_idx, target_url in enumerate(endpoints):
            try:
                post_kw = {
                    "headers": headers,
                    "json": payload,
                    "timeout": timeout,
                }
                if getattr(self, "proxy", None):
                    post_kw["proxy"] = self.proxy
                async with session.post(
                    target_url,
                    **post_kw,
                ) as response:
                    body = await response.text()
                    if response.status >= 400:
                        if response.status == 404 and ep_idx + 1 < len(endpoints):
                            continue
                        clean_msg = self._clean_error_message(response.status, body, base_url)
                        return {"name": name, "status": f"http_{response.status}", "vote": "HOLD", "confidence": 0,
                                "reason": clean_msg, "risk_flags": ["provider_error"]}
                    try:
                        data = json.loads(body)
                    except json.JSONDecodeError:
                        content_type = response.headers.get("Content-Type", "")
                        if ep_idx + 1 < len(endpoints) and ("html" in content_type.lower() or "<html" in body.lower()):
                            continue
                        clean_msg = self._clean_error_message(response.status, body, base_url)
                        return {
                            "name": name, "status": "non_json_response", "vote": "HOLD", "confidence": 0,
                            "reason": clean_msg,
                            "risk_flags": ["invalid_api_path"],
                        }
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    result = self._extract_json(content)
                    confidence = max(0, min(100, int(float(result.get("confidence", 0)))))
                    return {
                        "name": name,
                        "status": "ok",
                        "vote": self._direction(result.get("vote")),
                        "confidence": confidence,
                        "reason": str(result.get("reason", ""))[:500],
                        "risk_flags": list(result.get("risk_flags", []))[:8] if isinstance(result.get("risk_flags", []), list) else [],
                    }
            except (asyncio.TimeoutError, TimeoutError):
                if ep_idx + 1 < len(endpoints):
                    continue
                return {"name": name, "status": "timeout", "vote": "HOLD", "confidence": 0,
                        "reason": f"模型请求超过{self.timeout_seconds:g}秒", "risk_flags": ["provider_timeout"]}
            except Exception as exc:
                if ep_idx + 1 < len(endpoints):
                    continue
                return {"name": name, "status": "error", "vote": "HOLD", "confidence": 0,
                        "reason": str(exc)[:300], "risk_flags": ["provider_error"]}

    async def review(self, candidate_signal: int, context: dict) -> dict:
        candidate = "LONG" if candidate_signal > 0 else "SHORT" if candidate_signal < 0 else "HOLD"
        if not self.enabled:
            return {"approved": True, "status": "disabled", "candidate": candidate, "votes": [],
                    "reason": "AI committee disabled"}
        if not self.providers:
            return {"approved": False, "status": "no_providers", "candidate": candidate, "votes": [],
                    "reason": "AI committee has no configured providers"}

        async with aiohttp.ClientSession() as session:
            votes = await asyncio.gather(*[
                self._call_provider(session, provider, context) for provider in self.providers
            ])

        valid = [v for v in votes if v.get("status") == "ok"]
        aligned = [v for v in valid if v.get("vote") == candidate and v.get("confidence", 0) >= self.min_confidence]
        directions = {v.get("vote") for v in valid if v.get("vote") != "HOLD"}
        approved = (
            candidate in {"LONG", "SHORT"}
            and len(aligned) >= self.min_votes
            and (not self.require_unanimous or len(aligned) == len(valid))
            and (not directions or directions == {candidate})
        )
        return {
            "approved": approved,
            "status": "approved" if approved else "rejected",
            "candidate": candidate,
            "votes": votes,
            "aligned_votes": len(aligned),
            "valid_votes": len(valid),
            "reason": f"{len(aligned)}/{self.min_votes} aligned AI votes",
        }

    async def test_provider(self, provider: dict, api_key: str = "") -> dict:
        """Test one provider without placing an order or changing committee state."""
        provider = dict(provider or {})
        if api_key and "***" not in api_key:
            provider["api_key"] = api_key
        context = {
            "test_mode": True,
            "symbol": "TESTUSDT",
            "candidate": "LONG",
            "price": 100.0,
            "strategy_score": 70,
            "strategy_factors": [
                "EMA trend aligned",
                "higher timeframe aligned",
                "volume confirmation",
            ],
            "indicators": {
                "rsi": 55,
                "macd_hist": 0.12,
                "atr": 1.2,
                "htf_trend": 1,
            },
            "timeframe": "5m",
            "higher_timeframe": "15m",
            "recent_closes": [98.8, 99.1, 99.4, 99.2, 99.8, 100.0],
            "note": "Connectivity test only. Return a valid committee JSON vote.",
        }
        started = time.perf_counter()
        async with aiohttp.ClientSession() as session:
            result = await self._call_provider(session, provider, context)
        result["latency_ms"] = round((time.perf_counter() - started) * 1000)
        result["success"] = result.get("status") == "ok"
        return result
