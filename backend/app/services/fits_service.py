"""
FITS inspection service — Milestone 4.

WCS note: astropy.wcs C extension (_wcs.pyd) is blocked by Application Control
policy on this host. WCS is implemented using pure-Python TAN/TAN-SIP projection
math with FITS CD or PC/CDELT matrix conventions.

Security: only TRUSTED_HOSTS URLs accepted; no filesystem paths from callers;
cache paths never exposed in API responses; file-size limit enforced.

Scientific integrity: original FITS data never modified; FLAGS inspected per-HDU;
WCS extracted per-HDU; ZODI not subtracted.
"""
from __future__ import annotations

import hashlib
import io
import logging
import math
import os
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from astropy.io import fits

logger = logging.getLogger(__name__)

TRUSTED_HOSTS = frozenset(["irsa.ipac.caltech.edu"])
MAX_FITS_BYTES = 200 * 1024 * 1024
DOWNLOAD_TIMEOUT = 120
HEADER_TIMEOUT = 20
FITS_BLOCK = 2880
HEADER_BLOCKS = 40

_HTTP_HEADERS = {"User-Agent": "CosmicPulse/4.0 (NASA SpaceApps 2026)"}
_download_locks: dict[str, threading.Lock] = {}
_locks_mutex = threading.Lock()


def _cache_dir() -> Path:
    d = Path(os.environ.get("FITS_CACHE_DIR", tempfile.gettempdir())) / "cosmic_pulse_fits"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(url: str) -> Path:
    h = hashlib.sha256(url.encode()).hexdigest()[:16]
    return _cache_dir() / f"{h}.fits"


def _get_download_lock(url: str) -> threading.Lock:
    with _locks_mutex:
        if url not in _download_locks:
            _download_locks[url] = threading.Lock()
        return _download_locks[url]


def _validate_url(url: str) -> None:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Only http/https URLs are accepted, got: {parsed.scheme!r}")
    host = parsed.netloc.split(":")[0].lower()
    if host not in TRUSTED_HOSTS:
        raise ValueError(
            f"URL host {host!r} is not in the trusted host list. "
            f"Trusted: {sorted(TRUSTED_HOSTS)}"
        )


def _fetch_header_bytes(url: str) -> bytes:
    end = FITS_BLOCK * HEADER_BLOCKS - 1
    r = httpx.get(
        url, timeout=HEADER_TIMEOUT, follow_redirects=True,
        headers={**_HTTP_HEADERS, "Range": f"bytes=0-{end}"},
    )
    if r.status_code not in (200, 206):
        raise IOError(f"Byte-range request failed: HTTP {r.status_code}")
    return r.content


