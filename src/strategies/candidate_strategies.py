"""备选量化高胜率策略引擎集合 (Candidate Strategy Engines)
提供 7 大高胜率备选策略的执行逻辑、参数空间与信号生成规范，支持历史数据模拟与自进化调优。
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd

from strategy import (
    calc_ema, calc_ma, calc_rsi, calc_atr, calc_bollinger,
    calc_vwap, calc_macd, find_swing_pivots
)


@dataclass
class StrategySignal:
    """策略产生的单次信号"""
    idx: int
    side: str  # "LONG" / "SHORT"
    entry_price: float
    stop_loss: float
    take_profit: float
    params: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


class BaseCandidateStrategy:
    """备选策略基类"""
    id: str = "base"
    name: str = "Base Strategy"
    title: str = "基础策略"
    description: str = ""
    timeframe: str = "15m"
    category: str = "trend"  # trend, range, momentum, smart_money, grid
    default_symbols: List[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        self.params = dict(self.get_default_params())
        if params:
            self.params.update(params)

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        """获取默认参数"""
        raise NotImplementedError

    @classmethod
    def get_param_bounds(cls) -> Dict[str, Dict[str, Any]]:
        """定义参数调优搜索空间: {key: {type, min, max, step, options}}"""
        raise NotImplementedError

    def generate_signals(self, closes: np.ndarray, highs: np.ndarray,
                         lows: np.ndarray, volumes: np.ndarray) -> List[StrategySignal]:
        """遍历 K 线历史生成进出场信号"""
        raise NotImplementedError

    def simulate_lifecycle(self, closes: np.ndarray, highs: np.ndarray,
                           lows: np.ndarray, volumes: np.ndarray,
                           atr_arr: np.ndarray, start_idx: int) -> Tuple[List[Tuple[float, float, str, int]], int, str]:
        """模拟单笔交易从开仓到平仓的完整生命周期:
        返回: (exits [(ratio, price, reason, exit_idx)], hold_bars, final_reason)
        默认生命周期基于固定止损止盈/跟踪止损，策略可覆写支持马丁加仓或金字塔加仓。
        """
        raise NotImplementedError


# =====================================================================
# 1. 动态安全网格马丁策略 (Dynamic Safety-Grid DCA)
# =====================================================================
class DCAMartingaleStrategy(BaseCandidateStrategy):
    id = "grid_martingale"
    name = "Dynamic Safety-Grid DCA"
    title = "动态安全网格马丁策略 (DCA)"
    description = "华尔街改良版动态网格马丁：ATR间距拉伸 + 软阶梯加仓 (1.2x~1.4x) + 12%硬熔断保险丝"
    timeframe = "15m"
    category = "grid"
    default_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"]

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "rsi_period": 14,
            "rsi_oversold": 28.0,
            "rsi_overbought": 72.0,
            "ema_dist_atr": 1.5,
            "tier1_dist_atr": 1.2,
            "tier1_mult": 1.2,
            "tier2_dist_atr": 1.8,
            "tier2_mult": 1.4,
            "tier3_dist_atr": 2.5,
            "tier3_mult": 1.6,
            "tp_pct": 1.5,        # 止盈: 相对均价 +1.5%
            "cutoff_pct": 12.0,    # 硬性回撤熔断: -12.0%
        }

    @classmethod
    def get_param_bounds(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "rsi_period": {"type": "int", "min": 10, "max": 21, "step": 1},
            "rsi_oversold": {"type": "float", "min": 22.0, "max": 34.0, "step": 1.0},
            "ema_dist_atr": {"type": "float", "min": 1.0, "max": 2.2, "step": 0.1},
            "tier1_dist_atr": {"type": "float", "min": 0.8, "max": 1.6, "step": 0.1},
            "tier1_mult": {"type": "float", "min": 1.1, "max": 1.4, "step": 0.05},
            "tp_pct": {"type": "float", "min": 1.0, "max": 2.6, "step": 0.2},
            "cutoff_pct": {"type": "float", "min": 8.0, "max": 16.0, "step": 1.0},
        }

    def generate_signals(self, closes: np.ndarray, highs: np.ndarray,
                         lows: np.ndarray, volumes: np.ndarray) -> List[StrategySignal]:
        signals = []
        p = self.params
        n = len(closes)
        if n < 60:
            return signals

        rsi = calc_rsi(closes, int(p["rsi_period"]))
        ema21 = calc_ema(closes, 21)
        atr = calc_atr(highs, lows, closes, 14)

        for i in range(50, n):
            c = float(closes[i])
            atrv = float(atr[i]) if atr[i] > 0 else c * 0.01
            dist_ema = (ema21[i] - c) / atrv if atrv > 0 else 0

            # 做多信号: RSI极端超卖且价格离EMA21超过指定ATR
            if rsi[i] < p["rsi_oversold"] and dist_ema >= p["ema_dist_atr"]:
                signals.append(StrategySignal(
                    idx=i, side="LONG", entry_price=c,
                    stop_loss=c * (1 - p["cutoff_pct"] / 100),
                    take_profit=c * (1 + p["tp_pct"] / 100),
                    params=self.params, extra={"type": "dca_base"}
                ))
            # 做空信号: RSI极端超买且价格高于EMA21超过指定ATR
            elif rsi[i] > p["rsi_overbought"] and (-dist_ema) >= p["ema_dist_atr"]:
                signals.append(StrategySignal(
                    idx=i, side="SHORT", entry_price=c,
                    stop_loss=c * (1 + p["cutoff_pct"] / 100),
                    take_profit=c * (1 - p["tp_pct"] / 100),
                    params=self.params, extra={"type": "dca_base"}
                ))
        return signals

    def simulate_lifecycle(self, closes: np.ndarray, highs: np.ndarray,
                           lows: np.ndarray, volumes: np.ndarray,
                           atr_arr: np.ndarray, start_idx: int,
                           side: str = "LONG") -> Tuple[List[Tuple[float, float, str, int]], int, str]:
        p = self.params
        n = len(closes)
        entry_price = float(closes[start_idx])
        base_atr = float(atr_arr[start_idx]) if atr_arr[start_idx] > 0 else entry_price * 0.01

        # 网格状态: legs = [{'price': p, 'ratio': r}]
        legs = [{"price": entry_price, "ratio": 1.0}]
        tier1_done = False
        tier2_done = False
        tier3_done = False

        for i in range(start_idx + 1, n):
            c = float(closes[i])
            hi = float(highs[i])
            lo = float(lows[i])

            # 计算加权平均持仓价
            tot_ratio = sum(leg["ratio"] for leg in legs)
            avg_entry = sum(leg["price"] * leg["ratio"] for leg in legs) / tot_ratio

            # 盈亏百分比
            pnl_pct = (c - avg_entry) / avg_entry * 100 if side == "LONG" else (avg_entry - c) / avg_entry * 100

            # 1. 硬熔断检查
            if pnl_pct <= -p["cutoff_pct"]:
                cutoff_price = avg_entry * (1 - p["cutoff_pct"] / 100) if side == "LONG" else avg_entry * (1 + p["cutoff_pct"] / 100)
                return [(tot_ratio, cutoff_price, "cutoff_sl", i)], i - start_idx, "cutoff_sl"

            # 2. 止盈检查 (回抽超过加权成本 +tp_pct)
            if pnl_pct >= p["tp_pct"]:
                tp_price = avg_entry * (1 + p["tp_pct"] / 100) if side == "LONG" else avg_entry * (1 - p["tp_pct"] / 100)
                return [(tot_ratio, tp_price, "grid_tp", i)], i - start_idx, "grid_tp"

            # 3. 补仓判定
            adv_dist = (entry_price - lo) if side == "LONG" else (hi - entry_price)
            if not tier1_done and adv_dist >= p["tier1_dist_atr"] * base_atr:
                tier1_done = True
                add_price = entry_price - p["tier1_dist_atr"] * base_atr if side == "LONG" else entry_price + p["tier1_dist_atr"] * base_atr
                legs.append({"price": add_price, "ratio": float(p["tier1_mult"])})

            elif tier1_done and not tier2_done and adv_dist >= p["tier2_dist_atr"] * base_atr:
                tier2_done = True
                add_price = entry_price - p["tier2_dist_atr"] * base_atr if side == "LONG" else entry_price + p["tier2_dist_atr"] * base_atr
                legs.append({"price": add_price, "ratio": float(p["tier2_mult"])})

            elif tier2_done and not tier3_done and adv_dist >= p["tier3_dist_atr"] * base_atr:
                tier3_done = True
                add_price = entry_price - p["tier3_dist_atr"] * base_atr if side == "LONG" else entry_price + p["tier3_dist_atr"] * base_atr
                legs.append({"price": add_price, "ratio": float(p["tier3_mult"])})

        # 回测结束收尾
        tot_ratio = sum(leg["ratio"] for leg in legs)
        return [(tot_ratio, float(closes[-1]), "eod", n - 1)], n - 1 - start_idx, "eod"


# =====================================================================
# 2. SMC聪明钱订单块与流动性劫持策略 (Smart Money Concepts)
# =====================================================================
class SMCOrderBlockStrategy(BaseCandidateStrategy):
    id = "smart_money"
    name = "Smart Money Order Block"
    title = "SMC聪明钱订单块与流动性劫持策略"
    description = "机构流动性猎杀 (Liquidity Sweep) + 订单块 (Order Block) 回踩确认，捕捉高盈亏比 (1:3+) 狙击行情"
    timeframe = "15m"
    category = "smart_money"
    default_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "ob_lookback": 20,
            "disp_mult": 1.6,       # 位移放量倍数
            "sweep_atr": 0.25,      # 猎杀流动性穿透 ATR
            "sl_buffer_atr": 0.35,  # 止损缓冲 ATR
            "rr_target": 3.2,       # 目标盈亏比
            "fvg_min_pct": 0.4      # 公允价值缺口最小幅度%
        }

    @classmethod
    def get_param_bounds(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "ob_lookback": {"type": "int", "min": 12, "max": 32, "step": 2},
            "disp_mult": {"type": "float", "min": 1.2, "max": 2.4, "step": 0.1},
            "sweep_atr": {"type": "float", "min": 0.15, "max": 0.5, "step": 0.05},
            "sl_buffer_atr": {"type": "float", "min": 0.2, "max": 0.6, "step": 0.05},
            "rr_target": {"type": "float", "min": 2.2, "max": 4.5, "step": 0.25},
        }

    def generate_signals(self, closes: np.ndarray, highs: np.ndarray,
                         lows: np.ndarray, volumes: np.ndarray) -> List[StrategySignal]:
        signals = []
        p = self.params
        n = len(closes)
        if n < 60:
            return signals

        atr = calc_atr(highs, lows, closes, 14)
        lookback = int(p["ob_lookback"])

        for i in range(lookback + 5, n):
            c = float(closes[i])
            atrv = float(atr[i]) if atr[i] > 0 else c * 0.01

            # 检测流动性掠夺 (Sweep of swing low): 探出新低但收盘强力收回
            prev_low = float(np.min(lows[i - lookback:i - 2]))
            if lows[i - 1] < prev_low - p["sweep_atr"] * atrv and closes[i - 1] > prev_low:
                # 产生向上的位移 K 线
                body = closes[i] - min(closes[i - 1], closes[i])
                if body >= p["disp_mult"] * atrv:
                    sl = float(lows[i - 1]) - p["sl_buffer_atr"] * atrv
                    risk = max(1e-5, c - sl)
                    tp = c + risk * float(p["rr_target"])
                    signals.append(StrategySignal(
                        idx=i, side="LONG", entry_price=c,
                        stop_loss=sl, take_profit=tp,
                        params=self.params, extra={"pattern": "smc_bullish_ob"}
                    ))

            # 检测流动性掠夺 (Sweep of swing high): 冲出新高但收盘倒贴阴线
            prev_high = float(np.max(highs[i - lookback:i - 2]))
            if highs[i - 1] > prev_high + p["sweep_atr"] * atrv and closes[i - 1] < prev_high:
                body = max(closes[i - 1], closes[i]) - closes[i]
                if body >= p["disp_mult"] * atrv:
                    sl = float(highs[i - 1]) + p["sl_buffer_atr"] * atrv
                    risk = max(1e-5, sl - c)
                    tp = c - risk * float(p["rr_target"])
                    signals.append(StrategySignal(
                        idx=i, side="SHORT", entry_price=c,
                        stop_loss=sl, take_profit=tp,
                        params=self.params, extra={"pattern": "smc_bearish_ob"}
                    ))
        return signals

    def simulate_lifecycle(self, closes: np.ndarray, highs: np.ndarray,
                           lows: np.ndarray, volumes: np.ndarray,
                           atr_arr: np.ndarray, start_idx: int,
                           side: str = "LONG") -> Tuple[List[Tuple[float, float, str, int]], int, str]:
        p = self.params
        n = len(closes)
        entry_price = float(closes[start_idx])
        atrv = float(atr_arr[start_idx]) if atr_arr[start_idx] > 0 else entry_price * 0.01

        sl_dist = atrv * (1.0 + float(p["sl_buffer_atr"]))
        stop_price = entry_price - sl_dist if side == "LONG" else entry_price + sl_dist
        risk = abs(entry_price - stop_price)
        tp_price = entry_price + risk * float(p["rr_target"]) if side == "LONG" else entry_price - risk * float(p["rr_target"])

        # 保本线设定: 当盈利达到 1:1.5 RR 时，止损移至开仓价
        be_hit = False
        be_trigger = entry_price + risk * 1.5 if side == "LONG" else entry_price - risk * 1.5

        for i in range(start_idx + 1, n):
            hi = float(highs[i])
            lo = float(lows[i])
            c = float(closes[i])

            # 止损触发
            if (lo <= stop_price) if side == "LONG" else (hi >= stop_price):
                reason = "breakeven" if be_hit else "smc_sl"
                return [(1.0, stop_price, reason, i)], i - start_idx, reason

            # 触发保本
            if not be_hit and ((hi >= be_trigger) if side == "LONG" else (lo <= be_trigger)):
                be_hit = True
                stop_price = entry_price

            # 止盈触发
            if (hi >= tp_price) if side == "LONG" else (lo <= tp_price):
                return [(1.0, tp_price, "smc_tp_high_rr", i)], i - start_idx, "smc_tp_high_rr"

        return [(1.0, float(closes[-1]), "eod", n - 1)], n - 1 - start_idx, "eod"


# =====================================================================
# 3. TTM Squeeze 波动率挤压突破策略
# =====================================================================
class TTMSqueezeStrategy(BaseCandidateStrategy):
    id = "ttm_squeeze"
    name = "TTM Squeeze Momentum"
    title = "TTM_Squeeze波动率挤压突破策略"
    description = "布林带压缩进肯特纳通道 (Squeeze ON) 蓄势，通道爆开 (Squeeze OFF) 伴随动能拐点爆发顺势追击"
    timeframe = "15m"
    category = "momentum"
    default_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "bb_period": 20,
            "bb_std": 2.0,
            "kc_mult": 1.5,
            "mom_period": 14,
            "trail_atr": 2.2,
            "tp_atr": 3.0,
        }

    @classmethod
    def get_param_bounds(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "bb_period": {"type": "int", "min": 14, "max": 26, "step": 2},
            "bb_std": {"type": "float", "min": 1.7, "max": 2.4, "step": 0.1},
            "kc_mult": {"type": "float", "min": 1.2, "max": 1.8, "step": 0.1},
            "mom_period": {"type": "int", "min": 10, "max": 20, "step": 2},
            "trail_atr": {"type": "float", "min": 1.5, "max": 3.0, "step": 0.25},
        }

    def generate_signals(self, closes: np.ndarray, highs: np.ndarray,
                         lows: np.ndarray, volumes: np.ndarray) -> List[StrategySignal]:
        signals = []
        p = self.params
        n = len(closes)
        if n < 50:
            return signals

        bb_up, bb_mid, bb_lo = calc_bollinger(closes, int(p["bb_period"]), float(p["bb_std"]))
        atr = calc_atr(highs, lows, closes, int(p["bb_period"]))
        kc_mult = float(p["kc_mult"])

        # 动能指标: 价格相对中轨的偏离动能
        mom = closes - (bb_mid + calc_ema(closes, int(p["mom_period"]))) / 2

        # 挤压状态: 布林带是否完全在肯特纳通道之内
        kc_up = bb_mid + kc_mult * atr
        kc_lo = bb_mid - kc_mult * atr
        squeeze_on = (bb_up < kc_up) & (bb_lo > kc_lo)

        for i in range(25, n):
            # 挤压由 True 变为 False (爆发释放瞬间)
            if squeeze_on[i - 1] and not squeeze_on[i]:
                c = float(closes[i])
                atrv = float(atr[i]) if atr[i] > 0 else c * 0.01

                if mom[i] > 0 and mom[i] > mom[i - 1]:
                    signals.append(StrategySignal(
                        idx=i, side="LONG", entry_price=c,
                        stop_loss=c - float(p["trail_atr"]) * atrv,
                        take_profit=c + float(p["tp_atr"]) * atrv,
                        params=self.params, extra={"type": "squeeze_fire_long"}
                    ))
                elif mom[i] < 0 and mom[i] < mom[i - 1]:
                    signals.append(StrategySignal(
                        idx=i, side="SHORT", entry_price=c,
                        stop_loss=c + float(p["trail_atr"]) * atrv,
                        take_profit=c - float(p["tp_atr"]) * atrv,
                        params=self.params, extra={"type": "squeeze_fire_short"}
                    ))
        return signals

    def simulate_lifecycle(self, closes: np.ndarray, highs: np.ndarray,
                           lows: np.ndarray, volumes: np.ndarray,
                           atr_arr: np.ndarray, start_idx: int,
                           side: str = "LONG") -> Tuple[List[Tuple[float, float, str, int]], int, str]:
        p = self.params
        n = len(closes)
        entry_price = float(closes[start_idx])
        trail_mult = float(p["trail_atr"])
        peak = entry_price

        for i in range(start_idx + 1, n):
            c = float(closes[i])
            hi = float(highs[i])
            lo = float(lows[i])
            atrv = float(atr_arr[i]) if atr_arr[i] > 0 else c * 0.01

            if side == "LONG":
                peak = max(peak, hi)
                stop_line = peak - trail_mult * atrv
                if lo <= stop_line:
                    return [(1.0, stop_line, "ttm_trail_stop", i)], i - start_idx, "ttm_trail_stop"
                if c >= entry_price + float(p["tp_atr"]) * atrv:
                    return [(1.0, c, "ttm_tp_target", i)], i - start_idx, "ttm_tp_target"
            else:
                peak = min(peak, lo)
                stop_line = peak + trail_mult * atrv
                if hi >= stop_line:
                    return [(1.0, stop_line, "ttm_trail_stop", i)], i - start_idx, "ttm_trail_stop"
                if c <= entry_price - float(p["tp_atr"]) * atrv:
                    return [(1.0, c, "ttm_tp_target", i)], i - start_idx, "ttm_tp_target"

        return [(1.0, float(closes[-1]), "eod", n - 1)], n - 1 - start_idx, "eod"


# =====================================================================
# 4. VWAP机构量价锚定与均值回归策略 (VWAP Mean Reversion)
# =====================================================================
class VWAPReversionStrategy(BaseCandidateStrategy):
    id = "vwap_reversion"
    name = "VWAP Mean Reversion"
    title = "VWAP机构量价锚定与均值回归策略"
    description = "日内机构成交量加权均线偏离 ±2.0σ 极值区套利，反弹回归基准线获利清仓"
    timeframe = "15m"
    category = "range"
    default_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "entry_std": 2.0,      # 入场标准差偏离
            "exit_std": 0.25,      # 止盈标准差回归中位
            "stop_std": 3.4,       # 止损外轨标准差
            "vol_filter": 1.15,    # 逆向反转放量倍数
        }

    @classmethod
    def get_param_bounds(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "entry_std": {"type": "float", "min": 1.6, "max": 2.6, "step": 0.1},
            "exit_std": {"type": "float", "min": 0.0, "max": 0.6, "step": 0.1},
            "stop_std": {"type": "float", "min": 2.8, "max": 4.2, "step": 0.2},
            "vol_filter": {"type": "float", "min": 1.0, "max": 1.8, "step": 0.1},
        }

    def generate_signals(self, closes: np.ndarray, highs: np.ndarray,
                         lows: np.ndarray, volumes: np.ndarray) -> List[StrategySignal]:
        signals = []
        p = self.params
        n = len(closes)
        if n < 50:
            return signals

        vwap = calc_vwap(highs, lows, closes, volumes)
        # 计算滚动标准差
        diff = closes - vwap
        std = pd.Series(diff).rolling(24).std().values
        std = np.nan_to_num(std, nan=closes * 0.01)

        vol_ma = pd.Series(volumes).rolling(20).mean().values

        for i in range(30, n):
            c = float(closes[i])
            s = float(std[i]) if std[i] > 0 else c * 0.01
            v_ratio = volumes[i] / vol_ma[i] if vol_ma[i] > 0 else 1.0

            # 下方极端超跌 + 收阳线反弹
            if c <= vwap[i] - p["entry_std"] * s and closes[i] > closes[i - 1] and v_ratio >= p["vol_filter"]:
                signals.append(StrategySignal(
                    idx=i, side="LONG", entry_price=c,
                    stop_loss=vwap[i] - p["stop_std"] * s,
                    take_profit=vwap[i] - p["exit_std"] * s,
                    params=self.params, extra={"vwap_dist": (c - vwap[i]) / vwap[i] * 100}
                ))
            # 上方极端超买 + 收阴线回落
            elif c >= vwap[i] + p["entry_std"] * s and closes[i] < closes[i - 1] and v_ratio >= p["vol_filter"]:
                signals.append(StrategySignal(
                    idx=i, side="SHORT", entry_price=c,
                    stop_loss=vwap[i] + p["stop_std"] * s,
                    take_profit=vwap[i] + p["exit_std"] * s,
                    params=self.params, extra={"vwap_dist": (c - vwap[i]) / vwap[i] * 100}
                ))
        return signals

    def simulate_lifecycle(self, closes: np.ndarray, highs: np.ndarray,
                           lows: np.ndarray, volumes: np.ndarray,
                           atr_arr: np.ndarray, start_idx: int,
                           side: str = "LONG") -> Tuple[List[Tuple[float, float, str, int]], int, str]:
        p = self.params
        n = len(closes)
        entry_price = float(closes[start_idx])
        vwap = calc_vwap(highs, lows, closes, volumes)
        diff = closes - vwap
        std = pd.Series(diff).rolling(24).std().values
        std = np.nan_to_num(std, nan=entry_price * 0.01)

        for i in range(start_idx + 1, n):
            c = float(closes[i])
            hi = float(highs[i])
            lo = float(lows[i])
            s = float(std[i]) if std[i] > 0 else entry_price * 0.01

            sl_price = vwap[i] - p["stop_std"] * s if side == "LONG" else vwap[i] + p["stop_std"] * s
            tp_price = vwap[i] - p["exit_std"] * s if side == "LONG" else vwap[i] + p["exit_std"] * s

            # 止损触碰
            if (lo <= sl_price) if side == "LONG" else (hi >= sl_price):
                return [(1.0, sl_price, "vwap_sl_outer", i)], i - start_idx, "vwap_sl_outer"

            # 均值回归止盈完成
            if (hi >= tp_price) if side == "LONG" else (lo <= tp_price):
                return [(1.0, tp_price, "vwap_reversion_tp", i)], i - start_idx, "vwap_reversion_tp"

        return [(1.0, float(closes[-1]), "eod", n - 1)], n - 1 - start_idx, "eod"


# =====================================================================
# 5. 经典海龟双向ATR通道突破策略 (Turtle Breakout)
# =====================================================================
class TurtleBreakoutStrategy(BaseCandidateStrategy):
    id = "turtle_breakout"
    name = "Turtle Channel Breakout"
    title = "海龟双向ATR通道突破趋势策略"
    description = "理查德·丹尼斯传奇海龟法则：唐奇安通道突破建仓 + 2.0*ATR 硬止损 + 顺势金字塔加仓"
    timeframe = "1h"
    category = "trend"
    default_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "entry_period": 20,
            "exit_period": 10,
            "sl_atr": 2.0,
            "pyramid_atr": 0.5,
            "max_units": 3,
        }

    @classmethod
    def get_param_bounds(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "entry_period": {"type": "int", "min": 14, "max": 35, "step": 2},
            "exit_period": {"type": "int", "min": 6, "max": 18, "step": 1},
            "sl_atr": {"type": "float", "min": 1.5, "max": 3.0, "step": 0.25},
            "pyramid_atr": {"type": "float", "min": 0.4, "max": 0.8, "step": 0.1},
            "max_units": {"type": "int", "min": 1, "max": 4, "step": 1},
        }

    def generate_signals(self, closes: np.ndarray, highs: np.ndarray,
                         lows: np.ndarray, volumes: np.ndarray) -> List[StrategySignal]:
        signals = []
        p = self.params
        n = len(closes)
        ep = int(p["entry_period"])
        if n < ep + 10:
            return signals

        atr = calc_atr(highs, lows, closes, 14)

        for i in range(ep + 1, n):
            # 突破前 N 根最高价
            donchian_high = float(np.max(highs[i - ep:i]))
            donchian_low = float(np.min(lows[i - ep:i]))
            c = float(closes[i])
            atrv = float(atr[i]) if atr[i] > 0 else c * 0.01

            if c > donchian_high:
                signals.append(StrategySignal(
                    idx=i, side="LONG", entry_price=c,
                    stop_loss=c - float(p["sl_atr"]) * atrv,
                    take_profit=c + float(p["sl_atr"]) * 3.0 * atrv,
                    params=self.params, extra={"high_break": donchian_high}
                ))
            elif c < donchian_low:
                signals.append(StrategySignal(
                    idx=i, side="SHORT", entry_price=c,
                    stop_loss=c + float(p["sl_atr"]) * atrv,
                    take_profit=c - float(p["sl_atr"]) * 3.0 * atrv,
                    params=self.params, extra={"low_break": donchian_low}
                ))
        return signals

    def simulate_lifecycle(self, closes: np.ndarray, highs: np.ndarray,
                           lows: np.ndarray, volumes: np.ndarray,
                           atr_arr: np.ndarray, start_idx: int,
                           side: str = "LONG") -> Tuple[List[Tuple[float, float, str, int]], int, str]:
        p = self.params
        n = len(closes)
        entry_price = float(closes[start_idx])
        atrv = float(atr_arr[start_idx]) if atr_arr[start_idx] > 0 else entry_price * 0.01
        xp = int(p["exit_period"])

        legs = [{"price": entry_price, "ratio": 1.0}]
        unit_count = 1
        stop_loss = entry_price - float(p["sl_atr"]) * atrv if side == "LONG" else entry_price + float(p["sl_atr"]) * atrv

        for i in range(start_idx + 1, n):
            hi = float(highs[i])
            lo = float(lows[i])
            c = float(closes[i])

            # 1. 顺势金字塔加仓: 每盈利 0.5 ATR 加仓 1 个 Unit，并将止损线上移
            if unit_count < int(p["max_units"]):
                last_price = legs[-1]["price"]
                step = float(p["pyramid_atr"]) * atrv
                if side == "LONG" and hi >= last_price + step:
                    add_p = last_price + step
                    legs.append({"price": add_p, "ratio": 0.5})
                    unit_count += 1
                    stop_loss = add_p - float(p["sl_atr"]) * atrv  # 上移止损
                elif side == "SHORT" and lo <= last_price - step:
                    add_p = last_price - step
                    legs.append({"price": add_p, "ratio": 0.5})
                    unit_count += 1
                    stop_loss = add_p + float(p["sl_atr"]) * atrv

            # 2. 止损退出
            if (lo <= stop_loss) if side == "LONG" else (hi >= stop_loss):
                tot_ratio = sum(leg["ratio"] for leg in legs)
                return [(tot_ratio, stop_loss, "turtle_sl", i)], i - start_idx, "turtle_sl"

            # 3. 反向 Donchian 突破平仓退出
            if i >= xp + 2:
                exit_reverse = float(np.min(lows[i - xp:i])) if side == "LONG" else float(np.max(highs[i - xp:i]))
                if (lo <= exit_reverse) if side == "LONG" else (hi >= exit_reverse):
                    tot_ratio = sum(leg["ratio"] for leg in legs)
                    return [(tot_ratio, exit_reverse, "turtle_reverse_exit", i)], i - start_idx, "turtle_reverse_exit"

        tot_ratio = sum(leg["ratio"] for leg in legs)
        return [(tot_ratio, float(closes[-1]), "eod", n - 1)], n - 1 - start_idx, "eod"


# =====================================================================
# 6. 多周期EMA共振与RSI顶底背离策略 (EMA RSI Divergence)
# =====================================================================
class EMARSIDivergenceStrategy(BaseCandidateStrategy):
    id = "ema_rsi_divergence"
    name = "EMA & RSI Divergence"
    title = "多周期EMA共振与RSI顶底背离策略"
    description = "高周期趋势滤镜 + 15m RSI 顶底背离高胜率反转结构，配合双均线金叉死叉入场"
    timeframe = "15m"
    category = "trend"
    default_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "rsi_period": 14,
            "div_lookback": 20,
            "ema_fast": 9,
            "ema_slow": 21,
            "tp_rr": 2.4,
            "sl_atr": 1.5,
        }

    @classmethod
    def get_param_bounds(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "rsi_period": {"type": "int", "min": 10, "max": 21, "step": 1},
            "div_lookback": {"type": "int", "min": 14, "max": 28, "step": 2},
            "ema_fast": {"type": "int", "min": 7, "max": 14, "step": 1},
            "ema_slow": {"type": "int", "min": 18, "max": 30, "step": 1},
            "tp_rr": {"type": "float", "min": 1.8, "max": 3.5, "step": 0.25},
            "sl_atr": {"type": "float", "min": 1.2, "max": 2.4, "step": 0.2},
        }

    def generate_signals(self, closes: np.ndarray, highs: np.ndarray,
                         lows: np.ndarray, volumes: np.ndarray) -> List[StrategySignal]:
        signals = []
        p = self.params
        n = len(closes)
        lookback = int(p["div_lookback"])
        if n < lookback + 25:
            return signals

        rsi = calc_rsi(closes, int(p["rsi_period"]))
        ema_f = calc_ema(closes, int(p["ema_fast"]))
        ema_s = calc_ema(closes, int(p["ema_slow"]))
        atr = calc_atr(highs, lows, closes, 14)

        for i in range(lookback + 10, n):
            c = float(closes[i])
            atrv = float(atr[i]) if atr[i] > 0 else c * 0.01

            # RSI 看涨底背离: 价格创新低，但 RSI 形成更高低点
            price_sub = closes[i - lookback:i]
            rsi_sub = rsi[i - lookback:i]
            half = lookback // 2

            p_low1, p_low2 = np.min(price_sub[:half]), np.min(price_sub[half:])
            r_low1, r_low2 = np.min(rsi_sub[:half]), np.min(rsi_sub[half:])

            # 金叉扳机
            gold_cross = ema_f[i] >= ema_s[i] and ema_f[i - 1] < ema_s[i - 1]
            death_cross = ema_f[i] <= ema_s[i] and ema_f[i - 1] > ema_s[i - 1]

            if p_low2 < p_low1 and r_low2 > r_low1 and r_low2 < 45 and gold_cross:
                sl = c - float(p["sl_atr"]) * atrv
                tp = c + (c - sl) * float(p["tp_rr"])
                signals.append(StrategySignal(
                    idx=i, side="LONG", entry_price=c,
                    stop_loss=sl, take_profit=tp,
                    params=self.params, extra={"divergence": "bullish"}
                ))

            # RSI 看跌顶背离
            p_hi1, p_hi2 = np.max(price_sub[:half]), np.max(price_sub[half:])
            r_hi1, r_hi2 = np.max(rsi_sub[:half]), np.max(rsi_sub[half:])

            if p_hi2 > p_hi1 and r_hi2 < r_hi1 and r_hi2 > 55 and death_cross:
                sl = c + float(p["sl_atr"]) * atrv
                tp = c - (sl - c) * float(p["tp_rr"])
                signals.append(StrategySignal(
                    idx=i, side="SHORT", entry_price=c,
                    stop_loss=sl, take_profit=tp,
                    params=self.params, extra={"divergence": "bearish"}
                ))
        return signals

    def simulate_lifecycle(self, closes: np.ndarray, highs: np.ndarray,
                           lows: np.ndarray, volumes: np.ndarray,
                           atr_arr: np.ndarray, start_idx: int,
                           side: str = "LONG") -> Tuple[List[Tuple[float, float, str, int]], int, str]:
        p = self.params
        n = len(closes)
        entry_price = float(closes[start_idx])
        atrv = float(atr_arr[start_idx]) if atr_arr[start_idx] > 0 else entry_price * 0.01

        sl_dist = float(p["sl_atr"]) * atrv
        sl_price = entry_price - sl_dist if side == "LONG" else entry_price + sl_dist
        tp_price = entry_price + sl_dist * float(p["tp_rr"]) if side == "LONG" else entry_price - sl_dist * float(p["tp_rr"])

        for i in range(start_idx + 1, n):
            hi = float(highs[i])
            lo = float(lows[i])

            if (lo <= sl_price) if side == "LONG" else (hi >= sl_price):
                return [(1.0, sl_price, "divergence_sl", i)], i - start_idx, "divergence_sl"
            if (hi >= tp_price) if side == "LONG" else (lo <= tp_price):
                return [(1.0, tp_price, "divergence_tp", i)], i - start_idx, "divergence_tp"

        return [(1.0, float(closes[-1]), "eod", n - 1)], n - 1 - start_idx, "eod"


# =====================================================================
# 7. EMA双均线趋势跟踪策略 (EMA Trend Following)
# =====================================================================
class EMATrendStrategy(BaseCandidateStrategy):
    id = "trend_following"
    name = "EMA Trend Following"
    title = "EMA双均线趋势跟踪策略"
    description = "经典稳健顺势系统：EMA9与EMA21金叉/死叉 + 成交量确认 + 分批止盈跟踪"
    timeframe = "15m"
    category = "trend"
    default_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "ema_fast": 9,
            "ema_slow": 21,
            "vol_mult": 1.2,
            "sl_atr": 1.8,
            "tp1_atr": 1.6,
            "trail_atr": 2.0,
        }

    @classmethod
    def get_param_bounds(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "ema_fast": {"type": "int", "min": 7, "max": 14, "step": 1},
            "ema_slow": {"type": "int", "min": 18, "max": 30, "step": 1},
            "vol_mult": {"type": "float", "min": 1.0, "max": 1.6, "step": 0.1},
            "sl_atr": {"type": "float", "min": 1.4, "max": 2.5, "step": 0.1},
            "tp1_atr": {"type": "float", "min": 1.2, "max": 2.2, "step": 0.1},
            "trail_atr": {"type": "float", "min": 1.5, "max": 2.8, "step": 0.25},
        }

    def generate_signals(self, closes: np.ndarray, highs: np.ndarray,
                         lows: np.ndarray, volumes: np.ndarray) -> List[StrategySignal]:
        signals = []
        p = self.params
        n = len(closes)
        slow = int(p["ema_slow"])
        if n < slow + 20:
            return signals

        ema_f = calc_ema(closes, int(p["ema_fast"]))
        ema_s = calc_ema(closes, slow)
        atr = calc_atr(highs, lows, closes, 14)
        vol_ma = pd.Series(volumes).rolling(20).mean().values

        for i in range(slow + 5, n):
            c = float(closes[i])
            atrv = float(atr[i]) if atr[i] > 0 else c * 0.01
            v_ok = volumes[i] >= vol_ma[i] * float(p["vol_filter"] if "vol_filter" in p else p.get("vol_mult", 1.2))

            # 金叉且站稳
            if ema_f[i] > ema_s[i] and ema_f[i - 1] <= ema_s[i - 1] and c >= ema_f[i] and v_ok:
                signals.append(StrategySignal(
                    idx=i, side="LONG", entry_price=c,
                    stop_loss=c - float(p["sl_atr"]) * atrv,
                    take_profit=c + float(p["tp1_atr"]) * atrv,
                    params=self.params, extra={"cross": "golden"}
                ))
            # 死叉且跌破
            elif ema_f[i] < ema_s[i] and ema_f[i - 1] >= ema_s[i - 1] and c <= ema_f[i] and v_ok:
                signals.append(StrategySignal(
                    idx=i, side="SHORT", entry_price=c,
                    stop_loss=c + float(p["sl_atr"]) * atrv,
                    take_profit=c - float(p["tp1_atr"]) * atrv,
                    params=self.params, extra={"cross": "death"}
                ))
        return signals

    def simulate_lifecycle(self, closes: np.ndarray, highs: np.ndarray,
                           lows: np.ndarray, volumes: np.ndarray,
                           atr_arr: np.ndarray, start_idx: int,
                           side: str = "LONG") -> Tuple[List[Tuple[float, float, str, int]], int, str]:
        p = self.params
        n = len(closes)
        entry_price = float(closes[start_idx])
        atrv = float(atr_arr[start_idx]) if atr_arr[start_idx] > 0 else entry_price * 0.01

        sl_price = entry_price - float(p["sl_atr"]) * atrv if side == "LONG" else entry_price + float(p["sl_atr"]) * atrv
        tp1_price = entry_price + float(p["tp1_atr"]) * atrv if side == "LONG" else entry_price - float(p["tp1_atr"]) * atrv

        tp1_done = False
        remaining = 1.0
        exits = []
        peak = entry_price

        for i in range(start_idx + 1, n):
            hi = float(highs[i])
            lo = float(lows[i])
            c = float(closes[i])
            cur_atr = float(atr_arr[i]) if atr_arr[i] > 0 else atrv

            # 初始硬止损
            if not tp1_done and ((lo <= sl_price) if side == "LONG" else (hi >= sl_price)):
                exits.append((remaining, sl_price, "initial_sl", i))
                return exits, i - start_idx, "initial_sl"

            # 第一止盈: 平 50%，保本移损
            if not tp1_done and ((hi >= tp1_price) if side == "LONG" else (lo <= tp1_price)):
                tp1_done = True
                exits.append((0.5, tp1_price, "tp1_half", i))
                remaining = 0.5
                sl_price = entry_price  # 止损移至保本

            # 达到 TP1 后进入跟踪止损
            if tp1_done:
                if side == "LONG":
                    peak = max(peak, hi)
                    trail_stop = peak - float(p["trail_atr"]) * cur_atr
                    eff_stop = max(sl_price, trail_stop)
                    if lo <= eff_stop:
                        exits.append((remaining, eff_stop, "trail_exit", i))
                        return exits, i - start_idx, "trail_exit"
                else:
                    peak = min(peak, lo)
                    trail_stop = peak + float(p["trail_atr"]) * cur_atr
                    eff_stop = min(sl_price, trail_stop)
                    if hi >= eff_stop:
                        exits.append((remaining, eff_stop, "trail_exit", i))
                        return exits, i - start_idx, "trail_exit"

        if remaining > 0:
            exits.append((remaining, float(closes[-1]), "eod", n - 1))
        return exits, n - 1 - start_idx, "eod"


# =====================================================================
# 8. 威科夫吸筹模型与 Spring 弹簧效应策略 (Wyckoff Accumulation & Spring)
# =====================================================================
class WyckoffSpringStrategy(BaseCandidateStrategy):
    id = "wyckoff_spring"
    name = "Wyckoff Accumulation Spring"
    title = "威科夫吸筹模型与Spring弹簧效应策略"
    description = "威科夫Phase C弹簧效应：箱体下沿假跌破刺穿+长下影收回+缩量二次测试+SOS放量突破"
    timeframe = "15m"
    category = "range"
    default_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "tr_lookback": 30,
            "spring_penetration_pct": 0.5,
            "sos_ema": 9,
            "vol_surge_mult": 1.5,
            "sl_buffer_atr": 0.5,
            "tp1_ratio": 0.5,
            "trail_atr": 2.0,
        }

    @classmethod
    def get_param_bounds(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "tr_lookback": {"type": "int", "min": 20, "max": 45, "step": 5},
            "spring_penetration_pct": {"type": "float", "min": 0.2, "max": 1.2, "step": 0.1},
            "sos_ema": {"type": "int", "min": 7, "max": 14, "step": 1},
            "vol_surge_mult": {"type": "float", "min": 1.2, "max": 2.2, "step": 0.2},
            "sl_buffer_atr": {"type": "float", "min": 0.3, "max": 1.0, "step": 0.1},
            "trail_atr": {"type": "float", "min": 1.5, "max": 3.0, "step": 0.2},
        }

    def generate_signals(self, closes: np.ndarray, highs: np.ndarray,
                         lows: np.ndarray, volumes: np.ndarray) -> List[StrategySignal]:
        signals = []
        p = self.params
        n = len(closes)
        lookback = int(p["tr_lookback"])
        if n < lookback + 20:
            return signals

        ema_sos = calc_ema(closes, int(p["sos_ema"]))
        atr = calc_atr(highs, lows, closes, 14)
        vol_ma = pd.Series(volumes).rolling(20).mean().values

        for i in range(lookback + 5, n):
            c = float(closes[i])
            atrv = float(atr[i]) if atr[i] > 0 else c * 0.01
            support = np.min(lows[i - lookback: i - 3])
            resistance = np.max(highs[i - lookback: i - 3])
            tr_height = resistance - support
            if tr_height <= atrv * 0.5:
                continue

            # 多头 Spring: 过去 1~4 根内有跌破 support 并收回
            recent_low = np.min(lows[i - 3: i])
            spring_cand = recent_low < support * (1.0 - float(p["spring_penetration_pct"]) / 100.0)
            reclaimed = c > support and c > ema_sos[i]
            vol_ok = volumes[i] >= vol_ma[i] * float(p["vol_surge_mult"])

            if spring_cand and reclaimed and vol_ok:
                sl = recent_low - float(p["sl_buffer_atr"]) * atrv
                tp1 = resistance
                signals.append(StrategySignal(
                    idx=i, side="LONG", entry_price=c,
                    stop_loss=sl, take_profit=tp1,
                    params=self.params, extra={"pattern": "spring_sos"}
                ))

            # 空头 Upthrust (UTAD - 顶背离假突破):
            recent_high = np.max(highs[i - 3: i])
            utad_cand = recent_high > resistance * (1.0 + float(p["spring_penetration_pct"]) / 100.0)
            utad_reclaimed = c < resistance and c < ema_sos[i]
            if utad_cand and utad_reclaimed and vol_ok:
                sl = recent_high + float(p["sl_buffer_atr"]) * atrv
                tp1 = support
                signals.append(StrategySignal(
                    idx=i, side="SHORT", entry_price=c,
                    stop_loss=sl, take_profit=tp1,
                    params=self.params, extra={"pattern": "utad"}
                ))
        return signals

    def simulate_lifecycle(self, closes: np.ndarray, highs: np.ndarray,
                           lows: np.ndarray, volumes: np.ndarray,
                           atr_arr: np.ndarray, start_idx: int,
                           side: str = "LONG") -> Tuple[List[Tuple[float, float, str, int]], int, str]:
        p = self.params
        n = len(closes)
        entry_price = float(closes[start_idx])
        atrv = float(atr_arr[start_idx]) if atr_arr[start_idx] > 0 else entry_price * 0.01

        lookback = int(p["tr_lookback"])
        prev_idx = max(0, start_idx - lookback)
        if side == "LONG":
            resistance = np.max(highs[prev_idx:start_idx])
            sl_price = np.min(lows[max(0, start_idx - 4):start_idx + 1]) - float(p["sl_buffer_atr"]) * atrv
            tp1_price = max(entry_price + atrv, resistance)
        else:
            support = np.min(lows[prev_idx:start_idx])
            sl_price = np.max(highs[max(0, start_idx - 4):start_idx + 1]) + float(p["sl_buffer_atr"]) * atrv
            tp1_price = min(entry_price - atrv, support)

        tp1_done = False
        remaining = 1.0
        exits = []
        peak = entry_price

        for i in range(start_idx + 1, n):
            hi = float(highs[i])
            lo = float(lows[i])
            cur_atr = float(atr_arr[i]) if atr_arr[i] > 0 else atrv

            if not tp1_done and ((lo <= sl_price) if side == "LONG" else (hi >= sl_price)):
                exits.append((remaining, sl_price, "spring_sl", i))
                return exits, i - start_idx, "spring_sl"

            if not tp1_done and ((hi >= tp1_price) if side == "LONG" else (lo <= tp1_price)):
                tp1_done = True
                exits.append((0.5, tp1_price, "spring_tp1", i))
                remaining = 0.5
                sl_price = entry_price

            if tp1_done:
                if side == "LONG":
                    peak = max(peak, hi)
                    trail_stop = peak - float(p["trail_atr"]) * cur_atr
                    eff_stop = max(sl_price, trail_stop)
                    if lo <= eff_stop:
                        exits.append((remaining, eff_stop, "trail_exit", i))
                        return exits, i - start_idx, "trail_exit"
                else:
                    peak = min(peak, lo)
                    trail_stop = peak + float(p["trail_atr"]) * cur_atr
                    eff_stop = min(sl_price, trail_stop)
                    if hi >= eff_stop:
                        exits.append((remaining, eff_stop, "trail_exit", i))
                        return exits, i - start_idx, "trail_exit"

        if remaining > 0:
            exits.append((remaining, float(closes[-1]), "eod", n - 1))
        return exits, n - 1 - start_idx, "eod"


# =====================================================================
# 9. ICT 经典银弹与 Killzone 流动性掠夺策略 (ICT Silver Bullet)
# =====================================================================
class ICTSilverBulletStrategy(BaseCandidateStrategy):
    id = "ict_silver_bullet"
    name = "ICT Silver Bullet & Killzone"
    title = "ICT经典银弹与Killzone流动性掠夺策略"
    description = "ICT银弹模型：高低点流动性掠夺(BSL/SSL) + 市场结构突变(MSS) + 公允价值缺口(FVG)回踩入场"
    timeframe = "15m"
    category = "smart_money"
    default_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "pivot_lookback": 15,
            "fvg_min_atr": 0.4,
            "displacement_body_pct": 55,
            "tp_rr": 2.5,
            "sl_buffer_atr": 0.3,
            "trail_atr": 1.8,
        }

    @classmethod
    def get_param_bounds(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "pivot_lookback": {"type": "int", "min": 10, "max": 25, "step": 5},
            "fvg_min_atr": {"type": "float", "min": 0.2, "max": 0.8, "step": 0.1},
            "displacement_body_pct": {"type": "float", "min": 45.0, "max": 75.0, "step": 5.0},
            "tp_rr": {"type": "float", "min": 1.5, "max": 3.5, "step": 0.5},
            "trail_atr": {"type": "float", "min": 1.2, "max": 2.6, "step": 0.2},
        }

    def generate_signals(self, closes: np.ndarray, highs: np.ndarray,
                         lows: np.ndarray, volumes: np.ndarray) -> List[StrategySignal]:
        signals = []
        p = self.params
        n = len(closes)
        lookback = int(p["pivot_lookback"])
        if n < lookback + 20:
            return signals

        atr = calc_atr(highs, lows, closes, 14)

        for i in range(lookback + 5, n - 1):
            c = float(closes[i])
            atrv = float(atr[i]) if atr[i] > 0 else c * 0.01

            prev_high = np.max(highs[i - lookback: i - 2])
            prev_low = np.min(lows[i - lookback: i - 2])

            candle_body = abs(closes[i] - float(closes[i-1]))
            candle_range = highs[i] - lows[i] if highs[i] > lows[i] else atrv
            body_pct = (candle_body / candle_range) * 100.0

            bullish_fvg = (lows[i] - highs[i-2]) > float(p["fvg_min_atr"]) * atrv
            ssl_sweep = np.min(lows[i-3: i]) <= prev_low

            if bullish_fvg and ssl_sweep and body_pct >= float(p["displacement_body_pct"]):
                entry = c
                sl = np.min(lows[i-3: i+1]) - float(p["sl_buffer_atr"]) * atrv
                risk = max(atrv * 0.5, entry - sl)
                tp = entry + risk * float(p["tp_rr"])
                signals.append(StrategySignal(
                    idx=i, side="LONG", entry_price=entry,
                    stop_loss=sl, take_profit=tp,
                    params=self.params, extra={"fvg_gap": float(lows[i] - highs[i-2])}
                ))

            bearish_fvg = (lows[i-2] - highs[i]) > float(p["fvg_min_atr"]) * atrv
            bsl_sweep = np.max(highs[i-3: i]) >= prev_high

            if bearish_fvg and bsl_sweep and body_pct >= float(p["displacement_body_pct"]):
                entry = c
                sl = np.max(highs[i-3: i+1]) + float(p["sl_buffer_atr"]) * atrv
                risk = max(atrv * 0.5, sl - entry)
                tp = entry - risk * float(p["tp_rr"])
                signals.append(StrategySignal(
                    idx=i, side="SHORT", entry_price=entry,
                    stop_loss=sl, take_profit=tp,
                    params=self.params, extra={"fvg_gap": float(lows[i-2] - highs[i])}
                ))
        return signals

    def simulate_lifecycle(self, closes: np.ndarray, highs: np.ndarray,
                           lows: np.ndarray, volumes: np.ndarray,
                           atr_arr: np.ndarray, start_idx: int,
                           side: str = "LONG") -> Tuple[List[Tuple[float, float, str, int]], int, str]:
        p = self.params
        n = len(closes)
        entry_price = float(closes[start_idx])
        atrv = float(atr_arr[start_idx]) if atr_arr[start_idx] > 0 else entry_price * 0.01

        if side == "LONG":
            sl_price = np.min(lows[max(0, start_idx - 3):start_idx + 1]) - float(p["sl_buffer_atr"]) * atrv
            risk = max(atrv * 0.5, entry_price - sl_price)
            tp1_price = entry_price + risk * 1.5
            tp2_price = entry_price + risk * float(p["tp_rr"])
        else:
            sl_price = np.max(highs[max(0, start_idx - 3):start_idx + 1]) + float(p["sl_buffer_atr"]) * atrv
            risk = max(atrv * 0.5, sl_price - entry_price)
            tp1_price = entry_price - risk * 1.5
            tp2_price = entry_price - risk * float(p["tp_rr"])

        tp1_done = False
        remaining = 1.0
        exits = []
        peak = entry_price

        for i in range(start_idx + 1, n):
            hi = float(highs[i])
            lo = float(lows[i])
            cur_atr = float(atr_arr[i]) if atr_arr[i] > 0 else atrv

            if not tp1_done and ((lo <= sl_price) if side == "LONG" else (hi >= sl_price)):
                exits.append((remaining, sl_price, "ict_sl", i))
                return exits, i - start_idx, "ict_sl"

            if not tp1_done and ((hi >= tp1_price) if side == "LONG" else (lo <= tp1_price)):
                tp1_done = True
                exits.append((0.5, tp1_price, "ict_tp1", i))
                remaining = 0.5
                sl_price = entry_price

            if tp1_done:
                if (hi >= tp2_price if side == "LONG" else lo <= tp2_price):
                    exits.append((remaining, tp2_price, "ict_tp2_full", i))
                    return exits, i - start_idx, "ict_tp2_full"

                if side == "LONG":
                    peak = max(peak, hi)
                    trail_stop = peak - float(p["trail_atr"]) * cur_atr
                    eff_stop = max(sl_price, trail_stop)
                    if lo <= eff_stop:
                        exits.append((remaining, eff_stop, "trail_exit", i))
                        return exits, i - start_idx, "trail_exit"
                else:
                    peak = min(peak, lo)
                    trail_stop = peak + float(p["trail_atr"]) * cur_atr
                    eff_stop = min(sl_price, trail_stop)
                    if hi >= eff_stop:
                        exits.append((remaining, eff_stop, "trail_exit", i))
                        return exits, i - start_idx, "trail_exit"

        if remaining > 0:
            exits.append((remaining, float(closes[-1]), "eod", n - 1))
        return exits, n - 1 - start_idx, "eod"


# =====================================================================
# 10. AMD 亚洲盘流动性诱捕与诱导假突破策略 (AMD Asian Session)
# =====================================================================
class AMDAsianSessionStrategy(BaseCandidateStrategy):
    id = "amd_asian_session"
    name = "AMD Asian Session Manipulation"
    title = "AMD亚洲盘流动性诱捕与诱导假突破策略"
    description = "经典AMD模型：亚洲盘积累(Accumulation)+欧美开盘假突破诱导(Judas Manipulation)+极速反向派发(Distribution)"
    timeframe = "15m"
    category = "momentum"
    default_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "session_bars": 24,
            "fake_spike_atr": 0.8,
            "reversal_bars": 3,
            "tp_rr": 2.2,
            "sl_buffer_atr": 0.4,
            "trail_atr": 1.6,
        }

    @classmethod
    def get_param_bounds(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "session_bars": {"type": "int", "min": 16, "max": 32, "step": 4},
            "fake_spike_atr": {"type": "float", "min": 0.4, "max": 1.5, "step": 0.2},
            "reversal_bars": {"type": "int", "min": 2, "max": 5, "step": 1},
            "tp_rr": {"type": "float", "min": 1.5, "max": 3.2, "step": 0.3},
            "trail_atr": {"type": "float", "min": 1.2, "max": 2.4, "step": 0.2},
        }

    def generate_signals(self, closes: np.ndarray, highs: np.ndarray,
                         lows: np.ndarray, volumes: np.ndarray) -> List[StrategySignal]:
        signals = []
        p = self.params
        n = len(closes)
        s_bars = int(p["session_bars"])
        if n < s_bars + 20:
            return signals

        atr = calc_atr(highs, lows, closes, 14)

        for i in range(s_bars + 10, n):
            c = float(closes[i])
            atrv = float(atr[i]) if atr[i] > 0 else c * 0.01

            s_high = np.max(highs[i - s_bars: i - 3])
            s_low = np.min(lows[i - s_bars: i - 3])
            spike_threshold = float(p["fake_spike_atr"]) * atrv

            spike_high = np.max(highs[i - int(p["reversal_bars"]): i + 1])
            if spike_high >= s_high + spike_threshold and c < s_high:
                sl = spike_high + float(p["sl_buffer_atr"]) * atrv
                risk = max(atrv * 0.5, sl - c)
                signals.append(StrategySignal(
                    idx=i, side="SHORT", entry_price=c,
                    stop_loss=sl, take_profit=c - risk * float(p["tp_rr"]),
                    params=self.params, extra={"amd": "bearish_distribution"}
                ))

            spike_low = np.min(lows[i - int(p["reversal_bars"]): i + 1])
            if spike_low <= s_low - spike_threshold and c > s_low:
                sl = spike_low - float(p["sl_buffer_atr"]) * atrv
                risk = max(atrv * 0.5, c - sl)
                signals.append(StrategySignal(
                    idx=i, side="LONG", entry_price=c,
                    stop_loss=sl, take_profit=c + risk * float(p["tp_rr"]),
                    params=self.params, extra={"amd": "bullish_distribution"}
                ))
        return signals

    def simulate_lifecycle(self, closes: np.ndarray, highs: np.ndarray,
                           lows: np.ndarray, volumes: np.ndarray,
                           atr_arr: np.ndarray, start_idx: int,
                           side: str = "LONG") -> Tuple[List[Tuple[float, float, str, int]], int, str]:
        p = self.params
        n = len(closes)
        entry_price = float(closes[start_idx])
        atrv = float(atr_arr[start_idx]) if atr_arr[start_idx] > 0 else entry_price * 0.01

        lookback = int(p["reversal_bars"]) + 1
        if side == "LONG":
            sl_price = np.min(lows[max(0, start_idx - lookback):start_idx + 1]) - float(p["sl_buffer_atr"]) * atrv
            risk = max(atrv * 0.5, entry_price - sl_price)
            tp1_price = entry_price + risk * 1.2
            tp2_price = entry_price + risk * float(p["tp_rr"])
        else:
            sl_price = np.max(highs[max(0, start_idx - lookback):start_idx + 1]) + float(p["sl_buffer_atr"]) * atrv
            risk = max(atrv * 0.5, sl_price - entry_price)
            tp1_price = entry_price - risk * 1.2
            tp2_price = entry_price - risk * float(p["tp_rr"])

        tp1_done = False
        remaining = 1.0
        exits = []
        peak = entry_price

        for i in range(start_idx + 1, n):
            hi = float(highs[i])
            lo = float(lows[i])
            cur_atr = float(atr_arr[i]) if atr_arr[i] > 0 else atrv

            if not tp1_done and ((lo <= sl_price) if side == "LONG" else (hi >= sl_price)):
                exits.append((remaining, sl_price, "amd_sl", i))
                return exits, i - start_idx, "amd_sl"

            if not tp1_done and ((hi >= tp1_price) if side == "LONG" else (lo <= tp1_price)):
                tp1_done = True
                exits.append((0.5, tp1_price, "amd_tp1", i))
                remaining = 0.5
                sl_price = entry_price

            if tp1_done:
                if (hi >= tp2_price if side == "LONG" else lo <= tp2_price):
                    exits.append((remaining, tp2_price, "amd_tp2", i))
                    return exits, i - start_idx, "amd_tp2"

                if side == "LONG":
                    peak = max(peak, hi)
                    trail_stop = peak - float(p["trail_atr"]) * cur_atr
                    eff_stop = max(sl_price, trail_stop)
                    if lo <= eff_stop:
                        exits.append((remaining, eff_stop, "trail_exit", i))
                        return exits, i - start_idx, "trail_exit"
                else:
                    peak = min(peak, lo)
                    trail_stop = peak + float(p["trail_atr"]) * cur_atr
                    eff_stop = min(sl_price, trail_stop)
                    if hi >= eff_stop:
                        exits.append((remaining, eff_stop, "trail_exit", i))
                        return exits, i - start_idx, "trail_exit"

        if remaining > 0:
            exits.append((remaining, float(closes[-1]), "eod", n - 1))
        return exits, n - 1 - start_idx, "eod"


# =====================================================================
# 11. 成交量分布图 (Volume Profile) 与 POC 高价值区回踩策略
# =====================================================================
class VolumeProfilePOCStrategy(BaseCandidateStrategy):
    id = "volume_profile_poc"
    name = "Volume Profile POC Reversion"
    title = "成交量分布图(Volume Profile)与POC高价值区回踩策略"
    description = "成交量分布图模型：高价值区POC锚定 + 价值区高低沿(VAH/VAL)支撑阻力 + 回踩放量弹射"
    timeframe = "15m"
    category = "volume"
    default_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "vp_lookback": 48,
            "bins": 18,
            "poc_touch_atr": 0.5,
            "sl_atr": 1.5,
            "tp_rr": 2.2,
            "trail_atr": 1.8,
        }

    @classmethod
    def get_param_bounds(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "vp_lookback": {"type": "int", "min": 30, "max": 60, "step": 6},
            "bins": {"type": "int", "min": 12, "max": 24, "step": 2},
            "poc_touch_atr": {"type": "float", "min": 0.3, "max": 0.8, "step": 0.1},
            "sl_atr": {"type": "float", "min": 1.0, "max": 2.2, "step": 0.2},
            "tp_rr": {"type": "float", "min": 1.5, "max": 3.0, "step": 0.3},
            "trail_atr": {"type": "float", "min": 1.2, "max": 2.5, "step": 0.2},
        }

    @staticmethod
    def _calc_poc(window_closes: np.ndarray, window_volumes: np.ndarray, bins: int) -> float:
        min_p = np.min(window_closes)
        max_p = np.max(window_closes)
        if max_p <= min_p:
            return float(min_p)
        bin_edges = np.linspace(min_p, max_p, bins + 1)
        bin_indices = np.clip(np.digitize(window_closes, bin_edges) - 1, 0, bins - 1)
        bin_vols = np.zeros(bins)
        for b_idx, vol in zip(bin_indices, window_volumes):
            bin_vols[b_idx] += vol
        max_bin = int(np.argmax(bin_vols))
        poc = (bin_edges[max_bin] + bin_edges[max_bin + 1]) / 2.0
        return float(poc)

    def generate_signals(self, closes: np.ndarray, highs: np.ndarray,
                         lows: np.ndarray, volumes: np.ndarray) -> List[StrategySignal]:
        signals = []
        p = self.params
        n = len(closes)
        lookback = int(p["vp_lookback"])
        bins = int(p["bins"])
        if n < lookback + 20:
            return signals

        atr = calc_atr(highs, lows, closes, 14)
        ema50 = calc_ema(closes, 50)

        for i in range(lookback + 5, n):
            c = float(closes[i])
            atrv = float(atr[i]) if atr[i] > 0 else c * 0.01

            poc = self._calc_poc(closes[i - lookback: i], volumes[i - lookback: i], bins)
            touch_tol = float(p["poc_touch_atr"]) * atrv

            if c > ema50[i] and (lows[i] <= poc + touch_tol) and c >= poc:
                sl = poc - float(p["sl_atr"]) * atrv
                risk = max(atrv * 0.5, c - sl)
                signals.append(StrategySignal(
                    idx=i, side="LONG", entry_price=c,
                    stop_loss=sl, take_profit=c + risk * float(p["tp_rr"]),
                    params=self.params, extra={"poc": poc}
                ))
            elif c < ema50[i] and (highs[i] >= poc - touch_tol) and c <= poc:
                sl = poc + float(p["sl_atr"]) * atrv
                risk = max(atrv * 0.5, sl - c)
                signals.append(StrategySignal(
                    idx=i, side="SHORT", entry_price=c,
                    stop_loss=sl, take_profit=c - risk * float(p["tp_rr"]),
                    params=self.params, extra={"poc": poc}
                ))
        return signals

    def simulate_lifecycle(self, closes: np.ndarray, highs: np.ndarray,
                           lows: np.ndarray, volumes: np.ndarray,
                           atr_arr: np.ndarray, start_idx: int,
                           side: str = "LONG") -> Tuple[List[Tuple[float, float, str, int]], int, str]:
        p = self.params
        n = len(closes)
        entry_price = float(closes[start_idx])
        atrv = float(atr_arr[start_idx]) if atr_arr[start_idx] > 0 else entry_price * 0.01

        sl_dist = float(p["sl_atr"]) * atrv
        sl_price = entry_price - sl_dist if side == "LONG" else entry_price + sl_dist
        tp1_price = entry_price + sl_dist * 1.5 if side == "LONG" else entry_price - sl_dist * 1.5
        tp2_price = entry_price + sl_dist * float(p["tp_rr"]) if side == "LONG" else entry_price - sl_dist * float(p["tp_rr"])

        tp1_done = False
        remaining = 1.0
        exits = []
        peak = entry_price

        for i in range(start_idx + 1, n):
            hi = float(highs[i])
            lo = float(lows[i])
            cur_atr = float(atr_arr[i]) if atr_arr[i] > 0 else atrv

            if not tp1_done and ((lo <= sl_price) if side == "LONG" else (hi >= sl_price)):
                exits.append((remaining, sl_price, "poc_sl", i))
                return exits, i - start_idx, "poc_sl"

            if not tp1_done and ((hi >= tp1_price) if side == "LONG" else (lo <= tp1_price)):
                tp1_done = True
                exits.append((0.5, tp1_price, "poc_tp1", i))
                remaining = 0.5
                sl_price = entry_price

            if tp1_done:
                if (hi >= tp2_price if side == "LONG" else lo <= tp2_price):
                    exits.append((remaining, tp2_price, "poc_tp2", i))
                    return exits, i - start_idx, "poc_tp2"

                if side == "LONG":
                    peak = max(peak, hi)
                    trail_stop = peak - float(p["trail_atr"]) * cur_atr
                    eff_stop = max(sl_price, trail_stop)
                    if lo <= eff_stop:
                        exits.append((remaining, eff_stop, "trail_exit", i))
                        return exits, i - start_idx, "trail_exit"
                else:
                    peak = min(peak, lo)
                    trail_stop = peak + float(p["trail_atr"]) * cur_atr
                    eff_stop = min(sl_price, trail_stop)
                    if hi >= eff_stop:
                        exits.append((remaining, eff_stop, "trail_exit", i))
                        return exits, i - start_idx, "trail_exit"

        if remaining > 0:
            exits.append((remaining, float(closes[-1]), "eod", n - 1))
        return exits, n - 1 - start_idx, "eod"


# =====================================================================
# 12. 极端放量旗形突破与动量中继战法策略 (Momentum Flag Relay)
# =====================================================================
class MomentumFlagRelayStrategy(BaseCandidateStrategy):
    id = "momentum_flag_relay"
    name = "Extreme Volume Flag Breakout"
    title = "极端放量旗形突破与动量中继战法策略"
    description = "动量旗形模型：旗杆剧烈脉冲拉升 + 旗面缩量窄幅休整 + 突破旗形通道放量二次主升"
    timeframe = "15m"
    category = "momentum"
    default_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"]

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "pole_bars": 5,
            "pole_surge_pct": 2.5,
            "flag_bars": 6,
            "vol_shrink_ratio": 0.65,
            "sl_atr": 1.3,
            "tp_rr": 2.4,
            "trail_atr": 1.8,
        }

    @classmethod
    def get_param_bounds(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "pole_bars": {"type": "int", "min": 3, "max": 7, "step": 1},
            "pole_surge_pct": {"type": "float", "min": 1.5, "max": 4.5, "step": 0.5},
            "flag_bars": {"type": "int", "min": 4, "max": 10, "step": 1},
            "vol_shrink_ratio": {"type": "float", "min": 0.4, "max": 0.8, "step": 0.05},
            "sl_atr": {"type": "float", "min": 0.9, "max": 2.0, "step": 0.1},
            "tp_rr": {"type": "float", "min": 1.5, "max": 3.5, "step": 0.3},
            "trail_atr": {"type": "float", "min": 1.2, "max": 2.5, "step": 0.2},
        }

    def generate_signals(self, closes: np.ndarray, highs: np.ndarray,
                         lows: np.ndarray, volumes: np.ndarray) -> List[StrategySignal]:
        signals = []
        p = self.params
        n = len(closes)
        pole_len = int(p["pole_bars"])
        flag_len = int(p["flag_bars"])
        total_pattern = pole_len + flag_len
        if n < total_pattern + 20:
            return signals

        atr = calc_atr(highs, lows, closes, 14)
        vol_ma = pd.Series(volumes).rolling(20).mean().values

        for i in range(total_pattern + 5, n):
            c = float(closes[i])
            atrv = float(atr[i]) if atr[i] > 0 else c * 0.01

            pole_start = i - flag_len - pole_len
            pole_end = i - flag_len
            flag_start = pole_end
            flag_end = i

            pole_ret = (closes[pole_end] - closes[pole_start]) / closes[pole_start] * 100.0
            pole_avg_vol = np.mean(volumes[pole_start:pole_end])
            flag_avg_vol = np.mean(volumes[flag_start:flag_end])

            # 牛旗识别
            if pole_ret >= float(p["pole_surge_pct"]) and pole_avg_vol > vol_ma[pole_end] * 1.3:
                if flag_avg_vol <= pole_avg_vol * float(p["vol_shrink_ratio"]):
                    flag_high = np.max(highs[flag_start:flag_end])
                    if c > flag_high and volumes[i] >= vol_ma[i] * 1.2:
                        sl = np.min(lows[flag_start:flag_end]) - float(p["sl_atr"]) * atrv
                        risk = max(atrv * 0.5, c - sl)
                        signals.append(StrategySignal(
                            idx=i, side="LONG", entry_price=c,
                            stop_loss=sl, take_profit=c + risk * float(p["tp_rr"]),
                            params=self.params, extra={"flag_type": "bull_flag"}
                        ))

            # 熊旗识别
            bear_pole_ret = (closes[pole_start] - closes[pole_end]) / closes[pole_start] * 100.0
            if bear_pole_ret >= float(p["pole_surge_pct"]) and pole_avg_vol > vol_ma[pole_end] * 1.3:
                if flag_avg_vol <= pole_avg_vol * float(p["vol_shrink_ratio"]):
                    flag_low = np.min(lows[flag_start:flag_end])
                    if c < flag_low and volumes[i] >= vol_ma[i] * 1.2:
                        sl = np.max(highs[flag_start:flag_end]) + float(p["sl_atr"]) * atrv
                        risk = max(atrv * 0.5, sl - c)
                        signals.append(StrategySignal(
                            idx=i, side="SHORT", entry_price=c,
                            stop_loss=sl, take_profit=c - risk * float(p["tp_rr"]),
                            params=self.params, extra={"flag_type": "bear_flag"}
                        ))
        return signals

    def simulate_lifecycle(self, closes: np.ndarray, highs: np.ndarray,
                           lows: np.ndarray, volumes: np.ndarray,
                           atr_arr: np.ndarray, start_idx: int,
                           side: str = "LONG") -> Tuple[List[Tuple[float, float, str, int]], int, str]:
        p = self.params
        n = len(closes)
        entry_price = float(closes[start_idx])
        atrv = float(atr_arr[start_idx]) if atr_arr[start_idx] > 0 else entry_price * 0.01

        flag_lookback = int(p["flag_bars"])
        if side == "LONG":
            flag_base = np.min(lows[max(0, start_idx - flag_lookback):start_idx])
            sl_price = flag_base - float(p["sl_atr"]) * atrv
            risk = max(atrv * 0.5, entry_price - sl_price)
            tp1_price = entry_price + risk * 1.3
            tp2_price = entry_price + risk * float(p["tp_rr"])
        else:
            flag_top = np.max(highs[max(0, start_idx - flag_lookback):start_idx])
            sl_price = flag_top + float(p["sl_atr"]) * atrv
            risk = max(atrv * 0.5, sl_price - entry_price)
            tp1_price = entry_price - risk * 1.3
            tp2_price = entry_price - risk * float(p["tp_rr"])

        tp1_done = False
        remaining = 1.0
        exits = []
        peak = entry_price

        for i in range(start_idx + 1, n):
            hi = float(highs[i])
            lo = float(lows[i])
            cur_atr = float(atr_arr[i]) if atr_arr[i] > 0 else atrv

            if not tp1_done and ((lo <= sl_price) if side == "LONG" else (hi >= sl_price)):
                exits.append((remaining, sl_price, "flag_sl", i))
                return exits, i - start_idx, "flag_sl"

            if not tp1_done and ((hi >= tp1_price) if side == "LONG" else (lo <= tp1_price)):
                tp1_done = True
                exits.append((0.5, tp1_price, "flag_tp1", i))
                remaining = 0.5
                sl_price = entry_price

            if tp1_done:
                if (hi >= tp2_price if side == "LONG" else lo <= tp2_price):
                    exits.append((remaining, tp2_price, "flag_tp2", i))
                    return exits, i - start_idx, "flag_tp2"

                if side == "LONG":
                    peak = max(peak, hi)
                    trail_stop = peak - float(p["trail_atr"]) * cur_atr
                    eff_stop = max(sl_price, trail_stop)
                    if lo <= eff_stop:
                        exits.append((remaining, eff_stop, "trail_exit", i))
                        return exits, i - start_idx, "trail_exit"
                else:
                    peak = min(peak, lo)
                    trail_stop = peak + float(p["trail_atr"]) * cur_atr
                    eff_stop = min(sl_price, trail_stop)
                    if hi >= eff_stop:
                        exits.append((remaining, eff_stop, "trail_exit", i))
                        return exits, i - start_idx, "trail_exit"

        if remaining > 0:
            exits.append((remaining, float(closes[-1]), "eod", n - 1))
        return exits, n - 1 - start_idx, "eod"


# 策略全集映射表 (完整12大策略体系)
CANDIDATE_STRATEGIES_REGISTRY: Dict[str, Any] = {
    "grid_martingale": DCAMartingaleStrategy,
    "smart_money": SMCOrderBlockStrategy,
    "ttm_squeeze": TTMSqueezeStrategy,
    "vwap_reversion": VWAPReversionStrategy,
    "turtle_breakout": TurtleBreakoutStrategy,
    "ema_rsi_divergence": EMARSIDivergenceStrategy,
    "trend_following": EMATrendStrategy,
    "wyckoff_spring": WyckoffSpringStrategy,
    "ict_silver_bullet": ICTSilverBulletStrategy,
    "amd_asian_session": AMDAsianSessionStrategy,
    "volume_profile_poc": VolumeProfilePOCStrategy,
    "momentum_flag_relay": MomentumFlagRelayStrategy,
}


def get_candidate_strategy(strategy_id: str, params: Optional[Dict[str, Any]] = None) -> BaseCandidateStrategy:
    """按 strategy_id 实例化策略"""
    cls = CANDIDATE_STRATEGIES_REGISTRY.get(strategy_id)
    if not cls:
        alt_map = {
            "dca": "grid_martingale",
            "martingale": "grid_martingale",
            "smc": "smart_money",
            "squeeze": "ttm_squeeze",
            "vwap": "vwap_reversion",
            "turtle": "turtle_breakout",
            "divergence": "ema_rsi_divergence",
            "trend": "trend_following",
            "ema": "trend_following",
            "wyckoff": "wyckoff_spring",
            "spring": "wyckoff_spring",
            "ict": "ict_silver_bullet",
            "silver_bullet": "ict_silver_bullet",
            "amd": "amd_asian_session",
            "asian": "amd_asian_session",
            "volume_profile": "volume_profile_poc",
            "poc": "volume_profile_poc",
            "flag": "momentum_flag_relay",
            "momentum_flag": "momentum_flag_relay",
        }
        mapped = alt_map.get(strategy_id.lower())
        cls = CANDIDATE_STRATEGIES_REGISTRY.get(mapped, EMATrendStrategy)
    return cls(params)

