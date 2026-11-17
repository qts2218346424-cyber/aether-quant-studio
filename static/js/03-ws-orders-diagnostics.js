// ===== WebSocket =====
function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => { document.getElementById('ws-dot').className='conn-dot on'; const el=document.getElementById('ws-text'); el.dataset.runtimeState='connected'; el.textContent=I18N[currentLanguage].connected; };
  ws.onerror = () => { const el=document.getElementById('ws-text'); if (el && ws?.readyState !== WebSocket.OPEN) { document.getElementById('ws-dot').className='conn-dot'; el.dataset.runtimeState='disconnected'; el.textContent=I18N[currentLanguage].disconnected; } };
  ws.onclose = () => { document.getElementById('ws-dot').className='conn-dot'; const el=document.getElementById('ws-text'); el.dataset.runtimeState='disconnected'; el.textContent=I18N[currentLanguage].disconnected; setTimeout(connectWS, 3000); };
  ws.onmessage = e => { try { updateUI(JSON.parse(e.data)); } catch (error) { console.error('WebSocket message error', error); } };
}

function updateUI(d) {
  // Stats
  if (d.balance !== undefined) smoothAnimateNumber(document.getElementById('s-balance'), Number(d.balance), { suffix: ' U', decimals: 2 });
  if (d.unrealized_pnl !== undefined) {
    const el = document.getElementById('s-upnl');
    smoothAnimateNumber(el, Number(d.unrealized_pnl), { suffix: ' U', decimals: 2, sign: true });
    el.className = 'val ' + (Number(d.unrealized_pnl) >= 0 ? 'pos' : 'neg');
  }
  if (d.available_balance !== undefined) smoothAnimateNumber(document.getElementById('s-avail'), Number(d.available_balance), { suffix: ' U', decimals: 2 });
  if (d.positions) {
    document.getElementById('s-pos').textContent = d.positions.length;
    const previousPositions = lastPositions;
    lastPositions = d.positions;
    renderPositions(d.positions);
    // 同步持仓数据给多图表视图
    const changed = JSON.stringify(d.positions.map(p=>p.symbol+p.qty)) !== JSON.stringify(previousPositions.map(p=>p.symbol+p.qty));
    if (currentView === 'positions' && changed) renderPositionsGrid(d.positions);
  }
  if (d.leverage) document.getElementById('s-lev').textContent = d.leverage + 'x';
  if (d.htf_interval) {
    const htf = document.getElementById('htf-label');
    htf.dataset.interval = d.htf_interval;
    htf.textContent = I18N[currentLanguage].htf + d.htf_interval;
  }
  if (d.funding_rates && d.funding_rates[currentSymbol] !== undefined) {
    const fr = d.funding_rates[currentSymbol];
    const el = document.getElementById('s-funding');
    el.textContent = (fr*100).toFixed(4) + '%';
    el.className = 'val ' + (fr >= 0 ? 'pos' : 'neg');
  }
  // Auto badge
  if (d.auto_trade !== undefined) {
    const badge = document.getElementById('auto-badge');
    badge.className = 'auto-badge ' + (d.auto_trade ? 'on' : 'off');
    badge.textContent = d.auto_trade ? I18N[currentLanguage].autoOn : I18N[currentLanguage].autoOff;
  }
  // TypeSafe Jev badge
  const tsBadge = document.getElementById('typesafe-badge');
  if (tsBadge && d.typesafe_enabled !== undefined) {
    const isTs = Boolean(d.typesafe_enabled);
    tsBadge.className = 'auto-badge ' + (isTs ? 'typesafe-on' : 'off');
    tsBadge.textContent = isTs ? '🧠 Jev 风控: 开' : '🧠 Jev 风控: 关';
    tsBadge.title = isTs ? 'TypeSafe Jev (System One) 决策门禁运行中 (点击关闭)' : 'TypeSafe Jev 已关闭 (点击开启)';
  }
  // Grid badge (高波动网格两头吃)
  const gb = document.getElementById('grid-badge');
  if (gb) {
    const grids = d.grids || [];
    if (grids.length) {
      const g = grids[0];
      gb.style.display = 'inline';
      gb.textContent = `${tr('grid')} ${g.symbol} ${g.round_trips}${tr('rounds')} +${fmt(g.grid_pnl,4)}U${g.winding_down ? ` (${tr('windingDown')})` : ''}`;
      gb.title = `${tr('center')} ${g.center} | ${tr('spacing')} ${g.spacing} | ${tr('leverage')} ${g.lev}x`;
    } else { gb.style.display = 'none'; }
  }
  // Symbols (持仓+观察币, 动态更新)
  const syms = d.all_symbols || d.symbols;
  if (syms && syms.length) {
    const sel = document.getElementById('symbol-select');
    const opts = [...sel.options].map(o => o.value);
    if (JSON.stringify(opts) !== JSON.stringify(syms)) {
      const cur = sel.value;
      sel.innerHTML = '';
      syms.forEach(s => sel.add(new Option(s, s)));
      sel.value = syms.includes(cur) ? cur : syms[0];
      if (!currentSymbol || !syms.includes(currentSymbol)) currentSymbol = sel.value;
    }
  }
  // Indicators + Score
  if (d.indicators && d.indicators[currentSymbol]) renderIndicators(d.indicators[currentSymbol]);
  if (d.smart_money && d.smart_money[currentSymbol]) renderSmartMoney(d.smart_money[currentSymbol]);
  if (Array.isArray(d.execution_events)) renderExecutionEvents(d.execution_events);
  // Signals
  if (d.last_signal) prependSignal(d.last_signal);
  // 实时K线更新(仅当显示的周期与后端推送周期一致时)
  if (d.interval) streamInterval = d.interval;
  if (d.latest_klines && d.latest_klines[currentSymbol] &&
      document.getElementById('interval-select').value === streamInterval) {
    applyRealtimeKline(d.latest_klines[currentSymbol]);
  }
}

function fmt(v, dec) { return parseFloat(v).toFixed(dec); }

let lastIndicators = null;
let lastSmartMoney = null;
let lastAiPayload = null;
let lastAiSymbol = '';
let lastRecommendPayload = null;
let lastNewsPayload = null;
let lastExecutionEvents = [];

function renderIndicators(ind) {
  lastIndicators = ind;
  renderChartInfoPanel();
  const ribbon = ind.ribbon > 0 ? tr('bullish') : ind.ribbon < 0 ? tr('bearish') : tr('mixed');
  const items = [
    [tr('indicatorPrice'), ind.price], [tr('score'), ind.score],
    ['RSI', ind.rsi], [tr('stochRsi'), ind.stoch_k],
    ['MACD', ind.macd], [tr('macdHistogram'), ind.macd_hist],
    ['EMA9', ind.ema9], ['EMA21', ind.ema21],
    [tr('bollingerUpper'), ind.bb_upper], [tr('bollingerLower'), ind.bb_lower],
    ['VWAP', ind.vwap], [tr('vwapDeviation'), ind.vwap_dist_pct + '%'],
    ['ATR', ind.atr], [tr('bollingerWidth'), ind.bb_width + '%'],
    [tr('ribbon'), ribbon],
    [tr('htfTrend'), ind.htf_trend > 0 ? tr('long') : ind.htf_trend < 0 ? tr('short') : '-'],
    [tr('swingPattern'), localizeRuntimeText(ind.swing_pattern || '--')],
    [tr('support'), ind.sr_support ?? '--'],
    [tr('resistance'), ind.sr_resistance ?? '--'],
    [tr('mainIntent'), ind.main_intent ? `${localizeRuntimeText(ind.main_intent)}${ind.main_intent_confidence ? ' ' + ind.main_intent_confidence + '%' : ''}` : '--'],
  ];
  document.getElementById('ind-grid').innerHTML = items.map(([k,v]) =>
    `<div class="ind-item"><div class="k">${k}</div><div class="v">${v ?? '--'}</div></div>`
  ).join('');
  const score = ind.score || 0;
  const el = document.getElementById('score-val');
  el.textContent = score > 0 ? '+' + score : score;
  el.className = 'score-value ' + (score >= 60 ? 'long' : score <= -60 ? 'short' : 'neutral');
  const fill = document.getElementById('score-fill');
  const pct = Math.min(Math.abs(score), 100);
  fill.style.width = pct + '%';
  fill.style.background = score >= 60 ? 'var(--green)' : score <= -60 ? 'var(--red)' : 'var(--text-2)';
}

function renderSmartMoney(sm) {
  lastSmartMoney = sm;
  const el = document.getElementById('smart-money-card');
  if (!el || !sm) return;
  const dir = sm.direction === 'LONG' ? 'long' : sm.direction === 'SHORT' ? 'short' : 'neutral';
  const score = Number(sm.score || 0);
  const tt = sm.top_trader || {};
  const ta = sm.top_trader_account || {};
  const ls = sm.long_short || {};
  const oi = sm.open_interest || {};
  const topComponents = (sm.components || []).slice()
    .sort((a,b)=>Math.abs(Number(b.points||0))-Math.abs(Number(a.points||0)))
    .slice(0,2)
    .map(c=>`${localizeRuntimeText(c.name)} ${Number(c.points||0)>=0?'+':''}${c.points}`)
    .join(' · ');
  el.className = `smart-card ${dir}`;
  el.innerHTML = `
    <div class="smart-head">
      <span class="smart-title">${tr('smartMoney')}</span>
      <span class="smart-score" style="color:${dir==='long'?'var(--green)':dir==='short'?'var(--red)':'var(--text-1)'}">${score>=0?'+':''}${score}</span>
      <span class="smart-label ${dir}">${escapeHtml(localizeRuntimeText(sm.label || '\u667a\u80fd\u8d44\u91d1\u89c2\u671b'))}</span>
    </div>
    <div class="smart-grid">
      <span>${txt('大户持仓', 'Top trader OI')} <b>${tt.ratio ?? '--'}</b></span>
      <span>${txt('大户账户', 'Top trader accounts')} <b>${ta.ratio ?? '--'}</b></span>
      <span>${txt('全市场账户', 'Market accounts')} <b>${ls.ratio ?? '--'}</b></span>
      <span>OI 1h <b>${oi.change_1h_pct>=0?'+':''}${oi.change_1h_pct ?? '--'}%</b></span>
      <span>${tr('indicatorPrice')} 1h <b>${sm.price_change_1h>=0?'+':''}${sm.price_change_1h ?? '--'}%</b></span>
      <span>${txt('数据质量', 'Data quality')} <b>${Math.round(Number(sm.data_quality||0)*100)}%</b></span>
    </div>
    <div class="smart-reason">${escapeHtml(localizeRuntimeText(topComponents || sm.interpretation || '方向尚未形成共振'))}</div>`;
}

function renderPositions(positions) {
  const el = document.getElementById('pos-list');
  if (!positions.length) { el.innerHTML = `<div class="empty-state">${tr('noPositions')}</div>`; if (chart) renderChart(); return; }
  el.innerHTML = positions.map(p => {
    const sideClass = String(p.side || '').toLowerCase();
    return `
    <div class="pos-card ${sideClass}">
      <div class="pos-header">
        <span class="pos-sym">${p.symbol}</span>
        <span class="pos-side-tag ${sideClass}">${displaySide(p.side, true)} ${p.leverage}x</span>
      </div>
      <div class="pos-details">
        <span>${tr('quantity')}: ${p.qty}</span>
        <span>${tr('entryPrice')}: ${p.entry_price}</span>
        <span>${tr('markPrice')}: ${p.mark_price}</span>
        <span class="pnl" style="color:${p.unrealized_pnl>=0?'var(--green)':'var(--red)'}">${tr('pnl')}: ${fmt(p.unrealized_pnl,3)}</span>
      </div>
      <button class="pos-close-btn" onclick="closePosition('${p.symbol}')">${tr('closePosition')}</button>
    </div>`;
   }).join('');
  if (chart) renderChart();
}

