"""
channel_validator.py - Validate a YouTube channel fits the user's fitness profile.

Uses claude-haiku-4-5-20251001 for a lightweight classification.
Always fails open: unexpected results or errors allow the channel through.
"""

import logging
import os

import anthropic

logger = logging.getLogger(__name__)


def validate_channel_fitness(
    channel_name: str,
    channel_description: str,
    profile: str,
    goal: str,
) -> tuple[bool, str | None]:
    """
    Check whether a channel suits the user's fitness profile and goal.

    Returns:
        (True, None)       - channel is suitable, allow through
        (False, "label")   - channel doesn't fit; label is what it actually is
        (True, None)       - on any error, unsure, or missing API key, fail open
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("[channel_validator] ANTHROPIC_API_KEY not set - skipping validation")
        return True, None

    prompt = (
        "You are validating whether a YouTube channel suits a user's fitness plan.\n\n"
        f"User profile: {profile}\n"
        f"User goal: {goal}\n\n"
        f"Channel name: {channel_name}\n"
        f"Channel description: {channel_description}\n\n"
        "Does this channel contain fitness or workout content that suits this user?\n"
        "Reply with ONLY one of:\n"
        '- "yes"\n'
        '- "no: <3-word label of what the channel actually is>"\n'
        '- "unsure"\n\n'
        'Examples of valid replies: "yes", "no: cooking recipes", "no: video games", "unsure"'
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip().lower()

        if text.startswith("yes"):
            return True, None
        elif text.startswith("no:"):
            label = text[3:].strip()
            return False, label if label else "unrelated content"
        else:
            # "unsure" or anything unexpected - fail open
            return True, None

    except Exception as e:
        logger.warning(f"[channel_validator] Claude call failed - failing open: {e}")
        return True, None
