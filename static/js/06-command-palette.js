/* ==========================================================================
   Aether Quant Studio · 06-command-palette.js
   Ctrl+K Global Command Palette, Quick Symbol Jump & Keyboard Shortcuts
   ========================================================================== */

let cmdPaletteOpen = false;
let cmdSelectedIndex = 0;
let cmdFilteredActions = [];

function buildCommandCatalog(query) {
  const q = String(query || '').trim().toLowerCase();
  const actions = [];

  // 1. Dynamic symbol switching from loaded dropdown
  const symSelect = document.getElementById('symbol-select');
  if (symSelect && symSelect.options.length > 0) {
    const syms = Array.from(symSelect.options).map(o => o.value).filter(Boolean);
    const matchedSyms = q
      ? syms.filter(s => s.toLowerCase().includes(q)).slice(0, 8)
      : syms.slice(0, 5);
    matchedSyms.forEach(sym => {
      actions.push({
        group: '切换监控合约标的',
        icon: '🪙',
        title: `切换至 ${sym}`,
        sub: sym === currentSymbol ? '当前选中' : '加载实时K线与AI解盘',
        hint: 'Symbol',
        run: () => { if (typeof selectSymbolAndShow === 'function') selectSymbolAndShow(sym); }
      });
    });
  }

  // 2. Core terminal commands
  const coreCommands = [
    {
      group: '核心工作台与智能体',
      icon: '⚡',
      title: '打开策略自进化与历史回测工作台',
      sub: '70% 样本内搜索 + 30% 防过拟合检验',
      hint: 'Evolution',
      keywords: 'evolution backtest 回测 策略 自进化',
      run: () => { if (typeof openObsidianHub === 'function') openObsidianHub('evolution'); }
    },
    {
      group: '核心工作台与智能体',
      icon: '📓',
      title: '打开 Obsidian 量化知识中枢',
      sub: '双链策略规则、五维交易习惯雷达',
      hint: 'Vault',
      keywords: 'obsidian vault 知识库 习惯 复盘',
      run: () => { if (typeof openObsidianHub === 'function') openObsidianHub(); }
    },
    {
      group: '核心工作台与智能体',
      icon: '✍️',
      title: '打开币安广场 AI 博客创作工作室',
      sub: '一键生成 1280×720 封面并发布广场',
      hint: 'Studio',
      keywords: 'blog square 广场 博客 封面 研报',
      run: () => { if (typeof generateBlog === 'function') generateBlog(); }
    },
    {
      group: '核心工作台与智能体',
      icon: '⚙',
      title: '打开量化参数与 AI 投委会设置',
      sub: '风控预算、预设切换、Jev 门禁配置',
      hint: 'Settings',
      keywords: 'settings config 设置 参数 风控 jev ai',
      run: () => { if (typeof openSettings === 'function') openSettings(); }
    },
    {
      group: '图表与周期控制',
      icon: '⛶',
      title: '切换 K 线全屏沉浸看盘模式',
      sub: '快捷键 F / ESC 退出',
      hint: 'F',
      keywords: 'fullscreen 全屏 看盘 k线',
      run: () => { if (typeof toggleChartFullscreen === 'function') toggleChartFullscreen(); }
    },
    {
      group: '图表与周期控制',
      icon: '📈',
      title: '切换至资金权益曲线视图',
      sub: '账户净值走势追踪',
      hint: 'View',
      keywords: 'equity 权益 净值 资金曲线',
      run: () => { if (typeof switchView === 'function') switchView('equity'); }
    },
    {
      group: '图表与周期控制',
      icon: '🌐',
      title: '切换至多币动能热力视图',
      sub: '全市场多空强弱矩阵',
      hint: 'View',
      keywords: 'momentum 动能 热力 多币',
      run: () => { if (typeof switchView === 'function') switchView('momentum'); }
    },
    {
      group: '风控自检与战报导出',
      icon: '🛡️',
      title: '查看实盘仓位对账与熔断监控详情',
      sub: '核对本地状态与交易所真实持仓',
      hint: 'Risk',
      keywords: 'reconcile risk 对账 熔断 风控',
      run: () => { if (typeof openReconciliationModal === 'function') openReconciliationModal(); }
    },
    {
      group: '风控自检与战报导出',
      icon: '📊',
      title: '打开今日实盘交易战报与 AI 复盘',
      sub: '胜率统计与逐笔明细',
      hint: 'Report',
      keywords: 'daily report 战报 每日报告 复盘',
      run: () => { if (typeof showDailyReport === 'function') showDailyReport(); }
    },
    {
      group: '视觉主题与无障碍',
      icon: '☀️',
      title: '一键切换 明亮简约 / 深空暗黑 主题',
      sub: '快捷键 D',
      hint: 'D',
      keywords: 'theme light dark 主题 白天 暗黑 配色',
      run: () => { if (typeof toggleThemeLightDark === 'function') toggleThemeLightDark(); }
    },
    {
      group: '视觉主题与无障碍',
      icon: '🎨',
      title: '切换 红绿标准 / 蓝橙色弱友好 模式',
      sub: 'WCAG 无障碍视觉支持',
      hint: 'a11y',
      keywords: 'colorblind a11y 色盲 色弱 蓝橙 红绿',
      run: () => { if (typeof toggleColorBlindMode === 'function') toggleColorBlindMode(); }
    }
  ];

  // 3. Quick timeframe switching
  ['1m', '5m', '15m', '1h', '4h', '1d'].forEach(iv => {
    coreCommands.push({
      group: '图表与周期控制',
      icon: '⏱️',
      title: `切换 K 线周期至 ${iv}`,
      sub: '同步刷新主图与技术指标',
      hint: iv,
      keywords: `timeframe interval 周期 ${iv}`,
      run: () => { if (typeof selectChartInterval === 'function') selectChartInterval(iv); }
    });
  });

  coreCommands.forEach(cmd => {
    if (!q) {
      actions.push(cmd);
    } else {
      const hay = `${cmd.title} ${cmd.sub} ${cmd.keywords || ''} ${cmd.group}`.toLowerCase();
      if (hay.includes(q)) actions.push(cmd);
    }
  });

  return actions;
}

