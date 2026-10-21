import json
from unittest.mock import MagicMock, patch

import research
import synthesize


def _msg(content, stop_reason):
    msg = MagicMock()
    msg.content = content
    msg.stop_reason = stop_reason
    msg.usage.input_tokens = 100
    msg.usage.output_tokens = 20
    return msg


def _text_msg(text, stop_reason="end_turn"):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return _msg([block], stop_reason)


def _tool_msg(query="Patagonia factory conditions", source="web", tool_id="toolu_1"):
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = research.TOOL["name"]
    block.input = {"query": query, "source": source}
    return _msg([block], "tool_use")


SCORE = {
    "ethics_score": 72,
    "ownership_score": 60,
    "summary": "Good supply chain.",
    "sources": [{"label": "S", "url": "https://example.com"}],
}


class FakeBrowser:
    """Stands in for EvidenceBrowser: records queries, returns canned page text."""

    def __init__(self, text="Evidence about the brand.", fail=False):
        self.text = text
        self.fail = fail
        self.queries = []
        self.closed = False

    def search(self, query, source):
        self.queries.append((query, source))
        if self.fail:
            raise RuntimeError("navigation timeout")
        return {
            "text": self.text,
            "source": {"label": f"Search: {query}", "url": "https://example.com/evidence"},
        }

    def close(self):
        self.closed = True


def _patch_claude(*messages):
    """Return successive mocked responses; the last one repeats if the loop runs on."""
    seq = list(messages)

    def _next(**kwargs):
        return seq.pop(0) if len(seq) > 1 else seq[0]

    return patch.object(synthesize.client.messages, "create", side_effect=_next)


# ---------- parsing the final answer ----------


def test_valid_response_is_parsed():
    with _patch_claude(_text_msg(json.dumps(SCORE))):
        result = synthesize.synthesize("Patagonia", browser=FakeBrowser())
    assert result["ethics_score"] == 72
    assert result["ownership_score"] == 60
    assert result["summary"] == "Good supply chain."


def test_malformed_json_returns_fallback():
    with _patch_claude(_text_msg("not json at all")):
        result = synthesize.synthesize("BadBrand", browser=FakeBrowser())
    assert result["ethics_score"] == 50
    assert result["ownership_score"] == 50
    assert "Insufficient" in result["summary"]


def test_strips_markdown_fences():
    wrapped = f"```json\n{json.dumps(SCORE)}\n```"
    with _patch_claude(_text_msg(wrapped)):
        result = synthesize.synthesize("Nike", browser=FakeBrowser())
    assert result["ethics_score"] == 72


def test_score_coercion_from_string():
    # Claude occasionally returns scores as strings - we must cast them to int.
    payload = dict(SCORE, ethics_score="72", ownership_score="60")
    with _patch_claude(_text_msg(json.dumps(payload))):
        result = synthesize.synthesize("Brand", browser=FakeBrowser())
    assert isinstance(result["ethics_score"], int)
    assert result["ethics_score"] == 72


def test_api_exception_returns_fallback():
    with patch.object(synthesize.client.messages, "create", side_effect=Exception("timeout")):
        result = synthesize.synthesize("CrashBrand", browser=FakeBrowser())
    assert result["ethics_score"] == 50
    assert result["ownership_score"] == 50


def test_missing_summary_is_filled():
    # Valid JSON without a summary used to reach ResearchResponse and 500 the route.
    payload = {"ethics_score": 60, "ownership_score": 40, "sources": []}
    with _patch_claude(_text_msg(json.dumps(payload))):
        result = synthesize.synthesize("Brand", browser=FakeBrowser())
    assert result["summary"] == synthesize.FALLBACK_SUMMARY


# ---------- the tool loop ----------


def test_model_query_reaches_the_browser():
    browser = FakeBrowser()
    with _patch_claude(_tool_msg("Everlane labor practices"), _text_msg(json.dumps(SCORE))):
        result = synthesize.synthesize("Everlane", browser=browser)
    assert browser.queries == [("Everlane labor practices", "web")]
    assert result["ethics_score"] == 72


def test_wikipedia_source_is_passed_through():
    browser = FakeBrowser()
    with _patch_claude(
        _tool_msg("Everlane", source="wikipedia"), _text_msg(json.dumps(SCORE))
    ):
        synthesize.synthesize("Everlane", browser=browser)
    assert browser.queries == [("Everlane", "wikipedia")]