let lastSigTime = '';
let signalHistory = [];
function renderSignals() {
  const el = document.getElementById('bottom-signals');
  if (!el || !signalHistory.length) return;
  el.innerHTML = signalHistory.map(sig => {
    const isLong = sig.signal === '\u5f00\u591a' || sig.signal === 'LONG';
    const cls = isLong ? 'long' : 'short';
    const factors = (sig.factors || []).map(f => {
      const bull = f.includes('+') && !f.includes('-');
       return `<span class="factor-tag ${bull?'bull':'bear'}">${localizeRuntimeText(f)}</span>`;
    }).join('');
    return `<div class="signal-item" onclick="selectSymbolAndShow('${escapeJsStr(sig.symbol)}')" style="cursor:pointer;" title="点击切换至 ${escapeHtml(sig.symbol)} 图表">
      <span class="signal-time">${sig.time}</span>
      <span class="signal-badge ${cls}">${displaySide(isLong ? 'LONG' : 'SHORT')}</span>
      <div class="signal-body">
        <span class="signal-sym">${sig.symbol}</span>
        <span class="signal-score">${tr('score')}: ${sig.score || '--'}</span>
        <span class="signal-price">@ ${sig.price}</span>
       <div class="signal-factors">${factors || localizeRuntimeText(sig.reason || '')}</div>
      </div>
    </div>`;
  }).join('');
}
function prependSignal(sig) {
  if (!sig || sig.time === lastSigTime) return;
  lastSigTime = sig.time;
  signalHistory.unshift(sig);
  if (signalHistory.length > 30) signalHistory.pop();
  renderSignals();
}

// ===== Tabs =====
function switchSideTab(el) {
  document.querySelectorAll('.side-tab').forEach(t => { t.classList.remove('active'); t.setAttribute('aria-selected', 'false'); });
  el.classList.add('active');
  el.setAttribute('aria-selected', 'true');
  try { el.scrollIntoView({ block: 'nearest', inline: 'nearest' }); } catch (_) {}
  const sidePanel = document.querySelector('.side-panel');
  if (sidePanel && sidePanel.classList.contains('collapsed')) {
    if (typeof toggleSidePanelCollapse === 'function') {
      toggleSidePanelCollapse(false);
    }
  }
  ['indicators','ai','obsidian','positions','rankings','recommend'].forEach(id => {
    const p = document.getElementById('side-'+id);
    if (p) p.style.display = id === el.dataset.tab ? '' : 'none';
  });
  if (el.dataset.tab === 'ai') loadAIAnalysis();
  if (el.dataset.tab === 'obsidian') loadObsidianStrategyMatch(currentSymbol);
  if (el.dataset.tab === 'rankings') loadMarketRankings();
  if (el.dataset.tab === 'recommend') loadRecommend();
}

