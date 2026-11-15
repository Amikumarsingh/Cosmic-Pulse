"""
Live integration tests — require network access to IRSA.
Run separately: pytest tests/test_live_integration.py -v -m live
"""

import pytest
from app.services import irsa

pytestmark = pytest.mark.live


def test_live_fits_head_accessible():
    """FITS file responds to HEAD with HTTP 200."""
    result = irsa.check_product_access(irsa.KNOWN_FITS_URL, timeout=20)
    assert result.http_status == 200, f"Expected 200, got {result.http_status}"


def test_live_fits_byte_range_works():
    """FITS file supports byte-range reads."""
    result = irsa.check_product_access(irsa.KNOWN_FITS_URL, timeout=20)
    assert result.byte_range_works, "Byte-range read failed"


def test_live_fits_magic_valid():
    """First 6 bytes of FITS file are 'SIMPLE'."""
    result = irsa.check_product_access(irsa.KNOWN_FITS_URL, timeout=20)
    assert result.fits_magic_valid, "FITS magic bytes invalid"
    assert result.verification_level == "FITS_MAGIC_OK"


def test_live_fits_size_matches_expected():
    """FITS file size matches the confirmed 65,393,280 bytes."""
    result = irsa.check_product_access(irsa.KNOWN_FITS_URL, timeout=20)
    assert result.content_length == 65_393_280, (
        f"Expected 65393280 bytes, got {result.content_length}"
    )


def test_live_tap_schema_accessible():
    """IRSA TAP_SCHEMA query returns spherex tables."""
    fields, rows, err = irsa._tap_post(
        "SELECT table_name FROM TAP_SCHEMA.tables "
        "WHERE table_name LIKE 'spherex%'",
        timeout=30,
    )
    assert err == "", f"TAP schema query failed: {err}"
    table_names = [r[0] for r in rows]
    assert "spherex.obscore" in table_names


def test_live_known_obs_in_cone_search():
    """Known observation is returned when searching its coordinates."""
    ra = irsa.CONFIRMED_METADATA["ra"]
    dec = irsa.CONFIRMED_METADATA["dec"]
    results, _ = irsa.search_observations(ra, dec, radius_deg=0.5, check_access=False)
    obs_ids = [r.obs_id for r in results]
    assert irsa.KNOWN_OBS_ID in obs_ids, (
        f"Known obs {irsa.KNOWN_OBS_ID} not found in results: {obs_ids}"
    )


def test_live_known_obs_not_in_distant_cone():
    """Known observation is NOT returned when searching far away."""
    results, _ = irsa.search_observations(0.0, 0.0, radius_deg=0.1, check_access=False)
    obs_ids = [r.obs_id for r in results]
    assert irsa.KNOWN_OBS_ID not in obs_ids
