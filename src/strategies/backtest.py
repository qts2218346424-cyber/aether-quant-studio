"""策略回测引擎

真实成本建模(从实盘与盘口实测):
  - 手续费 0.05% 单边(币安 USDT 合约 taker 标准档, 与实盘 commission 反推一致)
  - 滑点     按盘口深度实测, 小市值币约 0.02% 单边
  - 资金费率 每 8 小时结算一次, 按持仓时长计提

用法:
    python backtest.py                      # 基线回测
    python backtest.py --days 20            # 指定历史天数
    python backtest.py --scan threshold     # 扫描信号阈值
    python backtest.py --scan exit          # 扫描止盈止损组合
    python backtest.py --scan factor        # 因子贡献度分析
"""
import argparse
import asyncio
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from binance_client import BinanceFuturesClient
from config import load_config
from strategy import StrategyEngine, calc_atr, calc_ema

# ========== 成本模型(实测值, 见模块 docstring) ==========
TAKER_FEE_PCT = 0.05      # 单边手续费%
MAKER_FEE_PCT = 0.02      # 限价单单边手续费%
DEFAULT_SLIP_PCT = 0.02   # 单边滑点%(小市值币 100U 名义实测均值)
FUNDING_PCT_PER_8H = 0.01  # 资金费率%每8小时(中性假设, 实际按币种浮动)

BARS_PER_8H = {"1m": 480, "3m": 160, "5m": 96, "15m": 32, "30m": 16, "1h": 8}


@dataclass
class ExitParams:
    """平仓参数(对应 config.json 的 position_management)"""
    sl_atr: float = 3.0            # 软止损 ATR 倍数
    tp1_atr: float = 1.5           # 第一止盈 ATR 倍数
    tp2_atr: float = 2.5           # 第二止盈 ATR 倍数
    partial_pct: float = 0.5       # 每次分批减仓比例
    trail_atr: float = 1.5         # 跟踪止损 ATR 倍数
    lock_profit_atr: float = 0.4   # 保本锁利 ATR 倍数
    hard_stop_pct: float = 4.0     # 硬止损百分比
    max_margin_loss_pct: float = 0.0  # 保证金损失上限(0=不启用, 实盘45/杠杆)
    min_stop_pct: float = 2.2      # 软止损下限%(实盘 min_stop_pct)
    stop_conf_candles: int = 2     # 软止损需连续确认的收盘根数
    trail_after_tp: int = 1        # 第几次止盈后启动跟踪(1 或 2)
    max_hold_bars: int = 0         # 最大持仓K线数, 0=不限
    leverage: float = 1.0          # 杠杆倍数(仅用于max_margin_loss_pct换算)
    ema20_exit: bool = False       # 价格跌破/升破EMA20退出(用户信号2)
    ema20_confirm: int = 2         # 连续N根收盘确认才清仓
    breakout_fail_exit: bool = False  # 孤立高低点两次突破未果退出(用户信号1)
    breakout_fail_count: int = 2   # 突破失败N次后清仓
    peak_drawdown_atr: float = 0.0  # 峰值回撤止损: 浮盈≥1ATR后, 从持仓峰值回撤≥N×ATR即清仓(0=关闭)


@dataclass
class CostParams:
    """成本参数"""
    entry_fee_pct: float = TAKER_FEE_PCT
    exit_fee_pct: float = TAKER_FEE_PCT
    slip_pct: float = DEFAULT_SLIP_PCT
    funding_pct_per_8h: float = FUNDING_PCT_PER_8H
    apply_funding: bool = True


@dataclass
class Trade:
    """一笔完整交易(含分批平仓明细)"""
    symbol: str
    side: str
    entry_idx: int
    entry_price: float
    entry_time: int
    exits: list = field(default_factory=list)  # [(比例, 价格, 原因, idx)]
    gross_pct: float = 0.0   # 毛收益%(按仓位加权)
    cost_pct: float = 0.0    # 总成本%
    net_pct: float = 0.0     # 净收益%
    hold_bars: int = 0
    final_reason: str = ""

    @property
    def closed_ratio(self) -> float:
        return sum(r for r, _, _, _ in self.exits)


class PositionSim:
    """多腿仓位模拟: 首腿 + 回调加仓腿, 分批减仓按剩余比例结算。

    向后兼容: entry_price/entry_idx/remaining/close 语义不变,
    单腿时 avg_entry == entry_price, 旧回测行为完全一致。
    """

    def __init__(self, side: str, entry_price: float, entry_idx: int):
        self.side = side
        self.entry_price = entry_price
        self.entry_idx = entry_idx
        self.legs: list = [{"price": entry_price, "ratio": 1.0, "idx": entry_idx}]
        self.add_count = 0          # 已加仓次数
        self.remaining = 1.0        # 相对首腿的剩余比例(含加仓腿, 最大 1+0.5*n)
        self.exits: list = []
        self.tp1_done = False
        self.tp2_done = False
        self.peak = entry_price
        self.stop_breach = 0
        self.breakeven_on = False   # 保本激活持久标记(激活后不因加仓摊高均价而关闭)

    @property
    def is_long(self) -> bool:
        return self.side == "LONG"

    @property
    def avg_entry(self) -> float:
        total_ratio = sum(leg["ratio"] for leg in self.legs)
        if total_ratio <= 0:
            return self.entry_price
        return sum(leg["price"] * leg["ratio"] for leg in self.legs) / total_ratio

    def pnl_pct_at(self, price: float) -> float:
        avg = self.avg_entry
        if self.is_long:
            return (price - avg) / avg * 100
        return (avg - price) / avg * 100

    @property
    def peak_pnl(self) -> float:
        return self.pnl_pct_at(self.peak)

    def add_leg(self, price: float, ratio: float, idx: int):
        """回调加仓: ratio 相对首腿(如 0.5), 记录加仓价与位置"""
        self.legs.append({"price": price, "ratio": ratio, "idx": idx})
        self.remaining += ratio
        self.add_count += 1

    def update_peak(self, high: float, low: float):
        self.peak = max(self.peak, high) if self.is_long else min(self.peak, low)

    def close(self, ratio: float, price: float, reason: str, idx: int) -> float:
        """按比例平仓(相对当前总仓位), 返回实际平掉的比例"""
        ratio = min(ratio, self.remaining)
        if ratio <= 0:
            return 0.0
        self.exits.append((ratio, price, reason, idx))
        self.remaining -= ratio
        return ratio


