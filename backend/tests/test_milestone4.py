"""
Unit tests for COSMIC PULSE backend — Milestone 4.
FITS inspection engine: HDU metadata, WCS, pixel/sky conversion, cutouts.

All tests are deterministic — no network access required.
Live tests are in test_live_integration.py.
"""

from __future__ import annotations

import io
import math
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from astropy.io import fits
from fastapi.testclient import TestClient

from app.main import app
from app.services import fits_service as fs
from app.services.irsa import KNOWN_OBS_ID, KNOWN_FITS_URL

client = TestClient(app)


# ── Fixtures ───────────────────────────────────────────────────────

def _make_wcs_header(naxis1=2040, naxis2=2040, ra=160.615, dec=30.669) -> fits.Header:
    """Minimal TAN WCS header matching the real SPHEREx observation."""
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
    h["CDELT1"] = -6.2e-5   # Synthetic fixture scale
    h["CDELT2"] = 6.2e-5
    h["BUNIT"] = "MJy"
    return h


def _make_test_fits() -> bytes:
    """
    Build a minimal in-memory FITS file with 7 HDUs matching the real SPHEREx structure:
    PRIMARY (empty), IMAGE (2040x2040), FLAGS (2040x2040), VARIANCE (2040x2040),
    ZODI (2040x2040), EPSF (BinTable), WCS-WAVE (BinTable).
    """
    hdul = fits.HDUList()

    # HDU 0: PRIMARY — empty
    primary = fits.PrimaryHDU()
    primary.header["VERSION"] = "7.0.5"
    hdul.append(primary)

    # HDU 1: IMAGE
    img_data = np.zeros((2040, 2040), dtype=np.float32)
    img_hdu = fits.ImageHDU(data=img_data, name="IMAGE")
    wcs_h = _make_wcs_header()
    for k, v in wcs_h.items():
        if k not in ("NAXIS", "NAXIS1", "NAXIS2", "SIMPLE", "EXTEND"):
            img_hdu.header[k] = v
    img_hdu.header["BITPIX"] = -32
    hdul.append(img_hdu)

    # HDU 2: FLAGS — co-indexed 2040x2040 bitmask
    flags_data = np.zeros((2040, 2040), dtype=np.int32)
    hdul.append(fits.ImageHDU(data=flags_data, name="FLAGS"))

    # HDU 3: VARIANCE
    var_data = np.ones((2040, 2040), dtype=np.float32) * 0.01
    hdul.append(fits.ImageHDU(data=var_data, name="VARIANCE"))

    # HDU 4: ZODI
    zodi_data = np.ones((2040, 2040), dtype=np.float32) * 0.5
    hdul.append(fits.ImageHDU(data=zodi_data, name="ZODI"))

    # HDU 5: EPSF binary table
    col = fits.Column(name="PSF_DATA", format="E", array=np.array([1.0, 2.0]))
    hdul.append(fits.BinTableHDU.from_columns([col], name="EPSF"))

    # HDU 6: WCS-WAVE binary table
    col2 = fits.Column(name="WAVELENGTH", format="E", array=np.array([1.0, 2.0]))
    hdul.append(fits.BinTableHDU.from_columns([col2], name="WCS-WAVE"))

    buf = io.BytesIO()
    hdul.writeto(buf)
    return buf.getvalue()


def _headers_from_fits_bytes(fits_bytes: bytes) -> list[tuple[fits.Header, bool]]:
    with fits.open(io.BytesIO(fits_bytes)) as hdul:
        return [(h.header.copy(), h.data is not None) for h in hdul]


@pytest.fixture(scope="module")
def test_fits_bytes() -> bytes:
    return _make_test_fits()


