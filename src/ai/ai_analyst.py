"""AI分析引擎 - 实时K线分析与交易策略建议"""
import numpy as np
import pandas as pd
from strategy import (
    calc_ma, calc_ema, calc_rsi, calc_macd, calc_bollinger,
    calc_atr, calc_vwap, calc_obv, calc_stoch_rsi,
    detect_rsi_divergence, detect_volume_spike, detect_ema_ribbon
)


def find_support_resistance(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, n_levels=3):
    """寻找关键支撑/阻力位(基于局部极值聚类)"""
    if len(closes) < 20:
        return [], []
    window = 5
    pivots_high, pivots_low = [], []
    for i in range(window, len(highs) - window):
        if highs[i] == max(highs[i-window:i+window+1]):
            pivots_high.append(highs[i])
        if lows[i] == min(lows[i-window:i+window+1]):
            pivots_low.append(lows[i])

    price = closes[-1]
    # 聚类相近的极值点
    def cluster(levels, tol_pct=0.005):
        if not levels:
            return []
        levels = sorted(levels)
        clusters = [[levels[0]]]
        for lv in levels[1:]:
            if abs(lv - clusters[-1][-1]) / clusters[-1][-1] < tol_pct:
                clusters[-1].append(lv)
            else:
                clusters.append([lv])
        return [round(float(np.mean(c)), 6) for c in clusters]

    resistances = sorted([r for r in cluster(pivots_high) if r > price])[:n_levels]
    supports = sorted([s for s in cluster(pivots_low) if s < price], reverse=True)[:n_levels]
    return supports, resistances