@dataclass
class ManualParams:
    """手动打法参数(模仿 BLESS/ERA 成功单的加仓与锁利节奏)"""
    pullback_pct: float = 2.5    # 峰值浮盈回撤多少%触发加仓
    add_ratio: float = 0.5       # 每次加仓比例(相对首腿)
    max_adds: int = 3            # 最多加仓次数
    breakeven_pct: float = 2.0   # 峰值浮盈达到多少%后激活保本止损
    tp1_pct: float = 5.0         # 第一止盈: 浮盈%平 1/3
    tp2_pct: float = 8.0         # 第二止盈: 浮盈%再平 1/3
    tp_ratio: float = 1.0 / 3.0  # 每次止盈平仓比例(相对当前仓位)
    trail_atr: float = 2.0       # 尾仓跟踪止损 ATR 倍数
    hard_stop_pct: float = 6.0   # 硬止损%(沿用实盘)
    min_stop_pct: float = 2.2    # 软止损下限%(沿用实盘)
    sl_atr: float = 3.0          # 软止损 ATR 倍数(沿用)
    stop_conf_candles: int = 2   # 软止损连续确认根数
    max_hold_bars: int = 0       # 最大持仓K线数, 0=不限


def maybe_add_leg(pos: PositionSim, price: float, params: ManualParams) -> bool:
    """回调加仓判定: 峰值浮盈后从峰值回撤 >= pullback_pct, 且仍浮盈, 且未超次数。

    只做顺势回调加仓, 浮亏状态绝不摊平。
    """
    if pos.add_count >= params.max_adds:
        return False
    pnl_now = pos.pnl_pct_at(price)
    if pnl_now <= 0:
        return False
    peak = pos.peak_pnl
    if peak < params.pullback_pct + 0.5:
        # 峰值利润不足一个回调幅度, 没有"回调"可言
        return False
    return peak - pnl_now >= params.pullback_pct


def breakeven_active(pos: PositionSim, params: ManualParams) -> bool:
    """首笔(或加仓后组合)峰值浮盈达到 breakeven_pct 后激活保本。

    激活后止损线上移到加权均价(全部腿), 回调到均价即全平, 不亏本金。
    """
    return pos.peak_pnl >= params.breakeven_pct


def simulate_trade_manual(pos: PositionSim, closes, highs, lows, atr_arr,
                          params: ManualParams, interval: str) -> tuple:
    """手动打法生命周期: 硬止损 → 保本 → 回调加仓 → 分批止盈 → 尾仓跟踪 → 软止损 → 超时

    返回 (exits, hold_bars, final_reason), 与 simulate_trade 同构,
    供 backtest_symbol 的 manual 分支直接复用。
    """
    n = len(closes)
    for i in range(pos.entry_idx + 1, n):
        if pos.remaining <= 1e-9:
            break
        c = float(closes[i])
        hi = float(highs[i])
        lo = float(lows[i])
        atr = float(atr_arr[i]) if i < len(atr_arr) and atr_arr[i] > 0 else 0.0
        pos.update_peak(hi, lo)
        avg = pos.avg_entry

        # 1) 硬止损: 百分比固定, 优先级最高(相对加权均价, 全腿保护)
        hard_dist = avg * params.hard_stop_pct / 100
        hard_stop = avg - hard_dist if pos.is_long else avg + hard_dist
        hard_hit = (lo <= hard_stop) if pos.is_long else (hi >= hard_stop)
        if hard_hit:
            pos.close(pos.remaining, hard_stop, "hard_stop", i)
            return pos.exits, i - pos.entry_idx, "hard_stop"

        # 2) 保本止损: 峰值浮盈达标后激活(持久标记), 价格回到加权均价即全平
        if not pos.breakeven_on and breakeven_active(pos, params):
            pos.breakeven_on = True
        if pos.breakeven_on:
            be_hit = (c <= avg) if pos.is_long else (c >= avg)
            if be_hit:
                pos.close(pos.remaining, avg, "breakeven", i)
                return pos.exits, i - pos.entry_idx, "breakeven"

        # 3) 回调加仓: 峰值回撤达标且仍浮盈(加仓前判定, 加仓后立即止损检查)
        if maybe_add_leg(pos, c, params):
            pos.add_leg(c, params.add_ratio, i)

        # 4) 分批止盈: +5% 平 1/3, +8% 再平 1/3(相对加权均价, 按当前仓位比例)
        pnl_pct = pos.pnl_pct_at(c)
        if not pos.tp1_done and pnl_pct >= params.tp1_pct:
            pos.tp1_done = True
            pos.close(pos.remaining * params.tp_ratio, c, "tp1", i)
        elif pos.tp1_done and not pos.tp2_done and pnl_pct >= params.tp2_pct:
            pos.tp2_done = True
            pos.close(pos.remaining * params.tp_ratio, c, "tp2", i)

        # 5) 尾仓跟踪: 第二批止盈后, 从峰值回撤 2×ATR 平掉剩余
        if pos.tp2_done and pos.remaining > 1e-9 and atr > 0:
            if pos.is_long:
                trail_stop = pos.peak - atr * params.trail_atr
                trail_hit = c <= trail_stop
            else:
                trail_stop = pos.peak + atr * params.trail_atr
                trail_hit = c >= trail_stop
            if trail_hit:
                pos.close(pos.remaining, c, "trail", i)
                return pos.exits, i - pos.entry_idx, "trail"

        # 6) 软止损: 连续 N 根收盘确认(相对加权均价)
        if atr > 0:
            soft_dist = max(avg * params.min_stop_pct / 100, atr * params.sl_atr)
            soft_dist = min(soft_dist, hard_dist * 0.85)
            soft_stop = avg - soft_dist if pos.is_long else avg + soft_dist
            breached = (c <= soft_stop) if pos.is_long else (c >= soft_stop)
            pos.stop_breach = pos.stop_breach + 1 if breached else 0
            if pos.stop_breach >= params.stop_conf_candles:
                pos.close(pos.remaining, c, "soft_stop", i)
                return pos.exits, i - pos.entry_idx, "soft_stop"

        # 7) 超时退出
        if params.max_hold_bars and (i - pos.entry_idx) >= params.max_hold_bars:
            pos.close(pos.remaining, c, "timeout", i)
            return pos.exits, i - pos.entry_idx, "timeout"

    if pos.remaining > 1e-9:
        pos.close(pos.remaining, float(closes[-1]), "eod", n - 1)
        return pos.exits, n - 1 - pos.entry_idx, "eod"
    reason = pos.exits[-1][2] if pos.exits else ""
    return pos.exits, (pos.exits[-1][3] - pos.entry_idx if pos.exits else 0), reason


