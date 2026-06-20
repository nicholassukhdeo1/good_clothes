# alternatives.py — the novel feature: "this scored low, here are better buys."
# Claude proposes more-conscious brands in the SAME category. We build the search
# URL ourselves from the brand name so the link always works (no hallucinated URLs)
# — consistent with the project's honesty rule: every clickable thing is real.

import json
from urllib.parse import quote_plus
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Coarse category from the product title — keeps cache keys stable and gives Claude
# a concrete "same kind of item" to match. Order matters (most specific first).
_CATEGORIES = [
    ("jeans", ["jean", "denim"]),
    ("t-shirt", ["t-shirt", "tee", " tshirt"]),
    ("shirt", ["shirt", "blouse"]),
    ("sweater", ["sweater", "knit", "jumper", "cardigan"]),
    ("hoodie", ["hoodie", "sweatshirt"]),
    ("jacket", ["jacket", "coat", "parka", "blazer"]),
    ("pants", ["trouser", "pant", "chino"]),
    ("dress", ["dress", "gown"]),
    ("shoes", ["sneaker", "shoe", "boot", "loafer"]),
    ("bag", ["bag", "tote", "backpack"]),
]


def infer_category(title: str) -> str:
    t = (title or "").lower()
    for name, kws in _CATEGORIES:
        if any(k in t for k in kws):
            return name
    return "clothing"


SYSTEM = """You help shoppers swap a low-scoring fashion item for more conscious options.
Given an item's category and why it scored poorly, suggest 3 REAL, well-known brands
that make that same category of item AND are meaningfully better on materials, labor
ethics, or independent ownership. Prefer brands a shopper can actually find online.
Return a SINGLE JSON object, no prose, no markdown fences:
{
  "alternatives": [
    {"name": "<real brand>", "why": "<one short reason it's a better buy>", "est_score": <int 0-100>}
  ]
}
Exactly 3 items. Each est_score must be clearly higher than the original item's score.
Do NOT invent brands or URLs — names only; the app builds the links."""


def _search_url(brand: str, category: str) -> str:
    # A real, always-working discovery link. We control this string, so it can't be a
    # hallucinated dead link — the shopper lands on a genuine search for the brand's item.
    return f"https://duckduckgo.com/?q={quote_plus(f'{brand} {category}')}"


def suggest_alternatives(brand: str, title: str, score: int, composition: str) -> dict:
    category = infer_category(title)
    user = (
        f"Original item: {brand} {category}\n"
        f"Composition: {composition or 'unknown'}\n"
        f"It scored {score}/100 on conscious-consumption (materials + ethics + ownership). "
        f"Suggest 3 better brands for this category."
    )
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=SYSTEM,
            messages=[{"role": "user", "content": user}],
        )
        raw = "".join(b.text for b in msg.content if b.type == "text").strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        items = json.loads(raw).get("alternatives", [])
    except Exception:
        items = []

    out = []
    for it in items[:3]:
        name = str(it.get("name", "")).strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "why": str(it.get("why", "")).strip(),
                "est_score": int(it.get("est_score", min(score + 25, 95))),
                "url": _search_url(name, category),
            }
        )
    return {"category": category, "alternatives": out}
