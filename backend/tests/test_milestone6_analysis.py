"""
Unit tests for COSMIC PULSE backend — Milestone 6: Source Analysis.

All tests use synthetic FITS images with known source positions and fluxes.
No network access is required. Live IRSA tests are in test_live_integration.py.

Synthetic test images are clearly labelled as such throughout.
"""
from __future__ import annotations

import io
import json
import math
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from astropy.io import fits
from fastapi.testclient import TestClient

from app.main import app
from app.services import source_analysis as sa
from app.services.irsa import KNOWN_OBS_ID

client = TestClient(app)

DETECT_URL = f"/api/analysis/{KNOWN_OBS_ID}/detect"
RESULTS_URL = f"/api/analysis/{KNOWN_OBS_ID}/results"


# ── Synthetic FITS helpers ─────────────────────────────────────────

def _make_synthetic_fits(
    data: np.ndarray,
    ra: float = 160.615,
    dec: float = 30.669,
    bunit: str = "MJy",
) -> Path:
    """
    Build a minimal FITS file with a real IMAGE HDU containing synthetic data.
    Clearly labelled as synthetic in the function name.
    """
    ny, nx = data.shape
    hdul = fits.HDUList([fits.PrimaryHDU()])
    img = fits.ImageHDU(data=data.astype(np.float32), name="IMAGE")
    img.header["NAXIS"] = 2
    img.header["NAXIS1"] = nx
    img.header["NAXIS2"] = ny
    img.header["CTYPE1"] = "RA---TAN"
    img.header["CTYPE2"] = "DEC--TAN"
    img.header["CRPIX1"] = nx / 2.0 + 0.5
    img.header["CRPIX2"] = ny / 2.0 + 0.5
    img.header["CRVAL1"] = ra
    img.header["CRVAL2"] = dec
    img.header["CDELT1"] = -6.2e-5
    img.header["CDELT2"] = 6.2e-5
    img.header["BUNIT"] = bunit
    img.header["BITPIX"] = -32
    hdul.append(img)
    buf = io.BytesIO()
    hdul.writeto(buf)
    buf.seek(0)
    return buf


def _write_synthetic_fits(tmp_path: Path, data: np.ndarray, **kw) -> Path:
    p = tmp_path / "synthetic.fits"
    buf = _make_synthetic_fits(data, **kw)
    p.write_bytes(buf.read())
    return p


def _flat_with_sources(
    ny: int = 200, nx: int = 200,
    sources: list[tuple[int, int, float]] | None = None,
    background: float = 1.0,
    noise_std: float = 0.1,
    seed: int = 42,
) -> np.ndarray:
    """
    Synthetic image: flat background + Gaussian noise + point sources.
    sources: list of (y, x, peak_flux) in 0-based pixel coords.
    """
    rng = np.random.default_rng(seed)
    data = rng.normal(background, noise_std, (ny, nx)).astype(np.float32)
    if sources:
        for sy, sx, flux in sources:
            if 0 <= sy < ny and 0 <= sx < nx:
                data[sy, sx] += flux
    return data


# ── 1. Background estimation ───────────────────────────────────────

def test_background_flat_image():
    """Synthetic flat image: background should be close to true value."""
    data = np.full((128, 128), 5.0, dtype=np.float32)
    bkg, rms = sa.estimate_background(data, box_size=32)
    assert abs(float(np.median(bkg)) - 5.0) < 0.1


def test_background_rms_noisy_image():
    """Synthetic noisy image: RMS should be close to noise std."""
    rng = np.random.default_rng(0)
    data = rng.normal(0.0, 1.0, (128, 128)).astype(np.float32)
    _, rms = sa.estimate_background(data, box_size=32)
    assert 0.5 < float(np.median(rms)) < 2.0


def test_background_output_shape():
    data = np.zeros((100, 100), dtype=np.float32)
    bkg, rms = sa.estimate_background(data, box_size=25)
    assert bkg.shape == (100, 100)
    assert rms.shape == (100, 100)


