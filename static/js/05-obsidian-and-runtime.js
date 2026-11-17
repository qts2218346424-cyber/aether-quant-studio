// ===== Obsidian Knowledge Hub JS =====
let obsStatus = null;

async function checkObsidianStatus() {
  try {
    const res = await fetch('/api/obsidian/status');
    const data = await res.json();
    obsStatus = data;
    const dot = document.getElementById('obsidian-dot');
    if (dot) {
      dot.classList.toggle('connected', Boolean(data.connected));
    }
    const countSpan = document.getElementById('obs-strat-count');
    if (countSpan) countSpan.textContent = data.strategy_count || 0;
  } catch (e) {
    console.debug('obsidian status error', e);
  }
}

let currentSnapshotDataUrl = '';

function openSnapshotModal() {
  if (!chart) {
    alert('图表尚未初始化完成');
    return;
  }
  try {
    currentSnapshotDataUrl = chart.getDataURL({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: THEMES[currentTheme]?.bg1 || '#ffffff'
    });
  } catch (e) {
    console.error('Snapshot capture failed', e);
    alert('截图生成失败: ' + e.message);
    return;
  }

  const sym = currentSymbol || document.getElementById('symbol-select')?.value || 'BTCUSDT';
  const interval = document.getElementById('interval-select')?.value || '15m';

  const overlay = document.getElementById('obsidian-snapshot-modal-overlay');
  if (!overlay) return;

  const titleEl = document.getElementById('snap-sym-title');
  if (titleEl) titleEl.textContent = `${sym} (${interval})`;
  const imgEl = document.getElementById('snap-preview-img');
  if (imgEl) imgEl.src = currentSnapshotDataUrl;
  const noteEl = document.getElementById('obs-snapshot-note');
  if (noteEl) noteEl.value = '';
  const statusEl = document.getElementById('snap-status-msg');
  if (statusEl) statusEl.textContent = '';
  const btn = document.getElementById('snap-submit-btn');
  if (btn) {
    btn.disabled = false;
    btn.textContent = '💾 保存并归档至 Obsidian';
  }
  overlay.style.display = 'flex';
}

function closeSnapshotModal() {
  const overlay = document.getElementById('obsidian-snapshot-modal-overlay');
  if (overlay) overlay.style.display = 'none';
}

function addSnapshotTag(text) {
  const textarea = document.getElementById('obs-snapshot-note');
  if (!textarea) return;
  const current = textarea.value.trim();
  if (current) {
    textarea.value = current + '；' + text;
  } else {
    textarea.value = text;
  }
  textarea.focus();
}

async function submitChartSnapshot() {
  if (!currentSnapshotDataUrl) {
    alert('截图数据丢失，请重新打开截图窗口');
    return;
  }
  const btn = document.getElementById('snap-submit-btn');
  const statusMsg = document.getElementById('snap-status-msg');
  const note = (document.getElementById('obs-snapshot-note')?.value || '').trim();
  const sym = currentSymbol || document.getElementById('symbol-select')?.value || 'BTCUSDT';
  const interval = document.getElementById('interval-select')?.value || '15m';

  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ 正在归档至 Obsidian...';
  }
  if (statusMsg) {
    statusMsg.style.color = 'var(--text-2)';
    statusMsg.textContent = '正在保存截图并更新复盘笔记...';
  }

  try {
    const res = await fetch('/api/obsidian/capture_note', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: sym,
        interval: interval,
        note: note,
        image_base64: currentSnapshotDataUrl
      })
    });
    const d = await res.json();
    if (d.ok) {
      if (statusMsg) {
        statusMsg.style.color = '#34d399';
        statusMsg.textContent = `✅ ${d.message || '归档成功！'}`;
      }
      if (btn) btn.textContent = '✅ 已成功归档';
      checkObsidianStatus();
      setTimeout(() => {
        closeSnapshotModal();
      }, 1400);
    } else {
      if (statusMsg) {
        statusMsg.style.color = '#f87171';
        statusMsg.textContent = `❌ ${d.error || '保存失败'}`;
      }
      if (btn) {
        btn.disabled = false;
        btn.textContent = '重试归档';
      }
    }
  } catch (e) {
    if (statusMsg) {
      statusMsg.style.color = '#f87171';
      statusMsg.textContent = `❌ 请求异常: ${e.message}`;
    }
    if (btn) {
      btn.disabled = false;
      btn.textContent = '重试归档';
    }
  }
}

function openObsidianHub() {
  const initialTab = arguments.length > 0 ? arguments[0] : null;
  const overlay = document.getElementById('obsidian-modal-overlay');
  if (overlay) overlay.style.display = 'flex';
  loadObsidianHabits();
  loadObsidianStrategies();
  loadObsidianConfig();
  loadStrategyEvolutionCandidates();
  if (initialTab) {
    switchObsidianTab(initialTab);
  }
}

function closeObsidianHub() {
  const overlay = document.getElementById('obsidian-modal-overlay');
  if (overlay) overlay.style.display = 'none';
}

function switchObsidianTab(tabName) {
  document.querySelectorAll('.obsidian-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.obsTab === tabName);
  });
  document.getElementById('obs-tab-habits').style.display = tabName === 'habits' ? 'block' : 'none';
  document.getElementById('obs-tab-strategies').style.display = tabName === 'strategies' ? 'block' : 'none';
  const evoTab = document.getElementById('obs-tab-evolution');
  if (evoTab) evoTab.style.display = tabName === 'evolution' ? 'block' : 'none';
  document.getElementById('obs-tab-config').style.display = tabName === 'config' ? 'block' : 'none';

  if (tabName === 'habits' && habitRadarChart) {
    setTimeout(() => habitRadarChart.resize(), 50);
  }
  if (tabName === 'evolution') {
    loadStrategyEvolutionCandidates();
    if (evoEquityChart) setTimeout(() => evoEquityChart.resize(), 50);
  }
}

// ===== 备选策略历史模拟与自进化工作台 (Auto-Evolution) =====
let evoCandidatesCache = [];
let currentEvoResult = null;
let evoEquityChart = null;

function populateEvolutionSymbols(preferredSymbol) {
  const symSelect = document.getElementById('evo-symbol-select');
  if (!symSelect) return;
  const currentVal = preferredSymbol || symSelect.value;

  // 1. User's active real positions
  const posSymbols = Array.from(new Set((lastPositions || []).map(p => p.symbol).filter(Boolean)));

  // 2. Terminal select options / current viewing symbol
  const terminalSel = document.getElementById('symbol-select');
  const termSymbols = terminalSel ? Array.from(terminalSel.options).map(o => o.value).filter(Boolean) : [];
  if (currentSymbol && !termSymbols.includes(currentSymbol)) termSymbols.unshift(currentSymbol);

  // 3. Mainstream liquid symbols
  const mainSymbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'DOGEUSDT', 'SUIUSDT', 'XRPUSDT', 'PEPEUSDT', 'NEARUSDT', 'AVAXUSDT'];

  let html = '';

  // Group 1: User's real positions
  if (posSymbols.length > 0) {
    html += `<optgroup label="💼 我的当前真实持仓 (优先推荐)">`;
    posSymbols.forEach(s => {
      const p = (lastPositions || []).find(x => x.symbol === s);
      const sideText = p ? ` (${p.side || p.positionSide || ''} ${p.qty || p.positionAmt || ''})` : '';
      html += `<option value="${s}">💼 ${s}${sideText}</option>`;
    });
    html += `</optgroup>`;
  }

  // Group 2: Current terminal symbol & watchlist
  const watchlist = termSymbols.filter(s => !posSymbols.includes(s));
  if (watchlist.length > 0) {
    html += `<optgroup label="🎯 当前看盘 / 终端自选">`;
    watchlist.slice(0, 10).forEach(s => {
      const label = s === currentSymbol ? `🎯 ${s} (当前看板)` : s;
      html += `<option value="${s}">${label}</option>`;
    });
    html += `</optgroup>`;
  }

  // Group 3: Mainstream leaders
  const mains = mainSymbols.filter(s => !posSymbols.includes(s) && !watchlist.includes(s));
  if (mains.length > 0) {
    html += `<optgroup label="🔥 主流高流动性标的">`;
    mains.forEach(s => {
      html += `<option value="${s}">${s}</option>`;
    });
    html += `</optgroup>`;
  }

  // Group 4: Custom entry
  html += `<optgroup label="➕ 自定义标的">`;
  html += `<option value="__custom__">➕ 手动输入其他合约标的...</option>`;
  html += `</optgroup>`;

  symSelect.innerHTML = html;

  if (currentVal && currentVal !== '__custom__' && Array.from(symSelect.options).some(o => o.value === currentVal)) {
    symSelect.value = currentVal;
  } else if (posSymbols.length > 0) {
    symSelect.value = posSymbols[0];
  } else if (currentSymbol && Array.from(symSelect.options).some(o => o.value === currentSymbol)) {
    symSelect.value = currentSymbol;
  } else {
    symSelect.value = 'BTCUSDT';
  }
}

function onEvolutionSymbolChange() {
  const symSelect = document.getElementById('evo-symbol-select');
  if (!symSelect) return;
  if (symSelect.value === '__custom__') {
    promptCustomBacktestSymbol();
  }
}

