"""将 5 套高级机构级交易策略模型注入 Obsidian 知识库 (E:\量化\01-交易策略)"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
import src  # noqa: F401

import sys
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from pathlib import Path
from obsidian_bridge import ObsidianBridge

b = ObsidianBridge()
vp = b.get_vault_path()
if not vp:
    print("[-] Error: Obsidian vault path not found")
    sys.exit(1)

strat_dir = vp / "01-交易策略"
strat_dir.mkdir(parents=True, exist_ok=True)

strategies = [
    {
        "filename": "08-威科夫吸筹模型与Spring弹簧效应策略.md",
        "content": """---
title: 威科夫吸筹与弹簧效应(Spring)爆发策略
type: wyckoff_accumulation
status: active
symbols: [BTCUSDT, ETHUSDT, SOLUSDT, ALL]
timeframe: 15m
target_win_rate: 76.5%
profit_factor: 3.6
risk_reward_ratio: 1:3.5
indicators:
  - Wyckoff Trading Range (TR)
  - Phase C Spring
  - Test of Spring
  - Sign of Strength (SOS)
  - Jump Across Creek (JAC)
tags:
  - 威科夫理论
  - 弹簧效应
  - 机构吸筹
  - 假跌破真反转
---

# 威科夫吸筹与弹簧效应(Spring)爆发策略

> [!NOTE] 核心逻辑本质
> 机构在长达数日甚至数周的吸筹区间内逐步吸收浮动筹码。在拉升前，主力会制造一次击穿所有散户止损线的致命下砸（Phase C Spring），测试市场潜在浮动供应。一旦跌破后迅速以大阳线收回，即确认空头筹码耗尽，随后将展开摧枯拉朽的顺势主升浪。

## 🧭 知识库双向链接
- 知识地图中枢: [[00-知识库索引_MOC|知识库总索引]]
- 关联行为风控: [[03-交易习惯与行为进化/交易习惯进化追踪|交易习惯进化追踪]]
- 对比策略: [[01-交易策略/02-SMC聪明钱订单块与流动性劫持策略|SMC聪明钱订单块策略]]

---

## 📊 威科夫吸筹五阶段流转模型

```mermaid
flowchart TD
    PA["Phase A: 抛售高潮 SC + 自动反弹 AR 确立交易区间"] --> PB["Phase B: 多次二次测试 ST 吸收浮动筹码"]
    PB --> PC["Phase C: 终极清洗 Spring 击穿支撑留长下影"]
    PC --> Test["Test 回踩确认 极度缩量不创新低"]
    Test --> PD["Phase D: 强势出现 SOS 连续大阳线跃过小溪 JAC"]
    PD --> PE["Phase E: 彻底脱离吸筹区 启动主升浪单边行情"]
```

---

## 📈 K 线形态图解 (ASCII 架构)

```text
 区间上限 (Resistance) ─────────────────────────────────── SOS (强势放量突破) ───> Markup 主升浪
                        ▲      ▲            ▲           /
                        │  AR  │    ST      │          / LPS (回踩支撑)
                        │      │            │         /
 区间下限 (Support)    ────┼──────┼────────────┼────────/────────────────────────
                  SC    │      │            │       /
 (抛售高潮) ────> ▼      ▼            ▼      /
                                             ▼
                                           Spring (弹簧刺破收回)
                                           [长下影 Pinbar + 缩量 Test]
```

---

## 一、入场条件 (Entry Rules)
1. **区间确立**: 盘面在 15m/1h 周期维持至少 24 小时以上的横向箱体震荡，有明确的支撑位 (Support) 与阻力位 (Resistance)；
2. **Spring 触发**: 价格向下刺穿箱体最低支撑，但在 1~3 根 K 线内迅速被巨量买盘收回，K 线收盘价必须坚决站回支撑线上方，并留有显著下影线；
3. **极度缩量测试 (Test)**: 价格出现弱势轻微二次回探，成交量衰减至过去 20 根均量的 50% 以下，绝对不创 Spring 的最低点；
4. **大阳线启动 (SOS)**: 随后出现一根实体占比超 75% 的多头放量吞没大阳线（量比 > 1.5x），收盘站稳均线 EMA9，立即执行做多开仓。

