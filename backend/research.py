# research.py — the Browserbase layer (your sponsor integration).
# Drives a cloud browser on Browserbase to gather raw evidence about a brand.
# Returns { text, sources } that synthesize.py hands to Claude.
#
# Why Browserbase and not requests/BeautifulSoup: real sites block naive scrapers.
# A managed browser session handles JS, fingerprints, and consent walls for you —
# that's the "agent that uses the web" the prize asks for.

from urllib.parse import quote_plus
from browserbase import Browserbase
from playwright.sync_api import sync_playwright
from config import BROWSERBASE_API_KEY, BROWSERBASE_PROJECT_ID

# DuckDuckGo's HTML endpoint + Wikipedia are far more scrape-friendly than Google.
# TODO: add stronger sources, e.g. a brand's Good On You page if one exists.
def _targets(brand: str):
    q = quote_plus(brand)
    return [
        ("Search: ethics", f"https://duckduckgo.com/html/?q={q}+ethical+sustainable+brand+factory"),
        ("Search: ownership", f"https://duckduckgo.com/html/?q={q}+parent+company+owner+private+equity"),
        ("Wikipedia", f"https://en.wikipedia.org/wiki/{brand.replace(' ', '_')}"),
    ]


def gather_brand_evidence(brand: str) -> dict:
    bb = Browserbase(api_key=BROWSERBASE_API_KEY)
    session = bb.sessions.create(project_id=BROWSERBASE_PROJECT_ID)

    evidence, sources = [], []
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(session.connect_url)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for label, url in _targets(brand):
            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(1500)
                text = page.inner_text("body")[:4000]
                evidence.append(f"[{label}]\n{text}")
                sources.append({"label": label, "url": page.url})
            except Exception as e:
                evidence.append(f"[{label}] failed: {e}")
        browser.close()

    return {"text": "\n\n".join(evidence), "sources": sources}
