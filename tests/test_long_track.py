"""长线赛道(1长线+3短线)测试

覆盖设计文档 docs/superpowers/specs/2026-08-05-long-short-track-design.md 第11节。
重点验证三个结构性阻断点已被解决:
  1. 跟踪止损必须用swing ATR, 用5m ATR×1.5长线必被震出
  2. 升级失败时不能留下"假长线"(带着tp2全平单)
  3. 1h级别的确认不能退化成5m计数
"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from trader import Trader

SWING_BAR = 1_700_000_000_000
HOUR_MS = 3_600_000


def rising(n=60, start=100.0, step=0.5):
    """递增序列 -> EMA多头排列(detect_ema_ribbon = 1)"""
    return [start + i * step for i in range(n)]


def falling(n=60, start=140.0, step=0.5):
    """递减序列 -> EMA空头排列(detect_ema_ribbon = -1)"""
    return [start - i * step for i in range(n)]


def ohlc(closes, last_open_time=SWING_BAR, spread=1.0):
    return {
        "highs": [c + spread for c in closes],
        "lows": [c - spread for c in closes],
        "closes": list(closes),
        "last_open_time": last_open_time,
    }


def base_pm():
    """贴近 config.json 当前实际值的 position_management"""
    return {
        "partial_close_pct": 50,
        "trailing_atr": 1.5,
        "lock_profit_atr": 0.4,
        "holding_mode": "swing",
        "initial_stop_atr": 3,
        "min_stop_pct": 2.2,
        "hard_stop_pct": 4,
        "max_margin_loss_pct": 45,
        "stop_confirmation_candles": 2,
        "require_swing_reversal": True,
        "trail_after_tp": 1,
        "tp1_atr": 1.5,
        "tp2_atr": 2.5,
        "long_track": {
            "enabled": True,
            "max_long_slots": 1,
            "tp1_close_pct": 30,
            "trail_atr_swing": 3.0,
            "reversal_confirm_bars": 2,
            "hard_stop_pct": 6.0,
        },
    }


def make_trader(symbol="TESTUSDT", swing="up", htf="up", with_ohlc=True,
                pm_override=None, tmpfile=None):
    trader = Trader.__new__(Trader)
    pm = base_pm()
    for key, value in (pm_override or {}).items():
        if key == "long_track" and isinstance(value, dict):
            pm["long_track"].update(value)
        else:
            pm[key] = value
    trader.strategy = SimpleNamespace(cfg={"position_management": pm})
    trader.swing_interval = "1h"
    trader.tp_state = {}
    trader.execution_events = []
    trader.positions_cache = {}

    series = {"up": rising(), "down": falling(), "flat": [100.0] * 60}
    trader.swing_cache = {symbol: series[swing]}
    trader.htf_cache = {symbol: series[htf]}
    trader.swing_ohlc_cache = (
        {symbol: ohlc(series[swing])} if with_ohlc else {})
    if tmpfile is not None:
        trader._long_track_file = lambda: tmpfile
    return trader


def scalp_state(side="LONG", qty=10.0, mode="conservative", **extra):
    st = {
        "side": side, "orig_qty": qty, "tp1": False, "tp2": False, "tp3": False,
        "mode": mode, "entry_time": 0, "peak_price": 0.0, "stop_breach_count": 0,
        "track": "scalp", "pending_upgrade": False, "track_since": 0.0,
        "long_breach_count": 0, "last_swing_bar": 0,
    }
    st.update(extra)
    return st


class Tp1UpgradeDecisionTests(unittest.TestCase):
    """TP1 达成时的赛道判定与减仓比例"""

    def test_long_candidate_closes_30_percent_and_marks_pending(self):
        trader = make_trader()
        trader.tp_state["TESTUSDT"] = scalp_state(peak_price=100.0)
        trader.positions_cache = {"TESTUSDT": {"entry_price": 100.0}}

        # atr=1, tp1_atr=1.5 -> tp1_pct=1.5%; +2% 达成
        action = trader._scaled_exit_action(
            "TESTUSDT", "LONG", 10.0, 100.0, 102.0, atr=1.0,
            swing_trend=1, closed_candle=False, leverage=6)

        self.assertIsNotNone(action)
        close_qty, reason = action
        self.assertAlmostEqual(close_qty, 3.0)  # 30%, 不是短线的 50%
        self.assertIn("转长线", reason)
        st = trader.tp_state["TESTUSDT"]
        self.assertTrue(st["pending_upgrade"])
        # 交易所侧改单成功前不能置 track
        self.assertEqual(st["track"], "scalp")

    def test_scalp_tp1_still_closes_50_percent(self):
        """回归: 不满足升级条件时短线行为不变"""
        trader = make_trader(swing="down")  # swing 反向 -> 不升级
        trader.tp_state["TESTUSDT"] = scalp_state(peak_price=100.0)

        action = trader._scaled_exit_action(
            "TESTUSDT", "LONG", 10.0, 100.0, 102.0, atr=1.0,
            swing_trend=1, closed_candle=False, leverage=6)

        close_qty, reason = action
        self.assertAlmostEqual(close_qty, 5.0)
        self.assertIn("波段止盈1", reason)
        self.assertFalse(trader.tp_state["TESTUSDT"]["pending_upgrade"])

    def test_upgrade_rejected_when_htf_opposite(self):
        trader = make_trader(swing="up", htf="down")
        trader.tp_state["TESTUSDT"] = scalp_state(peak_price=100.0)

        ok, reason = trader._can_upgrade_to_long(
            "TESTUSDT", "LONG", trader.tp_state["TESTUSDT"])

        self.assertFalse(ok)
        self.assertIn("高TF", reason)

    def test_upgrade_rejected_when_swing_atr_missing(self):
        """swing OHLC 不足 -> 拒绝升级(宁可错过, 不能用错的ATR管宽止损仓)"""
        trader = make_trader(with_ohlc=False)
        trader.tp_state["TESTUSDT"] = scalp_state(peak_price=100.0)

        ok, reason = trader._can_upgrade_to_long(
            "TESTUSDT", "LONG", trader.tp_state["TESTUSDT"])

        self.assertFalse(ok)
        self.assertIn("ATR", reason)

    def test_upgrade_rejected_for_profit_bet(self):
        trader = make_trader()
        trader.tp_state["TESTUSDT"] = scalp_state(mode="profit_bet")

        ok, reason = trader._can_upgrade_to_long(
            "TESTUSDT", "LONG", trader.tp_state["TESTUSDT"])

        self.assertFalse(ok)
        self.assertIn("利润博弈", reason)

    def test_upgrade_rejected_when_long_slot_full(self):
        trader = make_trader()
        trader.tp_state["OTHERUSDT"] = scalp_state(track="swing_long")
        trader.positions_cache = {"OTHERUSDT": {"entry_price": 50.0}}
        trader.tp_state["TESTUSDT"] = scalp_state()

        ok, reason = trader._can_upgrade_to_long(
            "TESTUSDT", "LONG", trader.tp_state["TESTUSDT"])

        self.assertFalse(ok)
        self.assertIn("长线槽已满", reason)

    def test_stale_tp_state_does_not_occupy_long_slot(self):
        """tp_state 有残留但交易所无持仓时不应占槽"""
        trader = make_trader()
        trader.tp_state["GHOSTUSDT"] = scalp_state(track="swing_long")
        trader.positions_cache = {}  # 已平仓
        trader.tp_state["TESTUSDT"] = scalp_state()

        self.assertEqual(trader._long_slots_used(), 0)
        ok, _ = trader._can_upgrade_to_long(
            "TESTUSDT", "LONG", trader.tp_state["TESTUSDT"])
        self.assertTrue(ok)

    def test_short_side_upgrade_requires_both_trends_down(self):
        trader = make_trader(swing="down", htf="down")
        trader.tp_state["TESTUSDT"] = scalp_state(side="SHORT")

        ok, _ = trader._can_upgrade_to_long(
            "TESTUSDT", "SHORT", trader.tp_state["TESTUSDT"])

        self.assertTrue(ok)


class LongTrackExitTests(unittest.TestCase):
    """长线持有期的退出参数"""

    def test_tp2_does_not_reduce_on_long_track(self):
        trader = make_trader()
        trader.tp_state["TESTUSDT"] = scalp_state(
            track="swing_long", tp1=True, peak_price=103.0)

        # tp2_atr=2.5 -> 2.5%; +3% 已达成
        action = trader._scaled_exit_action(
            "TESTUSDT", "LONG", 7.0, 100.0, 103.0, atr=1.0,
            swing_trend=1, closed_candle=False, leverage=6)

        self.assertIsNone(action)  # 不减仓
        self.assertTrue(trader.tp_state["TESTUSDT"]["tp2"])

    def test_trailing_uses_swing_atr_not_operating_atr(self):
        """核心: 5m ATR×1.5 会平掉, swing ATR×3 应该拿住"""
        trader = make_trader()
        trader.tp_state["TESTUSDT"] = scalp_state(
            track="swing_long", tp1=True, tp2=True, peak_price=110.0)

        # 5m atr=0.5 -> 短线跟踪线 110-0.75=109.25, 当前108会被平
        # swing atr≈2 -> 长线跟踪线 110-6=104, 当前108应保留
        action = trader._scaled_exit_action(
            "TESTUSDT", "LONG", 7.0, 100.0, 108.0, atr=0.5,
            swing_trend=1, closed_candle=False, leverage=6)

        self.assertIsNone(action)

    def test_scalp_trailing_still_fires_on_operating_atr(self):
        """同样价位下短线仓应该被跟踪止损平掉(证明上一个用例的对比有效)"""
        trader = make_trader()
        trader.tp_state["TESTUSDT"] = scalp_state(
            tp1=True, tp2=True, peak_price=110.0)

        action = trader._scaled_exit_action(
            "TESTUSDT", "LONG", 7.0, 100.0, 108.0, atr=0.5,
            swing_trend=1, closed_candle=False, leverage=6)

        self.assertIsNotNone(action)
        self.assertIn("跟踪止损", action[1])

    def test_fresh_long_track_tolerates_deep_pullback(self):
        """刚升级的长线仓 peak≈entry, 必须容忍3~6%回落。

        回归保护: 若给长线加上短线那条保本底线(entry+ATR×0.4=100.8),
        止损会被顶到+0.8%, 回落不足1%就被平, 长线名不副实。
        """
        trader = make_trader()
        trader.tp_state["TESTUSDT"] = scalp_state(
            track="swing_long", tp1=True, peak_price=101.5)

        # swing atr=2, 跟踪线 = 101.5 - 2×3 = 95.5; 硬止损 = 94
        action = trader._scaled_exit_action(
            "TESTUSDT", "LONG", 7.0, 100.0, 97.0, atr=1.0,
            swing_trend=1, closed_candle=False, leverage=6)

        self.assertIsNone(action)

    def test_scalp_breakeven_floor_is_kept(self):
        """短线仍保留保本底线(tp1/tp2已落袋, 不该回到成本以下)"""
        trader = make_trader()
        trader.tp_state["TESTUSDT"] = scalp_state(
            tp1=True, tp2=True, peak_price=101.5)

        action = trader._scaled_exit_action(
            "TESTUSDT", "LONG", 7.0, 100.0, 100.2, atr=1.0,
            swing_trend=1, closed_candle=False, leverage=6)

        self.assertIsNotNone(action)  # 保本底线 100+1×0.4=100.4 > 100.2
        self.assertIn("跟踪止损", action[1])

    def test_long_track_hard_stop_is_wider(self):
        trader = make_trader()
        trader.tp_state["TESTUSDT"] = scalp_state(
            track="swing_long", tp1=True, peak_price=100.0)

        # -5%: 长线(6%)不触发
        self.assertIsNone(trader._scaled_exit_action(
            "TESTUSDT", "LONG", 7.0, 100.0, 95.0, atr=1.0,
            swing_trend=1, closed_candle=False, leverage=6))

        # 同价位短线(4%)必须触发
        trader.tp_state["OTHERUSDT"] = scalp_state(tp1=True, peak_price=100.0)
        trader.swing_ohlc_cache["OTHERUSDT"] = trader.swing_ohlc_cache["TESTUSDT"]
        action = trader._scaled_exit_action(
            "OTHERUSDT", "LONG", 7.0, 100.0, 95.0, atr=1.0,
            swing_trend=1, closed_candle=False, leverage=6)
        self.assertIsNotNone(action)
        self.assertIn("硬止损", action[1])

    def test_long_track_hard_stop_still_capped_by_leverage(self):
        """max_margin_loss_pct/leverage 仍然兜底: 高杠杆下6%会被压缩"""
        trader = make_trader(pm_override={"max_margin_loss_pct": 30})
        trader.tp_state["TESTUSDT"] = scalp_state(
            track="swing_long", tp1=True, peak_price=100.0)

        # cap = 30/10 = 3% < 6%, 所以 -3.5% 就该触发
        action = trader._scaled_exit_action(
            "TESTUSDT", "LONG", 7.0, 100.0, 96.5, atr=1.0,
            swing_trend=1, closed_candle=False, leverage=10)

        self.assertIsNotNone(action)
        self.assertIn("硬止损", action[1])


class SwingBarConfirmationTests(unittest.TestCase):
    """1h 级别确认不能退化成 5m 计数"""

    def test_breach_count_only_advances_when_swing_bar_advances(self):
        trader = make_trader(swing="down")
        trader.tp_state["TESTUSDT"] = scalp_state(
            track="swing_long", tp1=True, peak_price=105.0)
        st = trader.tp_state["TESTUSDT"]

        # 第1根swing收盘: count 0->1
        self.assertIsNone(trader._scaled_exit_action(
            "TESTUSDT", "LONG", 7.0, 100.0, 105.0, atr=1.0,
            swing_trend=-1, closed_candle=True, leverage=6))
        self.assertEqual(st["long_breach_count"], 1)

        # 同一根swing内又来了几次5m收盘: count 必须不动
        for _ in range(5):
            trader._scaled_exit_action(
                "TESTUSDT", "LONG", 7.0, 100.0, 105.0, atr=1.0,
                swing_trend=-1, closed_candle=True, leverage=6)
        self.assertEqual(st["long_breach_count"], 1)

    def test_two_swing_bars_against_trend_closes_position(self):
        trader = make_trader(swing="down")
        trader.tp_state["TESTUSDT"] = scalp_state(
            track="swing_long", tp1=True, peak_price=105.0)

        trader._scaled_exit_action(
            "TESTUSDT", "LONG", 7.0, 100.0, 105.0, atr=1.0,
            swing_trend=-1, closed_candle=True, leverage=6)

        # 推进到下一根swing K线
        trader.swing_ohlc_cache["TESTUSDT"]["last_open_time"] = SWING_BAR + HOUR_MS
        action = trader._scaled_exit_action(
            "TESTUSDT", "LONG", 7.0, 100.0, 105.0, atr=1.0,
            swing_trend=-1, closed_candle=True, leverage=6)

        self.assertIsNotNone(action)
        self.assertAlmostEqual(action[0], 7.0)  # 全平
        self.assertIn("长线结构反转", action[1])
        self.assertNotIn("TESTUSDT", trader.tp_state)

    def test_breach_count_resets_when_trend_realigns(self):
        trader = make_trader(swing="down")
        trader.tp_state["TESTUSDT"] = scalp_state(
            track="swing_long", tp1=True, peak_price=105.0)
        st = trader.tp_state["TESTUSDT"]

        trader._scaled_exit_action(
            "TESTUSDT", "LONG", 7.0, 100.0, 105.0, atr=1.0,
            swing_trend=-1, closed_candle=True, leverage=6)
        self.assertEqual(st["long_breach_count"], 1)

        # 趋势回到同向, 新的一根swing收盘 -> 计数清零
        trader.swing_ohlc_cache["TESTUSDT"]["last_open_time"] = SWING_BAR + HOUR_MS
        trader._scaled_exit_action(
            "TESTUSDT", "LONG", 7.0, 100.0, 105.0, atr=1.0,
            swing_trend=1, closed_candle=True, leverage=6)
        self.assertEqual(st["long_breach_count"], 0)


class ApplyUpgradeTests(unittest.IsolatedAsyncioTestCase):
    """交易所侧改单: 先改交易所, 成功才改内存"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpfile = Path(self._tmp.name) / "long_track.json"

    def tearDown(self):
        self._tmp.cleanup()

    async def test_success_sets_track_blocks_pyramid_and_cancels_tp(self):
        trader = make_trader(tmpfile=self.tmpfile)
        trader.tp_state["TESTUSDT"] = scalp_state(
            tp1=True, pending_upgrade=True, peak_price=102.0)
        trader.positions_cache = {"TESTUSDT": {"entry_price": 100.0}}
        trader.client = SimpleNamespace(
            cancel_all_orders=AsyncMock(),
            place_protective_stop=AsyncMock(),
        )

        ok = await trader._apply_pending_upgrade("TESTUSDT", "LONG", 100.0)

        self.assertTrue(ok)
        st = trader.tp_state["TESTUSDT"]
        self.assertEqual(st["track"], "swing_long")
        self.assertTrue(st["pyramided"])  # 长线禁止加仓
        self.assertFalse(st["pending_upgrade"])

        trader.client.cancel_all_orders.assert_awaited_once_with("TESTUSDT")
        # 只挂止损, 不再挂 TAKE_PROFIT_MARKET(它是closePosition会全平长线仓)
        self.assertEqual(trader.client.place_protective_stop.await_count, 1)
        args = trader.client.place_protective_stop.await_args.args
        self.assertEqual(args[2], "STOP_MARKET")
        self.assertAlmostEqual(args[3], 94.0)  # 100 * (1 - 6%)

    async def test_short_side_stop_is_above_entry(self):
        trader = make_trader(swing="down", htf="down", tmpfile=self.tmpfile)
        trader.tp_state["TESTUSDT"] = scalp_state(
            side="SHORT", tp1=True, pending_upgrade=True)
        trader.positions_cache = {"TESTUSDT": {"entry_price": 100.0}}
        trader.client = SimpleNamespace(
            cancel_all_orders=AsyncMock(),
            place_protective_stop=AsyncMock(),
        )

        await trader._apply_pending_upgrade("TESTUSDT", "SHORT", 100.0)

        args = trader.client.place_protective_stop.await_args.args
        self.assertAlmostEqual(args[3], 106.0)

    async def test_order_failure_rolls_back_to_scalp(self):
        trader = make_trader(tmpfile=self.tmpfile)
        trader.tp_state["TESTUSDT"] = scalp_state(
            tp1=True, pending_upgrade=True)
        trader.client = SimpleNamespace(
            cancel_all_orders=AsyncMock(side_effect=RuntimeError("network down")),
            place_protective_stop=AsyncMock(),
        )

        ok = await trader._apply_pending_upgrade("TESTUSDT", "LONG", 100.0)

        self.assertFalse(ok)
        st = trader.tp_state["TESTUSDT"]
        self.assertEqual(st["track"], "scalp")  # 不留假长线
        self.assertFalse(st["pending_upgrade"])
        self.assertFalse(self.tmpfile.exists())
        failed = [e for e in trader.execution_events if e["outcome"] == "failed"]
        self.assertEqual(len(failed), 1)
        self.assertIn("升级失败", failed[0]["reason"])
        self.assertIn("剩余仓位继续走短线", failed[0]["error"])

    async def test_no_pending_flag_is_a_noop(self):
        trader = make_trader(tmpfile=self.tmpfile)
        trader.tp_state["TESTUSDT"] = scalp_state(tp1=True)
        trader.client = SimpleNamespace(
            cancel_all_orders=AsyncMock(),
            place_protective_stop=AsyncMock(),
        )

        self.assertFalse(
            await trader._apply_pending_upgrade("TESTUSDT", "LONG", 100.0))
        trader.client.cancel_all_orders.assert_not_awaited()


