let chart = null, ws = null, currentSymbol = '';
let habitRadarChart = null;
let toolToastTimer = null;
let currentView = 'single';
let posCharts = {};
let posChartSymbols = [];
let posRefreshTimer = null;
let equityChart = null;
let momentumChart = null;
let streamInterval = '5m';
// 实时K线数据缓冲
let kSymbol = '', kOpenTimes = [], kTimes = [], kSeries = [], kVols = [];
let chartOrderMode = false;
let chartOrderDraft = null;
let activeChartTool = 'cursor';
let userHorizontalLevels = [];
let userTrendLines = [];
let trendStartPoint = null;
let measureStartPoint = null;
let currentMeasureResult = null;

const I18N = {
  'zh-CN': {
    connected: '已连接', connecting: '连接中...', disconnected: '断开',
    htf: '高周期: ', settings: '⚙ 策略设置', autoOn: '自动交易 开', autoOff: '自动交易 关',
    balance: '余额', unrealizedPnl: '未实现盈亏', availableBalance: '可用余额',
    positions: '持仓数', positionsTab: '持仓', leverage: '杠杆', fundingRate: '资金费率',
    singleSymbol: '单币', positionCharts: '持仓图表', refresh: '刷新',
    indicators: '指标', aiAnalysis: 'AI分析', rankings: '榜单查询', recommendations: '推荐',
    signalLog: '信号日志', newsSentiment: '新闻情绪', tradeRecords: '成交记录',
    executionDiagnostics: '执行诊断', positionProtection: '持仓保护模式',
    positionProtectionCopy: '当前界面仅用于参数与系统预览，不会修改、平仓或新增当前持仓。',
    smartMoney: '聪明钱', waitingData: '等待数据',
    smartMoneyReason: '综合大户持仓、大户账户、散户拥挤、持仓量、价格与资金费率。',
    priceBelow: '价格低于', query: '查询', topGainers: '涨幅前20', topLosers: '跌幅前20',
    topVolume: '成交额前20', dailyReport: '每日报告', generateBlog: '生成博客',
    previewMode: '只读预览', activeSystem: '当前系统', marketRegime: '市场状态',
    signalQuality: '信号质量', riskBudget: '风险预算', execution: '执行状态',
    dataFreshness: '数据新鲜度', htfConfirmation: '15m · 高周期 1h 确认',
    regimeTypes: '趋势 / 震荡 / 高波动', technicalConfidence: '技术信号置信度',
    dailyRiskUtilization: '日内风险使用率', ordersProtection: '订单与保护单',
    lastStatusUpdate: '最近状态更新', coreSystem: '核心系统', active: '启用中',
    preview: '预览', readOnly: '只读', trendFollowing: '趋势跟随',
    trendFollowingCopy: 'EMA 结构、高周期共振、动量过滤与闭合 K 线确认。',
    breakoutMomentum: '突破动量', breakoutCopy: '区间扩张、成交量确认与波动率状态切换。',
    meanReversion: '均值回归', meanReversionCopy: 'RSI 极值、布林带偏离、回归确认与保护。',
    flow: '资金流', smartFlow: '聪明钱', smartFlowCopy: '大户持仓、持仓量、资金费率与市场拥挤度。',
    range: '区间', gridSystem: '网格系统', gridCopy: '区间识别、ATR 间距、分层挂单与仓位上限。',
    ensemble: '组合', ensembleVote: '组合投票', ensembleCopy: '多系统一致性、置信度聚合与风险门槛.',
    score: '评分', quantity: '数量', entryPrice: '开仓价', markPrice: '标记价', pnl: '盈亏', closePosition: '市价平仓',
    long: '多头', short: '空头', neutral: '观望', longPosition: '多单', shortPosition: '空单',
    readOnlySystem: '只读系统', viewingSystem: '正在预览', positionsUnchanged: '当前持仓不会被修改。',
    monitoring: '监控中', confidence: '置信度', support: '支撑', resistance: '压力',
    indicatorPrice: '价格', stochRsi: '随机 RSI K', macdHistogram: 'MACD 柱', bollingerUpper: '布林上轨', bollingerLower: '布林下轨', vwapDeviation: 'VWAP 偏离', bollingerWidth: '布林带宽度', ribbon: '均线带', bullish: '多头', bearish: '空头', mixed: '混乱',
    htfTrend: '高周期趋势', swingPattern: '波段形态', mainIntent: '主力意图',
     open: '\u5f00\u76d8', close: '\u6536\u76d8', high: '\u6700\u9ad8', low: '\u6700\u4f4e', volume: '\u6210\u4ea4\u91cf', signalScore: '\u4fe1\u53f7\u8bc4\u5206', scoreCollapse: '\u6298\u53e0\u4fe1\u53f7\u8bc4\u5206', scoreExpand: '\u5c55\u5f00\u4fe1\u53f7\u8bc4\u5206', aiEntry: '\u5efa\u8bae\u5165\u573a', aiStop: '\u5efa\u8bae\u6b62\u635f', aiTp1: '\u6b62\u76c8\u0020\u0031', aiTp2: '\u6b62\u76c8\u0020\u0032', entryZone: '\u5165\u573a\u533a\u95f4', suggestedEntry: '\u5efa\u8bae\u5165\u573a\u4ef7', riskReward: '\u98ce\u9669\u6536\u76ca\u6bd4', planStatus: '\u8ba1\u5212\u72b6\u6001',

     chartLines: '\u56fe\u8868\u7ebf\u6761', entryLine: '\u6211\u7684\u5f00\u4ed3\u7ebf', stopLine: '\u6b62\u635f\u7ebf', takeProfitLines: '\u6b62\u76c8\u7ebf', supportResistanceLines: '\u652f\u6491 / \u538b\u529b', emaLines: 'EMA \u5747\u7ebf', vwapLine: 'VWAP', denseVolumeZones: '\u5bc6\u96c6\u6210\u4ea4\u533a', swingPoints: '\u8d8b\u52bf\u9ad8\u4f4e\u70b9', chartInfoTitle: '\u56fe\u8868\u4fe1\u606f', chartDataTitle: '\u539f\u59cbK\u7ebf\u6570\u636e', chartDataHint: '\u5f53\u524d\u5468\u671f\u7684\u6700\u65b0K\u7ebf\u8bb0\u5f55', chartNoData: '\u6682\u65e0K\u7ebf\u6570\u636e', trendBias: '\u8d8b\u52bf\u504f\u5411', candleCount: '\u6570\u636e\u6837\u672c',
     chartTab: '图表', infoTab: '信息', dataTab: '数据', timeframe1m: '1分', timeframe5m: '5分', timeframe15m: '15分', timeframe1h: '1小时', timeframe4h: '4小时', timeframe1d: '1天', timeframe1w: '1周', chartContract: '永续', chartVenue: 'Binance', chartVolume: '成交量 (Volume)', chartTimezone: 'UTC+8', chartPercent: '%', chartLog: 'log', chartAuto: '自动', chartCompare: '对比', chartIndicator: '指标', chartSnapshot: '截图', obsidianSnapshot: '记入Obsidian', chartCursor: '光标', chartTrendLine: '趋势线', chartHorizontalLine: '水平线', chartMeasure: '测量', chartText: '文字', chartZoom: '放大', chartFullscreen: '全屏', exitFullscreen: '退出全屏', themeToggle: '切换配色',
     chartOrder: '图上开单', chartOrderHint: '开启后点击K线价格，快速填写限价开仓单', chartOrderHintActive: '请点击主图中的目标价格，打开限价开仓票据', chartOrderTicket: '限价开仓', chartOrderSymbol: '交易品种', chartOrderSide: '方向', chartOrderPrice: '限价', chartOrderQuantity: '数量', chartOrderBuy: '做多 / 买入', chartOrderSell: '做空 / 卖出', chartOrderConfirm: '我确认这是新的限价开仓单，提交后可能会成交并改变持仓。', chartOrderConfirmRequired: '请先勾选确认项', chartOrderSubmit: '确认提交限价单', chartOrderSubmitting: '提交中…', chartOrderCancel: '取消', chartOrderPending: '待提交限价线', chartOrderModeOn: '退出图上开单', chartOrderModeOff: '图上开单', chartOrderInvalid: '请填写有效的价格和数量', chartOrderSubmitted: '限价单已提交', chartOrderFailed: '提交失败：',
    aiLoading: 'AI 建议加载中...', themePalette: '界面配色', themeLight: '白色简约', themeNavy: '深蓝黑', themeMidnight: '午夜深蓝', themeOled: '纯黑 OLED', themeGraphite: '石墨灰',
    noPositions: '暂无持仓', noExecutionEvents: '暂无执行记录', noOpinion: '暂无结论', newsLoadFailed: '新闻加载失败', noNews: '暂无新闻（可能网络受限）',
    myPositionSentiment: '我的持仓情绪', newsSentimentLabel: '新闻情绪', bullishCount: '看多', bearishCount: '看空', neutralCount: '中性', totalItems: '共', items: '条', refreshEveryFiveMinutes: '5分钟刷新',
    retailLongShort: '散户多空比', topTraderOi: '大户持仓', topTraderAccounts: '大户账户', marketAccounts: '全市场账户', dataQuality: '数据质量',
    rankingsLoading: '正在查询低价合约榜单...', rankingsFailed: '榜单查询失败：', price: '价格', matched: '匹配', contracts: '个', contract: '合约', currentPrice: '现价', change: '涨跌', oneClickOrder: '一键下单', noContractsInRange: '该价格范围暂无合约',
    gainers24h: '24小时涨幅', losers24h: '24小时跌幅', volume24h: '24小时成交额',
    recommendationLoading: '正在扫描活跃合约...', recommendationLoadFailed: '推荐加载失败：',
    aiWhitelistRequired: '请先在策略设置中配置交易白名单', aiNoSymbols: '尚未配置交易品种，系统不会扫描全市场或自动开仓', aiLoadFailed: 'AI分析加载失败',
    grid: '网格', rounds: '回合', windingDown: '收尾', center: '中心', spacing: '间距',
    presetsTitle: '场景化交易风格预设（一键套用回测最佳参数）',
    presetsSubtitle: '无需手动精调数十个底层量化参数，点击即刻套用经过历史验证的参数组合',
    coreControlsTitle: '日常核心参数（重点关注这 3 项）',
    advancedQuantTitle: '高级底层量化参数（已由预设智能填充，日常无需修改）',
    aiMatrixTitle: 'AI 大模型专业分工矩阵',
    aiMatrixSubtitle: '三权分立协同：Claude 终审风控否决、DeepSeek 历史回测归因、OpenAI 广场解盘主笔',
    aiCommitteeGateToggle: '开启开仓前智能风控审查 (AI 投委会)',
    aiCommitteeGateHint: '开启后需通过 Claude 严格风控检查才允许执行实盘下单',
    settingsTitle: '策略设置', settingsInstant: '修改即时生效，无需重启服务', selection: '选币', symbolsLabel: '指定币种（逗号分隔，留空=全部合格币种）', signalThreshold: '信号阈值', scanThreshold: '扫描阈值', maxPrice: '最高价格', minVolatility: '最小波动率 %', minVolumeSurge: '最小放量倍数', candidateScanLimit: '候选扫描数量', minVolume24h: '最小24h成交额', maxSpread: '最大价差 (bps)', useAllSymbols: '使用全部合格币种', positionManagement: '持仓管理', tp1Atr: '止盈1 ATR', tp2Atr: '止盈2 ATR', partialClose: '部分平仓 %', trailingAtr: '移动止损 ATR', trailAfterTp: '移动止损启动于', initialStopAtr: '初始止损 ATR', hardStop: '强制止损 %', stopConfirmations: '止损确认K线数', isolatedMargin: '新仓位使用逐仓', defaultLeverage: '默认杠杆', minNotionalBuffer: '最小名义缓冲 %', maxNotionalOvershoot: '最大仓位超额 %', positionSize: '仓位比例 %', maxPositions: '最大持仓数', dailyLossStop: '日亏损停止 %', modelConnectionTest: '模型连接测试', modelNoEntry: '模型不参与自动入场决策', model: '模型', apiUrl: '接口地址', apiKey: 'API 密钥', keyConfigured: '已配置，留空保持不变', keyInput: '输入 API 密钥', test: '测试', noModels: '未配置模型', loaded: '已加载', cancel: '取消', save: '保存', settingsLoadFailed: '设置加载失败：', saved: '已保存', saveFailed: '保存失败：', testing: '测试中...', passed: '通过', unknownError: '未知错误',
    report: '日报', netPnl: '净盈亏', winRate: '胜率', sync: '同步', syncSuccess: '成功', syncPending: '待处理/失败', time: '时间', type: '类型', symbol: '币种', direction: '方向', reason: '理由', todayNoRecords: '今日暂无记录', exportHtml: '导出HTML图表', exportMarkdown: '导出MD总结', resync: '重新同步', reportLoadFailed: '日报加载失败：', botManaged: '机器人管理', externalActivity: '外部活动', closes: '次平仓',
    title: 'Quant Terminal - 币安合约'
  },
  'en-US': {
    connected: 'Connected', connecting: 'Connecting...', disconnected: 'Disconnected',
    htf: 'HTF: ', settings: '⚙ Strategy Settings', autoOn: 'Auto Trading ON', autoOff: 'Auto Trading OFF',
    balance: 'Balance', unrealizedPnl: 'Unrealized PnL', availableBalance: 'Available',
    positions: 'Positions', leverage: 'Leverage', fundingRate: 'Funding Rate',
    singleSymbol: 'Single Symbol', positionCharts: 'Position Charts', refresh: 'Refresh',
    indicators: 'Indicators', aiAnalysis: 'AI Analysis', rankings: 'Rankings', recommendations: 'Recommendations',
    signalLog: 'Signal Log', newsSentiment: 'News Sentiment', tradeRecords: 'Trade Records',
    executionDiagnostics: 'Execution', positionProtection: 'POSITION PROTECTION',
    positionProtectionCopy: 'Settings and system preview only; current positions are not modified.',
    smartMoney: 'Smart Flow', waitingData: 'Waiting for data',
    smartMoneyReason: 'Large-account positioning, crowding, open interest, price and funding rate.',
    priceBelow: 'Price below', query: 'Query', topGainers: 'Top Gainers', topLosers: 'Top Losers',
    topVolume: 'Top Volume', dailyReport: 'Daily Report', generateBlog: 'Generate Blog',
    previewMode: 'READ-ONLY PREVIEW', activeSystem: 'ACTIVE SYSTEM', marketRegime: 'MARKET REGIME',
    signalQuality: 'SIGNAL QUALITY', riskBudget: 'RISK BUDGET', execution: 'EXECUTION',
    dataFreshness: 'DATA FRESHNESS', htfConfirmation: '15m · HTF 1h confirmation',
    regimeTypes: 'Trend / Range / Volatile', technicalConfidence: 'Technical confidence',
    dailyRiskUtilization: 'Daily risk utilization', ordersProtection: 'Orders and protection',
    lastStatusUpdate: 'Last status update', coreSystem: 'CORE SYSTEM', active: 'ACTIVE',
    preview: 'PREVIEW', readOnly: 'READ-ONLY', trendFollowing: 'Trend Following',
    trendFollowingCopy: 'EMA structure, HTF alignment, momentum filters and closed-candle confirmation.',
    breakoutMomentum: 'Breakout Momentum', breakoutCopy: 'Range expansion, volume confirmation and volatility regime shift.',
    meanReversion: 'Mean Reversion', meanReversionCopy: 'RSI extremes, Bollinger deviation, reversion confirmation and protection.',
    flow: 'FLOW', smartFlow: 'Smart Flow', smartFlowCopy: 'Large-account positioning, open interest, funding and crowding.',
    range: 'RANGE', gridSystem: 'Grid System', gridCopy: 'Range detection, ATR spacing, layered orders and position caps.',
    ensemble: 'ENSEMBLE', ensembleVote: 'Ensemble Vote', ensembleCopy: 'Cross-system agreement, confidence aggregation and risk gating.',
    score: 'Score', quantity: 'Quantity', entryPrice: 'Entry', markPrice: 'Mark', pnl: 'PnL', closePosition: 'Market Close',
    long: 'Long', short: 'Short', neutral: 'Neutral', longPosition: 'Long Position', shortPosition: 'Short Position',
    readOnlySystem: 'READ-ONLY SYSTEM', viewingSystem: 'Viewing', positionsUnchanged: 'Current positions are not modified.',
    monitoring: 'Monitoring', confidence: 'Confidence', support: 'Support', resistance: 'Resistance',
    indicatorPrice: 'Price', stochRsi: 'StochRSI K', macdHistogram: 'MACD Histogram', bollingerUpper: 'Bollinger Upper', bollingerLower: 'Bollinger Lower', vwapDeviation: 'VWAP Deviation', bollingerWidth: 'Bollinger Width', ribbon: 'EMA Ribbon', bullish: 'Bullish', bearish: 'Bearish', mixed: 'Mixed',
    htfTrend: 'HTF Trend', swingPattern: 'Swing Pattern', mainIntent: 'Market Intent',
     open: 'Open', close: 'Close', high: 'High', low: 'Low', volume: 'Volume', signalScore: 'Signal Score', scoreCollapse: 'Collapse signal score', scoreExpand: 'Expand signal score', aiEntry: 'AI entry', aiStop: 'AI stop', aiTp1: 'Take profit 1', aiTp2: 'Take profit 2', entryZone: 'Entry zone', suggestedEntry: 'Suggested entry', riskReward: 'Risk / reward', planStatus: 'Plan status',

     chartLines: 'Chart lines', entryLine: 'My entry', stopLine: 'Stop loss', takeProfitLines: 'Take-profit levels', supportResistanceLines: 'Support / resistance', emaLines: 'EMA lines', vwapLine: 'VWAP line', denseVolumeZones: 'Dense volume zones', swingPoints: 'Trend highs/lows', chartInfoTitle: 'Chart information', chartDataTitle: 'Raw candle data', chartDataHint: 'Latest candle records for the selected interval', chartNoData: 'No candle data', trendBias: 'Trend bias', candleCount: 'Candles',
     chartTab: 'Chart', infoTab: 'Info', dataTab: 'Data', timeframe1m: '1m', timeframe5m: '5m', timeframe15m: '15m', timeframe1h: '1H', timeframe4h: '4H', timeframe1d: '1D', timeframe1w: '1W', chartContract: 'Perpetual', chartVenue: 'Binance', chartVolume: 'Volume', chartTimezone: 'UTC+8', chartPercent: '%', chartLog: 'log', chartAuto: 'Auto', chartCompare: 'Compare', chartIndicator: 'Indicators', chartSnapshot: 'Snapshot', obsidianSnapshot: 'Snapshot to Obsidian', chartCursor: 'Cursor', chartTrendLine: 'Trend line', chartHorizontalLine: 'Horizontal line', chartMeasure: 'Measure', chartText: 'Text', chartZoom: 'Zoom', chartFullscreen: 'Fullscreen', exitFullscreen: 'Exit Fullscreen', themeToggle: 'Toggle Theme',
     chartOrder: 'Chart order', chartOrderHint: 'Enable this, then click a price on the chart to fill a limit order', chartOrderHintActive: 'Click a target price on the main chart to open the limit ticket', chartOrderTicket: 'Limit entry', chartOrderSymbol: 'Symbol', chartOrderSide: 'Side', chartOrderPrice: 'Limit price', chartOrderQuantity: 'Quantity', chartOrderBuy: 'Long / Buy', chartOrderSell: 'Short / Sell', chartOrderConfirm: 'I confirm this is a new limit entry; submitting may fill and change the position.', chartOrderConfirmRequired: 'Check the confirmation box first', chartOrderSubmit: 'Submit limit order', chartOrderSubmitting: 'Submitting…', chartOrderCancel: 'Cancel', chartOrderPending: 'Pending limit line', chartOrderModeOn: 'Exit chart order', chartOrderModeOff: 'Chart order', chartOrderInvalid: 'Enter a valid price and quantity', chartOrderSubmitted: 'Limit order submitted', chartOrderFailed: 'Submit failed: ',
    aiLoading: 'Loading AI advice...', themePalette: 'Color theme', themeLight: 'Minimal Light', themeNavy: 'Navy Black', themeMidnight: 'Midnight Blue', themeOled: 'Pure Black OLED', themeGraphite: 'Graphite Gray',
    noPositions: 'No positions', noExecutionEvents: 'No execution events', noOpinion: 'No opinion', newsLoadFailed: 'Failed to load news', noNews: 'No news available (network may be restricted)',
    myPositionSentiment: 'My Position Sentiment', newsSentimentLabel: 'News Sentiment', bullishCount: 'Bullish', bearishCount: 'Bearish', neutralCount: 'Neutral', totalItems: 'Total', items: 'items', refreshEveryFiveMinutes: 'Refreshes every 5 min',
    retailLongShort: 'Retail long/short', topTraderOi: 'Top trader OI', topTraderAccounts: 'Top trader accounts', marketAccounts: 'Market accounts', dataQuality: 'Data quality',
    rankingsLoading: 'Loading low-price contract rankings...', rankingsFailed: 'Ranking lookup failed: ', price: 'Price', matched: 'Matched', contracts: 'contracts', contract: 'Contract', currentPrice: 'Last', change: 'Change', oneClickOrder: 'Place order', noContractsInRange: 'No contracts in this price range',
    gainers24h: '24h Gainers', losers24h: '24h Losers', volume24h: '24h Volume',
    recommendationLoading: 'Scanning active contracts...', recommendationLoadFailed: 'Recommendations failed to load: ',
    aiWhitelistRequired: 'Configure the trading whitelist in Strategy Settings first', aiNoSymbols: 'No trading symbols configured; the system will not scan the market or open positions', aiLoadFailed: 'AI analysis failed to load',
    grid: 'Grid', rounds: 'rounds', windingDown: 'winding down', center: 'Center', spacing: 'Spacing',
    executionOpen: 'Auto open', executionClose: 'Auto close', executionManualOpen: 'Manual open', executionRecommendOpen: 'Recommended open', executionSuccess: 'Filled', executionPartial: 'Partially filled', executionFailed: 'Failed', executionSkipped: 'Skipped', executionOrder: 'Order', requestedQuantity: 'Requested', normalizedQuantity: 'Normalized', executedQuantity: 'Filled', status: 'Status', orderId: 'Order ID',
    presetsTitle: 'Scenario-based Strategy Presets (One-click Optimal Setup)',
    presetsSubtitle: 'No need to tune dozens of low-level quant params manually; click to apply proven setups',
    coreControlsTitle: 'Daily Core Controls (Focus on these 3 items)',
    advancedQuantTitle: 'Advanced Low-level Quant Parameters (Optimized by presets; rarely touched)',
    aiMatrixTitle: 'AI Multi-Model Matrix',
    aiMatrixSubtitle: 'Separation of duties: Claude risk veto, DeepSeek backtest diagnosis, OpenAI Square author',
    aiCommitteeGateToggle: 'Enable Pre-entry Risk Review (AI Committee)',
    aiCommitteeGateHint: 'Requires Claude strict risk pass before placing live orders',
    settingsTitle: 'Strategy Settings', settingsInstant: 'Changes apply immediately; no service restart required', selection: 'Universe', symbolsLabel: 'Symbols (comma-separated; empty means all eligible symbols)', signalThreshold: 'Signal threshold', scanThreshold: 'Scan threshold', maxPrice: 'Max price', minVolatility: 'Min volatility %', minVolumeSurge: 'Min volume surge', candidateScanLimit: 'Candidate scan limit', minVolume24h: 'Min 24h quote volume', maxSpread: 'Max spread (bps)', useAllSymbols: 'Use all eligible symbols', positionManagement: 'Position management', tp1Atr: 'Take profit 1 ATR', tp2Atr: 'Take profit 2 ATR', partialClose: 'Partial close %', trailingAtr: 'Trailing stop ATR', trailAfterTp: 'Enable trailing after', initialStopAtr: 'Initial stop ATR', hardStop: 'Hard stop %', stopConfirmations: 'Stop confirmation candles', isolatedMargin: 'Use isolated margin for new positions', defaultLeverage: 'Default leverage', minNotionalBuffer: 'Min notional buffer %', maxNotionalOvershoot: 'Max notional overshoot %', positionSize: 'Position size %', maxPositions: 'Max positions', dailyLossStop: 'Daily loss stop %', modelConnectionTest: 'Model connection test', modelNoEntry: 'Models do not participate in automatic entry decisions', model: 'Model', apiUrl: 'API URL', apiKey: 'API key', keyConfigured: 'Configured; leave blank to keep unchanged', keyInput: 'Enter API key', test: 'Test', noModels: 'No models configured', loaded: 'Loaded', cancel: 'Cancel', save: 'Save', settingsLoadFailed: 'Settings failed to load: ', saved: 'Saved', saveFailed: 'Save failed: ', testing: 'Testing...', passed: 'Passed', unknownError: 'Unknown error',
    report: 'Daily Report', netPnl: 'Net PnL', winRate: 'Win rate', sync: 'Sync', syncSuccess: 'Succeeded', syncPending: 'Pending/failed', time: 'Time', type: 'Type', symbol: 'Symbol', direction: 'Direction', reason: 'Reason', todayNoRecords: 'No records today', exportHtml: 'Export HTML chart', exportMarkdown: 'Export Markdown summary', resync: 'Sync again', reportLoadFailed: 'Daily report failed to load: ', botManaged: 'Bot-managed', externalActivity: 'External activity', closes: 'closes',
    title: 'Quant Terminal - Futures'
  }
};
let currentLanguage = 'zh-CN';
const SYSTEM_I18N_KEYS = {
  trend: 'trendFollowing',
  trend_following: 'trendFollowing',
  breakout: 'breakoutMomentum',
  mean_reversion: 'meanReversion',
  smart_money: 'smartFlow',
  grid: 'gridSystem',
  ensemble: 'ensembleVote'
};
function tr(key, fallback='') { return I18N[currentLanguage]?.[key] || fallback || key; }
function displaySystemName(system) { return tr(SYSTEM_I18N_KEYS[system] || system, system); }
function displaySide(side, position=false) {
  const isLong = String(side || '').toUpperCase() === 'LONG';
  return tr(position ? (isLong ? 'longPosition' : 'shortPosition') : (isLong ? 'long' : 'short'));
}
function txt(zh, en) { return currentLanguage === 'zh-CN' ? zh : en; }
const RUNTIME_TEXT_EN = [
  ['聪明钱方向中性，不改变候选', 'Smart-money direction is neutral; candidate unchanged'],
  ['聪明钱偏多', 'Smart money bullish'],
  ['聪明钱偏空', 'Smart money bearish'],
  ['智能资金观望', 'Smart money is waiting'],
  ['EMA丝带多头排列', 'EMA ribbon bullish alignment'],
  ['EMA丝带空头排列', 'EMA ribbon bearish alignment'],
  ['价格/OI 1h共振', 'Price/OI 1h confluence'],
  ['上升趋势', 'Rising trend'],
  ['上升', 'Rising'],
  ['强度', 'Strength'],
  ['多空信号交织', 'Long/short signals are mixed'],
  ['建议等待方向明确', 'Wait for clearer direction'],
  ['十字星', 'Doji'],
  ['多空犹豫,变盘在即', 'indecision; a reversal may be near'],
  ['多空信号尚未形成高周期反转确认', 'No HTF reversal confirmation from long/short signals'],
  ['维持仓位观察', 'Maintain the position and monitor'],
  ['止损随价格和波动上移', 'Raise the stop with price and volatility'],
  ['波段结构线', 'Swing structure line'],
  ['硬风险线', 'Hard risk line'],
  ['跟踪保护线', 'Trailing protection line'],
  ['拉升', 'Markup'],
  ['吸筹', 'Accumulation'],
  ['洗盘', 'Shakeout'],
  ['出货', 'Distribution'],
  ['多头排列', 'bullish alignment'],
  ['空头排列', 'bearish alignment'],
  ['高TF趋势确认', 'HTF trend confirmation'],
  ['高周期趋势确认', 'HTF trend confirmation'],
  ['EMA丝带', 'EMA ribbon'],
  ['OBV突破均线', 'OBV breakout above average'],
  ['量价背离·抛压衰竭', 'Price-volume divergence · selling pressure exhaustion'],
  ['量价背离', 'Price-volume divergence'],
  ['抛压衰竭', 'selling pressure exhaustion'],
  ['突破均线', 'breakout above average'],
  ['偏多', 'Bullish'],
  ['偏空', 'Bearish'],
  ['多头', 'Long'],
  ['空头', 'Short'],
  ['中性', 'Neutral'],
  ['多单', 'Long Position'],
  ['空单', 'Short Position'],
  ['趋势', 'Trend'],
  ['震荡', 'Range'],
  ['高波动', 'Volatile'],
  ['方向尚未形成共振', 'No directional consensus yet'],
  ['数据质量', 'Data quality'],
  ['持仓多空比', 'Position long/short ratio'],
  ['账户多空比', 'Account long/short ratio'],
  ['大户持仓', 'Top trader OI'],
  ['大户账户', 'Top trader accounts'],
  ['成交量确认', 'Volume confirmation'],
  ['资金费率', 'Funding rate'],
  ['持仓量', 'Open interest'],
  ['去杠杆', 'Deleveraging'],
  ['价格/OI', 'Price/OI'],
  ['共振', 'confluence'],
  ['候选', 'candidate']
];
function localizeRuntimeText(value) {
  let text = String(value ?? '');
  if (currentLanguage === 'zh-CN') return text;
  for (const [source, target] of RUNTIME_TEXT_EN) text = text.split(source).join(target);
  return text.replace(/RisingTrend/g, 'Rising trend')
    .replace(/Strength(?=\d)/g, 'Strength ')
    .replace(/，/g, ', ')
    .replace(/。/g, '. ')
    .replace(/；/g, '; ')
    .replace(/、/g, ', ');
}
function displayAction(action) {
  if (action === '偏多' || action === 'LONG') return tr('long');
  if (action === '偏空' || action === 'SHORT') return tr('short');
  return tr('neutral');
}
function renderStatusBanner(system) {
  const banner = document.querySelector('.status-banner');
  if (!banner) return;
  const label = displaySystemName(system || 'trend_following');
  banner.dataset.system = system || 'trend_following';
  banner.innerHTML = `<span>●</span><strong>${tr('readOnlySystem')}</strong><span>${tr('viewingSystem')} ${label}; ${tr('positionsUnchanged')}</span>`;
}
function setLanguage(locale) {
  currentLanguage = I18N[locale] ? locale : 'zh-CN';
  const dict = I18N[currentLanguage];
  document.documentElement.lang = currentLanguage;
  document.title = dict.title;
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    if (dict[key]) el.textContent = dict[key];
  });
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const key = el.dataset.i18nTitle;
    if (dict[key]) el.title = dict[key];
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.dataset.i18nPlaceholder;
    if (dict[key]) el.placeholder = dict[key];
  });
  const settings = document.getElementById('settings-btn');
  if (settings) settings.textContent = dict.settings;
  const auto = document.getElementById('auto-badge');
  if (auto) auto.textContent = auto.classList.contains('on') ? dict.autoOn : dict.autoOff;
  const htf = document.getElementById('htf-label');
  if (htf) htf.textContent = dict.htf + (htf.dataset.interval || '--');
  const activeSystem = document.getElementById('metric-system');
  if (activeSystem) activeSystem.textContent = displaySystemName(activeSystem.dataset.systemLabel || 'trend_following');
  renderStatusBanner(document.querySelector('.status-banner')?.dataset.system || 'trend_following');
  if (typeof refreshDynamicLanguage === 'function') refreshDynamicLanguage();
  if (chart) renderChart();
  const regime = document.getElementById('metric-regime');
  if (regime && (regime.dataset.staticValue === 'waiting' || regime.textContent === '????' || regime.textContent === '等待数据' || regime.textContent === 'Waiting for data')) {
    regime.dataset.staticValue = 'waiting';
    regime.textContent = tr('waitingData');
  }
  const execution = document.getElementById('metric-execution');
  if (execution && (execution.dataset.staticValue === 'monitoring' || execution.textContent === '???' || execution.textContent === '监控中' || execution.textContent === 'Monitoring')) {
    execution.dataset.staticValue = 'monitoring';
    execution.textContent = tr('monitoring');
  }
  if (!lastAiPayload && !document.getElementById('symbol-select')?.value) {
    const aiPanel = document.getElementById('ai-panel');
    const adviceBar = document.getElementById('advice-bar');
    if (aiPanel) aiPanel.innerHTML = `<div class="empty-state">${tr('aiWhitelistRequired')}</div>`;
    if (adviceBar) adviceBar.innerHTML = `<span class="advice-loading">${tr('aiNoSymbols')}</span>`;
  }
  const wsText = document.getElementById('ws-text');
  if (wsText) {
    const state = wsText.dataset.runtimeState;
    wsText.textContent = state === 'connected' ? dict.connected : state === 'disconnected' ? dict.disconnected : dict.connecting;
  }
  document.querySelectorAll('.locale-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.locale === currentLanguage);
  });
  syncChartTimeframeButtons();
  updateChartHeader();
  try { localStorage.setItem('quant_language', currentLanguage); } catch (e) {}
}
function initLanguage() {
  let saved = null;
  try { saved = localStorage.getItem('quant_language'); } catch (e) {}
  setLanguage(I18N[saved] ? saved : 'zh-CN');
}