def _fetch_hdu_headers(url: str) -> list[tuple[fits.Header, int]]:
    headers: list[tuple[fits.Header, int]] = []
    offset = 0
    file_size: int | None = None

    for _ in range(128):
        end = offset + FITS_BLOCK * HEADER_BLOCKS - 1
        response = httpx.get(
            url, timeout=HEADER_TIMEOUT, follow_redirects=True,
            headers={**_HTTP_HEADERS, "Range": f"bytes={offset}-{end}"},
        )
        if response.status_code != 206:
            raise IOError(f"FITS header range failed: HTTP {response.status_code}")
        content_range = response.headers.get("content-range", "")
        try:
            range_spec, total = content_range.removeprefix("bytes ").split("/")
            range_start, range_end = map(int, range_spec.split("-"))
            file_size = int(total)
        except (ValueError, TypeError) as e:
            raise IOError(f"Invalid FITS Content-Range: {content_range!r}") from e
        if range_start != offset or range_end < offset or file_size <= range_end:
            raise IOError(f"Unexpected FITS Content-Range: {content_range!r}")

        raw = response.content
        if len(raw) != range_end - range_start + 1:
            raise IOError(
                f"Incomplete FITS header range at byte {offset}: "
                f"received {len(raw)} bytes"
            )
        header_bytes = None
        for start in range(0, len(raw), 80):
            if raw[start:start + 8].strip() == b"END":
                header_bytes = raw[:math.ceil((start + 80) / FITS_BLOCK) * FITS_BLOCK]
                break
        if header_bytes is None:
            raise IOError(f"FITS header at byte {offset} exceeds {HEADER_BLOCKS} blocks")

        header = fits.Header.fromstring(header_bytes.decode("ascii"), sep="")
        headers.append((header, len(header_bytes)))

        naxis = int(header.get("NAXIS", 0))
        axes_size = math.prod(
            int(header.get(f"NAXIS{i}", 0)) for i in range(1, naxis + 1)
        ) if naxis else 0
        bitpix = abs(int(header.get("BITPIX", 8)))
        pcount = int(header.get("PCOUNT", 0))
        gcount = int(header.get("GCOUNT", 1))
        data_size = (bitpix // 8) * gcount * (pcount + axes_size)
        next_offset = offset + len(header_bytes) + math.ceil(data_size / FITS_BLOCK) * FITS_BLOCK
        if next_offset == file_size:
            break
        if next_offset <= offset or next_offset > file_size:
            raise IOError(f"Invalid FITS HDU size at byte {offset}")
        offset = next_offset
    else:
        raise IOError("FITS product contains too many HDUs")

    return headers


def _download_fits(url: str) -> Path:
    dest = _cache_path(url)
    lock = _get_download_lock(url)
    with lock:
        head = httpx.head(
            url, timeout=DOWNLOAD_TIMEOUT, follow_redirects=True, headers=_HTTP_HEADERS
        )
        if head.status_code not in (200, 206):
            raise IOError(f"FITS size check failed: HTTP {head.status_code}")
        expected_size = int(head.headers.get("content-length", 0)) or None
        current_size = dest.stat().st_size if dest.exists() else 0
        if current_size > 0 and (expected_size is None or current_size == expected_size):
            logger.info("FITS cache hit: %s", dest.name)
            return dest
        if expected_size is not None and current_size > expected_size:
            dest.unlink()
            current_size = 0

        logger.info("Downloading FITS: %s -> %s", url, dest.name)
        received = current_size
        if received == 0:
            with httpx.stream("GET", url, timeout=DOWNLOAD_TIMEOUT,
                              follow_redirects=True, headers=_HTTP_HEADERS) as r:
                if r.status_code != 200:
                    raise IOError(f"Download failed: HTTP {r.status_code}")
                content_length = int(r.headers.get("content-length", 0)) or expected_size
                if content_length and content_length > MAX_FITS_BYTES:
                    raise ValueError(f"FITS file too large: {content_length} bytes")
                with open(dest, "wb") as fh:
                    for chunk in r.iter_bytes(chunk_size=65536):
                        received += len(chunk)
                        if received > MAX_FITS_BYTES:
                            dest.unlink(missing_ok=True)
                            raise ValueError(f"Download exceeded {MAX_FITS_BYTES} byte limit")
                        fh.write(chunk)

        while expected_size is not None and received < expected_size:
            start = received
            expected_range = f"bytes {start}-{expected_size - 1}/{expected_size}"
            with httpx.stream(
                "GET", url, timeout=DOWNLOAD_TIMEOUT, follow_redirects=True,
                headers={**_HTTP_HEADERS, "Range": f"bytes={start}-{expected_size - 1}"},
            ) as r:
                if r.status_code != 206 or r.headers.get("content-range") != expected_range:
                    raise IOError(
                        f"FITS continuation failed: expected {expected_range}, "
                        f"got HTTP {r.status_code} {r.headers.get('content-range')}"
                    )
                with open(dest, "ab") as fh:
                    for chunk in r.iter_bytes(chunk_size=65536):
                        received += len(chunk)
                        if received > MAX_FITS_BYTES:
                            dest.unlink(missing_ok=True)
                            raise ValueError(
                                f"Download exceeded {MAX_FITS_BYTES} byte limit"
                            )
                        fh.write(chunk)
            if received == start:
                raise IOError("FITS continuation returned no data")
        if expected_size is not None and received != expected_size:
            raise IOError(
                f"Incomplete FITS download: received {received} of {expected_size} bytes"
            )
        logger.info("Downloaded %d bytes -> %s", received, dest.name)
        return dest


def _serialise_header(header: fits.Header) -> dict[str, Any]:
    cards: list[dict[str, Any]] = []
    history: list[str] = []
    comments: list[str] = []
    for card in header.cards:
        key = card.keyword
        if key == "HISTORY":
            history.append(str(card.value))
            continue
        if key == "COMMENT":
            comments.append(str(card.value))
            continue
        if key in ("", "END"):
            continue
        val = card.value
        if isinstance(val, np.integer):
            val = int(val)
        elif isinstance(val, np.floating):
            val = float(val)
        elif isinstance(val, np.bool_):
            val = bool(val)
        elif hasattr(fits, "card") and isinstance(val, fits.card.Undefined):
            val = None
        cards.append({"key": key, "value": val, "comment": card.comment or ""})
    return {"cards": cards, "history": history, "comments": comments}


# Pure-Python TAN/TAN-SIP (gnomonic) WCS — astropy.wcs C extension blocked on this host.
# Reference: Calabretta & Greisen 2002, A&A 395, 1077.

def _get_cd_matrix(header: fits.Header) -> np.ndarray | None:
    if header.get("CD1_1") is not None:
        return np.array([
            [float(header["CD1_1"]), float(header.get("CD1_2", 0.0))],
            [float(header.get("CD2_1", 0.0)), float(header["CD2_2"])],
        ])
    cdelt1 = header.get("CDELT1")
    cdelt2 = header.get("CDELT2")
    if cdelt1 is not None and cdelt2 is not None:
        if any(header.get(f"PC{i}_{j}") is not None for i in (1, 2) for j in (1, 2)):
            pc = np.array([
                [float(header.get("PC1_1", 1.0)), float(header.get("PC1_2", 0.0))],
                [float(header.get("PC2_1", 0.0)), float(header.get("PC2_2", 1.0))],
            ])
            return np.diag([float(cdelt1), float(cdelt2)]) @ pc
        crota2 = float(header.get("CROTA2", 0.0))
        cos_r = math.cos(math.radians(crota2))
        sin_r = math.sin(math.radians(crota2))
        return np.array([
            [float(cdelt1) * cos_r, -float(cdelt2) * sin_r],
            [float(cdelt1) * sin_r,  float(cdelt2) * cos_r],
        ])
    return None


def _sip_coefficients(header: fits.Header, prefix: str) -> dict[tuple[int, int], float]:
    coefficients: dict[tuple[int, int], float] = {}
    for key in header:
        parts = key.split("_")
        if (len(parts) == 3 and parts[0] == prefix
                and parts[1].isdigit() and parts[2].isdigit()):
            coefficients[(int(parts[1]), int(parts[2]))] = float(header[key])
    return coefficients


def _sip_polynomial(
    u: float, v: float, coefficients: dict[tuple[int, int], float] | None,
) -> float:
    if not coefficients:
        return 0.0
    return sum(coef * u ** i * v ** j for (i, j), coef in coefficients.items())


def _tan_pixel_to_sky(
    x_fits: float, y_fits: float,
    crpix1: float, crpix2: float,
    crval1_deg: float, crval2_deg: float,
    cd: np.ndarray,
    sip_a: dict[tuple[int, int], float] | None = None,
    sip_b: dict[tuple[int, int], float] | None = None,
) -> tuple[float, float]:
    u = x_fits - crpix1
    v = y_fits - crpix2
    dx = u + _sip_polynomial(u, v, sip_a)
    dy = v + _sip_polynomial(u, v, sip_b)
    xi  = cd[0, 0] * dx + cd[0, 1] * dy
    eta = cd[1, 0] * dx + cd[1, 1] * dy
    xi_r  = math.radians(xi)
    eta_r = math.radians(eta)
    ra0  = math.radians(crval1_deg)
    dec0 = math.radians(crval2_deg)
    denom = math.cos(dec0) - eta_r * math.sin(dec0)
    ra_r  = math.atan2(xi_r, denom) + ra0
    dec_r = math.atan2(
        eta_r * math.cos(dec0) + math.sin(dec0),
        math.sqrt(xi_r ** 2 + denom ** 2),
    )
    return math.degrees(ra_r) % 360.0, math.degrees(dec_r)


def _tan_sky_to_pixel(
    ra_deg: float, dec_deg: float,
    crpix1: float, crpix2: float,
    crval1_deg: float, crval2_deg: float,
    cd: np.ndarray,
    sip_a: dict[tuple[int, int], float] | None = None,
    sip_b: dict[tuple[int, int], float] | None = None,
) -> tuple[float, float]:
    ra_r  = math.radians(ra_deg)
    dec_r = math.radians(dec_deg)
    ra0   = math.radians(crval1_deg)
    dec0  = math.radians(crval2_deg)
    dra   = ra_r - ra0
    denom = (math.sin(dec0) * math.sin(dec_r)
             + math.cos(dec0) * math.cos(dec_r) * math.cos(dra))
    if abs(denom) < 1e-15:
        raise ValueError("Coordinate is at or behind the projection plane")
    xi  = math.degrees(math.cos(dec_r) * math.sin(dra) / denom)
    eta = math.degrees(
        (math.cos(dec0) * math.sin(dec_r)
         - math.sin(dec0) * math.cos(dec_r) * math.cos(dra)) / denom
    )
    det = cd[0, 0] * cd[1, 1] - cd[0, 1] * cd[1, 0]
    if abs(det) < 1e-30:
        raise ValueError("CD matrix is singular")
    inv = np.array([[ cd[1, 1], -cd[0, 1]], [-cd[1, 0], cd[0, 0]]]) / det
    distorted_u = inv[0, 0] * xi + inv[0, 1] * eta
    distorted_v = inv[1, 0] * xi + inv[1, 1] * eta
    dx, dy = distorted_u, distorted_v
    for _ in range(50):
        next_dx = distorted_u - _sip_polynomial(dx, dy, sip_a)
        next_dy = distorted_v - _sip_polynomial(dx, dy, sip_b)
        if max(abs(next_dx - dx), abs(next_dy - dy)) < 1e-10:
            dx, dy = next_dx, next_dy
            break
        dx, dy = next_dx, next_dy
    else:
        raise ValueError("SIP inverse did not converge")
    return crpix1 + dx, crpix2 + dy


def _extract_wcs_params(header: fits.Header) -> dict[str, Any] | None:
    ctype1 = str(header.get("CTYPE1", ""))
    ctype2 = str(header.get("CTYPE2", ""))
    if (not ctype1.upper().startswith("RA---TAN")
            or not ctype2.upper().startswith("DEC--TAN")):
        return None
    crpix1 = header.get("CRPIX1")
    crpix2 = header.get("CRPIX2")
    crval1 = header.get("CRVAL1")
    crval2 = header.get("CRVAL2")
    if any(v is None for v in (crpix1, crpix2, crval1, crval2)):
        return None
    cd = _get_cd_matrix(header)
    if cd is None:
        return None
    has_sip = ctype1.upper().endswith("-SIP") and ctype2.upper().endswith("-SIP")
    return {
        "ctype1": ctype1, "ctype2": ctype2,
        "crpix1": float(crpix1), "crpix2": float(crpix2),
        "crval1": float(crval1), "crval2": float(crval2),
        "cd": cd,
        "has_sip": has_sip,
        "sip_a": _sip_coefficients(header, "A") if has_sip else None,
        "sip_b": _sip_coefficients(header, "B") if has_sip else None,
    }


def _extract_wcs_summary(header: fits.Header, shape: list[int]) -> dict[str, Any]:
    # shape is numpy order [rows, cols] = [naxis2, naxis1]
    result: dict[str, Any] = {
        "valid": False,
        "ctype1": header.get("CTYPE1"),
        "ctype2": header.get("CTYPE2"),
        "crpix1": header.get("CRPIX1"),
        "crpix2": header.get("CRPIX2"),
        "crval1": header.get("CRVAL1"),
        "crval2": header.get("CRVAL2"),
        "cdelt1": header.get("CDELT1"),
        "cdelt2": header.get("CDELT2"),
        "cd_matrix": (
            [
                [float(header["CD1_1"]), float(header.get("CD1_2", 0.0))],
                [float(header.get("CD2_1", 0.0)), float(header.get("CD2_2", 0.0))],
            ] if header.get("CD1_1") is not None else None
        ),
        "pc_matrix": (
            [
                [float(header.get("PC1_1", 1.0)), float(header.get("PC1_2", 0.0))],
                [float(header.get("PC2_1", 0.0)), float(header.get("PC2_2", 1.0))],
            ] if any(
                header.get(f"PC{i}_{j}") is not None
                for i in (1, 2) for j in (1, 2)
            ) else None
        ),
        "has_sip": bool(header.get("A_ORDER") or header.get("B_ORDER")),
        "naxis": len(shape),
        "error": None,
        "pixel_scale_deg": None,
        "pixel_scale_arcsec": None,
        "center_ra": None,
        "center_dec": None,
        "center_note": None,
        "projection": None,
    }
    try:
        params = _extract_wcs_params(header)
        if params is None:
            result["error"] = "No celestial WCS found in header"
            return result
        result["valid"] = True
        cd = params["cd"]
        scale1 = math.sqrt(cd[0, 0] ** 2 + cd[1, 0] ** 2)
        scale2 = math.sqrt(cd[0, 1] ** 2 + cd[1, 1] ** 2)
        pscale = (scale1 + scale2) / 2.0
        result["pixel_scale_deg"] = pscale
        result["pixel_scale_arcsec"] = pscale * 3600.0
        if len(shape) >= 2:
            # shape = [naxis2, naxis1]; FITS 1-based centre: x=naxis1/2+0.5, y=naxis2/2+0.5
            cx = shape[1] / 2.0 + 0.5
            cy = shape[0] / 2.0 + 0.5
            try:
                ra, dec = _tan_pixel_to_sky(
                    cx, cy,
                    params["crpix1"], params["crpix2"],
                    params["crval1"], params["crval2"], cd,
                    params["sip_a"], params["sip_b"],
                )
                result["center_ra"] = ra
                result["center_dec"] = dec
                result["center_note"] = "Derived from image centre pixel — not CRVAL"
            except Exception as e:
                result["center_note"] = f"Centre calculation failed: {e}"
        ctype1 = str(result["ctype1"] or "").upper()
        result["projection"] = (
            "TAN" if ctype1.endswith("-SIP") else ctype1.split("-")[-1]
        ) if "-" in ctype1 else None
        if params["has_sip"]:
            result["error"] = (
                "SIP distortion terms are applied by the pure-Python TAN-SIP transform; "
                "the product astrometry has not been independently calibrated."
            )
    except Exception as e:
        result["valid"] = False
        result["error"] = str(e)
    return result


@dataclass
class HduInfo:
    index: int
    extname: str
    hdu_type: str
    has_data: bool
    naxis: int
    shape: list[int]
    bitpix: int | None
    dtype: str | None
    bunit: str | None
    header: dict[str, Any]
    table_columns: list[str]
    wcs_summary: dict[str, Any] | None
    notes: list[str] = field(default_factory=list)


def _inspect_hdu_header(
    header: fits.Header, index: int, hdu_type: str, has_data: bool,
    dtype: str | None = None, table_columns: list[str] | None = None,
) -> HduInfo:
    extname = str(header.get("EXTNAME", "PRIMARY" if index == 0 else f"HDU{index}"))
    naxis = int(header.get("NAXIS", 0))
    bitpix = header.get("BITPIX")
    bunit = header.get("BUNIT") or None
    notes: list[str] = []

    # shape in numpy order [naxis2, naxis1] so it matches array layout
    shape: list[int] = []
    if naxis > 0:
        axes = [int(header.get(f"NAXIS{i}", 0)) for i in range(1, naxis + 1)]
        shape = list(reversed(axes))

    if dtype is None and bitpix is not None:
        _bmap = {8: "uint8", 16: "int16", 32: "int32", 64: "int64",
                 -32: "float32", -64: "float64"}
        dtype = _bmap.get(int(bitpix))

    table_columns = table_columns or []

    if extname == "FLAGS" and shape and shape != [2040, 2040]:
        notes.append(
            f"FLAGS extension has shape {shape} — not a full 2040x2040 image. "
            "Cannot be directly co-indexed with IMAGE pixels."
        )

    wcs_summary: dict[str, Any] | None = None
    if hdu_type in ("ImageHDU", "PrimaryHDU", "CompImageHDU") and naxis >= 2:
        wcs_summary = _extract_wcs_summary(header, shape)

    return HduInfo(
        index=index, extname=extname, hdu_type=hdu_type,
        has_data=has_data, naxis=naxis, shape=shape,
        bitpix=int(bitpix) if bitpix is not None else None,
        dtype=dtype, bunit=bunit,
        header=_serialise_header(header),
        table_columns=table_columns,
        wcs_summary=wcs_summary, notes=notes,
    )


def _inspect_hdu(hdu: Any, index: int) -> HduInfo:
    dtype = str(hdu.data.dtype) if hdu.data is not None and hasattr(hdu.data, "dtype") else None
    table_columns = (
        [col.name for col in hdu.columns]
        if isinstance(hdu, (fits.BinTableHDU, fits.TableHDU)) else []
    )
    return _inspect_hdu_header(
        hdu.header, index, type(hdu).__name__, hdu.data is not None,
        dtype=dtype, table_columns=table_columns,
    )


def _inspect_hdu_header_only(header: fits.Header, index: int) -> HduInfo:
    extension = str(header.get("XTENSION", "")).strip().upper()
    hdu_type = {
        "": "PrimaryHDU",
        "IMAGE": "ImageHDU",
        "BINTABLE": "BinTableHDU",
        "TABLE": "TableHDU",
    }.get(extension, "UnknownHDU")
    naxis = int(header.get("NAXIS", 0))
    has_data = naxis > 0 and all(
        int(header.get(f"NAXIS{i}", 0)) > 0 for i in range(1, naxis + 1)
    )
    nfields = int(header.get("TFIELDS", 0))
    columns = [
        str(header[f"TTYPE{i}"])
        for i in range(1, nfields + 1) if header.get(f"TTYPE{i}") is not None
    ]
    return _inspect_hdu_header(header, index, hdu_type, has_data, table_columns=columns)


@dataclass
class FitsInspectionResult:
    url: str
    obs_id: str
    reachable: bool
    header_readable: bool
    hdus_inspected: bool
    pixel_data_loaded: bool
    hdu_count: int
    hdus: list[HduInfo]
    primary_image_hdu_index: int | None
    error: str | None = None
    access_method: str = "byte_range_header"


def inspect_fits(url: str, obs_id: str, load_pixels: bool = False) -> FitsInspectionResult:
    base = FitsInspectionResult(
        url=url, obs_id=obs_id,
        reachable=False, header_readable=False, hdus_inspected=False,
        pixel_data_loaded=False, hdu_count=0, hdus=[], primary_image_hdu_index=None,
    )
    try:
        _validate_url(url)
        if load_pixels:
            fits_path = _download_fits(url)
            base.access_method = "full_download"
            with fits.open(str(fits_path), memmap=True, mode="readonly") as hdul:
                inspected = []
                for i, hdu in enumerate(hdul):
                    try:
                        inspected.append(_inspect_hdu(hdu, i))
                    except Exception as e:
                        logger.warning("HDU %d inspection failed: %s", i, e)
                        inspected.append(HduInfo(
                            index=i, extname=f"HDU{i}", hdu_type="Unknown",
                            has_data=False, naxis=0, shape=[], bitpix=None,
                            dtype=None, bunit=None,
                            header={"cards": [], "history": [], "comments": []},
                            table_columns=[], wcs_summary=None,
                            notes=["HDU inspection failed; metadata is unavailable."],
                        ))
        else:
            base.access_method = "byte_range_header"
            headers = _fetch_hdu_headers(url)
            inspected = []
            for i, (header, _) in enumerate(headers):
                try:
                    inspected.append(_inspect_hdu_header_only(header, i))
                except Exception as e:
                    logger.warning("HDU %d inspection failed: %s", i, e)
                    inspected.append(HduInfo(
                        index=i, extname=f"HDU{i}", hdu_type="Unknown",
                        has_data=False, naxis=0, shape=[], bitpix=None,
                        dtype=None, bunit=None,
                        header={"cards": [], "history": [], "comments": []},
                        table_columns=[], wcs_summary=None,
                        notes=["HDU inspection failed; metadata is unavailable."],
                    ))
        base.reachable = True
        base.header_readable = True
        base.hdus_inspected = True
        base.hdu_count = len(inspected)
        base.hdus = inspected
        base.primary_image_hdu_index = next(
            (h.index for h in inspected if h.extname == "IMAGE" and h.naxis == 2),
            None,
        )
        base.pixel_data_loaded = load_pixels
    except ValueError as e:
        base.error = str(e)
    except IOError as e:
        base.error = str(e)
    except Exception as e:
        logger.exception("Unexpected error inspecting FITS")
        base.error = "Unexpected FITS inspection error"
    return base


def _get_image_hdu(hdul: fits.HDUList) -> Any:
    for hdu in hdul:
        if hdu.header.get("EXTNAME") == "IMAGE" and hdu.data is not None:
            return hdu
    raise ValueError("No IMAGE extension with data found in FITS file")


def pixel_to_sky(url: str, x: float, y: float) -> dict[str, Any]:
    _validate_url(url)
    fits_path = _download_fits(url)
    with fits.open(str(fits_path), memmap=True, mode="readonly") as hdul:
        image_hdu = _get_image_hdu(hdul)
        params = _extract_wcs_params(image_hdu.header)
        if params is None:
            raise ValueError("IMAGE extension has no celestial WCS")
        ra, dec = _tan_pixel_to_sky(
            x, y,
            params["crpix1"], params["crpix2"],
            params["crval1"], params["crval2"], params["cd"],
            params["sip_a"], params["sip_b"],
        )
    return {
        "x_fits": x, "y_fits": y,
        "x_zero": x - 1, "y_zero": y - 1,
        "ra_deg": ra, "dec_deg": dec,
        "coordinate_frame": "ICRS",
        "pixel_convention": "FITS_1_BASED",
        "source_hdu": "IMAGE",
        "wcs_approximate": True,
        "wcs_note": (
            f"IMAGE {'TAN-SIP (PC and SIP terms)' if params['has_sip'] else 'TAN (PC/CD matrix)'} "
            "WCS applied; the product astrometry is not independently calibrated."
        ),
    }


def sky_to_pixel(url: str, ra: float, dec: float) -> dict[str, Any]:
    _validate_url(url)
    fits_path = _download_fits(url)
    with fits.open(str(fits_path), memmap=True, mode="readonly") as hdul:
        image_hdu = _get_image_hdu(hdul)
        params = _extract_wcs_params(image_hdu.header)
        if params is None:
            raise ValueError("IMAGE extension has no celestial WCS")
        x_fits, y_fits = _tan_sky_to_pixel(
            ra, dec,
            params["crpix1"], params["crpix2"],
            params["crval1"], params["crval2"], params["cd"],
            params["sip_a"], params["sip_b"],
        )
        naxis2, naxis1 = image_hdu.data.shape
        in_bounds = bool(1 <= x_fits <= naxis1 and 1 <= y_fits <= naxis2)
    return {
        "ra_deg": ra, "dec_deg": dec,
        "x_zero": x_fits - 1, "y_zero": y_fits - 1,
        "x_fits": x_fits, "y_fits": y_fits,
        "coordinate_frame": "ICRS",
        "pixel_convention": "FITS_1_BASED",
        "source_hdu": "IMAGE",
        "in_bounds": in_bounds,
        "wcs_approximate": True,
        "wcs_note": (
            f"IMAGE {'TAN-SIP (PC and SIP terms)' if params['has_sip'] else 'TAN (PC/CD matrix)'} "
            "WCS applied; the product astrometry is not independently calibrated."
        ),
    }


@dataclass
class CutoutResult:
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
    output_path: str
    bunit: str | None
    source_hdu: str
    processing_note: str


def extract_cutout(
    url: str, obs_id: str,
    ra: float, dec: float,
    width_px: int, height_px: int,
) -> CutoutResult:
    if width_px < 1 or width_px > 2040:
        raise ValueError(f"width_px must be 1-2040, got {width_px}")
    if height_px < 1 or height_px > 2040:
        raise ValueError(f"height_px must be 1-2040, got {height_px}")

    _validate_url(url)
    fits_path = _download_fits(url)

    with fits.open(str(fits_path), memmap=True, mode="readonly") as hdul:
        image_hdu = _get_image_hdu(hdul)
        data = image_hdu.data.copy()
        header = image_hdu.header.copy()
        bunit = header.get("BUNIT") or None

        params = _extract_wcs_params(header)
        if params is None:
            raise ValueError("IMAGE extension has no celestial WCS")

        cx_fits, cy_fits = _tan_sky_to_pixel(
            ra, dec,
            params["crpix1"], params["crpix2"],
            params["crval1"], params["crval2"], params["cd"],
            params["sip_a"], params["sip_b"],
        )

        naxis2, naxis1 = data.shape
        cx0 = cx_fits - 1
        cy0 = cy_fits - 1

        x0 = int(round(cx0 - width_px / 2))
        y0 = int(round(cy0 - height_px / 2))
        x1 = x0 + width_px
        y1 = y0 + height_px

        x0c = max(0, x0);  x1c = min(naxis1, x1)
        y0c = max(0, y0);  y1c = min(naxis2, y1)

        if x0c >= x1c or y0c >= y1c:
            raise ValueError(
                f"Requested cutout at RA={ra}, Dec={dec} is entirely outside the image."
            )

        partial = (x0 < 0 or y0 < 0 or x1 > naxis1 or y1 > naxis2)
        cutout_data = data[y0c:y1c, x0c:x1c].copy()
        actual_shape = list(cutout_data.shape)

        parent_crpix1 = float(params["crpix1"])
        parent_crpix2 = float(params["crpix2"])
        cutout_crpix1 = parent_crpix1 - x0c
        cutout_crpix2 = parent_crpix2 - y0c

        out_header = fits.Header()
        fixed_wcs_keys = {
            "CTYPE1", "CTYPE2", "CUNIT1", "CUNIT2", "CRVAL1", "CRVAL2",
            "CDELT1", "CDELT2", "CROTA2", "RADESYS", "EQUINOX",
            "LONPOLE", "LATPOLE", "A_ORDER", "B_ORDER", "AP_ORDER", "BP_ORDER",
        }
        for key in header:
            if (key in fixed_wcs_keys or key.startswith(
                    ("CD1_", "CD2_", "PC1_", "PC2_", "A_", "B_", "AP_", "BP_"))):
                out_header[key] = header[key]
        out_header["CRPIX1"] = cutout_crpix1
        out_header["CRPIX2"] = cutout_crpix2
        out_header["NAXIS"] = 2
        out_header["NAXIS1"] = actual_shape[1]
        out_header["NAXIS2"] = actual_shape[0]
        if bunit:
            out_header["BUNIT"] = bunit
        out_header["PARENT"] = obs_id
        out_header["CUT_RA"] = ra
        out_header["CUT_DEC"] = dec
        out_header["CUT_WPX"] = width_px
        out_header["CUT_HPX"] = height_px
        out_header["PARTIAL"] = partial

        out_hdu = fits.PrimaryHDU(data=cutout_data, header=out_header)
        out_filename = f"cutout_{obs_id}_{ra:.4f}_{dec:.4f}_{width_px}x{height_px}.fits"
        out_hdu.writeto(str(_cache_dir() / out_filename), overwrite=True)

    return CutoutResult(
        obs_id=obs_id, ra=ra, dec=dec,
        width_px=width_px, height_px=height_px,
        actual_shape=actual_shape,
        center_x_fits=cx_fits, center_y_fits=cy_fits,
        crpix_parent=[parent_crpix1, parent_crpix2],
        crpix_cutout=[cutout_crpix1, cutout_crpix2],
        wcs_valid=True, partial=partial,
        output_path=out_filename,
        bunit=bunit, source_hdu="IMAGE",
        processing_note=(
            "Cutout with translated WCS. Original IMAGE data unchanged. "
            f"CRPIX translated from [{parent_crpix1}, {parent_crpix2}] "
            f"to [{cutout_crpix1:.2f}, {cutout_crpix2:.2f}]."
            + (" Partial cutout — requested region extends beyond image boundary."
               if partial else "")
        ),
    )


# ── Image rendering ────────────────────────────────────────────────
# Uses astropy.visualization (pure Python) for stretch + PIL for PNG output.
# astropy.wcs C extension is NOT required here.
# Original pixel values are never modified; stretching affects display only.

VALID_STRETCHES = frozenset(["linear", "log", "asinh", "zscale"])
_preview_lock = threading.Lock()


@dataclass
class ImageInfoResult:
    obs_id: str
    source_hdu: str
    naxis1: int
    naxis2: int
    dtype: str
    bunit: str | None
    data_min: float
    data_max: float
    data_mean: float
    data_median: float
    nan_count: int
    inf_count: int
    total_pixels: int
    wcs_valid: bool
    pixel_scale_arcsec: float | None


@dataclass
class PreviewResult:
    obs_id: str
    source_hdu: str
    stretch: str
    width_px: int
    height_px: int
    bunit: str | None
    vmin: float
    vmax: float
    nan_count: int
    png_bytes: bytes
    from_cache: bool
    note: str


def _preview_cache_path(url: str, stretch: str, size: int) -> Path:
    key = f"{url}|{stretch}|{size}"
    h = hashlib.sha256(key.encode()).hexdigest()[:16]
    return _cache_dir() / f"preview_{h}.png"


def _preview_meta_path(png_path: Path) -> Path:
    return png_path.with_suffix(".json")


def _apply_stretch(data: np.ndarray, stretch: str) -> tuple[np.ndarray, float, float]:
    """
    Apply display stretch to a 2D float array.
    Returns (normalised 0-1 array, vmin, vmax used).
    Original data is NOT modified.
    """
    from astropy.visualization import (
        ZScaleInterval, AsinhStretch, LinearStretch, LogStretch,
        ImageNormalize,
    )

    # Replace non-finite values with NaN for interval computation
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        return np.zeros_like(data, dtype=np.float32), 0.0, 1.0

    if stretch == "zscale":
        interval = ZScaleInterval(n_samples=min(10000, finite.size))
        vmin, vmax = interval.get_limits(finite)
        stretch_obj = LinearStretch()
    elif stretch == "log":
        # Log stretch: clip to positive range
        pos = finite[finite > 0]
        if pos.size == 0:
            vmin, vmax = float(finite.min()), float(finite.max())
        else:
            vmin = float(np.percentile(pos, 1))
            vmax = float(np.percentile(pos, 99))
        stretch_obj = LogStretch()
    elif stretch == "asinh":
        vmin = float(np.percentile(finite, 0.5))
        vmax = float(np.percentile(finite, 99.5))
        stretch_obj = AsinhStretch()
    else:  # linear
        vmin = float(np.percentile(finite, 1))
        vmax = float(np.percentile(finite, 99))
        stretch_obj = LinearStretch()

    if vmin >= vmax:
        vmax = vmin + 1.0

    norm = ImageNormalize(vmin=vmin, vmax=vmax, stretch=stretch_obj, clip=True)
    normed = norm(data)
    # ImageNormalize returns a masked array; fill masked (NaN) with 0
    if hasattr(normed, "filled"):
        normed = normed.filled(0.0)
    return normed.astype(np.float32), vmin, vmax


def _array_to_png(normed: np.ndarray, out_size: int) -> bytes:
    """Convert a 0-1 normalised 2D array to a PNG bytes object using PIL."""
    from PIL import Image

    # Downsample to out_size x out_size using PIL (LANCZOS)
    img_uint8 = (np.clip(normed, 0, 1) * 255).astype(np.uint8)
    img = Image.fromarray(img_uint8, mode="L")
    img = img.resize((out_size, out_size), Image.LANCZOS)
    # Apply a perceptually uniform colormap (viridis) via matplotlib
    import matplotlib.cm as cm
    arr = np.array(img) / 255.0
    rgba = (cm.inferno(arr) * 255).astype(np.uint8)
    img_color = Image.fromarray(rgba, mode="RGBA")
    buf = io.BytesIO()
    img_color.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def get_image_info(url: str, obs_id: str) -> ImageInfoResult:
    """Return statistical metadata about the IMAGE HDU. Requires full download."""
    _validate_url(url)
    fits_path = _download_fits(url)

    with fits.open(str(fits_path), memmap=True, mode="readonly") as hdul:
        image_hdu = _get_image_hdu(hdul)
        data = image_hdu.data  # memmap — no full copy
        header = image_hdu.header
        bunit = header.get("BUNIT") or None
        naxis2, naxis1 = data.shape

        finite = data[np.isfinite(data)]
        nan_count = int(np.sum(np.isnan(data)))
        inf_count = int(np.sum(np.isinf(data)))

        wcs_params = _extract_wcs_params(header)
        pixel_scale: float | None = None
        if wcs_params is not None:
            cd = wcs_params["cd"]
            s1 = math.sqrt(cd[0, 0] ** 2 + cd[1, 0] ** 2)
            s2 = math.sqrt(cd[0, 1] ** 2 + cd[1, 1] ** 2)
            pixel_scale = (s1 + s2) / 2.0 * 3600.0

        # Normalise dtype name: '>f4' -> 'float32' etc.
        _dtype_map = {'>f4': 'float32', '<f4': 'float32', '>f8': 'float64',
                      '<f8': 'float64', '>i2': 'int16', '<i2': 'int16',
                      '>i4': 'int32', '<i4': 'int32', '>u1': 'uint8'}
        dtype_str = _dtype_map.get(str(data.dtype), str(data.dtype))
        return ImageInfoResult(
            obs_id=obs_id,
            source_hdu="IMAGE",
            naxis1=naxis1,
            naxis2=naxis2,
            dtype=dtype_str,
            bunit=bunit,
            data_min=float(finite.min()) if finite.size > 0 else float("nan"),
            data_max=float(finite.max()) if finite.size > 0 else float("nan"),
            data_mean=float(finite.mean()) if finite.size > 0 else float("nan"),
            data_median=float(np.median(finite)) if finite.size > 0 else float("nan"),
            nan_count=nan_count,
            inf_count=inf_count,
            total_pixels=int(data.size),
            wcs_valid=wcs_params is not None,
            pixel_scale_arcsec=pixel_scale,
        )


def render_preview(
    url: str,
    obs_id: str,
    stretch: str = "zscale",
    size: int = 512,
) -> PreviewResult:
    """
    Render a PNG preview of the IMAGE HDU.
    Stretch affects display only — original pixel values are unchanged.
    Returns PNG bytes and metadata. Uses a per-(url, stretch, size) cache.
    """
    if stretch not in VALID_STRETCHES:
        raise ValueError(
            f"Invalid stretch {stretch!r}. Valid options: {sorted(VALID_STRETCHES)}"
        )
    if not (64 <= size <= 1024):
        raise ValueError(f"size must be 64-1024, got {size}")

    _validate_url(url)
    png_cache = _preview_cache_path(url, stretch, size)

    with _preview_lock:
        if png_cache.exists() and png_cache.stat().st_size > 0:
            logger.info("Preview cache hit: %s", png_cache.name)
            meta_path = _preview_meta_path(png_cache)
            meta: dict[str, Any] = {}
            if meta_path.exists():
                import json as _json
                try:
                    meta = _json.loads(meta_path.read_text())
                except Exception:
                    pass
            return PreviewResult(
                obs_id=obs_id, source_hdu="IMAGE",
                stretch=stretch, width_px=size, height_px=size,
                bunit=meta.get("bunit"), vmin=meta.get("vmin", 0.0),
                vmax=meta.get("vmax", 0.0),
                nan_count=meta.get("nan_count", 0),
                png_bytes=png_cache.read_bytes(),
                from_cache=True,
                note="Served from preview cache. Stretch: " + stretch,
            )

    fits_path = _download_fits(url)

    with fits.open(str(fits_path), memmap=True, mode="readonly") as hdul:
        image_hdu = _get_image_hdu(hdul)
        # Read full data into memory for rendering (2040x2040 float32 = ~16 MB)
        data = image_hdu.data.astype(np.float32)
        bunit = image_hdu.header.get("BUNIT") or None
        nan_count = int(np.sum(np.isnan(data)))

    normed, vmin, vmax = _apply_stretch(data, stretch)
    png_bytes = _array_to_png(normed, size)

    with _preview_lock:
        png_cache.write_bytes(png_bytes)
        import json as _json
        _preview_meta_path(png_cache).write_text(_json.dumps({
            "bunit": bunit, "vmin": float(vmin), "vmax": float(vmax),
            "nan_count": int(nan_count),
        }))

    note = (
        f"Display stretch: {stretch}. "
        f"vmin={vmin:.4g}, vmax={vmax:.4g} {bunit or ''}. "
        "Original pixel values unchanged. "
        + (f"{nan_count} NaN pixels masked to zero. " if nan_count > 0 else "")
        + "Colormap: inferno."
    )

    return PreviewResult(
        obs_id=obs_id, source_hdu="IMAGE",
        stretch=stretch, width_px=size, height_px=size,
        bunit=bunit, vmin=vmin, vmax=vmax,
        nan_count=nan_count, png_bytes=png_bytes,
        from_cache=False, note=note,
    )
