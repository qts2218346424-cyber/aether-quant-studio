// ===== Blog and Daily Report =====
const BLOG_I18N = {
  'zh-CN': {
    studio: '\u535a\u5ba2\u589e\u957f\u5de5\u4f5c\u53f0', subtitle: '\u6570\u636e\u9a71\u52a8 \u00b7 \u4e00\u952e\u53d1\u5e03\u7d20\u6750',
    platform: '\u53d1\u5e03\u5e73\u53f0', tone: '\u5185\u5bb9\u8bed\u6c14', length: '\u6587\u7ae0\u957f\u5ea6', coverStyle: '\u5c01\u9762\u98ce\u683c',
    general: '\u901a\u7528\u957f\u6587', xhs: '\u5c0f\u7ea2\u4e66 / \u77ed\u5185\u5bb9', x: 'Twitter / X', telegram: 'Telegram / \u793e\u7fa4',
    analytical: '\u4e13\u4e1a\u5206\u6790', conversational: '\u8f7b\u91cf\u89e3\u8bfb', contrarian: '\u89c2\u70b9\u9c9c\u660e',
    concise: '\u7cbe\u7b80', standard: '\u6807\u51c6', deep: '\u6df1\u5ea6', terminal: '\u7ec8\u7aef\u84dd\u56fe', heatmap: '\u70ed\u529b\u96f7\u8fbe', minimal: '\u6781\u7b80\u6570\u636e',
    title: '\u6807\u9898', hook: '\u5f00\u5934\u94a9\u5b50', article: '\u6b63\u6587', tags: '\u6807\u7b7e', cta: '\u4e92\u52a8\u5f15\u5bfc', cover: '\u884c\u60c5\u5c01\u9762', prompt: '\u56fe\u7247\u63d0\u793a\u8bcd',
    copy: '\u590d\u5236\u5168\u6587', copyTitle: '\u590d\u5236\u6807\u9898', copyTags: '\u590d\u5236\u6807\u7b7e', download: '\u4e0b\u8f7d PNG \u5c01\u9762', squarePublish: '\u53d1\u5e03\u5230 Binance Square', squarePublishing: '\u6b63\u5728\u4e0a\u4f20\u5c01\u9762\u5e76\u53d1\u5e03\u2026', squarePublished: '\u5df2\u53d1\u5e03', squareSubmittedNoLink: '\u5df2\u63d0\u4ea4\uff0c\u6682\u65e0\u94fe\u63a5', squarePublishFailed: '\u53d1\u5e03\u5931\u8d25\uff1a', autoPublish: '\u5b9a\u65f6\u53d1\u5e03', autoPublishOn: '\u6bcf 30 \u5206\u949f\u81ea\u52a8\u53d1\u5e03', autoPublishOff: '\u5df2\u6682\u505c', nextAutoPublish: '\u4e0b\u6b21\u53d1\u5e03', close: '\u5173\u95ed', refreshed: '\u5df2\u66f4\u65b0',
    tip: '\u53ea\u8bfb\u751f\u6210\uff1a\u5185\u5bb9\u6765\u81ea\u5f53\u524d\u63a8\u8350\u6570\u636e\uff0c\u4e0d\u4f1a\u521b\u5efa\u8ba2\u5355\uff0c\u4e5f\u4e0d\u4f1a\u4fee\u6539\u5f53\u524d\u6301\u4ed3\u3002',
    insight: '\u5e02\u573a\u89c2\u5bdf', risk: '\u98ce\u9669\u63d0\u793a', follow: '\u4f60\u66f4\u5173\u6ce8\u54ea\u4e00\u4e2a\u4fe1\u53f7\uff1f\u6b22\u8fce\u7559\u8a00\u4ea4\u6d41\u3002', noData: '\u6682\u65e0\u63a8\u8350\u6570\u636e\uff0c\u8bf7\u5148\u5237\u65b0\u626b\u63cf'
  },
  'en-US': {
    studio: 'Blog Growth Studio', subtitle: 'Data-led \u00b7 Ready-to-publish assets', platform: 'Platform', tone: 'Tone', length: 'Length', coverStyle: 'Cover style',
    general: 'Long-form', xhs: 'Xiaohongshu / Short', x: 'Twitter / X', telegram: 'Telegram / Community', analytical: 'Analytical', conversational: 'Conversational', contrarian: 'Strong point of view',
    concise: 'Concise', standard: 'Standard', deep: 'Deep dive', terminal: 'Terminal Blueprint', heatmap: 'Heatmap Radar', minimal: 'Minimal Data', title: 'Title', hook: 'Opening hook', article: 'Article', tags: 'Tags', cta: 'Engagement CTA', cover: 'Market cover', prompt: 'Image prompt',
    copy: 'Copy all', copyTitle: 'Copy title', copyTags: 'Copy tags', download: 'Download PNG cover', squarePublish: 'Publish to Binance Square', squarePublishing: 'Uploading cover and publishing…', squarePublished: 'Published', squareSubmittedNoLink: 'Submitted, link unavailable', autoPublish: 'Scheduled publishing', autoPublishOn: 'Auto-publish every 30 minutes', autoPublishOff: 'Paused', nextAutoPublish: 'Next publish', squarePublishFailed: 'Publish failed: ', close: 'Close', refreshed: 'Updated', tip: 'Read-only generation: uses current recommendation data only. No orders or position changes.', insight: 'Market watch', risk: 'Risk note', follow: 'Which signal are you watching? Share your view.', noData: 'No recommendation data. Refresh the scan first.'
  }
};
let blogStudioState = null;
function blogDict() { return BLOG_I18N[currentLanguage] || BLOG_I18N['zh-CN']; }
function blogNum(value, digits=2) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString(currentLanguage, { maximumFractionDigits: digits }) : '--';
}
function toCashtag(sym) {
  if (!sym) return '';
  let s = String(sym).trim().toUpperCase();
  if (s.endsWith('USDT') && s.length > 4) s = s.slice(0, -4);
  return s.startsWith('$') ? s : `$${s}`;
}
function blogDirection(item) { return String(item.side_en || item.side || '').toUpperCase() === 'LONG' ? 'LONG' : 'SHORT'; }
function blogOptions() {
  return {
    platform: document.getElementById('blog-platform')?.value || 'general',
    tone: document.getElementById('blog-tone')?.value || 'analytical',
    length: document.getElementById('blog-length')?.value || 'standard',
    coverStyle: document.getElementById('blog-cover-style')?.value || 'terminal',
    sentiment: document.getElementById('blog-sentiment')?.value || 'auto'
  };
}
function syncBlogSentimentBadge(direction) {
  const badge = document.getElementById('blog-sentiment-badge');
  const badgeText = document.getElementById('blog-sentiment-badge-text');
  if (!badge || !badgeText) return;
  const isLong = direction === 'LONG';
  if (isLong) {
    badge.style.background = 'rgba(16,185,129,.12)';
    badge.style.borderColor = 'rgba(16,185,129,.35)';
    badge.style.color = '#10b981';
    badgeText.innerHTML = '🟢【当前观点：看涨 · 做多】';
  } else {
    badge.style.background = 'rgba(239,68,68,.12)';
    badge.style.borderColor = 'rgba(239,68,68,.35)';
    badge.style.color = '#ef4444';
    badgeText.innerHTML = '🔴【当前观点：看跌 · 做空】';
  }
}
function onBlogSentimentChange() {
  updateBlogStudio(true);
}
function buildBlogContent(items, options={}) {
  const d = blogDict(), opt = { platform:'general', tone:'analytical', length:'standard', coverStyle:'terminal', sentiment:'auto', ...options };
  const zh = currentLanguage === 'zh-CN';
  const top = items[0] || {}, longs = items.filter(it => blogDirection(it) === 'LONG').length, shorts = items.length - longs;
  const avgScore = items.reduce((sum, it) => sum + Number(it.score || 0), 0) / Math.max(items.length, 1);
  const avgChange = items.reduce((sum, it) => sum + Number(it.change_24h ?? it.change_24h_pct ?? 0), 0) / Math.max(items.length, 1);
  const watchCount = Math.min(3, items.length);
  const symbols = items.slice(0, 3).map(it => toCashtag(it.symbol)).filter(Boolean).join(' · ') || (zh ? '$BTC' : '$BTC');
  const rawDirection = blogDirection(top);
  let direction = rawDirection;
  if (opt.sentiment === 'BULLISH') direction = 'LONG';
  else if (opt.sentiment === 'BEARISH') direction = 'SHORT';

  const topCash = toCashtag(top.symbol) || '$BTC';
  const cleanTop = top.symbol ? (top.symbol.endsWith('USDT') && top.symbol.length > 4 ? top.symbol.slice(0, -4) : top.symbol) : '';
  const lead = direction === 'LONG' ? (zh ? '多头信号在集中' : 'Long signals are clustering') : (zh ? '空头压力在累积' : 'Short pressure is building');
  const modeName = { general: zh ? '深度长文' : 'Long-form', xhs: zh ? '小红书短内容' : 'Short-form', x: 'X thread', telegram: zh ? '社群播报' : 'Community brief', binance_square: zh ? '币安广场专栏' : 'Binance Square' }[opt.platform] || 'Long-form';
  const toneMarker = opt.tone === 'conversational'
    ? (zh ? '说句实在话｜' : 'Quick take | ')
    : opt.tone === 'contrarian'
      ? (zh ? '先别急着下定论｜' : 'Counter-view | ')
      : '';
  const title = opt.platform === 'binance_square'
    ? (zh ? `🚨 ${toneMarker}盯了 ${topCash} 好久，这波${direction === 'LONG' ? '多头突破' : '承压回落'}？关键位置我先盯紧` : `🚨 ${toneMarker}${lead}: ${topCash} key levels to watch`)
    : opt.platform === 'xhs'
    ? (zh ? `📌 ${toneMarker}${symbols}：${direction === 'LONG' ? '偏多' : '偏空'}信号，3个点说清楚` : `${toneMarker}${symbols}: ${direction} signal in 3 data points`)
    : opt.platform === 'x'
      ? `${toneMarker}${lead} | ${symbols}: ${watchCount} data points`
      : opt.platform === 'telegram'
        ? (zh ? `【${toneMarker}行情播报】${symbols}：${direction === 'LONG' ? '偏多' : '偏空'}信号更新` : `[${toneMarker}Market brief] ${symbols}: ${direction} update`)
        : (zh ? `${toneMarker}${lead}：${symbols} 的下一段行情，先看这 ${watchCount} 个位置` : `${toneMarker}${lead}: ${watchCount} data points to watch next on ${symbols}`);
  const overview = zh
    ? `今天扫出来的标的中，有 ${longs} 个偏多、${shorts} 个偏空，24H 平均变动 ${avgChange >= 0 ? '+' : ''}${blogNum(avgChange)}%。说实话，这种盘面分化很正常，不能盲目一锅端，我个人更倾向于多看少动、等待闭合K线给出确认。`
    : `${items.length} candidates scanned: ${longs} long, ${shorts} short, 24h average move ${avgChange >= 0 ? '+' : ''}${blogNum(avgChange)}%. Realistically, diverging conditions call for patience and candle confirmation.`;
  const toneHook = opt.tone === 'conversational'
    ? (zh ? `先说结论：这轮行情不是让人无脑追的，我把 ${symbols} 目前最关键的多空防守线列出来，大家看看跟你们的思路合不合。` : `Bottom line: avoid chasing blindly; here are the key defensive levels on ${symbols}.`)
    : opt.tone === 'contrarian'
      ? (zh ? `盘面表面上是这个方向，但我更警惕的是主力借机做诱多/诱空清扫。${symbols} 的这轮信号能不能成，先看下面这两个防守位。` : `Surface bias looks clear, but watch for liquidity sweeps before committing to ${symbols}.`)
      : (zh ? `说实话，这段走势我也犹豫过。下面把我复核的盘面数据、第一防守位和止损逻辑摆出来，供大家参考。` : `Here is a candid read on ${symbols}, covering momentum, levels and clear invalidation.`);
  const rows = items.map((it, index) => {
    const side = blogDirection(it), change = Number(it.change_24h ?? it.change_24h_pct ?? 0);
    const itCash = toCashtag(it.symbol);
    const factors = (it.factors || []).slice(0, 5).join(' / ') || it.reason || (zh ? '等待更多确认' : 'Waiting for confirmation');
    const levels = [it.support ? `${zh ? '支撑' : 'S'} ${blogNum(it.support, 6)}` : '', it.resistance ? `${zh ? '压力' : 'R'} ${blogNum(it.resistance, 6)}` : ''].filter(Boolean).join(' · ');
    if (opt.platform === 'xhs') return `${side === 'LONG' ? '🟢' : '🔴'} ${itCash}｜${side === 'LONG' ? '偏多' : '偏空'}｜评分 ${blogNum(it.score)}｜24H ${change >= 0 ? '+' : ''}${blogNum(change)}%
看点：${factors}${levels ? `
关键位：${levels}` : ''}`;
    if (opt.platform === 'x') return `${index + 1}/ ${itCash} ${side} · score ${blogNum(it.score)} · 24H ${change >= 0 ? '+' : ''}${blogNum(change)}% · ${factors}`;
    if (zh) return `${index + 1}. **${itCash}** · ${side === 'LONG' ? '偏多 ▲' : '偏空 ▼'}
现价 ${blogNum(it.price, 6)} ｜评分 ${blogNum(it.score)} ｜ATR波动 ${blogNum(it.atr_pct)}% ｜24H ${change >= 0 ? '+' : ''}${blogNum(change)}%
技术看点：${factors}${levels ? `
参考区间：${levels}` : ''}`;
    return `${index + 1}) ${itCash} · ${side}
Price ${blogNum(it.price, 6)} | Score ${blogNum(it.score)} | ATR ${blogNum(it.atr_pct)}% | 24H ${change >= 0 ? '+' : ''}${blogNum(change)}%
Evidence: ${factors}${levels ? `
Key levels: ${levels}` : ''}`;
  });
  const validation = opt.tone === 'contrarian'
    ? (zh ? '我的防守思路：先等收盘K线确认，一旦跌破支撑或站上压力，立刻承认自己判断错误并离场，绝不硬抗。' : 'My defense: wait for candle close. If key level breaks, exit promptly rather than averaging down.')
    : (zh ? '执行前先看两件事：一是收盘K线是否站稳，二是成交量有没有配合放量。如果跌破防守点位，原设想直接失效，绝不加仓死扛。' : 'Two checks before executing: closed candle confirmation and volume backing. Invalidate immediately if key level fails.');
  const levels = zh ? `关键支撑 ${blogNum(top.support, 6)} ｜关键压力 ${blogNum(top.resistance, 6)} ｜止损防守 ${blogNum(top.sl, 6)} ｜止盈目标 ${blogNum(top.tp1, 6)}` : `Support ${blogNum(top.support, 6)} | Resistance ${blogNum(top.resistance, 6)} | Stop Loss ${blogNum(top.sl, 6)} | Take Profit ${blogNum(top.tp1, 6)}`;
  const risk = zh ? '老生常谈的一句话：行情瞬息万变，这里只是基于数据的个人思考，绝不构成投资建议。务必严格控制仓位与单笔最大亏损。' : 'Risk reminder: Market conditions change quickly. This is personal observation, not financial advice. Strict position sizing is essential.';
  const cta = opt.platform === 'xhs' ? (zh ? '你今天手上有哪些持仓？评论区交流一下！' : 'Which coin are you watching? Share your read in the comments.') : opt.platform === 'x' ? (zh ? '顺势还是等回踩？说说你的思路。' : 'Follow the move or wait for a pullback?') : opt.platform === 'telegram' ? (zh ? '大家今天怎么看？欢迎在群里讨论。' : 'What is your view today? Join the discussion.') : opt.tone === 'contrarian' ? (zh ? '你觉得这里是真突破，还是主力在诱多诱空？' : 'Is this a trend start or a trap?') : (zh ? '你今天最盯哪个币？欢迎在评论区聊聊你的逻辑。' : d.follow);
  const commonRisk = `${validation}
${levels}
${risk}`;
  let body;
  if (opt.platform === 'binance_square') {
    const sideZh = direction === 'LONG' ? (zh ? '偏多 · 看涨 🟢' : 'LONG 🟢') : (zh ? '偏空 · 看跌 🔴' : 'SHORT 🔴');
    const sentimentBadge = direction === 'LONG' ? '🟢【看涨 · 做多】' : '🔴【看跌 · 做空】';
    const actionCta = direction === 'LONG' ? `做多 ${topCash} 🚀` : `做空 ${topCash} 👇`;
    body = [
      sentimentBadge,
      toneHook,
      `📊 ${overview}`,
      `🧭 ${zh ? '我的实盘计划（清晰明了，绝不含糊）：' : 'My Execution Plan:'}
• ${zh ? '核心标的' : 'Target'}：${topCash}（${sideZh}）
• ${zh ? '关键价位' : 'Key Levels'}：${zh ? '入场参考' : 'Entry'} ${blogNum(top.price, 6)} ｜ ${zh ? '关键支撑' : 'Support'} ${blogNum(top.support, 6)} ｜ ${zh ? '关键阻力' : 'Resistance'} ${blogNum(top.resistance, 6)}
• ${zh ? '止损防守' : 'Stop Loss'}：${blogNum(top.sl, 6)}（${zh ? '破位立刻止损，绝不扛单' : 'cut immediately if broken'}）
• ${zh ? '止盈目标' : 'Take Profit'}：${blogNum(top.tp1, 6)}（${zh ? '达到目标分批落袋' : 'take profit staged'}）

${actionCta}`,
      `⚠️ ${risk}`,
      `💬 ${cta}`
    ].join('\n\n');
  } else if (opt.platform === 'x') {
    const xBlocks = [toneHook, overview, rows.join('\n\n')];
    if (opt.length !== 'concise') xBlocks.push(`🧭 ${zh ? '我的操作计划' : 'Execution plan'}
${levels}
${validation}`);
    else xBlocks.push(commonRisk);
    xBlocks.push(cta);
    body = xBlocks.join('\n\n');
  } else if (opt.length === 'concise') {
    body = [toneHook, overview, rows.join('\n\n'), commonRisk, cta].join('\n\n');
  } else if (opt.platform === 'xhs') {
    body = [toneHook, `📊 ${zh ? '盘面速览' : 'Data snapshot'}
${overview}`, rows.join('\n\n'), `✅ ${zh ? '我的防守逻辑' : 'How to validate'}
${commonRisk}`, `💬 ${cta}`].join('\n\n');
  } else if (opt.platform === 'telegram') {
    body = [`【${modeName}】`, toneHook, `📊 ${d.insight}
${overview}`, `🎯 ${zh ? '信号拆解' : 'Signal breakdown'}
${rows.join('\n\n')}`, `🧭 ${zh ? '验证与风险' : 'Validation and risk'}
${commonRisk}`, `💬 ${zh ? '互动' : 'Discussion'}
${cta}`].join('\n\n');
  } else {
    body = [toneHook, `📊 ${zh ? '今日盘面感受' : d.insight}
${overview}`, `🎯 ${zh ? '我重点关注的标的' : 'Signal breakdown'}
${rows.join('\n\n')}`, `🧭 ${zh ? '我的操作与防守逻辑' : 'Validation path'}
${validation}`, `📍 ${zh ? '关键价位与防守线' : 'Key levels and execution frame'}
${levels}
${zh ? '实盘纪律：分批建仓、低倍杠杆、先定止损再进场。' : 'Use staged sizing, modest leverage and predefined invalidation.'}`, `💬 ${zh ? '抛个问题给大家' : d.cta}
${cta}`, `⚠️ ${zh ? '交易纪律提醒' : d.risk}
${risk}`].join('\n\n');
  }
  // 严格限制标签数量 <= 5（币安广场上限5个，包含 #看涨 或 #看跌）
  const baseTags = zh
    ? ['#币安广场', ...(cleanTop ? [`#${cleanTop}`] : []), direction === 'LONG' ? '#看涨' : '#看跌', direction === 'LONG' ? '#做多' : '#做空', '#合约交易']
    : ['#BinanceSquare', ...(cleanTop ? [`#${cleanTop}`] : []), direction === 'LONG' ? '#Bullish' : '#Bearish', '#Futures'];
  const tags = baseTags.slice(0, 5);
  const prompt = zh ? `为${modeName}制作 ${opt.coverStyle === 'heatmap' ? '市场热力雷达' : opt.coverStyle === 'minimal' ? '极简数据卡片' : '深色终端信息图'}，突出 ${symbols}、${direction}、评分 ${blogNum(top.score)}，16:9` : `Create a ${modeName} 16:9 cover highlighting ${symbols}, ${direction} and score ${blogNum(top.score)}.`;
  return { title, hook: toneHook, body, tags: tags.join(' '), prompt, cta, avgScore, avgChange, longs, shorts, modeName, direction, sentiment: direction === 'LONG' ? 'BULLISH' : 'BEARISH' };
}
function buildBlogText(items, options={}) { const content = buildBlogContent(items, options); return [content.title, content.body, content.tags].join('\n\n'); }
function updateBlogTargetSummary(top, direction) {
  const symEl = document.getElementById('blog-summary-sym');
  const priceEl = document.getElementById('blog-summary-price');
  const sideEl = document.getElementById('blog-summary-side');
  const supEl = document.getElementById('blog-summary-sup');
  const resEl = document.getElementById('blog-summary-res');
  const slEl = document.getElementById('blog-summary-sl');
  const tpEl = document.getElementById('blog-summary-tp');
  if (!symEl || !top) return;
  const sym = top.symbol || 'BTCUSDT';
  const price = Number(top.price || 0);
  const pStr = price >= 10 ? `$${price.toFixed(2)}` : `$${price.toFixed(4)}`;
  const isLong = direction === 'LONG';
  const sup = Number(top.support || (isLong ? price * 0.98 : price * 1.02));
  const res = Number(top.resistance || (isLong ? price * 1.03 : price * 0.97));
  const sl = Number(top.sl || (isLong ? price * 0.975 : price * 1.025));
  const tp = Number(top.tp1 || (isLong ? price * 1.05 : price * 0.95));

  symEl.textContent = sym;
  if (priceEl) priceEl.textContent = pStr;
  if (sideEl) {
    sideEl.textContent = isLong ? '🟢 看涨 · 多' : '🔴 看跌 · 空';
    sideEl.style.color = isLong ? '#00f59b' : '#ff4d6d';
  }
  if (supEl) supEl.textContent = price >= 10 ? `$${sup.toFixed(2)}` : `$${sup.toFixed(4)}`;
  if (resEl) resEl.textContent = price >= 10 ? `$${res.toFixed(2)}` : `$${res.toFixed(4)}`;
  if (slEl) slEl.textContent = price >= 10 ? `$${sl.toFixed(2)}` : `$${sl.toFixed(4)}`;
  if (tpEl) tpEl.textContent = price >= 10 ? `$${tp.toFixed(2)}` : `$${tp.toFixed(4)}`;
}

