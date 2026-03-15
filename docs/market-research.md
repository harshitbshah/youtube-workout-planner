# Market Research - Competitive Landscape & PMF

> Researched 2026-03-07. Revisit before any serious productization effort.

---

## TL;DR

No product exists that does exactly what this project does. The specific
combination - **multi-channel YouTube scanning + LLM classification by workout
type/body focus/difficulty + training-split-aware schedule generation +
YouTube playlist write-back** - is a genuine gap. Several partial solutions
exist but each stops short in a key way.

---

## Closest Competitor: MzFit

**Website:** https://mzfit.app | **Platform:** iOS only

The most direct overlap. Worth monitoring closely.

**What it does well:**
- Pulls from YouTube fitness channels you follow
- Auto-categorizes videos by body part and workout type
- "This Week" feature - auto-generates a weekly class schedule from your channels
- Smart playlists that auto-update as new videos match your criteria
- Apple Watch + HealthKit integration (workout auto-tracked when video plays)

**Where it stops short:**
| Gap | Why it matters |
|---|---|
| iOS only | No Android, no web, no self-hosted option |
| Keyword/tag classification (no LLM) | Can't reliably classify ambiguous or multi-focus videos |
| No training split config | Can't express push/pull/legs or specific day constraints |
| No YouTube playlist write-back | Separate player, not integrated with your YouTube account |
| Closed, single-creator app | Not configurable per-channel or per-schedule structure |

**PMF signal:** Actively maintained (January 2025 release, Apple Watch companion
launched 2024). Real users, real reviews. Validates the core demand.

---

## Praxis - AI Assistant for YouTube Workouts

Appeared on Product Hunt (video exists on their Facebook page) but no live
product was found. The name has since been reused by an unrelated SaaS
boilerplate. Someone saw the opportunity, made noise, didn't ship.

**Takeaway:** Execution is the moat here, not the idea.

---

## AI Workout Plan Generators (Not real competitors)

Dr. Muscle, Strongr Fastr, WorkoutGen, Easy-Peasy AI, BodBot, Planfit, etc.

These generate **text-based exercise plans from scratch**. No YouTube
integration whatsoever. They answer: "tell me what exercises to do." This
project answers: "take the YouTube channels I already love and build me a
structured weekly plan from their actual videos."

Entirely different jobs to be done. Not competing for the same user behaviour.

---

## YouTube's Own AI Playlist Generator (Feb 2026)

YouTube Premium launched a text-prompt playlist generator for music. Users
type a mood or vibe and get a playlist.

**Why it's not a threat:**
- Music-oriented, general-purpose
- No concept of training schedule logic, body focus, difficulty, or weekly progression
- "Make me a chill playlist" ≠ "build me a push-pull-legs week from these 5 channels"
- Won't build workout-specific scheduling logic - too niche for a platform product

**Indirect signal:** YouTube is investing in AI-driven playlist curation, which
confirms the direction. Their move validates demand at the macro level.

---

## Open Source / GitHub

Zero open-source projects found that combine the full loop:
YouTube Data API → LLM classification → workout scheduling → playlist write-back.

Closest individual pieces found:
- `aabid0193/youtube-data-llm-pipeline` - YouTube ingest + LLM Q&A, no scheduling
- `SMAPPNYU/youtube-data-api` - API client only, no classification
- Various LLM summarizers - no YouTube Data API integration, no scheduling

**This project is the only open-source implementation of the full pipeline.**

---

## PMF Assessment

| Signal | Evidence |
|---|---|
| Real user pain | People manually build YouTube workout schedules weekly - documented friction on r/fitness, r/bodyweightfitness |
| Proven demand | MzFit actively maintained with real users despite iOS-only limitation |
| No direct competitor | Exact combo (own channels + LLM classification + training split + playlist write-back) doesn't exist |
| Adjacent market is large | AI fitness apps are a top-funded category in 2025-26 |
| YouTube's own move | Investing in AI playlists signals macro validation, won't build niche scheduling logic |
| Failed prior attempt | Praxis tried and didn't ship - suggests execution, not idea, is the barrier |
| Open-source gap | No GitHub project covers the full loop |

---

## What People Do Today (Real Competition)

The actual behaviour this replaces: **manually copy-pasting YouTube videos
into a Notion table or spreadsheet every Sunday.** That is the real
competition - a weekly manual chore that this project eliminates entirely.

---

## Differentiation if Productized

1. **Bring-your-own channels** - user picks creators, not a curated catalog
2. **Training split awareness** - LLM understands push/pull/legs, not just "workout"
3. **YouTube playlist write-back** - output lives where the content already is
4. **Automation** - zero weekly effort once configured
5. **Cross-platform** - web app, not iOS-only

---

## Sources

- [MzFit](https://mzfit.app/)
- [MzFit on App Store](https://apps.apple.com/us/app/mzfit-youtube-fitness/id1544078193)
- [YouTube AI Playlist Generator - TechCrunch](https://techcrunch.com/2026/02/10/youtube-rolls-out-an-ai-playlist-generator-for-premium-users/)
- [Praxis on Product Hunt (Facebook video)](https://www.facebook.com/producthunt/videos/meet-praxis_-your-ai-assistant-for-youtube-workouts/3976550529134151/)
- [Top 5 Free AI Workout Generators 2026 - Dr. Muscle](https://dr-muscle.com/ai-workout-plan-generator/)
- [WorkoutGen](https://workoutgen.app/)
- [youtube-data-llm-pipeline on GitHub](https://github.com/aabid0193/youtube-data-llm-pipeline)
- [SMAPPNYU/youtube-data-api on GitHub](https://github.com/SMAPPNYU/youtube-data-api)
