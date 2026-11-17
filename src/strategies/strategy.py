"""高胜率策略引擎 v2 - 多因子加权评分 + 多时间框架确认"""
import numpy as np
import pandas as pd


# ========== 指标计算 ==========

def calc_ma(closes: np.ndarray, period: int) -> np.ndarray:
    return pd.Series(closes).rolling(period).mean().values

def calc_ema(closes: np.ndarray, period: int) -> np.ndarray:
    return pd.Series(closes).ewm(span=period, adjust=False).mean().values

def calc_rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    delta = np.diff(closes, prepend=closes[0])
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).ewm(alpha=1/period, min_periods=period).mean().values
    avg_loss = pd.Series(loss).ewm(alpha=1/period, min_periods=period).mean().values
    rs = np.divide(avg_gain, avg_loss, out=np.ones_like(avg_gain), where=avg_loss != 0)
    return 100 - (100 / (1 + rs))

def calc_macd(closes: np.ndarray, fast=12, slow=26, signal=9):
    ema_fast = calc_ema(closes, fast)
    ema_slow = calc_ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calc_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calc_bollinger(closes: np.ndarray, period=20, std_mult=2):
    s = pd.Series(closes)
    mid = s.rolling(period).mean().values
    std = s.rolling(period).std().values
    return mid + std_mult * std, mid, mid - std_mult * std

def calc_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period=14) -> np.ndarray:
    tr = np.maximum(highs[1:] - lows[1:],
                    np.maximum(np.abs(highs[1:] - closes[:-1]),
                               np.abs(lows[1:] - closes[:-1])))
    tr = np.concatenate([[highs[0] - lows[0]], tr])
    return pd.Series(tr).ewm(alpha=1/period, min_periods=period).mean().values