// ===== 主题(背景色) =====
const THEMES = {
  midnight: { bg0:'#070A12', bg1:'#0D1322', bg2:'#131C30', bg3:'#1A2640', border:'rgba(255,255,255,0.08)', borderLight:'rgba(255,255,255,0.18)', text0:'#F8FAFC', text1:'#CBD5E1', text2:'#7E8B9F', panelBg:'rgba(13,19,34,.88)' },
  navy:     { bg0:'#080B10', bg1:'#0F1622', bg2:'#172233', bg3:'#202E44', border:'rgba(255,255,255,0.07)', borderLight:'rgba(255,255,255,0.15)', text0:'#F8FAFC', text1:'#CBD5E1', text2:'#778899', panelBg:'rgba(15,22,34,.90)' },
  oled:     { bg0:'#000000', bg1:'#0A0A0A', bg2:'#141414', bg3:'#1F1F1F', border:'rgba(255,255,255,0.10)', borderLight:'rgba(255,255,255,0.20)', text0:'#FFFFFF', text1:'#CCCCCC', text2:'#777777', panelBg:'rgba(10,10,10,.92)' },
  graphite: { bg0:'#0E1015', bg1:'#151820', bg2:'#1E222D', bg3:'#282D3B', border:'rgba(255,255,255,0.08)', borderLight:'rgba(255,255,255,0.18)', text0:'#F8FAFC', text1:'#C0CBD9', text2:'#7E8795', panelBg:'rgba(21,24,32,.90)' },
  light:    { bg0:'#f8fafc', bg1:'#ffffff', bg2:'#f1f5f9', bg3:'#e2e8f0', border:'#e2e8f0', borderLight:'#cbd5e1', text0:'#0f172a', text1:'#334155', text2:'#64748b', panelBg:'rgba(255,255,255,.96)' }
};
const THEME_NAMES = { midnight:'午夜深蓝', navy:'深蓝黑', oled:'纯黑 OLED', graphite:'石墨灰', light:'白色简约' };
let currentTheme = 'midnight';
let isColorBlindMode = false;

