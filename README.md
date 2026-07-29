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

## Where to spend your hand-written effort

Let Claude Code generate boilerplate. Your judgment goes into:
- `extension/materials.js` — the fiber rubric (be ready to defend it).
- `backend/synthesize.py` — the Claude prompt + JSON schema.
- `backend/research.py` — which sources you browse (DuckDuckGo + Wikipedia are stubbed;
  a brand's Good On You page is a strong add).
- The demo: pick one product that scores LOW and one that scores HIGH for contrast.


## Stretch (true "beyond a prompt" depth)
Write each brand assessment back as long-term memory and retrieve similar brands — turns
the tool into something that gets smarter the more you browse.

## Architecture note
The extension does materials + the final combine; the backend does ONLY brand research.
This split means each layer is independently demoable and a Browserbase failure never
takes down the visible score.
