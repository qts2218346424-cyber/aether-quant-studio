"""交易执行模块 v2 - 适配多因子策略引擎"""
import asyncio
import copy
import json
import math
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from pathlib import Path

import numpy as np

from binance_client import BinanceFuturesClient
from strategy import StrategyEngine, detect_ema_ribbon, detect_main_force_intent, calc_atr
from risk_manager import RiskManager
from ai_analyst import AIAnalyst
from news_fetcher import NewsFetcher
from market_sentiment import MarketSentiment
from ai_committee import AICommittee
from typesafe_engine import TypeSafeDecisionEngine
from config import load_config
from trade_journal import journal


# 高时间框架映射
HTF_MAP = {"1m": "5m", "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d"}

# 每日交易HTML图表报表模板 (__DATA__ 会被替换为报表JSON)
def _rolling_ma(values: list, period: int) -> list:
    """简单移动平均, 前period-1个位置为None(与币安MA渲染一致)"""
    out = []
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= period:
            s -= values[i - period]
        out.append(round(s / period, 8) if i + 1 >= period else None)
    return out


HTML_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>每日交易图表报告</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
  :root { --bg:#0b0e11; --card:#161a1e; --border:#252a32; --t1:#eaecef; --t2:#848e9c;
          --green:#2ebd85; --red:#f6465d; --gold:#f0b90b; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--t1);
         font-family:"Microsoft YaHei","PingFang SC",Arial,sans-serif; padding:18px; }
  h1 { font-size:18px; margin-bottom:4px; }
  .sub { color:var(--t2); font-size:12px; margin-bottom:14px; }
  .chips { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:16px; }
  .chip { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:10px 16px; }
  .chip .k { font-size:11px; color:var(--t2); }
  .chip .v { font-size:17px; font-weight:700; margin-top:2px; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:8px;
          padding:12px; margin-bottom:16px; }
  .card h2 { font-size:14px; margin-bottom:8px; color:var(--gold); }
  .chart { width:100%; height:280px; }
  .kchart { width:100%; height:400px; }
  table { width:100%; border-collapse:collapse; font-size:11px; margin-top:10px; }
  th,td { padding:5px 8px; text-align:left; border-bottom:1px solid var(--border); white-space:nowrap; }
  th { color:var(--t2); font-weight:600; }
  td.reason { white-space:normal; max-width:420px; }
  .g { color:var(--green); } .r { color:var(--red); } .y { color:var(--gold); }
  .empty { color:var(--t2); padding:30px; text-align:center; }
  .notes { margin-top:10px; padding-left:18px; font-size:12px; line-height:1.9; color:var(--t1); }
  .notes li::marker { color:var(--gold); }
</style>
</head>
<body>
<div id="app"></div>
<script>
const DATA = __DATA__;
const S = DATA.summary;
const app = document.getElementById('app');
const fmtTs = ts => { const d = new Date(ts);
  return ('0'+(d.getMonth()+1)).slice(-2)+'-'+('0'+d.getDate()).slice(-2)+' '+('0'+d.getHours()).slice(-2)+':'+('0'+d.getMinutes()).slice(-2); };
const fmtHm = ts => { const d = new Date(ts);
  return ('0'+d.getHours()).slice(-2)+':'+('0'+d.getMinutes()).slice(-2); };
const esc = s => String(s ?? '').replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const cls = v => v > 0 ? 'g' : (v < 0 ? 'r' : '');
const fp = v => v == null ? '--' : Number(Number(v).toPrecision(8)).toString();
const intentColor = it => it === '出货' ? 'var(--red)'
  : (it === '洗盘' || it === '吸筹') ? 'var(--green)'
  : it === '拉升' ? '#f0b90b' : 'var(--t2)';

let html = `<h1>每日交易图表报告 · ${S.date}</h1>
<div class="sub">量化交易机器人自动生成 · K线周期 5m · 金色=开仓 / 绿红=平仓盈亏 · MA(7)/(25)/(99)</div>
<div class="chips">
  <div class="chip"><div class="k">平仓笔数</div><div class="v">${S.closed}</div></div>
  <div class="chip"><div class="k">胜率</div><div class="v">${S.win_rate}%</div></div>
  <div class="chip"><div class="k">净盈亏</div>
    <div class="v ${cls(S.net_pnl)}">${S.net_pnl >= 0 ? '+' : ''}${S.net_pnl.toFixed(4)} U</div></div>
  <div class="chip"><div class="k">手续费</div>
    <div class="v r">-${S.commission.toFixed(4)} U</div></div>
  <div class="chip"><div class="k">未平仓</div><div class="v y">${S.open_left}</div></div>
</div>`;

if (!DATA.pnl_series.length && !DATA.symbols.length) {
  html += '<div class="card"><div class="empty">当日无交易记录</div></div>';
} else {
  // ===== 每日总结: 量价结构 + 主力意图 =====
  if (DATA.symbol_summary.length) {
    const rows = DATA.symbol_summary.map(sp => `<tr>
      <td><b>${sp.symbol}</b></td>
      <td class="${cls(sp.chg_pct)}">${sp.chg_pct >= 0 ? '+' : ''}${sp.chg_pct}%</td>
      <td style="color:${sp.vol_feature.includes('放量下跌') ? 'var(--red)' : sp.vol_feature.includes('缩量') ? '#f0b90b' : 'var(--t1)'}">${sp.vol_feature} (${sp.vol_ratio})</td>
      <td style="color:${intentColor(sp.intent)}">${sp.intent || '--'}${sp.intent_confidence ? ' ' + sp.intent_confidence + '%' : ''}</td>
      <td>${sp.trade_count}</td>
      <td class="${cls(sp.realized)}">${sp.realized >= 0 ? '+' : ''}${sp.realized.toFixed(4)} U</td>
    </tr>`).join('');
    const notesHtml = (DATA.notes || []).map(n => `<li>${esc(n)}</li>`).join('');
    html += `<div class="card"><h2>每日总结 · 量价结构与主力意图</h2>
      <table><thead><tr><th>币种</th><th>近12h涨跌</th><th>量价特征(阴量/阳量)</th>
        <th>主力意图</th><th>平仓笔数</th><th>已实现盈亏</th></tr></thead>
      <tbody>${rows}</tbody></table>
      ${notesHtml ? `<ul class="notes">${notesHtml}</ul>` : ''}
    </div>`;
  }
  if (DATA.pnl_series.length) {
    html += '<div class="card"><h2>每笔收益与累计盈亏</h2><div id="pnl-chart" class="chart"></div></div>';
  }
  DATA.symbols.forEach((sp, idx) => {
    const rows = sp.trades.map(t => `<tr>
      <td>${esc(t.status === '持仓中' ? (t.entry_time || '--') : (t.exit_time || '--'))}</td>
      <td class="${t.side === 'LONG' ? 'g' : 'r'}">${t.side === 'LONG' ? '多' : '空'}</td>
      <td>${t.qty}</td>
      <td>${t.entry_price || '--'} → ${t.exit_price ?? '持仓中'}</td>
      <td class="${cls(t.pnl)}">${t.exit_ts ? (t.pnl >= 0 ? '+' : '') + t.pnl.toFixed(4) + ' U' : '--'}</td>
      <td>${t.leverage ? t.leverage + 'x' : '--'}</td>
      <td class="reason">${esc(t.reason || (t.status === '持仓中' ? '持仓中' : '--'))}</td>
    </tr>`).join('');
    html += `<div class="card"><h2>${sp.symbol} · K线与买卖点 · <span style="color:${intentColor(sp.intent)};font-size:12px">主力意图: ${sp.intent || '--'}${sp.intent_confidence ? ' ' + sp.intent_confidence + '%' : ''}</span> · <span style="color:var(--t2);font-size:12px">${sp.vol_feature}</span></h2>
      <div id="kchart-${idx}" class="kchart"></div>
      <table><thead><tr><th>时间</th><th>方向</th><th>数量</th><th>开→平价格</th>
        <th>盈亏</th><th>杠杆</th><th>理由</th></tr></thead><tbody>${rows}</tbody></table>
    </div>`;
  });
}
app.innerHTML = html;

if (DATA.pnl_series.length) {
  const pc = echarts.init(document.getElementById('pnl-chart'));
  pc.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { data: ['每笔盈亏', '累计盈亏'], textStyle: { color: '#848e9c' } },
    grid: { left: 50, right: 30, top: 34, bottom: 52 },
    xAxis: { type: 'category', data: DATA.pnl_series.map(p => p.label),
             axisLabel: { color: '#848e9c', rotate: 28, fontSize: 10 } },
    yAxis: { type: 'value', name: 'U', axisLabel: { color: '#848e9c' },
             splitLine: { lineStyle: { color: '#252a32' } } },
    series: [
      { name: '每笔盈亏', type: 'bar', barMaxWidth: 26,
        data: DATA.pnl_series.map(p => ({ value: p.pnl,
          itemStyle: { color: p.pnl >= 0 ? '#2ebd85' : '#f6465d' } })) },
      { name: '累计盈亏', type: 'line', smooth: true, symbolSize: 5,
        data: DATA.pnl_series.map(p => p.cum),
        lineStyle: { color: '#f0b90b', width: 2 }, itemStyle: { color: '#f0b90b' } }
    ]
  });
}

DATA.symbols.forEach((sp, idx) => {
  const labels = sp.klines.map(k => fmtTs(k[0]));
  const nearest = ts => {
    let best = 0, bd = Infinity;
    sp.klines.forEach((k, i) => { const d = Math.abs(k[0] - ts);
      if (d < bd) { bd = d; best = i; } });
    return best;
  };
  const marks = sp.marks.map(m => ({
    coord: [labels[nearest(m.ts)], m.price],
    value: m.label, symbol: 'pin', symbolSize: 42,
    itemStyle: { color: m.color },
    label: { fontSize: 9, color: '#fff' }
  }));
  const kc = echarts.init(document.getElementById('kchart-' + idx));
  kc.setOption({
    backgroundColor: 'transparent',
    animation: false,
    legend: { data: ['K线', 'MA(7)', 'MA(25)', 'MA(99)'], textStyle: { color: '#848e9c', fontSize: 10 }, top: 0 },
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(22,26,30,0.96)', borderColor: '#252a32',
      textStyle: { color: '#eaecef', fontSize: 11 },
      formatter: function (ps) {
        const kItem = ps.find(p => p.seriesType === 'candlestick');
        if (!kItem) return '';
        const d = kItem.data;
        const o = d[0], cl = d[1], lo = d[2], hi = d[3];
        const chg = cl - o;
        const pct = o ? chg / o * 100 : 0;
        const amp = o ? (hi - lo) / o * 100 : 0;
        const cCol = chg >= 0 ? '#2ebd85' : '#f6465d';
        const vol = sp.vols[kItem.dataIndex];
        let h = `<div style="line-height:1.75">时间 ${kItem.axisValue}<br>`
          + `开 <b>${fp(o)}</b>　高 <b style="color:#2ebd85">${fp(hi)}</b><br>`
          + `低 <b style="color:#f6465d">${fp(lo)}</b>　收 <b style="color:${cCol}">${fp(cl)}</b><br>`
          + `涨跌 <span style="color:${cCol}">${chg >= 0 ? '+' : ''}${fp(chg)} (${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%)</span><br>`
          + `振幅 ${amp.toFixed(2)}%　量 ${Number(vol || 0).toLocaleString()}<br>`;
        ps.forEach(p => {
          if (p.seriesType === 'line' && p.value != null) {
            h += `<span style="color:${p.color}">${p.seriesName}: ${fp(p.value)}</span>　`;
          }
        });
        return h + '</div>';
      }
    },
    grid: { left: 62, right: 20, top: 28, bottom: 40 },
    xAxis: { type: 'category', data: labels,
             axisLabel: { color: '#848e9c', fontSize: 10 } },
    yAxis: { type: 'value', scale: true, axisLabel: { color: '#848e9c' },
             splitLine: { lineStyle: { color: '#252a32' } } },
    series: [
      {
        name: 'K线', type: 'candlestick',
        data: sp.klines.map(k => [k[1], k[4], k[3], k[2]]),
        itemStyle: { color: '#2ebd85', color0: '#f6465d',
                     borderColor: '#2ebd85', borderColor0: '#f6465d' },
        markPoint: { data: marks }
      },
      { name: 'MA(7)', type: 'line', data: sp.ma7, symbol: 'none',
        lineStyle: { width: 1, color: '#f5c542' }, itemStyle: { color: '#f5c542' } },
      { name: 'MA(25)', type: 'line', data: sp.ma25, symbol: 'none',
        lineStyle: { width: 1, color: '#c07bff' }, itemStyle: { color: '#c07bff' } },
      { name: 'MA(99)', type: 'line', data: sp.ma99, symbol: 'none',
        lineStyle: { width: 1, color: '#5aa2f7' }, itemStyle: { color: '#5aa2f7' } }
    ]
  });
});

window.addEventListener('resize', () => {
  document.querySelectorAll('[_echarts_instance_]').forEach(el => {
    const inst = echarts.getInstanceByDom(el);
    if (inst) inst.resize();
  });
});
</script>
</body>
</html>