---

## 二、风控与止损 (Risk Management)
- **初始硬止损**: 设在 Spring 极限下影线低点下方 0.3%~0.5% 处，一旦跌破该低点意味着吸筹逻辑被彻底破坏，立即认赔离场；
- **单笔最大风险**: 严格限制在总资金净值的 1.5% 以内，不可随意下移止损。

---

## 三、止盈目标 (Exit Rules)
- **TP1 (第一目标)**: 达到箱体上轨阻力位（盈亏比 1:2.0），平仓 50% 头寸，同时将剩余仓位止损移动至保本价（Break-even）；
- **TP2 (第二目标)**: 突破箱体跃过小溪（JAC），按箱体垂直高度的 1.618 倍等幅拓展测算，盈亏比通常可达 1:3.5~1:5.0。

---

## 四、执行反思与习惯提醒
- ⚠️ 严禁在 Spring 尚未收盘确认时凭感觉抄底！必须等待下影线确立及随后的极度缩量 Test！
- ⚠️ 若 Spring 之后未出现量价齐升的 SOS，反而再度阴跌破位，必须无条件执行止损！
"""
    },
    {
        "filename": "09-ICT经典银弹与Killzone流动性掠夺策略.md",
        "content": """---
title: ICT经典银弹与Killzone流动性掠夺策略
type: smart_money_concepts
status: active
symbols: [BTCUSDT, ETHUSDT, SOLUSDT, ALL]
timeframe: 15m
target_win_rate: 78.0%
profit_factor: 3.8
risk_reward_ratio: 1:3.2
indicators:
  - London/NY Killzone
  - Buy-side Liquidity (BSL)
  - Sell-side Liquidity (SSL)
  - Fair Value Gap (FVG)
  - Displacement
tags:
  - ICT
  - 银弹策略
  - 掠夺流动性
  - Killzone时段
---

# ICT经典银弹与Killzone流动性掠夺策略

> [!NOTE] 机构算法核心秘密
> 银行间价格递送算法（IPDA）在固定时间窗口（Killzone）激活。算法的任务是搜寻散户堆叠在关键高低点上方的巨量止损买单（BSL）或止损卖单（SSL），掠夺流动性后产生急速位移（Displacement），留下价值失衡缺口（FVG），并在回踩时瞬间锁定顺势大波段。

## 🧭 知识库双向链接
- 知识地图中枢: [[00-知识库索引_MOC|知识库总索引]]
- 关联行为风控: [[03-交易习惯与行为进化/交易习惯进化追踪|交易习惯进化追踪]]

---

## 📊 Killzone 流动性猎杀闭环

```mermaid
sequenceDiagram
    autonumber
    participant Time as 算法激活时段 (Killzone)
    participant Pool as 外部流动性 (BSL/SSL)
    participant IPDA as 机构报价算法 (Smart Money)
    participant FVG as 市场失衡区 (50% CE)

    Time->>IPDA: 伦敦/纽约开盘算法开启 (时段对齐)
    IPDA->>Pool: 蓄意推升刺破前期高点，触发散户止损买单 (Sweep BSL)
    Pool-->>IPDA: 巨量对手盘流入，机构吃满空头仓位
    IPDA->>FVG: 暴力砸盘产生位移 (Displacement)，形成 3 根 K 线不重叠失衡缺口 (FVG)
    FVG->>IPDA: 价格有序回抽至 FVG 50% 敏感中轴位 (Consequent Encroachment)
    IPDA->>Pool: 挂单精准成交，向下猎杀下方目标 SSL (盈亏比 1:3.2+)
```

---

## 一、入场条件 (Entry Rules)
1. **时区过滤**: 优先在伦敦开盘（15:00-17:00 UTC+8）或纽约开盘（20:00-22:00 UTC+8）高流动性黄金窗口内触发；
2. **流动性掠夺**: 价格刺穿前期关键高点 (BSL) 或前期低点 (SSL) 至少 15bps，随后留出长影线反抽收盘在极值点内侧；
3. **结构位移破坏 (MSS)**: 伴随放量的大实体 K 线跌破/突破最近一根关键摆动结构，确认大资金进场；
4. **FVG精准回踩**: 由 3 根连续 K 线构成未重叠缺口，等待价格平稳回落/回抽至该 FVG 区域的 50% 水平线（CE - Consequent Encroachment），精准市价或限价单入场。