function toggleColorBlindMode() {
  isColorBlindMode = !isColorBlindMode;
  document.body.setAttribute('data-color-mode', isColorBlindMode ? 'colorblind' : 'normal');
  try { localStorage.setItem('quant_a11y_color', isColorBlindMode ? '1' : '0'); } catch(e) {}
  const ind = document.getElementById('a11y-color-indicator');
  const txt = document.getElementById('a11y-color-text');
  if (ind && txt) {
    ind.style.background = isColorBlindMode ? '#3b82f6' : '#10b981';
    txt.textContent = isColorBlindMode ? '蓝橙(a11y)' : '红绿';
  }
  if (typeof loadKlines === 'function') {
    try { loadKlines(); } catch(e) {}
  }
}

// 自动恢复无障碍色系偏好
try {
  if (localStorage.getItem('quant_a11y_color') === '1') {
    setTimeout(toggleColorBlindMode, 30);
  }
} catch(e) {}

function applyTheme(name) {
  const prevWasLight = (currentTheme === 'light');
  if (!THEMES[name]) name = 'midnight';
  currentTheme = name;
  const nowIsLight = (name === 'light');
  const t = THEMES[name];
  const root = document.documentElement.style;
  root.setProperty('--bg-0', t.bg0);
  root.setProperty('--bg-1', t.bg1);
  root.setProperty('--bg-2', t.bg2);
  root.setProperty('--bg-3', t.bg3);
  root.setProperty('--border', t.border);
  root.setProperty('--border-light', t.borderLight);
  root.setProperty('--text-0', t.text0);
  root.setProperty('--text-1', t.text1);
  root.setProperty('--text-2', t.text2);
  root.setProperty('--panel-bg', t.panelBg);
  document.body.classList.toggle('theme-light', name === 'light');
  document.documentElement.style.colorScheme = name === 'light' ? 'light' : 'dark';
  try { localStorage.setItem('quant_theme', name); } catch(e) {}
  // 刷新图表配色
  if (prevWasLight !== nowIsLight && chart) {
    try {
      chart.dispose();
      chart = null;
      initChart();
      if (typeof renderChart === 'function') renderChart();
    } catch(e) { console.error('Re-init chart on theme switch error', e); }
  } else if (chart) chart.setOption({
    backgroundColor: 'transparent',
    xAxis: [{axisLine:{lineStyle:{color:t.border}},axisLabel:{color:t.text2}},{axisLine:{lineStyle:{color:t.border}},axisLabel:{color:t.text2}}],
    yAxis: [{splitLine:{lineStyle:{color:t.bg2}},axisLabel:{color:t.text2}},{splitLine:{lineStyle:{color:t.bg2}},axisLabel:{color:t.text2}}],
    tooltip: { backgroundColor: t.panelBg, borderColor: t.border, textStyle: { color: t.text0 } }
  }, {lazyUpdate:true});
  if (equityChart) equityChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { backgroundColor: t.panelBg, borderColor: t.border, textStyle: { color: t.text0 } }
  }, {lazyUpdate:true});
  if (momentumChart) momentumChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { backgroundColor: t.panelBg, borderColor: t.border, textStyle: { color: t.text0 } }
  }, {lazyUpdate:true});
  if (habitRadarChart) habitRadarChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { backgroundColor: t.panelBg, borderColor: t.border, textStyle: { color: t.text0 } }
  }, {lazyUpdate:true});
  Object.keys(posCharts).forEach(sym => {
    const inst = posCharts[sym];
    if (inst) inst.setOption({ xAxis: {axisLine:{lineStyle:{color:t.border}},axisLabel:{color:t.text2}}, yAxis: {splitLine:{lineStyle:{color:t.bg2}},axisLabel:{color:t.text2}}, tooltip: { backgroundColor: t.panelBg, borderColor: t.border, textStyle: { color: t.text0 }, formatter: function(params) {
      const p = params.filter(x => x.seriesType === 'candlestick')[0];
      if (!p) return '';
      const d = p.data;
      const dir = d[1] >= d[0] ? '▲' : '▼';
      const col = d[1] >= d[0] ? '#10b981' : '#ef4444';
      const fmt = v => Number(v).toFixed(8).replace(/0+$/, '').replace(/\.$/, '');
      let h = `<div style="font-size:10px;line-height:1.8;color:${THEMES[currentTheme].text0}">${p.axisValue}`;
      h += `<table style="margin-top:2px;border-collapse:collapse">`;
      for (const [k, v] of [[tr('open'), fmt(d[0])], [tr('close'), `<span style="color:${col}">${fmt(d[1])} ${dir}</span>`], [tr('low'), fmt(d[2])], [tr('high'), fmt(d[3])]])
        h += `<tr><td style="color:${THEMES[currentTheme].text2};padding-right:8px">${k}</td><td style="font-weight:600;color:${THEMES[currentTheme].text0}">${v}</td></tr>`;
      h += `</table></div>`;
      return h;
    } } }, {lazyUpdate:true});
  });
  // 更新色块选中态
  document.querySelectorAll('.theme-dot').forEach(el => {
    el.classList.toggle('active', el.dataset.theme === name);
  });
  const icon = name === 'light' ? '☀️' : (name === 'oled' ? '⬛' : '🌙');
  const iconEl = document.getElementById('header-theme-icon');
  if (iconEl) iconEl.textContent = icon;
  const labelEl = document.getElementById('header-theme-text');
  if (labelEl) {
    const key = name === 'light' ? 'themeLight' : (name === 'navy' ? 'themeNavy' : (name === 'midnight' ? 'themeMidnight' : (name === 'oled' ? 'themeOled' : 'themeGraphite')));
    labelEl.textContent = tr(key) || THEME_NAMES[name] || name;
  }
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const key = el.dataset.i18nTitle;
    if (I18N[currentLanguage]?.[key]) el.title = I18N[currentLanguage][key];
  });
}

