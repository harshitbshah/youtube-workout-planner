from src.classifier import _build_user_message, _parse_classification


# ─── _parse_classification ────────────────────────────────────────────────────

def test_parse_classification_valid():
    raw = (
        '{"workout_type": "HIIT", "body_focus": "full", "difficulty": "intermediate",'
        ' "has_warmup": true, "has_cooldown": false}'
    )
    result = _parse_classification(raw)
    assert result == {
        "workout_type": "HIIT",
        "body_focus": "full",
        "difficulty": "intermediate",
        "has_warmup": 1,
        "has_cooldown": 0,
    }


def test_parse_classification_markdown_fenced():
    raw = (
        "```json\n"
        '{"workout_type": "Strength", "body_focus": "upper", "difficulty": "beginner",'
        ' "has_warmup": false, "has_cooldown": true}\n'
        "```"
    )
    result = _parse_classification(raw)
    assert result["workout_type"] == "Strength"
    assert result["body_focus"] == "upper"
    assert result["has_cooldown"] == 1


def test_parse_classification_invalid_fields():
    # Unknown enum values fall back to defaults
    raw = (
        '{"workout_type": "Dance", "body_focus": "torso", "difficulty": "mega-hard",'
        ' "has_warmup": true, "has_cooldown": false}'
    )
    result = _parse_classification(raw)
    assert result["workout_type"] == "Other"
    assert result["body_focus"] == "any"
    assert result["difficulty"] == "intermediate"


def test_parse_classification_invalid_json():
    result = _parse_classification("not json at all {{{")
    assert result is None


# ─── _build_user_message ──────────────────────────────────────────────────────

def _video(**kwargs):
    defaults = {
        "title": "30 Min HIIT Workout",
        "duration_sec": 1800,
        "tags": "hiit,cardio",
        "description": "Full body workout",
    }
    defaults.update(kwargs)
    return defaults


def test_build_user_message_with_transcript():
    msg = _build_user_message(_video(), "Welcome everyone, today we're doing HIIT")
    assert "Transcript intro" in msg
    assert "Welcome everyone" in msg


def test_build_user_message_without_transcript():
    msg = _build_user_message(_video(), None)
    assert "Transcript intro" not in msg
    assert "30 Min HIIT Workout" in msg


def test_build_user_message_no_duration():
    msg = _build_user_message(_video(duration_sec=None), None)
    assert "Duration:" not in msg
    assert "30 Min HIIT Workout" in msg