"""


class Trader:
    def __init__(self):
        self.cfg = load_config()
        self.client = BinanceFuturesClient(self.cfg)
        self.strategy = StrategyEngine(self.cfg["strategy"])
        self.risk = RiskManager(self.cfg["risk"])
        self.analyst = AIAnalyst()
        self.entry_decision_mode = self.cfg.get("entry_decision_mode", "strategy_direct")
        ai_cfg = dict(self.cfg.get("ai_committee", {}) or {})
        if "proxy" not in ai_cfg and self.cfg.get("proxy"):
            ai_cfg["proxy"] = self.cfg.get("proxy")
        self.ai_committee = AICommittee(ai_cfg)
        self.ai_reviews_log: list[dict] = []
        self.typesafe_engine = TypeSafeDecisionEngine(self.cfg.get("typesafe", {}), proxy=self.cfg.get("proxy"))
        self.typesafe_reviews_log: list[dict] = []
        self.autonomous_hunter_last_sweep: float = 0.0
        self.autonomous_hunter_interval: float = float(
            self.cfg.get("typesafe", {}).get("autonomous_hunter", {}).get("scan_interval_sec", 30.0)
        )
        self.news_fetcher = NewsFetcher(self.cfg.get("proxy"))
        self.market_sentiment = MarketSentiment(self.cfg.get("proxy"), self.cfg.get("base_url", "https://fapi.binance.com"))
        self.analysis_cache: dict[str, dict] = {}  # symbol -> analysis result
        self.leverage = self.cfg.get("leverage", 10)
        self.symbols = self._normalize_symbols(self.cfg.get("symbols", []))
        self.position_symbols: list[str] = []  # 当前持仓币种(运行时自动检测)
        self.positions_cache: dict[str, dict] = {}  # symbol -> 持仓详情(供AI持仓分析)
        self.interval = self.cfg.get("interval", "5m")
        self.htf_interval = HTF_MAP.get(self.interval, "1h")
        self.swing_interval = self._position_management_cfg().get("swing_interval", "1h")
        self.running = False
        self.auto_trade = False
        self.live_trading_enabled = bool(self.cfg.get("live_trading_enabled", False))
        self.paper_trading = bool(self.cfg.get("paper_trading", True))
        raw_mode = self.cfg.get("trading_mode")
        if raw_mode in ("READONLY", "SHADOW", "PAPER", "MICRO_LIVE", "LIVE"):
            self.trading_mode = raw_mode
        else:
            self.trading_mode = "PAPER" if self.paper_trading else ("LIVE" if self.live_trading_enabled else "READONLY")
        self.last_market_data_ts: float = time.time()
        self._reconciliation_task = None
        self.reconciliation_log: list[dict] = []
        self.decision_snapshots_log: list[dict] = []
        self.signals_log: list[dict] = []
        self.trades_log: list[dict] = []
        self.execution_events: list[dict] = []
        # 完整K线缓存: symbol -> {closes, highs, lows, volumes}
        self.klines_cache: dict[str, dict] = {}
        self.htf_cache: dict[str, list] = {}  # 高TF closes
        self.swing_cache: dict[str, list] = {}
        # 长线赛道: swing周期完整OHLC(算1h ATR需要high/low, swing_cache只存closes)
        self.swing_ohlc_cache: dict[str, dict] = {}
        self.funding_rates: dict[str, float] = {}
        self.latest_indicators: dict[str, dict] = {}
        self.latest_result: dict[str, dict] = {}
        self.latest_smart_money: dict[str, dict] = {}
        self.latest_klines: dict[str, dict] = {}  # 实时K线tick: symbol -> kline dict
        self._last_closed_time: dict[str, int] = {}  # 轮询检测K线收盘用
        self.tp_state: dict[str, dict] = {}  # 分批止盈状态: symbol -> {side, orig_qty, tp1, tp2}
        self.grid_state: dict[str, dict] = {}  # 高波动网格(两头吃): symbol -> 网格状态
        # 交易冷却: 同币平仓后冷却 + 连亏熔断(见 config risk 段)
        self._cooldown_until: dict[str, float] = {}  # symbol -> 下次可开仓时间戳
        self._streak_losses: int = 0                  # 连续亏损笔数
        self._streak_until: float = 0.0               # 连亏熔断到期时间戳(0=未熔断)
        self._last_trade_close_time: float = 0.0      # 最近一次平仓时间(跨币冷却)
        # 动态躲避(大波动币种): symbol -> {until, losses} 连续亏损暂停开仓, 到期自动恢复
        self._volatile_pause: dict[str, dict] = {}
        self._volatile_losses: dict[str, int] = {}    # symbol -> 连续亏损计数
        self._trade_sync_cache: dict[str, tuple[float, dict]] = {}
        self._ws_task = None
        self._poll_task = None
        self._funding_task = None

    @staticmethod
    def _number(value, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _order_execution(cls, order: dict) -> dict:
        """Normalize the exchange's RESULT payload into a single fill outcome."""
        order = order if isinstance(order, dict) else {}
        local = order.get("_local_execution", {}) or {}
        status = str(order.get("status", "")).upper()
        executed_qty = cls._number(order.get("executedQty"))
        normalized_qty = cls._number(local.get("normalized_qty"))
        requested_qty = cls._number(local.get("requested_qty"))
        return {
            "order_id": order.get("orderId"),
            "status": status or "UNKNOWN",
            "requested_qty": requested_qty,
            "normalized_qty": normalized_qty,
            "executed_qty": executed_qty,
            "avg_price": cls._number(order.get("avgPrice")),
            "completed": bool(order.get("orderId")) and status == "FILLED" and executed_qty > 0,
            "partial": executed_qty > 0 and status != "FILLED",
        }

    def _record_execution_event(self, action: str, outcome: str, symbol: str,
                                side: str, reason: str = "", error: str = "",
                                **details):
        event = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": action,
            "outcome": outcome,
            "symbol": symbol,
            "side": side,
            "reason": str(reason or "")[:180],
            "error": str(error or "")[:240],
        }
        for key, value in details.items():
            if value is not None:
                event[key] = value
        self.execution_events.append(event)
        if len(self.execution_events) > 100:
            del self.execution_events[:-100]

    async def manual_limit_open(self, symbol: str, side: str,
                                quantity: float, price: float) -> dict:
        """从图表票据提交一笔明确确认的GTC限价开仓单。"""
        normalized_symbol = str(symbol or "").strip().upper().replace("/", "")
        normalized_side = str(side or "").strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol is required")
        if normalized_side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        try:
            normalized_quantity = float(quantity)
            normalized_price = float(price)
        except (TypeError, ValueError):
            raise ValueError("quantity and price must be numbers") from None
        if not math.isfinite(normalized_quantity) or normalized_quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if not math.isfinite(normalized_price) or normalized_price <= 0:
            raise ValueError("price must be greater than zero")
        if hasattr(self, "_trade_symbol_allowed") and not self._trade_symbol_allowed(normalized_symbol):
            raise ValueError(f"symbol {normalized_symbol} is not allowed")
        if getattr(self, "trading_mode", "") == "READONLY":
            raise ValueError("系统当前处于只读模式(READONLY)，已物理锁定下单功能")

        # 执行层统一硬风控强制校验（支持轻量级无状态单测客户端平滑回退）
        if getattr(self, "risk", None) is not None and hasattr(self.client, "get_account"):
            account = await self.client.get_account()
            balance = float(account.get("totalWalletBalance", 0))
            open_positions = await self.client.get_positions()
            passed, _, gate_reason, gate_details = self.risk.check_execution_risk_gate(
                symbol=normalized_symbol,
                side="LONG" if normalized_side == "BUY" else "SHORT",
                price=normalized_price,
                quantity=normalized_quantity,
                requested_leverage=getattr(self, "leverage", 1),
                balance=balance,
                open_positions=open_positions,
                data_last_updated_ts=getattr(self, "last_market_data_ts", None),
                is_force=True,
            )
            if not passed:
                self._record_execution_event(
                    "manual_limit_open", "blocked_by_hard_risk_gate", normalized_symbol, normalized_side,
                    reason="hard_risk_gate", gate_reason=gate_reason,
                )
                raise ValueError(f"执行层硬风控拦截: {gate_reason}")

        direction = "LONG" if normalized_side == "BUY" else "SHORT"
        position_side = await self.client._position_side(direction)
        client_order_id = f"web-{normalized_symbol[:8]}-{int(time.time() * 1000) % 1000000}"
        order = await self.client.place_limit_order(
            normalized_symbol,
            normalized_side,
            position_side,
            normalized_quantity,
            normalized_price,
            client_order_id,
        )
        status = str(order.get("status", "UNKNOWN")).upper()
        self._record_execution_event(
            "manual_limit_open",
            "success" if status in {"NEW", "PARTIALLY_FILLED", "FILLED"} else "failed",
            normalized_symbol,
            normalized_side,
            reason="chart ticket",
            order_id=order.get("orderId"),
            requested_qty=normalized_quantity,
            requested_price=normalized_price,
            exchange_status=status,
        )
        return {
            "ok": True,
            "symbol": normalized_symbol,
            "side": normalized_side,
            "position_side": position_side,
            "quantity": normalized_quantity,
            "price": normalized_price,
            "status": status,
            "order": order,
        }

    async def _open_position_maker_first(self, symbol: str, side: str,
                                         position_side: str, qty: float,
                                         ref_price: float,
                                         execution_cfg: dict,
                                         limit_hint: float = 0.0,
                                         atr: float = 0.0) -> dict:
        """开仓优先挂限价maker单。

        limit_hint: 更合适的入场价(做多=支撑位, 做空=压力位), 0=不用。
        挂单价 = clamp(limit_hint, 现价∓0.6×ATR) 防止挂太远永不成交;
        限价单等待 limit_wait_sec(默认300s) 内成交, 超时撤单放弃
        (不市价追入, 等下一轮信号重新评估)。
        maker成交省taker 0.03%双边, 转市价仅损失少许时间。
        """
        enabled = bool(execution_cfg.get("maker_first", False))
        wait = float(execution_cfg.get("limit_wait_sec", 300))
        if not enabled or not ref_price or ref_price <= 0:
            if side == "BUY":
                return await self.client.market_open_long(symbol, qty)
            return await self.client.market_open_short(symbol, qty)

        try:
            tick = await self.client._price_tick(symbol)
            ref_d = Decimal(str(ref_price))
            if side == "BUY":
                limit_price = max(tick, ref_d - tick)  # 买: 挂低1个tick
            else:
                limit_price = ref_d + tick  # 卖: 挂高1个tick
            # 支撑位/压力位限价: 限制最大让价 0.6×ATR(约回撤一半), 防止挂太远永不成交
            if limit_hint and limit_hint > 0 and atr > 0:
                if side == "BUY":
                    floor = ref_d - Decimal(str(atr)) * Decimal("0.6")
                    limit_price = max(floor, Decimal(str(limit_hint)))
                else:
                    ceil = ref_d + Decimal(str(atr)) * Decimal("0.6")
                    limit_price = min(ceil, Decimal(str(limit_hint)))
            limit_price = float(
                (Decimal(str(limit_price)) / Decimal(str(tick))).quantize(
                    Decimal("1"), rounding=ROUND_DOWN if side == "BUY" else ROUND_UP)
                * Decimal(str(tick)))
            cid = f"mkr-{symbol[:8]}-{int(time.time() * 1000) % 1000000}"
            order = await self.client.place_limit_order(
                symbol, side, position_side, qty, float(limit_price), cid)
            status = str(order.get("status", "")).upper()
            if status == "FILLED":
                print(f"[maker] {symbol} {side} 限价单立即成交@{order.get('avgPrice')} (maker)")
                return order
            # 未成交: 轮询等待
            oid = order.get("orderId")
            deadline = time.time() + wait
            while time.time() < deadline:
                await asyncio.sleep(1)
                try:
                    cur = await self.client.get_order(symbol, order_id=oid)
                    st = str(cur.get("status", "")).upper()
                    if st == "FILLED":
                        cur.setdefault("_local_execution", order.get("_local_execution", {}))
                        print(f"[maker] {symbol} {side} 限价单轮询成交@{cur.get('avgPrice')} (maker)")
                        return cur
                    if st not in ("NEW", "PARTIALLY_FILLED"):
                        break
                except Exception:
                    pass
            # 超时未成交: 撤限价单, 放弃本轮(不市价追入)
            try:
                await self.client.cancel_order(symbol, order_id=oid)
            except Exception:
                pass
            print(f"[maker] {symbol} {side} 限价单{wait:.0f}s未成交@{limit_price}, "
                  f"撤单放弃(等下一轮信号)")
            return {"status": "CANCELED", "_abandoned": True, "orderId": oid,
                    "avgPrice": 0, "executedQty": 0, "cumQuote": 0}
        except Exception as e:
            print(f"[maker] {symbol} {side} 限价流程异常({e}), 直接市价")
            if side == "BUY":
                return await self.client.market_open_long(symbol, qty)
            return await self.client.market_open_short(symbol, qty)

    def watch_symbols(self) -> list[str]:
        """完整监控列表 = 当前持仓(优先) + 配置观察币, 去重"""
        return list(dict.fromkeys(self.position_symbols + self.symbols))

    @staticmethod
    def _normalize_symbols(symbols) -> list[str]:
        if isinstance(symbols, str):
            symbols = symbols.replace("，", ",").split(",")
        if not isinstance(symbols, (list, tuple, set)):
            return []
        result = []
        for value in symbols:
            symbol = str(value).strip().upper().replace("/", "")
            if symbol and symbol not in result:
                result.append(symbol)
        return result

    def _liquidity_cfg(self) -> dict:
        defaults = {
            "enabled": True,
            "min_quote_volume_24h": 10000000,
            "max_spread_bps": 15,
        }
        defaults.update(self.strategy.cfg.get("liquidity", {}) or {})
        return defaults

    def _trade_symbol_allowed(self, symbol: str) -> bool:
        """Whitelist gate with an explicit all-qualified-symbols mode."""
        if self._market_selection_cfg().get("allow_all_symbols", False):
            return True
        return symbol.upper() in set(self.symbols)

    def _market_selection_cfg(self) -> dict:
        """Universe filters applied inside the explicit trading whitelist."""
        defaults = {
            "enabled": True,
            "max_price": 1.0,
            "min_atr_pct": 0.8,
            "min_vol_surge": 1.2,
            "candidate_scan_limit": 80,
        }
        defaults.update(self.strategy.cfg.get("market_selection", {}) or {})
        return defaults

    def _execution_cfg(self) -> dict:
        defaults = {
            "margin_mode": "ISOLATED",
            "enforce_margin_mode": True,
            "min_notional_buffer_pct": 2,
            "max_notional_overshoot_pct": 15,
        }
        defaults.update(self.cfg.get("execution", {}) or {})
        return defaults

    def _entry_size_pct(self, tier_ratio: float, fallback: float) -> float:
        """每笔保证金 = risk.position_size_pct(全局基准%) × 档位系数;
        未配置时回退到内置档位. 默认 position_size_pct=15 时:
        swing保守 0.5×15=7.5% / swing激进 0.7×15=10.5% / 非swing 0.6×15=9% / 激进 1.0×15=15%"""
        try:
            v = float(self.cfg.get("risk", {}).get("position_size_pct") or 0)
        except (TypeError, ValueError):
            v = 0.0
        return v / 100 * tier_ratio if v > 0 else fallback

    def _entry_margin_multiplier(self) -> float:
        """Scale planned opening margin without changing explicit manual quantities."""
        try:
            value = float(self.cfg.get("risk", {}).get("entry_margin_multiplier", 1.0))
        except (TypeError, ValueError):
            value = 1.0
        return min(3.0, max(0.1, value))

    def _planned_entry_notional(
        self, balance: float, size_pct: float, leverage: int | float,
        min_notional: float = 5.0,
    ) -> float:
        """Return the exchange-valid target notional after the configured margin scale."""
        base_margin = max(0.0, float(balance)) * max(0.0, float(size_pct))
        base_notional = max(float(min_notional), base_margin * max(1.0, float(leverage)))
        return base_notional * self._entry_margin_multiplier()

    async def _prepare_new_position(self, symbol: str, leverage: int | float | None = None):
        """Apply configured margin mode and leverage before a new order; never touches existing positions."""
        execution = self._execution_cfg()
        if execution.get("enforce_margin_mode", True):
            margin_mode = str(execution.get("margin_mode", "ISOLATED")).upper()
            try:
                await self.client.set_margin_type(symbol, margin_mode)
            except Exception as exc:
                # Binance uses -4046 when the requested margin mode is already active.
                if "-4046" not in str(exc) and "No need to change margin type" not in str(exc):
                    raise RuntimeError(f"margin mode setup failed for {symbol}: {exc}") from exc
        if leverage:
            effective_leverage, max_leverage = await self.client.clamp_leverage(symbol, leverage)
            await self.client.set_leverage(symbol, effective_leverage)
            return effective_leverage, max_leverage
        return None, None

    async def _liquidity_snapshot(self, symbol: str, ticker: dict = None) -> dict:
        cfg = self._liquidity_cfg()
        if not cfg.get("enabled", True):
            return {
                "symbol": symbol, "allowed": True, "quote_volume_24h": None,
                "spread_bps": None, "reason": "流动性过滤未启用",
            }
        try:
            ticker = ticker or await self.client.get_ticker(symbol)
            quote_volume = float(ticker.get("quoteVolume", 0) or 0)
            bid = float(ticker.get("bidPrice", 0) or 0)
            ask = float(ticker.get("askPrice", 0) or 0)
            spread_bps = ((ask - bid) / ((ask + bid) / 2) * 10000) if bid > 0 and ask >= bid else None
            min_volume = float(cfg.get("min_quote_volume_24h", 10000000))
            max_spread = float(cfg.get("max_spread_bps", 15))
            volume_ok = quote_volume >= min_volume
            spread_ok = spread_bps is None or spread_bps <= max_spread
            allowed = volume_ok and spread_ok
            reasons = []
            if not volume_ok:
                reasons.append(f"24h成交额{quote_volume/1e6:.2f}M低于{min_volume/1e6:.2f}M")
            if not spread_ok:
                reasons.append(f"价差{spread_bps:.1f}bps高于{max_spread:.1f}bps")
            return {
                "symbol": symbol,
                "allowed": allowed,
                "quote_volume_24h": round(quote_volume, 2),
                "spread_bps": round(spread_bps, 2) if spread_bps is not None else None,
                "reason": "；".join(reasons) if reasons else "流动性通过",
            }
        except Exception as e:
            return {
                "symbol": symbol, "allowed": False,
                "quote_volume_24h": 0, "spread_bps": None,
                "reason": f"流动性数据获取失败: {e}",
            }

    def _position_management_cfg(self) -> dict:
        defaults = {
            "reduce_confidence": 75,
            "full_exit_confidence": 80,
            "partial_close_pct": 30,
            "trailing_atr": 3.0,
            "lock_profit_atr": 0.25,
            "exit_score_threshold": 5,
            "require_htf_reversal": True,
            "holding_mode": "swing",
            "swing_interval": "1h",
            "initial_stop_atr": 3.0,
            "min_stop_pct": 1.8,
            "hard_stop_pct": 4.0,
            "max_margin_loss_pct": 45.0,
            "stop_confirmation_candles": 2,
            "require_swing_reversal": True,
            "trail_after_tp": 2,
            "tp1_atr": 3.0,
            "tp2_atr": 6.0,
            "swing_max_leverage": 6,
            "max_entry_margin_pct": 25.0,
            "short_early_stop_enabled": True,
            "short_early_stop_minutes": 30,
            "short_early_stop_pct": 2.5,
        }
        defaults.update(self.strategy.cfg.get("position_management", {}) or {})
        return defaults

    def _auto_entry_min_base_score(self) -> float:
        """Require a meaningful technical score before smart-money weighting may enter."""
        threshold = abs(float(self.strategy.threshold))
        configured = self.strategy.cfg.get("auto_entry_min_base_score")
        if configured is None:
            return max(20.0, threshold)
        try:
            return max(threshold, abs(float(configured)))
        except (TypeError, ValueError):
            return max(20.0, threshold)

    @staticmethod
    def _closed_kline_rows(klines: list) -> list:
        """Binance REST klines include the currently forming candle as the last row."""
        return list(klines[:-1]) if len(klines) > 1 else []

    @staticmethod
    def _technical_recommendation_signal(result: dict) -> int:
        """A strategy veto is final and may not be rescued by later score weighting."""
        signal = int(result.get("signal", 0) or 0)
        return signal if signal in (-1, 1) else 0

    @staticmethod
    def _minimum_notional_leverage_plan(
        planned_notional: float,
        balance: float,
        starting_leverage: int,
        leverage_cap: int,
        max_entry_margin_pct: float,
    ) -> dict:
        """Fit an exchange-minimum notional inside a strategy leverage and margin budget."""
        planned_notional = max(0.0, float(planned_notional))
        balance = max(0.0, float(balance))
        starting_leverage = max(1, int(starting_leverage))
        leverage_cap = max(1, int(leverage_cap))
        margin_ratio = min(0.95, max(0.05, float(max_entry_margin_pct) / 100))
        max_margin = balance * margin_ratio
        required_leverage = (
            max(1, math.ceil(planned_notional / max_margin))
            if max_margin > 0 else leverage_cap + 1
        )
        allowed = required_leverage <= leverage_cap
        leverage = min(leverage_cap, max(starting_leverage, required_leverage))
        return {
            "allowed": allowed,
            "leverage": leverage,
            "required_leverage": required_leverage,
            "leverage_cap": leverage_cap,
            "max_margin": max_margin,
            "margin": planned_notional / leverage if leverage else planned_notional,
            "margin_ratio": margin_ratio,
        }

    def _smart_money_cfg(self) -> dict:
        defaults = {
            "enabled": True,
            "score_weight": 18,
            "min_alignment_score": 18,
            "block_opposite_score": 32,
            "require_confirmation": False,
            "scan_limit": 8,
        }
        defaults.update(self.strategy.cfg.get("smart_money", {}) or {})
        return defaults

    def _bars_per_hour(self) -> int:
        return {
            "1m": 60, "3m": 20, "5m": 12, "15m": 4,
            "30m": 2, "1h": 1, "2h": 1, "4h": 1,
        }.get(self.interval, 12)

    @staticmethod
    def _series_change(values, bars: int) -> float:
        if values is None or len(values) <= bars or float(values[-bars - 1]) == 0:
            return 0.0
        return (float(values[-1]) - float(values[-bars - 1])) / float(values[-bars - 1]) * 100

    async def _smart_money_snapshot(
        self,
        symbol: str,
        closes=None,
        volumes=None,
        price_change_24h: float | None = None,
        funding_rate: float | None = None,
        force: bool = False,
    ) -> dict:
        """生成某交易对的聪明钱快照；只使用公开市场数据，不触发订单。"""
        closes = closes if closes is not None else self.klines_cache.get(symbol, {}).get("closes", [])
        volumes = volumes if volumes is not None else self.klines_cache.get(symbol, {}).get("volumes", [])
        bars_1h = self._bars_per_hour()
        price_change_1h = self._series_change(closes, bars_1h)
        if price_change_24h is None:
            price_change_24h = self._series_change(closes, min(bars_1h * 24, max(1, len(closes) - 1)))
        volume_surge = 1.0
        if volumes is not None and len(volumes) >= 10:
            recent = float(np.mean(volumes[-3:]))
            base = float(np.mean(volumes[-50:])) if len(volumes) >= 50 else float(np.mean(volumes))
            volume_surge = recent / base if base > 0 else 1.0
        if funding_rate is None:
            funding_rate = self.funding_rates.get(symbol)

        sentiment = await self.market_sentiment.get_derivatives(symbol, force=force)
        smart = self.market_sentiment.score_smart_money(
            sentiment,
            price_change_1h=price_change_1h,
            price_change_24h=price_change_24h,
            volume_surge=volume_surge,
            funding_rate=funding_rate,
        )
        smart["symbol"] = symbol
        smart["long_short"] = sentiment.get("long_short", {})
        smart["top_trader_account"] = sentiment.get("top_trader_account", {})
        smart["top_trader"] = sentiment.get("top_trader", {})
        smart["open_interest"] = sentiment.get("open_interest", {})
        smart["funding_rate"] = funding_rate
        smart["updated_at"] = datetime.now().strftime("%H:%M:%S")
        self.latest_smart_money[symbol] = smart
        return smart

    def _refine_intent_with_derivatives(self, item: dict, smart: dict) -> None:
        """用持仓量(OI)变化+大户行为对量价意图做二次确认, 可把假洗盘(真出货)纠错"""
        intent = item.get("intent", "观望")
        if intent in ("观望", "拉升", None):
            return
        dist_pts = 0
        shake_pts = 0
        notes = []
        oi = (smart or {}).get("open_interest") or {}
        tt = (smart or {}).get("top_trader") or {}
        if oi.get("available"):
            oi4 = float(oi.get("change_4h_pct") or 0)
            if intent == "出货":
                if oi4 < -2:
                    dist_pts += 2
                    notes.append(f"OI 4h {oi4:+.1f}% 资金撤离佐证出货")
                elif oi4 > 3:
                    dist_pts -= 1
                    notes.append(f"OI 4h {oi4:+.1f}% 仍在增仓, 出货证据减弱")
            else:  # 洗盘 / 吸筹
                if oi4 < -4:
                    dist_pts += 3
                    notes.append(f"OI 4h {oi4:+.1f}% 资金大幅撤离")
                elif -1.5 <= oi4 <= 3:
                    shake_pts += 2
                    notes.append(f"OI 4h {oi4:+.1f}% 平稳, 主力未撤(洗盘佐证)")
        if tt.get("available"):
            ttc = float(tt.get("change_24h_pct") or 0)
            if intent == "出货" and ttc <= -12:
                dist_pts += 1
                notes.append(f"大户持仓比24h {ttc:+.0f}% 减仓")
            elif intent != "出货" and ttc >= 12:
                shake_pts += 1
                notes.append(f"大户持仓比24h {ttc:+.0f}% 加仓")
        if not notes:
            return
        conf = int(item.get("intent_confidence") or 0)
        if intent == "出货":
            conf = max(10, min(95, conf + dist_pts * 9))
        else:
            if dist_pts >= 3:
                item["intent"] = "出货"
                conf = min(95, 40 + dist_pts * 12)
                notes.insert(0, "OI证据推翻判断: 洗盘→出货")
            else:
                conf = max(10, min(95, conf + shake_pts * 9 - dist_pts * 9))
        item["intent_confidence"] = conf
        item["intent_reasons"] = list(item.get("intent_reasons") or []) + notes

    def _smart_money_decision(self, signal: int, smart: dict | None) -> dict:
        cfg = self._smart_money_cfg()
        candidate = "LONG" if signal > 0 else "SHORT"
        if not cfg.get("enabled", True):
            return {"pass": True, "aligned": False, "score_delta": 0.0, "reason": "聪明钱过滤未启用"}
        smart = smart or {}
        quality = float(smart.get("data_quality", 0))
        score = float(smart.get("score", 0))
        if quality < 0.5:
            return {
                "pass": True, "aligned": False, "score_delta": 0.0,
                "reason": "聪明钱数据质量不足，沿用原策略结果",
            }

        smart_direction = smart.get("direction", "NEUTRAL")
        aligned = smart_direction == candidate and abs(score) >= float(cfg.get("min_alignment_score", 18))
        opposite = smart_direction not in ("NEUTRAL", candidate)
        block_opposite = opposite and abs(score) >= float(cfg.get("block_opposite_score", 32))
        require_confirmation = bool(cfg.get("require_confirmation", False))
        passed = not block_opposite and (aligned or not require_confirmation)
        max_weight = float(cfg.get("score_weight", 18))
        adjustment = round(min(max_weight, max_weight * abs(score) / 100), 1)
        score_delta = adjustment if aligned else -adjustment if opposite else 0.0
        if block_opposite:
            reason = f"聪明钱强反向 {score:+.1f}，否决 {candidate} 候选"
        elif require_confirmation and not aligned:
            reason = f"聪明钱未达到同向确认门槛，暂缓 {candidate}"
        elif aligned:
            reason = f"聪明钱同向 {score:+.1f}，候选加权 +{adjustment:.1f}"
        elif opposite:
            reason = f"聪明钱轻度反向 {score:+.1f}，候选降权 -{adjustment:.1f}"
        else:
            reason = "聪明钱方向中性，不改变候选"
        return {
            "pass": passed,
            "aligned": aligned,
            "opposite": opposite,
            "score_delta": score_delta,
            "reason": reason,
        }

    def _apply_smart_money_to_result(self, result: dict, smart: dict) -> dict:
        """在技术策略之后做加权/过滤；聪明钱本身不独立制造交易方向。"""
        base_score = float(result.get("score", 0))
        base_direction = 1 if base_score > 0 else -1 if base_score < 0 else 0
        result["base_score"] = round(base_score, 1)
        result["smart_money"] = smart
        if base_direction == 0:
            result["smart_money_decision"] = {
                "pass": True, "aligned": False, "score_delta": 0.0, "reason": "技术策略无方向",
            }
            return result

        decision = self._smart_money_decision(base_direction, smart)
        adjusted_score = base_score + base_direction * float(decision.get("score_delta", 0))
        adjusted_score = round(max(-100.0, min(100.0, adjusted_score)), 1)
        result["score"] = adjusted_score
        result["indicators"]["base_score"] = round(base_score, 1)
        result["indicators"]["score"] = adjusted_score
        result["indicators"]["smart_money_score"] = smart.get("score", 0)
        result["smart_money_decision"] = decision
        result["factors"].append(decision["reason"])
        result["reason"] = " | ".join(result["factors"])

        long_th = self.strategy.cfg.get("long_threshold", self.strategy.threshold)
        short_th = self.strategy.cfg.get("short_threshold", self.strategy.threshold)
        final_signal = 1 if adjusted_score >= long_th else -1 if adjusted_score <= -short_th else 0
        if not decision.get("pass", True):
            final_signal = 0
        result["signal"] = final_signal
        return result

    def _swing_trend(self, symbol: str) -> int:
        values = np.array(self.swing_cache.get(symbol, []))
        return detect_ema_ribbon(values) if len(values) >= 55 else 0

    def _htf_trend(self, symbol: str) -> int:
        """高TF(默认15m)缎带趋势, 与_swing_trend同口径"""
        values = np.array(self.htf_cache.get(symbol, []))
        return detect_ema_ribbon(values) if len(values) >= 55 else 0

    @staticmethod
    def _to_swing_ohlc(klines: list) -> dict:
        """swing周期K线转OHLC缓存。last_open_time用于识别swing收盘边界:
        每次拉取条数固定(120), 只有open_time推进才代表新K线收盘。"""
        return {
            "highs": [float(k[2]) for k in klines],
            "lows": [float(k[3]) for k in klines],
            "closes": [float(k[4]) for k in klines],
            "last_open_time": int(klines[-1][0]) if klines else 0,
        }

    def _long_track_cfg(self) -> dict:
        """长线赛道配置。独立defaults: position_management是浅层update,
        config里的long_track会整体替换而非合并, 缺键需在此兜底。"""
        defaults = {
            "enabled": True,
            "max_long_slots": 1,
            "tp1_close_pct": 30.0,
            "trail_atr_swing": 3.0,
            "reversal_confirm_bars": 2,
            "hard_stop_pct": 6.0,
        }
        defaults.update(self._position_management_cfg().get("long_track", {}) or {})
        return defaults

    def _swing_atr(self, symbol: str) -> float:
        """swing周期(默认1h)ATR。数据不足返回0, 调用方据此拒绝升级——
        宁可错过, 不能用错误的ATR去管一个宽止损仓位。"""
        ohlc = self.swing_ohlc_cache.get(symbol) or {}
        highs = ohlc.get("highs") or []
        lows = ohlc.get("lows") or []
        closes = ohlc.get("closes") or []
        if len(highs) < 15 or len(lows) < 15 or len(closes) < 15:
            return 0.0
        try:
            series = calc_atr(np.array(highs), np.array(lows), np.array(closes))
            value = float(series[-1])
        except Exception:
            return 0.0
        if value <= 0 or np.isnan(value):
            return 0.0
        return value

    def _swing_bar_advanced(self, symbol: str, st: dict) -> bool:
        """swing周期是否走出了新的一根(用于1h级别的破位计数)"""
        last = int((self.swing_ohlc_cache.get(symbol) or {}).get("last_open_time") or 0)
        if last <= 0:
            return False
        if int(st.get("last_swing_bar") or 0) == last:
            return False
        st["last_swing_bar"] = last
        return True

    def _long_slots_used(self, exclude: str | None = None) -> int:
        """长线赛道占用数。以交易所实际持仓为准: tp_state存在残留,
        直到仓位归零那一轮才清理。"""
        count = 0
        for sym, st in self.tp_state.items():
            if sym == exclude or (st or {}).get("track") != "swing_long":
                continue
            if sym in self.positions_cache:
                count += 1
        return count

    def _can_upgrade_to_long(self, symbol: str, side: str, st: dict) -> tuple[bool, str]:
        """TP1达成时判定能否升级长线赛道。纯同步无IO——
        _scaled_exit_action是同步函数, 交易所侧改单由调用方异步执行。"""
        cfg = self._long_track_cfg()
        if not cfg.get("enabled", True):
            return False, "长线赛道未启用"
        if st.get("track") == "swing_long":
            return False, "已在长线赛道"
        if st.get("mode") == "profit_bet":
            return False, "利润博弈单不升级"
        max_slots = max(1, int(cfg.get("max_long_slots", 1)))
        if self._long_slots_used(exclude=symbol) >= max_slots:
            return False, f"长线槽已满({max_slots})"
        if self._swing_atr(symbol) <= 0:
            return False, "swing ATR数据不足"
        want = 1 if side == "LONG" else -1
        if self._swing_trend(symbol) != want:
            return False, "swing趋势未同向"
        if self._htf_trend(symbol) != want:
            return False, "高TF趋势未同向"
        return True, "swing+高TF同向"

    async def _refresh_positions(self) -> list[dict]:
        """拉取持仓, 同步更新 position_symbols 与 positions_cache"""
        try:
            positions = await self.client.get_positions()
            open_pos = []
            for p in positions:
                amt = float(p["positionAmt"])
                if amt != 0:
                    open_pos.append({
                        "symbol": p["symbol"],
                        "side": "LONG" if amt > 0 else "SHORT",
                        "qty": abs(amt),
                        "entry_price": float(p["entryPrice"]),
                        "mark_price": float(p["markPrice"]),
                        "unrealized_pnl": float(p["unRealizedProfit"]),
                        "leverage": p["leverage"],
                        "liquidation_price": float(p.get("liquidationPrice", 0)),
                    })
            self.position_symbols = [p["symbol"] for p in open_pos]
            self.positions_cache = {p["symbol"]: p for p in open_pos}
            return open_pos
        except Exception as e:
            print(f"[Trader] 拉取持仓失败: {e}")
            return []

    def _seed_daily_risk_from_journal(self):
        """Restore bot-only day PnL so the daily loss gate survives service restarts."""
        try:
            records = journal.get_day_records()
            bot_records = [
                row for row in records
                if str(row.get("source", "local") or "local").lower() == "local"
                or str(row.get("source", "")).lower().startswith("local+")
            ]
            realized = sum(
                float(row.get("pnl", 0) or 0)
                for row in bot_records if row.get("type") == "close"
            )
            commission = sum(
                abs(float(row.get("commission", 0) or 0))
                for row in bot_records
            )
            self.risk.seed_daily_realized_pnl(realized - commission)
        except Exception as exc:
            print(f"[Trader] 恢复当日风控盈亏失败: {exc}")

    async def start(self):
        self.running = True
        await self.client.sync_time()
        # 并发设置杠杆
        async def _safe_set_leverage(sym):
            try:
                await self.client.set_leverage(sym, self.leverage)
            except Exception as e:
                print(f"[Trader] 设置{sym}杠杆失败(可能已设): {e}")

        await asyncio.gather(*[_safe_set_leverage(sym) for sym in self.symbols], return_exceptions=True)

        # 启动时检测持仓, 纳入监控列表
        open_pos = await self._refresh_positions()
        # 长线赛道是内存态, 必须从落盘恢复
        self._restore_long_track(open_pos)
        self._seed_daily_risk_from_journal()
        try:
            sync_result = await self.sync_trade_journal(force=True)
            print(
                f"[????] ????: {sync_result.get('orders', 0)}???, "
                f"??{sync_result.get('merge', {}).get('imported', 0)}?"
            )
        except Exception as exc:
            print(f"[????] ??????: {exc}")

        # 并发加载历史K线(当前TF + 高TF)
        watch_list = self.watch_symbols()
        await asyncio.gather(*[self._load_history(sym) for sym in watch_list], return_exceptions=True)

        # 并发初始评估: 立即填充指标和AI分析
        async def _safe_eval(sym):
            try:
                await self._evaluate(sym)
            except Exception as e:
                print(f"[Trader] 初始评估{sym}失败: {e}")

        await asyncio.gather(*[_safe_eval(sym) for sym in watch_list], return_exceptions=True)

        # 实时K线驱动: 币安对当前出口IP的WS只握手不下发数据, 改用高频REST轮询
        self._poll_task = asyncio.create_task(self._realtime_poll())
        # 定时刷新资金费率和高TF数据
        self._funding_task = asyncio.create_task(self._periodic_refresh())
        # 自动交易扫描: 定期从推荐列表发现新机会并开仓
        self._auto_scan_task = asyncio.create_task(self._auto_scan_loop())
        # 高频退出监控: 每3秒检查持仓止盈止损, 有利润及时回收
        self._exit_monitor_task = asyncio.create_task(self._exit_monitor_loop())
        # 高波动网格对冲(两头吃): 震荡市双向挂单吃差价
        self._grid_task = asyncio.create_task(self._grid_loop())
        # 仓位对账守护: 定期比对交易所真实持仓与系统记录, 识别幽灵仓位与漏单
        self._reconciliation_task = asyncio.create_task(self._reconciliation_loop())
        print(f"[Trader] 启动 | 监控: {self.watch_symbols()} | 周期: {self.interval} | 高TF: {self.htf_interval} | 实时:REST轮询 | 硬风控对账已启动")

    async def _load_history(self, symbol: str):
        """并发加载历史K线数据"""
        try:
            res_k, res_htf, res_swing = await asyncio.gather(
                self.client.get_klines(symbol, self.interval, 300),
                self.client.get_klines(symbol, self.htf_interval, 100),
                self.client.get_klines(symbol, self.swing_interval, 120),
                return_exceptions=True
            )
            if isinstance(res_k, list):
                self.klines_cache[symbol] = {
                    "closes": [float(k[4]) for k in res_k],
                    "highs": [float(k[2]) for k in res_k],
                    "lows": [float(k[3]) for k in res_k],
                    "volumes": [float(k[5]) for k in res_k],
                }
            if isinstance(res_htf, list):
                self.htf_cache[symbol] = [float(k[4]) for k in res_htf]
            if isinstance(res_swing, list):
                self.swing_cache[symbol] = [float(k[4]) for k in res_swing]
                self.swing_ohlc_cache[symbol] = self._to_swing_ohlc(res_swing)
        except Exception as e:
            print(f"[Trader] 加载{symbol}历史失败: {e}")

    async def _periodic_refresh(self):
        """每60秒刷新资金费率和高TF数据"""
        while self.running:
            try:
                for sym in self.watch_symbols():
                    # 资金费率
                    try:
                        fr = await self.client.get_funding_rate(sym)
                        if fr:
                            self.funding_rates[sym] = float(fr[0]["fundingRate"])
                    except Exception:
                        pass
                    # 高TF K线
                    try:
                        htf_klines = await self.client.get_klines(sym, self.htf_interval, 100)
                        self.htf_cache[sym] = [float(k[4]) for k in htf_klines]
                    except Exception:
                        pass
                    try:
                        swing_klines = await self.client.get_klines(sym, self.swing_interval, 120)
                        self.swing_cache[sym] = [float(k[4]) for k in swing_klines]
                        self.swing_ohlc_cache[sym] = self._to_swing_ohlc(swing_klines)
                    except Exception:
                        pass
            except Exception as e:
                print(f"[Trader] 定期刷新异常: {e}")
            await asyncio.sleep(60)

    def _to_kline(self, symbol: str, k: list, is_closed: bool) -> dict:
        """把REST K线行转成内部kline dict"""
        return {
            "symbol": symbol,
            "open_time": k[0],
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "close_time": k[6],
            "is_closed": is_closed,
        }

    async def _realtime_poll(self):
        """高频REST轮询驱动实时K线(币安WS对当前出口IP只握手不下发数据)"""
        while self.running:
            syms = self.watch_symbols()
            for sym in syms:
                # 运行时新出现的币种(如新持仓)先加载历史K线
                if sym not in self.klines_cache:
                    self.klines_cache[sym] = {"closes": [], "highs": [], "lows": [], "volumes": []}
                    await self._load_history(sym)
                    # 新币种立即评估, 不用等下一根K线收盘(否则指标/AI会空最多5分钟)
                    try:
                        await self._evaluate(sym)
                    except Exception as e:
                        print(f"[轮询] {sym} 初始评估失败: {e}")

            async def _poll_one(sym: str):
                klines = await self.client.get_klines(sym, self.interval, 2)
                if len(klines) < 2:
                    return
                closed_k, forming_k = klines[-2], klines[-1]
                # 检测到上一根K线收盘 -> 先喂收盘K线触发策略评估
                last_closed = self._last_closed_time.get(sym)
                if last_closed is not None and closed_k[0] > last_closed:
                    await self._on_kline(self._to_kline(sym, closed_k, True))
                self._last_closed_time[sym] = closed_k[0]
                # 喂当前形成中的K线(更新缓存+推送前端)
                await self._on_kline(self._to_kline(sym, forming_k, False))

            # 并发拉取所有监控币种, 一圈耗时=单次网络延迟而非币数×延迟
            results = await asyncio.gather(
                *(_poll_one(sym) for sym in syms), return_exceptions=True)
            for sym, res in zip(syms, results):
                if isinstance(res, Exception):
                    print(f"[轮询] {sym} 异常: {res}")
            await asyncio.sleep(1.5)

    async def _auto_scan_loop(self):
        """自动交易扫描: 定期从推荐列表发现新机会, 根据评分分配保守/激进仓位"""
        await asyncio.sleep(5)
        while self.running:
            try:
                if self.auto_trade:
                    await self._refresh_positions()
                    held = set(self.position_symbols)

                    # Mode A: 传统多因子策略初筛机会 (Gatekeeper 守门过滤)
                    rec = await self.get_recommendations(limit=8)
                    items = rec.get("items", [])
                    if items:
                        profit_bet_symbol = await self._maybe_execute_profit_bet(items, held)
                        if profit_bet_symbol:
                            await self._refresh_positions()
                            held = set(self.position_symbols)
                        for it in items[:4]:
                            sym = it["symbol"]
                            if sym in held:
                                continue
                            signal = 1 if it["side_en"] == "LONG" else -1
                            scan_threshold = self.strategy.cfg.get("scan_threshold", self.strategy.threshold)
                            if it["abs_score"] >= scan_threshold:
                                # 评分达到正式策略阈值, 策略直连执行(按评分分配保守/激进仓)
                                mode = "aggressive" if it["abs_score"] >= 50 else "conservative"
                                print(f"[自动扫描] {sym} 评分{it['score']} 热度{it['hot_score']} → {mode}仓")
                                await self._execute_signal(
                                    sym, signal, it["price"], mode=mode,
                                    candidate_context={
                                        "score": it.get("score", 0),
                                        "base_score": it.get("base_score", it.get("score", 0)),
                                        "factors": it.get("factors", []),
                                        "indicators": {"rsi": it.get("rsi"), "atr_pct": it.get("atr_pct")},
                                        "funding_rate": it.get("funding_rate"),
                                        "smart_money": it.get("smart_money"),
                                        "smart_money_decision": it.get("smart_money_decision"),
                                        "liquidity": it.get("liquidity"),
                                        "recommendation": it,
                                    },
                                )
                                await asyncio.sleep(1)

                    # Mode B: Jev 自主狙击猎手全盘扫描 (Autonomous Hunter Sweep)
                    # 仅在混合/自主模式 (typesafe_hybrid / typesafe_autonomous) 下启动；
                    # 在稳中求进的审查门禁模式 (typesafe_evaluator / typesafe_jev) 下严格静默，恪守“传统粗筛，Jev把关与一票否决”
                    is_hunter_mode = self.entry_decision_mode in ("typesafe_hybrid", "typesafe_autonomous", "hybrid")
                    hunter_enabled = getattr(self.typesafe_engine, "autonomous_enabled", False)
                    if is_hunter_mode and hunter_enabled:
                        await self._run_jev_autonomous_hunter_sweep(held=held)
            except Exception as e:
                print(f"[自动扫描] 异常: {e}")
            await asyncio.sleep(10)

    async def _run_jev_autonomous_hunter_sweep(self, held: set[str]):
        """Jev 自主狙击猎手全盘扫描 (Mode B: Autonomous Hunter)

        独立于传统指标初筛触发，Jev 主动调用 12 套 Obsidian 策略脑图与 7 维原子特征进行全盘独立扫描。
        仅当发现 S 级高置信度结构（例如威科夫 Spring、ICT 银弹、Volume Profile POC 强支撑）且违规率极低时，
        直接产出主动开仓决策（LONG / SHORT）。
        """
        now = time.time()
        # 扫描节流: 至少间隔 autonomous_hunter_interval 秒 (默认30秒)
        if now - getattr(self, "autonomous_hunter_last_sweep", 0.0) < getattr(self, "autonomous_hunter_interval", 30.0):
            return
        self.autonomous_hunter_last_sweep = now

        # 获取候选池: 监控列表 + 缓存活跃币 (去重且排除已持仓)
        candidate_symbols = [s for s in self.watch_symbols() if s not in held]
        rec_cache = getattr(self, "_recommend_cache", None)
        if rec_cache and isinstance(rec_cache, dict):
            cached_items = rec_cache.get("data", {}).get("items", []) if "data" in rec_cache else rec_cache.get("items", [])
            for item in cached_items:
                sym = item.get("symbol")
                if sym and sym not in held and sym not in candidate_symbols:
                    candidate_symbols.append(sym)

        if not candidate_symbols:
            return

        # 每次扫描最多检查 12 个代表性币种，避免过度占用 CPU/网络
        scan_batch = candidate_symbols[:12]
        for sym in scan_batch:
            if sym in held or not self.running or not self.auto_trade:
                continue
            try:
                price = 0.0
                tick = self.latest_klines.get(sym)
                if tick and tick.get("close"):
                    price = float(tick["close"])
                if price <= 0:
                    cached_closes = self.klines_cache.get(sym, {}).get("closes")
                    if cached_closes:
                        price = float(cached_closes[-1])
                if price <= 0:
                    continue

                recent_closes = (self.klines_cache.get(sym, {}).get("closes") or [])[-12:]
                fr = self.funding_rates.get(sym)
                latest_res = self.latest_result.get(sym, {})
                ind = latest_res.get("indicators", {})
                atr = float(ind.get("atr") or (price * 0.015))
                atr_pct = float(ind.get("atr_pct") or (atr / price * 100 if price else 1.5))
                sm = latest_res.get("smart_money")
                if not sm:
                    try:
                        sm = await self._smart_money_snapshot(sym)
                    except Exception:
                        sm = None

                candidate_ctx = {
                    "score": latest_res.get("score", 50),
                    "base_score": latest_res.get("base_score", 50),
                    "factors": latest_res.get("factors", []),
                    "indicators": {"rsi": ind.get("rsi", 50.0), "atr_pct": atr_pct, "atr": atr},
                    "funding_rate": fr,
                    "smart_money": sm,
                    "is_autonomous": True,
                }

                hunter_review = await self.typesafe_engine.scan_autonomous_hunter(
                    symbol=sym,
                    price=price,
                    recent_closes=recent_closes,
                    candidate_context=candidate_ctx,
                    funding_rate=fr,
                )

                if hunter_review.get("approved") and hunter_review.get("action") in ("LONG", "SHORT"):
                    act = hunter_review["action"]
                    sig = 1 if act == "LONG" else -1
                    pb_title = hunter_review.get("playbook", {}).get("strategy_title", "S-Tier Setup")
                    print(
                        f"[Jev 主动猎手锁定] 发现 S 级机构剧本机会: {sym} {act} | "
                        f"置信度={hunter_review.get('confidence'):.2f} | 策略={pb_title} | "
                        f"破位质量={hunter_review.get('breakout_quality', 0):.1f} | 违规风险={hunter_review.get('discipline_violation', 0):.2f}"
                    )
                    self.typesafe_reviews_log.append({
                        "timestamp": time.time(),
                        "symbol": sym,
                        "signal": sig,
                        "is_autonomous": True,
                        "review": hunter_review,
                    })
                    if len(self.typesafe_reviews_log) > 200:
                        self.typesafe_reviews_log = self.typesafe_reviews_log[-200:]

                    candidate_ctx["typesafe_review"] = hunter_review
                    candidate_ctx["recommendation"] = {"symbol": sym, "side_en": act, "price": price}

                    await self._execute_signal(
                        sym, sig, price, mode="aggressive",
                        candidate_context=candidate_ctx,
                    )
                    held.add(sym)
                    await asyncio.sleep(2)
            except Exception as hunter_err:
                pass

    async def _exit_monitor_loop(self):
        """高频退出监控: 每1秒用全市场最新价检查所有持仓的止盈止损, 不依赖K线收盘"""
        await asyncio.sleep(8)  # 启动后等历史数据加载
        while self.running:
            try:
                if not self.auto_trade:
                    await asyncio.sleep(1)
                    continue
                positions = await self.client.get_positions()
                held = [p for p in positions if float(p["positionAmt"]) != 0]
                if not held:
                    await asyncio.sleep(1)
                    continue
                # 批量拉一次全市场最新价, 覆盖所有持仓
                try:
                    price_map = {}
                    for item in await self.client.get_all_ticker_prices():
                        price_map[item.get("symbol", "")] = float(item.get("price", 0) or 0)
                except Exception as e:
                    print(f"[退出监控] 批量价格拉取失败: {e}")
                    price_map = {}
                for p in held:
                    sym = p["symbol"]
                    amt = float(p["positionAmt"])
                    side = "LONG" if amt > 0 else "SHORT"
                    entry_price = float(p["entryPrice"])
                    if sym in self.grid_state:
                        continue  # 网格仓位由网格循环自管理, 退出监控不干预
                    if sym not in self.tp_state:
                        continue  # 手动开的单脚本不管理(用户要求 2026-08-13)
                    # 优先全市场最新价, 其次实时K线, 最后markPrice
                    current_price = price_map.get(sym) or 0
                    if current_price <= 0:
                        tick = self.latest_klines.get(sym)
                        current_price = tick["close"] if tick else float(p.get("markPrice", 0))
                    if current_price <= 0:
                        continue
                    atr = float(self.latest_result.get(sym, {}).get("indicators", {}).get("atr") or 0)
                    tp_state_before = copy.deepcopy(self.tp_state.get(sym))
                    # 做空早止损: 可配置化（根据持仓管理参数动态判定是否提前止损空单）
                    st0 = self.tp_state.get(sym)
                    pm_cfg = self._position_management_cfg()
                    early_stop_enabled = bool(pm_cfg.get("short_early_stop_enabled", True))
                    early_stop_sec = float(pm_cfg.get("short_early_stop_minutes", 30)) * 60
                    early_stop_pct = float(pm_cfg.get("short_early_stop_pct", 2.5))
                    if side == "SHORT" and st0 and early_stop_enabled:
                        age = time.time() - float(st0.get("entry_time") or 0)
                        short_pnl_pct = ((entry_price - current_price) / entry_price * 100
                                         if entry_price > 0 else 0)
                        if 0 < age <= early_stop_sec and short_pnl_pct <= -early_stop_pct:
                            print(f"[exit monitor] {sym} 做空早止损: 开仓{age:.0f}s浮亏"
                                  f"{short_pnl_pct:+.2f}% <= -{early_stop_pct}%, 全平")
                            if not (await self._close_pos(
                                    sym, side, abs(amt), f"做空早止损·{int(early_stop_sec/60)}分钟内浮亏{early_stop_pct}%",
                                    entry_price=entry_price, exit_price=current_price,
                            )).get("ok", False):
                                if tp_state_before is not None:
                                    self.tp_state[sym] = tp_state_before
                            continue
                    action = self._scaled_exit_action(
                        sym, side, abs(amt), entry_price, current_price, atr,
                        swing_trend=self._swing_trend(sym), closed_candle=False,
                        leverage=float(p.get("leverage", 1) or 1),
                    )
                    if action:
                        close_qty, reason = action
                        print(f"[exit monitor] {sym} {reason} | price={current_price} entry={entry_price}")
                        if not (await self._close_pos(
                                sym, side, close_qty, reason,
                                entry_price=entry_price, exit_price=current_price,
                        )).get("ok", False):
                            # 失败只回滚交易所侧动作标记(pending_upgrade), 不回滚
                            # tp1/tp2/bf_fails等"已触发"标记: 回滚会让下轮循环重新
                            # 触发同一减仓动作, 残留微仓低于minQty时每秒死循环
                            # (BSBUSDT 2026-08-07 连续40+次"止盈1·减30%"重试)。
                            st_now = self.tp_state.get(sym)
                            if st_now is not None:
                                st_now["pending_upgrade"] = bool(
                                    (tp_state_before or {}).get("pending_upgrade"))
                        else:
                            await self._apply_pending_upgrade(sym, side, entry_price)
                    else:
                        # 趋势反转实时检查: 原逻辑只在15m收盘时查一次(最多滞后15分钟),
                        # 这里每秒用实时价替换最后一根收盘K线再判, 反转发生立即感知
                        st = self.tp_state.get(sym)
                        entry_time = st.get("entry_time", 0) if st else 0
                        if entry_time and (time.time() - entry_time) < 60:
                            continue  # 开仓保护期
                        cache = self.klines_cache.get(sym)
                        if not cache or len(cache["closes"]) < 60:
                            continue
                        closes_live = np.array(cache["closes"])
                        closes_live[-1] = current_price  # 实时价参与指标判断
                        htf_closes = np.array(self.htf_cache.get(sym, []))
                        swing_closes = np.array(self.swing_cache.get(sym, []))
                        exit_result = self.strategy.check_exit(
                            closes_live, side, entry_price,
                            np.array(cache["highs"]), np.array(cache["lows"]),
                            htf_closes=htf_closes if len(htf_closes) >= 55 else None,
                            swing_closes=swing_closes if len(swing_closes) >= 55 else None,
                            volumes=np.array(cache["volumes"]),
                        )
                        on_long_track = (st or {}).get("track") == "swing_long"
                        if exit_result["exit"]:
                            trend_now = self._swing_trend(sym)
                            swing_against = ((side == "LONG" and trend_now < 0)
                                             or (side == "SHORT" and trend_now > 0))
                            if on_long_track and not swing_against:
                                print(f"[长线赛道] {sym} 忽略退出信号"
                                      f"({exit_result['reason'][:40]}), {self.swing_interval}趋势未反向")
                            else:
                                tp_state_before2 = copy.deepcopy(self.tp_state.get(sym))
                                self.tp_state.pop(sym, None)
                                print(f"[exit monitor] {sym} 实时趋势反转清仓: "
                                      f"{exit_result['reason'][:60]} | price={current_price}")
                                if not (await self._close_pos(
                                        sym, side, abs(amt), exit_result["reason"],
                                        entry_price=entry_price, exit_price=current_price,
                                )).get("ok", False):
                                    if tp_state_before2 is not None:
                                        self.tp_state[sym] = tp_state_before2
                        elif (exit_result.get("exit_score", 0) >= 3
                              and not on_long_track):
                            if (st or {}).get("halved"):
                                # 第二次反转预警: 方向确认走坏, 剩余仓位全平,
                                # 不再"减半观察"拖到硬止损(PROMUSDT 2026-08-14 -1U教训)
                                tp_state_before2 = copy.deepcopy(self.tp_state.get(sym))
                                self.tp_state.pop(sym, None)
                                print(f"[exit monitor] {sym} 二次反转预警全平: "
                                      f"{exit_result['reason'][:60]} | price={current_price}")
                                if not (await self._close_pos(
                                        sym, side, abs(amt), exit_result["reason"],
                                        entry_price=entry_price, exit_price=current_price,
                                )).get("ok", False):
                                    if tp_state_before2 is not None:
                                        self.tp_state[sym] = tp_state_before2
                            else:
                                halve_qty = round(abs(amt) * 0.5, 8)
                                if halve_qty > 0:
                                    ok = (await self._close_pos(
                                        sym, side, halve_qty,
                                        f"反转预警·减仓50%观察(exit_score={exit_result['exit_score']})",
                                        entry_price=entry_price, exit_price=current_price,
                                    )).get("ok", False)
                                    if ok and st:
                                        st["halved"] = True
                                        print(f"[减仓] {sym} {side} 实时反转预警, 减半{halve_qty}观察")

            except Exception as e:
                print(f"[退出监控] 异常: {e}")
            await asyncio.sleep(1)

    async def stop(self):
        self.running = False
        if self._ws_task:
            self._ws_task.cancel()
        if self._poll_task:
            self._poll_task.cancel()
        if self._funding_task:
            self._funding_task.cancel()
        if getattr(self, "_auto_scan_task", None):
            self._auto_scan_task.cancel()
        if getattr(self, "_exit_monitor_task", None):
            self._exit_monitor_task.cancel()
        if getattr(self, "_grid_task", None):
            self._grid_task.cancel()
        if getattr(self, "_reconciliation_task", None):
            self._reconciliation_task.cancel()
        await self.client.close()
        print("[Trader] 已停止")

    async def _on_kline(self, kline: dict):
        """WebSocket/REST 轮询K线回调"""
        self.last_market_data_ts = time.time()
        if self.risk.circuit_breaker_active and "行情" in self.risk.circuit_breaker_reason:
            self.risk.reset_circuit_breaker()
        sym = kline["symbol"]
        # 保存最新tick供前端实时渲染
        self.latest_klines[sym] = kline
        if sym not in self.klines_cache:
            self.klines_cache[sym] = {"closes": [], "highs": [], "lows": [], "volumes": []}
        cache = self.klines_cache[sym]

        if kline["is_closed"]:
            cache["closes"].append(kline["close"])
            cache["highs"].append(kline["high"])
            cache["lows"].append(kline["low"])
            cache["volumes"].append(kline["volume"])
            # 保持300根
            for key in cache:
                if len(cache[key]) > 300:
                    cache[key].pop(0)
            await self._evaluate(sym)
        else:
            if cache["closes"]:
                cache["closes"][-1] = kline["close"]
                cache["highs"][-1] = max(cache["highs"][-1], kline["high"])
                cache["lows"][-1] = min(cache["lows"][-1], kline["low"])

    async def _evaluate(self, symbol: str):
        """多因子策略评估"""
        cache = self.klines_cache.get(symbol)
        if not cache or len(cache["closes"]) < 60:
            return

        closes = np.array(cache["closes"])
        highs = np.array(cache["highs"])
        lows = np.array(cache["lows"])
        volumes = np.array(cache["volumes"])
        htf_closes = np.array(self.htf_cache.get(symbol, []))
        funding_rate = self.funding_rates.get(symbol)

        result = self.strategy.evaluate(
            closes, highs, lows, volumes,
            funding_rate=funding_rate,
            htf_closes=htf_closes if len(htf_closes) >= 55 else None
        )
        try:
            smart = await self._smart_money_snapshot(
                symbol, closes=closes, volumes=volumes, funding_rate=funding_rate)
            result = self._apply_smart_money_to_result(result, smart)
        except Exception as e:
            print(f"[聪明钱] {symbol} 快照失败: {e}")
        self.latest_indicators[symbol] = result["indicators"]
        self.latest_result[symbol] = result

        # AI分析(每根K线收盘后更新)
        try:
            self.analysis_cache[symbol] = self.analyst.analyze(
                closes, highs, lows, volumes,
                funding_rate=funding_rate,
                htf_closes=htf_closes if len(htf_closes) >= 55 else None,
                position=self.positions_cache.get(symbol),
                position_management=self._position_management_cfg()
            )
        except Exception as e:
            print(f"[AI分析] {symbol} 异常: {e}")

        if result["signal"] != 0:
            signal_record = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "symbol": symbol,
                "signal": "开多" if result["signal"] == 1 else "开空",
                "price": result["indicators"]["price"],
                "score": result["score"],
                "reason": result["reason"],
                "factors": result["factors"],
            }
            self.signals_log.append(signal_record)
            if len(self.signals_log) > 200:
                self.signals_log.pop(0)
            print(f"[信号] {symbol} {signal_record['signal']} | 评分:{result['score']} | {result['reason']}")

            if self.auto_trade:
                await self._execute_signal(
                    symbol, result["signal"], result["indicators"]["price"],
                    candidate_context=result,
                )

        # 检查持仓是否需要平仓
        await self._check_exits(symbol, closes, highs, lows, volumes)

    async def _check_exits(self, symbol: str, closes, highs, lows, volumes=None):
        """检查现有持仓是否触发平仓条件(自动交易模式)"""
        if not self.auto_trade:
            return
        if symbol in self.grid_state:
            return  # 网格仓位由网格循环自管理, 信号平仓逻辑不干预
        if symbol not in self.tp_state:
            return  # 手动开的单脚本不管理(用户要求 2026-08-13)
        try:
            positions = await self.client.get_positions()
            for p in positions:
                if p["symbol"] != symbol:
                    continue
                amt = float(p["positionAmt"])
                if amt == 0:
                    # 仓位确实平了才清状态。get_positions可能瞬时返回0(网络/
                    # 快照竞态), 误清会让_scaled_exit_action用当前持仓重建
                    # tp_state, orig_qty/tp1/tp2/bf_fails全部丢失, 已触发的
                    # 止盈减仓按错误比例重算(BSBUSDT 2026-08-07 减仓8刀失真)。
                    # 二次确认仍为0才pop, 瞬时误判不触发。
                    try:
                        recheck = await self.client.get_positions()
                        still_zero = all(
                            q["symbol"] != symbol or float(q["positionAmt"]) == 0
                            for q in recheck
                        )
                    except Exception:
                        still_zero = False
                    if still_zero:
                        self.tp_state.pop(symbol, None)  # 仓位已平, 清理状态
                    continue
                side = "LONG" if amt > 0 else "SHORT"
                entry_price = float(p["entryPrice"])
                current_price = float(closes[-1])
                atr = float(self.latest_result.get(symbol, {}).get("indicators", {}).get("atr") or 0)

                # 分批止盈 + ATR止损(机械退出主逻辑)
                tp_state_before = copy.deepcopy(self.tp_state.get(symbol))
                action = self._scaled_exit_action(
                    symbol, side, abs(amt), entry_price, current_price, atr,
                    swing_trend=self._swing_trend(symbol), closed_candle=True,
                    leverage=float(p.get("leverage", 1) or 1),
                    bar_high=float(highs[-1]), bar_low=float(lows[-1]),
                )
                if action:
                    close_qty, reason = action
                    if not (await self._close_pos(
                            symbol, side, close_qty, reason,
                            entry_price=entry_price, exit_price=current_price,
                    )).get("ok", False):
                        # 失败只回滚pending_upgrade, 不回滚已触发标记(防死循环, 见退出监控)
                        st_now = self.tp_state.get(symbol)
                        if st_now is not None:
                            st_now["pending_upgrade"] = bool(
                                (tp_state_before or {}).get("pending_upgrade"))
                    else:
                        await self._apply_pending_upgrade(symbol, side, entry_price)
                    continue

                # 顺势加仓: 浮盈足够且趋势仍对齐时加50%仓位
                if await self._maybe_pyramid(symbol, side, abs(amt), entry_price, current_price, atr, p):
                    continue  # 加仓完成, 本轮不再做趋势反转判断

                # 手动打法: 保本止损 + 回调加仓(回测A/B通过 2026-08-13)
                ap = self.strategy.cfg.get("add_on_pullback") or {}
                if ap.get("enabled") and self.tp_state.get(symbol):
                    st = self.tp_state[symbol]
                    is_long = side == "LONG"
                    pnl_pct = ((current_price - entry_price) / entry_price * 100
                               if is_long else (entry_price - current_price) / entry_price * 100)
                    peak = float(st.get("peak_price") or entry_price)
                    peak_pnl = ((peak - entry_price) / entry_price * 100
                                if is_long else (entry_price - peak) / entry_price * 100)
                    # 保本激活: 峰值浮盈达标后持久标记(加仓摊高成本也不关闭)
                    if peak_pnl >= float(ap.get("breakeven_pct", 2.0)):
                        st["breakeven_on"] = True
                    # 保本执行: 价格回到持仓均价即全平, 不亏本金
                    if st.get("breakeven_on") and (
                            (is_long and current_price <= entry_price)
                            or (not is_long and current_price >= entry_price)):
                        close_qty = abs(amt)
                        if (await self._close_pos(
                                symbol, side, close_qty, "保本止损",
                                entry_price=entry_price, exit_price=current_price,
                        )).get("ok", False):
                            print(f"[手动打法] {symbol} {side} 保本止损全平 "
                                  f"@~{current_price:.6f}")
                            continue
                    # 回调加仓: 峰值回撤达标且仍浮盈(浮亏绝不摊平)
                    add_count = int(st.get("add_count", 0))
                    if (add_count < int(ap.get("max_adds", 3)) and pnl_pct > 0
                            and peak_pnl - pnl_pct >= float(ap.get("pullback_pct", 2.5))):
                        if await self._exec_pullback_add(
                                symbol, side, entry_price, current_price, atr, p, ap):
                            continue  # 加仓完成, 本轮不再做趋势反转判断

                # 策略趋势平仓(辅助: 趋势反转时全平, 开仓1分钟内不触发防入场噪音)
                st = self.tp_state.get(symbol)
                entry_time = st.get("entry_time", 0) if st else 0
                if entry_time and (time.time() - entry_time) < 60:
                    continue  # 开仓1分钟内不做趋势反转平仓
                htf_closes = np.array(self.htf_cache.get(symbol, []))
                swing_closes = np.array(self.swing_cache.get(symbol, []))
                exit_result = self.strategy.check_exit(
                    closes, side, entry_price, highs, lows,
                    htf_closes=htf_closes if len(htf_closes) >= 55 else None,
                    swing_closes=swing_closes if len(swing_closes) >= 55 else None,
                    volumes=volumes,
                )
                on_long_track = (st or {}).get("track") == "swing_long"
                if exit_result["exit"]:
                    trend_now = self._swing_trend(symbol)
                    swing_against = ((side == "LONG" and trend_now < 0)
                                     or (side == "SHORT" and trend_now > 0))
                    if on_long_track and not swing_against:
                        # 长线仓: 操作周期(5m)视角的反转不足以平掉长线, 必须swing
                        # 也反向。否则趋势中的正常回调会把长线仓提前砍掉。
                        print(f"[长线赛道] {symbol} 忽略退出信号"
                              f"({exit_result['reason']}), {self.swing_interval}趋势未反向")
                    else:
                        tp_state_before = copy.deepcopy(self.tp_state.get(symbol))
                        self.tp_state.pop(symbol, None)
                        if not (await self._close_pos(
                                symbol, side, abs(amt), exit_result["reason"],
                                entry_price=entry_price, exit_price=current_price,
                        )).get("ok", False):
                            if tp_state_before is not None:
                                self.tp_state[symbol] = tp_state_before
                # 减仓观察: exit_score到预警线但未触发全平, 先减半等一等
                # 放宽: 任意exit_score≥3即减半观察(不限于主力/反向结构),
                # 避免反转初期因条件过严不减仓而挨到止损
                # 长线仓跳过: 减仓已在tp1的30%完成, 不再二次削减
                # 第二次预警: 剩余仓位全平(PROMUSDT 2026-08-14 -1U教训)
                elif (exit_result.get("exit_score", 0) >= 3
                      and not on_long_track):
                    if (st or {}).get("halved"):
                        tp_state_before2 = copy.deepcopy(self.tp_state.get(symbol))
                        self.tp_state.pop(symbol, None)
                        print(f"[减仓] {symbol} {side} 二次反转预警全平: "
                              f"{exit_result['reason'][:60]}")
                        if not (await self._close_pos(
                                symbol, side, abs(amt), exit_result["reason"],
                                entry_price=entry_price, exit_price=current_price,
                        )).get("ok", False):
                            if tp_state_before2 is not None:
                                self.tp_state[symbol] = tp_state_before2
                    else:
                        halve_qty = round(abs(amt) * 0.5, 8)
                        if halve_qty > 0:
                            ok = (await self._close_pos(
                                symbol, side, halve_qty,
                                f"反转预警·减仓50%观察(exit_score={exit_result['exit_score']})",
                                entry_price=entry_price, exit_price=current_price,
                            )).get("ok", False)
                            if ok and st:
                                st["halved"] = True
                                print(f"[减仓] {symbol} {side} 反转预警, 减半{halve_qty}观察")


        except Exception as e:
            print(f"[平仓检查] {symbol}: {e}")

    def _bot_managed_position_count(self, open_positions: list) -> int:
        """脚本自己管理的仓位数量: tp_state(信号仓) + grid_state(网格仓)。
        手动开的单不计入, 用户有手动单时脚本仍可开满自己的3仓(总持仓4)。"""
        managed = 0
        for p in open_positions:
            sym = p.get("symbol", "")
            if sym in self.tp_state or sym in self.grid_state:
                managed += 1
        return managed

    async def _maybe_pyramid(self, symbol: str, side: str, qty: float,
                             entry_price: float, current_price: float, atr: float,
                             pos: dict) -> bool:
        """顺势加仓: 浮盈≥1ATR且趋势未反转时加50%仓位, 止损上移至保本"""
        st = self.tp_state.get(symbol)
        if not st or st.get("pyramided"):
            return False
        if atr <= 0:
            return False
        if time.time() - float(st.get("entry_time") or 0) < 300:
            return False  # 保护期内不加仓
        adv = (current_price - entry_price) if side == "LONG" else (entry_price - current_price)
        pyramid_mult = float(self._position_management_cfg().get("pyramid_atr_mult", 1.0))
        if adv < atr * pyramid_mult:
            return False
        # 主力意图反向不加: 多单遇出货/空单遇吸筹洗盘
        ind = self.latest_result.get(symbol, {}).get("indicators", {})
        intent = ind.get("main_intent")
        if (side == "LONG" and intent == "出货") or (side == "SHORT" and intent in ("吸筹", "洗盘")):
            return False
        # 风控与资金校验
        try:
            account = await self.client.get_account()
            balance = float(account["totalWalletBalance"])
            available = float(account.get("availableBalance") or 0)
            positions = await self.client.get_positions()
            open_positions = [x for x in positions if float(x["positionAmt"]) != 0]
            can_open, reason = self.risk.can_open(
                self._bot_managed_position_count(open_positions), balance=balance)
            if not can_open:
                return False
            risk_cfg = self.cfg.get("risk", {})
            max_tot_mult = float(risk_cfg.get("max_total_notional_multiple", 8))
            open_notional = sum(
                abs(float(x["positionAmt"])) * float(x.get("markPrice") or x.get("entryPrice") or 0)
                for x in open_positions)
            add_qty_raw = qty * 0.5
            add_notional = add_qty_raw * current_price
            if open_notional + add_notional > balance * max_tot_mult:
                return False
            lev = float(pos.get("leverage") or 1)
            required_margin = add_notional / max(lev, 1)
            if required_margin > available * 0.9:
                return False
            add_qty = await self.client.normalize_quantity(symbol, add_qty_raw)
            if add_qty <= 0:
                return False
            if side == "LONG":
                order = await self.client.market_open_long(symbol, add_qty)
            else:
                order = await self.client.market_open_short(symbol, add_qty)
            execution = self._order_execution(order)
            if execution["executed_qty"] <= 0:
                return False
            st["pyramided"] = True
            st["orig_qty"] = float(st.get("orig_qty") or qty) + execution["executed_qty"]
            fill_price = execution["avg_price"] or current_price
            journal.record_open(symbol, side, execution["executed_qty"], fill_price,
                                int(lev), round(add_notional / max(lev, 1), 2), 0)
            # 加仓后止损上移至保本+微利, 交易所侧重置保护单
            be = entry_price * 1.001 if side == "LONG" else entry_price * 0.999
            tp = current_price + atr * 2.5 if side == "LONG" else current_price - atr * 2.5
            await self._place_protective_orders(symbol, side, be, tp)
            print(f"[加仓] {symbol} {side} +{execution['executed_qty']:.4f} @{fill_price} "
                  f"浮盈{adv/atr:.1f}ATR, 止损移至保本{be:.4f}")
            self._record_execution_event(
                "OPEN", "success", symbol, side, "顺势加仓",
                f"浮盈{adv/atr:.1f}ATR加仓50%, 止损上移保本",
                executed_qty=execution["executed_qty"], avg_price=fill_price,
                original_entry=entry_price, breakeven_stop=be,
            )
            return True
        except Exception as e:
            print(f"[加仓] {symbol} 失败: {e}")
            return False

    async def _exec_pullback_add(self, symbol: str, side: str, entry_price: float,
                                 current_price: float, atr: float, pos: dict,
                                 ap: dict) -> bool:
        """手动打法回调加仓: 加 add_ratio×首笔仓位, 加仓后挂保本保护单"""
        st = self.tp_state.get(symbol)
        if not st:
            return False
        try:
            account = await self.client.get_account()
            balance = float(account["totalWalletBalance"])
            available = float(account.get("availableBalance") or 0)
            positions = await self.client.get_positions()
            open_positions = [x for x in positions if float(x["positionAmt"]) != 0]
            can_open, reason = self.risk.can_open(
                self._bot_managed_position_count(open_positions), balance=balance)
            if not can_open:
                return False
            risk_cfg = self.cfg.get("risk", {})
            max_tot_mult = float(risk_cfg.get("max_total_notional_multiple", 8))
            open_notional = sum(
                abs(float(x["positionAmt"])) * float(x.get("markPrice") or x.get("entryPrice") or 0)
                for x in open_positions)
            base_qty = float(st.get("first_qty") or st.get("orig_qty") or 0)
            add_qty_raw = base_qty * float(ap.get("add_ratio", 0.5))
            add_notional = add_qty_raw * current_price
            if open_notional + add_notional > balance * max_tot_mult:
                return False
            lev = float(pos.get("leverage") or 1)
            if add_notional / max(lev, 1) > available * 0.9:
                return False
            add_qty = await self.client.normalize_quantity(symbol, add_qty_raw)
            if add_qty <= 0:
                return False
            if side == "LONG":
                order = await self.client.market_open_long(symbol, add_qty)
            else:
                order = await self.client.market_open_short(symbol, add_qty)
            execution = self._order_execution(order)
            if execution["executed_qty"] <= 0:
                return False
            st["add_count"] = int(st.get("add_count", 0)) + 1
            st["orig_qty"] = float(st.get("orig_qty") or 0) + execution["executed_qty"]
            fill_price = execution["avg_price"] or current_price
            journal.record_open(symbol, side, execution["executed_qty"], fill_price,
                                int(lev), round(add_notional / max(lev, 1), 2), 0)
            # 保本保护单: 回测中保本线=加权均价, 挂单给微利缓冲
            be = entry_price * 1.001 if side == "LONG" else entry_price * 0.999
            tp = current_price + atr * 2.5 if side == "LONG" else current_price - atr * 2.5
            await self._place_protective_orders(symbol, side, be, tp)
            print(f"[手动打法] {symbol} {side} 回调加仓{st['add_count']}/3 "
                  f"+{execution['executed_qty']:.4f} @{fill_price}")
            self._record_execution_event(
                "OPEN", "success", symbol, side, "回调加仓",
                f"第{st['add_count']}次加仓, 峰值回撤达标, 止损上移保本",
                executed_qty=execution["executed_qty"], avg_price=fill_price,
                original_entry=entry_price, breakeven_stop=be,
            )
            return True
        except Exception as e:
            print(f"[手动打法] {symbol} 回调加仓失败: {e}")
            return False

    def _legacy_scaled_exit_action(self, symbol: str, side: str, qty: float,
                            entry_price: float, current_price: float, atr: float):
        """三档分批止盈+ATR止损, 根据仓位模式使用不同参数。
        保守仓: 止损1.5ATR, TP1=2ATR/TP2=3.5ATR/TP3=6ATR (稳健持有)
        激进仓: 止损2ATR, TP1=3ATR/TP2=5ATR/TP3=8ATR (搏大波段)
        开仓后3分钟为保护期, 不触发止损(避免入场噪音震出)。"""
        if entry_price <= 0 or current_price <= 0:
            return None

        # 读取仓位模式
        st = self.tp_state.get(symbol)
        mode = st.get("mode", "conservative") if st else "conservative"

        if mode == "aggressive":
            sl_mult, tp1_mult, tp2_mult, tp3_mult = 2.0, 3.0, 5.0, 8.0
        else:
            sl_mult, tp1_mult, tp2_mult, tp3_mult = 1.5, 2.0, 3.5, 6.0

        # 保护期: 开仓后180秒内不触发止损, 给持仓呼吸空间
        entry_time = st.get("entry_time", 0) if st else 0
        in_grace = (time.time() - entry_time) < 180 if entry_time else False

        if side == "LONG":
            pnl_pct = (current_price - entry_price) / entry_price * 100
            stop_hit = atr > 0 and current_price <= entry_price - atr * sl_mult
        else:
            pnl_pct = (entry_price - current_price) / entry_price * 100
            stop_hit = atr > 0 and current_price >= entry_price + atr * sl_mult

        # 止损: 全部平仓(保护期内跳过)
        if stop_hit and not in_grace:
            self.tp_state.pop(symbol, None)
            return (qty, f"ATR止损触发({sl_mult}倍ATR)")

        # 维护分批止盈状态(记录原始仓位用于按比例减仓)
        if st is None or st.get("side") != side:
            st = {"side": side, "orig_qty": qty, "tp1": False, "tp2": False, "tp3": False,
                  "mode": mode, "entry_time": time.time()}
            self.tp_state[symbol] = st
        orig = st["orig_qty"] or qty
        atr_pct = atr / entry_price * 100 if atr > 0 else 0
        tp1_pct = atr_pct * tp1_mult
        tp2_pct = atr_pct * tp2_mult
        tp3_pct = atr_pct * tp3_mult

        if not st["tp1"] and tp1_pct > 0 and pnl_pct >= tp1_pct:
            st["tp1"] = True
            close_qty = min(round(orig * 0.3, 8), qty)
            return (close_qty, f"分批止盈1·减30%(+{pnl_pct:.1f}%)")
        if st["tp1"] and not st["tp2"] and tp2_pct > 0 and pnl_pct >= tp2_pct:
            st["tp2"] = True
            close_qty = min(round(orig * 0.3, 8), qty)
            return (close_qty, f"分批止盈2·减30%(+{pnl_pct:.1f}%)")
        if st["tp2"] and not st["tp3"] and tp3_pct > 0 and pnl_pct >= tp3_pct:
            st["tp3"] = True
            close_qty = qty  # 全平剩余40%
            return (close_qty, f"分批止盈3·全平(+{pnl_pct:.1f}%)")
        return None

    def _medium_scaled_exit_action(self, symbol: str, side: str, qty: float,
                            entry_price: float, current_price: float, atr: float):
        """Three-stage profit management: partial exits, then a trailing remainder."""
        if entry_price <= 0 or current_price <= 0:
            return None

        pm = self._position_management_cfg()
        st = self.tp_state.get(symbol)
        mode = st.get("mode", "conservative") if st else "conservative"
        if mode == "aggressive":
            sl_mult, tp1_mult, tp2_mult = 2.0, 3.0, 5.0
        else:
            sl_mult, tp1_mult, tp2_mult = 1.5, 2.0, 3.5

        if st is None or st.get("side") != side:
            st = {
                "side": side,
                "orig_qty": qty,
                "tp1": False,
                "tp2": False,
                "tp3": False,
                "mode": mode,
                "entry_time": 0,
                "peak_price": current_price,
            }
            self.tp_state[symbol] = st

        if side == "LONG":
            st["peak_price"] = max(float(st.get("peak_price", current_price)), current_price)
            pnl_pct = (current_price - entry_price) / entry_price * 100
            initial_stop = entry_price - atr * sl_mult if atr > 0 else 0
            protected_stop = entry_price + atr * float(pm["lock_profit_atr"]) if atr > 0 else 0
            trailing_stop = st["peak_price"] - atr * float(pm["trailing_atr"]) if atr > 0 else 0
            stop_price = max(initial_stop, protected_stop, trailing_stop) if st["tp1"] else initial_stop
            stop_hit = atr > 0 and current_price <= stop_price
        else:
            st["peak_price"] = min(float(st.get("peak_price", current_price)), current_price)
            pnl_pct = (entry_price - current_price) / entry_price * 100
            initial_stop = entry_price + atr * sl_mult if atr > 0 else 0
            protected_stop = entry_price - atr * float(pm["lock_profit_atr"]) if atr > 0 else 0
            trailing_stop = st["peak_price"] + atr * float(pm["trailing_atr"]) if atr > 0 else 0
            stop_price = min(initial_stop, protected_stop, trailing_stop) if st["tp1"] else initial_stop
            stop_hit = atr > 0 and current_price >= stop_price

        entry_time = st.get("entry_time", 0)
        in_grace = (time.time() - entry_time) < 180 if entry_time else False
        if stop_hit and not in_grace:
            self.tp_state.pop(symbol, None)
            label = "跟踪止损" if st["tp1"] else f"ATR止损({sl_mult:g}倍)"
            return qty, f"{label}触发({pnl_pct:+.2f}%)"

        orig = float(st.get("orig_qty") or qty)
        partial = max(0.1, min(0.5, float(pm["partial_close_pct"]) / 100))
        tp1_pct = atr / entry_price * 100 * tp1_mult if atr > 0 else 0
        tp2_pct = atr / entry_price * 100 * tp2_mult if atr > 0 else 0

        if not st["tp1"] and tp1_pct > 0 and pnl_pct >= tp1_pct:
            st["tp1"] = True
            return min(round(orig * partial, 8), qty), f"分批止盈1·减{partial * 100:.0f}%(+{pnl_pct:.2f}%)"
        if st["tp1"] and not st["tp2"] and tp2_pct > 0 and pnl_pct >= tp2_pct:
            st["tp2"] = True
            return min(round(orig * partial, 8), qty), f"分批止盈2·减{partial * 100:.0f}%(+{pnl_pct:.2f}%)"

        # The last stage is deliberately trailing; there is no fixed TP3 full exit.
        return None

    def _scaled_exit_action(self, symbol: str, side: str, qty: float,
                            entry_price: float, current_price: float, atr: float,
                            swing_trend: int = 0, closed_candle: bool = False,
                            leverage: float = 1, bar_high: float = 0,
                            bar_low: float = 0):
        """Swing mode: tolerate normal pullbacks and exit on structural failure.
        bar_high/bar_low: 收盘K线的高低点, 仅收盘确认时传入(突破未果信号用)"""
        if entry_price <= 0 or current_price <= 0:
            return None

        pm = self._position_management_cfg()
        if pm.get("holding_mode", "swing") != "swing":
            return self._medium_scaled_exit_action(
                symbol, side, qty, entry_price, current_price, atr)

        st = self.tp_state.get(symbol)
        mode = st.get("mode", "conservative") if st else "conservative"
        if st is None or st.get("side") != side:
            st = {
                "side": side,
                "orig_qty": qty,
                "tp1": False,
                "tp2": False,
                "tp3": False,
                "mode": mode,
                "entry_time": 0,
                "peak_price": current_price,
                "stop_breach_count": 0,
                "track": "scalp",
                "pending_upgrade": False,
                "track_since": 0.0,
                "long_breach_count": 0,
                "last_swing_bar": 0,
                "bf_peak": current_price,
                "bf_trough": current_price,
                "bf_fails": 0,
                "bf_failed_now": False,
                "add_count": 0, "breakeven_on": False,
                "first_qty": qty,
            }
            self.tp_state[symbol] = st

        long_cfg = self._long_track_cfg()
        on_long_track = st.get("track") == "swing_long"

        is_long = side == "LONG"
        if is_long:
            st["peak_price"] = max(float(st.get("peak_price", current_price)), current_price)
            pnl_pct = (current_price - entry_price) / entry_price * 100
        else:
            st["peak_price"] = min(float(st.get("peak_price", current_price)), current_price)
            pnl_pct = (entry_price - current_price) / entry_price * 100

        if on_long_track:
            configured_hard_pct = max(0.5, float(long_cfg.get("hard_stop_pct", 6.0)))
        else:
            configured_hard_pct = max(0.5, float(pm["hard_stop_pct"]))
            # 低分单收紧硬止损: |score|在40~55之间用3.5%(PROMUSDT 2026-08-14
            # -50分单6.24%止损亏1U的教训), 高分单(>=55)保持配置的6%
            entry_score = abs(float(st.get("score", 0) or 0))
            if 0 < entry_score < 55:
                configured_hard_pct = min(
                    configured_hard_pct,
                    float(pm.get("low_score_hard_stop_pct", 3.5)))
        leverage_cap_pct = float(pm.get("max_margin_loss_pct", 45)) / max(1.0, leverage)
        effective_hard_pct = min(configured_hard_pct, leverage_cap_pct)
        hard_dist = entry_price * effective_hard_pct / 100
        min_dist = entry_price * max(0.1, float(pm["min_stop_pct"])) / 100
        atr_dist = atr * max(1.0, float(pm["initial_stop_atr"])) if atr > 0 else 0
        soft_dist = max(min_dist, atr_dist)
        soft_dist = min(soft_dist, hard_dist * 0.85)

        hard_stop = entry_price - hard_dist if is_long else entry_price + hard_dist
        soft_stop = entry_price - soft_dist if is_long else entry_price + soft_dist
        hard_hit = current_price <= hard_stop if is_long else current_price >= hard_stop
        soft_hit = current_price <= soft_stop if is_long else current_price >= soft_stop

        if hard_hit:
            self.tp_state.pop(symbol, None)
            return qty, f"波段硬止损触发({pnl_pct:+.2f}%)"

        if on_long_track:
            # 长线用swing ATR跟踪(默认1h×3), 给趋势3~6%的呼吸空间;
            # 传入的atr是操作周期(5m)的, ×1.5只有0.5~1%空间, 长线必被震出。
            trail_active = True
            trail_base = self._swing_atr(symbol)
            trail_atr = max(1.0, float(long_cfg.get("trail_atr_swing", 3.0)))
        else:
            trail_after_tp = max(1, min(2, int(pm.get("trail_after_tp", 2))))
            trail_active = st["tp2"] if trail_after_tp >= 2 else st["tp1"]
            trail_base = atr
            trail_atr = max(1.5, float(pm["trailing_atr"]))
        if trail_active and trail_base > 0:
            if is_long:
                trailing_stop = st["peak_price"] - trail_base * trail_atr
                if not on_long_track:
                    # 短线保本底线: tp1/tp2已落袋, 不该再让它回到成本以下。
                    # 长线不能加这条: 刚升级时peak≈entry×1.015, 保本底线会把
                    # 止损顶到+0.8%, 回落不足1%就被平, 3~6%呼吸空间形同虚设。
                    trailing_stop = max(
                        entry_price + trail_base * float(pm["lock_profit_atr"]),
                        trailing_stop)
                trail_hit = current_price <= trailing_stop
            else:
                trailing_stop = st["peak_price"] + trail_base * trail_atr
                if not on_long_track:
                    trailing_stop = min(
                        entry_price - trail_base * float(pm["lock_profit_atr"]),
                        trailing_stop)
                trail_hit = current_price >= trailing_stop
            if trail_hit:
                self.tp_state.pop(symbol, None)
                label = "长线" if on_long_track else "波段"
                return qty, f"{label}跟踪止损触发({pnl_pct:+.2f}%)"

        swing_against = (
            (is_long and swing_trend < 0)
            or (not is_long and swing_trend > 0)
        )
        if closed_candle and on_long_track:
            # 长线只认swing级别的结构反转, 且需连续N根swing收盘确认。
            # 不复用stop_breach_count: 它按操作周期(5m)递增, "连续2根"会退化成10分钟。
            if self._swing_bar_advanced(symbol, st):
                if swing_against:
                    st["long_breach_count"] = int(st.get("long_breach_count", 0)) + 1
                else:
                    st["long_breach_count"] = 0
            need = max(1, int(long_cfg.get("reversal_confirm_bars", 2)))
            if int(st.get("long_breach_count", 0)) >= need:
                self.tp_state.pop(symbol, None)
                return qty, (
                    f"长线结构反转·连续{st['long_breach_count']}根{self.swing_interval}确认"
                    f"({pnl_pct:+.2f}%)"
                )
        elif closed_candle:
            if soft_hit:
                st["stop_breach_count"] = int(st.get("stop_breach_count", 0)) + 1
            else:
                st["stop_breach_count"] = 0
            confirmations = max(1, int(pm["stop_confirmation_candles"]))
            structure_failed = (
                st["stop_breach_count"] >= confirmations
                and (not pm.get("require_swing_reversal", True) or swing_against)
            )
            if structure_failed:
                self.tp_state.pop(symbol, None)
                return qty, (
                    f"波段结构止损·连续{st['stop_breach_count']}根收盘确认"
                    f"({pnl_pct:+.2f}%)"
                )

        orig = float(st.get("orig_qty") or qty)
        partial = max(0.1, min(0.5, float(pm["partial_close_pct"]) / 100))
        tp1_mult = max(1.0, float(pm.get("tp1_atr", 3.0)))
        tp2_mult = max(tp1_mult + 0.5, float(pm.get("tp2_atr", 6.0)))
        tp1_pct = atr / entry_price * 100 * tp1_mult if atr > 0 else 0
        tp2_pct = atr / entry_price * 100 * tp2_mult if atr > 0 else 0

        if not st["tp1"] and tp1_pct > 0 and pnl_pct >= tp1_pct:
            st["tp1"] = True
            can_upgrade, up_reason = self._can_upgrade_to_long(symbol, side, st)
            if can_upgrade:
                # 只做标记。撤交易所止盈单/改止损是异步IO, 由调用方拿到本次平仓
                # 动作后执行, 成功才把track置为swing_long(先改交易所侧再改内存)。
                st["pending_upgrade"] = True
                close_pct = max(0.05, min(0.9, float(
                    long_cfg.get("tp1_close_pct", 30.0)) / 100))
                return min(round(orig * close_pct, 8), qty), (
                    f"止盈1·减{close_pct * 100:.0f}%转长线({up_reason})(+{pnl_pct:.2f}%)")
            return min(round(orig * partial, 8), qty), (
                f"波段止盈1·减{partial * 100:.0f}%(+{pnl_pct:.2f}%)")
        if st["tp1"] and not st["tp2"] and tp2_pct > 0 and pnl_pct >= tp2_pct:
            st["tp2"] = True
            if on_long_track:
                return None  # 长线不在tp2减仓, 剩余仓位交给swing跟踪止损
            return min(round(orig * partial, 8), qty), (
                f"波段止盈2·减{partial * 100:.0f}%(+{pnl_pct:.2f}%)")

        # 8) 孤立高低点突破未果(用户需求): 浮盈≥1ATR后, 持仓期孤立高点被触及
        #    又收盘回落=突破失败, 第1次减半仓观察, 第2次动能耗尽清仓。
        #    仅收盘确认时判定(bar_high/bar_low由K线收盘路径传入), 盘中不触发。
        #    回测验证: 同数据A/B净+10.4pp, 只在浮盈锁利场景生效, 不砍新趋势单。
        bf_exit = bool(pm.get("breakout_fail_exit", False))
        if (bf_exit and closed_candle and bar_high > 0 and bar_low > 0
                and atr > 0 and pnl_pct >= atr / entry_price * 100 * 1.0):
            # 更新持仓期孤立点参照(始终跟踪, 不限浮盈)
            if is_long:
                st["bf_peak"] = max(float(st.get("bf_peak", entry_price)), bar_high)
            else:
                st["bf_trough"] = min(float(st.get("bf_trough", entry_price)), bar_low)
            if is_long:
                prev_peak = float(st.get("bf_peak", entry_price))
                broke = bar_high >= prev_peak
                failed = current_price < prev_peak
            else:
                prev_trough = float(st.get("bf_trough", entry_price))
                broke = bar_low <= prev_trough
                failed = current_price > prev_trough
            if broke and failed and not st.get("bf_failed_now", False):
                st["bf_fails"] = int(st.get("bf_fails", 0)) + 1
                st["bf_failed_now"] = True
                if st["bf_fails"] >= max(2, int(pm.get("breakout_fail_count", 2))):
                    self.tp_state.pop(symbol, None)
                    return qty, f"突破未果·{st['bf_fails']}次冲高回落动能耗尽({pnl_pct:+.2f}%)"
                if st["bf_fails"] == 1 and qty > 0:
                    halve = min(round(qty * 0.5, 8), qty)
                    if halve > 0:
                        return halve, f"突破未果·冲高回落减半观察({pnl_pct:+.2f}%)"
            elif not broke:
                st["bf_failed_now"] = False
        return None

    def _mark_open_failure(self, symbol: str, error: str):
        """开仓下单被交易所拒绝(保证金不足/数量违规等)后, 该币冷却N分钟防无限重试。
        注意: 不能用_volatile_pause(那是亏损触发, 语义不同); 不响应超时/限流类
        临时错误(网络抖动重试无害)。"""
        err = str(error or "")
        if any(k in err for k in ("-2019", "-4131", "-4164", "Margin is insufficient",
                                  "below exchange minimum", "below the market minimum")):
            if not hasattr(self, "_open_fail_until"):
                self._open_fail_until = {}
            wait = float((self.cfg.get("risk", {}) or {}).get("open_fail_cooldown_sec", 300))
            self._open_fail_until[symbol] = time.time() + wait
            print(f"[开仓退避] {symbol} 下单被拒({err[:80]}), 暂停开仓{int(wait)}秒")

    def _cooldown_blocked(self, symbol: str) -> bool:
        """冷却检查: 同币平仓冷却 + 连亏熔断。返回 True=禁止开仓。"""
        now = time.time()
        # 连亏熔断
        if self._streak_until > now:
            remain = int(self._streak_until - now)
            print(f"[冷却] 连亏{self._streak_losses}笔熔断中, {remain}秒后恢复开仓")
            self._record_execution_event(
                "OPEN", "skipped", symbol, "",
                "loss streak circuit breaker", f"连亏{self._streak_losses}笔熔断中",
            )
            return True
        # 同币冷却
        until = self._cooldown_until.get(symbol)
        if until and until > now:
            remain = int(until - now)
            print(f"[冷却] {symbol} 平仓冷却中, {remain}秒后可再开")
            self._record_execution_event(
                "OPEN", "skipped", symbol, "",
                "per-symbol cooldown", f"平仓后冷却{remain}s",
            )
            return True
        # 开仓失败退避: 下单被拒(保证金不足/参数错误)后暂停该币N分钟,
        # 避免自动扫描每10秒对同一币无限重试(2026-08-07 CYSUSDT等连续百次
        # Margin insufficient)
        fail_until = getattr(self, "_open_fail_until", {}).get(symbol)
        if fail_until and fail_until > now:
            remain = int(fail_until - now)
            print(f"[开仓退避] {symbol} 下单失败冷却中, {remain}秒后再考虑开仓")
            self._record_execution_event(
                "OPEN", "skipped", symbol, "",
                "open failure backoff", f"下单失败冷却{remain}s",
            )
            return True
        # 动态躲避: 大波动/连续亏损币种暂停开仓, 等波动稳定(到期自动恢复)
        vp = self._volatile_pause.get(symbol)
        if vp and vp["until"] > now:
            remain = int(vp["until"] - now)
            print(f"[动态躲避] {symbol} 连续亏损{vp['losses']}笔波动过大, "
                  f"{remain}秒后再考虑入场")
            self._record_execution_event(
                "OPEN", "skipped", symbol, "",
                "volatile pause", f"连续亏损{vp['losses']}笔, 等待波动稳定{remain}s",
            )
            return True
        return False

    def _record_close_cooldown(self, symbol: str, pnl: float):
        """平仓后记录冷却状态(同币冷却 + 连亏计数)"""
        risk_cfg = (getattr(self, "cfg", {}) or {}).get("risk", {})
        sym_cd = float(risk_cfg.get("symbol_cooldown_sec", 900))
        streak_n = int(risk_cfg.get("loss_streak_count", 3))
        streak_cd = float(risk_cfg.get("loss_streak_cooldown_sec", 1800))
        if not hasattr(self, "_cooldown_until"):
            self._cooldown_until = {}
        if not hasattr(self, "_volatile_losses"):
            self._volatile_losses = {}
        if not hasattr(self, "_volatile_pause"):
            self._volatile_pause = {}
        if not hasattr(self, "_streak_losses"):
            self._streak_losses = 0
        if not hasattr(self, "_last_trade_close_time"):
            self._last_trade_close_time = 0.0
        self._cooldown_until[symbol] = time.time() + sym_cd
        self._last_trade_close_time = time.time()
        # 单币连续亏损计数: 用于大波动币种动态躲避(区别于连亏熔断, 只罚该币)
        if pnl <= 0:
            self._volatile_losses[symbol] = self._volatile_losses.get(symbol, 0) + 1
            vol_cfg = self._market_selection_cfg()
            pause_thresh = int(vol_cfg.get("volatile_loss_count", 2))
            pause_sec = float(vol_cfg.get("volatile_pause_sec", 1800))
            if self._volatile_losses[symbol] >= pause_thresh:
                self._volatile_pause[symbol] = {
                    "until": time.time() + pause_sec,
                    "losses": self._volatile_losses[symbol],
                }
                print(f"[动态躲避] {symbol} 连续亏损{self._volatile_losses[symbol]}笔, "
                      f"暂停开仓{int(pause_sec)}秒等波动稳定")
        else:
            self._volatile_losses.pop(symbol, None)
            self._volatile_pause.pop(symbol, None)
        if pnl <= 0:
            self._streak_losses += 1
            if self._streak_losses >= streak_n:
                self._streak_until = time.time() + streak_cd
                print(f"[冷却] 连亏{self._streak_losses}笔触发熔断, 暂停开仓{int(streak_cd)}秒")
        else:
            self._streak_losses = 0

    async def _close_pos(self, symbol: str, side: str, qty: float, reason: str,
                         entry_price: float | None = None,
                         exit_price: float | None = None) -> dict:
        """Close a position and record only the quantity actually reported as filled."""
        requested_qty = qty
        normalized_qty = 0.0
        try:
            normalized_qty = await self.client.normalize_quantity(symbol, qty)
            if normalized_qty <= 0:
                # 请求量低于交易所最小下单量(残留微仓): 不能再分批减, 直接全平。
                # 之前这里抛错导致调用方回滚tp_state, 退出监控每秒重试同一减仓
                # 动作直到持仓被交易所侧止损单平掉(BSBUSDT 2026-08-07 死循环)。
                try:
                    pos = self.positions_cache.get(symbol)
                    if not entry_price or entry_price <= 0:
                        entry_price = pos["entry_price"] if pos else 0
                    if not exit_price or exit_price <= 0:
                        tick = self.latest_klines.get(symbol)
                        exit_price = tick["close"] if tick else (pos["mark_price"] if pos else 0)
                    # 残留微仓低于minQty, 传quantity会被normalize拒掉; 用
                    # closePosition全平标志, 不需要quantity
                    ps = await self.client._position_side("LONG" if side == "LONG" else "SHORT")
                    order = await self.client.place_order(
                        symbol,
                        "SELL" if side == "LONG" else "BUY",
                        "MARKET",
                        position_side=ps,
                        close_position=True,
                    )
                    execution = self._order_execution(order)
                    actual_qty = execution["executed_qty"]
                    if actual_qty <= 0:
                        error = (f"exchange returned {execution['status']} with no executed "
                                 f"quantity while liquidating dust")
                        self._record_execution_event(
                            "CLOSE", "failed", symbol, side, reason, error,
                            requested_qty=requested_qty, normalized_qty=normalized_qty,
                            executed_qty=0.0, order_id=execution["order_id"],
                            exchange_status=execution["status"],
                        )
                        return {"ok": False, "error": error, **execution}
                    if execution["avg_price"] > 0:
                        exit_price = execution["avg_price"]
                    pnl = 0.0
                    pnl_pct = 0.0
                    if entry_price > 0 and exit_price > 0:
                        if side == "LONG":
                            pnl = (exit_price - entry_price) * actual_qty
                            pnl_pct = (exit_price - entry_price) / entry_price * 100
                        else:
                            pnl = (entry_price - exit_price) * actual_qty
                            pnl_pct = (entry_price - exit_price) / entry_price * 100
                    record = {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "symbol": symbol,
                        "side": f"close_{side}",
                        "qty": actual_qty,
                        "price": exit_price,
                        "reason": reason,
                        "order_id": execution["order_id"],
                        "status": execution["status"],
                    }
                    self.trades_log.append(record)
                    journal.record_close(
                        symbol, side, actual_qty, entry_price, exit_price, reason,
                        pnl, pnl_pct, order_id=execution["order_id"],
                    )
                    self.risk.record_realized_pnl(pnl)
                    self._record_close_cooldown(symbol, pnl)
                    self._record_execution_event(
                        "CLOSE", "dust_cleanup", symbol, side, reason,
                        f"残留微仓(请求{requested_qty}<minQty)全平, 实平{actual_qty}",
                        requested_qty=requested_qty, executed_qty=actual_qty,
                        avg_price=exit_price, order_id=execution["order_id"],
                        exchange_status=execution["status"],
                    )
                    print(f"[close] {symbol} {side} | {reason} | 残留微仓全平 qty={actual_qty} "
                          f"| PnL={pnl:+.4f}U")
                    return {"ok": True, **execution, "exit_price": exit_price,
                            "dust_cleanup": True}
                except Exception as e:
                    self._record_execution_event(
                        "CLOSE", "failed", symbol, side, reason, str(e),
                        requested_qty=requested_qty, normalized_qty=normalized_qty,
                    )
                    return {"ok": False, "error": str(e), "requested_qty": requested_qty,
                            "normalized_qty": normalized_qty, "executed_qty": 0.0}
            pos = self.positions_cache.get(symbol)
            if not entry_price or entry_price <= 0:
                entry_price = pos["entry_price"] if pos else 0
            if not exit_price or exit_price <= 0:
                tick = self.latest_klines.get(symbol)
                exit_price = tick["close"] if tick else (pos["mark_price"] if pos else 0)
            if side == "LONG":
                order = await self.client.market_close_long(symbol, normalized_qty)
            else:
                order = await self.client.market_close_short(symbol, normalized_qty)
            execution = self._order_execution(order)
            actual_qty = execution["executed_qty"]
            if actual_qty <= 0:
                error = f"exchange returned {execution['status']} with no executed quantity"
                self._record_execution_event(
                    "CLOSE", "failed", symbol, side, reason, error,
                    requested_qty=requested_qty, normalized_qty=normalized_qty,
                    executed_qty=0.0, order_id=execution["order_id"],
                    exchange_status=execution["status"],
                )
                return {"ok": False, "error": error, **execution}
            if execution["avg_price"] > 0:
                exit_price = execution["avg_price"]

            # 仓位已全平: 只撤本方向(被平方向)的残余单防误触发。
            # 不能 cancel_all_orders: 网格在双向模式挂的入场/止盈单不能被误撤,
            # 否则网格状态与交易所失同步, 止盈单无持仓可减会触发 -2022 无限重试。
            try:
                remaining = [p for p in await self.client.get_positions()
                             if p["symbol"] == symbol and float(p["positionAmt"]) != 0]
                if not remaining:
                    open_orders = await self.client.get_open_orders(symbol)
                    for o in open_orders or []:
                        if str(o.get("positionSide", "")).upper() == side.upper():
                            try:
                                await self.client.cancel_order(symbol, order_id=o.get("orderId"))
                            except Exception:
                                pass
            except Exception:
                pass

            pnl = 0.0
            pnl_pct = 0.0
            if entry_price > 0 and exit_price > 0:
                if side == "LONG":
                    pnl = (exit_price - entry_price) * actual_qty
                    pnl_pct = (exit_price - entry_price) / entry_price * 100
                else:
                    pnl = (entry_price - exit_price) * actual_qty
                    pnl_pct = (entry_price - exit_price) / entry_price * 100
            record = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "symbol": symbol,
                "side": f"close_{side}",
                "qty": actual_qty,
                "price": exit_price,
                "reason": reason,
                "order_id": execution["order_id"],
                "status": execution["status"],
            }
            self.trades_log.append(record)
            journal.record_close(
                symbol, side, actual_qty, entry_price, exit_price, reason, pnl, pnl_pct,
                order_id=execution["order_id"],
            )
            self.risk.record_realized_pnl(pnl)
            self._record_close_cooldown(symbol, pnl)
            outcome = "success" if execution["completed"] else "partial"
            self._record_execution_event(
                "CLOSE", outcome, symbol, side, reason,
                requested_qty=execution["requested_qty"] or requested_qty,
                normalized_qty=execution["normalized_qty"] or normalized_qty,
                executed_qty=actual_qty, avg_price=exit_price,
                order_id=execution["order_id"], exchange_status=execution["status"],
            )
            print(f"[close] {symbol} {side} | {reason} | qty={actual_qty} | PnL={pnl:+.4f}U")
            try:
                await self.client.cancel_all_orders(symbol)
            except Exception:
                pass
            return {"ok": execution["completed"], **execution, "exit_price": exit_price}
        except Exception as e:
            print(f"[close failed] {symbol}: {e}")
            self._record_execution_event(
                "CLOSE", "failed", symbol, side, reason, str(e),
                requested_qty=requested_qty, normalized_qty=normalized_qty,
            )
            return {"ok": False, "error": str(e), "requested_qty": requested_qty,
                    "normalized_qty": normalized_qty, "executed_qty": 0.0}

    # ==================== 第一优先: 安全与风控核心防线 ====================
    async def emergency_stop_all(self, flatten_positions: bool = True, reason: str = "人工一键紧急停止") -> dict:
        """一键紧急停止 (Emergency Kill Switch):
        1. 瞬间关闭自动交易 (auto_trade = False)
        2. 激活执行层硬风控急停锁 (emergency_stopped = True)
        3. 并发撤销交易所所有持仓币种的限价挂单和Algo条件保护单
        4. 若 flatten_positions=True: 并发市价全平当前所有真实持仓
        5. 记录不可篡改的紧急急停审计事件
        """
        self.auto_trade = False
        self.risk.trigger_emergency_stop(reason)
        print(f"🚨 [紧急急停] 已触发! 自动交易已关闭, 原因: {reason}")

        cancelled = await self.client.cancel_all_orders_globally()

        flatten_results = {}
        if flatten_positions:
            try:
                positions = await self.client.get_positions()
                symbols_to_close = []
                for p in positions:
                    amt = float(p.get("positionAmt", 0))
                    sym = p.get("symbol")
                    if abs(amt) > 1e-6 and sym:
                        symbols_to_close.append((sym, amt))

                for sym, amt in symbols_to_close:
                    try:
                        if amt > 0:
                            res = await self.client.market_close_long(sym, abs(amt))
                        else:
                            res = await self.client.market_close_short(sym, abs(amt))
                        flatten_results[sym] = "CLOSED"
                        self.tp_state.pop(sym, None)
                        await self.client.cancel_all_orders(sym)
                    except Exception as ce:
                        flatten_results[sym] = f"ERROR: {ce}"
            except Exception as pe:
                flatten_results["_query_error"] = str(pe)

        self._record_execution_event(
            "EMERGENCY_KILL_SWITCH", "triggered", "ALL", "ALL",
            reason=reason, flatten_positions=flatten_positions,
            flatten_results=flatten_results,
        )

        return {
            "ok": True,
            "auto_trade": False,
            "emergency_stopped": True,
            "reason": reason,
            "cancelled_orders": cancelled,
            "flatten_positions": flatten_positions,
            "flatten_results": flatten_results,
            "timestamp": time.time(),
        }

    async def resume_from_emergency(self) -> dict:
        """解除全局紧急急停，允许恢复手动或自动交易"""
        self.risk.reset_emergency_stop()
        self._record_execution_event("EMERGENCY_KILL_SWITCH", "resumed", "ALL", "ALL", reason="人工解除急停")
        return {
            "ok": True,
            "emergency_stopped": False,
            "message": "紧急急停已成功解除，系统风控恢复正常监控态",
        }

    async def _reconciliation_loop(self):
        """常驻周期性仓位对账守护协程 (每25秒运行一次)"""
        await asyncio.sleep(8)
        while self.running:
            try:
                positions = await self.client.get_positions()
                report = self.risk.reconcile_positions(positions, self.tp_state)
                if report.get("discrepancies"):
                    for disc in report["discrepancies"]:
                        print(f"⚠️ [仓位对账报警] {disc['type']} - {disc['symbol']}: {disc['message']}")
                        self._record_execution_event(
                            "RECONCILIATION", "mismatch", disc["symbol"],
                            disc.get("exchange", {}).get("side", "UNKNOWN") if disc.get("exchange") else "LOCAL",
                            reason=disc["type"], detail=disc["message"],
                        )
                self.reconciliation_log.append(report)
                if len(self.reconciliation_log) > 50:
                    self.reconciliation_log = self.reconciliation_log[-50:]
            except Exception as exc:
                self.risk.trip_circuit_breaker(f"交易所持仓查询网络异常: {exc}")
            await asyncio.sleep(25)

    async def run_reconciliation_now(self) -> dict:
        """立即执行一次手动对账"""
        try:
            positions = await self.client.get_positions()
            report = self.risk.reconcile_positions(positions, self.tp_state)
            return {"ok": True, **report}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def set_trading_mode(self, mode: str) -> dict:
        """模式分级设置: READONLY / SHADOW / PAPER / MICRO_LIVE / LIVE"""
        valid_modes = {"READONLY", "SHADOW", "PAPER", "MICRO_LIVE", "LIVE"}
        if mode not in valid_modes:
            return {"ok": False, "error": f"不支持的交易模式: {mode}, 必须是 {valid_modes}"}
        old_mode = self.trading_mode
        self.trading_mode = mode
        if mode == "READONLY":
            self.auto_trade = False
            self.live_trading_enabled = False
            self.paper_trading = True
        elif mode == "SHADOW":
            self.live_trading_enabled = False
            self.paper_trading = True
        elif mode == "PAPER":
            self.live_trading_enabled = False
            self.paper_trading = True
        elif mode in ("MICRO_LIVE", "LIVE"):
            self.live_trading_enabled = True
            self.paper_trading = False

        from config import load_config, save_config
        cfg = load_config()
        cfg["trading_mode"] = mode
        cfg["live_trading_enabled"] = self.live_trading_enabled
        cfg["paper_trading"] = self.paper_trading
        save_config(cfg)
        self.cfg = cfg

        print(f"🔄 [交易模式切换] {old_mode} → {mode} (实盘开仓: {self.live_trading_enabled}, 纸面模拟: {self.paper_trading})")
        return {"ok": True, "old_mode": old_mode, "new_mode": mode, "live_trading_enabled": self.live_trading_enabled}

    def record_decision_snapshot(
        self,
        symbol: str,
        signal: int,
        outcome: str,
        reason: str,
        details: dict | None = None
    ):
        """记录不可篡改的决策快照黑匣子 (开仓/放弃开仓全景还原)"""
        snapshot = {
            "id": f"dec_{int(time.time() * 1000)}",
            "time": datetime.now().isoformat(timespec="seconds"),
            "symbol": symbol,
            "signal": signal,
            "side": "LONG" if signal > 0 else ("SHORT" if signal < 0 else "HOLD"),
            "outcome": outcome,
            "reason": reason,
            "trading_mode": getattr(self, "trading_mode", "UNKNOWN"),
            "details": details or {},
        }
        self.decision_snapshots_log.append(snapshot)
        if len(self.decision_snapshots_log) > 200:
            self.decision_snapshots_log = self.decision_snapshots_log[-200:]
        return snapshot

    async def _place_protective_orders(self, symbol: str, side_en: str,
                                       sl_price: float, tp_price: float):
        """交易所侧硬性止盈止损: 服务宕机/断网时仓位仍受保护。
        TP挂在tp2(第二目标), tp1分批止盈仍由软件逻辑执行。"""
        if not sl_price or not tp_price or sl_price <= 0 or tp_price <= 0:
            return
        try:
            await self.client.cancel_all_orders(symbol)
            close_side = "SELL" if side_en == "LONG" else "BUY"
            await self.client.place_protective_stop(
                symbol, side_en, "STOP_MARKET", sl_price, close_side)
            await self.client.place_protective_stop(
                symbol, side_en, "TAKE_PROFIT_MARKET", tp_price, close_side)
            print(f"[保护单] {symbol} {side_en} 交易所侧 SL={sl_price} TP={tp_price} 已挂出(标记价格触发)")
        except Exception as e:
            print(f"[保护单] {symbol} 挂出失败: {e} (回退为纯软件监控)")

    # ==================== 长线赛道 ====================
    async def _place_long_track_protection(self, symbol: str, side_en: str,
                                           sl_price: float) -> bool:
        """长线赛道保护单: 撤掉tp2的止盈单, 只留硬止损。

        不能复用_place_protective_orders: 它在tp_price<=0时直接return, 连SL都不挂;
        且它吞掉异常, 而升级必须知道成败才能决定是否改track。

        代价: 长线仓在交易所侧不再有止盈保护(止损仍在)。这对长线是正确的——
        开仓时挂的是TAKE_PROFIT_MARKET+closePosition, 价格一到tp2就被全平,
        软件层"跳过tp2继续持有"永远等不到执行。
        """
        if not sl_price or sl_price <= 0:
            return False
        try:
            await self.client.cancel_all_orders(symbol)
            close_side = "SELL" if side_en == "LONG" else "BUY"
            await self.client.place_protective_stop(
                symbol, side_en, "STOP_MARKET", sl_price, close_side)
            print(f"[长线保护单] {symbol} {side_en} SL={sl_price} 已挂出, "
                  f"止盈单已撤(改由{self.swing_interval}跟踪止损退出)")
            return True
        except Exception as e:
            print(f"[长线保护单] {symbol} 失败: {e}")
            return False

    async def _apply_pending_upgrade(self, symbol: str, side: str,
                                     entry_price: float) -> bool:
        """执行长线升级的交易所侧改单。顺序不可颠倒: 先改交易所, 成功才改内存。

        失败则放弃升级, track保持scalp: 带着tp2全平单的"长线仓"是假长线,
        比老实做短线更糟。
        """
        st = self.tp_state.get(symbol)
        if not st or not st.get("pending_upgrade"):
            return False
        st["pending_upgrade"] = False
        cfg = self._long_track_cfg()
        hard_pct = max(0.5, float(cfg.get("hard_stop_pct", 6.0)))
        trail_mult = cfg.get("trail_atr_swing", 3.0)
        sl_price = (entry_price * (1 - hard_pct / 100) if side == "LONG"
                    else entry_price * (1 + hard_pct / 100))
        if not await self._place_long_track_protection(symbol, side, sl_price):
            self._record_execution_event(
                "UPGRADE", "failed", symbol, side, "长线赛道升级失败",
                "交易所侧改单失败, 保持短线赛道; 本单已按长线比例减仓, "
                "剩余仓位继续走短线流程(硬止损与tp2减仓仍生效)",
                entry_price=entry_price, planned_stop=round(sl_price, 8),
            )
            return False
        st["track"] = "swing_long"
        st["track_since"] = time.time()
        st["pyramided"] = True  # 长线禁止加仓: 加仓会把止损改成保本并挂5m止盈全平单
        st["long_breach_count"] = 0
        st["last_swing_bar"] = int(
            (self.swing_ohlc_cache.get(symbol) or {}).get("last_open_time") or 0)
        self._persist_long_track()
        print(f"[长线赛道] {symbol} {side} 已升级: 硬止损{hard_pct}%, "
              f"跟踪{trail_mult}×{self.swing_interval}ATR")
        self._record_execution_event(
            "UPGRADE", "success", symbol, side, "长线赛道升级",
            f"swing+高TF同向, 硬止损{hard_pct}%, 跟踪{trail_mult}×{self.swing_interval}ATR",
            entry_price=entry_price, stop_price=round(sl_price, 8),
        )
        return True

    @staticmethod
    def _long_track_file() -> Path:
        return Path(__file__).resolve().parents[2] / "data" / "long_track.json"

    def _persist_long_track(self):
        """落盘长线赛道供重启恢复。tp_state是纯内存的, 不落盘则重启后长线仓
        退化成"没有交易所止盈单的短线仓", 在tp1处又被减仓一次。"""
        try:
            payload = [
                {
                    "symbol": sym,
                    "side": st.get("side"),
                    "track_since": st.get("track_since", 0),
                    "orig_qty": st.get("orig_qty", 0),
                    "mode": st.get("mode", "conservative"),
                    "peak_price": st.get("peak_price", 0),
                    "tp1": bool(st.get("tp1")),
                    "tp2": bool(st.get("tp2")),
                    # 恢复时用来确认是同一笔仓位: 长线仓平掉后若同symbol又开了
                    # 新短线仓, 只比symbol+side会把新仓误恢复成长线赛道。
                    "entry_price": float(
                        (self.positions_cache.get(sym) or {}).get("entry_price") or 0),
                }
                for sym, st in self.tp_state.items()
                if (st or {}).get("track") == "swing_long"
            ]
            f = self._long_track_file()
            f.parent.mkdir(exist_ok=True)
            f.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                         encoding="utf-8")
        except Exception as e:
            print(f"[长线赛道] 落盘失败: {e}")

    def _restore_long_track(self, open_positions: list[dict]):
        """启动时恢复长线赛道, 与交易所实际持仓交叉验证, 对不上的丢弃。

        peak_price必须一起恢复: 跟踪止损依赖它, 重置成当前价会让止损位失真。
        """
        f = self._long_track_file()
        if not f.exists():
            return
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[长线赛道] 读取失败: {e}")
            return
        if not isinstance(payload, list):
            return
        live = {p["symbol"]: p for p in open_positions}
        restored = []
        for item in payload:
            sym = item.get("symbol")
            pos = live.get(sym)
            if not pos or pos.get("side") != item.get("side"):
                continue  # 仓位已平或方向已变, 丢弃
            saved_entry = float(item.get("entry_price") or 0)
            live_entry = float(pos.get("entry_price") or 0)
            if saved_entry > 0 and live_entry > 0:
                drift = abs(live_entry - saved_entry) / saved_entry
                if drift > 0.005:
                    print(f"[长线赛道] {sym} 开仓价不匹配"
                          f"(落盘{saved_entry} vs 实际{live_entry}), 判定为新仓, 丢弃")
                    continue
            st = dict(self.tp_state.get(sym) or {})
            st.update({
                "side": item.get("side"),
                "orig_qty": float(item.get("orig_qty") or pos.get("qty") or 0),
                "tp1": bool(item.get("tp1", True)),
                "tp2": bool(item.get("tp2")),
                "tp3": st.get("tp3", False),
                "mode": item.get("mode", "conservative"),
                "entry_time": st.get("entry_time", 0),
                "peak_price": float(item.get("peak_price")
                                    or pos.get("entry_price") or 0),
                "stop_breach_count": 0,
                "track": "swing_long",
                "pending_upgrade": False,
                "track_since": float(item.get("track_since") or 0),
                "long_breach_count": 0,
                "last_swing_bar": 0,
                "pyramided": True,
            })
            self.tp_state[sym] = st
            restored.append(sym)
        if restored:
            print(f"[长线赛道] 已恢复: {', '.join(restored)}")
        if len(restored) != len(payload):
            self._persist_long_track()  # 清掉对不上的条目

    # ==================== 高波动网格对冲(两头吃) ====================
    def _grid_cfg(self) -> dict:
        defaults = {
            "enabled": True,          # 总开关
            "min_atr_pct": 1.0,       # 波动率门槛: ATR%够大才有肉吃
            "max_abs_change_1h": 1.5, # 1h涨跌限制: 过滤单边行情(只做震荡)
            "spacing_atr": 1.2,       # 网格间距 = 1.2倍ATR
            "rungs_per_side": 2,      # 每侧挂单层数
            "leverage": 6,            # 网格杠杆
            "max_margin_ratio": 0.8,  # 最多动用可用余额比例
            "breakout_atr": 3.0,      # 突破N倍ATR撤入场单止损观望
            "max_grids": 1,           # 同时最多网格数
            "max_price": 10.0,        # 单价上限
        }
        defaults.update(self.strategy.cfg.get("grid", {}) or {})
        return defaults

    def _profit_bet_cfg(self) -> dict:
        defaults = {
            "enabled": True,
            "allocation_pct": 25.0,
            "min_daily_net_profit_u": 0.20,
            "min_atr_pct": 1.0,
            "leverage": 6,
            "stop_atr": 1.5,
            "min_stop_pct": 1.2,
            "max_stop_pct": 3.0,
            "max_wallet_risk_pct": 3.0,
            "max_notional_multiple": 1.5,
            "max_per_day": 1,
        }
        defaults.update(self.strategy.cfg.get("profit_bet", {}) or {})
        return defaults

    @staticmethod
    def _profit_bet_plan(balance: float, daily_profit: float, atr_pct: float,
                         cfg: dict) -> dict:
        balance = max(0.0, float(balance))
        daily_profit = max(0.0, float(daily_profit))
        allocation = daily_profit * max(0.0, float(cfg["allocation_pct"])) / 100
        wallet_cap = balance * max(0.0, float(cfg["max_wallet_risk_pct"])) / 100
        risk_budget = min(allocation, wallet_cap)
        stop_pct = max(
            float(cfg["min_stop_pct"]),
            float(atr_pct) * float(cfg["stop_atr"]),
        )
        stop_pct = min(stop_pct, float(cfg["max_stop_pct"]))
        target_notional = risk_budget / (stop_pct / 100) if stop_pct > 0 else 0
        target_notional = min(
            target_notional,
            balance * max(0.0, float(cfg["max_notional_multiple"])),
        )
        return {
            "risk_budget": risk_budget,
            "stop_pct": stop_pct,
            "target_notional": target_notional,
            "allocation": allocation,
            "wallet_cap": wallet_cap,
        }

    def _daily_profit_bet_state(self) -> dict:
        report = journal.daily_report()
        bot_net = float(
            ((report.get("by_source") or {}).get("bot") or {}).get("net_pnl", 0)
            or 0
        )
        used = sum(
            1 for row in report.get("records", [])
            if row.get("type") == "open"
            and bool((row.get("entry_context") or {}).get("profit_bet"))
        )
        return {"net_profit": bot_net, "used": used, "date": report.get("date")}

    async def _maybe_execute_profit_bet(self, items: list, held: set[str]) -> str | None:
        cfg = self._profit_bet_cfg()
        if not cfg.get("enabled", True):
            return None
        state = self._daily_profit_bet_state()
        if state["net_profit"] < float(cfg["min_daily_net_profit_u"]):
            return None
        if state["used"] >= int(cfg["max_per_day"]):
            return None
        if len(held) >= int(self.cfg.get("risk", {}).get("max_positions", 2)):
            return None
        candidates = [
            item for item in items
            if item["symbol"] not in held
            and float(item.get("atr_pct", 0) or 0) >= float(cfg["min_atr_pct"])
        ]
        if not candidates:
            return None
        candidate = max(
            candidates,
            key=lambda item: (
                float(item.get("atr_pct", 0)),
                float(item.get("hot_score", 0)),
            ),
        )
        account = await self.client.get_account()
        balance = float(account.get("totalWalletBalance") or 0)
        plan = self._profit_bet_plan(
            balance, state["net_profit"], float(candidate.get("atr_pct", 0)), cfg)
        if plan["risk_budget"] <= 0 or plan["target_notional"] < 5:
            return None
        signal = 1 if candidate["side_en"] == "LONG" else -1
        context = {
            "score": candidate.get("score", 0),
            "base_score": candidate.get("base_score", candidate.get("score", 0)),
            "factors": candidate.get("factors", []),
            "indicators": {
                "rsi": candidate.get("rsi"),
                "atr_pct": candidate.get("atr_pct"),
            },
            "funding_rate": candidate.get("funding_rate"),
            "smart_money": candidate.get("smart_money"),
            "smart_money_decision": candidate.get("smart_money_decision"),
            "liquidity": candidate.get("liquidity"),
            "recommendation": candidate,
            "profit_bet": {
                **plan,
                "daily_net_profit": state["net_profit"],
                "date": state["date"],
                "leverage": int(cfg["leverage"]),
            },
        }
        print(
            f"[利润博弈] {candidate['symbol']} ATR={candidate.get('atr_pct')}% "
            f"当日净利润={state['net_profit']:.4f}U 风险预算={plan['risk_budget']:.4f}U"
        )
        await self._execute_signal(
            candidate["symbol"], signal, candidate["price"],
            mode="profit_bet", candidate_context=context,
        )
        return candidate["symbol"]

    async def _grid_loop(self):
        """网格主循环: 2秒级监控成交并补单(挂单本身在交易所撮合, 毫秒级精准)"""
        await asyncio.sleep(12)
        await self._grid_cleanup_orphans()
        tick = 0
        while self.running:
            try:
                gcfg = self._grid_cfg()
                if self.auto_trade and gcfg.get("enabled", True):
                    await self._grid_manage()
                    tick += 1
                    if tick % 30 == 0 and len(self.grid_state) < int(gcfg.get("max_grids", 1)):
                        await self._grid_scan_and_start()
            except Exception as e:
                print(f"[网格] 循环异常: {e}")
            await asyncio.sleep(2)

    async def _grid_cleanup_orphans(self):
        """重启后清理上一代遗留的网格挂单(状态不持久化, 宁可清掉重开)"""
        try:
            orders = await self.client.get_open_orders()
            for o in orders or []:
                cid = o.get("clientOrderId", "")
                if str(cid).startswith("gridbot-"):
                    try:
                        await self.client.cancel_order(o["symbol"], order_id=o.get("orderId"))
                        print(f"[网格] 清理遗留挂单 {o['symbol']} {o.get('side')} {o.get('price')}")
                    except Exception as e:
                        print(f"[网格] 清理挂单失败 {o['symbol']}: {e}")
        except Exception as e:
            print(f"[网格] 查询挂单失败: {e}")

    async def _grid_scan_and_start(self):
        """寻找高波动+震荡(无趋势)的币开网格: 波动大才有差价, 震荡才敢两头挂"""
        gcfg = self._grid_cfg()
        try:
            tickers = await self.client.get_all_tickers()
        except Exception:
            return
        cand = []
        for t in tickers:
            sym = t.get("symbol", "")
            if not sym.endswith("USDT") or sym.endswith("_PERP"):
                continue
            try:
                p = float(t.get("lastPrice", 0))
                qv = float(t.get("quoteVolume", 0))
                chg24 = float(t.get("priceChangePercent", 0))
            except (ValueError, TypeError):
                continue
            if p <= 0 or p > float(gcfg.get("max_price", 10)) or qv < 1e7:
                continue
            if abs(chg24) > 10:
                continue  # 24h已大幅单边, 不网格
            cand.append((sym, p, qv))
        cand.sort(key=lambda x: -x[2])
        held = set(self.position_symbols)
        for sym, price, _ in cand[:12]:
            if sym in held or sym in self.grid_state:
                continue
            try:
                klines = await self.client.get_klines(sym, self.interval, 200)
                if len(klines) < 100:
                    continue
                closes = np.array([float(k[4]) for k in klines])
                highs = np.array([float(k[2]) for k in klines])
                lows = np.array([float(k[3]) for k in klines])
                vols = np.array([float(k[5]) for k in klines])
                opens = np.array([float(k[1]) for k in klines])
                atr = float(calc_atr(highs, lows, closes, 14)[-1])
                atr_pct = atr / price * 100 if price else 0
                chg_1h = self._series_change(closes, self._bars_per_hour())
                ribbon = detect_ema_ribbon(closes)
                # 入选条件: 高波动 + 近1小时无大幅单边 + EMA丝带无趋势(震荡市)
                if atr_pct < float(gcfg.get("min_atr_pct", 1.0)):
                    continue
                if abs(chg_1h) > float(gcfg.get("max_abs_change_1h", 1.5)):
                    continue
                if ribbon != 0:
                    continue
                # 主力出货中的币不做网格(接飞刀)
                intent = detect_main_force_intent(closes, highs, lows, vols, opens, atr)
                if intent["intent"] == "出货" and intent["confidence"] >= 55:
                    print(f"[网格] {sym} 波动达标但主力出货{intent['confidence']}%, 放弃")
                    continue
                await self._start_grid(sym, price, atr, gcfg)
                return
            except Exception as e:
                print(f"[网格] {sym} 评估失败: {e}")

    async def _start_grid(self, symbol: str, center: float, atr: float, gcfg: dict):
        rungs = int(gcfg.get("rungs_per_side", 2))
        spacing = max(atr * float(gcfg.get("spacing_atr", 1.2)), center * 0.0015)
        # 资金校验: 网格总保证金不得超过可用余额的指定比例(仓位控制)
        try:
            account = await self.client.get_account()
            available = float(account.get("availableBalance") or 0)
            _st, _mq, _xq, mn = await self.client._quantity_rule(symbol)
        except Exception as e:
            print(f"[网格] {symbol} 规则查询失败: {e}")
            return
        # 单格名义金额: config可配(默认5U), 现有资金倾斜给网格时调大
        rung_notional = max(float(mn) * 1.02,
                            float(gcfg.get("min_rung_notional", 5.0)))
        try:
            lev, _max = await self.client.clamp_leverage(symbol, int(gcfg.get("leverage", 6)))
        except Exception as e:
            print(f"[网格] {symbol} 杠杆查询失败: {e}")
            return
        required_margin = (2 * rungs * rung_notional) / lev if lev else 0
        if required_margin > available * float(gcfg.get("max_margin_ratio", 0.8)):
            print(f"[网格] {symbol} 符合高波动震荡条件, 但保证金不足"
                  f"(需{required_margin:.2f}U/可用{available:.2f}U), 等余额增长后再开")
            return
        try:
            await self._prepare_new_position(symbol, lev)
        except Exception as e:
            print(f"[网格] {symbol} 初始化失败: {e}")
            return
        tag = int(time.time() * 1000) % 100000000
        state = {"symbol": symbol, "center": center, "spacing": spacing, "atr": atr,
                 "lev": lev, "started": time.time(), "round_trips": 0,
                 "grid_pnl": 0.0, "winding_down": False, "rungs": []}
        try:
            for i in range(1, rungs + 1):
                bp = center - i * spacing
                sp = center + i * spacing
                bq = await self.client.quantity_for_notional(symbol, bp, rung_notional)
                sq = await self.client.quantity_for_notional(symbol, sp, rung_notional)
                cid_b = f"gridbot-{symbol[:6]}-B{i}-{tag}"
                cid_s = f"gridbot-{symbol[:6]}-S{i}-{tag}"
                ob = await self.client.place_limit_order(symbol, "BUY", "LONG", bq, bp, cid_b)
                os_ = await self.client.place_limit_order(symbol, "SELL", "SHORT", sq, sp, cid_s)
                state["rungs"].append({
                    "i": i, "long_qty": bq, "short_qty": sq,
                    "buy_price": bp, "sell_price": sp,
                    "buy_id": str(ob.get("orderId")), "buy_phase": "entry",
                    "sell_id": str(os_.get("orderId")), "sell_phase": "entry",
                })
        except Exception as e:
            print(f"[网格] {symbol} 挂单失败, 撤销已挂: {e}")
            try:
                await self.client.cancel_all_orders(symbol)
            except Exception:
                pass
            return
        self.grid_state[symbol] = state
        self._record_execution_event(
            "GRID", "success", symbol, "NEUTRAL",
            f"开网格两头吃: 每侧{rungs}层 间距{spacing:.6f} 杠杆{lev}x",
            grid_center=center, grid_spacing=round(spacing, 8))
        print(f"[网格] {symbol} 开格 | 中心{center} 间距{spacing:.5f} 每侧{rungs}层 {lev}x")

    async def _grid_manage(self):
        """2秒级监控: 入场单成交→对面挂止盈单; 止盈成交→一格差价落袋并重新挂入场单"""
        for symbol, st in list(self.grid_state.items()):
            try:
                open_orders = await self.client.get_open_orders(symbol)
            except Exception:
                continue
            # 网格腿的止盈单是 reduce-only 语义: 双向模式下若对应方向持仓为 0,
            # 交易所必然拒绝(-2022)。每轮拉一次真实持仓, 无持仓的腿直接收尾。
            try:
                pos_map = {}
                for p in await self.client.get_positions():
                    if p["symbol"] == symbol and float(p["positionAmt"]) != 0:
                        pos_map[str(p.get("positionSide", ""))] = float(p["positionAmt"])
                st["has_long_pos"] = bool(pos_map.get("LONG"))
                st["has_short_pos"] = bool(pos_map.get("SHORT"))
            except Exception:
                st["has_long_pos"] = True
                st["has_short_pos"] = True
            open_ids = {str(o.get("orderId")) for o in open_orders or []}
            price = 0.0
            try:
                tk = await self.client.get_ticker(symbol)
                price = float(tk.get("lastPrice") or 0)
            except Exception:
                pass
            # 突破保护: 价格冲出网格边界 → 撤掉所有入场单, 只留止盈单收尾
            if price > 0 and not st["winding_down"]:
                bound = max(st["atr"] * float(self._grid_cfg().get("breakout_atr", 3.0)),
                            st["spacing"] * (len(st["rungs"]) + 1))
                if abs(price - st["center"]) > bound:
                    st["winding_down"] = True
                    for rung in st["rungs"]:
                        try:
                            if rung["buy_phase"] == "entry":
                                await self.client.cancel_order(symbol, order_id=rung["buy_id"])
                                rung["buy_phase"] = "cancelled"
                            if rung["sell_phase"] == "entry":
                                await self.client.cancel_order(symbol, order_id=rung["sell_id"])
                                rung["sell_phase"] = "cancelled"
                        except Exception:
                            pass
                    print(f"[网格] {symbol} 价格突破边界({price}), 撤入场单收尾")
            for rung in st["rungs"]:
                # ---- 多头腿: 低位买入 → 高一格卖出 ----
                if rung["buy_phase"] == "entry" and rung["buy_id"] not in open_ids:
                    if st["winding_down"]:
                        rung["buy_phase"] = "cancelled"
                    else:
                        # 止盈单=reduce-only语义: 双向模式无多头持仓时交易所必拒(-2022)。
                        # 入场单消失但持仓为零(被外部平掉/撤单)时标记 done 收尾, 不无限重试。
                        if not st["has_long_pos"]:
                            rung["buy_phase"] = "done"
                            print(f"[网格] {symbol} 多头无持仓, 止盈腿放弃(收尾)")
                            continue
                        exit_price = rung["buy_price"] + st["spacing"]
                        cid = f"gridbot-{symbol[:6]}-XB{rung['i']}-{int(time.time() * 1000) % 100000000}"
                        try:
                            o = await self.client.place_limit_order(
                                symbol, "SELL", "LONG", rung["long_qty"], exit_price, cid)
                            rung["buy_id"] = str(o.get("orderId"))
                            rung["buy_phase"] = "exit"
                        except Exception as e:
                            # 止盈挂单失败(-2022等)不能无限重试: 已触发的
                            # 入场腿不再产生新动作, 直接标记 done 收尾
                            print(f"[网格] {symbol} 多头止盈挂单失败: {e} (收尾)")
                            rung["buy_phase"] = "done"
                elif rung["buy_phase"] == "exit" and rung["buy_id"] not in open_ids:
                    st["round_trips"] += 1
                    st["grid_pnl"] += st["spacing"] * rung["long_qty"]
                    print(f"[网格] {symbol} 多头一格落袋 +{st['spacing'] * rung['long_qty']:.4f}U "
                          f"(累计{st['grid_pnl']:.4f}U/{st['round_trips']}回合)")
                    if st["winding_down"]:
                        rung["buy_phase"] = "done"
                    else:
                        cid = f"gridbot-{symbol[:6]}-B{rung['i']}-{int(time.time() * 1000) % 100000000}"
                        try:
                            o = await self.client.place_limit_order(
                                symbol, "BUY", "LONG", rung["long_qty"], rung["buy_price"], cid)
                            rung["buy_id"] = str(o.get("orderId"))
                            rung["buy_phase"] = "entry"
                        except Exception as e:
                            print(f"[网格] {symbol} 多头重挂失败: {e}")
                            rung["buy_phase"] = "done"
                # ---- 空头腿: 高位卖出 → 低一格买回 ----
                if rung["sell_phase"] == "entry" and rung["sell_id"] not in open_ids:
                    if st["winding_down"]:
                        rung["sell_phase"] = "cancelled"
                    else:
                        if not st["has_short_pos"]:
                            rung["sell_phase"] = "done"
                            print(f"[网格] {symbol} 空头无持仓, 止盈腿放弃(收尾)")
                            continue
                        exit_price = rung["sell_price"] - st["spacing"]
                        cid = f"gridbot-{symbol[:6]}-XS{rung['i']}-{int(time.time() * 1000) % 100000000}"
                        try:
                            o = await self.client.place_limit_order(
                                symbol, "BUY", "SHORT", rung["short_qty"], exit_price, cid)
                            rung["sell_id"] = str(o.get("orderId"))
                            rung["sell_phase"] = "exit"
                        except Exception as e:
                            # 止盈挂单失败(-2022等)不能无限重试: 已触发的
                            # 入场腿不再产生新动作, 直接标记 done 收尾
                            print(f"[网格] {symbol} 空头止盈挂单失败: {e} (收尾)")
                            rung["sell_phase"] = "done"
                elif rung["sell_phase"] == "exit" and rung["sell_id"] not in open_ids:
                    st["round_trips"] += 1
                    st["grid_pnl"] += st["spacing"] * rung["short_qty"]
                    print(f"[网格] {symbol} 空头一格落袋 +{st['spacing'] * rung['short_qty']:.4f}U "
                          f"(累计{st['grid_pnl']:.4f}U/{st['round_trips']}回合)")
                    if st["winding_down"]:
                        rung["sell_phase"] = "done"
                    else:
                        cid = f"gridbot-{symbol[:6]}-S{rung['i']}-{int(time.time() * 1000) % 100000000}"
                        try:
                            o = await self.client.place_limit_order(
                                symbol, "SELL", "SHORT", rung["short_qty"], rung["sell_price"], cid)
                            rung["sell_id"] = str(o.get("orderId"))
                            rung["sell_phase"] = "entry"
                        except Exception as e:
                            print(f"[网格] {symbol} 空头重挂失败: {e}")
                            rung["sell_phase"] = "done"
            # 收尾完成: 所有腿结束且无挂单 → 移除网格状态
            # (不限于 winding_down: 止盈腿因无持仓被放弃后, 网格不再产生新动作, 直接收尾)
            phases = [rung["buy_phase"] for rung in st["rungs"]] + \
                     [rung["sell_phase"] for rung in st["rungs"]]
            if all(p in ("cancelled", "done") for p in phases) and not open_ids:
                if st["winding_down"] or any(p == "done" for p in phases):
                    self._record_execution_event(
                        "GRID", "success", symbol, "NEUTRAL",
                        f"网格收尾: {st['round_trips']}回合 毛利润{st['grid_pnl']:.4f}U")
                    self.grid_state.pop(symbol, None)
                    print(f"[网格] {symbol} 收尾完成 {st['round_trips']}回合/{st['grid_pnl']:.4f}U")

    async def _execute_signal(self, symbol: str, signal: int, price: float,
                              mode: str = "conservative", candidate_context: dict = None,
                              force: bool = False):
        """执行交易信号。mode: conservative(保守仓) / aggressive(激进仓)
        force=True 表示手动一键下单: 跳过黑名单与最小技术分门槛, 其余风控照常。"""
        # 数据驱动过滤: 黑名单币种 + 回避时段(降低过度交易/手续费)
        scfg = self.strategy.cfg
        if not self._trade_symbol_allowed(symbol):
            print(f"[白名单过滤] {symbol} 不在已选择交易品种中，跳过自动开仓")
            return
        # 交易冷却: 同币平仓冷却 + 连亏熔断(手动 force 跳过冷却, 尊重人工干预)
        if not force and self._cooldown_blocked(symbol):
            return
        candidate_context = dict(candidate_context or {})
        liquidity = candidate_context.get("liquidity")
        if not liquidity:
            liquidity = await self._liquidity_snapshot(symbol)
            candidate_context["liquidity"] = liquidity
        if not liquidity.get("allowed", False):
            print(f"[流动性过滤] {symbol}: {liquidity.get('reason', '未通过')}")
            return
        if not force and symbol in set(scfg.get("blacklist", [])):
            print(f"[过滤] {symbol} 在黑名单, 跳过开仓")
            return
        avoid_hours = set(scfg.get("avoid_hours", []))
        now_hour = datetime.now().hour
        if avoid_hours and now_hour in avoid_hours:
            print(f"[过滤] {symbol} 回避时段({now_hour}点), 跳过开仓")
            return
        # 波动率上界: 大波动币种(ATR%过高)波动未稳定前不入场, 等稳定再考虑
        ms_cfg = self._market_selection_cfg()
        max_atr_pct = float(ms_cfg.get("max_atr_pct", 0) or 0)
        if not force and max_atr_pct > 0:
            ind = candidate_context.get("indicators") or self.latest_indicators.get(symbol) or {}
            atr_now = float(ind.get("atr") or 0)
            price_now = float(ind.get("price") or price)
            atr_pct_now = (atr_now / price_now * 100) if (atr_now > 0 and price_now > 0) else 0
            if atr_pct_now > max_atr_pct:
                print(f"[波动过滤] {symbol} ATR%={atr_pct_now:.2f}% 超过上限{max_atr_pct}%, "
                      f"波动未稳定, 跳过开仓")
                self._record_execution_event(
                    "OPEN", "skipped", symbol, "LONG" if signal > 0 else "SHORT",
                    "volatile market", f"ATR%={atr_pct_now:.2f}%超上限{max_atr_pct}%",
                )
                return
        # 主力意图闸门: 不接出货中的多头飞刀, 不做洗盘中的空头
        base_score = float(candidate_context.get(
            "base_score", candidate_context.get("score", 0)
        ) or 0)
        min_base_score = self._auto_entry_min_base_score()
        if not force and not candidate_context.get("is_autonomous") and abs(base_score) < min_base_score:
            reason = (
                f"base technical score {base_score:.1f} is below "
                f"the auto-entry minimum {min_base_score:.1f}"
            )
            print(f"[??????] {symbol}: {reason}")
            self._record_execution_event(
                "OPEN", "skipped", symbol, "LONG" if signal > 0 else "SHORT",
                "base technical score gate", reason,
                base_score=round(base_score, 4),
                required_base_score=round(min_base_score, 4),
                adjusted_score=round(float(candidate_context.get("score", 0) or 0), 4),
            )
            return
        _rec = candidate_context.get("recommendation") or {}
        _rec_intent = _rec.get("intent")
        _rec_conf = int(_rec.get("intent_confidence") or 0)
        if signal == 1 and _rec_intent == "出货" and _rec_conf >= 55:
            print(f"[主力意图] {symbol} 疑似主力出货(置信{_rec_conf}%), 放弃做多入场")
            self._record_execution_event(
                "OPEN", "skipped", symbol, "LONG",
                "疑似主力出货", f"意图置信度{_rec_conf}%",
            )
            return
        if signal == -1 and _rec_intent in ("洗盘", "吸筹") and _rec_conf >= 55:
            print(f"[主力意图] {symbol} 主力{_rec_intent}中(置信{_rec_conf}%), 放弃做空入场")
            self._record_execution_event(
                "OPEN", "skipped", symbol, "SHORT",
                f"主力{_rec_intent}中", f"意图置信度{_rec_conf}%",
            )
            return
        try:
            smart = candidate_context.get("smart_money")
            if not smart:
                smart = await self._smart_money_snapshot(symbol)
                candidate_context["smart_money"] = smart
            smart_decision = candidate_context.get("smart_money_decision") or self._smart_money_decision(signal, smart)
            candidate_context["smart_money_decision"] = smart_decision
            if not smart_decision.get("pass", True):
                print(f"[聪明钱过滤] {symbol} {'LONG' if signal > 0 else 'SHORT'}: {smart_decision.get('reason')}")
                return

            # TypeSafe Jev (System One) 决策审查门禁 / 双引擎模式 (兼容 typesafe_evaluator / typesafe_jev / typesafe_hybrid)
            ts_enabled = (self.entry_decision_mode in ("typesafe_jev", "typesafe_evaluator", "typesafe_hybrid", "hybrid")) or bool(self.typesafe_engine.enabled)
            if not force and ts_enabled:
                if "typesafe_review" in candidate_context:
                    review = candidate_context["typesafe_review"]
                else:
                    closes_recent = (self.klines_cache.get(symbol, {}).get("closes") or [])[-8:]
                    fr = self.funding_rates.get(symbol)
                    review = await self.typesafe_engine.evaluate_entry(
                        symbol=symbol,
                        candidate_signal=signal,
                        price=price,
                        candidate_context=candidate_context,
                        recent_closes=closes_recent,
                        funding_rate=fr,
                    )
                    self.typesafe_reviews_log.append({
                        "timestamp": time.time(),
                        "symbol": symbol,
                        "signal": signal,
                        "review": review,
                    })
                    if len(self.typesafe_reviews_log) > 200:
                        self.typesafe_reviews_log = self.typesafe_reviews_log[-200:]

                if not review.get("approved", False):
                    reason = review.get("reason", "TypeSafe Jev rejected entry")
                    print(f"[TypeSafe Jev 拦截] {symbol} {'LONG' if signal > 0 else 'SHORT'}: {reason} (耗时: {review.get('latency_ms', 0)}ms)")
                    self._record_execution_event(
                        "OPEN", "skipped", symbol, "LONG" if signal > 0 else "SHORT",
                        "TypeSafe Jev Gate", reason,
                        confidence=review.get("confidence"),
                        risk_score=review.get("risk_level_score"),
                        breakout_score=review.get("breakout_quality_score"),
                    )
                    return
                is_auto = candidate_context.get("is_autonomous", False)
                tag_label = " [Jev主动猎手]" if is_auto else " [Jev守门放行]"
                print(f"[TypeSafe Jev 通过{tag_label}] {symbol} {'LONG' if signal > 0 else 'SHORT'} 置信度={review.get('confidence', 0):.2f}, 复合分={review.get('composite_score', 'N/A')}, 耗时={review.get('latency_ms', 0)}ms")
                candidate_context["typesafe_review"] = review

            # 策略直连 / Jev审核通过: 信号通过聪明钱与AI校验后进入下单流程
            if self.auto_trade:
                mode_desc = "Jev自主猎手出击" if candidate_context.get("is_autonomous") else ("TypeSafe Jev通过" if ts_enabled else "策略直连")
                print(f"[{mode_desc}] {symbol} {'LONG' if signal > 0 else 'SHORT'} 评分{candidate_context.get('score', 0)} → 进入执行流程")

            positions = await self.client.get_positions()
            open_positions = [p for p in positions if float(p["positionAmt"]) != 0]

            # Position guard: 优先用内存态tp_state判断(不依赖网络)。
            # 2026-08-14 CYSUSDT教训: 网络断连时get_positions返回空,
            # guard失效导致同币同方向二次开仓(19:33开空后19:41又开空,
            # 最终-0.54U止损)。
            st_existing = self.tp_state.get(symbol)
            if st_existing:
                st_side = str(st_existing.get("side") or "")
                same_dir = (signal == 1 and st_side == "LONG") or (signal == -1 and st_side == "SHORT")
                if same_dir:
                    print(f"[Position guard] {symbol} tp_state已有同方向仓位({st_side}), 拒绝二次开仓")
                    self._record_execution_event(
                        "OPEN", "skipped", symbol, "LONG" if signal == 1 else "SHORT",
                        "same-direction position in tp_state", "内存态已有同方向仓位",
                    )
                    return
            # 同币浮亏禁开: 交易所侧该币有任何方向仓位且浮亏, 拒绝新信号单
            for p in open_positions:
                if p["symbol"] != symbol:
                    continue
                amt = float(p["positionAmt"])
                same_direction = (signal == 1 and amt > 0) or (signal == -1 and amt < 0)
                if same_direction:
                    upnl = float(p.get("unRealizedProfit", 0) or 0)
                    if upnl < 0:
                        print(f"[Position guard] {symbol} 同方向仓位浮亏{upnl:+.4f}U, 拒绝加仓")
                        self._record_execution_event(
                            "OPEN", "skipped", symbol, "LONG" if signal == 1 else "SHORT",
                            "same-direction position underwater",
                            f"浮亏{upnl:+.4f}U",
                        )
                        return
                    print(f"[Position guard] {symbol} already has a same-direction position; skip entry")
                else:
                    print(f"[Position guard] {symbol} has an opposing position; skip automatic hedge entry")
                return

            account = await self.client.get_account()
            balance = float(account["totalWalletBalance"])
            can_open, reason = self.risk.can_open(
                self._bot_managed_position_count(open_positions), balance=balance)
            if not can_open:
                print(f"[风控] 拒绝开仓: {reason}")
                self._record_execution_event(
                    "OPEN", "skipped", symbol, "LONG" if signal == 1 else "SHORT",
                    "daily loss gate", reason,
                    balance=round(balance, 8),
                )
                return

            # 双仓位模式: 保守仓低杠杆小仓位, 激进仓高杠杆标准仓位
            pm = self._position_management_cfg()
            holding_mode = pm.get("holding_mode", "swing")
            swing_leverage_cap = None
            if mode == "profit_bet":
                max_lev = max(2, int(pm.get("swing_max_leverage", 6)))
                swing_leverage_cap = max_lev
                lev = min(int(self._profit_bet_cfg().get("leverage", 6)), max_lev)
                size_pct = 0.0
            elif holding_mode == "swing":
                max_lev = max(2, int(pm.get("swing_max_leverage", 6)))
                swing_leverage_cap = max_lev
                if mode == "aggressive":
                    lev = min(max(self.leverage, 3), max_lev)
                    size_pct = self._entry_size_pct(0.7, 0.07)
                else:
                    lev = min(max(self.leverage // 2, 2), max_lev)
                    size_pct = self._entry_size_pct(0.5, 0.05)
            elif mode == "aggressive":
                lev = min(self.leverage * 2, 20)
                size_pct = self._entry_size_pct(1.0, 0.10)
            else:
                lev = max(self.leverage // 2, 3)
                size_pct = self._entry_size_pct(0.6, 0.06)

            if candidate_context.get("custom_leverage"):
                requested_leverage = int(candidate_context["custom_leverage"])
            else:
                requested_leverage = lev
            try:
                lev, max_leverage = await self.client.clamp_leverage(symbol, requested_leverage)
            except Exception as exc:
                self._record_execution_event(
                    "OPEN", "failed", symbol, "LONG" if signal == 1 else "SHORT",
                    "leverage capability lookup", str(exc),
                    requested_leverage=requested_leverage,
                )
                return
            strategy_leverage_cap = max_leverage
            if swing_leverage_cap is not None:
                strategy_leverage_cap = min(strategy_leverage_cap, swing_leverage_cap)
            lev = min(lev, strategy_leverage_cap)
            if candidate_context.get("custom_notional"):
                notional = float(candidate_context["custom_notional"])
                margin = float(candidate_context.get("custom_margin") or (notional / lev if lev else notional))
            elif mode == "profit_bet":
                bet = candidate_context.get("profit_bet") or {}
                notional = max(5.0, float(bet.get("target_notional", 0) or 0))
                margin = notional / lev if lev else notional
            else:
                notional = self._planned_entry_notional(balance, size_pct, lev)
                margin = notional / lev if lev else notional
            execution_cfg = self._execution_cfg()
            min_notional_buffer = max(0.0, float(
                execution_cfg.get("min_notional_buffer_pct", 2.0)
            ))
            max_overshoot = max(0.0, float(
                execution_cfg.get("max_notional_overshoot_pct", 15.0)
            ))
            requested_qty = notional / price if price > 0 else 0
            qty = await self.client.quantity_for_notional(
                symbol, price, notional * (1 + min_notional_buffer / 100)
            )
            planned_notional = qty * price
            if mode == "profit_bet":
                bet = candidate_context.get("profit_bet") or {}
                planned_risk = planned_notional * float(
                    bet.get("stop_pct", 0) or 0) / 100
                risk_budget = float(bet.get("risk_budget", 0) or 0)
                if risk_budget <= 0 or planned_risk > risk_budget * 1.05:
                    self._record_execution_event(
                        "OPEN", "skipped", symbol,
                        "LONG" if signal == 1 else "SHORT",
                        "profit bet exceeds daily profit risk budget",
                        planned_notional=round(planned_notional, 8),
                        planned_risk=round(planned_risk, 8),
                        risk_budget=round(risk_budget, 8),
                    )
                    return
            if qty <= 0:
                self._record_execution_event(
                    "OPEN", "skipped", symbol, "LONG" if signal == 1 else "SHORT",
                    "invalid normalized quantity",
                    requested_qty=requested_qty, normalized_qty=qty,
                    requested_notional=round(notional, 8),
                    planned_notional=round(planned_notional, 8),
                )
                return
            # 仓位控制硬上限: 拒绝任何会演变成全仓猛干的下单
            risk_cfg = self.cfg.get("risk", {})
            max_pos_mult = float(risk_cfg.get("max_position_notional_multiple", 6))
            max_tot_mult = float(risk_cfg.get("max_total_notional_multiple", 8))
            if planned_notional > balance * max_pos_mult:
                self._record_execution_event(
                    "OPEN", "skipped", symbol, "LONG" if signal == 1 else "SHORT",
                    "position notional exceeds account cap",
                    requested_qty=requested_qty, normalized_qty=qty,
                    planned_notional=round(planned_notional, 8),
                    balance_cap=round(balance * max_pos_mult, 6),
                )
                print(f"[仓位控制] {symbol} 名义{planned_notional:.1f}U 超过账户上限"
                      f"{balance * max_pos_mult:.1f}U({max_pos_mult}倍余额), 放弃开仓")
                return
            open_notional = sum(
                abs(float(p["positionAmt"])) * float(p.get("markPrice") or p.get("entryPrice") or 0)
                for p in open_positions)
            if open_notional + planned_notional > balance * max_tot_mult:
                self._record_execution_event(
                    "OPEN", "skipped", symbol, "LONG" if signal == 1 else "SHORT",
                    "total notional exceeds account cap",
                    requested_qty=requested_qty, normalized_qty=qty,
                    planned_notional=round(planned_notional, 8),
                    open_notional=round(open_notional, 6),
                    total_cap=round(balance * max_tot_mult, 6),
                )
                print(f"[仓位控制] {symbol} 持仓总名义将达{open_notional + planned_notional:.1f}U, "
                      f"超过总上限{balance * max_tot_mult:.1f}U({max_tot_mult}倍余额), 放弃开仓")
                return
            # 小资金适配: 交易所最小名义(低价币多为50U)远超计划时, 抬杠杆压缩保证金而非放弃
            max_entry_margin_pct = float(pm.get("max_entry_margin_pct", 25.0))
            max_entry_margin = balance * min(
                0.95, max(0.05, max_entry_margin_pct / 100)
            )
            margin_over_budget = (
                planned_notional / lev > max_entry_margin
                if lev and max_entry_margin > 0 else True
            )
            if (
                planned_notional > notional * (1 + max_overshoot / 100)
                or margin_over_budget
            ):
                leverage_plan = self._minimum_notional_leverage_plan(
                    planned_notional, balance, lev, strategy_leverage_cap,
                    max_entry_margin_pct,
                )
                needed_lev = leverage_plan["required_leverage"]
                if not leverage_plan["allowed"]:
                    self._record_execution_event(
                        "OPEN", "skipped", symbol, "LONG" if signal == 1 else "SHORT",
                        "exchange minimum order exceeds strategy leverage or margin budget",
                        requested_qty=requested_qty, normalized_qty=qty,
                        requested_notional=round(notional, 8),
                        planned_notional=round(planned_notional, 8),
                        needed_leverage=needed_lev,
                        strategy_leverage_cap=strategy_leverage_cap,
                        exchange_leverage_cap=max_leverage,
                        max_entry_margin=round(leverage_plan["max_margin"], 8),
                    )
                    print(
                        f"[??????] {symbol} ?{needed_lev}x???????????"
                        f"{leverage_plan['max_margin']:.2f}U????????"
                        f"{strategy_leverage_cap}x?????"
                    )
                    return
                lev = leverage_plan["leverage"]
                print(
                    f"[?????] {symbol} ???????{planned_notional:.1f}U -> "
                    f"??{lev}x, ????{leverage_plan['margin']:.2f}U"
                )
            margin = planned_notional / lev if lev else planned_notional
            max_entry_margin = balance * min(
                0.95, max(0.05, float(pm.get("max_entry_margin_pct", 25.0)) / 100)
            )
            if margin > max_entry_margin:
                self._record_execution_event(
                    "OPEN", "skipped", symbol, "LONG" if signal == 1 else "SHORT",
                    "margin exceeds strategy entry budget",
                    requested_qty=requested_qty, normalized_qty=qty,
                    requested_notional=round(notional, 8),
                    planned_notional=round(planned_notional, 8),
                    leverage=lev, available_balance=round(balance, 6),
                    max_entry_margin=round(max_entry_margin, 6),
                )
                return

            # ===== 终极执行层硬风控门禁 (Universal Execution Risk Gate) =====
            rec_sl = float((candidate_context.get("recommendation") or {}).get("sl") or 0)
            passed_gate, effective_lev, gate_reason, gate_details = self.risk.check_execution_risk_gate(
                symbol=symbol,
                side="LONG" if signal > 0 else "SHORT",
                price=price,
                quantity=qty,
                requested_leverage=lev,
                balance=balance,
                open_positions=open_positions,
                sl_price=rec_sl if rec_sl > 0 else None,
                data_last_updated_ts=self.last_market_data_ts,
                is_force=force,
            )
            if not passed_gate:
                print(f"🛑 [执行层硬风控一票否决] {symbol}: {gate_reason}")
                self._record_execution_event(
                    "OPEN", "blocked_by_hard_risk_gate", symbol, "LONG" if signal == 1 else "SHORT",
                    "execution_hard_risk_gate", gate_reason, **gate_details
                )
                self.record_decision_snapshot(symbol, signal, "BLOCKED", gate_reason, gate_details)
                return
            lev = effective_lev

            # ===== 模式分级控制: 影子模式 (SHADOW) =====
            if getattr(self, "trading_mode", "") == "SHADOW":
                print(f"👻 [影子模式] 信号完整推演放行，仅记录纸面账本，不下单发往交易所: {symbol} {'多' if signal == 1 else '空'} {qty}")
                shadow_record = {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "symbol": symbol,
                    "side": "多" if signal == 1 else "空",
                    "qty": qty,
                    "price": price,
                    "mode": mode,
                    "leverage": lev,
                    "status": "SHADOW_RECORDED",
                    "_is_shadow": True,
                }
                self.trades_log.append(shadow_record)
                self.record_decision_snapshot(symbol, signal, "SHADOW_RECORDED", "影子模式记账", gate_details)
                return {
                    "ok": True,
                    "symbol": symbol,
                    "side": "LONG" if signal == 1 else "SHORT",
                    "qty": qty,
                    "price": price,
                    "_is_shadow": True,
                }

            # ===== 模式分级控制: 小资金实盘 (MICRO_LIVE) =====
            if getattr(self, "trading_mode", "") == "MICRO_LIVE":
                lev = min(lev, 3)
                if planned_notional > 20.0:
                    planned_notional = 20.0
                    qty = await self.client.quantity_for_notional(symbol, price, 20.0)
                    print(f"🛡️ [小资金实盘] 强制限制单笔名义 ≤20U, 杠杆 ≤3x: {symbol} (当前名义={planned_notional}U)")

            try:
                applied_leverage, _ = await self._prepare_new_position(symbol, lev)
                lev = applied_leverage or lev
            except Exception as exc:
                print(f"[Entry preparation] {symbol} skipped: {exc}")
                self._record_execution_event(
                    "OPEN", "failed", symbol, "LONG" if signal == 1 else "SHORT",
                    "entry preparation", str(exc),
                    requested_qty=requested_qty, normalized_qty=qty,
                    requested_leverage=requested_leverage, max_leverage=max_leverage,
                )
                return

            # 更合适的入场价: 做多挂支撑位, 做空挂压力位(用户要求 2026-08-13)
            _rec = candidate_context.get("recommendation") or {}
            _ind = candidate_context.get("indicators") or {}
            limit_hint = 0.0
            entry_atr = float(_ind.get("atr_pct", 0) or 0) * price / 100
            if entry_atr <= 0:
                entry_atr = float((self.latest_result.get(symbol, {})
                                   .get("indicators", {}) or {}).get("atr") or 0)
            if signal == 1:
                limit_hint = float(_rec.get("support") or 0)
            else:
                limit_hint = float(_rec.get("resistance") or 0)
            if signal == 1:
                order = await self._open_position_maker_first(
                    symbol, "BUY", "LONG", qty, price, execution_cfg,
                    limit_hint=limit_hint, atr=entry_atr)
                side_str = "多"
            else:
                order = await self._open_position_maker_first(
                    symbol, "SELL", "SHORT", qty, price, execution_cfg,
                    limit_hint=limit_hint, atr=entry_atr)
                side_str = "空"

            if order.get("_abandoned"):
                # 限价单等不到支撑/压力位, 主动放弃本轮(不追市价)
                print(f"[入场] {symbol} {side_str} 未等到支撑/压力位, 放弃本轮")
                self._record_execution_event(
                    "OPEN", "skipped", symbol, "LONG" if signal == 1 else "SHORT",
                    "limit entry abandoned", f"未等到{'支撑' if signal == 1 else '压力'}位",
                    limit_hint=round(limit_hint, 8), ref_price=round(price, 8),
                )
                return
            execution = self._order_execution(order)
            actual_qty = execution["executed_qty"]
            side_en = "LONG" if signal == 1 else "SHORT"
            if actual_qty <= 0:
                error = f"exchange returned {execution['status']} with no executed quantity"
                self._record_execution_event(
                    "OPEN", "failed", symbol, side_en, "market entry", error,
                    requested_qty=execution["requested_qty"] or requested_qty,
                    normalized_qty=execution["normalized_qty"] or qty,
                    order_id=execution["order_id"], exchange_status=execution["status"],
                )
                print(f"[order failed] {symbol}: {error}")
                self._mark_open_failure(symbol, error)
                return
            fill_price = execution["avg_price"] if execution["avg_price"] > 0 else price
            outcome = "success" if execution["completed"] else "partial"
            self._record_execution_event(
                "OPEN", outcome, symbol, side_en, "strategy entry",
                requested_qty=execution["requested_qty"] or requested_qty,
                normalized_qty=execution["normalized_qty"] or qty,
                executed_qty=actual_qty, avg_price=fill_price,
                order_id=execution["order_id"], exchange_status=execution["status"],
                requested_notional=round(notional, 8),
                planned_notional=round(planned_notional, 8),
                requested_leverage=requested_leverage, leverage=lev,
                max_leverage=max_leverage,
            )

            trade_record = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "symbol": symbol,
                "side": side_str,
                "qty": actual_qty,
                "price": fill_price,
                "mode": mode,
                "leverage": lev,
                "order_id": execution["order_id"],
                "status": execution["status"],
            }
            self.trades_log.append(trade_record)
            score = float(candidate_context.get(
                "score", self.latest_result.get(symbol, {}).get("score", 0)
            ) or 0)
            self.tp_state[symbol] = {
                "side": side_en, "orig_qty": actual_qty,
                "tp1": False, "tp2": False, "tp3": False,
                "mode": mode, "entry_time": time.time(),
                "add_count": 0, "breakeven_on": False,
                "first_qty": actual_qty,
                "score": round(score, 1),
            }
            smart_snapshot = candidate_context.get("smart_money") or {}
            entry_context = {
                "decision_mode": "strategy_direct",
                "profit_bet": (
                    candidate_context.get("profit_bet")
                    if mode == "profit_bet" else None
                ),
                "base_score": round(base_score, 4),
                "adjusted_score": round(score, 4),
                "required_base_score": round(min_base_score, 4),
                "factors": [str(item) for item in candidate_context.get("factors", [])][:12],
                "smart_money": {
                    "score": smart_snapshot.get("score"),
                    "direction": smart_snapshot.get("direction"),
                    "confidence": smart_snapshot.get("confidence"),
                    "data_quality": smart_snapshot.get("data_quality"),
                },
                "mode": mode,
                "planned_notional": round(planned_notional, 8),
                "entry_margin": round(margin, 8),
                "entry_margin_pct": round(margin / balance * 100, 4) if balance else 0,
                "leverage": lev,
                "strategy_leverage_cap": strategy_leverage_cap,
                "exchange_leverage_cap": max_leverage,
                "order_id": execution["order_id"],
            }
            journal.record_open(
                symbol, side_en, actual_qty, fill_price, lev, round(margin, 2), score,
                order_id=execution["order_id"], entry_context=entry_context,
            )
            # 交易所侧保护单: SL用推荐止损(支撑/压力位修正过), TP用第二目标
            rec = candidate_context.get("recommendation") or {}
            sl_price = float(rec.get("sl") or 0)
            tp_price = float(rec.get("tp2") or rec.get("tp1") or 0)
            valid = sl_price > 0 and tp_price > 0 and (
                (signal == 1 and sl_price < fill_price < tp_price)
                or (signal == -1 and tp_price < fill_price < sl_price))
            if not valid:
                atr_p = float((candidate_context.get("indicators") or {}).get("atr_pct") or 0) or 0.5
                atr_p_price = fill_price * atr_p / 100
                sl_price = fill_price - atr_p_price if signal == 1 else fill_price + atr_p_price
                tp_price = fill_price + atr_p_price * 2.5 if signal == 1 else fill_price - atr_p_price * 2.5
            await self._place_protective_orders(symbol, side_en, sl_price, tp_price)
            mode_cn = (
                "利润博弈" if mode == "profit_bet"
                else ("激进" if mode == "aggressive" else "保守")
            )
            print(f"[order] {side_str} {symbol} qty={actual_qty} status={execution['status']} "
                  f"leverage={lev}x [{mode_cn}] price?{fill_price}")
            return {
                "ok": True,
                "symbol": symbol,
                "side": side_en,
                "qty": actual_qty,
                "price": fill_price,
                "leverage": lev,
                "margin": round(margin, 8),
                "mode": mode,
                "sl": sl_price,
                "tp": tp_price,
                "order_id": execution["order_id"],
                "status": execution["status"],
                "score": round(score, 4),
                "base_score": round(base_score, 4),
            }

        except Exception as e:
            print(f"[order failed] {symbol}: {e}")
            self._record_execution_event(
                "OPEN", "failed", symbol, "LONG" if signal == 1 else "SHORT",
                "strategy entry", str(e),
            )
            self._mark_open_failure(symbol, str(e))

    def _inject_position(self, result: dict, symbol: str) -> dict:
        """用最新持仓上下文刷新分析结果(PnL实时变化, 不依赖技术分析缓存)"""
        pos = self.positions_cache.get(symbol)
        result["position"] = pos
        if pos and result.get("action"):
            try:
                htf_values = np.array(
                    self.swing_cache.get(symbol, [])
                    or self.htf_cache.get(symbol, [])
                )
                htf_trend = detect_ema_ribbon(htf_values) if len(htf_values) >= 55 else 0
                result["position_advice"] = self.analyst._position_advice(
                    result["action"], result.get("confidence", 0), pos,
                    float(result.get("price") or pos["mark_price"]),
                    float(result.get("atr") or 0),
                    result.get("supports", []), result.get("resistances", []),
                    htf_trend, self._position_management_cfg())
                # 同步把"操作建议"段落更新为持仓专属建议
                for sec in result.get("sections", []):
                    if sec.get("title") == "操作建议":
                        sec["text"] = result["position_advice"]["text"]
                        break
            except Exception as e:
                print(f"[持仓建议] {symbol} 异常: {e}")
        else:
            result["position_advice"] = None
        return result

    async def get_analysis(self, symbol: str) -> dict:
        """获取指定币种的AI分析(含新闻+市场情绪)"""
        # 有缓存直接返回(注入最新持仓上下文)
        if symbol in self.analysis_cache:
            return self._inject_position(self.analysis_cache[symbol], symbol)
        # 无缓存则即时分析(支持任意币种,不限于监控列表)
        try:
            klines = await self.client.get_klines(symbol, self.interval, 300)
            closes = np.array([float(k[4]) for k in klines])
            highs = np.array([float(k[2]) for k in klines])
            lows = np.array([float(k[3]) for k in klines])
            volumes = np.array([float(k[5]) for k in klines])
            htf = await self.client.get_klines(symbol, self.htf_interval, 100)
            htf_closes = np.array([float(k[4]) for k in htf])
            fr = None
            try:
                fr_data = await self.client.get_funding_rate(symbol)
                if fr_data:
                    fr = float(fr_data[0]["fundingRate"])
            except Exception:
                pass
            # 拉取新闻和市场情绪(带缓存,不会频繁请求)
            news = []
            sentiment = {}
            try:
                news = await self.news_fetcher.fetch_all()
            except Exception as e:
                print(f"[News] 抓取失败: {e}")
            try:
                sentiment = await self.market_sentiment.get_all(symbol)
            except Exception as e:
                print(f"[Sentiment] 抓取失败: {e}")
            try:
                smart = await self._smart_money_snapshot(
                    symbol, closes=closes, volumes=volumes,
                    funding_rate=fr, price_change_24h=None)
                sentiment["smart_money"] = smart
            except Exception as e:
                print(f"[聪明钱] 分析快照失败: {e}")
            result = self.analyst.analyze(closes, highs, lows, volumes,
                                          funding_rate=fr,
                                          htf_closes=htf_closes if len(htf_closes) >= 55 else None,
                                          news=news, sentiment=sentiment,
                                          position=self.positions_cache.get(symbol),
                                          position_management=self._position_management_cfg())
            self.analysis_cache[symbol] = result
            return self._inject_position(result, symbol)
        except Exception as e:
            return {"summary": f"分析失败: {e}", "sections": [], "action": "观望", "confidence": 0}

    async def get_smart_money(self, symbol: str, force: bool = False) -> dict:
        """获取可视化聪明钱快照；缺少本地K线时即时补齐。"""
        cache = self.klines_cache.get(symbol, {})
        closes = cache.get("closes", [])
        volumes = cache.get("volumes", [])
        if len(closes) < 60:
            klines = await self.client.get_klines(symbol, self.interval, 300)
            closes = np.array([float(k[4]) for k in klines])
            volumes = np.array([float(k[5]) for k in klines])
        funding_rate = self.funding_rates.get(symbol)
        if funding_rate is None:
            try:
                fr_data = await self.client.get_funding_rate(symbol)
                if fr_data:
                    funding_rate = float(fr_data[0]["fundingRate"])
                    self.funding_rates[symbol] = funding_rate
            except Exception:
                pass
        return await self._smart_money_snapshot(
            symbol, closes=closes, volumes=volumes,
            funding_rate=funding_rate, force=force)

    def _sentiment_vs_position(self, pos: dict, sent: dict, fr, fg: dict) -> dict:
        """判断市场情绪利多/利空用户的某个持仓"""
        side = pos["side"]  # LONG / SHORT
        score = 0
        reasons = []

        # 散户多空比(反向指标: 散户拥挤的方向常被反杀)
        ls = sent.get("long_short", {})
        ratio = ls.get("ratio", 1.0)
        long_pct = ls.get("long_pct", 50)
        if side == "SHORT":
            if ratio > 1.3:
                score += 1; reasons.append(f"散户偏多({long_pct:.0f}%做多)，拥挤多头易被砸盘，利你的空单")
            elif ratio < 0.77:
                score -= 1; reasons.append(f"散户偏空({100-long_pct:.0f}%做空)，空头拥挤易反弹，不利你的空单")
        else:
            if ratio < 0.77:
                score += 1; reasons.append(f"散户偏空，拥挤空头易被拉爆，利你的多单")
            elif ratio > 1.3:
                score -= 1; reasons.append(f"散户偏多({long_pct:.0f}%做多)，多头拥挤易回调，不利你的多单")

        # 大户持仓比(跟随聪明钱, 非反向)
        tt = sent.get("top_trader", {}).get("ratio", 1.0)
        if side == "SHORT":
            if tt < 0.83:
                score += 1; reasons.append(f"大户偏空(比值{tt})，与你方向一致")
            elif tt > 1.2:
                score -= 1; reasons.append(f"大户偏多(比值{tt})，与你方向相反")
        else:
            if tt > 1.2:
                score += 1; reasons.append(f"大户偏多(比值{tt})，与你方向一致")
            elif tt < 0.83:
                score -= 1; reasons.append(f"大户偏空(比值{tt})，与你方向相反")

        smart = sent.get("smart_money", {})
        smart_score = float(smart.get("score", 0))
        if smart.get("data_quality", 0) >= 0.5 and abs(smart_score) >= 18:
            smart_side = "LONG" if smart_score > 0 else "SHORT"
            if smart_side == side:
                score += 2
                reasons.append(f"聪明钱综合分{smart_score:+.1f}，与持仓方向共振")
            else:
                score -= 2
                reasons.append(f"聪明钱综合分{smart_score:+.1f}，与持仓方向相反")

        # 资金费率(反向+收付费)
        if fr is not None:
            if side == "SHORT":
                if fr > 0.01:
                    score += 1; reasons.append(f"资金费率{fr*100:.3f}%为正，你做空可收资金费且多头拥挤")
                elif fr < -0.01:
                    score -= 1; reasons.append(f"资金费率{fr*100:.3f}%为负，空头拥挤，你需付资金费")
            else:
                if fr < -0.01:
                    score += 1; reasons.append(f"资金费率{fr*100:.3f}%为负，你做多可收资金费且空头拥挤")
                elif fr > 0.01:
                    score -= 1; reasons.append(f"资金费率{fr*100:.3f}%为正，多头拥挤，你需付资金费")

        # 持仓量变化(波动预警)
        oi_chg = sent.get("open_interest", {}).get("change_24h_pct", 0)
        if abs(oi_chg) > 10:
            reasons.append(f"持仓量24h {oi_chg:+.1f}%，资金大幅异动，波动加剧注意风险")

        # 恐贪指数(全局反向参考)
        fg_val = fg.get("value", 50)
        if fg_val >= 75:
            reasons.append(f"恐贪指数{fg_val}({fg.get('label','')})，市场过热逆向偏空")
        elif fg_val <= 25:
            reasons.append(f"恐贪指数{fg_val}({fg.get('label','')})，市场恐慌逆向偏多")

        if score >= 1:
            label, cls = "利多你的持仓", "good"
        elif score <= -1:
            label, cls = "利空你的持仓", "danger"
        else:
            label, cls = "情绪中性", "neutral"
        return {"label": label, "cls": cls, "score": score, "reasons": reasons}

    async def get_position_sentiment(self) -> list:
        """并发获取每个持仓的市场情绪, 并判定是否利多/利空该持仓"""
        if not self.positions_cache:
            return []
        try:
            fg = await self.market_sentiment.get_fear_greed()
        except Exception:
            fg = {"value": 50, "label": "未知", "interpretation": ""}

        async def one(sym: str, pos: dict) -> dict:
            fr = self.funding_rates.get(sym)
            smart = await self._smart_money_snapshot(sym, funding_rate=fr)
            ls = smart.get("long_short", {})
            ta = smart.get("top_trader_account", {})
            tt = smart.get("top_trader", {})
            oi = smart.get("open_interest", {})
            sent = {
                "long_short": ls, "top_trader_account": ta,
                "top_trader": tt, "open_interest": oi, "smart_money": smart,
            }
            return {
                "symbol": sym, "side": pos["side"],
                "unrealized_pnl": pos["unrealized_pnl"],
                "long_short": ls, "top_trader_account": ta,
                "top_trader": tt, "open_interest": oi,
                "smart_money": smart,
                "funding_rate": fr,
                "verdict": self._sentiment_vs_position(pos, sent, fr, fg),
            }

        try:
            return list(await asyncio.gather(
                *[one(s, p) for s, p in self.positions_cache.items()]))
        except Exception as e:
            print(f"[持仓情绪] 异常: {e}")
            return []

    async def get_news(self) -> dict:
        """获取新闻列表+情绪统计+持仓情绪"""
        try:
            news = await self.news_fetcher.fetch_all()
            summary = self.news_fetcher.get_sentiment_summary()
            positions_sentiment = await self.get_position_sentiment()
            return {"news": news, "summary": summary, "positions_sentiment": positions_sentiment}
        except Exception as e:
            return {"news": [], "summary": {}, "positions_sentiment": [], "error": str(e)}

    async def sync_trade_journal(self, date_str: str = None,
                                 force: bool = False) -> dict:
        """Synchronize fills from the configured Binance futures account."""
        date_str = date_str or datetime.now().strftime("%Y-%m-%d")
        cached = self._trade_sync_cache.get(date_str)
        if cached and not force and time.time() - cached[0] < 30:
            return cached[1]

        try:
            day_start = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return {"success": False, "error": "日期格式应为 YYYY-MM-DD"}
        day_end = day_start + timedelta(days=1)
        start_ms = int(day_start.timestamp() * 1000)
        end_ms = int(day_end.timestamp() * 1000) - 1
        if date_str == datetime.now().strftime("%Y-%m-%d"):
            server_now = int(time.time() * 1000) + self.client.time_offset
            end_ms = min(end_ms, server_now)

        try:
            commission_rows, realized_rows = await asyncio.gather(
                self.client.get_income_history(
                    "COMMISSION", start_time=start_ms, end_time=end_ms),
                self.client.get_income_history(
                    "REALIZED_PNL", start_time=start_ms, end_time=end_ms),
            )
            symbols = {
                r.get("symbol") for r in commission_rows + realized_rows
                if r.get("symbol")
            }
            symbols.update(self.position_symbols)
            symbols.update(
                r.get("symbol") for r in journal.get_day_records(date_str)
                if r.get("symbol")
            )

            fills = []
            errors = {}
            for symbol in sorted(symbols):
                try:
                    rows = await self.client.get_user_trades(
                        symbol, limit=1000,
                        start_time=start_ms, end_time=end_ms)
                    fills.extend(
                        row for row in rows
                        if start_ms <= int(row.get("time", 0)) <= end_ms
                    )
                except Exception as exc:
                    errors[symbol] = str(exc)[:180]
                await asyncio.sleep(0.05)

            grouped = {}
            for fill in fills:
                symbol = str(fill.get("symbol", ""))
                trade_side = str(fill.get("side", "")).upper()
                position_side = str(fill.get("positionSide", "BOTH")).upper()
                realized_pnl = float(fill.get("realizedPnl", 0) or 0)

                if position_side == "LONG":
                    record_type = "open" if trade_side == "BUY" else "close"
                    side = "LONG"
                elif position_side == "SHORT":
                    record_type = "open" if trade_side == "SELL" else "close"
                    side = "SHORT"
                elif realized_pnl != 0:
                    record_type = "close"
                    side = "LONG" if trade_side == "SELL" else "SHORT"
                else:
                    record_type = "open"
                    side = "LONG" if trade_side == "BUY" else "SHORT"

                order_id = fill.get("orderId") or fill.get("id")
                key = (symbol, str(order_id), record_type, side)
                item = grouped.setdefault(key, {
                    "symbol": symbol,
                    "order_id": order_id,
                    "type": record_type,
                    "side": side,
                    "qty": 0.0,
                    "value": 0.0,
                    "pnl": 0.0,
                    "commission": 0.0,
                    "commission_asset": fill.get("commissionAsset", "USDT"),
                    "timestamp_ms": int(fill.get("time", 0)),
                    "trade_ids": [],
                })
                qty = float(fill.get("qty", 0) or 0)
                price = float(fill.get("price", 0) or 0)
                commission_asset = str(fill.get("commissionAsset", "USDT"))
                item["qty"] += qty
                item["value"] += qty * price
                item["pnl"] += realized_pnl
                if commission_asset in {"USDT", "USDC"}:
                    item["commission"] += abs(
                        float(fill.get("commission", 0) or 0))
                item["timestamp_ms"] = min(
                    item["timestamp_ms"], int(fill.get("time", 0)))
                item["trade_ids"].append(fill.get("id"))

            external_records = []
            for item in grouped.values():
                qty = item["qty"]
                if qty <= 0:
                    continue
                price = item["value"] / qty
                stamp = item["timestamp_ms"]
                occurred = datetime.fromtimestamp(stamp / 1000)
                base = {
                    "type": item["type"],
                    "time": occurred.strftime("%H:%M:%S"),
                    "timestamp": int(stamp / 1000),
                    "symbol": item["symbol"],
                    "side": item["side"],
                    "qty": round(qty, 8),
                    "commission": round(item["commission"], 8),
                    "commission_asset": item["commission_asset"],
                    "source": "binance",
                    "external_id": (
                        f"binance:{item['symbol']}:{item['order_id']}:"
                        f"{item['type']}:{item['side']}"
                    ),
                    "order_id": item["order_id"],
                    "trade_ids": item["trade_ids"],
                }
                if item["type"] == "open":
                    base.update({
                        "price": round(price, 8),
                        "leverage": 0,
                        "margin": 0,
                        "score": 0,
                        "reason": "币安成交同步",
                    })
                else:
                    pnl = item["pnl"]
                    if item["side"] == "LONG":
                        entry_price = price - pnl / qty
                    else:
                        entry_price = price + pnl / qty
                    pnl_pct = (
                        pnl / (entry_price * qty) * 100
                        if entry_price > 0 and qty > 0 else 0
                    )
                    base.update({
                        "entry_price": round(entry_price, 8),
                        "exit_price": round(price, 8),
                        "reason": "币安成交同步",
                        "pnl": round(pnl, 8),
                        "pnl_pct": round(pnl_pct, 4),
                    })
                external_records.append(base)

            merge_result = journal.merge_external_records(
                date_str, external_records)
            result = {
                "success": True,
                "date": date_str,
                "symbols": len(symbols),
                "fills": len(fills),
                "orders": len(external_records),
                "errors": errors,
                "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                **merge_result,
            }
        except Exception as exc:
            result = {
                "success": False,
                "date": date_str,
                "error": str(exc)[:300],
                "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        self._trade_sync_cache[date_str] = (time.time(), result)
        return result

    async def _collect_report_data(self, date_str: str = None) -> dict:
        """汇总某日交易数据: 配对成交 + K线/MA/量价结构/主力意图 + 复盘要点"""
        date_str = date_str or datetime.now().strftime("%Y-%m-%d")
        try:
            await self.sync_trade_journal(date_str)
        except Exception as e:
            print(f"[报表导出] 同步币安成交失败, 使用本地记录: {e}")
        records = [dict(r) for r in journal._load(date_str)]

        # 配对开平仓(FIFO): 开仓单与后续平仓单配成完整交易
        trades = []
        open_queue: dict = {}
        for r in records:
            if r.get("type") == "open":
                open_queue.setdefault((r.get("symbol"), r.get("side")), []).append(r)
            elif r.get("type") == "close":
                key = (r.get("symbol"), r.get("side"))
                queue = open_queue.get(key) or []
                o = queue.pop(0) if queue else None
                trades.append({
                    "symbol": r.get("symbol"), "side": r.get("side"),
                    "qty": float(r.get("qty") or 0),
                    "entry_time": (o or {}).get("time"),
                    "entry_ts": int((o or {}).get("timestamp") or 0),
                    "entry_price": float((o or {}).get("price") or r.get("entry_price") or 0),
                    "exit_time": r.get("time"), "exit_ts": int(r.get("timestamp") or 0),
                    "exit_price": float(r.get("exit_price") or 0),
                    "pnl": round(float(r.get("pnl") or 0), 4),
                    "pnl_pct": float(r.get("pnl_pct") or 0),
                    "commission": float(r.get("commission") or 0),
                    "leverage": (o or {}).get("leverage"),
                    "reason": r.get("reason") or "",
                    "status": "已平仓" if o else "已平仓(外部开仓)",
                })
        for (sym, side), queue in open_queue.items():
            for o in queue:
                trades.append({
                    "symbol": sym, "side": side, "qty": float(o.get("qty") or 0),
                    "entry_time": o.get("time"), "entry_ts": int(o.get("timestamp") or 0),
                    "entry_price": float(o.get("price") or 0),
                    "exit_time": None, "exit_ts": 0, "exit_price": None,
                    "pnl": 0.0, "pnl_pct": 0.0,
                    "commission": float(o.get("commission") or 0),
                    "leverage": o.get("leverage"), "reason": "", "status": "持仓中",
                })
        trades.sort(key=lambda t: t.get("exit_ts") or t.get("entry_ts") or 0)

        closed = [t for t in trades if t["exit_ts"]]
        wins = [t for t in closed if t["pnl"] > 0]
        net_pnl = round(sum(t["pnl"] for t in closed), 4)
        commission = round(sum(t["commission"] for t in trades), 4)
        summary = {
            "date": date_str,
            "closed": len(closed),
            "open_left": len(trades) - len(closed),
            "wins": len(wins),
            "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else 0.0,
            "net_pnl": net_pnl,
            "commission": commission,
        }
        cum = 0.0
        pnl_series = []
        for t in closed:
            cum += t["pnl"]
            pnl_series.append({
                "label": f'{(t["exit_time"] or "")[:5]} {t["symbol"].replace("USDT", "")}',
                "pnl": t["pnl"], "cum": round(cum, 4),
            })

        symbols = []
        for t in trades:
            if t["symbol"] not in symbols:
                symbols.append(t["symbol"])
        sem = asyncio.Semaphore(4)

        async def fetch_one(sym):
            async with sem:
                sym_trades = [t for t in trades if t["symbol"] == sym]
                ts_all = [t["entry_ts"] for t in sym_trades if t["entry_ts"]] + \
                         [t["exit_ts"] for t in sym_trades if t["exit_ts"]]
                if not ts_all:
                    return None
                start_ms = (min(ts_all) - 12 * 3600) * 1000  # 前推12h上下文: 足够算MA99与主力意图
                end_ms = (max(ts_all) + 3600) * 1000
                try:
                    klines = await self.client.get_klines(
                        sym, self.interval, 1000, start_time=start_ms, end_time=end_ms)
                except Exception as e:
                    print(f"[报表导出] {sym} K线获取失败: {e}")
                    return None
                ks = [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])]
                      for k in klines]
                marks = []
                for t in sym_trades:
                    if t["entry_ts"]:
                        marks.append({
                            "ts": t["entry_ts"] * 1000, "price": t["entry_price"],
                            "label": "开多" if t["side"] == "LONG" else "开空",
                            "color": "#f0b90b",
                        })
                    if t["exit_ts"]:
                        marks.append({
                            "ts": t["exit_ts"] * 1000, "price": t["exit_price"],
                            "label": f'{t["pnl"]:+.3f}U',
                            "color": "#2ebd85" if t["pnl"] >= 0 else "#f6465d",
                        })
                closes_arr = np.array([k[4] for k in ks])
                highs_arr = np.array([k[2] for k in ks])
                lows_arr = np.array([k[3] for k in ks])
                vols_arr = np.array([k[5] for k in ks])
                opens_arr = np.array([k[1] for k in ks])
                # 窗口量价结构: 放量下跌 / 缩量下跌 / ...
                bull = closes_arr >= opens_arr
                up_vol = float(np.mean(vols_arr[bull])) if bull.any() else 0.0
                dn_vol = float(np.mean(vols_arr[~bull])) if (~bull).any() else 0.0
                vol_ratio = round(dn_vol / up_vol, 2) if up_vol > 0 else 1.0
                chg_pct = round((closes_arr[-1] / closes_arr[0] - 1) * 100, 2) if len(ks) else 0.0
                if vol_ratio >= 1.3:
                    vol_feature = "放量下跌" if chg_pct < 0 else "放量换手"
                elif vol_ratio <= 0.75:
                    vol_feature = "缩量下跌" if chg_pct < 0 else "缩量整理"
                else:
                    vol_feature = "量价均衡"
                # 窗口末端主力意图
                if len(ks) >= 60:
                    atr_tail = float(calc_atr(highs_arr, lows_arr, closes_arr, 14)[-1])
                    intent_w = detect_main_force_intent(
                        closes_arr, highs_arr, lows_arr, vols_arr, opens_arr, atr_tail)
                else:
                    intent_w = {"intent": "观望", "confidence": 0, "reasons": []}
                realized = round(sum(t["pnl"] for t in sym_trades if t["exit_ts"]), 4)
                return {
                    "symbol": sym, "klines": ks, "marks": marks, "trades": sym_trades,
                    "vols": [k[5] for k in ks],
                    "ma7": _rolling_ma([k[4] for k in ks], 7),
                    "ma25": _rolling_ma([k[4] for k in ks], 25),
                    "ma99": _rolling_ma([k[4] for k in ks], 99),
                    "vol_feature": vol_feature, "vol_ratio": vol_ratio,
                    "chg_pct": chg_pct,
                    "intent": intent_w.get("intent"),
                    "intent_confidence": intent_w.get("confidence"),
                    "intent_reasons": intent_w.get("reasons", []),
                    "realized": realized,
                }

        results = await asyncio.gather(*[fetch_one(s) for s in symbols])
        symbol_payloads = [r for r in results if r]

        # 复盘要点
        notes = []
        if closed:
            best = max(closed, key=lambda t: t["pnl"])
            notes.append(f'最佳一笔: {best["symbol"]} {(best["exit_time"] or "")[:5]} {best["pnl"]:+.4f}U ({best["reason"] or "无理由"})')
            losing = [t for t in closed if t["pnl"] < 0]
            if losing:
                worst = min(losing, key=lambda t: t["pnl"])
                notes.append(f'最差一笔: {worst["symbol"]} {(worst["exit_time"] or "")[:5]} {worst["pnl"]:+.4f}U')
            else:
                notes.append(f"全部{len(closed)}笔平仓均盈利, 胜率{summary['win_rate']}%")
        for sp in symbol_payloads:
            if sp["vol_feature"] == "放量下跌":
                notes.append(f'{sp["symbol"]} 窗口内放量下跌(阴量/阳量={sp["vol_ratio"]}), 主力派发嫌疑, 规避追多')
            elif sp["vol_feature"] == "缩量下跌":
                notes.append(f'{sp["symbol"]} 缩量下跌(阴量/阳量={sp["vol_ratio"]}), 抛压衰竭, 关注企稳结构')
            if sp["intent"] == "出货" and (sp["intent_confidence"] or 0) >= 55:
                notes.append(f'{sp["symbol"]} 判定主力出货({sp["intent_confidence"]}%): ' + "; ".join(sp["intent_reasons"][:2]))
            elif sp["intent"] in ("洗盘", "吸筹") and (sp["intent_confidence"] or 0) >= 55:
                notes.append(f'{sp["symbol"]} 判定主力{sp["intent"]}({sp["intent_confidence"]}%): ' + "; ".join(sp["intent_reasons"][:2]))
        if summary["open_left"]:
            notes.append(f"尚有{summary['open_left']}笔持仓未平, 交易所侧保护单仍在岗")

        symbol_summary = [{
            "symbol": sp["symbol"], "chg_pct": sp["chg_pct"],
            "vol_feature": sp["vol_feature"], "vol_ratio": sp["vol_ratio"],
            "intent": sp["intent"], "intent_confidence": sp["intent_confidence"],
            "realized": sp["realized"],
            "trade_count": len([t for t in sp["trades"] if t["exit_ts"]]),
        } for sp in symbol_payloads]

        return {
            "summary": summary,
            "pnl_series": pnl_series,
            "symbols": symbol_payloads,
            "symbol_summary": symbol_summary,
            "notes": notes,
            "trades_all": trades,
        }

    async def export_html_report(self, date_str: str = None) -> str:
        """导出每日交易记录为独立HTML图表: 币安风格K线+买卖点+每日总结"""
        data = await self._collect_report_data(date_str)
        return HTML_REPORT_TEMPLATE.replace(
            "__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))

    async def export_md_report(self, date_str: str = None) -> str:
        """导出每日总结为Markdown(供知识库导入)"""
        data = await self._collect_report_data(date_str)
        s = data["summary"]
        lines = [f"# 每日交易总结 · {s['date']}", ""]
        lines += ["## 概览", ""]
        lines.append(f"- 平仓笔数: {s['closed']} (胜 {s['wins']} / 负 {s['closed'] - s['wins']}), 胜率 {s['win_rate']}%")
        lines.append(f"- 净盈亏: {s['net_pnl']:+.4f} U | 手续费: {s['commission']:.4f} U | 未平仓: {s['open_left']}")
        if data["trades_all"]:
            lines += ["", "## 成交明细", "",
                      "| 时间 | 币种 | 方向 | 数量 | 开仓价 | 平仓价 | 盈亏U | 盈亏% | 理由 |",
                      "|---|---|---|---|---|---|---|---|---|"]
            for t in data["trades_all"]:
                when = t["exit_time"] or t["entry_time"] or "--"
                status_note = "" if t["exit_ts"] else " (持仓中)"
                lines.append(
                    f"| {when} | {t['symbol']} | {'多' if t['side'] == 'LONG' else '空'} | "
                    f"{t['qty']} | {t['entry_price'] or '--'} | {t['exit_price'] if t['exit_price'] else '--'} | "
                    f"{t['pnl']:+.4f}{status_note} | {t['pnl_pct']:+.2f}% | {t['reason'] or '--'} |")
        if data["symbol_summary"]:
            lines += ["", "## 分币种量价结构与主力意图", ""]
            for sp in data["symbol_summary"]:
                src = next((x for x in data["symbols"] if x["symbol"] == sp["symbol"]), {})
                lines.append(f"### {sp['symbol']}")
                lines.append(f"- 近12h涨跌: {sp['chg_pct']:+.2f}% | 已实现盈亏: {sp['realized']:+.4f} U | 平仓{sp['trade_count']}笔")
                lines.append(f"- 量价特征: **{sp['vol_feature']}** (阴量/阳量={sp['vol_ratio']})")
                reasons = "; ".join((src.get("intent_reasons") or [])[:3]) or "结构不明"
                lines.append(f"- 主力意图: **{sp['intent']}** ({sp['intent_confidence']}%) — {reasons}")
                lines.append("")
        if data["notes"]:
            lines += ["## 复盘要点", ""]
            lines += [f"- {n}" for n in data["notes"]]
        lines += ["", "---", f"*由量化交易机器人自动生成 · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"]
        return "\n".join(lines)

    async def manual_order(self, symbol: str, side: str, qty: float):
        """Place a user-requested market order and retain its exchange fill result."""
        symbol = self._normalize_symbols([symbol])[0] if self._normalize_symbols([symbol]) else ""
        if not self._trade_symbol_allowed(symbol):
            return {"error": f"{symbol or 'symbol'} is not in the selected trading universe"}
        liquidity = await self._liquidity_snapshot(symbol)
        if not liquidity.get("allowed", False):
            return {"error": f"{symbol} liquidity filter blocked the order: {liquidity.get('reason', '')}"}
        if getattr(self, "trading_mode", "") == "READONLY":
            return {"error": "系统当前处于只读模式(READONLY)，已物理锁定下单功能"}

        account = await self.client.get_account()
        balance = float(account.get("totalWalletBalance", 0))
        open_positions = await self.client.get_positions()
        
        # 获取当前市价
        ref_price = 0.0
        try:
            k_cache = self.latest_klines.get(symbol) or {}
            ref_price = float(k_cache.get("close", 0))
            if ref_price <= 0:
                ticker = await self.client.get_ticker(symbol)
                ref_price = float(ticker.get("lastPrice", 0))
        except Exception:
            pass

        passed, eff_lev, gate_reason, gate_details = self.risk.check_execution_risk_gate(
            symbol=symbol,
            side=side_en,
            price=ref_price or 1.0,
            quantity=qty,
            requested_leverage=self.leverage,
            balance=balance,
            open_positions=open_positions,
            data_last_updated_ts=self.last_market_data_ts,
            is_force=True,
        )
        if not passed:
            self._record_execution_event(
                "MANUAL_OPEN", "blocked_by_hard_risk_gate", symbol, side_en,
                reason="hard_risk_gate", gate_reason=gate_reason,
            )
            return {"error": f"执行层硬风控拦截: {gate_reason}"}

        try:
            await self._prepare_new_position(symbol, eff_lev)
            if side == "BUY":
                order = await self.client.market_open_long(symbol, qty)
            else:
                order = await self.client.market_open_short(symbol, qty)
            execution = self._order_execution(order)
            outcome = "success" if execution["completed"] else (
                "partial" if execution["executed_qty"] > 0 else "failed"
            )
            self._record_execution_event(
                "MANUAL_OPEN", outcome, symbol, side_en, "manual order",
                requested_qty=execution["requested_qty"] or qty,
                normalized_qty=execution["normalized_qty"],
                executed_qty=execution["executed_qty"],
                avg_price=execution["avg_price"], order_id=execution["order_id"],
                exchange_status=execution["status"],
            )
            if execution["executed_qty"] <= 0:
                return {"error": f"exchange returned {execution['status']} with no executed quantity",
                        **execution}
            fill_price = execution["avg_price"] if execution["avg_price"] > 0 else ref_price
            self.tp_state[symbol] = {
                "side": side_en, "orig_qty": execution["executed_qty"],
                "tp1": False, "tp2": False, "tp3": False,
                "mode": "conservative", "entry_time": time.time(),
            }
            # 交易所端硬保护单自动兜底 (按配置止损%计算)
            if fill_price > 0:
                sl_pct = self.risk.stop_loss_pct / 100.0
                tp_pct = self.risk.take_profit_pct / 100.0
                if side_en == "LONG":
                    sl_p = fill_price * (1.0 - sl_pct)
                    tp_p = fill_price * (1.0 + tp_pct)
                else:
                    sl_p = fill_price * (1.0 + sl_pct)
                    tp_p = fill_price * (1.0 - tp_pct)
                await self._place_protective_orders(symbol, side_en, sl_p, tp_p)

            return {**order, "execution": execution}
        except Exception as e:
            self._record_execution_event(
                "MANUAL_OPEN", "failed", symbol, side_en, "manual order", str(e),
                requested_qty=qty,
            )
            return {"error": str(e)}

    async def close_position(self, symbol: str):
        """Close the complete current position with fill-aware accounting."""
        try:
            positions = await self.client.get_positions()
            for p in positions:
                if p["symbol"] == symbol:
                    amt = float(p["positionAmt"])
                    if amt > 0:
                        return await self._close_pos(
                            symbol, "LONG", abs(amt), "manual close",
                            entry_price=float(p.get("entryPrice", 0) or 0),
                            exit_price=float(p.get("markPrice", 0) or 0),
                        )
                    if amt < 0:
                        return await self._close_pos(
                            symbol, "SHORT", abs(amt), "manual close",
                            entry_price=float(p.get("entryPrice", 0) or 0),
                            exit_price=float(p.get("markPrice", 0) or 0),
                        )
            return {"msg": "no open position"}
        except Exception as e:
            print(f"[manual close failed] {symbol}: {e}")
            return {"error": str(e)}

    async def recommend_buy(self, symbol: str, side_en: str, qty, leverage=None):
        """Open a recommendation with exchange step-size normalization and fill diagnostics."""
        try:
            symbol = self._normalize_symbols([symbol])[0] if self._normalize_symbols([symbol]) else ""
            if not self._trade_symbol_allowed(symbol):
                return {"error": f"{symbol or 'symbol'} is not in the selected trading universe"}
            liquidity = await self._liquidity_snapshot(symbol)
            if not liquidity.get("allowed", False):
                return {"error": f"{symbol} liquidity filter blocked the order: {liquidity.get('reason', '')}"}
            qty = float(qty)
            if qty <= 0:
                return {"error": "invalid quantity"}
            requested_leverage = int(leverage or self.leverage)
            ticker = await self.client.get_ticker(symbol)
            market_price = float(ticker.get("lastPrice", 0) or 0)
            qty, notional, min_notional = await self.client.validate_market_open_quantity(
                symbol, market_price, qty)
            effective_leverage, max_leverage = await self.client.clamp_leverage(
                symbol, requested_leverage)
            applied_leverage, _ = await self._prepare_new_position(symbol, effective_leverage)
            effective_leverage = applied_leverage or effective_leverage
            if side_en == "LONG":
                order = await self.client.market_open_long(symbol, qty)
            else:
                order = await self.client.market_open_short(symbol, qty)
            execution = self._order_execution(order)
            outcome = "success" if execution["completed"] else (
                "partial" if execution["executed_qty"] > 0 else "failed"
            )
            self._record_execution_event(
                "RECOMMEND_OPEN", outcome, symbol, side_en, "recommended order",
                requested_qty=execution["requested_qty"] or qty,
                normalized_qty=execution["normalized_qty"],
                executed_qty=execution["executed_qty"],
                avg_price=execution["avg_price"], order_id=execution["order_id"],
                exchange_status=execution["status"],
                requested_leverage=requested_leverage, leverage=effective_leverage,
                max_leverage=max_leverage, notional=round(notional, 8),
                min_notional=min_notional,
            )
            if execution["executed_qty"] <= 0:
                return {"error": f"exchange returned {execution['status']} with no executed quantity",
                        **execution}
            self.tp_state[symbol] = {
                "side": side_en, "orig_qty": execution["executed_qty"],
                "tp1": False, "tp2": False, "tp3": False,
                "mode": "conservative", "entry_time": time.time(),
            }
            print(f"[recommended order] {side_en} {symbol} qty={execution['executed_qty']} "
                  f"status={execution['status']} order={execution['order_id']}")
            return {"symbol": symbol, "side": side_en, "qty": execution["executed_qty"],
                    "leverage": effective_leverage, "requested_leverage": requested_leverage,
                    "max_leverage": max_leverage, "orderId": execution["order_id"],
                    "status": execution["status"], "execution": execution}
        except Exception as e:
            print(f"[recommended order failed] {symbol}: {e}")
            self._record_execution_event(
                "RECOMMEND_OPEN", "failed", symbol, side_en, "recommended order", str(e)
            )
            return {"error": str(e)}

    async def _one_click_analysis(self, symbol: str) -> dict:
        """拉取K线/HTF/资金费率并跑策略评分, 返回评分结果。"""
        closed = await self.client.get_klines(symbol, self.interval, 200)
        rows = list(closed[:-1]) if len(closed) > 1 else []
        if len(rows) < 60:
            raise ValueError("K线数据不足(需≥60根已收盘K线)")
        closes = np.array([float(k[4]) for k in rows])
        highs = np.array([float(k[2]) for k in rows])
        lows = np.array([float(k[3]) for k in rows])
        volumes = np.array([float(k[5]) for k in rows])
        htf_klines = await self.client.get_klines(symbol, self.htf_interval, 100)
        htf_closes = np.array([float(k[4]) for k in htf_klines])
        funding_rate = None
        try:
            fr = await self.client.get_funding_rate(symbol)
            if fr:
                funding_rate = float(fr[-1].get("fundingRate", 0) or 0)
        except Exception:
            pass
        return self.strategy.evaluate(
            closes, highs, lows, volumes,
            funding_rate=funding_rate,
            htf_closes=htf_closes if len(htf_closes) >= 55 else None,
        )

    async def rank_order_preview(self, symbol: str, max_price: float = None,
                                 leverage: int = None, margin: float = None,
                                 side: str = None) -> dict:
        """榜单一键下单预览: 实时策略评分 → 方向/杠杆/仓位/止损止盈, 不实际下单。支持自定义杠杆、仓位与方向"""
        norm = self._normalize_symbols([symbol])
        symbol = norm[0] if norm else ""
        if not symbol:
            return {"error": "无效合约代码"}
        try:
            result = await self._one_click_analysis(symbol)
        except Exception as e:
            return {"error": f"策略分析失败: {e}"}
        signal = int(result.get("signal", 0))

        # 方向判定: 支持手动指定或默认使用策略推荐方向
        if side and str(side).upper() in ("LONG", "SHORT", "BUY", "SELL", "做多", "做空"):
            s_up = str(side).upper()
            side_en = "LONG" if ("LONG" in s_up or "BUY" in s_up or "多" in s_up) else "SHORT"
        elif signal != 0:
            side_en = "LONG" if signal == 1 else "SHORT"
        else:
            return {
                "error": "当前无策略信号",
                "score": result.get("score", 0),
                "reason": result.get("reason", "无明确信号"),
                "indicators": result.get("indicators", {}),
            }

        indicators = result.get("indicators", {})
        price = float(indicators.get("price", 0) or 0)
        atr_now = float(indicators.get("atr", 0) or 0)
        atr_pct = (atr_now / price * 100) if price > 0 and atr_now > 0 else 0.5
        try:
            account = await self.client.get_account()
            balance = float(account.get("totalWalletBalance", 0) or 0)
        except Exception:
            balance = 1000.0
        if price <= 0:
            return {"error": "价格无效, 无法计算仓位"}
        pm = self._position_management_cfg()

        if leverage is not None and int(leverage) > 0:
            requested_leverage = max(1, min(125, int(leverage)))
        else:
            requested_leverage = min(max(self.leverage // 2, 2), int(pm.get("swing_max_leverage", 6)))
        effective_leverage, max_leverage = await self.client.clamp_leverage(symbol, requested_leverage)
        lev = min(requested_leverage, effective_leverage)

        if margin is not None and float(margin) > 0:
            user_margin = float(margin)
            notional = user_margin * lev
        else:
            size_pct = self._entry_size_pct(0.5, 0.05)
            notional = self._planned_entry_notional(balance, size_pct, lev)

        exec_cfg = self._execution_cfg()
        buffer = float(exec_cfg.get("min_notional_buffer_pct", 2.0))
        qty = await self.client.quantity_for_notional(symbol, price, notional * (1 + buffer / 100))
        planned_notional = qty * price
        actual_margin = planned_notional / lev if lev else planned_notional

        strategy_leverage_cap = min(max_leverage, int(pm.get("swing_max_leverage", 6)))
        if leverage is None:
            leverage_plan = self._minimum_notional_leverage_plan(
                planned_notional,
                balance,
                lev,
                strategy_leverage_cap,
                float(pm.get("max_entry_margin_pct", 25.0)),
            )
            if not leverage_plan["allowed"]:
                return {
                    "error": (
                        f"交易所最小下单与1.5倍保证金需要至少"
                        f"{leverage_plan['required_leverage']}x，超过策略上限"
                        f"{strategy_leverage_cap}x"
                    ),
                    "score": result.get("score", 0),
                    "required_margin": round(leverage_plan["margin"], 4),
                }
            lev = leverage_plan["leverage"]
            actual_margin = planned_notional / lev if lev else planned_notional

        risk_cfg = self.cfg.get("risk", {})
        max_pos_mult = float(risk_cfg.get("max_position_notional_multiple", 6))
        if margin is None and planned_notional > balance * max_pos_mult:
            return {
                "error": f"仓位过大被风控拦截: 需{planned_notional:.1f}U名义, 超过账户上限{balance * max_pos_mult:.1f}U({max_pos_mult}倍余额)",
                "score": result.get("score", 0),
                "reason": "交易所最小下单单位强制名义过大, 建议更换更低价币或加大保证金",
            }
        _, _, _, _, _, sl, tp1, tp2, tp3 = self._calc_recommendation(
            balance, price, atr_pct, side_en, max_leverage=effective_leverage)
        return {
            "ok": True,
            "symbol": symbol,
            "side": side_en,
            "side_cn": "做多" if side_en == "LONG" else "做空",
            "score": result.get("score", 0),
            "price": price,
            "atr_pct": round(atr_pct, 3),
            "leverage": lev,
            "max_leverage": max_leverage,
            "margin": round(actual_margin, 2),
            "qty": round(qty, 8),
            "notional": round(planned_notional, 4),
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "reason": result.get("reason", ""),
            "factors": result.get("factors", []),
        }

    async def rank_one_click_open(self, symbol: str, max_price: float = None,
                                  leverage: int = None, margin: float = None,
                                  side: str = None, sl: float = None, tp: float = None) -> dict:
        """榜单一键下单: 支持自定义杠杆、仓位保证金、多空方向与止损止盈"""
        preview = await self.rank_order_preview(
            symbol, max_price=max_price, leverage=leverage, margin=margin, side=side
        )
        if not preview.get("ok"):
            return preview
        symbol = preview["symbol"]
        side_en = preview["side"]
        signal = 1 if side_en == "LONG" else -1
        price = preview["price"]

        candidate_ctx = {
            "score": preview["score"],
            "base_score": preview["score"],
            "indicators": {"atr_pct": preview.get("atr_pct") or 0},
            "recommendation": {
                "sl": sl if sl is not None else preview["sl"],
                "tp1": tp if tp is not None else preview["tp1"],
                "tp2": preview["tp2"],
            },
            "factors": preview.get("factors", []),
            "custom_leverage": preview["leverage"],
            "custom_margin": preview["margin"],
            "custom_notional": preview["notional"],
            "custom_sl": sl if sl is not None else preview["sl"],
            "custom_tp": tp if tp is not None else preview["tp1"],
        }
        result = await self._execute_signal(
            symbol, signal, price, mode="conservative",
            candidate_context=candidate_ctx,
            force=True,
        )
        if not result:
            return {"error": "下单被风控/过滤拦截, 请查看执行诊断", "preview": preview}
        result["preview"] = preview
        return result

    async def get_status(self) -> dict:
        """获取当前状态"""
        try:
            account = await self.client.get_account()
            open_pos = await self._refresh_positions()
            return {
                "balance": float(account["totalWalletBalance"]),
                "unrealized_pnl": float(account["totalUnrealizedProfit"]),
                "available_balance": float(account.get("availableBalance", 0)),
                "margin_ratio": float(account.get("totalMarginBalance", 0)),
                "positions": open_pos,
                "running": self.running,
                "auto_trade": self.auto_trade,
                "live_trading_enabled": self.live_trading_enabled,
                "paper_trading": self.paper_trading,
                "trading_mode": getattr(self, "trading_mode", "PAPER"),
                "risk_summary": self.risk.get_summary(),
                "emergency_stopped": self.risk.emergency_stopped,
                "circuit_breaker": {
                    "active": self.risk.circuit_breaker_active,
                    "reason": self.risk.circuit_breaker_reason,
                    "timestamp": self.risk.circuit_breaker_timestamp,
                },
                "last_market_data_ts": getattr(self, "last_market_data_ts", 0.0),
                "data_staleness_sec": round(time.time() - getattr(self, "last_market_data_ts", time.time()), 1) if getattr(self, "last_market_data_ts", 0) > 0 else 0.0,
                "reconciliation": {
                    "status": self.risk.reconciliation_status,
                    "last_time": self.risk.last_reconciliation_time,
                    "discrepancies": self.risk.reconciliation_discrepancies,
                },
                "symbols": self.symbols,
                "trade_symbols": self.symbols,
                "all_symbols": self.watch_symbols(),
                "liquidity": self._liquidity_cfg(),
                "market_selection": self._market_selection_cfg(),
                "interval": self.interval,
                "htf_interval": self.htf_interval,
                "swing_interval": self.swing_interval,
                "leverage": self.leverage,
                "funding_rates": self.funding_rates,
                "smart_money": self.latest_smart_money,
                "grids": [{
                    "symbol": s, "center": st["center"], "spacing": round(st["spacing"], 8),
                    "lev": st["lev"], "round_trips": st.get("round_trips", 0),
                    "grid_pnl": round(st.get("grid_pnl", 0.0), 4),
                    "winding_down": st.get("winding_down", False),
                } for s, st in self.grid_state.items()],
                "execution_events": self.execution_events[-30:],
                "entry_decision_mode": self.entry_decision_mode,
                "typesafe_enabled": (self.entry_decision_mode in ("typesafe_jev", "typesafe_evaluator", "typesafe_hybrid", "hybrid")) or bool(getattr(self.typesafe_engine, "enabled", False)),
                "autonomous_hunter_enabled": (self.entry_decision_mode in ("typesafe_hybrid", "typesafe_autonomous", "hybrid")) and bool(getattr(self.typesafe_engine, "autonomous_enabled", False)),
            }
        except Exception as e:
            return {
                "error": str(e),
                "running": self.running,
                "auto_trade": self.auto_trade,
                "live_trading_enabled": self.live_trading_enabled,
                "paper_trading": self.paper_trading,
                "trading_mode": getattr(self, "trading_mode", "PAPER"),
                "risk_summary": self.risk.get_summary() if hasattr(self, "risk") else {},
                "emergency_stopped": getattr(getattr(self, "risk", None), "emergency_stopped", False),
                "circuit_breaker": {
                    "active": getattr(getattr(self, "risk", None), "circuit_breaker_active", False),
                    "reason": getattr(getattr(self, "risk", None), "circuit_breaker_reason", ""),
                },
                "entry_decision_mode": self.entry_decision_mode,
                "typesafe_enabled": (self.entry_decision_mode in ("typesafe_jev", "typesafe_evaluator", "typesafe_hybrid", "hybrid")) or bool(getattr(self.typesafe_engine, "enabled", False)),
                "autonomous_hunter_enabled": (self.entry_decision_mode in ("typesafe_hybrid", "typesafe_autonomous", "hybrid")) and bool(getattr(self.typesafe_engine, "autonomous_enabled", False)),
            }

    def _calc_recommendation(self, balance: float, price: float, atr_pct: float,
                             side_en: str = "LONG", max_leverage: int | float = 20):
        """根据波动率与合约可用余额测算杠杆/仓位/风险 + 分批止盈止损价位。
        目标: 单笔止损触发时约亏保证金30%, 即账户总资金的~3%(恒定风险)。"""
        stop_pct = max(atr_pct * 1.0, 0.4)   # 止损距离%(1倍ATR, 至少0.4%)
        lev = round(25 / stop_pct)            # 让 止损%×杠杆 ≈ 25%保证金
        lev = max(1, min(lev, int(max_leverage), 20))  # 受该合约实际杠杆上限约束
        margin = round(balance * 0.1, 2)      # 单笔建议投入10%资金
        position_value = margin * lev
        # 币安最低名义价值5U, 不足则提高保证金
        if position_value < 5 and lev > 0:
            margin = round(5.0 / lev + 0.01, 2)
            position_value = margin * lev
        qty = position_value / price if price else 0
        risk_u = position_value * stop_pct / 100
        risk_pct = risk_u / balance * 100 if balance else 0
        # 分批止盈止损价位(方向感知, 止损1ATR, TP1=1.5ATR, TP2=2.5ATR, TP3=4ATR)
        atr_price = price * atr_pct / 100 if price else 0
        if side_en == "LONG":
            sl = round(price - atr_price * 1.0, 8)
            tp1 = round(price + atr_price * 1.5, 8)
            tp2 = round(price + atr_price * 2.5, 8)
            tp3 = round(price + atr_price * 4.0, 8)
        else:
            sl = round(price + atr_price * 1.0, 8)
            tp1 = round(price - atr_price * 1.5, 8)
            tp2 = round(price - atr_price * 2.5, 8)
            tp3 = round(price - atr_price * 4.0, 8)
        return lev, margin, qty, round(risk_u, 2), round(risk_pct, 2), sl, tp1, tp2, tp3

    @staticmethod
    def build_market_rankings(tickers: list, max_price: float = 5,
                              limit: int = 20) -> dict:
        """Build 24h gain, loss and quote-volume rankings for low-price contracts."""
        if max_price is None or float(max_price) <= 0:
            effective_max_price = 1e12
        else:
            effective_max_price = max(0.00000001, float(max_price))
        limit = max(1, min(100, int(limit)))
        rows = []
        for ticker in tickers or []:
            symbol = str(ticker.get("symbol", "")).upper()
            if not symbol.endswith("USDT") or symbol.endswith("_PERP"):
                continue
            try:
                price = float(ticker.get("lastPrice", 0) or 0)
                change_pct = float(ticker.get("priceChangePercent", 0) or 0)
                quote_volume = float(ticker.get("quoteVolume", 0) or 0)
                base_volume = float(ticker.get("volume", 0) or 0)
            except (TypeError, ValueError):
                continue
            if price <= 0 or price >= effective_max_price or quote_volume <= 0:
                continue
            rows.append({
                "symbol": symbol,
                "price": price,
                "change_pct": round(change_pct, 4),
                "quote_volume": round(quote_volume, 2),
                "base_volume": round(base_volume, 2),
            })
        return {
            "max_price": max_price,
            "limit": limit,
            "matched": len(rows),
            "gainers": sorted(
                rows, key=lambda item: item["change_pct"], reverse=True)[:limit],
            "losers": sorted(
                rows, key=lambda item: item["change_pct"])[:limit],
            "volume": sorted(
                rows, key=lambda item: item["quote_volume"], reverse=True)[:limit],
        }

    async def get_recommendations(self, limit: int = 8) -> dict:
        """实时扫描全市场, 推荐高评分合约 + 匹配总资产的杠杆/仓位"""
        now = time.time()
        cache = getattr(self, "_recommend_cache", None)
        if cache and now - cache["ts"] < 60:
            return cache["data"]
        market_selection = self._market_selection_cfg()
        if not self.symbols and not market_selection.get("allow_all_symbols", False):
            return {
                "error": "尚未配置交易白名单，请在策略设置中填写合约代码",
                "items": [],
                "balance": 0,
                "ts": datetime.now().strftime("%H:%M:%S"),
                "note": "自动交易只允许白名单品种，系统不会扫描全市场",
            }

        account_warning = None
        try:
            account = await self.client.get_account()
            balance = float(account.get("availableBalance") or account["totalWalletBalance"])
        except Exception as e:
            balance = 1000.0
            account_warning = f"实盘账户未就绪 ({e})，已启用 1000U 模拟基准测算推荐"

        try:
            tickers = await self.client.get_all_tickers()
        except Exception as e:
            return {"error": f"获取行情失败: {e}", "items": [], "balance": round(balance, 2)}

        # 筛选活跃USDT永续, 按成交额排名
        candidates = []
        allowed_symbols = set(self.symbols)
        liquidity_cfg = self._liquidity_cfg()
        market_selection = self._market_selection_cfg()
        for t in tickers:
            sym = t.get("symbol", "")
            if not sym.endswith("USDT"):
                continue
            if allowed_symbols and not market_selection.get("allow_all_symbols", False) and sym not in allowed_symbols:
                continue
            try:
                qv = float(t.get("quoteVolume", 0))
                price = float(t.get("lastPrice", 0))
                chg = float(t.get("priceChangePercent", 0))
                bid = float(t.get("bidPrice", 0) or 0)
                ask = float(t.get("askPrice", 0) or 0)
            except (ValueError, TypeError):
                continue
            if qv <= 0 or price <= 0:
                continue
            if (market_selection.get("enabled", True)
                    and price > float(market_selection.get("max_price", 1.0))):
                continue
            if liquidity_cfg.get("enabled", True):
                min_volume = float(liquidity_cfg.get("min_quote_volume_24h", 10000000))
                if qv < min_volume:
                    continue
                if bid > 0 and ask >= bid:
                    spread_bps = (ask - bid) / ((ask + bid) / 2) * 10000
                    if spread_bps > float(liquidity_cfg.get("max_spread_bps", 15)):
                        continue
            candidates.append((sym, qv, price, chg, t))
        candidates.sort(key=lambda x: x[1], reverse=True)
        candidate_scan_limit = max(
            limit, int(market_selection.get("candidate_scan_limit", 80)))
        top = candidates[:min(len(candidates), candidate_scan_limit)]
        scan_rejections = Counter()

        async def eval_one(sym, price, chg, ticker):
            try:
                # 过滤单价超过配置上限的币种
                max_allowed_price = float(market_selection.get("max_price", 250000.0))
                if price > max_allowed_price:
                    scan_rejections["price_above_limit"] += 1
                    return None
                klines = self._closed_kline_rows(
                    await self.client.get_klines(sym, self.interval, 200)
                )
                if len(klines) < 60:
                    scan_rejections["insufficient_klines"] += 1
                    return None
                closes = np.array([float(k[4]) for k in klines])
                highs = np.array([float(k[2]) for k in klines])
                lows = np.array([float(k[3]) for k in klines])
                volumes = np.array([float(k[5]) for k in klines])
                opens = np.array([float(k[1]) for k in klines])
                htf_closes = None
                try:
                    htf_klines = self._closed_kline_rows(
                        await self.client.get_klines(sym, self.htf_interval, 100)
                    )
                    if len(htf_klines) >= 55:
                        htf_closes = np.array([float(k[4]) for k in htf_klines])
                except Exception:
                    pass
                result = self.strategy.evaluate(closes, highs, lows, volumes, htf_closes=htf_closes)
                technical_signal = self._technical_recommendation_signal(result)
                if technical_signal == 0:
                    scan_rejections["technical_signal_veto"] += 1
                    return None
                score = result["score"]
                ind = result["indicators"]
                atr = float(ind.get("atr") or 0)
                atr_pct = atr / price * 100 if price else 0
                # 主力意图推断(洗盘 vs 出货): 不与主力对手, 顺势借力
                intent_info = detect_main_force_intent(closes, highs, lows, volumes, opens, atr)
                intent = intent_info["intent"]
                intent_conf = intent_info["confidence"]
                if intent == "出货":
                    if score > 0:
                        score -= 12
                        result["factors"].append(f"疑似主力出货({intent_conf}%),压制做多(-12)")
                    else:
                        score -= 10
                        result["factors"].append(f"主力出货迹象({intent_conf}%),顺势空加重(-10)")
                elif intent in ("洗盘", "吸筹"):
                    if score > 0:
                        score += 10
                        result["factors"].append(f"主力{intent}蓄势({intent_conf}%),顺势多加重(+10)")
                    else:
                        score += 12
                        result["factors"].append(f"疑似主力{intent}({intent_conf}%),压制做空(+12)")
                # 成交量异动(轮动核心): 近3根均量 / 近50根均量
                vol_recent = float(np.mean(volumes[-3:]))
                vol_base = float(np.mean(volumes[-50:])) if len(volumes) >= 50 else float(np.mean(volumes))
                vol_surge = round(vol_recent / vol_base, 2) if vol_base > 0 else 1.0
                if market_selection.get("enabled", True):
                    min_atr_pct = float(market_selection.get("min_atr_pct", 0.8))
                    max_atr_pct = float(market_selection.get("max_atr_pct", 0) or 0)
                    min_vol_surge = float(market_selection.get("min_vol_surge", 1.2))
                    if atr_pct < min_atr_pct:
                        scan_rejections["atr_below_minimum"] += 1
                        return None
                    if max_atr_pct > 0 and atr_pct > max_atr_pct:
                        scan_rejections["atr_above_maximum"] += 1
                        return None
                    if vol_surge < min_vol_surge:
                        scan_rejections["volume_surge_below_minimum"] += 1
                        return None
                price_change_1h = self._series_change(closes, self._bars_per_hour())
                # 热度分: 技术评分(60%) + 放量倍数(40%, 3倍封顶)
                surge_pts = min(vol_surge / 3.0, 1.0) * 100
                hot_score = round(abs(score) * 0.6 + surge_pts * 0.4, 1)
                if score * technical_signal <= 0:
                    scan_rejections["technical_direction_conflict"] += 1
                    return None
                side_en = "LONG" if technical_signal > 0 else "SHORT"
                lev, margin, qty, risk_u, risk_pct, sl, tp1, tp2, tp3 = self._calc_recommendation(balance, price, atr_pct, side_en)
                # 支撑/压力位修正止损止盈: 多单SL贴支撑下方、TP1看压力位; 空单反之
                sr_support = ind.get("sr_support")
                sr_resistance = ind.get("sr_resistance")
                atr_price = price * atr_pct / 100 if price else 0
                if side_en == "LONG":
                    if sr_support and 0 < price - sr_support <= atr_price * 1.6:
                        sl = round(sr_support * 0.997, 8)
                    if sr_resistance and sr_resistance - price >= atr_price * 0.8:
                        tp1 = round(sr_resistance * 0.999, 8)
                else:
                    if sr_resistance and 0 < sr_resistance - price <= atr_price * 1.6:
                        sl = round(sr_resistance * 1.003, 8)
                    if sr_support and price - sr_support >= atr_price * 0.8:
                        tp1 = round(sr_support * 1.001, 8)
                quote_volume = float(ticker.get("quoteVolume", 0) or 0)
                bid = float(ticker.get("bidPrice", 0) or 0)
                ask = float(ticker.get("askPrice", 0) or 0)
                spread_bps = ((ask - bid) / ((ask + bid) / 2) * 10000) if bid > 0 and ask >= bid else None
                # 可下单性预检: maxQty*price < minNotional 的币物理上无法下单, 提前剔除
                try:
                    _st, _mq, _xq, _mn = await self.client._quantity_rule(sym)
                    if _xq > 0 and _mn > 0 and float(_xq) * price < float(_mn):
                        scan_rejections["notional_above_max_qty"] += 1
                        return None
                    # 仓位控制: 最小名义超过账户承受上限的币不碰, 避免被迫全仓猛干
                    _risk_cfg = self.cfg.get("risk", {})
                    _max_mult = float(_risk_cfg.get("max_position_notional_multiple", 6))
                    if float(_mn) > balance * _max_mult:
                        scan_rejections["min_notional_above_cap"] += 1
                        return None
                except Exception:
                    pass
                return {
                    "symbol": sym,
                    "side": "做多" if score > 0 else "做空",
                    "side_en": side_en,
                    "score": score,
                    "abs_score": abs(score),
                    "hot_score": hot_score,
                    "vol_surge": vol_surge,
                    "price_change_1h": round(price_change_1h, 2),
                    "price": price,
                    "rsi": ind.get("rsi"),
                    "atr_pct": round(atr_pct, 2),
                    "change_24h": round(chg, 2),
                    "support": sr_support,
                    "support_touches": ind.get("sr_support_touches", 0),
                    "resistance": sr_resistance,
                    "resistance_touches": ind.get("sr_resistance_touches", 0),
                    "intent": intent,
                    "intent_confidence": intent_conf,
                    "intent_reasons": intent_info["reasons"],
                    "liquidity": {
                        "symbol": sym,
                        "allowed": True,
                        "quote_volume_24h": round(quote_volume, 2),
                        "spread_bps": round(spread_bps, 2) if spread_bps is not None else None,
                        "reason": "白名单及流动性通过",
                    },
                    "leverage": lev,
                    "margin": margin,
                    "qty": round(qty, 6),
                    "risk_u": risk_u,
                    "risk_pct": risk_pct,
                    "sl": sl,
                    "tp1": tp1,
                    "tp2": tp2,
                    "tp3": tp3,
                    "reason": result["reason"],
                    "factors": result["factors"],
                    "recent_closes": [round(float(v), 8) for v in closes[-30:]],
                }
            except Exception:
                scan_rejections["evaluation_error"] += 1
                return None

        results = await asyncio.gather(*[eval_one(s, p, c, t) for s, _, p, c, t in top])
        # 先用技术与成交量预筛，再只对前排候选拉取衍生品数据，避免全市场请求过多。
        _eval_ok = [r for r in results if r]
        preliminary = [r for r in _eval_ok if r["abs_score"] >= 12]
        scan_rejections["score_below_minimum"] += len(_eval_ok) - len(preliminary)
        print(f"[推荐管线] 扫描{len(top)} → 技术通过{len(_eval_ok)} → 预筛(abs≥12){len(preliminary)}")
        if scan_rejections:
            print("[推荐管线] 拒绝分布: " + ", ".join(
                f"{k}={v}" for k, v in scan_rejections.most_common()))
        if _eval_ok and not preliminary:
            print("[推荐管线] 技术分明细: " + ", ".join(
                f"{r['symbol']}:{r['side_en']}:{r['score']}" for r in _eval_ok[:10]))
        preliminary.sort(key=lambda x: x["hot_score"], reverse=True)
        smart_scan_limit = max(limit, int(self._smart_money_cfg().get("scan_limit", 8)))
        preliminary = preliminary[:min(smart_scan_limit, 12)]

        smart_semaphore = asyncio.Semaphore(4)

        async def enrich_smart(item: dict):
            async with smart_semaphore:
                fr = None
                try:
                    fr_data = await self.client.get_funding_rate(item["symbol"])
                    if fr_data:
                        fr = float(fr_data[0]["fundingRate"])
                except Exception:
                    pass
                try:
                    derivatives = await self.market_sentiment.get_derivatives(item["symbol"])
                    smart = self.market_sentiment.score_smart_money(
                        derivatives,
                        price_change_1h=item.get("price_change_1h", 0),
                        price_change_24h=item.get("change_24h", 0),
                        volume_surge=item.get("vol_surge", 1),
                        funding_rate=fr,
                    )
                    smart.update({
                        "symbol": item["symbol"],
                        "long_short": derivatives.get("long_short", {}),
                        "top_trader_account": derivatives.get("top_trader_account", {}),
                        "top_trader": derivatives.get("top_trader", {}),
                        "open_interest": derivatives.get("open_interest", {}),
                        "funding_rate": fr,
                        "updated_at": datetime.now().strftime("%H:%M:%S"),
                    })
                    self.latest_smart_money[item["symbol"]] = smart
                    self._refine_intent_with_derivatives(item, smart)
                    direction = 1 if item["side_en"] == "LONG" else -1
                    decision = self._smart_money_decision(direction, smart)
                    base_score = float(item["score"])
                    adjusted = base_score + direction * float(decision.get("score_delta", 0))
                    adjusted = round(max(-100.0, min(100.0, adjusted)), 1)
                    item["base_score"] = round(base_score, 1)
                    item["score"] = adjusted
                    item["abs_score"] = abs(adjusted)
                    item["smart_money"] = smart
                    item["smart_money_decision"] = decision
                    item["funding_rate"] = fr
                    item["factors"] = list(item.get("factors", [])) + [decision["reason"]]
                    surge_pts = min(float(item.get("vol_surge", 1)) / 3.0, 1.0) * 100
                    item["hot_score"] = round(
                        item["abs_score"] * 0.55
                        + surge_pts * 0.25
                        + abs(float(smart.get("score", 0))) * 0.20,
                        1,
                    )
                    return item if decision.get("pass", True) else None
                except Exception as e:
                    item["smart_money"] = {
                        "score": 0, "direction": "NEUTRAL", "label": "聪明钱数据暂缺",
                        "data_quality": 0, "components": [], "error": str(e),
                    }
                    item["smart_money_decision"] = {
                        "pass": True, "aligned": False, "score_delta": 0,
                        "reason": "聪明钱数据暂缺，沿用技术候选",
                    }
                    item["factors"] = list(item.get("factors", [])) + ["聪明钱数据暂缺，沿用技术候选"]
                    return item

        enriched = await asyncio.gather(*[enrich_smart(item) for item in preliminary])
        _enr_ok = [r for r in enriched if r]
        if _enr_ok:
            print("[推荐管线] 聪明钱调整: " + ", ".join(
                f"{r['symbol']}:{r['side_en']}:{r['base_score']}->{r['score']}" for r in _enr_ok))
        items = [r for r in enriched if r and r["abs_score"] >= 15]
        print(f"[推荐管线] 终筛(abs>=15){len(items)} -> 进入执行约束")
        items.sort(key=lambda x: x["hot_score"], reverse=True)
        items = items[:limit]

        leverage_semaphore = asyncio.Semaphore(3)

        async def make_executable(item: dict):
            """Return a recommendation only when its real leverage and order limits fit the account."""
            async with leverage_semaphore:
                requested_leverage = int(item["leverage"])
                try:
                    effective_leverage, max_leverage = await self.client.clamp_leverage(
                        item["symbol"], requested_leverage)
                    lev, _, _, _, _, sl, tp1, tp2, tp3 = self._calc_recommendation(
                        balance, item["price"], item["atr_pct"], item["side_en"],
                        max_leverage=effective_leverage,
                    )
                    desired_notional = max(5.0, balance * 0.1 * lev)
                    qty = await self.client.quantity_for_notional(
                        item["symbol"], item["price"], desired_notional)
                    notional = qty * item["price"]
                    margin = notional / lev if lev else 0.0
                    if margin > balance * 0.95:
                        return {
                            "_execution_rejected": True,
                            "symbol": item["symbol"],
                            "reason": (
                                f"minimum executable margin {margin:.2f}U exceeds "
                                f"the available balance {balance:.2f}U"
                            ),
                            "required_margin": round(margin, 4),
                            "available_balance": round(balance, 4),
                            "max_leverage": max_leverage,
                        }
                    stop_pct = max(float(item["atr_pct"]), 0.4)
                    risk_u = notional * stop_pct / 100
                    item.update({
                        "requested_leverage": requested_leverage,
                        "max_leverage": max_leverage,
                        "leverage": lev,
                        "margin": round(margin, 2),
                        "qty": round(qty, 6),
                        "notional": round(notional, 4),
                        "risk_u": round(risk_u, 2),
                        "risk_pct": round(risk_u / balance * 100, 2) if balance else 0,
                        "sl": sl,
                        "tp1": tp1,
                        "tp2": tp2,
                        "tp3": tp3,
                    })
                    return item
                except Exception as exc:
                    return {
                        "_execution_rejected": True,
                        "symbol": item["symbol"],
                        "reason": str(exc)[:220],
                    }

        constrained = await asyncio.gather(*[make_executable(item) for item in items])
        execution_rejections = [
            item for item in constrained
            if item and item.get("_execution_rejected")
        ]
        rejected_execution_count = len(execution_rejections)
        items = [
            item for item in constrained
            if item and not item.get("_execution_rejected")
        ]

        data = {
            "balance": round(balance, 2),
            "account_warning": account_warning,
            "items": items,
            "scanned_candidate_count": len(top),
            "rejected_execution_count": rejected_execution_count,
            "execution_rejections": execution_rejections[:8],
            "scan_rejections": dict(scan_rejections),
            "ts": datetime.now().strftime("%H:%M:%S"),
            "note": (
                f"仅扫描白名单{','.join(self.symbols) or '未配置'}"
                f" · 流动性门槛24h成交额≥{float(liquidity_cfg.get('min_quote_volume_24h', 10000000))/1e6:.1f}M"
                f" · 合约可用余额{round(balance,2)}U · 已过滤单价>{round(balance*6,0)}U币种"
                " · 技术预筛→聪明钱加权/强反向否决→风控"
            ),
        }
        self._recommend_cache = {"ts": now, "data": data}
        return data

    async def evaluate_symbol_for_blog_candidate(
        self, symbol: str, ticker: dict = None, default_side: str = None
    ) -> dict:
        """为博客创作与封面图秒级评估单个标的的技术指标与建议关键位"""
        norm = self._normalize_symbols([symbol])
        sym = norm[0] if norm else str(symbol).upper()
        if not sym.endswith("USDT"):
            sym += "USDT"

        price = 0.0
        chg = 0.0
        quote_vol = 0.0
        if ticker:
            try:
                price = float(ticker.get("lastPrice", 0) or 0)
                chg = float(ticker.get("priceChangePercent", 0) or 0)
                quote_vol = float(ticker.get("quoteVolume", 0) or 0)
            except Exception:
                pass

        klines = []
        try:
            raw_klines = await self.client.get_klines(sym, self.interval, 100)
            klines = self._closed_kline_rows(raw_klines)
        except Exception:
            pass

        if len(klines) >= 30:
            closes = np.array([float(k[4]) for k in klines])
            highs = np.array([float(k[2]) for k in klines])
            lows = np.array([float(k[3]) for k in klines])
            volumes = np.array([float(k[5]) for k in klines])
            if price <= 0:
                price = float(closes[-1])
        else:
            p_seed = price if price > 0 else 100.0
            closes = np.array([p_seed])
            highs = closes
            lows = closes
            volumes = np.array([1000.0])
            if price <= 0:
                price = p_seed

        score = 0
        factors = []
        ind = {}
        if len(klines) >= 60:
            try:
                eval_res = self.strategy.evaluate(closes, highs, lows, volumes)
                score = int(eval_res.get("score", 0))
                factors = list(eval_res.get("factors", []))[:3]
                ind = eval_res.get("indicators", {})
            except Exception:
                pass

        atr = float(ind.get("atr") or 0)
        if atr <= 0 and len(klines) >= 15:
            high_low = highs[-14:] - lows[-14:]
            atr = float(np.mean(high_low))
        atr_pct = round((atr / price * 100) if price > 0 and atr > 0 else max(1.5, abs(chg) * 0.15), 2)

        sr_support = ind.get("sr_support")
        sr_resistance = ind.get("sr_resistance")
        if not sr_support and len(lows) >= 20:
            sr_support = round(float(np.min(lows[-25:])), 6)
        if not sr_resistance and len(highs) >= 20:
            sr_resistance = round(float(np.max(highs[-25:])), 6)

        # 确定多空方向
        if default_side and str(default_side).upper() in ("LONG", "SHORT"):
            side_en = str(default_side).upper()
        elif score != 0:
            side_en = "LONG" if score > 0 else "SHORT"
        elif chg >= 0:
            side_en = "LONG"
        else:
            side_en = "SHORT"

        atr_dist = price * (atr_pct / 100) if price > 0 else 0
        if side_en == "LONG":
            if sr_support and sr_support < price and (price - sr_support) <= atr_dist * 2.5:
                sl = round(sr_support * 0.995, 6)
            else:
                sl = round(price * (1 - max(0.018, atr_pct * 0.012)), 6)

            if sr_resistance and sr_resistance > price and (sr_resistance - price) >= atr_dist * 0.5:
                tp1 = round(sr_resistance * 0.998, 6)
            else:
                tp1 = round(price * (1 + max(0.035, atr_pct * 0.024)), 6)
        else:
            if sr_resistance and sr_resistance > price and (sr_resistance - price) <= atr_dist * 2.5:
                sl = round(sr_resistance * 1.005, 6)
            else:
                sl = round(price * (1 + max(0.018, atr_pct * 0.012)), 6)

            if sr_support and sr_support < price and (price - sr_support) >= atr_dist * 0.5:
                tp1 = round(sr_support * 1.002, 6)
            else:
                tp1 = round(price * (1 - max(0.035, atr_pct * 0.024)), 6)

        hot_tags = []
        if chg >= 12:
            hot_tags.append(f"24H涨幅榜大阳突破({chg:+0.2f}%)")
        elif chg > 0:
            hot_tags.append(f"24H涨幅前排({chg:+0.2f}%)")
        elif chg <= -12:
            hot_tags.append(f"24H跌幅榜恐慌跳水({chg:+0.2f}%)")
        else:
            hot_tags.append(f"24H跌幅前排({chg:+0.2f}%)")

        if quote_vol >= 1e8:
            hot_tags.append("亿级头部成交量")
        elif quote_vol >= 1e7:
            hot_tags.append("千万级高流动性")

        all_factors = hot_tags + [f for f in factors if f not in hot_tags]
        summary_reason = " / ".join(all_factors[:3]) or ("多头动能爆发" if side_en == "LONG" else "空头承压回落")

        return {
            "symbol": sym,
            "side": "做多" if side_en == "LONG" else "做空",
            "side_en": side_en,
            "score": score,
            "hot_score": round(abs(chg) * 2 + abs(score), 1),
            "price": price,
            "change_24h": round(chg, 2),
            "quote_volume": round(quote_vol, 2),
            "atr_pct": atr_pct,
            "support": sr_support,
            "resistance": sr_resistance,
            "sl": sl,
            "tp1": tp1,
            "factors": all_factors[:4],
            "reason": summary_reason,
            "recent_closes": [round(float(v), 8) for v in closes[-30:]] if len(closes) >= 5 else [],
        }

    async def get_blog_candidates(
        self, source: str = "recommend", limit: int = 5, symbol: str = None
    ) -> dict:
        """获取博客创作候选标的: 支持量化推荐、24H涨幅榜、24H跌幅榜、持仓币与指定代码"""
        limit = max(1, min(20, int(limit or 5)))
        source = str(source or "recommend").lower()

        # 1. 指定单币种分析
        if symbol:
            target_sym = str(symbol).upper()
            if not target_sym.endswith("USDT"):
                target_sym += "USDT"
            ticker_match = None
            try:
                tickers = await self.client.get_all_tickers()
                ticker_match = next((t for t in tickers if t.get("symbol", "").upper() == target_sym), None)
            except Exception:
                pass
            item = await self.evaluate_symbol_for_blog_candidate(target_sym, ticker=ticker_match)
            return {
                "ok": True,
                "source": "symbol",
                "symbol": target_sym,
                "items": [item],
                "ts": datetime.now().strftime("%H:%M:%S"),
            }

        # 2. 原策略推荐
        if source == "recommend":
            try:
                rec = await self.get_recommendations(limit=limit)
                items = rec.get("items", [])[:limit]
                return {
                    "ok": True,
                    "source": "recommend",
                    "items": items,
                    "ts": datetime.now().strftime("%H:%M:%S"),
                }
            except Exception as e:
                return {"ok": False, "error": f"获取推荐失败: {e}", "items": []}

        # 3. 实盘持仓币种
        if source == "positions":
            try:
                positions = await self.client.get_positions()
                active_pos = [p for p in positions if float(p.get("positionAmt", 0)) != 0]
                if not active_pos:
                    return {
                        "ok": True,
                        "source": "positions",
                        "items": [],
                        "note": "当前实盘暂无持仓",
                        "ts": datetime.now().strftime("%H:%M:%S"),
                    }
                tasks = []
                for p in active_pos[:limit]:
                    sym = p.get("symbol", "")
                    pos_amt = float(p.get("positionAmt", 0))
                    default_side = "LONG" if pos_amt > 0 else "SHORT"
                    tasks.append(self.evaluate_symbol_for_blog_candidate(sym, default_side=default_side))
                items = await asyncio.gather(*tasks)
                return {
                    "ok": True,
                    "source": "positions",
                    "items": [it for it in items if it],
                    "ts": datetime.now().strftime("%H:%M:%S"),
                }
            except Exception as e:
                return {"ok": False, "error": f"获取持仓候选失败: {e}", "items": []}

        # 4. 24H 涨幅榜、跌幅榜、成交额榜
        try:
            tickers = await self.client.get_all_tickers()
        except Exception as e:
            return {"ok": False, "error": f"获取全市场行情失败: {e}", "items": []}

        valid_tickers = []
        for t in tickers or []:
            sym = str(t.get("symbol", "")).upper()
            if not sym.endswith("USDT") or sym.endswith("_PERP"):
                continue
            try:
                qv = float(t.get("quoteVolume", 0) or 0)
                p = float(t.get("lastPrice", 0) or 0)
                chg = float(t.get("priceChangePercent", 0) or 0)
            except Exception:
                continue
            if p <= 0 or qv < 800000:
                continue
            valid_tickers.append((sym, chg, qv, p, t))

        if source == "gainers":
            valid_tickers.sort(key=lambda x: x[1], reverse=True)
            default_side = "LONG"
        elif source == "losers":
            valid_tickers.sort(key=lambda x: x[1])
            default_side = "SHORT"
        else:  # volume
            valid_tickers.sort(key=lambda x: x[2], reverse=True)
            default_side = None

        chosen = valid_tickers[:limit]
        tasks = [
            self.evaluate_symbol_for_blog_candidate(
                s, ticker=t, default_side=default_side
            )
            for s, _, _, _, t in chosen
        ]
        items = await asyncio.gather(*tasks)
        return {
            "ok": True,
            "source": source,
            "items": [it for it in items if it],
            "ts": datetime.now().strftime("%H:%M:%S"),
        }
