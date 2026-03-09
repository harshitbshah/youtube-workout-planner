# Legal & Compliance Plan

## V0 Launch (must-have)

### Legal Documents
- **Privacy Policy** — required by Google API ToS (no exceptions)
- **Terms of Service** — covers liability limits, acceptable use, account termination, IP ownership
- Generate both using Termly or GetTerms for v0; lawyer review before any paid tier
- Host at `/privacy` and `/terms`, linked in footer on every page

### Onboarding Consent
1. Account creation: checkbox — *"I agree to the Terms of Service and Privacy Policy"*
2. Before first plan is generated: health disclaimer acknowledgment (one-time checkbox, never shown again)

### Footer (all pages)
- Links to Privacy Policy and Terms of Service
- *"This product uses the YouTube API Services"* — link to [YouTube ToS](https://www.youtube.com/t/terms) and [Google Privacy Policy](https://policies.google.com/privacy) (required by YouTube API ToS)
- *"Not affiliated with YouTube, Google, or any featured channels"*

### Data Deletion
- `DELETE /auth/me` must explicitly purge the user's YouTube OAuth tokens from the DB
- Google API ToS requires user YouTube data to be deleted within 30 days of account deletion
- **TODO:** verify current implementation covers this

---

## Long-term (post-launch, as scale increases)

| Item | Trigger |
|---|---|
| Lawyer-reviewed Privacy Policy + ToS | Before any paid tier launches |
| Cookie Policy + GDPR consent banner | When analytics are added |
| Dedicated `/disclaimer` page with detailed health language | Before significant user growth |
| CCPA compliance | When targeting California users at scale |
| EU AI Act compliance | Monitor as regulations firm up; applies to AI-driven health recommendations |
| FTC AI disclosure audit | Before any marketing push |

---

## AI Disclosure
- FTC guidelines require disclosure when AI meaningfully influences content recommendations
- V0: display a visible "Curated by AI" badge on the plan dashboard
- Long-term: formal audit as FTC guidance evolves

---

## Notes
- Platform-pays model means Anthropic API costs are on us — no need for billing disclaimers at v0
- YouTube OAuth scopes: only request minimum needed; display clearly what access is requested on the consent screen
- Channel creators could object to being featured — ToS should include a clause covering this