def simulate_trade(pos: PositionSim, closes, highs, lows, atr_arr,
                   params: ExitParams, interval: str) -> tuple:
    """走完一笔交易的生命周期, 返回 (exits, hold_bars, final_reason)"""
    n = len(closes)
    entry = pos.entry_price
    ema20 = calc_ema(closes, 20) if params.ema20_exit or params.breakout_fail_exit else None
    # 突破未果跟踪: 持仓期间峰值/谷值作为孤立点参照, 突破失败次数存pos动态属性
    ema_breach = 0          # 连续收盘低于/高于EMA20的根数
    for i in range(pos.entry_idx + 1, n):
        if pos.remaining <= 1e-9:
            break
        c = float(closes[i])
        hi = float(highs[i])
        lo = float(lows[i])
        atr = float(atr_arr[i]) if i < len(atr_arr) and atr_arr[i] > 0 else 0.0
        pos.update_peak(hi, lo)
        pnl_pct = pos.pnl_pct_at(c)

        # 1) 硬止损: 百分比固定, 优先级最高
        #    与实盘一致: effective = min(hard_stop_pct, max_margin_loss_pct/leverage)。
        #    实盘每秒监控+交易所侧STOP_MARKET, K线内插针触达即平。
        #    只看收盘价会漏掉插针穿透, 导致回测单笔亏损被高估(假巨亏)。
        hard_dist = entry * params.hard_stop_pct / 100
        if params.max_margin_loss_pct > 0 and params.leverage > 1:
            eff_pct = min(params.hard_stop_pct,
                          params.max_margin_loss_pct / params.leverage)
            hard_dist = entry * eff_pct / 100
        hard_stop = entry - hard_dist if pos.is_long else entry + hard_dist
        hard_hit = (lo <= hard_stop) if pos.is_long else (hi >= hard_stop)
        if hard_hit:
            pos.close(pos.remaining, hard_stop, "hard_stop", i)
            return pos.exits, i - pos.entry_idx, "hard_stop"

        # 1.5) 峰值回撤止损: 浮盈曾≥1ATR后, 价格从持仓峰值回撤≥N×ATR即清仓。
        #      目标: 保住浮盈, 避免"从+3%回吐到硬止损-6%"。
        #      与hard_stop一致: 用触发价(峰值∓N×ATR)结算, 对应实盘每秒监控
        #      回撤达阈值的瞬间平仓, 而不是假设砸到K线最低点才平。
        if params.peak_drawdown_atr > 0 and atr > 0:
            if pos.is_long:
                peak_pnl_pct = (pos.peak - entry) / entry * 100 if entry > 0 else 0.0
                dd_price = pos.peak - atr * params.peak_drawdown_atr
                dd_hit = lo <= dd_price
            else:
                peak_pnl_pct = (entry - pos.peak) / entry * 100 if entry > 0 else 0.0
                dd_price = pos.peak + atr * params.peak_drawdown_atr
                dd_hit = hi >= dd_price
            # 激活条件: 浮盈曾≥1ATR(有利润可保护)才启用峰值回撤
            if peak_pnl_pct >= atr / entry * 100 and dd_hit:
                pos.close(pos.remaining, dd_price, "peak_drawdown", i)
                return pos.exits, i - pos.entry_idx, "peak_drawdown"

        if atr > 0:
            atr_pct = atr / entry * 100
            # 2) 分批止盈
            if not pos.tp1_done and pnl_pct >= atr_pct * params.tp1_atr:
                pos.tp1_done = True
                pos.close(params.partial_pct, c, "tp1", i)
            elif pos.tp1_done and not pos.tp2_done and pnl_pct >= atr_pct * params.tp2_atr:
                pos.tp2_done = True
                pos.close(params.partial_pct, c, "tp2", i)

            # 3) 跟踪止损(止盈达标后启动, 且不低于保本线)
            trail_on = pos.tp2_done if params.trail_after_tp >= 2 else pos.tp1_done
            if trail_on and pos.remaining > 1e-9:
                lock = atr * params.lock_profit_atr
                if pos.is_long:
                    trail_stop = max(entry + lock, pos.peak - atr * params.trail_atr)
                    trail_hit = c <= trail_stop
                else:
                    trail_stop = min(entry - lock, pos.peak + atr * params.trail_atr)
                    trail_hit = c >= trail_stop
                if trail_hit:
                    pos.close(pos.remaining, c, "trail", i)
                    return pos.exits, i - pos.entry_idx, "trail"

            # 4) 软止损: 需连续 N 根收盘确认(对应实盘结构止损)
            #    与实盘 trader.py._scaled_exit_action 保持一致:
            #    下限 min_stop_pct, 上限 hard_stop*0.85(否则硬止损会先触发)
            soft_dist = max(entry * params.min_stop_pct / 100, atr * params.sl_atr)
            soft_dist = min(soft_dist, hard_dist * 0.85)
            soft_stop = entry - soft_dist if pos.is_long else entry + soft_dist
            breached = (c <= soft_stop) if pos.is_long else (c >= soft_stop)
            pos.stop_breach = pos.stop_breach + 1 if breached else 0
            if pos.stop_breach >= params.stop_conf_candles:
                pos.close(pos.remaining, c, "soft_stop", i)
                return pos.exits, i - pos.entry_idx, "soft_stop"

        # 5) 超时退出
        if params.max_hold_bars and (i - pos.entry_idx) >= params.max_hold_bars:
            pos.close(pos.remaining, c, "timeout", i)
            return pos.exits, i - pos.entry_idx, "timeout"

        # 6) EMA20 位置信号(用户需求2): 多头收盘连续N根跌破EMA20 => 动能转弱
        #    两段式:
        #    a) 浮盈不足(<1ATR)时, 跌破EMA20 = 开仓逻辑失败, 加速止损(砍亏损单)
        #    b) 浮盈充足(>=1ATR)时, 不干预(趋势单盘中穿均线正常, 交给跟踪止损)
        if params.ema20_exit and atr > 0 and ema20 is not None and ema20[i] > 0 \
                and pnl_pct < atr_pct * 1.0:
            if pos.is_long:
                below = c < ema20[i]
            else:
                below = c > ema20[i]
            ema_breach = ema_breach + 1 if below else 0
            if ema_breach >= params.ema20_confirm:
                pos.close(pos.remaining, c, "ema20_breach", i)
                return pos.exits, i - pos.entry_idx, "ema20_breach"
            elif ema_breach == 1 and pos.remaining > 0.5:
                pos.close(0.5, c, "ema20_reduce", i)

        # 7) 孤立高低点突破未果(用户需求1): 多头曾突破持仓期孤立高点,
        #    收盘回落(失败), 再次冲高又未站稳 => 突破动能耗尽
        #    仅在浮盈≥1ATR后生效(锁利保护, 不干预入场初期)
        if params.breakout_fail_exit and i - pos.entry_idx >= 2:
            if pos.is_long:
                if not hasattr(pos, "bf_peak"):
                    pos.bf_peak = float(highs[pos.entry_idx])
                prev_peak = pos.bf_peak
                if hi > prev_peak:
                    pos.bf_peak = hi
                if pnl_pct >= atr_pct * 1.0 and pnl_pct >= 0.3:
                    broke = hi >= prev_peak
                    failed = c < prev_peak
                    if broke and failed and not getattr(pos, "bf_failed_now", False):
                        # 本根盘中触及前高但收盘回落 => 一次突破失败
                        pos.bf_fails = getattr(pos, "bf_fails", 0) + 1
                        pos.bf_failed_now = True
                        if pos.bf_fails >= params.breakout_fail_count:
                            pos.close(pos.remaining, c, "breakout_fail", i)
                            return pos.exits, i - pos.entry_idx, "breakout_fail"
                        elif pos.bf_fails == 1 and pos.remaining > 0.5:
                            # 首次失败: 减仓50%观察, 不立即清仓
                            pos.close(0.5, c, "breakout_fail_reduce", i)
                    elif not broke:
                        pos.bf_failed_now = False
            else:
                if not hasattr(pos, "bf_trough"):
                    pos.bf_trough = float(lows[pos.entry_idx])
                prev_trough = pos.bf_trough
                if lo < prev_trough:
                    pos.bf_trough = lo
                if pnl_pct >= atr_pct * 1.0 and pnl_pct >= 0.3:
                    broke = lo <= prev_trough
                    failed = c > prev_trough
                    if broke and failed and not getattr(pos, "bf_failed_now", False):
                        pos.bf_fails = getattr(pos, "bf_fails", 0) + 1
                        pos.bf_failed_now = True
                        if pos.bf_fails >= params.breakout_fail_count:
                            pos.close(pos.remaining, c, "breakout_fail", i)
                            return pos.exits, i - pos.entry_idx, "breakout_fail"
                        elif pos.bf_fails == 1 and pos.remaining > 0.5:
                            pos.close(0.5, c, "breakout_fail_reduce", i)
                    elif not broke:
                        pos.bf_failed_now = False

    # 数据末尾仍持仓: 按最后收盘价结算(标记为 eod, 统计时可排除)
    if pos.remaining > 1e-9:
        pos.close(pos.remaining, float(closes[-1]), "eod", n - 1)
        return pos.exits, n - 1 - pos.entry_idx, "eod"
    reason = pos.exits[-1][2] if pos.exits else ""
    return pos.exits, (pos.exits[-1][3] - pos.entry_idx if pos.exits else 0), reason


