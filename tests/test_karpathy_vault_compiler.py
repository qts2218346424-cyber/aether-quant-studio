from src.paths import load_frontend_bundle_text
import os
import shutil
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
    vault = tmp_path / "test_karpathy_vault"
    vault.mkdir()
    try:
        yield vault
    finally:
        save_config(orig_cfg)
        shutil.rmtree(vault, ignore_errors=True)


def test_karpathy_vault_structure_and_templates(temp_vault):
    bridge = ObsidianBridge()
    res = bridge.init_templates(temp_vault)
    assert res["ok"] is True
    assert (temp_vault / "00-原始资料与灵感库").is_dir()
    assert (temp_vault / "00-原始资料与灵感库" / "README.md").exists()
    assert (temp_vault / "01-交易策略").is_dir()
    assert (temp_vault / "02-交易复盘" / "每日总结").is_dir()
    assert (temp_vault / "03-交易习惯与行为进化").is_dir()
    assert (temp_vault / "00-知识库索引_MOC.md").exists()

    # 验证全球高胜率策略笔记
    strat_dir = temp_vault / "01-交易策略"
    expected_strats = [
        "01-动态安全网格马丁策略(DCA).md",
        "02-SMC聪明钱订单块与流动性劫持策略.md",
        "03-TTM_Squeeze波动率挤压突破策略.md",
        "04-VWAP机构量价锚定与均值回归策略.md",
        "05-海龟双向ATR通道突破趋势策略.md",
        "06-多周期EMA共振与RSI顶底背离策略.md",
        "EMA双均线趋势跟踪策略.md"
    ]
    for es in expected_strats:
        p = strat_dir / es
        assert p.exists(), f"Strategy file missing: {es}"
        content = p.read_text(encoding="utf-8")
        assert "title:" in content
        assert "[[00-知识库索引_MOC|知识库总索引]]" in content

    # 验证动态安全网格马丁策略关键参数
    martin = (strat_dir / "01-动态安全网格马丁策略(DCA).md").read_text(encoding="utf-8")
    assert "type: grid_martingale" in martin
    assert "target_win_rate: 91.5%" in martin
    assert "ATR" in martin
    assert "熔断" in martin

    # 验证 MOC 文件内容
    moc_content = (temp_vault / "00-知识库索引_MOC.md").read_text(encoding="utf-8")
    assert "Map of Content · Karpathy LLM-Wiki" in moc_content
    assert "动态安全网格马丁策略" in moc_content
    assert "SMC聪明钱订单块与流动性劫持策略" in moc_content
    assert "TTM Squeeze 波动率挤压突破策略" in moc_content
    assert "VWAP 机构量价锚定与均值回归策略" in moc_content
    assert "海龟双向 ATR 通道突破趋势策略" in moc_content
    assert "多周期 EMA 共振与 RSI 顶底背离策略" in moc_content
    assert "核心量化概念与知识图谱" in moc_content
    assert "自维护审计报告" in moc_content


def test_compile_vault_and_live_attribution(temp_vault):
    orig_cfg = load_config()
    try:
        bridge = ObsidianBridge()
        bridge.init_templates(temp_vault)
        bridge.set_vault_path(str(temp_vault))

        # 扫描解析策略
        strats = bridge.scan_strategies(force_refresh=True)
        assert len(strats) >= 7
        titles = [s["title"] for s in strats]
        assert "动态安全网格马丁策略 (Dynamic Safety-Grid DCA)" in titles
        assert "SMC聪明钱订单块与流动性劫持策略" in titles

        # 执行自维护编译
        c_res = bridge.compile_vault(temp_vault)
        assert c_res["ok"] is True
        assert c_res["strategy_count"] >= 7
        assert c_res["health_score"] >= 90.0
        assert Path(c_res["moc_file"]).exists()

        # 验证同步交易复盘日记时自动自愈并更新 MOC
        sync_res = bridge.sync_to_obsidian("2026-09-08")
        assert sync_res["ok"] is True
        assert "compile_info" in sync_res
        assert sync_res["compile_info"]["ok"] is True
    finally:
        save_config(orig_cfg)