let rankingData = null;
let activeRanking = 'gainers';
async function loadMarketRankings(force) {
  const maxPrice = Math.max(0.000001, Number(document.getElementById('rank-max-price').value || 5));
  const list = document.getElementById('rank-list');
  list.innerHTML = `<div class="empty-state">${tr('rankingsLoading')}</div>`;
  try {
    const response = await fetch(`/api/market_rankings?max_price=${encodeURIComponent(maxPrice)}&limit=20`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    rankingData = await response.json();
    renderMarketRanking();
  } catch (error) {
    list.innerHTML = `<div class="empty-state">${tr('rankingsFailed')}${escapeHtml(error.message)}</div>`;
  }
}
function switchRanking(button) {
  document.querySelectorAll('.rank-tab').forEach(item => item.classList.remove('active'));
  button.classList.add('active');
  activeRanking = button.dataset.rank;
  renderMarketRanking();
}
function formatRankVolume(value) {
  const n = Number(value || 0);
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return n.toFixed(0);
}
function selectSymbolAndShow(symbol) {
  if (!symbol) return;
  const select = document.getElementById('symbol-select');
  if (select && ![...select.options].some(option => option.value === symbol)) {
    select.add(new Option(symbol, symbol));
  }
  if (select) select.value = symbol;
  currentSymbol = symbol;
  switchView('single');
  loadKlines();
  loadAIAnalysis();
}

function selectRankingSymbol(symbol) {
  selectSymbolAndShow(symbol);
}
// ===== Reports Hub Dropdown Handlers =====
function toggleReportsDropdown(e) {
  if (e) e.stopPropagation();
  const menu = document.getElementById('reports-dropdown-menu');
  if (!menu) return;
  menu.style.display = (menu.style.display === 'none' || !menu.style.display) ? 'block' : 'none';
}
function closeReportsDropdown() {
  const menu = document.getElementById('reports-dropdown-menu');
  if (menu) menu.style.display = 'none';
}
window.toggleReportsDropdown = toggleReportsDropdown;
window.closeReportsDropdown = closeReportsDropdown;
window.addEventListener('click', function(e) {
  const dropdown = document.querySelector('.reports-hub-dropdown');
  if (dropdown && !dropdown.contains(e.target)) {
    closeReportsDropdown();
  }
});

// ===== Quick Order Modal Controller =====
let currentQuickOrder = {
  symbol: '',
  price: 0,
  side: 'LONG',
  leverage: 5,
  margin: 20,
  maxLeverage: 50,
  stepSize: '1',
  tickSize: '0.01',
  sl: null,
  tp: null,
  submitting: false,
};

async function openQuickOrderModal(symbol, initSide, initLev, initMargin, initSl, initTp) {
  const overlay = document.getElementById('quick-order-overlay');
  if (!overlay) return;
  overlay.style.display = 'flex';

  const savedLev = parseInt(localStorage.getItem('qo_last_leverage')) || 5;
  const savedMargin = parseFloat(localStorage.getItem('qo_last_margin')) || 20;

  currentQuickOrder = {
    symbol: symbol,
    price: 0,
    side: (initSide || 'LONG').toUpperCase(),
    leverage: initLev != null ? parseInt(initLev) : savedLev,
    margin: initMargin != null ? parseFloat(initMargin) : savedMargin,
    maxLeverage: 50,
    stepSize: '1',
    tickSize: '0.01',
    sl: initSl != null ? parseFloat(initSl) : null,
    tp: initTp != null ? parseFloat(initTp) : null,
    submitting: false,
  };

  document.getElementById('qo-symbol').textContent = symbol;
  document.getElementById('qo-price').textContent = '加载中...';
  document.getElementById('qo-change').textContent = '';
  document.getElementById('qo-error-msg').style.display = 'none';
  document.getElementById('qo-error-msg').textContent = '';

  setQuickOrderSide(currentQuickOrder.side);
  setQuickOrderLeverage(currentQuickOrder.leverage, false);
  setQuickOrderMargin(currentQuickOrder.margin, false);

  try {
    const res = await fetch(`/api/rank_preview?symbol=${encodeURIComponent(symbol)}&leverage=${currentQuickOrder.leverage}&margin=${currentQuickOrder.margin}&side=${currentQuickOrder.side}`);
    const p = await res.json();
    if (p.ok) {
      currentQuickOrder.price = parseFloat(p.price) || 0;
      currentQuickOrder.maxLeverage = p.max_leverage || 50;
      if (p.step_size) currentQuickOrder.stepSize = p.step_size;
      if (p.tick_size) currentQuickOrder.tickSize = p.tick_size;

      if (!initSide && p.side) {
        setQuickOrderSide(p.side);
      }
      if (p.max_leverage) {
        document.getElementById('qo-max-lev').textContent = p.max_leverage;
        document.getElementById('qo-lev-slider').max = Math.min(p.max_leverage, 50);
        document.getElementById('qo-lev-input').max = p.max_leverage;
      }
      if (p.balance != null) {
        document.getElementById('qo-user-balance').textContent = Number(p.balance).toFixed(2);
      }
      document.getElementById('qo-price').textContent = p.price ? Number(p.price).toPrecision(6) : '--';
      const scoreText = p.score != null ? `策略评分 ${p.score}` : '多因子扫描';
      document.getElementById('qo-score-tag').textContent = scoreText;

      if (initSl == null && p.sl != null) currentQuickOrder.sl = p.sl;
      if (initTp == null && p.tp1 != null) currentQuickOrder.tp = p.tp1;

      document.getElementById('qo-sl-input').value = currentQuickOrder.sl != null ? currentQuickOrder.sl : '';
      document.getElementById('qo-tp-input').value = currentQuickOrder.tp != null ? currentQuickOrder.tp : '';

      recalcQuickOrder();
    } else {
      document.getElementById('qo-error-msg').textContent = p.error || '获取行情分析失败';
      document.getElementById('qo-error-msg').style.display = 'block';
      if (p.price) {
        currentQuickOrder.price = parseFloat(p.price);
        document.getElementById('qo-price').textContent = Number(p.price).toPrecision(6);
        recalcQuickOrder();
      }
    }
  } catch (e) {
    document.getElementById('qo-error-msg').textContent = '连接失败: ' + e.message;
    document.getElementById('qo-error-msg').style.display = 'block';
  }
}

function closeQuickOrderModal() {
  const overlay = document.getElementById('quick-order-overlay');
  if (overlay) overlay.style.display = 'none';
}

function setQuickOrderSide(side) {
  currentQuickOrder.side = side;
  const isLong = side === 'LONG';
  const longBtn = document.getElementById('qo-btn-long');
  const shortBtn = document.getElementById('qo-btn-short');
  const submitBtn = document.getElementById('qo-submit-btn');
  if (longBtn) longBtn.classList.toggle('active', isLong);
  if (shortBtn) shortBtn.classList.toggle('active', !isLong);
  if (submitBtn) {
    submitBtn.className = `qo-btn-submit ${isLong ? 'long' : 'short'}`;
    submitBtn.textContent = isLong ? `🟢 立即做多 ${currentQuickOrder.symbol || ''}` : `🔴 立即做空 ${currentQuickOrder.symbol || ''}`;
  }
  recalcQuickOrder();
}

function setQuickOrderLeverage(lev, triggerRecalc = true) {
  lev = parseInt(lev) || 1;
  const maxLev = currentQuickOrder.maxLeverage || 50;
  if (lev > maxLev) lev = maxLev;
  if (lev < 1) lev = 1;
  currentQuickOrder.leverage = lev;
  document.getElementById('qo-lev-input').value = lev;
  document.getElementById('qo-lev-slider').value = Math.min(lev, parseInt(document.getElementById('qo-lev-slider').max) || 50);

  document.querySelectorAll('.qo-lev-pill').forEach(pill => {
    pill.classList.toggle('active', parseInt(pill.dataset.lev) === lev);
  });
  localStorage.setItem('qo_last_leverage', lev);
  if (triggerRecalc) recalcQuickOrder();
}

function onQuickOrderLevSlider(val) {
  setQuickOrderLeverage(val);
}

function onQuickOrderLevInput(val) {
  setQuickOrderLeverage(val);
}

function setQuickOrderMargin(margin, triggerRecalc = true) {
  margin = parseFloat(margin) || 10;
  if (margin <= 0) margin = 1;
  currentQuickOrder.margin = margin;
  document.getElementById('qo-margin-input').value = margin;

  document.querySelectorAll('.qo-margin-pill').forEach(pill => {
    pill.classList.toggle('active', parseFloat(pill.dataset.margin) === margin);
  });
  localStorage.setItem('qo_last_margin', margin);
  if (triggerRecalc) recalcQuickOrder();
}

function onQuickOrderMarginInput(val) {
  setQuickOrderMargin(val);
}

function onQuickOrderSlTpChange() {
  const slVal = parseFloat(document.getElementById('qo-sl-input').value);
  const tpVal = parseFloat(document.getElementById('qo-tp-input').value);
  currentQuickOrder.sl = !isNaN(slVal) ? slVal : null;
  currentQuickOrder.tp = !isNaN(tpVal) ? tpVal : null;
  recalcQuickOrder();
}

function recalcQuickOrder() {
  const lev = currentQuickOrder.leverage || 1;
  const margin = currentQuickOrder.margin || 10;
  const notional = margin * lev;
  document.getElementById('qo-calc-notional').textContent = `${notional.toFixed(2)} USDT`;

  const price = currentQuickOrder.price || 0;
  const isLong = (currentQuickOrder.side || 'LONG') === 'LONG';

  // 1. 预估强平价与安全缓冲感知 (Liquidation Impact Gauge)
  if (price > 0 && lev > 0) {
    const bufferPct = Math.max(0.6, (100 / lev) * 0.9);
    const estLiq = isLong ? price * (1 - bufferPct / 100) : price * (1 + bufferPct / 100);

    const liqPriceEl = document.getElementById('qo-est-liq-price');
    const bufferTextEl = document.getElementById('qo-liq-buffer-text');
    const barFillEl = document.getElementById('qo-liq-bar-fill');

    if (liqPriceEl) liqPriceEl.textContent = `${estLiq.toFixed(2)} U`;
    if (bufferTextEl && barFillEl) {
      if (lev <= 10) {
        bufferTextEl.textContent = `${bufferPct.toFixed(1)}% (极安全)`;
        bufferTextEl.style.color = 'var(--green)';
        barFillEl.style.width = '88%';
        barFillEl.style.background = 'var(--green)';
      } else if (lev <= 25) {
        bufferTextEl.textContent = `${bufferPct.toFixed(1)}% (适中)`;
        bufferTextEl.style.color = 'var(--yellow)';
        barFillEl.style.width = '55%';
        barFillEl.style.background = 'var(--yellow)';
      } else {
        bufferTextEl.textContent = `${bufferPct.toFixed(1)}% (极高风险)`;
        bufferTextEl.style.color = 'var(--red)';
        barFillEl.style.width = '20%';
        barFillEl.style.background = 'var(--red)';
      }
    }
  }

  // 2. 数量与止损风险测算
  if (price > 0) {
    const rawQty = notional / price;
    document.getElementById('qo-calc-qty').textContent = `${rawQty.toPrecision(5)}`;

    if (currentQuickOrder.sl) {
      const diff = Math.abs(price - currentQuickOrder.sl);
      const estLoss = rawQty * diff;
      const pct = margin > 0 ? ((estLoss / margin) * 100).toFixed(1) : '0';
      document.getElementById('qo-calc-risk').textContent = `-${estLoss.toFixed(2)} USDT (${pct}%)`;
    } else {
      document.getElementById('qo-calc-risk').textContent = '--';
    }

    // 3. 动态盈亏比测算 (Risk / Reward Ratio)
    const rrEl = document.getElementById('qo-rr-ratio');
    if (rrEl) {
      if (currentQuickOrder.sl && currentQuickOrder.tp) {
        const risk = Math.abs(price - currentQuickOrder.sl);
        const reward = Math.abs(currentQuickOrder.tp - price);
        if (risk > 0) {
          const rr = (reward / risk).toFixed(2);
          rrEl.textContent = `1 : ${rr}`;
          if (rr >= 2.0) {
            rrEl.style.color = 'var(--green)';
            rrEl.style.borderColor = 'var(--green-border)';
          } else if (rr >= 1.0) {
            rrEl.style.color = 'var(--yellow)';
            rrEl.style.borderColor = 'rgba(245,158,11,0.3)';
          } else {
            rrEl.style.color = 'var(--red)';
            rrEl.style.borderColor = 'var(--red-border)';
          }
        } else {
          rrEl.textContent = '--';
        }
      } else {
        rrEl.textContent = '输入SL与TP测算';
        rrEl.style.color = 'var(--text-2)';
        rrEl.style.borderColor = 'var(--border)';
      }
    }
  } else {
    document.getElementById('qo-calc-qty').textContent = '--';
    document.getElementById('qo-calc-risk').textContent = '--';
  }
}

async function submitQuickOrder() {
  if (currentQuickOrder.submitting) return;
  const submitBtn = document.getElementById('qo-submit-btn');
  const errEl = document.getElementById('qo-error-msg');
  errEl.style.display = 'none';

  const payload = {
    symbol: currentQuickOrder.symbol,
    side: currentQuickOrder.side,
    leverage: currentQuickOrder.leverage,
    margin: currentQuickOrder.margin,
    sl: currentQuickOrder.sl,
    tp: currentQuickOrder.tp,
  };

  currentQuickOrder.submitting = true;
  submitBtn.disabled = true;
  submitBtn.textContent = '正在提交订单...';

  try {
    const res = await fetch('/api/rank_one_click', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.error) {
      errEl.textContent = '下单被拒绝: ' + data.error;
      errEl.style.display = 'block';
      submitBtn.disabled = false;
      submitBtn.textContent = currentQuickOrder.side === 'LONG' ? `🟢 立即做多 ${currentQuickOrder.symbol}` : `🔴 立即做空 ${currentQuickOrder.symbol}`;
      currentQuickOrder.submitting = false;
      return;
    }

    closeQuickOrderModal();
    alert(`🎉 下单成功!\n` +
      `合约: ${data.symbol}\n` +
      `方向: ${data.side === 'LONG' ? '做多 🟢' : '做空 🔴'}\n` +
      `杠杆: ${data.leverage}x\n` +
      `成交量: ${data.qty} (投入 ${currentQuickOrder.margin}U, 名义 ${Number(data.notional || 0).toFixed(1)}U)\n` +
      `保护单: SL ${data.sl || '--'} / TP ${data.tp || '--'}`);

    const posTab = document.querySelector('.side-tab[data-tab="positions"]');
    if (posTab && typeof switchSideTab === 'function') switchSideTab(posTab);
  } catch (e) {
    errEl.textContent = '网络错误: ' + e.message;
    errEl.style.display = 'block';
  } finally {
    currentQuickOrder.submitting = false;
    submitBtn.disabled = false;
    submitBtn.textContent = currentQuickOrder.side === 'LONG' ? `🟢 立即做多 ${currentQuickOrder.symbol}` : `🔴 立即做空 ${currentQuickOrder.symbol}`;
  }
}

async function rankOneClick(symbol) {
  openQuickOrderModal(symbol);
}

window.openQuickOrderModal = openQuickOrderModal;
window.closeQuickOrderModal = closeQuickOrderModal;
window.setQuickOrderSide = setQuickOrderSide;
window.setQuickOrderLeverage = setQuickOrderLeverage;
window.onQuickOrderLevSlider = onQuickOrderLevSlider;
window.onQuickOrderLevInput = onQuickOrderLevInput;
window.setQuickOrderMargin = setQuickOrderMargin;
window.onQuickOrderMarginInput = onQuickOrderMarginInput;
window.onQuickOrderSlTpChange = onQuickOrderSlTpChange;
window.recalcQuickOrder = recalcQuickOrder;
window.submitQuickOrder = submitQuickOrder;
window.rankOneClick = rankOneClick;

function renderMarketRanking() {
  if (!rankingData) return;
  const rows = rankingData[activeRanking] || [];
  const list = document.getElementById('rank-list');
  const meta = document.getElementById('rank-meta');
  const names = {gainers:tr('gainers24h'), losers:tr('losers24h'), volume:tr('volume24h')};
  meta.textContent = `${tr('price')} < ${rankingData.max_price}U | ${tr('matched')} ${rankingData.matched} ${tr('contracts')} | ${names[activeRanking]} | ${rankingData.ts}`;
  if (!rows.length) {
    list.innerHTML = `<div class="empty-state">${tr('noContractsInRange')}</div>`;
    return;
  }
  list.innerHTML = `<div class="rank-head"><span>#</span><span>${tr('contract')}</span><span style="text-align:right">${tr('currentPrice')}</span><span style="text-align:right">${activeRanking === 'volume' ? tr('volume') : tr('change')}</span><span></span></div>` +
    rows.map((row, index) => {
      const change = Number(row.change_pct || 0);
      const value = activeRanking === 'volume'
        ? formatRankVolume(row.quote_volume)
        : `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
      const valueClass = activeRanking === 'volume' ? '' : (change >= 0 ? 'up' : 'down');
      return `<div class="rank-row" onclick="selectRankingSymbol('${escapeJsStr(row.symbol)}')">
        <span class="rank-no">${index + 1}</span>
        <span class="rank-symbol">${escapeHtml(row.symbol)}</span>
        <span class="rank-price">${Number(row.price).toPrecision(6)}</span>
        <span class="rank-value ${valueClass}">${value}</span>
        <span class="rank-action" style="display:flex;gap:4px;justify-content:flex-end">
          <button class="one-click-btn" onclick="event.stopPropagation();rankOneClick('${escapeJsStr(row.symbol)}')">${tr('oneClickOrder')}</button>
          <button class="one-click-btn" style="background:linear-gradient(135deg,#7c3aed,#2563eb);border-color:#6366f1;color:#fff" onclick="event.stopPropagation();generateBlogForSymbol('${escapeJsStr(row.symbol)}')">✍️ 创作</button>
        </span>
      </div>`;
    }).join('');
}
function switchBottomTab(el) {
  document.querySelectorAll('.bottom-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  const bottomPanel = document.querySelector('.bottom-panel');
  if (bottomPanel && bottomPanel.classList.contains('collapsed')) {
    if (typeof toggleBottomPanelCollapse === 'function') {
      toggleBottomPanelCollapse(false);
    }
  }
  ['signals','news','trades','execution'].forEach(id => {
    const b = document.getElementById('bottom-'+id);
    if (b) b.style.display = id === el.dataset.tab ? '' : 'none';
  });
  if (el.dataset.tab === 'news') loadNews();
  if (el.dataset.tab === 'trades') loadTrades();
  if (el.dataset.tab === 'execution') loadExecutionEvents();
}

// ===== Trade Records Feature Controller =====
let allTradesData = [];

function onTradesTimeFilterChange() {
  const val = document.getElementById('trades-time-filter')?.value || '7d';
  const customWrap = document.getElementById('trades-custom-date-wrap');
  if (val === 'custom') {
    if (customWrap) customWrap.style.display = 'inline-flex';
    const endInput = document.getElementById('trades-end-date');
    const startInput = document.getElementById('trades-start-date');
    const todayStr = new Date().toISOString().slice(0, 10);
    if (endInput && !endInput.value) endInput.value = todayStr;
    if (startInput && !startInput.value) {
      const prev = new Date();
      prev.setDate(prev.getDate() - 7);
      startInput.value = prev.toISOString().slice(0, 10);
    }
  } else {
    if (customWrap) customWrap.style.display = 'none';
    loadTrades();
  }
}

async function loadTrades(showToast = false) {
  const container = document.getElementById('trades-table-container');
  try {
    const timeFilter = document.getElementById('trades-time-filter')?.value || '7d';
    let url = `/api/trades?time_range=${encodeURIComponent(timeFilter)}&limit=500`;
    if (timeFilter === 'custom') {
      const startDate = document.getElementById('trades-start-date')?.value || '';
      const endDate = document.getElementById('trades-end-date')?.value || '';
      if (startDate) url += `&start_date=${encodeURIComponent(startDate)}`;
      if (endDate) url += `&end_date=${encodeURIComponent(endDate)}`;
    }

    const res = await fetch(url);
    const d = await res.json();
    if (d.status === 'ok') {
      allTradesData = d.trades || [];
      const s = d.summary || {};
      const countEl = document.getElementById('trades-count-badge');
      const pnlEl = document.getElementById('trades-pnl-badge');
      const winEl = document.getElementById('trades-winrate-badge');
      const feeEl = document.getElementById('trades-fee-badge');

      if (countEl) countEl.textContent = s.total_trades || 0;
      if (pnlEl) {
        const pnl = Number(s.total_pnl || 0);
        pnlEl.textContent = `${pnl >= 0 ? '+' : ''}${pnl.toFixed(4)} U`;
        pnlEl.className = pnl >= 0 ? 'pos' : 'neg';
      }
      if (winEl) winEl.textContent = `${s.win_rate || 0}% (${s.win_count || 0}胜/${s.loss_count || 0}负)`;
      if (feeEl) feeEl.textContent = `${(s.total_commission || 0).toFixed(4)} U`;

      const symSelect = document.getElementById('trades-symbol-filter');
      if (symSelect && d.symbols && d.symbols.length > 0) {
        const curVal = symSelect.value;
        let optsHtml = '<option value="">全部标的</option>';
        d.symbols.forEach(sym => {
          optsHtml += `<option value="${escapeHtml(sym)}"${sym === curVal ? ' selected' : ''}>${escapeHtml(sym)}</option>`;
        });
        symSelect.innerHTML = optsHtml;
      }

      filterTradesList();
      if (showToast && typeof showToolToast === 'function') {
        showToolToast(`成交记录已同步，共 ${allTradesData.length} 笔记录`, 'success');
      }
    } else {
      if (container) container.innerHTML = `<div class="empty-state">加载失败: ${escapeHtml(d.error || '未知错误')}</div>`;
    }
  } catch(err) {
    console.error('loadTrades error:', err);
    if (container) container.innerHTML = `<div class="empty-state">网络异常，未能加载成交记录</div>`;
  }
}

function filterTradesList() {
  const symFilter = document.getElementById('trades-symbol-filter')?.value || '';
  const typeFilter = document.getElementById('trades-type-filter')?.value || '';

  let filtered = allTradesData;
  if (symFilter) {
    filtered = filtered.filter(t => (t.symbol || '').toUpperCase() === symFilter.toUpperCase());
  }
  if (typeFilter) {
    filtered = filtered.filter(t => (t.type || '').toLowerCase() === typeFilter.toLowerCase());
  }
  renderTradesList(filtered);
}

function renderTradesList(trades) {
  const container = document.getElementById('trades-table-container');
  if (!container) return;

  if (!trades || trades.length === 0) {
    container.innerHTML = '<div class="empty-state">暂无符合条件的成交记录</div>';
    return;
  }

  const rowsHtml = trades.map(t => {
    const isClose = (t.type || '').toLowerCase() === 'close';
    const isLong = (t.side || '').toUpperCase().includes('BUY') || (t.side || '').toUpperCase().includes('LONG');
    const sideClass = isLong ? 'long' : 'short';
    const sideText = displaySide(t.side || (isLong ? 'LONG' : 'SHORT'));
    const typeBadge = isClose ? '<span class="trade-type-badge close">平仓</span>' : '<span class="trade-type-badge open">开仓</span>';
    
    let pnlHtml = '--';
    let pnlPctHtml = '--';
    if (isClose && t.pnl !== undefined && t.pnl !== null) {
      const pnl = Number(t.pnl || 0);
      const pnlPct = Number(t.pnl_pct || 0);
      const pnlCls = pnl >= 0 ? 'pos' : 'neg';
      pnlHtml = `<span class="trade-pnl ${pnlCls}">${pnl >= 0 ? '+' : ''}${pnl.toFixed(4)}</span>`;
      pnlPctHtml = `<span class="trade-pnl-pct ${pnlCls}">${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%</span>`;
    }

    const price = t.price !== undefined ? Number(t.price).toFixed(4) : '--';
    const qty = t.qty !== undefined ? Number(t.qty) : '--';
    const fee = t.commission !== undefined ? `${Number(t.commission).toFixed(4)} ${escapeHtml(t.commission_asset || 'USDT')}` : '0.0000 USDT';
    const reason = t.reason ? `<span class="trade-reason-tag">${escapeHtml(t.reason)}</span>` : '<span style="color:var(--text-3)">-</span>';
    
    // 优雅呈现日期与时间
    const dateStr = t.date || (t.datetime ? t.datetime.slice(0, 10) : '');
    const timeOnly = t.time || (t.datetime ? t.datetime.slice(11) : '');
    let timeHtml = '';
    if (dateStr && timeOnly) {
      const shortDate = dateStr.length >= 10 ? dateStr.slice(5) : dateStr;
      timeHtml = `<span style="color:var(--text-2);margin-right:5px;font-family:monospace;">${escapeHtml(shortDate)}</span><span style="font-family:monospace;font-weight:600;">${escapeHtml(timeOnly)}</span>`;
    } else {
      timeHtml = `<span style="font-family:monospace;color:var(--text-2);">${escapeHtml(t.datetime || t.time || t.timestamp || '--')}</span>`;
    }
    const sym = escapeHtml(t.symbol || '--');

    return `<tr class="trade-row">
      <td style="white-space:nowrap;">${timeHtml}</td>
      <td><span class="trade-symbol-link" onclick="selectSymbolAndShow('${escapeJsStr(t.symbol)}')">${sym}</span></td>
      <td>${typeBadge} <span class="trade-side-badge ${sideClass}">${sideText}</span></td>
      <td style="font-family:monospace;text-align:right;">${price}</td>
      <td style="font-family:monospace;text-align:right;">${qty}</td>
      <td style="text-align:right;">${pnlHtml}</td>
      <td style="text-align:right;">${pnlPctHtml}</td>
      <td style="font-size:11px;color:var(--text-2);text-align:right;">${fee}</td>
      <td>${reason}</td>
    </tr>`;
  }).join('');

  container.innerHTML = `
    <table class="trades-data-table">
      <thead>
        <tr>
          <th>时间 (日期/时刻)</th>
          <th>标的</th>
          <th>操作 / 方向</th>
          <th style="text-align:right;">成交均价</th>
          <th style="text-align:right;">数量</th>
          <th style="text-align:right;">已实现盈亏 (U)</th>
          <th style="text-align:right;">收益率</th>
          <th style="text-align:right;">手续费</th>
          <th>平仓 / 触发原因</th>
        </tr>
      </thead>
      <tbody>
        ${rowsHtml}
      </tbody>
    </table>
  `;
}

async function syncAndRefreshTrades() {
  const btn = event?.currentTarget || document.querySelector('#bottom-trades .tab-action-btn.primary');
  const origText = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = '🔄 同步中...'; }
  await loadTrades(true);
  if (btn) { btn.disabled = false; btn.textContent = origText || '🔄 刷新同步币安'; }
}

function exportTradesCsv() {
  if (!allTradesData || allTradesData.length === 0) {
    alert('暂无成交记录可导出');
    return;
  }
  const headers = ['日期', '时刻', '完整时间', '标的', '类型', '方向', '成交均价', '数量', '已实现盈亏(USDT)', '收益率(%)', '手续费', '手续费币种', '原因', '订单ID'];
  const csvRows = [headers.join(',')];

  allTradesData.forEach(t => {
    const isClose = (t.type || '').toLowerCase() === 'close';
    const dateVal = t.date || (t.datetime ? t.datetime.slice(0, 10) : '');
    const timeVal = t.time || (t.datetime ? t.datetime.slice(11) : '');
    const fullTimeVal = t.datetime || `${dateVal} ${timeVal}`.trim();
    const row = [
      `"${dateVal}"`,
      `"${timeVal}"`,
      `"${fullTimeVal}"`,
      `"${t.symbol || ''}"`,
      `"${isClose ? '平仓' : '开仓'}"`,
      `"${t.side || ''}"`,
      `"${t.price || 0}"`,
      `"${t.qty || 0}"`,
      `"${t.pnl !== undefined ? t.pnl : ''}"`,
      `"${t.pnl_pct !== undefined ? t.pnl_pct : ''}"`,
      `"${t.commission || 0}"`,
      `"${t.commission_asset || 'USDT'}"`,
      `"${(t.reason || '').replace(/"/g, '""')}"`,
      `"${t.order_id || ''}"`
    ];
    csvRows.push(row.join(','));
  });

  const blob = new Blob(['\uFEFF' + csvRows.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const timeFilter = document.getElementById('trades-time-filter')?.value || 'range';
  const dt = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
  a.download = `binance_trades_${timeFilter}_${dt}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ===== Execution Diagnostics Controller =====
let currentDiagFilter = 'all';

function filterDiagEvents(filter, btn) {
  currentDiagFilter = filter;
  document.querySelectorAll('.diag-filter-chip').forEach(c => c.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderFilteredExecutionEvents();
}

async function loadExecutionEvents() {
  try {
    const res = await fetch('/api/execution_events?limit=50');
    const d = await res.json();
    if (d.status === 'ok') {
      const eng = d.engine_status || {};
      const apiStatusEl = document.getElementById('diag-api-status');
      const apiLatencyEl = document.getElementById('diag-api-latency');
      const timeOffsetEl = document.getElementById('diag-time-offset');
      const riskStatusEl = document.getElementById('diag-risk-status');
      const riskDetailEl = document.getElementById('diag-risk-detail');
      const autoStatusEl = document.getElementById('diag-auto-status');
      const posQuotaEl = document.getElementById('diag-pos-quota');
      const aiStatusEl = document.getElementById('diag-ai-status');

      if (apiStatusEl) {
        apiStatusEl.innerHTML = eng.connected 
          ? '<span class="status-dot green"></span> 正常连接' 
          : '<span class="status-dot red"></span> 离线 / 待重试';
      }
      if (apiLatencyEl && eng.latency_ms !== null && eng.latency_ms !== undefined) {
        apiLatencyEl.textContent = `(${eng.latency_ms} ms)`;
      }
      if (timeOffsetEl) {
        timeOffsetEl.textContent = `服务器时间: ${eng.server_time || '--'}`;
      }

      if (riskStatusEl) {
        riskStatusEl.innerHTML = eng.risk_blocked
          ? '<span style="color:#ef4444;font-weight:bold;">⚠️ 触发风控熔断</span>'
          : '<span style="color:#10b981;font-weight:bold;">🛡️ 运行安全</span>';
      }
      if (riskDetailEl) {
        riskDetailEl.textContent = `日损: ${eng.daily_loss_pct || 0}% / 熔断线 ${eng.max_daily_loss_pct || 5}%`;
      }

      if (autoStatusEl) {
        autoStatusEl.innerHTML = eng.auto_trade
          ? '<span style="color:#38bdf8;font-weight:bold;">🟢 实盘全自动开启</span>'
          : '<span style="color:var(--text-3);">⏸️ 暂停托管 / 半自动</span>';
      }
      if (posQuotaEl) {
        posQuotaEl.textContent = `持仓配额: ${eng.active_positions || 0} / ${eng.max_positions || 3} 仓`;
      }

      if (aiStatusEl) {
        if (eng.entry_decision_mode === 'typesafe_jev') {
          aiStatusEl.innerHTML = '<span style="color:#0ea5e9;font-weight:bold;">🧠 Jev 毫秒级风控</span>';
        } else if (eng.entry_decision_mode === 'committee') {
          aiStatusEl.textContent = '🤖 投委会双重风控';
        } else {
          aiStatusEl.textContent = '⚡ 策略直通执行';
        }
      }

      renderExecutionEvents(d.events || []);
    }
  } catch(e) {
    console.error('loadExecutionEvents error:', e);
  }
}

async function runDiagnosticsSelfCheck() {
  const btn = document.getElementById('btn-diag-self-check');
  const origText = btn ? btn.textContent : '';
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⚡ 自检中...';
  }

  try {
    const sym = currentSymbol || 'BTCUSDT';
    const res = await fetch('/api/execution_diagnostics/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol: sym })
    });
    const d = await res.json();
    if (d.ok) {
      const data = d.data || {};
      const minNotionalEl = document.getElementById('diag-min-notional');
      if (minNotionalEl) {
        minNotionalEl.textContent = `最小名义: $${data.min_notional} · 步长: ${data.step_size}`;
      }
      const latencyEl = document.getElementById('diag-api-latency');
      if (latencyEl) {
        latencyEl.textContent = `(${data.latency_ms} ms)`;
      }
      await loadExecutionEvents();
      alert(`✅ 实盘通道自检通过！\n标的: ${data.symbol}\n往返延迟: ${data.latency_ms} ms\n最小名义价值: $${data.min_notional}\n下单步长: ${data.step_size}\n合约可用余额: $${Number(data.balance).toFixed(2)}`);
    } else {
      alert(`❌ 实盘通道自检未通过: ${d.error || '未知异常'}`);
    }
  } catch(err) {
    alert('自检网络请求异常: ' + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = origText || '⚡ 一键自检';
    }
  }
}

function renderFilteredExecutionEvents() {
  const listEl = document.getElementById('execution-events-list') || document.getElementById('bottom-execution');
  if (!listEl) return;

  let events = [...lastExecutionEvents];
  if (currentDiagFilter === 'success') {
    events = events.filter(e => e.outcome === 'success');
  } else if (currentDiagFilter === 'failed') {
    events = events.filter(e => ['failed', 'blocked', 'rejected'].includes(e.outcome));
  } else if (currentDiagFilter === 'skipped') {
    events = events.filter(e => ['skipped', 'idle'].includes(e.outcome));
  }

  if (!events.length) {
    listEl.innerHTML = `<div class="empty-state">${tr('noExecutionEvents')}</div>`;
    return;
  }

  const actionNames = {
    OPEN: tr('executionOpen'), CLOSE: tr('executionClose'),
    MANUAL_OPEN: tr('executionManualOpen'), RECOMMEND_OPEN: tr('executionRecommendOpen'),
    DIAGNOSTIC_TEST: '实盘自检测试', SYSTEM_START: '系统初始化', RISK_CHECK: '风控状态巡检'
  };
  const outcomeNames = {
    success: tr('executionSuccess'),
    partial: tr('executionPartial'),
    failed: tr('executionFailed'),
    skipped: tr('executionSkipped'),
    blocked: '风控拦截'
  };
  const n = v => (v === undefined || v === null || v === '') ? '--' : Number(v).toString();

  listEl.innerHTML = events.reverse().map(e => {
    const outcome = ['success','partial','failed','skipped','blocked'].includes(e.outcome) ? e.outcome : 'failed';
    const actionLabel = actionNames[e.action] || e.action || tr('executionOrder');
    const symLabel = e.symbol ? escapeHtml(e.symbol) : '--';
    const sideLabel = e.side ? displaySide(e.side) : '';
    const title = `${actionLabel} ${symLabel} ${sideLabel}`.trim();
    
    let qty = '';
    if (e.requested_qty !== undefined || e.normalized_qty !== undefined || e.executed_qty !== undefined) {
      qty = `${tr('requestedQuantity')} ${n(e.requested_qty)} -> ${tr('normalizedQuantity')} ${n(e.normalized_qty)} -> ${tr('executedQuantity')} ${n(e.executed_qty)}`;
    }
    let order = '';
    if (e.exchange_status || e.order_id) {
      order = `${tr('status')} ${escapeHtml(e.exchange_status || '--')} | ${tr('orderId')} ${escapeHtml(e.order_id || '--')}`;
    }
    const reason = e.reason ? `<span style="margin-left:6px;color:var(--text-2);font-size:11px;">[${escapeHtml(e.reason)}]</span>` : '';
    const error = escapeHtml(e.error || '');
    const detailLine = [qty, order].filter(Boolean).join(' | ');

    return `<div class="execution-item">
      <span class="execution-time">${escapeHtml(e.time || '--')}</span>
      <span class="execution-outcome ${outcome}">${outcomeNames[outcome] || outcome}</span>
      <div class="execution-main">
        <span class="execution-title">${title}</span>${reason}
        ${detailLine ? `<div class="execution-detail">${detailLine}</div>` : ''}
        ${error ? `<div class="execution-error">${error}</div>` : ''}
      </div>
    </div>`;
  }).join('');
}

function renderExecutionEvents(events) {
  lastExecutionEvents = Array.isArray(events) ? events : [];
  renderFilteredExecutionEvents();
}

// ===== Actions =====
async function toggleAuto() {
  const badge = document.getElementById('auto-badge');
  const enabled = badge.classList.contains('off');
  await fetch('/api/auto_trade', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({enabled}) });
}
async function closePosition(symbol) {
  if (!confirm(`平仓 ${symbol}?`)) return;
  try {
    const r = await fetch('/api/close', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({symbol}) });
    const d = await r.json();
    if (d.error) alert(`平仓失败: ${symbol}\n${d.error}`);
    else if (d.orderId || d.status) alert(`平仓成功: ${symbol}\n订单号 ${d.orderId || '-'} · ${d.status || ''}`);
    else if (d.msg) alert(d.msg);
    else alert(`平仓响应: ${symbol}\n` + JSON.stringify(d));
  } catch(e) { alert('平仓请求异常: ' + e.message); }
}
// ===== View Toggle & Positions Charts =====
let lastPositions = [];   // latest positions from WS

function switchView(view) {
  currentView = view;
  document.getElementById('view-single')?.classList.toggle('active', view === 'single');
  document.getElementById('view-positions')?.classList.toggle('active', view === 'positions');
  document.getElementById('view-equity')?.classList.toggle('active', view === 'equity');
  document.getElementById('view-momentum')?.classList.toggle('active', view === 'momentum');

  const klineEl = document.getElementById('kline-chart');
  const posGridEl = document.getElementById('positions-grid');
  const eqEl = document.getElementById('equity-view');
  const moEl = document.getElementById('momentum-view');
  const scorePanel = document.querySelector('.score-panel');
  const lineControls = document.querySelector('.chart-line-controls');
  const sysOverview = document.getElementById('system-overview');

  if (klineEl) klineEl.style.display = view === 'single' ? '' : 'none';
  if (posGridEl) posGridEl.style.display = view === 'positions' ? 'grid' : 'none';
  if (eqEl) eqEl.style.display = view === 'equity' ? 'block' : 'none';
  if (moEl) moEl.style.display = view === 'momentum' ? 'block' : 'none';
  if (scorePanel) scorePanel.style.display = view === 'single' ? '' : 'none';
  if (lineControls) lineControls.style.display = view === 'single' ? 'flex' : 'none';
  if (sysOverview) sysOverview.style.display = view === 'single' ? 'flex' : 'none';

  if (view === 'positions') {
    renderPositionsGrid(lastPositions);
    startPosRefresh();
  } else {
    stopPosRefresh();
  }

  if (view === 'equity') {
    renderEquityView();
  } else if (view === 'momentum') {
    renderMomentumView();
  } else if (view === 'single') {
    setTimeout(() => chart && chart.resize(), 50);
  }
}

async function renderEquityView() {
  const container = document.getElementById('equity-view');
  if (!container) return;
  if (!equityChart) {
    equityChart = echarts.init(container, currentTheme === 'light' ? null : 'dark');
    window.addEventListener('resize', () => equityChart && equityChart.resize());
  }

  equityChart.showLoading({ color: '#38bdf8', textColor: '#b0bdd0', maskColor: 'rgba(17,24,39,0.8)' });

  try {
    const res = await fetch('/api/daily_report');
    const rpt = await res.json();
    const records = (rpt.records || []).filter(r => r.type === 'close');

    let cumPnL = 0;
    const times = [];
    const cumPnlSeries = [];
    const barPnlSeries = [];

    if (records.length) {
      records.forEach((r, i) => {
        const pnl = Number(r.pnl || 0);
        cumPnL += pnl;
        times.push(r.time ? `${r.symbol || ''} ${r.time}` : `#${i + 1}`);
        cumPnlSeries.push(Number(cumPnL.toFixed(4)));
        barPnlSeries.push({
          value: Number(pnl.toFixed(4)),
          itemStyle: { color: pnl >= 0 ? '#10b981' : '#ef4444' }
        });
      });
    } else {
      times.push('初始');
      cumPnlSeries.push(0);
      barPnlSeries.push(0);
    }

    equityChart.hideLoading();
    equityChart.setOption({
      backgroundColor: 'transparent',
      title: {
        text: `📈 实盘累计已实现盈亏走势 · 净收益: ${cumPnL >= 0 ? '+' : ''}${cumPnL.toFixed(4)} USDT`,
        left: 20,
        top: 10,
        textStyle: { fontSize: 13, color: cumPnL >= 0 ? '#10b981' : '#ef4444', fontWeight: 'bold' }
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: THEMES[currentTheme].panelBg,
        borderColor: THEMES[currentTheme].border,
        textStyle: { fontSize: 12, color: THEMES[currentTheme].text0 }
      },
      legend: {
        data: ['累计净盈亏 (USDT)', '单笔盈亏 (USDT)'],
        top: 10,
        right: 20,
        textStyle: { color: THEMES[currentTheme].text2 }
      },
      grid: [
        { left: 50, right: 30, top: 50, height: '56%' },
        { left: 50, right: 30, top: '74%', height: '18%' }
      ],
      xAxis: [
        { type: 'category', data: times, gridIndex: 0, axisLine: { lineStyle: { color: THEMES[currentTheme].border } }, axisLabel: { fontSize: 10, color: THEMES[currentTheme].text2 } },
        { type: 'category', data: times, gridIndex: 1, axisLine: { lineStyle: { color: THEMES[currentTheme].border } }, axisLabel: { show: false } }
      ],
      yAxis: [
        { type: 'value', gridIndex: 0, scale: true, splitLine: { lineStyle: { color: THEMES[currentTheme].bg2 } }, axisLabel: { fontSize: 10, color: THEMES[currentTheme].text2 } },
        { type: 'value', gridIndex: 1, scale: true, splitLine: { show: false }, axisLabel: { fontSize: 9, color: THEMES[currentTheme].text2 } }
      ],
      series: [
        {
          name: '累计净盈亏 (USDT)',
          type: 'line',
          data: cumPnlSeries,
          gridIndex: 0,
          smooth: true,
          showSymbol: true,
          symbolSize: 6,
          itemStyle: { color: '#38bdf8', borderColor: '#ffffff', borderWidth: 1.5 },
          lineStyle: { width: 3, color: '#38bdf8', shadowBlur: 14, shadowColor: 'rgba(56, 189, 248, 0.55)' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(56, 189, 248, 0.38)' },
              { offset: 1, color: 'rgba(56, 189, 248, 0.01)' }
            ])
          },
          markLine: {
            silent: true,
            data: [{ yAxis: 0, lineStyle: { color: 'rgba(255, 255, 255, 0.25)', type: 'dashed' } }]
          }
        },
        {
          name: '单笔盈亏 (USDT)',
          type: 'bar',
          data: barPnlSeries,
          xAxisIndex: 1,
          yAxisIndex: 1,
          itemStyle: {
            borderRadius: [2, 2, 0, 0],
            color: p => (typeof p.data === 'object' ? p.data.value : p.data) >= 0 ? 'rgba(16, 185, 129, 0.85)' : 'rgba(244, 63, 94, 0.85)'
          }
        }
      ]
    });
  } catch (e) {
    equityChart.hideLoading();
    console.error('renderEquityView error', e);
  }
}

