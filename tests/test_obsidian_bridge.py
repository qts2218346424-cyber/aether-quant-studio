import os
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app import app
from obsidian_bridge import ObsidianBridge, obsidian_bridge
from config import load_config, save_config

client = TestClient(app)

@pytest.fixture
def temp_vault(tmp_path):
    orig_cfg = load_config()
    vault = tmp_path / "test_obsidian_vault"
    vault.mkdir()
    try:
        yield vault
    finally:
        save_config(orig_cfg)
        shutil.rmtree(vault, ignore_errors=True)

def test_vault_init_templates(temp_vault):
    bridge = ObsidianBridge()
    res = bridge.init_templates(temp_vault)
    assert res["ok"] is True
    assert (temp_vault / "01-交易策略").is_dir()
    assert (temp_vault / "02-交易复盘" / "每日总结").is_dir()
    assert (temp_vault / "03-交易习惯与行为进化").is_dir()

    # 检查范例策略文件
    sample_strat = temp_vault / "01-交易策略" / "EMA双均线趋势跟踪策略.md"
    assert sample_strat.exists()
    content = sample_strat.read_text(encoding="utf-8")
    assert "type: trend_following" in content
    assert "入场条件" in content

    # 检查交易习惯文件
    habit_file = temp_vault / "03-交易习惯与行为进化" / "交易习惯进化追踪.md"
    assert habit_file.exists()
    assert "交易习惯与行为进化追踪" in habit_file.read_text(encoding="utf-8")

def test_scan_and_parse_strategies(temp_vault):
    bridge = ObsidianBridge()
    bridge.init_templates(temp_vault)
    
    # 模拟设置 vault 路径
    orig_cfg = load_config()
    try:
        bridge.set_vault_path(str(temp_vault))

        # 添加自定义策略笔记
        custom_strat = temp_vault / "01-交易策略" / "突破动量策略.md"
        custom_strat.write_text("""---
title: 突破动量狙击策略
type: breakout
status: active
symbols: [BTCUSDT, DOGEUSDT]
timeframe: 5m
risk_reward_ratio: 1:3
tags: [突破, 动量, 策略]
---

# 突破动量狙击策略

## 一、入场条件
- 价格突破 20 根 K 线最高价
- 成交量达到均量 2 倍以上

## 二、止盈目标
- 第一目标 1:2，第二目标 1:3

## 三、风控与止损
- 假突破跌回箱体中轨立即止损
""", encoding="utf-8")

        strats = bridge.scan_strategies(force_refresh=True)
        assert len(strats) >= 2
        titles = [s["title"] for s in strats]
        assert "突破动量狙击策略" in titles
        assert "EMA双均线趋势跟踪策略" in titles

        bo = next(s for s in strats if s["title"] == "突破动量狙击策略")
        assert bo["type"] == "breakout"
        assert "BTCUSDT" in bo["symbols"]
        assert "最高价" in bo["entry_rules"]
        assert "止损" in bo["risk_rules"]
    finally:
        # 还原配置
        save_config(orig_cfg)

def test_analyze_habits():
    bridge = ObsidianBridge()
    habits = bridge.analyze_habits(days=7)
    assert "overall_score" in habits
    assert "radar" in habits
    radar = habits["radar"]
    assert 0 <= radar["discipline"] <= 100
    assert 0 <= radar["anti_fomo"] <= 100
    assert 0 <= radar["patience"] <= 100
    assert 0 <= radar["emotional_control"] <= 100
    assert 0 <= radar["adherence"] <= 100
    assert "stage" in habits

def test_sync_to_obsidian(temp_vault):
    orig_cfg = load_config()
    bridge = ObsidianBridge()
    bridge.set_vault_path(str(temp_vault))
    try:
        res = bridge.sync_to_obsidian("2026-09-07")
        assert res["ok"] is True
        
        review_file = Path(res["review_file"])
        assert review_file.exists()
        content = review_file.read_text(encoding="utf-8")
        assert "title: 交易复盘 · 2026-09-07" in content
        assert "[[03-交易习惯与行为进化/交易习惯进化追踪|交易习惯进化追踪]]" in content
        assert "AI 交易习惯与行为诊断" in content
        assert "🏆 策略实盘表现归因" in content

        habit_file = Path(res["habit_file"])
        assert habit_file.exists()
        habit_content = habit_file.read_text(encoding="utf-8")
        assert "交易习惯与行为进化追踪" in habit_content
        assert "五维习惯表现" in habit_content
    finally:
        save_config(orig_cfg)

