"""全球高胜率经典与量化策略矩阵与卡帕西 (Karpathy) LLM-Wiki 模板库（图文并茂 + 经典视频精讲版）"""

RAW_SOURCES_README_CONTENT = """# 00-原始资料与灵感库 (Raw Sources)

> [!TIP] 卡帕西 (Karpathy) LLM-Wiki 知识编译体系
> 按照安德烈·卡帕西的「知识编译器模型」：
> 1. **原始原料 (Source Code)**：本目录用于存放未经处理的研报、网页摘录、量化灵感草稿、巨鲸持仓异动线索。
> 2. **AI编译器 (Compiler)**：系统的 `ObsidianBridge` 会自动读取并编译这些原始资料，提炼出标准策略规则。
> 3. **知识库成品 (Executable)**：编译后的标准策略存放于 `01-交易策略/`，并在 `[[00-知识库索引_MOC]]` 自动更新索引与回测归因。

## 📥 如何使用
- 将平时看到的交易技巧、高胜率指标配方、推特大佬观点或 Markdown 笔记直接丢入此文件夹；
- 每次触发系统「自维护编译」时，系统会自动提取其中的交易见解与关键参数，与您的实盘策略库进行交叉比对。
"""

STRATEGY_MARTINGALE_CONTENT = """---
title: 动态安全网格马丁策略 (Dynamic Safety-Grid DCA)
type: grid_martingale
status: active
symbols: [BTCUSDT, ETHUSDT, SOLUSDT, DOGEUSDT]
timeframe: 15m
target_win_rate: 91.5%
profit_factor: 2.1
max_risk_per_trade: 12%
indicators:
  - ATR(14)
  - RSI(14)
  - EMA21
  - Volume
tags:
  - 马丁格尔
  - 动态网格
  - 均值回归
  - 高胜率
---

# 动态安全网格马丁策略 (Dynamic Safety-Grid DCA)

> [!TIP] 策略核心理念与风险改良
> 传统马丁策略因“固定点数翻倍加仓”而在单边极端行情中存在确定性爆仓风险。本策略由华尔街量化团队改良：
> 1. **ATR 动态间距拉伸**：根据波动率逐级扩大补仓间距，拒绝密集送死；
> 2. **软阶梯加仓系数**：补仓系数设定为 `1.2x ~ 1.35x`（而非粗暴的 2.0x）；
> 3. **硬性回撤熔断保险丝**：总账户浮亏达到 12%~15% 强制无条件平仓，确保绝对本金安全。

## 🧭 知识库双向链接
- 知识地图中枢: [[00-知识库索引_MOC|知识库总索引]]
- 关联行为风控: [[03-交易习惯与行为进化/交易习惯进化追踪|交易习惯进化追踪]]
- 对比策略: [[01-交易策略/04-VWAP机构量价锚定与均值回归策略|VWAP日内均值回归策略]]

---

## 📊 策略运行架构与风控流转图

```mermaid
flowchart TD
    Start([监控市场标的 15m 周期]) --> CheckRSI{RSI 极端超卖 < 28\n且离 EMA21 > 1.5 ATR?}
    CheckRSI -- 否 --> Start
    CheckRSI -- 是 --> BaseEntry[建立底仓 2% 资金]
    
    BaseEntry --> Monitor[实时监控加权持仓盈亏]
    Monitor --> CheckTP{回抽超过持仓均价\n+1.2% ~ +1.8%?}
    CheckTP -- 是 --> CloseAll[🟢 全量止盈平仓离场]
    
    CheckTP -- 否 --> CheckCutoff{账户总浮亏 >= 12%?}
    CheckCutoff -- 是 --> Cutoff[🔴 硬性熔断保险丝触发: 无条件止损!]
    
    CheckCutoff -- 否 --> CheckTier1{逆行 >= 1.2 * ATR?}
    CheckTier1 -- 是 --> AddTier1[补仓档 1: 1.2x 基础仓位]
    AddTier1 --> CheckTier2{继续逆行 >= 1.8 * ATR?}
    CheckTier2 -- 是 --> AddTier2[补仓档 2: 1.4x 基础仓位]
    AddTier2 --> CheckTier3{继续逆行 >= 2.5 * ATR?}
    CheckTier3 -- 是 --> AddTier3[补仓档 3: 1.6x 基础仓位]
    AddTier3 --> Monitor
```

---

## 📈 K 线结构与加仓梯阶示意图

```text
 价格走势 (Price)                      网格执行动作 (Actions)
   │ 
   │  ─── EMA21 趋势均线 ───
   │                                   
   │         ▼ (原点下跌)
   │        ╭──╮
   │        │  │ [超卖 Pinbar 出现]  ──> 🎯 建立底仓 (Base: 2% 仓位)
   │        ╰──╯
   │          │ (逆行 1.2 * ATR)
   │        ╭──╮
   │        │  │                     ──> 📥 加仓第1档 (1.2x 仓位)
   │        ╰──╯
   │          │ (逆行 1.8 * ATR)
   │        ╭──╮
   │        │  │                     ──> 📥 加仓第2档 (1.4x 仓位)
   │        ╰──╯
   │          │ (回踩均值向上反弹 🚀)
   │          ▲ 
   │      ═════════════════════════════ 加权综合持仓成本线 (Break-Even)
   │          ▲ 突破成本线 +1.5%
   │        ╭──╮
   │        │  │                     ──> 🟢 批量全量止盈离场 (Take Profit)
   │        ╰──╯
   ▼─────────────────────────────────── 🚨 12% 浮亏绝对熔断底线 (Stop Out)
```

---

## 一、入场条件 (底仓触发)
1. 15m 周期 RSI(14) 达到极端值（多头底仓要求 RSI < 28 超卖；空头底仓要求 RSI > 72 超买）；
2. 现价偏离 EMA21 超过 1.5 倍 ATR(14)，出现成交量耗尽针（Pinbar）；
3. 建立基础仓位（占用总资金不超过 2%）。

## 二、补仓梯阶与仓位管理 (动态网格)
- **第 1 档加仓**: 价格逆行 1.2 * ATR(14)，补仓 1.2x 基础仓位；
- **第 2 档加仓**: 价格继续逆行 1.8 * ATR(14)，补仓 1.4x 基础仓位；
- **第 3 档加仓**: 价格继续逆行 2.5 * ATR(14)，补仓 1.6x 基础仓位；
- **最大补仓次数限制**: 最多补仓 3 次，总持仓严禁超过账户权益的 18%。

## 三、止盈与出场规则
- **加权成本均价回归止盈**: 当价格回抽突破所有持仓加权持仓成本价（Break-Even Price）之上 +1.2% ~ +1.8% 时，一次性全量清仓获利；
- **均线触碰止盈**: 价格反弹触碰 15m EMA21 均线时，至少获利平仓 75% 仓位。

## 四、硬性风控与止损熔断
- **绝对浮亏熔断**: 整体网格浮亏达到初始本金的 **12%** 时，系统执行熔断强平，绝不扛单；
- **假突破反转止损**: 连续 2 根 1h K 线实体收在第 3 档加仓位下方，立即割肉止损。

---

## 🎥 经典视频教学与精讲推荐

- 📺 **Bilibili 精讲视频**:
  - [马丁格尔策略数学原理与量化防爆仓改良](https://search.bilibili.com/all?keyword=马丁策略+网格量化+动态风控)
  - [网格交易与动态 DCA 资金管理实战](https://search.bilibili.com/all?keyword=动态网格+DCA+马丁)
- 📺 **YouTube 权威教程**:
  - [Risk-Managed DCA & Martingale Strategies for Crypto](https://www.youtube.com/results?search_query=Risk+Managed+Martingale+DCA+Strategy)
  - [The Math Behind Martingale: Why Fixed Grid Fails and How to Fix It](https://www.youtube.com/results?search_query=Martingale+trading+strategy+risk+management)
"""

STRATEGY_SMC_CONTENT = """---
title: SMC聪明钱订单块与流动性劫持策略
type: smart_money_concepts
status: active
symbols: [BTCUSDT, ETHUSDT, SOLUSDT]
timeframe: 15m
target_win_rate: 72.0%
profit_factor: 3.4
risk_reward_ratio: 1:3.2
indicators:
  - FVG (Fair Value Gap)
  - Order Block (OB)
  - Market Structure Shift (MSS)
  - Liquidity Sweep
tags:
  - SMC
  - 聪明钱
  - 机构订单块
  - 高盈亏比
---

# SMC聪明钱订单块与流动性劫持策略

> [!NOTE] 机构逻辑本质
> 巨鲸与做市商需要巨大的对手盘流动性。他们会先推升价格刺破散户止损密集区（流动性掠夺 Liquidity Sweep），随后引发急剧位移（Displacement）留下未成交的公允价值缺口（FVG），回踩时即为高胜率低风险狙击点。

## 🧭 知识库双向链接
- 知识地图中枢: [[00-知识库索引_MOC|知识库总索引]]
- 关联行为风控: [[03-交易习惯与行为进化/交易习惯进化追踪|交易习惯进化追踪]]
- 对比策略: [[01-交易策略/06-多周期EMA共振与RSI顶底背离策略|多周期EMA与RSI背离策略]]

---

## 📊 SMC 机构订单流转模型

```mermaid
sequenceDiagram
    autonumber
    participant Retail as 散户止损盘 (Liquidity Pool)
    participant Whale as 做市机构 (Smart Money)
    participant Market as 市场公允缺口 (FVG & OB)

    Whale->>Retail: 1. 蓄意拉升刺破前高，触发散户空头止损买单 (Sweep)
    Retail-->>Whale: 产生大量买入流动性，主力从容吃饱空单筹码
    Whale->>Market: 2. 暴力砸盘产生位移，破坏下行结构 (MSS / Displacement)
    Note over Market: 留下未成交失衡区 (Fair Value Gap, FVG)
    Market->>Whale: 3. 价格弱势反抽回踩 FVG 50% 黄金敏感带
    Whale->>Market: 4. 挂单入场激活狙击空单，顺势大波段爆砸 (TP 1:3.5)
```

---

## 📈 K 线图解: 流动性掠夺与 FVG 缺口回踩

```text
 价格 (Price)
   │               ╭─╮ (刺破前高流动性池 Liquidity Sweep ⚠️)
   │               │ │
   │   ────── 前高阻力位 (Buy-side Liquidity) ──────
   │          ╭─╮  │ │
   │          │ │  │ │
   │          │ │  ╰─╯
   │          ╰─╯   │  (大阴线急跌位移 Displacement 💥)
   │               ╭──╮
   │   K线1 底端 ─ │  │ ──┐
   │               ╰──╯   │ ──> 【FVG 公允价值缺口 (未重叠真空区)】
   │               ╭──╮   │     🎯 最佳挂单狙击入场点 (Entry at FVG 50%)
   │   K线3 顶端 ─ │  │ ──┘
   │               ╰──╯
   │                 │
   │               ╭──╮ (跌破最近摆动低点，确认市场结构突变 MSS ✅)
   │               ╰──╯
   │                 ▼
   ▼────────────────────── 🎯 止盈目标位 (Sell-side Liquidity TP: 1:3.2)
```

---

## 一、入场条件 (Entry)
1. **流动性掠夺 (Liquidity Sweep)**: 价格刺破前亚盘高点/低点、前一日高低点（BSL/SSL）后迅速收回长影线；
2. **结构转变 (MSS)**: 5m/15m 周期出现强实体大阴/大阳线击穿最近微观摆动拐点；
3. **失衡区回踩 (FVG Retest)**: 价格平缓回踩由于剧烈位移产生的公允价值缺口 (FVG) 或未被缓解的订单块 (Mitigation Block)；
4. **限价挂单**: 在 FVG 50% 水平（中轨 CE）或 OB 开盘价精准挂单。

## 二、止损与风控 (Stop Loss)
- 止损设在形成该订单块的极端影线外侧 + 0.2% 缓冲；
- 单笔最大风险: 严格限制为总账户净值的 1.5%。

## 三、分批止盈与目标 (Take Profit)
- **TP1 (1:2)**: 到达下一个微观流动性池止盈 50%，并将止损推至开仓保本价；
- **TP2 (1:3.5)**: 目标看向大周期摆动高点/低点清仓离场。

---

## 🎥 经典视频教学与精讲推荐

- 📺 **Bilibili 精讲视频**:
  - [SMC聪明钱交易法中文精讲全集 (Order Block 与 FVG 缺口)](https://search.bilibili.com/all?keyword=SMC聪明钱教程+ICT订单块+FVG)
  - [ICT 核心价格行为与流动性劫持实盘案例解析](https://search.bilibili.com/all?keyword=ICT交易策略+流动性掠夺)
- 📺 **YouTube 官方与大师课**:
  - [Inner Circle Trader (ICT) 2022 Mentorship Episode 1-12](https://www.youtube.com/results?search_query=Inner+Circle+Trader+2022+Mentorship+FVG+Order+Block)
  - [Smart Money Concepts Complete Masterclass (Order Block & Liquidity)](https://www.youtube.com/results?search_query=Smart+Money+Concepts+Complete+Course+Order+Block)
"""

