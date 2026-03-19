# Setup Progress

Track your progress through the one-time setup steps.
Check boxes off directly on GitHub (click the checkbox) or edit locally (`[ ]` → `[x]`).

---

## Environment

- [ ] Python 3.10+ confirmed (`python3 --version`)
- [ ] Dependencies installed (`pip install -r requirements.txt`)

## Google Cloud - API Key (read access)

- [ ] Google Cloud project created (`workout-planner`)
- [ ] YouTube Data API v3 enabled
- [ ] API key created and saved

## Google Cloud - OAuth (playlist write access)

- [ ] OAuth consent screen configured (External, test user added)
- [ ] OAuth client ID created (Desktop app)
- [ ] `scripts/client_secret.json` downloaded and placed

## OAuth Refresh Token

- [ ] `python scripts/get_oauth_token.py` run successfully
- [ ] Client ID copied
- [ ] Client secret copied
- [ ] Refresh token copied

## Anthropic

- [ ] Anthropic account created
- [ ] API key created (`sk-ant-...`)

## YouTube

- [ ] Playlist `Weekly Workout Plan` created on YouTube
- [ ] Playlist ID saved for GitHub Secrets step

## Local Configuration

- [ ] `config.yaml` schedule adjusted to your training split

## Local Runs

- [ ] `python main.py --init` completed (full channel scan + classification)
- [ ] `python main.py --dry-run` plan looks correct

## GitHub

- [ ] GitHub repo created (private if you want to keep your workout history personal)
- [ ] Code pushed (`git push -u origin main`)
- [ ] Secret `YOUTUBE_API_KEY` added
- [ ] Secret `YOUTUBE_CLIENT_ID` added
- [ ] Secret `YOUTUBE_CLIENT_SECRET` added
- [ ] Secret `YOUTUBE_OAUTH_REFRESH_TOKEN` added
- [ ] Secret `ANTHROPIC_API_KEY` added
- [ ] Secret `YOUTUBE_PLAYLIST_ID` added
- [ ] Secret `CONFIG_YAML` added (`base64 -w 0 config.yaml`)

## Final Verification

- [ ] GitHub Actions triggered manually (Actions tab → Weekly Workout Plan → Run workflow)
- [ ] YouTube playlist refreshed with this week's videos
