# research.py - the Browserbase layer (your sponsor integration).
# Drives a cloud browser on Browserbase to gather raw evidence about a brand.
#
# Claude drives this file. gather_brand_evidence is exposed to the model as a tool
# (TOOL below), so the model writes its own search queries, reads what comes back,
# and searches again when the evidence is thin. synthesize.py owns the loop that
# executes those calls; this module only knows how to fetch one page.
#
# Why Browserbase and not requests/BeautifulSoup: real sites block naive scrapers.
# A managed browser session handles JS, fingerprints, and consent walls for you -
# that's the "agent that uses the web" the prize asks for.

from urllib.parse import quote_plus
from browserbase import Browserbase
from playwright.sync_api import sync_playwright
from config import BROWSERBASE_API_KEY, BROWSERBASE_PROJECT_ID

PAGE_CHAR_LIMIT = 4000   # how much body text one page contributes to the prompt
NAV_TIMEOUT_MS = 30000
SETTLE_MS = 1500         # let client-rendered results paint before reading text


# The tool Claude can call. The model supplies the QUERY; it never supplies a URL,
# so it cannot point the browser somewhere we didn't choose and cannot invent a
# source - the same honesty rule alternatives.py follows for its links.
TOOL = {
    "name": "gather_brand_evidence",
    "description": (
        "Search the live web for evidence about a clothing brand and return the page "
        "text plus the URL it came from. Call it once per question you want answered "
        "(labor practices, factory conditions, parent company, ownership), and call it "
        "again with different terms when a result comes back empty or off-topic."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Search terms, e.g. 'Everlane factory labor conditions'. "
                    "Always include the brand name."
                ),
            },
            "source": {
                "type": "string",
                "enum": ["web", "wikipedia"],
                "description": (
                    "'web' runs a search-engine query. 'wikipedia' opens the article "
                    "whose title matches the query, which is best for ownership and "
                    "corporate history."
                ),
            },
        },
        "required": ["query", "source"],
        "additionalProperties": False,
    },
}


def _url_for(query: str, source: str):
    # We build every URL ourselves from the model's query. DuckDuckGo's HTML endpoint
    # and Wikipedia are far more scrape-friendly than Google. Anything that isn't
    # "wikipedia" falls through to a search, so a bad enum value can't break the run.
    if source == "wikipedia":
        title = query.strip().replace(" ", "_")
        return "Wikipedia", f"https://en.wikipedia.org/wiki/{title}"
    return f"Search: {query}", f"https://duckduckgo.com/html/?q={quote_plus(query)}"


class EvidenceBrowser:
    """One Browserbase session, reused across every tool call in a request.

    Opened lazily on the first search, so a request that never searches never pays
    for a cloud browser. Each instance belongs to a single request: FastAPI runs the
    sync /research route in a threadpool, so one shared session would be a data race.
    """

    def __init__(self):
        self._pw = None
        self._browser = None
        self._page = None

    def _ensure_page(self):
        if self._page is None:
            bb = Browserbase(api_key=BROWSERBASE_API_KEY)
            session = bb.sessions.create(project_id=BROWSERBASE_PROJECT_ID)
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.connect_over_cdp(session.connect_url)
            ctx = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
            self._page = ctx.pages[0] if ctx.pages else ctx.new_page()
        return self._page

    def search(self, query: str, source: str) -> dict:
        """Load one page and return {text, source}. Raises on a failed navigation."""
        label, url = _url_for(query, source)
        page = self._ensure_page()
        page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
        page.wait_for_timeout(SETTLE_MS)
        return {
            "text": page.inner_text("body")[:PAGE_CHAR_LIMIT],
            # page.url, not the url we built: it reflects redirects, so the badge
            # links where the browser actually landed.
            "source": {"label": label, "url": page.url},
        }

    def close(self):
        # Best effort - a half-open browser must never turn into a 500 on a scored badge.
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:
                pass
        self._pw = self._browser = self._page = None


def gather_brand_evidence(browser: EvidenceBrowser, query: str, source: str = "web") -> dict:
    """The tool body: what runs when Claude calls gather_brand_evidence."""
    if not query.strip():
        raise ValueError("query must not be empty")
    return browser.search(query, source)
