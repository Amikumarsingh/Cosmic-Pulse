import logging
from fastapi import APIRouter
from pydantic import BaseModel
from app.services.irsa import KNOWN_OBS_ID, KNOWN_FITS_URL, check_product_access

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str
    version: str
    backend_milestone: int
    known_obs_id: str
    fits_accessible: bool
    fits_verification_level: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    access = check_product_access(KNOWN_FITS_URL, timeout=10)
    logger.info("Health: fits_level=%s", access.verification_level)
    return HealthResponse(
        status="ok",
        version="0.6.0",
        backend_milestone=6,
        known_obs_id=KNOWN_OBS_ID,
        fits_accessible=access.fits_magic_valid,
        fits_verification_level=access.verification_level,
    )


@router.get("/live")
async def liveness() -> dict[str, str]:
    """Fast process liveness check for hosting-provider health probes."""
    return {"status": "ok"}


@router.get("/archive/health")
async def archive_health() -> dict:
    access = check_product_access(KNOWN_FITS_URL, timeout=10)
    return {
        "irsa_tap_schema": "not_checked",
        "irsa_tap_data": "not_checked",
        "irsa_ibe_fits": access.verification_level,
        "fits_magic_valid": access.fits_magic_valid,
        "fits_byte_range": access.byte_range_works,
        "fits_size_bytes": access.content_length,
        "note": (
            "This endpoint does not probe IRSA TAP. Recent TAP queries returned "
            "HTTP 502, so TAP availability is unverified. FITS access is checked "
            "via IRSA IBE byte-range HTTP."
        ),
    }
