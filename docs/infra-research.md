# Infrastructure Research

> Captured 2026-03-07, ahead of the web app build. Maps the open questions from
> [scaling.md](./scaling.md) to concrete options and recommendations.

---

## Railway - Lessons Learned (2026-03-09)

Captured from debugging the first live deployment.

### Proxy port must match `$PORT`
Railway injects `PORT` (typically `8080`) into the container at runtime. Its reverse proxy
routes external traffic to whatever port is configured in the Networking settings (Railway
dashboard → service → Settings → Networking). These two values must match.

The Dockerfile CMD default `${PORT:-8000}` means the app starts on 8080 (Railway's PORT)
while the proxy was still configured for 8000. **Fix:** change the proxy port to 8080 in the
Railway dashboard, or set PORT explicitly as a Railway variable.

### `postgres://` → `postgresql://` rewrite required
Railway's PostgreSQL service emits `DATABASE_URL` with a `postgres://` scheme. SQLAlchemy 2.x
removed support for this alias - `create_engine` raises `NoSuchModuleError` at import time.
Add a one-line rewrite before `create_engine` and before passing the URL to Alembic:
```python
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
```

### Cross-domain session cookies require `SameSite=none; Secure`
When frontend (Vercel) and backend (Railway) are on different domains, Starlette's default
`SameSite=lax` blocks the session cookie on cross-origin `fetch` requests. Set
`same_site="none"` and `https_only=True` on `SessionMiddleware` in production. Browsers
require the `Secure` flag whenever `SameSite=none` is used.

### Internal health probes bypass the public proxy
Railway's health check probes (`100.64.x.x`) connect directly to the container, bypassing
the public reverse proxy. A misconfigured proxy port causes `/health` to return 200
internally while all external traffic gets 502. Do not rely on health check success alone
to confirm public accessibility - always test from outside Railway's network.

### Useful Railway CLI commands
```bash
npm install -g @railway/cli
railway login --browserless          # use when browser auto-open fails
railway list                         # list projects
railway link --project <name>        # link local dir to project
railway service status --all         # show all services + deployment status
railway logs --service <name>        # tail runtime logs
railway variables --service <name>   # show all env vars
railway redeploy --service <name> --yes   # redeploy latest cached image
railway up --service <name> --detach      # rebuild + deploy from local source
railway ssh --service <name> -- <cmd>     # exec into running container
```

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

- **Railway** provisions all services (web, Postgres, Redis, workers) in one project with a single click per service. Usage-based billing means near-zero cost when idle - good for a side project with unpredictable early traffic. Weaknesses: no free tier, 5-minute request timeout, manual horizontal scaling.
- **Render** charges fixed monthly rates regardless of usage - predictable for stable workloads, expensive for idle ones. Autoscaling, zero-downtime deploys, and a Heroku-style `Procfile` worker model make it the most production-ready option.
- **Fly.io** offers the cheapest managed Postgres (~$34/mo vs Railway's ~$92 for comparable specs) and scale-to-zero workers. Best choice if low-latency global deployment matters, but more infrastructure config upfront.

### Recommendation

Start on **Railway** for the prototype - all required services provision instantly, usage-based billing keeps costs near zero until there are real users, and the DX is fast.

Migrate to **Render** when/if there's a stable paying user base that justifies predictable billing and production-grade autoscaling.

---

## Scheduler / Background Jobs

**Decision made (2026-03-07):** use **APScheduler** (in-process) for Phase 3, not Celery + Redis.

### Options evaluated

| Option | Extra infra | Cost | Best for |
|---|---|---|---|
| **APScheduler** (in-process) | None | $0 | Early-stage, small user base |
| **Celery + Redis** | Redis instance + worker process | $0–15/mo | Scale, retries, job visibility |
| **PostgreSQL-backed queue** | None (reuses existing Postgres) | $0 | Mid-ground, no Redis |

### Decision rationale

- Celery + Redis adds two new infrastructure dependencies before the app has any users
- At low user counts, the weekly cron runs sequentially per user in seconds - no need for distributed workers
- APScheduler runs inside the existing FastAPI process; zero extra services to deploy or monitor
- Migration path is straightforward: when user counts grow or job duration becomes an issue, swap APScheduler for Celery Beat + Redis workers without changing the underlying task logic

### Cost context (Celery + Redis, for reference)

- Managed Redis (Upstash free tier): $0 for low command volumes; pennies/month otherwise
- Celery worker: no separate paid service - just a Python process; ~$5–7/mo extra if hosting on a separate dyno
- Total: $0 (same VM + Upstash free) to ~$15/mo (managed Redis + separate worker dyno)

### Future migration trigger

Switch to Celery when any of these apply:
- Weekly scan/classify job takes >30 seconds per user (parallelism needed)
- Need job retries, dead-letter queues, or task monitoring dashboard
- Horizontal scaling of workers becomes necessary

---

## Frontend

**Decision made (2026-03-08):** Next.js 16 + Tailwind CSS v4, hosted on Vercel.



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

Next.js on Vercel - Vercel free tier for the frontend, Railway for the backend API.
Full React SPA was considered overkill; HTMX was considered but Next.js was chosen
for its component model (reusable ChannelManager, ScheduleEditor across onboarding + settings)
and first-class TypeScript support.

---

## Anthropic API - shared vs. user-supplied key

**Decision needed:** does the platform pay for classification, or does each user bring their own key?

### Cost context

- Full channel init (~2,000 videos): ~$1–2 total via Batch API
- Weekly incremental run (10–30 new videos): a few cents

### Options

| Approach | UX | Cost risk | Complexity |
|---|---|---|---|
| **Shared platform key** | Frictionless onboarding - no API key required from users | Platform absorbs classification cost | Add per-user usage cap to control spend |
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
- YouTube API key creation is free and takes ~2 minutes - could be part of the OAuth onboarding flow, or handled transparently by the platform

### Recommendation

Not a blocker for v1. A single shared key comfortably covers the first ~10 users. Add per-user API key support (or apply for a quota increase) before scaling beyond that.

---

## Summary - recommended stack

| Layer | Choice | Notes |
|---|---|---|
| API | FastAPI | Already Python; no change |
| Database | PostgreSQL on Railway | Replaces SQLite |
| Task queue + scheduler | APScheduler (in-process) for Phase 3; migrate to Celery + Redis if scale demands it | Replaces GitHub Actions cron |
| Auth | Google OAuth | Same Google account as YouTube |
| Frontend | HTMX (simple) or Next.js on Vercel (fast) | Decide based on iteration speed preference |
| Hosting (v1) | Railway | All services in one project, usage-based pricing |
| Hosting (v2+) | Render | When stable user base justifies fixed billing |
| Anthropic | BYOK for v1, platform-pays later | See § Anthropic API below |
| YouTube API | Shared key to start | Per-user or quota increase before scaling past ~10 users |

---

## Playlist ownership / revoked access

The playlist lives in the user's YouTube account. The app holds their OAuth refresh token and writes to their playlist on a weekly schedule. If the user revokes the app's access, the next publish attempt gets a 401.

### Recommended approach

- On any OAuth 401 during publish, mark the user's credentials as `invalid` in `user_credentials` - do not retry
- Skip the publish run for that user; leave their existing YouTube playlist as-is (last good state)
- Send an email notification: "We couldn't update your playlist - reconnect your YouTube account"
- Reconnect = standard OAuth flow; plan history and library are preserved in the DB, nothing is lost
- Show a persistent in-app banner until they reconnect

**Key principle:** never fail silently. A stale playlist with a clear notification is better than an unclear half-updated one.

This requires no special design decisions now - implement as a "don't fail silently" requirement in Phase 5 (playlist publishing).

---

## Free tier / pricing

### Cost context

The main cost driver is Anthropic classification, not hosting:

| Operation | Cost |
|---|---|
| Full channel init (~2,000 videos) | ~$1–2 via Batch API |
| Weekly incremental run (10–30 videos) | A few cents |

Hosting on Railway at low user counts is near-zero (usage-based, mostly idle).

### Options

**Option A - Platform pays (shared key)**
- Frictionless onboarding - no API key required
- Platform absorbs classification cost; add a per-user monthly cap to bound exposure
- Requires revenue or a willingness to subsidise free users

**Option B - BYOK (bring your own Anthropic key)**
- Zero classification cost to the platform
- Slightly more friction: user needs an Anthropic account and to paste a key
- Well-matched to early adopters who are already comfortable with API keys and OAuth flows
- Validation: test the key immediately on paste; show only last 4 chars once saved; notify + surface in-app banner if credits run out

**Option C - Free to start, introduce pricing later**
- Absorb cost at v1 to maximise signups and feedback signal
- Introduce a paywall once there's enough data on where the natural upgrade triggers are
- Most natural gate: **number of channels** (init cost scales linearly, and "more channels = more variety" is a value users understand)

### Decision (2026-03-07): platform-pays for v1

V1 targets a small group of friends. Absorbing the classification cost (~$1–2 per user ever, pennies/week after) removes all onboarding friction and keeps the focus on product feedback rather than setup.

- Uses server-side `ANTHROPIC_API_KEY` for all classification
- `user_credentials.anthropic_key` stays in the DB schema for future BYOK support but is unused in v1
- Revisit pricing model when scaling beyond friends - natural gate is number of channels (init cost scales linearly)

**Future pricing options when scaling:**
- BYOK - zero cost to platform, adds friction, suited to technical users
- Platform-pays + subscription (~$5–8/mo) - frictionless, suited to non-technical fitness enthusiasts
- Hybrid - platform-pays up to a cap, BYOK to remove the cap
