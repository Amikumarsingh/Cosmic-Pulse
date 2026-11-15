"""
Unit tests for COSMIC PULSE backend — Milestone 5.
FITS image rendering: PNG preview, stretch algorithms, image-info endpoint.

All tests are deterministic — no network access required.
Live IRSA tests are in test_live_integration.py.
"""
from __future__ import annotations

import io
import struct
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from astropy.io import fits
from fastapi.testclient import TestClient

from app.main import app
from app.services import fits_service as fs
from app.services.irsa import KNOWN_OBS_ID, KNOWN_FITS_URL

client = TestClient(app)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


# ── Fixtures ───────────────────────────────────────────────────────

def _make_wcs_header(naxis1=2040, naxis2=2040, ra=160.615, dec=30.669) -> fits.Header:
    h = fits.Header()
    h["NAXIS"] = 2
    h["NAXIS1"] = naxis1
    h["NAXIS2"] = naxis2
    h["CTYPE1"] = "RA---TAN"
    h["CTYPE2"] = "DEC--TAN"
    h["CRPIX1"] = naxis1 / 2.0 + 0.5
    h["CRPIX2"] = naxis2 / 2.0 + 0.5
    h["CRVAL1"] = ra
    h["CRVAL2"] = dec
    h["CDELT1"] = -6.2e-5
    h["CDELT2"] = 6.2e-5
    h["BUNIT"] = "MJy"
    return h


def _make_image_fits(data: np.ndarray | None = None) -> bytes:
    """Build a minimal FITS with a real IMAGE HDU."""
    if data is None:
        rng = np.random.default_rng(42)
        data = rng.standard_normal((256, 256)).astype(np.float32)
    hdul = fits.HDUList([fits.PrimaryHDU()])
    img_hdu = fits.ImageHDU(data=data, name="IMAGE")
    wcs_h = _make_wcs_header(naxis1=data.shape[1], naxis2=data.shape[0])
    for k, v in wcs_h.items():
        if k not in ("NAXIS", "NAXIS1", "NAXIS2", "SIMPLE", "EXTEND"):
            img_hdu.header[k] = v
    img_hdu.header["BITPIX"] = -32
    hdul.append(img_hdu)
    buf = io.BytesIO()
    hdul.writeto(buf)
    return buf.getvalue()