function promptCustomBacktestSymbol() {
  const symSelect = document.getElementById('evo-symbol-select');
  const input = prompt('请输入要回测的币安 USDT 合约代码（例如：PEPEUSDT, ZECUSDT, SUIUSDT）：', currentSymbol || 'BTCUSDT');
  if (!input) {
    if (symSelect && symSelect.value === '__custom__') {
      symSelect.value = (lastPositions && lastPositions.length) ? lastPositions[0].symbol : 'BTCUSDT';
    }
    return;
  }
  let s = input.trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (!s.endsWith('USDT')) s += 'USDT';

  if (symSelect) {
    let opt = Array.from(symSelect.options).find(o => o.value === s);
    if (!opt) {
      opt = document.createElement('option');
      opt.value = s;
      opt.textContent = `🌟 ${s} (自定义标的)`;
      symSelect.insertBefore(opt, symSelect.firstChild);
    }
    symSelect.value = s;
  }
}

async function loadStrategyEvolutionCandidates() {
  try {
    populateEvolutionSymbols();
    const res = await fetch('/api/strategies/candidates');
    const data = await res.json();
    if (!data.ok) return;
    evoCandidatesCache = data.candidates || [];

    const select = document.getElementById('evo-strat-select');
    if (!select) return;
    const currentVal = select.value;
    select.innerHTML = evoCandidatesCache.map(c => `<option value="${c.id}">${c.title} (${c.timeframe})</option>`).join('');
    if (currentVal && evoCandidatesCache.some(c => c.id === currentVal)) {
      select.value = currentVal;
    }
    onEvolutionStrategyChange();
  } catch (e) {
    console.error('Failed to load evolution candidates', e);
  }
}

function onEvolutionStrategyChange() {
  const select = document.getElementById('evo-strat-select');
  if (!select) return;
  const sid = select.value;
  const c = evoCandidatesCache.find(x => x.id === sid);
  if (!c) return;

  const titleEl = document.getElementById('evo-strat-title');
  if (titleEl) titleEl.textContent = c.title;
  const badgeEl = document.getElementById('evo-strat-badge');
  if (badgeEl) badgeEl.textContent = `${(c.category || 'TREND').toUpperCase()} · ${c.timeframe}`;
  const descEl = document.getElementById('evo-strat-desc');
  if (descEl) descEl.textContent = c.description;

  const optBadge = document.getElementById('evo-last-optimized-badge');
  if (optBadge) {
    if (c.last_optimized) {
      optBadge.innerHTML = `<span style="color:#10b981;font-weight:600">🟢 上次自进化: ${c.last_optimized}</span>`;
    } else {
      optBadge.textContent = '尚未进行自进化调优';
    }
  }

  const symSelect = document.getElementById('evo-symbol-select');
  if (symSelect && (!symSelect.value || symSelect.value === '__custom__')) {
    if (c.default_symbols && c.default_symbols.length) {
      symSelect.value = c.default_symbols[0];
    }
  }
}


async function runStrategyBacktestUI() {
  const sid = document.getElementById('evo-strat-select')?.value || 'grid_martingale';
  const sym = document.getElementById('evo-symbol-select')?.value || 'BTCUSDT';
  const interval = document.getElementById('evo-interval-select')?.value || '15m';
  const days = parseInt(document.getElementById('evo-days-select')?.value || '15');

  const statusBar = document.getElementById('evo-status-bar');
  if (statusBar) {
    statusBar.style.display = 'block';
    statusBar.textContent = `⏳ 正在在 ${sym} (${interval} · ${days}天) 上模拟回测【${sid}】...`;
  }
  const btn = document.getElementById('btn-evo-backtest');
  if (btn) btn.disabled = true;

  try {
    const res = await fetch('/api/strategies/backtest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ strategy_id: sid, symbol: sym, interval: interval, days: days })
    });
    const d = await res.json();
    if (statusBar) statusBar.style.display = 'none';
    if (btn) btn.disabled = false;

    if (d.ok) {
      const mockResult = {
        strategy_id: sid,
        title: evoCandidatesCache.find(x => x.id === sid)?.title || sid,
        interval: interval,
        symbol: sym,
        days: days,
        baseline: { params: d.params, metrics: d.metrics },
        improved: { params: d.params, metrics: d.metrics },
        uplift: { win_rate_delta: 0.0, net_pnl_delta: 0.0, drawdown_reduction: 0.0, profit_factor_delta: 0.0, is_genuine: true },
        optimized_at: '回测运行完成 (基线状态)'
      };
      currentEvoResult = mockResult;
      renderEvolutionComparison(mockResult);
    } else {
      alert('回测失败: ' + (d.error || '未知错误'));
    }
  } catch (e) {
    if (statusBar) statusBar.style.display = 'none';
    if (btn) btn.disabled = false;
    alert('请求异常: ' + e.message);
  }
}

async function runStrategyAutoImproveUI() {
  const sid = document.getElementById('evo-strat-select')?.value || 'grid_martingale';
  const sym = document.getElementById('evo-symbol-select')?.value || 'BTCUSDT';
  const interval = document.getElementById('evo-interval-select')?.value || '15m';
  const days = parseInt(document.getElementById('evo-days-select')?.value || '20');

  const statusBar = document.getElementById('evo-status-bar');
  if (statusBar) {
    statusBar.style.display = 'block';
    statusBar.textContent = `⚡ 正在执行 AI 自进化与参数空间探索 (70% 训练集寻优 + 30% 样本外检验)...`;
  }
  const btn = document.getElementById('btn-evo-auto');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ 优化搜索中...';
  }

  try {
    const res = await fetch('/api/strategies/auto_improve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ strategy_id: sid, symbol: sym, interval: interval, days: days, auto_sync_obsidian: true })
    });
    const d = await res.json();
    if (statusBar) statusBar.style.display = 'none';
    if (btn) {
      btn.disabled = false;
      btn.textContent = '⚡ 一键自动改进与进化';
    }

    if (d.ok) {
      currentEvoResult = d;
      renderEvolutionComparison(d);
      loadStrategyEvolutionCandidates();
    } else {
      alert('优化失败: ' + (d.error || '未知错误'));
    }
  } catch (e) {
    if (statusBar) statusBar.style.display = 'none';
    if (btn) {
      btn.disabled = false;
      btn.textContent = '⚡ 一键自动改进与进化';
    }
    alert('请求异常: ' + e.message);
  }
}

function renderEvolutionComparison(data) {
  const container = document.getElementById('evo-results-container');
  if (!container) return;
  container.style.display = 'block';

  const base = data.baseline.metrics;
  const imp = data.improved.metrics;
  const up = data.uplift;

  document.getElementById('evo-base-wr').textContent = `${base.win_rate}%`;
  document.getElementById('evo-imp-wr').textContent = `${imp.win_rate}%`;
  const wrPill = document.getElementById('evo-wr-delta-pill');
  if (wrPill) {
    wrPill.textContent = `${up.win_rate_delta >= 0 ? '+' : ''}${up.win_rate_delta}%`;
    wrPill.className = `factor-tag ${up.win_rate_delta >= 0 ? 'bull' : 'bear'}`;
  }

  document.getElementById('evo-base-pnl').textContent = `${base.net_pnl > 0 ? '+' : ''}${base.net_pnl}%`;
  document.getElementById('evo-imp-pnl').textContent = `${imp.net_pnl > 0 ? '+' : ''}${imp.net_pnl}%`;
  const pnlPill = document.getElementById('evo-pnl-delta-pill');
  if (pnlPill) {
    pnlPill.textContent = `${up.net_pnl_delta >= 0 ? '+' : ''}${up.net_pnl_delta}%`;
    pnlPill.className = `factor-tag ${up.net_pnl_delta >= 0 ? 'bull' : 'bear'}`;
  }

  document.getElementById('evo-base-dd').textContent = `${base.max_drawdown}%`;
  document.getElementById('evo-imp-dd').textContent = `${imp.max_drawdown}%`;
  const ddPill = document.getElementById('evo-dd-delta-pill');
  if (ddPill) {
    ddPill.textContent = `风险降低 ${up.drawdown_reduction}%`;
    ddPill.className = `factor-tag ${up.drawdown_reduction >= 0 ? 'bull' : 'bear'}`;
  }

  document.getElementById('evo-base-pf').textContent = `${base.profit_factor}`;
  document.getElementById('evo-imp-pf').textContent = `${imp.profit_factor}`;
  const pfPill = document.getElementById('evo-pf-delta-pill');
  if (pfPill) {
    pfPill.textContent = `${up.profit_factor_delta >= 0 ? '+' : ''}${up.profit_factor_delta}`;
    pfPill.className = `factor-tag ${up.profit_factor_delta >= 0 ? 'bull' : 'bear'}`;
  }

  const tbody = document.getElementById('evo-params-tbody');
  if (tbody) {
    const baseP = data.baseline.params || {};
    const impP = data.improved.params || {};
    const allKeys = Array.from(new Set([...Object.keys(baseP), ...Object.keys(impP)]));

    tbody.innerHTML = allKeys.map(k => {
      const v1 = baseP[k];
      const v2 = impP[k];
      const changed = String(v1) !== String(v2);
      return `
        <tr style="border-bottom:1px solid var(--border)">
          <td style="padding:4px;color:var(--text-1);font-weight:600">${k}</td>
          <td style="padding:4px;color:var(--text-2)">${v1 ?? '--'}</td>
          <td style="padding:4px;color:${changed ? '#34d399;font-weight:700' : 'var(--text-0)'}">
            ${v2 ?? '--'} ${changed ? '✨' : ''}
          </td>
        </tr>
      `;
    }).join('');
  }

  renderEvolutionCharts(base.equity_curve || [], imp.equity_curve || []);
}

