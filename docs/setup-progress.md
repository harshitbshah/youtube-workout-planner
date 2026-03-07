# Setup Progress

Track your progress through the one-time setup steps.
Check boxes off directly on GitHub (click the checkbox) or edit locally (`[ ]` → `[x]`).

---

## Environment

- [x] Python 3.10+ confirmed (`python3 --version`)
- [x] Dependencies installed (`pip install -r requirements.txt`)

## Google Cloud — API Key (read access)

- [x] Google Cloud project created (`workout-planner`)
- [x] YouTube Data API v3 enabled
- [x] API key created and saved

## Google Cloud — OAuth (playlist write access)

- [x] OAuth consent screen configured (External, test user added)
- [x] OAuth client ID created (Desktop app)
- [x] `scripts/client_secret.json` downloaded and placed

## OAuth Refresh Token

- [x] `python scripts/get_oauth_token.py` run successfully
- [x] Client ID copied
- [x] Client secret copied
- [x] Refresh token copied

## Anthropic

- [x] Anthropic account created
- [x] API key created (`sk-ant-...`)

## YouTube

- [x] Playlist `Weekly Workout Plan` created on YouTube
- [x] Playlist ID copied and added to `config.yaml`

## Local Configuration

- [x] `config.yaml` schedule adjusted to your training split

## Local Runs

- [x] `python main.py --init` completed (full channel scan + classification)
- [x] `python main.py --dry-run` plan looks correct

## GitHub

- [x] Private repo `youtube-workout-planner` created on GitHub
- [x] Code pushed (`git push -u origin main`)
- [x] Secret `YOUTUBE_API_KEY` added
- [x] Secret `YOUTUBE_CLIENT_ID` added
- [x] Secret `YOUTUBE_CLIENT_SECRET` added
- [x] Secret `YOUTUBE_OAUTH_REFRESH_TOKEN` added
- [x] Secret `ANTHROPIC_API_KEY` added

## Final Verification

- [x] GitHub Actions triggered manually → run completed successfully
- [x] YouTube playlist refreshed with this week's videos
