# synthesize.py — turns raw browsed evidence into a structured, sourced score via Claude.
import json
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY

client = Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM = """You evaluate a clothing brand for a conscious-consumption tool.
Use ONLY the evidence provided — do not invent facts. Return a SINGLE JSON object and
nothing else (no prose, no markdown fences), with exactly these keys:
{
  "ethics_score": <int 0-100, worker treatment & supply-chain transparency; higher=better>,
  "ownership_score": <int 0-100, independent/small=high, large conglomerate or PE-owned=low>,
  "summary": "<one sentence, plain language>",
  "sources": [{"label": "<short>", "url": "<url>"}]
}
If the evidence is thin or absent, score near 50, say so in the summary, and keep
the strongest sources you were given."""


def synthesize(brand: str, evidence: dict) -> dict:
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Brand: {brand}\n\n"
                        f"Evidence:\n{evidence['text']}\n\n"
                        f"Candidate sources:\n{json.dumps(evidence['sources'])}"
                    ),
                }
            ],
        )
        raw = "".join(b.text for b in msg.content if b.type == "text").strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        data["ethics_score"] = int(data["ethics_score"])
        data["ownership_score"] = int(data["ownership_score"])
        return data
    except Exception:
        # never let a bad LLM response break the badge
        return {
            "ethics_score": 50,
            "ownership_score": 50,
            "summary": "Insufficient data to assess confidently.",
            "sources": evidence.get("sources", [])[:2],
        }
