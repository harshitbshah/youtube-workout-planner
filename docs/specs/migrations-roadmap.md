# Migrations Roadmap

Canonical list of all database migrations — live and planned — in sequence.
Update this file whenever a new migration is added or a spec claims a migration number.

**Live DB:** migrations 001–008 (Railway, as of 2026-03-13)

---

## Live migrations (deployed)

| # | File | Adds | Phase |
|---|------|------|-------|
| 001 | `001_initial_schema.py` | `users`, `channels`, `videos`, `classifications`, `schedules`, `program_history`, `user_credentials` | Phase 1–3 |
| 002 | `002_add_credentials_valid.py` | `user_credentials.credentials_valid`, `user_credentials.youtube_playlist_id` | Phase 5 |
| 003 | `003_add_classifier_batch_id.py` | `user_credentials.classifier_batch_id` | Pipeline reliability |
| 004 | `004_add_last_active_batch_log_announcements.py` | `users.last_active_at`, `batch_usage_log`, `announcements` | Admin console |
| 005 | `005_add_scan_log_user_activity_log.py` | `scan_log`, `user_activity_log` | Admin charts |
| 006 | `006_add_channel_first_scan_done.py` | `channels.first_scan_done` | Phase A — F3 |
| 007 | `007_add_channel_last_video_published_at.py` | `channels.last_video_published_at` | Phase A — F4 |
| 008 | `008_add_user_last_scan_error.py` | `users.last_scan_error` | Phase A — graceful failure |

---

## Planned migrations (not yet implemented)

| # | Spec | File (proposed) | Adds | Phase |
|---|------|-----------------|------|-------|
| 009 | [ai-profile-enrichment.md](ai-profile-enrichment.md) | `009_add_user_profile_fields.py` | `users`: `life_stage`, `goal`, `profile_notes`, `profile_enrichment`, `weekly_review_cache`, `weekly_review_generated_at`; `program_history`: `original_video_id`, `published_at` | O1 + O3 |
| 010 | [exercise-breakdown-with-gifs.md](exercise-breakdown-with-gifs.md) | `010_add_exercise_breakdowns.py` | `exercise_breakdowns` table | Exercise breakdown |
| 011 | [channel-recommendations.md](channel-recommendations.md) | `011_add_channel_thumbnail.py` | `channels.thumbnail_url` | R2 |
| 012 | [channel-recommendations.md](channel-recommendations.md) | `012_add_video_feedback.py` | `video_feedback` table | R3 |
| 013 | [ai-cost-reduction.md](ai-cost-reduction.md) | `013_add_monthly_classify_budget.py` | `users.monthly_classify_budget` | F7 |
| 014 | [ai-cost-reduction.md](ai-cost-reduction.md) | `014_add_global_classification_cache.py` | `global_classification_cache` table | F8 |
| 015 | [email-weekly-plan.md](email-weekly-plan.md) | `015_add_email_notifications.py` | `users.email_notifications` | Phase C |

---

## Notes

- Migration 009 consolidates all Phase O1 + O3 `users` columns and `program_history` additions into a single migration. `life_stage` and `goal` added here satisfy both Phase O1 and the prerequisite for Phase R3 — no separate migration needed for R3.
- Migrations 013 and 014 (F7, F8) are deferred until real users justify the cost controls.
- Migration 015 (email) is deferred until Resend + custom domain are set up.
- If features are implemented out of order, renumber accordingly. Always confirm the live state with `ls alembic/versions/` before writing a migration file.