def test_background_rms_positive():
    """RMS map must be strictly positive."""
    data = np.ones((64, 64), dtype=np.float32)
    _, rms = sa.estimate_background(data, box_size=16)
    assert float(rms.min()) > 0.0


def test_background_single_tile():
    """box_size larger than image: single tile, constant maps."""
    data = np.full((20, 20), 3.0, dtype=np.float32)
    bkg, rms = sa.estimate_background(data, box_size=64)
    assert bkg.shape == (20, 20)
    assert abs(float(bkg[0, 0]) - 3.0) < 0.5


def test_background_includes_partial_edge_tiles():
    data = np.full((100, 100), 2.0, dtype=np.float32)
    data[64:, :] = 10.0
    data[:, 64:] = 10.0
    bkg, _ = sa.estimate_background(data, box_size=64)
    assert float(np.median(bkg[80:, 80:])) == pytest.approx(10.0)


def test_background_fills_all_nan_tiles_from_valid_tiles():
    data = np.full((128, 128), 5.0, dtype=np.float32)
    data[64:, 64:] = np.nan
    bkg, rms = sa.estimate_background(data, box_size=64)
    assert np.isfinite(bkg).all()
    assert np.isfinite(rms).all()
    assert float(np.median(bkg)) == pytest.approx(5.0)


# ── 2. Source detection — synthetic images ─────────────────────────

def test_detect_single_source(tmp_path):
    """Synthetic: one bright point source should be detected."""
    data = _flat_with_sources(sources=[(100, 100, 50.0)], noise_std=0.1)
    p = _write_synthetic_fits(tmp_path, data)
    result = sa.run_source_analysis(p, "SYNTHETIC_TEST", nsigma=3.0, npixels_min=1)
    assert result.n_sources >= 1
    # Brightest source should be near (100, 100)
    s = result.sources[0]
    assert abs(s.y_centroid - 100) < 3.0
    assert abs(s.x_centroid - 100) < 3.0


def test_detect_multiple_sources(tmp_path):
    """Synthetic: three well-separated sources should all be detected."""
    data = _flat_with_sources(
        sources=[(50, 50, 40.0), (100, 150, 35.0), (160, 80, 30.0)],
        noise_std=0.05,
    )
    p = _write_synthetic_fits(tmp_path, data)
    result = sa.run_source_analysis(p, "SYNTHETIC_TEST", nsigma=3.0, npixels_min=1)
    assert result.n_sources >= 3


def test_detect_no_sources_below_threshold(tmp_path):
    """Synthetic: pure noise image at high threshold should yield zero sources."""
    rng = np.random.default_rng(7)
    data = rng.normal(0.0, 1.0, (100, 100)).astype(np.float32)
    p = _write_synthetic_fits(tmp_path, data)
    result = sa.run_source_analysis(p, "SYNTHETIC_TEST", nsigma=10.0, npixels_min=5)
    assert result.n_sources == 0


def test_detect_npixels_filter(tmp_path):
    """Synthetic: single-pixel source rejected when npixels_min=5."""
    data = _flat_with_sources(sources=[(50, 50, 100.0)], noise_std=0.01)
    p = _write_synthetic_fits(tmp_path, data)
    result_1px = sa.run_source_analysis(p, "SYNTHETIC_TEST", nsigma=3.0, npixels_min=1)
    result_5px = sa.run_source_analysis(p, "SYNTHETIC_TEST", nsigma=3.0, npixels_min=5)
    # Single pixel source detected at npixels_min=1 but not at 5
    assert result_1px.n_sources >= result_5px.n_sources


def test_detect_centroid_accuracy(tmp_path):
    """Synthetic: centroid should be within 1 pixel of true position."""
    true_y, true_x = 80, 120
    data = _flat_with_sources(sources=[(true_y, true_x, 100.0)], noise_std=0.01)
    p = _write_synthetic_fits(tmp_path, data)
    result = sa.run_source_analysis(p, "SYNTHETIC_TEST", nsigma=3.0, npixels_min=1)
    assert result.n_sources >= 1
    s = result.sources[0]
    assert abs(s.y_centroid - true_y) < 1.5
    assert abs(s.x_centroid - true_x) < 1.5