---

## 二、风控与止损 (Risk Management)
- **初始硬止损**: 置于造成本次 Displacement 位移的极端高低点外侧 + 1.0 * ATR(15m)；
- **单笔最大风险**: 严格锁定账户权益的 1.5%。

---

## 三、止盈目标 (Exit Rules)
- **TP1**: 对侧内部结构流动性高低点（盈亏比 1:2.0），减仓 50% 并将止损挪至成本价；
- **TP2**: 对侧外部极值流动性池（盈亏比 1:3.2 以上）。

---

## 四、执行反思与习惯提醒
- ⚠️ 绝不在无 FVG 失衡支持的普通支撑阻力位轻举妄动！
- ⚠️ 严防在非 Killzone 的垃圾时间段（如午间亚洲垃圾时间）追逐虚假突破！
"""
    },
    {
        "filename": "10-AMD亚洲盘流动性诱捕与诱导假突破策略.md",
        "content": """---
title: AMD亚洲盘流动性诱捕与诱导假突破策略
type: breakout
status: active
symbols: [BTCUSDT, ETHUSDT, SOLUSDT, ALL]
timeframe: 15m
target_win_rate: 74.0%
profit_factor: 3.2
risk_reward_ratio: 1:3.0
indicators:
  - Asian Range High/Low
  - London Judas Swing
  - Manipulation Expansion
  - True Distribution
tags:
  - AMD模型
  - 亚洲盘
  - 犹大秋千
  - 假突破反手
---

# AMD亚洲盘流动性诱捕与诱导假突破策略

> [!NOTE] 核心逻辑本质
> 经典的 AMD 周期律：Accumulation (亚盘窄幅吸筹) -> Manipulation (欧盘初诱空/诱多制造假突破 Judas Swing) -> Distribution (纽约盘真趋势顺势大派发)。利用欧盘开盘诱导散户追单的极端情绪，反手狙击单边爆发。

## 🧭 知识库双向链接
- 知识地图中枢: [[00-知识库索引_MOC|知识库总索引]]
- 关联行为风控: [[03-交易习惯与行为进化/交易习惯进化追踪|交易习惯进化追踪]]

---

## 📊 AMD 节奏演化图解

```mermaid
flowchart LR
    A["1. Accumulation 亚盘 08:00-14:00 极度缩量震荡，确立清晰亚盘箱体"] --> M["2. Manipulation 欧盘 15:00-16:30 虚假刺穿箱体边界 Judas Swing 诱敌深入"]
    M --> D["3. Distribution 美盘 19:30-24:00 快速收回箱体，开启反向单边大派发"]
```

---

## 📈 K 线结构剖析

```text
 亚盘高点 (Asian High) ───────────┐         ┌─── Judas Swing 假突破 (诱多)
                                   │  亚盘   │      ▲
                                   │  箱体   │      │
 亚盘低点 (Asian Low)  ───────────┴─────────┴──────┼─────────────────────────────────────────────
                                                    │ 反转大阴线跌回箱体内 (入场做空点)
                                                    ▼
                                                    ▼▼▼ 纽约盘真实派发 (单边暴跌大波段) ───>
```

---

## 一、入场条件 (Entry Rules)
1. **锁定亚盘基准**: 记录 UTC+8 早上 08:00 至 14:30 之间形成的最高价 (Asian High) 和最低价 (Asian Low)；
2. **侦测 Judas 诱骗刺透**: 伦敦开盘初 (15:00-16:30)，价格出现快速急拉刺破 Asian High（或急跌刺破 Asian Low）达 10~35 个基点，诱使突破型散户追单；
3. **假突破吞没收回**: 价格无法在亚盘边界外站稳，下一根或两根 15m K 线以坚决实体跌回/涨回亚盘箱体内部；
4. **顺势开仓**: 一旦收盘重新确认回到亚盘区间，立即反向开仓（刺破高点收回做空，刺破低点收回做多）。

---