async function renderMomentumView() {
  const container = document.getElementById('momentum-view');
  if (!container) return;
  if (!momentumChart) {
    momentumChart = echarts.init(container, currentTheme === 'light' ? null : 'dark');
    momentumChart.on('click', params => {
      if (params.name) {
        currentSymbol = params.name;
        const sel = document.getElementById('symbol-select');
        if (sel) sel.value = currentSymbol;
        switchView('single');
        loadKlines();
      }
    });
    window.addEventListener('resize', () => momentumChart && momentumChart.resize());
  }

  momentumChart.showLoading({ color: '#f59e0b', textColor: '#b0bdd0', maskColor: 'rgba(17,24,39,0.8)' });

  try {
    const res = await fetch('/api/market_rankings?limit=15');
    const data = await res.json();
    const gainers = (data.gainers || []).slice(0, 10);
    const losers = (data.losers || []).slice(0, 10);

    const symbols = [];
    const chgData = [];

    losers.reverse().forEach(item => {
      symbols.push(item.symbol);
      chgData.push({
        value: Number(item.change_pct || 0),
        itemStyle: { color: '#ef4444' }
      });
    });
    gainers.forEach(item => {
      symbols.push(item.symbol);
      chgData.push({
        value: Number(item.change_pct || 0),
        itemStyle: { color: '#10b981' }
      });
    });

    momentumChart.hideLoading();
    momentumChart.setOption({
      backgroundColor: 'transparent',
      title: {
        text: '🌐 市场主力热点动能排行 (点击标的直接切换该币 K 线)',
        left: 20,
        top: 10,
        textStyle: { fontSize: 13, color: THEMES[currentTheme].text0, fontWeight: 'bold' }
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: THEMES[currentTheme].panelBg,
        borderColor: THEMES[currentTheme].border,
        textStyle: { color: THEMES[currentTheme].text0 },
        formatter: params => {
          const p = params[0];
          return `${p.name}<br/>24h 涨跌幅: <b style="color:${p.value >= 0 ? '#10b981' : '#ef4444'}">${p.value >= 0 ? '+' : ''}${p.value}%</b><br/><span style="color:${THEMES[currentTheme].text2}">点击可立即查看该币K线</span>`;
        }
      },
      grid: { left: 90, right: 40, top: 45, bottom: 25 },
      xAxis: {
        type: 'value',
        axisLabel: { formatter: '{value}%', color: THEMES[currentTheme].text2 },
        splitLine: { lineStyle: { color: THEMES[currentTheme].bg2 } }
      },
      yAxis: {
        type: 'category',
        data: symbols,
        axisLabel: { color: THEMES[currentTheme].text0, fontWeight: 'bold', fontSize: 11 },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: THEMES[currentTheme].border } }
      },
      series: [
        {
          name: '24h 涨跌幅',
          type: 'bar',
          data: chgData,
          label: {
            show: true,
            position: 'right',
            formatter: p => `${p.value >= 0 ? '+' : ''}${p.value}%`,
            fontSize: 10
          }
        }
      ]
    });
  } catch (e) {
    momentumChart.hideLoading();
    console.error('renderMomentumView error', e);
  }
}

