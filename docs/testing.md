# Testing Plan

> Written 2026-03-07. Ready to implement — see PROGRESS.md for current status.

---

## Philosophy

- Don't start the next phase until `pytest` is green on the current one
- Pure functions → unit tests (no mocks, no DB)
- DB-dependent logic → integration tests against a temp SQLite file (no production DB touched)
- External APIs (YouTube, Anthropic) → mock only, never real calls in tests

---

## Key Implementation Note — DB Isolation

`db.py` hardcodes `DB_PATH` pointing to `workout_library.db`. Tests must not touch
the production DB. Fix: patch `DB_PATH` in a pytest fixture using `monkeypatch` —
**no production code changes needed.**

```python
# tests/conftest.py
@pytest.fixture
def test_db(tmp_path, monkeypatch):
    import src.db as db_module
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()
```

Every test that touches the DB receives this fixture. Each test gets a fresh,
isolated DB in a temp directory that's deleted after the test.

---

## Existing Codebase — Test Coverage Plan

### `tests/test_db.py`
| Test | What it checks |
|---|---|
| `test_init_db_creates_tables` | All three tables exist after `init_db()` |
| `test_init_db_idempotent` | Calling `init_db()` twice doesn't error |

### `tests/test_scanner.py`
| Test | What it checks |
|---|---|
| `test_parse_duration_full` | `PT1H2M3S` → 3723 |
| `test_parse_duration_minutes_only` | `PT30M` → 1800 |
| `test_parse_duration_seconds_only` | `PT45S` → 45 |
| `test_parse_duration_hours_only` | `PT2H` → 7200 |
| `test_parse_duration_invalid` | empty / garbage string → 0 |
| `test_save_videos_inserts` | new videos are saved to DB |
| `test_save_videos_skips_duplicates` | same video ID twice → no error, count=1 |

`get_channel_info` and `_scan_uploads` require YouTube API client → mock with
`unittest.mock.MagicMock`. Test that correct API methods are called with correct args.

### `tests/test_classifier.py`
| Test | What it checks |
|---|---|
| `test_parse_classification_valid` | valid JSON → correct dict |
| `test_parse_classification_markdown_fenced` | ` ```json { } ``` ` → strips fences and parses |
| `test_parse_classification_invalid_fields` | unknown workout_type → falls back to "Other" |
| `test_parse_classification_invalid_json` | malformed JSON → returns None |
| `test_build_user_message_with_transcript` | transcript included in output |
| `test_build_user_message_without_transcript` | no transcript section when None |
| `test_build_user_message_no_duration` | duration line omitted when duration_sec is None |

`classify_unclassified_batch` requires Anthropic client → mock the client,
assert batch is created with correct request structure.

### `tests/test_planner.py`
| Test | What it checks |
|---|---|
| `test_get_upcoming_monday_is_monday` | returned date is always a Monday |
| `test_get_upcoming_monday_never_today` | if today is Monday, returns next Monday |
| `test_score_candidate_recency_boost` | recent video scores +100 vs old video |
| `test_score_candidate_channel_spread` | unused channel scores +40 vs used channel |
| `test_format_plan_summary_with_rest` | Rest days show "Rest", not video info |
| `test_format_plan_summary_with_video` | video title, type, duration appear in output |
| `test_pick_video_for_slot_basic` | returns a video matching type/focus from test DB |
| `test_pick_video_for_slot_no_candidates` | returns None when library is empty |
| `test_pick_video_for_slot_fallback_tiers` | relaxes constraints when strict query fails |
| `test_pick_video_for_slot_avoids_history` | doesn't return recently used videos |

---

## Web App Phases — "Done When" Criteria

### Phase 1 — Backend foundation
- `pytest tests/` passes green
- `GET /health` returns 200
- DB migrations run cleanly on a fresh PostgreSQL instance
- Google OAuth login flow completes (manual test in browser)
- `generate_weekly_plan()` runs against PostgreSQL test DB with fixture data

### Phase 2 — Core API
- All endpoints return correct responses against test DB (pytest + httpx)
- `POST /channels` triggers a background scan task (assert task enqueued, mock worker)
- `GET /plan/upcoming` returns a valid plan for a seeded user

### Phase 3 — Background jobs
- Celery worker processes a scan task end-to-end (local Redis + worker running)
- Weekly cron fires for a test user and produces a plan (manual trigger, short interval)
- Worker failures don't crash the queue (assert dead-letter handling)

### Phase 4 — Frontend

Full sign-in flow: see `docs/google-oauth-setup.md` for the OAuth warning and fix.
Delete checklist items as you verify them. Delete the whole section when fully ticked.