## 二、风控与止损 (Risk Management)
- **初始止损**: 置于 Judas Swing 诱骗假突破的最高点/最低点外侧 + 0.25%；
- **单笔最大风险**: 严格控制在 2.0% 以内。

---

## 三、止盈目标 (Exit Rules)
- **TP1**: 亚盘箱体的对侧边界（盈亏比 1:1.8），止盈半仓并改保本；
- **TP2**: 亚盘区间宽度的 1.5 倍等幅拓展位（盈亏比 1:3.0+）。

---

## 四、执行反思与习惯提醒
- ⚠️ 绝不在欧盘初出现大阳线向上突破时盲目追单！牢记 70% 的欧盘初突破都是诱敌的 Judas 陷阱！
"""
    },
    {
        "filename": "11-成交量分布图(Volume Profile)与POC高价值区回踩策略.md",
        "content": """---
title: Volume Profile 筹码分布图与 POC 高价值区回踩策略
type: mean_reverting
status: active
symbols: [BTCUSDT, ETHUSDT, SOLUSDT, ALL]
timeframe: 15m
target_win_rate: 75.0%
profit_factor: 3.1
risk_reward_ratio: 1:2.8
indicators:
  - Volume Profile (VPVR)
  - Point of Control (POC)
  - Value Area High (VAH)
  - Value Area Low (VAL)
  - Low Volume Nodes (LVN)
tags:
  - 筹码分布
  - 机构公允价
  - POC引力
  - 价值区回归
---

# Volume Profile 筹码分布图与 POC 高价值区回踩策略

> [!NOTE] 核心逻辑本质
> 价格由成交量驱动。POC (Point of Control) 是过去一段时间市场成交最密集的公允价值核心，拥有巨大的引力（Gravity）。当价格偏离价值区后重新回踩 POC 或 VAH/VAL 边缘时，往往伴随机构资金的防守回补，提供极佳的高胜率进场点。

## 🧭 知识库双向链接
- 知识地图中枢: [[00-知识库索引_MOC|知识库总索引]]
- 关联行为风控: [[03-交易习惯与行为进化/交易习惯进化追踪|交易习惯进化追踪]]

---

## 📊 Volume Profile 筹码结构分布图解

```mermaid
graph TD
    VAH["价值区上沿 VAH 70% 筹码上边界 - 强阻力"] --> LVN1["低成交量真空区 LVN 价格快速滑移，无阻力"]
    LVN1 --> POC["控制点 POC 筹码最密集峰值 - 强引力与支撑中枢"]
    POC --> LVN2["低成交量真空区 LVN 流动性真空"]
    LVN2 --> VAL["价值区下沿 VAL 70% 筹码下边界 - 强支撑"]
```

---

## 一、入场条件 (Entry Rules)
1. **建立价值区分布**: 调取近 48 小时成交量轮廓分布图（Volume Profile），精确锁定 POC 控制线、VAH 上轨与 VAL 下轨；
2. **偏离与回踩**: 价格在大周期（1h）确立向上或向下趋势的前提下，出现短周期健康回踩并逼近 POC 强筹码峰值位；
3. **量能骤减与阻力衰竭**: 当价格触碰 POC 时，成交量明显萎缩（表明并无大量抛压突破该处筹码墙），且 15m 级别收出拒收影线（Pinbar）；
4. **反转放量确认**: 随后一根 K 线同向放量拉起，RSI 处于 45~55 之间的健康回踩区，立即挂单或市价顺势开仓。

---

## 二、风控与止损 (Risk Management)
- **初始止损**: 锚定在 POC 背后最近的低成交量空洞区（LVN）外侧 + 0.3%，因为一旦跌破 LVN 意味着公允价值彻底移位；
- **单笔最大风险**: 账户权益的 1.5%。

---

## 三、止盈目标 (Exit Rules)
- **TP1**: 价值区对侧边缘（VAH 或 VAL，盈亏比 1:1.8），减仓 50% 并上移保本；
- **TP2**: 突破价值区后的真空加速目标位（盈亏比 1:2.8~1:3.5）。

---

## 四、执行反思与习惯提醒
- ⚠️ 严禁在价格处于低成交量节点 (LVN) 中间悬空时开仓！LVN 区域滑点极大且无支撑！
"""
    },
    {
        "filename": "12-极端放量旗形突破与动量中继战法策略.md",
        "content": """---
