# Web App Deployment Guide

Step-by-step setup for deploying the full web application (FastAPI backend + Next.js frontend).
If you only want the CLI tool running on GitHub Actions, see the main README instead.

---

## Overview

| Service | Purpose | Cost |
|---|---|---|
| **Railway** | Backend (FastAPI + PostgreSQL) | Usage-based, ~$0 idle |
| **Vercel** | Frontend (Next.js) | Free tier covers most use |
| **Sentry** | Error monitoring (backend + frontend) | Free tier (5k events/month) |
| **UptimeRobot** | Uptime monitoring, pings `/health` | Free tier (50 monitors) |
| **Resend** | Transactional email (weekly plan, feedback) | Free tier (3k emails/month) |
| **Google Cloud** | OAuth (login + YouTube playlist write) | Free |
| **Anthropic** | Video classification via Claude Haiku | ~$1-2 per user ever, cents/week after |

---

## 1. Google Cloud - OAuth Setup

The web app uses Google OAuth for login (basic profile) and separately for YouTube playlist
writing (requires verified YouTube scope). Both use the same OAuth client.

### Create project and credentials

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. New project → name it `workout-planner`
3. APIs & Services → Library → enable **YouTube Data API v3**
4. APIs & Services → Credentials → **+ Create Credentials** → **OAuth client ID**
5. Configure consent screen if prompted:
   - User type: **External**
   - App name: `Plan My Workout`, support email: your email
   - Add scopes: `openid`, `email`, `profile`, `https://www.googleapis.com/auth/youtube`
   - Privacy policy URL: your deployed `/privacy` page
   - Add test users: your own email
6. Back on Create OAuth client ID:
   - Application type: **Web application**
   - Authorized JavaScript origins: `https://your-frontend-domain.com`
   - Authorized redirect URIs:
     - `https://your-backend-domain.com/auth/google/callback`
     - `https://your-backend-domain.com/auth/youtube/callback`
7. Copy **Client ID** and **Client Secret**

### Publish to Production (remove "unverified app" warning)

For login-only (no YouTube scope): go to OAuth consent screen → **Publish App**. No review needed.

For YouTube scope (playlist writing): you must submit for Google verification. This takes 1-4 weeks
and requires a privacy policy URL, demo video, and explanation of YouTube API usage. See
`docs/google-oauth-setup.md` for the full verification checklist.

---

## 2. Railway - Backend + Database

### Initial setup

