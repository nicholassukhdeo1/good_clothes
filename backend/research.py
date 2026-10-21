# research.py - the Browserbase layer (your sponsor integration).
# Drives a cloud browser on Browserbase to gather raw evidence about a brand.
#
# Claude drives this file. gather_brand_evidence is exposed to the model as a tool
# (TOOL below), so the model writes its own search queries, reads what comes back,
# and searches again when the evidence is thin. synthesize.py owns the loop that
# executes those calls; this module knows how to fetch pages and nothing else.
#
# Why Browserbase and not requests/BeautifulSoup: real sites block naive scrapers.
# A managed browser session handles JS, fingerprints, and consent walls for you -
# that's the "agent that uses the web" the prize asks for.

import asyncio
import threading
from urllib.parse import quote_plus

from browserbase import Browserbase
from playwright.async_api import async_playwright

from config import BROWSERBASE_API_KEY, BROWSERBASE_PROJECT_ID

PAGE_CHAR_LIMIT = 4000   # how much body text one page contributes to the prompt
NAV_TIMEOUT_MS = 30000

# Below this, a page is an error or a stub rather than evidence. Measured: Wikipedia
# rate-limits Browserbase's egress IPs intermittently and answers with a ~430 char
# "Too many requests" page, which used to reach Claude as if it were research.
MIN_USEFUL_CHARS = 600

# There is deliberately no settle/sleep after navigation. Both sources are
# server-rendered, and measuring showed a 1.5s wait per page changed the text we
# extract by one character while costing 4.5s on a three-page turn. A source that
# genuinely needs to paint should wait on a selector, not on the clock.


class ThinPage(RuntimeError):
    """A page loaded but carried no usable evidence (rate limit, stub, empty)."""


# The tool Claude can call. The model supplies the QUERY; it never supplies a URL,
# so it cannot point the browser somewhere we didn't choose and cannot invent a
# source - the same honesty rule alternatives.py follows for its links.
TOOL = {
    "name": "gather_brand_evidence",
    "description": (
        "Search the live web for evidence about a clothing brand and return the page "
        "text plus the URL it came from. Call it once per question you want answered "
        "(labor practices, factory conditions, parent company, ownership), and call it "
        "again with different terms when a result comes back empty or off-topic. "
        "Asking for several searches in one turn is cheaper than one at a time: they "
        "run concurrently."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Search terms, e.g. 'Everlane factory labor conditions'. "
                    "Always include the brand name. For a wikipedia lookup, name the "
                    "company as the article would, e.g. 'Patagonia, Inc.'."
                ),
            },
            "source": {
                "type": "string",
                "enum": ["web", "wikipedia"],
                "description": (
                    "'web' runs a search-engine query. 'wikipedia' looks the company "
                    "up on Wikipedia, which is best for ownership and corporate "
                    "history but is sometimes rate-limited."
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
        # Wikipedia's own search, not a guessed /wiki/<slug>: an exact title match
        # redirects straight to the article, and a near miss lands on results
        # instead of a 404.
        return "Wikipedia", f"https://en.wikipedia.org/w/index.php?search={quote_plus(query)}"
    return f"Search: {query}", f"https://duckduckgo.com/html/?q={quote_plus(query)}"


class EvidenceBrowser:
    """One Browserbase session per request, loading pages concurrently.

    Claude usually asks for several searches in one turn. Playwright's sync API can
    only drive one page at a time, so the pages here run on an async Playwright
    instance owned by a private event loop in a worker thread: callers stay plain
    sync code (FastAPI runs /research in a threadpool) while several tabs are in
    flight at once.

    One instance belongs to one request. Opened lazily on the first search, so a
    request that never searches never pays for a cloud browser.
    """

    def __init__(self):
        self._loop = None
        self._thread = None
        self._pw = None
        self._browser = None
        self._ctx = None

    def search_all(self, requests: list) -> list:
        """Load every (query, source) pair at once.

        Returns one entry per request, in the order given: either {text, source} or
        the Exception that request failed with, so one dead page cannot lose the rest.
        """
        if not requests:
            return []
        self._ensure_open()
        return self._submit(self._gather(requests))

    def close(self):
        # Best effort - a half-open browser must never turn into a 500 on a scored badge.
        if self._loop is None:
            return
        try:
            self._submit(self._shutdown())
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        self._loop.close()
        self._loop = self._thread = self._pw = self._browser = self._ctx = None

    # ---- the private event loop ----

    def _submit(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    def _ensure_open(self):
        if self._loop is not None:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, name="evidence-browser", daemon=True
        )
        self._thread.start()
        self._submit(self._open())

    async def _open(self):
        # Creating the session is a blocking HTTP call, but it is ~0.2s and this loop
        # has nothing else to do yet.
        bb = Browserbase(api_key=BROWSERBASE_API_KEY)
        session = bb.sessions.create(project_id=BROWSERBASE_PROJECT_ID)
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.connect_over_cdp(session.connect_url)
        self._ctx = (
            self._browser.contexts[0]
            if self._browser.contexts
            else await self._browser.new_context()
        )

    async def _shutdown(self):
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._pw is not None:
            try:
                await self._pw.stop()
            except Exception:
                pass

    # ---- loading ----

    async def _gather(self, requests):
        return await asyncio.gather(
            *(self._one(q, s) for q, s in requests), return_exceptions=True
        )

    async def _one(self, query: str, source: str) -> dict:
        if not query.strip():
            raise ValueError("query must not be empty")
        label, url = _url_for(query, source)
        page = await self._ctx.new_page()
        try:
            await page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
            text = await page.inner_text("body")
            # page.url, not the url we built: it reflects redirects, so the badge
            # links where the browser actually landed.
            landed = page.url
        finally:
            await page.close()

        if len(text.strip()) < MIN_USEFUL_CHARS:
            # Not evidence. Say so, so the model spends its next search somewhere
            # else instead of a whole turn working out that this one failed.
            raise ThinPage(f"{label} returned no usable content ({len(text.strip())} chars)")
        return {"text": text[:PAGE_CHAR_LIMIT], "source": {"label": label, "url": landed}}


def gather_brand_evidence(browser: EvidenceBrowser, calls: list) -> list:
    """The tool body: every gather_brand_evidence call from one turn, run at once.

    Returns one entry per call, in order: {text, source} or the Exception it failed
    with.
    """
    return browser.search_all(
        [(str(c.get("query", "")), str(c.get("source", "web"))) for c in calls]
    )