@pytest.fixture(scope="module")
def image_fits_path(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("fits5")
    p = d / "image.fits"
    p.write_bytes(_make_image_fits())
    return p


@pytest.fixture(scope="module")
def nan_fits_path(tmp_path_factory) -> Path:
    """FITS with NaN and Inf pixels."""
    d = tmp_path_factory.mktemp("fits5nan")
    rng = np.random.default_rng(7)
    data = rng.standard_normal((128, 128)).astype(np.float32)
    data[0, 0] = float("nan")
    data[1, 1] = float("inf")
    data[2, 2] = float("-inf")
    p = d / "nan.fits"
    p.write_bytes(_make_image_fits(data))
    return p


@pytest.fixture(scope="module")
def flat_fits_path(tmp_path_factory) -> Path:
    """FITS with all-zero data (edge case for stretch)."""
    d = tmp_path_factory.mktemp("fits5flat")
    data = np.zeros((64, 64), dtype=np.float32)
    p = d / "flat.fits"
    p.write_bytes(_make_image_fits(data))
    return p


# ── 1. render_preview — basic PNG output ──────────────────────────

@pytest.mark.parametrize("stretch", ["linear", "log", "asinh", "zscale"])
def test_render_preview_returns_png(image_fits_path, stretch):
    with patch("app.services.fits_service._download_fits", return_value=image_fits_path):
        result = fs.render_preview(KNOWN_FITS_URL, KNOWN_OBS_ID, stretch=stretch, size=128)
    assert result.png_bytes[:8] == PNG_MAGIC
    assert len(result.png_bytes) > 500
    assert result.stretch == stretch
    assert result.width_px == 128
    assert result.height_px == 128
    assert result.source_hdu == "IMAGE"
    assert result.obs_id == KNOWN_OBS_ID


def test_render_preview_default_stretch(image_fits_path):
    with patch("app.services.fits_service._download_fits", return_value=image_fits_path):
        result = fs.render_preview(KNOWN_FITS_URL, KNOWN_OBS_ID)
    assert result.stretch == "zscale"
    assert result.width_px == 512


def test_render_preview_bunit_preserved(image_fits_path, tmp_path):
    with patch("app.services.fits_service._cache_dir", return_value=tmp_path):
        with patch("app.services.fits_service._download_fits", return_value=image_fits_path):
            result = fs.render_preview(KNOWN_FITS_URL, KNOWN_OBS_ID, stretch="linear")
    assert result.bunit == "MJy"


def test_render_preview_vmin_lt_vmax(image_fits_path, tmp_path):
    with patch("app.services.fits_service._cache_dir", return_value=tmp_path):
        with patch("app.services.fits_service._download_fits", return_value=image_fits_path):
            result = fs.render_preview(KNOWN_FITS_URL, KNOWN_OBS_ID, stretch="zscale")
    assert result.vmin < result.vmax


# ── 2. NaN / Inf handling ──────────────────────────────────────────

def test_render_preview_nan_pixels(nan_fits_path, tmp_path):
    with patch("app.services.fits_service._cache_dir", return_value=tmp_path):
        with patch("app.services.fits_service._download_fits", return_value=nan_fits_path):
            result = fs.render_preview(KNOWN_FITS_URL, KNOWN_OBS_ID, stretch="zscale", size=64)
    assert result.png_bytes[:8] == PNG_MAGIC
    assert result.nan_count > 0


def test_render_preview_all_zero(flat_fits_path):
    """All-zero image should not raise; returns a valid PNG."""
    with patch("app.services.fits_service._download_fits", return_value=flat_fits_path):
        result = fs.render_preview(KNOWN_FITS_URL, KNOWN_OBS_ID, stretch="linear", size=64)
    assert result.png_bytes[:8] == PNG_MAGIC


# ── 3. Invalid parameters ──────────────────────────────────────────

def test_render_preview_invalid_stretch():
    with pytest.raises(ValueError, match="Invalid stretch"):
        fs.render_preview(KNOWN_FITS_URL, KNOWN_OBS_ID, stretch="gamma")


def test_render_preview_size_too_small():
    with pytest.raises(ValueError, match="size must be"):
        fs.render_preview(KNOWN_FITS_URL, KNOWN_OBS_ID, size=10)


def test_render_preview_size_too_large():
    with pytest.raises(ValueError, match="size must be"):
        fs.render_preview(KNOWN_FITS_URL, KNOWN_OBS_ID, size=2000)


def test_render_preview_invalid_url():
    with pytest.raises(ValueError, match="trusted host"):
        fs.render_preview("https://evil.com/bad.fits", KNOWN_OBS_ID)


# ── 4. Preview cache ───────────────────────────────────────────────

def test_render_preview_cache_hit(image_fits_path, tmp_path):
    with patch("app.services.fits_service._cache_dir", return_value=tmp_path):
        with patch("app.services.fits_service._download_fits", return_value=image_fits_path):
            r1 = fs.render_preview(KNOWN_FITS_URL, KNOWN_OBS_ID, stretch="linear", size=64)
            r2 = fs.render_preview(KNOWN_FITS_URL, KNOWN_OBS_ID, stretch="linear", size=64)
    assert r1.from_cache is False
    assert r2.from_cache is True
    assert r1.png_bytes == r2.png_bytes


# ── 5. get_image_info ──────────────────────────────────────────────

def test_get_image_info_basic(image_fits_path):
    with patch("app.services.fits_service._download_fits", return_value=image_fits_path):
        info = fs.get_image_info(KNOWN_FITS_URL, KNOWN_OBS_ID)
    assert info.naxis1 == 256
    assert info.naxis2 == 256
    assert info.dtype == "float32"
    assert info.bunit == "MJy"
    assert info.total_pixels == 256 * 256
    assert info.nan_count == 0
    assert info.inf_count == 0
    assert info.data_min < info.data_max
    assert info.source_hdu == "IMAGE"
    assert info.wcs_valid is True
    assert info.pixel_scale_arcsec is not None
    assert 0.1 < info.pixel_scale_arcsec < 1.0


def test_get_image_info_nan_count(nan_fits_path):
    with patch("app.services.fits_service._download_fits", return_value=nan_fits_path):
        info = fs.get_image_info(KNOWN_FITS_URL, KNOWN_OBS_ID)
    assert info.nan_count >= 1
    assert info.inf_count >= 2


# ── 6. _apply_stretch internals ────────────────────────────────────

@pytest.mark.parametrize("stretch", ["linear", "log", "asinh", "zscale"])
def test_apply_stretch_output_range(stretch):
    rng = np.random.default_rng(0)
    data = rng.standard_normal((100, 100)).astype(np.float32)
    normed, vmin, vmax = fs._apply_stretch(data, stretch)
    assert normed.shape == data.shape
    assert float(normed.min()) >= 0.0
    assert float(normed.max()) <= 1.0 + 1e-6
    assert vmin < vmax


def test_apply_stretch_all_nan():
    data = np.full((10, 10), float("nan"), dtype=np.float32)
    normed, vmin, vmax = fs._apply_stretch(data, "zscale")
    assert normed.shape == (10, 10)
    assert vmin == 0.0
    assert vmax == 1.0


def test_apply_stretch_does_not_modify_original():
    data = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    original = data.copy()
    fs._apply_stretch(data, "linear")
    np.testing.assert_array_equal(data, original)


# ── 7. API endpoints ───────────────────────────────────────────────

def test_api_preview_endpoint_returns_png(image_fits_path):
    with patch("app.services.fits_service._download_fits", return_value=image_fits_path):
        r = client.get(f"/api/fits/{KNOWN_OBS_ID}/preview",
                       params={"stretch": "zscale", "size": 128})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == PNG_MAGIC
    assert r.headers.get("x-source-hdu") == "IMAGE"
    assert r.headers.get("x-stretch") == "zscale"


def test_api_preview_all_stretches(image_fits_path):
    for stretch in ["linear", "log", "asinh", "zscale"]:
        with patch("app.services.fits_service._download_fits", return_value=image_fits_path):
            r = client.get(f"/api/fits/{KNOWN_OBS_ID}/preview",
                           params={"stretch": stretch, "size": 64})
        assert r.status_code == 200, f"stretch={stretch} failed"
        assert r.content[:8] == PNG_MAGIC


def test_api_preview_invalid_stretch():
    r = client.get(f"/api/fits/{KNOWN_OBS_ID}/preview",
                   params={"stretch": "gamma", "size": 128})
    assert r.status_code == 400


def test_api_preview_size_out_of_range():
    r = client.get(f"/api/fits/{KNOWN_OBS_ID}/preview",
                   params={"stretch": "zscale", "size": 9999})
    assert r.status_code == 422


def test_api_preview_unknown_obs():
    r = client.get("/api/fits/FAKE_999/preview")
    assert r.status_code == 404


def test_api_image_info_endpoint(image_fits_path):
    with patch("app.services.fits_service._download_fits", return_value=image_fits_path):
        r = client.get(f"/api/fits/{KNOWN_OBS_ID}/image-info")
    assert r.status_code == 200
    data = r.json()
    assert data["obs_id"] == KNOWN_OBS_ID
    assert data["source_hdu"] == "IMAGE"
    assert data["naxis1"] == 256
    assert data["naxis2"] == 256
    assert data["dtype"] == "float32"
    assert data["bunit"] == "MJy"
    assert data["total_pixels"] == 256 * 256
    assert data["nan_count"] == 0
    assert data["wcs_valid"] is True
    assert data["pixel_scale_arcsec"] is not None


def test_api_image_info_unknown_obs():
    r = client.get("/api/fits/FAKE_999/image-info")
    assert r.status_code == 404


# ── 8. Regression: M3+M4 still pass ───────────────────────────────

def test_m4_inspect_still_works():
    """Smoke test: M4 inspect endpoint unaffected by M5 additions."""
    from tests.test_milestone4 import _headers_from_fits_bytes, _make_test_fits
    fits_bytes = _make_test_fits()
    with patch(
        "app.services.fits_service._fetch_hdu_headers",
        return_value=_headers_from_fits_bytes(fits_bytes),
    ):
        r = client.get("/api/fits/inspect", params={"observation_id": KNOWN_OBS_ID})
    assert r.status_code == 200
    assert r.json()["hdu_count"] == 7
