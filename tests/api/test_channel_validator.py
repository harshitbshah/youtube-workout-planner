"""
Unit tests for api/services/channel_validator.py

All Anthropic API calls are mocked — no real network calls.
"""

from unittest.mock import MagicMock, patch

import pytest

from api.services.channel_validator import validate_channel_fitness


def _make_claude_response(text: str) -> MagicMock:
    """Build a minimal mock that looks like an Anthropic message response."""
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


# ─── Happy path ───────────────────────────────────────────────────────────────

def test_yes_response_allows_channel():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_claude_response("yes")

    with patch("api.services.channel_validator.anthropic.Anthropic", return_value=mock_client), \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        ok, label = validate_channel_fitness("Athlean-X", "Strength training workouts", "adult", "Build muscle")

    assert ok is True
    assert label is None


def test_no_response_blocks_channel_with_label():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_claude_response("no: cooking recipes")

    with patch("api.services.channel_validator.anthropic.Anthropic", return_value=mock_client), \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        ok, label = validate_channel_fitness("Gordon Ramsay", "Cooking and recipes", "adult", "Build muscle")

    assert ok is False
    assert label == "cooking recipes"


def test_no_response_without_label_uses_fallback():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_claude_response("no:")

    with patch("api.services.channel_validator.anthropic.Anthropic", return_value=mock_client), \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        ok, label = validate_channel_fitness("Mystery Channel", "", "adult", "Build muscle")

    assert ok is False
    assert label == "unrelated content"


# ─── Fail open cases ──────────────────────────────────────────────────────────

def test_unsure_response_fails_open():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_claude_response("unsure")

    with patch("api.services.channel_validator.anthropic.Anthropic", return_value=mock_client), \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        ok, label = validate_channel_fitness("Vague Channel", "", "adult", "Build muscle")

    assert ok is True
    assert label is None


def test_unexpected_response_fails_open():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_claude_response("maybe")

    with patch("api.services.channel_validator.anthropic.Anthropic", return_value=mock_client), \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        ok, label = validate_channel_fitness("Some Channel", "", "adult", "Build muscle")

    assert ok is True
    assert label is None


def test_anthropic_exception_fails_open():
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("network error")

    with patch("api.services.channel_validator.anthropic.Anthropic", return_value=mock_client), \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        ok, label = validate_channel_fitness("Some Channel", "Some desc", "adult", "Build muscle")

    assert ok is True
    assert label is None


def test_no_api_key_fails_open():
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
        ok, label = validate_channel_fitness("Some Channel", "Some desc", "adult", "Build muscle")

    assert ok is True
    assert label is None


# ─── Response text variations ─────────────────────────────────────────────────

def test_yes_with_trailing_text_still_passes():
    """Claude might say 'yes, this is a fitness channel' — still counts as yes."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_claude_response("yes, definitely fitness")

    with patch("api.services.channel_validator.anthropic.Anthropic", return_value=mock_client), \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        ok, label = validate_channel_fitness("Athlean-X", "Workouts", "adult", "Build muscle")

    assert ok is True


def test_no_response_is_case_insensitive():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_claude_response("No: Video Games")

    with patch("api.services.channel_validator.anthropic.Anthropic", return_value=mock_client), \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        ok, label = validate_channel_fitness("Gaming Channel", "", "adult", "Build muscle")

    assert ok is False
    assert label == "video games"
