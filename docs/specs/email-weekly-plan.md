# Weekly Plan Email - Design Spec

**Status:** ✅ Implemented (2026-03-13) - code complete, awaiting Resend account + domain verification to go live
**Trigger:** Sunday cron in `api/scheduler.py`, immediately after `generate_weekly_plan_for_user`
**Provider:** Resend API (Python SDK)
**Last updated:** 2026-03-11

---

## Prerequisites Checklist (before starting implementation)

These must be completed by the developer before implementation begins. Implementation
itself is ~1–2 hours once these are in place.

- [ ] **Create Resend account** - resend.com, free tier (3,000 emails/month, 100/day)
- [ ] **Buy a custom domain** - e.g. `planmyworkout.app` or `planmyworkout.com` (~$10–15/year
      on Cloudflare, Namecheap, or Google Domains). `planmyworkout.vercel.app` is a
      Vercel-managed subdomain - DNS cannot be edited, so it cannot be used for Resend verification.
- [ ] **Verify the domain in Resend** - Domains → Add domain → add MX/TXT/DKIM records
      to your DNS provider. Verification usually takes a few minutes.
- [ ] **Create a Resend API key** - API Keys → Create → copy it (shown once)
- [ ] **Decide the FROM_EMAIL address** - `plan@<your-domain>` or `noreply@<your-domain>`

Once done, bring back:
1. The Resend API key (`re_xxxxxxxxxxxx`)
2. Confirmation the domain is verified in Resend
3. The chosen FROM_EMAIL address

Then set on Railway: `RESEND_API_KEY`, `FROM_EMAIL`, `APP_URL=https://planmyworkout.app`

### Shortcut for testing only (not production)
Resend provides a shared sending domain (`onboarding@resend.dev`) that works immediately
with no DNS setup. Acceptable for local dev/testing but not for real users. Swapping to
a real domain later is a one-line `FROM_EMAIL` env var change - no code changes needed.

---

## Open Design Questions (resolve before implementing)

These were discussed and left open. Confirm each before starting:

| # | Question | Spec default | Notes |
|---|---|---|---|
| 1 | **Video thumbnails in the email?** | No thumbnails | Omitted for Outlook compatibility. Worth adding if targeting Gmail/Apple Mail only. |
| 2 | **Rest day label** | "Recovery" | Spec uses "Recovery" (not "Rest day") to match the senior-friendly onboarding language. Intentional for all users? |
| 3 | **Opt-in vs opt-out default** | Opt-out (default `True`) | Everyone gets the email unless they turn it off. Consider opt-in if concerned about unsolicited mail. |
| 4 | **Unsubscribe flow** | Settings page (requires auth) | No separate token-based unsubscribe link for v1. Acceptable since the user is already signed in. May need a real unsubscribe token for CAN-SPAM compliance if scaling. |

---

## Why This Phase Is Deferred

Email is a **retention tool, not a core feature**. The app already delivers a fresh plan
every Sunday - the email is a convenience nudge for users who forget to check the app.

Recommended trigger for picking this up: when you have real users and can observe
week-2+ retention drop-off without the email reminder.

Implementation effort when ready: low - all files are self-contained, no existing
routes change, scheduler hook is one function call.

---

## What the Email Does

Sent every Sunday evening (after the pipeline finishes) with the user's full weekly
workout plan - one row per day, each workout linked directly to the YouTube video.
The goal is to let a user glance at the email on Sunday night and know exactly what
they're doing all week without opening the app.

---

## New Files to Create

| File | Purpose |
|---|---|
| `api/services/email.py` | `send_weekly_plan_email(user, plan)` - builds + sends via Resend |
| `api/templates/weekly_plan_email.html` | HTML email template (Jinja2, table-based layout) |

## Files to Modify

| File | Change |
|---|---|
| `api/scheduler.py` | Call `send_weekly_plan_email` after plan generation succeeds |
| `api/models.py` | Add `email_notifications` boolean to `User` (default `True`) |
| `api/routers/auth.py` | Expose `email_notifications` in `GET /auth/me` response |
| `frontend/src/app/settings/page.tsx` | Add email preference toggle in Profile section |
| `alembic/versions/015_add_email_notifications.py` | Migration 015: `users.email_notifications` boolean (default `True`) |
| `requirements.txt` | Add `resend` package |

---

## New Environment Variables

