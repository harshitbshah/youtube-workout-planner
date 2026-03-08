"""
main.py — FastAPI application entry point.

Run locally:
    cd ~/Projects/youtube-workout-planner
    source .venv/bin/activate && source .env
    uvicorn api.main:app --reload
"""

import logging
import os
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .routers import auth, channels, health, jobs, library, plan, schedule
from .scheduler import start_scheduler, stop_scheduler


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
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="YouTube Workout Planner API", version="0.1.0", lifespan=lifespan)

_frontend_origins = os.getenv(
    "FRONTEND_ORIGINS", "http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "dev-secret-change-in-production"),
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(channels.router)
app.include_router(schedule.router)
app.include_router(plan.router)
app.include_router(jobs.router)
app.include_router(library.router)
