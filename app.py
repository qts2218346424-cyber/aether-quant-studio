"""Aether Quant Studio · 苍穹量枢 — FastAPI 主应用入口

采用高内聚分层模块化架构组装全部领域路由与实时流服务：
- src/core/         核心交易状态机、币安异步客户端、硬风控门禁与账本
- src/strategies/   多因子信号引擎、候选策略库、仿真回测与自进化管线
- src/ai/           TypeSafe Jev (System One) 直觉门禁与多模型投委会
- src/integrations/ Obsidian 双链知识库编译器与币安广场智能运营管线
- src/api/          模块化 FastAPI 路由层与共享快照 WebSocket 服务
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import src  # noqa: F401 - 初始化分层包搜索路径
from src.paths import REPORTS_DIR, STATIC_DIR
from src.api.context import square_auto_publisher, trader, ws_clients
from src.api import (
    routes_ai,
    routes_market,
    routes_obsidian,
    routes_risk,
    routes_square,
    routes_strategies,
    routes_system,
    routes_trading,
    ws as ws_module,
)

# 保留核心函数符号重导出，确保全量历史测试套件 100% 向后兼容
from obsidian_bridge import obsidian_bridge
from src.api.routes_market import get_systems, preview_systems
from src.api.routes_strategies import (
    apply_strategy_preset,
    get_strategy_candidates,
    run_strategy_auto_improve,
    run_strategy_backtest,
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    trader_task = asyncio.create_task(trader.start())
    pub_task = asyncio.create_task(square_auto_publisher.start())
    yield
    await square_auto_publisher.stop()
    await trader.stop()
    for task in (trader_task, pub_task):
        if not task.done():
            task.cancel()


app = FastAPI(
    title="Aether Quant Studio · 苍穹量枢",
    description="个人量化玩具与币安合约多策略智能终端",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


for _router_mod in (
    routes_market,
    routes_trading,
    routes_risk,
    routes_ai,
    routes_obsidian,
    routes_strategies,
    routes_square,
    routes_system,
    ws_module,
):
    app.include_router(_router_mod.router)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
if REPORTS_DIR.exists():
    app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR)), name="reports")


__all__ = [
    "app",
    "trader",
    "square_auto_publisher",
    "ws_clients",
    "get_systems",
    "preview_systems",
    "get_strategy_candidates",
    "run_strategy_backtest",
    "run_strategy_auto_improve",
    "apply_strategy_preset",
]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8800)))
