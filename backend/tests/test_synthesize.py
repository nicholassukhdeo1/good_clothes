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


def _multi_tool_msg(*pairs):
    """One assistant turn asking for several searches at once."""
    blocks = []
    for i, (query, source) in enumerate(pairs, 1):
        block = MagicMock()
        block.type = "tool_use"
        block.id = f"toolu_{i}"
        block.name = research.TOOL["name"]
        block.input = {"query": query, "source": source}
        blocks.append(block)
    return _msg(blocks, "tool_use")


SCORE = {
    "ethics_score": 72,
    "ownership_score": 60,
    "summary": "Good supply chain.",
    "sources": [{"label": "S", "url": "https://example.com"}],
}


class FakeBrowser:
    """Stands in for EvidenceBrowser: records each batch, returns canned page text.

    `fail` fails every request; `fail_queries` fails only the ones whose query
    contains one of those substrings, the way one dead page in a concurrent batch
    comes back as an Exception beside its healthy siblings.
    """

    def __init__(self, text="Evidence about the brand.", fail=False, fail_queries=()):
        self.text = text
        self.fail = fail
        self.fail_queries = fail_queries
        self.batches = []  # one entry per search_all call
        self.queries = []  # flattened, in the order they were requested
        self.closed = False

    def search_all(self, requests):
        self.batches.append(list(requests))
        self.queries.extend(requests)
        out = []
        for query, _source in requests:
            if self.fail or any(f in query for f in self.fail_queries):
                out.append(RuntimeError("navigation timeout"))
            else:
                out.append(
                    {
                        "text": self.text,
                        "source": {
                            "label": f"Search: {query}",
                            "url": "https://example.com/evidence",
                        },
                    }
                )
        return out

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


# ---------- concurrency ----------


def test_one_turns_calls_go_out_in_a_single_batch():
    # The point of the concurrent loader: two searches asked for in one turn are
    # loaded together, not one page after another.
    browser = FakeBrowser()
    turn = _multi_tool_msg(("Everlane labor", "web"), ("Everlane owner", "wikipedia"))
    with _patch_claude(turn, _text_msg(json.dumps(SCORE))):
        synthesize.synthesize("Everlane", browser=browser)
    assert browser.batches == [
        [("Everlane labor", "web"), ("Everlane owner", "wikipedia")]
    ]


def test_every_call_in_a_turn_gets_its_own_result():
    # The API requires a tool_result per tool_use, matched by id.
    browser = FakeBrowser()
    turn = _multi_tool_msg(("Everlane labor", "web"), ("Everlane owner", "wikipedia"))
    with _patch_claude(turn, _text_msg(json.dumps(SCORE))) as create:
        synthesize.synthesize("Everlane", browser=browser)
    results = create.call_args_list[1].kwargs["messages"][2]["content"]
    assert [r["tool_use_id"] for r in results] == ["toolu_1", "toolu_2"]


def test_one_dead_page_does_not_sink_the_rest_of_the_batch():
    browser = FakeBrowser(fail_queries=("owner",))
    turn = _multi_tool_msg(("Everlane labor", "web"), ("Everlane owner", "wikipedia"))
    with _patch_claude(turn, _text_msg(json.dumps(SCORE))) as create:
        result = synthesize.synthesize("Everlane", browser=browser)

    results = create.call_args_list[1].kwargs["messages"][2]["content"]
    assert results[0].get("is_error") is None
    assert results[1]["is_error"] is True
    # The healthy page is still evidence, and still a usable source.
    assert result["ethics_score"] == 72


def test_calls_beyond_the_budget_are_refused_without_loading():
    # A turn that asks for more searches than remain: the extras get a refusal
    # result, and no page is loaded for them.
    browser = FakeBrowser()
    turn = _multi_tool_msg(*[(f"q{i}", "web") for i in range(1, 8)])
    with _patch_claude(turn, _text_msg(json.dumps(SCORE))) as create:
        synthesize.synthesize("Everlane", browser=browser)

    assert len(browser.queries) == synthesize.MAX_TOOL_CALLS
    results = create.call_args_list[1].kwargs["messages"][2]["content"]
    refusals = [r for r in results if r.get("is_error") and "budget" in r["content"]]
    assert len(refusals) == 7 - synthesize.MAX_TOOL_CALLS
    # Still one result per call, or the API rejects the turn.
    assert len([r for r in results if r["type"] == "tool_result"]) == 7