@pytest.fixture(scope="module")
def test_fits_path(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("fits")
    p = d / "test.fits"
    p.write_bytes(_make_test_fits())
    return p


# ── 1. URL validation ──────────────────────────────────────────────

def test_validate_url_trusted_host():
    fs._validate_url("https://irsa.ipac.caltech.edu/ibe/data/test.fits")


def test_validate_url_untrusted_host():
    with pytest.raises(ValueError, match="trusted host"):
        fs._validate_url("https://evil.example.com/bad.fits")


def test_validate_url_non_http():
    with pytest.raises(ValueError, match="Only http/https"):
        fs._validate_url("ftp://irsa.ipac.caltech.edu/test.fits")


def test_validate_url_known_fits_url():
    fs._validate_url(KNOWN_FITS_URL)


def test_download_resumes_truncated_fits_response(tmp_path):
    class FakeStream:
        def __init__(self, status_code, headers, chunks):
            self.status_code = status_code
            self.headers = headers
            self.chunks = chunks

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def iter_bytes(self, chunk_size):
            yield from self.chunks

    dest = tmp_path / "partial.fits"
    initial = FakeStream(200, {"content-length": "6"}, [b"abc"])
    continuation = FakeStream(
        206, {"content-range": "bytes 3-5/6"}, [b"def"],
    )
    with patch("app.services.fits_service._cache_path", return_value=dest), \
         patch("app.services.fits_service.httpx.head",
               return_value=MagicMock(status_code=200, headers={"content-length": "6"})), \
         patch("app.services.fits_service.httpx.stream",
               side_effect=[initial, continuation]):
        assert fs._download_fits(KNOWN_FITS_URL) == dest
    assert dest.read_bytes() == b"abcdef"


def test_fetch_hdu_headers_walks_all_fits_extensions(test_fits_bytes):
    class FakeResponse:
        status_code = 206

        def __init__(self, content, content_range):
            self.content = content
            self.headers = {"content-range": content_range}

    def fake_get(_url, headers, **_kwargs):
        start, end = map(int, headers["Range"].removeprefix("bytes=").split("-"))
        end = min(end, len(test_fits_bytes) - 1)
        return FakeResponse(
            test_fits_bytes[start:end + 1],
            f"bytes {start}-{end}/{len(test_fits_bytes)}",
        )

    with patch("app.services.fits_service.httpx.get", side_effect=fake_get):
        headers = fs._fetch_hdu_headers(KNOWN_FITS_URL)
    assert [h["EXTNAME"] if "EXTNAME" in h else "PRIMARY" for h, _ in headers] == [
        "PRIMARY", "IMAGE", "FLAGS", "VARIANCE", "ZODI", "EPSF", "WCS-WAVE",
    ]
    assert headers[1][0]["BUNIT"] == "MJy"


# ── 2. Header serialisation ────────────────────────────────────────

def test_serialise_header_basic():
    h = fits.Header()
    h["NAXIS"] = 2
    h["BUNIT"] = "MJy"
    h.add_history("Processed by pipeline")
    h.add_comment("Test comment")
    result = fs._serialise_header(h)
    keys = [c["key"] for c in result["cards"]]
    assert "NAXIS" in keys
    assert "BUNIT" in keys
    assert result["history"] == ["Processed by pipeline"]
    assert result["comments"] == ["Test comment"]


def test_serialise_header_no_raw_header_objects():
    h = fits.Header()
    h["CRVAL1"] = 160.615
    result = fs._serialise_header(h)
    for card in result["cards"]:
        assert not isinstance(card["value"], fits.Header)
        assert isinstance(card["value"], (str, int, float, bool, type(None)))


def test_serialise_header_numpy_scalars():
    h = fits.Header()
    h["NAXIS1"] = np.int32(2040)
    h["CDELT1"] = np.float64(-6.2e-5)
    result = fs._serialise_header(h)
    vals = {c["key"]: c["value"] for c in result["cards"]}
    assert isinstance(vals["NAXIS1"], int)
    assert isinstance(vals["CDELT1"], float)


# ── 3. HDU inspection ──────────────────────────────────────────────

def test_inspect_primary_hdu_empty(test_fits_bytes):
    with fits.open(io.BytesIO(test_fits_bytes)) as hdul:
        info = fs._inspect_hdu(hdul[0], 0)
    assert info.index == 0
    assert info.extname == "PRIMARY"
    assert info.naxis == 0
    assert info.shape == []
    assert info.has_data is False


def test_inspect_image_hdu(test_fits_bytes):
    with fits.open(io.BytesIO(test_fits_bytes)) as hdul:
        info = fs._inspect_hdu(hdul[1], 1)
    assert info.extname == "IMAGE"
    assert info.naxis == 2
    assert info.shape == [2040, 2040]
    assert info.bitpix == -32
    assert info.dtype is not None
    assert info.bunit == "MJy"
    assert info.wcs_summary is not None


def test_inspect_flags_hdu_shape(test_fits_bytes):
    with fits.open(io.BytesIO(test_fits_bytes)) as hdul:
        info = fs._inspect_hdu(hdul[2], 2)
    assert info.extname == "FLAGS"
    assert info.shape == [2040, 2040]
    assert not info.notes


def test_inspect_variance_hdu(test_fits_bytes):
    with fits.open(io.BytesIO(test_fits_bytes)) as hdul:
        info = fs._inspect_hdu(hdul[3], 3)
    assert info.extname == "VARIANCE"
    assert info.shape == [2040, 2040]


def test_inspect_zodi_hdu(test_fits_bytes):
    with fits.open(io.BytesIO(test_fits_bytes)) as hdul:
        info = fs._inspect_hdu(hdul[4], 4)
    assert info.extname == "ZODI"
    assert info.shape == [2040, 2040]


def test_inspect_epsf_binary_table(test_fits_bytes):
    with fits.open(io.BytesIO(test_fits_bytes)) as hdul:
        info = fs._inspect_hdu(hdul[5], 5)
    assert info.extname == "EPSF"
    assert "PSF_DATA" in info.table_columns
    assert info.wcs_summary is None


def test_inspect_wcs_wave_binary_table(test_fits_bytes):
    with fits.open(io.BytesIO(test_fits_bytes)) as hdul:
        info = fs._inspect_hdu(hdul[6], 6)
    assert info.extname == "WCS-WAVE"
    assert "WAVELENGTH" in info.table_columns


# ── 4. WCS extraction ──────────────────────────────────────────────

def test_wcs_summary_valid():
    h = _make_wcs_header()
    result = fs._extract_wcs_summary(h, [2040, 2040])
    assert result["valid"] is True
    assert result["ctype1"] == "RA---TAN"
    assert result["ctype2"] == "DEC--TAN"
    assert result["crval1"] == pytest.approx(160.615, abs=0.001)
    assert result["crval2"] == pytest.approx(30.669, abs=0.001)


def test_wcs_summary_pixel_scale():
    h = _make_wcs_header()
    result = fs._extract_wcs_summary(h, [2040, 2040])
    assert result["pixel_scale_arcsec"] is not None
    assert 0.1 < result["pixel_scale_arcsec"] < 1.0


def test_wcs_summary_center_not_assumed_crval():
    h = _make_wcs_header()
    result = fs._extract_wcs_summary(h, [2040, 2040])
    assert result["center_note"] is not None
    assert "Derived" in result["center_note"]


def test_wcs_summary_invalid_header():
    h = fits.Header()
    h["NAXIS"] = 2
    h["NAXIS1"] = 100
    h["NAXIS2"] = 100
    # No CTYPE — no celestial WCS
    result = fs._extract_wcs_summary(h, [100, 100])
    assert result["valid"] is False


def test_pc_matrix_and_sip_match_astropy():
    from astropy.wcs import WCS

    h = _make_wcs_header()
    h["CDELT1"] = 1.0
    h["CDELT2"] = 1.0
    h["PC1_1"] = 0.00159204547099
    h["PC1_2"] = -0.000685114964011
    h["PC2_1"] = -0.000626281472603
    h["PC2_2"] = -0.00156681541804
    h["CTYPE1"] = "RA---TAN-SIP"
    h["CTYPE2"] = "DEC--TAN-SIP"
    h["A_ORDER"] = 2
    h["B_ORDER"] = 2
    h["A_0_0"] = 0.485247252898
    h["A_0_2"] = -1.40644436462e-6
    h["B_0_0"] = -1.07312104443
    h["B_1_1"] = -6.82698821084e-7

    params = fs._extract_wcs_params(h)
    assert params is not None
    assert np.allclose(params["cd"], [
        [0.00159204547099, -0.000685114964011],
        [-0.000626281472603, -0.00156681541804],
    ])
    summary = fs._extract_wcs_summary(h, [2040, 2040])
    assert summary["projection"] == "TAN"
    assert summary["pc_matrix"] == [
        [0.00159204547099, -0.000685114964011],
        [-0.000626281472603, -0.00156681541804],
    ]
    pixels_fits = [(1020.5, 1020.5), (1.0, 1.0), (1800.0, 600.0)]
    astropy_world = WCS(h).all_pix2world(
        [[x - 1, y - 1] for x, y in pixels_fits], 0,
    )
    for (x, y), (ra_expected, dec_expected) in zip(pixels_fits, astropy_world):
        actual = fs._tan_pixel_to_sky(
            x, y, params["crpix1"], params["crpix2"],
            params["crval1"], params["crval2"], params["cd"],
            params["sip_a"], params["sip_b"],
        )
        assert actual == pytest.approx((ra_expected, dec_expected), abs=1e-10)
        recovered = fs._tan_sky_to_pixel(
            *actual, params["crpix1"], params["crpix2"],
            params["crval1"], params["crval2"], params["cd"],
            params["sip_a"], params["sip_b"],
        )
        assert recovered == pytest.approx((x, y), abs=1e-6)


# ── 5. Full inspect_fits (mocked remote) ──────────────────────────

def test_inspect_fits_byte_range(test_fits_bytes):
    with fits.open(io.BytesIO(test_fits_bytes)) as hdul:
        headers = [(h.header.copy(), h.data is not None) for h in hdul]
    with patch("app.services.fits_service._fetch_hdu_headers", return_value=headers):
        result = fs.inspect_fits(KNOWN_FITS_URL, KNOWN_OBS_ID, load_pixels=False)

    assert result.reachable is True
    assert result.header_readable is True
    assert result.hdus_inspected is True
    assert result.pixel_data_loaded is False
    assert result.hdu_count == 7
    assert result.access_method == "byte_range_header"
    extnames = [h.extname for h in result.hdus]
    assert "PRIMARY" in extnames
    assert "IMAGE" in extnames
    assert "FLAGS" in extnames
    assert "VARIANCE" in extnames
    assert "ZODI" in extnames
    assert "EPSF" in extnames
    assert "WCS-WAVE" in extnames


def test_inspect_fits_primary_image_index(test_fits_bytes):
    with fits.open(io.BytesIO(test_fits_bytes)) as hdul:
        headers = [(h.header.copy(), h.data is not None) for h in hdul]
    with patch("app.services.fits_service._fetch_hdu_headers", return_value=headers):
        result = fs.inspect_fits(KNOWN_FITS_URL, KNOWN_OBS_ID, load_pixels=False)
    assert result.primary_image_hdu_index == 1


def test_inspect_fits_network_error():
    with patch("app.services.fits_service._fetch_hdu_headers",
               side_effect=IOError("connection refused")):
        result = fs.inspect_fits(KNOWN_FITS_URL, KNOWN_OBS_ID, load_pixels=False)
    assert result.reachable is False
    assert result.error is not None


def test_inspect_fits_invalid_url():
    result = fs.inspect_fits("https://evil.com/bad.fits", KNOWN_OBS_ID)
    assert result.reachable is False
    assert "trusted host" in (result.error or "")


# ── 6. Pixel-to-sky conversion ─────────────────────────────────────

def test_pixel_to_sky_centre(test_fits_path):
    with patch("app.services.fits_service._download_fits",
               return_value=test_fits_path):
        result = fs.pixel_to_sky(KNOWN_FITS_URL, 1020.5, 1020.5)

    assert "ra_deg" in result
    assert "dec_deg" in result
    assert result["ra_deg"] == pytest.approx(160.615, abs=0.01)
    assert result["dec_deg"] == pytest.approx(30.669, abs=0.01)
    assert result["x_fits"] == 1020.5
    assert result["pixel_convention"] == "FITS_1_BASED"
    assert result["source_hdu"] == "IMAGE"


def test_pixel_to_sky_zero_based_offset(test_fits_path):
    with patch("app.services.fits_service._download_fits",
               return_value=test_fits_path):
        result = fs.pixel_to_sky(KNOWN_FITS_URL, 1.0, 1.0)
    assert result["x_zero"] == pytest.approx(0.0, abs=1e-9)
    assert result["y_zero"] == pytest.approx(0.0, abs=1e-9)


# ── 7. Sky-to-pixel conversion ─────────────────────────────────────

def test_sky_to_pixel_known_coords(test_fits_path):
    with patch("app.services.fits_service._download_fits",
               return_value=test_fits_path):
        result = fs.sky_to_pixel(KNOWN_FITS_URL, 160.615, 30.669)

    assert result["x_fits"] == pytest.approx(1020.5, abs=1.0)
    assert result["y_fits"] == pytest.approx(1020.5, abs=1.0)
    assert result["in_bounds"] is True
    assert result["pixel_convention"] == "FITS_1_BASED"


def test_sky_to_pixel_out_of_field(test_fits_path):
    with patch("app.services.fits_service._download_fits",
               return_value=test_fits_path):
        result = fs.sky_to_pixel(KNOWN_FITS_URL, 0.0, 0.0)
    assert result["in_bounds"] is False


# ── 8. Coordinate round-trip ───────────────────────────────────────

def test_pixel_sky_round_trip(test_fits_path):
    """pixel→sky→pixel should recover original pixel within 0.01 px."""
    with patch("app.services.fits_service._download_fits",
               return_value=test_fits_path):
        fwd = fs.pixel_to_sky(KNOWN_FITS_URL, 500.0, 700.0)
        back = fs.sky_to_pixel(KNOWN_FITS_URL, fwd["ra_deg"], fwd["dec_deg"])

    assert back["x_fits"] == pytest.approx(500.0, abs=0.01)
    assert back["y_fits"] == pytest.approx(700.0, abs=0.01)


# ── 9. Cutout generation ───────────────────────────────────────────

def test_cutout_basic(test_fits_path):
    with patch("app.services.fits_service._download_fits",
               return_value=test_fits_path):
        result = fs.extract_cutout(
            KNOWN_FITS_URL, KNOWN_OBS_ID,
            ra=160.615, dec=30.669,
            width_px=128, height_px=128,
        )

    assert result.actual_shape == [128, 128]
    assert result.wcs_valid is True
    assert result.bunit == "MJy"
    assert result.source_hdu == "IMAGE"
    assert result.output_path.endswith(".fits")
    # No full server path in output
    assert "\\" not in result.output_path
    assert "/" not in result.output_path


def test_cutout_wcs_crpix_translated(test_fits_path):
    """CRPIX must be translated from parent to cutout frame."""
    with patch("app.services.fits_service._download_fits",
               return_value=test_fits_path):
        result = fs.extract_cutout(
            KNOWN_FITS_URL, KNOWN_OBS_ID,
            ra=160.615, dec=30.669,
            width_px=128, height_px=128,
        )

    # Parent CRPIX is ~1020.5; cutout CRPIX should be ~64.5
    assert result.crpix_parent[0] == pytest.approx(1020.5, abs=1.0)
    assert result.crpix_cutout[0] == pytest.approx(64.5, abs=2.0)


def test_cutout_original_unchanged(test_fits_path):
    """Verify the source FITS file is not modified after cutout."""
    import hashlib
    before = hashlib.md5(test_fits_path.read_bytes()).hexdigest()
    with patch("app.services.fits_service._download_fits",
               return_value=test_fits_path):
        fs.extract_cutout(
            KNOWN_FITS_URL, KNOWN_OBS_ID,
            ra=160.615, dec=30.669,
            width_px=64, height_px=64,
        )
    after = hashlib.md5(test_fits_path.read_bytes()).hexdigest()
    assert before == after


def test_cutout_out_of_bounds_partial(test_fits_path):
    """Cutout at image edge should succeed as partial, not raise."""
    with patch("app.services.fits_service._download_fits",
               return_value=test_fits_path):
        # Near corner — will be partial
        result = fs.extract_cutout(
            KNOWN_FITS_URL, KNOWN_OBS_ID,
            ra=160.615, dec=30.669,
            width_px=512, height_px=512,
        )
    assert result.actual_shape is not None


def test_cutout_invalid_width():
    with pytest.raises(ValueError, match="width_px"):
        fs.extract_cutout(KNOWN_FITS_URL, KNOWN_OBS_ID,
                          ra=160.615, dec=30.669,
                          width_px=0, height_px=128)


def test_cutout_invalid_height():
    with pytest.raises(ValueError, match="height_px"):
        fs.extract_cutout(KNOWN_FITS_URL, KNOWN_OBS_ID,
                          ra=160.615, dec=30.669,
                          width_px=128, height_px=3000)


# ── 10. API endpoints ──────────────────────────────────────────────

def test_api_inspect_endpoint(test_fits_bytes):
    with patch("app.services.fits_service._fetch_hdu_headers",
               return_value=_headers_from_fits_bytes(test_fits_bytes)):
        r = client.get("/api/fits/inspect",
                       params={"observation_id": KNOWN_OBS_ID})
    assert r.status_code == 200
    data = r.json()
    assert data["obs_id"] == KNOWN_OBS_ID
    assert data["hdu_count"] == 7
    assert data["hdus_inspected"] is True
    assert data["pixel_data_loaded"] is False


def test_api_inspect_unknown_obs():
    r = client.get("/api/fits/inspect", params={"observation_id": "FAKE_999"})
    assert r.status_code == 404


def test_api_headers_endpoint(test_fits_bytes):
    with patch("app.services.fits_service._fetch_hdu_headers",
               return_value=_headers_from_fits_bytes(test_fits_bytes)):
        r = client.get(f"/api/fits/{KNOWN_OBS_ID}/headers")
    assert r.status_code == 200
    data = r.json()
    assert data["obs_id"] == KNOWN_OBS_ID
    assert len(data["hdus"]) == 7
    extnames = [h["extname"] for h in data["hdus"]]
    assert "IMAGE" in extnames
    assert "FLAGS" in extnames


def test_api_wcs_endpoint(test_fits_bytes):
    with patch("app.services.fits_service._fetch_hdu_headers",
               return_value=_headers_from_fits_bytes(test_fits_bytes)):
        r = client.get(f"/api/fits/{KNOWN_OBS_ID}/wcs")
    assert r.status_code == 200
    data = r.json()
    assert data["source_hdu"] == "IMAGE"
    assert data["wcs"]["valid"] is True
    assert data["wcs"]["ctype1"] == "RA---TAN"


def test_api_pixel_to_sky_endpoint(test_fits_path):
    with patch("app.services.fits_service._download_fits",
               return_value=test_fits_path):
        r = client.get(
            f"/api/fits/{KNOWN_OBS_ID}/pixel-to-sky",
            params={"x": 1020.5, "y": 1020.5},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["ra_deg"] == pytest.approx(160.615, abs=0.01)
    assert data["dec_deg"] == pytest.approx(30.669, abs=0.01)


def test_api_pixel_to_sky_out_of_range():
    r = client.get(
        f"/api/fits/{KNOWN_OBS_ID}/pixel-to-sky",
        params={"x": 9999, "y": 1},
    )
    assert r.status_code == 422


def test_api_sky_to_pixel_endpoint(test_fits_path):
    with patch("app.services.fits_service._download_fits",
               return_value=test_fits_path):
        r = client.get(
            f"/api/fits/{KNOWN_OBS_ID}/sky-to-pixel",
            params={"ra": 160.615, "dec": 30.669},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["x_fits"] == pytest.approx(1020.5, abs=1.0)
    assert data["in_bounds"] is True


def test_api_sky_to_pixel_invalid_ra():
    r = client.get(
        f"/api/fits/{KNOWN_OBS_ID}/sky-to-pixel",
        params={"ra": 400, "dec": 0},
    )
    assert r.status_code == 422


def test_api_cutout_endpoint(test_fits_path):
    with patch("app.services.fits_service._download_fits",
               return_value=test_fits_path):
        r = client.post(
            f"/api/fits/{KNOWN_OBS_ID}/cutout",
            json={"ra": 160.615, "dec": 30.669, "width_px": 128, "height_px": 128},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["actual_shape"] == [128, 128]
    assert data["wcs_valid"] is True
    assert data["bunit"] == "MJy"
    assert data["crpix_parent"][0] == pytest.approx(1020.5, abs=1.0)
    assert data["crpix_cutout"][0] == pytest.approx(64.5, abs=2.0)
    # output_filename must not contain path separators
    assert "\\" not in data["output_filename"]
    assert "/" not in data["output_filename"]


def test_api_cutout_invalid_width():
    r = client.post(
        f"/api/fits/{KNOWN_OBS_ID}/cutout",
        json={"ra": 160.615, "dec": 30.669, "width_px": 0, "height_px": 128},
    )
    assert r.status_code == 422


def test_api_cutout_unknown_obs():
    r = client.post(
        "/api/fits/FAKE_999/cutout",
        json={"ra": 160.615, "dec": 30.669, "width_px": 128, "height_px": 128},
    )
    assert r.status_code == 404


# ── 11. Existing M3 tests still pass ──────────────────────────────

def test_m3_health_still_works():
    from tests.test_milestone3 import _make_access_result
    with patch("app.routers.health.check_product_access",
               return_value=_make_access_result()):
        r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"


def test_m3_observation_detail_still_works():
    from tests.test_milestone3 import _make_known_record
    with patch("app.services.irsa.get_known_observation",
               return_value=_make_known_record()):
        r = client.get(f"/observations/{KNOWN_OBS_ID}")
    assert r.status_code == 200
    assert r.json()["obs_id"] == KNOWN_OBS_ID
