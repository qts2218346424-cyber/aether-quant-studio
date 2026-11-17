"""执行层核心风控与安全熔断模块 (Execution Hard Risk Gate & Circuit Breaker)"""
import time
import math
import logging
from typing import Any

logger = logging.getLogger("risk_manager")


class RiskManager:
    """工业级执行层硬风控管理器。
    
    作为所有开仓订单（自动策略、AI自主猎手、榜单一键下单、图表限价开单）
    在发往交易所前的最后一道绝对防线，保证无任何逻辑可以绕过硬性风控。
    """

    def __init__(self, cfg: dict | None = None):
        cfg = cfg or {}
        # 基础参数
        self.position_size_pct = float(cfg.get("position_size_pct", 10.0))
        self.stop_loss_pct = float(cfg.get("stop_loss_pct", 2.0))
        self.take_profit_pct = float(cfg.get("take_profit_pct", 4.0))
        self.max_daily_loss_pct = float(cfg.get("max_daily_loss_pct", 10.0))
        self.max_positions = int(cfg.get("max_positions", 4))

        # 增强硬风控参数
        self.max_single_risk_pct = float(cfg.get("max_single_risk_pct", 3.0))  # 单笔最大允许风险占本金比
        self.max_position_notional_multiple = float(cfg.get("max_position_notional_multiple", 6.0))
        self.max_total_notional_multiple = float(cfg.get("max_total_notional_multiple", 8.0))
        self.max_leverage_limit = int(cfg.get("max_leverage_limit", 20))  # 系统绝对杠杆硬顶
        self.max_data_staleness_seconds = float(cfg.get("max_data_staleness_seconds", 25.0))  # 行情最大允许延迟

        # 每日亏损追踪
        self._daily_realized_pnl = 0.0
        self._daily_reference_balance = 0.0
        self._day_start = time.time()

        # 紧急制动 (Kill Switch)
        self.emergency_stopped = False
        self.emergency_reason = ""
        self.emergency_timestamp = 0.0

        # 通讯与数据熔断器 (Circuit Breaker)
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = ""
        self.circuit_breaker_timestamp = 0.0

        # 对账状态
        self.last_reconciliation_time = 0.0
        self.reconciliation_status = "OK"
        self.reconciliation_discrepancies: list[dict] = []

    def reset_daily(self):
        now = time.time()
        if now - self._day_start > 86400:
            self._daily_realized_pnl = 0.0
            self._daily_reference_balance = 0.0
            self._day_start = now

    def trigger_emergency_stop(self, reason: str = "人工一键紧急停止"):
        """触发全局紧急急停，彻底锁死所有开仓入口"""
        self.emergency_stopped = True
        self.emergency_reason = reason
        self.emergency_timestamp = time.time()
        logger.warning(f"🚨 [风控] 全局紧急停止已触发: {reason}")

    def reset_emergency_stop(self):
        """解除全局紧急急停"""
        self.emergency_stopped = False
        self.emergency_reason = ""
        self.emergency_timestamp = 0.0
        logger.info("[风控] 全局紧急停止已解除")

    def trip_circuit_breaker(self, reason: str):
        """触发通讯/数据异常熔断"""
        if not self.circuit_breaker_active:
            self.circuit_breaker_active = True
            self.circuit_breaker_reason = reason
            self.circuit_breaker_timestamp = time.time()
            logger.warning(f"⚡ [熔断] 数据/通讯异常触发系统自动熔断: {reason}")

    def reset_circuit_breaker(self):
        """恢复通讯/数据熔断"""
        if self.circuit_breaker_active:
            self.circuit_breaker_active = False
            self.circuit_breaker_reason = ""
            self.circuit_breaker_timestamp = 0.0
            logger.info("🟢 [熔断恢复] 数据/通讯已恢复，熔断解除")

    def check_data_freshness(self, last_update_ts: float | None) -> tuple[bool, str]:
        """检查行情数据新鲜度"""
        if last_update_ts is None or last_update_ts <= 0:
            return False, "无有效行情时间戳"
        age = time.time() - last_update_ts
        if age > self.max_data_staleness_seconds:
            msg = f"行情数据延迟已达 {age:.1f} 秒 (超过上限 {self.max_data_staleness_seconds} 秒)"
            self.trip_circuit_breaker(msg)
            return False, msg
        return True, "OK"

    def can_open(self, current_positions: int, balance: float | None = None) -> tuple[bool, str]:
        """基础开仓许可检查 (保留原有接口)"""
        self.reset_daily()
        if self.emergency_stopped:
            return False, f"系统处于紧急急停状态: {self.emergency_reason}"
        if self.circuit_breaker_active:
            return False, f"系统处于通讯/数据熔断状态: {self.circuit_breaker_reason}"
        if current_positions >= self.max_positions:
            return False, f"已达最大持仓数({self.max_positions})"
        if balance is not None and float(balance) > 0:
            if self._daily_reference_balance <= 0:
                self._daily_reference_balance = float(balance)
            max_loss_u = self._daily_reference_balance * self.max_daily_loss_pct / 100
            if self._daily_realized_pnl <= -max_loss_u:
                return False, (
                    f"今日已实现亏损 {self._daily_realized_pnl:.4f}U "
                    f"达到 {self.max_daily_loss_pct:g}% 上限"
                )
        return True, "OK"

    def check_execution_risk_gate(
        self,
        symbol: str,
        side: str,
        price: float,
        quantity: float,
        requested_leverage: int,
        balance: float,
        open_positions: list[dict],
        sl_price: float | None = None,
        data_last_updated_ts: float | None = None,
        is_force: bool = False,
    ) -> tuple[bool, int, str, dict[str, Any]]:
        """执行层统一硬风控门禁 (Universal Execution Risk Gate)。
        
        任何订单（无论是自动扫描、AI主动猎手、图上开单、榜单下单）必须在此进行不可绕过的终极校验。
        
        返回: (是否通过, 最终合规杠杆, 拦截/说明原因, 详细指标诊断字典)
        """
        self.reset_daily()
        details: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "price": price,
            "quantity": quantity,
            "balance": balance,
            "timestamp": time.time(),
        }

        # 1. 紧急急停检查 (一票否决)
        if self.emergency_stopped:
            return False, requested_leverage, f"🚨 全局紧急急停生效中: {self.emergency_reason}", details

        # 2. 自动熔断器检查 (一票否决)
        if self.circuit_breaker_active:
            return False, requested_leverage, f"⚡ 数据/通讯熔断生效中: {self.circuit_breaker_reason}", details

        # 3. 数据新鲜度硬性拦截
        if data_last_updated_ts and data_last_updated_ts > 0:
            fresh, fresh_msg = self.check_data_freshness(data_last_updated_ts)
            if not fresh:
                return False, requested_leverage, f"数据陈旧熔断: {fresh_msg}", details

        # 4. 账户余额正数检查
        if balance <= 0:
            return False, requested_leverage, f"账户有效余额不足 ({balance:.2f}U)", details

        # 5. 今日最大日内亏损硬防线 (即使 force 手动下单也禁止违背日内最大亏损)
        if self._daily_reference_balance <= 0:
            self._daily_reference_balance = float(balance)
        max_daily_loss_u = self._daily_reference_balance * (self.max_daily_loss_pct / 100.0)
        if self._daily_realized_pnl <= -max_daily_loss_u:
            return False, requested_leverage, (
                f"今日累计亏损已达 {self._daily_realized_pnl:.2f}U, 触碰单日硬性上限 "
                f"-{max_daily_loss_u:.2f}U ({self.max_daily_loss_pct}%), 今日锁定开仓"
            ), details

        # 6. 最大并发持仓数量
        # 计算当前已有持仓数量 (不含同币同向加仓)
        active_symbols = {p["symbol"] for p in open_positions if abs(float(p.get("positionAmt", 0))) > 0}
        if symbol not in active_symbols and len(active_symbols) >= self.max_positions:
            return False, requested_leverage, f"已达最大允许持仓币种数 ({self.max_positions}个)", details

        # 7. 杠杆硬上限钳位 (Clamp)
        effective_leverage = min(requested_leverage, self.max_leverage_limit)
        details["requested_leverage"] = requested_leverage
        details["effective_leverage"] = effective_leverage

        # 8. 计划名义本金与账户杠杆比例检查
        planned_notional = float(quantity) * float(price)
        details["planned_notional"] = planned_notional
        
        # 单币最大名义价值上限 (不得超过账户净值的 max_position_notional_multiple 倍)
        max_pos_notional = balance * self.max_position_notional_multiple
        if planned_notional > max_pos_notional:
            return False, effective_leverage, (
                f"单币名义金额 {planned_notional:.1f}U 超过允许上限 {max_pos_notional:.1f}U "
                f"({self.max_position_notional_multiple}倍净值)"
            ), details

        # 9. 账户总持仓名义价值上限
        current_total_notional = sum(
            abs(float(p.get("positionAmt", 0))) * float(p.get("markPrice") or p.get("entryPrice") or price)
            for p in open_positions
        )
        details["current_total_notional"] = current_total_notional
        max_total_notional = balance * self.max_total_notional_multiple
        if current_total_notional + planned_notional > max_total_notional:
            return False, effective_leverage, (
                f"持仓总名义将达 {current_total_notional + planned_notional:.1f}U, 超过账户总风控上限 "
                f"{max_total_notional:.1f}U ({self.max_total_notional_multiple}倍净值)"
            ), details

        # 10. 单笔预估止损风险额硬检查 (若设置了止损价)
        if sl_price and sl_price > 0:
            loss_per_coin = abs(price - sl_price)
            estimated_loss = float(quantity) * loss_per_coin
            max_single_loss = balance * (self.max_single_risk_pct / 100.0)
            details["estimated_loss"] = estimated_loss
            details["max_single_loss"] = max_single_loss
            if estimated_loss > max_single_loss * 1.1:  # 允许 10% 缓冲避免浮点误杀
                return False, effective_leverage, (
                    f"单笔止损预计损失 {estimated_loss:.2f}U 超过单笔风险上限 "
                    f"{max_single_loss:.2f}U ({self.max_single_risk_pct}% 净值)"
                ), details

        return True, effective_leverage, "风控检查全部通过", details

    def reconcile_positions(
        self,
        exchange_positions: list[dict],
        internal_tp_state: dict[str, dict]
    ) -> dict[str, Any]:
        """仓位对账核心逻辑 (Position Reconciliation Engine)。
        
        比对交易所真实持仓与内部 tracking 状态，识别漏单、幽灵仓位、僵尸仓位与数据不一致。
        """
        self.last_reconciliation_time = time.time()
        discrepancies = []

        # 整理真实持仓
        real_positions = {}
        for p in exchange_positions:
            amt = float(p.get("positionAmt", 0))
            if abs(amt) > 1e-6:
                real_positions[p["symbol"]] = {
                    "amt": amt,
                    "side": "LONG" if amt > 0 else "SHORT",
                    "entry_price": float(p.get("entryPrice", 0)),
                    "unrealized_pnl": float(p.get("unRealizedProfit", 0)),
                }

        # 1. 检查幽灵仓位 (交易所存在，但系统未记录)
        for sym, r_pos in real_positions.items():
            if sym not in internal_tp_state:
                discrepancies.append({
                    "symbol": sym,
                    "type": "GHOST_POSITION",
                    "severity": "HIGH",
                    "message": f"交易所存在活跃持仓 {r_pos['side']} {abs(r_pos['amt'])}, 但系统内部未纳管 (幽灵仓位)",
                    "exchange": r_pos,
                    "internal": None,
                })
            else:
                i_side = internal_tp_state[sym].get("side")
                if i_side and i_side != r_pos["side"]:
                    discrepancies.append({
                        "symbol": sym,
                        "type": "DIRECTION_MISMATCH",
                        "severity": "CRITICAL",
                        "message": f"持仓方向不符: 交易所为 {r_pos['side']}, 系统记录为 {i_side}",
                        "exchange": r_pos,
                        "internal": internal_tp_state[sym],
                    })

        # 2. 检查僵尸仓位 (系统记录有持仓，但交易所已无仓位)
        for sym, i_pos in internal_tp_state.items():
            if sym not in real_positions:
                discrepancies.append({
                    "symbol": sym,
                    "type": "ZOMBIE_POSITION",
                    "severity": "MEDIUM",
                    "message": f"系统记录中存在仓位 {i_pos.get('side')}, 但交易所实际已平仓 (僵尸仓位)",
                    "exchange": None,
                    "internal": i_pos,
                })

        self.reconciliation_discrepancies = discrepancies
        self.reconciliation_status = "WARNING" if discrepancies else "OK"

        return {
            "status": self.reconciliation_status,
            "timestamp": self.last_reconciliation_time,
            "discrepancies_count": len(discrepancies),
            "discrepancies": discrepancies,
            "real_count": len(real_positions),
            "internal_count": len(internal_tp_state),
        }

    def calc_quantity(self, balance: float, price: float, leverage: int) -> float:
        """按账户百分比计算下单数量, 根据价格自动适配精度(避免币安-1111)"""
        margin = balance * (self.position_size_pct / 100)
        notional = margin * leverage
        if notional < 5:
            notional = 5.0
        qty = notional / price if price > 0 else 0
        if price >= 10000:
            decimals = 3
        elif price >= 1000:
            decimals = 2
        elif price >= 100:
            decimals = 1
        elif price >= 1:
            decimals = 0
        else:
            decimals = 0
        qty = math.floor(qty * (10 ** decimals)) / (10 ** decimals)
        return qty

    def check_sl_tp(self, entry_price: float, current_price: float, side: str) -> tuple[bool, str]:
        """检查止盈止损"""
        if side == "LONG":
            pnl_pct = (current_price - entry_price) / entry_price * 100
        else:
            pnl_pct = (entry_price - current_price) / entry_price * 100

        if pnl_pct <= -self.stop_loss_pct:
            return True, f"触发止损({pnl_pct:.2f}%)"
        if pnl_pct >= self.take_profit_pct:
            return True, f"触发止盈({pnl_pct:.2f}%)"
        return False, ""

    def record_realized_pnl(self, pnl: float):
        """记录已平仓盈亏"""
        self.reset_daily()
        self._daily_realized_pnl += float(pnl or 0)

    def seed_daily_realized_pnl(self, pnl: float):
        """恢复今日历史盈亏"""
        self.reset_daily()
        self._daily_realized_pnl = float(pnl or 0)

    def record_pnl(self, pnl_pct: float):
        self.record_realized_pnl(pnl_pct)

    def get_summary(self) -> dict[str, Any]:
        """获取风控运行全景状态"""
        self.reset_daily()
        max_daily_loss_u = self._daily_reference_balance * (self.max_daily_loss_pct / 100.0) if self._daily_reference_balance > 0 else 0.0
        return {
            "emergency_stopped": self.emergency_stopped,
            "emergency_reason": self.emergency_reason,
            "circuit_breaker_active": self.circuit_breaker_active,
            "circuit_breaker_reason": self.circuit_breaker_reason,
            "daily_realized_pnl": round(self._daily_realized_pnl, 4),
            "daily_reference_balance": round(self._daily_reference_balance, 2),
            "max_daily_loss_u": round(max_daily_loss_u, 2),
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_positions": self.max_positions,
            "max_leverage_limit": self.max_leverage_limit,
            "max_position_notional_multiple": self.max_position_notional_multiple,
            "max_total_notional_multiple": self.max_total_notional_multiple,
            "reconciliation_status": self.reconciliation_status,
            "discrepancies_count": len(self.reconciliation_discrepancies),
        }