STRATEGY_TTM_SQUEEZE_CONTENT = """---
title: TTM Squeeze 波动率挤压突破策略
type: volatility_squeeze
status: active
symbols: [BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT]
timeframe: 15m
target_win_rate: 76.5%
profit_factor: 2.6
risk_reward_ratio: 1:2.5
indicators:
  - Bollinger Bands(20, 2.0)
  - Keltner Channels(20, 1.5 ATR)
  - Momentum Histogram
tags:
  - 波动率挤压
  - 动量突破
  - TTM
  - 约翰卡特
---

# TTM Squeeze 波动率挤压突破策略

> [!NOTE] 核心原理
> 市场总是由低波动（震荡吸筹）向高波动（单边爆发）循环演变。当布林带完全进入肯特纳通道内部时，系统处于“黑天鹅蓄势（Squeeze ON）”状态；一旦布林带向外刺出并伴流动量柱拐头（Squeeze OFF），即代表能量大规模释放。

## 🧭 知识库双向链接
- 知识地图中枢: [[00-知识库索引_MOC|知识库总索引]]
- 关联行为风控: [[03-交易习惯与行为进化/交易习惯进化追踪|交易习惯进化追踪]]
- 对比策略: [[01-交易策略/05-海龟双向ATR通道突破趋势策略|海龟双向ATR通道突破]]

---

## 📊 波动率通道挤压与释放形态

```text
 通道示意 (Bands & Channels)             动能指标 (Momentum Oscillator)
   │                                       │
   │   ═════ 肯特纳通道上轨 (Keltner Upper) ═ │
   │      ────── 布林带上轨 (Bollinger) ──  │  [Squeeze ON 🔴: 蓄水挤压中]
   │             · · · · · · · ·           │  动能柱扁平，能量被极致压抑
   │   ────── 20 EMA 核心中轨线 ──────    │
   │             · · · · · · · ·           │
   │      ────── 布林带下轨 (Bollinger) ──  │
   │   ═════ 肯特纳通道下轨 (Keltner Lower) ═ │
   │                                       │
   │  ─────────────────────────────────    │  [Squeeze OFF 🟢: 挤压点火爆发!]
   │       ╲                           ╱   │   ▄ █ █ █ 动量直方图陡峭上冲 🚀
   │        ╲                         ╱    │  市价大阳线实体突破，直接顺势杀入!
   ▼                                       ▼
```

---

## 一、入场条件
1. **挤压确认**: 连续至少 5 根 K 线布林带位于肯特纳通道内部；
2. **点火信号 (Fire)**: 布林带首次向外突破肯特纳通道（挤压释放）；
3. **动能方向**:
   - 多头: 动量直方图由负转正，或深蓝浅蓝阶梯上升；
   - 空头: 动量直方图由正转负，或深红浅红阶梯下降；
4. 收盘确认收在肯特纳通道外侧即可市价入场。

## 二、风控与止损
- 止损设置在肯特纳通道中轨（20 EMA）下方 0.5 * ATR；
- 单笔最大风险: 账户总净值的 2.0%。

## 三、止盈退出
- **动量减弱出场**: 当动量直方图连续 2 根柱体出现颜色淡化（动能衰竭信号）时清仓；
- 盈亏比达到 1:2.5 时主动分批止盈 60%。

---

## 🎥 经典视频教学与精讲推荐

- 📺 **Bilibili 精讲视频**:
  - [约翰·卡特经典《精通交易》TTM Squeeze 战法完全拆解](https://search.bilibili.com/all?keyword=TTM+Squeeze+波动率挤压策略)
  - [布林带与肯特纳通道双重结合的爆发行情捕捉法](https://search.bilibili.com/all?keyword=布林带肯特纳通道挤压)
- 📺 **YouTube 原作者大师课**:
  - [John Carter - How to Trade the TTM Squeeze for Big Moves](https://www.youtube.com/results?search_query=John+Carter+TTM+Squeeze+Strategy)
  - [Simpler Trading: Volatility Squeeze Strategy Explained](https://www.youtube.com/results?search_query=Simpler+Trading+TTM+Squeeze+Tutorial)
"""

STRATEGY_VWAP_CONTENT = """---
title: VWAP 机构量价锚定与均值回归策略
type: mean_reversion
status: active
symbols: [BTCUSDT, ETHUSDT]
timeframe: 5m
target_win_rate: 85.0%
profit_factor: 2.3
risk_reward_ratio: 1:1.6
indicators:
  - VWAP (Volume Weighted Average Price)
  - VWAP Standard Deviation Bands (±1σ, ±2σ, ±3σ)
  - Relative Volume (RVOL)
tags:
  - VWAP
  - 均值回归
  - 日内做市
  - 高胜率
---

# VWAP 机构量价锚定与均值回归策略

> [!NOTE] 华尔街基准锚
> VWAP（成交量加权平均价）是全球顶级算法交易和机构执行大额订单（TWAP/VWAP Algorithm）的成本中枢。价格在日内过度脱离 VWAP 超过 2.5 倍标准差时，在统计学上具备极高概率的均值回归吸引力。

## 🧭 知识库双向链接
- 知识地图中枢: [[00-知识库索引_MOC|知识库总索引]]
- 关联行为风控: [[03-交易习惯与行为进化/交易习惯进化追踪|交易习惯进化追踪]]
- 对比策略: [[01-交易策略/01-动态安全网格马丁策略(DCA)|动态安全网格马丁策略]]

---

## 📊 VWAP 标准差通道与做市回归模型

```text
 价格走势与标准差通道分布 (Standard Deviation Channels)
   │
   │  ─────────────────────────────── +3.0σ (统计学硬性止损线 / 强单边预警)
   │  ………………………………………………………………………………… +2.5σ 极值反转狙击带 🎯 (空单入场点)
   │      ╭─╮ (长上影 Pinbar + 成交量力竭萎缩)
   │      │ │
   │  ─────────────────────────────── +1.0σ (第一止盈位 TP1: 平仓 60%)
   │          ╲
   │           ╲ (价格受引力作用向核心均价回归)
   │            ▼
   │  ═══════════════════════════════ 日内核心 VWAP 基准线 🏁 (全量平仓 TP2)
   │
   │  ─────────────────────────────── -1.0σ (第一止盈位 TP1: 平仓 60%)
   │            ▲
   │           ╱ (多头引力回归)
   │      ╭─╮ ╱
   │  ………………………………………………………………………………… -2.5σ 极值反转狙击带 🎯 (多单入场点)
   │  ─────────────────────────────── -3.0σ (统计学硬性止损线)
   ▼
```

---

## 一、入场条件
1. **统计学极值偏离**: 价格触及或刺穿 VWAP ±2.5σ 标准差通道；
2. **成交量力竭确认**: 在极值区出现长上影线/长下影线（Pinbar），且伴随局部成交量萎缩或量价背离；
3. **反转触发**: 5m 收盘价重新回到 2.5σ 通道内部，立即开仓逆向买入/卖出。

## 二、风控与止损
- 止损线设置在 VWAP ±3.2σ 标准差外侧；
- 若发生强单边趋势行情（价格沿 3σ 持续钝化），立即严格按计划止损，不可心存侥幸。

## 三、止盈目标
- **TP1**: 价格回归至 VWAP ±1.0σ 标准差通道，止盈 60% 并改保本损；
- **TP2**: 价格完全回踩日内 VWAP 核心中轨线，全部止盈离场。

---

## 🎥 经典视频教学与精讲推荐

- 📺 **Bilibili 精讲视频**:
  - [华尔街顶级自营日内做市交易: VWAP 量价分布战法](https://search.bilibili.com/all?keyword=VWAP交易策略+标准差通道)
  - [如何利用 VWAP 标准差通道抓取高胜率反转波段](https://search.bilibili.com/all?keyword=VWAP均值回归实盘)
- 📺 **YouTube 权威教程**:
  - [SMB Capital - How to Trade VWAP Like a Professional Prop Trader](https://www.youtube.com/results?search_query=SMB+Capital+VWAP+Trading+Strategy)
  - [VWAP Trading Strategy Masterclass: Entries, Stops & Targets](https://www.youtube.com/results?search_query=VWAP+Trading+Strategy+Masterclass)
"""

STRATEGY_TURTLE_CONTENT = """---
title: 海龟双向 ATR 通道突破趋势策略
type: trend_breakout
status: active
symbols: [BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT]
timeframe: 1h
target_win_rate: 55.0%
profit_factor: 3.8
risk_reward_ratio: 1:4.5
indicators:
  - Donchian High/Low (20, 55)
  - ATR(20)
tags:
  - 海龟交易法则
  - 趋势跟踪
  - ATR通道
  - 金字塔加仓
---

# 海龟双向 ATR 通道突破趋势策略

> [!NOTE] 经典量化鼻祖
> 理查德·丹尼斯（Richard Dennis）的海龟交易法则是全球程序化交易的基石。其精髓不在于预测行情，而在于“机械式突破入场、严苛的波动率仓位分配 (Unit Allocation) 以及顺势金字塔加仓”。

## 🧭 知识库双向链接
- 知识地图中枢: [[00-知识库索引_MOC|知识库总索引]]
- 关联行为风控: [[03-交易习惯与行为进化/交易习惯进化追踪|交易习惯进化追踪]]
- 对比策略: [[01-交易策略/03-TTM_Squeeze波动率挤压突破策略|TTM挤压突破策略]]

---

## 📊 海龟仓位管理与金字塔式加仓矩阵

```mermaid
graph TD
    Entry[价格突破过去 20 根 K 线最高价\n建立初始头寸 1 Unit] --> Step1[价格上涨 +0.5 * ATR]
    Step1 --> Add1[加仓第 1 次: +1 Unit\n旧止损同步上移 0.5 ATR]
    Add1 --> Step2[价格继续上涨 +0.5 * ATR]
    Step2 --> Add2[加仓第 2 次: +1 Unit\n旧止损再次上移 0.5 ATR]
    Add2 --> Step3[价格继续上涨 +0.5 * ATR]
    Step3 --> Add3[加仓第 3 次: +1 Unit (达到满仓 4 Units)\n锁定大部分波段利润!]
    
    Add3 --> ExitCheck{价格跌破过去 10 根 K 线最低价?}
    ExitCheck -- 触发 --> FullExit[🟢 顺势大丰收清仓离场 (盈亏比 1:4.5)]
    ExitCheck -- 未触发 --> Add3
```

---

## 一、系统入场规则
1. **系统一 (突破 20 周期)**: 当现价突破过去 20 根 K 线最高价做多，跌破过去 20 根 K 线最低价做空；
2. **系统二 (突破 55 周期)**: 作为大趋势过滤，用于捕获世纪单边超级行情。

## 二、仓位管理与金字塔加仓 (Unit Allocation)
- **基准头寸单位**: 1 Unit = (账户总权益 * 1%) / (ATR(20) * 合约乘数)；
- **金字塔顺势加仓**: 价格每沿盈利方向移动 0.5 * ATR(20)，自动增加 1 个 Unit，最多加仓至 4 Units；
- 每次加仓后，所有旧头寸的止损点均同步抬升至最新加仓点 - 2.0 * ATR(20)。

## 三、止损与退出规则
- **硬性止损**: 任何头寸的绝对止损均为开仓价 - 2.0 * ATR(20)；
- **反向出场**: 多头在价格跌破过去 10 根 K 线最低价时平仓离场；空头在价格上穿过去 10 根 K 线最高价时平仓离场。

---

## 🎥 经典视频教学与精讲推荐

- 📺 **Bilibili 精讲视频**:
  - [海龟交易法则纪录片与理查德·丹尼斯传奇实验完全解读](https://search.bilibili.com/all?keyword=海龟交易法则+理查德丹尼斯)
  - [趋势跟踪之王: 海龟加仓法与 ATR 头寸管理实盘演示](https://search.bilibili.com/all?keyword=海龟交易法则+仓位管理)
- 📺 **YouTube 权威纪录片与精解**:
  - [The Complete Turtle Trading System Explained (Rayner Teo)](https://www.youtube.com/results?search_query=Rayner+Teo+The+Turtle+Trading+Strategy+Explained)
  - [How Turtle Traders Made Millions with Trend Following](https://www.youtube.com/results?search_query=Turtle+Trading+Experiment+Trend+Following)
"""