function updateBlogStudio(force=false) {
  if (!blogStudioState) return;
  const content = buildBlogContent(blogStudioState.items, blogOptions()); blogStudioState.content = content;
  const fields = { title:'blog-title', hook:'blog-hook', body:'blog-ta', tags:'blog-tags', prompt:'blog-prompt' };
  Object.entries(fields).forEach(([key, id]) => { const el = document.getElementById(id); if (el && (force || key === 'prompt' || !el.dataset.edited)) el.value = content[key]; });
  const chips = document.getElementById('blog-metrics');
  if (chips) { const zh = currentLanguage === 'zh-CN'; chips.innerHTML = `<span class="blog-chip accent">${blogDict().insight}</span><span class="blog-chip">${content.longs} ${zh ? '\u591a\u5934' : 'LONG'}</span><span class="blog-chip">${content.shorts} ${zh ? '\u7a7a\u5934' : 'SHORT'}</span><span class="blog-chip">${zh ? '\u5e73\u5747\u8bc4\u5206' : 'AVG'} ${blogNum(content.avgScore)}</span>`; }
  syncBlogSentimentBadge(content.direction);
  updateBlogTargetSummary(blogStudioState.items[0], content.direction);
  drawBlogCover(blogStudioState.items, blogOptions(), content);
  const topSym = blogStudioState?.items?.[0]?.symbol;
  if (topSym && typeof loadKlineChartForSymbol === 'function') {
    loadKlineChartForSymbol(topSym);
  }
}
function drawBlogCover(items, options={}, content=buildBlogContent(items, options)) {
  const canvas = document.getElementById('blog-cover-canvas'); if (!canvas) return;
  const ctx = canvas.getContext('2d'); if (!ctx) return;
  const W = 1600, H = 900; canvas.width = W; canvas.height = H;
  const zh = currentLanguage === 'zh-CN';
  const font = '"Microsoft YaHei", "PingFang SC", Arial, sans-serif';
  let top = items[0] || {};
  if (content && items && items.length > 1) {
    const textToCheck = `${content.title || ''} ${content.tags || ''} ${(content.body || '').slice(0, 300)}`.toUpperCase();
    const matched = items.find(it => {
      const s = String(it.symbol || '').toUpperCase().replace('USDT', '');
      return s && (textToCheck.includes(`$${s}`) || textToCheck.includes(` ${s} `) || textToCheck.includes(`${s}USDT`));
    });
    if (matched) top = matched;
  }
  const isLong = content?.direction ? (content.direction === 'LONG') : (blogDirection(top) === 'LONG');
  const accent = isLong ? '#00f59b' : '#ff3b69';
  const accentDim = isLong ? '#007a4d' : '#991b35';
  const accentBg = isLong ? 'rgba(0,245,155,.12)' : 'rgba(255,59,105,.12)';

  const rawSym = String(top.symbol || 'BTCUSDT').toUpperCase();
  const cleanSym = rawSym.endsWith('USDT') && rawSym.length > 4 ? rawSym.slice(0, -4) : rawSym;
  const cashSym = `$${cleanSym}`;

  const price = Number(top.price || 64500.0);
  const change = Number(top.change_24h ?? top.change_24h_pct ?? 3.8);
  const score = Math.round(Number(top.score || 82));
  const atr = Number(top.atr_pct || 2.3);
  const sup = Number(top.support || (isLong ? price * 0.98 : price * 1.02));
  const res = Number(top.resistance || (isLong ? price * 1.03 : price * 0.97));
  const sl = Number(top.sl || (isLong ? price * 0.975 : price * 1.025));
  const tp = Number(top.tp1 || (isLong ? price * 1.05 : price * 0.95));

  const risk = Math.abs(price - sl);
  const reward = Math.abs(tp - price);
  const rr = risk > 0 ? (reward / risk).toFixed(1) : '2.2';

  const refCode = (window.blogPromotion?.referral_code || 'BINANCE_VIP');
  const discount = (window.blogPromotion?.fee_discount_pct || 20);

  // 1. 深色极客量化渐变背景
  const bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, '#070e1c');
  bg.addColorStop(0.5, '#0c172d');
  bg.addColorStop(1, '#081122');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  // 氛围光效与轻微网格
  const glow = (x, y, radius, color) => {
    const g = ctx.createRadialGradient(x, y, 0, x, y, radius);
    g.addColorStop(0, color);
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.fillRect(x - radius, y - radius, radius * 2, radius * 2);
  };
  glow(1200, 200, 500, 'rgba(13,36,72,.5)');
  glow(200, 750, 450, isLong ? 'rgba(0,245,155,.08)' : 'rgba(255,59,105,.08)');

  ctx.strokeStyle = 'rgba(17,34,59,.6)';
  ctx.lineWidth = 1;
  for (let x = 60; x < W; x += 80) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
  for (let y = 40; y < H; y += 60) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }

  const roundRect = (x, y, w, h, r, fill, stroke, strokeW = 1) => {
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, r);
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = strokeW; ctx.stroke(); }
  };
  const text = (value, x, y, size, color, weight='400', align='left') => {
    ctx.font = `${weight} ${size}px ${font}`;
    ctx.fillStyle = color;
    ctx.textAlign = align;
    ctx.fillText(String(value ?? ''), x, y);
  };

  // 2. 顶部胶囊导航栏
  const headY = 36;
  roundRect(64, headY, 450, 44, 22, '#0f223d', '#22426d', 2);
  text('★ BINANCE QUANT STUDIO · 量化研报', 257, headY + 28, 16, '#ffcf56', '700', 'center');

  const badgeW = 330;
  roundRect(W - 64 - badgeW, headY, badgeW, 44, 22, accentBg, accent, 2);
  ctx.beginPath();
  ctx.arc(W - 64 - badgeW + 28, headY + 22, 7, 0, Math.PI * 2);
  ctx.fillStyle = accent;
  ctx.fill();
  const dirText = isLong ? '▲ 看涨 · 做多 BULLISH' : '▼ 看跌 · 做空 BEARISH';
  text(dirText, W - 64 - badgeW / 2 + 10, headY + 28, 17, accent, '700', 'center');

  // 3. 左侧核心标的与挂单 HUD 卡片 (x: 64 to 614, y: 104 to 810)
  const leftX = 64, leftW = 550;
  roundRect(leftX, 104, leftW, 706, 20, '#0a172b', '#1d3759', 2);

  text(cashSym, leftX + 32, 175, 52, '#ffffff', '800');
  roundRect(leftX + 320, 144, 190, 40, 10, '#12253f', '#2b4e78');
  text(`${rawSym} 永续合约`, leftX + 415, 169, 14, '#8ba8c8', '700', 'center');

  const pStr = price >= 10 ? `$${price.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})}` : `$${price.toFixed(4)}`;
  const chgStr = `${change >= 0 ? '+' : ''}${change.toFixed(2)}% 24H`;
  text(pStr, leftX + 32, 235, 36, accent, '700');
  ctx.font = `700 36px ${font}`;
  const pLen = ctx.measureText(pStr).width;
  text(chgStr, leftX + 32 + pLen + 18, 235, 22, change >= 0 ? '#00f59b' : '#ff3b69', '700');

  // 三个量化微指标 (量化评分、ATR、聪明钱)
  const metrics = [
    ['量化多因子评分', `${score} / 100`, accent],
    ['ATR波动率指数', `${atr.toFixed(2)}%`, '#77b8ff'],
    ['聪明钱主力博弈', isLong ? '多头共振 · 大单吸筹' : '承压诱多 · 主力出逃', '#ffcf56'],
  ];
  metrics.forEach(([lbl, val, col], i) => {
    const cardY = 270 + i * 72;
    roundRect(leftX + 32, cardY, leftW - 64, 60, 12, '#0e1f37', '#1c3558');
    text(lbl, leftX + 52, cardY + 36, 15, '#8ba8c8', '400', 'left');
    text(val, leftX + leftW - 52, cardY + 36, 17, col, '700', 'right');
  });

  // 实盘挂单与止盈止损 HUD
  const hudY = 505;
  roundRect(leftX + 32, hudY, leftW - 64, 280, 16, '#0b223a', accentDim, 2);
  text('◆ 实盘交易策略与点位执行 HUD', leftX + 52, hudY + 34, 16, '#ffffff', '700');

  const hudRows = [
    ['入场参考区间', price >= 10 ? `${(price*0.995).toFixed(2)} - ${(price*1.005).toFixed(2)}` : `${(price*0.995).toFixed(4)} - ${(price*1.005).toFixed(4)}`, '#ffffff'],
    ['关键止损防守', price >= 10 ? `${sl.toFixed(2)} (破位坚决离场)` : `${sl.toFixed(4)} (坚决止损)`, '#ff4d6d'],
    ['止盈目标价位', price >= 10 ? `TP1 ${tp.toFixed(2)} | TP2 ${(tp*1.03).toFixed(2)}` : `TP1 ${tp.toFixed(4)}`, '#00f59b'],
    ['策略盈亏比(R:R)', `${rr}:1 优质非对称博弈`, '#ffcf56'],
  ];
  hudRows.forEach(([hlbl, hval, hcol], i) => {
    const rowY = hudY + 80 + i * 48;
    text(hlbl, leftX + 52, rowY, 14, '#8ba8c8');
    text(hval, leftX + leftW - 52, rowY, 15, hcol, '700', 'right');
  });

  // 4. 右侧 K 线走势图与均线 (x: 640 to 1536)
  const rightX = 640, rightW = W - rightX - 64;
  roundRect(rightX, 104, rightW, 706, 20, '#0a1628', '#1d3759', 2);

  text(`● ${rawSym} 近30周期 K线走势 & 关键支撑阻力带`, rightX + 32, 142, 18, '#c8ddf0', '700');
  text('15M / 1H 周期', rightX + rightW - 32, 142, 14, '#77b8ff', '700', 'right');

  const chartX = rightX + 80, chartY = 260, chartW = rightW - 120, chartH = 460;
  const closesRaw = (top.recent_closes || []).filter(x => x != null);
  let closes = closesRaw.slice(-30).map(Number);
  if (closes.length < 8) {
    let baseP = price;
    closes = [baseP];
    const drift = isLong ? 0.003 : -0.003;
    for (let i = 0; i < 29; i++) {
      baseP = baseP * (1 + drift + (Math.sin(i * 1.7) * 0.015));
      closes.push(baseP);
    }
  }

  const n = closes.length;
  const candles = closes.map((c, i) => {
    const prev = i > 0 ? closes[i - 1] : c;
    const o = prev;
    const h = Math.max(o, c) * (1 + Math.abs(Math.sin(i * 1.5)) * 0.012);
    const l = Math.min(o, c) * (1 - Math.abs(Math.cos(i * 2.1)) * 0.012);
    return [o, h, l, c];
  });

  const allP = [...candles.flat(), sup, res, sl, tp];
  const pMin = Math.min(...allP);
  const pMax = Math.max(...allP);
  const pRange = (pMax - pMin) || (price * 0.02);
  const toCy = (val) => Math.round(chartY + (pMax - val) / pRange * chartH);

  // Horizontal Grid Lines
  for (let gi = 0; gi < 5; gi++) {
    const gy = chartY + Math.round(gi * chartH / 4);
    ctx.strokeStyle = '#152b48';
    ctx.beginPath(); ctx.moveTo(chartX, gy); ctx.lineTo(chartX + chartW, gy); ctx.stroke();
    const gridP = pMax - (pMax - pMin) * gi / 4;
    text(price >= 10 ? gridP.toFixed(2) : gridP.toFixed(4), chartX - 12, gy + 4, 12, '#6985a6', '400', 'right');
  }

  // Resistance Line (Red)
  const resY = toCy(res);
  ctx.strokeStyle = '#ff4d6d'; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(chartX, resY); ctx.lineTo(chartX + chartW, resY); ctx.stroke();
  roundRect(chartX + chartW - 140, resY - 20, 130, 20, 4, '#3b0f1a');
  text(`阻力位 ${price >= 10 ? res.toFixed(2) : res.toFixed(4)}`, chartX + chartW - 75, resY - 6, 12, '#ff4d6d', '700', 'center');

  // Support Line (Green)
  const supY = toCy(sup);
  ctx.strokeStyle = '#00f59b'; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(chartX, supY); ctx.lineTo(chartX + chartW, supY); ctx.stroke();
  roundRect(chartX + chartW - 140, supY + 4, 130, 20, 4, '#072b1d');
  text(`支撑位 ${price >= 10 ? sup.toFixed(2) : sup.toFixed(4)}`, chartX + chartW - 75, supY + 18, 12, '#00f59b', '700', 'center');

  // Draw Candles
  const cw = Math.max(6, Math.floor(chartW / n - 4));
  const cgap = Math.max(2, Math.floor((chartW - cw * n) / Math.max(1, n - 1)));
  const emaPoints = [];

  candles.forEach(([co, ch, cl, cc], i) => {
    const cx = chartX + i * (cw + cgap) + Math.floor(cw / 2);
    const isBull = cc >= co;
    const bCol = isBull ? '#00f59b' : '#ff3b69';
    const wCol = isBull ? '#00b875' : '#cc2f54';

    // Wick
    ctx.strokeStyle = wCol; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(cx, toCy(ch)); ctx.lineTo(cx, toCy(cl)); ctx.stroke();

    // Body
    const yTop = Math.min(toCy(co), toCy(cc));
    const yBot = Math.max(toCy(co), toCy(cc));
    ctx.fillStyle = bCol;
    ctx.fillRect(cx - Math.floor(cw / 2), yTop, cw, Math.max(2, yBot - yTop));

    emaPoints.push([cx, toCy((co + cc) / 2)]);
  });

  // EMA Curve
  if (emaPoints.length > 1) {
    ctx.strokeStyle = '#ffcf56'; ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(emaPoints[0][0], emaPoints[0][1]);
    for (let i = 1; i < emaPoints.length; i++) {
      ctx.lineTo(emaPoints[i][0], emaPoints[i][1]);
    }
    ctx.stroke();
  }

  // Legend at bottom of chart
  const legY = 770;
  text('── EMA 动态均线', chartX, legY, 13, '#ffcf56', '700');
  text('── 核心阻力', chartX + 160, legY, 13, '#ff4d6d', '700');
  text('── 核心支撑', chartX + 280, legY, 13, '#00f59b', '700');
  text('阳线 ▲ / 阴线 ▼', rightX + rightW - 32, legY, 13, '#8ba8c8', '700', 'right');

  // 5. 底部品牌与互动水印
  const footY = 862;
  const brandCta = '★ 币安广场量化专栏 ｜ 严控风险 拒绝扛单 ｜ 紧跟实盘动态';
  text(brandCta, 64, footY, 16, '#ffcf56', '700');
  text('BINANCE SQUARE QUANT STUDIO · 实盘透明', W - 64, footY, 15, '#6985a6', '700', 'right');
}
function downloadBlogCover() { const canvas = document.getElementById('blog-cover-canvas'); if (!canvas) return; const link = document.createElement('a'); link.download = `quant-market-cover-${new Date().toISOString().slice(0,10)}.png`; link.href = canvas.toDataURL('image/png'); link.click(); }
function fallbackCopy(text) { const helper = document.createElement('textarea'); helper.value = text; helper.style.position = 'fixed'; helper.style.opacity = '0'; document.body.appendChild(helper); helper.select(); document.execCommand('copy'); helper.remove(); }
function blogCopy(text, button) { const done = () => { if (!button) return; const original = button.textContent; button.textContent = blogDict().refreshed; setTimeout(() => { button.textContent = original; }, 1200); }; if (navigator.clipboard?.writeText) navigator.clipboard.writeText(text).then(done).catch(() => { fallbackCopy(text); done(); }); else { fallbackCopy(text); done(); } }
function copyBlog(e) { const title = document.getElementById('blog-title')?.value || ''; const body = document.getElementById('blog-ta')?.value || ''; const tags = document.getElementById('blog-tags')?.value || ''; blogCopy([title, body, tags].filter(Boolean).join('\n\n'), e?.target); }
function copyBlogTitle(e) { blogCopy(document.getElementById('blog-title')?.value || '', e?.target); }
function copyBlogTags(e) { blogCopy(document.getElementById('blog-tags')?.value || '', e?.target); }
async function loadBlogPromotion() {
  try {
    const res = await window['fetch']('/api/blog/promotion');
    const data = await res.json();
    if (data.ok && data.promotion) {
      window.blogPromotion = data.promotion;
      const refCodeEl = document.getElementById('blog-ref-code');
      const refUrlEl = document.getElementById('blog-ref-url');
      const copyUrlEl = document.getElementById('blog-copy-url');
      const discEl = document.getElementById('blog-ref-discount');
      if (refCodeEl) refCodeEl.value = data.promotion.referral_code || '';
      if (refUrlEl) refUrlEl.value = data.promotion.referral_url || '';
      if (copyUrlEl) copyUrlEl.value = data.promotion.copy_trading_url || '';
      if (discEl) discEl.value = data.promotion.fee_discount_pct ?? 20;
    }
  } catch (e) {
    console.warn('loadBlogPromotion failed:', e);
  }
}
async function loadBlogImageConfig() {
  try {
    const res = await window['fetch']('/api/blog/image_config');
    const data = await res.json();
    if (data.ok && data.config) {
      window.blogImageConfig = data.config;
    }
  } catch (e) {
    console.warn('loadBlogImageConfig failed:', e);
  }
}
async function saveBlogPromotion() {
  const referral_code = document.getElementById('blog-ref-code')?.value?.trim() || '';
  const referral_url = document.getElementById('blog-ref-url')?.value?.trim() || '';
  const copy_trading_url = document.getElementById('blog-copy-url')?.value?.trim() || '';
  const fee_discount_pct = Number(document.getElementById('blog-ref-discount')?.value) || 20;
  window.blogPromotion = {
    enabled: true,
    referral_code,
    referral_url,
    copy_trading_url,
    fee_discount_pct,
  };
  try {
    await window['fetch']('/api/blog/promotion', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(window.blogPromotion),
    });
  } catch (e) {
    console.warn('saveBlogPromotion failed:', e);
  }
  drawBlogCover();
}
function insertPromotionToBody() {
  const ta = document.getElementById('blog-ta');
  if (!ta) return;
  const promo = window.blogPromotion || {};
  const code = promo.referral_code || 'BINANCE_VIP';
  const disc = promo.fee_discount_pct || 20;
  const snippet = `\n\n🎁 专属福利与实盘跟单：\n想要同步我的实盘同款量化信号？在币安开户或主页填写专属邀请码【${code}】，立享最高 ${disc}% 交易手续费永久返还！\n🔗 专属返佣与跟单：点击个人主页置顶链接或输入邀请码即可一键绑定。`;
  if (!ta.value.includes(code)) {
    ta.value = ta.value.trim() + snippet;
    ta.dataset.edited = '1';
  }
}
async function loadSquareAutoStatus() {
  const checkbox = document.getElementById('blog-auto-publish'), state = document.getElementById('blog-auto-state'), next = document.getElementById('blog-auto-next');
  if (!checkbox || !state) return;
  try {
    const response = await window['fetch']('/api/square/auto/status');
    const data = await response.json();
    checkbox.checked = !!data.enabled;
    state.textContent = data.enabled ? blogDict().autoPublishOn : blogDict().autoPublishOff;
    state.className = `blog-auto-state ${data.enabled ? 'on' : 'off'}`;
    if (next) next.textContent = data.next_run_at ? `${blogDict().nextAutoPublish}: ${data.next_run_at}` : '';
  } catch (error) {
    state.textContent = currentLanguage === 'zh-CN' ? '状态读取失败' : 'Status unavailable';
    state.className = 'blog-auto-state off';
  }
}
async function toggleSquareAutoPublish(e) {
  const enabled = !!e?.target?.checked, state = document.getElementById('blog-auto-state'), next = document.getElementById('blog-auto-next');
  try {
    const response = await window['fetch']('/api/square/auto', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({enabled, interval_sec:1800}) });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
    if (state) { state.textContent = enabled ? blogDict().autoPublishOn : blogDict().autoPublishOff; state.className = `blog-auto-state ${enabled ? 'on' : 'off'}`; }
    if (next) next.textContent = data.next_run_at ? `${blogDict().nextAutoPublish}: ${data.next_run_at}` : '';
  } catch (error) {
    if (e?.target) e.target.checked = !enabled;
    if (state) { state.textContent = error.message; state.className = 'blog-auto-state off'; }
  }
}

async function loadSquareDailyAnalytics() {
  try {
    const res = await fetch('/api/square/analytics/daily');
    const data = await res.json();
    if (!data.ok) return;

    const elCount = document.getElementById('sq-today-count');
    if (elCount) elCount.textContent = `${data.today_posts_count || 0} 篇`;

    const elReview = document.getElementById('sq-review-state');
    if (elReview) {
      if (data.has_daily_review_today) {
        elReview.textContent = '✅ 今日已复盘';
        elReview.style.color = '#10b981';
      } else {
        elReview.textContent = '⏳ 今日待复盘';
        elReview.style.color = '#f59e0b';
      }
    }

    const elCooling = document.getElementById('sq-cooling-symbols');
    if (elCooling) {
      const coolingList = data.recent_symbols || [];
      if (coolingList.length > 0) {
        elCooling.innerHTML = coolingList.slice(0, 3).map(s => `<span style="background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.3);color:#f87171;padding:1px 4px;border-radius:3px;margin-right:3px">$${s.replace('USDT','')}</span>`).join('');
      } else {
        elCooling.textContent = '无（所有币种均可轮换）';
        elCooling.style.color = '#10b981';
      }
    }
  } catch (e) {
    console.warn('loadSquareDailyAnalytics error:', e);
  }
}

