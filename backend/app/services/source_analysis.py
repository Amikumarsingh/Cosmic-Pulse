"""
Source detection and aperture photometry service — Milestone 6.

Algorithm (pure NumPy / SciPy — photutils blocked by Application Control policy):

1. Background estimation
   - Divide image into box_size × box_size tiles.
   - Compute sigma-clipped median per tile (3σ, 5 iterations).
   - Linearly interpolate tile medians back to full image size → background map.
   - Background RMS estimated as σ_clipped MAD × 1.4826 per tile, same interpolation.

2. Source detection
   - Subtract background map from data.
   - Mask NaN/Inf pixels.
   - Threshold: background_subtracted > nsigma × rms_map.
   - Connected-component labelling (scipy.ndimage.label, 8-connectivity).
   - Reject components with area < npixels_min.

3. Source catalogue
   - Centroid: intensity-weighted centre of mass (scipy.ndimage.center_of_mass).
   - Bounding box: scipy.ndimage.find_objects.
   - Area: pixel count per label.
   - Peak flux: max pixel value in segment.

4. Aperture photometry
   - Circular aperture of radius aperture_radius pixels centred on centroid.
   - Aperture sum on background-subtracted data.
   - Flux is unavailable if the aperture crosses an image edge or contains
     non-finite pixels.
   - No uncertainty reported: VARIANCE extension semantics unverified for this
     product; reporting a number would be scientifically misleading.

5. WCS
   - Pixel → sky via pure-Python TAN/TAN-SIP implementation.

Scientific integrity notes:
- ZODI is NOT subtracted. Background estimation removes a smooth component but
  does not separate zodiacal light from astrophysical background.
- FLAGS is co-indexed with IMAGE but its bit definitions are not verified;
  flagged pixels are not masked in this implementation.
- All flux values are in the BUNIT of the IMAGE HDU.
- Results are cached per (obs_id, parameters) to avoid redundant computation.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from scipy.ndimage import label as ndi_label
from scipy.ndimage import find_objects as ndi_find_objects
from scipy.ndimage import zoom as ndi_zoom
from scipy.interpolate import RegularGridInterpolator

from astropy.io import fits

logger = logging.getLogger(__name__)

_result_lock = threading.Lock()

# ── Background estimation ──────────────────────────────────────────

def _sigma_clip_stats(
    arr: np.ndarray, sigma: float = 3.0, maxiters: int = 5
) -> tuple[float, float]:
    """Return (median, mad_std) of arr after iterative sigma clipping."""
    data = arr[np.isfinite(arr)]
    if data.size == 0:
        return 0.0, 0.0
    for _ in range(maxiters):
        med = float(np.median(data))
        mad = float(np.median(np.abs(data - med)))
        std = mad * 1.4826
        if std == 0:
            break
        data = data[np.abs(data - med) <= sigma * std]
        if data.size == 0:
            break
    med = float(np.median(data)) if data.size > 0 else 0.0
    mad = float(np.median(np.abs(data - med))) if data.size > 0 else 0.0
    return med, mad * 1.4826


def estimate_background(
    data: np.ndarray,
    box_size: int = 64,
    sigma: float = 3.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Estimate 2D background and RMS maps via tiled sigma-clipped statistics.

    Returns (background_map, rms_map) both with same shape as data.
    """
    ny, nx = data.shape
    ny_boxes = max(1, math.ceil(ny / box_size))
    nx_boxes = max(1, math.ceil(nx / box_size))

    bkg_grid = np.zeros((ny_boxes, nx_boxes), dtype=np.float64)
    rms_grid = np.zeros((ny_boxes, nx_boxes), dtype=np.float64)

    for iy in range(ny_boxes):
        for ix in range(nx_boxes):
            y0 = iy * box_size
            y1 = min(ny, y0 + box_size)
            x0 = ix * box_size
            x1 = min(nx, x0 + box_size)
            tile = data[y0:y1, x0:x1]
            if not np.isfinite(tile).any():
                bkg_grid[iy, ix] = np.nan
                rms_grid[iy, ix] = np.nan
                continue
            med, rms = _sigma_clip_stats(tile.ravel(), sigma=sigma)
            bkg_grid[iy, ix] = med
            rms_grid[iy, ix] = max(rms, 1e-30)  # avoid zero RMS

    # Fill empty tiles from the median valid tile rather than making an
    # invalid region look like zero-valued background.
    valid_tiles = np.isfinite(bkg_grid) & np.isfinite(rms_grid)
    if valid_tiles.any():
        bkg_grid[~valid_tiles] = float(np.median(bkg_grid[valid_tiles]))
        rms_grid[~valid_tiles] = float(np.median(rms_grid[valid_tiles]))
    else:
        bkg_grid.fill(0.0)
        rms_grid.fill(0.0)

    # Interpolate grid back to full image size
    if ny_boxes == 1 and nx_boxes == 1:
        bkg_map = np.full(data.shape, bkg_grid[0, 0], dtype=np.float32)
        rms_map = np.full(data.shape, rms_grid[0, 0], dtype=np.float32)
    else:
        # Grid centres in pixel coordinates
        y_centres = np.array([
            (min(ny, (i + 1) * box_size) + i * box_size - 1) / 2
            for i in range(ny_boxes)
        ])
        x_centres = np.array([
            (min(nx, (i + 1) * box_size) + i * box_size - 1) / 2
            for i in range(nx_boxes)
        ])

        bkg_interp = RegularGridInterpolator(
            (y_centres, x_centres), bkg_grid,
            method="linear", bounds_error=False, fill_value=None,
        )
        rms_interp = RegularGridInterpolator(
            (y_centres, x_centres), rms_grid,
            method="linear", bounds_error=False, fill_value=None,
        )
        yy, xx = np.mgrid[0:ny, 0:nx]
        pts = np.column_stack([
            np.clip(yy.ravel(), y_centres[0], y_centres[-1]),
            np.clip(xx.ravel(), x_centres[0], x_centres[-1]),
        ])
        bkg_map = bkg_interp(pts).reshape(ny, nx).astype(np.float32)
        rms_map = rms_interp(pts).reshape(ny, nx).astype(np.float32)

    return bkg_map, rms_map