function startPosRefresh() {
  stopPosRefresh();
  posRefreshTimer = setInterval(() => {
    if (currentView === 'positions') refreshPosCharts();
  }, 5000);
}
function stopPosRefresh() {
  if (posRefreshTimer) { clearInterval(posRefreshTimer); posRefreshTimer = null; }
}

async function refreshPosCharts() {
  // 只刷新当前持仓的图
  for (const sym of posChartSymbols) {
    await loadPosChart(sym);
  }
}

async function loadPosChart(symbol) {
  const inst = posCharts[symbol];
  if (!inst) return;
  try {
    const interval = document.getElementById('interval-select').value;
    const res = await fetch(`/api/klines/${symbol}?interval=${interval}&limit=100`);
    const data = await res.json();
    if (!data.length) return;
    const times = data.map(d => new Date(d.time).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',hour12:false}));
    const klines = data.map(d => [d.open, d.close, d.low, d.high]);
    inst.setOption({ xAxis: { data: times }, series: [{ data: klines }] });
    // 更新头部价格
    const priceEl = document.getElementById(`pos-price-${symbol}`);
    if (priceEl) priceEl.textContent = data[data.length-1].close;
  } catch(e) { /* ignore */ }
}

function renderPositionsGrid(positions) {
  lastPositions = positions || [];
  const grid = document.getElementById('positions-grid');
  const syms = lastPositions.map(p => p.symbol);

  // 清理已平仓的图
  for (const sym of Object.keys(posCharts)) {
    if (!syms.includes(sym)) {
      posCharts[sym].dispose();
      delete posCharts[sym];
    }
  }
  posChartSymbols = syms;

  if (!syms.length) {
    grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">${txt('暂无持仓', 'No positions')}</div>`;
    return;
  }

  // 构建/更新卡片
  grid.innerHTML = lastPositions.map(p => {
    const cls = p.side.toLowerCase();
    const pnlColor = p.unrealized_pnl >= 0 ? 'var(--green)' : 'var(--red)';
    return `
    <div class="pos-chart-card ${cls}">
      <div class="pos-chart-header">
        <span class="pos-chart-sym">${p.symbol}</span>
        <div class="pos-chart-meta">
          <span class="pos-side-tag ${cls}">${displaySide(p.side, true)} ${p.leverage}x</span>
          <span id="pos-price-${p.symbol}">${p.mark_price}</span>
          <span class="pos-chart-pnl" style="color:${pnlColor}">${p.unrealized_pnl >= 0 ? '+' : ''}${fmt(p.unrealized_pnl, 3)}</span>
        </div>
      </div>
      <div class="pos-chart-body" id="pos-chart-${p.symbol}"></div>
    </div>`;
  }).join('');

  // 初始化ECharts实例
  for (const p of lastPositions) {
    const el = document.getElementById(`pos-chart-${p.symbol}`);
    if (!el) continue;
    if (posCharts[p.symbol]) {
      posCharts[p.symbol].dispose();
    }
    const inst = echarts.init(el, currentTheme === 'light' ? null : 'dark');
    inst.setOption({
      backgroundColor: 'transparent',
      animation: false,
      grid: { left: 48, right: 8, top: 8, bottom: 18 },
      xAxis: { type: 'category', data: [], axisLine: { lineStyle: { color: THEMES[currentTheme].border } }, axisLabel: { fontSize: 8, color: THEMES[currentTheme].text2 }, splitLine: { show: false } },
      yAxis: { scale: true, splitLine: { lineStyle: { color: THEMES[currentTheme].bg2 } }, axisLabel: { fontSize: 8, color: THEMES[currentTheme].text2 } },
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' }, backgroundColor: THEMES[currentTheme].panelBg, borderColor: THEMES[currentTheme].border, textStyle: { fontSize: 10 },
        formatter: function(params) {
          const p = params.filter(x => x.seriesType === 'candlestick')[0];
          if (!p) return '';
          const d = p.data;
          const dir = d[1] >= d[0] ? '▲' : '▼';
          const col = d[1] >= d[0] ? '#10b981' : '#ef4444';
          const fmt = v => Number(v).toFixed(8).replace(/0+$/, '').replace(/\.$/, '');
          let h = `<div style="font-size:10px;line-height:1.8">${p.axisValue}`;
          h += `<table style="margin-top:2px;border-collapse:collapse">`;
          for (const [k, v] of [[tr('open'), fmt(d[0])], [tr('close'), `<span style="color:${col}">${fmt(d[1])} ${dir}</span>`], [tr('low'), fmt(d[2])], [tr('high'), fmt(d[3])]])
            h += `<tr><td style="color:${THEMES[currentTheme].text2};padding-right:8px">${k}</td><td style="font-weight:600">${v}</td></tr>`;
          h += `</table></div>`;
          return h;
        } },
      series: [{ type: 'candlestick', data: [], itemStyle: { color: '#10b981', color0: '#ef4444', borderColor: '#10b981', borderColor0: '#ef4444' } }]
    });
    posCharts[p.symbol] = inst;
    loadPosChart(p.symbol);
  }
}

