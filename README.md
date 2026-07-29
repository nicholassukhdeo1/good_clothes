# good_clothes

A Chrome extension that scores how worthy a clothing item is to buy (0–100), combining
**materials** (read off the page, deterministic), **ethics**, and **ownership** (researched
live via a Browserbase cloud browser, scored by Claude).

```
materials  (local, instant, always works)
   +  ethics + ownership  (Browserbase → Claude, cached per brand)
   =  worthiness score
```


## Run it

Backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then paste your real keys into .env
uvicorn main:app --reload   # http://localhost:8000
```
(You connect to Browserbase's remote browser over CDP, so you do NOT need a local
`playwright install` for chromium.)

Extension:
1. `chrome://extensions` → enable Developer mode → **Load unpacked** → pick `extension/`.
2. Open a product page on your supported retailer. Badge appears bottom-right.

---

## Demo safety

- **Pre-warm the cache for your demo brand** so the live demo is instant and never depends
  on Browserbase behaving on stage:
  ```bash
  curl -X POST localhost:8000/research \
    -H "Content-Type: application/json" -d '{"brand":"Uniqlo"}'
  ```
  Run it once; the result is cached in `cache.db`. On stage you hit cache.
- Materials scoring is local, so the badge shows a real score even with the backend off —
  that's your guaranteed fallback demo.

---

## Where to spend your hand-written effort

Let Claude Code generate boilerplate. Your judgment goes into:
- `extension/materials.js` — the fiber rubric (be ready to defend it).
- `backend/synthesize.py` — the Claude prompt + JSON schema.
- `backend/research.py` — which sources you browse (DuckDuckGo + Wikipedia are stubbed;
  a brand's Good On You page is a strong add).
- The demo: pick one product that scores LOW and one that scores HIGH for contrast.

## Build order (matches your schedule)
- **Block 1:** badge → background → backend → fake score. Kill CORS/manifest issues here.
- **Block 2:** real DOM scrape + materials score. This alone is a complete submission.
- **Block 3:** Browserbase research + Claude synthesis (the big swing).
- **11pm:** dry run, `git tag` the working version as your fallback.
- **Block 4:** sources display, summary, polish. Stretch: "here are 3 better-scoring alternatives."

## Stretch (true "beyond a prompt" depth)
Write each brand assessment back as long-term memory and retrieve similar brands — turns
the tool into something that gets smarter the more you browse.

## Architecture note
The extension does materials + the final combine; the backend does ONLY brand research.
This split means each layer is independently demoable and a Browserbase failure never
takes down the visible score.