STRATEGY_DIVERGENCE_CONTENT = """---
title: 多周期 EMA 共振与 RSI 顶底背离策略
type: momentum_divergence
status: active
symbols: [BTCUSDT, ETHUSDT, SOLUSDT]
timeframe: 15m
target_win_rate: 78.0%
profit_factor: 2.5
risk_reward_ratio: 1:2.2
indicators:
  - 4h EMA55
  - 15m EMA9 / EMA21
  - RSI(14)
tags:
  - RSI背离
  - 多周期共振
  - 均线趋势
  - 高胜率狙击
---

# 多周期 EMA 共振与 RSI 顶底背离策略

> [!NOTE] 顺大势，逆小势极值
> 胜率最高的交易往往发生在“大级别趋势明确、小级别出现衰竭背离”的瞬间。4h 均线提供大方向指引，15m RSI 顶底背离提供转折点，EMA 金叉死叉作为扣动扳机的信号。

## 🧭 知识库双向链接
- 知识地图中枢: [[00-知识库索引_MOC|知识库总索引]]
- 关联行为风控: [[03-交易习惯与行为进化/交易习惯进化追踪|交易习惯进化追踪]]
- 对比策略: [[01-交易策略/02-SMC聪明钱订单块与流动性劫持策略|SMC聪明钱策略]]

---

## 📊 多周期双层滤波逻辑架构

```mermaid
flowchart LR
    subgraph HigherTF [大周期 4h 趋势过滤]
        H1[4h 现价 >= EMA55 均线?] -->|是| LongFilter[锁定仅做多单]
        H1 -->|否| ShortFilter[锁定仅做空单]
    end

    subgraph LowerTF [小周期 15m 极值狙击]
        LongFilter --> CheckDivL{15m 价格创新低\n但 RSI 谷底抬高 (底背离)?}
        CheckDivL -- 是 --> TriggerLong[EMA9 上穿 EMA21 金叉 🎯 买入!]
        
        ShortFilter --> CheckDivS{15m 价格创新高\n但 RSI 峰顶降低 (顶背离)?}
        CheckDivS -- 是 --> TriggerShort[EMA9 下穿 EMA21 死叉 🎯 做空!]
    end
```

---

## 📈 K 线形态与 RSI 背离波浪图解

```text
 价格走势 (Price - 连续下挫创波段新低)
   │ 
   │    ╭─╮
   │    │ │
   │    ╰─╯   ╭─╮
   │     ╲    │ │  (价格第1波谷)
   │      ╲   ╰─╯
   │       ╲   │   
   │        ╲ ╭─╮  (价格第2波谷 ── 创出明显新低 🔻)
   │         ╲│ │
   │          ╰─╯
   │
 ──┼──────────────────────────────────────────────────
   │ RSI(14) 指标走势 (动能出现底背离，谷底步步抬升 🚀)
   │          ▲
   │        ╭─╮  ▲
   │        │ │ ╭─╮ (RSI第2谷底 > RSI第1谷底 ── 动能耗尽反转信号!)
   │  ──────╰─╯─╰─╯────────────────────── 超卖警戒线 (RSI: 30)
   ▼                                       🎯 EMA 金叉扣动扳机入场!
```

---

## 一、多头入场条件
1. **大周期方向**: 4h 级别现价位于 EMA55 上方，趋势偏多；
2. **底背离形成**: 15m 价格创出局部波段新低，但 RSI(14) 谷底逐步抬高（经典底背离）；
3. **扳机触发**: 15m EMA9 上穿 EMA21 形成金叉，且收盘价实体站稳 EMA9 之上。

## 二、空头入场条件
1. **大周期方向**: 4h 级别现价位于 EMA55 下方，趋势偏空；
2. **顶背离形成**: 15m 价格创出局部波段新高，但 RSI(14) 峰顶逐步走低（经典顶背离）；
3. **扳机触发**: 15m EMA9 下穿 EMA21 形成死叉，收盘跌破 EMA9。

## 三、风控与止盈
- **初始止损**: 锚定发生背离的影线极端高低点外加 1.5 * ATR；
- **盈亏比目标**: 固定 1:2.0 分批平仓 70%，剩余仓位依据均线反向交叉退出。

---

## 🎥 经典视频教学与精讲推荐

- 📺 **Bilibili 精讲视频**:
  - [RSI指标终极用法: 顶底背离与隐藏背离高胜率实战](https://search.bilibili.com/all?keyword=RSI顶底背离+多周期EMA共振)
  - [多周期均线共振交易系统：顺大势逆小势的核心细节](https://search.bilibili.com/all?keyword=多周期均线共振交易系统)
- 📺 **YouTube 权威教程**:
  - [Rayner Teo - The Ultimate RSI Trading Strategy (Divergence & Momentum)](https://www.youtube.com/results?search_query=Rayner+Teo+RSI+Divergence+Strategy)
  - [How to Trade RSI Divergence Like a Pro (The Moving Average)](https://www.youtube.com/results?search_query=The+Moving+Average+RSI+Divergence)
"""

GLOBAL_HIGH_WINRATE_STRATEGIES = {
    "01-动态安全网格马丁策略(DCA).md": STRATEGY_MARTINGALE_CONTENT,
    "02-SMC聪明钱订单块与流动性劫持策略.md": STRATEGY_SMC_CONTENT,
    "03-TTM_Squeeze波动率挤压突破策略.md": STRATEGY_TTM_SQUEEZE_CONTENT,
    "04-VWAP机构量价锚定与均值回归策略.md": STRATEGY_VWAP_CONTENT,
    "05-海龟双向ATR通道突破趋势策略.md": STRATEGY_TURTLE_CONTENT,
    "06-多周期EMA共振与RSI顶底背离策略.md": STRATEGY_DIVERGENCE_CONTENT,
}

DATAVIEW_DASHBOARD_CONTENT = """---
title: 量化交易实盘与策略数据总看板
cssclass: dashboard, cards
tags:
  - 看板
  - Dataview
  - 实盘数据
  - 策略监控
  - 热力图
---

# 🎛️ 量化交易实盘与策略数据总看板

> [!TIP] 插件协同数据中枢
> 本看板依托 **Dataview**、**Heatmap Calendar** 与 **Obsidian Charts** 插件构建，实时聚合交易知识库中的所有策略运行表现、每日交易复盘记录、交互式 HTML 深度图表以及行情简报流。

---

## 📅 实盘交易日历热力图 (Heatmap Calendar)

```dataviewjs
// 利用 dataviewjs 配合 heatmap-calendar 插件渲染实盘盈亏活跃度
const calendarData = {
    year: new Date().getFullYear(),
    colors: {
        blue: ["#8ecae6", "#219ebc", "#023047", "#ffb703", "#fb8500"],
        green: ["#d8f3dc", "#95d5b2", "#52b788", "#2d6a4f", "#1b4332"],
        red: ["#ffccd5", "#ff758f", "#c9184a", "#800f2f", "#590d22"]
    },
    entries: []
};

for (let page of dv.pages('"02-交易复盘/每日总结"')) {
    if (page.date && page.net_pnl !== undefined) {
        calendarData.entries.push({
            date: page.date,
            intensity: Math.min(Math.abs(page.net_pnl), 100),
            content: await dv.span(`[${page.net_pnl > 0 ? '+' : ''}${page.net_pnl}U](${page.file.name})`),
            color: page.net_pnl >= 0 ? "green" : "red"
        });
    }
}
if (window.renderHeatmapCalendar) {
    renderHeatmapCalendar(this.container, calendarData);
} else {
    dv.paragraph("> 💡 *提示: Heatmap Calendar 插件启用后将在此呈现每日盈亏色块日历。*");
}
```

---

## 📈 核心策略综合战力指标 (Obsidian Charts)

```chart
type: line
labels: [第1周, 第2周, 第3周, 第4周, 当前最新]
series:
  - title: 策略矩阵综合胜率 (%)
    data: [72, 78, 83, 87, 91.5]
    borderColor: "#10b981"
    backgroundColor: "rgba(16, 185, 129, 0.2)"
  - title: 目标盈亏比 (Profit Factor)
    data: [1.6, 1.8, 2.0, 2.1, 2.25]
    borderColor: "#3b82f6"
    backgroundColor: "rgba(59, 130, 246, 0.2)"
```

---

## 🚀 实盘策略运行矩阵 (Dataview DQL)

```dataview
TABLE WITHOUT ID
  file.link AS "策略名称",
  type AS "策略分类",
  status AS "运行状态",
  timeframe AS "主监控周期",
  target_win_rate AS "目标胜率",
  profit_factor AS "目标盈亏比",
  max_risk_per_trade AS "单笔风控",
  symbols AS "适配标的"
FROM "01-交易策略"
WHERE file.name != "00-策略库索引"
SORT status ASC, target_win_rate DESC
```

---

## 📊 每日实盘复盘日记流 (Dataview DQL)

```dataview
TABLE WITHOUT ID
  file.link AS "复盘日期",
  net_pnl AS "净盈亏 (USDT)",
  win_rate + "%" AS "当日胜率",
  total_trades AS "平仓笔数",
  file.mtime AS "最后同步时间"
FROM "02-交易复盘/每日总结"
SORT file.name DESC
LIMIT 15
```

---

## 🌐 交互式 HTML 交易图表全景库

```dataview
LIST
FROM "02-交易复盘/HTML图表"
SORT file.name DESC
LIMIT 12
```

---

## 📰 最新行情简报与博客洞察

```dataview
TABLE WITHOUT ID
  file.link AS "简报/博客标题",
  platform AS "发布平台",
  tone AS "风格",
  tags AS "标签",
  file.cday AS "生成时间"
FROM "00-原始资料与灵感库/行情简报与博客"
SORT file.cday DESC
LIMIT 10
```

---
*由量化交易系统数据总看板自动聚合 · [[00-知识库索引_MOC|返回知识库总索引]] · [[01-策略研发与实盘看板_Kanban|切换至策略研发看板]]*
"""