def test_tool_result_is_fed_back_to_the_model():
    browser = FakeBrowser(text="Everlane discloses its factory list.")
    with _patch_claude(_tool_msg(tool_id="toolu_abc"), _text_msg(json.dumps(SCORE))) as create:
        synthesize.synthesize("Everlane", browser=browser)

    second_call = create.call_args_list[1].kwargs["messages"]
    assert second_call[1]["role"] == "assistant"
    result_block = second_call[2]["content"][0]
    assert second_call[2]["role"] == "user"
    assert result_block["type"] == "tool_result"
    assert result_block["tool_use_id"] == "toolu_abc"
    # The page text and the URL both have to reach the model: it scores from the
    # text and can only cite a URL it has seen.
    assert "Everlane discloses its factory list." in result_block["content"]
    assert "https://example.com/evidence" in result_block["content"]


def test_tool_is_offered_on_every_request():
    browser = FakeBrowser()
    with _patch_claude(_tool_msg(), _text_msg(json.dumps(SCORE))) as create:
        synthesize.synthesize("Everlane", browser=browser)
    for call in create.call_args_list:
        assert call.kwargs["tools"] == [research.TOOL]


def test_failed_search_is_reported_to_the_model():
    browser = FakeBrowser(fail=True)
    with _patch_claude(_tool_msg(tool_id="toolu_x"), _text_msg(json.dumps(SCORE))) as create:
        result = synthesize.synthesize("DeadSite", browser=browser)

    result_block = create.call_args_list[1].kwargs["messages"][2]["content"][0]
    assert result_block["is_error"] is True
    assert "navigation timeout" in result_block["content"]
    # A failed search is not a failed run - the model still got to score.
    assert result["ethics_score"] == 72


def test_search_budget_is_a_hard_cap():
    # A model that never stops asking must not keep loading pages.
    browser = FakeBrowser()
    with _patch_claude(_tool_msg()):
        result = synthesize.synthesize("LoopBrand", browser=browser)
    assert len(browser.queries) == synthesize.MAX_TOOL_CALLS
    assert result["ethics_score"] == 50


def test_tool_choice_is_none_once_the_budget_is_spent():
    browser = FakeBrowser()
    with _patch_claude(_tool_msg()) as create:
        synthesize.synthesize("LoopBrand", browser=browser)
    assert create.call_args_list[0].kwargs["tool_choice"] == {"type": "auto"}
    assert create.call_args_list[-1].kwargs["tool_choice"] == {"type": "none"}


def test_sources_fall_back_to_what_the_tool_returned():
    browser = FakeBrowser()
    payload = dict(SCORE, sources=[])
    with _patch_claude(_tool_msg(), _text_msg(json.dumps(payload))):
        result = synthesize.synthesize("Everlane", browser=browser)
    assert result["sources"] == [
        {"label": "Search: Patagonia factory conditions", "url": "https://example.com/evidence"}
    ]


def test_fallback_keeps_sources_gathered_before_the_crash():
    with _patch_claude(_tool_msg(), _text_msg("not json at all")):
        result = synthesize.synthesize("Everlane", browser=FakeBrowser())
    assert result["ethics_score"] == 50
    assert result["sources"] == [
        {"label": "Search: Patagonia factory conditions", "url": "https://example.com/evidence"}
    ]


def test_truncated_turn_does_not_run_its_tool_call():
    # A max_tokens turn can carry a half-written tool call. Running it is wrong.
    browser = FakeBrowser()
    truncated = _tool_msg()
    truncated.stop_reason = "max_tokens"
    with _patch_claude(truncated):
        result = synthesize.synthesize("Brand", browser=browser)
    assert browser.queries == []
    assert result["ethics_score"] == 50


# ---------- browser lifetime ----------


def test_browser_is_closed_when_synthesize_owns_it():
    browser = FakeBrowser()
    with patch.object(research, "EvidenceBrowser", return_value=browser):
        with _patch_claude(_text_msg(json.dumps(SCORE))):
            synthesize.synthesize("Patagonia")
    assert browser.closed is True


def test_browser_is_closed_after_a_crash():
    browser = FakeBrowser()
    with patch.object(research, "EvidenceBrowser", return_value=browser):
        with patch.object(synthesize.client.messages, "create", side_effect=Exception("boom")):
            synthesize.synthesize("Patagonia")
    assert browser.closed is True


def test_caller_supplied_browser_is_left_open():
    browser = FakeBrowser()
    with _patch_claude(_text_msg(json.dumps(SCORE))):
        synthesize.synthesize("Patagonia", browser=browser)
    assert browser.closed is False