def settle_trade(trade: Trade, costs: CostParams, interval: str) -> Trade:
    """结算一笔交易的毛利、成本、净利"""
    is_long = trade.side == "LONG"
    gross = 0.0
    for ratio, price, _, _ in trade.exits:
        if is_long:
            gross += (price - trade.entry_price) / trade.entry_price * 100 * ratio
        else:
            gross += (trade.entry_price - price) / trade.entry_price * 100 * ratio
    trade.gross_pct = gross

    # 成本: 开仓一次全额, 平仓按各批比例; 滑点两侧都吃
    closed = trade.closed_ratio
    fee = costs.entry_fee_pct * 1.0 + costs.exit_fee_pct * closed
    slip = costs.slip_pct * 1.0 + costs.slip_pct * closed
    funding = 0.0
    if costs.apply_funding:
        bars_8h = BARS_PER_8H.get(interval, 96)
        periods = trade.hold_bars / bars_8h if bars_8h else 0
        funding = costs.funding_pct_per_8h * periods
    trade.cost_pct = fee + slip + funding
    trade.net_pct = trade.gross_pct - trade.cost_pct
    return trade


async def fetch_klines(client, symbol: str, interval: str, days: int) -> list:
    """分页拉取历史K线以突破单次 1500 根上限"""
    bars_per_day = {"1m": 1440, "3m": 480, "5m": 288, "15m": 96,
                    "30m": 48, "1h": 24}.get(interval, 288)
    need = bars_per_day * days
    interval_ms = {"1m": 60, "3m": 180, "5m": 300, "15m": 900,
                   "30m": 1800, "1h": 3600}.get(interval, 300) * 1000
    end = int(datetime.now().timestamp() * 1000)
    out: list = []
    while len(out) < need:
        batch = min(1500, need - len(out))
        start = end - batch * interval_ms
        try:
            rows = await client.get_klines(symbol, interval, batch,
                                           start_time=start, end_time=end)
        except Exception:
            break
        if not rows:
            break
        out = list(rows) + out
        end = int(rows[0][0]) - 1
        if len(rows) < batch:
            break
        await asyncio.sleep(0.12)
    # 去重并按时间排序
    seen: dict = {}
    for row in out:
        seen[int(row[0])] = row
    return [seen[k] for k in sorted(seen)]