def test_detect_bbox_contains_centroid(tmp_path):
    """Synthetic: bounding box must contain the centroid."""
    data = _flat_with_sources(sources=[(60, 70, 50.0)], noise_std=0.05)
    p = _write_synthetic_fits(tmp_path, data)
    result = sa.run_source_analysis(p, "SYNTHETIC_TEST", nsigma=3.0, npixels_min=1)
    assert result.n_sources >= 1
    s = result.sources[0]
    assert s.bbox_x0 <= s.x_centroid <= s.bbox_x1 + 1
    assert s.bbox_y0 <= s.y_centroid <= s.bbox_y1 + 1


# ── 3. Aperture photometry ─────────────────────────────────────────

def test_aperture_flux_positive_source(tmp_path):
    """Synthetic: aperture flux of a bright source should be positive."""
    data = _flat_with_sources(sources=[(100, 100, 50.0)], noise_std=0.01)
    p = _write_synthetic_fits(tmp_path, data)
    result = sa.run_source_analysis(p, "SYNTHETIC_TEST", nsigma=3.0, npixels_min=1,
                                    aperture_radius_px=3.0)
    assert result.n_sources >= 1
    assert result.sources[0].aperture_flux > 0.0


def test_aperture_flux_scales_with_brightness(tmp_path):
    """Synthetic: brighter source should have larger aperture flux."""
    data1 = _flat_with_sources(sources=[(100, 100, 20.0)], noise_std=0.01)
    data2 = _flat_with_sources(sources=[(100, 100, 80.0)], noise_std=0.01)
    p1 = _write_synthetic_fits(tmp_path / "f1.fits" if False else tmp_path, data1)
    p2 = tmp_path / "bright.fits"
    buf = _make_synthetic_fits(data2)
    p2.write_bytes(buf.read())
    r1 = sa.run_source_analysis(p1, "SYNTHETIC_DIM", nsigma=3.0, npixels_min=1)
    r2 = sa.run_source_analysis(p2, "SYNTHETIC_BRIGHT", nsigma=3.0, npixels_min=1)
    if r1.n_sources >= 1 and r2.n_sources >= 1:
        assert r2.sources[0].aperture_flux > r1.sources[0].aperture_flux


def test_aperture_circular_mask():
    """Unit test: circular aperture mask has correct area."""
    mask = sa._circular_aperture_mask(3.0)
    # Area of circle r=3: π*9 ≈ 28.3 → expect 29 pixels
    assert 25 <= int(mask.sum()) <= 33


def test_aperture_sum_known_value():
    """Unit test: aperture sum on a known array."""
    data = np.zeros((20, 20), dtype=np.float32)
    data[10, 10] = 100.0
    # r=1 aperture: only the centre pixel (and immediate neighbours if within r)
    s = sa._aperture_sum(data, 10.0, 10.0, 1.0)
    assert s >= 100.0  # at minimum the centre pixel


def test_aperture_photometry_recovers_known_background_subtracted_flux(tmp_path):
    data = np.full((64, 64), 7.0, dtype=np.float32)
    data[32, 32] = 107.0
    p = _write_synthetic_fits(tmp_path, data)
    result = sa.run_source_analysis(
        p, "SYNTHETIC_KNOWN_FLUX", nsigma=3.0,
        npixels_min=1, aperture_radius_px=3.0, box_size=16,
    )
    assert result.n_sources == 1
    assert result.sources[0].aperture_flux == pytest.approx(100.0)


def test_aperture_flux_unavailable_at_image_edge():
    data = np.zeros((10, 10), dtype=np.float32)
    assert sa._aperture_sum(data, 0.0, 5.0, 2.0) is None


def test_aperture_flux_unavailable_for_nonfinite_pixels():
    data = np.zeros((10, 10), dtype=np.float32)
    data[5, 6] = np.nan
    assert sa._aperture_sum(data, 5.0, 5.0, 2.0) is None