// ===== AI Analysis =====
let aiTimer = null;
let aiLastSymbol = '';

async function loadAIAnalysis() {
  const symbol = document.getElementById('symbol-select').value || currentSymbol;
  const panel = document.getElementById('ai-panel');
  if (!symbol) {
    panel.innerHTML = `<div class="empty-state">${tr('aiWhitelistRequired')}</div>`;
    document.getElementById('advice-bar').innerHTML =
      `<span class="advice-loading">${tr('aiNoSymbols')}</span>`;
    return;
  }
  try {
    const res = await fetch(`/api/analysis/${symbol}`);
    const d = await res.json();
    renderAIAnalysis(d, symbol);
    renderAdviceBar(d, symbol);
    aiLastSymbol = symbol;
  } catch(e) {
    panel.innerHTML = `<div class="empty-state">${tr('aiLoadFailed')}</div>`;
  }
  // 每30秒自动刷新(无论tab是否可见，保证建议条常驻更新)
  if (!aiTimer) aiTimer = setInterval(loadAIAnalysis, 30000);
}

function renderAIAnalysis(d, symbol) {
  lastAiPayload = d; lastAiSymbol = symbol;
  const panel = document.getElementById('ai-panel');
  const actionCls = d.action === '偏多' ? 'long' : d.action === '偏空' ? 'short' : 'neutral';
  const actionLabel = displayAction(d.action);

  let entryPlanCard = '';
  const entryPlan = d.entry_plan || {};
  if (!d.position && entryPlan.side) {
    const fp = v => v != null && Number.isFinite(Number(v)) ? parseFloat(Number(v).toPrecision(8)) : '--';
    const status = entryPlan.status || 'WAIT';
    const statusLabel = status === 'READY'
      ? txt('可执行计划', 'Actionable plan')
      : status === 'WAIT_CONFIRMATION'
        ? txt('等待高周期确认', 'Waiting for HTF confirmation')
        : txt('等待回踩入场', 'Waiting for pullback');
    entryPlanCard = `
      <div class="entry-plan-card">
        <div class="entry-plan-head">
          <span class="entry-plan-title">${tr('aiEntry')} · ${entryPlan.side}</span>
          <span class="entry-plan-status ${status === 'READY' ? 'ready' : ''}">${statusLabel}</span>
        </div>
        <div class="entry-plan-grid">
          <div class="entry-plan-item"><span>${tr('entryZone')}</span><b class="entry">${fp(entryPlan.entry_low)} - ${fp(entryPlan.entry_high)}</b></div>
          <div class="entry-plan-item"><span>${tr('suggestedEntry')}</span><b class="entry">${fp(entryPlan.entry_price)}</b></div>
          <div class="entry-plan-item"><span>${tr('aiStop')}</span><b class="stop">${fp(entryPlan.stop_loss)}</b></div>
          <div class="entry-plan-item"><span>${tr('aiTp1')}</span><b class="tp">${fp(entryPlan.tp1)}</b></div>
          <div class="entry-plan-item"><span>${tr('aiTp2')}</span><b class="tp">${fp(entryPlan.tp2)}</b></div>
          <div class="entry-plan-item"><span>${tr('riskReward')}</span><b>1 : ${fp(entryPlan.rr)}</b></div>
        </div>
      </div>`;
  }

  // 持仓专属卡片(仅当该币有持仓时)
  let posCard = '';
  if (d.position) {
    const p = d.position, pa = d.position_advice || {};
    const sideCls = p.side === 'LONG' ? 'long' : 'short';
    const sideLabel = displaySide(p.side, true);
    const vCls = pa.cls === 'good' ? 'good' : pa.cls === 'danger' ? 'danger' : 'neutral';
    const pnl = p.unrealized_pnl || 0;
    const pnlCls = pnl >= 0 ? 'pos' : 'neg';
    const pnlPct = pa.pnl_pct !== undefined ? pa.pnl_pct : 0;
    const roi = pa.roi_pct !== undefined ? pa.roi_pct : 0;
    const liq = pa.liq || p.liquidation_price || 0;
    const fp = v => v ? parseFloat(Number(v).toPrecision(6)) : '--';
    posCard = `
      <div class="pos-ai-card">
        <div class="pos-ai-head">
          <span class="pos-ai-sym">${symbol}</span>
          <span class="pos-ai-side ${sideCls}">${sideLabel} ${p.leverage}x</span>
          <span class="pos-ai-verdict ${vCls}">${pa.verdict || '--'}</span>
        </div>
        <div class="pos-ai-grid">
          <div class="pos-ai-item"><span class="k">${tr('entryPrice')}</span><span class="v">${fp(p.entry_price)}</span></div>
          <div class="pos-ai-item"><span class="k">${tr('quantity')}</span><span class="v">${p.qty}</span></div>
          <div class="pos-ai-item"><span class="k">${tr('markPrice')}</span><span class="v">${fp(p.mark_price)}</span></div>
          <div class="pos-ai-item"><span class="k">${txt('强平价', 'Liquidation')}</span><span class="v">${fp(liq)}</span></div>
          <div class="pos-ai-item"><span class="k">${tr('pnl')}</span><span class="v ${pnlCls}">${pnl>=0?'+':''}${fmt(pnl,3)} U (${pnlPct>=0?'+':''}${pnlPct}%)</span></div>
          <div class="pos-ai-item"><span class="k">${txt('保证金收益', 'Margin ROI')}</span><span class="v ${pnlCls}">${roi>=0?'+':''}${roi}%</span></div>
        </div>
        ${(pa.scaled_tp && pa.scaled_tp.length) ? `<div class="stp-wrap"><div class="stp-title">${txt('止盈阶梯', 'Take-profit ladder')}</div>${pa.scaled_tp.map(t => `<div class="stp-row"><span class="stp-label">${t.label}</span><span class="stp-price">${t.price ? fp(t.price) : '--'}</span><span class="stp-pct">${t.pct != null ? t.pct + '%' : '--'}</span></div>`).join('')}</div>` : ''}
        ${pa.text ? `<div class="pos-ai-advice">${localizeRuntimeText(pa.text)}</div>` : ''}
      </div>`;
  }

  let html = entryPlanCard + posCard + `
    <div class="ai-summary">
      <div class="label">AI ${txt('实时分析', 'Live Analysis')} · ${symbol}</div>
      <div class="text">${localizeRuntimeText(d.summary || '--')}</div>
      <div class="ai-action-row">
        <span class="ai-action ${actionCls}">${actionLabel}</span>
        <span class="ai-conf">${tr('confidence')} ${d.confidence || 0}%</span>
        <div class="ai-conf-bar"><div class="ai-conf-fill" style="width:${d.confidence || 0}%"></div></div>
      </div>
      <div class="ai-bull-bear">
        <span class="bull">${txt('看多信号', 'Bullish signals')} ${d.bull_points || 0}</span>
        <span class="bear">${txt('看空信号', 'Bearish signals')} ${d.bear_points || 0}</span>
      </div>
    </div>`;

  for (const sec of (d.sections || [])) {
    html += `<div class="ai-section"><div class="title">${localizeRuntimeText(sec.title)}</div><div class="text">${localizeRuntimeText(sec.text)}</div></div>`;
  }

  if ((d.supports && d.supports.length) || (d.resistances && d.resistances.length)) {
    let lvl = `<div class="ai-section"><div class="title">${txt('关键价位速查', 'Key levels')}</div><div class="text">`;
    if (d.resistances && d.resistances.length) lvl += `${tr('resistance')}: ${d.resistances.map(r=>`<span style="color:var(--red)">${r}</span>`).join(' / ')}<br>`;
    if (d.supports && d.supports.length) lvl += `${tr('support')}: ${d.supports.map(s=>`<span style="color:var(--green)">${s}</span>`).join(' ')}`;
    lvl += '</div></div>';
    html += lvl;
  }

  html += `<div class="ai-refresh">${txt('更新于', 'Updated')} ${new Date().toLocaleTimeString(currentLanguage,{hour12:false})} · ${txt('30秒自动刷新', 'Auto-refreshes every 30s')}</div>`;
   panel.innerHTML = html;
   if (chart && currentSymbol === symbol) renderChart();
}

