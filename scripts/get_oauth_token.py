"""
get_oauth_token.py — One-time local script to generate a YouTube OAuth refresh token.

Run this ONCE on your local machine:
  python scripts/get_oauth_token.py

It will:
  1. Open your browser for Google OAuth consent
  2. Print your client_id, client_secret, and refresh_token
  3. You then copy these into GitHub Secrets (never commit them)

Prerequisites:
  - pip install google-auth-oauthlib
  - A Google Cloud project with YouTube Data API v3 enabled
  - OAuth 2.0 Client ID credentials (type: Desktop app)
    Download the JSON from Google Cloud Console and place it at:
    scripts/client_secret.json   (this file is gitignored)

  OR pass client_id and client_secret as environment variables:
    YOUTUBE_CLIENT_ID=... YOUTUBE_CLIENT_SECRET=... python scripts/get_oauth_token.py
"""

import json
import os
import sys
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Missing dependency. Run:  pip install google-auth-oauthlib")
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/youtube"]
CLIENT_SECRET_FILE = Path(__file__).parent / "client_secret.json"


def main():
    # ── Option A: use downloaded client_secret.json ──────────────────────────
    if CLIENT_SECRET_FILE.exists():
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CLIENT_SECRET_FILE), scopes=SCOPES
        )

    # ── Option B: use environment variables ──────────────────────────────────
    elif os.environ.get("YOUTUBE_CLIENT_ID") and os.environ.get("YOUTUBE_CLIENT_SECRET"):
        client_config = {
            "installed": {
                "client_id":     os.environ["YOUTUBE_CLIENT_ID"],
                "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"],
                "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
                "token_uri":     "https://oauth2.googleapis.com/token",
                "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)

    else:
        print(
            "No credentials found.\n\n"
            "Either:\n"
            "  A) Place your downloaded OAuth JSON at scripts/client_secret.json\n"
            "  B) Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET env variables\n\n"
            "See README.md Setup → Step 3 for instructions."
        )
        sys.exit(1)

    print("Opening browser for Google OAuth consent...")
    print("(If the browser doesn't open, copy the URL printed below)\n")

    creds = flow.run_local_server(port=0, prompt="consent")

    print("\n" + "=" * 60)
    print("SUCCESS — copy these values into your GitHub Secrets:")
    print("=" * 60)
    print(f"\nYOUTUBE_CLIENT_ID\n  {creds.client_id}")
    print(f"\nYOUTUBE_CLIENT_SECRET\n  {creds.client_secret}")
    print(f"\nYOUTUBE_OAUTH_REFRESH_TOKEN\n  {creds.refresh_token}")
    print("\n" + "=" * 60)
    print("IMPORTANT: Do NOT commit these values to git.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
