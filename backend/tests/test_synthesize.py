import json
from unittest.mock import patch, MagicMock
import synthesize


def _mock_claude(text):
    part = MagicMock()
    part.type = "text"
    part.text = text
    msg = MagicMock()
    msg.content = [part]
    return msg


EVIDENCE = {"text": "Some brand evidence text.", "sources": [{"label": "S", "url": "https://example.com"}]}


def test_valid_response_is_parsed():
    payload = {"ethics_score": 72, "ownership_score": 60, "summary": "Good supply chain.", "sources": []}
    with patch.object(synthesize.client.messages, "create", return_value=_mock_claude(json.dumps(payload))):
        result = synthesize.synthesize("Patagonia", EVIDENCE)
    assert result["ethics_score"] == 72
    assert result["ownership_score"] == 60
    assert result["summary"] == "Good supply chain."


def test_malformed_json_returns_fallback():
    with patch.object(synthesize.client.messages, "create", return_value=_mock_claude("not json at all")):
        result = synthesize.synthesize("BadBrand", EVIDENCE)
    assert result["ethics_score"] == 50
    assert result["ownership_score"] == 50
    assert "Insufficient" in result["summary"]


def test_strips_markdown_fences():
    payload = {"ethics_score": 65, "ownership_score": 80, "summary": "Ok.", "sources": []}
    wrapped = f"```json\n{json.dumps(payload)}\n```"
    with patch.object(synthesize.client.messages, "create", return_value=_mock_claude(wrapped)):
        result = synthesize.synthesize("Nike", EVIDENCE)
    assert result["ethics_score"] == 65


def test_score_coercion_from_string():
    # Claude occasionally returns scores as strings — we must cast them to int.
    payload = {"ethics_score": "72", "ownership_score": "60", "summary": "Ok.", "sources": []}
    with patch.object(synthesize.client.messages, "create", return_value=_mock_claude(json.dumps(payload))):
        result = synthesize.synthesize("Brand", EVIDENCE)
    assert isinstance(result["ethics_score"], int)
    assert result["ethics_score"] == 72


def test_api_exception_returns_fallback():
    with patch.object(synthesize.client.messages, "create", side_effect=Exception("timeout")):
        result = synthesize.synthesize("CrashBrand", EVIDENCE)
    assert result["ethics_score"] == 50
    assert result["ownership_score"] == 50