function toggleThemeLightDark() {
  applyTheme(currentTheme === 'light' ? 'navy' : 'light');
}

function toggleChartFullscreen(force) {
  const chartArea = document.querySelector('.chart-area');
  if (!chartArea) return;
  const isFs = typeof force === 'boolean' ? force : !chartArea.classList.contains('fullscreen-mode');
  chartArea.classList.toggle('fullscreen-mode', isFs);

  const fsBtn = document.getElementById('chart-fullscreen-btn');
  if (fsBtn) {
    fsBtn.innerHTML = isFs ? '<span class="fs-icon">⤡</span> <span class="fs-text">' + tr('exitFullscreen') + '</span>' : '<span class="fs-icon">⛶</span> <span class="fs-text">' + tr('chartFullscreen') + '</span>';
    fsBtn.classList.toggle('active', isFs);
  }

  if (isFs) {
    try {
      if (document.documentElement.requestFullscreen && !document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
      }
    } catch (e) {}
    showChartToolToast('【全屏看盘】按 ESC 键或点击右上角退出全屏');
  } else {
    try {
      if (document.fullscreenElement && document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      }
    } catch (e) {}
    showChartToolToast('已退出全屏模式');
  }

  const triggerResize = () => {
    if (chart) chart.resize();
    if (equityChart) equityChart.resize();
    if (momentumChart) momentumChart.resize();
  };
  triggerResize();
  requestAnimationFrame(triggerResize);
  setTimeout(triggerResize, 80);
  setTimeout(triggerResize, 250);
}