def test_compile_api_endpoint(temp_vault):
    orig_cfg = load_config()
    try:
        bridge = ObsidianBridge()
        bridge.init_templates(temp_vault)
        bridge.set_vault_path(str(temp_vault))

        # 测试 POST /api/obsidian/compile
        res = client.post("/api/obsidian/compile", json={})
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert data["strategy_count"] >= 7
        assert "00-知识库索引_MOC.md" in data["moc_file"]

        # 测试 GET /api/obsidian/status 返回 moc_exists
        res_stat = client.get("/api/obsidian/status")
        assert res_stat.status_code == 200
        stat = res_stat.json()
        assert stat["ok"] is True
        assert stat["connected"] is True
        assert stat["moc_exists"] is True
        assert stat["strategy_count"] >= 7
    finally:
        save_config(orig_cfg)


def test_frontend_compile_and_moc_elements():
    html = load_frontend_bundle_text()
    assert 'id="btn-obs-compile"' in html
    assert "function compileObsidianVault()" in html
    assert "/api/obsidian/compile" in html
    assert "Karpathy Wiki" in html
    assert "理论胜率:" in html
    assert "saveBlogToObsidian" in html
    assert "保存至Obsidian(MD+封面)" in html


def test_dataview_and_kanban_boards(temp_vault):
    bridge = ObsidianBridge()
    res = bridge.init_templates(temp_vault)
    assert res["ok"] is True
    
    # 验证 Dataview 数据总看板
    dv_file = temp_vault / "00-交易数据看板_Dataview.md"
    assert dv_file.exists()
    dv_text = dv_file.read_text(encoding="utf-8")
    assert "cssclass: dashboard, cards" in dv_text
    assert "Heatmap Calendar" in dv_text
    assert "dataviewjs" in dv_text
    assert "```chart" in dv_text
    assert "TABLE WITHOUT ID" in dv_text

    # 验证 Kanban 策略生命周期看板
    kb_file = temp_vault / "01-策略研发与实盘看板_Kanban.md"
    assert kb_file.exists()
    kb_text = kb_file.read_text(encoding="utf-8")
    assert "kanban-plugin: basic" in kb_text
    assert "## 💡 策略灵感与原始研报" in kb_text
    assert "## 🚀 实盘运行中策略" in kb_text
    assert "## ⚠️ 风险观察与限额监控" in kb_text


def test_save_html_and_md_reports(temp_vault):
    orig_cfg = load_config()
    try:
        bridge = ObsidianBridge()
        bridge.init_templates(temp_vault)
        bridge.set_vault_path(str(temp_vault))

        # 测试 save_html_report
        sample_html = "<html><body><h1>2026-09-08 交易复盘全景图表</h1><div id='echarts-kline'></div></body></html>"
        html_res = bridge.save_html_report("2026-09-08", sample_html)
        assert html_res["ok"] is True
        saved_html = temp_vault / "02-交易复盘" / "HTML图表" / "2026-09-08-交易复盘图表.html"
        assert saved_html.exists()
        assert "echarts-kline" in saved_html.read_text(encoding="utf-8")

        # 测试 save_md_report
        sample_md = "# 每日交易总结 · 2026-09-08\n\n- 平仓笔数: 5, 净盈亏: +128.50 U"
        md_res = bridge.save_md_report("2026-09-08", sample_md)
        assert md_res["ok"] is True
        saved_md = temp_vault / "02-交易复盘" / "每日总结" / "2026-09-08-每日总结导出.md"
        assert saved_md.exists()
        assert "+128.50 U" in saved_md.read_text(encoding="utf-8")
    finally:
        save_config(orig_cfg)


