# synthesize.py - turns browsed evidence into a structured, sourced score via Claude.
#
# Claude does the research itself: it gets the gather_brand_evidence tool
# (research.TOOL) and decides what to search for, reads the page text that comes
# back, and searches again when a result is thin or off-topic. We own the loop, the
# caps, and the browser's lifetime; the model owns the queries and the judgement.
import json
import time

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

# The API enforces this shape on the final answer, so the model cannot narrate
# first. It used to: on Shein it wrote 450 tokens of prose, then a fenced JSON
# block, and the whole scored answer was thrown away for a 50/50 fallback.
SCORE_FORMAT = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "ethics_score": {
                "type": "integer",
                "description": "0-100, worker treatment and supply-chain transparency; higher is better",
            },
            "ownership_score": {
                "type": "integer",
                "description": "0-100, independent/small is high, conglomerate or PE-owned is low",
            },
            "summary": {"type": "string", "description": "one sentence, at most 25 words"},
            "sources": {
                "type": "array",
                "description": "only URLs that appeared in a tool result",
                "items": {
                    "type": "object",
                    "properties": {
                        # The badge shows the first three labels in one 11px row,
                        # so a long label wraps and looks broken.
                        "label": {
                            "type": "string",
                            "description": "2-4 words naming the source, e.g. 'BBC investigation'",
                        },
                        "url": {"type": "string"},
                    },
                    "required": ["label", "url"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["ethics_score", "ownership_score", "summary", "sources"],
        "additionalProperties": False,
    },
}

SYSTEM = """You evaluate a clothing brand for a conscious-consumption tool.

Research the brand yourself with the gather_brand_evidence tool before you score it.
Search for its labor practices and supply-chain transparency, and separately for its
parent company or ownership. Read what each search returns; if one comes back empty
or off-topic, search again with different terms. Asking for two or three searches in
one turn is faster than asking one at a time. Stop as soon as you can justify a score.

Score ONLY from what your searches returned - do not invent facts, and only cite URLs
that appeared in a tool result.

How to score, both 0-100:
- ethics_score: worker treatment and supply-chain transparency. Higher is better.
- ownership_score: independent or small is high; a large conglomerate or private
  equity owner is low.

Keep the summary to one sentence of at most 25 words, in plain language. If the
evidence is thin or absent, score near 50, say so in the summary, and keep the
strongest sources you found."""


def _fallback(sources: list) -> dict:
    # never let a bad LLM response break the badge
    return {
        "ethics_score": 50,
        "ownership_score": 50,
        "summary": FALLBACK_SUMMARY,
        "sources": sources[:2],
    }


def _error_result(block, message: str) -> dict:
    # Hand a failure back as the tool's result instead of ending the run: the model
    # can see what broke and try different terms.
    return {
        "type": "tool_result",
        "tool_use_id": block.id,
        "content": message,
        "is_error": True,
    }


def _run_tools(browser, blocks: list, collected: list) -> list:
    """Run every gather_brand_evidence call from one turn at once.

    Claude asks for two or three searches in a single turn, so they are loaded
    concurrently rather than one page after another. Returns one tool_result per
    block, in order - the API wants a result for every call it made.
    """
    if not blocks:
        return []
    try:
        outcomes = research.gather_brand_evidence(browser, [b.input for b in blocks])
    except Exception as e:
        # The browser itself is unusable, so every pending call failed with it.
        outcomes = [e] * len(blocks)

    results = []
    for block, found in zip(blocks, outcomes):
        if isinstance(found, Exception):
            results.append(_error_result(block, f"Search failed: {found}"))
            continue
        src = found["source"]
        collected.append(src)
        results.append(
            {
                "type": "tool_result",
                "tool_use_id": block.id,
                # The URL rides along with the text because the model has to cite
                # real sources, and it can only cite what it has been shown.
                "content": f"[{src['label']}] {src['url']}\n{found['text']}",
            }
        )
    return results


def _json_object(raw: str) -> dict:
    """Parse the model's answer, tolerating a prose preamble or a fenced block.

    SCORE_FORMAT already enforces bare JSON, so this is a safety net rather than
    the normal path - but a discarded answer costs a whole research pass, so it is
    worth being forgiving here.
    """
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(raw[start : end + 1])


def _clean_sources(sources: list) -> list:
    """Make every source a real, clickable link.

    DuckDuckGo prints result URLs without a scheme ("www.example.com/x") and the
    model cites what it sees, so they arrive scheme-less. The badge drops them
    straight into href, where a scheme-less URL resolves against the shop's own
    domain and 404s - exactly the dead link this project refuses to ship.
    """
    cleaned = []
    for s in sources:
        url = str(s.get("url", "")).strip()
        label = str(s.get("label", "")).strip()
        if not url or "." not in url:
            continue
        if not url.startswith(("http://", "https://")):
            url = "https://" + url.lstrip("/")
        cleaned.append({"label": label or url, "url": url})
    return cleaned


def _parse_score(msg, collected: list) -> dict:
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    data = _json_object(raw)
    data["ethics_score"] = int(data["ethics_score"])
    data["ownership_score"] = int(data["ownership_score"])
    # ResearchResponse requires a summary, so a JSON object without one would 500
    # the endpoint rather than degrade. Fill it the way the fallback would.
    if not data.get("summary"):
        data["summary"] = FALLBACK_SUMMARY
    # Whatever the model cited, made clickable; the sources the tool actually
    # returned are the backstop when nothing usable survives.
    data["sources"] = _clean_sources(data.get("sources") or []) or collected[:2]
    return data


def _loop(brand: str, browser, collected: list) -> dict:
    messages = [
        {
            "role": "user",
            "content": f"Brand: {brand}\n\nResearch this brand with the tool, then score it.",
        }
    ]
    searches = 0
    started = time.perf_counter()

    for turn in range(1, MAX_TURNS + 1):
        spent = searches >= MAX_TOOL_CALLS
        msg = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM,
            output_config={"format": SCORE_FORMAT},
            tools=[research.TOOL],
            # Out of searches: let it answer, but stop it asking for more.
            tool_choice={"type": "none"} if spent else {"type": "auto"},
            messages=messages,
        )
        # t= is wall clock since the run started. The badge shows the user an ETA,
        # so keep the real number visible in the logs.
        print(
            f"[usage] synthesize turn={turn} searches={searches} "
            f"in={msg.usage.input_tokens} out={msg.usage.output_tokens} "
            f"t={time.perf_counter() - started:.1f}s"
        )

        # A truncated or declined turn can carry a half-written tool call, which we
        # must not execute. Treat it as a failed run and fall back.
        if msg.stop_reason in ("max_tokens", "refusal"):
            return _fallback(collected)

        calls = [b for b in msg.content if b.type == "tool_use"]
        if not calls:
            return _parse_score(msg, collected)

        messages.append({"role": "assistant", "content": msg.content})

        # Hard cap, not a hint: tool_choice "none" should already have stopped the
        # model asking, but page loads are the expensive part, so we refuse them
        # here rather than trust the model to obey.
        allowed = calls[: max(0, MAX_TOOL_CALLS - searches)]
        searches += len(allowed)
        results = _run_tools(browser, allowed, collected)
        results += [
            _error_result(b, "Search budget spent. Score from the evidence you already have.")
            for b in calls[len(allowed) :]
        ]
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