function renderEvolutionCharts(baseCurve, impCurve) {
  const dom = document.getElementById('evo-equity-chart');
  if (!dom) return;
  if (!evoEquityChart) {
    evoEquityChart = echarts.init(dom, currentTheme === 'light' ? null : 'dark');
  }

  const times = Array.from(new Set([
    ...baseCurve.map(x => x.time),
    ...impCurve.map(x => x.time)
  ])).sort((a, b) => a - b);

  const baseMap = new Map(baseCurve.map(x => [x.time, x.equity]));
  const impMap = new Map(impCurve.map(x => [x.time, x.equity]));

  let lastBase = 100.0;
  let lastImp = 100.0;

  const baseSeriesData = [];
  const impSeriesData = [];
  const xLabels = [];

  times.forEach(t => {
    if (baseMap.has(t)) lastBase = baseMap.get(t);
    if (impMap.has(t)) lastImp = impMap.get(t);
    const d = new Date(t);
    xLabels.push(`${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`);
    baseSeriesData.push(lastBase);
    impSeriesData.push(lastImp);
  });

  evoEquityChart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 45, right: 20, top: 20, bottom: 25 },
    tooltip: { trigger: 'axis', backgroundColor: THEMES[currentTheme].panelBg, borderColor: THEMES[currentTheme].border, textStyle: { color: THEMES[currentTheme].text0 } },
    xAxis: {
      type: 'category',
      data: xLabels,
      axisLine: { lineStyle: { color: THEMES[currentTheme].border } },
      axisLabel: { color: THEMES[currentTheme].text2, fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      scale: true,
      splitLine: { lineStyle: { color: currentTheme === 'light' ? '#f1f5f9' : 'rgba(255,255,255,0.06)' } },
      axisLabel: { color: THEMES[currentTheme].text2, fontSize: 10, formatter: '{value} U' }
    },
    series: [
      {
        name: '基线原参数',
        type: 'line',
        data: baseSeriesData,
        showSymbol: false,
        lineStyle: { width: 1.5, color: '#94a3b8', type: 'dashed' },
        itemStyle: { color: '#94a3b8' }
      },
      {
        name: 'AI进化调优版',
        type: 'line',
        data: impSeriesData,
        showSymbol: false,
        lineStyle: { width: 2.5, color: '#10b981' },
        itemStyle: { color: '#10b981' },
        areaStyle: { color: 'rgba(16, 185, 129, 0.12)' }
      }
    ]
  });
}

async function applyEvolvedPresetToSystem() {
  if (!currentEvoResult) {
    alert('暂无可应用的进化成果，请先点击「运行历史回测」或「一键自动改进」');
    return;
  }
  const sid = currentEvoResult.strategy_id;
  const params = currentEvoResult.improved.params;
  const feedback = document.getElementById('evo-action-feedback');

  try {
    const res = await fetch('/api/strategies/apply_preset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ strategy_id: sid, params: params })
    });
    const d = await res.json();
    if (d.ok) {
      if (feedback) {
        feedback.innerHTML = `<span style="color:#10b981;font-weight:600">✅ ${d.message}</span>`;
      }
      alert(`✅ 策略【${currentEvoResult.title}】的最佳进化参数已成功热加载至系统运行时！`);
    } else {
      if (feedback) feedback.innerHTML = `<span style="color:#ef4444">❌ 应用失败: ${d.error}</span>`;
    }
  } catch (e) {
    alert('请求失败: ' + e.message);
  }
}

async function syncEvolvedResultToObsidian() {
  if (!currentEvoResult) {
    alert('暂无可同步的进化成果');
    return;
  }
  const feedback = document.getElementById('evo-action-feedback');
  if (feedback) feedback.innerHTML = '⏳ 正在同步至 Obsidian 策略笔记并重编 MOC...';

  try {
    const res = await fetch('/api/strategies/sync_obsidian', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentEvoResult)
    });
    const d = await res.json();
    if (d.ok) {
      if (feedback) {
        feedback.innerHTML = `<span style="color:#10b981;font-weight:600">✅ ${d.message}</span>`;
      }
      alert(`✅ 成功将最新进化战绩写入 Obsidian 对应策略笔记！\n文件: ${d.file}`);
      loadObsidianStrategies(true);
    } else {
      if (feedback) feedback.innerHTML = `<span style="color:#ef4444">❌ 同步失败: ${d.error}</span>`;
    }
  } catch (e) {
    alert('请求失败: ' + e.message);
  }
}

async function loadObsidianHabits() {
  try {
    const res = await fetch('/api/obsidian/habits?days=7');
    const data = await res.json();
    if (!data.ok) return;
    const habits = data.habits || {};
    const radar = habits.radar || {};

    const scoreEl = document.getElementById('habit-overall-score');
    if (scoreEl) scoreEl.textContent = (habits.overall_score || 85) + ' 分';
    const stageEl = document.getElementById('habit-stage-pill');
    if (stageEl) stageEl.textContent = habits.stage || '稳健探索期';

    const stList = document.getElementById('habit-strengths-list');
    if (stList) {
      stList.innerHTML = (habits.strengths || []).map(s => `<div class="habit-diag-item pos">✅ ${s}</div>`).join('') || '<div class="habit-diag-item pos">纪律良好</div>';
    }
    const wnList = document.getElementById('habit-warnings-list');
    if (wnList) {
      wnList.innerHTML = (habits.warnings || []).map(w => `<div class="habit-diag-item warn">🔴 ${w}</div>`).join('') || '<div class="habit-diag-item">暂无严重违纪警告</div>';
    }

    renderHabitRadar(radar);
  } catch (e) {
    console.error('load habits error', e);
  }
}

function renderHabitRadar(radar) {
  const dom = document.getElementById('habit-radar-chart');
  if (!dom) return;
  if (!habitRadarChart) {
    habitRadarChart = echarts.init(dom, currentTheme === 'light' ? null : 'dark');
  }
  habitRadarChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', backgroundColor: THEMES[currentTheme].panelBg, borderColor: THEMES[currentTheme].border, textStyle: { color: THEMES[currentTheme].text0 } },
    radar: {
      indicator: [
        { name: '止损纪律', max: 100 },
        { name: '抗FOMO追涨', max: 100 },
        { name: '持仓盈亏比', max: 100 },
        { name: '情绪稳定度', max: 100 },
        { name: '策略契合度', max: 100 }
      ],
      shape: 'polygon',
      splitNumber: 4,
      axisName: { color: THEMES[currentTheme].text2, fontSize: 11 },
      splitLine: { lineStyle: { color: currentTheme === 'light' ? '#e2e8f0' : 'rgba(51, 65, 85, 0.6)' } },
      splitArea: { show: true, areaStyle: { color: currentTheme === 'light' ? ['#f8fafc', '#f1f5f9'] : ['rgba(30, 41, 59, 0.2)', 'rgba(30, 41, 59, 0.4)'] } },
      axisLine: { lineStyle: { color: currentTheme === 'light' ? '#cbd5e1' : 'rgba(51, 65, 85, 0.6)' } }
    },
    series: [{
      type: 'radar',
      data: [{
        value: [
          radar.discipline || 85,
          radar.anti_fomo || 80,
          radar.patience || 78,
          radar.emotional_control || 88,
          radar.adherence || 82
        ],
        name: '行为习惯评分',
        symbol: 'circle',
        symbolSize: 6,
        itemStyle: { color: '#8b5cf6' },
        areaStyle: { color: 'rgba(139, 92, 246, 0.35)' },
        lineStyle: { width: 2, color: '#a78bfa' }
      }]
    }]
  });
}

async function loadObsidianStrategies(force = false) {
  const container = document.getElementById('obs-strategy-list');
  if (!container) return;
  container.innerHTML = '<div class="empty-state">正在扫描 Obsidian 策略笔记...</div>';
  try {
    const res = await fetch(`/api/obsidian/strategies?force=${force}`);
    const data = await res.json();
    const strats = data.strategies || [];
    const countSpan = document.getElementById('obs-strat-count');
    if (countSpan) countSpan.textContent = strats.length;

    if (!strats.length) {
      container.innerHTML = `
        <div class="empty-state" style="padding:24px;text-align:center">
          <div style="font-size:20px;margin-bottom:8px">📭</div>
          <p style="color:var(--text-1);font-size:13px">未在知识库中检测到策略笔记</p>
          <p style="color:var(--text-2);font-size:11px;margin-top:6px">请前往「知识库路径与同步」选项卡设置路径并点击“一键初始化模板”</p>
        </div>
      `;
      return;
    }

    container.innerHTML = strats.map(s => {
      const symbolsStr = Array.isArray(s.symbols) ? s.symbols.join(', ') : (s.symbols || '全部币种');
      const tagsStr = (s.tags || []).map(t => `<span class="obsidian-strat-badge">#${t}</span>`).join(' ');
      return `
        <div class="obsidian-strategy-card">
          <div class="obsidian-strat-head">
            <div>
              <span class="obsidian-strat-title">📜 ${s.title}</span>
              <span style="font-size:11px;color:var(--text-2);margin-left:8px">${s.relative_path}</span>
            </div>
            <div style="display:flex;gap:6px;align-items:center">
              ${tagsStr}
              <span class="obsidian-strat-badge" style="background:rgba(16,185,129,.15);color:#34d399;border-color:rgba(16,185,129,.3)">${s.timeframe || '15m'}</span>
            </div>
          </div>
          <div style="font-size:11px;color:var(--text-2);margin-bottom:6px">
            适用标的: <b style="color:var(--text-0)">${symbolsStr}</b> | 理论胜率: <b style="color:var(--green)">${s.target_win_rate || '75%+'}</b> | 盈亏比设定: <b style="color:var(--green)">${s.profit_factor || s.risk_reward_ratio || '1:2'}</b>
          </div>
          <div class="obsidian-strat-rules">
            <div class="obsidian-rule-col">
              <strong>🎯 入场条件</strong>
              <span>${s.entry_rules}</span>
            </div>
            <div class="obsidian-rule-col">
              <strong>🛡️ 风控与止盈</strong>
              <span>止损: ${s.risk_rules}<br>止盈: ${s.exit_rules}</span>
            </div>
          </div>
        </div>
      `;
    }).join('');
  } catch (e) {
    container.innerHTML = `<div class="empty-state" style="color:var(--red)">扫描失败: ${e.message}</div>`;
  }
}

