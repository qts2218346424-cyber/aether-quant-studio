from src.paths import load_frontend_bundle_text
from pathlib import Path


html = load_frontend_bundle_text()


def test_dense_volume_zones_are_toggleable_and_rendered_as_mark_areas():
    assert 'data-chart-line="denseZones"' in html
    assert "function chartDenseVolumeAreas()" in html
    assert "markArea: { silent: true, z: 0, data: chartDenseVolumeAreas() }" in html


def test_swing_high_low_points_are_toggleable_and_rendered_as_mark_points():
    assert 'data-chart-line="swingPoints"' in html
    assert "function chartSwingPoints()" in html
    assert "markPoint: { silent: true, data: chartSwingPoints() }" in html
    assert "swingHigh" in html and "swingLow" in html


def test_annotation_features_are_read_only():
    start = html.index("function chartDenseVolumeAreas()")
    end = html.index("function chartMarkLine()", start)
    section = html[start:end]
    assert "fetch(" not in section
    assert "/api/order" not in section