async function generateDailyReviewDraft() {
  const btn = document.getElementById('btn-gen-daily-review');
  const origText = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ 正在研判全天多空格局并生成复盘...';
  }
  try {
    const res = await fetch('/api/square/daily_review/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ publish_now: false })
    });
    const result = await res.json();
    if (!result.ok || !result.data) {
      throw new Error(result.error || '生成失败');
    }
    const d = result.data;
    const elTitle = document.getElementById('blog-title');
    const elBody = document.getElementById('blog-ta');
    const elTags = document.getElementById('blog-tags');
    const elSentiment = document.getElementById('blog-sentiment');

    if (elTitle) { elTitle.value = d.title || ''; elTitle.dataset.edited = '1'; }
    if (elBody) { elBody.value = d.body || ''; elBody.dataset.edited = '1'; }
    if (elTags) { elTags.value = d.tags || ''; elTags.dataset.edited = '1'; }
    if (elSentiment && d.sentiment) {
      elSentiment.value = d.sentiment;
      if (typeof onBlogSentimentChange === 'function') onBlogSentimentChange();
    }
    if (result.items && blogStudioState) {
      blogStudioState.items = result.items;
      updateBlogStudio(true);
    }
    const status = document.getElementById('blog-publish-status');
    if (status) {
      status.className = 'blog-publish-status success';
      status.textContent = '✅ 已生成【今日大盘全景复盘与战绩追踪】作品，可在右侧预览并一键发布！';
    }
  } catch (err) {
    alert('生成每日复盘失败: ' + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origText;
    }
  }
}

async function showSquarePostsModal() {
  let modal = document.getElementById('sq-posts-history-modal');
  if (modal) modal.remove();

  modal = document.createElement('div');
  modal.id = 'sq-posts-history-modal';
  modal.className = 'blog-overlay';
  modal.style.zIndex = '9999';
  modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

  modal.innerHTML = `
    <div class="blog-modal" style="width:780px;max-width:95vw;max-height:85vh;display:flex;flex-direction:column;background:#0b1120;border:1px solid rgba(124,58,237,.4);box-shadow:0 20px 40px rgba(0,0,0,.7)">
      <div class="blog-head" style="border-bottom:1px solid rgba(255,255,255,.08);padding:12px 16px">
        <div>
          <span class="t" style="color:#c084fc">📜 自媒体已发布作品库与运营复盘流水</span>
          <span class="sub" style="color:var(--text-2);margin-left:8px">记录每篇作品的标的、方向、直达链接与表现</span>
        </div>
        <span class="x" onclick="document.getElementById('sq-posts-history-modal').remove()" style="cursor:pointer">✕</span>
      </div>
      <div id="sq-posts-table-wrap" style="flex:1;overflow-y:auto;padding:12px 16px;font-size:12px">
        <div style="text-align:center;padding:30px;color:var(--text-2)">⏳ 正在加载自媒体作品数据...</div>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  try {
    const res = await fetch('/api/square/posts/history?limit=50');
    const data = await res.json();
    const wrap = document.getElementById('sq-posts-table-wrap');
    if (!wrap) return;
    const posts = data.posts || [];
    if (posts.length === 0) {
      wrap.innerHTML = `<div style="text-align:center;padding:40px;color:var(--text-2)">暂无已发布作品记录</div>`;
      return;
    }
    wrap.innerHTML = `
      <table style="width:100%;border-collapse:collapse;text-align:left">
        <thead>
          <tr style="border-bottom:1px solid rgba(255,255,255,.1);color:var(--text-2);font-size:11px">
            <th style="padding:6px 8px">发布时间</th>
            <th style="padding:6px 8px">核心标的</th>
            <th style="padding:6px 8px">情绪方向</th>
            <th style="padding:6px 8px">类型</th>
            <th style="padding:6px 8px">摘要 / 标题</th>
            <th style="padding:6px 8px;text-align:right">操作</th>
          </tr>
        </thead>
        <tbody>
          ${posts.map(p => {
            const isBull = p.sentiment === 'BULLISH';
            const sentBadge = isBull ? '<span style="color:#10b981;font-weight:700">🟢 看涨</span>' : '<span style="color:#ef4444;font-weight:700">🔴 看跌</span>';
            const typeZh = p.post_type === 'daily_review' ? '<span style="color:#f59e0b;font-weight:600">📊 大盘复盘</span>' : '<span style="color:#38bdf8">⚡ 盘面研报</span>';
            const timeStr = (p.published_at || '').replace('T', ' ').slice(0, 16);
            const linkBtn = p.link ? `<a href="${p.link}" target="_blank" rel="noopener" style="display:inline-block;padding:2px 8px;background:rgba(59,130,246,.2);border:1px solid rgba(59,130,246,.4);color:#93c5fd;border-radius:4px;text-decoration:none;font-size:11px;font-weight:600">直达广场 ↗</a>` : '<span style="color:var(--text-2)">-</span>';
            return `
              <tr style="border-bottom:1px solid rgba(255,255,255,.05)">
                <td style="padding:8px;color:var(--text-2);font-family:monospace;white-space:nowrap">${timeStr}</td>
                <td style="padding:8px;font-weight:700;color:#ffcf56">${p.symbol || '--'}</td>
                <td style="padding:8px">${sentBadge}</td>
                <td style="padding:8px">${typeZh}</td>
                <td style="padding:8px;max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${p.summary || p.title || ''}">${p.title || p.summary || '--'}</td>
                <td style="padding:8px;text-align:right">${linkBtn}</td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    `;
  } catch (err) {
    const wrap = document.getElementById('sq-posts-table-wrap');
    if (wrap) wrap.innerHTML = `<div style="color:#ef4444;padding:20px;text-align:center">加载失败: ${err.message}</div>`;
  }
}


function renderBlogGallery() {
  const container = document.getElementById('blog-gallery-list');
  const counter = document.getElementById('blog-gallery-counter');
  if (!container) return;
  const list = window.blogGalleryImages || [];
  if (counter) {
    counter.textContent = `已选 ${list.length} / 4 张`;
    counter.style.color = list.length >= 4 ? '#ef4444' : '#a78bfa';
  }
  if (list.length === 0) {
    container.innerHTML = `<div id="blog-gallery-empty" style="font-size:10px;color:var(--text-2);padding:8px 0;width:100%;text-align:center">💡 可点击上方按钮选择本地截图/分析图，或直接在正文输入框按 Ctrl+V 粘贴图片！</div>`;
    return;
  }
  container.innerHTML = list.map((item, idx) => `
    <div style="position:relative;flex-shrink:0;width:110px;background:#0d1829;border:1px solid #2563eb;border-radius:6px;overflow:hidden;padding:4px;text-align:center">
      <img src="${item.data_url}" style="width:100%;height:60px;object-fit:cover;border-radius:4px" />
      <div style="font-size:9px;color:var(--text-1);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin:2px 0">${item.name || `附图 ${idx+1}`}</div>
      <div style="display:flex;justify-content:center;gap:3px;margin-top:2px">
        <button type="button" onclick="insertGalleryImageToBody(${idx})" style="font-size:9px;background:rgba(59,130,246,.2);border:1px solid rgba(59,130,246,.4);color:#93c5fd;border-radius:3px;padding:1px 4px;cursor:pointer" title="插入到光标处">📌插正文</button>
        <button type="button" onclick="setGalleryImageAsCover(${idx})" style="font-size:9px;background:rgba(245,158,11,.2);border:1px solid rgba(245,158,11,.4);color:#fbbf24;border-radius:3px;padding:1px 4px;cursor:pointer" title="设为16:9封面">🎨设封面</button>
        <button type="button" onclick="removeGalleryImage(${idx})" style="font-size:9px;background:rgba(239,68,68,.2);border:1px solid rgba(239,68,68,.4);color:#fca5a5;border-radius:3px;padding:1px 4px;cursor:pointer" title="移除附图">🗑️</button>
      </div>
    </div>
  `).join('');
}

function addBlogImageToGallery(dataUrl, name = '附图', source = 'local') {
  if (!window.blogGalleryImages) window.blogGalleryImages = [];
  if (window.blogGalleryImages.length >= 4) {
    alert('⚠️ 币安广场单篇文章/动态最多支持附加 4 张图片！');
    return;
  }
  if (window.blogGalleryImages.some(it => it.data_url === dataUrl)) {
    return;
  }
  window.blogGalleryImages.push({ data_url: dataUrl, name, source });
  renderBlogGallery();
}

async function handleBlogLocalImageUpload(e) {
  const files = e?.target?.files;
  if (!files || !files.length) return;
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    if (window.blogGalleryImages && window.blogGalleryImages.length >= 4) {
      alert('⚠️ 附图已达到上限 4 张！');
      break;
    }
    const reader = new FileReader();
    reader.onload = async (ev) => {
      const dataUrl = ev.target.result;
      try {
        const res = await fetch('/api/blog/upload_image', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ data_url: dataUrl, filename: file.name })
        });
        const d = await res.json();
        if (d.ok) {
          addBlogImageToGallery(d.data_url, file.name.slice(0, 15), 'upload');
        } else {
          alert('图片上传失败: ' + (d.error || '格式错误'));
        }
      } catch (err) {
        addBlogImageToGallery(dataUrl, file.name.slice(0, 15), 'upload');
      }
    };
    reader.readAsDataURL(file);
  }
  if (e?.target) e.target.value = '';
}

function insertGalleryImageToBody(idx) {
  const item = (window.blogGalleryImages || [])[idx];
  if (!item) return;
  const ta = document.getElementById('blog-ta');
  if (!ta) return;
  const insertText = `\n\n![${item.name}](${item.data_url})\n\n`;
  ta.value = (ta.value || '').trim() + insertText;
  ta.dataset.edited = '1';
  alert(`✅ 已在正文中插入【${item.name}】附图标注！`);
}

function setGalleryImageAsCover(idx) {
  const item = (window.blogGalleryImages || [])[idx];
  if (!item) return;
  const canvas = document.getElementById('blog-cover-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const img = new Image();
  img.onload = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    alert(`🎨 已成功将【${item.name}】设为文章 16:9 封面大图！`);
  };
  img.src = item.data_url;
}

function removeGalleryImage(idx) {
  if (!window.blogGalleryImages) return;
  window.blogGalleryImages.splice(idx, 1);
  renderBlogGallery();
}

function initBlogPasteHandler() {
  const ta = document.getElementById('blog-ta');
  if (!ta || ta.dataset.pasteBound) return;
  ta.dataset.pasteBound = '1';
  ta.addEventListener('paste', (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf('image') !== -1) {
        const blob = items[i].getAsFile();
        const reader = new FileReader();
        reader.onload = async (ev) => {
          const dataUrl = ev.target.result;
          addBlogImageToGallery(dataUrl, `截图_${new Date().toLocaleTimeString().replace(/:/g, '')}`, 'paste');
        };
        reader.readAsDataURL(blob);
      }
    }
  });
}

function onBlogPublishModeChange() {
  const mode = document.getElementById('blog-publish-mode')?.value || 'article';
  const titleInput = document.getElementById('blog-title');
  if (mode === 'post') {
    if (titleInput) {
      titleInput.placeholder = '⚡ 动态模式（无需标题，将在广场信息流直显 1~4 张附图，曝光更高）';
      titleInput.style.opacity = '0.75';
    }
  } else {
    if (titleInput) {
      titleInput.placeholder = '输入引人入胜的研报大标题...';
      titleInput.style.opacity = '1';
    }
  }
}

async function publishBlog(e) {
  const button = e?.target, status = document.getElementById('blog-publish-status');
  const publishMode = document.getElementById('blog-publish-mode')?.value || 'article';
  const titleVal = document.getElementById('blog-title')?.value?.trim() || '';
  const title = publishMode === 'post' ? '' : titleVal;
  let body = document.getElementById('blog-ta')?.value?.trim() || '';

  // 1. 收集所有附加图片
  const images = [];
  (window.blogGalleryImages || []).forEach(img => {
    if (img.data_url && !images.includes(img.data_url)) {
      images.push(img.data_url);
    }
  });

  // 如果正文中直接粘贴了 base64 图片，提取入 images
  const b64Matches = body.match(/data:image\/[a-zA-Z]+;base64,[^)]+/g) || [];
  b64Matches.forEach(b64 => {
    if (!images.includes(b64) && images.length < 4) {
      images.push(b64);
    }
  });

  // 2. 规范正文文本：替换超长 base64 字符串为干净图注，消除标题 ## 标记
  body = body.replace(/!\[([^\]]*)\]\(data:image\/[^)]+\)/g, (m, c) => c ? `【${c}】` : '【走势分析图】');
  body = body.replace(/!\[([^\]]*)\]\([^)]+\)/g, (m, c) => c ? `【${c}】` : '');
  body = body.replace(/^#{1,6}\s+/gm, '').trim();

  let tags = document.getElementById('blog-tags')?.value?.trim() || '';
  // 自动限制标签数量最多 5 个（币安广场 API 上限）
  if (tags) {
    const rawList = tags.replace(/[,，]/g, ' ').split(/\s+/).filter(Boolean);
    if (rawList.length > 5) {
      tags = rawList.slice(0, 5).join(' ');
      const tagsEl = document.getElementById('blog-tags');
      if (tagsEl) tagsEl.value = tags;
    }
  }

  const cover = document.getElementById('blog-cover-canvas')?.toDataURL('image/png') || '';
  const sentimentVal = document.getElementById('blog-sentiment')?.value;
  const autoSentiment = (blogStudioState?.content?.direction === 'LONG' || !blogStudioState?.content?.direction) ? 'BULLISH' : 'BEARISH';
  const sentiment = (sentimentVal && sentimentVal !== 'auto') ? sentimentVal : autoSentiment;

  let currentSymbol = blogStudioState?.content?.symbol || (blogStudioState?.items?.[0]?.symbol) || '';
  if (!currentSymbol) {
    const symM = body.match(/\$([A-Za-z0-9]+)/);
    if (symM) currentSymbol = symM[1].toUpperCase();
  }

  if (publishMode === 'post') {
    const cleanSym = currentSymbol ? currentSymbol.replace(/USDT$/i, '') : '';
    const sentBadge = sentiment === 'BULLISH' ? '🟢【看涨 · 做多 BULLISH】' : '🔴【看跌 · 做空 BEARISH】';
    if (!body.startsWith('🟢') && !body.startsWith('🔴') && !body.slice(0, 40).includes('看涨') && !body.slice(0, 40).includes('看跌')) {
      body = `${sentBadge} ${cleanSym ? '$' + cleanSym : ''}\n\n${body}`;
    }
  }

  if (publishMode === 'article' && !title) {
    if (status) {
      status.className = 'blog-publish-status error';
      status.textContent = blogDict().squarePublishFailed + (currentLanguage === 'zh-CN' ? '文章模式标题不能为空（或切换为动态模式发布）' : 'title is required for article mode');
    }
    return;
  }
  if (!body) {
    if (status) {
      status.className = 'blog-publish-status error';
      status.textContent = blogDict().squarePublishFailed + (currentLanguage === 'zh-CN' ? '正文不能为空' : 'body is required');
    }
    return;
  }

  if (button) { button.disabled = true; button.textContent = blogDict().squarePublishing; }
  if (status) { status.className = 'blog-publish-status'; status.textContent = ''; }
  try {
    const response = await window['fetch']('/api/square/publish', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        title,
        body,
        tags,
        cover_data_url: cover,
        images,
        sentiment,
        symbol: currentSymbol
      })
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || `HTTP ${response.status}`);
    if (status) {
      status.className = 'blog-publish-status success';
      const modeZh = result.content_type === 'article_with_cover' ? '长文模式(带封面)' : '动态模式(多图直显)';
      const imgInfo = `附带 ${result.images_count || images.length} 张图片`;
      status.textContent = result.link ? `${blogDict().squarePublished} [${modeZh} · ${imgInfo}] · ${result.link}` : `${blogDict().squareSubmittedNoLink} [${modeZh} · ${imgInfo}]`;
    }
    if (result.link) window.open(result.link, '_blank', 'noopener');
  } catch (error) {
    if (status) {
      status.className = 'blog-publish-status error';
      status.textContent = blogDict().squarePublishFailed + error.message;
    }
  } finally {
    if (button) { button.disabled = false; button.textContent = blogDict().squarePublish; }
  }
}