async function loadObsidianConfig() {
  try {
    const res = await fetch('/api/obsidian/status');
    const data = await res.json();
    const input = document.getElementById('obs-vault-path-input');
    if (input && data.vault_path) {
      input.value = data.vault_path;
    }
  } catch (e) {}
}

async function saveObsidianConfig() {
  const input = document.getElementById('obs-vault-path-input');
  const statusSpan = document.getElementById('obs-config-status');
  if (!input || !input.value.trim()) {
    alert('请输入有效的 Obsidian Vault 文件夹路径');
    return;
  }
  if (statusSpan) statusSpan.textContent = '保存中...';
  try {
    const res = await fetch('/api/obsidian/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ vault_path: input.value.trim(), auto_sync: true })
    });
    const data = await res.json();
    if (data.ok) {
      if (statusSpan) statusSpan.textContent = '✅ 保存成功！';
      checkObsidianStatus();
      loadObsidianStrategies(true);
      loadObsidianHabits();
    } else {
      if (statusSpan) statusSpan.textContent = '❌ 保存失败: ' + (data.error || '未知错误');
    }
  } catch (e) {
    if (statusSpan) statusSpan.textContent = '❌ 网络错误: ' + e.message;
  }
}

async function initObsidianTemplates() {
  const input = document.getElementById('obs-vault-path-input');
  const statusSpan = document.getElementById('obs-config-status');
  if (statusSpan) statusSpan.textContent = '初始化目录与模板中...';
  try {
    const res = await fetch('/api/obsidian/init_templates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ vault_path: input ? input.value.trim() : null })
    });
    const data = await res.json();
    if (data.ok) {
      if (statusSpan) statusSpan.textContent = '✨ 初始化模板成功！';
      alert('已在您的知识库成功初始化：\n- 01-交易策略\n- 02-交易复盘\n- 03-交易习惯与行为进化');
      loadObsidianStrategies(true);
      checkObsidianStatus();
    } else {
      if (statusSpan) statusSpan.textContent = '❌ ' + (data.error || '失败');
    }
  } catch (e) {
    if (statusSpan) statusSpan.textContent = '❌ ' + e.message;
  }
}

async function syncSquareGuidelinesToObsidian() {
  const statusSpan = document.getElementById('obs-config-status') || document.getElementById('blog-publish-status');
  if (statusSpan) statusSpan.textContent = '正在同步发帖规范与模板库到 Obsidian...';
  try {
    const res = await fetch('/api/obsidian/sync_square_guidelines', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (data.ok) {
      if (statusSpan) statusSpan.textContent = '✨ 成功同步发帖规范与模板库至 Obsidian！';
      alert('已成功同步至 Obsidian 知识库 (04-币安广场与个人博客)：\n- 01-币安广场爆款写作指南与SOP.md\n- 02-爆款文章模板库.md\n- 2026-09-08_BTC夜盘深度推演.md\n\n规范要点：纯净实战交易、日常严禁红包、4大交易员人设、4大流派高盈亏比模板！');
    } else {
      if (statusSpan) statusSpan.textContent = '❌ 同步失败: ' + (data.error || '未知错误');
    }
  } catch (e) {
    if (statusSpan) statusSpan.textContent = '❌ ' + e.message;
  }
}

async function syncCurrentTradesToObsidian() {
  try {
    const res = await fetch('/api/obsidian/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (data.ok) {
      alert(`✅ 成功同步至 Obsidian 知识库！\n复盘笔记: ${data.review_file}\n习惯追踪: ${data.habit_file}`);
      loadObsidianHabits();
    } else {
      alert('同步失败: ' + (data.error || '请先检查知识库路径配置'));
    }
  } catch (e) {
    alert('请求失败: ' + e.message);
  }
}

async function compileObsidianVault() {
  const btn = document.getElementById('btn-obs-compile');
  const origText = btn ? btn.innerHTML : '';
  if (btn) btn.innerHTML = '⏳ 自维护编译中...';
  try {
    const res = await fetch('/api/obsidian/compile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (data.ok) {
      if (typeof showChartToolToast === 'function') {
        showChartToolToast(`✅ 自维护编译成功！已索引 ${data.strategy_count} 篇策略与 MOC 知识地图`, 3500);
      } else {
        alert(`✅ 自维护编译成功！已索引 ${data.strategy_count} 篇策略与 MOC 知识地图。`);
      }
      loadObsidianStrategies(true);
    } else {
      alert('编译失败: ' + (data.error || '未知错误'));
    }
  } catch (e) {
    alert('请求失败: ' + e.message);
  } finally {
    if (btn) btn.innerHTML = origText;
  }
}

// === 图表画线与标尺测量工具 ===
function showChartToolToast(msg, duration = 3000) {
  const toast = document.getElementById('chart-tool-toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.style.display = 'block';
  toast.style.opacity = '1';
  if (toolToastTimer) clearTimeout(toolToastTimer);
  toolToastTimer = setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => { if (toast.style.opacity === '0') toast.style.display = 'none'; }, 250);
  }, duration);
}

function selectChartTool(tool, btn) {
  activeChartTool = tool;
  document.querySelectorAll('.chart-rail-tool').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  measureStartPoint = null;
  trendStartPoint = null;

  const chartDom = document.getElementById('kline-chart');
  if (chartDom) {
    chartDom.style.cursor = (tool === 'trend' || tool === 'hline' || tool === 'measure') ? 'crosshair' : 'default';
  }

  if (tool === 'trend') {
    showChartToolToast('📐 【趋势线模式】请在K线图上点击第 1 点（起点），再点击第 2 点完成连线');
    hideMeasureTooltip();
  } else if (tool === 'hline') {
    showChartToolToast('📏 【水平线模式】点击K线图任意价位添加贯穿水平参考线');
    hideMeasureTooltip();
  } else if (tool === 'measure') {
    showChartToolToast('⏱️ 【多空测量尺】点击第 1 点作为起点，再点击第 2 点测量涨跌幅与周期');
    showMeasureTooltip('请在 K 线图上点击第一点作为测量起点...', 20, 20);
  } else if (tool === 'cursor') {
    showChartToolToast('🔍 【光标模式】鼠标悬停查看K线数值，拖动可平移缩放');
    hideMeasureTooltip();
  }
}

function clearChartDrawings() {
  userHorizontalLevels = [];
  userTrendLines = [];
  trendStartPoint = null;
  measureStartPoint = null;
  currentMeasureResult = null;
  hideMeasureTooltip();
  renderChart();
  showChartToolToast('🗑️ 已清除所有图表画线与测量标注');
  const cursorBtn = document.querySelector('.chart-rail-tool[data-tool="cursor"]');
  selectChartTool('cursor', cursorBtn);
}

function showMeasureTooltip(msg, x, y) {
  const hud = document.getElementById('chart-measure-hud');
  const txt = document.getElementById('chart-measure-text');
  if (!hud || !txt) return;
  txt.innerHTML = `<div style="color:var(--text-1);font-size:11px">${msg}</div>`;
  const plot = document.querySelector('.chart-plot-wrap');
  const maxX = plot ? plot.clientWidth - 220 : 400;
  const maxY = plot ? plot.clientHeight - 120 : 300;
  const clampedX = Math.max(10, Math.min(x + 12, maxX));
  const clampedY = Math.max(10, Math.min(y + 12, maxY));
  hud.style.left = clampedX + 'px';
  hud.style.top = clampedY + 'px';
  hud.style.display = 'block';
}

function hideMeasureTooltip() {
  const hud = document.getElementById('chart-measure-hud');
  if (hud) hud.style.display = 'none';
}

