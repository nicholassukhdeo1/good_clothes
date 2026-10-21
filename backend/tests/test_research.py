import asyncio

import pytest

import research


class FakeBrowser:
    def __init__(self, results=None):
        self.requests = None
        self._results = results

    def search_all(self, requests):
        self.requests = list(requests)
        if self._results is not None:
            return self._results
        return [
            {"text": "page text", "source": {"label": f"Search: {q}", "url": "https://x.test"}}
            for q, _ in requests
        ]


class FakePage:
    """One browser tab. Records where it was sent and whether it was closed."""

    def __init__(self, text, url="https://example.test/landed"):
        self._text = text
        self.url = url
        self.goto_url = None
        self.closed = False

    async def goto(self, url, **kwargs):
        self.goto_url = url

    async def inner_text(self, selector):
        return self._text

    async def close(self):
        self.closed = True


class FakeContext:
    def __init__(self, *pages):
        self._pages = list(pages)
        self.opened = 0

    async def new_page(self):
        self.opened += 1
        return self._pages.pop(0)


def _browser_with(*pages):
    browser = research.EvidenceBrowser()
    browser._ctx = FakeContext(*pages)
    return browser


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


def test_wikipedia_source_goes_through_wikipedia_search():
    # Not a guessed /wiki/<slug>: an exact title match redirects to the article and
    # a near miss lands on results instead of a 404.
    label, url = research._url_for("Patagonia, Inc.", "wikipedia")
    assert url == "https://en.wikipedia.org/w/index.php?search=Patagonia%2C+Inc."
    assert label == "Wikipedia"


def test_unknown_source_falls_back_to_a_search():
    # A bad enum value must not break the run.
    _, url = research._url_for("Everlane", "news")
    assert url.startswith("https://duckduckgo.com/html/")


# ---------- loading one page ----------


def test_page_text_and_landing_url_are_returned():
    page = FakePage("e" * 1200, url="https://en.wikipedia.org/wiki/Everlane")
    browser = _browser_with(page)
    out = asyncio.run(browser._one("Everlane", "wikipedia"))
    assert out["text"] == "e" * 1200
    # The landing URL, so the badge links where the browser actually ended up.
    assert out["source"] == {"label": "Wikipedia", "url": "https://en.wikipedia.org/wiki/Everlane"}
    assert page.goto_url == research._url_for("Everlane", "wikipedia")[1]


def test_page_text_is_truncated():
    browser = _browser_with(FakePage("e" * 9000))
    out = asyncio.run(browser._one("Everlane", "web"))
    assert len(out["text"]) == research.PAGE_CHAR_LIMIT


def test_rate_limited_wikipedia_page_is_not_evidence():
    # Measured for real: Wikipedia intermittently 429s Browserbase's egress IPs and
    # answers with a ~430 char error page, which used to reach Claude as research.
    rate_limited = (
        "Error\n\nToo many requests. Please email noc@wikimedia.org for more "
        "information. (8f5b856)\n\nIf you report this error to the Wikimedia System "
        "Administrators, please include the details below."
    )
    browser = _browser_with(FakePage(rate_limited))
    with pytest.raises(research.ThinPage):
        asyncio.run(browser._one("Everlane", "wikipedia"))


def test_thin_page_is_rejected():
    browser = _browser_with(FakePage("Not found."))
    with pytest.raises(research.ThinPage):
        asyncio.run(browser._one("Everlane", "web"))


def test_tab_is_closed_even_when_the_page_is_thin():
    page = FakePage("tiny")
    browser = _browser_with(page)
    with pytest.raises(research.ThinPage):
        asyncio.run(browser._one("Everlane", "web"))
    assert page.closed is True


def test_tab_is_closed_after_a_good_load():
    page = FakePage("e" * 1200)
    browser = _browser_with(page)
    asyncio.run(browser._one("Everlane", "web"))
    assert page.closed is True


def test_empty_query_is_rejected():
    browser = _browser_with(FakePage("e" * 1200))
    with pytest.raises(ValueError):
        asyncio.run(browser._one("   ", "web"))


# ---------- loading a whole turn's worth at once ----------


def test_requests_run_concurrently_and_keep_their_order():
    page_a, page_b = FakePage("a" * 1200), FakePage("b" * 1200)
    browser = _browser_with(page_a, page_b)
    out = asyncio.run(browser._gather([("a", "web"), ("b", "wikipedia")]))
    assert [o["text"][0] for o in out] == ["a", "b"]
    assert browser._ctx.opened == 2


def test_one_dead_page_does_not_lose_the_others():
    # return_exceptions keeps the good result; the caller reports the bad one.
    browser = _browser_with(FakePage("thin"), FakePage("b" * 1200))
    out = asyncio.run(browser._gather([("a", "web"), ("b", "web")]))
    assert isinstance(out[0], research.ThinPage)
    assert out[1]["text"] == "b" * 1200


def test_no_requests_never_opens_a_browser():
    # A turn with nothing to load must not pay for a cloud session.
    assert research.EvidenceBrowser().search_all([]) == []


# ---------- the tool body ----------


def test_gather_passes_every_call_in_one_batch():
    browser = FakeBrowser()
    research.gather_brand_evidence(
        browser,
        [
            {"query": "Everlane labor", "source": "web"},
            {"query": "Everlane owner", "source": "wikipedia"},
        ],
    )
    assert browser.requests == [("Everlane labor", "web"), ("Everlane owner", "wikipedia")]


def test_gather_defaults_to_a_web_search():
    browser = FakeBrowser()
    research.gather_brand_evidence(browser, [{"query": "Everlane"}])
    assert browser.requests == [("Everlane", "web")]