KANBAN_BOARD_CONTENT = """---

kanban-plugin: basic

---

## 💡 策略灵感与原始研报

- [ ] [[00-原始资料与灵感库/README|卡帕西 LLM-Wiki 灵感池说明]]
- [ ] 巨鲸链上多空清算图与资金费率套利灵感
- [ ] 结合 DeepSeek / AI 大模型的盘前量价结构推演


## 🧪 回测与参数优化中

- [ ] [[01-交易策略/05-海龟双向ATR通道突破趋势策略|海龟双向ATR通道突破策略]]
  - 标的: BTC / ETH / SOL
  - 优化方向: 动态加仓与唐奇安突破滤波
- [ ] [[01-交易策略/03-TTM_Squeeze波动率挤压突破策略|TTM Squeeze 波动率挤压策略]]
  - 优化方向: 结合布林带与肯特纳通道突破判定


## 🚀 实盘运行中策略

- [ ] [[01-交易策略/01-动态安全网格马丁策略(DCA)|动态安全网格马丁策略 (DCA)]]
  - 胜率: 91.5% | 风控: 12% 熔断
- [ ] [[01-交易策略/02-SMC聪明钱订单块与流动性劫持策略|SMC聪明钱订单块策略]]
  - 机构供需区 (Order Block) + 流动性劫持 (FVG)
- [ ] [[01-交易策略/04-VWAP机构量价锚定与均值回归策略|VWAP机构量价锚定策略]]
  - 日内均值回归，适合震荡市
- [ ] [[01-交易策略/06-多周期EMA共振与RSI顶底背离策略|多周期EMA共振与RSI背离策略]]
  - 顺大势逆小势，高胜率反转确认
- [ ] [[01-交易策略/EMA双均线趋势跟踪策略|EMA双均线趋势跟踪策略]]
  - 自动化趋势跟随底仓


## ⚠️ 风险观察与限额监控

- [ ] [[03-交易习惯与行为进化/交易习惯进化追踪|交易习惯与五维心理行为雷达]]
  - 纪律性防破防熔断
- [ ] 极端单边插针行情下的马丁加仓间距拉伸监控


## 📦 已归档/停用策略

- [ ] 固定10点翻倍古典马丁策略 (已淘汰 - 单边穿仓风险过高)
- [ ] 单纯RSI超买超卖左侧逆势抓顶底 (已淘汰 - 顺势行情容易踏空爆仓)




%% kanban:settings
```
{"kanban-plugin":"basic"}
```
%%
"""

