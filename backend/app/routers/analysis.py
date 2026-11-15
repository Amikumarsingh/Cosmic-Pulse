"""
Source analysis router — Milestone 6.

Endpoints:
  POST /api/analysis/{obs_id}/detect        — run source detection
  GET  /api/analysis/{obs_id}/results       — retrieve cached results
  GET  /api/analysis/{obs_id}/sources/{id}  — single source detail

All analysis is performed on the full-resolution 2040×2040 IMAGE HDU.
The 512×512 PNG preview is NOT used for scientific measurements.
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import source_analysis as sa
from app.services.fits_service import _download_fits, _validate_url
from app.services.irsa import KNOWN_OBS_ID, KNOWN_FITS_URL

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])

# Default parameters
DEFAULT_NSIGMA = 3.0
DEFAULT_NPIXELS = 5
DEFAULT_APERTURE = 3.0
DEFAULT_BOX = 64
MAX_SOURCES_RETURNED = 200


def _resolve_obs(obs_id: str) -> str:
    if obs_id != KNOWN_OBS_ID:
        raise HTTPException(
            status_code=404,
            detail=f"Observation '{obs_id}' not found. "
                   f"Only '{KNOWN_OBS_ID}' is currently confirmed.",
        )
    return KNOWN_FITS_URL


def _cache_dir() -> Path:
    d = Path(os.environ.get("FITS_CACHE_DIR", tempfile.gettempdir())) / "cosmic_pulse_fits"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Pydantic models ────────────────────────────────────────────────

class DetectRequest(BaseModel):
    nsigma: float = Field(DEFAULT_NSIGMA, ge=0.5, le=20.0,
                          description="Detection threshold in units of background RMS")
    npixels_min: int = Field(DEFAULT_NPIXELS, ge=1, le=500,
                             description="Minimum connected pixels for a valid source")
    aperture_radius_px: float = Field(DEFAULT_APERTURE, ge=0.5, le=20.0,
                                      description="Circular aperture radius in pixels")
    box_size: int = Field(DEFAULT_BOX, ge=8, le=512,
                          description="Tile size for background estimation")


class SourceResponse(BaseModel):
    source_id: int
    label: int
    x_centroid: float
    y_centroid: float
    x_fits: float
    y_fits: float
    ra_deg: float | None = None
    dec_deg: float | None = None
    wcs_approximate: bool
    area_px: int
    peak_flux: float
    bbox_x0: int
    bbox_y0: int
    bbox_x1: int
    bbox_y1: int
    aperture_radius_px: float
    aperture_flux: float | None
    bunit: str | None = None


class AnalysisResponse(BaseModel):
    obs_id: str
    source_hdu: str
    nsigma: float
    npixels_min: int
    aperture_radius_px: float
    box_size: int
    bkg_median: float
    bkg_rms_median: float
    n_sources: int
    sources: list[SourceResponse]
    naxis1: int
    naxis2: int
    bunit: str | None = None
    nan_count: int
    sources_capped: bool
    from_cache: bool
    scientific_notes: list[str]


def _to_response(result: sa.AnalysisResult) -> AnalysisResponse:
    return AnalysisResponse(
        obs_id=result.obs_id,
        source_hdu=result.source_hdu,
        nsigma=result.nsigma,
        npixels_min=result.npixels_min,
        aperture_radius_px=result.aperture_radius_px,
        box_size=result.box_size,
        bkg_median=result.bkg_median,
        bkg_rms_median=result.bkg_rms_median,
        n_sources=result.n_sources,
        sources=[SourceResponse(**s.__dict__) for s in result.sources],
        naxis1=result.naxis1,
        naxis2=result.naxis2,
        bunit=result.bunit,
        nan_count=result.nan_count,
        sources_capped=result.sources_capped,
        from_cache=result.from_cache,
        scientific_notes=result.scientific_notes,
    )


# ── Endpoints ──────────────────────────────────────────────────────

@router.post(
    "/{obs_id}/detect",
    response_model=AnalysisResponse,
    summary="Run source detection and aperture photometry on the IMAGE HDU",
)
async def detect_sources(obs_id: str, req: DetectRequest) -> AnalysisResponse:
    """
    Run background estimation, source detection, and aperture photometry
    on the full-resolution 2040×2040 IMAGE HDU.

    Requires full FITS download (~62 MB, cached after first call).
    Results are cached per (obs_id, parameters).

    Scientific notes:
    - Background estimated via sigma-clipped tiled median.
    - ZODI NOT subtracted.
    - FLAGS is co-indexed but not applied (bit definitions and exclusion policy
      are unverified).
    - No photometric uncertainty (VARIANCE semantics unverified).
    - Coordinates use the IMAGE TAN-SIP WCS; astrometric calibration is not
      independently verified.
    - Aperture flux is unavailable for apertures clipped by image edges or
      containing non-finite pixels.
    """
    _resolve_obs(obs_id)
    logger.info(
        "detect: %s nsigma=%.1f npixels=%d aperture=%.1f box=%d",
        obs_id, req.nsigma, req.npixels_min, req.aperture_radius_px, req.box_size,
    )
    try:
        fits_path = _download_fits(KNOWN_FITS_URL)
        result = sa.run_source_analysis(
            fits_path=fits_path,
            obs_id=obs_id,
            nsigma=req.nsigma,
            npixels_min=req.npixels_min,
            aperture_radius_px=req.aperture_radius_px,
            box_size=req.box_size,
            cache_dir=_cache_dir(),
            max_sources=MAX_SOURCES_RETURNED,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail="The requested analysis could not be completed.",
        ) from e
    except Exception as e:
        logger.exception("Source analysis failed")
        raise HTTPException(
            status_code=502,
            detail="Source analysis temporarily unavailable. Please try again.",
        ) from e

    return _to_response(result)


@router.get(
    "/{obs_id}/results",
    response_model=AnalysisResponse,
    summary="Retrieve cached analysis results (default parameters)",
)
async def get_results(
    obs_id: str,
    nsigma: Annotated[float, Query(ge=0.5, le=20.0)] = DEFAULT_NSIGMA,
    npixels_min: Annotated[int, Query(ge=1, le=500)] = DEFAULT_NPIXELS,
    aperture_radius_px: Annotated[float, Query(ge=0.5, le=20.0)] = DEFAULT_APERTURE,
    box_size: Annotated[int, Query(ge=8, le=512)] = DEFAULT_BOX,
) -> AnalysisResponse:
    """
    Return cached analysis results for the given parameters.
    Returns 404 if no cached result exists — run POST /detect first.
    """
    _resolve_obs(obs_id)
    key = sa._analysis_cache_key(
        obs_id, nsigma, npixels_min, aperture_radius_px, box_size,
        MAX_SOURCES_RETURNED,
    )
    path = sa._analysis_cache_path(_cache_dir(), key)
    cached = sa._load_cached(path)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail="No cached results for these parameters. Run POST /detect first.",
        )
    cached.from_cache = True
    return _to_response(cached)


@router.get(
    "/{obs_id}/sources/{source_id}",
    response_model=SourceResponse,
    summary="Return detail for a single detected source",
)
async def get_source(
    obs_id: str,
    source_id: int,
    nsigma: Annotated[float, Query(ge=0.5, le=20.0)] = DEFAULT_NSIGMA,
    npixels_min: Annotated[int, Query(ge=1, le=500)] = DEFAULT_NPIXELS,
    aperture_radius_px: Annotated[float, Query(ge=0.5, le=20.0)] = DEFAULT_APERTURE,
    box_size: Annotated[int, Query(ge=8, le=512)] = DEFAULT_BOX,
) -> SourceResponse:
    """
    Return detail for a single source by source_id from cached results.
    Run POST /detect first to populate the cache.
    """
    _resolve_obs(obs_id)
    key = sa._analysis_cache_key(
        obs_id, nsigma, npixels_min, aperture_radius_px, box_size,
        MAX_SOURCES_RETURNED,
    )
    path = sa._analysis_cache_path(_cache_dir(), key)
    cached = sa._load_cached(path)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail="No cached results. Run POST /detect first.",
        )
    match = next((s for s in cached.sources if s.source_id == source_id), None)
    if match is None:
        raise HTTPException(
            status_code=404,
            detail=f"Source {source_id} not found in results.",
        )
    return SourceResponse(**match.__dict__)