def calc_vwap(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    typical = (highs + lows + closes) / 3
    cum_tp_vol = np.cumsum(typical * volumes)
    cum_vol = np.cumsum(volumes)
    return np.divide(cum_tp_vol, cum_vol, out=typical, where=cum_vol != 0)

def calc_obv(closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    direction = np.sign(np.diff(closes, prepend=closes[0]))
    return np.cumsum(direction * volumes)

def calc_stoch_rsi(closes: np.ndarray, rsi_period=14, stoch_period=14, k_period=3, d_period=3):
    rsi = calc_rsi(closes, rsi_period)
    rsi_s = pd.Series(rsi)
    lowest = rsi_s.rolling(stoch_period).min().values
    highest = rsi_s.rolling(stoch_period).max().values
    denom = highest - lowest
    stoch_rsi = np.divide(rsi - lowest, denom, out=np.zeros_like(rsi), where=denom != 0) * 100
    k = pd.Series(stoch_rsi).rolling(k_period).mean().values
    d = pd.Series(k).rolling(d_period).mean().values
    return k, d


# ========== 信号检测 ==========

def detect_rsi_divergence(closes: np.ndarray, rsi: np.ndarray, lookback=20) -> int:
    """RSI背离检测: 1=看涨背离, -1=看跌背离, 0=无"""
    if len(closes) < lookback + 5:
        return 0
    recent_c = closes[-lookback:]
    recent_r = rsi[-lookback:]
    mid = lookback // 2

    # 看涨背离: 价格创新低但RSI没创新低
    price_low1 = np.min(recent_c[:mid])
    price_low2 = np.min(recent_c[mid:])
    rsi_low1 = np.min(recent_r[:mid])
    rsi_low2 = np.min(recent_r[mid:])
    if price_low2 < price_low1 and rsi_low2 > rsi_low1 and rsi_low2 < 45:
        return 1

    # 看跌背离: 价格创新高但RSI没创新高
    price_high1 = np.max(recent_c[:mid])
    price_high2 = np.max(recent_c[mid:])
    rsi_high1 = np.max(recent_r[:mid])
    rsi_high2 = np.max(recent_r[mid:])
    if price_high2 > price_high1 and rsi_high2 < rsi_high1 and rsi_high2 > 55:
        return -1

    return 0

def detect_volume_spike(volumes: np.ndarray, threshold=2.0) -> bool:
    """成交量异常放大"""
    if len(volumes) < 21:
        return False
    avg_vol = np.mean(volumes[-21:-1])
    return bool(avg_vol > 0 and volumes[-1] > avg_vol * threshold)

def detect_ema_ribbon(closes: np.ndarray) -> int:
    """EMA丝带趋势: 多头排列=1, 空头排列=-1, 混乱=0"""
    ema8 = calc_ema(closes, 8)[-1]
    ema13 = calc_ema(closes, 13)[-1]
    ema21 = calc_ema(closes, 21)[-1]
    ema55 = calc_ema(closes, 55)[-1]
    if ema8 > ema13 > ema21 > ema55:
        return 1
    if ema8 < ema13 < ema21 < ema55:
        return -1
    return 0


def detect_volume_price_divergence(closes: np.ndarray, volumes: np.ndarray, lookback=10) -> int:
    """量价背离(领先信号): 价格创新高但成交量递减=上涨乏力(-1); 价格创新低但量缩=下跌动能衰竭(+1)"""
    if len(closes) < lookback + 5 or len(volumes) < lookback + 5:
        return 0
    recent_c = closes[-lookback:]
    recent_v = volumes[-lookback:]
    half = lookback // 2

    # 看跌量价背离: 后半段价格更高, 但成交量更低
    price_higher = np.max(recent_c[half:]) > np.max(recent_c[:half])
    vol_lower = np.mean(recent_v[half:]) < np.mean(recent_v[:half]) * 0.75
    if price_higher and vol_lower:
        return -1

    # 看涨量价背离: 后半段价格更低, 但成交量萎缩(抛压衰竭)
    price_lower = np.min(recent_c[half:]) < np.min(recent_c[:half])
    vol_shrink = np.mean(recent_v[half:]) < np.mean(recent_v[:half]) * 0.75
    if price_lower and vol_shrink:
        return 1

    return 0


def detect_momentum_deceleration(closes: np.ndarray, period=5) -> int:
    """动量衰减(领先信号): ROC连续下降=上涨动能衰竭(-1); ROC连续上升=下跌动能衰竭(+1)"""
    if len(closes) < period + 4:
        return 0
    # 计算最近4个ROC值
    rocs = []
    for i in range(4):
        idx = len(closes) - 1 - i
        if idx - period >= 0:
            roc = (closes[idx] - closes[idx - period]) / closes[idx - period] * 100
            rocs.append(roc)
    if len(rocs) < 4:
        return 0
    rocs = rocs[::-1]  # 时间顺序: 旧→新

    # 上涨动量衰减: ROC为正但连续下降(涨得越来越慢)
    if rocs[-1] > 0 and rocs[-1] < rocs[-2] < rocs[-3]:
        return -1
    # 下跌动量衰减: ROC为负但连续上升(跌得越来越慢)
    if rocs[-1] < 0 and rocs[-1] > rocs[-2] > rocs[-3]:
        return 1
    return 0


def detect_bb_rejection(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray,
                        bb_upper: np.ndarray, bb_lower: np.ndarray) -> int:
    """布林带拒绝(领先信号): 触碰上轨+收阴=做空(-1); 触碰下轨+收阳=做多(+1)"""
    if len(closes) < 3:
        return 0
    c = closes[-1]
    o = closes[-2]  # 用前一根open近似(实际应该用open数组)
    body_bearish = c < o  # 阴线
    body_bullish = c > o  # 阳线

    # 上轨拒绝: 最高价触及/突破上轨, 但收盘回落(阴线)
    if highs[-1] >= bb_upper[-1] and body_bearish and c < bb_upper[-1]:
        return -1
    # 下轨拒绝: 最低价触及/突破下轨, 但收盘回升(阳线)
    if lows[-1] <= bb_lower[-1] and body_bullish and c > bb_lower[-1]:
        return 1
    return 0


# ========== 二次波段反转(双顶/双底) ==========

def find_swing_pivots(highs: np.ndarray, lows: np.ndarray, k: int = 2, max_age: int = 120):
    """分形波段点检测: 高点两侧k根均更低=波段高点; 低点两侧k根均更高=波段低点"""
    n = len(highs)
    pivot_highs, pivot_lows = [], []
    start = max(k, n - max_age)
    for i in range(start, n - k):
        window_h = highs[i - k:i + k + 1]
        window_l = lows[i - k:i + k + 1]
        if highs[i] == np.max(window_h) and (window_h == highs[i]).sum() == 1:
            pivot_highs.append((i, float(highs[i])))
        if lows[i] == np.min(window_l) and (window_l == lows[i]).sum() == 1:
            pivot_lows.append((i, float(lows[i])))
    return pivot_highs, pivot_lows


def detect_second_swing_reversal(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray,
                                 rsi: np.ndarray, atr_value: float) -> tuple:
    """
    二次波段高点/低点反转(高胜率结构信号):
    - 双顶: 价格两次冲击同一高点区域(二次波段高点), 回落拒绝 -> 做空
    - 双底: 价格两次下探同一低点区域(二次波段低点), 反弹拒绝 -> 做多
    90%行情无趋势延续, 二次波段后的反向是主要盈利结构。
    返回 (得分, info): 基础±20, 颈线突破+10, RSI背离+5
    """
    n = len(closes)
    if n < 60 or atr_value <= 0:
        return 0, {}
    pivot_highs, pivot_lows = find_swing_pivots(highs, lows)

    # ---- 双顶(二次波段高点)做空 ----
    if len(pivot_highs) >= 2:
        i1, h1 = pivot_highs[-2]
        i2, h2 = pivot_highs[-1]
        age = n - 1 - i2            # 第二顶距今K线数
        gap = i2 - i1               # 两顶间隔
        neck = float(np.min(lows[i1:i2 + 1]))   # 两顶之间的谷底=颈线
        wave_depth = h1 - neck        # 第一波回调深度
        c = float(closes[-1])
        fresh = 2 <= age <= 10
        near = abs(h2 - h1) <= 0.9 * atr_value and h2 >= h1 - 0.5 * atr_value
        deep = wave_depth >= 1.0 * atr_value
        rejected = c < h2 - 0.2 * atr_value and c < float(closes[i2]) and closes[-1] <= closes[-2]
        if fresh and near and deep and rejected:
            pts = -20
            detail = [f"二次波段顶{i2 - i1}根内二次冲顶被拒"]
            if c < neck:
                pts -= 10
                detail.append("颈线已破")
            if rsi is not None and rsi[i2] < rsi[i1] - 3:
                pts -= 5
                detail.append("顶背离")
            return pts, {"pattern": "双顶", "label": "二次波段顶·做空" + "·" + "·".join(detail),
                         "neck": round(neck, 8), "p1": round(h1, 8), "p2": round(h2, 8)}

    # ---- 双底(二次波段低点)做多 ----
    if len(pivot_lows) >= 2:
        i1, l1 = pivot_lows[-2]
        i2, l2 = pivot_lows[-1]
        age = n - 1 - i2
        gap = i2 - i1
        neck = float(np.max(highs[i1:i2 + 1]))  # 两底之间的反弹高点=颈线
        wave_depth = neck - l1
        c = float(closes[-1])
        fresh = 2 <= age <= 10
        near = abs(l2 - l1) <= 0.9 * atr_value and l2 <= l1 + 0.5 * atr_value
        deep = wave_depth >= 1.0 * atr_value
        rejected = c > l2 + 0.2 * atr_value and c > float(closes[i2]) and closes[-1] >= closes[-2]
        if fresh and near and deep and rejected:
            pts = 20
            detail = [f"二次波段底{i2 - i1}根内二次下探被拒"]
            if c > neck:
                pts += 10
                detail.append("颈线已破")
            if rsi is not None and rsi[i2] > rsi[i1] + 3:
                pts += 5
                detail.append("底背离")
            return pts, {"pattern": "双底", "label": "二次波段底·做多" + "·" + "·".join(detail),
                         "neck": round(neck, 8), "p1": round(l1, 8), "p2": round(l2, 8)}

    return 0, {}


def detect_support_resistance(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray,
                              atr_value: float, lookback: int = 120) -> dict:
    """支撑/压力位: 波段高低点按0.5ATR聚类, 触点越多越强。
    返回最近的支撑(价格下方)、压力(价格上方)及其强度。"""
    n = len(closes)
    if n < 30 or atr_value <= 0:
        return {"support": None, "support_touches": 0,
                "resistance": None, "resistance_touches": 0, "levels": []}
    pivot_highs, pivot_lows = find_swing_pivots(highs, lows, k=2, max_age=lookback)
    prices = sorted(p for _, p in pivot_highs + pivot_lows)
    if not prices:
        prices = sorted([float(np.max(highs[-20:])), float(np.min(lows[-20:]))])
    clusters = []
    for p in prices:
        if clusters and p - clusters[-1]["price"] <= 0.5 * atr_value:
            c = clusters[-1]
            c["price"] = (c["price"] * c["touches"] + p) / (c["touches"] + 1)
            c["touches"] += 1
        else:
            clusters.append({"price": p, "touches": 1})
    c_now = float(closes[-1])
    below = [c for c in clusters if c["price"] < c_now - 0.1 * atr_value]
    above = [c for c in clusters if c["price"] > c_now + 0.1 * atr_value]
    support = max(below, key=lambda x: x["price"]) if below else None
    resistance = min(above, key=lambda x: x["price"]) if above else None
    if support is None:
        support = {"price": float(np.min(lows[-20:])), "touches": 1}
    if resistance is None:
        resistance = {"price": float(np.max(highs[-20:])), "touches": 1}
    return {
        "support": round(support["price"], 8),
        "support_touches": support["touches"],
        "resistance": round(resistance["price"], 8),
        "resistance_touches": resistance["touches"],
        "levels": [round(c["price"], 8) for c in clusters],
    }


def detect_main_force_intent(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray,
                             volumes: np.ndarray, opens: np.ndarray = None,
                             atr_value: float = 0) -> dict:
    """主力意图推断(量价结构):
    洗盘 = 缩量回调+关键位不破+下影承接, 主力未走;
    出货 = 高位放量滞涨+长上影+阴线放量, 主力派发;
    拉升 = 上行且无派发迹象; 观望 = 结构不明。
    返回 intent/confidence/reasons/dist_pts/shake_pts(后两者供衍生品数据二次修正)。"""
    n = len(closes)
    if n < 60 or atr_value <= 0:
        return {"intent": "观望", "confidence": 0, "reasons": [], "dist_pts": 0, "shake_pts": 0}
    if opens is None:
        opens = np.concatenate([[closes[-25]], closes[-25:-1]]) if n >= 25 else closes
        opens = opens[-min(24, n):]
    w = min(24, n - 1)
    if len(opens) < w:
        opens = closes[-w - 1:-1]
    c = closes[-w:]
    h = highs[-w:]
    l = lows[-w:]
    v = volumes[-w:]
    o = opens[-w:] if len(opens) >= w else closes[-w - 1:-1]

    chg_4h = (closes[-1] / closes[-min(49, n - 1)] - 1) * 100
    trend_up = chg_4h > 0.3
    trend_down = chg_4h < -0.3
    atr_pct = atr_value / closes[-1] * 100 if closes[-1] > 0 else 0

    dist_pts = 0
    shake_pts = 0
    d_reasons = []
    s_reasons = []

    # 1) 阴阳量比: 阴线均量/阳线均量, >1.3=抛压放量(派发特征)
    bull = c >= o
    up_vol = float(np.mean(v[bull])) if bull.any() else 0.0
    down_vol = float(np.mean(v[~bull])) if (~bull).any() else 0.0
    vd_ratio = down_vol / up_vol if up_vol > 0 else 1.0
    if vd_ratio >= 1.3:
        dist_pts += 2
        d_reasons.append(f"阴线均量为阳线{vd_ratio:.1f}倍(抛压放量)")
    elif 0 < vd_ratio <= 0.75:
        shake_pts += 1
        s_reasons.append(f"回调缩量(阴量仅阳量{vd_ratio:.0%})")

    # 2) 高位放量滞涨: 近6根量放大但价格不动, 且处于近24根高位区 = 派发嫌疑
    vol_base = float(np.mean(v)) if np.mean(v) > 0 else 1.0
    vol6 = float(np.mean(v[-6:])) / vol_base
    chg6 = abs(c[-1] / c[-7] - 1) * 100 if len(c) >= 7 else 0
    rng_h = float(np.max(h) - np.min(l))
    pos_in_rng = (c[-1] - float(np.min(l))) / rng_h if rng_h > 0 else 0.5
    if vol6 >= 1.4 and chg6 < max(0.4 * atr_pct, 0.15) and pos_in_rng > 0.65:
        dist_pts += 2
        d_reasons.append(f"高位放量滞涨(量{vol6:.1f}倍/6根仅{chg6:.2f}%)")

    # 3) 上下影线结构(近12根)
    body = np.abs(c[-12:] - o[-12:])
    rng12 = h[-12:] - l[-12:]
    up_wick = h[-12:] - np.maximum(c[-12:], o[-12:])
    dn_wick = np.minimum(c[-12:], o[-12:]) - l[-12:]
    long_up = int(np.sum((rng12 > 0) & (up_wick > np.maximum(body, 1e-12))
                         & (up_wick > 0.45 * rng12)))
    long_dn = int(np.sum((rng12 > 0) & (dn_wick > np.maximum(body, 1e-12))
                         & (dn_wick > 0.45 * rng12)))
    if long_up >= 2:
        dist_pts += 1
        d_reasons.append(f"{long_up}根长上影(上方持续派发)")
    if long_dn >= 2:
        shake_pts += 1
        s_reasons.append(f"{long_dn}根长下影(下方承接强)")

    # 4) 回调缩量结构: 最近高点之后的回落段量能萎缩且回调不深 = 洗盘特征
    hi_idx = int(np.argmax(h))
    if hi_idx < w - 3:
        leg_up_vol = float(np.mean(v[:hi_idx + 1])) if hi_idx >= 1 else vol_base
        pull_vol = float(np.mean(v[hi_idx:]))
        pull_depth = float(np.max(h)) - float(np.min(c[hi_idx:]))
        if leg_up_vol > 0 and pull_vol < 0.75 * leg_up_vol and pull_depth < 3.0 * atr_value:
            shake_pts += 2
            s_reasons.append(f"回调缩量至{pull_vol / leg_up_vol:.0%}且幅度仅{pull_depth / atr_value:.1f}ATR(洗盘)")
        # 下影承接+收复: 最近3根重新走强
        if long_dn >= 1 and c[-1] > c[-3] and not trend_down:
            shake_pts += 1
            s_reasons.append("下影承接后收复")

    # 5) 放量急跌且无反弹(恐慌抛售=出货末段)
    if trend_down and vd_ratio >= 1.3 and c[-1] <= c[-3]:
        dist_pts += 1
        d_reasons.append("放量下行无反弹(持续派发)")

    # ---- 判定 ----
    if dist_pts >= 3 and dist_pts >= shake_pts + 1:
        intent, pts, reasons = "出货", dist_pts, d_reasons
    elif shake_pts >= 3 and shake_pts >= dist_pts + 1:
        intent = "洗盘" if not trend_down else "吸筹"
        pts, reasons = shake_pts, s_reasons
    elif trend_up and dist_pts <= shake_pts:
        intent, pts, reasons = "拉升", 2, ["上行趋势且无派发迹象"]
    else:
        intent, pts, reasons = "观望", 0, []
    confidence = 0 if intent == "观望" else min(95, 28 + pts * 13)
    return {
        "intent": intent,
        "confidence": confidence,
        "reasons": reasons[:4],
        "dist_pts": dist_pts,
        "shake_pts": shake_pts,
        "trend_down": trend_down,
    }


def detect_breakout(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray,
                    volumes: np.ndarray, atr_value: float, lookback: int = 20) -> int:
    """右侧先手(解决入场太慢): 放量突破前N根高/低点当下即入场, 不等趋势确认滞后。
    1=放量向上突破, -1=放量向下破位, 0=无"""
    n = len(closes)
    if n < lookback + 5 or atr_value <= 0:
        return 0
    prior_high = float(np.max(highs[-lookback - 1:-1]))
    prior_low = float(np.min(lows[-lookback - 1:-1]))
    c = float(closes[-1])
    vol_base = float(np.mean(volumes[-lookback:]))
    vol_recent = float(np.mean(volumes[-3:]))
    surge = vol_recent / vol_base if vol_base > 0 else 1.0
    # 突破需放量确认(≥1.5倍均量), 且突破幅度有效(>0.15ATR防假突破)
    if c > prior_high + 0.15 * atr_value and surge >= 1.5:
        return 1
    if c < prior_low - 0.15 * atr_value and surge >= 1.5:
        return -1
    return 0


# ========== 策略引擎 ==========

class StrategyEngine:
    """
    多因子加权评分系统
    信号: 1=开多, -1=开空, 0=无信号
    评分范围: -100 ~ +100, |score| >= threshold 才触发
    """

    # 参与评分的因子键(供回测做贡献度分析与权重调优)
    FACTOR_KEYS = (
        "ribbon", "htf_trend", "rsi_stoch", "rsi_divergence", "macd",
        "vwap", "bb_position", "volume_spike", "obv", "volume_price_div",
        "momentum_decel", "bb_rejection", "funding", "swing_reversal",
        "breakout",
    )

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.threshold = cfg.get("signal_threshold", 60)
        # 回测可注入需禁用的因子键; 实盘默认全部启用
        self.disabled_factors: set = set(cfg.get("disabled_factors", []) or [])

    def _factor_weight(self, key: str, default: float) -> float:
        """因子权重可由配置覆盖(factor_weights), 便于回测调优后落地"""
        weights = self.cfg.get("factor_weights", {}) or {}
        try:
            return float(weights.get(key, default))
        except (TypeError, ValueError):
            return default

    def evaluate(self, closes: np.ndarray, highs: np.ndarray = None,
                 lows: np.ndarray = None, volumes: np.ndarray = None,
                 funding_rate: float = None, htf_closes: np.ndarray = None) -> dict:
        """
        多因子评估
        htf_closes: 高时间框架K线(用于趋势确认)
        funding_rate: 当前资金费率
        """
        if len(closes) < 60:
            return {"signal": 0, "score": 0, "indicators": {}, "reason": "数据不足", "factors": []}

        s = self.cfg
        if highs is None:
            highs = closes
        if lows is None:
            lows = closes
        if volumes is None:
            volumes = np.ones_like(closes)

        # 计算所有指标
        ma_fast = calc_ma(closes, s.get("ma_fast", 7))
        ma_slow = calc_ma(closes, s.get("ma_slow", 25))
        ema9 = calc_ema(closes, 9)
        ema21 = calc_ema(closes, 21)
        rsi = calc_rsi(closes, s.get("rsi_period", 14))
        macd_line, signal_line, histogram = calc_macd(
            closes, s.get("macd_fast", 12), s.get("macd_slow", 26), s.get("macd_signal", 9)
        )
        bb_upper, bb_mid, bb_lower = calc_bollinger(closes, s.get("bb_period", 20), s.get("bb_std", 2))
        atr = calc_atr(highs, lows, closes, 14)
        vwap = calc_vwap(highs, lows, closes, volumes)
        obv = calc_obv(closes, volumes)
        stoch_k, stoch_d = calc_stoch_rsi(closes)

        # 多时间框架趋势
        htf_trend = 0
        if htf_closes is not None and len(htf_closes) >= 55:
            htf_trend = detect_ema_ribbon(htf_closes)

        # ========== 因子评分 ==========
        score = 0.0
        factors = []
        disabled = self.disabled_factors
        w = self._factor_weight

        def on(key: str) -> bool:
            """因子是否启用(回测做贡献度分析时可逐个关闭)"""
            return key not in disabled

        # 1. EMA丝带趋势 (权重10, 降低滞后影响)
        ribbon = detect_ema_ribbon(closes)
        if on("ribbon") and ribbon != 0:
            pts = ribbon * w("ribbon", 10)
            score += pts
            factors.append(f"EMA丝带{'多头' if ribbon > 0 else '空头'}排列({pts:+.0f})")

        # 2. 多时间框架确认 (权重15, 降低滞后影响)
        if on("htf_trend") and htf_trend != 0:
            if ribbon != 0 and htf_trend == np.sign(ribbon):
                pts = htf_trend * w("htf_trend", 15)
                score += pts
                factors.append(f"高TF趋势确认({pts:+.0f})")
            elif ribbon != 0 and htf_trend != np.sign(ribbon):
                pts = htf_trend * w("htf_trend_against", 5)
                score += pts
                factors.append(f"高TF趋势逆向({pts:+.0f})")

        # 3. RSI + StochRSI (权重15)
        if on("rsi_stoch"):
            rsi_w = w("rsi_stoch", 15)
            rsi_w_weak = w("rsi_stoch_weak", 8)
            if rsi[-1] < 30 and stoch_k[-1] < 20:
                score += rsi_w
                factors.append(f"RSI={rsi[-1]:.0f}+StochRSI超卖({rsi_w:+.0f})")
            elif rsi[-1] > 70 and stoch_k[-1] > 80:
                score -= rsi_w
                factors.append(f"RSI={rsi[-1]:.0f}+StochRSI超买({-rsi_w:+.0f})")
            elif rsi[-1] < 40 and stoch_k[-1] > stoch_d[-1]:
                score += rsi_w_weak
                factors.append(f"RSI偏低+StochRSI金叉({rsi_w_weak:+.0f})")
            elif rsi[-1] > 60 and stoch_k[-1] < stoch_d[-1]:
                score -= rsi_w_weak
                factors.append(f"RSI偏高+StochRSI死叉({-rsi_w_weak:+.0f})")

        # 4. RSI背离 (权重20) - 高胜率反转信号
        divergence = detect_rsi_divergence(closes, rsi)
        if on("rsi_divergence") and divergence != 0:
            pts = divergence * w("rsi_divergence", 20)
            score += pts
            factors.append(f"RSI{'看涨' if divergence > 0 else '看跌'}背离({pts:+.0f})")

        # 5. MACD动量 (权重10)
        if on("macd"):
            macd_w = w("macd", 10)
            macd_w_weak = w("macd_weak", 5)
            if histogram[-1] > 0 and histogram[-2] <= 0:
                score += macd_w
                factors.append(f"MACD柱翻正({macd_w:+.0f})")
            elif histogram[-1] < 0 and histogram[-2] >= 0:
                score -= macd_w
                factors.append(f"MACD柱翻负({-macd_w:+.0f})")
            elif histogram[-1] > histogram[-2] > 0:
                score += macd_w_weak
                factors.append(f"MACD动量增强({macd_w_weak:+.0f})")
            elif histogram[-1] < histogram[-2] < 0:
                score -= macd_w_weak
                factors.append(f"MACD动量减弱({-macd_w_weak:+.0f})")

        # 6. VWAP回归 (权重15)
        vwap_dist = (closes[-1] - vwap[-1]) / vwap[-1] * 100 if vwap[-1] != 0 else 0
        if on("vwap"):
            vwap_w = w("vwap", 15)
            if vwap_dist < -1.5 and closes[-1] > closes[-2]:
                score += vwap_w
                factors.append(f"VWAP下方回归({vwap_w:+.0f})")
            elif vwap_dist > 1.5 and closes[-1] < closes[-2]:
                score -= vwap_w
                factors.append(f"VWAP上方回归({-vwap_w:+.0f})")

        # 7. 布林带位置 (权重10)
        bb_width = (bb_upper[-1] - bb_lower[-1]) / bb_mid[-1] * 100 if bb_mid[-1] != 0 else 0
        if on("bb_position"):
            bb_w = w("bb_position", 10)
            if closes[-1] <= bb_lower[-1]:
                score += bb_w
                factors.append(f"触及布林下轨({bb_w:+.0f})")
            elif closes[-1] >= bb_upper[-1]:
                score -= bb_w
                factors.append(f"触及布林上轨({-bb_w:+.0f})")

        # 8. 成交量确认 (权重10)
        vol_spike = detect_volume_spike(volumes)
        if on("volume_spike") and vol_spike:
            vol_w = w("volume_spike", 10)
            if score > 0:
                score += vol_w
                factors.append(f"放量确认({vol_w:+.0f})")
            elif score < 0:
                score -= vol_w
                factors.append(f"放量确认({-vol_w:+.0f})")

        # 9. OBV趋势 (权重5)
        obv_ma = calc_ma(obv, 10)
        if on("obv"):
            obv_w = w("obv", 5)
            if obv[-1] > obv_ma[-1] and obv[-2] <= obv_ma[-2]:
                score += obv_w
                factors.append(f"OBV突破均线({obv_w:+.0f})")
            elif obv[-1] < obv_ma[-1] and obv[-2] >= obv_ma[-2]:
                score -= obv_w
                factors.append(f"OBV跌破均线({-obv_w:+.0f})")

        # 10. 量价背离 (权重15, 领先信号: 高点缩量=即将反转)
        vp_div = detect_volume_price_divergence(closes, volumes)
        if on("volume_price_div") and vp_div != 0:
            pts = vp_div * w("volume_price_div", 15)
            score += pts
            factors.append(f"量价背离·{'上涨乏力' if vp_div < 0 else '抛压衰竭'}({pts:+.0f})")

        # 11. 动量衰减 (权重10, 领先信号: ROC连续下降=趋势即将反转)
        momentum = detect_momentum_deceleration(closes)
        if on("momentum_decel") and momentum != 0:
            pts = momentum * w("momentum_decel", 10)
            score += pts
            factors.append(f"动量{'衰减·涨不动' if momentum < 0 else '恢复·跌不动'}({pts:+.0f})")

        # 12. 布林带拒绝 (权重15, 领先信号: 触轨+反向K线=即将回归)
        bb_rej = detect_bb_rejection(closes, highs, lows, bb_upper, bb_lower)
        if on("bb_rejection") and bb_rej != 0:
            pts = bb_rej * w("bb_rejection", 15)
            score += pts
            factors.append(f"布林{'上轨拒绝·做空' if bb_rej < 0 else '下轨拒绝·做多'}({pts:+.0f})")

        # 13. 资金费率反转 (权重15) - 极端费率做反向
        if on("funding") and funding_rate is not None:
            fund_w = w("funding", 15)
            if funding_rate > 0.05:
                score -= fund_w
                factors.append(f"资金费率{funding_rate:.4f}过高做空({-fund_w:+.0f})")
            elif funding_rate < -0.03:
                score += fund_w
                factors.append(f"资金费率{funding_rate:.4f}过低做多({fund_w:+.0f})")

        # 14. 二次波段反转 (权重20-35, 结构信号: 二次冲顶/探底被拒=高胜率反转)
        swing_pts, swing_info = detect_second_swing_reversal(
            closes, highs, lows, rsi, float(atr[-1]))
        if on("swing_reversal") and swing_pts != 0:
            swing_scale = w("swing_reversal_scale", 1.0)
            swing_pts = swing_pts * swing_scale
            score += swing_pts
            factors.append(f"{swing_info.get('label', '二次波段反转')}({swing_pts:+.0f})")
        elif not on("swing_reversal"):
            swing_pts = 0

        # 15. 支撑/压力位结构分析(供入场空间检查与止盈止损定位)
        sr = detect_support_resistance(closes, highs, lows, float(atr[-1]))

        # 16. 主力意图推断(量价结构: 洗盘/出货/拉升/观望)
        intent_info = detect_main_force_intent(closes, highs, lows, volumes, None, float(atr[-1]))

        # 17. 突破先手(权重35, 右侧快入场: 放量突破前高的当下入场, 不等趋势确认)
        breakout_sig = detect_breakout(closes, highs, lows, volumes, float(atr[-1]))
        if not on("breakout"):
            breakout_sig = 0
        elif breakout_sig != 0:
            pts = breakout_sig * w("breakout", 35)
            score += pts
            factors.append(f"突破先手·放量{'突破前高' if breakout_sig > 0 else '跌破前低'}({pts:+.0f})")

        # ========== 最终信号(数据驱动: 方向不对称阈值 + 高TF顺势过滤) ==========
        # 历史回测: 做空胜率77.8%/盈亏比3.21, 做多胜率56.5%/盈亏比0.47
        # -> 做空门槛略低, 做多门槛更高(需更强确认), 过滤逆势单
        long_th = s.get("long_threshold", self.threshold)
        short_th = s.get("short_threshold", self.threshold)
        final_signal = 0
        if score >= long_th:
            final_signal = 1
        elif score <= -short_th:
            final_signal = -1
        # 突破驱动的信号不受滞后过滤约束(先手本质就是快于趋势确认)
        breakout_driven = breakout_sig != 0 and final_signal == breakout_sig

        # 高TF趋势必须同向, 否则过滤(逆势单是亏损主因)
        if final_signal != 0 and s.get("require_htf_align", False):
            if htf_trend != 0 and float(np.sign(htf_trend)) != float(np.sign(final_signal)):
                factors.append("高TF趋势逆向,已过滤")
                final_signal = 0

        # 顺势模式(只借力不逆势): 主导趋势存在时, 逆趋势信号一律过滤
        dominant = htf_trend if htf_trend != 0 else ribbon
        if final_signal != 0 and not breakout_driven and s.get("require_trend_align", True) and dominant != 0 \
                and float(np.sign(dominant)) != float(np.sign(final_signal)):
            factors.append(f"逆势信号(主导趋势{'多' if dominant > 0 else '空'}),顺势模式已过滤")
            final_signal = 0

        # 支撑/压力空间检查: 压力贴顶不追多, 支撑贴脸不追空(盈亏比不足)
        atr_now = float(atr[-1])
        if not breakout_driven and final_signal == 1 and sr["resistance"] is not None \
                and (sr["resistance"] - float(closes[-1])) < 0.4 * atr_now:
            factors.append("上方压力位过近,上涨空间不足,取消做多")
            final_signal = 0
        elif not breakout_driven and final_signal == -1 and sr["support"] is not None \
                and (float(closes[-1]) - sr["support"]) < 0.4 * atr_now:
            factors.append("下方支撑位过近,下跌空间不足,取消做空")
            final_signal = 0

        indicators = {
            "price": round(float(closes[-1]), 6),
            "ma_fast": round(float(ma_fast[-1]), 6),
            "ma_slow": round(float(ma_slow[-1]), 6),
            "ema9": round(float(ema9[-1]), 6),
            "ema21": round(float(ema21[-1]), 6),
            "rsi": round(float(rsi[-1]), 2),
            "stoch_k": round(float(stoch_k[-1]), 2),
            "stoch_d": round(float(stoch_d[-1]), 2),
            "macd": round(float(macd_line[-1]), 6),
            "macd_signal": round(float(signal_line[-1]), 6),
            "macd_hist": round(float(histogram[-1]), 6),
            "bb_upper": round(float(bb_upper[-1]), 6),
            "bb_mid": round(float(bb_mid[-1]), 6),
            "bb_lower": round(float(bb_lower[-1]), 6),
            "bb_width": round(bb_width, 2),
            "atr": round(float(atr[-1]), 6),
            "vwap": round(float(vwap[-1]), 6),
            "vwap_dist_pct": round(vwap_dist, 3),
            "vol_spike": vol_spike,
            "ribbon": ribbon,
            "htf_trend": htf_trend,
            "funding_rate": funding_rate,
            "swing_pattern": swing_info.get("pattern") or "--",
            "swing_neck": swing_info.get("neck"),
            "sr_support": sr["support"],
            "sr_support_touches": sr["support_touches"],
            "sr_resistance": sr["resistance"],
            "sr_resistance_touches": sr["resistance_touches"],
            "main_intent": intent_info["intent"],
            "main_intent_confidence": intent_info["confidence"],
            "breakout": breakout_sig,
            "score": round(score, 1),
        }

        return {
            "signal": final_signal,
            "score": round(score, 1),
            "indicators": indicators,
            "reason": " | ".join(factors) if factors else "无明确信号",
            "factors": factors,
        }

    def check_exit(self, closes: np.ndarray, entry_side: str,
                   entry_price: float = 0, highs: np.ndarray = None,
                   lows: np.ndarray = None, htf_closes: np.ndarray = None,
                   swing_closes: np.ndarray = None, volumes: np.ndarray = None,
                   opens: np.ndarray = None) -> dict:
        """智能平仓: 综合多指标判断"""
        if len(closes) < 50:
            return {"exit": False, "reason": ""}

        s = self.cfg
        rsi = calc_rsi(closes, s.get("rsi_period", 14))
        ema9 = calc_ema(closes, 9)
        ema21 = calc_ema(closes, 21)
        macd_line, signal_line, histogram = calc_macd(closes)
        stoch_k, stoch_d = calc_stoch_rsi(closes)

        reasons = []
        exit_score = 0

        swing_pts_exit = 0
        if highs is not None and lows is not None and len(highs) >= 60:
            atr_arr = calc_atr(highs, lows, closes, 14)
            swing_pts_exit, _ = detect_second_swing_reversal(
                closes, highs, lows, rsi, float(atr_arr[-1]))

        intent_info = None
        if highs is not None and lows is not None and volumes is not None and len(closes) >= 60:
            atr_arr2 = calc_atr(highs, lows, closes, 14)
            intent_info = detect_main_force_intent(
                closes, highs, lows, volumes, opens, float(atr_arr2[-1]))

        if entry_side == "LONG":
            if intent_info and intent_info["intent"] == "出货" \
                    and intent_info["confidence"] >= 50:
                exit_score += 2
                reasons.append(f"疑似主力出货({intent_info['confidence']}%),加速离场")
            if swing_pts_exit < 0:
                exit_score += 2
                reasons.append("二次波段顶结构形成(反向结构)")
            if rsi[-1] > 75:
                exit_score += 2
                reasons.append(f"RSI={rsi[-1]:.0f}严重超买")
            if ema9[-1] < ema21[-1] and ema9[-2] >= ema21[-2]:
                exit_score += 2
                reasons.append("EMA9/21死叉")
            if histogram[-1] < 0 and histogram[-2] >= 0:
                exit_score += 1
                reasons.append("MACD柱翻负")
            if stoch_k[-1] > 80 and stoch_k[-1] < stoch_d[-1]:
                exit_score += 1
                reasons.append("StochRSI高位死叉")
            # 检测看跌背离
            div = detect_rsi_divergence(closes, rsi)
            if div == -1:
                exit_score += 2
                reasons.append("RSI看跌背离")
        elif entry_side == "SHORT":
            if intent_info and intent_info["intent"] in ("洗盘", "吸筹") \
                    and intent_info["confidence"] >= 50:
                exit_score += 2
                reasons.append(f"疑似主力{intent_info['intent']}({intent_info['confidence']}%),空头离场")
            if swing_pts_exit > 0:
                exit_score += 2
                reasons.append("二次波段底结构形成(反向结构)")
            if rsi[-1] < 25:
                exit_score += 2
                reasons.append(f"RSI={rsi[-1]:.0f}严重超卖")
            if ema9[-1] > ema21[-1] and ema9[-2] <= ema21[-2]:
                exit_score += 2
                reasons.append("EMA9/21金叉")
            if histogram[-1] > 0 and histogram[-2] <= 0:
                exit_score += 1
                reasons.append("MACD柱翻正")
            if stoch_k[-1] < 20 and stoch_k[-1] > stoch_d[-1]:
                exit_score += 1
                reasons.append("StochRSI低位金叉")
            div = detect_rsi_divergence(closes, rsi)
            if div == 1:
                exit_score += 2
                reasons.append("RSI看涨背离")

        pm = s.get("position_management", {})
        base_threshold = int(pm.get("exit_score_threshold", 5))
        # 空单反弹更快，使用更敏感的退出阈值（比多单低1分）
        threshold = base_threshold - 1 if entry_side == "SHORT" else base_threshold
        require_htf = bool(pm.get("require_htf_reversal", True))
        htf_trend = 0
        if htf_closes is not None and len(htf_closes) >= 55:
            htf_trend = detect_ema_ribbon(htf_closes)
        htf_against = (
            (entry_side == "LONG" and htf_trend < 0)
            or (entry_side == "SHORT" and htf_trend > 0)
        )
        require_swing = bool(pm.get("require_swing_reversal", True))
        swing_trend = 0
        if swing_closes is not None and len(swing_closes) >= 55:
            swing_trend = detect_ema_ribbon(swing_closes)
        swing_against = (
            (entry_side == "LONG" and swing_trend < 0)
            or (entry_side == "SHORT" and swing_trend > 0)
        )
        # 反转确认: 普通信号需1h或swing任一反向确认(任一即可, 不再要求双确认,
        # 否则急反转时只能挨到止损); 强信号(exit_score高出阈值3分)无需等待,
        # 指标共振本身置信度已足够, 立即离场
        htf_or_swing_against = (
            (not require_htf or htf_against)
            or (not require_swing or swing_against)
        )
        strong_exit = exit_score >= threshold + 3
        trend_confirmed = strong_exit or htf_or_swing_against
        should_exit = exit_score >= threshold and trend_confirmed
        if exit_score >= threshold and not trend_confirmed:
            reasons.append("波动周期尚未确认反转，继续持有并观察结构")
        return {
            "exit": should_exit,
            "reason": " + ".join(reasons),
            "exit_score": exit_score,
            "htf_trend": htf_trend,
            "htf_confirmed": htf_against,
            "swing_trend": swing_trend,
            "swing_confirmed": swing_against,
        }
