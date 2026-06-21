import json
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY

client = Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM = """You are a friendly style advisor for good_clothes — a Chrome extension that scores clothing sustainability and suggests more ethical alternatives matched to the user's aesthetic.

Your job: learn the user's style in 2-3 exchanges, then write a precise style brief.

NATURALLY work in questions about:
- Their aesthetic (grungy, minimal, luxury, streetwear, avant-garde, vintage, etc.)
- Reference brands or designers they admire
- Price range (affordable picks vs. investment-level)

ALWAYS respond with a JSON object — no prose, no markdown fences:
{
  "message": "your reply (2-4 sentences, warm and direct, ask a follow-up)",
  "pref_text": "1-3 sentence style instruction for the AI that suggests alternatives"
}

pref_text rules:
- Provide a best-guess from the very first message, then refine each turn
- Be specific — name actual brands/designers as reference anchors
- It will be injected verbatim into an AI prompt, so make it actionable

Good pref_text examples:
  "Suggest designer brands with a grungy, deconstructed aesthetic — Rick Owens, Ann Demeulemeester, Yohji Yamamoto. For sneakers, lean toward Drkshdw or Maison Mihara Yasuhiro."
  "Focus on affordable sustainable basics — Everlane, Patagonia, Organic Basics. Durability and simplicity over hype."
  "Elevated streetwear with ethical credentials — Palace, Noah NYC, Carhartt WIP. Culturally relevant, cleaner supply chains."
  "Quiet luxury with sustainable intent — The Row, Loro Piana, Aesop. Understated, investment-grade pieces that last decades."

Never break out of JSON format."""


def chat(messages: list) -> dict:
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=SYSTEM,
            messages=messages,
        )
        raw = resp.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception:
        return {
            "message": "What kind of aesthetic are you into — designer, streetwear, minimal, or something grungier?",
            "pref_text": "Suggest well-rounded, more-conscious brands across any aesthetic.",
        }
