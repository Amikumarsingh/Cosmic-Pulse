"""
FITS inspection router — Milestone 4.

All endpoints operate on the confirmed SPHEREx observation only.
Internal cache paths are never returned to API clients.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import fits_service as fs
from app.services.irsa import KNOWN_OBS_ID, KNOWN_FITS_URL

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fits", tags=["fits"])


# ── Pydantic response models ───────────────────────────────────────

class WcsSummary(BaseModel):
    valid: bool
    ctype1: str | None = None
    ctype2: str | None = None
    crpix1: float | None = None
    crpix2: float | None = None
    crval1: float | None = None
    crval2: float | None = None
    cdelt1: float | None = None
    cdelt2: float | None = None
    cd_matrix: list[list[float]] | None = None
    pc_matrix: list[list[float]] | None = None
    has_sip: bool = False
    pixel_scale_deg: float | None = None
    pixel_scale_arcsec: float | None = None
    center_ra: float | None = None
    center_dec: float | None = None
    center_note: str | None = None
    projection: str | None = None
    naxis: int = 0
    error: str | None = None


class HduSummary(BaseModel):
    index: int
    extname: str
    hdu_type: str
    has_data: bool
    naxis: int
    shape: list[int]
    bitpix: int | None = None
    dtype: str | None = None
    bunit: str | None = None
    table_columns: list[str] = Field(default_factory=list)
    wcs_summary: WcsSummary | None = None
    notes: list[str] = Field(default_factory=list)


class FitsInspectResponse(BaseModel):
    obs_id: str
    reachable: bool
    header_readable: bool
    hdus_inspected: bool
    pixel_data_loaded: bool
    hdu_count: int
    hdus: list[HduSummary]
    primary_image_hdu_index: int | None = None
    access_method: str
    error: str | None = None


class HeaderCard(BaseModel):
    key: str
    value: Any
    comment: str


class HduHeaders(BaseModel):
    index: int
    extname: str
    cards: list[HeaderCard]
    history: list[str]
    comments: list[str]


class HeadersResponse(BaseModel):
    obs_id: str
    hdus: list[HduHeaders]


class WcsResponse(BaseModel):
    obs_id: str
    source_hdu: str
    wcs: WcsSummary


class PixelToSkyResponse(BaseModel):
    obs_id: str
    x_fits: float
    y_fits: float
    x_zero: float
    y_zero: float
    ra_deg: float
    dec_deg: float
    coordinate_frame: str
    pixel_convention: str
    source_hdu: str
    wcs_approximate: bool
    wcs_note: str


class SkyToPixelResponse(BaseModel):
    obs_id: str
    ra_deg: float
    dec_deg: float
    x_zero: float
    y_zero: float
    x_fits: float
    y_fits: float
    coordinate_frame: str
    pixel_convention: str
    source_hdu: str
    in_bounds: bool
    wcs_approximate: bool
    wcs_note: str


class CutoutRequest(BaseModel):
    ra: float = Field(..., ge=0, lt=360, description="Right Ascension (degrees)")
    dec: float = Field(..., ge=-90, le=90, description="Declination (degrees)")
    width_px: int = Field(128, ge=1, le=512, description="Cutout width in pixels")
    height_px: int = Field(128, ge=1, le=512, description="Cutout height in pixels")


class CutoutResponse(BaseModel):
    obs_id: str
    ra: float
    dec: float
    width_px: int
    height_px: int
    actual_shape: list[int]
    center_x_fits: float
    center_y_fits: float
    crpix_parent: list[float]
    crpix_cutout: list[float]
    wcs_valid: bool
    partial: bool
    output_filename: str   # filename only — no server path
    bunit: str | None = None
    source_hdu: str
    processing_note: str


# ── Helpers ────────────────────────────────────────────────────────

def _resolve_obs(observation_id: str) -> str:
    """Return the FITS URL for a known observation, or raise 404."""
    if observation_id != KNOWN_OBS_ID:
        raise HTTPException(
            status_code=404,
            detail=f"Observation '{observation_id}' not found. "
                   f"Only '{KNOWN_OBS_ID}' is currently confirmed.",
        )
    return KNOWN_FITS_URL


def _hdu_info_to_summary(h: fs.HduInfo) -> HduSummary:
    wcs = None
    if h.wcs_summary:
        wcs = WcsSummary(**{k: v for k, v in h.wcs_summary.items()
                            if k in WcsSummary.model_fields})
    return HduSummary(
        index=h.index, extname=h.extname, hdu_type=h.hdu_type,
        has_data=h.has_data, naxis=h.naxis, shape=h.shape,
        bitpix=h.bitpix, dtype=h.dtype, bunit=h.bunit,
        table_columns=h.table_columns, wcs_summary=wcs, notes=h.notes,
    )


def _service_error(e: Exception) -> HTTPException:
    msg = str(e)
    if "not in the trusted host list" in msg or "Only http/https" in msg:
        return HTTPException(status_code=403, detail=msg)
    if "not found" in msg.lower() or "no IMAGE" in msg:
        return HTTPException(status_code=404, detail=msg)
    logger.error(
        "FITS service request failed",
        exc_info=(type(e), e, e.__traceback__),
    )
    return HTTPException(
        status_code=502,
        detail="FITS service temporarily unavailable. Please try again.",
    )


# ── Endpoints ──────────────────────────────────────────────────────

@router.get("/inspect", response_model=FitsInspectResponse,
            summary="Inspect FITS structure for the known observation")
async def inspect_fits(
    observation_id: Annotated[str, Query(description="Observation ID")] = KNOWN_OBS_ID,
) -> FitsInspectResponse:
    """
    Inspect all HDUs of the confirmed SPHEREx FITS product.
    Uses byte-range header read — does NOT download the full 65 MB file.
    """
    url = _resolve_obs(observation_id)
    logger.info("FITS inspect: %s (byte-range header)", observation_id)
    try:
        result = fs.inspect_fits(url, observation_id, load_pixels=False)
    except Exception as e:
        raise _service_error(e) from e

    if result.error and not result.reachable:
        raise HTTPException(
            status_code=502,
            detail="Confirmed FITS product is temporarily unavailable.",
        )

    return FitsInspectResponse(
        obs_id=result.obs_id,
        reachable=result.reachable,
        header_readable=result.header_readable,
        hdus_inspected=result.hdus_inspected,
        pixel_data_loaded=result.pixel_data_loaded,
        hdu_count=result.hdu_count,
        hdus=[_hdu_info_to_summary(h) for h in result.hdus],
        primary_image_hdu_index=result.primary_image_hdu_index,
        access_method=result.access_method,
        error=result.error,
    )


@router.get("/{observation_id}/headers", response_model=HeadersResponse,
            summary="Return structured FITS headers for all HDUs")
async def get_headers(observation_id: str) -> HeadersResponse:
    """
    Return serialised FITS headers for every HDU, including HISTORY and COMMENT records.
    Uses byte-range header read.
    """
    url = _resolve_obs(observation_id)
    logger.info("FITS headers: %s", observation_id)
    try:
        result = fs.inspect_fits(url, observation_id, load_pixels=False)
    except Exception as e:
        raise _service_error(e) from e

    if not result.header_readable:
        raise HTTPException(
            status_code=502,
            detail="FITS headers are temporarily unavailable.",
        )

    hdu_headers = []
    for h in result.hdus:
        cards = [HeaderCard(**c) for c in h.header.get("cards", [])]
        hdu_headers.append(HduHeaders(
            index=h.index, extname=h.extname,
            cards=cards,
            history=h.header.get("history", []),
            comments=h.header.get("comments", []),
        ))

    return HeadersResponse(obs_id=observation_id, hdus=hdu_headers)


@router.get("/{observation_id}/wcs", response_model=WcsResponse,
            summary="Return WCS metadata for the IMAGE extension")
async def get_wcs(observation_id: str) -> WcsResponse:
    """
    Return WCS information extracted from the IMAGE extension header.
    Includes pixel scale, reference coordinates, and image centre.
    Uses byte-range header read.
    """
    url = _resolve_obs(observation_id)
    logger.info("FITS WCS: %s", observation_id)
    try:
        result = fs.inspect_fits(url, observation_id, load_pixels=False)
    except Exception as e:
        raise _service_error(e) from e

    if not result.hdus_inspected:
        raise HTTPException(
            status_code=502,
            detail="FITS HDU inspection is temporarily unavailable.",
        )

    image_hdu = next(
        (h for h in result.hdus if h.extname == "IMAGE" and h.wcs_summary),
        None,
    )
    if image_hdu is None:
        raise HTTPException(status_code=404, detail="IMAGE extension with WCS not found")

    wcs_data = image_hdu.wcs_summary or {}
    wcs_model = WcsSummary(**{k: v for k, v in wcs_data.items()
                               if k in WcsSummary.model_fields})
    return WcsResponse(obs_id=observation_id, source_hdu="IMAGE", wcs=wcs_model)


@router.get("/{observation_id}/pixel-to-sky", response_model=PixelToSkyResponse,
            summary="Convert FITS pixel coordinates to sky coordinates")
async def pixel_to_sky(
    observation_id: str,
    x: Annotated[float, Query(ge=1, le=2040, description="FITS pixel X (1-based)")],
    y: Annotated[float, Query(ge=1, le=2040, description="FITS pixel Y (1-based)")],
) -> PixelToSkyResponse:
    """
    Convert FITS 1-based pixel (x, y) to ICRS sky coordinates using IMAGE WCS.
    Requires full FITS download (cached after first call).
    """
    url = _resolve_obs(observation_id)
    logger.info("pixel→sky: %s x=%.1f y=%.1f", observation_id, x, y)
    try:
        result = fs.pixel_to_sky(url, x, y)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail="The requested pixel-to-sky conversion could not be completed.",
        ) from e
    except Exception as e:
        raise _service_error(e) from e

    return PixelToSkyResponse(obs_id=observation_id, **result)


@router.get("/{observation_id}/sky-to-pixel", response_model=SkyToPixelResponse,
            summary="Convert sky coordinates to FITS pixel coordinates")
async def sky_to_pixel(
    observation_id: str,
    ra: Annotated[float, Query(ge=0, lt=360, description="Right Ascension (degrees)")],
    dec: Annotated[float, Query(ge=-90, le=90, description="Declination (degrees)")],
) -> SkyToPixelResponse:
    """
    Convert ICRS sky coordinates to FITS 1-based pixel (x, y) using IMAGE WCS.
    Requires full FITS download (cached after first call).
    """
    url = _resolve_obs(observation_id)
    logger.info("sky→pixel: %s ra=%.4f dec=%.4f", observation_id, ra, dec)
    try:
        result = fs.sky_to_pixel(url, ra, dec)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail="The requested sky-to-pixel conversion could not be completed.",
        ) from e
    except Exception as e:
        raise _service_error(e) from e

    return SkyToPixelResponse(obs_id=observation_id, **result)


@router.post("/{observation_id}/cutout", response_model=CutoutResponse,
             summary="Generate a coordinate-aware cutout from the IMAGE extension")
async def generate_cutout(
    observation_id: str,
    req: CutoutRequest,
) -> CutoutResponse:
    """
    Generate a Cutout2D from the IMAGE extension centred on (RA, Dec).
    WCS is correctly translated. Original data is unchanged.
    Requires full FITS download (cached after first call).
    Returns metadata and output filename — not raw pixel data.
    """
    url = _resolve_obs(observation_id)
    logger.info(
        "Cutout: %s ra=%.4f dec=%.4f %dx%d",
        observation_id, req.ra, req.dec, req.width_px, req.height_px,
    )
    try:
        result = fs.extract_cutout(url, observation_id, req.ra, req.dec,
                                   req.width_px, req.height_px)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail="The requested cutout could not be generated.",
        ) from e
    except Exception as e:
        raise _service_error(e) from e

    return CutoutResponse(
        obs_id=result.obs_id,
        ra=result.ra, dec=result.dec,
        width_px=result.width_px, height_px=result.height_px,
        actual_shape=result.actual_shape,
        center_x_fits=result.center_x_fits, center_y_fits=result.center_y_fits,
        crpix_parent=result.crpix_parent, crpix_cutout=result.crpix_cutout,
        wcs_valid=result.wcs_valid, partial=result.partial,
        output_filename=result.output_path,
        bunit=result.bunit, source_hdu=result.source_hdu,
        processing_note=result.processing_note,
    )


# ── Milestone 5: image rendering endpoints ─────────────────────────

from fastapi.responses import Response


class ImageInfoResponse(BaseModel):
    obs_id: str
    source_hdu: str
    naxis1: int
    naxis2: int
    dtype: str
    bunit: str | None = None
    data_min: float
    data_max: float
    data_mean: float
    data_median: float
    nan_count: int
    inf_count: int
    total_pixels: int
    wcs_valid: bool
    pixel_scale_arcsec: float | None = None


@router.get(
    "/{observation_id}/image-info",
    response_model=ImageInfoResponse,
    summary="Return statistical metadata for the IMAGE HDU",
)
async def get_image_info(observation_id: str) -> ImageInfoResponse:
    """
    Return pixel statistics and metadata for the IMAGE extension.
    Requires full FITS download (cached after first call).
    Does not modify original data.
    """
    url = _resolve_obs(observation_id)
    logger.info("image-info: %s", observation_id)
    try:
        r = fs.get_image_info(url, observation_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail="IMAGE metadata could not be read.",
        ) from e
    except Exception as e:
        raise _service_error(e) from e
    return ImageInfoResponse(
        obs_id=r.obs_id, source_hdu=r.source_hdu,
        naxis1=r.naxis1, naxis2=r.naxis2,
        dtype=r.dtype, bunit=r.bunit,
        data_min=r.data_min, data_max=r.data_max,
        data_mean=r.data_mean, data_median=r.data_median,
        nan_count=r.nan_count, inf_count=r.inf_count,
        total_pixels=r.total_pixels,
        wcs_valid=r.wcs_valid,
        pixel_scale_arcsec=r.pixel_scale_arcsec,
    )


@router.get(
    "/{observation_id}/preview",
    summary="Render a PNG preview of the IMAGE HDU",
    response_class=Response,
    responses={
        200: {"content": {"image/png": {}}, "description": "PNG preview image"},
        400: {"description": "Invalid parameters"},
        404: {"description": "Observation not found"},
        502: {"description": "FITS access error"},
    },
)
async def get_preview(
    observation_id: str,
    stretch: Annotated[
        str,
        Query(description="Stretch algorithm: linear | log | asinh | zscale"),
    ] = "zscale",
    size: Annotated[
        int,
        Query(ge=64, le=1024, description="Output image size in pixels (square)"),
    ] = 512,
) -> Response:
    """
    Render a PNG preview of the SPHEREx IMAGE HDU.

    - Stretch affects display only; original FITS pixel values are unchanged.
    - NaN pixels are masked to zero in the display.
    - Colormap: inferno.
    - Previews are cached per (observation, stretch, size).
    - Requires full FITS download (~62 MB, cached after first call).
    """
    url = _resolve_obs(observation_id)
    logger.info("preview: %s stretch=%s size=%d", observation_id, stretch, size)
    try:
        result = fs.render_preview(url, observation_id, stretch=stretch, size=size)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail="The requested preview could not be generated.",
        ) from e
    except Exception as e:
        raise _service_error(e) from e

    headers = {
        "X-Obs-Id": result.obs_id,
        "X-Source-Hdu": result.source_hdu,
        "X-Stretch": result.stretch,
        "X-Vmin": str(result.vmin),
        "X-Vmax": str(result.vmax),
        "X-Bunit": result.bunit or "",
        "X-Nan-Count": str(result.nan_count),
        "X-From-Cache": str(result.from_cache).lower(),
        "X-Note": result.note[:200],
        "Cache-Control": "public, max-age=3600",
    }
    return Response(content=result.png_bytes, media_type="image/png", headers=headers)





# ── Milestone 6: Time Machine comparison metadata ──────────────────

class EpochMeta(BaseModel):
    obs_id: str
    date_obs: str | None = None
    detector: str | None = None
    mission: str
    data_release: str
    ra: float
    dec: float
    naxis1: int | None = None
    naxis2: int | None = None
    bunit: str | None = None
    pixel_scale_arcsec: float | None = None
    wcs_valid: bool
    available: bool
    is_real: bool
    unavailable_reason: str | None = None


class CompatibilityCheck(BaseModel):
    name: str
    status: str   # CONFIRMED | NOT_CHECKED | FAILED | PENDING
    note: str | None = None


class CompareMetaResponse(BaseModel):
    epoch_a: EpochMeta
    epoch_b: EpochMeta | None = None
    epochs_available: int
    comparison_possible: bool
    compatibility_checks: list[CompatibilityCheck]
    scientific_note: str


@router.get(
    "/{observation_id}/compare-meta",
    response_model=CompareMetaResponse,
    summary="Return comparison metadata for Time Machine (single or dual epoch)",
)
async def get_compare_meta(observation_id: str) -> CompareMetaResponse:
    """
    Return structured metadata for the Time Machine comparison view.
    Epoch A is the confirmed SPHEREx observation.
    Epoch B is not yet identified — returns comparison_possible=False with explanation.
    Does NOT require full FITS download.
    """
    _resolve_obs(observation_id)

    from app.services.irsa import CONFIRMED_METADATA

    m = CONFIRMED_METADATA
    epoch_a = EpochMeta(
        obs_id=m["obs_id"],
        date_obs=m["date_obs"],
        detector=m["detector"],
        mission=m["mission"],
        data_release=m["data_release"],
        ra=m["ra"],
        dec=m["dec"],
        naxis1=m["naxis1"],
        naxis2=m["naxis2"],
        bunit=m["bunit"],
        pixel_scale_arcsec=m["pixel_scale_arcsec"],
        wcs_valid=True,
        available=True,
        is_real=True,
    )

    checks = [
        CompatibilityCheck(name="Epoch A available", status="CONFIRMED"),
        CompatibilityCheck(name="Epoch B available", status="PENDING",
                           note="No second SPHEREx observation confirmed yet"),
        CompatibilityCheck(name="Same detector", status="NOT_CHECKED"),
        CompatibilityCheck(name="Same wavelength band", status="NOT_CHECKED"),
        CompatibilityCheck(name="Overlapping footprint", status="NOT_CHECKED"),
        CompatibilityCheck(
            name="WCS alignment", status="NOT_CHECKED",
            note="Epoch A uses the product TAN-SIP header; astrometry is not independently calibrated",
        ),
        CompatibilityCheck(name="Calibration compatible", status="NOT_CHECKED"),
    ]

    return CompareMetaResponse(
        epoch_a=epoch_a,
        epoch_b=None,
        epochs_available=1,
        comparison_possible=False,
        compatibility_checks=checks,
        scientific_note=(
            "Multi-epoch comparison requires two scientifically compatible observations "
            "with verified detector, wavelength, calibration, and WCS compatibility. "
            "Only one SPHEREx DR1 observation has been confirmed (2025W17_4B_0001_1, "
            "24 April 2025). A second epoch has not yet been identified. Epoch A sky "
            "coordinates come from the FITS header and are not independently calibrated."
        ),
    )
