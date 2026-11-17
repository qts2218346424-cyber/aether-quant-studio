# Aether Quant Studio · 技术架构与模块指南

## 1. 分层设计原则

本项目在 v2.0 重构中全面解除了早期单文件巨石耦合，采用五层职责隔离架构：

1. **`src/core/`（交易与风控内核）**
   - `config.py`：Schema-v2 配置归一化、首次启动零配置回退与原子写盘保护。
   - `binance_client.py`：币安 USDT 本位永续合约异步 REST / WebSocket 通信封装。
   - `trader.py`：五级交易运行模式（`READONLY` / `SHADOW` / `PAPER` / `MICRO_LIVE` / `LIVE`）、长短线双轨状态机与实盘对账。
   - `risk_manager.py`：硬性开仓门禁、最大日损熔断、连亏冷却与数据陈旧度熔断器。
   - `trade_journal.py`：本地 JSON 持久化成交账本与多源同步对账。

2. **`src/strategies/`（信号、回测与自进化）**
   - `strategy.py`：多因子技术评分引擎与高周期共振判定。
   - `candidate_strategies.py`：可插拔候选策略注册表。
   - `backtest.py` & `strategy_auto_improver.py`：历史 K 线仿真撮合与样本内外（IS/OOS）防过拟合参数自动寻优。
   - `market_sentiment.py`：大户多空比、持仓量（OI）、资金费率与聪明钱评分聚合。

3. **`src/ai/`（AI 投委会与直觉门禁）**
   - `typesafe_engine.py`：TypeSafe Jev (System One) 毫秒级校准门禁引擎。
   - `ai_analyst.py` & `ai_committee.py`：K 线形态 AI 解盘与多模型并发投票。

4. **`src/integrations/`（生态联动）**
   - `obsidian_bridge.py`：Obsidian 双链知识库同步、策略编译器与五维习惯雷达。
   - `blog_auto_publish.py` & `binance_square_publisher.py`：币安广场图文创作与自动巡检发布管线。

5. **`src/api/` & `static/`（网关与模块化前端）**
   - 后端按领域拆分为 9 个 `APIRouter` 模块，由根目录 `app.py` 统一挂载。
   - 前端静态资源按 `static/css/01..06` 与 `static/js/01..06` 模块化加载，无需繁重的 Node 打包链路即可直接运行与调试。