function generateBlog() {
  let items = (blogStudioState?.items && blogStudioState.items.length) ? blogStudioState.items.slice(0, 5) : (window.recItemsData || []).slice(0, 5);
  let initialSource = 'recommend';
  let needAutoFetch = false;

  if (!items.length) {
    if (window.rankingData?.gainers?.length) {
      items = window.rankingData.gainers.slice(0, 5).map(r => ({
        symbol: r.symbol,
        price: r.price,
        change_24h: r.change_pct,
        side_en: 'LONG',
        side: '做多',
        score: Math.round(Number(r.change_pct || 0) * 2),
        factors: [`24H涨幅榜(+${r.change_pct}%)`, '放量突破热币'],
        sl: r.price ? Number((r.price * 0.98).toPrecision(6)) : null,
        tp1: r.price ? Number((r.price * 1.05).toPrecision(6)) : null,
      }));
      initialSource = 'gainers';
    } else if (window.lastPositions?.length) {
      items = window.lastPositions.slice(0, 5).map(p => ({
        symbol: p.symbol,
        price: Number(p.entry_price || p.entryPrice || 0),
        side_en: (p.side || p.positionSide || 'LONG').toUpperCase().includes('SHORT') ? 'SHORT' : 'LONG',
        factors: ['当前实盘持仓'],
      }));
      initialSource = 'positions';
    } else {
      // 动态读取页面已缓存的行情价格，彻底消除 65000 等历史脱节硬编码
      const btcLivePrice = Number(window.marketTickers?.BTCUSDT?.price || window.lastPrices?.BTCUSDT || 84000.0);
      const ethLivePrice = Number(window.marketTickers?.ETHUSDT?.price || window.lastPrices?.ETHUSDT || 3100.0);
      const solLivePrice = Number(window.marketTickers?.SOLUSDT?.price || window.lastPrices?.SOLUSDT || 180.0);
      items = [
        { symbol: 'BTCUSDT', price: btcLivePrice, change_24h: 1.2, side_en: 'LONG', score: 78, factors: ['24H成交额龙头', '多头关键分水岭'], sl: Number((btcLivePrice * 0.982).toFixed(1)), tp1: Number((btcLivePrice * 1.035).toFixed(1)) },
        { symbol: 'ETHUSDT', price: ethLivePrice, change_24h: 1.8, side_en: 'LONG', score: 65, factors: ['主流生态共振'], sl: Number((ethLivePrice * 0.982).toFixed(1)), tp1: Number((ethLivePrice * 1.035).toFixed(1)) },
        { symbol: 'SOLUSDT', price: solLivePrice, change_24h: 2.6, side_en: 'LONG', score: 80, factors: ['高流动性龙头'], sl: Number((solLivePrice * 0.982).toFixed(2)), tp1: Number((solLivePrice * 1.035).toFixed(2)) },
      ];
      initialSource = 'gainers';
      needAutoFetch = true;
    }
  }

  blogStudioState = { items, content: null }; const d = blogDict(); const overlay = document.createElement('div'); overlay.className = 'blog-overlay'; overlay.id = 'blog-overlay'; overlay.onclick = e => { if (e.target === overlay) closeBlog(); };
  overlay.innerHTML = `<div class="blog-modal blog-studio">
  <div class="blog-head">
    <div><span class="t">${d.studio}</span><span class="sub">实盘数据驱动 · 一键发布至币安广场</span></div>
    <span class="x" onclick="closeBlog()" title="关闭">✕</span>
  </div>
  <div class="blog-studio-body">
    <!-- LEFT PANEL: CONTROLS & AI GENERATION -->
    <aside class="blog-control-panel">
      <div class="blog-section-title" style="color:#a78bfa;display:flex;justify-content:space-between;align-items:center">
        <span>🤖 AI 智能解盘工坊 <small>GPT-5.6 / V4</small></span>
        <button type="button" onclick="openBlogAIKeyModal()" style="font-size:10px;background:rgba(167,139,250,.18);color:#c084fc;border:1px solid rgba(167,139,250,.4);border-radius:4px;cursor:pointer;padding:2px 7px;font-weight:600;display:inline-flex;align-items:center;gap:3px" title="直接在前端配置 OpenAI、DeepSeek、Claude 及绘图 API Key">
          <span>⚙️</span><span>配置模型 Key</span>
        </button>
      </div>
      <div class="blog-field">
        <label>🎯 标的来源范围</label>
        <select id="blog-candidate-source" onchange="onBlogCandidateSourceChange(this.value)">
          <option value="recommend" ${initialSource === 'recommend' ? 'selected' : ''}>🎯 量化策略推荐 (默认)</option>
          <option value="gainers" ${initialSource === 'gainers' ? 'selected' : ''}>🔥 24H 涨幅榜 (暴拉热币)</option>
          <option value="losers">💥 24H 跌幅榜 (暴跌跳水)</option>
          <option value="positions" ${initialSource === 'positions' ? 'selected' : ''}>💎 当前实盘持仓</option>
        </select>
      </div>
      <div class="blog-field">
        <label>AI 创作主笔</label>
        <select id="blog-ai-model">
          <option value="auto" selected>✨ 智能优选 (自动调用最佳AI)</option>
          <option value="1">⚡ DeepSeek · V4 (动量反转与实战研判)</option>
          <option value="0">🤖 OpenAI · GPT-5.6 (深度行情解盘)</option>
        </select>
      </div>
      <div class="blog-field">
        <label>AI 角色人设</label>
        <select id="blog-ai-role">
          <option value="binance_top_creator" selected>🔥 币安广场爆款大V (真实实盘·深度解盘)</option>
          <option value="tactical_sniper">🎯 SMC/价格行为学操盘手 (流动性劫掠)</option>
          <option value="candid_veteran">🍷 多轮牛熊老韭菜 (掏心窝子走心长谈)</option>
          <option value="microstructure_hunter">🔍 微观盘口异动猎手 (大单吸筹·OI背离)</option>
          <option value="contrarian_debater">⚔️ 反共识辩论者 (敢唱反调·打破羊群偏见)</option>
          <option value="chill_swing_trader">☕ 松弛感生活交易员 (咖啡闲聊·松弛随笔)</option>
          <option value="playbook_strategist">♟️ 沙盘双剧本推演官 (双向触发预案)</option>
          <option value="day_trader">⚡ 日内快准狠波段手 (言简意赅)</option>
        </select>
      </div>
      <div class="blog-field">
        <label>文案排版变奏 (千篇千面)</label>
        <select id="blog-format-style">
          <option value="auto" selected>🎲 自动多变轮换 (杜绝固定模版)</option>
          <option value="flow_narrative">🌊 纯口语流式叙述 (推特长推风·无公文标头)</option>
          <option value="field_notes">⚡ 极简实战手记 (短快灵·三段直击要害)</option>
          <option value="dialogue_debate">💬 互动辩论体 (直击散户盲区·引导站队)</option>
          <option value="tactical_playbook">📋 沙盘双剧本体 (剧本A企稳 vs 剧本B止损)</option>
          <option value="chill_casual">🛋️ 松弛随性感 (日常唠嗑·抚平焦虑)</option>
        </select>
      </div>
      <div class="blog-field">
        <label>📈 观点倾向 (Sentiment 标识)</label>
        <select id="blog-sentiment" onchange="onBlogSentimentChange()">
          <option value="auto" selected>🤖 智能自动 (随标的量化方向)</option>
          <option value="BULLISH">🟢 看涨 · 做多 (Bullish)</option>
          <option value="BEARISH">🔴 看跌 · 做空 (Bearish)</option>
        </select>
      </div>
      <div class="blog-field">
        <label>补充关注点 / 持仓点评 (可选)</label>
        <input id="blog-ai-extra" class="obsidian-input" style="width:100%;font-size:11px;padding:4px 6px" placeholder="例如：重点结合我的多单浮盈、分析关键支撑..." />
      </div>
      <button id="btn-blog-ai-gen" class="blog-btn" type="button" onclick="generateBlogWithAI()" style="width:100%;margin-top:6px;margin-bottom:6px;background:linear-gradient(135deg,#7c3aed 0%,#2563eb 100%);color:#fff;font-weight:700;padding:8px 10px;border:none;border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px;box-shadow:0 2px 8px rgba(124,58,237,.35)">
        ✨ 调用 AI 智能解盘与爆款创作
      </button>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-top:4px;margin-bottom:6px">
        <label style="display:flex;align-items:center;gap:6px;font-size:11px;color:#94a3b8;cursor:pointer" title="默认关闭。仅在需要偶尔晒单时勾选；绝大多数文章聚焦客观盘面技术分析">
          <input type="checkbox" id="blog-ai-include-positions" />
          <span>📊 附带实盘持仓与战报 (默认关闭，仅偶尔晒单时勾选)</span>
        </label>
      </div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
        <label style="display:flex;align-items:center;gap:6px;font-size:11px;color:#c084fc;cursor:pointer">
          <input type="checkbox" id="blog-ai-gen-img" />
          <span>🎨 同步调用 OpenAI 绘制专属配图</span>
        </label>
        <button type="button" onclick="openBlogAIKeyModal('image')" style="font-size:10px;background:transparent;color:#a78bfa;border:none;cursor:pointer;text-decoration:underline;padding:0" title="配置 DALL-E 图像模型、画质与 API Key">配置图片 API</button>
      </div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
        <label style="display:flex;align-items:center;gap:6px;font-size:11px;color:#f59e0b;cursor:pointer" title="仅在特定发红包活动时勾选，平时默认关闭，生成纯净实战交易笔记">
          <input type="checkbox" id="blog-ai-redpacket" />
          <span>🎁 附带答题红包 (仅在特定发红包时勾选，默认关闭)</span>
        </label>
      </div>

      <div class="blog-section-title" style="color:#60a5fa;margin-top:6px">📢 广场发布形式</div>
      <div class="blog-field">
        <select id="blog-publish-mode" onchange="onBlogPublishModeChange()">
          <option value="article" selected>📰 深度长文 (带大标题与16:9封面)</option>
          <option value="post">⚡ 动态贴 (信息流多图直显 · 曝光更高)</option>
        </select>
      </div>

      <!-- Hidden fallbacks for blogOptions() -->
      <select id="blog-platform" onchange="updateBlogStudio(true)" style="display:none"><option value="binance_square" selected>Binance Square</option></select>
      <select id="blog-tone" onchange="updateBlogStudio(true)" style="display:none"><option value="analytical" selected>Analytical</option></select>
      <select id="blog-length" onchange="updateBlogStudio(true)" style="display:none"><option value="standard" selected>Standard</option></select>
      <select id="blog-cover-style" onchange="updateBlogStudio(true)" style="display:none"><option value="terminal" selected>Terminal</option></select>

      <div class="blog-auto-card">
        <div class="blog-auto-head">
          <span>⏰ 定时自动发布 (每1小时)</span>
          <span id="blog-auto-state" class="blog-auto-state off">${d.autoPublishOff}</span>
        </div>
        <label style="margin-top:7px;display:flex;align-items:center;gap:6px;cursor:pointer;font-size:11px;color:var(--text-1)">
          <input id="blog-auto-publish" type="checkbox" onchange="toggleSquareAutoPublish(event)">
          开启后台全自动发帖
        </label>
        <div id="blog-auto-next" style="color:var(--text-2);font-size:10px;margin-top:5px"></div>
      </div>

      <!-- 自媒体运营与每日复盘作品中心 -->
      <div class="blog-auto-card" style="margin-top:10px;border-color:rgba(124,58,237,.3);background:rgba(20,15,40,.6)">
        <div class="blog-auto-head" style="color:#c084fc">
          <span>📈 自媒体运营与复盘作品</span>
          <button type="button" onclick="showSquarePostsModal()" style="font-size:10px;background:rgba(124,58,237,.2);color:#c084fc;border:1px solid rgba(124,58,237,.4);border-radius:4px;cursor:pointer;padding:1px 6px">作品库流水 📜</button>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px;font-size:11px">
          <div style="background:rgba(255,255,255,.04);padding:5px 8px;border-radius:6px">
            <div style="color:var(--text-2);font-size:10px">今日作品数</div>
            <div id="sq-today-count" style="font-size:14px;font-weight:700;color:#38bdf8">-- 篇</div>
          </div>
          <div style="background:rgba(255,255,255,.04);padding:5px 8px;border-radius:6px">
            <div style="color:var(--text-2);font-size:10px">大盘全景复盘</div>
            <div id="sq-review-state" style="font-size:12px;font-weight:700;color:#f59e0b">未发布</div>
          </div>
        </div>
        <div id="sq-rotation-chips" style="margin-top:7px;font-size:10px;color:var(--text-2);line-height:1.4">
          <span>🔄 轮换冷却中: </span><span id="sq-cooling-symbols" style="color:#ef4444">无</span>
        </div>
        <button type="button" id="btn-gen-daily-review" onclick="generateDailyReviewDraft()" class="blog-btn" style="width:100%;margin-top:8px;background:linear-gradient(135deg,#059669,#10b981);color:#fff;font-size:11px;font-weight:700;padding:6px;border:none;border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:4px">
          📑 生成【今日大盘全景复盘】作品
        </button>
      </div>
    </aside>

    <!-- MIDDLE PANEL: CONTENT EDITOR & PREVIEW -->
    <section class="blog-editor-panel">
      <div class="blog-section-title" style="display:flex;justify-content:space-between;align-items:center">
        <span>${d.title}</span>
        <button type="button" class="rec-refresh" onclick="generateBlogWithAI('polish')" style="padding:2px 8px;font-size:11px;background:rgba(124,58,237,.15);color:#a78bfa;border:1px solid rgba(124,58,237,.3);border-radius:4px;cursor:pointer">
          🪄 AI 深度润色
        </button>
      </div>
      <div id="blog-sentiment-badge" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;padding:6px 12px;border-radius:6px;font-size:12px;font-weight:700;background:rgba(16,185,129,.12);border:1px solid rgba(16,185,129,.35);color:#10b981">
        <span id="blog-sentiment-badge-text">🟢【当前观点：看涨 · 做多】</span>
        <span style="font-size:10px;font-weight:normal;opacity:0.85">💡 发布时官方将自动打上红绿标</span>
      </div>
      <div id="blog-ai-badge" style="display:none;margin-bottom:8px;padding:5px 10px;border-radius:6px;font-size:11px;background:rgba(16,185,129,.12);border:1px solid rgba(16,185,129,.3);color:#10b981;font-weight:600"></div>

      <div class="blog-field">
        <input id="blog-title" class="blog-title-input" placeholder="输入引人入胜的研报大标题..." />
      </div>
      <div id="blog-metrics" class="blog-preview-meta"></div>

      <div class="blog-field" style="flex:1;display:flex;flex-direction:column">
        <label>${d.article}</label>
        <textarea class="blog-ta" id="blog-ta" style="min-height:280px" placeholder="正文内容..."></textarea>
      </div>

      <!-- Unified Image & Chart Section -->
      <div class="blog-field" style="margin-top:10px;background:rgba(15,23,42,.65);border:1px solid rgba(59,130,246,.3);border-radius:8px;padding:10px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <label style="font-size:11px;color:#93c5fd;font-weight:700;display:flex;align-items:center;gap:5px">
            📷 文章附图与分析图 (最多4张 · 随文章一键发布至官方广场)
          </label>
          <div style="display:flex;gap:6px">
            <input type="file" id="blog-local-img-input" accept="image/*" multiple onchange="handleBlogLocalImageUpload(event)" style="display:none" />
            <button type="button" onclick="document.getElementById('blog-local-img-input').click()" style="font-size:10px;background:rgba(59,130,246,.2);border:1px solid rgba(59,130,246,.4);color:#93c5fd;border-radius:4px;cursor:pointer;padding:3px 8px;font-weight:600">📁 本地上传图片</button>
            <button type="button" onclick="insertCurrentKlineChartToGallery()" style="font-size:10px;background:rgba(99,102,241,.25);border:1px solid rgba(99,102,241,.5);color:#a5b4fc;border-radius:4px;cursor:pointer;padding:3px 8px;font-weight:600">📊 载入K线走势图</button>
            <button type="button" id="btn-blog-openai-img" onclick="generateOpenAIBlogImage('gallery')" style="font-size:10px;background:linear-gradient(135deg,#059669,#10b981);border:none;color:#fff;border-radius:4px;cursor:pointer;padding:3px 8px;font-weight:600" title="调用 OpenAI DALL-E 接口为文章生成一张专属配图">🎨 OpenAI 智能生图</button>
          </div>
        </div>
        <div id="blog-gallery-list" style="display:flex;gap:8px;overflow-x:auto;padding:6px 0;min-height:54px;align-items:center">
          <div id="blog-gallery-empty" style="font-size:10px;color:var(--text-2);padding:8px 0;width:100%;text-align:center">
            💡 可点击上方按钮上传图片/载入K线走势图/OpenAI生图，或直接在正文框按 Ctrl+V 粘贴截图
          </div>
        </div>
        <div style="font-size:10px;color:var(--text-2);margin-top:4px;display:flex;justify-content:space-between">
          <span>✨ 提示：动态/长文附图在发布到币安广场时将直显于信息流，获得更高曝光量与点击互动</span>
          <span id="blog-gallery-counter" style="color:#a78bfa;font-weight:600">已选 0 / 4 张</span>
        </div>
        <!-- 文章内嵌专业分析图与操作（供脚本与快捷调用） -->
        <div style="display:none">
          <span>文章内嵌专业分析图</span>
          <img id="blog-kline-preview-img" alt="专业K线分析图" />
          <button type="button" onclick="copyKlineChartImage()">📋 复制图表</button>
          <button type="button" onclick="downloadKlineChartImage()">📥 下载PNG</button>
          <button type="button" onclick="insertKlineChartToBody()">📌 插入正文</button>
        </div>
      </div>

      <div class="blog-field" style="margin-top:8px">
        <label>${d.tags} (最多5个)</label>
        <input id="blog-tags" class="blog-tags" placeholder="#币安广场 #BTC #做多" />
      </div>
    </section>

    <!-- RIGHT PANEL: 16:9 COVER & TARGET HUD -->
    <aside class="blog-cover-panel">
      <div class="blog-section-title">
        <span>🎨 16:9 封面预览</span>
        <small>专业走势与HUD</small>
      </div>
      <div class="blog-cover-wrap">
        <canvas id="blog-cover-canvas" width="1280" height="720"></canvas>
      </div>
      <div style="margin-top:8px;display:flex;gap:6px">
        <button type="button" onclick="downloadBlogCover()" class="blog-btn" style="flex:1;padding:6px;font-size:11px;background:rgba(59,130,246,.15);border:1px solid rgba(59,130,246,.35);color:#93c5fd;border-radius:6px;cursor:pointer;font-weight:600">
          📥 下载 16:9 封面
        </button>
        <button type="button" id="btn-blog-openai-cover" onclick="generateOpenAIBlogImage('cover')" class="blog-btn" style="flex:1;padding:6px;font-size:11px;background:linear-gradient(135deg,#059669,#10b981);border:none;color:#fff;border-radius:6px;cursor:pointer;font-weight:600" title="调用 OpenAI 接口为当前文章生成一张16:9专属AI封面大图">
          🎨 OpenAI 绘制封面
        </button>
      </div>

      <!-- Real-time Level Summary Card -->
      <div id="blog-target-summary" style="margin-top:12px;background:rgba(10,22,40,.6);border:1px solid rgba(59,130,246,.25);border-radius:8px;padding:10px;font-size:11px">
        <div style="font-weight:700;color:#93c5fd;margin-bottom:8px;display:flex;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,.08);padding-bottom:5px">
          <span>◆ 盘面核心点位速查</span>
          <span id="blog-summary-sym" style="color:#ffcf56">BTCUSDT</span>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;color:var(--text-2)">
          <div>现价: <b id="blog-summary-price" style="color:#fff">--</b></div>
          <div>方向: <b id="blog-summary-side" style="color:#00f59b">--</b></div>
          <div>关键支撑: <b id="blog-summary-sup" style="color:#00f59b">--</b></div>
          <div>关键阻力: <b id="blog-summary-res" style="color:#ff4d6d">--</b></div>
          <div>防守止损: <b id="blog-summary-sl" style="color:#ff4d6d">--</b></div>
          <div>止盈目标: <b id="blog-summary-tp" style="color:#00f59b">--</b></div>
        </div>
      </div>

      <!-- 搞笑梗图（已按优化要求默认收起） -->
      <div id="blog-meme-container" style="display:none">
        <span>封面搞笑梗图</span>
        <img id="blog-meme-img" alt="搞笑梗图" />
        <button type="button" onclick="refreshBlogMeme()">换一张</button>
      </div>
    </aside>
  </div>

  <!-- FOOTER: 4 CLEAN ACTION BUTTONS -->
  <div class="blog-foot">
    <div id="blog-publish-status" class="blog-publish-status"></div>
    <button class="blog-btn primary" onclick="publishBlog(event)" style="flex:2;background:linear-gradient(135deg,#2563eb,#1d4ed8);font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:center;gap:6px">
      📢 一键发布至币安广场 (Binance Square)
    </button>
    <button class="blog-btn" onclick="copyBlog(event)" style="flex:1">
      📋 复制全文与标签
    </button>
    <button class="blog-btn" onclick="saveBlogToObsidian(event)" style="flex:1;background:rgba(124,58,237,.2);border-color:rgba(124,58,237,.4);color:#c084fc">
      📓 保存至Obsidian(MD+封面)
    </button>
    <button class="blog-btn" onclick="closeBlog()" style="flex:0.6">
      ${d.close}
    </button>
  </div>
</div>`;

  document.body.appendChild(overlay); ['blog-title','blog-ta','blog-tags'].forEach(id => document.getElementById(id)?.addEventListener('input', e => { e.target.dataset.edited = '1'; })); updateBlogStudio(); loadSquareAutoStatus(); loadSquareDailyAnalytics(); loadBlogPromotion(); loadBlogImageConfig(); initBlogPasteHandler(); renderBlogGallery();
  if (needAutoFetch) {
    setTimeout(() => { onBlogCandidateSourceChange('gainers'); }, 60);
  }
}
function closeBlog() { const overlay = document.getElementById('blog-overlay'); if (overlay) overlay.remove(); blogStudioState = null; }

async function onBlogCandidateSourceChange(source) {
  if (!blogStudioState) return;
  const badge = document.getElementById('blog-ai-badge');
  if (source === 'recommend') {
    if (window.recItemsData && window.recItemsData.length) {
      blogStudioState.items = window.recItemsData.slice(0, 5);
      updateBlogStudio(true);
      if (badge) {
        badge.style.display = 'block';
        badge.style.background = 'rgba(59,130,246,.12)';
        badge.style.borderColor = 'rgba(59,130,246,.3)';
        badge.style.color = '#60a5fa';
        badge.innerHTML = `🎯 已切换至量化策略推荐标的 (${blogStudioState.items.length} 个机会)`;
      }
      return;
    }
    if (badge) {
      badge.style.display = 'block';
      badge.style.background = 'rgba(59,130,246,.12)';
      badge.style.borderColor = 'rgba(59,130,246,.3)';
      badge.style.color = '#60a5fa';
      badge.innerHTML = `⏳ 正在实时扫描量化推荐候选池...`;
    }
    try {
      const res = await fetch('/api/blog/candidates?source=recommend&limit=5');
      const data = await res.json();
      if (data.ok && data.items && data.items.length) {
        blogStudioState.items = data.items;
        updateBlogStudio(true);
        if (badge) {
          badge.style.background = 'rgba(16,185,129,.12)';
          badge.style.borderColor = 'rgba(16,185,129,.3)';
          badge.style.color = '#10b981';
          badge.innerHTML = `🎯 成功载入量化策略推荐标的 (${data.items.length} 个机会)`;
        }
        return;
      }
    } catch(e) {}
    if (badge) {
      badge.style.display = 'block';
      badge.style.background = 'rgba(234,179,8,.12)';
      badge.style.borderColor = 'rgba(234,179,8,.3)';
      badge.style.color = '#eab308';
      badge.innerHTML = `💡 当前量化推荐池暂无强信号标的，已为您保留热币，或可切换至上方 <b>🔥 24H 涨幅榜</b> 创作！`;
    }
    return;
  }
  if (badge) {
    badge.style.display = 'block';
    badge.style.background = 'rgba(59,130,246,.12)';
    badge.style.borderColor = 'rgba(59,130,246,.3)';
    badge.style.color = '#60a5fa';
    badge.innerHTML = `⏳ 正在全市场扫描 <b>${source === 'gainers' ? '24H 涨幅榜' : source === 'losers' ? '24H 跌幅榜' : '当前持仓'}</b> 并计算支撑阻力分水岭...`;
  }
  try {
    const res = await fetch(`/api/blog/candidates?source=${encodeURIComponent(source)}&limit=5`);
    const data = await res.json();
    if (data.ok && data.items && data.items.length) {
      blogStudioState.items = data.items;
      updateBlogStudio(true);
      if (badge) {
        badge.style.background = 'rgba(16,185,129,.12)';
        badge.style.borderColor = 'rgba(16,185,129,.3)';
        badge.style.color = '#10b981';
        const srcName = source === 'gainers' ? '🔥 24H 涨幅榜暴拉热币' : source === 'losers' ? '💥 24H 跌幅榜跳水异动' : '💎 实盘持仓';
        badge.innerHTML = `✨ 成功载入 <b>${srcName}</b>（${data.items.map(it => it.symbol).join(' · ')}）！`;
      }
    } else {
      throw new Error(data.note || data.error || '未获取到有效候选标的');
    }
  } catch (err) {
    if (badge) {
      badge.style.color = '#ef4444';
      badge.innerHTML = `⚠️ 标的切换提示: ${err.message}`;
    }
  }
}

async function generateBlogForSymbol(symbol, side) {
  if (!symbol) return;
  if (!blogStudioState) {
    blogStudioState = { items: [{ symbol, price: 0, side_en: side || 'LONG' }], content: null };
    generateBlog();
  }
  const badge = document.getElementById('blog-ai-badge');
  if (badge) {
    badge.style.display = 'block';
    badge.style.background = 'rgba(59,130,246,.12)';
    badge.style.borderColor = 'rgba(59,130,246,.3)';
    badge.style.color = '#60a5fa';
    badge.innerHTML = `⏳ 正在秒级拉取 <b>${escapeHtml(symbol)}</b> 的真实 K 线走势并计算关键支撑压力位...`;
  }
  const sel = document.getElementById('blog-candidate-source');
  if (sel) {
    let symOpt = [...sel.options].find(o => o.value === `symbol_${symbol}`);
    if (!symOpt) {
      symOpt = new Option(`🔍 榜单热币: ${symbol}`, `symbol_${symbol}`);
      sel.add(symOpt);
    }
    sel.value = `symbol_${symbol}`;
  }
  try {
    const res = await fetch(`/api/blog/candidates?source=symbol&symbol=${encodeURIComponent(symbol)}`);
    const data = await res.json();
    if (data.ok && data.items && data.items.length) {
      blogStudioState.items = data.items;
      updateBlogStudio(true);
      if (badge) {
        badge.style.background = 'rgba(16,185,129,.12)';
        badge.style.borderColor = 'rgba(16,185,129,.3)';
        badge.style.color = '#10b981';
        badge.innerHTML = `✅ 已载入 <b>${escapeHtml(symbol)}</b> 盘面数据与 K 线走势截图！可直接复制或点击上方 AI 智能解盘。`;
      }
    } else {
      throw new Error(data.error || '获取行情失败');
    }
  } catch (err) {
    if (badge) {
      badge.style.color = '#ef4444';
      badge.innerHTML = `❌ 载入 ${escapeHtml(symbol)} 失败: ${err.message}`;
    }
  }
}

async function refreshBlogMeme() { /* deprecated */ }