**Landing page (`/`)**
- [ ] Nav: "Workout Planner" logo left, "Sign in" link right
- [ ] Hero: headline, sub-headline, "Get started free →" CTA, "Free · No credit card" badge
- [ ] "How it works" section: 3 steps (01/02/03)
- [ ] "Why Workout Planner" section: 3 feature cards
- [ ] Bottom CTA section + footer
- [ ] Already signed-in user is silently redirected (spinner → dashboard or onboarding)
- [ ] Both CTA buttons link to Google OAuth

**Sign-in & onboarding**
- [ ] New user clicks "Get started free" → Google OAuth → `/onboarding`
- [ ] Step 1: search channels, add ≥1, Continue enabled only when ≥1 added
- [ ] Step 2: schedule grid pre-filled with defaults, can toggle rest days, save navigates to Step 3
- [ ] Step 3: "Generate my first plan now" triggers scan, redirects to `/dashboard`
- [ ] Returning user (has channels) → `/dashboard` (bypasses onboarding)
- [ ] Sign out clears session; Back button does not restore dashboard

**Dashboard**
- [ ] Header: Library | Settings | Regenerate | Publish to YouTube (disabled) | Sign out
- [ ] "Publish to YouTube" greyed out, cursor `not-allowed`, tooltip on hover
- [ ] Plan grid shows 7 days with thumbnails, duration badges, workout/body/difficulty badges
- [ ] "Regenerate" triggers a new plan and updates the grid in place
- [ ] Library and Settings links navigate correctly

**Library page (`/library`)**
- [ ] "← Back" returns to `/dashboard`
- [ ] Video count shown top-right
- [ ] Cards: thumbnail, duration badge (bottom-right of image), title (2-line clamp), channel name, badges
- [ ] Clicking a card opens YouTube in a new tab
- [ ] Workout type dropdown: Strength / HIIT / Cardio / Mobility (not "Hiit")
- [ ] Each filter narrows the grid and updates the total count
- [ ] Combined filters apply as AND
- [ ] "Clear filters" resets all dropdowns and restores full library
- [ ] Channel dropdown hidden when user has only 1 channel
- [ ] "Assign to day" select → shows "✓ Assigned to Mon" for 2s, then resets
- [ ] Assign when no plan exists → "Failed — generate a plan first"
- [ ] After assigning, dashboard shows the newly assigned video on that day
- [ ] Pagination: Previous disabled on page 1, Next on last page, no overlapping videos across pages
- [ ] Applying a filter while on page >1 resets to page 1

**Settings page (`/settings`)**
- [ ] "← Dashboard" link returns to `/dashboard`
- [ ] Profile: display name editable, "Save" disabled when name unchanged, shows "Display name updated" on save
- [ ] Profile: email shown as read-only
- [ ] Channels: can search and add new channels, can remove existing ones
- [ ] Schedule: edit any day's workout type/body focus/difficulty/duration, toggle rest days
- [ ] Schedule: "Save schedule" shows "Schedule saved." confirmation
- [ ] Danger zone: "Delete my account" button appears with red border
- [ ] Danger zone: clicking shows confirmation ("Are you sure?") with Yes/Cancel buttons
- [ ] Danger zone: confirming deletes everything and redirects to `/` (landing page)
- [ ] Danger zone: cancelling dismisses the confirmation without any action

**API sanity (Swagger at /docs)**
- [ ] `PATCH /auth/me` with `{"display_name": "Test"}` → 200 with updated name
- [ ] `DELETE /auth/me` → 204, subsequent `GET /auth/me` → 401
- [ ] `GET /library?workout_type=HIIT` and `?workout_type=hiit` → same results (case-insensitive)
- [ ] `GET /library?page=0` → 422; `GET /library?limit=101` → 422
- [ ] Unauthenticated `GET /library` or `PATCH /auth/me` → 401

**Mobile (resize browser to ~390px wide)**
- [ ] Landing page: single column, CTA button full-width
- [ ] Dashboard grid: 2 columns
- [ ] Library grid: 2 columns, filter bar wraps without overflow
- [ ] Settings: sections stack vertically, no horizontal overflow

### Phase 5 — Playlist publishing
- Server-side OAuth flow completes without terminal copy-paste (manual test)
- On simulated 401, user credentials marked invalid and run skipped gracefully
- End-to-end: trigger full run → YouTube playlist updated (manual test, real API)

---

## Test Dependencies to Add to `requirements.txt`

```
pytest
pytest-asyncio      # for async FastAPI routes in Phase 2+
httpx               # FastAPI test client
```
