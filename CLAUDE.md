# YouTube Workout Planner — Claude Instructions

## Session Start
1. Read `PROGRESS.md` for current status and next steps
2. Run `git log --oneline -10` to see recent commits
3. Continue from where the last session left off

## Project Summary
Automated weekly YouTube workout playlist builder. Every Sunday a GitHub Actions job:
1. Scans configured YouTube channels for new videos
2. Classifies them via Claude Haiku (workout type, body focus, difficulty)
3. Picks one video per training day based on `config.yaml` schedule
4. Refreshes the YouTube playlist in day order

## Key Files
- `main.py` — entry point (`--init` / `--classify-only` / `--run` / `--dry-run`)
- `config.yaml` — channels + weekly schedule (edit to change training split)
- `workout_library.db` — SQLite database, auto-committed by CI after each run
- `src/scanner.py` — fetches videos from YouTube channels
- `src/classifier.py` — LLM classification via Anthropic Batch API
- `src/planner.py` — weekly plan generation logic
- `src/playlist.py` — YouTube playlist management (OAuth write access)
- `.github/workflows/weekly_plan.yml` — Sunday 6pm UTC scheduled job

## Documentation
- `docs/architecture.md` — pipeline components, data flow, design decisions
- `docs/scaling.md` — web app vision, target architecture, open questions
- `docs/infra-research.md` — hosting, scheduler, frontend, API decisions

## Tech Stack
- Python 3.10+, SQLite
- YouTube Data API v3 (read) + OAuth (playlist write)
- Anthropic API — Claude Haiku via Batch API for classification
- GitHub Actions for scheduling

## Conventions
- Secrets live in `.env` locally and GitHub Actions Secrets in CI — never committed
- `workout_library.db` IS committed (it's the data store)
- Use `--dry-run` to preview plans without touching the playlist
- `--init` is safe to re-run — skips already-scanned videos