async function loadKlineChartForSymbol(symbol) {
  if (!symbol) return;
  const imgEl = document.getElementById('blog-kline-preview-img');
  const holderEl = document.getElementById('blog-kline-preview-placeholder');
  if (holderEl) { holderEl.style.display = 'block'; holderEl.textContent = `⏳ 正在渲染 ${symbol} 专业 K 线走势图...`; }
  if (imgEl) { imgEl.style.display = 'none'; }
  try {
    const res = await fetch(`/api/blog/kline_chart?symbol=${encodeURIComponent(symbol)}`);
    const data = await res.json();
    if (data.ok && data.data_url) {
      if (blogStudioState) {
        blogStudioState.klineDataUrl = data.data_url;
      }
      if (imgEl) {
        imgEl.src = data.data_url;
        imgEl.style.display = 'block';
      }
      if (holderEl) {
        holderEl.style.display = 'none';
      }
      if (window.blogGalleryImages && !window.blogGalleryImages.some(it => it.source === 'kline') && window.blogGalleryImages.length < 4) {
        window.blogGalleryImages.push({ data_url: data.data_url, name: `${symbol}走势图`, source: 'kline' });
        renderBlogGallery();
      }
    }
  } catch(e) {
    if (holderEl) { holderEl.textContent = `⚠️ K线分析图载入失败: ${e.message}`; }
  }
}

function insertCurrentKlineChartToGallery() {
  const sym = blogStudioState?.items?.[0]?.symbol || 'BTCUSDT';
  const dataUrl = blogStudioState?.klineDataUrl;
  if (dataUrl) {
    addBlogImageToGallery(dataUrl, `📊 ${sym}走势图`, 'kline');
  } else {
    loadKlineChartForSymbol(sym);
  }
}

function copyKlineChartImage() {
  const dataUrl = blogStudioState?.klineDataUrl;
  if (!dataUrl) { alert('尚未获取到专业分析图'); return; }
  try {
    const byteString = atob(dataUrl.split(',')[1]);
    const ab = new ArrayBuffer(byteString.length);
    const ia = new Uint8Array(ab);
    for (let i = 0; i < byteString.length; i++) ia[i] = byteString.charCodeAt(i);
    const blob = new Blob([ab], { type: 'image/png' });
    if (navigator.clipboard && window.ClipboardItem) {
      navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]).then(() => {
        alert('✅ 已将专业分析图复制到剪贴板！');
      }).catch(() => {
        fallbackCopy(dataUrl);
        alert('✅ 已复制分析图数据');
      });
    } else {
      fallbackCopy(dataUrl);
      alert('✅ 已复制分析图数据');
    }
  } catch(e) {
    fallbackCopy(dataUrl);
    alert('✅ 已复制分析图数据');
  }
}

function downloadKlineChartImage() {
  const dataUrl = blogStudioState?.klineDataUrl;
  if (!dataUrl) { alert('尚未获取到专业分析图'); return; }
  const topSym = blogStudioState?.items?.[0]?.symbol || 'CRYPTO';
  const a = document.createElement('a');
  a.download = `${topSym}_kline_analysis_${new Date().toISOString().slice(0,10)}.png`;
  a.href = dataUrl;
  a.click();
}

function insertKlineChartToBody() {
  const ta = document.getElementById('blog-ta');
  if (!ta) return;
  const topSym = blogStudioState?.items?.[0]?.symbol || 'CRYPTO';
  const dataUrl = blogStudioState?.klineDataUrl || '';
  if (dataUrl) {
    addBlogImageToGallery(dataUrl, `📊 ${topSym}走势图`, 'kline');
  }
  const insertText = `\n\n![📊 ${topSym} 专业走势分析图](${dataUrl})\n\n`;
  ta.value = (ta.value || '').trim() + insertText;
  ta.dataset.edited = '1';
  alert('✅ 已将专业分析图内嵌标记插入正文并加入待发布图片画廊！');
}

async function saveBlogToObsidian(event) {
  const btn = event?.currentTarget || event?.target;
  const originalText = btn ? btn.textContent : '';
  const status = document.getElementById('blog-publish-status');
  try {
    if (btn) { btn.disabled = true; btn.textContent = '⏳ 保存中...'; }
    const title = document.getElementById('blog-title')?.value || '';
    const hook = document.getElementById('blog-hook')?.value || '';
    const body = document.getElementById('blog-ta')?.value || '';
    const tags = document.getElementById('blog-tags')?.value || '';
    const platform = document.getElementById('blog-platform')?.value || 'general';
    const tone = document.getElementById('blog-tone')?.value || 'analytical';
    const canvas = document.getElementById('blog-cover-canvas');
    let cover_data_url = '';
    if (canvas) {
      try {
        cover_data_url = canvas.toDataURL('image/png');
      } catch (e) {
        console.warn('Canvas toDataURL failed:', e);
      }
    }
    const firstGalleryImg = (window.blogGalleryImages && window.blogGalleryImages.length > 0) ? window.blogGalleryImages[0].data_url : '';
    const analysis_chart_data_url = blogStudioState?.klineDataUrl || firstGalleryImg || '';
    const res = await fetch('/api/obsidian/save_blog_note', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title,
        hook,
        body,
        tags,
        platform,
        tone,
        cover_data_url,
        analysis_chart_data_url
      })
    });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      throw new Error(data.error || `HTTP ${res.status}`);
    }
    if (status) {
      status.className = 'blog-publish-status success';
      status.textContent = `✅ 成功归档至 Obsidian「${data.note_filename || '行情简报'}」，搞笑梗图封面与正文专业分析图已自动生成！`;
    }
    if (btn) { btn.textContent = '✅ 已保存至Obsidian'; }
    setTimeout(() => {
      if (btn) { btn.disabled = false; btn.textContent = originalText; }
    }, 2500);
  } catch (err) {
    if (status) {
      status.className = 'blog-publish-status error';
      status.textContent = `❌ 保存失败: ${err.message}`;
    }
    if (btn) { btn.disabled = false; btn.textContent = originalText; }
  }
}

async function generateBlogWithAI(mode = 'create') {
  const btn = document.getElementById('btn-blog-ai-gen');
  const badge = document.getElementById('blog-ai-badge');
  const origBtnText = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ 🤖 AI 主笔正在研判盘面并撰写爆款文章...';
  }
  if (badge) {
    badge.style.display = 'block';
    badge.style.background = 'rgba(59,130,246,.12)';
    badge.style.borderColor = 'rgba(59,130,246,.3)';
    badge.style.color = '#60a5fa';
    badge.innerHTML = '⏳ 正在汇总量化指标与持仓快照，调用底层 AI 模型进行技术面深度推演中...';
  }

  try {
    const items = (blogStudioState?.items && blogStudioState.items.length) ? blogStudioState.items.slice(0, 5) : (window.recItemsData || []).slice(0, 5);
    const includePositions = !!document.getElementById('blog-ai-include-positions')?.checked;
    const positions = includePositions ? (lastPositions || []) : [];
    const platform = document.getElementById('blog-platform')?.value || 'binance_square';
    const tone = document.getElementById('blog-tone')?.value || 'analytical';
    const length = document.getElementById('blog-length')?.value || 'standard';
    const providerIndex = document.getElementById('blog-ai-model')?.value || 'auto';
    const persona = document.getElementById('blog-ai-role')?.value || 'binance_top_creator';
    const formatStyle = document.getElementById('blog-format-style')?.value || 'auto';
    let extra = document.getElementById('blog-ai-extra')?.value?.trim() || '';

    if (mode === 'polish') {
      const curTitle = document.getElementById('blog-title')?.value || '';
      let curBody = document.getElementById('blog-ta')?.value || '';
      curBody = curBody.replace(/^#{1,6}\s+/gm, '');
      extra += `\n【当前草稿请做专业润色与爆款结构升级（排版严禁在标题前输出 ## 或 # 符号，段落排版自然生动，严禁机械使用 Emoji 公文标头与单一模板）】：\n标题：${curTitle}\n正文：${curBody}`;
    }

    const autoGenImg = !!document.getElementById('blog-ai-gen-img')?.checked;
    const includeRedPacket = !!document.getElementById('blog-ai-redpacket')?.checked;

    const resp = await fetch('/api/blog/ai_generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        items,
        positions,
        platform,
        tone,
        length,
        provider_index: providerIndex,
        persona,
        format_style: formatStyle,
        custom_instruction: extra,
        generate_image: autoGenImg,
        include_red_packet: includeRedPacket
      })
    });

    const res = await resp.json();
    if (!resp.ok || !res.ok) {
      throw new Error(res.error || `HTTP ${resp.status}`);
    }

    const d = res.data || {};
    if (d.title) {
      const el = document.getElementById('blog-title');
      if (el) { el.value = d.title; el.dataset.edited = '1'; }
    }
    if (d.hook) {
      const el = document.getElementById('blog-hook');
      if (el) { el.value = d.hook; el.dataset.edited = '1'; }
    }
    if (d.body) {
      const el = document.getElementById('blog-ta');
      const cleanBody = String(d.body || '')
        .replace(/^#{1,6}\s+/gm, '')
        .replace(/!\[.*?\]\([^)]+\)/g, '')
        .trim();
      if (el) { el.value = cleanBody; el.dataset.edited = '1'; }
    }
    if (d.tags) {
      const el = document.getElementById('blog-tags');
      if (el) { el.value = d.tags; el.dataset.edited = '1'; }
    }
    if (d.prompt) {
      const el = document.getElementById('blog-prompt');
      if (el) { el.value = d.prompt; }
    }
    if (d.sentiment) {
      const sentSel = document.getElementById('blog-sentiment');
      if (sentSel) sentSel.value = d.sentiment;
      syncBlogSentimentBadge(d.sentiment === 'BULLISH' ? 'LONG' : 'SHORT');
    }

    // Auto-attach AI generated image if returned
    if (d.image_data_url) {
      const topSym = blogStudioState?.items?.[0]?.symbol || 'CRYPTO';
      addBlogImageToGallery(d.image_data_url, `🎨 ${topSym} AI封面配图`, 'openai');
      const canvas = document.getElementById('blog-cover-canvas');
      if (canvas) {
        const ctx = canvas.getContext('2d');
        const img = new Image();
        img.onload = () => {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        };
        img.src = d.image_data_url;
      }
    }

    // Update cover preview
    if (blogStudioState) {
      blogStudioState.content = {
        ...(blogStudioState.content || {}),
        title: d.title || blogStudioState.content?.title,
        hook: d.hook || blogStudioState.content?.hook,
        tags: d.tags || blogStudioState.content?.tags,
        direction: d.sentiment === 'BULLISH' ? 'LONG' : (d.sentiment === 'BEARISH' ? 'SHORT' : blogStudioState.content?.direction)
      };
      drawBlogCover(blogStudioState.items, blogOptions(), blogStudioState.content);
    }

    if (badge) {
      badge.style.display = 'block';
      badge.style.background = 'rgba(16,185,129,.12)';
      badge.style.borderColor = 'rgba(16,185,129,.3)';
      badge.style.color = '#10b981';
      const imgNote = d.image_data_url ? ' · 🎨 OpenAI 专属配图已同步生成！' : '';
      badge.innerHTML = `✨ <b>AI 主笔创作完成！</b> 由 <b>${res.provider_name || 'AI'} (${res.model || ''})</b> 实时生成 (耗时 ${(res.latency_ms / 1000).toFixed(1)}s)${imgNote}`;
    }
  } catch (err) {
    alert('AI 生成失败: ' + err.message);
    if (badge) {
      badge.style.display = 'block';
      badge.style.background = 'rgba(239,68,68,.12)';
      badge.style.borderColor = 'rgba(239,68,68,.3)';
      badge.style.color = '#ef4444';
      badge.innerHTML = `❌ AI 生成失败: ${err.message}`;
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origBtnText;
    }
  }
}

async function generateOpenAIBlogImage(target = 'gallery') {
  const btn = target === 'cover' ? document.getElementById('btn-blog-openai-cover') : document.getElementById('btn-blog-openai-img');
  const origText = btn ? btn.innerHTML : '';
  const topSym = blogStudioState?.items?.[0]?.symbol || 'BTCUSDT';
  const customPrompt = blogStudioState?.content?.prompt || document.getElementById('blog-title')?.value || `A futuristic cryptocurrency trading chart visual for ${topSym}`;

  if (btn) { btn.disabled = true; btn.innerHTML = '⏳ 正在绘图...'; }
  const statusEl = document.getElementById('blog-publish-status');
  try {
    let curImgModel = (
      document.getElementById('bkey-img-model')?.value ||
      document.getElementById('sp-img-model')?.value ||
      window.blogImageConfig?.model ||
      'gpt-image-2'
    ).trim();
    if (curImgModel === 'custom') {
      curImgModel = (document.getElementById('bkey-img-model-custom')?.value || window.blogImageConfig?.model || 'gpt-image-2').trim();
    }
    if (statusEl) { statusEl.className = 'blog-publish-status'; statusEl.textContent = `🎨 正在使用 ${curImgModel} 为 ${topSym} 生成专属配图...`; }

    const res = await fetch('/api/blog/generate_image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: topSym,
        prompt: customPrompt,
        size: curImgModel === 'dall-e-2' ? '1024x1024' : (window.blogImageConfig?.size || '1792x1024'),
        model: curImgModel
      })
    });
    const data = await res.json();
    if (!res.ok || !data.ok || !data.data_url) {
      throw new Error(data.error || '图片生成失败');
    }

    if (target === 'cover') {
      const canvas = document.getElementById('blog-cover-canvas');
      if (canvas) {
        const ctx = canvas.getContext('2d');
        const img = new Image();
        img.onload = () => {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        };
        img.src = data.data_url;
      }
      addBlogImageToGallery(data.data_url, `🎨 ${topSym} AI封面`, 'openai');
      if (statusEl) { statusEl.className = 'blog-publish-status success'; statusEl.textContent = `✨ 成功生成并应用 OpenAI 16:9 封面图！`; }
    } else {
      addBlogImageToGallery(data.data_url, `🎨 ${topSym} AI配图`, 'openai');
      if (statusEl) { statusEl.className = 'blog-publish-status success'; statusEl.textContent = `✨ 成功生成 OpenAI 配图并加入文章附图画廊！`; }
    }
  } catch (err) {
    let errMsg = err.message || '';
    const isRelayAccountErr = (
      errMsg.includes('无可用渠道') ||
      errMsg.includes('distributor') ||
      errMsg.includes('model_not_found') ||
      errMsg.includes('未开启绘图渠道') ||
      errMsg.toLowerCase().includes('no available compatible accounts') ||
      errMsg.toLowerCase().includes('no available channels') ||
      errMsg.toLowerCase().includes('compatible accounts') ||
      errMsg.includes('503') ||
      errMsg.includes('暂无可用账号') ||
      errMsg.includes('超时') ||
      target === 'cover'
    );
    if (isRelayAccountErr) {
      drawBlogCover(blogStudioState.items, blogOptions(), blogStudioState.content);
      const canvas = document.getElementById('blog-cover-canvas');
      if (canvas) {
        const localDataUrl = canvas.toDataURL('image/png');
        addBlogImageToGallery(localDataUrl, `📊 ${topSym} 量化科技感封面`, 'local');
      }
      alert('【AI 绘图自动容灾回退提示】\n\n' + errMsg + '\n\n💡 监测到当前绘图上游账号池异常（如中转站暂无可用账号 / 503），系统已自动为您无缝绘制本地 16:9 高清量化科技感封面并应用到文章！保证博客排版完整美观、可直接发布！');
      if (statusEl) {
        statusEl.className = 'blog-publish-status warning';
        statusEl.textContent = '⚠️ 中转站绘图上游暂无可用账号，已自动生成并应用本地 16:9 高清量化科技封面！';
      }
    } else {
      alert('OpenAI 绘图提示: ' + errMsg);
      if (statusEl) { statusEl.className = 'blog-publish-status error'; statusEl.textContent = `❌ 绘图失败: ${errMsg}`; }
    }
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = origText; }
  }
}