title: 极端放量旗形突破与动量中继策略
type: trend_following
status: active
symbols: [BTCUSDT, ETHUSDT, SOLUSDT, ALL]
timeframe: 15m
target_win_rate: 77.0%
profit_factor: 3.5
risk_reward_ratio: 1:3.2
indicators:
  - High Volume Impulse Flagpole
  - Declining Volume Flag Channel
  - Fibonacci Retracement (0.382)
  - Breakout Volume Expansion
tags:
  - 牛旗战法
  - 熊旗战法
  - 动量中继
  - 爆量突破
---

# 极端放量旗形突破与动量中继策略

> [!NOTE] 核心逻辑本质
> 旗形是所有顺势形态中胜率最高、盈亏比最对称的动量中继形态。旗杆代表主力的绝对统治力（极速放量脉冲）；旗面代表空头反扑无力（缩量窄幅反向平行收敛）；二次放量突破则代表主升浪/主跌浪第二波的等幅爆发。

## 🧭 知识库双向链接
- 知识地图中枢: [[00-知识库索引_MOC|知识库总索引]]
- 关联行为风控: [[03-交易习惯与行为进化/交易习惯进化追踪|交易习惯进化追踪]]

---

## 📈 牛旗战法形态解构 (ASCII 架构)

```text
 价格上涨
   ▲           二次暴发主升浪 (等幅映射 TP2 = 旗杆长度)
   │          /
   │         /  突破确认 (放量大阳线，入场开仓点)
   │     ┌──/─────────┐ 旗面通道 (Flag Channel)
   │     │ / ╲   ╱    │ [成交量梯级萎缩至 30%]
   │     │╱   ╲ ╱     │ [回撤 < 38.2% 旗杆高]
   │     └─────▼──────┘
   │
   │  旗杆 (Flagpole)
   │  [极速脉冲放量 > 2.5x 均量]
  ─┴───────────────────────────────────────────> 时间
```

---

## 一、入场条件 (Entry Rules)
1. **旗杆脉冲确立**: 在 15m 周期出现 3~5 根连续饱满实体同向冲激 K 线，期间成交量放大至 20 根均量的 2.5 倍以上；
2. **旗面收敛通道**: 价格进入 3~8 根 K 线的窄幅反向微倾斜通道整理，回撤深度不得超过旗杆垂直高度的 38.2%（健康浅度休整）；
3. **成交量阶梯萎缩**: 旗面整理期间，成交量必须逐级递减（表明主力并未出货，仅仅是散户浮筹洗盘）；
4. **突破放量引爆**: 出现一根大阳线（牛旗）或大阴线（熊旗）坚决突破旗面上轨/下轨趋势线，收盘完全位于通道外侧，且放量大于 1.8 倍均量，立即开仓顺势追击。

---

## 二、风控与止损 (Risk Management)
- **初始止损**: 锚定在旗面整理通道的最低支撑点（牛旗）或最高点（熊旗）下方 1.0 * ATR；
- **单笔最大风险**: 严格限制为账户权益的 2.0%。

---

## 三、止盈目标 (Exit Rules)
- **TP1**: 达到突破点 + 50% 旗杆垂直高度（盈亏比 1:1.8），止盈一半并锁定保本；
- **TP2 (等幅测算)**: 达到突破点 + 100% 旗杆长度（盈亏比通常在 1:3.0~1:4.2）。

---

## 四、执行反思与习惯提醒
- ⚠️ 旗面回撤若跌破旗杆 50% 斐波那契分界，该形态立刻废弃！坚决不能入场！
- ⚠️ 突破 K 线必须有放量配合，严禁在无量勉强出轨时提早抢跑！
"""
    }
]

for s in strategies:
    target_file = strat_dir / s["filename"]
    target_file.write_text(s["content"], encoding="utf-8")
    print(f"[+] Injected into Obsidian: {s['filename']}")

scanned = b.scan_strategies()
print(f"[*] Total active strategies in Obsidian: {len(scanned)}")
for s in scanned:
    print(f"    - [{s.get('type')}] {s.get('title')}")