def test_obsidian_api_endpoints(temp_vault):
    orig_cfg = load_config()
    try:
        # 1. Config API
        res_cfg = client.post("/api/obsidian/config", json={
            "vault_path": str(temp_vault),
            "auto_sync": True
        })
        assert res_cfg.status_code == 200
        assert res_cfg.json()["ok"] is True

        # 2. Init API
        res_init = client.post("/api/obsidian/init_templates", json={
            "vault_path": str(temp_vault)
        })
        assert res_init.status_code == 200
        assert res_init.json()["ok"] is True

        # 3. Status API
        res_status = client.get("/api/obsidian/status")
        assert res_status.status_code == 200
        stat = res_status.json()
        assert stat["ok"] is True
        assert stat["connected"] is True
        assert stat["strategy_count"] >= 1

        # 4. Strategies API
        res_strat = client.get("/api/obsidian/strategies")
        assert res_strat.status_code == 200
        assert res_strat.json()["ok"] is True
        assert res_strat.json()["count"] >= 1

        # 5. Habits API
        res_habits = client.get("/api/obsidian/habits")
        assert res_habits.status_code == 200
        assert res_habits.json()["ok"] is True
        assert "overall_score" in res_habits.json()["habits"]

        # 6. Sync API
        res_sync = client.post("/api/obsidian/sync", json={"date": "2026-09-07"})
        assert res_sync.status_code == 200
        assert res_sync.json()["ok"] is True

        # 7. Capture Note API
        dummy_img = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        res_cap = client.post("/api/obsidian/capture_note", json={
            "symbol": "BTCUSDT",
            "interval": "15m",
            "note": "回踩EMA21获得支撑，确认多头动量",
            "image_base64": dummy_img,
            "date": "2026-09-07"
        })
        assert res_cap.status_code == 200
        cap_data = res_cap.json()
        assert cap_data["ok"] is True
        assert cap_data["symbol"] == "BTCUSDT"
        assert cap_data["interval"] == "15m"
        assert Path(cap_data["image_path"]).exists()

        # 验证复盘笔记包含截图引用与笔记
        rev_content = Path(cap_data["review_file"]).read_text(encoding="utf-8")
        assert "📸 实盘图表快照与复盘标记" in rev_content
        assert "BTCUSDT (15m)" in rev_content
        assert "回踩EMA21获得支撑" in rev_content
        # 8. Match Strategy API
        res_match = client.get("/api/obsidian/match/BTCUSDT")
        assert res_match.status_code == 200
        m_data = res_match.json()
        assert m_data["ok"] is True
        assert m_data["symbol"] == "BTCUSDT"
        assert "matches" in m_data
    finally:
        save_config(orig_cfg)


def test_match_strategies_for_symbol(temp_vault):
    bridge = ObsidianBridge()
    bridge.init_templates(temp_vault)
    orig_cfg = load_config()
    bridge.set_vault_path(str(temp_vault))
    try:
        indicators = {
            "price": 68000.0,
            "ema9": 68200.0,
            "ema21": 67800.0,
            "rsi": 58.0,
            "atr": 450.0,
            "vol_spike": 1.25,
            "htf_trend": 1
        }
        res = bridge.match_strategies_for_symbol("BTCUSDT", current_price=68000.0, indicators=indicators)
        assert res["ok"] is True
        assert res["count"] >= 1
        best = res["best_match"]
        assert best is not None
        assert best["match_score"] >= 75
        assert best["direction"] == "LONG"
        assert best["plan"]["side"] == "BUY"
        assert best["plan"]["stop_loss"] < 68000.0
        assert best["plan"]["take_profit"] > 68000.0
        assert any(c["status"] == "pass" for c in best["checklist"])
    finally:
        save_config(orig_cfg)