| Var | Example | Notes |
|---|---|---|
| `RESEND_API_KEY` | `re_xxxxxxxxxxxx` | From Resend dashboard |
| `FROM_EMAIL` | `hello@planmyworkout.app` | Must be a verified Resend domain |
| `APP_URL` | `https://planmyworkout.vercel.app` | Used to build dashboard link in email |

---

## Integration Point in `scheduler.py`

Add as step 5 in `_weekly_pipeline_for_user`, after plan generation:

```python
# Step 5: send weekly plan email
from .services.email import send_weekly_plan_email
from .models import User

user = session.query(User).filter(User.id == user_id).first()
if user and getattr(user, "email_notifications", True):
    try:
        send_weekly_plan_email(user, plan)
        logger.info(f"[weekly] user={user_id}: plan email sent to {user.email}")
    except Exception as e:
        logger.error(f"[weekly] user={user_id}: email failed - {e}")
        # Never let email failure break the pipeline
```

---

## `api/services/email.py`

```python
"""
email.py - Resend-powered transactional emails.
"""
import os
import resend
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
_jinja = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)


def _format_duration(duration_sec: int | None) -> str:
    if not duration_sec:
        return ""
    mins = round(duration_sec / 60)
    return f"{mins} min"


def _workout_type_style(workout_type: str | None) -> dict:
    """Return bg/text colour pair for the workout type pill."""
    styles = {
        "strength":  {"bg": "#fef3c7", "color": "#92400e"},
        "hiit":      {"bg": "#fee2e2", "color": "#991b1b"},
        "cardio":    {"bg": "#d1fae5", "color": "#065f46"},
        "mobility":  {"bg": "#ede9fe", "color": "#4c1d95"},
    }
    return styles.get((workout_type or "").lower(), {"bg": "#f3f4f6", "color": "#374151"})


def send_weekly_plan_email(user, plan: list[dict]) -> None:
    """
    Send the weekly plan email to the user.

    user  - SQLAlchemy User instance (needs .email, .display_name)
    plan  - list of {"day": str, "video": dict | None} from generate_weekly_plan_for_user
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY not set")

    resend.api_key = api_key

    app_url = os.environ.get("APP_URL", "https://planmyworkout.vercel.app")
    from_email = os.environ.get("FROM_EMAIL", "plan@planmyworkout.app")

    # Enrich plan days with display helpers
    enriched_days = []
    active_days = 0
    total_duration_sec = 0

    for entry in plan:
        video = entry.get("video")
        if video:
            active_days += 1
            total_duration_sec += video.get("duration_sec") or 0
            enriched_days.append({
                "day": entry["day"].capitalize(),
                "is_rest": False,
                "video": video,
                "duration_str": _format_duration(video.get("duration_sec")),
                "type_style": _workout_type_style(video.get("workout_type")),
            })
        else:
            enriched_days.append({
                "day": entry["day"].capitalize(),
                "is_rest": True,
            })

    total_duration_min = round(total_duration_sec / 60)

    # Format week_start from first non-rest entry (plan is always for upcoming Monday)
    from src.planner import get_upcoming_monday
    week_start = get_upcoming_monday()
    week_start_str = week_start.strftime("%-d %B")  # e.g. "10 March"

    template = _jinja.get_template("weekly_plan_email.html")
    html = template.render(
        display_name=user.display_name or user.email.split("@")[0],
        week_start=week_start_str,
        active_days=active_days,
        total_duration_min=total_duration_min,
        days=enriched_days,
        dashboard_url=f"{app_url}/dashboard",
        unsubscribe_url=f"{app_url}/settings#notifications",
    )

    resend.Emails.send({
        "from": f"Plan My Workout <{from_email}>",
        "to": user.email,
        "subject": f"Your workout plan for the week of {week_start_str}",
        "html": html,
    })
```

---

## HTML Template - `api/templates/weekly_plan_email.html`

Full table-based HTML for broad email client compatibility (Gmail, Outlook, Apple Mail,
mobile). Inline CSS only - no `<style>` blocks (Outlook strips them).

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="color-scheme" content="light" />
  <title>Your weekly workout plan</title>
