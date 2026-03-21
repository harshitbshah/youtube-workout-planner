# Spec: Weekly AI Review Card

**Created:** 2026-03-11
**Status:** Ready for implementation
**Depends on:** [AI Coach Chat](ai-coach-chat.md) - uses the coach router and `video_feedback` signals from [Collaborative Filtering](channel-recommendations.md)
**Migration:** 009 - `weekly_review_cache` and `weekly_review_generated_at` are included in the [AI Profile Enrichment](ai-profile-enrichment.md) migration (see [migrations-roadmap.md](migrations-roadmap.md))

**Related specs:**
- [ai-profile-enrichment.md](ai-profile-enrichment.md) - AI Profile Enrichment: migration 009 that includes this spec's schema
- [ai-coach-chat.md](ai-coach-chat.md) - AI Coach Chat: coach router where `GET /coach/weekly-review` lives

---

## What it shows

A lightweight read-only AI summary shown on the dashboard Monday mornings - one Claude
Haiku call that generates a brief weekly recap, cached for the week.

```
┌──────────────────────────────────────────────────────────┐
│  Last week - quick take                                   │
│                                                           │
│  You completed 3 of 4 sessions. Strength was your        │
│  strongest category - you've done it consistently for    │
│  3 weeks. You skipped both cardio sessions this month.   │
│  This week I've swapped Friday's HIIT for a dance        │
│  session - might be easier to stick to.                  │
│                                                           │
│  [Open Coach →]                                          │
└──────────────────────────────────────────────────────────┘
```

Shown as a dismissible card at the top of the dashboard, Monday only (or until dismissed).
Clicking "Open Coach →" opens the coach panel.

---

## New endpoint: `GET /coach/weekly-review`

```
GET /coach/weekly-review
Authorization: Bearer <token>
```

Returns: `{ "review": "string" }` or `{ "review": null }` if not enough history (< 2 weeks).

Backend logic:
1. Load last 2 weeks of `program_history` for the user
2. Load `video_feedback` rows (completion signals) for those weeks - from Collaborative Filtering (`video_feedback` table, migration 012). If not yet implemented, skip feedback signals gracefully.
3. Build a compact prompt: what was planned, what was completed, what was swapped
4. Single Claude Haiku call (no tools needed - read-only, text generation only)
5. Cache result in `users.weekly_review_cache` (text, nullable) + `users.weekly_review_generated_at`
   (DateTime) - regenerate once per week (on Monday), return cached otherwise

**Router file:** `api/routers/coach.py` (add to existing file alongside `POST /coach/chat`)

---

## DB changes - included in migration 009

These columns are bundled with the AI Profile Enrichment migration (009) to avoid two back-to-back `users`
table alterations:

```python
# In api/models.py - User class (added in migration 009)
weekly_review_cache          = Column(Text, nullable=True)
weekly_review_generated_at   = Column(DateTime(timezone=True), nullable=True)
```

---

## Frontend changes

**`app/dashboard/page.tsx`:**

1. On load (Monday only): call `GET /coach/weekly-review`
2. If `review` is non-null: render a dismissible card above the plan grid
3. "Open Coach →" button in the card opens `CoachPanel`
4. Dismiss: hide card for the rest of the session (no DB persistence needed for v1)

```typescript
// Pseudocode
const isMonday = new Date().getDay() === 1;
if (isMonday) {
  const { review } = await getWeeklyReview();
  if (review) setWeeklyReview(review);
}
```

---

## Files to create

None - endpoint goes in `api/routers/coach.py` (already created for AI Coach Chat).

## Files to modify

| File | Change |
|---|---|
| `api/routers/coach.py` | Add `GET /coach/weekly-review` logic |
| `api/models.py` | `weekly_review_cache` + `weekly_review_generated_at` on `User` (via migration 009) |
| `frontend/src/app/dashboard/page.tsx` | Fetch weekly review on Monday; render dismissible card |
| `frontend/src/lib/api.ts` | Add `getWeeklyReview()`, `WeeklyReviewResponse` type |

---

## Tests

### Unit tests (add to `tests/api/test_coach.py`)

1. `test_weekly_review_generates_on_monday` - Monday + no cache → Haiku called, result cached
2. `test_weekly_review_cached_within_week` - cache hit (same week) → Haiku not called
3. `test_weekly_review_null_insufficient_history` - fewer than 2 weeks of data → `review: null`
4. `test_weekly_review_unauthenticated` → 401

---

## Implementation order

1. Confirm migration 009 is deployed (includes `weekly_review_cache` + `weekly_review_generated_at`)
2. Add `GET /coach/weekly-review` endpoint to `api/routers/coach.py`
3. Unit tests 1–4 - all passing
4. Frontend: weekly review card on dashboard (Monday only, dismissible)
5. Ship O3
