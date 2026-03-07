"""
main.py — FastAPI application entry point.

Run locally:
    cd ~/Projects/youtube-workout-planner
    source .venv/bin/activate && source .env
    uvicorn api.main:app --reload
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from .routers import auth, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail loudly on startup if required secrets are missing.
    # Better to crash immediately than to store unencrypted credentials silently.
    if not os.getenv("ENCRYPTION_KEY"):
        raise RuntimeError(
            "ENCRYPTION_KEY environment variable must be set before starting the server. "
            "Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    yield


app = FastAPI(title="YouTube Workout Planner API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "dev-secret-change-in-production"),
)

app.include_router(health.router)
app.include_router(auth.router)