</head>
<body style="margin:0;padding:0;background-color:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">

  <!-- Outer wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f9fafb;">
    <tr>
      <td align="center" style="padding:32px 16px;">

        <!-- Card -->
        <table width="600" cellpadding="0" cellspacing="0" border="0"
               style="max-width:600px;width:100%;background-color:#ffffff;border-radius:12px;
                      border:1px solid #e5e7eb;overflow:hidden;">

          <!-- ── Header bar ── -->
          <tr>
            <td style="background-color:#18181b;padding:20px 32px;">
              <p style="margin:0;font-size:15px;font-weight:700;color:#ffffff;
                        letter-spacing:-0.2px;line-height:1;">Plan My Workout</p>
            </td>
          </tr>

          <!-- ── Hero ── -->
          <tr>
            <td style="padding:32px 32px 20px;">
              <h1 style="margin:0 0 6px;font-size:22px;font-weight:700;color:#111827;
                         line-height:1.3;letter-spacing:-0.4px;">
                Your plan for the week of {{ week_start }}
              </h1>
              <p style="margin:0;font-size:14px;color:#6b7280;line-height:1.5;">
                Hi {{ display_name }} - here's your
                {% if active_days == 0 %}rest week{% else %}{{ active_days }}-day plan{% endif %}
                {% if total_duration_min > 0 %}({{ total_duration_min }} min total){% endif %}.
              </p>
            </td>
          </tr>

          <!-- ── Day rows ── -->
          <tr>
            <td style="padding:0 32px 8px;">

              {% for entry in days %}

              {% if entry.is_rest %}
              <!-- Rest day row -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0"
                     style="margin-bottom:8px;border:1px solid #f3f4f6;border-radius:8px;">
                <tr>
                  <td style="padding:11px 14px;">
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td>
                          <p style="margin:0;font-size:12px;font-weight:600;color:#d1d5db;
                                    text-transform:uppercase;letter-spacing:0.6px;">
                            {{ entry.day }}
                          </p>
                        </td>
                        <td style="text-align:right;">
                          <p style="margin:0;font-size:12px;color:#d1d5db;">Recovery</p>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              {% else %}
              <!-- Active day row -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0"
                     style="margin-bottom:8px;border:1px solid #e5e7eb;border-radius:8px;
                            overflow:hidden;">
                <!-- Day label bar -->
                <tr>
                  <td style="padding:8px 14px;background-color:#f9fafb;
                             border-bottom:1px solid #e5e7eb;">
                    <p style="margin:0;font-size:11px;font-weight:700;color:#9ca3af;
                              text-transform:uppercase;letter-spacing:0.7px;">
                      {{ entry.day }}
                    </p>
                  </td>
                </tr>
                <!-- Video content -->
                <tr>
                  <td style="padding:14px 14px;">
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td style="vertical-align:top;padding-right:12px;">
                          <a href="{{ entry.video.url }}"
                             style="font-size:14px;font-weight:600;color:#111827;
                                    text-decoration:none;line-height:1.4;
                                    display:block;margin-bottom:4px;">
                            {{ entry.video.title }}
                          </a>
                          <p style="margin:0;font-size:12px;color:#9ca3af;line-height:1.4;">
                            {{ entry.video.channel_name }}
                            {% if entry.duration_str %}
                              &nbsp;·&nbsp;{{ entry.duration_str }}
                            {% endif %}
                          </p>
                        </td>
                        <td style="vertical-align:top;white-space:nowrap;text-align:right;
                                   width:1%;">
                          <span style="display:inline-block;
                                       background-color:{{ entry.type_style.bg }};
                                       color:{{ entry.type_style.color }};
                                       font-size:11px;font-weight:700;
                                       padding:3px 9px;border-radius:5px;
                                       text-transform:capitalize;letter-spacing:0.2px;">
                            {{ entry.video.workout_type or 'Other' }}
                          </span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
              {% endif %}

              {% endfor %}

            </td>
          </tr>

          <!-- ── CTA ── -->
          <tr>
            <td style="padding:16px 32px 32px;">
              <a href="{{ dashboard_url }}"
                 style="display:inline-block;background-color:#18181b;color:#ffffff;
                        text-decoration:none;font-size:14px;font-weight:600;
                        padding:12px 22px;border-radius:8px;letter-spacing:-0.1px;">
                Open my dashboard &rarr;
              </a>
            </td>
          </tr>

          <!-- ── Divider ── -->
          <tr>
            <td style="border-top:1px solid #f3f4f6;"></td>
          </tr>

          <!-- ── Footer ── -->
          <tr>
            <td style="padding:20px 32px;background-color:#fafafa;">
              <p style="margin:0;font-size:12px;color:#9ca3af;line-height:1.7;">
                You're receiving this because you have a Plan My Workout account.<br />
                <a href="{{ unsubscribe_url }}"
                   style="color:#9ca3af;text-decoration:underline;">
                  Manage notification preferences
                </a>
                &nbsp;·&nbsp;
                <a href="{{ dashboard_url }}"
                   style="color:#9ca3af;text-decoration:underline;">
                  planmyworkout.app
                </a>
              </p>
            </td>
          </tr>

        </table>
        <!-- /Card -->

      </td>
    </tr>
  </table>
  <!-- /Outer wrapper -->

