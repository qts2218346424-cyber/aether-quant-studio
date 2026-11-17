from src.paths import load_frontend_bundle_text
from pathlib import Path

html = load_frontend_bundle_text()


def test_obsidian_hub_ui_elements():
    assert 'id="obsidian-btn"' in html
    assert 'id="obsidian-dot"' in html
    assert 'id="obsidian-modal-overlay"' in html
    assert 'id="habit-radar-chart"' in html
    assert 'id="obs-strategy-list"' in html
    assert 'id="obs-vault-path-input"' in html
    assert 'function openObsidianHub()' in html
    assert 'function syncCurrentTradesToObsidian()' in html


def test_chart_indicators_and_sub_indicator_controls():
    assert 'data-chart-line="boll"' in html
    assert 'data-chart-line="tradeMarkers"' in html
    assert 'id="sub-ind-vol"' in html
    assert 'id="sub-ind-macd"' in html
    assert 'id="sub-ind-rsi"' in html
    assert "function switchSubIndicator(mode)" in html
    assert "function calcEMA(candles, period)" in html
    assert "function calcBOLL(candles, period = 20, stdDev = 2)" in html
    assert "function calcMACD(candles, fast = 12, slow = 26, signal = 9)" in html
    assert "function calcRSI(candles, period = 14)" in html


def test_trend_views_equity_and_momentum():
    assert 'id="view-equity"' in html
    assert 'id="view-momentum"' in html
    assert 'id="equity-view"' in html
    assert 'id="momentum-view"' in html
    assert "function renderEquityView()" in html
    assert "function renderMomentumView()" in html


def test_obsidian_snapshot_feature():
    assert 'id="chart-obsidian-snapshot-btn"' in html
    assert 'id="obsidian-snapshot-modal-overlay"' in html
    assert 'id="snap-preview-img"' in html
    assert 'id="obs-snapshot-note"' in html
    assert 'id="snap-submit-btn"' in html
    assert "function openSnapshotModal()" in html
    assert "function closeSnapshotModal()" in html
    assert "function submitChartSnapshot()" in html
    assert "function addSnapshotTag(text)" in html
    assert "/api/obsidian/capture_note" in html


def test_toolbar_and_view_toggle_layout():
    assert ".view-toggle button { padding: 4px 10px; border: none; background: var(--bg-2); color: var(--text-2); font-size: 11px; cursor: pointer; font-family: inherit; white-space: nowrap; min-width: max-content; }" in html
    assert "white-space:nowrap" in html
    assert "overflow-x: auto" in html


def test_symbol_linkage_and_smart_defaults():
    assert "function selectSymbolAndShow(symbol)" in html
    assert "selectSymbolAndShow" in html
    assert "onclick=\"selectSymbolAndShow" in html
    assert "BTCUSDT" in html


def test_obsidian_strategy_matching_ui():
    assert 'data-tab="obsidian"' in html
    assert 'id="side-obsidian"' in html
    assert 'id="obs-match-list"' in html
    assert 'id="obs-match-symbol-badge"' in html
    assert "function loadObsidianStrategyMatch(symbol)" in html
    assert "function renderObsidianStrategyMatch(data)" in html
    assert "function applyObsidianPlanToTicket(side, price)" in html
    assert "/api/obsidian/match/" in html


def test_chart_drawing_and_measurement_tools():
    assert 'class="chart-tool-rail"' in html
    assert 'id="chart-measure-hud"' in html
    assert 'id="chart-measure-text"' in html
    assert 'id="chart-tool-toast"' in html
    assert "activeChartTool" in html
    assert "userHorizontalLevels" in html
    assert "userTrendLines" in html
    assert "measureStartPoint" in html
    assert "function selectChartTool(tool, btn)" in html
    assert "function clearChartDrawings()" in html
    assert "function showMeasureResult(res, x, y)" in html
    assert "function showMeasureTooltip(msg, x, y)" in html
    assert "function hideMeasureTooltip()" in html
    assert "function showChartToolToast(msg" in html


def test_premium_ui_and_dynamic_interactions():
    # Verify fixed unicode escape labels in HTML
    assert '<span data-i18n="denseVolumeZones">密集成交区</span>' in html
    assert '<span data-i18n="swingPoints">趋势高低点</span>' in html
    assert r'>\u5bc6\u96c6' not in html
    assert r'>\u8d8b\u52bf' not in html

    # Verify price dynamic flash interaction
    assert "function flashPriceDisplay(symbol, price)" in html
    assert "price-flash-up" in html
    assert "price-flash-down" in html

    # Verify keyframe animations
    assert "@keyframes radar-pulse" in html
    assert "@keyframes price-flash-up" in html
    assert "@keyframes modalSlideUp" in html


def test_white_minimalist_theme():
    # Verify light & dark dual-theme definitions and switching hooks
    assert "light:    { bg0:'#f8fafc', bg1:'#ffffff'" in html
    assert 'data-theme="light"' in html
    assert "themeLight: '白色简约'" in html
    assert "themeLight: 'Minimal Light'" in html
    assert "body.theme-light" in html
    assert "--bg-0: #f8fafc; --bg-1: #ffffff;" in html
    assert "document.body.classList.toggle('theme-light', name === 'light')" in html
    assert "applyTheme(THEMES[saved] ? saved :" in html


def test_frontend_javascript_syntax_valid():
    import subprocess
    import shutil

    if not shutil.which("node"):
        return
    s1 = html.index("<script>") + 8
    s2 = html.index("</script>", s1)
    script = html[s1:s2]
    node_cmd = [
        "node",
        "-e",
        'let c=""; process.stdin.setEncoding("utf8"); process.stdin.on("data", d => c += d); process.stdin.on("end", () => { const vm=require("vm"); new vm.Script(c); });',
    ]
    res = subprocess.run(
        node_cmd, input=script, encoding="utf-8", capture_output=True
    )
    assert (
        res.returncode == 0
    ), f"JavaScript in static/index.html has syntax error:\n{res.stderr}"


def test_chart_fullscreen_and_header_theme_switcher():
    # Header theme switcher & quick toggle
    assert 'class="header-theme-wrap"' in html
    assert 'id="theme-quick-btn"' in html
    assert "function toggleThemeLightDark()" in html
    assert 'class="theme-switcher header-palette"' in html

    # Fullscreen mode controls
    assert 'id="chart-fullscreen-btn"' in html
    assert 'id="chart-fullscreen-exit"' in html
    assert 'data-tool="fullscreen"' in html
    assert "function toggleChartFullscreen(" in html
    assert ".chart-area.fullscreen-mode" in html
    assert ".chart-fullscreen-exit-btn" in html




