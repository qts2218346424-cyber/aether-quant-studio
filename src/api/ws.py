"""Shared-snapshot WebSocket streaming endpoint."""

from __future__ import annotations

import asyncio
import json
import time
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.context import get_trader, ws_clients

router = APIRouter(tags=["websocket"])

_ws_snapshot_lock = asyncio.Lock()
_ws_snapshot: dict | None = None
_ws_snapshot_ts: float = 0.0


def _json_default(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)


async def get_ws_snapshot() -> dict:
    """每秒最多拉取一次账户快照，多 WS 连接共享同一份快照以降低 API 频控压力。"""
    global _ws_snapshot, _ws_snapshot_ts
    now = time.monotonic()
    if _ws_snapshot is not None and now - _ws_snapshot_ts < 1.0:
        return _ws_snapshot
    async with _ws_snapshot_lock:
        now = time.monotonic()
        if _ws_snapshot is not None and now - _ws_snapshot_ts < 1.0:
            return _ws_snapshot
        t = get_trader()
        status = await t.get_status()
        status["indicators"] = t.latest_indicators
        status["last_signal"] = t.signals_log[-1] if t.signals_log else None
        status["latest_klines"] = t.latest_klines
        _ws_snapshot = status
        _ws_snapshot_ts = now
        return _ws_snapshot


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    try:
        while True:
            status = await get_ws_snapshot()
            await ws.send_text(json.dumps(status, default=_json_default))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        if ws in ws_clients:
            ws_clients.remove(ws)
    except Exception:
        if ws in ws_clients:
            ws_clients.remove(ws)