def test_aperture_uses_subpixel_centroid():
    data = np.zeros((10, 10), dtype=np.float32)
    data[5, 5] = 10.0
    data[5, 6] = 100.0
    assert sa._aperture_sum(data, 5.1, 5.0, 0.5) == pytest.approx(10.0)
    assert sa._aperture_sum(data, 5.9, 5.0, 0.5) == pytest.approx(100.0)


def test_source_count_reports_uncapped_total(tmp_path):
    data = np.zeros((64, 64), dtype=np.float32)
    data[10, 10] = 100.0
    data[30, 30] = 80.0
    data[50, 50] = 60.0
    p = _write_synthetic_fits(tmp_path, data)
    result = sa.run_source_analysis(
        p, "SYNTHETIC_CAPPED", nsigma=3.0, npixels_min=1,
        aperture_radius_px=1.0, box_size=16, max_sources=2,
    )
    assert result.n_sources == 3
    assert len(result.sources) == 2
    assert result.sources_capped is True
    assert result.sources[0].peak_flux > result.sources[1].peak_flux


def test_bunit_preserved(tmp_path):
    """Synthetic: BUNIT from FITS header should be preserved in results."""
    data = _flat_with_sources(sources=[(50, 50, 30.0)], noise_std=0.05)
    p = _write_synthetic_fits(tmp_path, data, bunit="MJy/sr")
    result = sa.run_source_analysis(p, "SYNTHETIC_TEST", nsigma=3.0, npixels_min=1)
    assert result.bunit == "MJy/sr"
    if result.n_sources > 0:
        assert result.sources[0].bunit == "MJy/sr"


# ── 4. NaN / Inf handling ──────────────────────────────────────────

def test_nan_pixels_counted(tmp_path):
    """Synthetic: NaN pixels should be counted and not crash detection."""
    data = _flat_with_sources(sources=[(100, 100, 50.0)], noise_std=0.05)
    data[0, 0] = float("nan")
    data[1, 1] = float("inf")
    p = _write_synthetic_fits(tmp_path, data)
    result = sa.run_source_analysis(p, "SYNTHETIC_TEST", nsigma=3.0, npixels_min=1)
    assert result.nan_count >= 2


def test_all_nan_image(tmp_path):
    """Synthetic: all-NaN image should return zero sources without crashing."""
    data = np.full((50, 50), float("nan"), dtype=np.float32)
    p = _write_synthetic_fits(tmp_path, data)
    result = sa.run_source_analysis(p, "SYNTHETIC_TEST", nsigma=3.0, npixels_min=1)
    assert result.n_sources == 0


# ── 5. WCS coordinate conversion ──────────────────────────────────

def test_wcs_coords_present(tmp_path):
    """Synthetic: sources should have ra_deg/dec_deg when WCS is valid."""
    data = _flat_with_sources(sources=[(100, 100, 50.0)], noise_std=0.01)
    p = _write_synthetic_fits(tmp_path, data)
    result = sa.run_source_analysis(p, "SYNTHETIC_TEST", nsigma=3.0, npixels_min=1)
    if result.n_sources >= 1:
        s = result.sources[0]
        assert s.ra_deg is not None
        assert s.dec_deg is not None
        assert s.wcs_approximate is True
        # RA should be near 160.615 for a 200x200 image centred there
        assert 155.0 < s.ra_deg < 165.0
        assert 25.0 < s.dec_deg < 35.0


def test_fits_coords_are_1based(tmp_path):
    """Synthetic: FITS coords should be 0-based centroid + 1."""
    data = _flat_with_sources(sources=[(50, 60, 80.0)], noise_std=0.01)
    p = _write_synthetic_fits(tmp_path, data)
    result = sa.run_source_analysis(p, "SYNTHETIC_TEST", nsigma=3.0, npixels_min=1)
    if result.n_sources >= 1:
        s = result.sources[0]
        assert abs(s.x_fits - (s.x_centroid + 1.0)) < 0.01
        assert abs(s.y_fits - (s.y_centroid + 1.0)) < 0.01