HTF_MAP = {"1m": "5m", "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d"}


def htf_closes_upto(htf_klines: list, ts_ms: int) -> np.ndarray:
    """取截至 ts_ms 时刻已收盘的高时间框架收盘价序列

    对齐实盘: 只使用当下已经收盘的高TF K线, 避免用到未来数据。
    """
    if not htf_klines:
        return np.array([])
    out = []
    for row in htf_klines:
        close_time = int(row[6])
        if close_time > ts_ms:
            break
        out.append(float(row[4]))
    return np.array(out)


async def backtest_symbol(client, symbol: str, interval: str,
                          strategy_cfg: dict, exit_params: ExitParams,
                          costs: CostParams, days: int = 5,
                          klines: list = None,
                          avoid_hours: set = None,
                          disabled_factors: set = None,
                          htf_klines: list = None,
                          min_atr_pct: float = 0.0,
                          manual_params: ManualParams = None) -> dict:
    """单币种走步回测"""
    klines = klines if klines is not None else await fetch_klines(
        client, symbol, interval, days)
    if len(klines) < 400:
        return None
    closes = np.array([float(k[4]) for k in klines])
    highs = np.array([float(k[2]) for k in klines])
    lows = np.array([float(k[3]) for k in klines])
    volumes = np.array([float(k[5]) for k in klines])
    atr_arr = calc_atr(highs, lows, closes, 14)

    engine = StrategyEngine(strategy_cfg)
    if disabled_factors:
        engine.disabled_factors = disabled_factors
    threshold = float(strategy_cfg.get("signal_threshold", 15))
    long_th = float(strategy_cfg.get("long_threshold", threshold))
    short_th = float(strategy_cfg.get("short_threshold", threshold))

    lookback = 300
    trades: list[Trade] = []
    i = lookback
    n = len(closes)
    while i < n - 1:
        window = slice(i - lookback + 1, i + 1)
        # 高TF趋势: 只取当下已收盘的高TF K线, 与实盘一致
        htf_series = None
        if htf_klines:
            series = htf_closes_upto(htf_klines, int(klines[i][6]))
            if len(series) >= 55:
                htf_series = series
        result = engine.evaluate(
            closes[window], highs[window], lows[window], volumes[window],
            funding_rate=None, htf_closes=htf_series)
        signal = int(result.get("signal", 0) or 0)
        score = float(result.get("score", 0) or 0)
        ok = (signal == 1 and score >= long_th) or (signal == -1 and score <= -short_th)
        if not ok:
            i += 1
            continue
        hour = datetime.fromtimestamp(int(klines[i][0]) / 1000).hour
        if avoid_hours and hour in avoid_hours:
            i += 1
            continue
        # 波动率门槛(对应实盘 market_selection.min_atr_pct):
        # 成本固定, ATR 过小则单笔空间吃不住成本
        if min_atr_pct > 0:
            atr_pct_now = (float(atr_arr[i]) / float(closes[i]) * 100
                           if closes[i] > 0 else 0.0)
            if atr_pct_now < min_atr_pct:
                i += 1
                continue
        side = "LONG" if signal == 1 else "SHORT"
        pos = PositionSim(side, float(closes[i]), i)
        if manual_params is not None:
            exits, hold_bars, final_reason = simulate_trade_manual(
                pos, closes, highs, lows, atr_arr, manual_params, interval)
        else:
            exits, hold_bars, final_reason = simulate_trade(
                pos, closes, highs, lows, atr_arr, exit_params, interval)
        trade = Trade(symbol=symbol, side=side, entry_idx=i,
                      entry_price=pos.avg_entry, entry_time=int(klines[i][0]),
                      exits=exits, hold_bars=hold_bars, final_reason=final_reason)
        settle_trade(trade, costs, interval)
        trades.append(trade)
        # 仓位平掉后才允许下一笔(与实盘单币种单仓一致)
        i = (exits[-1][3] + 1) if exits else (i + 1)

    return summarize(trades, symbol)


def summarize(trades: list, label: str = "") -> dict:
    """统计一组交易的表现"""
    real = [t for t in trades if t.final_reason != "eod"]
    if not real:
        return {"label": label, "trades": 0, "net_pct": 0.0, "gross_pct": 0.0,
                "cost_pct": 0.0, "win_rate": 0.0, "profit_factor": 0.0,
                "avg_net": 0.0, "reasons": {}, "hour_net": {}, "max_loss": 0.0}
    wins = [t for t in real if t.net_pct > 0]
    losses = [t for t in real if t.net_pct <= 0]
    gross_win = sum(t.net_pct for t in wins)
    gross_loss = abs(sum(t.net_pct for t in losses))
    net = sum(t.net_pct for t in real)
    hour_net: Counter = Counter()
    for t in real:
        hour_net[datetime.fromtimestamp(t.entry_time / 1000).hour] += t.net_pct
    return {
        "label": label,
        "trades": len(real),
        "net_pct": round(net, 2),
        "gross_pct": round(sum(t.gross_pct for t in real), 2),
        "cost_pct": round(sum(t.cost_pct for t in real), 2),
        "avg_net": round(net / len(real), 4),
        "win_rate": round(len(wins) / len(real) * 100, 1),
        "avg_win": round(gross_win / len(wins), 4) if wins else 0.0,
        "avg_loss": round(-gross_loss / len(losses), 4) if losses else 0.0,
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss else float("inf"),
        "max_loss": round(min((t.net_pct for t in real), default=0), 3),
        "max_win": round(max((t.net_pct for t in real), default=0), 3),
        "avg_hold_bars": round(sum(t.hold_bars for t in real) / len(real), 1),
        "reasons": dict(Counter(t.final_reason for t in real)),
        "hour_net": {h: round(v, 2) for h, v in sorted(hour_net.items())},
        "_trades": real,
    }