1. Sign up at [railway.app](https://railway.app)
2. Install the CLI: `npm install -g @railway/cli`
3. In your repo: `railway login` then `railway init` (or link an existing project)
4. Add a **PostgreSQL** plugin to your Railway project - Railway provides the `DATABASE_URL`
   automatically as an env var

### Deploy

Railway auto-deploys from the connected GitHub repo on every push to `main`. The `Dockerfile`
in the repo root handles the build.

Required config:
- Set **Start command**: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- Set **Proxy port** in Railway networking settings to match your app's port (default 8080)

### Environment variables

Set all of these in Railway → your service → Variables:

| Variable | How to get it | Notes |
|---|---|---|
| `DATABASE_URL` | Auto-set by Railway PostgreSQL plugin | Uses `postgresql://` scheme (not `postgres://`) |
| `GOOGLE_CLIENT_ID` | Google Cloud OAuth credentials | From step 1 |
| `GOOGLE_CLIENT_SECRET` | Google Cloud OAuth credentials | From step 1 |
| `GOOGLE_REDIRECT_URI` | `https://your-backend-domain.com/auth/google/callback` | Must match Google Cloud Console |
| `YOUTUBE_REDIRECT_URI` | `https://your-backend-domain.com/auth/youtube/callback` | Must match Google Cloud Console |
| `FRONTEND_URL` | `https://your-frontend-domain.com` | Controls post-OAuth redirect destination |
| `FRONTEND_ORIGINS` | `https://your-frontend-domain.com` | CORS allowed origins (comma-separated for multiple) |
| `SESSION_SECRET_KEY` | Random 32+ char string | Signs auth tokens; generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ENCRYPTION_KEY` | Fernet key | **Required** - server refuses to start without it. Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API Keys | For video classification |
| `YOUTUBE_API_KEY` | Google Cloud → APIs & Services → Credentials → API Key | For channel scanning (read-only) |
| `ADMIN_EMAIL` | Your email address | Single admin user for `/admin` console |
| `RESEND_API_KEY` | Resend dashboard → API Keys | For transactional email (see section 5) |
| `FROM_EMAIL` | e.g. `hello@yourdomain.com` | Must be from a verified Resend domain |
| `APP_URL` | `https://your-frontend-domain.com` | Used in email links |
| `SENTRY_DSN` | Sentry project → Settings → Client Keys | Optional - enables error monitoring |

### Run database migrations

After first deploy, apply Alembic migrations:
```bash
railway run alembic upgrade head
```

Or SSH into the Railway container:
```bash
railway ssh
alembic upgrade head
```

---

## 3. Vercel - Frontend

### Deploy

1. Sign up at [vercel.com](https://vercel.com)
2. Import your GitHub repo
3. Configure:
   - **Framework preset**: Next.js
   - **Root directory**: `frontend`
   - **Build command**: `npm run build` (default)
   - **Output directory**: `.next` (default)
4. Add environment variables (see below)
5. Deploy

### Environment variables

Set in Vercel → your project → Settings → Environment Variables:

| Variable | Value | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `https://your-backend-domain.com` | Railway backend URL |
| `NEXT_PUBLIC_SENTRY_DSN` | Sentry DSN for your frontend project | Optional - enables frontend error monitoring |

### Custom domain

Vercel → your project → Settings → Domains → Add domain. Point your DNS to Vercel's nameservers
or add a CNAME record. After the domain is live, update `FRONTEND_URL`, `FRONTEND_ORIGINS`, and
`GOOGLE_REDIRECT_URI` on Railway, and update the authorized origins/redirect URIs in Google Cloud
Console - missing any of these breaks the OAuth redirect.

---

## 4. Sentry - Error Monitoring

Sentry captures unhandled exceptions in the backend (FastAPI) and frontend (Next.js). It is
optional - the app runs fine without it. Set the env vars and errors start flowing automatically.

### Setup

1. Sign up at [sentry.io](https://sentry.io)
2. Create an **organization**
3. Create two projects:
   - **Project 1**: Platform = **FastAPI** (or Python), name = `workout-planner-backend`
   - **Project 2**: Platform = **Next.js**, name = `workout-planner-frontend`
4. Each project has a DSN - find it under Settings → Client Keys (DSN)

### Configure

- Set `SENTRY_DSN` on Railway with the backend project's DSN
- Set `NEXT_PUBLIC_SENTRY_DSN` on Vercel with the frontend project's DSN

That's it. Both integrations initialize automatically when the DSN is present.

### What gets captured

**Backend:** all unhandled exceptions + explicit `capture_exception()` calls in:
- Scheduler (scan, classify, plan generation, email, publish steps)
- Publish background task
- Channel suggestions, scanner date parsing, classifier cost tracking
- Channel fitness validator, feedback email

**Frontend:** all unhandled React exceptions + explicit `Sentry.captureException()` calls in:
- Dashboard (initial load, scan/generate/publish, swap picker)
- Settings (initial load, schedule save, regenerate)
- Library (assign to day, load)
- Onboarding (schedule confirm, scan trigger)

### Sentry tunnel (ad blocker bypass)

The backend has a `/sentry-tunnel` route that proxies frontend Sentry events server-side,
bypassing ad blockers. The frontend `sentry.config.ts` uses this tunnel automatically when
`NEXT_PUBLIC_SENTRY_DSN` is set. No extra configuration needed.

---

## 5. Resend - Transactional Email

Resend sends two types of emails: weekly plan summaries (to users) and feedback notifications
(to the admin). Both are disabled if `RESEND_API_KEY` is not set.

### Setup

1. Sign up at [resend.com](https://resend.com)
2. Add your domain: Resend → Domains → Add Domain
3. Add the DNS records Resend provides (TXT, MX, DKIM) to your domain registrar
4. Wait for verification (usually a few minutes)
5. Resend → API Keys → Create API Key → copy it

### Configure

Set on Railway:
- `RESEND_API_KEY` - the key from step 5
- `FROM_EMAIL` - `hello@yourdomain.com` (must be from the verified domain)
- `APP_URL` - your frontend URL (used in email links and unsubscribe URL)
- `ADMIN_EMAIL` - your email (feedback notifications are sent here)

### Email templates

The weekly plan email template is at `api/templates/weekly_plan_email.html`. It is rendered
server-side with Jinja2 and includes the plan for each active workout day (rest days hidden).

---

## 6. UptimeRobot - Uptime Monitoring

UptimeRobot pings the `/health` endpoint every 5 minutes and alerts by email if it goes down.
The health check runs `SELECT 1` against the database so both service-down and DB-dead
scenarios are caught.

### Setup

1. Sign up at [uptimerobot.com](https://uptimerobot.com) (free tier covers this)
2. Dashboard → **Add New Monitor**:
   - Monitor type: **HTTP(s)**
   - Friendly name: `Plan My Workout API`
   - URL: `https://your-backend-domain.com/health`
   - Monitoring interval: **5 minutes**
3. Alert contacts → add your email
4. Save

That's it. UptimeRobot will email you when the service goes down or recovers.

> **Note:** The `/health` endpoint supports both `GET` and `HEAD` requests. UptimeRobot free tier
> uses `HEAD` by default, which is why HEAD support was added.

---

## Complete Environment Variable Reference

### Backend (Railway)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string (auto-set by Railway) |
| `ENCRYPTION_KEY` | Yes | - | Fernet key for encrypting YouTube tokens at rest |
| `SESSION_SECRET_KEY` | Yes | `dev-secret-change-in-production` | Signs auth tokens (JWT-like) |
| `GOOGLE_CLIENT_ID` | Yes | - | OAuth login + YouTube connect |
| `GOOGLE_CLIENT_SECRET` | Yes | - | OAuth login + YouTube connect |
| `GOOGLE_REDIRECT_URI` | Yes | `http://localhost:8000/auth/google/callback` | Must match Google Cloud Console |
| `YOUTUBE_REDIRECT_URI` | Yes | `http://localhost:8000/auth/youtube/callback` | Must match Google Cloud Console |
| `FRONTEND_URL` | Yes | `http://localhost:3000` | Post-OAuth redirect destination |
| `FRONTEND_ORIGINS` | Yes | `http://localhost:3000` | CORS allowed origins (comma-separated) |
| `ANTHROPIC_API_KEY` | Yes | - | Video classification via Claude Haiku |
| `YOUTUBE_API_KEY` | Yes | - | Channel scanning (YouTube Data API, read-only) |
| `ADMIN_EMAIL` | Yes | - | Email of the admin user (gets access to `/admin`) |
| `RESEND_API_KEY` | No | - | Transactional email; emails disabled if not set |
| `FROM_EMAIL` | No | `hello@planmyworkout.app` | Sender address for emails |
| `APP_URL` | No | `https://planmyworkout.app` | Used in email links |
| `SENTRY_DSN` | No | - | Backend error monitoring; disabled if not set |
| `MIN_PLAN_CANDIDATES` | No | `3` | Min classified videos per slot for lazy classification gate |
| `TARGETED_BATCH_MULTIPLIER` | No | `5` | Videos per gap slot in targeted Anthropic mini-batch |

### Frontend (Vercel)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | Yes | `http://localhost:8000` | Backend API base URL |
| `NEXT_PUBLIC_SENTRY_DSN` | No | - | Frontend error monitoring; disabled if not set |

---

## Local Development

```bash
# Backend
cd ~/your-repo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create a local PostgreSQL database
createdb workout_planner_dev

# Set env vars (never commit .env)
cat > .env <<'EOF'
DATABASE_URL=postgresql:///workout_planner_dev
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
YOUTUBE_REDIRECT_URI=http://localhost:8000/auth/youtube/callback
FRONTEND_URL=http://localhost:3000
FRONTEND_ORIGINS=http://localhost:3000
SESSION_SECRET_KEY=local-dev-secret
ENCRYPTION_KEY=  # generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ANTHROPIC_API_KEY=sk-ant-...
YOUTUBE_API_KEY=AIza...
ADMIN_EMAIL=your@email.com
EOF

# Apply migrations
set -a && source .env && set +a
alembic upgrade head

# Start backend
.venv/bin/uvicorn api.main:app --reload
# API: http://localhost:8000 | Swagger: http://localhost:8000/docs

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
# Frontend: http://localhost:3000
```