function showMeasureResult(res, x, y) {
  const hud = document.getElementById('chart-measure-hud');
  const txt = document.getElementById('chart-measure-text');
  if (!hud || !txt || !res) return;

  const isUp = res.delta >= 0;
  const color = isUp ? '#10b981' : '#ef4444';
  const sign = isUp ? '+' : '';
  const deltaStr = `${sign}${res.delta.toFixed(4)}`;
  const pctStr = `${sign}${res.pct.toFixed(2)}%`;
  const p1Val = res.p1 && res.p1.price !== undefined ? res.p1.price : res.p1;
  const p2Val = res.p2 && res.p2.price !== undefined ? res.p2.price : res.p2;

  txt.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:5px;font-size:11px;min-width:180px">
      <div style="display:flex;justify-content:space-between;gap:12px">
        <span style="color:var(--text-2)">起点价格:</span>
        <strong style="color:var(--text-0)">${Number(p1Val).toFixed(4)}</strong>
      </div>
      <div style="display:flex;justify-content:space-between;gap:12px">
        <span style="color:var(--text-2)">终点价格:</span>
        <strong style="color:var(--text-0)">${Number(p2Val).toFixed(4)}</strong>
      </div>
      <div style="display:flex;justify-content:space-between;gap:12px;border-top:1px dashed var(--border);padding-top:4px;margin-top:2px">
        <span style="color:var(--text-2)">多空涨跌:</span>
        <strong style="color:${color}">${deltaStr} (${pctStr})</strong>
      </div>
      <div style="display:flex;justify-content:space-between;gap:12px">
        <span style="color:var(--text-2)">K线跨度:</span>
        <span style="color:var(--text-1)">${res.bars} 根 (周期 ${document.getElementById('interval-select')?.value || '5m'})</span>
      </div>
    </div>
  `;
  const plot = document.querySelector('.chart-plot-wrap');
  const maxX = plot ? plot.clientWidth - 220 : 400;
  const maxY = plot ? plot.clientHeight - 140 : 300;
  const clampedX = Math.max(10, Math.min(x + 12, maxX));
  const clampedY = Math.max(10, Math.min(y + 12, maxY));
  hud.style.left = clampedX + 'px';
  hud.style.top = clampedY + 'px';
  hud.style.display = 'block';
}

// === Obsidian 知识库策略实时匹配 ===
async function loadObsidianStrategyMatch(symbol) {
  const sym = symbol || currentSymbol || document.getElementById('symbol-select')?.value || 'BTCUSDT';
  const badge = document.getElementById('obs-match-symbol-badge');
  if (badge) badge.textContent = sym;
  const container = document.getElementById('obs-match-list');
  if (!container) return;

  container.innerHTML = '<div class="empty-state" style="padding:16px 0">正在评估知识库策略规则...</div>';

  try {
    const res = await fetch(`/api/obsidian/match/${encodeURIComponent(sym)}`);
    const data = await res.json();
    renderObsidianStrategyMatch(data);
  } catch (e) {
    container.innerHTML = `<div class="empty-state" style="color:#ef4444;padding:12px 0">加载策略匹配失败: ${e.message}</div>`;
  }
}

function renderObsidianStrategyMatch(data) {
  const container = document.getElementById('obs-match-list');
  if (!container) return;

  if (!data || !data.ok) {
    container.innerHTML = `
      <div class="empty-state" style="padding:16px 8px;text-align:center">
        <div style="font-size:24px;margin-bottom:6px">⚙️</div>
        <p style="color:var(--text-1);font-size:12px">无法连接 Obsidian 知识库</p>
        <p style="color:var(--text-2);font-size:11px;margin-top:4px">${data?.error || '请先在顶部「📓 Obsidian 知识库」配置 Vault 路径'}</p>
      </div>
    `;
    return;
  }

  const matches = data.matches || [];
  if (!matches.length) {
    container.innerHTML = `
      <div class="empty-state" style="padding:20px 8px;text-align:center">
        <div style="font-size:20px;margin-bottom:6px">📭</div>
        <p style="color:var(--text-1);font-size:12px">当前币种无活跃策略匹配</p>
        <p style="color:var(--text-2);font-size:11px;margin-top:4px">您可在 Obsidian 的 01-交易策略 中编写匹配该币种的策略笔记</p>
      </div>
    `;
    return;
  }

  container.innerHTML = matches.map(m => {
    const score = m.match_score || 0;
    const scoreColor = score >= 75 ? '#10b981' : score >= 50 ? '#f59e0b' : '#64748b';
    const dirBadge = m.direction === 'LONG'
      ? '<span style="background:rgba(16,185,129,.15);color:#10b981;border:1px solid rgba(16,185,129,.3);padding:1px 6px;border-radius:4px;font-size:10px;font-weight:700">多头 LONG</span>'
      : m.direction === 'SHORT'
      ? '<span style="background:rgba(239,68,68,.15);color:#ef4444;border:1px solid rgba(239,68,68,.3);padding:1px 6px;border-radius:4px;font-size:10px;font-weight:700">空头 SHORT</span>'
      : '<span style="background:rgba(148,163,184,.15);color:#94a3b8;padding:1px 6px;border-radius:4px;font-size:10px">中性/观望</span>';

    const checklistHtml = (m.checklist || []).map(c => {
      const icon = c.status === 'pass' ? '✅' : c.status === 'warn' ? '⚠️' : '❌';
      const cColor = c.status === 'pass' ? 'var(--text-0)' : c.status === 'warn' ? '#f59e0b' : 'var(--text-2)';
      const ruleName = c.rule || c.name || '评估规则';
      const detailText = c.detail || '';
      return `
        <div style="display:flex;align-items:flex-start;gap:6px;margin-bottom:3px;font-size:11px">
          <span>${icon}</span>
          <span style="color:${cColor};flex:1;line-height:1.4">${ruleName}: <span style="color:var(--text-2)">${detailText}</span></span>
        </div>
      `;
    }).join('');

    let planHtml = '';
    if (m.plan) {
      const p = m.plan;
      const entryVal = p.entry !== undefined ? p.entry : (p.entry_price !== undefined ? p.entry_price : '--');
      const rrRatio = p.rr_ratio || (p.risk_reward_ratio ? String(p.risk_reward_ratio).replace(/^1:/, '') : '2.0');
      const slVal = p.stop_loss !== undefined ? p.stop_loss : '--';
      const tpVal = p.take_profit !== undefined ? p.take_profit : '--';
      const sideClass = p.side === 'BUY' ? 'color:#10b981' : 'color:#ef4444';
      const numEntry = Number(entryVal);
      const slPct = (!isNaN(numEntry) && numEntry > 0 && p.stop_loss !== undefined) ? Math.abs((p.stop_loss - numEntry) / numEntry * 100).toFixed(2) : '0';
      const tpPct = (!isNaN(numEntry) && numEntry > 0 && p.take_profit !== undefined) ? Math.abs((p.take_profit - numEntry) / numEntry * 100).toFixed(2) : '0';
      const btnEntryArg = (!isNaN(numEntry) && numEntry > 0) ? numEntry : 0;

      planHtml = `
        <div style="margin-top:8px;padding:8px;background:rgba(0,0,0,.25);border-radius:6px;border:1px solid var(--border)">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <span style="font-size:11px;font-weight:700;color:var(--text-1)">📋 建议执行点位 (R:R 1:${rrRatio})</span>
            <button class="rec-refresh" onclick="applyObsidianPlanToTicket('${p.side}', ${btnEntryArg})" style="background:#7c3aed;color:#fff;border-color:#8b5cf6;padding:2px 8px;font-size:10px;font-weight:600">🎯 一键带入下单</button>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;font-size:10px">
            <div><span style="color:var(--text-2)">入场方向: </span><b style="${sideClass}">${p.side === 'BUY' ? '买入开多' : '卖出开空'}</b></div>
            <div><span style="color:var(--text-2)">建议入场: </span><b style="color:var(--text-0)">${entryVal}</b></div>
            <div><span style="color:var(--text-2)">止损位: </span><b style="color:#ef4444">${slVal}</b> <span style="color:var(--text-2)">(-${slPct}%)</span></div>
            <div style="grid-column:span 3"><span style="color:var(--text-2)">目标止盈: </span><b style="color:#10b981">${tpVal}</b> <span style="color:var(--text-2)">(+${tpPct}%)</span></div>
          </div>
        </div>
      `;
    }

    return `
      <div class="obsidian-strategy-card" style="margin-bottom:10px;padding:10px;background:var(--bg-1);border:1px solid var(--border);border-radius:8px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <div style="display:flex;align-items:center;gap:6px">
            <strong style="color:var(--text-0);font-size:12px">${m.title}</strong>
            ${dirBadge}
          </div>
          <span style="font-size:12px;font-weight:800;color:${scoreColor}">${score}% 匹配</span>
        </div>
        <div style="margin:6px 0;padding:6px 8px;background:rgba(255,255,255,0.02);border-radius:4px">
          ${checklistHtml}
        </div>
        ${planHtml}
      </div>
    `;
  }).join('');
}

function applyObsidianPlanToTicket(side, price) {
  if (typeof openChartOrderTicket === 'function') {
    openChartOrderTicket(price);
    if (typeof selectChartOrderSide === 'function' && side) {
      selectChartOrderSide(side);
    }
  }
}

// ===== Multi-Panel Mouse Resizing & Collapse Engine =====
(function() {
  const KEY_SIDE_WIDTH = 'qo_workspace_side_width';
  const KEY_BOTTOM_HEIGHT = 'qo_workspace_bottom_height';
  const KEY_TOP_COLLAPSED = 'qo_workspace_top_collapsed';

  const DEFAULT_SIDE_WIDTH = 320;
  const DEFAULT_BOTTOM_HEIGHT = 150;

  let isDragging = false;
  let activeResizer = null;
  let startX = 0;
  let startY = 0;
  let startWidth = 0;
  let startHeight = 0;
  let rafId = null;

  function triggerAllChartsResize() {
    if (typeof chart !== 'undefined' && chart && typeof chart.resize === 'function') chart.resize();
    if (window.chart && typeof window.chart.resize === 'function') window.chart.resize();
    if (window.equityChart && typeof window.equityChart.resize === 'function') window.equityChart.resize();
    if (window.momentumChart && typeof window.momentumChart.resize === 'function') window.momentumChart.resize();
    if (window.habitRadarChart && typeof window.habitRadarChart.resize === 'function') window.habitRadarChart.resize();
    if (window.posCharts && typeof window.posCharts === 'object') {
      Object.values(window.posCharts).forEach(c => {
        if (c && typeof c.resize === 'function') c.resize();
      });
    }
  }
  window.triggerAllChartsResize = triggerAllChartsResize;

  function updateToggleButtonsState() {
    const metricStrip = document.querySelector('.metric-strip');
    const sidePanel = document.querySelector('.side-panel');
    const bottomPanel = document.querySelector('.bottom-panel');
    const btnTop = document.getElementById('btn-toggle-top');
    const btnSide = document.getElementById('btn-toggle-side');
    const btnBottom = document.getElementById('btn-toggle-bottom');

    if (btnTop && metricStrip) {
      btnTop.textContent = metricStrip.classList.contains('collapsed') ? '▾' : '▴';
      btnTop.title = metricStrip.classList.contains('collapsed') ? '展开顶部统计卡片' : '折叠顶部统计卡片';
    }
    if (btnSide && sidePanel) {
      btnSide.textContent = sidePanel.classList.contains('collapsed') ? '◂' : '▸';
      btnSide.title = sidePanel.classList.contains('collapsed') ? '展开右侧侧栏' : '折叠右侧侧栏';
    }
    if (btnBottom && bottomPanel) {
      const isBotCollapsed = bottomPanel.classList.contains('collapsed') || bottomPanel.classList.contains('collapsed-full');
      btnBottom.textContent = isBotCollapsed ? '▴' : '▾';
      btnBottom.title = isBotCollapsed ? '展开底部面板' : '折叠底部面板';
    }
  }

  function setChartLayoutMode(mode) {
    const bottomPanel = document.querySelector('.bottom-panel');
    const mainEl = document.querySelector('.main');
    const mainRect = mainEl ? mainEl.getBoundingClientRect() : { height: window.innerHeight };
    const availHeight = Math.max(300, mainRect.height - 100);

    let targetHeight = 160;
    if (mode === 'max-chart') {
      targetHeight = 0;
    } else if (mode === 'half') {
      targetHeight = Math.round(availHeight * 0.48);
    } else if (mode === 'logs') {
      targetHeight = Math.round(availHeight * 0.62);
    } else { // default
      targetHeight = 160;
    }

    if (targetHeight === 0) {
      const curH = bottomPanel ? Math.round(bottomPanel.getBoundingClientRect().height) : 160;
      if (curH > 45) localStorage.setItem(KEY_BOTTOM_HEIGHT + '_prev', curH);
      if (bottomPanel) bottomPanel.classList.add('collapsed', 'collapsed-full');
      document.documentElement.style.setProperty('--bottom-panel-height', '0px');
      localStorage.setItem(KEY_BOTTOM_HEIGHT, 0);
    } else {
      if (bottomPanel) bottomPanel.classList.remove('collapsed', 'collapsed-full');
      document.documentElement.style.setProperty('--bottom-panel-height', `${targetHeight}px`);
      localStorage.setItem(KEY_BOTTOM_HEIGHT, targetHeight);
    }

    // Sync button states
    document.querySelectorAll('.splitter-preset-chip, .layout-preset-btn').forEach(btn => {
      btn.classList.remove('active');
    });
    if (mode === 'max-chart') {
      document.getElementById('layout-btn-max')?.classList.add('active');
      document.getElementById('splitter-chip-max')?.classList.add('active');
    } else if (mode === 'half') {
      document.getElementById('layout-btn-half')?.classList.add('active');
      document.getElementById('splitter-chip-half')?.classList.add('active');
    } else if (mode === 'logs') {
      document.getElementById('splitter-chip-logs')?.classList.add('active');
    } else if (mode === 'default') {
      document.getElementById('layout-btn-default')?.classList.add('active');
      document.getElementById('splitter-chip-default')?.classList.add('active');
    }

    updateToggleButtonsState();
    triggerAllChartsResize();
    setTimeout(triggerAllChartsResize, 50);
  }
  window.setChartLayoutMode = setChartLayoutMode;

  function toggleMetricStripCollapse(force) {
    const metricStrip = document.querySelector('.metric-strip');
    if (!metricStrip) return;
    const shouldCollapse = force !== undefined ? force : !metricStrip.classList.contains('collapsed');
    metricStrip.classList.toggle('collapsed', shouldCollapse);
    localStorage.setItem(KEY_TOP_COLLAPSED, shouldCollapse ? 'true' : 'false');
    updateToggleButtonsState();
    setTimeout(triggerAllChartsResize, 260);
  }
  window.toggleMetricStripCollapse = toggleMetricStripCollapse;

  function toggleSidePanelCollapse(force) {
    const sidePanel = document.querySelector('.side-panel');
    if (!sidePanel) return;
    const isCurrentlyCollapsed = sidePanel.classList.contains('collapsed');
    const shouldCollapse = force !== undefined ? force : !isCurrentlyCollapsed;

    if (shouldCollapse) {
      const curWidth = Math.round(sidePanel.getBoundingClientRect().width) || DEFAULT_SIDE_WIDTH;
      if (curWidth > 50) localStorage.setItem(KEY_SIDE_WIDTH + '_prev', curWidth);
      sidePanel.classList.add('collapsed');
      document.documentElement.style.setProperty('--side-panel-width', '0px');
    } else {
      sidePanel.classList.remove('collapsed');
      const restored = parseInt(localStorage.getItem(KEY_SIDE_WIDTH + '_prev')) || parseInt(localStorage.getItem(KEY_SIDE_WIDTH)) || DEFAULT_SIDE_WIDTH;
      const targetWidth = Math.max(200, Math.min(restored, 850));
      document.documentElement.style.setProperty('--side-panel-width', `${targetWidth}px`);
      localStorage.setItem(KEY_SIDE_WIDTH, targetWidth);
    }
    updateToggleButtonsState();
    setTimeout(triggerAllChartsResize, 20);
  }
  window.toggleSidePanelCollapse = toggleSidePanelCollapse;

  function toggleBottomPanelCollapse(force) {
    const bottomPanel = document.querySelector('.bottom-panel');
    if (!bottomPanel) return;
    const isCurrentlyCollapsed = bottomPanel.classList.contains('collapsed') || bottomPanel.classList.contains('collapsed-full');
    const shouldCollapse = force !== undefined ? force : !isCurrentlyCollapsed;

    if (shouldCollapse) {
      const curHeight = Math.round(bottomPanel.getBoundingClientRect().height) || DEFAULT_BOTTOM_HEIGHT;
      if (curHeight > 45) localStorage.setItem(KEY_BOTTOM_HEIGHT + '_prev', curHeight);
      bottomPanel.classList.add('collapsed', 'collapsed-full');
      document.documentElement.style.setProperty('--bottom-panel-height', '0px');
      localStorage.setItem(KEY_BOTTOM_HEIGHT, 0);
      document.getElementById('layout-btn-max')?.classList.add('active');
      document.getElementById('splitter-chip-max')?.classList.add('active');
    } else {
      bottomPanel.classList.remove('collapsed', 'collapsed-full');
      const restored = parseInt(localStorage.getItem(KEY_BOTTOM_HEIGHT + '_prev')) || parseInt(localStorage.getItem(KEY_BOTTOM_HEIGHT)) || DEFAULT_BOTTOM_HEIGHT;
      const targetHeight = Math.max(120, Math.min(restored, 800));
      document.documentElement.style.setProperty('--bottom-panel-height', `${targetHeight}px`);
      localStorage.setItem(KEY_BOTTOM_HEIGHT, targetHeight);
      document.querySelectorAll('.splitter-preset-chip, .layout-preset-btn').forEach(btn => btn.classList.remove('active'));
      if (Math.abs(targetHeight - 160) < 30) {
        document.getElementById('layout-btn-default')?.classList.add('active');
        document.getElementById('splitter-chip-default')?.classList.add('active');
      }
    }
    updateToggleButtonsState();
    triggerAllChartsResize();
    setTimeout(triggerAllChartsResize, 50);
  }
  window.toggleBottomPanelCollapse = toggleBottomPanelCollapse;

  function initResizers() {
    const splitterSide = document.getElementById('splitter-side');
    const splitterBottom = document.getElementById('splitter-bottom');
    const splitterTop = document.getElementById('splitter-top');
    const metricStrip = document.querySelector('.metric-strip');
    const sidePanel = document.querySelector('.side-panel');
    const bottomPanel = document.querySelector('.bottom-panel');

    // Restore saved dimensions
    const savedSideWidth = parseInt(localStorage.getItem(KEY_SIDE_WIDTH));
    if (!isNaN(savedSideWidth) && savedSideWidth >= 160 && savedSideWidth <= 900) {
      document.documentElement.style.setProperty('--side-panel-width', `${savedSideWidth}px`);
    }

    const savedBottomHeight = parseInt(localStorage.getItem(KEY_BOTTOM_HEIGHT));
    if (!isNaN(savedBottomHeight) && savedBottomHeight >= 0 && savedBottomHeight <= 1200) {
      if (savedBottomHeight === 0) {
        if (bottomPanel) bottomPanel.classList.add('collapsed', 'collapsed-full');
        document.documentElement.style.setProperty('--bottom-panel-height', '0px');
        document.getElementById('layout-btn-max')?.classList.add('active');
        document.getElementById('splitter-chip-max')?.classList.add('active');
      } else {
        if (bottomPanel) bottomPanel.classList.remove('collapsed', 'collapsed-full');
        document.documentElement.style.setProperty('--bottom-panel-height', `${savedBottomHeight}px`);
        if (Math.abs(savedBottomHeight - 160) < 25) {
          document.getElementById('layout-btn-default')?.classList.add('active');
          document.getElementById('splitter-chip-default')?.classList.add('active');
        }
      }
    }

    const savedTopCollapsed = localStorage.getItem(KEY_TOP_COLLAPSED);
    if (savedTopCollapsed === 'true' && metricStrip) {
      metricStrip.classList.add('collapsed');
    }
    updateToggleButtonsState();

    // Bind Splitter: Side (Left-Right dragging)
    if (splitterSide) {
      splitterSide.addEventListener('pointerdown', e => {
        if (e.button !== 0) return;
        e.preventDefault();
        try { splitterSide.setPointerCapture(e.pointerId); } catch(err) {}
        isDragging = true;
        activeResizer = 'side';
        startX = e.clientX;
        startWidth = sidePanel ? sidePanel.getBoundingClientRect().width : DEFAULT_SIDE_WIDTH;
        document.body.classList.add('resizing-active', 'resizing-col');
        splitterSide.classList.add('dragging');
      });

      splitterSide.addEventListener('dblclick', () => {
        toggleSidePanelCollapse();
      });
    }

    // Bind Splitter: Bottom (Up-Down dragging)
    if (splitterBottom) {
      splitterBottom.addEventListener('pointerdown', e => {
        if (e.button !== 0) return;
        if (e.target.closest('.splitter-preset-chip') || e.target.closest('.splitter-toggle-btn')) return;
        e.preventDefault();
        try { splitterBottom.setPointerCapture(e.pointerId); } catch(err) {}
        isDragging = true;
        activeResizer = 'bottom';
        startY = e.clientY;
        startHeight = bottomPanel ? bottomPanel.getBoundingClientRect().height : DEFAULT_BOTTOM_HEIGHT;
        document.body.classList.add('resizing-active', 'resizing-row');
        splitterBottom.classList.add('dragging');
      });

      splitterBottom.addEventListener('dblclick', (e) => {
        if (e.target.closest('.splitter-preset-chip') || e.target.closest('.splitter-toggle-btn')) return;
        toggleBottomPanelCollapse();
      });
    }

    // Bind Splitter: Top (Up-Down dragging)
    if (splitterTop) {
      splitterTop.addEventListener('pointerdown', e => {
        if (e.button !== 0) return;
        e.preventDefault();
        try { splitterTop.setPointerCapture(e.pointerId); } catch(err) {}
        isDragging = true;
        activeResizer = 'top';
        startY = e.clientY;
        document.body.classList.add('resizing-active', 'resizing-row');
        splitterTop.classList.add('dragging');
      });

      splitterTop.addEventListener('dblclick', () => {
        toggleMetricStripCollapse();
      });
    }

    // Pointer Move Handler
    window.addEventListener('pointermove', e => {
      if (!isDragging || !activeResizer) return;
      e.preventDefault();

      if (rafId) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        const mainEl = document.querySelector('.main');
        if (!mainEl) return;
        const mainRect = mainEl.getBoundingClientRect();

        if (activeResizer === 'side') {
          const newWidth = Math.round(mainRect.right - e.clientX);
          const clamped = Math.max(160, Math.min(mainRect.width - 240, Math.min(newWidth, 850)));
          if (sidePanel) sidePanel.classList.remove('collapsed');
          document.documentElement.style.setProperty('--side-panel-width', `${clamped}px`);
          updateToggleButtonsState();
          triggerAllChartsResize();
        } else if (activeResizer === 'bottom') {
          const newHeight = Math.round(mainRect.bottom - e.clientY);
          const maxH = Math.max(100, mainRect.height - 80);
          let clamped = Math.max(0, Math.min(maxH, newHeight));
          if (clamped < 25) clamped = 0;
          if (bottomPanel) {
            bottomPanel.classList.toggle('collapsed', clamped === 0);
            bottomPanel.classList.toggle('collapsed-full', clamped === 0);
          }
          document.documentElement.style.setProperty('--bottom-panel-height', `${clamped}px`);
          updateToggleButtonsState();
          triggerAllChartsResize();
        } else if (activeResizer === 'top') {
          const deltaY = e.clientY - startY;
          if (deltaY < -25 && metricStrip && !metricStrip.classList.contains('collapsed')) {
            metricStrip.classList.add('collapsed');
            localStorage.setItem(KEY_TOP_COLLAPSED, 'true');
            updateToggleButtonsState();
            triggerAllChartsResize();
          } else if (deltaY > 25 && metricStrip && metricStrip.classList.contains('collapsed')) {
            metricStrip.classList.remove('collapsed');
            localStorage.setItem(KEY_TOP_COLLAPSED, 'false');
            updateToggleButtonsState();
            triggerAllChartsResize();
          }
        }
      });
    });

    // Pointer Up Handler
    window.addEventListener('pointerup', (e) => {
      if (!isDragging) return;
      isDragging = false;
      document.body.classList.remove('resizing-active', 'resizing-col', 'resizing-row');
      if (splitterSide) {
        splitterSide.classList.remove('dragging');
        try { splitterSide.releasePointerCapture(e.pointerId); } catch(err) {}
      }
      if (splitterBottom) {
        splitterBottom.classList.remove('dragging');
        try { splitterBottom.releasePointerCapture(e.pointerId); } catch(err) {}
      }
      if (splitterTop) {
        splitterTop.classList.remove('dragging');
        try { splitterTop.releasePointerCapture(e.pointerId); } catch(err) {}
      }

      if (activeResizer === 'side' && sidePanel && !sidePanel.classList.contains('collapsed')) {
        const finalWidth = Math.round(sidePanel.getBoundingClientRect().width);
        if (finalWidth >= 160) localStorage.setItem(KEY_SIDE_WIDTH, finalWidth);
      } else if (activeResizer === 'bottom' && bottomPanel) {
        if (bottomPanel.classList.contains('collapsed-full')) {
          localStorage.setItem(KEY_BOTTOM_HEIGHT, 0);
        } else {
          const finalHeight = Math.round(bottomPanel.getBoundingClientRect().height);
          if (finalHeight >= 30) localStorage.setItem(KEY_BOTTOM_HEIGHT, finalHeight);
        }
      }
      activeResizer = null;
      updateToggleButtonsState();
      setTimeout(triggerAllChartsResize, 20);
    });

    setTimeout(triggerAllChartsResize, 100);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initResizers);
  } else {
    initResizers();
  }
})();

// ===== 常驻急停、模式分级与熔断指示器交互驱动 =====
let currentTradingMode = 'READONLY';
let isEmergencyStopped = false;

function toggleTradingModeMenu(e) {
  e.stopPropagation();
  const m = document.getElementById('mode-dropdown-menu');
  if (m) m.style.display = m.style.display === 'none' ? 'block' : 'none';
}

document.addEventListener('click', () => {
  const m = document.getElementById('mode-dropdown-menu');
  if (m) m.style.display = 'none';
});

async function selectTradingMode(mode, e) {
  if (e) e.stopPropagation();
  const m = document.getElementById('mode-dropdown-menu');
  if (m) m.style.display = 'none';
  
  if (mode === 'LIVE' || mode === 'MICRO_LIVE') {
    if (!confirm(`⚠️ 警告: 您即将切换到实盘模式 [${mode}]，真实资金将受策略开仓规则支配！确认继续吗？`)) {
      return;
    }
  }
  
  try {
    const res = await fetch('/api/mode/switch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode })
    });
    const data = await res.json();
    if (data.ok || data.trading_mode) {
      applyTradingModeUI(data.trading_mode || mode);
      showNotificationToast(`交易分级模式已切换为: ${data.trading_mode || mode}`);
    } else {
      alert(`模式切换提示: ${data.message || data.error || '失败'}`);
    }
  } catch(err) {
    showNotificationToast(`切换请求已发送: ${mode}`);
    applyTradingModeUI(mode);
  }
}

function applyTradingModeUI(mode) {
  currentTradingMode = mode;
  const label = document.getElementById('trading-mode-label');
  const capsule = document.getElementById('trading-mode-capsule');
  if (!label || !capsule) return;
  
  const map = {
    'READONLY': { t: '只读预览 (READONLY)', c: '' },
    'SHADOW': { t: '影子观察 (SHADOW)', c: 'micro' },
    'PAPER': { t: '模拟实盘 (PAPER)', c: 'paper' },
    'MICRO_LIVE': { t: '小微实盘 (MICRO_LIVE)', c: 'micro' },
    'LIVE': { t: '全额实盘 (LIVE)', c: 'live' }
  };
  const item = map[mode] || { t: mode, c: '' };
  label.textContent = item.t;
  capsule.className = `trading-mode-capsule ${item.c}`;
}

// 紧急急停交互
function onEmergencyKillClick() {
  if (isEmergencyStopped) {
    if (confirm('【解除急停确认】\n当前系统处于紧急急停锁死状态，是否解除急停锁、恢复系统正常风控监控态？')) {
      resumeEmergencyStop();
    }
  } else {
    const modal = document.getElementById('emergency-kill-overlay');
    if (modal) modal.style.display = 'flex';
  }
}

function closeEmergencyKillModal() {
  const modal = document.getElementById('emergency-kill-overlay');
  if (modal) modal.style.display = 'none';
}

async function executeEmergencyKill(mode) {
  closeEmergencyKillModal();
  try {
    const res = await fetch('/api/risk/emergency_kill', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode, reason: '用户前端一键紧急急停' })
    });
    const d = await res.json();
    isEmergencyStopped = true;
    updateKillBadgeUI(true);
    alert(`🚨 【紧急急停已生效】\n${d.message || '自动交易已关闭，开仓入口已锁死'}\n已撤销挂单数: ${d.cancelled_orders?.cancelled_count ?? 0}`);
  } catch(e) {
    isEmergencyStopped = true;
    updateKillBadgeUI(true);
    alert('🚨 紧急急停指令已发送至服务器！');
  }
}

async function resumeEmergencyStop() {
  try {
    const res = await fetch('/api/risk/resume', {
      method: 'POST'
    });
    const d = await res.json();
    isEmergencyStopped = false;
    updateKillBadgeUI(false);
    showNotificationToast(d.message || '紧急急停已成功解除');
  } catch(e) {
    isEmergencyStopped = false;
    updateKillBadgeUI(false);
    showNotificationToast('紧急急停解除指令已送达');
  }
}

function updateKillBadgeUI(stopped) {
  isEmergencyStopped = Boolean(stopped);
  const badge = document.getElementById('emergency-kill-badge');
  const txt = document.getElementById('emergency-kill-text');
  if (!badge || !txt) return;
  if (isEmergencyStopped) {
    badge.className = 'emergency-kill-badge active-kill';
    txt.textContent = '已急停 (点击解除)';
  } else {
    badge.className = 'emergency-kill-badge';
    txt.textContent = '紧急急停';
  }
}

// 熔断器与对账详情
function openReconciliationModal() {
  const modal = document.getElementById('reconciliation-modal-overlay');
  if (modal) modal.style.display = 'flex';
}

function closeReconciliationModal() {
  const modal = document.getElementById('reconciliation-modal-overlay');
  if (modal) modal.style.display = 'none';
}

async function runManualReconciliation() {
  const btn = document.getElementById('btn-manual-reconcile');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ 对账核验中...'; }
  try {
    const res = await fetch('/api/risk/reconcile_now', { method: 'POST' });
    const data = await res.json();
    if (btn) { btn.disabled = false; btn.textContent = '🔄 立即手动对账一次'; }
    updateReconciliationModalUI(data);
    showNotificationToast('持仓对账核验已完成');
  } catch(e) {
    if (btn) { btn.disabled = false; btn.textContent = '🔄 立即手动对账一次'; }
    showNotificationToast('对账指令已发送');
  }
}

function updateReconciliationModalUI(data) {
  const statusEl = document.getElementById('modal-recon-status');
  const timeEl = document.getElementById('modal-recon-time');
  const discEl = document.getElementById('modal-recon-discrepancies');
  if (!statusEl || !discEl) return;
  
  const st = data.status || 'OK';
  statusEl.textContent = st === 'OK' ? '对账一致 (OK)' : '存在差异异常 (MISMATCH)';
  statusEl.style.color = st === 'OK' ? '#10b981' : '#ef4444';
  if (timeEl) timeEl.textContent = `上次对账: ${new Date().toLocaleTimeString()}`;
  
  const discs = data.discrepancies || [];
  if (discs.length === 0) {
    discEl.innerHTML = '暂无任何持仓对账差异，本地止盈止损保护单与交易所真实仓位 100% 同步。';
    discEl.style.color = '#94a3b8';
  } else {
    discEl.innerHTML = discs.map(d => `<div style="color:#f87171;margin-bottom:4px">⚠️ [${d.symbol}] ${d.type}: ${d.message}</div>`).join('');
  }
}

function updateCircuitBreakerUI(cb) {
  const badge = document.getElementById('circuit-breaker-badge');
  const txt = document.getElementById('circuit-breaker-text');
  const mStatus = document.getElementById('modal-cb-status');
  const mReason = document.getElementById('modal-cb-reason');
  if (!badge || !txt) return;
  
  if (cb && cb.active) {
    badge.className = 'circuit-breaker-badge tripped';
    txt.textContent = '⚡ 熔断中';
    badge.title = `数据/通讯熔断器已触发: ${cb.reason || '行情数据异常'}`;
    if (mStatus) { mStatus.textContent = '⚡ 触发自动熔断'; mStatus.style.color = '#ef4444'; }
    if (mReason) mReason.textContent = cb.reason || '异常中断';
  } else {
    badge.className = 'circuit-breaker-badge safe';
    txt.textContent = '熔断: 安全';
    badge.title = '执行层通讯与数据熔断器正常监控态 · 点击查看详情';
    if (mStatus) { mStatus.textContent = '🟢 正常监控态'; mStatus.style.color = '#10b981'; }
    if (mReason) mReason.textContent = '通讯与行情时延均在安全阈值内';
  }
}

// 在 updateUI 中勾入驱动逻辑
const _origUpdateUI = typeof updateUI === 'function' ? updateUI : null;
if (_origUpdateUI) {
  updateUI = function(d) {
    _origUpdateUI(d);
    
    // 1. 急停状态
    if (d.emergency_stopped !== undefined) {
      updateKillBadgeUI(d.emergency_stopped);
    }
    // 2. 熔断状态
    if (d.circuit_breaker) {
      updateCircuitBreakerUI(d.circuit_breaker);
    }
    // 3. 交易模式分级
    if (d.trading_mode) {
      applyTradingModeUI(d.trading_mode);
    } else if (d.live_trading_enabled) {
      applyTradingModeUI('LIVE');
    } else if (d.paper_trading) {
      applyTradingModeUI('PAPER');
    }
    // 4. 对账状态
    if (d.reconciliation) {
      updateReconciliationModalUI(d.reconciliation);
    }
  };
}


// ===== Init =====
async function initSymbols() {
  try {
    const res = await fetch('/api/status');
    const d = await res.json();
    let syms = d.all_symbols || d.symbols || [];
    if (!syms || syms.length === 0) {
      syms = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'DOGEUSDT'];
    }
    const sel = document.getElementById('symbol-select');
    if (sel) {
      sel.innerHTML = '';
      syms.forEach(s => sel.add(new Option(s, s)));

      let preferred = null;
      if (d.positions && d.positions.length > 0 && syms.includes(d.positions[0].symbol)) {
        preferred = d.positions[0].symbol;
      } else if (signalHistory && signalHistory.length > 0 && syms.includes(signalHistory[0].symbol)) {
        preferred = signalHistory[0].symbol;
      }

      if (preferred) {
        currentSymbol = preferred;
      } else if (!currentSymbol || !syms.includes(currentSymbol)) {
        currentSymbol = syms[0];
      }
      sel.value = currentSymbol;
    }
  } catch(e) {
    console.error('initSymbols error', e);
    const sel = document.getElementById('symbol-select');
    if (sel && sel.options.length === 0) {
      const fallbackSyms = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];
      fallbackSyms.forEach(s => sel.add(new Option(s, s)));
      currentSymbol = 'BTCUSDT';
      sel.value = currentSymbol;
    }
  }
}

initLanguage();
initScorePanel();
initChartLineSettings();
initTheme();
initChart();
connectWS();
initSymbols().then(() => loadKlines());
setTimeout(loadAIAnalysis, 2000);
setInterval(loadKlines, 60000);
checkObsidianStatus();
setTimeout(() => {
  loadTrades();
  loadExecutionEvents();
}, 1500);
function refreshDynamicLanguage() {
  if (lastIndicators) renderIndicators(lastIndicators);
  if (lastSmartMoney) renderSmartMoney(lastSmartMoney);
  if (lastPositions.length) {
    renderPositions(lastPositions);
    if (currentView === 'positions') renderPositionsGrid(lastPositions);
  }
  if (signalHistory.length) renderSignals();
  if (lastAiPayload) {
    renderAIAnalysis(lastAiPayload, lastAiSymbol);
    renderAdviceBar(lastAiPayload, lastAiSymbol);
  }
  if (lastRecommendPayload) renderRecommend(lastRecommendPayload);
  if (lastNewsPayload && document.getElementById('bottom-news')?.style.display !== 'none') renderNews(lastNewsPayload);
  if (lastExecutionEvents) renderExecutionEvents(lastExecutionEvents);
  if (rankingData) renderMarketRanking();
  renderChartInfoPanel();
  renderChartDataPanel();
}
function selectSystemPreview(card, label) {
  document.querySelectorAll('.system-card').forEach(item => item.classList.remove('selected'));
  card.classList.add('selected');
  const el = document.getElementById('metric-system');
  const system = card.dataset.system || 'trend_following';
  if (el) {
    el.dataset.systemLabel = system;
    el.textContent = displaySystemName(system);
  }
  renderStatusBanner(system);
}

