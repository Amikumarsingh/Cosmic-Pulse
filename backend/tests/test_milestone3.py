"""
Unit tests for COSMIC PULSE backend — Milestone 3.
Uses mocked HTTP responses for deterministic testing.
Live integration tests are in test_live_integration.py (require network).
"""

import json
import math
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import irsa

client = TestClient(app)


# ── Helpers ────────────────────────────────────────────────────────

def _make_access_result(
    status=200, magic=True, byte_range=True, level="FITS_MAGIC_OK", error=None
) -> irsa.ProductAccessResult:
    return irsa.ProductAccessResult(
        url=irsa.KNOWN_FITS_URL,
        http_status=status,
        content_length=65_393_280,
        content_type="application/fits",
        accept_ranges=True,
        byte_range_works=byte_range,
        fits_magic_valid=magic,
        verification_level=level,
        error=error,
    )


def _make_known_record(access=None) -> irsa.ObservationRecord:
    m = irsa.CONFIRMED_METADATA
    return irsa.ObservationRecord(
        obs_id=m["obs_id"], ra=m["ra"], dec=m["dec"],
        date_obs=m["date_obs"], detector=m["detector"],
        mission=m["mission"], data_release=m["data_release"],
        calib_level=m["calib_level"], naxis1=m["naxis1"], naxis2=m["naxis2"],
        bunit=m["bunit"], fits_url=m["fits_url"],
        fits_size_bytes=m["fits_size_bytes"],
        access_result=access or _make_access_result(),
        source="fits_header", is_demo=False,
    )


# ── 1. TAP schema discovery ────────────────────────────────────────

def test_tap_schema_query_parses_correctly():
    """TAP_SCHEMA queries return the 5 known SPHEREx tables."""
    mock_response = {
        "VOTABLE": {
            "RESOURCE_ARRAY": [{
                "TABLE": {
                    "FIELD_ARRAY": [{"<xmlattr>": {"name": "table_name"}}],
                    "DATA": {"TABLEDATA": [
                        ["spherex.obscore"], ["spherex.observation"],
                        ["spherex.plane"], ["spherex.artifact"],
                        ["spherex.provenance_input"],
                    ]},
                }
            }]
        }
    }
    with patch("app.services.irsa.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200, text=json.dumps(mock_response)
        )
        fields, rows, err = irsa._tap_post(
            "SELECT table_name FROM TAP_SCHEMA.tables WHERE table_name LIKE 'spherex%'"
        )
    assert err == ""
    assert len(rows) == 5
    table_names = [r[0] for r in rows]
    assert "spherex.obscore" in table_names
    assert "spherex.artifact" in table_names


# ── 2. Successful observation search ──────────────────────────────

def test_search_includes_known_obs_when_in_cone():
    """Known observation is included when search cone covers its coordinates."""
    known_ra = irsa.CONFIRMED_METADATA["ra"]   # 160.615
    known_dec = irsa.CONFIRMED_METADATA["dec"]  # 30.669

    with patch("app.services.irsa.tap_cone_search", return_value=([], "TAP_TIMEOUT")), \
         patch("app.services.irsa.get_known_observation", return_value=_make_known_record()):
        results, err = irsa.search_observations(known_ra, known_dec, radius_deg=1.0)

    assert len(results) == 1
    assert results[0].obs_id == irsa.KNOWN_OBS_ID
    assert results[0].source == "fits_header"


def test_search_excludes_known_obs_when_outside_cone():
    """Known observation is NOT included when search cone does not cover it."""
    with patch("app.services.irsa.tap_cone_search", return_value=([], "")):
        results, _ = irsa.search_observations(0.0, 0.0, radius_deg=0.1)

    assert all(r.obs_id != irsa.KNOWN_OBS_ID for r in results)


# ── 3. Invalid RA validation ───────────────────────────────────────

def test_search_invalid_ra_too_high():
    r = client.get("/observations/search", params={"ra": 400, "dec": 0})
    assert r.status_code == 422


def test_search_invalid_ra_negative():
    r = client.get("/observations/search", params={"ra": -10, "dec": 0})
    assert r.status_code == 422


# ── 4. Invalid Dec validation ──────────────────────────────────────

def test_search_invalid_dec_too_high():
    r = client.get("/observations/search", params={"ra": 0, "dec": 95})
    assert r.status_code == 422


def test_search_invalid_dec_too_low():
    r = client.get("/observations/search", params={"ra": 0, "dec": -95})
    assert r.status_code == 422


# ── 5. Invalid radius ─────────────────────────────────────────────

def test_search_invalid_radius_zero():
    r = client.get("/observations/search", params={"ra": 0, "dec": 0, "radius": 0})
    assert r.status_code == 422


def test_search_invalid_radius_too_large():
    r = client.get("/observations/search", params={"ra": 0, "dec": 0, "radius": 10})
    assert r.status_code == 422


