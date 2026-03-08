# Google OAuth Setup

## The "Google hasn't verified this app" Warning

During development the OAuth app is in **Testing** mode. Anyone who signs in
sees this scary screen:

> _Google hasn't verified this app. You've been given access to an app that is
> currently being tested. You should only continue if you know the developer
> that invited you._

### Why it appears

Google Cloud OAuth apps start in **Testing** mode. Only explicitly added test
users can sign in at all, and all of them see the warning.

### Fix for friends — switch to Production (no review required)

Because the app only requests basic, non-sensitive scopes (`openid`, `email`,
`profile`), Google does **not** require a verification review to go to
Production. The warning disappears entirely.

**Steps:**

1. Go to [Google Cloud Console](https://console.cloud.google.com) → your project
2. APIs & Services → **OAuth consent screen**
3. Click **Publish App** (changes status from Testing → In production)
4. Confirm the prompt — no form or review needed for basic scopes

After publishing, any Google account can sign in and the warning is gone.

### When full verification IS required

Full Google verification (takes weeks, needs privacy policy URL) is only needed
if you add sensitive or restricted scopes — e.g. `youtube.force-ssl` for
playlist writing (Phase 5). Plan for this before opening the app publicly.

| Scope | Sensitivity | Verification needed? |
|---|---|---|
| `openid`, `email`, `profile` | Non-sensitive | No — just publish |
| `youtube.readonly` | Sensitive | Yes |
| `youtube.force-ssl` | Restricted | Yes (full review) |

---

## Adding Test Users (Testing mode only)

If you want to keep the app in Testing mode but let specific friends in:

1. OAuth consent screen → **Test users** → Add users
2. Add their Gmail addresses
3. They can now sign in (but still see the warning — it just won't block them)

This is fine for 1–2 people during active development. Switch to Production
when sharing more broadly.

---

## Manual Sign-In E2E Checklist

Test this after any auth or redirect change:

- [ ] `/` shows "Sign in with Google" button (not a spinner)
- [ ] Clicking sign-in redirects to Google's OAuth consent screen
- [ ] If in Testing mode: warning screen appears — click Advanced → Go to app
- [ ] If in Production mode: standard consent screen, no warning
- [ ] Select account and grant permissions
- [ ] **New user (no channels):** redirected to `/onboarding`
- [ ] **Returning user (has channels):** redirected to `/dashboard`
- [ ] `/dashboard` shows correct name in header
- [ ] Signing out redirects back to `/` and clears the session (hitting Back
      does not restore the dashboard without re-authenticating)
