// ===== K线标注线 =====
const chartLineSettings = {
  entry: true,
  stop: true,
  takeProfit: true,
  levels: true,
  ema: true,
  boll: false,
  tradeMarkers: true,
  vwap: false,
  denseZones: true,
  swingPoints: true
};
const CHART_LINE_COLORS = {
  entry: '#38bdf8',
  stop: '#ef4444',
  takeProfit: '#22c55e',
  support: '#60a5fa',
  resistance: '#f59e0b',
  ema: '#a78bfa',
  ema9: '#38bdf8',
  ema21: '#f59e0b',
  ema55: '#c084fc',
  boll: 'rgba(56, 189, 248, 0.4)',
  vwap: '#f472b6',
  denseZone: '#f59e0b',
  swingHigh: '#ef4444',
  swingLow: '#22c55e'
};
function initChartLineSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem('quant_chart_lines') || '{}');
    Object.keys(chartLineSettings).forEach(key => {
      if (typeof saved[key] === 'boolean') chartLineSettings[key] = saved[key];
    });
  } catch (e) {}
  document.querySelectorAll('[data-chart-line]').forEach(input => {
    input.checked = chartLineSettings[input.dataset.chartLine] !== false;
  });
}

function selectChartTab(tab) {
  if (!tab) return;
  const mode = tab.dataset.chartTab || 'chart';
  document.querySelectorAll('[data-chart-tab]').forEach(el => el.classList.toggle('active', el === tab));
  document.querySelectorAll('[data-chart-panel]').forEach(panel => {
    const active = panel.dataset.chartPanel === mode;
    panel.hidden = !active;
    if (active) panel.style.display = '';
  });
  if (mode === 'info') renderChartInfoPanel();
  if (mode === 'data') renderChartDataPanel();
  if (mode === 'chart' && chart) setTimeout(() => chart.resize(), 0);
}
function chartPanelValue(value, digits=8) { return formatChartValue(value, digits); }
function renderChartInfoPanel() {
  const panel = document.getElementById('chart-info-panel');
  if (!panel) return;
  const latest = kSeries.length ? kSeries[kSeries.length - 1] : null;
  const previous = kSeries.length > 1 ? kSeries[kSeries.length - 2] : null;
  if (!latest) { panel.innerHTML = `<div class="chart-empty">${tr('chartNoData')}</div>`; return; }
  const close = Number(latest[1]);
  const prevClose = Number(previous?.[1]);
  const change = Number.isFinite(prevClose) && prevClose ? (close - prevClose) / prevClose * 100 : null;
  const ind = lastIndicators || {};
  const ai = lastAiSymbol === currentSymbol ? lastAiPayload : null;
  const bias = ind.htf_trend > 0 ? tr('long') : ind.htf_trend < 0 ? tr('short') : tr('neutral');
  const plan = ai?.entry_plan || {};
  const planText = plan.entry_price ? `${tr('suggestedEntry')}: ${chartPanelValue(plan.entry_price)} ? ${tr('aiStop')}: ${chartPanelValue(plan.stop_loss)} ? ${tr('aiTp1')}: ${chartPanelValue(plan.tp1)}` : tr('chartNoData');
  panel.innerHTML = `<div class="chart-info-head"><div><div class="chart-info-title">${tr('chartInfoTitle')} ? ${currentSymbol || '--'}</div><div class="chart-info-subtitle">${tr(`timeframe${document.getElementById('interval-select')?.value || '5m'}`)}</div></div><div class="chart-info-subtitle">${tr('candleCount')}: ${kSeries.length}</div></div><div class="chart-info-grid"><div class="chart-info-card"><div class="k">${tr('open')}</div><div class="v">${chartPanelValue(latest[0])}</div></div><div class="chart-info-card"><div class="k">${tr('high')}</div><div class="v">${chartPanelValue(latest[3])}</div></div><div class="chart-info-card"><div class="k">${tr('low')}</div><div class="v">${chartPanelValue(latest[2])}</div></div><div class="chart-info-card"><div class="k">${tr('close')}</div><div class="v ${change >= 0 ? 'up' : 'down'}">${chartPanelValue(latest[1])}</div></div><div class="chart-info-card"><div class="k">${tr('volume')}</div><div class="v">${chartPanelValue(Math.abs(kVols[kVols.length - 1]), 2)}</div></div><div class="chart-info-card"><div class="k">${tr('trendBias')}</div><div class="v">${bias}</div></div><div class="chart-info-card"><div class="k">RSI</div><div class="v">${chartPanelValue(ind.rsi, 2)}</div></div><div class="chart-info-card"><div class="k">${tr('signalScore')}</div><div class="v">${chartPanelValue(ind.score, 2)}</div></div></div><div class="chart-info-note">${planText}</div>`;
}
function renderChartDataPanel() {
  const panel = document.getElementById('chart-data-panel');
  if (!panel) return;
  if (!kSeries.length) { panel.innerHTML = `<div class="chart-empty">${tr('chartNoData')}</div>`; return; }
  const rows = kSeries.slice(-60).map((row, offset) => {
    const index = kSeries.length - Math.min(60, kSeries.length) + offset;
    const open = Number(row[0]), close = Number(row[1]), change = open ? (close - open) / open * 100 : 0;
    const volume = Math.abs(Number(kVols[index] || 0));
    return `<tr><td>${kTimes[index] || '--'}</td><td>${chartPanelValue(open)}</td><td>${chartPanelValue(Number(row[3]))}</td><td>${chartPanelValue(Number(row[2]))}</td><td class="${change >= 0 ? 'up' : 'down'}">${chartPanelValue(close)}</td><td class="${change >= 0 ? 'up' : 'down'}">${change >= 0 ? '+' : ''}${chartPanelValue(change, 2)}%</td><td>${chartPanelValue(volume, 2)}</td></tr>`;
  }).join('');
  panel.innerHTML = `<div class="chart-data-toolbar"><strong>${tr('chartDataTitle')}</strong><span>${tr('chartDataHint')} ? ${tr('candleCount')}: ${kSeries.length}</span></div><table class="chart-data-table"><thead><tr><th>${tr('time')}</th><th>${tr('open')}</th><th>${tr('high')}</th><th>${tr('low')}</th><th>${tr('close')}</th><th>${tr('change')}</th><th>${tr('volume')}</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function syncChartTimeframeButtons() {
  const interval = document.getElementById('interval-select')?.value || '5m';
  document.querySelectorAll('[data-chart-interval]').forEach(button => {
    button.classList.toggle('active', button.dataset.chartInterval === interval);
  });
  const label = document.getElementById('chart-interval-name');
  if (label) label.textContent = tr(`timeframe${interval}`, interval);
}

function selectChartInterval(interval) {
  const select = document.getElementById('interval-select');
  if (!select || ![...select.options].some(option => option.value === interval)) return;
  select.value = interval;
  syncChartTimeframeButtons();
  loadKlines();
}

function formatChartValue(value, digits=8) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString(currentLanguage, {maximumFractionDigits: digits}) : '--';
}

function updateChartHeader(source=null) {
  const rows = Array.isArray(source) ? source : null;
  const latest = rows?.length ? rows[rows.length - 1] : (kSeries.length ? kSeries[kSeries.length - 1] : null);
  const previous = rows?.length > 1 ? rows[rows.length - 2] : (kSeries.length > 1 ? kSeries[kSeries.length - 2] : null);
  const read = (row, key, index) => Array.isArray(row) ? row[index] : row?.[key];
  const open = read(latest, 'open', 0);
  const close = read(latest, 'close', 1);
  const low = read(latest, 'low', 2);
  const high = read(latest, 'high', 3);
  const prevClose = read(previous, 'close', 1);
  const change = Number.isFinite(Number(close)) && Number.isFinite(Number(prevClose)) && Number(prevClose) !== 0
    ? (Number(close) - Number(prevClose)) / Number(prevClose) * 100 : null;
  const symbol = document.getElementById('chart-symbol-name');
  const ohlc = document.getElementById('chart-ohlc');
  const changeEl = document.getElementById('chart-change');
  const volume = document.getElementById('chart-volume-value');
  const date = document.getElementById('chart-date-status');
  if (symbol) symbol.textContent = currentSymbol || kSymbol || '--';
  if (ohlc) ohlc.innerHTML = `${tr('open')}=${formatChartValue(open)} ${tr('high')}=${formatChartValue(high)} ${tr('low')}=${formatChartValue(low)} ${tr('close')}=${formatChartValue(close)} <span id="chart-change" class="${Number(change) >= 0 ? 'up' : 'down'}">${change === null ? '--' : `${change >= 0 ? '+' : ''}${formatChartValue(change, 2)}%`}</span>`;
  if (volume) volume.textContent = formatChartValue(Math.abs(kVols[kVols.length - 1]));
  if (date) date.textContent = new Date().toLocaleDateString(currentLanguage, {month:'short', day:'numeric'});
  syncChartTimeframeButtons();
}
function setChartLineVisibility(key, visible) {
  if (!(key in chartLineSettings)) return;
  chartLineSettings[key] = Boolean(visible);
  try { localStorage.setItem('quant_chart_lines', JSON.stringify(chartLineSettings)); } catch (e) {}
  renderChart();
}
function lineNumber(value) {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? parseFloat(n.toPrecision(8)) : null;
}
function chartDenseVolumeAreas() {
  if (!chartLineSettings.denseZones || kSeries.length < 20 || kTimes.length < 2) return [];
  const rows = kSeries.map((row, index) => ({ row, volume: Math.abs(Number(kVols[index] || 0)) }))
    .filter(item => Array.isArray(item.row) && item.volume > 0);
  if (!rows.length) return [];
  const minPrice = Math.min(...rows.map(item => Number(item.row[2])));
  const maxPrice = Math.max(...rows.map(item => Number(item.row[3])));
  const span = maxPrice - minPrice;
  if (!(span > 0)) return [];
  const binCount = Math.min(32, Math.max(16, Math.round(Math.sqrt(rows.length) * 2)));
  const step = span / binCount;
  const bins = Array.from({length: binCount}, (_, index) => ({ index, volume: 0 }));
  rows.forEach(({row, volume}) => {
    const typical = (Number(row[0]) + Number(row[1]) + Number(row[2]) + Number(row[3])) / 4;
    const index = Math.max(0, Math.min(binCount - 1, Math.floor((typical - minPrice) / step)));
    bins[index].volume += volume;
  });
  const average = bins.reduce((sum, bin) => sum + bin.volume, 0) / binCount;
  const selected = [];
  bins.slice().sort((a, b) => b.volume - a.volume).forEach(bin => {
    if (bin.volume < average * 1.25 || selected.some(item => Math.abs(item.index - bin.index) < 2) || selected.length >= 3) return;
    selected.push(bin);
  });
  return selected.map(bin => {
    const low = minPrice + Math.max(0, bin.index - 0.7) * step;
    const high = minPrice + Math.min(binCount, bin.index + 1.7) * step;
    return {
      name: tr('denseVolumeZones'),
      itemStyle: { color: CHART_LINE_COLORS.denseZone, opacity: 0.11 },
      label: { show: true, position: 'insideLeft', color: CHART_LINE_COLORS.denseZone, fontSize: 10, formatter: tr('denseVolumeZones') },
      data: [[{ xAxis: kTimes[0], yAxis: low }, { xAxis: kTimes[kTimes.length - 1], yAxis: high }]]
    };
  });
}
function chartSwingPoints() {
  const points = [];
  if (chartLineSettings.swingPoints && kSeries.length >= 7 && kTimes.length >= 7) {
    const radius = 2;
    for (let i = radius; i < kSeries.length - radius; i++) {
      const high = Number(kSeries[i][3]);
      const low = Number(kSeries[i][2]);
      const left = kSeries.slice(i - radius, i).map(row => Number(row[3]));
      const right = kSeries.slice(i + 1, i + radius + 1).map(row => Number(row[3]));
      const lowLeft = kSeries.slice(i - radius, i).map(row => Number(row[2]));
      const lowRight = kSeries.slice(i + 1, i + radius + 1).map(row => Number(row[2]));
      if (high >= Math.max(...left, ...right) && high > Math.min(...left, ...right)) {
        points.push({ name: tr('swingHigh'), coord: [kTimes[i], high], value: 'H', symbol: 'circle', symbolSize: 8, itemStyle: { color: CHART_LINE_COLORS.swingHigh }, label: { show: true, position: 'top', color: CHART_LINE_COLORS.swingHigh, fontSize: 10, formatter: 'H' } });
      }
      if (low <= Math.min(...lowLeft, ...lowRight) && low < Math.max(...lowLeft, ...lowRight)) {
        points.push({ name: tr('swingLow'), coord: [kTimes[i], low], value: 'L', symbol: 'circle', symbolSize: 8, itemStyle: { color: CHART_LINE_COLORS.swingLow }, label: { show: true, position: 'bottom', color: CHART_LINE_COLORS.swingLow, fontSize: 10, formatter: 'L' } });
      }
    }
  }
  if (chartLineSettings.tradeMarkers && Array.isArray(lastTradesLog) && kTimes.length > 0) {
    const sym = currentSymbol || kSymbol;
    lastTradesLog.filter(t => t.symbol === sym).forEach(t => {
      const isBuy = String(t.side || '').toUpperCase().includes('LONG') || String(t.side || '').toUpperCase().includes('BUY');
      const timeStr = String(t.time || '');
      let idx = kTimes.findIndex(tm => timeStr && tm.slice(0, 5) === timeStr.slice(0, 5));
      if (idx < 0) idx = kTimes.length - 1;
      const refCandle = kSeries[idx] || [0, 0, 0, 0];
      const pr = Number(t.price || t.entry_price || t.exit_price || refCandle[isBuy ? 2 : 3]);
      points.push({
        name: isBuy ? '买入' : '卖出',
        coord: [kTimes[idx], pr],
        symbol: isBuy ? 'triangle' : 'pin',
        symbolRotate: isBuy ? 0 : 180,
        symbolSize: 13,
        itemStyle: { color: isBuy ? '#10b981' : '#ef4444' },
        label: {
          show: true,
          position: isBuy ? 'bottom' : 'top',
          color: isBuy ? '#10b981' : '#ef4444',
          fontSize: 10,
          formatter: isBuy ? '▲买' : '▼卖'
        }
      });
    });
  }
  return points.slice(-36);
}
function chartAnnotations() {
  return { markArea: { silent: true, z: 0, data: chartDenseVolumeAreas() }, markPoint: { silent: true, data: chartSwingPoints() } };
}
function chartLineExtent() {
  const values = [];
  (kSeries || []).forEach(row => {
    if (Array.isArray(row)) row.slice(0, 4).forEach(value => {
      const number = lineNumber(value);
      if (number !== null) values.push(number);
    });
  });
  chartLineLevels().forEach(line => {
    const number = lineNumber(line.yAxis);
    if (number !== null) values.push(number);
  });
  if (!values.length) return {};
  const min = Math.min(...values), max = Math.max(...values);
  const pad = Math.max((max - min) * 0.08, max * 0.0025);
  return { min: Math.max(0, min - pad), max: max + pad };
}
function chartLineLevels() {
  const lines = [];
  const position = (lastPositions || []).find(p => p.symbol === currentSymbol);
  const ai = lastAiSymbol === currentSymbol ? lastAiPayload : null;
  const advice = ai?.position_advice || {};
  const plan = ai?.entry_plan || {};
  const planSide = plan.side === 'LONG' || plan.side === 'SHORT' ? plan.side : null;
  // position entry/stop/take-profit levels take precedence over a new-entry plan.
  const add = (key, value, name, color, type='solid') => {
    const number = lineNumber(value);
    if (chartLineSettings[key] && number !== null) {
      lines.push({ name, yAxis: number, lineStyle: { color, width: 1.5, type }, label: { color, backgroundColor: 'rgba(10,14,23,.82)' } });
    }
  };
  const validPositionStop = (stop, pos) => {
    const number = lineNumber(stop);
    const entry = lineNumber(pos?.entry_price);
    const live = lineNumber(pos?.mark_price);
    if (number === null || entry === null) return null;
    const side = pos.side === 'LONG' ? 'LONG' : 'SHORT';
    if ((side === 'LONG' && number >= entry) || (side === 'SHORT' && number <= entry)) return null;
    if (live !== null && ((side === 'LONG' && number >= live) || (side === 'SHORT' && number <= live))) return null;
    return number;
  };
  const validPlan = (candidate) => {
    const side = candidate.side === 'LONG' || candidate.side === 'SHORT' ? candidate.side : null;
    const values = ['entry_low', 'entry_price', 'entry_high', 'stop_loss', 'tp1', 'tp2']
      .map(key => lineNumber(candidate[key]));
    if (!side || candidate.status === 'WAIT' || values.some(value => value === null)) return null;
    const [low, entry, high, stop, tp1, tp2] = values;
    const ordered = side === 'LONG'
      ? stop < low && low <= entry && entry <= high && high < tp1 && tp1 < tp2
      : stop > high && high >= entry && entry >= low && low > tp1 && tp1 > tp2;
    return ordered ? candidate : null;
  };
  const activePlan = validPlan(plan);
  if (position) {
    add('entry', position.entry_price, tr('entryLine'), CHART_LINE_COLORS.entry);
    const rawStop = advice.trailing_stop ?? advice.stop_loss ?? advice.sl ?? position.stop_loss ?? position.stop_price;
    let stop = validPositionStop(rawStop, position);
    if (stop === null) {
      const live = lineNumber(position.mark_price);
      const entry = lineNumber(position.entry_price);
      const atr = lineNumber(ai?.atr);
      if (entry !== null && atr !== null) {
        const reference = live !== null ? live : entry;
        stop = position.side === 'LONG'
          ? Math.min(entry - atr * 0.75, reference - atr * 0.75)
          : Math.max(entry + atr * 0.75, reference + atr * 0.75);
      }
    }
    add('stop', stop, tr('stopLine'), CHART_LINE_COLORS.stop, 'dashed');
    if (chartLineSettings.takeProfit && advice.scaled_tp?.length) {
      advice.scaled_tp.forEach((target, index) => add('takeProfit', target.price, `${tr('takeProfitLines')} ${index + 1}`, CHART_LINE_COLORS.takeProfit, 'dotted'));
    }
  } else if (activePlan) {
    add('entry', activePlan.entry_price, tr('aiEntry'), CHART_LINE_COLORS.entry);
    add('entry', activePlan.entry_low, `${tr('entryZone')} ${tr('low')}`, CHART_LINE_COLORS.entry, 'dotted');
    add('entry', activePlan.entry_high, `${tr('entryZone')} ${tr('high')}`, CHART_LINE_COLORS.entry, 'dotted');
    add('stop', activePlan.stop_loss, tr('aiStop'), CHART_LINE_COLORS.stop, 'dashed');
    if (chartLineSettings.takeProfit) {
      add('takeProfit', activePlan.tp1, tr('aiTp1'), CHART_LINE_COLORS.takeProfit, 'dotted');
      add('takeProfit', activePlan.tp2, tr('aiTp2'), CHART_LINE_COLORS.takeProfit, 'dotted');
    }
  }
  const ind = lastIndicators || {};
  const supports = ai?.supports?.length ? ai.supports : [ind.sr_support];
  const resistances = ai?.resistances?.length ? ai.resistances : [ind.sr_resistance];
  if (chartLineSettings.levels) {
    supports.filter(Boolean).forEach((value, index) => add('levels', value, `${tr('support')} ${index + 1}`, CHART_LINE_COLORS.support, 'dashed'));
    resistances.filter(Boolean).forEach((value, index) => add('levels', value, `${tr('resistance')} ${index + 1}`, CHART_LINE_COLORS.resistance, 'dashed'));
  }
  add('ema', ind.ema9, 'EMA9', CHART_LINE_COLORS.ema);
  add('ema', ind.ema21, 'EMA21', CHART_LINE_COLORS.ema, 'dashed');
  add('vwap', ind.vwap, 'VWAP', CHART_LINE_COLORS.vwap);
  const draftPrice = lineNumber(chartOrderDraft?.price);
  if (draftPrice !== null) {
    lines.push({
      name: tr('chartOrderPending'),
      yAxis: draftPrice,
      lineStyle: { color: chartOrderDraft.side === 'SELL' ? CHART_LINE_COLORS.stop : CHART_LINE_COLORS.entry, width: 2, type: 'solid' },
      label: { color: THEMES[currentTheme].text0, backgroundColor: 'rgba(10,14,23,.9)' }
    });
  }
  if (Array.isArray(userHorizontalLevels)) {
    userHorizontalLevels.forEach((price, idx) => {
      lines.push({
        name: `参考线 ${idx + 1}`,
        yAxis: price,
        lineStyle: { color: '#fbbf24', width: 1.8, type: 'dashed' },
        label: {
          color: '#fbbf24',
          backgroundColor: 'rgba(10,14,23,.9)',
          formatter: `参考线 ${price}`
        }
      });
    });
  }
  if (Array.isArray(userTrendLines)) {
    userTrendLines.forEach((trend, idx) => {
      lines.push([
        {
          name: `趋势线 ${idx + 1}`,
          coord: [trend.p1.time || trend.p1.index, trend.p1.price],
          lineStyle: { color: '#38bdf8', width: 2, type: 'solid' },
          label: {
            show: true,
            position: 'start',
            formatter: `TL ${idx + 1}`,
            color: '#38bdf8',
            backgroundColor: currentTheme === 'light' ? 'rgba(255,255,255,.9)' : 'rgba(10,14,23,.9)',
            padding: [2, 4],
            borderRadius: 3
          }
        },
        {
          coord: [trend.p2.time || trend.p2.index, trend.p2.price]
        }
      ]);
    });
  }
  if (trendStartPoint) {
    lines.push({
      name: '趋势线起点',
      coord: [trendStartPoint.time || trendStartPoint.index, trendStartPoint.price],
      symbol: 'circle',
      symbolSize: 8,
      itemStyle: { color: '#38bdf8' }
    });
  }
  if (currentMeasureResult && currentMeasureResult.p1 && currentMeasureResult.p2) {
    const isUp = currentMeasureResult.delta >= 0;
    const mColor = isUp ? '#10b981' : '#ef4444';
    lines.push([
      {
        name: '测量区间',
        coord: [currentMeasureResult.p1.time || currentMeasureResult.p1.index, currentMeasureResult.p1.price],
        lineStyle: { color: mColor, width: 2, type: 'dashed' },
        label: {
          show: true,
          position: 'middle',
          formatter: `${isUp ? '+' : ''}${currentMeasureResult.pct.toFixed(2)}% (${currentMeasureResult.bars}K)`,
          color: '#ffffff',
          backgroundColor: mColor,
          padding: [3, 7],
          borderRadius: 4
        }
      },
      {
        coord: [currentMeasureResult.p2.time || currentMeasureResult.p2.index, currentMeasureResult.p2.price]
      }
    ]);
  }
  return lines;
}
function chartMarkLine() {
  return {
    silent: true,
    symbol: ['none', 'none'],
    animation: false,
    label: {
      show: true,
      position: 'insideEndTop',
      fontSize: 10,
      formatter: params => `${params.name} ${lineNumber(params.value) ?? params.value}`,
      color: THEMES[currentTheme].text0,
      backgroundColor: 'rgba(10,14,23,.82)',
      padding: [2, 4],
      borderRadius: 2
    },
    data: chartLineLevels()
  };
}

function toggleChartOrderMode() {
  chartOrderMode = !chartOrderMode;
  const button = document.getElementById('chart-order-mode');
  if (button) {
    button.classList.toggle('active', chartOrderMode);
    button.dataset.i18n = chartOrderMode ? 'chartOrderModeOn' : 'chartOrderModeOff';
    button.textContent = tr(button.dataset.i18n);
  }
  const hint = document.getElementById('chart-order-hint');
  if (hint) {
    hint.dataset.i18n = chartOrderMode ? 'chartOrderHintActive' : 'chartOrderHint';
    hint.textContent = tr(hint.dataset.i18n);
  }
  if (!chartOrderMode) closeChartOrderTicket();
}

function closeChartOrderTicket() {
  document.getElementById('chart-order-ticket')?.remove();
  chartOrderDraft = null;
  renderChart();
}

function selectChartOrderSide(side) {
  if (!chartOrderDraft) return;
  chartOrderDraft.side = side === 'SELL' ? 'SELL' : 'BUY';
  document.querySelectorAll('[data-chart-order-side]').forEach(button => {
    button.classList.toggle('active', button.dataset.chartOrderSide === chartOrderDraft.side);
  });
  renderChart();
}

function openChartOrderTicket(price) {
  const normalizedPrice = lineNumber(price);
  if (normalizedPrice === null || !currentSymbol) return;
  chartOrderDraft = { price: normalizedPrice, side: 'BUY' };
  document.getElementById('chart-order-ticket')?.remove();
  const ticket = document.createElement('div');
  ticket.id = 'chart-order-ticket';
  ticket.className = 'chart-order-ticket';
  ticket.innerHTML = `
    <div class="chart-order-ticket-head">
      <strong data-i18n="chartOrderTicket">${tr('chartOrderTicket')}</strong>
      <button class="chart-order-ticket-close" type="button" onclick="closeChartOrderTicket()">×</button>
    </div>
    <div class="chart-order-ticket-body">
      <div class="chart-order-ticket-grid">
        <div class="chart-order-field"><label for="chart-order-symbol" data-i18n="chartOrderSymbol">${tr('chartOrderSymbol')}</label><input id="chart-order-symbol" value="${currentSymbol}" readonly></div>
        <div class="chart-order-field"><label for="chart-order-price" data-i18n="chartOrderPrice">${tr('chartOrderPrice')}</label><input id="chart-order-price" type="number" min="0" step="any" value="${normalizedPrice}"></div>
      </div>
      <div class="chart-order-field"><div class="chart-order-field-title" data-i18n="chartOrderSide">${tr('chartOrderSide')}</div>
        <div class="chart-order-side">
          <button type="button" class="active buy" data-chart-order-side="BUY" onclick="selectChartOrderSide('BUY')" data-i18n="chartOrderBuy">${tr('chartOrderBuy')}</button>
          <button type="button" class="sell" data-chart-order-side="SELL" onclick="selectChartOrderSide('SELL')" data-i18n="chartOrderSell">${tr('chartOrderSell')}</button>
        </div>
      </div>
      <div class="chart-order-field"><label for="chart-order-quantity" data-i18n="chartOrderQuantity">${tr('chartOrderQuantity')}</label><input id="chart-order-quantity" type="number" min="0" step="any" placeholder="0"></div>
      <label class="chart-order-confirm"><input id="chart-order-confirm" type="checkbox"><span data-i18n="chartOrderConfirm">${tr('chartOrderConfirm')}</span></label>
      <div class="chart-order-ticket-actions">
        <button type="button" onclick="closeChartOrderTicket()" data-i18n="chartOrderCancel">${tr('chartOrderCancel')}</button>
        <button id="chart-order-submit" type="button" class="primary" onclick="submitChartLimitOrder(event)" data-i18n="chartOrderSubmit">${tr('chartOrderSubmit')}</button>
      </div>
      <div id="chart-order-status" class="chart-order-status"></div>
    </div>`;
  document.body.appendChild(ticket);
  ticket.querySelector('#chart-order-price')?.focus();
  renderChart();
}

async function submitChartLimitOrder(event) {
  const button = event?.currentTarget || document.getElementById('chart-order-submit');
  const status = document.getElementById('chart-order-status');
  const symbol = document.getElementById('chart-order-symbol')?.value || currentSymbol;
  const side = chartOrderDraft?.side || 'BUY';
  const price = Number(document.getElementById('chart-order-price')?.value);
  const quantity = Number(document.getElementById('chart-order-quantity')?.value);
  const confirmed = Boolean(document.getElementById('chart-order-confirm')?.checked);
  if (!Number.isFinite(price) || price <= 0 || !Number.isFinite(quantity) || quantity <= 0 || !confirmed) {
    if (status) { status.className = 'chart-order-status error'; status.textContent = !confirmed ? tr('chartOrderConfirmRequired') : tr('chartOrderInvalid'); }
    return;
  }
  if (button) { button.disabled = true; button.textContent = tr('chartOrderSubmitting'); }
  if (status) { status.className = 'chart-order-status'; status.textContent = ''; }
  try {
    const response = await fetch('/api/chart_limit_order', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({symbol, side, quantity, price})
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || `HTTP ${response.status}`);
    if (status) { status.className = 'chart-order-status success'; status.textContent = `${tr('chartOrderSubmitted')} · ${result.status || 'NEW'}`; }
  } catch (error) {
    if (status) { status.className = 'chart-order-status error'; status.textContent = tr('chartOrderFailed') + (error?.message || tr('unknownError')); }
  } finally {
    if (button) { button.disabled = false; button.textContent = tr('chartOrderSubmit'); }
  }
}

// ===== Technical Indicators & Sub-Indicator Engine =====
let lastTradesLog = [];
let currentSubInd = 'vol'; // 'vol' | 'macd' | 'rsi'

function switchSubIndicator(mode) {
  currentSubInd = mode;
  ['vol', 'macd', 'rsi'].forEach(m => {
    const btn = document.getElementById('sub-ind-' + m);
    if (btn) btn.classList.toggle('active', m === mode);
  });
  renderChart();
}

function calcEMA(candles, period) {
  if (!candles || !candles.length) return [];
  const k = 2 / (period + 1);
  const res = [];
  let ema = Number(candles[0][1]);
  res.push(Number(ema.toFixed(6)));
  for (let i = 1; i < candles.length; i++) {
    const close = Number(candles[i][1]);
    ema = close * k + ema * (1 - k);
    res.push(Number(ema.toFixed(6)));
  }
  return res;
}

function calcBOLL(candles, period = 20, stdDev = 2) {
  if (!candles || !candles.length) return { upper: [], mid: [], lower: [] };
  const mid = [], upper = [], lower = [];
  for (let i = 0; i < candles.length; i++) {
    if (i < period - 1) {
      mid.push(null); upper.push(null); lower.push(null);
      continue;
    }
    const slice = candles.slice(i - period + 1, i + 1).map(c => Number(c[1]));
    const sum = slice.reduce((a, b) => a + b, 0);
    const mean = sum / period;
    const variance = slice.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / period;
    const std = Math.sqrt(variance);
    mid.push(Number(mean.toFixed(6)));
    upper.push(Number((mean + stdDev * std).toFixed(6)));
    lower.push(Number((mean - stdDev * std).toFixed(6)));
  }
  return { upper, mid, lower };
}

function calcMACD(candles, fast = 12, slow = 26, signal = 9) {
  if (!candles || !candles.length) return { dif: [], dea: [], macd: [] };
  const emaFast = calcEMA(candles, fast);
  const emaSlow = calcEMA(candles, slow);
  const dif = [];
  for (let i = 0; i < candles.length; i++) {
    dif.push(Number((emaFast[i] - emaSlow[i]).toFixed(6)));
  }
  const kSig = 2 / (signal + 1);
  const dea = [];
  let deaVal = dif[0] || 0;
  dea.push(Number(deaVal.toFixed(6)));
  for (let i = 1; i < dif.length; i++) {
    deaVal = dif[i] * kSig + deaVal * (1 - kSig);
    dea.push(Number(deaVal.toFixed(6)));
  }
  const macd = [];
  for (let i = 0; i < candles.length; i++) {
    macd.push(Number(((dif[i] - dea[i]) * 2).toFixed(6)));
  }
  return { dif, dea, macd };
}

function calcRSI(candles, period = 14) {
  if (!candles || !candles.length) return [];
  const rsi = [];
  let gains = 0, losses = 0;
  for (let i = 0; i < candles.length; i++) {
    if (i === 0) { rsi.push(null); continue; }
    const change = Number(candles[i][1]) - Number(candles[i - 1][1]);
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? -change : 0;
    if (i <= period) {
      gains += gain;
      losses += loss;
      if (i === period) {
        const avgGain = gains / period;
        const avgLoss = losses / period;
        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
        rsi.push(Number((100 - (100 / (1 + rs))).toFixed(2)));
      } else {
        rsi.push(null);
      }
    } else {
      const prevAvgGain = gains / period;
      const prevAvgLoss = losses / period;
      const avgGain = (prevAvgGain * (period - 1) + gain) / period;
      const avgLoss = (prevAvgLoss * (period - 1) + loss) / period;
      gains = avgGain * period;
      losses = avgLoss * period;
      const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
      rsi.push(Number((100 - (100 / (1 + rs))).toFixed(2)));
    }
  }
  return rsi;
}

// ===== Chart =====
function initChart() {
  const isLight = (currentTheme === 'light');
  chart = echarts.init(document.getElementById('kline-chart'), isLight ? null : 'dark');
  window.chart = chart;
  if (window.ResizeObserver) {
    const chartEl = document.getElementById('kline-chart');
    if (chartEl && !chartEl._roBound) {
      chartEl._roBound = true;
      const ro = new ResizeObserver(() => {
        if (chart && typeof chart.resize === 'function') {
          chart.resize();
        }
      });
      ro.observe(chartEl);
    }
  }
  chart.setOption({
    backgroundColor: 'transparent',
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' }, backgroundColor: THEMES[currentTheme].panelBg, borderColor: THEMES[currentTheme].border, textStyle: { fontSize: 12, fontFamily: 'monospace', color: THEMES[currentTheme].text0 },
      formatter: function(params) {
        const p = params.filter(x => x.seriesType === 'candlestick')[0];
        if (!p) return '';
        const d = p.data;
        const volP = params.filter(x => x.seriesType === 'bar')[0];
        const vol = volP ? volP.data : '-';
        const dir = d[1] >= d[0] ? '▲' : '▼';
        const col = d[1] >= d[0] ? '#10b981' : '#ef4444';
        const fmt = v => Number(v).toFixed(8).replace(/0+$/, '').replace(/\.$/, '');
        const rows = [
          [tr('open'), fmt(d[0])],
          [tr('close'), `<span style="color:${col}">${fmt(d[1])} ${dir}</span>`],
          [tr('low'), fmt(d[2])],
          [tr('high'), fmt(d[3])],
          [tr('volume'), vol]
        ];
        params.forEach(item => {
          if (['EMA9', 'EMA21', 'EMA55', 'BOLL-UP', 'BOLL-MID', 'BOLL-LOW', 'DIF', 'DEA', 'RSI14'].includes(item.seriesName) && item.data !== null && item.data !== undefined) {
            rows.push([item.seriesName, `<span style="color:${item.color}">${fmt(item.data)}</span>`]);
          }
        });
        let h = `<div style="font-size:12px;line-height:1.8">${p.axisValue}`;
        h += `<table style="margin-top:4px;border-collapse:collapse">`;
        for (const [k, v] of rows) h += `<tr><td style="color:${THEMES[currentTheme].text2};padding-right:10px">${k}</td><td style="font-weight:600">${v}</td></tr>`;
        h += `</table></div>`;
        return h;
      } },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: 60, right: 16, top: 12, height: '68%' },
      { left: 60, right: 16, top: '82%', height: '14%' }
    ],
    xAxis: [
      { type: 'category', data: [], gridIndex: 0, axisLine: { lineStyle: { color: THEMES[currentTheme].border } }, axisLabel: { fontSize: 9, color: THEMES[currentTheme].text2 }, splitLine: { show: false } },
      { type: 'category', data: [], gridIndex: 1, axisLine: { lineStyle: { color: THEMES[currentTheme].border } }, axisLabel: { show: false }, splitLine: { show: false } }
    ],
    yAxis: [
      { scale: true, gridIndex: 0, splitLine: { lineStyle: { color: THEMES[currentTheme].bg2 } }, axisLabel: { fontSize: 9, color: THEMES[currentTheme].text2 } },
      { scale: true, gridIndex: 1, splitLine: { show: false }, axisLabel: { fontSize: 9, color: THEMES[currentTheme].text2 } }
    ],
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 65, end: 100 }],
    series: [
      { type: 'candlestick', data: [], xAxisIndex: 0, yAxisIndex: 0, markArea: { silent: true, z: 0, data: [] }, markPoint: { silent: true, data: [] }, itemStyle: { color: '#10b981', color0: '#ef4444', borderColor: '#10b981', borderColor0: '#ef4444' } },
      { type: 'bar', data: [], xAxisIndex: 1, yAxisIndex: 1, itemStyle: { color: p => p.data >= 0 ? 'rgba(16,185,129,.5)' : 'rgba(239,68,68,.5)' } }
    ]
  });
  chart.getZr().on('click', event => {
    if (!chart.containPixel({gridIndex: 0}, [event.offsetX, event.offsetY])) return;
    const point = chart.convertFromPixel({gridIndex: 0}, [event.offsetX, event.offsetY]);
    const price = Array.isArray(point) ? Number(point[1]) : Number(point);
    const xCoord = Array.isArray(point) ? Math.round(point[0]) : 0;
    if (!Number.isFinite(price) || price <= 0) return;
    const safeX = Math.max(0, Math.min(xCoord, (kTimes.length ? kTimes.length - 1 : 0)));
    const time = kTimes[safeX] || '';

    if (activeChartTool === 'trend') {
      if (!trendStartPoint) {
        trendStartPoint = { time, price: Number(price.toPrecision(6)), index: safeX };
        renderChart();
        showChartToolToast(`已锁定趋势线起点: ${trendStartPoint.price}，请点击终点完成连线...`);
      } else {
        const p1 = trendStartPoint;
        const p2 = { time, price: Number(price.toPrecision(6)), index: safeX };
        userTrendLines.push({ p1, p2, id: Date.now() });
        trendStartPoint = null;
        renderChart();
        showChartToolToast(`✅ 趋势线已生成（当前共 ${userTrendLines.length} 条）`);
      }
      return;
    }

    if (activeChartTool === 'hline') {
      const roundedP = Number(price.toPrecision(6));
      userHorizontalLevels.push(roundedP);
      renderChart();
      showChartToolToast(`✅ 已在 ${roundedP} 处添加水平参考线（点击 ✕ 可清空）`);
      return;
    }

    if (activeChartTool === 'measure') {
      if (!measureStartPoint) {
        measureStartPoint = { time, price, index: safeX };
        showChartToolToast(`已锁定测量起点: ${price.toFixed(4)}，请点击终点...`);
        showMeasureTooltip(`起点: ${price.toFixed(4)}，请点击终点...`, event.offsetX, event.offsetY);
        renderChart();
      } else {
        const p1 = { time: measureStartPoint.time || time, price: measureStartPoint.price, index: measureStartPoint.index };
        const p2 = { time, price, index: safeX };
        const delta = p2.price - p1.price;
        const pct = (delta / p1.price) * 100;
        const bars = Math.abs(p2.index - p1.index) + 1;
        currentMeasureResult = { p1, p2, delta, pct, bars };
        measureStartPoint = null;
        renderChart();
        showMeasureResult(currentMeasureResult, event.offsetX, event.offsetY);
        showChartToolToast(`✅ 测量完成: ${delta >= 0 ? '+' : ''}${pct.toFixed(2)}% (${bars} 根K线)`);
      }
      return;
    }

    if (activeChartTool === 'cursor') {
      if (chartOrderMode) {
        openChartOrderTicket(price);
      } else {
        showChartToolToast(`当前价格: ${Number(price.toPrecision(6))}`);
      }
      return;
    }

    if (chartOrderMode) openChartOrderTicket(price);
  });
  window.addEventListener('resize', () => chart.resize());
}

async function loadKlines() {
  const symbol = document.getElementById('symbol-select')?.value || currentSymbol || 'BTCUSDT';
  if (!symbol) return;
  const interval = document.getElementById('interval-select')?.value || '5m';
  currentSymbol = symbol;
  try {
    const res = await fetch(`/api/klines/${symbol}?interval=${interval}&limit=200`);
    const data = await res.json();
    kSymbol = symbol;
    kOpenTimes = data.map(d => d.time);
    kTimes = data.map(d => fmtTime(d.time));
    kSeries = data.map(d => [d.open, d.close, d.low, d.high]);
    kVols = data.map(d => d.close >= d.open ? d.volume : -d.volume);
    renderChart();
    updateChartHeader(data);
    renderChartInfoPanel();
    renderChartDataPanel();
    if (data.length) flashPriceDisplay(symbol, data[data.length-1].close);
    if (document.getElementById('side-obsidian')?.style.display !== 'none') {
      loadObsidianStrategyMatch(symbol);
    }
    fetch(`/api/smart_money/${symbol}`)
      .then(r => r.json()).then(renderSmartMoney).catch(e => console.debug('smart money', e));
    fetch('/api/trades').then(r => r.json()).then(t => {
      if (Array.isArray(t)) { lastTradesLog = t; }
    }).catch(() => {});
  } catch(e) { console.error(e); }
}

// ===== 高性能平滑数字滚动微动效引擎 (Smooth Number Ticker Engine) =====
const _activeNumberAnimations = new WeakMap();
function smoothAnimateNumber(el, targetVal, options = {}) {
  if (!el || !Number.isFinite(targetVal)) return;
  const duration = options.duration || 320;
  const decimals = options.decimals !== undefined ? options.decimals : 2;
  const prefix = options.prefix || '';
  const suffix = options.suffix || '';
  const sign = options.sign || false;

  const currentVal = Number(el.dataset.animatedVal);
  const startVal = Number.isFinite(currentVal) ? currentVal : targetVal;

  if (Math.abs(startVal - targetVal) < 1e-7) {
    el.dataset.animatedVal = targetVal;
    const signStr = sign && targetVal > 0 ? '+' : '';
    el.textContent = `${prefix}${signStr}${fmt(targetVal, decimals)}${suffix}`;
    return;
  }

  if (_activeNumberAnimations.has(el)) {
    cancelAnimationFrame(_activeNumberAnimations.get(el));
  }
  const startTime = performance.now();

  function step(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    // Ease-Out Quartic 物理阻尼平滑曲线
    const ease = 1 - Math.pow(1 - progress, 4);
    const val = startVal + (targetVal - startVal) * ease;
    el.dataset.animatedVal = val;
    const signStr = sign && val > 0 ? '+' : '';
    el.textContent = `${prefix}${signStr}${fmt(val, decimals)}${suffix}`;

    if (progress < 1) {
      const handle = requestAnimationFrame(step);
      _activeNumberAnimations.set(el, handle);
    } else {
      el.dataset.animatedVal = targetVal;
      const signStr = sign && targetVal > 0 ? '+' : '';
      el.textContent = `${prefix}${signStr}${fmt(targetVal, decimals)}${suffix}`;
      _activeNumberAnimations.delete(el);
    }
  }

  const handle = requestAnimationFrame(step);
  _activeNumberAnimations.set(el, handle);
}

function flashPriceDisplay(symbol, price) {
  const el = document.getElementById('price-display');
  if (!el) return;
  const num = Number(price);
  const oldPrice = Number(el.dataset.lastPrice);
  if (Number.isFinite(num)) {
    el.dataset.lastPrice = num;
    if (Number.isFinite(oldPrice) && oldPrice !== num) {
      el.classList.remove('price-flash-up', 'price-flash-down');
      void el.offsetWidth;
      if (num > oldPrice) {
        el.classList.add('price-flash-up');
      } else {
        el.classList.add('price-flash-down');
      }
    }
    const dec = num >= 100 ? 2 : (num >= 1 ? 4 : 6);
    smoothAnimateNumber(el, num, { prefix: `${symbol} `, decimals: dec, duration: 240 });
  } else {
    el.textContent = `${symbol} ${price}`;
  }
}

function fmtTime(ms) {
  return new Date(ms).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',hour12:false});
}

function renderChart() {
  if (!chart) return;
  const extent = chartLineExtent();

  const ema9 = calcEMA(kSeries, 9);
  const ema21 = calcEMA(kSeries, 21);
  const ema55 = calcEMA(kSeries, 55);
  const boll = calcBOLL(kSeries, 20, 2);
  const macdData = calcMACD(kSeries, 12, 26, 9);
  const rsiData = calcRSI(kSeries, 14);

  const seriesList = [
    {
      name: 'kline',
      type: 'candlestick',
      data: kSeries,
      xAxisIndex: 0,
      yAxisIndex: 0,
      markLine: chartMarkLine(),
      ...chartAnnotations(),
      itemStyle: {
        color: '#10b981',
        color0: '#f43f5e',
        borderColor: '#10b981',
        borderColor0: '#f43f5e',
        shadowBlur: 4,
        shadowColor: 'rgba(0,0,0,0.45)'
      }
    }
  ];

  if (chartLineSettings.ema) {
    seriesList.push(
      { name: 'EMA9', type: 'line', data: ema9, xAxisIndex: 0, yAxisIndex: 0, smooth: true, showSymbol: false, lineStyle: { color: CHART_LINE_COLORS.ema9, width: 1.8, shadowBlur: 10, shadowColor: 'rgba(56, 189, 248, 0.45)' } },
      { name: 'EMA21', type: 'line', data: ema21, xAxisIndex: 0, yAxisIndex: 0, smooth: true, showSymbol: false, lineStyle: { color: CHART_LINE_COLORS.ema21, width: 1.8, shadowBlur: 8, shadowColor: 'rgba(168, 85, 247, 0.4)' } },
      { name: 'EMA55', type: 'line', data: ema55, xAxisIndex: 0, yAxisIndex: 0, smooth: true, showSymbol: false, lineStyle: { color: CHART_LINE_COLORS.ema55, width: 1.2, type: 'dashed' } }
    );
  }

  if (chartLineSettings.boll) {
    seriesList.push(
      { name: 'BOLL-UP', type: 'line', data: boll.upper, xAxisIndex: 0, yAxisIndex: 0, smooth: true, showSymbol: false, lineStyle: { color: CHART_LINE_COLORS.boll, width: 1, type: 'dashed' } },
      { name: 'BOLL-MID', type: 'line', data: boll.mid, xAxisIndex: 0, yAxisIndex: 0, smooth: true, showSymbol: false, lineStyle: { color: CHART_LINE_COLORS.boll, width: 1 } },
      { name: 'BOLL-LOW', type: 'line', data: boll.lower, xAxisIndex: 0, yAxisIndex: 0, smooth: true, showSymbol: false, lineStyle: { color: CHART_LINE_COLORS.boll, width: 1, type: 'dashed' } }
    );
  }

  const volOverlay = document.getElementById('chart-volume-value');
  const volSpan = document.querySelector('.chart-volume-overlay span');

  if (currentSubInd === 'macd') {
    if (volSpan) volSpan.textContent = 'MACD (12, 26, 9)';
    const lastDif = macdData.dif[macdData.dif.length - 1] ?? '--';
    const lastDea = macdData.dea[macdData.dea.length - 1] ?? '--';
    const lastMacd = macdData.macd[macdData.macd.length - 1] ?? '--';
    if (volOverlay) volOverlay.textContent = `DIF:${lastDif} DEA:${lastDea} MACD:${lastMacd}`;

    seriesList.push(
      {
        name: 'MACD',
        type: 'bar',
        data: macdData.macd,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: {
          borderRadius: [2, 2, 0, 0],
          color: p => p.data >= 0 ? new echarts.graphic.LinearGradient(0, 0, 0, 1, [{offset: 0, color: 'rgba(16,185,129,.9)'}, {offset: 1, color: 'rgba(16,185,129,.2)'}]) : new echarts.graphic.LinearGradient(0, 0, 0, 1, [{offset: 0, color: 'rgba(244,63,94,.2)'}, {offset: 1, color: 'rgba(244,63,94,.9)'}])
        }
      },
      { name: 'DIF', type: 'line', data: macdData.dif, xAxisIndex: 1, yAxisIndex: 1, showSymbol: false, lineStyle: { color: '#38bdf8', width: 1.4, shadowBlur: 8, shadowColor: 'rgba(56, 189, 248, 0.4)' } },
      { name: 'DEA', type: 'line', data: macdData.dea, xAxisIndex: 1, yAxisIndex: 1, showSymbol: false, lineStyle: { color: '#f59e0b', width: 1.4 } }
    );
  } else if (currentSubInd === 'rsi') {
    if (volSpan) volSpan.textContent = 'RSI (14)';
    const lastRsi = rsiData[rsiData.length - 1] ?? '--';
    if (volOverlay) volOverlay.textContent = `${lastRsi}`;

    seriesList.push(
      {
        name: 'RSI14',
        type: 'line',
        data: rsiData,
        xAxisIndex: 1,
        yAxisIndex: 1,
        showSymbol: false,
        lineStyle: { color: '#c084fc', width: 1.8, shadowBlur: 8, shadowColor: 'rgba(192, 132, 252, 0.4)' },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            { yAxis: 70, lineStyle: { color: '#f43f5e', type: 'dashed', width: 1 }, label: { show: true, formatter: '70' } },
            { yAxis: 30, lineStyle: { color: '#10b981', type: 'dashed', width: 1 }, label: { show: true, formatter: '30' } }
          ]
        }
      }
    );
  } else {
    if (volSpan) volSpan.textContent = tr('chartVolume');
    if (volOverlay && kVols.length) volOverlay.textContent = formatChartValue(Math.abs(kVols[kVols.length - 1]));

    seriesList.push(
      {
        name: 'Volume',
        type: 'bar',
        data: kVols,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: {
          borderRadius: [2, 2, 0, 0],
          color: p => p.data >= 0 ? new echarts.graphic.LinearGradient(0, 0, 0, 1, [{offset: 0, color: 'rgba(16,185,129,.8)'}, {offset: 1, color: 'rgba(16,185,129,.15)'}]) : new echarts.graphic.LinearGradient(0, 0, 0, 1, [{offset: 0, color: 'rgba(244,63,94,.15)'}, {offset: 1, color: 'rgba(244,63,94,.8)'}])
        }
      }
    );
  }

  chart.setOption({
    xAxis: [{ data: kTimes }, { data: kTimes }],
    yAxis: [extent, { scale: true }],
    series: seriesList
  }, { replaceMerge: ['series'] });

  updateChartHeader();
}

// 实时K线: 更新最后一根(未收盘)或追加新K线(收盘后)
function applyRealtimeKline(k) {
  if (!kOpenTimes.length || kSymbol !== currentSymbol) return;
  const lastT = kOpenTimes[kOpenTimes.length-1];
  if (k.open_time < lastT) return; // 过期tick
  if (k.open_time === lastT) {
    kSeries[kSeries.length-1] = [k.open, k.close, k.low, k.high];
    kVols[kVols.length-1] = k.close >= k.open ? k.volume : -k.volume;
  } else {
    kOpenTimes.push(k.open_time);
    kTimes.push(fmtTime(k.open_time));
    kSeries.push([k.open, k.close, k.low, k.high]);
    kVols.push(k.close >= k.open ? k.volume : -k.volume);
    if (kOpenTimes.length > 250) { kOpenTimes.shift(); kTimes.shift(); kSeries.shift(); kVols.shift(); }
  }
  renderChart();
  updateChartHeader({open:k.open, close:k.close, low:k.low, high:k.high});
  renderChartInfoPanel();
  renderChartDataPanel();
  flashPriceDisplay(currentSymbol, k.close);
}