# ── 6. Empty archive response ─────────────────────────────────────

def test_search_empty_tap_response_outside_cone():
    """Empty TAP + search outside known obs cone → empty results."""
    with patch("app.services.irsa.tap_cone_search", return_value=([], "")):
        r = client.get("/observations/search", params={"ra": 0, "dec": 0, "radius": 0.1})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 0
    assert data["tap_available"] is True


# ── 7. TAP timeout handling ───────────────────────────────────────

def test_search_tap_timeout_returns_gracefully():
    """TAP timeout does not crash the endpoint; known obs still returned if in cone."""
    known_ra = irsa.CONFIRMED_METADATA["ra"]
    known_dec = irsa.CONFIRMED_METADATA["dec"]

    with patch("app.services.irsa.tap_cone_search", return_value=([], "TAP_TIMEOUT")), \
         patch("app.services.irsa.get_known_observation", return_value=_make_known_record()):
        r = client.get("/observations/search",
                       params={"ra": known_ra, "dec": known_dec, "radius": 1.0})

    assert r.status_code == 200
    data = r.json()
    assert data["tap_available"] is False
    assert data["tap_error"] == "TAP_TIMEOUT"
    assert data["count"] >= 1


# ── 8. Observation detail lookup ──────────────────────────────────

def test_get_known_observation_detail():
    with patch("app.services.irsa.get_known_observation", return_value=_make_known_record()):
        r = client.get(f"/observations/{irsa.KNOWN_OBS_ID}")
    assert r.status_code == 200
    data = r.json()
    assert data["obs_id"] == irsa.KNOWN_OBS_ID
    assert abs(data["ra"] - 160.615237739) < 0.001
    assert abs(data["dec"] - 30.6690774567) < 0.001
    assert data["detector"] == "D1"
    assert data["date_obs"] == "2025-04-24T18:01:05.843"
    assert data["naxis1"] == 2040
    assert data["naxis2"] == 2040
    assert data["bunit"] == "MJy / sr"
    assert data["source"] == "fits_header"
    assert data["is_demo"] is False


def test_get_unknown_observation_returns_404():
    with patch("app.services.irsa.get_known_observation", return_value=_make_known_record()):
        r = client.get("/observations/FAKE_OBS_999")
    assert r.status_code == 404


# ── 9. Product URL validation ─────────────────────────────────────

def test_product_url_contains_known_obs_id():
    assert irsa.KNOWN_OBS_ID in irsa.KNOWN_FITS_URL


def test_product_url_is_irsa_ibe():
    assert "irsa.ipac.caltech.edu/ibe" in irsa.KNOWN_FITS_URL


def test_product_url_ends_with_fits():
    assert irsa.KNOWN_FITS_URL.endswith(".fits")


def test_get_products_endpoint():
    with patch("app.services.irsa.check_product_access",
               return_value=_make_access_result()):
        r = client.get(f"/observations/{irsa.KNOWN_OBS_ID}/products")
    assert r.status_code == 200
    products = r.json()
    assert len(products) == 1
    assert products[0]["detector"] == "D1"
    assert "IMAGE" in products[0]["extensions"]
    assert products[0]["access"]["fits_magic_valid"] is True


# ── 10. Repeat observation classification ─────────────────────────

def test_repeat_obs_tap_unavailable_returns_insufficient_metadata():
    with patch("app.services.irsa.tap_cone_search",
               return_value=([], "TAP_TIMEOUT")):
        result = irsa.find_repeat_observations(
            irsa.CONFIRMED_METADATA["ra"],
            irsa.CONFIRMED_METADATA["dec"],
        )
    assert result["classification"] == "INSUFFICIENT_METADATA"
    assert result["tap_available"] is False
    assert result["candidates_found"] == 0


def test_repeat_obs_no_candidates_returns_insufficient_metadata():
    with patch("app.services.irsa.tap_cone_search", return_value=([], "")):
        result = irsa.find_repeat_observations(
            irsa.CONFIRMED_METADATA["ra"],
            irsa.CONFIRMED_METADATA["dec"],
        )
    assert result["classification"] == "INSUFFICIENT_METADATA"
    assert result["tap_available"] is True


def test_repeat_obs_with_candidates_returns_spatial_overlap():
    fake_candidates = [{
        "obs_id": "FAKE_OBS_002",
        "s_ra": irsa.CONFIRMED_METADATA["ra"] + 0.1,
        "s_dec": irsa.CONFIRMED_METADATA["dec"] + 0.1,
        "t_min": 60500.0, "t_max": 60500.1,
        "energy_bandpassname": "band1",
        "calib_level": 2,
        "access_url": "https://example.com/fake.fits",
    }]
    with patch("app.services.irsa.tap_cone_search",
               return_value=(fake_candidates, "")):
        result = irsa.find_repeat_observations(
            irsa.CONFIRMED_METADATA["ra"],
            irsa.CONFIRMED_METADATA["dec"],
        )
    assert result["classification"] == "SPATIAL_OVERLAP_CONFIRMED"
    assert result["candidates_found"] == 1
    assert result["compatibility_checks"]["temporal_separation"] == "NOT_CHECKED"
    assert result["compatibility_checks"]["wcs_alignment"] == "NOT_CHECKED"


