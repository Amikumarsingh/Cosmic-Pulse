"""
Unit tests for COSMIC PULSE backend — Milestone 6.
Time Machine comparison metadata endpoint.

All tests are deterministic — no network access required.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.irsa import KNOWN_OBS_ID, CONFIRMED_METADATA

client = TestClient(app)

URL = f"/api/fits/{KNOWN_OBS_ID}/compare-meta"


# ── 1. HTTP basics ─────────────────────────────────────────────────

def test_compare_meta_200():
    r = client.get(URL)
    assert r.status_code == 200


def test_compare_meta_content_type():
    r = client.get(URL)
    assert "application/json" in r.headers["content-type"]


def test_compare_meta_unknown_obs_404():
    r = client.get("/api/fits/FAKE_OBS_999/compare-meta")
    assert r.status_code == 404


# ── 2. Top-level response fields ───────────────────────────────────

def test_compare_meta_epochs_available():
    data = client.get(URL).json()
    assert data["epochs_available"] == 1


def test_compare_meta_comparison_not_possible():
    data = client.get(URL).json()
    assert data["comparison_possible"] is False


def test_compare_meta_epoch_b_is_null():
    data = client.get(URL).json()
    assert data["epoch_b"] is None


def test_compare_meta_has_scientific_note():
    data = client.get(URL).json()
    note = data["scientific_note"]
    assert isinstance(note, str) and len(note) > 20


def test_compare_meta_scientific_note_mentions_single_epoch():
    data = client.get(URL).json()
    assert "one" in data["scientific_note"].lower() or "only" in data["scientific_note"].lower()


# ── 3. Epoch A metadata ────────────────────────────────────────────

def test_epoch_a_obs_id():
    data = client.get(URL).json()
    assert data["epoch_a"]["obs_id"] == KNOWN_OBS_ID


def test_epoch_a_is_real():
    data = client.get(URL).json()
    assert data["epoch_a"]["is_real"] is True


def test_epoch_a_available():
    data = client.get(URL).json()
    assert data["epoch_a"]["available"] is True


def test_epoch_a_wcs_valid():
    data = client.get(URL).json()
    assert data["epoch_a"]["wcs_valid"] is True


def test_epoch_a_ra_matches_confirmed():
    data = client.get(URL).json()
    assert abs(data["epoch_a"]["ra"] - CONFIRMED_METADATA["ra"]) < 1e-4


def test_epoch_a_dec_matches_confirmed():
    data = client.get(URL).json()
    assert abs(data["epoch_a"]["dec"] - CONFIRMED_METADATA["dec"]) < 1e-4


def test_epoch_a_mission():
    data = client.get(URL).json()
    assert data["epoch_a"]["mission"] == "SPHEREx"


def test_epoch_a_data_release():
    data = client.get(URL).json()
    assert data["epoch_a"]["data_release"] == "DR1"


def test_epoch_a_detector():
    data = client.get(URL).json()
    assert data["epoch_a"]["detector"] == "D1"


def test_epoch_a_bunit():
    data = client.get(URL).json()
    assert data["epoch_a"]["bunit"] == "MJy / sr"


def test_epoch_a_pixel_scale_reasonable():
    data = client.get(URL).json()
    ps = data["epoch_a"]["pixel_scale_arcsec"]
    assert ps is not None
    assert 5.5 < ps < 6.5


def test_epoch_a_naxis():
    data = client.get(URL).json()
    assert data["epoch_a"]["naxis1"] == 2040
    assert data["epoch_a"]["naxis2"] == 2040


# ── 4. Compatibility checks ────────────────────────────────────────

def test_compatibility_checks_present():
    data = client.get(URL).json()
    checks = data["compatibility_checks"]
    assert isinstance(checks, list)
    assert len(checks) >= 5


def test_epoch_a_check_confirmed():
    data = client.get(URL).json()
    checks = {c["name"]: c["status"] for c in data["compatibility_checks"]}
    assert checks.get("Epoch A available") == "CONFIRMED"


def test_epoch_b_check_pending():
    data = client.get(URL).json()
    checks = {c["name"]: c["status"] for c in data["compatibility_checks"]}
    assert checks.get("Epoch B available") == "PENDING"


def test_wcs_alignment_not_checked():
    data = client.get(URL).json()
    checks = {c["name"]: c["status"] for c in data["compatibility_checks"]}
    assert checks.get("WCS alignment") == "NOT_CHECKED"


# ── 5. Regression: M4 + M5 endpoints unaffected ───────────────────

def test_m5_image_info_still_registered():
    """Smoke: image-info route still exists after M6 additions."""
    r = client.get(f"/api/fits/FAKE_999/image-info")
    assert r.status_code == 404   # 404 = route exists, obs not found


def test_m5_preview_still_registered():
    """Smoke: preview route still exists after M6 additions."""
    r = client.get(f"/api/fits/FAKE_999/preview")
    assert r.status_code == 404