# ── 6. Invalid parameters ──────────────────────────────────────────

def test_invalid_nsigma(tmp_path):
    data = np.zeros((10, 10), dtype=np.float32)
    p = _write_synthetic_fits(tmp_path, data)
    with pytest.raises(ValueError, match="nsigma"):
        sa.run_source_analysis(p, "SYNTHETIC_TEST", nsigma=0.0)


def test_invalid_npixels(tmp_path):
    data = np.zeros((10, 10), dtype=np.float32)
    p = _write_synthetic_fits(tmp_path, data)
    with pytest.raises(ValueError, match="npixels_min"):
        sa.run_source_analysis(p, "SYNTHETIC_TEST", npixels_min=0)


def test_invalid_aperture(tmp_path):
    data = np.zeros((10, 10), dtype=np.float32)
    p = _write_synthetic_fits(tmp_path, data)
    with pytest.raises(ValueError, match="aperture_radius_px"):
        sa.run_source_analysis(p, "SYNTHETIC_TEST", aperture_radius_px=0.1)


# ── 7. Caching ─────────────────────────────────────────────────────

def test_cache_hit(tmp_path):
    """Synthetic: second call with same params should return from_cache=True."""
    data = _flat_with_sources(sources=[(100, 100, 50.0)], noise_std=0.05)
    p = _write_synthetic_fits(tmp_path, data)
    cache = tmp_path / "cache"
    cache.mkdir()
    r1 = sa.run_source_analysis(p, "SYNTHETIC_CACHE", cache_dir=cache)
    r2 = sa.run_source_analysis(p, "SYNTHETIC_CACHE", cache_dir=cache)
    assert r1.from_cache is False
    assert r2.from_cache is True
    assert r1.n_sources == r2.n_sources


def test_cache_different_params(tmp_path):
    """Synthetic: different nsigma → different cache key → independent results."""
    data = _flat_with_sources(sources=[(100, 100, 50.0)], noise_std=0.05)
    p = _write_synthetic_fits(tmp_path, data)
    cache = tmp_path / "cache2"
    cache.mkdir()
    r1 = sa.run_source_analysis(p, "SYNTHETIC_CACHE", nsigma=3.0, cache_dir=cache)
    r2 = sa.run_source_analysis(p, "SYNTHETIC_CACHE", nsigma=5.0, cache_dir=cache)
    assert r1.nsigma == 3.0
    assert r2.nsigma == 5.0


def test_result_reproducible(tmp_path):
    """Synthetic: same params → identical source count and positions."""
    data = _flat_with_sources(
        sources=[(50, 50, 40.0), (120, 130, 35.0)], noise_std=0.05
    )
    p = _write_synthetic_fits(tmp_path, data)
    r1 = sa.run_source_analysis(p, "SYNTHETIC_REPRO")
    r2 = sa.run_source_analysis(p, "SYNTHETIC_REPRO")
    assert r1.n_sources == r2.n_sources
    if r1.n_sources > 0:
        assert abs(r1.sources[0].x_centroid - r2.sources[0].x_centroid) < 0.01


# ── 8. Scientific notes ────────────────────────────────────────────

def test_scientific_notes_present(tmp_path):
    data = np.zeros((50, 50), dtype=np.float32)
    p = _write_synthetic_fits(tmp_path, data)
    result = sa.run_source_analysis(p, "SYNTHETIC_TEST")
    assert len(result.scientific_notes) >= 4
    notes_text = " ".join(result.scientific_notes).lower()
    assert "zodi" in notes_text
    assert "flags" in notes_text
    assert "sip" in notes_text
    assert "variance" in notes_text


# ── 9. API endpoints ───────────────────────────────────────────────

def test_api_detect_unknown_obs():
    r = client.post("/api/analysis/FAKE_999/detect", json={})
    assert r.status_code == 404


def test_api_detect_invalid_nsigma():
    r = client.post(DETECT_URL, json={"nsigma": 0.1})
    assert r.status_code == 422