function renderCommandPaletteList() {
  const container = document.getElementById('cmd-palette-results');
  const input = document.getElementById('cmd-palette-input');
  if (!container) return;

  cmdFilteredActions = buildCommandCatalog(input ? input.value : '');
  if (cmdSelectedIndex >= cmdFilteredActions.length) cmdSelectedIndex = 0;

  if (cmdFilteredActions.length === 0) {
    container.innerHTML = '<div class="empty-state" style="padding:28px 12px">未找到匹配的指令或合约标的</div>';
    return;
  }

  let html = '';
  let lastGroup = '';
  cmdFilteredActions.forEach((item, idx) => {
    if (item.group !== lastGroup) {
      lastGroup = item.group;
      html += `<div class="cmd-group-label">${lastGroup}</div>`;
    }
    const selClass = idx === cmdSelectedIndex ? ' selected' : '';
    html += `
      <button type="button" class="cmd-item${selClass}" data-cmd-idx="${idx}" onclick="executeCommandPaletteItem(${idx})">
        <span class="cmd-item-left">
          <span class="cmd-item-icon">${item.icon}</span>
          <span class="cmd-item-title">${item.title}</span>
          <span class="cmd-item-sub">${item.sub || ''}</span>
        </span>
        <span class="cmd-item-hint">${item.hint || '↵'}</span>
      </button>
    `;
  });
  container.innerHTML = html;

  const activeEl = container.querySelector('.cmd-item.selected');
  if (activeEl) {
    try { activeEl.scrollIntoView({ block: 'nearest' }); } catch (_) {}
  }
}

function openCommandPalette() {
  const overlay = document.getElementById('cmd-palette-overlay');
  const input = document.getElementById('cmd-palette-input');
  if (!overlay) return;
  cmdPaletteOpen = true;
  cmdSelectedIndex = 0;
  overlay.classList.add('open');
  if (input) {
    input.value = '';
    setTimeout(() => input.focus(), 10);
  }
  renderCommandPaletteList();
}

function closeCommandPalette() {
  const overlay = document.getElementById('cmd-palette-overlay');
  if (!overlay) return;
  cmdPaletteOpen = false;
  overlay.classList.remove('open');
}

function toggleCommandPalette() {
  if (cmdPaletteOpen) closeCommandPalette();
  else openCommandPalette();
}

function executeCommandPaletteItem(index) {
  const item = cmdFilteredActions[index];
  closeCommandPalette();
  if (item && typeof item.run === 'function') {
    item.run();
  }
}

function onCommandPaletteOverlayClick(event) {
  if (event.target && event.target.id === 'cmd-palette-overlay') {
    closeCommandPalette();
  }
}

document.addEventListener('keydown', (e) => {
  // Ctrl+K or Cmd+K toggles Command Palette globally
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    toggleCommandPalette();
    return;
  }

  if (cmdPaletteOpen) {
    if (e.key === 'Escape') {
      e.preventDefault();
      closeCommandPalette();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (cmdFilteredActions.length > 0) {
        cmdSelectedIndex = (cmdSelectedIndex + 1) % cmdFilteredActions.length;
        renderCommandPaletteList();
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (cmdFilteredActions.length > 0) {
        cmdSelectedIndex = (cmdSelectedIndex - 1 + cmdFilteredActions.length) % cmdFilteredActions.length;
        renderCommandPaletteList();
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      executeCommandPaletteItem(cmdSelectedIndex);
    }
    return;
  }

  // Single-key productivity shortcuts when not typing in an input/textarea/select
  const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
  const isEditable = tag === 'input' || tag === 'textarea' || tag === 'select' || (e.target && e.target.isContentEditable);
  if (isEditable || e.ctrlKey || e.metaKey || e.altKey) return;

  if (e.key === '?') {
    e.preventDefault();
    openCommandPalette();
  } else if (e.key.toLowerCase() === 'd') {
    if (typeof toggleThemeLightDark === 'function') toggleThemeLightDark();
  } else if (e.key.toLowerCase() === 'f') {
    if (typeof toggleChartFullscreen === 'function') toggleChartFullscreen();
  }
});