def merge_summaries(summaries: list, label: str) -> dict:
    """合并多币种结果"""
    all_trades = []
    for s in summaries:
        if s:
            all_trades.extend(s.get("_trades", []))
    return summarize(all_trades, label)


def print_summary(s: dict, indent: str = "  "):
    if not s or not s["trades"]:
        print(f"{indent}{s.get('label', '')}: 无有效交易")
        return
    print(f"{indent}{s['label']}: {s['trades']}笔 "
          f"毛{s['gross_pct']:+.1f}% 成本{s['cost_pct']:.1f}% 净{s['net_pct']:+.1f}% "
          f"| 均净{s['avg_net']:+.4f}%/笔 胜率{s['win_rate']}% "
          f"盈亏比{s['profit_factor']} 最大亏{s['max_loss']}%")


def default_symbols(cfg: dict) -> list:
    """内置回测币种列表, 排除 config 黑名单(实盘禁用的币不该参与回测)"""
    black = set((cfg.get("strategy", {}) or {}).get("blacklist", []) or [])
    return [s for s in DEFAULT_SYMBOLS if s not in black]


DEFAULT_SYMBOLS = ["BANKUSDT", "TAGUSDT", "NIGHTUSDT", "EVAAUSDT", "TACUSDT",
                   "ESPORTSUSDT", "ERAUSDT", "BILLUSDT", "ALLOUSDT", "BLESSUSDT"]


def strategy_cfg_from_config(cfg: dict, **overrides) -> dict:
    """以 config.json 的 strategy 段为基准构造回测配置"""
    s = dict(cfg.get("strategy", {}) or {})
    s.setdefault("ma_fast", 7)
    s.setdefault("ma_slow", 25)
    s.setdefault("rsi_period", 14)
    s.setdefault("macd_fast", 12)
    s.setdefault("macd_slow", 26)
    s.setdefault("macd_signal", 9)
    s.setdefault("bb_period", 20)
    s.setdefault("bb_std", 2)
    s.update(overrides)
    return s


def exit_params_from_config(cfg: dict, **overrides) -> ExitParams:
    pm = (cfg.get("strategy", {}) or {}).get("position_management", {}) or {}
    params = ExitParams(
        sl_atr=float(pm.get("initial_stop_atr", 3.0)),
        tp1_atr=float(pm.get("tp1_atr", 1.5)),
        tp2_atr=float(pm.get("tp2_atr", 2.5)),
        partial_pct=max(0.1, min(1.0, float(pm.get("partial_close_pct", 50)) / 100)),
        trail_atr=float(pm.get("trailing_atr", 1.5)),
        lock_profit_atr=float(pm.get("lock_profit_atr", 0.4)),
        hard_stop_pct=float(pm.get("hard_stop_pct", 4.0)),
        min_stop_pct=float(pm.get("min_stop_pct", 2.2)),
        stop_conf_candles=int(pm.get("stop_confirmation_candles", 2)),
        trail_after_tp=int(pm.get("trail_after_tp", 1)),
        max_margin_loss_pct=float(pm.get("max_margin_loss_pct", 0.0)),
        ema20_exit=bool(pm.get("ema20_exit", False)),
        breakout_fail_exit=bool(pm.get("breakout_fail_exit", False)),
        breakout_fail_count=int(pm.get("breakout_fail_count", 2)),
        peak_drawdown_atr=float(pm.get("peak_drawdown_atr", 0.0)),
        # 波段杠杆: 实盘 holding_mode=swing 时 lev = min(max(cfg_leverage//2, 2), swing_max_leverage)
        leverage=float(max(2, min(int(cfg.get("leverage", 8)) // 2,
                                  int(pm.get("swing_max_leverage", 6))))),
    )
    for key, value in overrides.items():
        setattr(params, key, value)
    return params


