# CLI Consolidation Plan

## Problem
The repo has two separate codebases doing the same thing:

- `src/` - original CLI code. Simple, no optimizations.
- `api/services/` - web app code. Has all the improvements:
  - **Scanner**: title keyword blocklist, livestream filter, duration cap (>2hrs),
    75-video first-scan cap per channel, skip inactive channels, 18-month cutoff
  - **Classifier**: lazy classification, rule-based pre-classifier (`title_classify()`),
    targeted mini-batches (`build_targeted_batch()`), `can_fill_plan()`, gap detection
  - **Planner**: full tier fallback logic, gap detection

`main.py` (CLI entry point) currently uses `src/` so it misses all of these optimizations.
The web app uses `api/services/` which has everything.

## Goal
Consolidate into one codebase: make `main.py` use `api/services/` directly,
then delete `src/`. All optimizations available to both CLI and web app automatically.

## The Problem with Consolidation
`api/services/` assumes SQLAlchemy + PostgreSQL. The CLI uses raw SQLite (`src/db.py`).
The services receive a SQLAlchemy `Session` object and use ORM models
(`Video`, `Classification`, `Channel`, `Schedule`, `ProgramHistory`, etc.).

## Approach

### Option A - SQLite SQLAlchemy session (recommended)
Configure SQLAlchemy to connect to the SQLite file instead of PostgreSQL.
SQLAlchemy supports both - just swap the connection string.
The ORM models and services work unchanged.

CLI sets up a SQLAlchemy engine pointing at `workout_library.db`:
```python
engine = create_engine("sqlite:///workout_library.db")
Session = sessionmaker(bind=engine)
```

Then passes a `Session` instance to `api/services/scanner.py`, `classifier.py`,
`planner.py`, `publisher.py` exactly as the web app does.

The ORM models (`api/models.py`) define the schema - SQLAlchemy creates the
SQLite tables automatically on first run (replacing `src/db.py`'s `init_db()`).

### Option B - Refactor services to be DB-agnostic
Abstract the DB calls behind a repository interface. More work, not worth it.

## Steps (Option A)

1. **Verify schema compatibility**
   - `api/models.py` has more columns than `src/db.py` (web app added profile,
     credentials, schedule, etc.)
   - CLI only needs: `Video`, `Classification`, `ProgramHistory`, `Channel`
   - The extra models (`User`, `UserCredentials`, `Schedule`, etc.) can just be
     created as empty tables - they won't be used by the CLI

2. **Update `main.py`**
   - Replace `from src.db import init_db` with SQLAlchemy engine setup
   - Replace `from src.scanner import ...` with `from api.services.scanner import ...`
   - Replace `from src.classifier import ...` with `from api.services.classifier import ...`
   - Replace `from src.planner import ...` with `from api.services.planner import ...`
   - Replace `from src.playlist import ...` with `from api.services.publisher import ...`
   - Pass SQLAlchemy session to each service call

3. **Handle user_id**
   - `api/services/` functions are multi-tenant - they take `user_id` as a parameter
   - For the CLI, create a single "local" user row in the `users` table
   - Use a fixed `user_id` (e.g. the local user's row ID) for all CLI operations

4. **Handle channel model differences**
   - `src/` channels come from `config.yaml` list
   - `api/models.py` has a `Channel` ORM model + `UserChannel` join table
   - On CLI init/run: sync `config.yaml` channels into the `channels` + `user_channels` tables

5. **Wire the scanner**
   - `api/services/scanner.py` takes `(session, channel)` where `channel` is an ORM object
   - Replace the raw YouTube client calls in `main.py` with `api/services/scanner.py`

6. **Wire the classifier**
   - `api/services/classifier.py` has `rule_classify_for_user()`, `can_fill_plan()`,
     `classify_for_user()`, `build_targeted_batch()` - all take `(session, user_id)`
   - Replace `src/classifier.py` calls with these

7. **Wire the planner**
   - `api/services/planner.py` has `generate_weekly_plan_for_user(session, user_id)`
   - Replace `src/planner.py` calls

8. **Wire the publisher**
   - `api/services/publisher.py` has `publish_plan_for_user(session, user_id, week_start)`
   - Replace `src/playlist.py` calls

9. **Delete `src/`** once all references are migrated and tests pass

## Key Files to Understand Before Starting
- `main.py` - current CLI entry point, 236 lines
- `src/db.py` - SQLite schema (3 tables: videos, classifications, program_history)
- `src/scanner.py` - raw YouTube scanning
- `src/classifier.py` - batch classification
- `src/planner.py` - plan generation
- `src/playlist.py` - YouTube playlist management
- `api/models.py` - SQLAlchemy ORM models (full schema)
- `api/services/scanner.py` - optimized scanner
- `api/services/classifier.py` - lazy classification + rule-based pre-classifier
- `api/services/planner.py` - plan generation with gap detection
- `api/services/publisher.py` - YouTube publisher

## Tests
- `tests/test_*.py` - CLI unit tests (test_scanner, test_classifier, test_planner, test_db)
  These will need updating as `src/` is replaced
- `tests/api/` - web app unit tests - should continue passing unchanged
- Run after each step: `.venv/bin/pytest tests/ -q`

## Current Status
- CLI `--init` is running on GitHub Actions right now using the old `src/` code
- It will complete successfully but without the optimizations
- Consolidation can be done as a separate PR after the current run finishes