async function openBlogAIKeyModal(focusSection = 'all') {
  let cfg = {};
  let imgCfg = {};
  try {
    const [cfgRes, imgRes] = await Promise.all([
      fetch('/api/config'),
      fetch('/api/blog/image_config')
    ]);
    if (cfgRes.ok) cfg = await cfgRes.json();
    if (imgRes.ok) {
      const data = await imgRes.json();
      imgCfg = data.config || {};
    }
  } catch (e) {
    console.warn('Failed to fetch config:', e);
  }

  const providers = cfg.ai_committee?.providers || [];
  const deepseek = providers[0] || { name: 'DeepSeek', model: 'deepseek-v4-flash-vision-exp', base_url: 'https://api.deepseek.com' };
  const openai = providers[1] || { name: 'OpenAI', model: 'gpt-5.6-sol', base_url: 'https://new.sharedchat.cc/codex' };
  const claude = providers[2] || { name: 'Claude', model: '', base_url: '' };

  const existing = document.getElementById('blog-ai-key-overlay');
  if (existing) existing.remove();

  const overlay = document.createElement('div');
  overlay.className = 'settings-overlay';
  overlay.id = 'blog-ai-key-overlay';
  overlay.style.zIndex = '10100';
  overlay.onclick = e => { if (e.target === overlay) closeBlogAIKeyModal(); };

  overlay.innerHTML = `
    <div class="settings-modal" style="width:min(880px, 96vw);max-height:92vh;border:1px solid rgba(168,85,247,.4);box-shadow:0 24px 80px rgba(0,0,0,.7), 0 0 24px rgba(168,85,247,.18);">
      <div class="settings-head" style="background:linear-gradient(90deg, rgba(168,85,247,.18), rgba(59,130,246,.12) 50%, transparent);">
        <div class="settings-title">
          <strong style="color:#c084fc;display:flex;align-items:center;gap:6px">⚙️ AI 模型与图片生成 API 快捷配置</strong>
          <span style="color:var(--text-2);font-size:11px">配置解盘大模型与 DALL-E 绘图密钥 · 保存后无需重启服务即刻生效</span>
        </div>
        <button class="settings-close" onclick="closeBlogAIKeyModal()">✕</button>
      </div>
      <div class="settings-body" style="display:flex;flex-direction:column;gap:12px;padding:16px;">
        <div style="background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.25);border-radius:8px;padding:10px 12px;font-size:11px;color:#93c5fd;line-height:1.5">
          💡 <b>提示</b>：在此填写的 API Key 与 Base URL 将直接保存在本地 <code>config.json</code> 并热加载。若您的 OpenAI 接口支持 DALL-E 3，图片生成将自动复用该 Key。
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(360px, 1fr));gap:12px">
          <!-- 1. OpenAI (主解盘与爆款创作) -->
          <div class="provider-card" style="border:1px solid rgba(59,130,246,.3);background:rgba(15,23,42,.65)">
            <div class="provider-name" style="color:#60a5fa">
              <span>🤖 OpenAI (博客主笔 · 行情深度解盘)</span>
              <span class="provider-dot" style="background:#3b82f6"></span>
            </div>
            <div class="provider-role-desc">用于撰写深度研报、实盘笔记、提炼吸睛大标题及行情策略。</div>
            <div class="settings-field"><label>模型名称 (Model)</label><input id="bkey-openai-model" value="${escapeHtml(openai.model || 'gpt-5.6-sol')}" placeholder="gpt-5.6-sol / gpt-4o"></div>
            <div class="settings-field"><label>API 地址 (Base URL)</label><input id="bkey-openai-url" value="${escapeHtml(openai.base_url || '')}" placeholder="https://api.openai.com/v1 或 反代地址"></div>
            <div class="settings-field"><label>API Key</label><input id="bkey-openai-key" type="password" placeholder="${openai.api_key_configured ? '已配置 (留空保持不变)' : 'sk-...'}"></div>
            <div class="provider-test-row">
              <button class="provider-test-btn" id="bkey-btn-test-openai" onclick="testBlogKey('openai')">⚡ 测试 OpenAI 连接</button>
              <span class="provider-test-status" id="bkey-status-openai"></span>
            </div>
          </div>

          <!-- 2. OpenAI DALL-E (爆款配图与16:9封面) -->
          <div class="provider-card" id="bkey-card-image" style="border:1px solid rgba(168,85,247,.4);background:rgba(168,85,247,.05)">
            <div class="provider-name" style="color:#c084fc">
              <span>🎨 OpenAI DALL-E (图像生成 · 16:9 封面)</span>
              <span class="provider-dot" style="background:#a855f7"></span>
            </div>
            <div class="provider-role-desc">为文章自动生成 16:9 科技感封面大图与盘面附图，直接随文章发布至币安广场。</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
              <div class="settings-field">
                <label>绘图模型</label>
                <select id="bkey-img-model" onchange="onBKeyImgModelChange(this.value)">
                  <option value="gpt-image-2" ${(imgCfg.model || 'gpt-image-2') === 'gpt-image-2' ? 'selected' : ''}>gpt-image-2 (中转站绘图 · 推荐)</option>
                  <option value="gpt-image-2.5-flare" ${imgCfg.model === 'gpt-image-2.5-flare' ? 'selected' : ''}>gpt-image-2.5-flare (中转站高阶版)</option>
                  <option value="gpt-image-2.5-sunburst" ${imgCfg.model === 'gpt-image-2.5-sunburst' ? 'selected' : ''}>gpt-image-2.5-sunburst (中转站太阳花)</option>
                  <option value="dall-e-3" ${imgCfg.model === 'dall-e-3' ? 'selected' : ''}>dall-e-3 (OpenAI 官方 16:9)</option>
                  <option value="dall-e-2" ${imgCfg.model === 'dall-e-2' ? 'selected' : ''}>dall-e-2 (经典方图)</option>
                  ${!['gpt-image-2', 'gpt-image-2.5-flare', 'gpt-image-2.5-sunburst', 'dall-e-3', 'dall-e-2'].includes(imgCfg.model || '') && imgCfg.model ? `<option value="${escapeHtml(imgCfg.model)}" selected>${escapeHtml(imgCfg.model)} (当前配置)</option>` : ''}
                  <option value="custom">自定义模型名称...</option>
                </select>
                <input id="bkey-img-model-custom" class="obsidian-input" style="display:none;margin-top:4px;font-size:11px;padding:4px 6px" placeholder="输入自定义模型名称，如 gpt-image-2" />
              </div>
              <div class="settings-field">
                <label>图像画质</label>
                <select id="bkey-img-quality">
                  <option value="standard" ${(imgCfg.quality || 'standard') === 'standard' ? 'selected' : ''}>standard (标准速度快)</option>
                  <option value="hd" ${imgCfg.quality === 'hd' ? 'selected' : ''}>hd (超清高精)</option>
                </select>
              </div>
            </div>
            <div class="settings-field"><label>独立 API 地址 (可选，留空则复用上方 OpenAI 地址)</label><input id="bkey-img-url" value="${escapeHtml(imgCfg.base_url || '')}" placeholder="留空自动复用 OpenAI 接口地址"></div>
            <div class="settings-field"><label>独立 API Key (可选，留空则复用上方 OpenAI Key)</label><input id="bkey-img-key" type="password" placeholder="${imgCfg.has_api_key ? '已配置 (留空复用 OpenAI Key)' : '留空复用 OpenAI Key'}"></div>
            <div class="provider-test-row">
              <button class="provider-test-btn" id="bkey-btn-test-img" onclick="testBlogKey('image')" style="border-color:#a855f7;background:rgba(168,85,247,.15);color:#c084fc">🎨 测试绘图接口连通性</button>
              <span class="provider-test-status" id="bkey-status-img"></span>
            </div>
          </div>

          <!-- 3. DeepSeek (动量反转与数据精算) -->
          <div class="provider-card" style="border:1px solid rgba(16,185,129,.3);background:rgba(15,23,42,.65)">
            <div class="provider-name" style="color:#34d399">
              <span>⚡ DeepSeek · V4 (动量反转 · 数据精算)</span>
              <span class="provider-dot" style="background:#10b981"></span>
            </div>
            <div class="provider-role-desc">用于快速反转研判、动量挖掘与精准数据回测。</div>
            <div class="settings-field"><label>模型名称 (Model)</label><input id="bkey-deepseek-model" value="${escapeHtml(deepseek.model || 'deepseek-v4-flash-vision-exp')}" placeholder="deepseek-chat / deepseek-v4-flash-vision-exp"></div>
            <div class="settings-field"><label>API 地址 (Base URL)</label><input id="bkey-deepseek-url" value="${escapeHtml(deepseek.base_url || 'https://api.deepseek.com')}" placeholder="https://api.deepseek.com"></div>
            <div class="settings-field"><label>API Key</label><input id="bkey-deepseek-key" type="password" placeholder="${deepseek.api_key_configured ? '已配置 (留空保持不变)' : 'sk-...'}"></div>
            <div class="provider-test-row">
              <button class="provider-test-btn" id="bkey-btn-test-deepseek" onclick="testBlogKey('deepseek')" style="border-color:#10b981;background:rgba(16,185,129,.15);color:#34d399">⚡ 测试 DeepSeek 连接</button>
              <span class="provider-test-status" id="bkey-status-deepseek"></span>
            </div>
          </div>

          <!-- 4. Claude (首席风控官与备选模型) -->
          <div class="provider-card" style="border:1px solid rgba(245,158,11,.3);background:rgba(15,23,42,.65)">
            <div class="provider-name" style="color:#fbbf24">
              <span>🛡️ Claude (首席风控官 · 备选模型)</span>
              <span class="provider-dot" style="background:#f59e0b"></span>
            </div>
            <div class="provider-role-desc">用于开仓前诱多诱空审查、极端行情风险一票否决。</div>
            <div class="settings-field"><label>模型名称 (Model)</label><input id="bkey-claude-model" value="${escapeHtml(claude.model || '')}" placeholder="claude-3-5-sonnet-20241022"></div>
            <div class="settings-field"><label>API 地址 (Base URL)</label><input id="bkey-claude-url" value="${escapeHtml(claude.base_url || '')}" placeholder="留空默认官方地址或代理"></div>
            <div class="settings-field"><label>API Key</label><input id="bkey-claude-key" type="password" placeholder="${claude.api_key_configured ? '已配置 (留空保持不变)' : 'sk-...'}"></div>
            <div class="provider-test-row">
              <button class="provider-test-btn" id="bkey-btn-test-claude" onclick="testBlogKey('claude')" style="border-color:#f59e0b;background:rgba(245,158,11,.15);color:#fbbf24">⚡ 测试 Claude 连接</button>
              <span class="provider-test-status" id="bkey-status-claude"></span>
            </div>
          </div>
        </div>
      </div>
      <div class="settings-foot" style="background:rgba(15,23,42,.95);border-top:1px solid rgba(168,85,247,.3)">
        <span class="settings-status" id="bkey-save-status">💾 配置修改后点击右侧按钮立即保存生效</span>
        <div class="settings-actions">
          <button class="settings-action" onclick="closeBlogAIKeyModal()">取消</button>
          <button class="settings-action primary" id="bkey-btn-save" onclick="saveBlogAIKeys()" style="background:linear-gradient(135deg,#7c3aed 0%,#2563eb 100%);border:none;box-shadow:0 2px 10px rgba(124,58,237,.4)">💾 保存配置 (立即生效)</button>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  if (focusSection === 'image') {
    setTimeout(() => {
      const card = document.getElementById('bkey-card-image');
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.style.boxShadow = '0 0 20px rgba(168,85,247,0.7)';
      }
    }, 100);
  }
}

function closeBlogAIKeyModal() {
  const el = document.getElementById('blog-ai-key-overlay');
  if (el) el.remove();
}

function onBKeyImgModelChange(val) {
  const customInput = document.getElementById('bkey-img-model-custom');
  if (customInput) {
    customInput.style.display = (val === 'custom') ? 'block' : 'none';
    if (val === 'custom') customInput.focus();
  }
}

async function testBlogKey(type) {
  let btn, status, model, url, key, providerIndex = -1;
  if (type === 'openai') {
    btn = document.getElementById('bkey-btn-test-openai');
    status = document.getElementById('bkey-status-openai');
    model = (document.getElementById('bkey-openai-model')?.value || '').trim();
    url = (document.getElementById('bkey-openai-url')?.value || '').trim();
    key = (document.getElementById('bkey-openai-key')?.value || '').trim();
    providerIndex = 1;
    if (url && !url.endsWith('/v1') && !url.includes('/v1') && !url.includes('/codex') && !url.includes('api.deepseek.com')) {
      url = url.replace(/\/+$/, '') + '/v1';
      const inputEl = document.getElementById('bkey-openai-url');
      if (inputEl) inputEl.value = url;
    }
  } else if (type === 'deepseek') {
    btn = document.getElementById('bkey-btn-test-deepseek');
    status = document.getElementById('bkey-status-deepseek');
    model = (document.getElementById('bkey-deepseek-model')?.value || '').trim();
    url = (document.getElementById('bkey-deepseek-url')?.value || '').trim();
    key = (document.getElementById('bkey-deepseek-key')?.value || '').trim();
    providerIndex = 0;
  } else if (type === 'claude') {
    btn = document.getElementById('bkey-btn-test-claude');
    status = document.getElementById('bkey-status-claude');
    model = (document.getElementById('bkey-claude-model')?.value || '').trim();
    url = (document.getElementById('bkey-claude-url')?.value || '').trim();
    key = (document.getElementById('bkey-claude-key')?.value || '').trim();
    providerIndex = 2;
  } else if (type === 'image') {
    btn = document.getElementById('bkey-btn-test-img');
    status = document.getElementById('bkey-status-img');
    let selModel = (document.getElementById('bkey-img-model')?.value || 'gpt-image-2').trim();
    if (selModel === 'custom') {
      selModel = (document.getElementById('bkey-img-model-custom')?.value || 'gpt-image-2').trim();
    }
    model = selModel;
    url = (document.getElementById('bkey-img-url')?.value || '').trim();
    key = (document.getElementById('bkey-img-key')?.value || '').trim();
    if (!url) url = (document.getElementById('bkey-openai-url')?.value || '').trim();
    if (!key) key = (document.getElementById('bkey-openai-key')?.value || '').trim();
    if (url && !url.endsWith('/v1') && !url.includes('/v1') && !url.includes('/codex') && !url.includes('api.deepseek.com')) {
      url = url.replace(/\/+$/, '') + '/v1';
      const inputEl = document.getElementById('bkey-img-url');
      if (inputEl && inputEl.value) inputEl.value = url;
    }

    if (btn) btn.disabled = true;
    if (status) { status.className = 'provider-test-status'; status.textContent = '测试中...'; }
    try {
      const resp = await fetch('/api/ai_test', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ type: 'image', index: 'image', provider: { model, base_url: url, api_key: key } })
      });
      const res = await resp.json();
      if (res.success) {
        status.className = 'provider-test-status ok';
        status.textContent = `✅ 连接成功 (${res.latency_ms || 30}ms)`;
      } else {
        status.className = 'provider-test-status bad';
        let reason = res.reason || res.status || '测试失败';
        if (typeof reason === 'string' && (reason.includes('<html') || reason.includes('<!DOCTYPE') || reason.includes('<!doctype') || reason.includes('non_json_response'))) {
          reason = '接口返回网页(HTML)而非API：缺少 /v1 路径，已自动为您补全 /v1，请重试';
        }
        status.textContent = `❌ ${reason}`;
      }
    } catch (e) {
      if (status) { status.className = 'provider-test-status bad'; status.textContent = `❌ ${e.message}`; }
    } finally {
      if (btn) btn.disabled = false;
    }
    return;
  }

  if (btn) btn.disabled = true;
  if (status) { status.className = 'provider-test-status'; status.textContent = '测试中...'; }
  try {
    const resp = await fetch('/api/ai_test', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        index: providerIndex,
        provider: { model, base_url: url, api_key: key }
      })
    });
    const res = await resp.json();
    if (res.success) {
      status.className = 'provider-test-status ok';
      status.textContent = `✅ 验证通过 (${res.latency_ms || 50}ms)`;
    } else {
      status.className = 'provider-test-status bad';
      let reason = res.reason || res.status || '验证失败';
      if (typeof reason === 'string' && (reason.includes('<html') || reason.includes('<!DOCTYPE') || reason.includes('<!doctype') || reason.includes('non_json_response'))) {
        reason = '接口返回网页(HTML)而非API：缺少 /v1 路径，已自动为您补全 /v1，请重试';
      }
      status.textContent = `❌ ${reason}`;
    }
  } catch (e) {
    if (status) { status.className = 'provider-test-status bad'; status.textContent = `❌ ${e.message}`; }
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function saveBlogAIKeys() {
  const btn = document.getElementById('bkey-btn-save');
  const status = document.getElementById('bkey-save-status');
  if (btn) btn.disabled = true;
  if (status) { status.style.color = '#60a5fa'; status.textContent = '⏳ 正在保存配置并热加载至引擎...'; }

  try {
    const curResp = await fetch('/api/config');
    const curCfg = await curResp.json();
    const providers = (curCfg.ai_committee?.providers || []).map(p => ({...p}));

    // Update DeepSeek (index 0)
    if (providers[0]) {
      providers[0].model = (document.getElementById('bkey-deepseek-model')?.value || providers[0].model).trim();
      providers[0].base_url = (document.getElementById('bkey-deepseek-url')?.value || providers[0].base_url).trim().replace(/\/+$/, '');
      const key0 = (document.getElementById('bkey-deepseek-key')?.value || '').trim();
      if (key0 && key0 !== '***') providers[0].api_key = key0;
    }

    // Update OpenAI (index 1)
    if (providers[1]) {
      providers[1].model = (document.getElementById('bkey-openai-model')?.value || providers[1].model).trim();
      let u1 = (document.getElementById('bkey-openai-url')?.value || providers[1].base_url).trim().replace(/\/+$/, '');
      if (u1 && !u1.endsWith('/v1') && !u1.includes('/v1') && !u1.includes('/codex') && !u1.includes('api.deepseek.com')) {
        u1 = u1 + '/v1';
      }
      providers[1].base_url = u1;
      const key1 = (document.getElementById('bkey-openai-key')?.value || '').trim();
      if (key1 && key1 !== '***') providers[1].api_key = key1;
    }

    // Update Claude (index 2)
    if (providers[2]) {
      providers[2].model = (document.getElementById('bkey-claude-model')?.value || providers[2].model).trim();
      providers[2].base_url = (document.getElementById('bkey-claude-url')?.value || providers[2].base_url).trim().replace(/\/+$/, '');
      const key2 = (document.getElementById('bkey-claude-key')?.value || '').trim();
      if (key2 && key2 !== '***') providers[2].api_key = key2;
    }

    // Image generation payload
    let imgModel = (document.getElementById('bkey-img-model')?.value || 'gpt-image-2').trim();
    if (imgModel === 'custom') {
      imgModel = (document.getElementById('bkey-img-model-custom')?.value || 'gpt-image-2').trim();
    }
    const imgQuality = (document.getElementById('bkey-img-quality')?.value || 'standard').trim();
    let imgUrl = (document.getElementById('bkey-img-url')?.value || '').trim().replace(/\/+$/, '');
    if (imgUrl && !imgUrl.endsWith('/v1') && !imgUrl.includes('/v1') && !imgUrl.includes('/codex') && !imgUrl.includes('api.deepseek.com')) {
      imgUrl = imgUrl + '/v1';
    }
    const imgKey = (document.getElementById('bkey-img-key')?.value || '').trim();

    const imgPayload = {
      model: imgModel,
      quality: imgQuality,
      size: imgModel === 'dall-e-2' ? '1024x1024' : '1792x1024',
      enabled: true
    };
    if (imgUrl) imgPayload.base_url = imgUrl;
    if (imgKey && imgKey !== '***') imgPayload.api_key = imgKey;

    window.blogImageConfig = Object.assign(window.blogImageConfig || {}, imgPayload);

    const payload = {
      ai_committee: {
        ...(curCfg.ai_committee || {}),
        providers,
        image_generation: imgPayload
      }
    };

    const saveResp = await fetch('/api/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    const saveRes = await saveResp.json();
    if (!saveResp.ok || !saveRes.ok) throw new Error(saveRes.error || `HTTP ${saveResp.status}`);

    if (status) {
      status.style.color = '#10b981';
      status.textContent = '✅ 配置已成功保存并即刻生效！';
    }
    setTimeout(() => {
      closeBlogAIKeyModal();
    }, 800);
  } catch (err) {
    if (status) {
      status.style.color = '#ef4444';
      status.textContent = `❌ 保存失败: ${err.message}`;
    }
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function showDailyReport(forceSync=false) {

  try {
    const response = await fetch(`/api/daily_report?sync=true&force=${forceSync}`);
    const report = await response.json();
    if (!response.ok || report.error) throw new Error(report.error || `HTTP ${response.status}`);
    const summary = report.summary || {};
    const netPnl = Number(summary.net_pnl ?? summary.total_pnl ?? 0);
    const bySource = report.by_source || {};
    const sourceSummary = [
      [tr('botManaged'), bySource.bot],
      [tr('externalActivity'), bySource.external],
    ].filter(([, value]) => value && (Number(value.open_count || 0) || Number(value.close_count || 0)))
      .map(([label, value]) => {
        const net = Number(value.net_pnl || 0);
        const color = net >= 0 ? 'var(--green)' : 'var(--red)';
        return `${label}: <b style="color:${color}">${net >= 0 ? '+' : ''}${net.toFixed(4)} U</b> (${Number(value.close_count || 0)} ${tr('closes')})`;
      }).join(' | ');
    const records = (report.records || []).map(record =>
      `<tr><td>${escapeHtml(record.time || '--')}</td><td>${escapeHtml(record.type || '--')}</td>` +
      `<td>${escapeHtml(record.symbol || '--')}</td><td>${escapeHtml(record.side || '--')}</td>` +
      `<td>${escapeHtml(record.qty ?? '--')}</td><td>${escapeHtml(record.reason || '--')}</td></tr>`
    ).join('') || `<tr><td colspan="6" style="text-align:center">${tr('todayNoRecords')}</td></tr>`;
    const overlay = document.createElement('div');
    overlay.className = 'blog-overlay';
    overlay.id = 'report-overlay';
    overlay.onclick = event => { if (event.target === overlay) overlay.remove(); };
    overlay.innerHTML = `
      <div class="blog-modal" style="width:720px;max-width:94vw">
        <div class="blog-head"><span class="t">${tr('report')} ${escapeHtml(report.date || '')}</span><span class="x" onclick="document.getElementById('report-overlay').remove()">?</span></div>
        <div style="padding:14px;overflow:auto">
          <div style="margin-bottom:12px">${tr('netPnl')}: <b style="color:${netPnl >= 0 ? 'var(--green)' : 'var(--red)'}">${netPnl >= 0 ? '+' : ''}${netPnl.toFixed(4)} U</b> | ${tr('winRate')}: ${escapeHtml(summary.win_rate ?? '--')}% | ${tr('sync')}: ${report.sync?.success ? tr('syncSuccess') : tr('syncPending')}</div>
          ${sourceSummary ? `<div style="margin:-4px 0 12px;color:var(--text-2);font-size:12px">${sourceSummary}</div>` : ''}
          <table style="width:100%;border-collapse:collapse;font-size:11px"><thead><tr><th>${tr('time')}</th><th>${tr('type')}</th><th>${tr('symbol')}</th><th>${tr('direction')}</th><th>${tr('quantity')}</th><th>${tr('reason')}</th></tr></thead><tbody>${records}</tbody></table>
          <pre style="white-space:pre-wrap;margin-top:14px;color:var(--text-1)">${escapeHtml(report.ai_summary || '')}</pre>
        </div>
        <div class="blog-foot"><button class="blog-btn" onclick="syncCurrentTradesToObsidian()" style="background:#7c3aed;color:#fff;border-color:#8b5cf6">📓 同步至Obsidian</button><button class="blog-btn" onclick="window.open('/api/export_trades_html?date=${escapeHtml(report.date || '')}','_blank')">${tr('exportHtml')}</button><button class="blog-btn" onclick="window.open('/api/export_trades_md?date=${escapeHtml(report.date || '')}','_blank')">${tr('exportMarkdown')}</button><button class="blog-btn" onclick="showDailyReport(true)">${tr('resync')}</button><button class="blog-btn" onclick="document.getElementById('report-overlay').remove()">${tr('close')}</button></div>
      </div>`;
    document.body.appendChild(overlay);
  } catch (error) {
    alert(tr('reportLoadFailed') + error.message);
  }
}

// ===== Visual Strategy Settings =====
let settingsConfig = null;

function escAttr(value) {
  return String(value ?? '').replace(/&/g,'&amp;').replace(/"/g,'&quot;')
    .replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function closeSettings() {
  const overlay = document.getElementById('settings-overlay');
  if (overlay) overlay.remove();
}

const STRATEGY_PRESETS = {
  conservative: {
    key: 'conservative',
    name: '稳健防守型',
    name_en: 'Conservative',
    icon: '🛡️',
    tag: '新手/防插针',
    tag_en: 'Defensive',
    desc: '低杠杆 · 10% 仓位 · 宽 ATR 防插针止损 · 5% 严格日损熔断。',
    desc_en: 'Low leverage · 10% pos · Wide ATR stops · Strict 5% daily loss cap.',
    values: {
      leverage: 3,
      position_size: 10,
      daily_loss: 5,
      tp1_atr: 1.2,
      tp2_atr: 2.0,
      partial_close: 50,
      trailing_atr: 1.2,
      trail_after_tp: 1,
      initial_stop_atr: 3.0,
      hard_stop_pct: 4.0,
      stop_confirmations: 2,
      signal_threshold: 48,
      scan_threshold: 45,
      min_atr_pct: 1.0,
      min_vol_surge: 0.3,
      min_volume: 5000000,
      max_spread: 6,
      max_pos: 2
    }
  },
  trend_swing: {
    key: 'trend_swing',
    name: '趋势波段型',
    name_en: 'Trend Swing',
    icon: '⚔️',
    tag: '主攻大行情 (推荐)',
    tag_en: 'Recommended',
    desc: '6x 杠杆 · 18% 仓位 · 动态追踪止损让利润奔跑 · 高周期共振。',
    desc_en: '6x lev · 18% pos · Trailing stops to ride trends · HTF confirmation.',
    values: {
      leverage: 6,
      position_size: 18,
      daily_loss: 7.5,
      tp1_atr: 1.5,
      tp2_atr: 2.5,
      partial_close: 50,
      trailing_atr: 1.0,
      trail_after_tp: 1,
      initial_stop_atr: 2.5,
      hard_stop_pct: 6.0,
      stop_confirmations: 2,
      signal_threshold: 40,
      scan_threshold: 40,
      min_atr_pct: 1.2,
      min_vol_surge: 0.2,
      min_volume: 3000000,
      max_spread: 8,
      max_pos: 3
    }
  },
  aggressive: {
    key: 'aggressive',
    name: '激进突破型',
    name_en: 'Aggressive',
    icon: '⚡',
    tag: '抓放量突破',
    tag_en: 'Momentum',
    desc: '8x 杠杆 · 25% 仓位 · 紧凑止损博弈放量波动率扩张 · 快进快出。',
    desc_en: '8x lev · 25% pos · Tight stops for volatility breakout · High velocity.',
    values: {
      leverage: 8,
      position_size: 25,
      daily_loss: 10,
      tp1_atr: 2.0,
      tp2_atr: 3.5,
      partial_close: 35,
      trailing_atr: 0.8,
      trail_after_tp: 1,
      initial_stop_atr: 1.8,
      hard_stop_pct: 4.5,
      stop_confirmations: 1,
      signal_threshold: 35,
      scan_threshold: 35,
      min_atr_pct: 1.8,
      min_vol_surge: 0.5,
      min_volume: 8000000,
      max_spread: 5,
      max_pos: 4
    }
  },
  ai_evolved: {
    key: 'ai_evolved',
    name: 'AI 自动进化',
    name_en: 'AI Evolved',
    icon: '🤖',
    tag: '历史回测实算',
    tag_en: 'Backtest Optimized',
    desc: '自动提取最新历史 K 线回测中样本外夏普最高的演化参数一键同步。',
    desc_en: 'Auto-loads optimal params with highest Out-of-Sample Sharpe from backtest history.',
    is_dynamic: true
  }
};

function syncCoreSlider(type, val) {
  const num = Number(val);
  if (type === 'leverage') {
    const range = document.getElementById('set-leverage-range');
    const input = document.getElementById('set-leverage');
    const badge = document.getElementById('val-badge-leverage');
    if (range) range.value = num;
    if (input) input.value = num;
    if (badge) badge.textContent = num + 'x';
  } else if (type === 'pos-size') {
    const range = document.getElementById('set-position-size-range');
    const input = document.getElementById('set-position-size');
    const badge = document.getElementById('val-badge-pos-size');
    if (range) range.value = num;
    if (input) input.value = num;
    if (badge) badge.textContent = num + '%';
  } else if (type === 'daily-loss') {
    const range = document.getElementById('set-max-daily-loss-range');
    const input = document.getElementById('set-max-daily-loss');
    const badge = document.getElementById('val-badge-daily-loss');
    if (range) range.value = num;
    if (input) input.value = num;
    if (badge) badge.textContent = num + '%';
  }
}

function updateInputsWithValues(vals) {
  if (!vals) return;
  const setVal = (id, v) => {
    const el = document.getElementById(id);
    if (el && v !== undefined) {
      el.value = v;
      el.dispatchEvent(new Event('input'));
      el.dispatchEvent(new Event('change'));
    }
  };

  if (vals.leverage !== undefined) syncCoreSlider('leverage', vals.leverage);
  if (vals.position_size !== undefined) syncCoreSlider('pos-size', vals.position_size);
  if (vals.daily_loss !== undefined) syncCoreSlider('daily-loss', vals.daily_loss);

  if (vals.tp1_atr !== undefined) setVal('set-tp1-atr', vals.tp1_atr);
  if (vals.tp2_atr !== undefined) setVal('set-tp2-atr', vals.tp2_atr);
  if (vals.partial_close !== undefined) setVal('set-partial-close', vals.partial_close);
  if (vals.trailing_atr !== undefined) setVal('set-trailing-atr', vals.trailing_atr);
  if (vals.trail_after_tp !== undefined) setVal('set-trail-after-tp', vals.trail_after_tp);
  if (vals.initial_stop_atr !== undefined) setVal('set-initial-stop-atr', vals.initial_stop_atr);
  if (vals.hard_stop_pct !== undefined) setVal('set-hard-stop-pct', vals.hard_stop_pct);
  if (vals.stop_confirmations !== undefined) setVal('set-stop-confirmations', vals.stop_confirmations);
  if (vals.signal_threshold !== undefined) setVal('set-signal-th', vals.signal_threshold);
  if (vals.scan_threshold !== undefined) setVal('set-scan-th', vals.scan_threshold);
  if (vals.min_atr_pct !== undefined) setVal('set-min-atr', vals.min_atr_pct);
  if (vals.min_vol_surge !== undefined) setVal('set-min-vol-surge', vals.min_vol_surge);
  if (vals.min_volume !== undefined) setVal('set-min-volume', vals.min_volume);
  if (vals.max_spread !== undefined) setVal('set-max-spread', vals.max_spread);
  if (vals.max_pos !== undefined) setVal('set-max-pos', vals.max_pos);
}

async function selectPreset(key) {
  document.querySelectorAll('.preset-card').forEach(c => c.classList.remove('active'));
  const card = document.getElementById(`preset-card-${key}`);
  if (card) card.classList.add('active');

  const preset = STRATEGY_PRESETS[key];
  if (!preset) return;

  const status = document.getElementById('settings-status');
  if (preset.is_dynamic) {
    if (status) {
      status.textContent = '⏳ 正在读取最新历史数据样本外最佳演化参数...';
      status.style.color = 'var(--blue)';
    }
    try {
      const res = await fetch('/api/strategies/candidates');
      const data = await res.json();
      const candidates = data.candidates || [];
      const best = candidates.reduce((prev, curr) => {
        const prevSharpe = prev?.backtest?.oos_sharpe ?? -999;
        const currSharpe = curr?.backtest?.oos_sharpe ?? -999;
        return currSharpe > prevSharpe ? curr : prev;
      }, null);

      if (best && best.params) {
        updateInputsWithValues({
          leverage: 6,
          position_size: 18,
          daily_loss: 7.5,
          signal_threshold: 40,
          ...best.params
        });
        if (status) {
          status.textContent = `✓ 已套用最优进化模型：${best.title || best.name} (样本外夏普: ${best.backtest?.oos_sharpe?.toFixed(2) || '优秀'})`;
          status.style.color = 'var(--green)';
        }
        return;
      }
    } catch (e) {
      console.warn('Failed to load candidate strategy:', e);
    }
  }

  updateInputsWithValues(preset.values);
  if (status) {
    const isZh = currentLanguage === 'zh-CN';
    status.textContent = isZh ? `✓ 已套用「${preset.name}」场景预设参数` : `✓ Applied preset: ${preset.name_en}`;
    status.style.color = 'var(--green)';
  }
}

async function openSettings() {
  try {
    const response = await fetch('/api/config');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    settingsConfig = await response.json();
    const strategy = settingsConfig.strategy || {};
    const selection = strategy.market_selection || {};
    const liquidity = strategy.liquidity || {};
    const pm = strategy.position_management || {};
    const execution = settingsConfig.execution || {};
    const risk = settingsConfig.risk || {};
    const providers = settingsConfig.ai_committee?.providers || [];
    const isZh = currentLanguage === 'zh-CN';

    const providerHtml = providers.map((provider, index) => {
      let roleBadge = '🤖 独立决策评审';
      let roleDesc = '独立审查行情与技术面特征，提供客观决策参考';
      const nameLower = (provider.name || '').toLowerCase();
      const modelLower = (provider.model || '').toLowerCase();
      const roleLower = (provider.role || '').toLowerCase();

      if (nameLower.includes('claude') || modelLower.includes('claude') || roleLower.includes('risk') || roleLower.includes('execution')) {
        roleBadge = '🛡️ 首席风控官 (开仓一票否决)';
        roleDesc = '开仓信号发出前异步审查资金费率偏离、大户背离与诱多风险，一票否决高危单。';
      } else if (nameLower.includes('deepseek') || modelLower.includes('deepseek') || modelLower.includes('grok') || roleLower.includes('momentum') || roleLower.includes('reversion')) {
        roleBadge = '🧬 数据精算师 (历史回测与诊断)';
        roleDesc = '深度归因复盘历史止损与失败单，诊断参数瓶颈，驱动策略参数自动进化演进。';
      } else if (nameLower.includes('openai') || modelLower.includes('gpt') || roleLower.includes('trend')) {
        roleBadge = '✍️ 行情解盘师 (币安广场主笔)';
        roleDesc = '抓取实盘打点与盈亏战报，自动撰写币安广场引流长文与 Obsidian 交易日记。';
      }

      return `
        <div class="provider-card">
          <div class="provider-name">
            <span class="provider-role-badge">${roleBadge}</span>
            <span class="provider-dot"></span>
          </div>
          <div class="provider-role-desc">${roleDesc}</div>
          <div class="settings-field"><label data-i18n="model">${tr('model')}</label><input id="sp-model-${index}" value="${escapeHtml(provider.model || '')}"></div>
          <div class="settings-field"><label data-i18n="apiUrl">${tr('apiUrl')}</label><input id="sp-url-${index}" value="${escapeHtml(provider.base_url || '')}"></div>
          <div class="settings-field"><label data-i18n="apiKey">${tr('apiKey')}</label><input id="sp-key-${index}" data-i18n-placeholder="${provider.api_key_configured ? 'keyConfigured' : 'keyInput'}" type="password" placeholder="${provider.api_key_configured ? tr('keyConfigured') : tr('keyInput')}"></div>
          <div class="provider-test-row"><button class="provider-test-btn" id="sp-test-btn-${index}" data-i18n="test" onclick="testProvider(${index})">${tr('test')}</button><span class="provider-test-status" id="sp-test-status-${index}"></span></div>
        </div>`;
    }).join('');

    const imgGen = settingsConfig.ai_committee?.image_generation || {};
    const imgCard = `
      <div class="provider-card" style="border:1px solid rgba(168,85,247,.35);background:rgba(168,85,247,.04)">
        <div class="provider-name">
          <span class="provider-role-badge" style="background:rgba(168,85,247,.2);color:#c084fc;border:1px solid rgba(168,85,247,.4)">🎨 视觉美术师 (DALL-E 图像生成)</span>
          <span class="provider-dot" style="background:#a855f7"></span>
        </div>
        <div class="provider-role-desc">为币安广场深度研报与快讯实时绘制 16:9 高清封面与科技感走势插图。</div>
        <div class="settings-field"><label>模型名称 (Model)</label><input id="sp-img-model" value="${escapeHtml(imgGen.model || 'gpt-image-2')}"></div>
        <div class="settings-field"><label>API 地址 (Base URL)</label><input id="sp-img-url" value="${escapeHtml(imgGen.base_url || '')}" placeholder="留空默认复用 OpenAI 主地址"></div>
        <div class="settings-field"><label>API Key</label><input id="sp-img-key" type="password" placeholder="${imgGen.api_key_configured ? tr('keyConfigured') : 'sk-... (留空复用OpenAI Key)'}"></div>
        <div class="provider-test-row"><button class="provider-test-btn" id="sp-img-test-btn" onclick="testImageProvider()">${tr('test')}</button><span class="provider-test-status" id="sp-img-test-status"></span></div>
      </div>`;
    const finalProviderHtml = providerHtml + imgCard;

    const overlay = document.createElement('div');
    overlay.className = 'settings-overlay';
    overlay.id = 'settings-overlay';
    overlay.innerHTML = `
      <div class="settings-modal">
        <div class="settings-head">
          <div class="settings-title">
            <strong data-i18n="settingsTitle">${tr('settingsTitle')}</strong>
            <span data-i18n="settingsInstant">${tr('settingsInstant')}</span>
          </div>
          <div style="display:flex;align-items:center;gap:6px">
            <div class="locale-switch">
              <button class="locale-btn ${currentLanguage==='zh-CN'?'active':''}" data-locale="zh-CN" onclick="setLanguage('zh-CN')">中</button>
              <button class="locale-btn ${currentLanguage==='en-US'?'active':''}" data-locale="en-US" onclick="setLanguage('en-US')">EN</button>
            </div>
            <button class="settings-close" onclick="closeSettings()">✕</button>
          </div>
        </div>
        <div class="settings-body">
          <!-- 0. 网络代理与端口设置 (Proxy) -->
          <div class="settings-section" style="background:rgba(59,130,246,0.05);border:1px solid rgba(59,130,246,0.3);border-radius:8px;padding:12px 14px;margin-bottom:14px;">
            <div class="settings-section-title" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
              <span style="color:#60a5fa;font-weight:700;font-size:13px;">🌐 网络代理与端口配置 (Proxy)</span>
              <small style="color:var(--text-2);">连接币安期货 API 必需的网络通道 (支持自定义任意端口)</small>
            </div>
            <div style="display:flex;flex-direction:column;gap:8px;">
              <div class="settings-field">
                <label style="display:flex;align-items:center;justify-content:space-between;">
                  <span>代理服务器地址及端口 (HTTP / SOCKS5)</span>
                  <span style="font-size:11px;color:var(--text-2);">当前生效: ${escapeHtml(settingsConfig.proxy || '未配置 (直连)')}</span>
                </label>
                <div style="display:flex;gap:8px;">
                  <input id="set-proxy" value="${escapeHtml(settingsConfig.proxy || '')}" placeholder="例如: http://127.0.0.1:7890 (留空为直连)" style="flex:1;background:rgba(0,0,0,0.25);border:1px solid var(--border);border-radius:6px;padding:8px 10px;color:var(--text-0);">
                  <button type="button" class="provider-test-btn" id="btn-test-proxy" onclick="testProxyConnection()" style="background:#2563eb;color:#fff;border:none;padding:0 14px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;white-space:nowrap;transition:background .2s;">
                    ⚡ 测试连接 & 检测出口IP
                  </button>
                </div>
              </div>
              <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px;font-size:11px;margin-top:2px;">
                <div style="display:flex;align-items:center;gap:6px;">
                  <span style="color:var(--text-2);">快速切换端口:</span>
                  <button type="button" style="padding:3px 9px;border-radius:4px;border:1px solid rgba(59,130,246,.4);background:rgba(59,130,246,.15);color:#93c5fd;cursor:pointer;font-size:11px;" onclick="setQuickProxy('7890')">FlClash (7890)</button>
                  <button type="button" style="padding:3px 9px;border-radius:4px;border:1px solid rgba(255,255,255,.15);background:rgba(255,255,255,.05);color:var(--text-1);cursor:pointer;font-size:11px;" onclick="setQuickProxy('7897')">Clash Verge (7897)</button>
                  <button type="button" style="padding:3px 9px;border-radius:4px;border:1px solid rgba(255,255,255,.15);background:rgba(255,255,255,.05);color:var(--text-1);cursor:pointer;font-size:11px;" onclick="setQuickProxy('10809')">v2rayN (10809)</button>
                  <button type="button" style="padding:3px 9px;border-radius:4px;border:1px solid rgba(239,68,68,.3);background:rgba(239,68,68,.1);color:#fca5a5;cursor:pointer;font-size:11px;" onclick="setQuickProxy('')">清空 (直连)</button>
                </div>
                <div id="proxy-test-status" style="font-size:11px;font-weight:600;"></div>
              </div>
            </div>
          </div>

          <!-- 1. 场景化一键预设 -->
          <div class="settings-section" style="background:rgba(139,92,246,0.06);border-color:rgba(139,92,246,0.3)">
            <div class="settings-section-title">
              <span style="color:#c4b5fd" data-i18n="presetsTitle">${tr('presetsTitle')}</span>
              <small data-i18n="presetsSubtitle">${tr('presetsSubtitle')}</small>
            </div>
            <div class="preset-grid">
              <div class="preset-card" id="preset-card-conservative" onclick="selectPreset('conservative')">
                <div class="preset-card-head">
                  <span class="preset-card-title">🛡️ 稳健防守型</span>
                  <span class="preset-card-tag">新手/防插针</span>
                </div>
                <div class="preset-card-desc">3x 杠杆 · 10% 仓位 · 宽 ATR 防插针止损 · 5% 严格日损熔断。</div>
              </div>
              <div class="preset-card active" id="preset-card-trend_swing" onclick="selectPreset('trend_swing')">
                <div class="preset-card-head">
                  <span class="preset-card-title">⚔️ 趋势波段型</span>
                  <span class="preset-card-tag">主攻大行情 (推荐)</span>
                </div>
                <div class="preset-card-desc">6x 杠杆 · 18% 仓位 · 动态追踪止损让利润奔跑 · 高周期共振。</div>
              </div>
              <div class="preset-card" id="preset-card-aggressive" onclick="selectPreset('aggressive')">
                <div class="preset-card-head">
                  <span class="preset-card-title">⚡ 激进突破型</span>
                  <span class="preset-card-tag">抓放量突破</span>
                </div>
                <div class="preset-card-desc">8x 杠杆 · 25% 仓位 · 紧凑止损博弈放量波动率扩张 · 快进快出。</div>
              </div>
              <div class="preset-card" id="preset-card-ai_evolved" onclick="selectPreset('ai_evolved')">
                <div class="preset-card-head">
                  <span class="preset-card-title">🤖 AI 自动进化</span>
                  <span class="preset-card-tag" style="background:rgba(16,185,129,.2);color:#6ee7b7">历史回测实算</span>
                </div>
                <div class="preset-card-desc">自动提取最新历史 K 线回测中样本外夏普最高的演化参数一键同步。</div>
              </div>
            </div>
          </div>

          <!-- 2. 日常核心控制条 (三滑块) -->
          <div class="settings-section">
            <div class="settings-section-title">
              <span data-i18n="coreControlsTitle">${tr('coreControlsTitle')}</span>
              <small style="color:var(--blue)">与预设实时联动</small>
            </div>
            <div class="settings-core-strip">
              <div class="core-slider-card">
                <div class="core-slider-header">
                  <label data-i18n="defaultLeverage">${tr('defaultLeverage')}</label>
                  <span class="core-value-badge" id="val-badge-leverage">${Number(settingsConfig.leverage ?? 6)}x</span>
                </div>
                <div class="core-slider-controls">
                  <input type="range" id="set-leverage-range" min="1" max="20" step="1" value="${Number(settingsConfig.leverage ?? 6)}" oninput="syncCoreSlider('leverage', this.value)">
                  <input type="number" id="set-leverage" min="1" max="20" step="1" value="${Number(settingsConfig.leverage ?? 6)}" oninput="syncCoreSlider('leverage', this.value)">
                </div>
              </div>
              <div class="core-slider-card">
                <div class="core-slider-header">
                  <label data-i18n="positionSize">${tr('positionSize')}</label>
                  <span class="core-value-badge" id="val-badge-pos-size">${Number(risk.position_size_pct ?? 18)}%</span>
                </div>
                <div class="core-slider-controls">
                  <input type="range" id="set-position-size-range" min="1" max="50" step="1" value="${Number(risk.position_size_pct ?? 18)}" oninput="syncCoreSlider('pos-size', this.value)">
                  <input type="number" id="set-position-size" min="1" max="50" step="1" value="${Number(risk.position_size_pct ?? 18)}" oninput="syncCoreSlider('pos-size', this.value)">
                </div>
              </div>
              <div class="core-slider-card">
                <div class="core-slider-header">
                  <label data-i18n="dailyLossStop">${tr('dailyLossStop')}</label>
                  <span class="core-value-badge" id="val-badge-daily-loss" style="color:var(--red)">${Number(risk.max_daily_loss_pct ?? 7.5)}%</span>
                </div>
                <div class="core-slider-controls">
                  <input type="range" id="set-max-daily-loss-range" min="1" max="30" step="0.5" value="${Number(risk.max_daily_loss_pct ?? 7.5)}" oninput="syncCoreSlider('daily-loss', this.value)">
                  <input type="number" id="set-max-daily-loss" min="1" max="30" step="0.5" value="${Number(risk.max_daily_loss_pct ?? 7.5)}" oninput="syncCoreSlider('daily-loss', this.value)">
                </div>
              </div>
            </div>
          </div>

          <!-- 3. 高级底层量化参数 (折叠面板) -->
          <details class="settings-advanced-details">
            <summary class="settings-advanced-summary">
              <span>▼ <span data-i18n="advancedQuantTitle">${tr('advancedQuantTitle')}</span></span>
              <small style="color:var(--text-2);font-weight:normal">点击展开/收起 18 项底层参数</small>
            </summary>
            <div class="settings-advanced-content">
              <div class="settings-section" style="margin-bottom:10px;background:rgba(26,34,53,.35)">
                <div class="settings-section-title"><span data-i18n="selection">${tr('selection')}</span></div>
                <div class="settings-grid">
                  <div class="settings-field wide"><label data-i18n="symbolsLabel">${tr('symbolsLabel')}</label><input id="set-symbols" value="${escapeHtml((settingsConfig.symbols || []).join(','))}"></div>
                  <div class="settings-field"><label data-i18n="signalThreshold">${tr('signalThreshold')}</label><input id="set-signal-th" type="number" min="0" max="100" value="${Number(strategy.signal_threshold ?? 40)}"></div>
                  <div class="settings-field"><label data-i18n="scanThreshold">${tr('scanThreshold')}</label><input id="set-scan-th" type="number" min="0" max="100" value="${Number(strategy.scan_threshold ?? 40)}"></div>
                  <div class="settings-field"><label data-i18n="maxPrice">${tr('maxPrice')}</label><input id="set-max-price" type="number" min="0.001" step=".01" value="${Number(selection.max_price ?? 10)}"></div>
                  <div class="settings-field"><label data-i18n="minVolatility">${tr('minVolatility')}</label><input id="set-min-atr" type="number" min="0.1" step=".1" value="${Number(selection.min_atr_pct ?? 1.2)}"></div>
                  <div class="settings-field"><label data-i18n="minVolumeSurge">${tr('minVolumeSurge')}</label><input id="set-min-vol-surge" type="number" min="0.1" step=".1" value="${Number(selection.min_vol_surge ?? 0.2)}"></div>
                  <div class="settings-field"><label data-i18n="candidateScanLimit">${tr('candidateScanLimit')}</label><input id="set-candidate-scan-limit" type="number" min="20" max="120" step="10" value="${Number(selection.candidate_scan_limit ?? 80)}"></div>
                  <div class="settings-field"><label data-i18n="minVolume24h">${tr('minVolume24h')}</label><input id="set-min-volume" type="number" min="0" step="1000000" value="${Number(liquidity.min_quote_volume_24h ?? 3000000)}"></div>
                  <div class="settings-field"><label data-i18n="maxSpread">${tr('maxSpread')}</label><input id="set-max-spread" type="number" min="1" step="1" value="${Number(liquidity.max_spread_bps ?? 8)}"></div>
                  <div class="settings-toggle"><input id="set-allow-all-symbols" type="checkbox" ${selection.allow_all_symbols ? 'checked' : ''}><label data-i18n="useAllSymbols">${tr('useAllSymbols')}</label></div>
                </div>
              </div>
              <div class="settings-section" style="margin-bottom:10px;background:rgba(26,34,53,.35)">
                <div class="settings-section-title"><span data-i18n="positionManagement">${tr('positionManagement')}</span></div>
                <div class="settings-grid">
                  <div class="settings-field"><label data-i18n="tp1Atr">${tr('tp1Atr')}</label><input id="set-tp1-atr" type="number" min="0.5" step=".25" value="${Number(pm.tp1_atr ?? 1.5)}"></div>
                  <div class="settings-field"><label data-i18n="tp2Atr">${tr('tp2Atr')}</label><input id="set-tp2-atr" type="number" min="1.0" step=".25" value="${Number(pm.tp2_atr ?? 2.5)}"></div>
                  <div class="settings-field"><label data-i18n="partialClose">${tr('partialClose')}</label><input id="set-partial-close" type="number" min="10" max="100" step="5" value="${Number(pm.partial_close_pct ?? 50)}"></div>
                  <div class="settings-field"><label data-i18n="trailingAtr">${tr('trailingAtr')}</label><input id="set-trailing-atr" type="number" min="0.5" step=".25" value="${Number(pm.trailing_atr ?? 1)}"></div>
                  <div class="settings-field"><label data-i18n="trailAfterTp">${tr('trailAfterTp')}</label><select id="set-trail-after-tp"><option value="1" ${Number(pm.trail_after_tp ?? 1)===1?'selected':''}>TP1</option><option value="2" ${Number(pm.trail_after_tp ?? 1)===2?'selected':''}>TP2</option></select></div>
                  <div class="settings-field"><label data-i18n="initialStopAtr">${tr('initialStopAtr')}</label><input id="set-initial-stop-atr" type="number" min="1" step=".25" value="${Number(pm.initial_stop_atr ?? 2.5)}"></div>
                  <div class="settings-field"><label data-i18n="hardStop">${tr('hardStop')}</label><input id="set-hard-stop-pct" type="number" min="1" step=".25" value="${Number(pm.hard_stop_pct ?? 6)}"></div>
                  <div class="settings-field"><label data-i18n="stopConfirmations">${tr('stopConfirmations')}</label><input id="set-stop-confirmations" type="number" min="1" max="5" step="1" value="${Number(pm.stop_confirmation_candles ?? 2)}"></div>
                </div>
              </div>
              <div class="settings-section" style="margin-bottom:0;background:rgba(26,34,53,.35)">
                <div class="settings-section-title"><span data-i18n="execution">${tr('execution')}</span></div>
                <div class="settings-grid">
                  <div class="settings-toggle"><input id="set-isolated-margin" type="checkbox" ${String(execution.margin_mode || 'ISOLATED').toUpperCase()==='ISOLATED'?'checked':''}><label data-i18n="isolatedMargin">${tr('isolatedMargin')}</label></div>
                  <div class="settings-field"><label data-i18n="minNotionalBuffer">${tr('minNotionalBuffer')}</label><input id="set-min-notional-buffer" type="number" min="0" max="10" step=".5" value="${Number(execution.min_notional_buffer_pct ?? 2)}"></div>
                  <div class="settings-field"><label data-i18n="maxNotionalOvershoot">${tr('maxNotionalOvershoot')}</label><input id="set-max-notional-overshoot" type="number" min="0" max="50" step="1" value="${Number(execution.max_notional_overshoot_pct ?? 18)}"></div>
                  <div class="settings-field"><label data-i18n="maxPositions">${tr('maxPositions')}</label><input id="set-max-pos" type="number" min="1" max="10" value="${Number(risk.max_positions ?? 3)}"></div>
                </div>
              </div>
            </div>
          </details>

          <!-- 4. TypeSafe Jev (System One) 智能决策门禁 -->
          <div class="settings-section" style="border:1px solid rgba(14,165,233,.35);background:rgba(14,165,233,.04);border-radius:8px;padding:12px 14px;margin-bottom:14px;">
            <div class="settings-section-title" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
              <div>
                <span style="color:#0ea5e9;font-weight:700;font-size:13px;">🧠 TypeSafe Jev (System One) 智能决策门禁</span>
                <small style="color:var(--text-2);display:block;margin-top:2px;">非生成式直连模型 · 毫秒级并行原子评估 · 真数学置信度门禁</small>
              </div>
              <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:11px;font-weight:600;color:var(--text-1);background:rgba(14,165,233,.12);padding:4px 10px;border-radius:6px;border:1px solid rgba(14,165,233,.3);">
                <input type="checkbox" id="set-typesafe-enabled" ${settingsConfig.typesafe?.enabled ? 'checked' : ''} style="width:16px;height:16px;accent-color:#0ea5e9">
                <span>开启 Jev 决策门禁</span>
              </label>
            </div>
            
            <div class="settings-grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px;">
              <div class="settings-field">
                <label>目标模型</label>
                <input id="set-typesafe-model" value="${escapeHtml(settingsConfig.typesafe?.model || 'jev-latest')}" placeholder="jev-latest">
              </div>
              <div class="settings-field">
                <label>TypeSafe API Key</label>
                <input id="set-typesafe-key" type="password" placeholder="${settingsConfig.typesafe?.api_key_configured ? '已配置 (留空保持现有Key)' : '请输入 API Key'}">
              </div>
              <div class="settings-field">
                <label title="0~1，默认0.65。只有模型置信度高于此值才准许执行">最小置信度门槛</label>
                <input id="set-typesafe-conf" type="number" step="0.05" min="0.5" max="0.99" value="${settingsConfig.typesafe?.min_confidence ?? 0.65}">
              </div>
              <div class="settings-field">
                <label title="0~4，默认2.5。若风险评估高于此分值则一票否决拦截">最大风险分上限</label>
                <input id="set-typesafe-risk" type="number" step="0.1" min="1.0" max="4.0" value="${settingsConfig.typesafe?.max_risk_score ?? 2.5}">
              </div>
              <div class="settings-field">
                <label title="0~4，默认1.8。突破或顺势单需达到此质量分才允许入场">突破质量门槛</label>
                <input id="set-typesafe-breakout" type="number" step="0.1" min="0.5" max="4.0" value="${settingsConfig.typesafe?.min_breakout_score ?? 1.8}">
              </div>
              <div class="settings-field">
                <label>超时时间 (秒)</label>
                <input id="set-typesafe-timeout" type="number" step="1" min="3" max="30" value="${settingsConfig.typesafe?.timeout_seconds ?? 8}">
              </div>
              <div class="settings-field" style="grid-column: 1 / -1; background: rgba(14,165,233,.08); padding: 9px 12px; border-radius: 6px; border: 1px dashed rgba(14,165,233,.35); margin-top: 4px;">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
                  <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-weight:600;color:#0284c7;font-size:12px;">
                    <input type="checkbox" id="set-typesafe-playbook" ${settingsConfig.typesafe?.use_obsidian_playbook !== false ? 'checked' : ''} style="width:15px;height:15px;accent-color:#0ea5e9">
                    <span>📚 挂载本地 Obsidian 策略脑图 (E:\量化)</span>
                  </label>
                  <span style="font-size:10px;color:var(--text-2);">实时抽取 7套实战策略规则 & 交易习惯纪律</span>
                </div>
                <div style="display:grid;grid-template-columns: 1fr 1fr;gap:10px;">
                  <div>
                    <label style="font-size:11px;" title="0~4分，默认1.5分。低于此契合度将一票否决拦截">策略契合度门槛 (0~4分)</label>
                    <input id="set-typesafe-min-playbook" type="number" step="0.1" min="0.5" max="4.0" value="${settingsConfig.typesafe?.min_playbook_score ?? 1.5}">
                  </div>
                  <div>
                    <label style="font-size:11px;" title="0~1，默认0.45。违背交易习惯或追高冲动概率高于此值则拦截">习惯违规警戒上限 (0~1)</label>
                    <input id="set-typesafe-max-violation" type="number" step="0.05" min="0.1" max="0.9" value="${settingsConfig.typesafe?.max_violation_prob ?? 0.45}">
                  </div>
                </div>
              </div>
            </div>

            <div style="display:flex;align-items:center;justify-content:space-between;margin-top:10px;padding-top:8px;border-top:1px dashed rgba(14,165,233,.2);">
              <button type="button" class="provider-test-btn" id="btn-test-typesafe" onclick="testTypeSafeConnection()" style="background:#0ea5e9;color:#fff;border:none;padding:5px 12px;border-radius:4px;cursor:pointer;font-size:11px;font-weight:600;">
                ⚡ 测试 TypeSafe 连通性
              </button>
              <span id="typesafe-test-status" style="font-size:11px;font-weight:500;"></span>
            </div>
          </div>

          <!-- 5. 传统 AI 模型分工矩阵 -->
          <div class="settings-section">
            <div class="settings-section-title">
              <span data-i18n="aiMatrixTitle">${tr('aiMatrixTitle')}</span>
              <small data-i18n="aiMatrixSubtitle">${tr('aiMatrixSubtitle')}</small>
            </div>
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;padding:9px 12px;background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.25);border-radius:7px;">
              <label style="display:flex;align-items:center;gap:8px;font-size:11px;cursor:pointer;">
                <input type="checkbox" id="set-ai-committee-enabled" ${settingsConfig.ai_committee?.enabled ? 'checked' : ''} style="width:16px;height:16px;accent-color:var(--blue)">
                <strong data-i18n="aiCommitteeGateToggle">${tr('aiCommitteeGateToggle')}</strong>
              </label>
              <span style="font-size:10px;color:var(--text-2);" data-i18n="aiCommitteeGateHint">${tr('aiCommitteeGateHint')}</span>
            </div>
            <div class="provider-grid">${finalProviderHtml || `<div class="empty-state" data-i18n="noModels">${tr('noModels')}</div>`}</div>
          </div>
        </div>
        <div class="settings-foot">
          <span class="settings-status" id="settings-status" data-i18n="loaded">${tr('loaded')}</span>
          <div class="settings-actions">
            <button class="settings-action" data-i18n="cancel" onclick="closeSettings()">${tr('cancel')}</button>
            <button class="settings-action primary" id="settings-save" data-i18n="save" onclick="saveSettings()">${tr('save')}</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(overlay);
  } catch (error) {
    alert('设置加载失败: ' + error.message);
  }
}

