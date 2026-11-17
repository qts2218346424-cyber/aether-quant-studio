"""Shared runtime context for modular FastAPI routers."""

from __future__ import annotations

import sys
from fastapi import WebSocket

import src  # noqa: F401 - ensure layered module search paths
from trader import Trader
from blog_auto_publish import SquareAutoPublisher

trader = Trader()
square_auto_publisher = SquareAutoPublisher(trader.get_blog_candidates, trader=trader)
ws_clients: list[WebSocket] = []


def get_trader() -> Trader:
    """Return active Trader instance (honors monkeypatching on root `app` module if present)."""
    app_mod = sys.modules.get("app")
    if app_mod is not None and hasattr(app_mod, "trader"):
        return getattr(app_mod, "trader")
    return trader