async def main():
    ap = argparse.ArgumentParser(description="策略回测")
    ap.add_argument("--days", type=int, default=5, help="回测天数")
    ap.add_argument("--interval", default=None, help="K线周期, 默认取 config")
    ap.add_argument("--symbols", default=None, help="逗号分隔币种, 默认内置列表")
    ap.add_argument("--scan", default=None,
                    choices=["threshold", "exit", "factor", "cost", "peakdd",
                             "manual_ab"],
                    help="参数扫描模式")
    ap.add_argument("--no-funding", action="store_true", help="不计资金费")
    ap.add_argument("--no-min-atr", action="store_true",
                    help="忽略 config 的 min_atr_pct(检验波动率门槛)")
    ap.add_argument("--no-htf", action="store_true",
                    help="忽略 config 的 require_htf_align(检验高TF过滤)")
    ap.add_argument("--out", default=None, help="结果输出JSON路径")
    # 单次验证特定参数(用于样本外检验, 覆盖 config.json)
    ap.add_argument("--sl", type=float, default=None, help="软止损ATR倍数")
    ap.add_argument("--tp1", type=float, default=None, help="第一止盈ATR倍数")
    ap.add_argument("--tp2", type=float, default=None, help="第二止盈ATR倍数")
    ap.add_argument("--trail", type=float, default=None, help="跟踪止损ATR倍数")
    ap.add_argument("--hard-stop", type=float, default=None, help="硬止损百分比")
    ap.add_argument("--peak-dd", type=float, default=None,
                    help="峰值回撤止损ATR倍数(0=关闭, 如1.5)")
    ap.add_argument("--min-stop", type=float, default=None, help="软止损下限百分比")
    ap.add_argument("--partial", type=float, default=None,
                    help="分批止盈比例(0-100, 100=止盈一次性全平)")
    ap.add_argument("--threshold", type=float, default=None, help="信号阈值")
    ap.add_argument("--no-avoid-hours", action="store_true",
                    help="忽略 config 的 avoid_hours(检验时段过滤是否过拟合)")
    ap.add_argument("--ema20", action="store_true",
                    help="开启价格vs EMA20退出信号(用户新需求2)")
    ap.add_argument("--breakout-fail", action="store_true",
                    help="开启孤立高低点两次突破未果退出信号(用户新需求1)")
    ap.add_argument("--with-htf", action="store_true",
                    help="强制拉取高TF数据参与评分(config 未开 require_htf_align 时)")
    args = ap.parse_args()

    cfg = load_config()
    client = BinanceFuturesClient(cfg)
    await client.sync_time()
    interval = args.interval or cfg.get("interval", "5m")
    symbols = ([s.strip().upper() for s in args.symbols.split(",")]
               if args.symbols else default_symbols(cfg))
    costs = CostParams(apply_funding=not args.no_funding)

    print(f"回测配置: {len(symbols)}币种 × {args.days}天 {interval} | "
          f"成本模型 手续费{costs.entry_fee_pct}%×2 滑点{costs.slip_pct}%×2 "
          f"资金费{costs.funding_pct_per_8h}%/8h")
    htf_interval = HTF_MAP.get(interval, "1h")
    need_htf = bool((cfg.get("strategy", {}) or {}).get("require_htf_align", False)) \
        or args.with_htf
    print("拉取历史K线..." + (f" (含高TF {htf_interval})" if need_htf else ""))
    kline_map = {}
    htf_map: dict = {}
    for sym in symbols:
        rows = await fetch_klines(client, sym, interval, args.days)
        if len(rows) >= 400:
            kline_map[sym] = rows
            span_h = (int(rows[-1][0]) - int(rows[0][0])) / 3600000
            print(f"  {sym}: {len(rows)}根 ({span_h/24:.1f}天)")
            if need_htf:
                # 高TF 需要额外历史以满足 55 根丝带计算
                htf_map[sym] = await fetch_klines(
                    client, sym, htf_interval, args.days + 20)
        else:
            print(f"  {sym}: 数据不足({len(rows)}根), 跳过")
    if not kline_map:
        print("无可用数据")
        await client.close()
        return

    scfg_over = {}
    if args.threshold is not None:
        scfg_over.update(signal_threshold=args.threshold,
                         long_threshold=args.threshold,
                         short_threshold=args.threshold)
    base_scfg = strategy_cfg_from_config(cfg, **scfg_over)

    exit_over = {k: v for k, v in (
        ("sl_atr", args.sl), ("tp1_atr", args.tp1),
        ("tp2_atr", args.tp2), ("trail_atr", args.trail),
        ("hard_stop_pct", args.hard_stop), ("min_stop_pct", args.min_stop),
        ("partial_pct", args.partial / 100 if args.partial is not None else None),
        ("ema20_exit", True if args.ema20 else None),
        ("breakout_fail_exit", True if args.breakout_fail else None),
        ("peak_drawdown_atr", args.peak_dd),
    ) if v is not None}
    base_exit = exit_params_from_config(cfg, **exit_over)
    avoid_hours = (set() if args.no_avoid_hours
                   else set(base_scfg.get("avoid_hours", []) or []))
    if args.no_min_atr:
        min_atr = 0.0
    else:
        ms_cfg = (cfg.get("strategy", {}) or {}).get("market_selection", {}) or {}
        min_atr = float(ms_cfg.get("min_atr_pct", 0.0))
    need_htf = bool((cfg.get("strategy", {}) or {}).get("require_htf_align", False)) \
        and not args.no_htf or args.with_htf
    if exit_over or scfg_over or args.no_avoid_hours:
        overrides = dict(scfg_over)
        overrides.update(exit_over)
        if args.no_avoid_hours:
            overrides["avoid_hours"] = "disabled"
        print(f"参数覆盖: {overrides}")
    results = {}

    async def run(label, scfg, exitp, costp=costs, avoid=None, disabled=None,
                  min_atr_pct=None, manual_params=None):
        outs = []
        matr = min_atr if min_atr_pct is None else min_atr_pct
        for sym, rows in kline_map.items():
            r = await backtest_symbol(
                client, sym, interval, scfg, exitp, costp,
                klines=rows, avoid_hours=avoid, disabled_factors=disabled,
                htf_klines=htf_map.get(sym), min_atr_pct=matr,
                manual_params=manual_params)
            if r:
                r["label"] = sym
                outs.append(r)
        merged = merge_summaries(outs, label)
        results[label] = {k: v for k, v in merged.items() if k != "_trades"}
        return merged, outs

    if args.scan is None:
        print("\n=== 当前 config.json 参数回测 ===")
        merged, per_sym = await run("current_config", base_scfg, base_exit,
                                    avoid=avoid_hours, min_atr_pct=min_atr)
        for r in per_sym:
            print_summary(r, "    ")
        print()
        print_summary(merged, "  合计 ")
        print(f"  退出分布: {merged['reasons']}")
        print(f"  时段净值: {merged['hour_net']}")

    elif args.scan == "threshold":
        print("\n=== 信号阈值扫描 ===")
        for th in [15, 20, 25, 30, 35, 45, 55]:
            scfg = strategy_cfg_from_config(
                cfg, signal_threshold=th, long_threshold=th, short_threshold=th)
            merged, _ = await run(f"th={th}", scfg, base_exit,
                                  avoid=avoid_hours, min_atr_pct=min_atr)
            print_summary(merged)

    elif args.scan == "exit":
        print("\n=== 止盈止损组合扫描 ===")
        for sl in [2.5, 3.0, 3.5]:
            for tp1 in [1.0, 1.5, 2.0, 2.5]:
                for trail in [1.0, 1.5, 2.5]:
                    p = exit_params_from_config(
                        cfg, sl_atr=sl, tp1_atr=tp1,
                        tp2_atr=tp1 + 1.0, trail_atr=trail)
                    merged, _ = await run(
                        f"SL{sl}/TP1{tp1}/Trail{trail}", base_scfg, p,
                        avoid=avoid_hours, min_atr_pct=min_atr)
                    print_summary(merged)

    elif args.scan == "cost":
        print("\n=== 成本敏感性(验证手续费优化价值) ===")
        variants = [
            ("全市价(taker×2)", CostParams(TAKER_FEE_PCT, TAKER_FEE_PCT,
                                          DEFAULT_SLIP_PCT, apply_funding=not args.no_funding)),
            ("入场限价(maker+taker)", CostParams(MAKER_FEE_PCT, TAKER_FEE_PCT,
                                              DEFAULT_SLIP_PCT / 2, apply_funding=not args.no_funding)),
            ("全限价(maker×2)", CostParams(MAKER_FEE_PCT, MAKER_FEE_PCT,
                                         0.0, apply_funding=not args.no_funding)),
            ("零成本(理论上限)", CostParams(0, 0, 0, apply_funding=False)),
        ]
        for label, cp in variants:
            merged, _ = await run(label, base_scfg, base_exit, cp,
                                  avoid=avoid_hours, min_atr_pct=min_atr)
            print_summary(merged)

    elif args.scan == "factor":
        print("\n=== 因子贡献度分析(逐个禁用对比) ===")
        merged, _ = await run("全因子", base_scfg, base_exit,
                              avoid=avoid_hours, min_atr_pct=min_atr)
        print_summary(merged, "  基准 ")
        baseline_net = merged["net_pct"]
        baseline_avg = merged["avg_net"]
        print("\n  禁用单个因子后的变化(净值下降=该因子有效):")
        rows = []
        for factor in StrategyEngine.FACTOR_KEYS:
            m, _ = await run(f"no_{factor}", base_scfg, base_exit,
                             avoid=avoid_hours, disabled={factor},
                             min_atr_pct=min_atr)
            delta = m["net_pct"] - baseline_net
            rows.append((factor, m["trades"], m["net_pct"], delta, m["avg_net"]))
        rows.sort(key=lambda x: x[3])
        print(f"    {'因子':22s} {'笔数':>5s} {'净值%':>9s} {'Δ净值':>9s} {'均净%':>9s}")
        for name, trades, net, delta, avg in rows:
            flag = "有效" if delta < -1 else ("无效/有害" if delta > 1 else "中性")
            print(f"    {name:22s} {trades:5d} {net:+9.1f} {delta:+9.1f} "
                  f"{avg:+9.4f}  {flag}")

    elif args.scan == "peakdd":
        print("\n=== 峰值回撤止损 A/B 对比(开/关) ===")
        base, _ = await run("关闭(当前)", base_scfg, base_exit,
                            avoid=avoid_hours, min_atr_pct=min_atr)
        print_summary(base, "  基准 ")
        baseline = base["net_pct"]
        print(f"  退出分布: {base['reasons']}")
        for dd in [1.0, 1.25, 1.5, 2.0, 2.5]:
            p = exit_params_from_config(cfg, peak_drawdown_atr=dd)
            m, _ = await run(f"峰值回撤{dd}ATR", base_scfg, p,
                             avoid=avoid_hours, min_atr_pct=min_atr)
            delta = m["net_pct"] - baseline
            print_summary(m)
            print(f"    Δ净值{delta:+.1f}% | 退出分布: {m['reasons']}")
        print("\n  收益-风险权衡(净值降低但回撤/单笔亏损减少):")
        print(f"  基准:  均亏{base['avg_loss']}% 最大单笔亏{base['max_loss']}%")
        for dd in [1.0, 1.25, 1.5, 2.0, 2.5]:
            p = exit_params_from_config(cfg, peak_drawdown_atr=dd)
            m, _ = await run(f"峰值回撤{dd}ATR", base_scfg, p,
                             avoid=avoid_hours, min_atr_pct=min_atr)
            print(f"  {dd}ATR: 净{m['net_pct']:+.1f}% 均亏{m['avg_loss']}% "
                  f"最大亏{m['max_loss']}% win{m['win_rate']}%")

    elif args.scan == "manual_ab":
        print("\n=== 手动打法 A/B 对比(旧逻辑 vs 回调加仓+保本+分批留尾) ===")
        old, _ = await run("旧逻辑(当前config)", base_scfg, base_exit,
                           avoid=avoid_hours, min_atr_pct=min_atr)
        print_summary(old, "  基准 ")
        print(f"  退出分布: {old['reasons']}")
        manual_p = ManualParams()
        new, per_sym_new = await run("手动打法", base_scfg, base_exit,
                                     avoid=avoid_hours, min_atr_pct=min_atr,
                                     manual_params=manual_p)
        print_summary(new, "  新打法")
        print(f"  退出分布: {new['reasons']}")
        delta = new["net_pct"] - old["net_pct"]
        # max_loss 是负数: 用绝对值比较, 新打法最大单笔亏损不超过旧值 1.3 倍
        max_loss_ok = abs(new["max_loss"]) <= abs(old["max_loss"]) * 1.3
        verdict = ("通过: 净收益提升且最大单笔亏损恶化<=30%"
                   if delta > 0 and max_loss_ok
                   else "未通过: 需调参后重跑")
        print(f"\n  Δ净值{delta:+.1f}% | 最大单笔亏 旧{old['max_loss']}% → 新{new['max_loss']}%")
        print(f"  判定: {verdict}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n结果已写入 {args.out}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