def test_repeat_obs_endpoint():
    with patch("app.services.irsa.tap_cone_search",
               return_value=([], "TAP_TIMEOUT")):
        r = client.get(f"/observations/{irsa.KNOWN_OBS_ID}/repeats")
    assert r.status_code == 200
    data = r.json()
    assert data["reference_obs_id"] == irsa.KNOWN_OBS_ID
    assert data["classification"] == "INSUFFICIENT_METADATA"
    assert "scientific_note" in data


# ── 11. Angular separation ────────────────────────────────────────

def test_angular_separation_same_point():
    assert irsa.angular_separation_deg(10.0, 20.0, 10.0, 20.0) == pytest.approx(0.0, abs=1e-10)


def test_angular_separation_known_value():
    # 1 degree separation along RA at Dec=0
    sep = irsa.angular_separation_deg(0.0, 0.0, 1.0, 0.0)
    assert sep == pytest.approx(1.0, abs=0.001)


def test_angular_separation_poles():
    sep = irsa.angular_separation_deg(0.0, 90.0, 180.0, 90.0)
    assert sep == pytest.approx(0.0, abs=1e-6)


# ── 12. Product access model ──────────────────────────────────────

def test_check_product_access_fits_magic_ok():
    """Mock a successful FITS byte-range read."""
    head_mock = MagicMock(
        status_code=200,
        headers={
            "content-length": "65393280",
            "content-type": "application/fits",
            "accept-ranges": "bytes",
        },
    )
    get_mock = MagicMock(
        status_code=206,
        content=b"SIMPLE" + b" " * 2874,
    )
    with patch("app.services.irsa.httpx.head", return_value=head_mock), \
         patch("app.services.irsa.httpx.get", return_value=get_mock):
        result = irsa.check_product_access(irsa.KNOWN_FITS_URL)

    assert result.http_status == 200
    assert result.fits_magic_valid is True
    assert result.byte_range_works is True
    assert result.verification_level == "FITS_MAGIC_OK"
    assert result.content_length == 65_393_280
    assert result.accept_ranges is True


def test_check_product_access_timeout():
    import httpx as _httpx
    with patch("app.services.irsa.httpx.head", side_effect=_httpx.TimeoutException("timeout")):
        result = irsa.check_product_access(irsa.KNOWN_FITS_URL)
    assert result.error == "TIMEOUT"
    assert result.fits_magic_valid is False
    assert result.verification_level == "URL_EXISTS"


# ── 13. Health endpoint ───────────────────────────────────────────

def test_health_endpoint():
    with patch("app.routers.health.check_product_access",
               return_value=_make_access_result()):
        r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["backend_milestone"] == 6
    assert data["fits_accessible"] is True
    assert data["fits_verification_level"] == "FITS_MAGIC_OK"


def test_liveness_endpoint_does_not_probe_irsa():
    with patch("app.routers.health.check_product_access") as check_access:
        r = client.get("/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    check_access.assert_not_called()


def test_cors_preflight_allows_local_frontend():
    r = client.options(
        "/live",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_archive_health_endpoint():
    with patch("app.routers.health.check_product_access",
               return_value=_make_access_result()):
        r = client.get("/archive/health")
    assert r.status_code == 200
    data = r.json()
    assert data["irsa_tap_data"] == "not_checked"
    assert "fits_magic_valid" in data


# ── 14. Confirmed metadata integrity ─────────────────────────────

def test_confirmed_metadata_ra_in_range():
    ra = irsa.CONFIRMED_METADATA["ra"]
    assert 0 <= ra < 360


def test_confirmed_metadata_dec_in_range():
    dec = irsa.CONFIRMED_METADATA["dec"]
    assert -90 <= dec <= 90


def test_confirmed_metadata_obs_id_matches_known():
    assert irsa.CONFIRMED_METADATA["obs_id"] == "2025W17_4B_0001_1"


def test_confirmed_metadata_date_obs_format():
    date_obs = irsa.CONFIRMED_METADATA["date_obs"]
    assert date_obs.startswith("2025-04-24")


def test_confirmed_metadata_image_size():
    assert irsa.CONFIRMED_METADATA["naxis1"] == 2040
    assert irsa.CONFIRMED_METADATA["naxis2"] == 2040


def test_confirmed_metadata_bunit():
    assert irsa.CONFIRMED_METADATA["bunit"] == "MJy / sr"
