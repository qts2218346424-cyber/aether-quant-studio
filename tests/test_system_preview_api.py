import asyncio

from app import get_systems, preview_systems


def test_system_catalog_is_read_only_and_complete():
    payload = asyncio.run(get_systems())
    names = {item["name"] for item in payload["modules"]}
    assert {"trend_following", "breakout", "mean_reversion", "smart_money", "grid", "ensemble"} <= names
    assert payload["orders_created"] == 0


def test_system_preview_has_no_order_side_effects():
    payload = asyncio.run(
        preview_systems(
            {
                "symbol": "HEIUSDT",
                "systems": ["trend_following", "breakout", "ensemble"],
                "interval": "15m",
                "limit": 200,
            }
        )
    )
    assert payload["mode"] == "read_only"
    assert payload["closed_candle_only"] is True
    assert payload["orders_created"] == 0
    assert {item["name"] for item in payload["results"]} == {
        "trend_following",
        "breakout",
        "ensemble",
    }