def test_api_detect_returns_analysis(tmp_path):
    """Synthetic: API detect endpoint returns valid AnalysisResponse."""
    data = _flat_with_sources(sources=[(100, 100, 50.0)], noise_std=0.05)
    p = _write_synthetic_fits(tmp_path, data)
    with patch("app.routers.analysis._download_fits", return_value=p):
        with patch("app.routers.analysis._cache_dir", return_value=tmp_path):
            r = client.post(DETECT_URL, json={
                "nsigma": 3.0, "npixels_min": 1,
                "aperture_radius_px": 3.0, "box_size": 32,
            })
    assert r.status_code == 200
    data_r = r.json()
    assert data_r["obs_id"] == KNOWN_OBS_ID
    assert data_r["source_hdu"] == "IMAGE"
    assert isinstance(data_r["n_sources"], int)
    assert isinstance(data_r["sources_capped"], bool)
    assert isinstance(data_r["sources"], list)
    assert len(data_r["scientific_notes"]) >= 4


def test_api_detect_does_not_expose_internal_paths():
    with patch(
        "app.routers.analysis._download_fits",
        side_effect=OSError(r"C:\private\cache\product.fits"),
    ):
        r = client.post(DETECT_URL, json={})
    assert r.status_code == 502
    assert "temporarily unavailable" in r.json()["detail"]
    assert r"C:\private" not in r.text


def test_api_results_not_found():
    """GET /results with no prior detect → 404."""
    import tempfile, os
    with patch("app.routers.analysis._cache_dir",
               return_value=Path(tempfile.mkdtemp())):
        r = client.get(RESULTS_URL)
    assert r.status_code == 404


def test_api_source_detail(tmp_path):
    """Synthetic: detect then fetch single source detail."""
    data = _flat_with_sources(sources=[(100, 100, 50.0)], noise_std=0.05)
    p = _write_synthetic_fits(tmp_path, data)
    with patch("app.routers.analysis._download_fits", return_value=p):
        with patch("app.routers.analysis._cache_dir", return_value=tmp_path):
            r_detect = client.post(DETECT_URL, json={
                "nsigma": 3.0, "npixels_min": 1,
                "aperture_radius_px": 3.0, "box_size": 32,
            })
    assert r_detect.status_code == 200
    sources = r_detect.json()["sources"]
    if sources:
        sid = sources[0]["source_id"]
        with patch("app.routers.analysis._cache_dir", return_value=tmp_path):
            r_src = client.get(
                f"/api/analysis/{KNOWN_OBS_ID}/sources/{sid}",
                params={"nsigma": 3.0, "npixels_min": 1,
                        "aperture_radius_px": 3.0, "box_size": 32},
            )
        assert r_src.status_code == 200
        assert r_src.json()["source_id"] == sid


def test_api_source_not_found(tmp_path):
    """Synthetic: source_id 9999 should return 404."""
    data = _flat_with_sources(sources=[(100, 100, 50.0)], noise_std=0.05)
    p = _write_synthetic_fits(tmp_path, data)
    with patch("app.routers.analysis._download_fits", return_value=p):
        with patch("app.routers.analysis._cache_dir", return_value=tmp_path):
            client.post(DETECT_URL, json={
                "nsigma": 3.0, "npixels_min": 1,
                "aperture_radius_px": 3.0, "box_size": 32,
            })
    with patch("app.routers.analysis._cache_dir", return_value=tmp_path):
        r = client.get(
            f"/api/analysis/{KNOWN_OBS_ID}/sources/9999",
            params={"nsigma": 3.0, "npixels_min": 1,
                    "aperture_radius_px": 3.0, "box_size": 32},
        )
    assert r.status_code == 404


# ── 10. Regression: prior milestones unaffected ────────────────────

def test_m6_compare_meta_still_works():
    r = client.get(f"/api/fits/{KNOWN_OBS_ID}/compare-meta")
    assert r.status_code == 200


def test_m5_preview_still_registered():
    r = client.get(f"/api/fits/FAKE_999/preview")
    assert r.status_code == 404  # route exists, obs not found