</body>
</html>
```

---

## Email Rendering - What Each Section Looks Like

```
┌─────────────────────────────────────┐
│ Plan My Workout              [dark] │
├─────────────────────────────────────┤
│                                     │
│  Your plan for the week of 10 March │
│  Hi Harshit - here's your 5-day    │
│  plan (175 min total).              │
│                                     │
│ ┌─ MONDAY ───────────────────────┐  │
│ │ 20-Min Full Body Strength      │  │
│ │ Heather Robertson · 22 min  [Strength] │
│ └────────────────────────────────┘  │
│                                     │
│ ┌─ TUESDAY ──────────────────────┐  │
│ │ HIIT Cardio Blast No Equipment │  │
│ │ Sydney Cummings · 30 min   [HIIT]  │
│ └────────────────────────────────┘  │
│                                     │
│  WEDNESDAY                 Recovery │
│                                     │
│  [Open my dashboard →]              │
├─────────────────────────────────────┤
│  Manage notification preferences    │
│  · planmyworkout.app         [grey] │
└─────────────────────────────────────┘
```

---

## Workout Type Pill Colours

| Type | Background | Text |
|---|---|---|
| `strength` | `#fef3c7` (amber-100) | `#92400e` (amber-800) |
| `hiit` | `#fee2e2` (red-100) | `#991b1b` (red-800) |
| `cardio` | `#d1fae5` (green-100) | `#065f46` (green-800) |
| `mobility` | `#ede9fe` (violet-100) | `#4c1d95` (violet-800) |
| other/none | `#f3f4f6` (gray-100) | `#374151` (gray-700) |

---

## Subject Line

```
Your workout plan for the week of {day} {month}
```

Examples:
- `Your workout plan for the week of 10 March`
- `Your workout plan for the week of 17 March`

Keep it factual and date-anchored - no emoji, no clickbait. It will appear alongside
calendar-style emails in most inboxes.

---

## User Preference - Opt-out

Add `email_notifications: bool = True` column to the `User` model.
Gate the send in `scheduler.py` on `user.email_notifications`.
Expose it in `GET /auth/me` and add a simple toggle in Settings → Profile:

```
[ ] Send me a weekly plan summary every Sunday evening
```

The "Manage notification preferences" link in the email footer points to
`/settings#notifications`.

No separate unsubscribe token/endpoint needed for v1 - the settings page
requires auth, which is acceptable since the user is already signed in when
clicking from email.

---

## Error Handling

- Wrap the entire email step in try/except in `scheduler.py` - a send failure must
  never break plan generation or publishing.
- Log `[weekly] user={id}: email failed - {error}` and continue.
- If `RESEND_API_KEY` is missing, log a warning and skip (don't crash startup).

---

## Testing

**Unit test** (`tests/api/test_email.py`):
- Mock `resend.Emails.send`
- Call `send_weekly_plan_email(mock_user, mock_plan)`
- Assert: `send` called once, subject contains "week of", HTML contains each
  non-rest day's video title and YouTube URL

**Manual checklist** (add to `docs/testing.md`):
- [ ] Trigger pipeline for a user with a full plan - verify email received
- [ ] Verify rest days render as "Recovery" (not blank)
- [ ] Verify "Manage notification preferences" link goes to `/settings#notifications`
- [ ] Toggle email off in Settings → re-trigger pipeline → verify no email sent
- [ ] Verify email renders correctly in Gmail web, Apple Mail, and mobile Gmail

---

## Dependencies

```
# requirements.txt - add:
resend>=2.0.0
jinja2>=3.0.0    # likely already present; verify
```

---

## What NOT to Change

- The scheduler timing (Sunday 18:00 UTC) is unchanged.
- No new API routes needed - email is a backend-only side effect of the pipeline.
- The `plan` list returned by `generate_weekly_plan_for_user` is passed directly
  to `send_weekly_plan_email` - no second DB query needed.
