import json
from unittest.mock import patch, MagicMock
import chat as chat_module


def _mock_claude(text):
    part = MagicMock()
    part.text = text
    msg = MagicMock()
    msg.content = [part]
    return msg


MESSAGES = [{"role": "user", "content": "I like Rick Owens and grungy aesthetics."}]


def test_valid_response_is_returned():
    payload = {"message": "Got it — dark and deconstructed.", "pref_text": "Suggest Rick Owens-adjacent labels."}
    with patch.object(chat_module.client.messages, "create", return_value=_mock_claude(json.dumps(payload))):
        result = chat_module.chat(MESSAGES)
    assert result["message"] == "Got it — dark and deconstructed."
    assert result["pref_text"] == "Suggest Rick Owens-adjacent labels."


def test_malformed_json_returns_fallback():
    with patch.object(chat_module.client.messages, "create", return_value=_mock_claude("not json")):
        result = chat_module.chat(MESSAGES)
    assert "message" in result
    assert "pref_text" in result
    assert isinstance(result["message"], str) and len(result["message"]) > 0


def test_api_exception_returns_fallback():
    with patch.object(chat_module.client.messages, "create", side_effect=Exception("network error")):
        result = chat_module.chat(MESSAGES)
    assert "message" in result
    assert len(result["message"]) > 0


def test_pref_text_defaults_to_empty_string_when_missing():
    payload = {"message": "Tell me more.", "pref_text": ""}
    with patch.object(chat_module.client.messages, "create", return_value=_mock_claude(json.dumps(payload))):
        result = chat_module.chat(MESSAGES)
    assert result["pref_text"] == ""
