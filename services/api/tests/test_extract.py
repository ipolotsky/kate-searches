"""Стадия extract: правило гидратации и trafilatura-извлечение без сети."""

from app.pipeline.extract import extract_text, needs_hydration

_HTML = """
<html><head><title>Archive drop</title></head>
<body>
<nav>menu one two three</nav>
<article>
<h1>Heritage house reissues its archive jackets</h1>
<p>The fashion house unveiled a reissued archive collection this morning in Milan,
featuring leather jackets and hand stitched denim that first appeared decades ago.</p>
<p>Resale specialists expect strong collector demand for the rare designer pieces.</p>
</article>
<footer>copyright boilerplate links privacy terms</footer>
</body></html>
"""


def test_needs_hydration_rules() -> None:
    assert needs_hydration(False, "anything", 500) is True
    assert needs_hydration(True, "x" * 600, 500) is False
    assert needs_hydration(True, "short", 500) is True


def test_extract_text_pulls_article_body() -> None:
    text, _language = extract_text(_HTML)
    assert "archive" in text.lower()
    assert "jackets" in text.lower()
    assert "menu one two three" not in text.lower()
    assert "privacy terms" not in text.lower()


def test_extract_text_empty_html() -> None:
    assert extract_text("") == ("", None)