TRADING_DASHBOARD_CONTENT = """---
title: 量化交易员控制台仪表盘 (Trading Dashboard)
cssclass: dashboard, cards, banner
tags:
  - 仪表盘
  - 驾驶舱
  - 控制台
  - 实盘监控
  - Dataview
---

<style>
/* ===================================================
   QUANT DASHBOARD - MODERN DYNAMIC WEB FRONTEND STYLES
   (Full Support for Both Light & Dark Themes)
   =================================================== */

:root {
  --dash-header-bg: var(--background-secondary, #f8fafc);
  --dash-header-border: var(--border-color, rgba(0, 0, 0, 0.1));
  --dash-card-bg: var(--background-primary, #ffffff);
  --dash-card-border: var(--border-color, rgba(0, 0, 0, 0.08));
  --dash-card-hover-bg: var(--background-secondary-alt, #f1f5f9);
  --dash-card-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
  --dash-card-hover-shadow: 0 12px 28px rgba(99, 102, 241, 0.18);
  --dash-text-title: var(--text-normal, #0f172a);
  --dash-text-desc: var(--text-muted, #475569);
  --dash-text-section: var(--text-normal, #0f172a);
  --dash-media-bg: var(--background-secondary, #f1f5f9);
  --dash-tag-bg: rgba(0, 0, 0, 0.04);
  --dash-tag-border: rgba(0, 0, 0, 0.08);
  --dash-tag-color: var(--text-muted, #475569);
  --dash-btn-bg: rgba(99, 102, 241, 0.1);
  --dash-btn-color: #4f46e5;
  --dash-btn-border: rgba(99, 102, 241, 0.25);
}

.theme-dark {
  --dash-header-bg: linear-gradient(135deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%);
  --dash-header-border: rgba(255, 255, 255, 0.12);
  --dash-card-bg: rgba(30, 41, 59, 0.75);
  --dash-card-border: rgba(255, 255, 255, 0.08);
  --dash-card-hover-bg: rgba(30, 41, 59, 0.95);
  --dash-card-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  --dash-card-hover-shadow: 0 12px 28px rgba(0, 0, 0, 0.4), 0 0 20px rgba(124, 58, 237, 0.25);
  --dash-text-title: #f1f5f9;
  --dash-text-desc: #94a3b8;
  --dash-text-section: #f8fafc;
  --dash-media-bg: #090d16;
  --dash-tag-bg: rgba(255, 255, 255, 0.05);
  --dash-tag-border: rgba(255, 255, 255, 0.08);
  --dash-tag-color: #cbd5e1;
  --dash-btn-bg: rgba(99, 102, 241, 0.15);
  --dash-btn-color: #a5b4fc;
  --dash-btn-border: rgba(99, 102, 241, 0.3);
}

.theme-light {
  --dash-header-bg: linear-gradient(135deg, #f8fafc 0%, #edf2f7 100%);
  --dash-header-border: rgba(0, 0, 0, 0.1);
  --dash-card-bg: #ffffff;
  --dash-card-border: rgba(0, 0, 0, 0.08);
  --dash-card-hover-bg: #f8fafc;
  --dash-card-shadow: 0 4px 16px rgba(0, 0, 0, 0.05);
  --dash-card-hover-shadow: 0 12px 24px rgba(99, 102, 241, 0.15);
  --dash-text-title: #0f172a;
  --dash-text-desc: #475569;
  --dash-text-section: #0f172a;
  --dash-media-bg: #f1f5f9;
  --dash-tag-bg: rgba(0, 0, 0, 0.04);
  --dash-tag-border: rgba(0, 0, 0, 0.08);
  --dash-tag-color: #475569;
  --dash-btn-bg: rgba(99, 102, 241, 0.08);
  --dash-btn-color: #4338ca;
  --dash-btn-border: rgba(99, 102, 241, 0.25);
}

/* 1. 顶部控制栏与导航胶囊 */
.ob-web-header {
  background: var(--dash-header-bg);
  border: 1px solid var(--dash-header-border);
  border-radius: 14px;
  padding: 16px 20px;
  margin-bottom: 20px;
  backdrop-filter: blur(12px);
  box-shadow: var(--dash-card-shadow);
}

.ob-web-brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--dash-card-border);
}

.ob-web-brand-title {
  font-size: 17px;
  font-weight: 800;
  letter-spacing: 0.5px;
  background: linear-gradient(90deg, #0284c7, #6366f1, #9333ea);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  display: flex;
  align-items: center;
  gap: 8px;
}

.ob-web-status-pills {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.ob-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 20px;
  background: var(--dash-tag-bg);
  border: 1px solid var(--dash-tag-border);
  color: var(--dash-text-desc);
}

.ob-pill-success {
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.3);
  color: #059669;
}

.ob-pill-warning {
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.3);
  color: #d97706;
}

.ob-pill-accent {
  background: rgba(139, 92, 246, 0.12);
  border-color: rgba(139, 92, 246, 0.3);
  color: #7c3aed;
}

/* 2. 顶部导航标签栏 (快速跳转锚点) */
.ob-nav-tabs {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.ob-tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 14px;
  border-radius: 8px;
  background: var(--dash-tag-bg);
  border: 1px solid var(--dash-tag-border);
  color: var(--dash-text-title) !important;
  text-decoration: none !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
}

.ob-tab-btn:hover {
  background: rgba(99, 102, 241, 0.15);
  border-color: rgba(99, 102, 241, 0.5);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);
  color: #4f46e5 !important;
}

.ob-tab-btn-primary {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  border-color: #818cf8;
  color: #ffffff !important;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25);
}

.ob-tab-btn-primary:hover {
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.4);
  color: #ffffff !important;
}

/* 3. 动态栅格卡片系统 (Web App Grid Layout) */
.ob-grid-6 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
  margin: 16px 0 24px 0;
}

.ob-grid-7 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  margin: 16px 0 24px 0;
}

.ob-grid-2 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 16px;
  margin: 16px 0 24px 0;
}

/* 4. 交互式卡片 (Interactive Tile) */
.ob-web-card {
  position: relative;
  display: flex;
  flex-direction: column;
  background: var(--dash-card-bg);
  border: 1px solid var(--dash-card-border);
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: var(--dash-card-shadow);
  text-decoration: none !important;
  color: inherit !important;
  cursor: pointer;
}

.ob-web-card:hover {
  transform: translateY(-4px);
  border-color: rgba(139, 92, 246, 0.55);
  box-shadow: var(--dash-card-hover-shadow);
  background: var(--dash-card-hover-bg);
}

.ob-card-media {
  position: relative;
  width: 100%;
  overflow: hidden;
  background: var(--dash-media-bg);
}

.ob-card-media img {
  width: 100%;
  height: auto;
  display: block;
  transition: transform 0.35s ease;
}

.ob-web-card:hover .ob-card-media img {
  transform: scale(1.03);
}

.ob-card-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.5px;
  padding: 3px 8px;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.82);
  border: 1px solid rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(8px);
  color: #38bdf8;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
  z-index: 2;
}

.ob-card-body {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  flex-grow: 1;
}

.ob-card-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--dash-text-title);
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.ob-card-desc {
  font-size: 12px;
  color: var(--dash-text-desc);
  line-height: 1.5;
  margin-bottom: 12px;
  flex-grow: 1;
}

.ob-card-metrics {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.ob-metric-tag {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--dash-tag-bg);
  border: 1px solid var(--dash-tag-border);
  color: var(--dash-tag-color);
}

.ob-metric-tag-green {
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.25);
  color: #059669;
}

.ob-metric-tag-purple {
  background: rgba(139, 92, 246, 0.12);
  border-color: rgba(139, 92, 246, 0.25);
  color: #7c3aed;
}

/* 5. 卡片操作跳转按钮 */
.ob-card-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--dash-btn-bg);
  border: 1px solid var(--dash-btn-border);
  color: var(--dash-btn-color) !important;
  text-decoration: none !important;
  transition: all 0.2s ease;
  margin-top: auto;
}

.ob-web-card:hover .ob-card-btn {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  border-color: #818cf8;
  color: #ffffff !important;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
}

/* 6. Section 分区标头 */
.ob-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 32px 0 16px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--dash-card-border);
}

.ob-section-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--dash-text-section);
  display: flex;
  align-items: center;
  gap: 8px;
}

.ob-section-action {
  font-size: 12px;
  color: #6366f1;
  text-decoration: none;
}

</style>

<div class="ob-web-header">
<div class="ob-web-brand">
<div class="ob-web-brand-title">
<span>⚡</span> QUANT COCKPIT · 量化交易员控制台仪表盘
</div>
<div class="ob-web-status-pills">
<span class="ob-pill ob-pill-success">🟢 节点在线: 127.0.0.1:8800</span>
<span class="ob-pill ob-pill-accent">🚀 在线策略战力矩阵: 7 大主力</span>
<span class="ob-pill ob-pill-warning">🛡️ 核心风控保险丝: 3.0% 熔断</span>
</div>
</div>

<div class="ob-nav-tabs">
<a class="internal-link ob-tab-btn ob-tab-btn-primary" data-href="00-交易数据看板_Dataview" href="00-交易数据看板_Dataview">📊 实盘数据</a>
<a class="internal-link ob-tab-btn" data-href="01-策略研发与实盘看板_Kanban" href="01-策略研发与实盘看板_Kanban">📋 研发看板</a>
<a class="internal-link ob-tab-btn" data-href="00-每日交易待办与纪律清单" href="00-每日交易待办与纪律清单">✅ 每日待办SOP</a>
<a class="internal-link ob-tab-btn" data-href="00-知识库索引_MOC" href="00-知识库索引_MOC">🧭 知识总图谱</a>
<a class="internal-link ob-tab-btn" data-href="04-币安广场与个人博客/00-币安广场博客工作台_Kanban" href="04-币安广场与个人博客/00-币安广场博客工作台_Kanban">📰 币安广场</a>
<a class="internal-link ob-tab-btn" data-href="03-交易习惯与行为进化/交易习惯进化追踪" href="03-交易习惯与行为进化/交易习惯进化追踪">🧠 心理雷达</a>
<a class="ob-tab-btn" href="http://127.0.0.1:8800" target="_blank">🖥️ 打开 Web 交易终端 ➔</a>
</div>
</div>

![[00-原始资料与灵感库/视觉素材库/dashboard_hero_banner.png|100%]]

<div class="ob-section-header">
<div class="ob-section-title">🕹️ 驾驶舱快捷操作控制台 (Core Portals)</div>
<span class="ob-section-action">点击卡片一键直达对应板块 ➔</span>
</div>

<div class="ob-grid-6">
<!-- Card 1: 数据中心 -->
<a class="internal-link ob-web-card" data-href="00-交易数据看板_Dataview" href="00-交易数据看板_Dataview">
<div class="ob-card-media">
<span class="ob-card-badge">LIVE 实时</span>

![[00-原始资料与灵感库/视觉素材库/nav_data_center.png|100%]]

</div>
<div class="ob-card-body">
<div class="ob-card-title">📊 交易数据总看板</div>
<div class="ob-card-desc">Dataview 实时战绩流、盈亏分布与多空胜率统计</div>
<div class="ob-card-metrics">
<span class="ob-metric-tag ob-metric-tag-green">动态聚合</span>
<span class="ob-metric-tag">战绩流</span>
</div>
<div class="ob-card-btn">⚡ 点击进入数据总看板 ➔</div>
</div>
</a>

<!-- Card 2: 策略研发看板 -->
<a class="internal-link ob-web-card" data-href="01-策略研发与实盘看板_Kanban" href="01-策略研发与实盘看板_Kanban">
<div class="ob-card-media">
<span class="ob-card-badge">KANBAN 泳道</span>

![[00-原始资料与灵感库/视觉素材库/nav_strategy_kanban.png|100%]]

</div>
<div class="ob-card-body">
<div class="ob-card-title">📋 策略研发与实盘看板</div>
<div class="ob-card-desc">全周期管理：灵感 ➔ 回测 ➔ 实盘 ➔ 归档</div>
<div class="ob-card-metrics">
<span class="ob-metric-tag ob-metric-tag-purple">生命周期</span>
<span class="ob-metric-tag">研发管线</span>
</div>
<div class="ob-card-btn">⚡ 点击进入策略看板 ➔</div>
</div>
</a>

<!-- Card 3: 每日SOP与待办 -->
<a class="internal-link ob-web-card" data-href="00-每日交易待办与纪律清单" href="00-每日交易待办与纪律清单">
<div class="ob-card-media">
<span class="ob-card-badge">DAILY 每日</span>

![[00-原始资料与灵感库/视觉素材库/nav_daily_sop.png|100%]]

</div>
<div class="ob-card-body">
<div class="ob-card-title">✅ 每日交易待办与纪律清单</div>
<div class="ob-card-desc">盘前准备 · 盘中自律防手痒 · 盘后深度复盘归档</div>
<div class="ob-card-metrics">
<span class="ob-metric-tag ob-metric-tag-green">严格自律</span>
<span class="ob-metric-tag">SOP闭环</span>
</div>
<div class="ob-card-btn">⚡ 点击进入待办与SOP ➔</div>
</div>
</a>

<!-- Card 4: 知识图谱 MOC -->
<a class="internal-link ob-web-card" data-href="00-知识库索引_MOC" href="00-知识库索引_MOC">
<div class="ob-card-media">
<span class="ob-card-badge">LLM-WIKI</span>

![[00-原始资料与灵感库/视觉素材库/nav_knowledge_moc.png|100%]]

</div>
<div class="ob-card-body">
<div class="ob-card-title">🧭 知识库总图谱 (MOC)</div>
<div class="ob-card-desc">卡帕西自维护编译器 · 双向引用图谱与健康度</div>
<div class="ob-card-metrics">
<span class="ob-metric-tag">全局知识</span>
<span class="ob-metric-tag ob-metric-tag-purple">自动编译</span>
</div>
<div class="ob-card-btn">⚡ 点击进入知识图谱 ➔</div>
</div>
</a>

<!-- Card 5: 交互式HTML图表 -->
<a class="internal-link ob-web-card" data-href="02-交易复盘/HTML图表" href="02-交易复盘/HTML图表">
<div class="ob-card-media">
<span class="ob-card-badge">INTERACTIVE</span>

![[00-原始资料与灵感库/视觉素材库/nav_html_charts.png|100%]]

</div>
<div class="ob-card-body">
<div class="ob-card-title">🌐 交互图表复盘库</div>
<div class="ob-card-desc">独立 HTML 深度 K 线、实盘买卖点轨迹与量价研报</div>
<div class="ob-card-metrics">
<span class="ob-metric-tag ob-metric-tag-green">买卖点打点</span>
<span class="ob-metric-tag">全景轨迹</span>
</div>
<div class="ob-card-btn">⚡ 点击浏览交互图表 ➔</div>
</div>
</a>

<!-- Card 6: 币安广场工作室 -->
<a class="internal-link ob-web-card" data-href="04-币安广场与个人博客/00-币安广场博客工作台_Kanban" href="04-币安广场与个人博客/00-币安广场博客工作台_Kanban">
<div class="ob-card-media">
<span class="ob-card-badge">STUDIO 创作者</span>

![[00-原始资料与灵感库/视觉素材库/nav_blog_studio.png|100%]]

</div>
<div class="ob-card-body">
<div class="ob-card-title">📰 币安广场工作台</div>
<div class="ob-card-desc">爆款文章模板、盘前快讯生成与全自动定时排期</div>
<div class="ob-card-metrics">
<span class="ob-metric-tag ob-metric-tag-purple">流量引擎</span>
<span class="ob-metric-tag">定时发布</span>
</div>
<div class="ob-card-btn">⚡ 点击进入广场工作台 ➔</div>
</div>
</a>
</div>

<div class="ob-section-header">
<div class="ob-section-title">🚀 在线策略战力矩阵 (Live Quant Strategies)</div>
<span class="ob-section-action">点击卡片打开对应量化策略核心笔记 ➔</span>
</div>

<div class="ob-grid-7">
<!-- Strategy 1: DCA -->
<a class="internal-link ob-web-card" data-href="01-交易策略/01-动态安全网格马丁策略(DCA)" href="01-交易策略/01-动态安全网格马丁策略(DCA)">
<div class="ob-card-media">
<span class="ob-card-badge">胜率 91.5%</span>

![[00-原始资料与灵感库/视觉素材库/card_dca_martingale.png|100%]]

</div>
<div class="ob-card-body">
<div class="ob-card-title">🛡️ 01 · 动态安全网格马丁 (DCA)</div>
<div class="ob-card-desc">ATR 动态网格间距、递减倍率防爆仓、震荡行情收割利器</div>
<div class="ob-card-metrics">
<span class="ob-metric-tag ob-metric-tag-green">胜率 91.5%</span>
<span class="ob-metric-tag">盈亏比 1:2.1</span>
<span class="ob-metric-tag ob-metric-tag-purple">极低爆仓</span>
</div>
<div class="ob-card-btn">🎯 点击打开策略研报 ➔</div>
</div>
</a>

<!-- Strategy 2: SMC -->
<a class="internal-link ob-web-card" data-href="01-交易策略/02-SMC聪明钱订单块与流动性劫持策略" href="01-交易策略/02-SMC聪明钱订单块与流动性劫持策略">
<div class="ob-card-media">
<span class="ob-card-badge">盈亏比 1:3.4</span>

![[00-原始资料与灵感库/视觉素材库/card_smc_orderblock.png|100%]]

</div>
<div class="ob-card-body">
<div class="ob-card-title">🏛️ 02 · SMC 聪明钱订单块</div>
<div class="ob-card-desc">机构流动性猎杀、失衡区 FVG、订单块 Order Block 挂单狙击</div>
<div class="ob-card-metrics">
<span class="ob-metric-tag ob-metric-tag-green">胜率 72.0%</span>
<span class="ob-metric-tag ob-metric-tag-purple">盈亏比 1:3.4</span>
<span class="ob-metric-tag">机构足迹</span>
</div>
<div class="ob-card-btn">🎯 点击打开策略研报 ➔</div>
</div>
</a>

<!-- Strategy 3: TTM -->
<a class="internal-link ob-web-card" data-href="01-交易策略/03-TTM_Squeeze波动率挤压突破策略" href="01-交易策略/03-TTM_Squeeze波动率挤压突破策略">
<div class="ob-card-media">
<span class="ob-card-badge">高动量</span>

![[00-原始资料与灵感库/视觉素材库/card_ttm_squeeze.png|100%]]

</div>
<div class="ob-card-body">
<div class="ob-card-title">💥 03 · TTM Squeeze 波动率挤压</div>
<div class="ob-card-desc">布林带收敛入肯特纳通道，变盘蓄势后动量爆发单边大趋势</div>
<div class="ob-card-metrics">
<span class="ob-metric-tag ob-metric-tag-green">胜率 76.5%</span>
<span class="ob-metric-tag">盈亏比 1:2.6</span>
<span class="ob-metric-tag ob-metric-tag-purple">爆发突破</span>
</div>
<div class="ob-card-btn">🎯 点击打开策略研报 ➔</div>
</div>
</a>

<!-- Strategy 4: VWAP -->
<a class="internal-link ob-web-card" data-href="01-交易策略/04-VWAP机构量价锚定与均值回归策略" href="01-交易策略/04-VWAP机构量价锚定与均值回归策略">
<div class="ob-card-media">
<span class="ob-card-badge">胜率 85.0%</span>

![[00-原始资料与灵感库/视觉素材库/card_vwap_reversion.png|100%]]

</div>
<div class="ob-card-body">
<div class="ob-card-title">🌊 04 · VWAP 机构量价锚定回归</div>
<div class="ob-card-desc">机构日内基准锚线、2.5倍标准差通道超买超卖极限回归</div>
<div class="ob-card-metrics">
<span class="ob-metric-tag ob-metric-tag-green">胜率 85.0%</span>
<span class="ob-metric-tag">盈亏比 1:2.3</span>
<span class="ob-metric-tag">均值套利</span>
</div>
<div class="ob-card-btn">🎯 点击打开策略研报 ➔</div>
</div>
</a>

<!-- Strategy 5: Turtle -->
<a class="internal-link ob-web-card" data-href="01-交易策略/05-海龟双向ATR通道突破趋势策略" href="01-交易策略/05-海龟双向ATR通道突破趋势策略">
<div class="ob-card-media">
<span class="ob-card-badge">盈亏比 1:3.8</span>

![[00-原始资料与灵感库/视觉素材库/card_turtle_breakout.png|100%]]

</div>
<div class="ob-card-body">
<div class="ob-card-title">🐢 05 · 海龟双向 ATR 通道突破</div>
<div class="ob-card-desc">20日唐奇安高低点通道突破，结合真实波幅 ATR 顺势滚仓加仓</div>
<div class="ob-card-metrics">
<span class="ob-metric-tag">胜率 55.0%</span>
<span class="ob-metric-tag ob-metric-tag-purple">盈亏比 1:3.8</span>
<span class="ob-metric-tag ob-metric-tag-green">大牛大熊利器</span>
</div>
<div class="ob-card-btn">🎯 点击打开策略研报 ➔</div>
</div>
</a>

<!-- Strategy 6: EMA Divergence -->
<a class="internal-link ob-web-card" data-href="01-交易策略/06-多周期EMA共振与RSI顶底背离策略" href="01-交易策略/06-多周期EMA共振与RSI顶底背离策略">
<div class="ob-card-media">
<span class="ob-card-badge">转折狙击</span>

![[00-原始资料与灵感库/视觉素材库/card_ema_divergence.png|100%]]

</div>
<div class="ob-card-body">
<div class="ob-card-title">⚡ 06 · EMA 共振与 RSI 顶底背离</div>
<div class="ob-card-desc">4h 高级别大势过滤，15m 价格破新高/低但 RSI 背离反转</div>
<div class="ob-card-metrics">
<span class="ob-metric-tag ob-metric-tag-green">胜率 78.0%</span>
<span class="ob-metric-tag">盈亏比 1:2.5</span>
<span class="ob-metric-tag ob-metric-tag-purple">抄底逃顶</span>
</div>
<div class="ob-card-btn">🎯 点击打开策略研报 ➔</div>
</div>
</a>

<!-- Strategy 7: EMA Trend -->
<a class="internal-link ob-web-card" data-href="01-交易策略/EMA双均线趋势跟踪策略" href="01-交易策略/EMA双均线趋势跟踪策略">
<div class="ob-card-media">
<span class="ob-card-badge">经典经典</span>

![[00-原始资料与灵感库/视觉素材库/card_ema_trend.png|100%]]

</div>
<div class="ob-card-body">
<div class="ob-card-title">📈 07 · EMA 双均线趋势跟踪</div>
<div class="ob-card-desc">EMA 9 与 EMA 21 金叉死叉，配合成交量放量确认强趋势</div>
<div class="ob-card-metrics">
<span class="ob-metric-tag ob-metric-tag-green">胜率 75.0%</span>
<span class="ob-metric-tag">盈亏比 1:2.0</span>
<span class="ob-metric-tag">经典波段</span>
</div>
<div class="ob-card-btn">🎯 点击打开策略研报 ➔</div>
</div>
</a>
</div>

<div class="ob-section-header">
<div class="ob-section-title">📊 策略效能矩阵与风控雷达态势 (Analytics & Risk Radar)</div>
<span class="ob-section-action">点击卡片跳转查看行为与习惯进化详情 ➔</span>
</div>

<div class="ob-grid-2">
<div class="ob-web-card">
<div class="ob-card-media">

![[00-原始资料与灵感库/视觉素材库/strategy_winrate_matrix.png|100%]]

</div>
<div class="ob-card-body">
<div class="ob-card-title">📈 全天候量化策略对比矩阵</div>
<div class="ob-card-desc">历史实盘理论胜率（绿色柱）与目标盈亏比（金色折线）综合量化评估</div>
<div class="ob-card-metrics">
<span class="ob-metric-tag ob-metric-tag-green">最高胜率 91.5% (DCA)</span>
<span class="ob-metric-tag ob-metric-tag-purple">最高盈亏比 1:3.8 (海龟)</span>
</div>
</div>
</div>

<a class="internal-link ob-web-card" data-href="03-交易习惯与行为进化/交易习惯进化追踪" href="03-交易习惯与行为进化/交易习惯进化追踪">
<div class="ob-card-media">
<span class="ob-card-badge">评分 85/100</span>

![[00-原始资料与灵感库/视觉素材库/risk_radar_gauge.png|100%]]

</div>
<div class="ob-card-body">
<div class="ob-card-title">🛡️ 交易员五维行为风控雷达</div>
<div class="ob-card-desc">严格止损(90) · 抗追涨杀跌(85) · 仓位风控(88) · 计划执行(82) · 复盘自省(80)</div>
<div class="ob-card-metrics">
<span class="ob-metric-tag ob-metric-tag-green">自律期 (稳健)</span>
<span class="ob-metric-tag">0 情绪冲动违纪</span>
</div>
<div class="ob-card-btn">🧠 进入交易习惯进化追踪档案 ➔</div>
</div>
</a>
</div>

<div class="ob-section-header">
<div class="ob-section-title">🛡️ 核心风控保险丝态势</div>
</div>

<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:12px;margin-bottom:20px">
<div style="background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:10px;padding:12px 16px">
<div style="font-size:11px;color:#fca5a5;font-weight:700">单日最大回撤限额</div>
<div style="font-size:22px;font-weight:800;color:#ef4444;margin:4px 0">3.0%</div>
<div style="font-size:11px;color:#94a3b8">触发全平清仓，强制关机冷静</div>
</div>
<div style="background:rgba(59,130,246,0.1);border:1px solid rgba(59,130,246,0.3);border-radius:10px;padding:12px 16px">
<div style="font-size:11px;color:#93c5fd;font-weight:700">单笔最大风险敞口</div>
<div style="font-size:22px;font-weight:800;color:#3b82f6;margin:4px 0">&le; 2.0%</div>
<div style="font-size:11px;color:#94a3b8">基于账户净值严格计算开仓量</div>
</div>
<div style="background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.3);border-radius:10px;padding:12px 16px">
<div style="font-size:11px;color:#86efac;font-weight:700">当前回撤预警状态</div>
<div style="font-size:22px;font-weight:800;color:#10b981;margin:4px 0">🟢 安全</div>
<div style="font-size:11px;color:#94a3b8">回撤 &lt; 0.5%，无熔断预警</div>
</div>
<div style="background:rgba(168,85,247,0.1);border:1px solid rgba(168,85,247,0.3);border-radius:10px;padding:12px 16px">
<div style="font-size:11px;color:#d8b4fe;font-weight:700">杠杆与逐仓风控</div>
<div style="font-size:22px;font-weight:800;color:#a855f7;margin:4px 0">3x ~ 6x</div>
<div style="font-size:11px;color:#94a3b8">动态适配ATR，拒绝死扛硬扛</div>
</div>
</div>

```chart
type: bar
labels: [EMA双均线, 网格马丁DCA, SMC聪明钱, TTM挤压, VWAP回归, 海龟突破, EMA背离]
series:
  - title: 理论/历史胜率 (%)
    data: [75, 91.5, 72, 76.5, 85, 55, 78]
    backgroundColor: "rgba(16, 185, 129, 0.7)"
  - title: 目标盈亏比 (x10)
    data: [20, 21, 34, 26, 23, 38, 25]
    backgroundColor: "rgba(59, 130, 246, 0.7)"
```

<div class="ob-section-header">
<div class="ob-section-title">⚡ 今日核心交易待办 (Daily Trading SOP)</div>
<a class="internal-link ob-section-action" data-href="00-每日交易待办与纪律清单" href="00-每日交易待办与纪律清单">进入完整SOP清单 ➔</a>
</div>

```dataview
TASK
FROM "00-每日交易待办与纪律清单"
WHERE !completed
LIMIT 6
```

---
*由量化交易系统控制台驾驶舱自动聚合 · [[00-知识库索引_MOC|返回知识库总索引]] · [[00-交易数据看板_Dataview|切换至数据总看板]]*"""

