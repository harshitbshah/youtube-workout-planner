# Infrastructure Research

> Captured 2026-03-07, ahead of the web app build. Maps the open questions from
> [scaling.md](./scaling.md) to concrete options and recommendations.

---

## Hosting

**Decision needed:** where does the FastAPI app, Celery workers, PostgreSQL, and Redis run?

### Options evaluated

| Platform | Pricing model | PostgreSQL | Redis | Best fit |
|---|---|---|---|---|
| **Railway** | Usage-based (CPU/RAM per minute) | ✅ one-click | ✅ one-click | Fast MVP, variable workloads |
| **Render** | Fixed/tiered instances | ✅ managed | ✅ $7/mo managed | Stable SaaS, production grade |
| **Fly.io** | Usage-based, scale-to-zero | ✅ managed ($33/mo) | ✅ | Global edge, GPU access |

### Key trade-offs

- **Railway** provisions all services (web, Postgres, Redis, workers) in one project with a single click per service. Usage-based billing means near-zero cost when idle — good for a side project with unpredictable early traffic. Weaknesses: no free tier, 5-minute request timeout, manual horizontal scaling.
- **Render** charges fixed monthly rates regardless of usage — predictable for stable workloads, expensive for idle ones. Autoscaling, zero-downtime deploys, and a Heroku-style `Procfile` worker model make it the most production-ready option.
- **Fly.io** offers the cheapest managed Postgres (~$34/mo vs Railway's ~$92 for comparable specs) and scale-to-zero workers. Best choice if low-latency global deployment matters, but more infrastructure config upfront.

### Recommendation

Start on **Railway** for the prototype — all required services provision instantly, usage-based billing keeps costs near zero until there are real users, and the DX is fast.

Migrate to **Render** when/if there's a stable paying user base that justifies predictable billing and production-grade autoscaling.

---

## Scheduler

**Decision needed:** what replaces GitHub Actions as the per-user weekly cron?

Vercel cron jobs only trigger HTTP endpoints — they cannot run the Python pipeline directly. GitHub Actions is the right tool for the current single-user setup and should stay as-is.

For multi-user: **Celery Beat** (included with Celery) handles per-user periodic tasks natively. Each user's weekly job is a scheduled Celery task, scoped by `user_id`. Railway and Render both support Celery workers via `Procfile`.

No additional infrastructure needed — the Celery + Redis setup already required for background scan/classify jobs also handles scheduling.

---

## Frontend

**Decision needed:** how much UI complexity, and where does it run?

The interaction surface is intentionally small:
- Week grid schedule editor
- Channel search + add
- Plan preview + manual day-swap

Three options:

| Approach | Complexity | Speed to build | Best for |
|---|---|---|---|
| **HTMX + FastAPI templates** | Low | Fast | Minimal JS, server-rendered, suits low-interactivity UI |
| **Next.js on Vercel** | Medium | Fast (with v0/Claude for component generation) | Clean split: frontend on Vercel free tier, backend on Railway |
| **React SPA** | High | Slower | Maximum flexibility, overkill for this surface area |

### Recommendation

**HTMX** is the leanest path and well-matched to the low interactivity of the UI. If iteration speed matters more than keeping things simple, **Next.js on Vercel** is a good split: Vercel's free tier handles the frontend, Railway handles the backend, and tools like v0 or Claude can generate components quickly.

Full React SPA is over-engineered for this use case.

---

## Anthropic API — shared vs. user-supplied key

**Decision needed:** does the platform pay for classification, or does each user bring their own key?

### Cost context

- Full channel init (~2,000 videos): ~$1–2 total via Batch API
- Weekly incremental run (10–30 new videos): a few cents

### Options

| Approach | UX | Cost risk | Complexity |
|---|---|---|---|
| **Shared platform key** | Frictionless onboarding — no API key required from users | Platform absorbs classification cost | Add per-user usage cap to control spend |
| **User-supplied key** | Adds friction (users need an Anthropic account) | Zero cost to platform | `user_credentials` table already has a field for this |

### Recommendation

Use a **shared platform key** for v1. Cost per user is very low; the friction of requiring an Anthropic account would hurt conversion. Add a per-user monthly usage cap to bound exposure.

Optionally allow power users to supply their own key (the data model already supports it) to remove any cap for advanced users.

---

## YouTube API quota

**Decision needed:** will the 10,000 units/day limit be a bottleneck at scale?

### Current usage per user per week

| Operation | Quota cost |
|---|---|
| Incremental channel scan (~500 videos) | ~20 units |
| Weekly playlist refresh (clear + insert) | ~650 units |
| **Total per user per week** | **~670 units** |

### Headroom

- Single API key supports ~14 users running weekly refreshes simultaneously (10,000 / 670 ≈ 14)
- For larger user bases: issue per-user API keys, or apply for a quota increase (Google grants these readily for legitimate apps)
- YouTube API key creation is free and takes ~2 minutes — could be part of the OAuth onboarding flow, or handled transparently by the platform

### Recommendation

Not a blocker for v1. A single shared key comfortably covers the first ~10 users. Add per-user API key support (or apply for a quota increase) before scaling beyond that.

---

## Summary — recommended stack

| Layer | Choice | Notes |
|---|---|---|
| API | FastAPI | Already Python; no change |
| Database | PostgreSQL on Railway | Replaces SQLite |
| Task queue + scheduler | Celery + Redis on Railway | Replaces GitHub Actions cron |
| Auth | Google OAuth | Same Google account as YouTube |
| Frontend | HTMX (simple) or Next.js on Vercel (fast) | Decide based on iteration speed preference |
| Hosting (v1) | Railway | All services in one project, usage-based pricing |
| Hosting (v2+) | Render | When stable user base justifies fixed billing |
| Anthropic | Shared platform key | With per-user cap; user-supplied key optional |
| YouTube API | Shared key to start | Per-user or quota increase before scaling past ~10 users |