# ── Source detection ───────────────────────────────────────────────

def _circular_aperture_mask(radius: float) -> np.ndarray:
    """Return a boolean mask for a circular aperture of given radius."""
    r = int(math.ceil(radius))
    size = 2 * r + 1
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return (x ** 2 + y ** 2) <= radius ** 2


def _aperture_sum(
    data: np.ndarray, cx: float, cy: float, radius: float,
) -> float | None:
    """Sum a circular aperture; return None when edge or invalid pixels truncate it."""
    x0 = math.floor(cx - radius)
    y0 = math.floor(cy - radius)
    x1 = math.ceil(cx + radius)
    y1 = math.ceil(cy + radius)
    yy, xx = np.ogrid[y0:y1 + 1, x0:x1 + 1]
    mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius ** 2
    ny, nx = data.shape
    inside = (xx >= 0) & (xx < nx) & (yy >= 0) & (yy < ny)
    if np.any(mask & ~inside):
        return None
    valid_x0 = max(0, x0)
    valid_y0 = max(0, y0)
    valid_x1 = min(nx, x1 + 1)
    valid_y1 = min(ny, y1 + 1)
    sub = data[valid_y0:valid_y1, valid_x0:valid_x1]
    sub_mask = mask[
        valid_y0 - y0:valid_y1 - y0,
        valid_x0 - x0:valid_x1 - x0,
    ]
    vals = sub[sub_mask]
    if not np.all(np.isfinite(vals)):
        return None
    return float(vals.sum())


# ── Dataclasses ────────────────────────────────────────────────────

@dataclass
class DetectedSource:
    source_id: int
    label: int
    # Centroid in 0-based pixel coords (x=col, y=row)
    x_centroid: float
    y_centroid: float
    # FITS 1-based pixel coords
    x_fits: float
    y_fits: float
    # Sky coordinates from the product TAN-SIP WCS
    ra_deg: float | None
    dec_deg: float | None
    wcs_approximate: bool
    # Morphology
    area_px: int
    peak_flux: float
    bbox_x0: int
    bbox_y0: int
    bbox_x1: int
    bbox_y1: int
    # Photometry
    aperture_radius_px: float
    aperture_flux: float | None
    bunit: str | None
    # No uncertainty: VARIANCE semantics unverified


@dataclass
class AnalysisResult:
    obs_id: str
    source_hdu: str
    # Parameters used
    nsigma: float
    npixels_min: int
    aperture_radius_px: float
    box_size: int
    # Background stats
    bkg_median: float
    bkg_rms_median: float
    # Detection results
    n_sources: int
    sources: list[DetectedSource]
    # Image info
    naxis1: int
    naxis2: int
    bunit: str | None
    nan_count: int
    # Provenance
    from_cache: bool
    scientific_notes: list[str]
    sources_capped: bool = False


# ── Cache ──────────────────────────────────────────────────────────

def _analysis_cache_key(obs_id: str, nsigma: float, npixels_min: int,
                         aperture_radius_px: float, box_size: int,
                         max_sources: int = 500) -> str:
    s = (
        f"source-analysis-v2|{obs_id}|{nsigma}|{npixels_min}|"
        f"{aperture_radius_px}|{box_size}|{max_sources}"
    )
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def _analysis_cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"analysis_{key}.json"


