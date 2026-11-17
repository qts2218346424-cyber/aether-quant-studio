from src.paths import load_frontend_bundle_text
from pathlib import Path


html = load_frontend_bundle_text()


def test_chart_lines_include_axis_extent_for_offscreen_position_levels():
    assert "chartLineExtent" in html
    assert "const extent = chartLineExtent()" in html
    assert "entry_plan" in html
    assert "entry_low" in html
    assert "stop_loss" in html


def test_position_lines_take_precedence_over_new_entry_plan():
    section = html[html.index("function chartLineLevels"):html.index("// ===== Chart =====")]
    assert "position entry/stop/take-profit levels take precedence" in section
    assert "else if (activePlan)" in section


def test_chart_renders_numeric_ai_entry_plan_in_analysis_panel():
    assert "entryZone" in html
    assert "suggestedEntry" in html
    assert "riskReward" in html


def test_chart_line_changes_remain_read_only():
    section = html[html.index("function chartLineLevels"):html.index("function toggleChartOrderMode")]
    for forbidden in ("/api/order", "/api/close", "/api/auto_trade", "/api/chart_limit_order"):
        assert forbidden not in section