def test_save_blog_note_and_api(temp_vault):
    orig_cfg = load_config()
    try:
        bridge = ObsidianBridge()
        bridge.init_templates(temp_vault)
        bridge.set_vault_path(str(temp_vault))

        # 测试 POST /api/obsidian/save_blog_note
        # 构造简单 1x1 透明 PNG Base64
        sample_png_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        blog_payload = {
            "title": "BTC多头结构破位预警与量价复盘",
            "hook": "日内现货成交量骤降，谨防诱多插针扫损！",
            "body": "从 15m 周期来看，EMA9 与 EMA21 形成死叉...",
            "tags": "BTCUSDT, 量价分析, 诱多预警",
            "platform": "xhs",
            "tone": "analytical",
            "cover_data_url": sample_png_b64,
            "date": "2026-09-08"
        }
        res = client.post("/api/obsidian/save_blog_note", json=blog_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert Path(data["note_path"]).exists()
        assert data["cover_filename"] != ""

        # 检查封面图片是否存在
        cover_path = temp_vault / "00-原始资料与灵感库" / "行情简报与博客" / "封面" / data["cover_filename"]
        assert cover_path.exists()
        assert cover_path.stat().st_size > 0

        # 检查博客 Markdown 文件内容
        note_txt = Path(data["note_path"]).read_text(encoding="utf-8")
        assert "BTC多头结构破位预警与量价复盘" in note_txt
        assert data["cover_filename"] in note_txt
        assert "![[" in note_txt
        assert "00-知识库索引_MOC" in note_txt
    finally:
        save_config(orig_cfg)


def test_dashboard_and_daily_tasks(temp_vault):
    bridge = ObsidianBridge()
    res = bridge.init_templates(temp_vault)
    assert res["ok"] is True

    # 1. 验证 00-量化交易员仪表盘_Dashboard.md
    dash_file = temp_vault / "00-量化交易员仪表盘_Dashboard.md"
    assert dash_file.exists()
    dash_txt = dash_file.read_text(encoding="utf-8")
    assert "量化交易员控制台仪表盘" in dash_txt
    assert "核心风控保险丝" in dash_txt
    assert "3.0%" in dash_txt
    assert "在线策略战力矩阵" in dash_txt
    assert "驾驶舱快捷操作控制台" in dash_txt
    assert "```chart" in dash_txt
    assert "TASK" in dash_txt

    # 2. 验证 00-每日交易待办与纪律清单.md
    tasks_file = temp_vault / "00-每日交易待办与纪律清单.md"
    assert tasks_file.exists()
    tasks_txt = tasks_file.read_text(encoding="utf-8")
    assert "每日交易待办与纪律清单" in tasks_txt
    assert "盘前准备检查清单" in tasks_txt
    assert "盘中执行与行为纪律" in tasks_txt
    assert "盘后复盘与归档结账" in tasks_txt
    assert "全库动态未完成任务汇总" in tasks_txt
    assert "TASK" in tasks_txt

    # 3. 验证 MOC 索引中收录仪表盘与待办清单
    moc_txt = (temp_vault / "00-知识库索引_MOC.md").read_text(encoding="utf-8")
    assert "00-量化交易员仪表盘_Dashboard" in moc_txt
    assert "00-每日交易待办与纪律清单" in moc_txt
    # 验证策略笔记精准识别，不把看板/仪表盘/待办误判为策略笔记
    strats = bridge.scan_strategies(force_refresh=True)
    assert len(strats) >= 7
    for s in strats:
        assert "仪表盘" not in s["title"]
        assert "待办" not in s["title"]


def test_square_blog_module_and_api(temp_vault, monkeypatch):
    orig_cfg = load_config()
    try:
        bridge = ObsidianBridge()
        bridge.init_templates(temp_vault)
        bridge.set_vault_path(str(temp_vault))

        # 1. 验证 04-币安广场与个人博客 核心目录结构
        sq_root = temp_vault / "04-币安广场与个人博客"
        assert sq_root.is_dir()
        assert (sq_root / "草稿库").is_dir()
        assert (sq_root / "定时排期库").is_dir()
        assert (sq_root / "已发布归档").is_dir()
        assert (sq_root / "封面").is_dir()

        # 2. 验证看板、SOP写作指南与模板库
        kanban = (sq_root / "00-币安广场博客工作台_Kanban.md").read_text(encoding="utf-8")
        assert "币安广场博客工作台" in kanban
        assert "kanban-plugin: basic" in kanban

        sop = (sq_root / "01-币安广场爆款写作指南与SOP.md").read_text(encoding="utf-8")
        assert "爆款创作指南与发帖 SOP" in sop
        assert "黄金前3秒" in sop

        tpl = (sq_root / "02-爆款文章模板库.md").read_text(encoding="utf-8")
        assert "币安广场爆款文章实战模板库" in tpl
        assert "聪明钱在想什么" in tpl
        assert "Order Block" in tpl

        # 3. 验证排期范例文档
        sample_post = sq_root / "定时排期库" / "2026-09-08_BTC夜盘深度推演.md"
        assert sample_post.exists()
        sample_txt = sample_post.read_text(encoding="utf-8")
        assert "BTC夜盘深度推演" in sample_txt
        assert "status: scheduled" in sample_txt
        assert "binance_square" in sample_txt

        # 4. 验证策略扫描保持纯粹（排除博客笔记）
        strats = bridge.scan_strategies(force_refresh=True)
        assert len(strats) == 7
        for s in strats:
            assert "04-币安广场" not in s["relative_path"]
            assert "推演" not in s["title"]

        # 5. 验证博客笔记扫描
        sq_blogs = bridge.scan_square_blogs(force_refresh=True)
        assert len(sq_blogs) >= 1
        b0 = sq_blogs[0]
        assert "BTC夜盘深度推演" in b0["title"]
        assert b0["status"] == "scheduled"
        assert b0["scheduled_time"] == "2026-09-08 20:00"

        # 6. 验证 GET /api/obsidian/square_blogs 接口
        res = client.get("/api/obsidian/square_blogs")
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert data["count"] >= 1
        assert any("BTC夜盘" in b["title"] for b in data["blogs"])

        # 7. 模拟一键发布至币安广场并归档
        async def fake_publish_blog(title, body, tags="", cover_data_url="", **kwargs):
            return {
                "id": "sq-88888",
                "link": "https://www.binance.com/square/post/sq-88888",
                "raw_status": "success",
                "cover_uploaded": True,
                "article_submitted": True
            }

        monkeypatch.setattr("binance_square_publisher.publish_blog", fake_publish_blog)

        pub_payload = {
            "relative_path": "04-币安广场与个人博客/定时排期库/2026-09-08_BTC夜盘深度推演.md"
        }
        res_pub = client.post("/api/obsidian/publish_square_note", json=pub_payload)
        assert res_pub.status_code == 200
        pub_data = res_pub.json()
        assert pub_data["ok"] is True
        assert pub_data["id"] == "sq-88888"
        assert pub_data["link"] == "https://www.binance.com/square/post/sq-88888"

        # 验证文件已移动到已发布归档并更新 frontmatter
        archived_f = sq_root / "已发布归档" / "2026-09-08_BTC夜盘深度推演.md"
        assert archived_f.exists()
        assert not sample_post.exists()  # 原排期文件已被移走/归档

        archived_txt = archived_f.read_text(encoding="utf-8")
        assert "status: published" in archived_txt
        assert "sq-88888" in archived_txt
        assert "published_at:" in archived_txt

        # 验证再次扫描状态变为 published
        sq_blogs_after = bridge.scan_square_blogs(force_refresh=True)
        assert any(b["status"] == "published" and b["square_post_id"] == "sq-88888" for b in sq_blogs_after)

    finally:
        save_config(orig_cfg)


