"""
COSMIC PULSE — FastAPI application entry point. Milestone 3.
"""

import logging
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routers import health, observations, fits, analysis

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

is_production = os.environ.get("APP_ENV", "development").lower() == "production"

app = FastAPI(
    title="COSMIC PULSE API",
    description=(
        "Astronomical investigation platform — SPHEREx DR1 backend.\n\n"
        "**Milestone 4**: FITS inspection engine — HDU metadata, WCS, pixel↔sky, cutouts.\n\n"
        "Known observation: `2025W17_4B_0001_1` · RA=160.615° · Dec=30.669° · 24 Apr 2025"
    ),
    version="0.6.0",
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

cors_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:4173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(health.router)
app.include_router(observations.router, prefix="/observations")
app.include_router(fits.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")

logger.info("COSMIC PULSE API v0.6.0 — Milestone 6 started")
