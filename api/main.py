"""
main.py — FastAPI application entry point.

Run locally:
    cd ~/Projects/youtube-workout-planner
    source .venv/bin/activate && source .env
    uvicorn api.main:app --reload
"""

import os

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from .routers import auth, health

app = FastAPI(title="YouTube Workout Planner API", version="0.1.0")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "dev-secret-change-in-production"),
)

app.include_router(health.router)
app.include_router(auth.router)