function closeSettings() {
  const overlay = document.getElementById('settings-overlay');
  if (overlay) overlay.remove();
}

async function saveSettings() {
  const status = document.getElementById('settings-status');
  const button = document.getElementById('settings-save');
  button.disabled = true;
  try {
    const config = settingsConfig || {};
    const strategy = config.strategy || {};
    const providers = (config.ai_committee?.providers || []).map((old, index) => {
      const provider = {...old};
      delete provider.api_key_configured;
      if (provider.api_key === '***') delete provider.api_key;
      provider.model = document.getElementById(`sp-model-${index}`).value.trim();
      let u = document.getElementById(`sp-url-${index}`).value.trim().replace(/\/+$/, '');
      if (u && !u.endsWith('/v1') && !u.includes('/v1') && !u.includes('/codex') && !u.includes('api.deepseek.com')) {
        u = u + '/v1';
      }
      provider.base_url = u;
      const key = document.getElementById(`sp-key-${index}`).value.trim();
      if (key) provider.api_key = key;
      return provider;
    });
    const symbols = document.getElementById('set-symbols').value.split(',').map(value => value.trim().toUpperCase().replace(/\//g, '')).filter(Boolean);
    const isAiCommitteeEnabled = Boolean(document.getElementById('set-ai-committee-enabled')?.checked);
    const isTypeSafeEnabled = Boolean(document.getElementById('set-typesafe-enabled')?.checked);
    const tsKey = (document.getElementById('set-typesafe-key')?.value || '').trim();
    const typesafePayload = {
      ...(config.typesafe || {}),
      enabled: isTypeSafeEnabled,
      model: (document.getElementById('set-typesafe-model')?.value || 'jev-latest').trim(),
      min_confidence: Number(document.getElementById('set-typesafe-conf')?.value || 0.65),
      max_risk_score: Number(document.getElementById('set-typesafe-risk')?.value || 2.5),
      min_breakout_score: Number(document.getElementById('set-typesafe-breakout')?.value || 1.8),
      timeout_seconds: Number(document.getElementById('set-typesafe-timeout')?.value || 8),
      use_obsidian_playbook: Boolean(document.getElementById('set-typesafe-playbook')?.checked),
      min_playbook_score: Number(document.getElementById('set-typesafe-min-playbook')?.value || 1.5),
      max_violation_prob: Number(document.getElementById('set-typesafe-max-violation')?.value || 0.45),
    };
    if (tsKey) {
      typesafePayload.api_key = tsKey;
    }
    const imgModel = (document.getElementById('sp-img-model')?.value || 'gpt-image-2').trim();
    let imgUrl = (document.getElementById('sp-img-url')?.value || '').trim().replace(/\/+$/, '');
    if (imgUrl && !imgUrl.endsWith('/v1') && !imgUrl.includes('/v1') && !imgUrl.includes('/codex') && !imgUrl.includes('api.deepseek.com')) {
      imgUrl = imgUrl + '/v1';
    }
    const imgKey = (document.getElementById('sp-img-key')?.value || '').trim();
    const curImg = config.ai_committee?.image_generation || {};
    const imageGenPayload = {
      ...curImg,
      model: imgModel,
      size: curImg.size || '1792x1024',
      quality: curImg.quality || 'standard',
      enabled: true,
    };
    if (imgUrl) imageGenPayload.base_url = imgUrl;
    if (imgKey && imgKey !== '***') imageGenPayload.api_key = imgKey;

    const payload = {
      proxy: (document.getElementById('set-proxy')?.value || '').trim(),
      symbols: [...new Set(symbols)],
      leverage: Number(document.getElementById('set-leverage').value),
      entry_decision_mode: isTypeSafeEnabled ? 'typesafe_jev' : (isAiCommitteeEnabled ? 'ai_committee' : 'strategy_direct'),
      strategy: {
        ...strategy,
        signal_threshold: Number(document.getElementById('set-signal-th').value),
        scan_threshold: Number(document.getElementById('set-scan-th').value),
        liquidity: {...(strategy.liquidity || {}), min_quote_volume_24h: Number(document.getElementById('set-min-volume').value), max_spread_bps: Number(document.getElementById('set-max-spread').value)},
        market_selection: {...(strategy.market_selection || {}), allow_all_symbols: document.getElementById('set-allow-all-symbols').checked, max_price: Number(document.getElementById('set-max-price').value), min_atr_pct: Number(document.getElementById('set-min-atr').value), min_vol_surge: Number(document.getElementById('set-min-vol-surge').value), candidate_scan_limit: Number(document.getElementById('set-candidate-scan-limit').value)},
        position_management: {...(strategy.position_management || {}), tp1_atr: Number(document.getElementById('set-tp1-atr').value), tp2_atr: Number(document.getElementById('set-tp2-atr').value), partial_close_pct: Number(document.getElementById('set-partial-close').value), trailing_atr: Number(document.getElementById('set-trailing-atr').value), trail_after_tp: Number(document.getElementById('set-trail-after-tp').value), initial_stop_atr: Number(document.getElementById('set-initial-stop-atr').value), hard_stop_pct: Number(document.getElementById('set-hard-stop-pct').value), stop_confirmation_candles: Number(document.getElementById('set-stop-confirmations').value)},
      },
      execution: {...(config.execution || {}), margin_mode: document.getElementById('set-isolated-margin').checked ? 'ISOLATED' : 'CROSSED', enforce_margin_mode: true, min_notional_buffer_pct: Number(document.getElementById('set-min-notional-buffer').value), max_notional_overshoot_pct: Number(document.getElementById('set-max-notional-overshoot').value)},
      risk: {...(config.risk || {}), position_size_pct: Number(document.getElementById('set-position-size').value), max_positions: Number(document.getElementById('set-max-pos').value), max_daily_loss_pct: Number(document.getElementById('set-max-daily-loss').value)},
      ai_committee: {...(config.ai_committee || {}), enabled: isAiCommitteeEnabled, providers, image_generation: imageGenPayload},
      typesafe: typesafePayload,
    };
    const response = await fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || `HTTP ${response.status}`);
     status.textContent = tr('saved');
    status.style.color = 'var(--green)';
    setTimeout(closeSettings, 700);
  } catch (error) {
     status.textContent = tr('saveFailed') + error.message;
    status.style.color = 'var(--red)';
    button.disabled = false;
  }
}

function setQuickProxy(port) {
  const input = document.getElementById('set-proxy');
  if (!input) return;
  input.value = port ? `http://127.0.0.1:${port}` : '';
}

async function testProxyConnection() {
  const input = document.getElementById('set-proxy');
  const status = document.getElementById('proxy-test-status');
  const btn = document.getElementById('btn-test-proxy');
  if (!input || !status) return;

  const proxyVal = input.value.trim();
  btn.disabled = true;
  status.style.color = 'var(--text-2)';
  status.textContent = '正在检测连接与出口IP...';

  try {
    const res = await fetch('/api/test_proxy', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({proxy: proxyVal})
    });
    const data = await res.json();
    if (data.ok) {
      status.style.color = 'var(--green)';
      status.textContent = `✅ ${data.message}`;
    } else {
      status.style.color = 'var(--red)';
      status.textContent = `❌ ${data.error || '连接失败'}`;
    }
  } catch (err) {
    status.style.color = 'var(--red)';
    status.textContent = '❌ 测试异常: ' + err.message;
  } finally {
    btn.disabled = false;
  }
}

