# Progress

## Current Status
Setup complete. System is running weekly in production via GitHub Actions.

## What's Done
- [x] Full pipeline working end-to-end (scan → classify → plan → publish)
- [x] YouTube API + OAuth configured
- [x] Anthropic Batch API classification integrated
- [x] GitHub Actions scheduled job live (Sundays 6pm UTC)
- [x] SQLite library auto-committed by CI after each run
- [x] Docs written: architecture, scaling vision, infra research

## Next Steps
Nothing active — system is in maintenance/run mode.

Add tasks here when starting new work, e.g.:
- [ ] Feature: adaptive periodization (cycling build/peak/deload blocks)
- [ ] Feature: preference learning (feedback loop from workout ratings)
- [ ] Feature: natural language rescheduling via Telegram/WhatsApp bot
- [ ] Feature: web app (see `docs/scaling.md` for architecture)

## Notes
- YouTube playlist revoked access is a known limitation — documented in `docs/infra-research.md`
- BYOK (Bring Your Own Key) model chosen over hosted API to avoid per-user Anthropic costs
- Channel back-catalogue classification cost: ~$1–2 one-time; weekly incremental: cents

## Session Log
| Date | What happened |
|---|---|
| 2026-03-07 | Added CLAUDE.md and PROGRESS.md for session continuity |