function renderAdviceBar(d, symbol) {
  const bar = document.getElementById('advice-bar');
  const cls = d.action === '偏多' ? 'long' : d.action === '偏空' ? 'short' : 'neutral';
  const label = displayAction(d.action);

  // 从sections中提取操作建议
  let advice = '';
  for (const sec of (d.sections || [])) {
     if (sec.title === '操作建议') { advice = localizeRuntimeText(sec.text); break; }
  }

  let levels = '';
  if ((d.supports && d.supports.length) || (d.resistances && d.resistances.length)) {
    if (d.resistances && d.resistances.length) levels += `${tr('resistance')} <span class="res">${d.resistances[0]}</span>`;
    if (d.supports && d.supports.length) levels += `${levels ? ' · ' : ''}${tr('support')} <span class="sup">${d.supports[0]}</span>`;
  }

  bar.innerHTML = `
    <span class="advice-dir ${cls}">${label}</span>
    <span class="advice-conf">${tr('confidence')} ${d.confidence || 0}%<span class="advice-conf-bar"><span class="advice-conf-fill" style="width:${d.confidence || 0}%"></span></span></span>
     <span class="advice-summary">${localizeRuntimeText(d.summary || '--')}</span>
    ${levels ? `<span class="advice-levels">${levels}</span>` : ''}
    ${advice ? `<span class="advice-action">${advice}</span>` : ''}
  `;
}

// ===== News =====
let newsTimer = null;

async function loadNews() {
  const el = document.getElementById('bottom-news');
  try {
    const res = await fetch('/api/news');
    const d = await res.json();
    renderNews(d);
  } catch(e) {
    el.innerHTML = `<div class="empty-state">${tr('newsLoadFailed')}</div>`;
  }
  if (!newsTimer) newsTimer = setInterval(() => {
    if (document.getElementById('bottom-news').style.display !== 'none') loadNews();
  }, 300000); // 5分钟刷新
}

function renderNews(d) {
  lastNewsPayload = d || {};
  const el = document.getElementById('bottom-news');
  const s = d.summary || {};
  const biasCls = s.bias === '偏多' ? 'bull' : s.bias === '偏空' ? 'bear' : 'neutral';
  const biasLabel = s.bias === '偏多' ? tr('bullishCount') : s.bias === '偏空' ? tr('bearishCount') : tr('neutralCount');

  // 持仓情绪卡片(结合用户持仓判定利多/利空)全新视觉化重构
  let psHtml = '';
  const ps = d.positions_sentiment || [];
  if (ps.length) {
    let goodCount = 0;
    let dangerCount = 0;
    let neutralCount = 0;

    ps.forEach(p => {
      const v = p.verdict || {};
      if (v.cls === 'good') goodCount++;
      else if (v.cls === 'danger') dangerCount++;
      else neutralCount++;
    });

    psHtml = `<div class="ps-wrap">
      <div class="ps-summary-hud">
        <div class="ps-summary-title">
          <span>🧭 我的持仓多空博弈与聪明钱监控</span>
          <span style="font-size:10px;font-weight:normal;color:var(--text-2)">(实时监测大户背离与全网散户拥挤踩踏风险)</span>
        </div>
        <div class="ps-summary-pills">
          <span class="ps-summary-pill">持仓总计: ${ps.length} 标的</span>
          <span class="ps-summary-pill good">🛡️ 顺风安全: ${goodCount}</span>
          <span class="ps-summary-pill danger">⚠️ 逆风/拥挤风险: ${dangerCount}</span>
          ${neutralCount ? `<span class="ps-summary-pill">⚖️ 情绪中性: ${neutralCount}</span>` : ''}
        </div>
      </div>
    `;

    for (const p of ps) {
      const v = p.verdict || {};
      const vCls = v.cls === 'good' ? 'good' : v.cls === 'danger' ? 'danger' : 'neutral';
      const sideCls = p.side === 'LONG' ? 'long' : 'short';
      const sideLabel = p.side === 'LONG' ? '做多 LONG' : '做空 SHORT';
      const ls = p.long_short || {};
      const ta = p.top_trader_account || {};
      const tt = p.top_trader || {};
      const oi = p.open_interest || {};
      const sm = p.smart_money || {};
      const fr = p.funding_rate;
      const oiChg = oi.change_24h_pct !== undefined && oi.change_24h_pct !== null ? Number(oi.change_24h_pct) : 0;
      const smScore = sm.score !== undefined && sm.score !== null ? Number(sm.score) : 0;

      // Calculate Long/Short percentages
      let longPct = Number(ls.long_pct !== undefined && ls.long_pct !== null ? ls.long_pct : 50);
      let shortPct = Number(ls.short_pct !== undefined && ls.short_pct !== null ? ls.short_pct : (100 - longPct));
      if (longPct + shortPct === 0) { longPct = 50; shortPct = 50; }
      const lsRatio = ls.ratio !== undefined && ls.ratio !== null ? Number(ls.ratio).toFixed(3) : '--';
      const ttRatio = tt.ratio !== undefined && tt.ratio !== null ? Number(tt.ratio).toFixed(3) : '--';
      const taRatio = ta.ratio !== undefined && ta.ratio !== null ? Number(ta.ratio).toFixed(3) : '--';

      // Crowd Warning Alert
      let crowdAlertHtml = '';
      if (shortPct >= 65) {
        crowdAlertHtml = `<div class="ps-crowd-alert short">🔥 全网空头严重拥挤 (${shortPct.toFixed(1)}%) · 警惕主力诱空扫损与反抽轧空</div>`;
      } else if (longPct >= 65) {
        crowdAlertHtml = `<div class="ps-crowd-alert long">🔥 全网多头严重拥挤 (${longPct.toFixed(1)}%) · 警惕多杀多集中踩踏砸盘</div>`;
      }

      // Funding rate description
      let frStr = '--';
      let frSub = '费率平稳';
      let frCls = '';
      if (fr !== null && fr !== undefined) {
        const frPct = fr * 100;
        frStr = `${frPct >= 0 ? '+' : ''}${frPct.toFixed(3)}%`;
        if (p.side === 'SHORT') {
          if (fr > 0.005) { frSub = '🟢 空单坐收资金费'; frCls = 'pos'; }
          else if (fr < -0.005) { frSub = '🔴 空头拥挤/需付资金费'; frCls = 'neg'; }
        } else {
          if (fr < -0.005) { frSub = '🟢 多单坐收资金费'; frCls = 'pos'; }
          else if (fr > 0.005) { frSub = '🔴 多头拥挤/需付资金费'; frCls = 'neg'; }
        }
      }

      // PnL Badge
      let pnlBadge = '';
      if (p.unrealized_pnl !== undefined && p.unrealized_pnl !== null) {
        const pnl = Number(p.unrealized_pnl);
        pnlBadge = `<span class="ps-pnl-pill ${pnl >= 0 ? 'pos' : 'neg'}">未实现: ${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)} U</span>`;
      }

      // Verdict label with icon
      let verdictLabel = localizeRuntimeText(v.label || tr('noOpinion'));
      let verdictIcon = v.cls === 'good' ? '🛡️' : v.cls === 'danger' ? '⚠️' : '⚖️';

      // Transform reason strings into beautiful chips
      const reasonsList = v.reasons || [];
      const reasonChips = reasonsList.map(r => {
        const text = localizeRuntimeText(r);
        let chipCls = 'info';
        let chipIcon = 'ℹ️';

        if (text.includes('不利') || text.includes('易反弹') || text.includes('易回调') || text.includes('逆向') || text.includes('需付') || text.includes('拥挤')) {
          chipCls = 'danger';
          chipIcon = '⚠️';
        } else if (text.includes('利') || text.includes('一致') || text.includes('共振') || text.includes('收资金费') || text.includes('偏多') || text.includes('偏空')) {
          chipCls = 'good';
          chipIcon = '✅';
        } else if (text.includes('注意') || text.includes('异动') || text.includes('加剧') || text.includes('恐慌') || text.includes('过热')) {
          chipCls = 'warning';
          chipIcon = '⚡';
        }
        return `<span class="ps-reason-tag ${chipCls}"><span class="chip-icon">${chipIcon}</span>${escapeHtml(text)}</span>`;
      }).join('');

      psHtml += `
        <div class="ps-card ${vCls}">
          <!-- 头部信息 -->
          <div class="ps-head">
            <div class="ps-head-left">
              <span class="ps-sym" onclick="selectSymbolAndShow('${escapeJsStr(p.symbol)}')">${escapeHtml(p.symbol)} ↗</span>
              <span class="ps-side ${sideCls}">${sideLabel}</span>
              ${pnlBadge}
            </div>
            <div class="ps-head-right">
              <span class="ps-verdict ${vCls}">${verdictIcon} ${verdictLabel}</span>
              <button type="button" class="ps-btn-chart" onclick="selectSymbolAndShow('${escapeJsStr(p.symbol)}')">📊 看行情</button>
            </div>
          </div>

          <!-- 散户多空力量对比能量槽 -->
          <div class="ps-duel-wrap">
            <div class="ps-duel-labels">
              <span class="long-label">多头 <strong>${longPct.toFixed(1)}%</strong></span>
              <span class="ratio-label">全网散户多空比: <strong>${lsRatio}</strong></span>
              <span class="short-label">空头 <strong>${shortPct.toFixed(1)}%</strong></span>
            </div>
            <div class="ps-duel-track" title="绿色为多头占比，红色为空头占比">
              <div class="ps-duel-bar-long" style="width: ${longPct}%;"></div>
              <div class="ps-duel-bar-short" style="width: ${shortPct}%;"></div>
            </div>
            ${crowdAlertHtml}
          </div>

          <!-- 4 宫格核心指标卡片 -->
          <div class="ps-stats-grid">
            <div class="ps-stat-card">
              <div class="ps-stat-title">🤖 聪明钱量化评分</div>
              <div class="ps-stat-val ${smScore >= 15 ? 'pos' : smScore <= -15 ? 'neg' : ''}">
                ${smScore >= 0 ? '+' : ''}${smScore.toFixed(1)}
              </div>
              <div class="ps-stat-desc">${smScore >= 15 ? '🟢 机构共振做多' : smScore <= -15 ? '🔴 机构主力做空' : '⚪ 中立均衡'}</div>
            </div>

            <div class="ps-stat-card">
              <div class="ps-stat-title">🏛️ 大户持仓 / 账户比</div>
              <div class="ps-stat-val">${ttRatio} / ${taRatio}</div>
              <div class="ps-stat-desc">${Number(tt.ratio || 1) > 1.2 ? '🟢 大户大幅做多' : Number(tt.ratio || 1) < 0.83 ? '🔴 大户大幅做空' : '⚖️ 大户仓位均衡'}</div>
            </div>

            <div class="ps-stat-card">
              <div class="ps-stat-title">⚡ 资金费率 (8h)</div>
              <div class="ps-stat-val ${frCls}">${frStr}</div>
              <div class="ps-stat-desc">${frSub}</div>
            </div>

            <div class="ps-stat-card">
              <div class="ps-stat-title">📊 24h 持仓量 (OI)</div>
              <div class="ps-stat-val ${oiChg >= 0 ? 'pos' : 'neg'}">${oiChg >= 0 ? '+' : ''}${oiChg.toFixed(2)}%</div>
              <div class="ps-stat-desc">${Math.abs(oiChg) >= 8 ? '🔥 资金大幅异动' : '持仓平稳'}</div>
            </div>
          </div>

          <!-- 研判与避坑提示标签墙 -->
          ${reasonChips ? `<div class="ps-reasons-wall">${reasonChips}</div>` : ''}
        </div>
      `;
    }
    psHtml += '</div>';
  }

  let html = psHtml + `<div class="news-summary">
    <span style="font-size:10px;color:var(--text-2)">${tr('newsSentimentLabel')}: </span>
    <span class="news-badge ${biasCls}">${biasLabel}</span>
    <span class="news-badge bull">${tr('bullishCount')} ${s.bullish || 0}</span>
    <span class="news-badge bear">${tr('bearishCount')} ${s.bearish || 0}</span>
    <span class="news-badge neutral">${tr('neutralCount')} ${s.neutral || 0}</span>
    <span style="font-size:9px;color:var(--text-2)">${tr('totalItems')}${s.total || 0}${tr('items')} · ${tr('refreshEveryFiveMinutes')}</span>
  </div>`;

  const news = d.news || [];
  if (!news.length) {
    html += `<div class="empty-state">${tr('noNews')}</div>`;
  } else {
    for (const n of news) {
      const sentCls = n.sentiment > 0 ? 'bull' : n.sentiment < 0 ? 'bear' : 'neutral';
      const sentLabel = n.sentiment > 0 ? tr('bullishCount') : n.sentiment < 0 ? tr('bearishCount') : tr('neutralCount');
      const title = n.url ? `<a href="${n.url}" target="_blank">${escapeHtml(n.title)}</a>` : escapeHtml(n.title);
      html += `<div class="news-item">
        <span class="news-src">${n.source || ''}</span>
        <span class="news-title">${title}</span>
        <span class="news-sent ${sentCls}">${sentLabel}</span>
      </div>`;
    }
  }
  el.innerHTML = html;
}

function escapeHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function escapeJsStr(s) {
  return String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'")
    .replace(/"/g, '\\"').replace(/\n/g, '\\n').replace(/\r/g, '\\r');
}

// ===== 实时推荐 =====
let recLoading = false;
async function loadRecommend(force) {
  if (recLoading) return;
  const el = document.getElementById('rec-list');
  recLoading = true;
  el.innerHTML = `<div class="empty-state">${tr('recommendationLoading')}</div>`;
  try {
    const res = await fetch('/api/recommend');
    const d = await res.json();
    renderRecommend(d);
  } catch(e) {
    el.innerHTML = `<div class="empty-state">${tr('recommendationLoadFailed')}${escapeHtml(e.message)}</div>`;
  }
  recLoading = false;
}

function renderRecommend(d) {
  lastRecommendPayload = d;
  const el = document.getElementById('rec-list');
  const meta = document.getElementById('rec-meta');
  if (d.error) {
    el.innerHTML = `<div class="rec-alert-banner">
      <div class="rec-alert-title">⚠️ ${txt('行情分析提示', 'Market Notice')}</div>
      <div class="rec-alert-desc">${escapeHtml(d.error)}</div>
    </div>`;
    return;
  }
  const items = d.items || [];
  const executionRejections = d.execution_rejections || [];
  meta.textContent = `${txt('余额', 'Balance')} ${d.balance}U | ${d.ts} | ${txt('扫描', 'Scanned')} ${d.scanned_candidate_count ?? '--'} | ${items.length} ${txt('个推荐', 'recommendations')}${executionRejections.length ? ` | ${executionRejections.length} ${txt('个执行拦截', 'execution blocks')}` : ''}`;

  const warnBanner = d.account_warning ? `<div class="rec-alert-sub">⚠️ ${escapeHtml(d.account_warning)} (${txt('已使用 1000U 基准资金扫描', 'Using 1000U baseline')})</div>` : '';

  if (!items.length) {
    const blocked = executionRejections.length
      ? `<div style="margin-top:9px;text-align:left;font-size:12px;line-height:1.6">${executionRejections.map(item =>
          `<div><b>${escapeHtml(item.symbol || '--')}</b>: ${escapeHtml(item.reason || txt('执行约束', 'Execution constraint'))}</div>`
        ).join('')}</div>`
      : '';
    el.innerHTML = `${warnBanner}<div class="empty-state">${txt('暂无可执行的高分信号', 'No executable high-score signals')}${blocked}</div>`;
    return;
  }
  const fp = v => v ? parseFloat(Number(v).toPrecision(6)) : '--';
  window.recItemsData = items;
  el.innerHTML = warnBanner + items.map((it, idx) => {
    const cls = it.side_en === 'LONG' ? 'long' : 'short';
    const factors = (it.factors || []).slice(-6).map(f => `<span class="rec-factor">${escapeHtml(localizeRuntimeText(f))}</span>`).join('');
    const surgeCls = it.vol_surge >= 2 ? 'lev' : '';
    const sm = it.smart_money || {}, tt = sm.top_trader || {}, ta = sm.top_trader_account || {}, oi = sm.open_interest || {};
    const smScore = Number(sm.score || 0);
    const smColor = smScore >= 15 ? 'var(--green)' : smScore <= -15 ? 'var(--red)' : 'var(--text-0)';
    return `<div class="rec-card ${cls}">
      <div class="rec-head">
        <span class="rec-sym">${it.symbol}</span>
        <span class="rec-side ${cls}">${displaySide(it.side_en || it.side)}</span>
        <span class="rec-score ${cls}">${txt('热度', 'Heat')} ${it.hot_score}</span>
        <button class="rec-order-pill ${cls}" onclick="openQuickOrderModal('${it.symbol}', '${it.side_en || it.side}', ${it.leverage || 5}, ${it.margin || 20}, ${it.sl || null}, ${it.tp1 || null})">⚡ ${txt('开仓', 'Order')}</button>
      </div>
      <div class="rec-grid">
        <div class="rec-item">${txt('放量倍数', 'Volume surge')} <b class="${surgeCls}">${it.vol_surge}x</b></div>
        <div class="rec-item">${txt('综合评分', 'Overall score')} <b>${it.score}</b> <span style="color:var(--text-2)">(${txt('技术', 'Technical')} ${it.base_score ?? it.score})</span></div>
        <div class="rec-item">${tr('smartMoney')} <b style="color:${smColor}">${smScore>=0?'+':''}${smScore}</b></div>
        <div class="rec-item">${txt('大户持仓/账户', 'Top trader OI/Accounts')} <b>${tt.ratio ?? '--'} / ${ta.ratio ?? '--'}</b></div>
        <div class="rec-item">OI 1h <b>${Number(oi.change_1h_pct||0)>=0?'+':''}${oi.change_1h_pct ?? '--'}%</b></div>
       <div class="rec-item" title="${escapeHtml(localizeRuntimeText((it.intent_reasons || []).join('；')))}">${tr('mainIntent')} <b style="color:${it.intent === '出货' ? 'var(--red)' : (it.intent === '洗盘' || it.intent === '吸筹') ? 'var(--green)' : it.intent === '拉升' ? '#f0b90b' : 'var(--text-2)'}">${localizeRuntimeText(it.intent || '--')}${it.intent_confidence ? ' ' + it.intent_confidence + '%' : ''}</b></div>
        <div class="rec-item">${tr('indicatorPrice')} <b>${fp(it.price)}</b></div>
        <div class="rec-item">24h <b>${it.change_24h}%</b></div>
        <div class="rec-item">RSI <b>${it.rsi ?? '--'}</b></div>
        <div class="rec-item">${txt('ATR波动', 'ATR volatility')} <b>${it.atr_pct}%</b></div>
        <div class="rec-item">${txt('推荐杠杆', 'Suggested leverage')} <b class="lev">${it.leverage}x</b></div>
        <div class="rec-item">${txt('建议投入', 'Suggested margin')} <b>${it.margin}U</b></div>
        <div class="rec-item">${txt('建议仓位', 'Suggested qty')} <b>${fp(it.qty)}</b></div>
        <div class="rec-item">${tr('support')} <b style="color:var(--green)">${fp(it.support) || '--'}${it.support_touches ? ' ×' + it.support_touches : ''}</b></div>
        <div class="rec-item">${tr('resistance')} <b style="color:var(--red)">${fp(it.resistance) || '--'}${it.resistance_touches ? ' ×' + it.resistance_touches : ''}</b></div>
        <div class="rec-item">${txt('止损风险', 'Stop risk')} <b>-${it.risk_u}U (${it.risk_pct}%)</b></div>
        <div class="rec-item">${txt('止损价', 'Stop')} <b style="color:var(--red)">${fp(it.sl)}</b></div>
        <div class="rec-item">${txt('止盈1(减30%)', 'TP1 (30%)')} <b style="color:var(--green)">${fp(it.tp1)}</b></div>
        <div class="rec-item">${txt('止盈2(减30%)', 'TP2 (30%)')} <b style="color:var(--green)">${fp(it.tp2)}</b></div>
        <div class="rec-item">${txt('止盈3(全平)', 'TP3 (100%)')} <b style="color:var(--green)">${fp(it.tp3)}</b></div>
      </div>
      ${factors ? `<div class="rec-factors">${factors}</div>` : ''}
    </div>`;
  }).join('');
}