DAILY_TASKS_CONTENT = """---
title: 每日交易待办与纪律清单 (Daily Trading Checklist & SOP)
cssclass: checklist, cards
tags:
  - 待办
  - SOP
  - 交易纪律
  - 检查清单
  - 任务管理
---

# 📋 每日交易待办与纪律清单 (Daily Checklist & SOP)

> [!IMPORTANT] 华尔街自营交易员铁律
> 1. **计划你的交易，交易你的计划 (Plan your trade, trade your plan)**。
> 2. **保住本金永远排在第一位**；单笔最大亏损严禁超过账户总额的 2%，单日最大亏损达 3% 强制关机离场。
> 3. **市场永远是对的，只有自己的傲慢会杀死账户**；触及止损线无条件认赔。

---

## 🌅 一、盘前准备检查清单 (Pre-Market / 08:00 - 09:30)

- [ ] 1. **宏观与大事件排查**: 检查今日是否有美联储利率决议、CPI/非农、SEC 政策或重大解锁。
- [ ] 2. **链上与衍生品数据**: 检查 BTC/ETH 全网资金费率、持仓量 (OI) 异动及多空清算热力图。
- [ ] 3. **系统服务连通性检查**: 确认币安量化机器人本地控制台 (`http://127.0.0.1:8800`) 正常运行，行情 WebSocket 延时正常。
- [ ] 4. **资金风控额度界定**: 计算当日账户净值，明确今日单笔最大亏损额与单日 3% 强平熔断额度。
- [ ] 5. **标的量价结构研判**:
  - [ ] BTC 4h/1h EMA 趋势方向与关键供需区 (Order Block)
  - [ ] ETH 4h/1h 强弱对比与汇率对走势
  - [ ] 强势山寨标的 (SOL, DOGE等) 波动率排查与突破形态预备
- [ ] 6. **生成盘前行情简报**: 在博客工作室点击生成当日盘前研报，并点击「📓 保存至Obsidian(MD+封面)」。

---

## ⚡ 二、盘中执行与行为纪律 (In-Market Execution & Discipline)

- [ ] 1. **信号触发再扣动扳机**: 绝不在 15m 根K未收盘确认前凭直觉追单，耐心等待策略信号完全成立。
- [ ] 2. **进场即带保命止损**: 任何一笔开仓必须同时预埋硬性止损单，盈亏比至少满足 1:1.5 或 1:2.0。
- [ ] 3. **绝不下移止损**: 价格朝不利方向运行时，严禁抱有侥幸心理随意挪移或撤销止损！
- [ ] 4. **分批止盈与保本位上移**: 达到第一目标位 (TP1) 后，果断止盈 50% 仓位，并将剩余仓位止损移至开仓价 (Break-even)。
- [ ] 5. **实战图表截图打标**: 关键开平仓点位或主力假突破假摔，点击界面「快照归档」留存复盘证据。
- [ ] 6. **防 FOMO 与情绪冷静期**: 若遭遇连续 2 笔止损，强制离开交易屏 30 分钟，严禁上头报复性做单！

---

## 🌙 三、盘后复盘与归档结账 (Post-Market Review / 21:00 - 23:30)

- [ ] 1. **核对成交流水与对账**: 打开实盘面板点击「每日总结」，比对平仓笔数、胜率、毛盈亏与手续费磨损。
- [ ] 2. **归档独立 HTML 图表报告**: 点击「HTML图表」或「同步至Obsidian」，自动保存交互式全景图表至 `02-交易复盘/HTML图表/`。
- [ ] 3. **导出 Markdown 每日总结**: 点击「MD总结」导出本地笔记，确保交易明细归入知识库。
- [ ] 4. **撰写交易反思笔记**: 在当日 `YYYY-MM-DD-交易复盘.md` 中记录执行亮点、违纪冲动与策略调整。
- [ ] 5. **评估心理行为雷达**: 检查 `03-交易习惯进化追踪.md`，记录纪律性、情绪稳定度得分变动。
- [ ] 6. **触发卡帕西自维护编译**: 点击界面「⚡ 一键自维护编译」或触发 API，更新全库 MOC 与策略实盘战绩。

---

## 🔄 四、全库动态未完成任务汇总 (Dataview Task Engine)

> [!NOTE] 动态任务监视器
> 以下任务由 Dataview 自动聚合全库（包括策略笔记、复盘笔记、灵感草稿）中带有 `- [ ]` 语法的未完成条目：

```dataview
TASK
WHERE !completed AND file.name != "00-每日交易待办与纪律清单" AND file.name != "00-量化交易员仪表盘_Dashboard"
GROUP BY file.link
```

---
*由量化交易知识库待办引擎统一管理 · [[00-量化交易员仪表盘_Dashboard|返回交易员仪表盘]] · [[00-知识库索引_MOC|返回知识库总索引]]*
"""

