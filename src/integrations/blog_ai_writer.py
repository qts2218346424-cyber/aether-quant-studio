"""AI Blog Writer for Binance Square & Social Media.

Integrates configured AI models (OpenAI, DeepSeek, Claude) from config.json
to generate professional, data-backed, high-converting market notes,
analysis breakdowns, execution levels, and covers.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

import aiohttp
from config import load_config


def _extract_json_payload(text: str) -> Dict[str, Any]:
    """Extract JSON object from text with potential markdown wrappers or partial truncation."""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    match = re.search(r"(\{[\s\S]*\})", text)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    # Regex field-by-field fallback for partially truncated JSON
    result: Dict[str, Any] = {}
    for key in ("title", "hook", "body", "prompt"):
        m = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)(?:"|$)', text, flags=re.DOTALL)
        if m:
            val = m.group(1)
            try:
                result[key] = json.loads(f'"{val}"')
            except Exception:
                result[key] = val.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")

    # Handle tags which might be a list or a string
    tags_match = re.search(r'"tags"\s*:\s*(\[[^\]]*\]|"((?:[^"\\]|\\.)*)(?:"|$))', text, flags=re.DOTALL)
    if tags_match:
        val = tags_match.group(1).strip()
        if val.startswith("["):
            try:
                parsed_list = json.loads(val)
                result["tags"] = " ".join(f"#{str(t).lstrip('#')}" for t in parsed_list)
            except Exception:
                # Regex extract elements in array
                tags_items = re.findall(r'"([^"]+)"', val)
                result["tags"] = " ".join(f"#{t.lstrip('#')}" for t in tags_items)
        else:
            try:
                result["tags"] = json.loads(val)
            except Exception:
                result["tags"] = val.strip('"')

    if result.get("title") or result.get("body"):
        return result


    return {}


def _normalize_chat_endpoints(base_url: str) -> List[str]:
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
    return [f"{url}/v1/chat/completions", f"{url}/chat/completions"]


def _clean_error_message(status: int, body: str, base_url: str) -> str:
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


async def _call_single_provider(
    provider: Dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    proxy: Optional[str] = None,
    timeout_seconds: float = 30.0,
) -> Dict[str, Any]:
    """Call an OpenAI-compatible provider with structured JSON instruction."""
    name = provider.get("name", "AI")
    model = provider.get("model", "")
    base_url = str(provider.get("base_url", "")).rstrip("/")
    api_key = os.getenv(provider.get("api_key_env", "")) or str(provider.get("api_key", "")).strip()

    if not api_key:
        return {"ok": False, "error": f"供应商 {name} 缺少 API Key"}
    if not base_url or not model:
        return {"ok": False, "error": f"供应商 {name} 缺少 base_url 或 model"}

    endpoints = _normalize_chat_endpoints(base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(provider.get("temperature", 0.3)),
        "max_tokens": int(provider.get("max_tokens", 3800)),
    }
    if provider.get("json_mode", True):
        payload["response_format"] = {"type": "json_object"}
        if "json" not in system_prompt.lower() and "json" not in user_prompt.lower():
            messages[0]["content"] = "You must output a valid json object.\n" + messages[0]["content"]

    started = time.perf_counter()
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    connector_args: Dict[str, Any] = {}
    MAX_TAGS = 5

    def _limit_tags(raw_tags, max_count: int = MAX_TAGS) -> str:
        """把 tags 字段截断到 max_count 个，防止 Binance Square 报 Hashtag 超限错误。"""
        if not raw_tags:
            return "#币安广场 #量化交易 #合约实战 #行情分析"
        if isinstance(raw_tags, list):
            raw_tags = " ".join(f"#{str(t).lstrip('#')}" for t in raw_tags)
        parts = str(raw_tags).split()
        hashtags = [p if p.startswith("#") else f"#{p}" for p in parts if p.strip()]
        return " ".join(hashtags[:max_count])

    def _clean_markdown_headers(text: str) -> str:
        """去除行首的 #、##、### 等 Markdown 标题标记，彻底解决双 ## 号影响美观的问题。"""
        if not text:
            return ""
        return re.sub(r'(?m)^#{1,6}\s+', '', text)

    connector_args: Dict[str, Any] = {}
    async with aiohttp.ClientSession(**connector_args) as session:
        for ep_idx, target_url in enumerate(endpoints):
            try:
                post_kwargs: Dict[str, Any] = {
                    "headers": headers,
                    "json": payload,
                    "timeout": timeout,
                }
                if proxy:
                    post_kwargs["proxy"] = proxy

                async with session.post(target_url, **post_kwargs) as resp:
                    status = resp.status
                    body = await resp.text()
                    latency_ms = round((time.perf_counter() - started) * 1000)

                    if status >= 400:
                        if status == 404 and ep_idx + 1 < len(endpoints):
                            continue
                        clean_err = _clean_error_message(status, body, base_url)
                        return {
                            "ok": False,
                            "error": f"{name} HTTP {status}: {clean_err}",
                            "latency_ms": latency_ms,
                        }

                    try:
                        res_json = json.loads(body)
                    except Exception:
                        if ep_idx + 1 < len(endpoints) and ("<html" in body.lower() or "<!doctype" in body.lower()):
                            continue
                        clean_err = _clean_error_message(status, body, base_url)
                        return {
                            "ok": False,
                            "error": f"{name} 返回非JSON数据: {clean_err}",
                            "latency_ms": latency_ms,
                        }

                    # Check for gateway errors disguised as 200
                    if res_json.get("code") == 0 and res_json.get("data") is None and res_json.get("msg"):
                        return {
                            "ok": False,
                            "error": f"{name} 网关提示: {res_json.get('msg')}",
                            "latency_ms": latency_ms,
                        }

                    choices = res_json.get("choices") or []
                    if not choices:
                        return {
                            "ok": False,
                            "error": f"{name} 未返回 choices: {body[:200]}",
                            "latency_ms": latency_ms,
                        }

                    content = choices[0].get("message", {}).get("content", "")
                    if not content and choices[0].get("message", {}).get("reasoning_content"):
                        pass
                    parsed = _extract_json_payload(content)
                    if not parsed and choices[0].get("message", {}).get("reasoning_content"):
                        parsed = _extract_json_payload(choices[0]["message"]["reasoning_content"])

                    if not parsed:
                        return {
                            "ok": True,
                            "raw_content": content,
                            "data": {
                                "title": f"量化盘面观察与交易策略分析 ({name})",
                                "hook": "今天盘面有些意思，多空信号都在这几个关键位上撑着，来看看我怎么理解的。",
                                "body": _clean_markdown_headers(content),
                                "tags": "#币安广场 #量化交易 #合约实战 #风险控制",
                                "prompt": f"Minimalist crypto quant terminal cover for {model}, dark theme 16:9",
                            },
                            "provider_name": name,
                            "model": model,
                            "latency_ms": latency_ms,
                        }

                    raw_tags = parsed.get("tags", "")
                    raw_body = parsed.get("body") or content
                    return {
                        "ok": True,
                        "data": {
                            "title": parsed.get("title") or "量化行情研判与实战策略简报",
                            "hook": parsed.get("hook") or "今天有几个位置值得重点盯一下，说说我的判断。",
                            "body": _clean_markdown_headers(raw_body),
                            "tags": _limit_tags(raw_tags),
                            "sentiment": str(parsed.get("sentiment") or ("BEARISH" if ("看跌" in raw_body or "做空" in raw_body) else "BULLISH")).upper(),
                            "prompt": parsed.get("prompt") or f"16:9 crypto market infographic for {name}",
                        },
                        "provider_name": name,
                        "model": model,
                        "latency_ms": latency_ms,
                    }

            except (asyncio.TimeoutError, TimeoutError):
                if ep_idx + 1 < len(endpoints):
                    continue
                return {"ok": False, "error": f"{name} 接口超时 ({timeout_seconds}s)"}
            except Exception as e:
                if ep_idx + 1 < len(endpoints):
                    continue
                return {"ok": False, "error": f"{name} 请求异常: {str(e)}"}
        return {"ok": False, "error": f"{name} 所有候选端点均请求失败"}