class PersistenceTests(unittest.TestCase):
    """重启恢复: tp_state 是内存态, 不落盘长线仓会退化"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpfile = Path(self._tmp.name) / "long_track.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, records):
        self.tmpfile.write_text(json.dumps(records), encoding="utf-8")

    def test_persist_only_writes_long_track_entries(self):
        trader = make_trader(tmpfile=self.tmpfile)
        trader.tp_state = {
            "AUSDT": scalp_state(track="swing_long", peak_price=120.0),
            "BUSDT": scalp_state(),  # 短线不落盘
        }
        trader.positions_cache = {
            "AUSDT": {"entry_price": 100.0},
            "BUSDT": {"entry_price": 50.0},
        }

        trader._persist_long_track()

        saved = json.loads(self.tmpfile.read_text(encoding="utf-8"))
        self.assertEqual([r["symbol"] for r in saved], ["AUSDT"])
        self.assertAlmostEqual(saved[0]["entry_price"], 100.0)
        self.assertAlmostEqual(saved[0]["peak_price"], 120.0)

    def test_restore_recovers_matching_position(self):
        trader = make_trader(tmpfile=self.tmpfile)
        self._write([{
            "symbol": "TESTUSDT", "side": "LONG", "entry_price": 100.0,
            "peak_price": 118.0, "orig_qty": 7.0, "tp1": True, "tp2": False,
            "track_since": 1.0, "mode": "aggressive",
        }])

        trader._restore_long_track([{
            "symbol": "TESTUSDT", "side": "LONG",
            "entry_price": 100.0, "qty": 7.0,
        }])

        st = trader.tp_state["TESTUSDT"]
        self.assertEqual(st["track"], "swing_long")
        self.assertTrue(st["pyramided"])
        self.assertTrue(st["tp1"])
        # peak 必须恢复, 否则跟踪止损位失真
        self.assertAlmostEqual(st["peak_price"], 118.0)

    def test_restore_discards_closed_position(self):
        trader = make_trader(tmpfile=self.tmpfile)
        self._write([{
            "symbol": "GONEUSDT", "side": "LONG", "entry_price": 100.0,
        }])

        trader._restore_long_track([])

        self.assertNotIn("GONEUSDT", trader.tp_state)
        self.assertEqual(json.loads(self.tmpfile.read_text(encoding="utf-8")), [])

    def test_restore_discards_flipped_side(self):
        trader = make_trader(tmpfile=self.tmpfile)
        self._write([{
            "symbol": "TESTUSDT", "side": "LONG", "entry_price": 100.0,
        }])

        trader._restore_long_track([{
            "symbol": "TESTUSDT", "side": "SHORT",
            "entry_price": 100.0, "qty": 7.0,
        }])

        self.assertNotIn("TESTUSDT", trader.tp_state)

    def test_restore_discards_entry_price_mismatch(self):
        """幽灵赛道: 长线仓平掉后同symbol又开了新仓, 不能误恢复成长线"""
        trader = make_trader(tmpfile=self.tmpfile)
        self._write([{
            "symbol": "TESTUSDT", "side": "LONG", "entry_price": 100.0,
        }])

        trader._restore_long_track([{
            "symbol": "TESTUSDT", "side": "LONG",
            "entry_price": 137.0, "qty": 7.0,  # 明显是另一笔仓位
        }])

        self.assertNotIn("TESTUSDT", trader.tp_state)

    def test_restore_tolerates_tiny_entry_drift(self):
        """加仓/手续费导致的微小均价偏移应当容忍"""
        trader = make_trader(tmpfile=self.tmpfile)
        self._write([{
            "symbol": "TESTUSDT", "side": "LONG", "entry_price": 100.0,
            "tp1": True,
        }])

        trader._restore_long_track([{
            "symbol": "TESTUSDT", "side": "LONG",
            "entry_price": 100.2, "qty": 7.0,  # 0.2% < 0.5% 阈值
        }])

        self.assertEqual(trader.tp_state["TESTUSDT"]["track"], "swing_long")

    def test_restore_survives_corrupt_file(self):
        trader = make_trader(tmpfile=self.tmpfile)
        self.tmpfile.write_text("{not json", encoding="utf-8")

        trader._restore_long_track([{
            "symbol": "TESTUSDT", "side": "LONG",
            "entry_price": 100.0, "qty": 7.0,
        }])

        self.assertEqual(trader.tp_state, {})

    def test_restore_without_file_is_noop(self):
        trader = make_trader(tmpfile=self.tmpfile)
        trader._restore_long_track([])
        self.assertEqual(trader.tp_state, {})


class ConfigTests(unittest.TestCase):
    def test_long_track_defaults_survive_partial_config(self):
        """position_management 是浅层update, long_track缺键必须有兜底"""
        trader = make_trader()
        trader.strategy.cfg["position_management"]["long_track"] = {
            "trail_atr_swing": 4.0}

        cfg = trader._long_track_cfg()

        self.assertEqual(cfg["trail_atr_swing"], 4.0)
        self.assertEqual(cfg["hard_stop_pct"], 6.0)
        self.assertEqual(cfg["max_long_slots"], 1)
        self.assertEqual(cfg["tp1_close_pct"], 30.0)

    def test_disabled_long_track_never_upgrades(self):
        trader = make_trader(pm_override={"long_track": {"enabled": False}})
        trader.tp_state["TESTUSDT"] = scalp_state(peak_price=100.0)

        action = trader._scaled_exit_action(
            "TESTUSDT", "LONG", 10.0, 100.0, 102.0, atr=1.0,
            swing_trend=1, closed_candle=False, leverage=6)

        self.assertAlmostEqual(action[0], 5.0)  # 回到短线 50%
        self.assertFalse(trader.tp_state["TESTUSDT"]["pending_upgrade"])

    def test_shipped_config_enables_long_track(self):
        cfg = json.loads(
            (Path(__file__).parent.parent / "config.json").read_text(encoding="utf-8"))
        lt = cfg["strategy"]["position_management"]["long_track"]

        self.assertTrue(lt["enabled"])
        self.assertEqual(lt["max_long_slots"], 1)
        self.assertEqual(cfg["risk"]["max_positions"], 3)  # 用户调为三仓(2026-08-13)


if __name__ == "__main__":
    unittest.main()
