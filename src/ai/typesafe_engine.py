"""TypeSafe Jev (System One) Decision Engine for Binance Trading System.

Integrates TypeSafe's Jev model (System One) to provide calibrated,
non-generative, typed decision judgments (Choice, Score, Noul) with
true mathematical confidence gating before trade entry.
Mounts local Obsidian knowledge base (strategies + discipline habits)
to ensure Jev evaluates setups against the trader's proprietary playbook.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx2
from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, Score

try:
    from obsidian_bridge import ObsidianBridge
except ImportError:
    ObsidianBridge = None


class TypeSafeStateBuilder:
    """Translates local technical indicators, smart money flow, and market

    conditions into structured English JSON State for Jev evaluation.
    """

    @staticmethod
    def _translate_pattern(pattern_zh: str) -> str:
        """Translate internal Chinese candle pattern strings to English."""
        mapping = {
            "连续阳线(强势上攻)": "Consecutive green candles (strong upward impulse)",
            "连续阴线(弱势下行)": "Consecutive red candles (strong downward impulse)",
            "十字星(多空犹豫,变盘在即)": "Doji / Spinning top (indecision at inflection point)",
            "长下影线(下方买盘强)": "Long lower shadow (strong pin bar buying rejection)",
            "长上影线(上方抛压重)": "Long upper shadow (strong pin bar selling rejection)",
            "波动收窄(蓄力中,即将选择方向)": "Contracting range (compression ahead of breakout)",
        }
        return mapping.get(pattern_zh, pattern_zh or "Standard candle formation")

    @staticmethod
    def _translate_intent(intent_zh: str) -> str:
        mapping = {
            "出货": "Distribution (smart money unloading into strength)",
            "吸筹": "Accumulation (smart money silently building positions)",
            "洗盘": "Washout / Shakeout (shaking out weak hands before trend)",
            "拉升": "Markup (active push into higher prices)",
            "观望": "Neutral / Waiting",
        }
        return mapping.get(intent_zh, intent_zh or "Neutral")

    @classmethod
    def extract_obsidian_playbook(
        cls,
        symbol: str,
        price: float,
        candidate_signal: int = 0,
        candidate_context: dict[str, Any] | None = None,
        bridge: Any | None = None,
    ) -> dict[str, Any] | None:
        """Extract matched strategies and habit analysis from local Obsidian vault."""
        if bridge is None:
            return None
        try:
            candidate_context = candidate_context or {}
            indicators = candidate_context.get("indicators") or {}
            ind_for_match = dict(indicators)
            ind_for_match["price"] = price
            if "htf_aligned" in candidate_context:
                ind_for_match["htf_trend"] = 1 if candidate_context["htf_aligned"] else -1

            strat_res = bridge.match_strategies_for_symbol(
                symbol=symbol,
                current_price=price,
                indicators=ind_for_match,
            )
            habits_res = bridge.analyze_habits(days=7)

            best = strat_res.get("best_match") if strat_res.get("ok") else None
            if not best:
                return None

            checklist_summary = [
                f"{c.get('name')}: {c.get('status')} ({c.get('detail')})"
                for c in (best.get("checklist") or [])[:5]
            ]

            habits_warnings = habits_res.get("warnings") or []
            habits_strengths = habits_res.get("strengths") or []

            return {
                "strategy_title": best.get("title"),
                "strategy_type": best.get("type"),
                "match_score": best.get("match_score"),
                "recommended_direction": best.get("direction"),
                "entry_rules": (best.get("entry_rules") or "").strip()[:500],
                "risk_rules": (best.get("risk_rules") or "").strip()[:300],
                "checklist_verifications": checklist_summary,
                "discipline_status": {
                    "overall_score": habits_res.get("overall_score"),
                    "warnings": habits_warnings[:3],
                    "strengths": habits_strengths[:3],
                },
            }
        except Exception:
            return None

    @classmethod
    def build_state(
        cls,
        symbol: str,
        candidate_signal: int,
        price: float,
        candidate_context: dict[str, Any] | None = None,
        recent_closes: list[float] | None = None,
        funding_rate: float | None = None,
        obsidian_playbook: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        candidate_context = dict(candidate_context or {})
        direction = "LONG" if candidate_signal > 0 else "SHORT" if candidate_signal < 0 else "HOLD"
        base_score = float(candidate_context.get("base_score", candidate_context.get("score", 0)) or 0)

        indicators = candidate_context.get("indicators") or {}
        rsi = float(indicators.get("rsi") or 50.0)
        macd_hist = float(indicators.get("macd_hist") or indicators.get("macd", 0.0) or 0.0)
        atr = float(indicators.get("atr") or 0.0)
        atr_pct = (atr / price * 100) if (price > 0 and atr > 0) else 0.0

        smart = candidate_context.get("smart_money") or {}
        intent = cls._translate_intent(smart.get("intent") or "")
        smart_score = float(smart.get("score") or 0.0)

        liquidity = candidate_context.get("liquidity") or {}
        spread_bps = float(liquidity.get("spread_bps") or 0.0)
        vol_24h = float(liquidity.get("quote_volume_24h") or 0.0)

        pattern = cls._translate_pattern(candidate_context.get("pattern") or "")
        factors = candidate_context.get("strategy_factors") or candidate_context.get("factors") or []

        # Recent 6-8 prices
        closes = recent_closes or candidate_context.get("recent_closes") or []
        if len(closes) > 8:
            closes = closes[-8:]

        state = {
            "asset": {
                "symbol": symbol,
                "current_price": round(price, 6),
                "atr": round(atr, 6),
                "atr_volatility_pct": round(atr_pct, 3),
                "funding_rate_pct": round((funding_rate or 0.0) * 100, 4) if funding_rate is not None else None,
                "liquidity_24h_volume_usd": round(vol_24h, 1) if vol_24h > 0 else None,
                "spread_bps": round(spread_bps, 2) if spread_bps > 0 else None,
            },
            "candidate_setup": {
                "proposed_direction": direction,
                "quantitative_base_score": round(base_score, 2),
                "key_strategy_factors": factors[:6],
                "candle_pattern": pattern,
                "recent_closes": [round(float(c), 6) for c in closes],
            },
            "technical_indicators": {
                "rsi_14": round(rsi, 2),
                "macd_histogram": round(macd_hist, 6),
                "higher_timeframe_aligned": bool(candidate_context.get("htf_aligned", True)),
                "smart_money_intent": intent,
                "smart_money_alignment_score": round(smart_score, 1),
            },
        }

        if obsidian_playbook:
            state["user_obsidian_playbook"] = {
                "matched_strategy": {
                    "title": obsidian_playbook.get("strategy_title"),
                    "type": obsidian_playbook.get("strategy_type"),
                    "vault_match_score": obsidian_playbook.get("match_score"),
                    "playbook_direction": obsidian_playbook.get("recommended_direction"),
                    "entry_rules": obsidian_playbook.get("entry_rules"),
                    "risk_rules": obsidian_playbook.get("risk_rules"),
                    "checklist_verifications": obsidian_playbook.get("checklist_verifications"),
                },
                "trader_habits_and_discipline": obsidian_playbook.get("discipline_status"),
            }

        return state


class TypeSafeDecisionEngine:
    """Evaluates trading signals using TypeSafe Jev (System One) API."""

    def __init__(
        self,
        cfg: dict[str, Any] | None = None,
        proxy: str | None = None,
        obsidian_bridge: Any | None = None,
    ):
        self.cfg = cfg or {}
        self.enabled = bool(self.cfg.get("enabled", False))
        self.model = str(self.cfg.get("model", "jev-latest")).strip() or "jev-latest"
        self.timeout_seconds = float(self.cfg.get("timeout_seconds", 8.0))
        self.min_confidence = float(self.cfg.get("min_confidence", 0.65))
        self.max_risk_score = float(self.cfg.get("max_risk_score", 2.5))
        self.min_breakout_score = float(self.cfg.get("min_breakout_score", 1.8))
        self.use_obsidian_playbook = bool(self.cfg.get("use_obsidian_playbook", True))
        self.min_playbook_score = float(self.cfg.get("min_playbook_score", 1.5))
        self.max_violation_prob = float(self.cfg.get("max_violation_prob", 0.45))
        self.api_key_env = str(self.cfg.get("api_key_env", "TYPESAFE_API_KEY")).strip()
        self.configured_api_key = str(self.cfg.get("api_key", "")).strip()
        self.proxy = proxy or self.cfg.get("proxy") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or ""
        self.autonomous_hunter_cfg = self.cfg.get("autonomous_hunter", {})
        self.autonomous_enabled = bool(self.autonomous_hunter_cfg.get("enabled", True))

        if obsidian_bridge is not None:
            self.obsidian_bridge = obsidian_bridge
        elif self.use_obsidian_playbook and ObsidianBridge is not None:
            try:
                self.obsidian_bridge = ObsidianBridge()
            except Exception:
                self.obsidian_bridge = None
        else:
            self.obsidian_bridge = None

    def get_api_key(self) -> str:
        """Fetch API Key prioritizing environment variable over config file."""
        return (os.getenv(self.api_key_env) or self.configured_api_key or "").strip()

    def _get_http_client(self) -> httpx2.AsyncClient | None:
        """Create httpx2 AsyncClient honoring proxy setting if configured."""
        if self.proxy:
            return httpx2.AsyncClient(proxy=self.proxy, timeout=self.timeout_seconds)
        return None

    def _build_questions(self, include_obsidian: bool = False) -> dict[str, Any]:
        """Define the atomic evaluation questions."""
        questions: dict[str, Any] = {
            "market_regime": Choice(
                instructions="What is the current market regime for this asset based on the snapshot?",
                criteria={
                    "strong_trend": "Clear directional trend, consistent moving average stack, healthy momentum.",
                    "mean_reverting": "Range-bound consolidation, oscillating around equilibrium/VWAP.",
                    "choppy_noise": "High volatility chop, conflicting signals, or lack of directional clarity.",
                },
            ),
            "signal_action": Choice(
                instructions="Based on technical structure, momentum, and risk indicators, what is the best immediate action?",
                criteria={
                    "LONG": "High probability bullish setup, buyers in control, favorable risk-reward for long entry.",
                    "SHORT": "High probability bearish breakdown, sellers in control, favorable risk-reward for short entry.",
                    "HOLD": "Inconclusive edge, overextended price, opposing orderflow, or excessive risk.",
                },
            ),
            "breakout_quality": Score(
                instructions="Evaluate the structural quality and authenticity of this trend setup or breakout.",
                criteria=[
                    "Level 0: Obvious trap or fakeout into immediate resistance/support.",
                    "Level 1: Weak setup, high divergence risk, lack of conviction.",
                    "Level 2: Neutral setup, standard momentum with moderate probability.",
                    "Level 3: Solid setup, clean expansion, trend factors well-aligned.",
                    "Level 4: Exceptional institutional momentum, high-conviction breakout.",
                ],
            ),
            "risk_level": Score(
                instructions="Rate the downside / invalidation hazard (e.g. overextension, squeeze risk, liquidity traps).",
                criteria=[
                    "Level 0: Minimal hazard, tight structural invalidation.",
                    "Level 1: Low risk, standard volatility with clear stop-loss boundary.",
                    "Level 2: Moderate risk, standard crypto market volatility.",
                    "Level 3: Elevated risk, stretched oscillators or divergence signals.",
                    "Level 4: Extreme hazard, blow-off move, illiquid or trap danger.",
                ],
            ),
            "trend_continuation": Noul(
                instructions="Is this price momentum likely to persist favorably over the next 2 to 5 candles without immediate invalidation?",
                criteria={
                    "true": "Momentum and volume profile favor favorable trend continuation.",
                    "false": "High probability of sudden reversal, stall, or shakeout.",
                },
            ),
        }
        if include_obsidian:
            questions["playbook_adherence"] = Score(
                instructions="Evaluate how strictly this market setup and candidate action satisfy the user's Obsidian strategy playbook entry rules.",
                criteria=[
                    "Level 0: Setup contradicts or completely fails the playbook's mandatory entry rules.",
                    "Level 1: Weak match; critical entry criteria missing, unverified, or conflicting.",
                    "Level 2: Moderate match; some criteria met but key structural confirmation is lacking.",
                    "Level 3: Solid match; satisfies core entry rules with good setup alignment.",
                    "Level 4: Textbook execution; all playbook criteria, risk ratios, and patterns fully aligned.",
                ],
            )
            questions["discipline_violation"] = Noul(
                instructions="Does taking this signal violate the trader's historical discipline warnings (e.g. FOMO chase, entering without clear stop loss, revenge trading)?",
                criteria={
                    "true": "High risk of psychological or discipline violation; exhibits chase/FOMO or violates habit warnings.",
                    "false": "Clean, disciplined execution strictly following trading rules and habit boundaries.",
                },
            )
        return questions

    async def evaluate_entry(
        self,
        symbol: str,
        candidate_signal: int,
        price: float,
        candidate_context: dict[str, Any] | None = None,
        recent_closes: list[float] | None = None,
        funding_rate: float | None = None,
    ) -> dict[str, Any]:
        """Evaluate a candidate signal using TypeSafe Jev model."""
        candidate_context = dict(candidate_context or {})
        candidate_direction = "LONG" if candidate_signal > 0 else "SHORT" if candidate_signal < 0 else "HOLD"

        api_key = self.get_api_key()
        if not api_key:
            return {
                "approved": False,
                "status": "missing_api_key",
                "candidate": candidate_direction,
                "reason": f"TypeSafe API key missing (set {self.api_key_env} or config.json typesafe.api_key)",
                "risk_flags": ["missing_api_key"],
                "latency_ms": 0,
            }

        # Extract Obsidian playbook & trader habits if enabled
        obsidian_playbook = None
        if self.use_obsidian_playbook and self.obsidian_bridge is not None:
            obsidian_playbook = TypeSafeStateBuilder.extract_obsidian_playbook(
                symbol=symbol,
                price=price,
                candidate_signal=candidate_signal,
                candidate_context=candidate_context,
                bridge=self.obsidian_bridge,
            )

        state = TypeSafeStateBuilder.build_state(
            symbol=symbol,
            candidate_signal=candidate_signal,
            price=price,
            candidate_context=candidate_context,
            recent_closes=recent_closes,
            funding_rate=funding_rate,
            obsidian_playbook=obsidian_playbook,
        )

        has_playbook = obsidian_playbook is not None
        questions = self._build_questions(include_obsidian=has_playbook)
        started = time.perf_counter()

        http_client = self._get_http_client()
        try:
            async with AsyncTypeSafeClient(
                api_key=api_key,
                model=self.model,
                timeout=self.timeout_seconds,
                http_client=http_client,
            ) as client:
                response = await client.system_one(state=state, questions=questions)
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1000)
            return {
                "approved": False,
                "status": "api_error",
                "candidate": candidate_direction,
                "reason": f"TypeSafe Jev request failed: {str(exc)[:200]}",
                "risk_flags": ["typesafe_api_error"],
                "latency_ms": latency_ms,
            }
        finally:
            if http_client is not None:
                await http_client.aclose()

        latency_ms = round((time.perf_counter() - started) * 1000)

        # Extract structured answers
        action_ans = response.choices.get("signal_action")
        regime_ans = response.choices.get("market_regime")
        breakout_ans = response.scores.get("breakout_quality")
        risk_ans = response.scores.get("risk_level")
        continuation_ans = response.nouls.get("trend_continuation")

        playbook_ans = response.scores.get("playbook_adherence") if has_playbook else None
        violation_ans = response.nouls.get("discipline_violation") if has_playbook else None

        if not action_ans:
            return {
                "approved": False,
                "status": "malformed_response",
                "candidate": candidate_direction,
                "reason": "Missing signal_action in TypeSafe response",
                "risk_flags": ["response_parsing_error"],
                "latency_ms": latency_ms,
            }

        jev_action = str(action_ans.choice).strip().upper()
        confidence = float(action_ans.confidence or 0.0)
        action_probs = dict(action_ans.probabilities or {})

        risk_score = float(risk_ans.score if risk_ans else 2.0)
        risk_confidence = float(risk_ans.confidence if risk_ans else 0.0)

        breakout_score = float(breakout_ans.score if breakout_ans else 2.0)
        continuation_prob = float(continuation_ans.noul if continuation_ans else 0.5)
        market_regime = str(regime_ans.choice if regime_ans else "unknown")

        playbook_score = float(playbook_ans.score if playbook_ans else 2.5) if has_playbook else None
        violation_prob = float(violation_ans.noul if violation_ans else 0.1) if has_playbook else None

        # Composite Decision Gates
        risk_flags: list[str] = []
        is_aligned = (jev_action == candidate_direction)
        if not is_aligned:
            risk_flags.append(f"direction_mismatch (jev recommends {jev_action} vs candidate {candidate_direction})")

        if confidence < self.min_confidence:
            risk_flags.append(f"low_confidence ({confidence:.2f} < {self.min_confidence:.2f})")

        if risk_score > self.max_risk_score:
            risk_flags.append(f"high_risk_score ({risk_score:.2f} > {self.max_risk_score:.2f})")

        if breakout_score < self.min_breakout_score:
            risk_flags.append(f"poor_breakout_quality ({breakout_score:.2f} < {self.min_breakout_score:.2f})")

        # Obsidian Playbook Gating
        if has_playbook and playbook_score is not None:
            if playbook_score < self.min_playbook_score:
                risk_flags.append(
                    f"obsidian_playbook_mismatch (playbook score {playbook_score:.2f} < {self.min_playbook_score:.2f})"
                )
        if has_playbook and violation_prob is not None:
            if violation_prob > self.max_violation_prob:
                risk_flags.append(
                    f"discipline_violation_risk (violation prob {violation_prob:.2f} > {self.max_violation_prob:.2f})"
                )

        playbook_ok = True
        if has_playbook:
            if playbook_score is not None and playbook_score < self.min_playbook_score:
                playbook_ok = False
            if violation_prob is not None and violation_prob > self.max_violation_prob:
                playbook_ok = False

        approved = (
            candidate_direction in {"LONG", "SHORT"}
            and is_aligned
            and confidence >= self.min_confidence
            and risk_score <= self.max_risk_score
            and breakout_score >= self.min_breakout_score
            and playbook_ok
        )

        if has_playbook and playbook_score is not None and violation_prob is not None:
            composite_score = round(
                (action_probs.get(candidate_direction, 0.0) * 30.0)
                + (breakout_score / 4.0 * 20.0)
                + ((4.0 - risk_score) / 4.0 * 20.0)
                + (playbook_score / 4.0 * 20.0)
                + ((1.0 - violation_prob) * 10.0),
                1,
            )
        else:
            composite_score = round(
                (action_probs.get(candidate_direction, 0.0) * 40.0)
                + (breakout_score / 4.0 * 30.0)
                + ((4.0 - risk_score) / 4.0 * 20.0)
                + (continuation_prob * 10.0),
                1,
            )

        pb_tag = f", playbook={playbook_score:.1f}" if has_playbook and playbook_score is not None else ""
        reason = (
            f"Jev {jev_action} (conf={confidence:.2f}, risk={risk_score:.1f}, breakout={breakout_score:.1f}{pb_tag})"
            if approved
            else f"Rejected by Jev: {', '.join(risk_flags) if risk_flags else 'unknown'}"
        )

        result_payload: dict[str, Any] = {
            "approved": approved,
            "status": "approved" if approved else "rejected",
            "candidate": candidate_direction,
            "jev_action": jev_action,
            "confidence": confidence,
            "action_probabilities": action_probs,
            "market_regime": market_regime,
            "breakout_quality_score": round(breakout_score, 2),
            "risk_level_score": round(risk_score, 2),
            "risk_confidence": round(risk_confidence, 2),
            "trend_continuation_prob": round(continuation_prob, 3),
            "composite_score": composite_score,
            "risk_flags": risk_flags,
            "reason": reason,
            "latency_ms": latency_ms,
            "model": getattr(response, "model", self.model),
            "tokens": getattr(response, "usage", None),
        }

        if has_playbook and obsidian_playbook is not None:
            result_payload["obsidian_playbook"] = {
                "matched_strategy": obsidian_playbook.get("strategy_title"),
                "strategy_type": obsidian_playbook.get("strategy_type"),
                "vault_match_score": obsidian_playbook.get("match_score"),
                "playbook_score": round(playbook_score, 2) if playbook_score is not None else None,
                "discipline_violation_prob": round(violation_prob, 3) if violation_prob is not None else None,
                "discipline_score": (obsidian_playbook.get("discipline_status") or {}).get("overall_score"),
            }
            result_payload["playbook_score"] = round(playbook_score, 2) if playbook_score is not None else None
            result_payload["discipline_violation_prob"] = round(violation_prob, 3) if violation_prob is not None else None

        return result_payload

    async def test_connection(self, api_key: str = "") -> dict[str, Any]:
        """Validate TypeSafe API credentials and check roundtrip latency."""
        key = (api_key or self.get_api_key()).strip()
        if not key:
            return {
                "success": False,
                "status": "missing_key",
                "message": "TypeSafe API Key is not configured.",
                "latency_ms": 0,
            }

        test_state = "Bitcoin broke above 92,000 with expanding volume on the 15m chart. Moving averages are aligned upwards."
        test_question = {
            "is_bullish": Noul(
                instructions="Does this indicate bullish continuation?",
                criteria={"true": "Clear bullish momentum", "false": "Bearish or ambiguous"},
            )
        }

        started = time.perf_counter()
        http_client = self._get_http_client()
        try:
            async with AsyncTypeSafeClient(
                api_key=key,
                model=self.model,
                timeout=self.timeout_seconds,
                http_client=http_client,
            ) as client:
                response = await client.system_one(state=test_state, questions=test_question)
            latency_ms = round((time.perf_counter() - started) * 1000)
            noul_val = response.nouls.get("is_bullish").noul if response.nouls.get("is_bullish") else 0.0
            return {
                "success": True,
                "status": "ok",
                "message": f"TypeSafe Jev connection successful! (noul: {noul_val:.2f})",
                "model": getattr(response, "model", self.model),
                "latency_ms": latency_ms,
            }
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1000)
            return {
                "success": False,
                "status": "error",
                "message": f"Connection failed: {str(exc)}",
                "latency_ms": latency_ms,
            }
        finally:
            if http_client is not None:
                await http_client.aclose()

    async def scan_autonomous_hunter(
        self,
        symbol: str,
        price: float,
        recent_closes: list[float] | None = None,
        candidate_context: dict[str, Any] | None = None,
        funding_rate: float | None = None,
    ) -> dict[str, Any]:
        """Jev 自主狙击引擎 (Autonomous Hunter)

        无需依赖传统指标初筛触发，Jev 主动调用 12 套 Obsidian 策略脑图与 7 维原子特征进行全盘独立扫描。
        仅当发现 S 级高置信度结构（例如威科夫 Spring、ICT 银弹、Volume Profile POC 强支撑）且违规率极低时，
        直接产出主动开仓决策（LONG / SHORT）。
        """
        candidate_context = dict(candidate_context or {})

        # 1. 尝试匹配 Obsidian 策略脑图
        obsidian_playbook = None
        if self.use_obsidian_playbook and self.obsidian_bridge is not None:
            obsidian_playbook = TypeSafeStateBuilder.extract_obsidian_playbook(
                symbol=symbol,
                price=price,
                candidate_signal=0,
                candidate_context=candidate_context,
                bridge=self.obsidian_bridge,
            )

        min_conf = float(self.autonomous_hunter_cfg.get("min_confidence", 0.68))
        min_pb = float(self.autonomous_hunter_cfg.get("min_playbook_score", 2.2))
        max_risk = float(self.autonomous_hunter_cfg.get("max_risk_score", 2.3))
        min_breakout = float(self.autonomous_hunter_cfg.get("min_breakout_score", 1.9))
        max_violation = float(self.autonomous_hunter_cfg.get("max_violation_prob", 0.28))

        # 2. 如果已配置有效 API Key，走 TypeSafe Jev 云端模型
        api_key = self.get_api_key()
        if api_key:
            state = TypeSafeStateBuilder.build_state(
                symbol=symbol,
                candidate_signal=0,
                price=price,
                candidate_context=candidate_context,
                recent_closes=recent_closes,
                funding_rate=funding_rate,
                obsidian_playbook=obsidian_playbook,
            )
            has_playbook = obsidian_playbook is not None
            questions = self._build_questions(include_obsidian=has_playbook)
            started = time.perf_counter()
            http_client = self._get_http_client()
            try:
                async with AsyncTypeSafeClient(
                    api_key=api_key,
                    model=self.model,
                    timeout=self.timeout_seconds,
                    http_client=http_client,
                ) as client:
                    response = await client.system_one(state=state, questions=questions)
                latency_ms = round((time.perf_counter() - started) * 1000)
                act = response.choices.get("signal_action").choice if response.choices.get("signal_action") else "HOLD"
                conf = response.choices.get("signal_action").confidence if response.choices.get("signal_action") else 0.5
                breakout = response.scores.get("breakout_quality").score if response.scores.get("breakout_quality") else 0.0
                risk = response.scores.get("risk_level").score if response.scores.get("risk_level") else 4.0
                pb_score = response.scores.get("playbook_adherence").score if (has_playbook and response.scores.get("playbook_adherence")) else (3.0 if has_playbook else 1.0)
                violation = response.nouls.get("discipline_violation").noul if (has_playbook and response.nouls.get("discipline_violation")) else 0.1

                approved = (act in ("LONG", "SHORT") and conf >= min_conf and risk <= max_risk and breakout >= min_breakout and pb_score >= min_pb and violation <= max_violation)
                return {
                    "approved": approved,
                    "action": act,
                    "confidence": conf,
                    "breakout_quality": breakout,
                    "risk_level": risk,
                    "playbook_score": pb_score,
                    "discipline_violation": violation,
                    "latency_ms": latency_ms,
                    "playbook": obsidian_playbook,
                    "reason": f"Jev Autonomous Hunter S-tier {act} (conf={conf:.2f}, pb={pb_score:.1f})" if approved else f"Jev passed on {symbol} ({act})",
                }
            except Exception:
                pass

        # 3. 本地事前无偏纯规则引擎 (Zero-Lookahead 离线/备用模式)
        try:
            from jev_evolution_pipeline import evaluate_simulation_sample
            rec_dir = 1 if (obsidian_playbook and obsidian_playbook.get("recommended_direction") == "LONG") else (-1 if (obsidian_playbook and obsidian_playbook.get("recommended_direction") == "SHORT") else 1)
            pseudo_sample = {
                "id": f"AUTO-{symbol}",
                "symbol": symbol,
                "signal": rec_dir,
                "price": price,
                "recent_closes": recent_closes or [],
                "candidate_context": candidate_context,
                "funding_rate": funding_rate or 0.0,
            }
            res = evaluate_simulation_sample(pseudo_sample, obsidian_playbook)
            act = res.get("jev_action", "HOLD")
            conf = res.get("confidence", 0.5)
            breakout = res.get("breakout_quality_score", 0.0)
            risk = res.get("risk_level_score", 4.0)
            pb_score = res.get("playbook_score", 0.0)
            violation = res.get("discipline_violation_prob", 0.5)

            hunter_approved = (
                res.get("approved", False)
                and act in ("LONG", "SHORT")
                and conf >= min_conf
                and risk <= max_risk
                and breakout >= min_breakout
                and pb_score >= min_pb
                and violation <= max_violation
            )
            return {
                "approved": hunter_approved,
                "action": act if hunter_approved else "HOLD",
                "confidence": conf,
                "breakout_quality": breakout,
                "risk_level": risk,
                "playbook_score": pb_score,
                "discipline_violation": violation,
                "latency_ms": res.get("latency_ms", 10),
                "playbook": obsidian_playbook,
                "reason": (
                    f"Jev Autonomous Hunter S-tier {act} (conf={conf:.2f}, pb={pb_score:.1f})"
                    if hunter_approved
                    else (res.get("reason", "") or f"Hunter filtered {symbol}")
                ),
            }
        except Exception as exc:
            return {
                "approved": False,
                "action": "HOLD",
                "confidence": 0.0,
                "reason": f"Hunter error: {exc}",
                "latency_ms": 0,
            }