async function testProvider(index) {
  const button = document.getElementById(`sp-test-btn-${index}`);
  const status = document.getElementById(`sp-test-status-${index}`);
  button.disabled = true;
  status.textContent = tr('testing');
  try {
    const old = settingsConfig.ai_committee?.providers?.[index] || {};
    const key = document.getElementById(`sp-key-${index}`).value.trim();
    const urlInput = document.getElementById(`sp-url-${index}`);
    let urlVal = (urlInput?.value || '').trim().replace(/\/+$/, '');
    // Auto-normalize if domain lacks /v1
    if (urlVal && !urlVal.endsWith('/v1') && !urlVal.includes('/v1') && !urlVal.includes('/codex') && !urlVal.includes('api.deepseek.com')) {
      urlVal = urlVal + '/v1';
      if (urlInput) urlInput.value = urlVal;
    }
    const provider = {...old, model: document.getElementById(`sp-model-${index}`).value.trim(), base_url: urlVal};
    delete provider.api_key_configured;
    if (key) provider.api_key = key;
    const response = await fetch('/api/ai_test', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({index, provider})});
    const result = await response.json();
    status.className = 'provider-test-status ' + (result.success ? 'ok' : 'bad');
    let reasonText = result.reason || result.status || tr('unknownError');
    if (reasonText.includes('<html') || reasonText.includes('<!DOCTYPE') || reasonText.includes('<!doctype') || reasonText.includes('non_json_response')) {
      reasonText = '接口返回网页(HTML)而非API：缺少 /v1 路径，已自动为您补全 /v1，请重试';
    }
    status.textContent = result.success ? `${tr('passed')} | ${result.latency_ms}ms` : `${tr('executionFailed')} | ${reasonText}`;
  } catch (error) {
    status.className = 'provider-test-status bad';
    status.textContent = `${tr('executionFailed')} | ${error.message}`;
  } finally {
    button.disabled = false;
  }
}

async function testImageProvider() {
  const button = document.getElementById('sp-img-test-btn');
  const status = document.getElementById('sp-img-test-status');
  if (button) button.disabled = true;
  if (status) {
    status.className = 'provider-test-status';
    status.textContent = tr('testing') || '测试中...';
  }
  try {
    const model = (document.getElementById('sp-img-model')?.value || 'gpt-image-2').trim();
    let urlInput = document.getElementById('sp-img-url');
    let url = (urlInput?.value || '').trim().replace(/\/+$/, '');
    let key = (document.getElementById('sp-img-key')?.value || '').trim();
    if (!url) {
      const openAiUrl = document.getElementById('sp-url-1') || document.getElementById('sp-url-0');
      if (openAiUrl && openAiUrl.value) url = openAiUrl.value.trim().replace(/\/+$/, '');
    }
    if (!key) {
      const openAiKey = document.getElementById('sp-key-1') || document.getElementById('sp-key-0');
      if (openAiKey && openAiKey.value) key = openAiKey.value.trim();
    }
    if (url && !url.endsWith('/v1') && !url.includes('/v1') && !url.includes('/codex') && !url.includes('api.deepseek.com')) {
      url = url + '/v1';
      if (urlInput) urlInput.value = url;
    }

    const response = await fetch('/api/ai_test', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        type: 'image',
        index: 'image',
        provider: { model, base_url: url, api_key: key }
      })
    });
    const result = await response.json();
    if (result.success) {
      status.className = 'provider-test-status ok';
      status.textContent = `${tr('passed')} | ${result.latency_ms || 30}ms`;
    } else {
      status.className = 'provider-test-status bad';
      let reasonText = result.reason || result.status || '测试失败';
      if (reasonText.includes('<html') || reasonText.includes('<!DOCTYPE') || reasonText.includes('<!doctype')) {
        reasonText = '接口返回网页(HTML)而非API：缺少 /v1 路径，已自动补全 /v1，请重试';
      }
      status.textContent = `${tr('executionFailed')} | ${reasonText}`;
    }
  } catch (error) {
    if (status) {
      status.className = 'provider-test-status bad';
      status.textContent = `${tr('executionFailed')} | ${error.message}`;
    }
  } finally {
    if (button) button.disabled = false;
  }
}

async function testTypeSafeConnection() {
  const button = document.getElementById('btn-test-typesafe');
  const status = document.getElementById('typesafe-test-status');
  if (button) button.disabled = true;
  if (status) {
    status.style.color = 'var(--text-2)';
    status.textContent = '正在连接 TypeSafe API 握手测试...';
  }
  try {
    const key = (document.getElementById('set-typesafe-key')?.value || '').trim();
    const response = await fetch('/api/typesafe/test', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({api_key: key})
    });
    if (!response.ok) {
      const errText = await response.text();
      let msg = `HTTP ${response.status}`;
      try {
        const errJson = JSON.parse(errText);
        msg = errJson.detail || errJson.message || msg;
      } catch (_) {}
      if (response.status === 404) {
        msg = '后端服务尚未重启更新，请重启交易服务';
      }
      if (status) {
        status.style.color = 'var(--red)';
        status.textContent = `❌ 测试失败: ${msg}`;
      }
      return;
    }
    const result = await response.json();
    if (result.success) {
      if (status) {
        status.style.color = 'var(--green)';
        status.textContent = `✅ 握手成功 | ${result.latency_ms}ms | 模型: ${result.model}`;
      }
    } else {
      if (status) {
        status.style.color = 'var(--red)';
        status.textContent = `❌ 测试失败: ${result.message || result.status || '未知错误'}`;
      }
    }
  } catch (error) {
    if (status) {
      status.style.color = 'var(--red)';
      status.textContent = `❌ 请求异常: ${error.message}`;
    }
  } finally {
    if (button) button.disabled = false;
  }
}

async function toggleTypeSafeQuick() {
  try {
    const res = await fetch('/api/typesafe/toggle', {method: 'POST'});
    const data = await res.json();
    const tsBadge = document.getElementById('typesafe-badge');
    if (tsBadge) {
      tsBadge.className = 'auto-badge ' + (data.enabled ? 'typesafe-on' : 'off');
      tsBadge.textContent = data.enabled ? '🧠 Jev 风控: 开' : '🧠 Jev 风控: 关';
      tsBadge.title = data.enabled ? 'TypeSafe Jev (System One) 决策审查运行中 (点击关闭)' : 'TypeSafe Jev 已关闭 (点击开启)';
    }
    const diagAi = document.getElementById('diag-ai-status');
    if (diagAi) {
      diagAi.textContent = data.enabled ? 'Jev 毫秒级风控' : '策略直通';
    }
    if (typeof showToolToast === 'function') {
      showToolToast(data.enabled ? '🧠 TypeSafe Jev 决策门禁已开启' : '⚡ 已切换为策略直连模式');
    }
  } catch (e) {
    alert('切换 Jev 模式失败: ' + e.message);
  }
}

