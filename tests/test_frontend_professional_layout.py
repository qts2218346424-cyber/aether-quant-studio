from src.paths import load_frontend_bundle_text
from pathlib import Path


html = load_frontend_bundle_text()


def test_professional_shell_and_existing_runtime_hooks_exist():
    assert 'class="metric-strip"' in html
    assert 'class="system-overview"' in html
    assert 'class="workspace-mode"' in html
    assert 'id="kline-chart"' in html
    assert 'id="bottom-execution"' in html


def test_preview_cards_are_read_only():
    assert html.count('data-i18n="readOnly"') >= 5
    assert "data-i18n=\"positionProtectionCopy\"" in html
    assert "function selectSystemPreview" in html


def test_language_switch_is_persistent_and_covers_shell_labels():
    assert "function setLanguage(locale)" in html
    assert "localStorage.setItem('quant_language'" in html
    assert "'en-US'" in html
    for key in (
        "balance",
        "availableBalance",
        "settings",
        "indicators",
        "executionDiagnostics",
    ):
        assert key in html


def test_dynamic_workspace_surfaces_use_localized_display_helpers():
    for helper in (
        "function displaySystemName",
        "function displaySide",
        "function renderStatusBanner",
        "function refreshDynamicLanguage",
        "function renderSignals",
    ):
        assert helper in html

    for stale_literal in (
        "Viewing ${label}",
        "Score: ${sig.score}",
        ">${p.side} ${p.leverage}x",
        "trend_following</div>",
        "['开盘', fmt(d[0])]",
        "['成交量', vol]",
        ">一键下单</button>",
    ):
        assert stale_literal not in html


def test_language_dictionary_covers_runtime_surfaces():
    for key in (
        "aiLoading",
        "signalScore",
        "volume",
        "themePalette",
        "rankingsLoading",
        "noExecutionEvents",
        "myPositionSentiment",
        "settingsTitle",
        "report",
    ):
        assert key in html

    assert "data-i18n-title=\"themePalette\"" in html
    assert "data-i18n=\"aiLoading\"" in html
    assert "data-i18n=\"signalScore\"" in html


def test_language_switch_refreshes_existing_dynamic_content_without_trade_calls():
    refresh_start = html.index("function refreshDynamicLanguage()")
    refresh_end = html.index("function selectSystemPreview", refresh_start)
    refresh = html[refresh_start:refresh_end]

    for renderer in (
        "renderIndicators(lastIndicators)",
        "renderPositions(lastPositions)",
        "renderSignals()",
        "renderAIAnalysis(lastAiPayload, lastAiSymbol)",
        "renderRecommend(lastRecommendPayload)",
    ):
        assert renderer in refresh

    for forbidden in ("/api/order", "/api/close", "/api/auto_trade"):
        assert forbidden not in refresh


def test_chart_price_lines_are_read_only_and_user_toggleable():
    for marker in (
        'data-chart-line="entry"',
        'data-chart-line="stop"',
        'data-chart-line="takeProfit"',
        'data-chart-line="levels"',
        'data-chart-line="ema"',
        'data-chart-line="vwap"',
        "function chartLineLevels",
        "function setChartLineVisibility",
        "function chartMarkLine",
        "markLine: chartMarkLine()",
        "localStorage.setItem('quant_chart_lines'",
    ):
        assert marker in html

    chart_section = html[html.index("function chartLineLevels"):html.index("// ===== Chart =====")]
    for forbidden in ("/api/order", "/api/close", "/api/auto_trade"):
        assert forbidden not in chart_section


def test_chart_order_ticket_is_explicit_and_bilingual():
    for marker in (
        'id="chart-order-mode"',
        'data-i18n="chartOrder"',
        "function toggleChartOrderMode",
        "function openChartOrderTicket",
        "function submitChartLimitOrder",
        "chart-order-price",
        "chart-order-quantity",
        "chart-order-confirm",
        "/api/chart_limit_order",
        "chartOrderHintActive",
        "chartOrderSubmitting",
    ):
        assert marker in html

    assert "chart.getZr().on('click'" in html
    assert "positionSide" not in html[html.index("submitChartLimitOrder"):html.index("// ===== WebSocket =====")]


def test_chart_shell_matches_tradingview_like_data_panel_shape():
    for marker in (
        'class="chart-tabbar"',
        'data-chart-tab="chart"',
        'data-chart-tab="info"',
        'data-chart-tab="data"',
        'class="chart-timeframes"',
        'data-chart-interval="1d"',
        'data-chart-interval="1w"',
        'class="chart-tool-rail"',
        'class="chart-symbol-overlay"',
        'id="chart-ohlc"',
        'class="chart-volume-overlay"',
        'id="chart-volume-value"',
        'class="chart-statusbar"',
        'function selectChartInterval',
        'function updateChartHeader',
        'data-i18n="chartTab"',
        'data-i18n="chartVolume"',
    ):
        assert marker in html

    assert 'id="kline-chart"' in html
    assert 'id="chart-order-mode"' in html