async def generate_ai_blog(
    items: List[Dict[str, Any]],
    positions: Optional[List[Dict[str, Any]]] = None,
    today_report: Optional[Dict[str, Any]] = None,
    platform: str = "binance_square",
    tone: str = "analytical",
    length: str = "standard",
    provider_index: Any = "auto",
    persona: str = "binance_top_creator",
    format_style: str = "auto",
    custom_instruction: str = "",
    generate_image: bool = False,
    include_red_packet: bool = False,
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate a high-converting, deeply researched market analysis note using configured AI."""
    cfg = cfg or load_config()
    providers = cfg.get("ai_committee", {}).get("providers", []) or []
    proxy = cfg.get("proxy") or None

    if not providers:
        return {
            "ok": False,
            "error": "系统未配置任何 AI 供应商，请先在「策略设置」的 AI 模型列表中配置 OpenAI 或 DeepSeek API Key。",
        }

    # Determine candidate providers with intelligent prioritization
    candidates = []
    if str(provider_index).isdigit():
        idx = int(provider_index)
        if 0 <= idx < len(providers):
            candidates = [providers[idx]]
    if not candidates:
        # Auto mode: prioritize responsive providers like DeepSeek first, demote failing gateways
        valid_providers = [
            p for p in providers
            if (p.get("api_key") or os.getenv(p.get("api_key_env", "")))
            and p.get("base_url")
            and p.get("model")
        ]
        if not valid_providers:
            valid_providers = [p for p in providers if p.get("base_url") and p.get("model")]

        # Sort: healthy direct APIs (e.g. api.deepseek.com) first, third-party relays second
        candidates = sorted(
            valid_providers,
            key=lambda p: (
                1 if "sharedchat" in str(p.get("base_url", "")).lower() else 0,
                0 if "deepseek" in str(p.get("name", "")).lower() or "deepseek" in str(p.get("base_url", "")).lower() else 1,
            )
        )

    # Load creator promotion and referral configuration
    promo = (cfg.get("creator_promotion") or {}) if isinstance(cfg, dict) else {}
    promo_enabled = bool(promo.get("enabled", True))
    ref_code = str(promo.get("referral_code", "")).strip()
    ref_url = str(promo.get("referral_url", "")).strip()
    copy_url = str(promo.get("copy_trading_url", "")).strip()
    fee_discount = promo.get("fee_discount_pct", 20)
    custom_hook = str(promo.get("custom_hook", "")).strip()

    # Format market scan items
    items_desc = []
    for i, it in enumerate((items or [])[:6]):
        sym = it.get("symbol", "UNKNOWN")
        side_val = str(it.get("side_en") or it.get("direction") or it.get("side") or "").upper()
        if "LONG" in side_val or "多" in side_val:
            side = "偏多 (LONG)"
        elif "SHORT" in side_val or "空" in side_val:
            side = "偏空 (SHORT)"
        else:
            side = "偏多 (LONG)" if it.get("score", 0) > 0 else "偏空 (SHORT)"
        score = it.get("score", 0)
        price = it.get("price", "--")
        chg = it.get("change_24h", 0)
        atr = it.get("atr_pct", 0)
        sup = it.get("support", "--")
        res = it.get("resistance", "--")
        sl = it.get("sl", "--")
        tp1 = it.get("tp1", "--")
        factors = " / ".join(str(f) for f in (it.get("factors") or [])[:3])
        factors_str = f" | 关键异动/因子: {factors}" if factors else ""
        items_desc.append(
            f"{i+1}. 标的: {sym} (🚨【币安实盘真实最新价格: {price} USDT，文中所有价格必须锚定此现价】) | 研判方向: {side} | 评分: {score} | 24H涨跌: {chg:+}% | 关键支撑位: {sup} | 关键阻力位: {res} | 建议止损防守位(SL): {sl} | 建议止盈目标(TP): {tp1}{factors_str}"
        )
    scan_summary = "\n".join(items_desc) if items_desc else "暂无活跃扫描标的"

    # Format user holdings（克制低调：仅在传入有效持仓时简略提供，否则明确不介绍持仓）
    pos_desc = []
    for p in positions or []:
        sym = p.get("symbol", "")
        side = p.get("side", p.get("positionSide", "HOLD"))
        qty = p.get("qty", p.get("positionAmt", 0))
        entry = p.get("entry_price", p.get("entryPrice", "--"))
        pnl = p.get("unrealized_pnl", p.get("unRealizedProfit", "--"))
        lev = p.get("leverage", 10)
        pos_desc.append(f"- 真实持仓参考: {sym} | 方向: {side} | 杠杆: {lev}x | 数量: {qty} | 成本均价: {entry} | 浮动盈亏: {pnl} USDT")
    positions_summary = "\n".join(pos_desc) if pos_desc else "（本文聚焦客观盘面技术分析，无需介绍作者个人持仓）"

    # Format today's realized PnL & closed trades summary
    today_pnl_desc = []
    if today_report and isinstance(today_report, dict):
        total_pnl = float(today_report.get("total_pnl", 0) or 0)
        win_rate = float(today_report.get("win_rate", 0) or 0)
        close_cnt = int(today_report.get("close_count", 0) or 0)
        wins = int(today_report.get("wins", 0) or 0)
        if close_cnt > 0:
            today_pnl_desc.append(
                f"- 今日实盘平仓交割: {close_cnt} 笔 (胜率: {win_rate:.1f}%, 盈利 {wins} 笔) | 今日已实现总净盈亏: {total_pnl:+.2f} USDT"
            )
            for c in (today_report.get("closes") or [])[-3:]:
                c_sym = c.get("symbol", "")
                c_pnl = float(c.get("pnl", 0) or 0)
                c_pct = float(c.get("pnl_pct", 0) or 0)
                c_reason = c.get("reason", "平仓")
                today_pnl_desc.append(
                    f"  * 已交割: {c_sym} | 盈亏: {c_pnl:+.2f}U ({c_pct:+.2f}%) | 触发: {c_reason}"
                )
    today_pnl_summary = "\n".join(today_pnl_desc) if today_pnl_desc else "（无需汇报交割战报）"

    # Persona definition: 多样化真人顶尖交易员画像（彻底消除AI机械味与单一模板感）
    persona_map = {
        "tactical_sniper": (
            "你是币安广场与Crypto Twitter上顶尖的SMC/价格行为学(Price Action)实战操盘手。"
            "行文风格：极其干练、冷峻清醒、直击痛点。你深谙主力庄家的操盘套路（流动性劫掠 Liquidity Sweep、假突破 Deviation、诱多诱空陷阱）。"
            "绝对不说空话套话，用最真实交易员的第一人称口吻（「说实话...」「这里我绝不会无脑追...」「我的防守底线很简单...」），拆解主力意图与高盈亏比挂单逻辑。"
        ),
        "candid_veteran": (
            "你是经历过多轮牛熊、实盘交过几百万学费的币圈老交易员（老韭菜）。"
            "行文风格：真诚坦率、接地气、像深夜在高质量私密交易群里给兄弟们掏心窝子复盘。"
            "你痛恨频繁开单和扛单，行文充满对市场的敬畏感和清醒的防守纪律，善于指出散户当前最容易犯的盲区，语言生动富有画面感。"
        ),
        "microstructure_hunter": (
            "你是专注盘口订单流与资金博弈的微观异动猎手。"
            "行文风格：敏锐抓取资金费率挤压、持仓量OI背离、大单吸筹与缩量假摔信号。"
            "用通俗易懂的实战大白话把盘口博弈解释清楚，不堆砌晦涩数学模型，直接告诉读者主力在什么位置建仓、防守放在哪里最划算。"
        ),
        "binance_top_creator": (
            "你是币安广场高赞、高互动的顶级爆款解盘主笔。"
            "行文风格：观点鲜明、敢于反直觉思考、前3秒钩子极具吸引力。善于从恐慌或贪婪中抓住最具确定性的机会，结构紧凑流畅，善于引发评论区深入讨论。"
        ),
        "contrarian_debater": (
            "你是敢于逆向思考、直击散户羊群效应的犀利辩论型交易员。"
            "行文风格：敢唱反调，直接打破常规偏见！当全网盲目追高时你提示流动性诱饵，当全网恐慌看空时你指出大单悄悄吸筹。"
            "语言辛辣有力量，逻辑环环相扣，极具感染力与互动争议性，读者看完全都忍不住在评论区参与站队讨论。"
        ),
        "chill_swing_trader": (
            "你是心态极佳、松弛感拉满的生活化波段交易员。"
            "行文风格：轻松幽默，像老朋友吃夜宵喝啤酒聊行情。把盯盘看作日常生活的一部分，绝不上纲上线，调侃主力庄家的同时把自己的防守点位讲得明明白白。"
            "用最接地气的口吻抚平读者的焦虑情绪，让人读起来极度舒适解压。"
        ),
        "playbook_strategist": (
            "你是推崇严密条件触发与沙盘推演的职业基金操盘官。"
            "行文风格：冷静理性，绝不当盲目算命的‘神棍’，而是给读者清晰拆解【剧本A（企稳跟随）】与【剧本B（破位防守）】。"
            "清晰告知读者行情的关键分界线在哪里，满足什么条件顺势干，跌破什么防线立刻撤退，教会读者像专业量化机构一样做交易计划。"
        ),
        "day_trader": (
            "你是高胜率日内波段猎手。"
            "行文风格：快、准、狠。只讲关键价格分水岭、进场逻辑、死守的防守线与分批止盈目标，言简意赅，一分钟读完即可实操。"
        ),
    }
    persona_prompt = persona_map.get(persona, persona_map["binance_top_creator"])

    # 动态排版结构流派（杜绝千篇一律的固定Emoji公文模板）
    import random
    available_styles = ["flow_narrative", "field_notes", "dialogue_debate", "tactical_playbook", "chill_casual"]
    if not format_style or format_style == "auto":
        # 基于输入标的与当前秒数随机选择一种排版流派，确保每次调用样式完全随机多变
        seed_val = int(sum(ord(c) for c in str(items[0].get("symbol", "BTC") if items else "BTC")) + int(time.time() % 100))
        format_style = available_styles[seed_val % len(available_styles)]

    format_style_guides = {
        "flow_narrative": (
            "【当前篇章排版变奏：纯口语流式叙述体】\n"
            "- 全篇采用 3-4 个纯口语自然段落，行云流水，一气呵成！\n"
            "- ❌ 严禁使用任何 `📌`、`💡`、`🎯`、`⚠️` 等公文式 Emoji 标头！\n"
            "- ❌ 严禁使用 `• 核心标的：... • 关键价位：... • 止损防守：...` 这种呆板的清单列表！\n"
            "- 标的现价、挂单点位、止损防守与止盈目标，必须像真人发朋友圈或推特长推一样，自然融入在句子里！"
        ),
        "field_notes": (
            "【当前篇章排版变奏：极简实盘手记短快灵体】\n"
            "- 篇幅极简干练（约 260 - 360 字），短句为主，节奏快准狠！\n"
            "- 分为 3 个紧凑小段：① 刚盯盘的直观感受；② 主力在这里的关键微观异动；③ 我的挂单点位与止损底线。\n"
            "- 拒绝任何多余修饰与公文模版，直击要害。"
        ),
        "dialogue_debate": (
            "【当前篇章排版变奏：反直觉辩论体】\n"
            "- 开场直击散户惯性思维盲区（例如：`很多人看到这根大阴线又慌着割肉，我却觉得机会来了`）。\n"
            "- 正文展开反直觉推理，告诉读者为什么大多数人此时在犯错，指出大资金的真实意图。\n"
            "- 给出清晰的攻防点位与做错止损线，结尾抛出富有争议性的问题引发评论区激辩。"
        ),
        "tactical_playbook": (
            "【当前篇章排版变奏：沙盘双剧本推演体】\n"
            "- 采用条件触发结构：分别交代【剧本A：若企稳关键支撑则顺势跟进】与【剧本B：若放量跌破防守则坚决空仓观望】。\n"
            "- 把入场点、止损点作为触发开关，教读者不盲目猜单边，做好两手准备。\n"
            "- 行文严谨有条理，专业度拉满。"
        ),
        "chill_casual": (
            "【当前篇章排版变奏：松弛感生活随笔体】\n"
            "- 口吻极其松弛、真诚、风趣，像朋友在群里发日常随感。\n"
            "- 结合日常生活场景（如刚喝完咖啡、吃夜宵、盯盘日常），把主力画门洗盘当乐子看。\n"
            "- 轻松中带着极硬的交易纪律，防守点位与离场线交待得清清楚楚。"
        ),
    }
    format_guide = format_style_guides.get(format_style, format_style_guides["flow_narrative"])

    # Platform formatting guides
    platform_guides = {
        "binance_square": "适配【币安广场 (Binance Square)】社区。内容排版舒适自然，段落错落有致，像真人KOL分享实盘笔记，拒绝任何AI模版排版痕迹。",
        "x": "适配【X / Twitter】长推推文，包含醒目推特标题、线程分段、极简数据要点与核心TAG标签。",
        "xhs": "适配【小红书/社区图文】，前置痛点与干货提炼，语气亲切实用，标签精准。",
        "telegram": "适配【Telegram 频道】，广播简报风，标题醒目，正文简短有力，直接给出核心点位与结论。",
        "general": "通用量化交易复盘研报，包含背景、重点标的、操作策略与风控纪律。",
    }
    platform_guide = platform_guides.get(platform, platform_guides["binance_square"])

    # Tone & Length instructions
    tone_instructions = {
        "analytical": "基调：技术实战流。聚焦关键支撑阻力、假突破反抽、盘口量价背离与盈亏比测算。",
        "conversational": "基调：真实口语互动风。像老朋友聊行情，口吻松弛、真诚、有态度，降低认知负担。",
        "contrarian": "基调：逆向预警流。直击当前散户共识的漏洞，警惕假摔洗盘或流动性诱饵。",
    }
    tone_prompt = tone_instructions.get(tone, tone_instructions["analytical"])

    length_instructions = {
        "concise": "篇幅：极简快准狠（约 250 - 380 字）。直击核心逻辑与进出场计划，拒绝水字数。",
        "standard": "篇幅：精炼实战笔记（约 350 - 500 字）。结构自然流动，逻辑充实，点位清晰，一气呵成。",
        "deep": "篇幅：深度复盘推演（约 500 - 750 字）。深度剖析多周期博弈与风控边界，行文紧凑有力。",
    }
    length_prompt = length_instructions.get(length, length_instructions["standard"])

    promo_snippet = ""
    if include_red_packet:
        red_packet_hook = str(promo.get("red_packet_hook", "")).strip()
        if red_packet_hook:
            promo_snippet = (
                f"🎁 【粉丝福利 · 评论答题瓜分红包（0.2 USDT · 100 份）】\n"
                f"❓ 今日实盘问答：今天我给重点标的设定的核心止损防守位是多少？（答案在正文里找）\n"
                f"💬 参与方式：在评论区留下你的数字答案，系统随机抽取粉丝瓜分 0.2U 答题红包！先答对先得！"
            )
        else:
            promo_snippet = (
                "🎁 【粉丝福利 · 评论答题瓜分红包（0.2 USDT · 100 份）】\n"
                "❓ 今日实盘互动：今天我重点盯盘的币种防守点位是多少？在评论区留下你的答案，随机抽取粉丝瓜分 0.2U 红包！"
            )

    no_red_packet_ban = "❌ 严禁出现红包、答题红包、瓜分0.2U、抽奖等字样（本文不包含任何红包活动，红包仅在博主特定活动时单独发布）！\n" if not include_red_packet else ""
    interaction_rule = (
        "5. 粉丝互动 · 评论答题红包：文末嵌入【评论答题红包】互动模块（0.2 USDT · 100 份），设计一个针对本文具体止损点位或持仓成本的互动提问，引导粉丝在评论区直接回复答案赢红包，极大引爆评论区热度！\n\n"
        if include_red_packet
        else "5. 评论区自然探讨：文末用一两句真实亲切的口吻邀请读者在评论区探讨交流行情（例如：`兄弟们看好这一波突破吗？在评论区聊聊`）。绝对严禁主动输出任何红包、答题红包或抽奖内容！\n\n"
    )

    system_prompt = (
        f"{persona_prompt}\n\n"
        "🚨【第一核心铁律：价格 100% 真实，严禁凭 AI 预训练记忆编造价格】\n"
        "1. 绝不可侵犯的价格红线：提示词中给出的【当前价格/现价】（如 BTC 现价约 84,000 USDT 等）是本次推演的唯一权威真值基准！\n"
        "2. 正文、标题中出现的所有现价、入场点位、支撑位、阻力位、防守止损位与止盈目标，必须 100% 严格围绕输入提示中提供的最新实盘现价展开（正负浮动在真实合理范围内，如现价 84,000 则点位必须在 81,000-88,000 区间）！\n"
        "3. 绝对禁止从大模型预训练历史记忆中编造脱离盘面的虚假陈旧价格（例如：BTC 严禁写 98,200、103,000、104,500 或 65,000 等离谱价格！一旦偏离真实价格超过 5% 即判定为严重事故）！\n"
        "4. 多空态度必须与标的方向 100% 保持一致：看涨(LONG)则标题、正文与 sentiment 必须统一为看涨做多，绝不允许正文出现看跌或做空字眼！反之看跌亦然！\n\n"
        "【至高军规：彻底消灭“AI 塑料味与单一模板感”，必须 100% 像顶级真人实盘交易员在发圈发动态】\n\n"
        "🔥 绝对禁止使用的“AI 工业废话与公式化套词”（出现任何一句即判定为严重失败）：\n"
        f"{no_red_packet_ban}"
        "❌ 严禁出现：「盘面多空博弈进入白热化阶段」\n"
        "❌ 严禁出现：「不适合盲目追涨杀跌」\n"
        "❌ 严禁出现：「目前量化雷达重点锁定的是」\n"
        "❌ 严禁出现：「下面逐一拆解核心逻辑与我的操作思路」\n"
        "❌ 严禁出现：「该信号具备较高的统计学胜率」\n"
        "❌ 严禁出现：「综上所述」、「总而言之」、「如上所述」、「值得注意的是」、「无独有偶」\n"
        "❌ 严禁每篇文案都使用相同的模板排版！绝对禁止使用呆板的公文式列表（如：`• 核心标的：... • 关键价位：... • 止损防守：... • 期望盈亏比：...`），要像真人那样用自然生动的语言叙述！\n"
        "❌ 严禁每段固定以 `📌`、`💡`、`🎯`、`⚠️` 开头！段落小标绝不要公式化，鼓励纯自然段落流式排版！\n"
        "❌ 严禁在第一行生硬地顶格写 `🟢【看涨 · 做多】` 或 `🔴【看跌 · 做空】` 这种机器人标签！观点要在标题和第一句话中通过自然语气自然体现！\n\n"
        "🌟 真人顶级创作者的优秀写作特征：\n"
        "1. 黄金前 3 秒钩子（Hook）：像真实盯盘后的直观感受，形式自由多变：\n"
        "   - 好例1：「说实话，刚才那波下杀把不少追多的兄弟洗下车了，但我复盘了一下盘口，这里有意思了。」\n"
        "   - 好例2：「很多人看到冲高就急着梭哈，但看一下上方的挂单墙，主力其实在暗暗放诱饵。」\n"
        "   - 好例3：「刚冲完咖啡看了一眼盘，这币走得挺妖，聊聊我的应对计划。」\n"
        "2. 关于作者个人持仓（核心原则：克制、低调、不要过多介绍自己的仓位，偶尔简要带过即可）：\n"
        "   - 文章核心必须 100% 聚焦于当前目标币种的客观盘面结构、量价异动、关键支撑阻力与盈亏比计划。\n"
        "   - 绝大多数文章请勿介绍或晒出个人持仓！严禁通篇宣讲个人账户、杠杆、浮盈浮亏，拒绝自嗨式频繁晒单。\n"
        "   - 若输入提示无持仓或无需介绍持仓，绝不可生造个人仓位；\n"
        "   - 只有当输入中显式提供了持仓数据且与当前推荐标的高度相关时，才可用极简短的一句话带过（如「我自己在支撑位小仓做了防守」），绝不单独占一大段！\n"
        "3. 币安广场专属 Cashtag：正文提到币种代码必须带美元符号，格式为 $SYMBOL（如 $BTC、$ETH、$SOL），以便币安自动生成行情小卡片。\n"
        "4. 真人的实盘逻辑（有理有据）：用通俗的交易员行话讲清楚：\n"
        "   - 为什么在这里做？（是跌破前低后的假摔收回？是缩量回踩结构支撑？还是顶背离受阻？）\n"
        "   - 入场参考区间在哪里；\n"
        "   - 止损防守放在什么具体价格（告诉读者：跌破这个位置说明我的推演逻辑被证伪，坚决认赔离场，绝不扛单）；\n"
        "   - 止盈目标看哪里（第一目标位分批减仓锁利，延展目标位继续博弈，附带盈亏比如 2.5:1）；\n"
        f"{interaction_rule}"
        "【输出格式强制要求】\n"
        "必须返回严格的合法 JSON 字符串，不得包含 Markdown 代码块包裹，字段必须包含：\n"
        '{"title": "吸睛爆款标题", "hook": "前置抓人开场白", "body": "完整的Markdown正文", "tags": "高流量标签字符串", "sentiment": "BULLISH或BEARISH", "prompt": "16:9英文封面设计提示词"}\n'
        "字段细节规范：\n"
        "1. title: 严禁使用「🚨 xxx结构企稳共振！多空博弈白热化」这种烂大街AI模板！必须是吸引人、有人情味、风格各异的交易员口吻，包含1个核心标的（如 $BTC 或 $SOL），例如：\n"
        "   - 疑问破局型：`$SOL 刚才这根插针很不寻常，主力到底是在洗盘还是诱多？`\n"
        "   - 实战接单型：`别在现价无脑追涨，聊聊我准备在哪个位置防守接针`\n"
        "   - 盈亏比剧本型：`$DOGE 三角整理接近尾声，分享我的小仓试错剧本（附具体止损）`\n"
        "   - 逆向辩论型：`全网都在恐慌看空，我为什么偏在这个位置做多 $BTC？`\n"
        "   - 轻松随笔型：`刚喝完咖啡看了一眼盘面，聊聊我对 $ETH 的接盘计划`\n"
        "2. hook: 1句话，像朋友圈/动态第一句一样抓人；\n"
        "3. body: 正文排版必须自然、多变且富有真人呼吸感！绝对不要在行首加 Markdown 标题号（# 或 ##），不要机械套用相同的段落排版，严格贯彻当前指定的排版变奏流派；\n"
        "4. tags: 4-5个精准标签，必须以空格分隔且总数不超过5个（例如：#币安广场 #$BTC #行情分析 #合约实战 #做多）；\n"
        "5. sentiment: 'BULLISH' 或 'BEARISH'；\n"
        "6. prompt: 针对该币种走势的16:9专业暗色科技感走势图封面英文提示词。"
    )

    user_prompt = (
        f"【发布目标平台】：{platform_guide}\n"
        f"【风格篇幅要求】：{tone_prompt} | {length_prompt}\n"
        f"{format_guide}\n\n"
        f"【系统实时量化扫描候选标的（重点聚焦第1个核心标的深入剖析，价格绝对真实严禁编造）】：\n{scan_summary}\n\n"
        f"【交易员当前实盘持仓参考（仅作辅助背景，严禁大段晒单喧宾夺主）】：\n{positions_summary}\n\n"
        f"【今日实战交割战报参考】：\n{today_pnl_summary}\n\n"
    )
    if promo_snippet:
        user_prompt += f"【粉丝互动 · 评论答题红包福利（请自然融入文末，激发评论区热烈讨论）】：\n{promo_snippet}\n\n"
    if custom_instruction:
        user_prompt += f"【交易员特别补充指令】：\n{custom_instruction}\n\n"

    user_prompt += (
        "【特别强化要求】：\n"
        "1. 🚨【最高价格铁律】：标的所有价格点位（现价/入场/防守止损/止盈）必须 100% 严格以【系统实时量化扫描候选标的】中给出的当前真实价格为基准！严禁编造任何与当前实盘价格相差超过 3% 的虚假历史价格（例如若 BTC 现价为 84,000，严禁写成 98,000 或 103,000）！\n"
        "2. 务必完全摆脱 AI 腔调！贯彻指定的【排版变奏流派】，模仿真实交易员的个性化语气，变变花样，严禁机械重复模版与Emoji标头！\n"
        "3. 关于作者持仓：保持克制低调，绝不要过多介绍自己的仓位，偶尔简要带过即可，文章核心必须 100% 聚焦于客观技术盘面与风控点位。\n"
        + (
            "4. 文末必须包含针对本文点位的「评论答题瓜分红包（0.2U 100份）」问答，让读者在评论区留言回答！\n"
            if include_red_packet
            else "4. 文末自然引导读者在评论区交流盯盘思路，严禁出现红包、答题红包或抽奖字样！\n"
        )
        + "5. 标的代码请使用 $SYMBOL 格式，明确给出进场参考、止损防守位（具体价格）和止盈目标位。\n"
        "6. 严禁使用任何被禁用的AI套词，严格以 JSON 格式输出。"
    )



    # Execute with fallback among candidate providers
    last_error = ""
    for provider in candidates:
        # Give sharedchat a short timeout if gateway is down, and ample 55s for DeepSeek reasoning
        p_timeout = 8.0 if "sharedchat" in str(provider.get("base_url", "")).lower() else 55.0
        res = await _call_single_provider(
            provider=provider,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            proxy=proxy,
            timeout_seconds=p_timeout,
        )
        if res.get("ok"):
            if generate_image:
                d = res.get("data", {})
                img_prompt = d.get("prompt") or d.get("title") or "crypto trading analysis"
                top_sym = items[0].get("symbol") if items else None
                try:
                    from openai_image_client import openai_image_client
                    img_res = await openai_image_client.generate_image(
                        prompt=img_prompt,
                        symbol=top_sym,
                        size="1792x1024",
                    )
                    if img_res.get("ok"):
                        d["image_data_url"] = img_res["data_url"]
                        d["image_local_path"] = img_res.get("local_path", "")
                        d["image_prompt"] = img_res.get("prompt", "")
                        res["image"] = img_res
                except Exception as img_err:
                    res["image_error"] = str(img_err)
            return res
        last_error = res.get("error", "未知错误")

    return {
        "ok": False,
        "error": f"所有 AI 供应商调用均失败。最后错误: {last_error}",
    }


async def generate_blog_image(
    prompt: Optional[str] = None,
    symbol: Optional[str] = None,
    size: str = "1792x1024",
    model: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Invoke OpenAI DALL-E image generation interface directly to create an article visual/cover."""
    from openai_image_client import openai_image_client
    return await openai_image_client.generate_image(
        prompt=prompt,
        symbol=symbol,
        size=size,
        model=model,
        **kwargs,
    )