def detect_pattern(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> str:
    """检测近期K线形态"""
    if len(closes) < 10:
        return ""
    c = closes[-5:]
    h = highs[-5:]
    l = lows[-5:]

    # 连续阳线/阴线
    up_count = sum(1 for i in range(1, len(c)) if c[i] > c[i-1])
    if up_count >= 4:
        return "连续阳线(强势上攻)"
    if up_count <= 1:
        return "连续阴线(弱势下行)"

    # 十字星(犹豫)
    body = abs(c[-1] - c[-2])
    full_range = h[-1] - l[-1]
    if full_range > 0 and body / full_range < 0.15:
        return "十字星(多空犹豫,变盘在即)"

    # 长下影线(买盘支撑)
    lower_shadow = min(c[-1], c[-2]) - l[-1]
    if full_range > 0 and lower_shadow / full_range > 0.5:
        return "长下影线(下方买盘强)"

    # 长上影线(抛压)
    upper_shadow = h[-1] - max(c[-1], c[-2])
    if full_range > 0 and upper_shadow / full_range > 0.5:
        return "长上影线(上方抛压重)"

    # 收窄震荡
    ranges = h[-5:] - l[-5:]
    if len(ranges) >= 5 and ranges[-1] < np.mean(ranges[:4]) * 0.5:
        return "波动收窄(蓄力中,即将选择方向)"

    return ""


def trend_strength(closes: np.ndarray) -> tuple:
    """趋势方向与强度 0-100"""
    if len(closes) < 30:
        return "震荡", 0
    ema20 = calc_ema(closes, 20)
    slope = (ema20[-1] - ema20[-10]) / ema20[-10] * 100
    adx_proxy = abs(slope) * 10  # 简化强度指标
    strength = min(int(adx_proxy * 5), 100)
    if slope > 0.05:
        return "上升", strength
    elif slope < -0.05:
        return "下降", strength
    return "震荡", strength


class AIAnalyst:
    """生成自然语言K线分析报告"""

    @staticmethod
    def _build_entry_plan(
        action: str,
        confidence: int,
        price: float,
        atr: float,
        supports: list,
        resistances: list,
        htf_trend: int = 0,
    ) -> dict:
        """生成只读的回调入场计划，不把当前价直接当成追单价。"""
        empty = {
            "status": "WAIT",
            "side": None,
            "entry_low": None,
            "entry_high": None,
            "entry_price": None,
            "stop_loss": None,
            "tp1": None,
            "tp2": None,
            "rr": None,
            "reason": "等待方向与关键价位确认",
        }
        if action not in ("偏多", "偏空") or confidence < 60 or price <= 0:
            return empty

        try:
            atr = float(atr)
            price = float(price)
            supports = sorted(
                {float(level) for level in (supports or []) if float(level) > 0 and float(level) < price},
                reverse=True,
            )
            resistances = sorted(
                {float(level) for level in (resistances or []) if float(level) > price}
            )
        except (TypeError, ValueError):
            return empty
        if atr <= 0:
            return empty

        side = "LONG" if action == "偏多" else "SHORT"
        if side == "LONG":
            anchor = supports[0] if supports else price - atr * 0.75
            entry_low = anchor - atr * 0.25
            entry_high = min(anchor + atr * 0.35, price - atr * 0.05)
            if entry_high <= entry_low:
                return empty
            stop_loss = anchor - atr * 0.9
            entry_price = (entry_low + entry_high) / 2
            risk = entry_price - stop_loss
            tp1 = next((level for level in resistances if level > entry_high), None)
            if tp1 is None:
                tp1 = entry_price + max(risk * 1.8, atr * 1.5)
            elif tp1 - entry_price < risk * 1.5:
                tp1 = entry_price + risk * 1.5
            next_resistance = next((level for level in resistances if level > tp1), None)
            tp2 = next_resistance or max(tp1 + risk * 0.75, entry_price + risk * 2.4)
        else:
            anchor = resistances[0] if resistances else price + atr * 0.75
            entry_low = max(anchor - atr * 0.35, price + atr * 0.05)
            entry_high = anchor + atr * 0.25
            if entry_high <= entry_low:
                return empty
            stop_loss = anchor + atr * 0.9
            entry_price = (entry_low + entry_high) / 2
            risk = stop_loss - entry_price
            tp1 = next((level for level in supports if level < entry_low), None)
            if tp1 is None:
                tp1 = entry_price - max(risk * 1.8, atr * 1.5)
            elif entry_price - tp1 < risk * 1.5:
                tp1 = entry_price - risk * 1.5
            next_support = next((level for level in supports if level < tp1), None)
            tp2 = next_support or min(tp1 - risk * 0.75, entry_price - risk * 2.4)
        if risk <= 0 or tp1 <= 0 or tp2 <= 0:
            return empty
        rr = abs(tp1 - entry_price) / risk
        if rr < 1.5:
            return empty
        status = "READY"
        if htf_trend and ((side == "LONG" and htf_trend < 0) or (side == "SHORT" and htf_trend > 0)):
            status = "WAIT_CONFIRMATION"
        return {
            "status": status,
            "side": side,
            "entry_low": round(entry_low, 8),
            "entry_high": round(entry_high, 8),
            "entry_price": round(entry_price, 8),
            "stop_loss": round(stop_loss, 8),
            "tp1": round(tp1, 8),
            "tp2": round(tp2, 8),
            "rr": round(rr, 2),
            "entry_ready": entry_low <= price <= entry_high,
            "reason": (
                "回踩支撑后再做多"
                if side == "LONG"
                else "反弹阻力后再做空"
            ),
        }

    def _legacy_position_advice(self, action: str, confidence: int, position: dict,
                         price: float, atr: float, supports: list, resistances: list) -> dict:
        """针对用户实际持仓给出 持有/加仓/减仓/平仓 建议"""
        side = position["side"]  # LONG / SHORT
        entry = float(position["entry_price"])
        pnl = float(position.get("unrealized_pnl", 0))
        lev = float(position.get("leverage", 1) or 1)
        liq = float(position.get("liquidation_price", 0) or 0)

        # 价格相对开仓价的盈亏%(不含杠杆) 与 保证金收益率(含杠杆)
        if side == "LONG":
            pnl_pct = (price - entry) / entry * 100 if entry else 0
        else:
            pnl_pct = (entry - price) / entry * 100 if entry else 0
        roi_pct = pnl_pct * lev

        side_cn = "多单" if side == "LONG" else "空单"
        # 持仓方向与技术信号是否共振
        aligned = (side == "LONG" and action == "偏多") or (side == "SHORT" and action == "偏空")
        against = (side == "LONG" and action == "偏空") or (side == "SHORT" and action == "偏多")

        if against and confidence >= 60:
            verdict, cls = "减仓/平仓", "danger"
            text = f"技术面{action}(置信{confidence}%)与你的{side_cn}方向相反，趋势对你不利。"
            if pnl_pct > 0:
                text += f"当前仍浮盈{pnl_pct:.2f}%(杠杆后约{roi_pct:+.1f}%)，建议趁机减仓或平仓锁利，避免利润回吐。"
            else:
                text += f"当前浮亏{abs(pnl_pct):.2f}%(杠杆后约{roi_pct:+.1f}%)，建议严控风险，反弹乏力则果断止损离场。"
        elif aligned and confidence >= 60:
            verdict, cls = "持有", "good"
            text = f"技术面{action}(置信{confidence}%)与你的{side_cn}方向一致，趋势站在你这边，可继续持有。"
            if pnl_pct > 0:
                text += f"当前浮盈{pnl_pct:.2f}%(杠杆后约{roi_pct:+.1f}%)，建议上移止损保护利润。"
            else:
                text += f"当前浮亏{abs(pnl_pct):.2f}%(杠杆后约{roi_pct:+.1f}%)，但趋势有利，可耐心持有等待回归。"
        else:
            verdict, cls = "持有观望", "neutral"
            text = f"技术面{action}(置信{confidence}%)，与你的{side_cn}无明确共振，方向尚不明朗。"
            if pnl_pct > 0:
                text += f"浮盈{pnl_pct:.2f}%(杠杆后约{roi_pct:+.1f}%)，建议设好止盈止损、观望为主。"
            else:
                text += f"浮亏{abs(pnl_pct):.2f}%(杠杆后约{roi_pct:+.1f}%)，建议控制仓位，跌破关键位坚决止损。"

        # 止损 + 分批止盈(阶梯减仓): 以ATR(波动率)计算合理距离, 避免贴现价一碰就触发
        ref = []
        scaled_tp = []
        if atr and atr > 0 and price > 0:
            stop_dist = atr * 1.5    # 止损: 1.5倍ATR
            tp1_dist = atr * 2.0     # 目标1: 2倍ATR -> 减仓30%
            tp2_dist = atr * 3.5     # 目标2: 3.5倍ATR -> 减仓50%, 剩余跟踪
            if side == "SHORT":
                stop = price + stop_dist
                tp1 = price - tp1_dist
                tp2 = price - tp2_dist
                ref.append(f"止损 {stop:.6g}(现价上方{stop_dist/price*100:.1f}%，突破说明趋势反转应离场)")
            else:
                stop = price - stop_dist
                tp1 = price + tp1_dist
                tp2 = price + tp2_dist
                ref.append(f"止损 {stop:.6g}(现价下方{stop_dist/price*100:.1f}%，跌破说明趋势反转应离场)")
            scaled_tp = [
                {"label": "目标1·减30%", "price": round(tp1, 8), "pct": round(tp1_dist / price * 100, 2), "close": 0.3},
                {"label": "目标2·减50%", "price": round(tp2, 8), "pct": round(tp2_dist / price * 100, 2), "close": 0.5},
                {"label": "剩余·跟踪止损", "price": None, "pct": None, "close": 0.2},
            ]
            ref.append(f"分批止盈 {tp1:.6g}减30% → {tp2:.6g}减50% → 剩余20%跟踪趋势(让利润奔跑)")
        else:
            # 无ATR时退回关键价位
            if side == "SHORT":
                if resistances:
                    ref.append(f"止损参考: 最近阻力 {resistances[0]:.6g} 上方")
                if supports:
                    ref.append(f"止盈参考: 最近支撑 {supports[0]:.6g}")
            else:
                if supports:
                    ref.append(f"止损参考: 最近支撑 {supports[0]:.6g} 下方")
                if resistances:
                    ref.append(f"止盈参考: 最近阻力 {resistances[0]:.6g}")
        if ref:
            text += " " + "；".join(ref) + "。"

        return {
            "verdict": verdict, "cls": cls, "text": text,
            "pnl_pct": round(pnl_pct, 2), "roi_pct": round(roi_pct, 1),
            "liq": liq, "scaled_tp": scaled_tp,
        }

    def _position_advice(self, action: str, confidence: int, position: dict,
                         price: float, atr: float, supports: list, resistances: list,
                         htf_trend: int = 0, management: dict = None) -> dict:
        """Return a trend-aware holding plan instead of a short-term exit call."""
        cfg = {
            "reduce_confidence": 75,
            "full_exit_confidence": 80,
            "partial_close_pct": 30,
            "trailing_atr": 3.0,
            "lock_profit_atr": 0.25,
        }
        cfg.update(management or {})

        side = position["side"]
        entry = float(position["entry_price"])
        lev = float(position.get("leverage", 1) or 1)
        liq = float(position.get("liquidation_price", 0) or 0)
        is_long = side == "LONG"
        pnl_pct = ((price - entry) if is_long else (entry - price)) / entry * 100 if entry else 0
        roi_pct = pnl_pct * lev
        atr_pct = atr / entry * 100 if atr > 0 and entry > 0 else 0

        aligned = (is_long and action == "偏多") or (not is_long and action == "偏空")
        against = (is_long and action == "偏空") or (not is_long and action == "偏多")
        htf_aligned = (is_long and htf_trend > 0) or (not is_long and htf_trend < 0)
        htf_against = (is_long and htf_trend < 0) or (not is_long and htf_trend > 0)
        partial_pct = max(10, min(50, int(float(cfg["partial_close_pct"]))))

        trailing_stop = None
        scaled_tp = []
        references = []
        if atr > 0 and entry > 0:
            configured_hard_pct = max(0.5, float(cfg.get("hard_stop_pct", 4)))
            margin_cap_pct = float(cfg.get("max_margin_loss_pct", 45)) / max(1.0, lev)
            effective_hard_pct = min(configured_hard_pct, margin_cap_pct)
            hard_dist = entry * effective_hard_pct / 100
            min_dist = entry * max(0.1, float(cfg.get("min_stop_pct", 1.8))) / 100
            atr_dist = atr * max(1.0, float(cfg.get("initial_stop_atr", 3)))
            soft_dist = min(max(min_dist, atr_dist), hard_dist * 0.85)
            initial_stop = entry - soft_dist if is_long else entry + soft_dist
            hard_stop = entry - hard_dist if is_long else entry + hard_dist
            # 浮亏仓位的原始止损可能已经落到现价另一侧，前端会显示成
            # “已经穿过价格”的无效保护线。AI建议只读修正为现价外侧的
            # 紧急保护参考线，执行引擎仍使用自己的退出逻辑。
            if pnl_pct <= 0:
                live_buffer = max(atr * 0.75, price * 0.005)
                if is_long:
                    initial_stop = min(initial_stop, price - live_buffer)
                else:
                    initial_stop = max(initial_stop, price + live_buffer)
            if pnl_pct > 0:
                protected = entry + atr * float(cfg["lock_profit_atr"]) if is_long else entry - atr * float(cfg["lock_profit_atr"])
                dynamic = price - atr * float(cfg["trailing_atr"]) if is_long else price + atr * float(cfg["trailing_atr"])
                trailing_stop = max(protected, dynamic) if is_long else min(protected, dynamic)
            else:
                trailing_stop = initial_stop

            tp1_atr = float(cfg.get("tp1_atr", 3))
            tp2_atr = float(cfg.get("tp2_atr", 6))
            tp1 = entry + atr * tp1_atr if is_long else entry - atr * tp1_atr
            tp2 = entry + atr * tp2_atr if is_long else entry - atr * tp2_atr
            references.append(f"波段结构线 {initial_stop:.6g}")
            references.append(f"硬风险线 {hard_stop:.6g}")
            references.append(f"跟踪保护线 {trailing_stop:.6g}")
            scaled_tp = [
                {"label": f"目标1·减{partial_pct}%", "price": round(tp1, 8),
                 "pct": round(abs(tp1 - entry) / entry * 100, 2), "close": partial_pct / 100},
                {"label": f"目标2·减{partial_pct}%", "price": round(tp2, 8),
                 "pct": round(abs(tp2 - entry) / entry * 100, 2), "close": partial_pct / 100},
                {"label": "剩余仓位·跟踪止损", "price": round(trailing_stop, 8),
                 "pct": None, "close": max(0, 1 - partial_pct / 50)},
            ]

        if against and htf_against and confidence >= int(cfg["full_exit_confidence"]):
            verdict, cls, management_action = "平仓", "danger", "exit"
            text = (
                f"短线{action}({confidence}%)与高周期趋势同时反向，持仓趋势确认失效。"
                "建议按跟踪止损执行平仓，避免把已实现浮盈回吐。"
            )
        elif against and htf_aligned:
            extreme_countertrend = (
                confidence >= int(cfg["reduce_confidence"]) + 10
                and pnl_pct >= max(atr_pct * 2, 0.8)
            )
            if extreme_countertrend:
                verdict, cls, management_action = f"减仓{partial_pct}% + 持有", "neutral", "reduce"
                text = (
                    f"短线{action}很强({confidence}%)，但高周期趋势仍与{side}一致。"
                    f"可先锁定{partial_pct}%利润，其余仓位继续持有并执行跟踪止损。"
                )
            else:
                verdict, cls, management_action = "持有 + 上移止损", "good", "trail"
                text = (
                    f"短线出现{action}({confidence}%)回调信号，但高周期趋势仍支持你的{side}。"
                    "不做全平，保留仓位，让趋势延续；只上移止损保护已有利润。"
                )
        elif against and confidence >= int(cfg["reduce_confidence"]) and pnl_pct > 0:
            verdict, cls, management_action = f"减仓{partial_pct}% + 跟踪", "neutral", "reduce"
            text = (
                f"短线{action}({confidence}%)且高周期未提供同向趋势支持。"
                f"建议减仓{partial_pct}%锁定浮盈，保留其余仓位并跟踪止损。"
            )
        elif aligned and confidence >= 60:
            verdict, cls, management_action = "持有 + 跟踪止损", "good", "trail"
            text = f"短线与高周期没有出现反向确认，继续持有{side}，并用跟踪止损保护利润。"
        else:
            verdict, cls, management_action = "持有观望 + 止损保护", "neutral", "hold"
            text = "多空信号尚未形成高周期反转确认，维持仓位观察，止损随价格和波动上移。"

        if pnl_pct > 0:
            text += f" 当前浮盈{pnl_pct:.2f}%（杠杆后约{roi_pct:+.1f}%）。"
        if references:
            text += " " + "；".join(references) + "。"

        return {
            "verdict": verdict,
            "cls": cls,
            "text": text,
            "pnl_pct": round(pnl_pct, 2),
            "roi_pct": round(roi_pct, 1),
            "liq": liq,
            "scaled_tp": scaled_tp,
            "trailing_stop": round(trailing_stop, 8) if trailing_stop else None,
            "management_action": management_action,
            "suggested_reduce_pct": partial_pct if management_action == "reduce" else 0,
            "htf_trend": htf_trend,
        }

    def analyze(self, closes: np.ndarray, highs: np.ndarray = None,
                lows: np.ndarray = None, volumes: np.ndarray = None,
                funding_rate: float = None, htf_closes: np.ndarray = None,
                news: list = None, sentiment: dict = None,
                position: dict = None, position_management: dict = None) -> dict:
        if len(closes) < 60:
            return {"summary": "数据不足，等待K线积累...", "sections": [], "action": "观望", "confidence": 0}

        if highs is None: highs = closes
        if lows is None: lows = closes
        if volumes is None: volumes = np.ones_like(closes)

        price = float(closes[-1])
        sections = []
        bull_points, bear_points = 0, 0

        # ===== 1. 趋势判断 =====
        direction, strength = trend_strength(closes)
        ribbon = detect_ema_ribbon(closes)
        htf_dir = ""
        htf_ribbon = 0
        if htf_closes is not None and len(htf_closes) >= 55:
            htf_ribbon = detect_ema_ribbon(htf_closes)
            htf_dir = "多头" if htf_ribbon > 0 else "空头" if htf_ribbon < 0 else "混乱"

        trend_text = f"当前处于{direction}趋势，强度{strength}/100。"
        if ribbon > 0:
            trend_text += "EMA丝带多头排列(8>13>21>55)，短线动能向上。"
            bull_points += 2
        elif ribbon < 0:
            trend_text += "EMA丝带空头排列，短线动能向下。"
            bear_points += 2
        else:
            trend_text += "均线纠缠，方向不明。"
        if htf_dir:
            trend_text += f"高时间框架趋势: {htf_dir}。"
            if htf_dir == "多头": bull_points += 1
            elif htf_dir == "空头": bear_points += 1
        sections.append({"title": "趋势判断", "icon": "trend", "text": trend_text})

        # ===== 2. 动量指标 =====
        rsi = calc_rsi(closes, 14)[-1]
        stoch_k, stoch_d = calc_stoch_rsi(closes)
        macd_line, signal_line, histogram = calc_macd(closes)
        mom_parts = []
        if rsi > 70:
            mom_parts.append(f"RSI={rsi:.0f}超买区，警惕回调"); bear_points += 1
        elif rsi < 30:
            mom_parts.append(f"RSI={rsi:.0f}超卖区，存在反弹需求"); bull_points += 1
        else:
            mom_parts.append(f"RSI={rsi:.0f}中性区")
        if stoch_k[-1] > stoch_d[-1]:
            mom_parts.append("StochRSI金叉向上"); bull_points += 1
        else:
            mom_parts.append("StochRSI死叉向下"); bear_points += 1
        if histogram[-1] > 0:
            mom_parts.append("MACD柱为正(多头动量)")
            if histogram[-1] > histogram[-2]: mom_parts.append("且动量增强"); bull_points += 1
        else:
            mom_parts.append("MACD柱为负(空头动量)")
            if histogram[-1] < histogram[-2]: mom_parts.append("且动量减弱"); bear_points += 1
        div = detect_rsi_divergence(closes, calc_rsi(closes, 14))
        if div == 1:
            mom_parts.append("检测到RSI看涨背离(重要反转信号)"); bull_points += 2
        elif div == -1:
            mom_parts.append("检测到RSI看跌背离(重要反转信号)"); bear_points += 2
        sections.append({"title": "动量指标", "icon": "momentum", "text": "；".join(mom_parts) + "。"})

        # ===== 3. 关键价位 =====
        supports, resistances = find_support_resistance(highs, lows, closes)
        bb_upper, bb_mid, bb_lower = calc_bollinger(closes)
        vwap = calc_vwap(highs, lows, closes, volumes)[-1]
        lvl_parts = []
        if resistances:
            lvl_parts.append("上方阻力: " + " / ".join(f"{r:.6g}" for r in resistances))
        if supports:
            lvl_parts.append("下方支撑: " + " / ".join(f"{s:.6g}" for s in supports))
        lvl_parts.append(f"VWAP={vwap:.6g}({'价格在其上方,偏多' if price > vwap else '价格在其下方,偏空'})")
        lvl_parts.append(f"布林带: 上轨{bb_upper[-1]:.6g} / 中轨{bb_mid[-1]:.6g} / 下轨{bb_lower[-1]:.6g}")
        if price > vwap: bull_points += 1
        else: bear_points += 1
        sections.append({"title": "关键价位", "icon": "levels", "text": "；".join(lvl_parts) + "。"})

        # ===== 4. 量价与形态 =====
        vol_parts = []
        if detect_volume_spike(volumes):
            vol_parts.append("成交量异常放大(>2倍均量)，关注资金动向")
        else:
            vol_parts.append("成交量正常")
        obv = calc_obv(closes, volumes)
        obv_ma = calc_ma(obv, 10)
        if obv[-1] > obv_ma[-1]:
            vol_parts.append("OBV在均线上方(资金净流入)"); bull_points += 1
        else:
            vol_parts.append("OBV在均线下方(资金净流出)"); bear_points += 1
        pattern = detect_pattern(closes, highs, lows)
        if pattern:
            vol_parts.append(f"K线形态: {pattern}")
        sections.append({"title": "量价形态", "icon": "volume", "text": "；".join(vol_parts) + "。"})

        # ===== 5. 资金费率 =====
        if funding_rate is not None:
            fr_text = f"当前资金费率 {funding_rate*100:.4f}%。"
            if funding_rate > 0.05:
                fr_text += "费率过高，多头拥挤，存在多头挤压(回调)风险。"
                bear_points += 1
            elif funding_rate < -0.03:
                fr_text += "费率为负，空头拥挤，存在空头挤压(反弹)机会。"
                bull_points += 1
            else:
                fr_text += "费率正常，市场情绪中性。"
            sections.append({"title": "资金费率", "icon": "funding", "text": fr_text})

        # ===== 6. 波动率 =====
        atr = calc_atr(highs, lows, closes, 14)[-1]
        atr_pct = atr / price * 100
        vol_text = f"ATR(14)={atr:.6g}，约为价格的{atr_pct:.2f}%。"
        if atr_pct > 2:
            vol_text += "波动剧烈，建议减小仓位、放宽止损。"
        elif atr_pct < 0.5:
            vol_text += "波动极低，可能在酝酿大行情。"
        else:
            vol_text += "波动适中。"
        sections.append({"title": "波动率", "icon": "volatility", "text": vol_text})

        # ===== 7. 新闻情绪 =====
        if news:
            from news_fetcher import NewsFetcher
            nf_summary = NewsFetcher().get_sentiment_summary.__func__  # noqa
            # 直接用传入news计算
            bullish_n = sum(1 for n in news if n.get("sentiment", 0) > 0)
            bearish_n = sum(1 for n in news if n.get("sentiment", 0) < 0)
            total_score = sum(n.get("sentiment", 0) for n in news)
            news_parts = [f"抓取到{len(news)}条相关新闻: 看多{bullish_n}条 / 看空{bearish_n}条 / 中性{len(news)-bullish_n-bearish_n}条"]
            if bullish_n > bearish_n * 1.5:
                news_parts.append("新闻面整体偏多"); bull_points += 2
            elif bearish_n > bullish_n * 1.5:
                news_parts.append("新闻面整体偏空"); bear_points += 2
            else:
                news_parts.append("新闻面中性")
            # 列出情绪最强的前3条
            top_news = sorted(news, key=lambda x: -abs(x.get("sentiment", 0)))[:3]
            for n in top_news:
                tag = "多" if n.get("sentiment", 0) > 0 else "空" if n.get("sentiment", 0) < 0 else "中"
                news_parts.append(f"[{n.get('source','')}/{tag}] {n.get('title','')[:60]}")
            sections.append({"title": "新闻情绪", "icon": "news", "text": "；".join(news_parts), "news_list": top_news})

        # ===== 8. 市场情绪数据 =====
        if sentiment:
            sent_parts = []
            fg = sentiment.get("fear_greed", {})
            if fg.get("value") is not None:
                sent_parts.append(f"恐惧贪婪指数: {fg['value']} ({fg.get('label','')})")
                if fg["value"] <= 25: bull_points += 1  # 极度恐慌逆向看多
                elif fg["value"] >= 75: bear_points += 1  # 极度贪婪逆向看空
                if fg.get("interpretation"): sent_parts.append(fg["interpretation"])
            ls = sentiment.get("long_short", {})
            if ls.get("ratio"):
                sent_parts.append(f"散户多空比: {ls['ratio']} (多{ls.get('long_pct',50)}%/空{ls.get('short_pct',50)}%)")
                if ls.get("interpretation"): sent_parts.append(ls["interpretation"])
            tt = sentiment.get("top_trader", {})
            if tt.get("ratio"):
                sent_parts.append(f"大户持仓多空比: {tt['ratio']}")
                if tt.get("interpretation"): sent_parts.append(tt["interpretation"])
            ta = sentiment.get("top_trader_account", {})
            if ta.get("ratio"):
                sent_parts.append(f"大户账户多空比: {ta['ratio']}")
                if ta.get("interpretation"): sent_parts.append(ta["interpretation"])
            oi = sentiment.get("open_interest", {})
            if oi.get("value_usd"):
                sent_parts.append(
                    f"持仓量: ${oi['value_usd']/1e6:.1f}M "
                    f"(1h {oi.get('change_1h_pct',0):+.1f}% / 24h {oi.get('change_24h_pct',0):+.1f}%)")
                if oi.get("interpretation"): sent_parts.append(oi["interpretation"])
            smart = sentiment.get("smart_money", {})
            smart_score = float(smart.get("score", 0))
            if smart:
                sent_parts.append(f"聪明钱综合分: {smart_score:+.1f} ({smart.get('label','')})")
                if smart_score >= 32:
                    bull_points += 2
                elif smart_score >= 18:
                    bull_points += 1
                elif smart_score <= -32:
                    bear_points += 2
                elif smart_score <= -18:
                    bear_points += 1
                if smart.get("interpretation"):
                    sent_parts.append(smart["interpretation"])
            if sent_parts:
                sections.append({"title": "市场情绪数据", "icon": "sentiment", "text": "；".join(sent_parts) + "。"})

        # ===== 综合建议 =====
        total = bull_points + bear_points
        if total == 0:
            action, confidence = "观望", 30
        else:
            bull_ratio = bull_points / total
            if bull_ratio >= 0.65:
                action = "偏多"
                confidence = min(int(50 + bull_ratio * 40), 90)
            elif bull_ratio <= 0.35:
                action = "偏空"
                confidence = min(int(50 + (1 - bull_ratio) * 40), 90)
            else:
                action = "观望"
                confidence = 40

        # 生成摘要
        summary_parts = [f"{direction}趋势(强度{strength})"]
        if action == "偏多":
            summary_parts.append(f"综合{bull_points}个看多信号 vs {bear_points}个看空信号，短线偏多")
        elif action == "偏空":
            summary_parts.append(f"综合{bear_points}个看空信号 vs {bull_points}个看多信号，短线偏空")
        else:
            summary_parts.append("多空信号交织，建议等待方向明确")
        if pattern:
            summary_parts.append(pattern)

        # 操作建议(持仓优先: 有持仓则给出持仓专属建议)
        entry_plan = self._build_entry_plan(
            action, confidence, price, atr, supports, resistances, htf_ribbon
        )
        position_advice = None
        if position:
            position_advice = self._position_advice(
                action, confidence, position, price, atr, supports, resistances,
                htf_ribbon, position_management)
            advice = position_advice["text"]
        elif action == "偏多":
            advice = (
                f"等待回踩入场区后再做多，避免直接追价。"
                f"止损参考{entry_plan['stop_loss'] or '--'}，"
                f"目标1 {entry_plan['tp1'] or '--'}，目标2 {entry_plan['tp2'] or '--'}。"
            )
        elif action == "偏空":
            advice = (
                f"等待反弹入场区后再做空，避免直接追价。"
                f"止损参考{entry_plan['stop_loss'] or '--'}，"
                f"目标1 {entry_plan['tp1'] or '--'}，目标2 {entry_plan['tp2'] or '--'}。"
            )
        else:
            advice = "当前信号不明确，建议空仓观望，等待趋势确认后再入场。切忌追涨杀跌。"

        if position is None and entry_plan["status"] == "WAIT":
            advice = "当前没有满足风险收益比的入场结构，建议等待新的收盘K线确认。"
        elif position is None and entry_plan["status"] == "WAIT_CONFIRMATION":
            advice = "高周期方向未确认，先等待共振后再考虑入场。"
        if position is None and entry_plan["status"] in ("READY", "WAIT_PULLBACK", "WAIT_CONFIRMATION"):
            advice = (
                f"{advice} 入场区间 {entry_plan['entry_low']} - {entry_plan['entry_high']}，"
                f"建议价 {entry_plan['entry_price']}，R:R 约 {entry_plan['rr']}。"
            )

        sections.append({"title": "操作建议", "icon": "advice", "text": advice})

        return {
            "summary": "，".join(summary_parts) + "。",
            "sections": sections,
            "action": action,
            "confidence": confidence,
            "bull_points": bull_points,
            "bear_points": bear_points,
            "price": price,
            "atr": float(atr),
            "supports": supports,
            "resistances": resistances,
            "entry_plan": entry_plan,
            "position": position,
            "position_advice": position_advice,
        }
