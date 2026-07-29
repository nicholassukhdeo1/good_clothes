# Codebase Map

A file-by-file rundown of what everything does and why it exists.

---

## Root

| File | Purpose |
|---|---|
| `README.md` | Setup instructions, how to run the backend and load the extension |
| `render.yaml` | Render deployment config — tells Render how to build and start the backend, and that secrets come from the dashboard (not this file) |
| `deck.html` | Standalone copy of the pitch deck for local use |
| `.gitignore` | Keeps `backend/.env`, `__pycache__`, `*.db`, and `venv/` out of git |

---

## Backend (`backend/`)

These files run on Render as a FastAPI server.
The extension talks to this server — it never calls Anthropic or Browserbase directly.

| File | Purpose |
|---|---|
| `main.py` | The FastAPI app. Defines all routes: `/research`, `/alternatives`, `/chat`, `/prefs`, `/health`, and `/` (the landing page). Entry point for the server. |
| `config.py` | Loads secrets from `.env` via `python-dotenv`. Every other file imports keys from here — keys never appear anywhere else in the backend. |
| `models.py` | Pydantic request and response shapes for every endpoint. Keeps the extension and backend in sync on what fields exist. |
| `research.py` | The Browserbase layer. Opens a cloud browser session, visits DuckDuckGo and Wikipedia to gather raw evidence about a brand, and returns the scraped text. Uses a real browser because modern sites block naive HTTP scrapers. |
| `synthesize.py` | Takes the raw evidence from `research.py` and sends it to Claude. Claude returns a structured JSON score (ethics, ownership, summary, sources). Includes a fallback to 50/50 if Claude returns anything unparseable. |
| `alternatives.py` | Given a low-scoring item, uses Claude vision to read the product photo and suggest 3 alternative brands that are more ethical and match the user's style. Builds Google Shopping links server-side so no URL is ever hallucinated. |
| `chat.py` | Powers the style onboarding chat. Sends conversation history to Claude Haiku and gets back a `{message, pref_text}` JSON response. The `pref_text` is what eventually biases alternative brand suggestions. |
| `cache.py` | A dead-simple SQLite cache keyed by brand name. Brand research is slow and expensive, so results are cached indefinitely. The cache is shared across all three main endpoints. |
| `db.py` | A thin Supabase layer for persisting user style preferences. If `SUPABASE_URL`/`SUPABASE_KEY` aren't set, every call is a safe no-op — the app keeps working, preferences just don't survive a browser refresh. |
| `landing.html` | The interactive slide deck served at the root URL (`good-clothes-backend.onrender.com`). Eight slides covering the problem, solution, demo, and tech stack. |
| `requirements.txt` | Python dependencies. `pytest` is in here so tests run with the same install step as the server. |
| `pytest.ini` | Tells pytest where to find tests (`tests/` subdirectory) and adds the `backend/` directory to the Python path so test files can import `cache`, `synthesize`, etc. directly. |
| `.env.example` | Template showing which environment variables are needed. The real `.env` is gitignored — this file is safe to commit. |

---

## Backend Tests (`backend/tests/`)

These test the core logic in isolation.
No API keys needed, no network calls — all external calls are mocked.

| File | Purpose |
|---|---|
| `conftest.py` | Sets dummy environment variables before any test imports happen. Prevents the Anthropic and Browserbase clients from erroring on initialization when real keys aren't present. |
| `test_cache.py` | Tests the SQLite cache: missing keys return `None`, put/get round-trips correctly, brand keys are case-insensitive, overwriting works. Each test gets its own temporary SQLite file so tests never share state. |
| `test_alternatives.py` | Tests `infer_category()` (e.g. "Crewneck Sweatshirt" → "hoodie", "Chelsea Boot" → "shoes") and `pref_guidance()` (known keys return their prompts, free-form style briefs pass through unchanged, empty string falls back to "balanced"). |
| `test_synthesize.py` | Tests the Claude response parser: valid JSON is parsed correctly, malformed JSON returns the 50/50 fallback, markdown fences are stripped, score strings are cast to int, and API exceptions return the fallback instead of crashing. |
| `test_chat.py` | Same pattern for the chat endpoint: valid responses return `{message, pref_text}`, malformed JSON and API exceptions both return a safe fallback instead of a 500 error. |

Run with:
```
cd backend && pytest tests/ -v
```

---

## Extension (`extension/`)

These files are what gets loaded into Chrome.
The extension never holds API keys — it talks to the backend for everything that requires one.

| File | Purpose |
|---|---|
| `manifest.json` | Chrome extension config. Declares permissions (`storage`, `activeTab`, `webNavigation`), which URLs the content script runs on (`*.ssense.com/*`), and which file is the service worker. |
| `background.js` | The MV3 service worker. Relays network requests from the content script to the backend (the content script can't call the backend directly due to CORS + page CSP). Also detects SPA navigation on SSENSE via `chrome.webNavigation` and tells the content script when to re-run. |
| `content.js` | The main badge. Scrapes the product page (brand, composition, image, title), scores materials locally, calls the backend for brand research and alternatives, and renders the badge UI into the page. Also handles the minimize button and Read More toggle. |
| `content.css` | All badge styles. Uses the Archivo + Newsreader font pairing, a green accent palette, and a sticky score ring so the number stays visible when the badge scrolls. |
| `materials.js` | Deterministic materials scoring — runs entirely in the browser with no network call. Parses fabric compositions from percentage notation (`80% Cotton, 20% Polyester`), labelled multi-part descriptions (`Upper: Calfskin. Sole: Rubber.`), and bare keyword matches (`Sterling Silver`). Returns a 0-100 score weighted by fiber sustainability. |
| `prefs.js` | Shared constants loaded by every extension page. Holds the backend URL, the anonymous user ID generator (`GC_getUid`), and the legacy dropdown labels (still used by `popup.js` for display). |
| `popup.html` | The HTML shell for the toolbar popup (the small window that opens when you click the extension icon). |
| `popup.js` | Reads the last scored item from `chrome.storage.local` and renders a compact summary — score ring, metric bars, and alternatives list. Also shows the current style lane with a "Change" link. |
| `onboarding.html` | The style setup page. Opens automatically on first install, or when the user clicks "Change style" in the popup. Chat bubble layout: assistant on the left, user on the right. |
| `onboarding.js` | Drives the onboarding chat. Maintains conversation history, sends it to `/chat` on the backend, renders responses as bubbles, and shows the generated style brief in a preview panel. On save, writes `pref_text` to `chrome.storage.sync` and to Supabase. |

---

## Extension Tests (`extension/tests/`)

| File | Purpose |
|---|---|
| `test_materials.js` | Tests the materials scoring logic from `materials.js`. Covers percentage-based compositions, alias normalization (lambskin → leather, 925 sterling → sterling silver), bare keyword matches, labelled multi-part inputs, and empty/unrecognized inputs. Uses only Node.js built-ins — no npm install required. |

Run with:
```
node extension/tests/test_materials.js
```
