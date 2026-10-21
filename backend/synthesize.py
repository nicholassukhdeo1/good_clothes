# synthesize.py - turns browsed evidence into a structured, sourced score via Claude.
#
# Claude does the research itself: it gets the gather_brand_evidence tool
# (research.TOOL) and decides what to search for, reads the page text that comes
# back, and searches again when a result is thin or off-topic. We own the loop, the
# caps, and the browser's lifetime; the model owns the queries and the judgement.
import json
from anthropic import Anthropic

import research
from config import ANTHROPIC_API_KEY

client = Anthropic(api_key=ANTHROPIC_API_KEY)

MODEL = "claude-sonnet-4-6"

# A badge is waiting on this call and every search is a real page load, so the loop
# stops at whichever cap it hits first. Two spare turns: enough to spend the whole
# search budget and still have a turn left to write the score.
MAX_TOOL_CALLS = 5
MAX_TURNS = MAX_TOOL_CALLS + 2

FALLBACK_SUMMARY = "Insufficient data to assess confidently."

SYSTEM = """You evaluate a clothing brand for a conscious-consumption tool.

Research the brand yourself with the gather_brand_evidence tool before you score it.
Search for its labor practices and supply-chain transparency, and separately for its
parent company or ownership. Read what each search returns; if one comes back empty
or off-topic, search again with different terms. Stop as soon as you can justify a
score - two or three searches is usually enough.

Score ONLY from what your searches returned - do not invent facts, and only cite URLs
that appeared in a tool result.

When you are done, reply with a SINGLE JSON object and nothing else (no prose, no
markdown fences), with exactly these keys:
{
  "ethics_score": <int 0-100, worker treatment & supply-chain transparency; higher=better>,
  "ownership_score": <int 0-100, independent/small=high, large conglomerate or PE-owned=low>,
  "summary": "<one sentence, at most 25 words, plain language>",
  "sources": [{"label": "<short>", "url": "<url>"}]
}
If the evidence is thin or absent, score near 50, say so in the summary, and keep
the strongest sources you found."""


def _fallback(sources: list) -> dict:
    # never let a bad LLM response break the badge
    return {
        "ethics_score": 50,
        "ownership_score": 50,
        "summary": FALLBACK_SUMMARY,
        "sources": sources[:2],
    }


def _run_tool(browser, block, collected: list) -> dict:
    """Execute one gather_brand_evidence call, shaped as a tool_result block."""
    try:
        found = research.gather_brand_evidence(
            browser,
            query=str(block.input.get("query", "")),
            source=str(block.input.get("source", "web")),
        )
    except Exception as e:
        # Hand the failure back as the tool's result instead of ending the run: the
        # model can see what broke and try different terms.
        return {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": f"Search failed: {e}",
            "is_error": True,
        }

    src = found["source"]
    collected.append(src)
    return {
        "type": "tool_result",
        "tool_use_id": block.id,
        # The URL rides along with the text because the model has to cite real
        # sources, and it can only cite what it has actually been shown.
        "content": f"[{src['label']}] {src['url']}\n{found['text']}",
    }


def _parse_score(msg, collected: list) -> dict:
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    data = json.loads(raw)
    data["ethics_score"] = int(data["ethics_score"])
    data["ownership_score"] = int(data["ownership_score"])
    # ResearchResponse requires a summary, so a JSON object without one would 500
    # the endpoint rather than degrade. Fill it the way the fallback would.
    if not data.get("summary"):
        data["summary"] = FALLBACK_SUMMARY
    if not data.get("sources"):
        data["sources"] = collected[:2]
    return data


def _loop(brand: str, browser, collected: list) -> dict:
    messages = [
        {
            "role": "user",
            "content": f"Brand: {brand}\n\nResearch this brand with the tool, then score it.",
        }
    ]
    searches = 0

    for turn in range(1, MAX_TURNS + 1):
        spent = searches >= MAX_TOOL_CALLS
        msg = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM,
            tools=[research.TOOL],
            # Out of searches: let it answer, but stop it asking for more.
            tool_choice={"type": "none"} if spent else {"type": "auto"},
            messages=messages,
        )
        print(
            f"[usage] synthesize turn={turn} searches={searches} "
            f"in={msg.usage.input_tokens} out={msg.usage.output_tokens}"
        )

        # A truncated or declined turn can carry a half-written tool call, which we
        # must not execute. Treat it as a failed run and fall back.
        if msg.stop_reason in ("max_tokens", "refusal"):
            return _fallback(collected)

        calls = [b for b in msg.content if b.type == "tool_use"]
        if not calls:
            return _parse_score(msg, collected)

        messages.append({"role": "assistant", "content": msg.content})
        results = []
        for block in calls:
            # Hard cap, not a hint: tool_choice "none" should already have stopped
            # the model asking, but page loads are the expensive part, so we refuse
            # them here rather than trust the model to obey. Every tool_use block
            # still gets a tool_result - the API requires one.
            if searches >= MAX_TOOL_CALLS:
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Search budget spent. Score from the evidence you already have.",
                        "is_error": True,
                    }
                )
                continue
            searches += 1
            results.append(_run_tool(browser, block, collected))
        if searches >= MAX_TOOL_CALLS:
            # tool_result blocks first, then the instruction - the API wants them
            # at the head of the message.
            results.append(
                {
                    "type": "text",
                    "text": "Search budget spent. Score the brand now from the evidence above.",
                }
            )
        messages.append({"role": "user", "content": results})

    # Still asking for tools at the turn cap. Degrade rather than keep looping.
    return _fallback(collected)


def synthesize(brand: str, browser=None) -> dict:
    """Research `brand` with Claude driving the browser, then return its score.

    Pass a `browser` to supply your own session (the tests pass a fake); otherwise
    one is opened on the first search and closed before this returns.
    """
    own_browser = browser is None
    if own_browser:
        browser = research.EvidenceBrowser()

    collected = []  # every source a tool call actually returned, for the fallback
    try:
        return _loop(brand, browser, collected)
    except Exception:
        return _fallback(collected)
    finally:
        if own_browser:
            browser.close()
