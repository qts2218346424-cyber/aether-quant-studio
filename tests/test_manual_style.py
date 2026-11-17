import unittest
from backtest import PositionSim


class PositionSimLegTests(unittest.TestCase):
    def test_single_leg_avg_entry_equals_entry_price(self):
        pos = PositionSim("LONG", 100.0, 0)
        self.assertEqual(pos.avg_entry, 100.0)

    def test_add_leg_recomputes_weighted_avg_entry(self):
        pos = PositionSim("LONG", 100.0, 0)
        pos.add_leg(90.0, 0.5, 5)
        # 均价 = (100*1.0 + 90*0.5) / 1.5 = 96.666...
        self.assertAlmostEqual(pos.avg_entry, 96.6666667, places=6)

    def test_pnl_pct_uses_weighted_avg_after_add(self):
        pos = PositionSim("SHORT", 0.02, 0)
        pos.add_leg(0.018, 0.5, 3)
        # 均价 = (0.02*1 + 0.018*0.5)/1.5 = 0.019333
        # SHORT: pnl = (avg - price)/avg
        self.assertAlmostEqual(pos.pnl_pct_at(0.017), 12.0689, places=3)

    def test_peak_pnl_tracks_add_legs(self):
        pos = PositionSim("LONG", 100.0, 0)
        pos.update_peak(105.0, 99.0)
        self.assertAlmostEqual(pos.peak_pnl, 5.0, places=6)
        pos.add_leg(102.0, 0.5, 5)  # 均价 (100+102*0.5)/1.5=100.667
        pos.update_peak(108.0, 101.0)
        # 峰值浮盈 = (108 - 100.667)/100.667*100 = 7.285
        self.assertAlmostEqual(pos.peak_pnl, 7.2847, places=3)

    def test_existing_single_leg_behavior_unchanged(self):
        # 旧接口: entry_price / remaining / close 保持单腿语义
        pos = PositionSim("LONG", 100.0, 0)
        self.assertEqual(pos.entry_price, 100.0)
        self.assertEqual(pos.remaining, 1.0)
        r = pos.close(0.3, 103.0, "tp1", 4)
        self.assertEqual(r, 0.3)
        self.assertEqual(pos.remaining, 0.7)


from backtest import ManualParams, maybe_add_leg


class MaybeAddLegTests(unittest.TestCase):
    def _params(self, **kw):
        p = ManualParams()
        for k, v in kw.items():
            setattr(p, k, v)
        return p

    def test_no_add_when_no_pullback(self):
        pos = PositionSim("LONG", 100.0, 0)
        pos.update_peak(102.0, 99.0)   # 峰值浮盈 2%
        ok = maybe_add_leg(pos, 101.0, self._params())
        self.assertFalse(ok)

    def test_add_when_pullback_exceeds_threshold(self):
        pos = PositionSim("LONG", 100.0, 0)
        pos.update_peak(105.0, 99.0)   # 峰值浮盈 5%
        # 现价 102: 回撤 = 5 - 2 = 3% >= 2.5%
        ok = maybe_add_leg(pos, 102.0, self._params())
        self.assertTrue(ok)

    def test_no_add_when_underwater(self):
        pos = PositionSim("SHORT", 0.02, 0)
        pos.update_peak(0.019, 0.021)  # 峰值浮盈 5%
        # 现价 0.0215: 浮亏, 不摊平
        ok = maybe_add_leg(pos, 0.0215, self._params())
        self.assertFalse(ok)

    def test_no_add_beyond_max_adds(self):
        pos = PositionSim("LONG", 100.0, 0)
        pos.add_leg(97.0, 0.5, 3)
        pos.add_leg(94.0, 0.5, 6)
        pos.add_leg(91.0, 0.5, 9)      # 已 3 次
        pos.update_peak(105.0, 90.0)
        ok = maybe_add_leg(pos, 101.0, self._params())
        self.assertFalse(ok)