# ---------- the enforced response shape ----------


def test_schema_is_sent_on_every_request():
    # The API enforces the answer's shape, which is what stops the model narrating.
    browser = FakeBrowser()
    with _patch_claude(_tool_msg(), _text_msg(json.dumps(SCORE))) as create:
        synthesize.synthesize("Everlane", browser=browser)
    for call in create.call_args_list:
        assert call.kwargs["output_config"] == {"format": synthesize.SCORE_FORMAT}


def test_schema_requires_every_field_the_badge_reads():
    schema = synthesize.SCORE_FORMAT["schema"]
    assert sorted(schema["required"]) == ["ethics_score", "ownership_score", "sources", "summary"]
    assert schema["additionalProperties"] is False


def test_prose_before_a_fenced_block_is_still_parsed():
    # Regression: measured on Shein. The model narrated its reasoning, then emitted
    # a fenced JSON block, and the whole scored answer was thrown away for a 50/50.
    narrated = (
        "I now have sufficient evidence to score Shein. Here is my assessment:\n\n"
        "**Ethics:** Multiple investigations document 75-hour workweeks.\n\n"
        "```json\n"
        '{"ethics_score": 6, "ownership_score": 10, "summary": "Repeatedly cited for '
        '75-hour weeks and sub-living wages.", "sources": [{"label": "BBC", "url": '
        '"https://example.com/bbc"}]}\n'
        "```"
    )
    with _patch_claude(_text_msg(narrated)):
        result = synthesize.synthesize("Shein", browser=FakeBrowser())
    assert result["ethics_score"] == 6
    assert result["ownership_score"] == 10
    assert result["sources"] == [{"label": "BBC", "url": "https://example.com/bbc"}]


def test_prose_with_no_json_at_all_still_falls_back():
    with _patch_claude(_text_msg("I could not find enough to score this brand.")):
        result = synthesize.synthesize("Nowhere", browser=FakeBrowser())
    assert result["ethics_score"] == 50


# ---------- sources have to be real, clickable links ----------


def test_scheme_less_urls_are_made_absolute():
    # Measured on Allbirds: DuckDuckGo prints result URLs without a scheme, the
    # model cites them verbatim, and the badge's href then resolves against the
    # shop's own domain.
    payload = dict(SCORE, sources=[{"label": "Eco-Stylist", "url": "www.eco-stylist.com/allbirds"}])
    with _patch_claude(_text_msg(json.dumps(payload))):
        result = synthesize.synthesize("Allbirds", browser=FakeBrowser())
    assert result["sources"] == [
        {"label": "Eco-Stylist", "url": "https://www.eco-stylist.com/allbirds"}
    ]


def test_absolute_urls_are_left_alone():
    payload = dict(SCORE, sources=[{"label": "BBC", "url": "http://bbc.co.uk/x"}])
    with _patch_claude(_text_msg(json.dumps(payload))):
        result = synthesize.synthesize("Brand", browser=FakeBrowser())
    assert result["sources"][0]["url"] == "http://bbc.co.uk/x"


def test_unusable_sources_are_dropped():
    payload = dict(SCORE, sources=[{"label": "none", "url": "N/A"}, {"label": "", "url": ""}])
    with _patch_claude(_tool_msg(), _text_msg(json.dumps(payload))):
        result = synthesize.synthesize("Brand", browser=FakeBrowser())
    # Nothing citable survived, so fall back to what the tool actually loaded.
    assert result["sources"] == [
        {"label": "Search: Patagonia factory conditions", "url": "https://example.com/evidence"}
    ]