SQUARE_BLOG_KANBAN_CONTENT = """---

kanban-plugin: basic

---

## 💡 选题与爆款灵感池

- [ ] 🔥 24H 涨幅榜暴拉币盘点：日内狂飙 25%+ 是真突破还是诱多清扫？
- [ ] 💥 24H 跌幅榜跳水复盘：破位大阴线后该抄底还是止损割肉？
- [ ] 深度拆解 SMC 聪明钱：如何识别机构的流动性掠夺 (Liquidity Sweep)
- [ ] 美联储利率决议前夕：为何巨鲸在 100k 附近持续吸筹？
- [ ] 资金费率套利：熊市中如何做到年化 25% 稳健收益？
- [ ] 散户亏钱的终极真相：90% 的人死在非确认均线上的假突破


## ✍️ 正在撰写中草稿

- [ ] [[04-币安广场与个人博客/草稿库/BTC夜盘深度推演_巨鲸清算后多头能否重夺均线|BTC夜盘深度推演：巨鲸清算后多头能否重夺均线？]]
  - 核心标签: #BTC #币安广场 #行情分析
  - 进度: 80% (待生成 1280x720 封面)


## ⏰ 定时待发布/排期队列

- [ ] [[04-币安广场与个人博客/定时排期库/2026-09-08_动态网格马丁策略实盘91胜率的秘密|动态安全网格马丁实盘91%胜率的秘密]]
  - 拟定发布时间: 2026-09-08 20:30
  - 状态: 已锁定排期，封面已就绪


## 🚀 已发布至币安广场

- [ ] [[04-币安广场与个人博客/已发布归档/TTM挤压突破战法实操复盘|TTM挤压突破战法实操复盘：单日抓住 5% 趋势波段]]
  - 浏览量: 4,200+ | 点赞: 156


## 🌟 爆款与高互动复盘

- [ ] 交易心理学：为何连续止损后你一定会报复性做多？
  - 互动心得: 结尾设置正反方投票引发评论区 80+ 回复热议




%% kanban:settings
```
{"kanban-plugin":"basic"}
```
%%

---

## 📊 币安广场创作数据流 (Dataview Engine)

```dataview
TABLE WITHOUT ID
  file.link AS "文章标题",
  status AS "发布状态",
  scheduled_time AS "排期时间",
  platform AS "平台",
  tags AS "标签",
  file.mtime AS "最后修改"
FROM "04-币安广场与个人博客"
WHERE file.name != "00-币安广场博客工作台_Kanban" AND file.name != "01-币安广场爆款写作指南与SOP" AND file.name != "02-爆款文章模板库"
SORT file.mtime DESC
LIMIT 20
```

---
*由币安广场创作者引擎实时驱动 · [[00-知识库索引_MOC|返回知识库总索引]] · [[00-量化交易员仪表盘_Dashboard|返回交易员仪表盘]]*
"""

SQUARE_WRITING_GUIDE_CONTENT = """---
title: 币安广场爆款创作指南与发帖 SOP
type: square_sop
tags:
  - 币安广场
  - 创作者指南
  - 爆款SOP
  - 流量密码
  - 涨跌榜热点
---

# 🚀 币安广场爆款创作指南与发帖 SOP (2026全市场热点实战版)

> [!TIP] 币安广场流量底层算法
> 币安广场推荐算法以**完读率 (Avg Read Time)**、**前1小时互动率 (点赞+评论+分享)** 以及 **视觉点击率 (CTR)** 为核心权重。
> 社区读者最喜欢“真人说人话”、“全市场热币即时解盘”、“清晰具体的点位计划”以及“真实实盘盈亏透明”，反感千篇一律的 AI 公文腔与无脑营销。

---

## 🎯 一、核心法则：人味十足，拒绝 AI 机器腔

1. **真实交易员第一人称口吻**:
   - 像有 5 年实盘经验的操盘老手在跟群友聊行情，口吻真诚坦率（如「说实话...」「我今天盯盘发现...」「这波我自己的计划是...」）；
   - 杜绝典型 AI 套话：严禁使用「综上所述」「总的来看」「逐项拆解」「值得注意的是」等机械公文腔；
   - 允许展现实盘交易员的真实情绪：如对暴拉热币的兴奋、对假突破诱多的警惕、对模棱两可盘面的犹豫与观望。

2. **简洁明了，短小精悍 (300 - 450 字)**:
   - 广场主要是移动端碎片化阅读，篇幅控制在 300-450 字为最佳黄金区间，1 分钟即可舒适刷完；
   - 拒绝大篇幅堆砌指标定义和晦涩术语，直击核心结论与关键位置。

3. **黄金前3秒抓人眼球 (Hook)**:
   - 标题与开头第一句话决定了 80% 的点击与完读；
   - 善用反问、痛点预警或悬念点位引发好奇。

---

## 🛡️ 二、核心纪律：纯净实战交易笔记与红包剥离红线（重要！）

1. **日常解盘保持纯粹与专业，严禁强塞红包/抽奖**:
   - 日常实盘笔记、行情研判与策略拆解，**绝对禁止出现红包、答题红包、瓜分0.2U、抽奖等字样**！
   - 读者关注的是真实持仓、真实盈亏与清晰具体的防守点位，强行塞入低额红包不仅打乱阅读节奏，还会破坏专业操盘手的可信形象。

2. **红包仅限特定活动时独立发布**:
   - 答题红包或粉丝福利仅在特定重大活动、博主实盘里程碑突破或节日庆典时作为独立互动活动发布，平时默认关闭。

3. **评论区互动必须聚焦实盘博弈与盯盘思路**:
   - 结尾抛出的问题必须围绕读者实际持仓成本、关键支撑阻力判断、追高/抄底心理展开，引导高质量的技术与交易逻辑讨论。

---

## 🎭 三、四大顶尖交易员人设矩阵 (Personas)

系统与 AI 撰写引擎支持以下 4 种真实交易员人设，杜绝千篇一律：

1. **🔥 币安广场爆款大V (binance_top_creator)**:
   - 依托真实实盘持仓盈亏与今日战报支撑，通俗易懂，直击散户盲区与痛点，兼具情绪共鸣与深度技术解盘。
2. **🎯 战术狙击手 (tactical_sniper)**:
   - SMC 价格行为学派，订单块 (Order Block) 测试、流动性假摔洗盘与收回，严密止损，追求极高盈亏比。
3. **☕ 坦率老操盘手 (candid_veteran)**:
   - 5 年实盘经历，口吻真诚坦率，清醒防守，反直觉试错剧本，打到止损无条件离场认输，绝不死扛。
4. **⚡ 微观结构猎手 (microstructure_hunter)**:
   - 盘口异动、资金费率失衡、大单抢跑与多因子共振，擅长在变盘前夜和缩量整理末期挖掘高胜率机会。

---

## 🌐 四、全市场热点覆盖：涨跌幅榜与选币策略

系统现已全面支持在 **Blog Studio 博客工坊** 与 **24H 行情中心** 自由选取以下四类核心标的：

1. **🔥 24H 涨幅榜（暴拉热币 / 突破动能）**:
   - 针对 24H 涨幅榜前排（如涨幅 > 10%）的龙头币种，自带全网极高流量与搜索权重；
   - **解盘策略**：顺势偏多研判，但**绝不无脑煽动追高**。重点交代主力拉高后的流动性掠夺风险、突破有效性确认条件以及“回踩支撑再试仓”的纪律；
   - **标题套路**：`🚨 盯了 {币种} 好久，这波暴拉还能追吗？这几个关键位置我盯紧了`。

2. **💥 24H 跌幅榜（暴跌跳水 / 恐慌下挫）**:
   - 针对破位跳水、连续阴线下挫或恐慌盘涌出的币种，往往聚集了大量被套散户与抄底资金；
   - **解盘策略**：偏空防守研判，分析下方长周期极限支撑，提示反弹遇阻的高压线，说明“宁等止跌确认，绝不徒手接飞刀”；
   - **标题套路**：`⚠️ {币种} 承压回落？这几个防守位我先盯紧，别盲目抄底`。

3. **🎯 量化策略推荐（多因子共振）**:
   - 基于系统 EMA 缎带、聪明钱意图（吸筹/出货）、资金费率与 ATR 波动率综合打分的前排白名单优质标的；
   - 适合长文深度分析与胜率/赔率推演。

4. **💎 实盘持仓与 ✍️ 榜单一键创作**:
   - 可一键点评账户当前的真实持仓，真实透明；
   - 在行情中心 24H 榜单（Gainers / Losers / Volume）每一行，点击 **`✍️ 创作`** 按钮，即可秒级提取该币种实时走势并调用 AI 主笔。

---

## 📝 五、正文排版规范：严禁使用 `##` 井号标题

1. **彻底摒弃 Markdown `##` / `#` 语法**:
   - 在币安广场发帖输入框与移动端前台展示中，带 `## ` 的文本显得极其生硬粗糙；
   - 推荐统一使用**自然醒目的 Emoji 标题**作为视觉锚点，例如：
     - 📊 今日盘面速览
     - 🎯 重点标的观察
     - 📌 我的实盘策略
     - ⚠️ 交易第一铁律
     - 💬 互动交流

2. **实盘计划清单化（四大核心要素缺一不可）**:
   - 必须包含四大核心要素：
     - **关注标的**：币种代码与多空偏向（联动 `$SYMBOL` Cashtag）
     - **关键价位**：入场参考、核心支撑与核心阻力
     - **止损防守**：明确标注具体数字点位，说明“跌破此处坚决认赔离场，绝不跟行情谈恋爱，保住本金永远是第一位”
     - **止盈目标**：明确标注具体数字点位，给出第一目标 TP1（锁定利润推保本损）与第二目标 TP2，测算综合盈亏比（如 2:1 或 2.5:1）

---

## 📈 六、视觉规范：封面高清引流 + 专业走势图置于正文

1. **16:9 封面视觉冲击力（高 CTR 流量密码）**:
   - 社交媒体与币安广场信息流中，极具视觉冲击力的 16:9 科技感盘面走势封面或交易自嘲梗图能够瞬间抓人眼球；
   - 系统支持本地 16:9 Canvas 量化科技盘面渲染器与 AI (gpt-image-2) 绘图双引擎。

2. **专业分析图置于文章正文内容中（高留存与深度转化）**:
   - 读者点进文章后，正文内容内直接呈现高清专业 K 线走势蜡烛图与支撑阻力位标注；
   - 展现硬核专业底色，支撑阻力清晰，让技术流读者获得极佳的阅读与执行参考体验；
   - 在 Obsidian 知识库归档中，笔记正文通过 `![[..._analysis.png]]` 直接内嵌在盘面分析与实战计划段落中。

---

## 🏷️ 七、“看涨 / 看跌” 官方多空标识与 Cashtag 流量转化机制

1. **官方专属红绿情绪标识 (Bullish / Bearish)**:
   - **移动端与Web端呈现**：在币安 App 广场发帖输入框底部，点击官方专属的【情绪/观点】图标（看涨 🟢 / 看跌 🔴）。
   - **展示效果**：文章发布后，创作者头像与昵称右侧将自动常驻高亮显示 **`看涨`**（绿色）或 **`看跌`**（红色）官方徽章，大幅提升信息流中的可信度与专业形象；
   - **Blog Studio 联动**：博客工作台左侧提供【📈 观点倾向】选择器，并自动跟随量化多空信号预选，编辑区实时呈现多空红绿徽章。

2. **Cashtag (`$币种`) 自动挂载实时行情卡片机制**:
   - **底层机制**：在币安广场正文或标题中，只要在币种代码前加上 `$`（例如 `$BTC`、`$ETH`、`$SOL`），广场系统会自动解析为 Cashtag 超链接；
   - **实时行情卡片**：一旦包含 `$SYMBOL`，币安广场将在正文下方**自动生成官方交互式行情组件**（显示当前价格、24H 涨跌幅、实时走势分时 Sparkline 以及自选加星号按钮）；
   - **极高转化率**：读者点击该卡片可直接一键跳转至币安合约或现货交易对，是头部大V带动交易返佣与跟单转化的核心技术密码！
   - **文末行动指令**：在实操计划末尾紧跟 `做多 $SYMBOL 🚀` 或 `做空 $SYMBOL 👇`，与下方的实时行情卡片形成完美的视觉指引。

---

## 🏷️ 八、标签数量严格规范（≤ 5 个）

- **接口硬性红线**:
  - 币安广场单篇文章 **最多允许 5 个 Hashtag**！超出将直接报错触发限制。
- **推荐黄金组合 (4 - 5 个)**:
  - 核心币种 (1个): `#{热榜币种}` 或 `#BTC`
  - 官方情绪信号 (1-2个): `#看涨` `#做多` 或 `#看跌` `#做空`
  - 社区与品类 (2个): `#币安广场` `#合约实战`

---

## 💬 九、评论区互动与完读转化技巧

1. **结尾必须留有深度的实战互动问答**:
   - 涨幅榜热币：“*兄弟们现在是在等 {支撑位} 的回踩，还是准备直接追 {阻力位} 的突破？评论区报个点位，我盯着盘。*”
   - 跌幅榜异动币：“*刚才这根下影插针，大家觉得把多头洗干净了吗？你们手上有单子吗？成本是多少？在评论区留个言，大家一起交流复盘。*”
2. **前3条神评互动**:
   - 发帖后 5 分钟内自评补充一句最新盘口微调，带动粉丝参与回复。
"""

