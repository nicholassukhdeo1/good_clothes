import pytest

import research


class FakeBrowser:
    def __init__(self):
        self.queries = []

    def search(self, query, source):
        self.queries.append((query, source))
        return {"text": "page text", "source": {"label": "Search: x", "url": "https://example.com"}}


# ---------- the tool contract Claude is handed ----------


def test_tool_schema_is_valid_for_strict_mode():
    # strict: true requires additionalProperties: false and every property required.
    schema = research.TOOL["input_schema"]
    assert research.TOOL["strict"] is True
    assert schema["additionalProperties"] is False
    assert sorted(schema["required"]) == sorted(schema["properties"])


def test_tool_takes_a_query_and_a_source_only():
    # The model supplies search terms, never a URL - it cannot point the browser
    # somewhere we did not choose, and cannot invent a source.
    assert sorted(research.TOOL["input_schema"]["properties"]) == ["query", "source"]
    assert research.TOOL["input_schema"]["properties"]["source"]["enum"] == ["web", "wikipedia"]


# ---------- URL building stays on our side ----------


def test_web_source_builds_a_search_url():
    label, url = research._url_for("Everlane factory conditions", "web")
    assert url == "https://duckduckgo.com/html/?q=Everlane+factory+conditions"
    assert label == "Search: Everlane factory conditions"


def test_wikipedia_source_builds_an_article_url():
    label, url = research._url_for("Stella McCartney", "wikipedia")
    assert url == "https://en.wikipedia.org/wiki/Stella_McCartney"
    assert label == "Wikipedia"


def test_unknown_source_falls_back_to_a_search():
    # A bad enum value must not break the run.
    _, url = research._url_for("Everlane", "news")
    assert url.startswith("https://duckduckgo.com/html/")


# ---------- the tool body ----------


def test_gather_delegates_to_the_browser():
    browser = FakeBrowser()
    out = research.gather_brand_evidence(browser, query="Everlane ownership", source="wikipedia")
    assert browser.queries == [("Everlane ownership", "wikipedia")]
    assert out["text"] == "page text"


def test_gather_defaults_to_a_web_search():
    browser = FakeBrowser()
    research.gather_brand_evidence(browser, query="Everlane")
    assert browser.queries == [("Everlane", "web")]


def test_gather_rejects_an_empty_query():
    with pytest.raises(ValueError):
        research.gather_brand_evidence(FakeBrowser(), query="   ")