def _load_cached(path: Path) -> AnalysisResult | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
        sources = [DetectedSource(**s) for s in raw.pop("sources")]
        return AnalysisResult(**raw, sources=sources)
    except Exception as e:
        logger.warning("Cache load failed: %s", e)
        return None


def _save_cached(path: Path, result: AnalysisResult) -> None:
    try:
        d = {k: v for k, v in result.__dict__.items() if k != "sources"}
        d["sources"] = [s.__dict__ for s in result.sources]
        path.write_text(json.dumps(d))
    except Exception as e:
        logger.warning("Cache save failed: %s", e)


# ── Main analysis function ─────────────────────────────────────────

def run_source_analysis(
    fits_path: Path,
    obs_id: str,
    nsigma: float = 3.0,
    npixels_min: int = 5,
    aperture_radius_px: float = 3.0,
    box_size: int = 64,
    cache_dir: Path | None = None,
    max_sources: int = 500,
) -> AnalysisResult:
    """
    Run background estimation, source detection, and aperture photometry
    on the IMAGE HDU of a FITS file.

    Parameters
    ----------
    fits_path : Path to the cached FITS file (full download required).
    obs_id : Observation identifier (for provenance).
    nsigma : Detection threshold in units of background RMS.
    npixels_min : Minimum connected pixels for a valid source.
    aperture_radius_px : Circular aperture radius in pixels.
    box_size : Tile size for background estimation.
    cache_dir : Directory for JSON result cache. None = no caching.
    max_sources : Cap on returned sources (brightest by peak flux).
    """
    if nsigma <= 0:
        raise ValueError(f"nsigma must be > 0, got {nsigma}")
    if npixels_min < 1:
        raise ValueError(f"npixels_min must be >= 1, got {npixels_min}")
    if aperture_radius_px < 0.5:
        raise ValueError(f"aperture_radius_px must be >= 0.5, got {aperture_radius_px}")
    if box_size < 4:
        raise ValueError(f"box_size must be >= 4, got {box_size}")

    # Check cache
    if cache_dir is not None:
        key = _analysis_cache_key(
            obs_id, nsigma, npixels_min, aperture_radius_px, box_size, max_sources
        )
        cache_path = _analysis_cache_path(cache_dir, key)
        with _result_lock:
            cached = _load_cached(cache_path)
        if cached is not None:
            cached.from_cache = True
            return cached

    # Load IMAGE HDU
    with fits.open(str(fits_path), memmap=True, mode="readonly") as hdul:
        image_hdu = None
        for hdu in hdul:
            if hdu.header.get("EXTNAME") == "IMAGE" and hdu.data is not None:
                image_hdu = hdu
                break
        if image_hdu is None:
            raise ValueError("No IMAGE extension with data found in FITS file")
        data = image_hdu.data.astype(np.float32)
        header = image_hdu.header.copy()
        bunit = header.get("BUNIT") or None

    naxis2, naxis1 = data.shape
    nan_count = int(np.sum(~np.isfinite(data)))

    # Background estimation
    bkg_map, rms_map = estimate_background(data, box_size=box_size)
    bkg_median = float(np.median(bkg_map))
    bkg_rms_median = float(np.median(rms_map))

    # Background subtraction
    sub = data - bkg_map
    # Mask non-finite pixels
    finite_mask = np.isfinite(sub)
    sub_clean = np.where(finite_mask, sub, 0.0)

    # Threshold and detect
    threshold_map = nsigma * rms_map
    detection_mask = (sub_clean > threshold_map) & finite_mask

    # Connected-component labelling (8-connectivity)
    struct = np.ones((3, 3), dtype=np.int32)
    labeled, n_labels = ndi_label(detection_mask, structure=struct)

    # Filter by minimum area
    if n_labels > 0:
        areas = np.bincount(labeled.ravel())[1:]  # skip background label 0
        valid_labels = np.where(areas >= npixels_min)[0] + 1  # 1-based
    else:
        valid_labels = np.array([], dtype=np.int64)

    # Extract WCS params for coordinate conversion
    from app.services.fits_service import _extract_wcs_params, _tan_pixel_to_sky
    wcs_params = _extract_wcs_params(header)

    sources: list[DetectedSource] = []
    slices_all = ndi_find_objects(labeled) if n_labels > 0 else []

    for lbl in valid_labels:
        sl = slices_all[lbl - 1]  # (slice_y, slice_x)
        if sl is None:
            continue
        sy, sx = sl
        # Centroid (intensity-weighted, 0-based)
        seg_mask = labeled[sl] == lbl
        segment_values = sub_clean[sl][seg_mask]
        local_y, local_x = np.nonzero(seg_mask)
        weight_sum = float(segment_values.sum())
        cy = float(sy.start + np.dot(local_y, segment_values) / weight_sum)
        cx = float(sx.start + np.dot(local_x, segment_values) / weight_sum)
        area = int(segment_values.size)
        peak = float(np.max(segment_values))

        # Bounding box (0-based, inclusive)
        bbox_y0 = sy.start
        bbox_y1 = sy.stop - 1
        bbox_x0 = sx.start
        bbox_x1 = sx.stop - 1

        # FITS 1-based coords
        x_fits = cx + 1.0
        y_fits = cy + 1.0

        # Sky coords
        ra_deg: float | None = None
        dec_deg: float | None = None
        if wcs_params is not None:
            try:
                ra_deg, dec_deg = _tan_pixel_to_sky(
                    x_fits, y_fits,
                    wcs_params["crpix1"], wcs_params["crpix2"],
                    wcs_params["crval1"], wcs_params["crval2"],
                    wcs_params["cd"],
                    wcs_params["sip_a"], wcs_params["sip_b"],
                )
            except Exception as e:
                logger.warning(
                    "WCS conversion failed for source at FITS pixel (%.3f, %.3f): %s",
                    x_fits, y_fits, e,
                )

        # Aperture photometry on background-subtracted data
        ap_flux = _aperture_sum(sub_clean, cx, cy, aperture_radius_px)

        sources.append(DetectedSource(
            source_id=len(sources) + 1,
            label=int(lbl),
            x_centroid=float(cx),
            y_centroid=float(cy),
            x_fits=x_fits,
            y_fits=y_fits,
            ra_deg=ra_deg,
            dec_deg=dec_deg,
            wcs_approximate=wcs_params is not None,
            area_px=area,
            peak_flux=peak,
            bbox_x0=bbox_x0,
            bbox_y0=bbox_y0,
            bbox_x1=bbox_x1,
            bbox_y1=bbox_y1,
            aperture_radius_px=aperture_radius_px,
            aperture_flux=ap_flux,
            bunit=bunit,
        ))

    # Keep the exact qualifying count separate from the returned catalogue cap.
    n_sources = len(sources)
    sources_capped = n_sources > max_sources

    # Sort by peak flux descending, cap at max_sources
    sources.sort(key=lambda s: s.peak_flux, reverse=True)
    sources = sources[:max_sources]
    # Re-number source_id after sort/cap
    for i, s in enumerate(sources):
        s.source_id = i + 1

    notes = [
        "Background estimated via sigma-clipped tiled median (box_size="
        f"{box_size}px, 3σ, 5 iterations). Smooth component only — "
        "zodiacal light NOT separately subtracted.",
        "FLAGS is a co-indexed 2040×2040 integer mask but is not applied because "
        "the individual flag-bit definitions and exclusion policy are unverified.",
        "Flux values are background-subtracted aperture sums in IMAGE HDU units "
        f"({bunit or 'unknown'}). No calibration corrections applied.",
        "Pixel coordinates (0-based image and 1-based FITS) are distinct from "
        "sky coordinates. RA/Dec use the IMAGE TAN-SIP WCS, including its PC "
        "matrix and SIP distortion; pure-Python results were checked against Astropy. "
        "Astrometric calibration is not independently verified.",
        "Aperture flux is unavailable when an aperture crosses the image edge "
        "or contains non-finite pixels.",
        "No photometric uncertainty reported: VARIANCE extension semantics "
        "unverified. Its header BUNIT is MJy2 / sr2.",
    ]
    if sources_capped:
        notes.append(
            f"{n_sources} qualifying detections found; only the brightest "
            f"{max_sources} by peak flux are included in this catalogue."
        )
    if nan_count > 0:
        notes.append(
            f"{nan_count} NaN/Inf pixels in IMAGE HDU masked to zero before detection."
        )

    result = AnalysisResult(
        obs_id=obs_id,
        source_hdu="IMAGE",
        nsigma=nsigma,
        npixels_min=npixels_min,
        aperture_radius_px=aperture_radius_px,
        box_size=box_size,
        bkg_median=bkg_median,
        bkg_rms_median=bkg_rms_median,
        n_sources=n_sources,
        sources=sources,
        naxis1=naxis1,
        naxis2=naxis2,
        bunit=bunit,
        nan_count=nan_count,
        from_cache=False,
        scientific_notes=notes,
        sources_capped=sources_capped,
    )

    if cache_dir is not None:
        with _result_lock:
            _save_cached(cache_path, result)

    return result