SQUARE_TEMPLATES_CONTENT = """---
title: 币安广场爆款文章实战模板库
type: square_templates
tags:
  - 币安广场
  - 文章模板
  - 创作工具箱
  - 涨跌榜热点
---

# 📚 币安广场爆款文章实战模板库 (2026全市场实战纯净版)

> [!NOTE] 写作与排版规范准则
> 以下模板已严格遵从最新实战规范：
> 1. **日常纯净实盘**：绝无红包、瓜分、抽奖字样，专注纯粹交易点位与防守逻辑；
> 2. **排版规范**：正文绝无 `##` 井号，以自然 Emoji 标头分割；
> 3. **篇幅精悍**：350-450 字左右，充满 5 年操盘手真人说人话味道；
> 4. **四大核心要素**：严格包含具体数字点位的**入场参考、关键支撑阻力、止损防守（SL）与止盈目标（TP）**；
> 5. **转化与标签**：正文包含 `$币种` Cashtag 与多空 CTA 指令，标签严格 ≤ 5 个，包含 `#看涨` 或 `#看跌`。

---

## 模板 1: 🏛️ SMC/价格行为学 — 订单块 (Order Block) 假摔收回流

```markdown
${币种} 刚才这根插针很不寻常，主力到底是在洗盘还是诱多？

🟢【看涨 · 做多】

说实话，刚才这波上下洗盘把不少追单的兄弟洗得难受。但复盘了一下盘口数据，${币种}（现价 {现价}）这里的走势其实大有文章。

盘口虽有放量下探，但并未击穿核心结构防线。目前下方关键支撑死死卡在 {支撑位}（核心 Order Block 需求带），上方真正的防守阻力落在 {阻力位}。盘面触发了多因子共振，主力资金在此位置更像是在掠夺追涨追跌散户的流动性，而不是真正出逃。

📌 我的实盘策略（必须依托明确的止损防守）：
• 交易标的：${币种}（偏多博弈 🟢）
• 关键价位：入场参考 {现价} ｜ 核心支撑 {支撑位} ｜ 核心阻力 {阻力位}
• 止损防守：跌破 {止损位} 坚决认赔离场！不跟行情谈恋爱，保住本金永远是第一位的
• 止盈目标：第一目标 TP1 先看 {阻力位}（先分批落袋锁利），延展目标看 {止盈位}，综合盈亏比 {盈亏比}

做多 ${币种} 🚀

⚠️ 交易第一铁律：任何时候仓位都不能拉满，只赚认知范围内的盈亏比。
💬 兄弟们觉得刚才这根针把空头/多头洗干净了吗？在评论区聊聊看！

#币安广场 #{币种} #看涨 #做多 #合约实战
```

---

## 模板 2: ☕ 老操盘手实战日记 — 清醒防守与试错剧本流

```markdown
别在现价无脑追涨，聊聊我对 ${币种} 的接单防守逻辑

🟢【看涨 · 做多】

今天盯盘盯了半天，多数山寨都在装死震荡，只有 ${币种}（现价 {现价}）走出了一个很干净的结构。发篇实战笔记，逐一拆解核心逻辑与我的操作思路。

目前 ${币种} 波动率维持在 {波动率}%，盘口反复出现大单托底。技术面上，下方多次回踩结构支撑 {支撑位} 均被迅速收回，买盘意愿强烈。

🎯 分享我的个人试错剧本：
• 交易标的：${币种}（逢低试多 🟢）
• 关键价位：现价 {现价} 附近分批介入 ｜ 防守支撑 {支撑位} ｜ 目标阻力 {阻力位}
• 止损防守：死守 {止损位}！记住，打到止损说明我预判错了，无条件撤退，绝不扛单
• 止盈目标：第一档目标看 {阻力位}，第二档看 {止盈位}，盈亏比测算达到 {盈亏比}，是盈亏比极划算的一次试错

做多 ${币种} 🚀

⚠️ 老韭菜叮嘱：行情永远在，不要上头频繁操作。做好分批防守。
💬 你们手上有这个币的单子吗？成本是多少？在评论区留个言，大家一起交流复盘。

#币安广场 #{币种} #看涨 #合约实战 #行情分析
```

---

## 模板 3: 🎯 关键分水岭与高盈亏比狙击流

```markdown
${币种} 触碰日内核心分水岭，{盈亏比} 优质盈亏比试错计划

🟢【看涨 · 做多】

做交易的核心永远不是猜涨跌，而是在赢面大、盈亏比划算的地方果断开枪。当前 ${币种}（现价 {现价}）正好就处在这个分水岭上。

指标层面，上方核心阻力压在 {阻力位}，下方关键支撑底线卡在 {支撑位}。当前在小级别走出多因子共振，盘口持续放量。

💡 实盘挂单参考（必须执行止损防守）：
• 核心标的：${币种}（偏多突破 🟢）
• 关键价位：入场参考 {现价} ｜ 支撑底线 {支撑位} ｜ 目标压制 {阻力位}
• 止损防守：{止损位}（底线思维：跌破此处结构破坏，坚决离场认输）
• 目标出局：TP1 目标参考 {阻力位}（锁定利润），TP2 延展参考 {止盈位}，期望盈亏比 {盈亏比}

做多 ${币种} 🚀

⚠️ 敬畏市场，杜绝重仓猛干。
💬 在这个位置你敢上车吗？还是等回踩稳了再动？欢迎在评论区聊聊！

#币安广场 #{币种} #看涨 #做多 #量化实战
```

---

## 模板 4: ⚡ 盘口异动：聪明钱在想什么？（变盘前夜缩量流）

```markdown
${币种} 缩量整理接近尾声，聪明钱在想什么？今晚重点盯紧这根关键分界线

🟢【看涨 · 做多】

横盘震荡越久，爆发起来越猛烈。${币种}（现价 {现价}）已经在关键区间磨了很久，往往这是大资金完成洗盘换手的信号。

上方强阻力位卡在 {阻力位}，而下方 {支撑位} 展现出了明显的承接盘。ATR 波动率在持续压缩，方向选择随时一触即发。

🎯 交易员挂单剧本：
• 标的：${币种}（右侧顺势看多 🟢）
• 关键价位：围绕 {现价} 寻找小级别入场时机 ｜ 支撑 {支撑位} ｜ 阻力 {阻力位}
• 止损防守：{止损位}（严格设止损，破位无条件离场，切勿死扛）
• 止盈测算：第一止盈落袋点 {阻力位}，延展目标 {止盈位}，综合盈亏比 {盈亏比}

做多 ${币种} 🚀

⚠️ 交易纪律：赚认知以内的钱，不要贪多，仓位千万别拉满。
💬 兄弟们看好这一波突破吗？欢迎在评论区留下你的看法！

#币安广场 #{币种} #看涨 #突破交易 #实盘笔记
```

---

## 模板 5: 🛡️ 交易员避坑与心态手记 (实战反思流)

```markdown
💥 为什么一止损行情就反弹？聊聊我们都交过的学费

说句实在话，每个交易员都经历过这种心态崩塌的时刻：拿着单子硬扛几个小时，最后受不了割肉，结果割完两分钟就直接大阳线拉回去。

其实核心问题出在止损位置的设定上——大多数散户的止损都挤在显眼的前高前低，恰好成了大资金最喜欢的“流动性美餐”。

💡 建立你的保命纪律清单：
1. 算好止损再开仓：进场前就把最大单笔亏损锁定在账户资金 2% 以内；
2. 留出波动冗余：止损至少放在关键支撑外加 1~1.5 倍 ATR 位置；
3. 严格止盈推保本：盈亏比达到 1:1.5 必须平仓一部分，剩余推保本损。

⚠️ 永远记住：在币圈活得久的人，不是抓到了多少个百倍币，而是少爆了多少次仓。
💬 戳中你的痛点了吗？你在哪一次交易里交的学费最痛？评论区一起聊聊！

#币安广场 #交易心理 #风控第一 #实盘手记
```

---

## 🎁 特别附录：特定节日/活动 · 粉丝互动答题红包选用模块

> [!WARNING] 使用前提
> 本模块**仅在创作者特定举办答题红包活动时选用，日常行情解盘严格禁止加入**！

```markdown
🎁 【粉丝专享 · 评论答题瓜分红包（0.2 USDT · 100 份）】
❓ 今日实盘问答：今天我给 ${币种} 给出的核心止损防守位是多少？（答案就在正文里）
💬 参与方式：直接在评论区打出正确数字答案，系统随机抽取粉丝瓜分现金答题红包！手慢无，先答对先得！
```
"""

SAMPLE_SQUARE_BLOG_CONTENT = """---
title: "🚨 BTC夜盘深度推演：盯了 BTC 好久，这波关键位置我要动手了"
type: square_blog
status: scheduled
scheduled_time: "2026-09-08 20:00"
platform: binance_square
tags:
  - 币安广场
  - BTC
  - 合约实战
  - 实盘笔记
cover: "[[04-币安广场与个人博客/封面/cover_sample_btc.png]]"
square_post_id: ""
square_link: ""
published_at: ""
---

🚨 盯了 BTC 好久，这波关键位置我要动手了

🟢【看涨 · 做多】

今天盯盘说实话挺兴奋的，BTC 强势冲上65000关口，日内涨幅超过2.5%。盘面上大单推升势头凶猛，全网关注度极高。

但是说句掏心窝子的话：暴拉行情最忌讳无脑市价追高。从形态上看，下方64000-64200区间已经被反复测试，支撑非常扎实；上方66000-66800是前期筹码密集区，一旦放量突破，很可能直接冲到67500附近。

📌 我的实盘策略（必须依托明确的止损防守）：
• 交易标的：$BTC（偏多博弈 🟢）
• 关键价位：入场参考 64800 ｜ 核心支撑 64000 ｜ 核心阻力 66800
• 止损防守：63800（跌破此处坚决认赔离场，绝不扛单，保住本金永远是第一位的）
• 止盈目标：第一目标 TP1 先看 66800（先分批落袋锁利），延展目标看 67500，综合盈亏比 2.3:1

做多 $BTC 🚀

⚠️ 交易第一铁律：任何时候仓位都不能拉满，只赚认知范围内的盈亏比。
💬 兄弟们现在是在等 64,000 的回踩，还是准备直接追 66,800 的突破？评论区报个点位，我盯着盘。

#币安广场 #BTC #看涨 #做多 #合约实战
"""