from backtest import ManualParams, maybe_add_leg, breakeven_active


class BreakevenTests(unittest.TestCase):
    def test_inactive_before_breakeven_pct(self):
        pos = PositionSim("LONG", 100.0, 0)
        pos.update_peak(101.5, 99.0)   # 峰值浮盈 1.5% < 2%
        self.assertFalse(breakeven_active(pos, ManualParams()))

    def test_active_after_breakeven_pct(self):
        pos = PositionSim("LONG", 100.0, 0)
        pos.update_peak(103.0, 99.0)   # 峰值浮盈 3% >= 2%
        self.assertTrue(breakeven_active(pos, ManualParams()))

    def test_active_uses_avg_entry_with_adds(self):
        pos = PositionSim("SHORT", 0.02, 0)
        pos.add_leg(0.017, 0.5, 4)     # 均价 0.019
        pos.update_peak(0.018, 0.0185) # 峰值浮盈 (0.019-0.018)/0.019=5.26%
        self.assertTrue(breakeven_active(pos, ManualParams()))


import unittest

import numpy as np

from backtest import (ManualParams, PositionSim, breakeven_active,
                      maybe_add_leg, simulate_trade_manual)


class SimulateTradeManualTests(unittest.TestCase):
    def _data(self):
        # 前 5 根横盘, 中间单边上涨至 115, 末尾回落触发跟踪止损
        closes = np.array([100.0] * 5 + [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115.0,
                                         114.0, 113.0, 112.0, 111.0])
        highs = closes + 0.5
        lows = closes - 0.5
        atr = np.full(len(closes), 1.0)
        return closes, highs, lows, atr

    def test_trending_long_hits_tp1_tp2_and_trail(self):
        closes, highs, lows, atr = self._data()
        p = ManualParams()
        pos = PositionSim("LONG", 100.0, 5)
        exits, hold, reason = simulate_trade_manual(
            pos, closes, highs, lows, atr, p, "15m")
        reasons = [e[2] for e in exits]
        self.assertIn("tp1", reasons)
        self.assertIn("tp2", reasons)
        self.assertTrue(any("trail" in r or "breakeven" in r for r in reasons))

    def test_add_leg_on_pullback_then_win(self):
        # 上涨-回调-再上涨: 回调处触发加仓
        closes = np.array([100.0]*5 + [102, 104, 106, 108, 104.5, 103.5, 102.0, 103.0, 106.0, 109.0, 112.0, 115.0, 118.0, 121.0, 124.0])
        highs = closes + 0.5
        lows = closes - 0.5
        atr = np.full(len(closes), 1.0)
        p = ManualParams()
        pos = PositionSim("LONG", 100.0, 5)
        exits, hold, reason = simulate_trade_manual(
            pos, closes, highs, lows, atr, p, "15m")
        self.assertGreaterEqual(pos.add_count, 1)
        self.assertTrue(any(e[2] in ("tp1", "tp2", "trail", "breakeven") for e in exits))

    def test_breakeven_stops_loss_at_avg(self):
        # 涨到 +3% 后一路跌回: 保本止损应全平在均价附近, 不亏
        closes = np.array([100.0]*5 + [101, 102, 103, 102, 101, 100.5, 100.0, 99.5, 99.0, 98.5, 98.0, 97.5, 97.0, 96.5, 96.0])
        highs = closes + 0.5
        lows = closes - 0.5
        atr = np.full(len(closes), 1.0)
        p = ManualParams()
        pos = PositionSim("LONG", 100.0, 5)
        exits, hold, reason = simulate_trade_manual(
            pos, closes, highs, lows, atr, p, "15m")
        self.assertIn(reason, ("breakeven", "soft_stop", "hard_stop"))
        # 平仓均价应接近 100(保本), 远高于硬止损 94
        last_exit_price = exits[-1][1]
        self.assertGreater(last_exit_price, 97.0)


if __name__ == "__main__":
    unittest.main()
