"""
Observations router — real IRSA archive integration (Milestone 3).
Routes are thin HTTP handlers; all logic lives in app.services.irsa.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from app.services import irsa

logger = logging.getLogger(__name__)
router = APIRouter(tags=["observations"])


# ── Response models ────────────────────────────────────────────────

class ProductAccess(BaseModel):
    url: str
    http_status: int
    content_length_bytes: int | None
    content_type: str | None
    accept_ranges: bool
    byte_range_works: bool
    fits_magic_valid: bool
    verification_level: str
    error: str | None = None


class ObservationSummary(BaseModel):
    obs_id: str
    ra: float
    dec: float
    date_obs: str | None
    detector: str
    mission: str
    data_release: str
    calib_level: int
    naxis1: int | None = None
    naxis2: int | None = None
    bunit: str | None = None
    fits_url: str | None = None
    fits_size_bytes: int | None = None
    source: str
    is_demo: bool = False


class ObservationDetail(ObservationSummary):
    access: ProductAccess | None = None
    known_extensions: list[str] = Field(default_factory=list)
    wcs_ctype1: str | None = None
    wcs_ctype2: str | None = None


class SearchResponse(BaseModel):
    results: list[ObservationSummary]
    count: int
    tap_available: bool
    tap_error: str | None = None
    search_ra: float
    search_dec: float
    search_radius_deg: float


class RepeatCompatibilityChecks(BaseModel):
    spatial_overlap: str
    temporal_separation: str
    detector_compatibility: str
    wavelength_compatibility: str
    calibration_compatibility: str
    wcs_alignment: str


class RepeatCandidate(BaseModel):
    obs_id: str
    ra: float | None
    dec: float | None
    t_min_mjd: str | None = None
    t_min_iso: str | None = None
    band: str | None = None
    calib_level: str | None = None
    access_url: str | None = None


class RepeatObservationsResponse(BaseModel):
    reference_obs_id: str
    reference_ra: float
    reference_dec: float
    search_radius_deg: float
    tap_available: bool
    tap_error: str | None = None
    candidates_found: int
    candidates: list[RepeatCandidate]
    classification: str
    explanation: str
    compatibility_checks: RepeatCompatibilityChecks
    scientific_note: str


# ── Helpers ────────────────────────────────────────────────────────

def _record_to_summary(rec: irsa.ObservationRecord) -> ObservationSummary:
    return ObservationSummary(
        obs_id=rec.obs_id,
        ra=rec.ra,
        dec=rec.dec,
        date_obs=rec.date_obs,
        detector=rec.detector,
        mission=rec.mission,
        data_release=rec.data_release,
        calib_level=rec.calib_level,
        naxis1=rec.naxis1,
        naxis2=rec.naxis2,
        bunit=rec.bunit,
        fits_url=rec.fits_url,
        fits_size_bytes=rec.fits_size_bytes,
        source=rec.source,
        is_demo=rec.is_demo,
    )


def _access_to_model(a: irsa.ProductAccessResult) -> ProductAccess:
    return ProductAccess(
        url=a.url,
        http_status=a.http_status,
        content_length_bytes=a.content_length,
        content_type=a.content_type,
        accept_ranges=a.accept_ranges,
        byte_range_works=a.byte_range_works,
        fits_magic_valid=a.fits_magic_valid,
        verification_level=a.verification_level,
        error=a.error,
    )


# ── Endpoints ──────────────────────────────────────────────────────

@router.get("/search", response_model=SearchResponse)
async def search_observations(
    ra: Annotated[float, Query(ge=0, lt=360, description="Right Ascension (degrees)")],
    dec: Annotated[float, Query(ge=-90, le=90, description="Declination (degrees)")],
    radius: Annotated[float, Query(gt=0, le=5, description="Search radius (degrees)")] = 0.5,
) -> SearchResponse:
    """
    Search for SPHEREx DR1 observations near given sky coordinates.

    Uses IRSA TAP CONTAINS query where available.
    Always checks whether the confirmed observation (2025W17_4B_0001_1)
    falls within the search cone.
    """
    logger.info("Search: RA=%.4f Dec=%.4f radius=%.3f", ra, dec, radius)
    records, tap_error = irsa.search_observations(ra, dec, radius)
    return SearchResponse(
        results=[_record_to_summary(r) for r in records],
        count=len(records),
        tap_available=not bool(tap_error),
        tap_error=tap_error or None,
        search_ra=ra,
        search_dec=dec,
        search_radius_deg=radius,
    )


@router.get("/{observation_id}", response_model=ObservationDetail)
async def get_observation(observation_id: str) -> ObservationDetail:
    """
    Retrieve detailed metadata for a specific observation.
    Checks FITS product accessibility for the known observation.
    """
    logger.info("Detail: %s", observation_id)
    if observation_id != irsa.KNOWN_OBS_ID:
        raise HTTPException(
            status_code=404,
            detail=f"Observation '{observation_id}' not found. "
                   f"Only '{irsa.KNOWN_OBS_ID}' is currently confirmed.",
        )

    rec = irsa.get_known_observation(check_access=True)
    access_model = _access_to_model(rec.access_result) if rec.access_result else None

    return ObservationDetail(
        obs_id=rec.obs_id,
        ra=rec.ra,
        dec=rec.dec,
        date_obs=rec.date_obs,
        detector=rec.detector,
        mission=rec.mission,
        data_release=rec.data_release,
        calib_level=rec.calib_level,
        naxis1=rec.naxis1,
        naxis2=rec.naxis2,
        bunit=rec.bunit,
        fits_url=rec.fits_url,
        fits_size_bytes=rec.fits_size_bytes,
        source=rec.source,
        is_demo=rec.is_demo,
        access=access_model,
        known_extensions=["IMAGE", "FLAGS", "VARIANCE", "ZODI", "EPSF", "WCS-WAVE"],
        wcs_ctype1=irsa.CONFIRMED_METADATA["wcs_ctype1"],
        wcs_ctype2=irsa.CONFIRMED_METADATA["wcs_ctype2"],
    )


@router.get("/{observation_id}/products", response_model=list[dict])
async def get_observation_products(observation_id: str) -> list[dict]:
    """
    List known FITS products for an observation.
    Checks current accessibility of each product URL.
    """
    if observation_id != irsa.KNOWN_OBS_ID:
        raise HTTPException(status_code=404, detail=f"Observation '{observation_id}' not found.")

    access = irsa.check_product_access(irsa.KNOWN_FITS_URL)
    return [{
        "obs_id": observation_id,
        "product_type": "level2",
        "detector": "D1",
        "filename": "level2_2025W17_4B_0001_1D1_spx_l2b-v27-2026-196.fits",
        "url": irsa.KNOWN_FITS_URL,
        "size_bytes": irsa.CONFIRMED_METADATA["fits_size_bytes"],
        "access": {
            "http_status": access.http_status,
            "verification_level": access.verification_level,
            "fits_magic_valid": access.fits_magic_valid,
            "byte_range_works": access.byte_range_works,
            "error": access.error,
        },
        "extensions": ["IMAGE", "FLAGS", "VARIANCE", "ZODI", "EPSF", "WCS-WAVE"],
        "data_release": "DR1",
    }]


@router.get("/{observation_id}/repeats", response_model=RepeatObservationsResponse)
async def find_repeat_observations(
    observation_id: str,
    radius: Annotated[float, Query(gt=0, le=5, description="Search radius (degrees)")] = 0.5,
) -> RepeatObservationsResponse:
    """
    Investigate whether repeat SPHEREx observations exist near the given observation.
    Returns an honest classification with explicit compatibility limitations.
    """
    if observation_id != irsa.KNOWN_OBS_ID:
        raise HTTPException(status_code=404, detail=f"Observation '{observation_id}' not found.")

    result = irsa.find_repeat_observations(
        ra=irsa.CONFIRMED_METADATA["ra"],
        dec=irsa.CONFIRMED_METADATA["dec"],
        radius_deg=radius,
    )

    candidates = [
        RepeatCandidate(
            obs_id=c["obs_id"],
            ra=c.get("ra"),
            dec=c.get("dec"),
            t_min_mjd=str(c["t_min_mjd"]) if c.get("t_min_mjd") else None,
            t_min_iso=c.get("t_min_iso"),
            band=c.get("band"),
            calib_level=str(c.get("calib_level")) if c.get("calib_level") else None,
            access_url=c.get("access_url"),
        )
        for c in result["candidates"]
    ]

    checks = result["compatibility_checks"]
    return RepeatObservationsResponse(
        reference_obs_id=result["reference_obs_id"],
        reference_ra=result["reference_ra"],
        reference_dec=result["reference_dec"],
        search_radius_deg=result["search_radius_deg"],
        tap_available=result["tap_available"],
        tap_error=result.get("tap_error"),
        candidates_found=result["candidates_found"],
        candidates=candidates,
        classification=result["classification"],
        explanation=result["explanation"],
        compatibility_checks=RepeatCompatibilityChecks(**checks),
        scientific_note=result["scientific_note"],
    )
