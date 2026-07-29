# good_clothes

A Chrome extension that scores clothing items 0-100 on materials, ethics, and ownership — and suggests better alternatives matched to your aesthetic.

Built at a hackathon. Targets SSENSE.

---

## What it does

When you open a product page, a badge appears with three scores:

- **Materials** - computed locally from the fabric composition listed on the page (deterministic, no network call, always works)
- **Ethics** - researched live by a Browserbase cloud browser scraping DuckDuckGo and Wikipedia, then scored by Claude
- **Ownership** - same research pass; penalizes PE-owned and conglomerate brands, rewards independent ownership

The three scores combine into a single 0-100 rating.
If the item scores below 60, the badge surfaces three alternative brands that are more conscious and match your style preferences.

---

## Architecture

```
Chrome extension (content script)
  │
  ├── materials.js       scores fabric composition locally — no network, always instant
  │
  └── background.js      relays to backend (extension can't call APIs directly)
         │
         ├── /research   Browserbase cloud browser → DuckDuckGo + Wikipedia → Claude synthesis
         ├── /alternatives  Claude vision reads product photo → suggests 3 better brands
         └── /chat       Claude Haiku powers the style onboarding conversation
```

The backend is a FastAPI server deployed on Render.
Keys live only in the backend — the extension ships to anyone who installs it, so no secrets touch the extension folder.

---

## Stack

- **Extension** - Chrome MV3 (content script, service worker, `chrome.webNavigation`)
- **Backend** - FastAPI (Python), deployed on Render
- **AI** - Anthropic Claude (Sonnet for research synthesis + vision, Haiku for chat)
- **Browser automation** - Browserbase + Playwright (cloud browser for scraping)
- **Persistence** - SQLite (brand research cache), Supabase (user style preferences)

---

## Running locally

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your API keys
uvicorn main:app --reload
```

**Extension:**
1. Go to `chrome://extensions` and enable Developer mode
2. Click Load unpacked and select the `extension/` folder
3. Open any product page on SSENSE — the badge appears bottom-right

---

## Tests

No API keys or network access needed — all external calls are mocked.

```bash
cd backend && pytest tests/ -v
```

```bash
node extension/tests/test_materials.js
```

See [`CODEBASE.md`](CODEBASE.md) for a file-by-file breakdown of the project.