document.addEventListener('keydown', e => {
  if ((e.key === 'Escape' || e.key === 'Esc') && document.querySelector('.chart-area.fullscreen-mode')) {
    toggleChartFullscreen(false);
  }
});
document.addEventListener('fullscreenchange', () => {
  if (!document.fullscreenElement && document.querySelector('.chart-area.fullscreen-mode')) {
    toggleChartFullscreen(false);
  }
});

function initScorePanel() {
  const panel = document.getElementById('score-panel');
  const toggle = document.getElementById('score-toggle');
  if (!panel || !toggle) return;
  let collapsed = false;
  try { collapsed = localStorage.getItem('quant_score_collapsed') === '1'; } catch (e) {}
  const sync = () => {
    panel.classList.toggle('collapsed', collapsed);
    toggle.textContent = collapsed ? '+' : '-';
    toggle.setAttribute('aria-expanded', String(!collapsed));
    toggle.title = tr(collapsed ? 'scoreExpand' : 'scoreCollapse');
  };
  toggle.addEventListener('click', () => {
    collapsed = !collapsed;
    try { localStorage.setItem('quant_score_collapsed', collapsed ? '1' : '0'); } catch (e) {}
    sync();
  });
  sync();
}

function initTheme() {
  let saved = null;
  try {
    const v3 = localStorage.getItem('quant_theme_pro_v3');
    if (!v3) {
      saved = 'midnight';
      localStorage.setItem('quant_theme', 'midnight');
      localStorage.setItem('quant_theme_pro_v3', '1');
    } else {
      saved = localStorage.getItem('quant_theme');
    }
  } catch(e) {}
  applyTheme(THEMES[saved] ? saved : 'midnight');
}

