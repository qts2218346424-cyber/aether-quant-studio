from src.paths import load_frontend_bundle_text
from pathlib import Path


html = load_frontend_bundle_text()
start = html.index("// ===== Blog and Daily Report =====")
end = html.index("async function showDailyReport", start)
blog = html[start:end]


def test_blog_studio_has_growth_controls_and_bilingual_copy():
    for marker in ("BLOG_I18N", "blog-platform", "blog-tone", "blog-length", "blog-cover-style", "copyBlogTitle", "copyBlogTags"):
        assert marker in blog
    assert "Blog Growth Studio" in blog
    assert "\\u535a\\u5ba2\\u589e\\u957f" in blog


def test_blog_cover_is_local_png_generation():
    assert "blog-cover-canvas" in blog
    assert "function drawBlogCover" in blog
    assert "toDataURL('image/png')" in blog
    assert "function downloadBlogCover" in blog


def test_blog_generation_is_read_only():
    generation = blog[blog.index("function generateBlog"):blog.index("function closeBlog")]
    assert "fetch(" not in generation
    for marker in ("/api/order", "/api/close", "place_order", "create_order"):
        assert marker not in blog
    assert "No orders or position changes" in blog


def test_blog_has_square_publish_action():
    assert "publishBlog" in blog
    assert "/api/square/publish" in blog
    assert "squarePublish" in blog
    assert "cover_data_url" in blog
    assert "我重点关注的标的" in blog
    assert "我的操作与防守逻辑" in blog


def test_blog_mode_selection_refreshes_all_generated_fields():
    assert "onchange=\"updateBlogStudio(true)\"" in blog
    assert "const toneMarker" in blog
    assert "const validation" in blog
    assert "if (opt.platform === 'x')" in blog
    assert "if (opt.length === 'concise')" in blog
    assert "rows.join('\\n\\n')" in blog
