# alternatives.py — the novel feature: "this scored low, here are better buys."
# Claude proposes more-conscious brands in the SAME category. We build the search
# URL ourselves from the brand name so the link always works (no hallucinated URLs)
# — consistent with the project's honesty rule: every clickable thing is real.

import json
import base64
import urllib.request
from urllib.parse import quote_plus
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY

client = Anthropic(api_key=ANTHROPIC_API_KEY)

_OK_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def _fetch_image_b64(url: str):
    # We download the photo ourselves (with a browser UA) instead of letting Anthropic
    # fetch the URL — retail CDNs block un-credentialed server fetches, so base64 is the
    # reliable path. Returns (media_type, b64) or None on any failure.
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            media_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            data = resp.read(5_000_000)  # cap ~5MB
        if media_type not in _OK_TYPES:
            media_type = "image/jpeg"  # most retail product shots are jpeg
        return media_type, base64.standard_b64encode(data).decode("ascii")
    except Exception:
        return None

# Coarse category from the product title — keeps cache keys stable and gives Claude
# a concrete "same kind of item" to match. Order matters (most specific first).
_CATEGORIES = [
    ("jeans", ["jean", "denim"]),
    ("t-shirt", ["t-shirt", "tee", " tshirt"]),
    ("hoodie", ["hoodie", "sweatshirt"]),
    ("sweater", ["sweater", "knit", "jumper", "cardigan"]),
    ("shirt", ["shirt", "blouse"]),
    ("vest", ["vest", "gilet"]),
    ("jacket", ["jacket", "coat", "parka", "blazer", "puffer", "down"]),
    ("pants", ["trouser", "pant", "chino"]),
    ("dress", ["dress", "gown"]),
    ("shoes", ["sneaker", "shoe", "boot", "loafer"]),
    ("bag", ["bag", "tote", "backpack"]),
]


# Style lanes the user picks during onboarding. Keys MUST match extension/prefs.js.
# Each phrase is injected into the prompt to bias WHICH better brands get suggested —
# the ethics/quality bar stays; only the taste/price target shifts.
PREF_GUIDANCE = {
    "balanced": "Pick the best overall more-conscious options across any price point.",
    "avant_garde": (
        "Strongly favor avant-garde, high-fashion designer labels — the kind i-D or Vogue "
        "feature (e.g. Rick Owens, Lemaire, Yohji Yamamoto, Acne Studios) — prized for "
        "craftsmanship and longevity."
    ),
    "affordable": (
        "Strongly favor affordable, widely-available brands at mass-market price points "
        "(the kind a shopper finds easily online) that are still clearly more ethical or "
        "durable than the original item."
    ),
    "streetwear": "Strongly favor elevated, more-sustainable streetwear labels.",
    "minimal": "Strongly favor minimal, timeless labels known for durable, long-lasting basics.",
}


def pref_guidance(pref: str) -> str:
    # Old dropdown keys still work; free-form chat briefs pass straight through.
    if pref in PREF_GUIDANCE:
        return PREF_GUIDANCE[pref]
    return pref if pref else PREF_GUIDANCE["balanced"]


def infer_category(title: str) -> str:
    t = (title or "").lower()
    for name, kws in _CATEGORIES:
        if any(k in t for k in kws):
            return name
    return "clothing"


SYSTEM = """You help shoppers swap a low-scoring fashion item for more conscious options.
You are given the item's category, why it scored poorly, and (usually) a PHOTO of it.

Do two things:
1. "look": from the photo, write a short visual shopping query for the garment —
   color + silhouette + key style details (e.g. "orange quilted down puffer vest").
   3-7 words, no brand name. If no photo, base it on the category alone.
2. "alternatives": suggest 3 REAL, well-known brands that make that same category AND
   are meaningfully better on materials, labor ethics, or independent ownership.
   Prefer brands a shopper can actually find online.

Return a SINGLE JSON object, no prose, no markdown fences:
{
  "look": "<short visual query, no brand>",
  "alternatives": [
    {"name": "<real brand>", "why": "<one short reason it's a better buy>", "est_score": <int 0-100>}
  ]
}
Exactly 3 alternatives. Each est_score must be clearly higher than the original's score.
Do NOT invent brands or URLs — names only; the app builds the links."""


def _search_url(brand: str, query: str) -> str:
    # Google Shopping search for "<brand> <visual look>" — lands the shopper on specific,
    # purchasable products that resemble the original. We build the string ourselves, so
    # it can't be a hallucinated dead link; the results are real listings.
    return f"https://www.google.com/search?tbm=shop&q={quote_plus(f'{brand} {query}')}"


def suggest_alternatives(
    brand: str, title: str, score: int, composition: str, image: str = "", pref: str = "balanced"
) -> dict:
    category = infer_category(title)
    prompt = (
        f"Original item: {brand} {category}\n"
        f"Composition: {composition or 'unknown'}\n"
        f"It scored {score}/100 on conscious-consumption (materials + ethics + ownership).\n"
        f"Style preference: {pref_guidance(pref)}\n"
        f"Describe the look and suggest 3 better brands for this category that fit the preference."
    )

    # Vision when we have a photo, text-only otherwise — same call either way.
    content = []
    if image:
        fetched = _fetch_image_b64(image)
        if fetched:
            media_type, b64 = fetched
            content.append(
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}}
            )
    content.append({"type": "text", "text": prompt})

    look = ""
    items = []
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=SYSTEM,
            messages=[{"role": "user", "content": content}],
        )
        print(f"[usage] alternatives in={msg.usage.input_tokens} out={msg.usage.output_tokens}")
        raw = "".join(b.text for b in msg.content if b.type == "text").strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        look = str(data.get("look", "")).strip()
        items = data.get("alternatives", [])
    except Exception:
        pass

    # Fall back to the category if vision didn't yield a usable look query.
    query = look or category
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
                "url": _search_url(name, query),
            }
        )
    return {"category": category, "look": look, "alternatives": out}
