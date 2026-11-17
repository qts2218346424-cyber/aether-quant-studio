from src.paths import load_frontend_bundle_text
from pathlib import Path


html = load_frontend_bundle_text()


def test_chart_tabs_have_real_panels_and_switching_logic():
    assert 'data-chart-tab="info"' in html
    assert 'data-chart-tab="data"' in html
    assert 'id="chart-info-panel"' in html
    assert 'id="chart-data-panel"' in html
    assert "panel.hidden = !active" in html


def test_info_and_data_panels_refresh_from_loaded_candles():
    assert "function renderChartInfoPanel()" in html
    assert "function renderChartDataPanel()" in html
    assert "renderChartInfoPanel();" in html
    assert "renderChartDataPanel();" in html
    assert "chart-data-table" in html


def test_chart_tabs_do_not_submit_orders():
    start = html.index("function selectChartTab(tab)")
    end = html.index("function syncChartTimeframeButtons", start)
    assert "fetch(" not in html[start:end]
    assert "/api/order" not in html[start:end]
