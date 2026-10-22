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
| `TESTING.md` | What is measured, how, and the current numbers - including the prompt-injection finding and what the suite does not prove |
| `.github/workflows/ci.yml` | Two CI tiers: lint plus both unit suites plus the offline injection eval on every push, and the live model evals on a schedule |

---

## Backend (`backend/`)

These files run on Render as a FastAPI server.
The extension talks to this server — it never calls Anthropic or Browserbase directly.

| File | Purpose |
|---|---|
| `main.py` | The FastAPI app. Defines all routes: `/research`, `/alternatives`, `/chat`, `/prefs`, `/health`, and `/` (the landing page). Entry point for the server. |
| `config.py` | Loads secrets from `.env` via `python-dotenv`. Every other file imports keys from here — keys never appear anywhere else in the backend. |
| `models.py` | Pydantic request and response shapes for every endpoint. Keeps the extension and backend in sync on what fields exist. |
| `evidence.py` | How untrusted page text enters Claude's context. Encloses every page in markers carrying a per-call random nonce, so nothing in the page can close the block and speak with the harness's authority. Detectors annotate a page that tries, and never edit it. |
| `ruff.toml` | Lint baseline: pyflakes, pycodestyle, import order. Opinionated families are off on purpose - the broad excepts are deliberate, and the injection corpus needs its zero-width characters. |
| `research.py` | The Browserbase layer, exposed to Claude as a tool. `TOOL` is the schema the model calls with its own search query; `EvidenceBrowser` holds one cloud browser session per request and loads a whole turn's searches concurrently, on async Playwright driven from a private event loop so sync callers stay sync. Builds every URL itself, so the model can never point the browser somewhere we did not choose. Rejects a page with under 600 characters as a `ThinPage` rather than passing a rate-limit or stub page to Claude as evidence. |
| `synthesize.py` | Owns the agentic loop. Wraps every tool result through `evidence.wrap`, and states the trust boundary in the system prompt. Hands Claude the `gather_brand_evidence` tool and keeps executing the searches it asks for until it stops asking, capped at 5 page loads and 7 turns. `SCORE_FORMAT` makes the API enforce the shape of the final answer, so the model cannot narrate before it. Normalizes cited URLs to absolute links, since search results print them without a scheme. Falls back to 50/50, keeping whatever sources were gathered, if anything in the loop fails. |
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
| `test_research.py` | Tests the tool contract, URL building, and page loading against fake tabs: the schema is valid for strict mode, the model can only pass a query and a source, `web` builds a DuckDuckGo search URL, `wikipedia` goes through Wikipedia search, a rate-limited or stub page is rejected as a `ThinPage`, the tab is closed on every path, a turn's requests load concurrently and keep their order, and one dead page does not lose the others. |
| `test_alternatives.py` | Tests `infer_category()` (e.g. "Crewneck Sweatshirt" → "hoodie", "Chelsea Boot" → "shoes") and `pref_guidance()` (known keys return their prompts, free-form style briefs pass through unchanged, empty string falls back to "balanced"). |
| `test_synthesize.py` | Tests the tool loop and the response parser against a fake browser: the model's query reaches the browser, page text and URL are fed back as a `tool_result`, a failed search comes back as `is_error` without ending the run, the 5-search budget is a hard cap, `tool_choice` switches to `none` once it is spent, a truncated turn never runs its tool call, and the browser is always closed. Plus the answer-handling cases: prose before a fenced JSON block is still parsed (it used to cost a whole research pass), malformed JSON returns the 50/50 fallback, score strings are cast to int, a missing summary is filled, scheme-less URLs are made absolute, and API exceptions return the fallback instead of crashing. |
| `test_evidence.py` | The evidence fence: nonce freshness, redrawing on a collision with the page, containment against forged closing markers and mismatched nonces, invisible-character stripping, and every corpus case parametrized through both containment and detection. |
| `test_evidence_eval.py` | The hard corpus and the paired-delta runner: that attack and control have the same shape and comparable length, that staged pages are served in order across turns with distinct sources, that a failed half invalidates the pair instead of scoring as zero movement, and that a downward case counts a drop rather than a rise. |
| `test_evals.py` | The eval suite as code. Pure metrics, corpus invariants (unique ids, every payload actually present in its page, no detector family left without a case), the harness, the attack-success predicates, and the CI gate - including that the gate can fail, which is the only way to know it is one. |
| `test_chat.py` | Same pattern for the chat endpoint: valid responses return `{message, pref_text}`, malformed JSON and API exceptions both return a safe fallback instead of a 500 error. |

Run with:
```
cd backend && pytest tests/ -v
```

---

## Backend Evals (`backend/evals/`)

Unit tests mock the model, so they prove the loop is wired correctly and nothing about
whether the output is good.
These measure the parts that only exist at runtime.
The offline tier needs no keys and runs in CI; the live tiers need an API key and run
on a schedule or on demand.
See [`TESTING.md`](TESTING.md) for the numbers.

| File | Purpose |
|---|---|
| `corpus.py` | 30 adversarial pages across 10 attack families, plus 10 control pages with no payload. The controls exist so the detector's false-positive rate is measured rather than assumed - one is a news article about prompt injection, which is the case a naive pattern list gets wrong. |
| `harness.py` | The two renderings under test (the original f-string, kept so "before" stays measurable, and the hardened wrapper), the containment and detection metrics, a `CorpusBrowser` that serves corpus pages so the live eval is reproducible, and one attack-success predicate per attacker goal. |
| `keys.py` | Resolves the API keys an eval needs through `config.py`, never `os.environ`. config is the only module that calls `load_dotenv()`, so a key in `backend/.env` does not exist in the environment until config is imported - both runners shipped with that bug. |
| `metrics.py` | Mean, population standard deviation, spread, rate, and fallback detection. Pure functions, unit tested, so every number the suite prints comes from code that runs in CI. |
| `corpus_hard.py` | Second-generation attacks. The first corpus attacks the model's obedience; these attack its credulity, mostly with no instruction anywhere - fabricated audits, invented ownership filings, retraction notices that recontextualise real criticism, and staged pages that cross-reference each other across searches. Every case is a minimal pair with a control that differs only in the fabrication. |
| `run_evidence.py` | Runs each pair twice and measures the score delta rather than an absolute threshold, because the dangerous version of this attack is a quiet +20. Null pairs measure the noise floor, since a delta is unreadable without one. |
| `brands.py` | 30 brands spanning well-covered, mid-coverage, conglomerate-owned, and barely-covered, for the variance runs. The tier is a note about evidence availability, not an expected score. |
| `report.py` | Writes each run to `evals/results/` as dated JSON so quality is diffable over time. |
| `run_injection.py` | Offline containment and detector coverage (no keys, gates CI via `--check`), plus a live A/B that drives the real model against both renderings. |
| `run_variance.py` | Runs the real pipeline *n* times per brand and reports score spread and fallback rate. Needs Anthropic and Browserbase keys: it measures the product against the real web, which cannot be faked. |

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
