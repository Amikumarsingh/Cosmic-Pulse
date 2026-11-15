/**
 * API service layer — typed wrappers for FastAPI backend.
 * Milestone 3: real backend connected for observations and health.
 */

import type {
  Observation, EvidenceCapsule, Investigation, SearchParams,
} from '../types'
import type { ArchiveSearchResult, ObservationDetail, RepeatObsResult } from '../types/archive'
import { DEMO_EVIDENCE_CAPSULE, DEMO_INVESTIGATION } from '../data/demoData'

const BASE_URL = (
  import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '')
).replace(/\/+$/, '')

export function apiUrl(path: string): string {
  if (!BASE_URL) {
    throw new Error('Production API is not configured. Set VITE_API_URL to the deployed backend URL.')
  }
  return `${BASE_URL}${path}`
}

const API_TIMEOUT_MS = 180_000

async function apiFetch<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const url = new URL(apiUrl(path))
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)))
  }
  const res = await fetch(url.toString(), { signal: AbortSignal.timeout(API_TIMEOUT_MS) })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`API ${res.status}: ${body.slice(0, 200) || res.statusText}`)
  }
  return res.json() as Promise<T>
}

// ── Health ─────────────────────────────────────────────────────────

export interface HealthStatus {
  status: string
  version: string
  backend_milestone: number
  known_obs_id: string
  fits_accessible: boolean
  fits_verification_level: string
}

export async function checkHealth(): Promise<HealthStatus & { online: boolean }> {
  try {
    const data = await apiFetch<HealthStatus>('/health')
    return { ...data, online: true }
  } catch {
    return {
      status: 'offline', version: 'unknown', backend_milestone: 0,
      known_obs_id: '', fits_accessible: false,
      fits_verification_level: 'UNKNOWN', online: false,
    }
  }
}

export async function checkArchiveHealth(): Promise<Record<string, unknown>> {
  try {
    return await apiFetch<Record<string, unknown>>('/archive/health')
  } catch {
    return { error: 'Backend offline' }
  }
}

// ── Observation search ─────────────────────────────────────────────

export async function searchObservationsArchive(
  params: SearchParams,
): Promise<ArchiveSearchResult> {
  return apiFetch<ArchiveSearchResult>('/observations/search', {
    ra: params.ra,
    dec: params.dec,
    radius: params.radiusDeg,
  })
}

// ── Observation detail ─────────────────────────────────────────────

export async function getObservationDetail(obsId: string): Promise<ObservationDetail> {
  return apiFetch<ObservationDetail>(`/observations/${encodeURIComponent(obsId)}`)
}

// ── Products ───────────────────────────────────────────────────────

export async function getObservationProducts(obsId: string): Promise<unknown[]> {
  return apiFetch<unknown[]>(`/observations/${encodeURIComponent(obsId)}/products`)
}

// ── Repeat observations ────────────────────────────────────────────

export async function findRepeatObservations(
  obsId: string, radius = 0.5,
): Promise<RepeatObsResult> {
  return apiFetch<RepeatObsResult>(
    `/observations/${encodeURIComponent(obsId)}/repeats`,
    { radius },
  )
}

// ── Legacy demo wrappers (used by non-Explorer pages) ─────────────

export async function searchObservations(_params: SearchParams): Promise<Observation[]> {
  // Kept for backward compatibility with pages not yet connected to real backend
  await new Promise(r => setTimeout(r, 400))
  return []
}

export async function getObservation(_id: string): Promise<Observation | null> {
  await new Promise(r => setTimeout(r, 200))
  return null
}

export async function getEvidenceCapsule(investigationId: string): Promise<EvidenceCapsule | null> {
  await new Promise(r => setTimeout(r, 300))
  if (investigationId === DEMO_EVIDENCE_CAPSULE.investigationId) return DEMO_EVIDENCE_CAPSULE
  return null
}

export async function listInvestigations(): Promise<Investigation[]> {
  await new Promise(r => setTimeout(r, 300))
  return [DEMO_INVESTIGATION]
}

export async function getInvestigation(id: string): Promise<Investigation | null> {
  await new Promise(r => setTimeout(r, 200))
  if (id === DEMO_INVESTIGATION.id) return DEMO_INVESTIGATION
  return null
}

// ── FITS Inspection API (Milestone 4) ──────────────────────────────

export interface WcsSummary {
  valid: boolean
  ctype1: string | null
  ctype2: string | null
  crpix1: number | null
  crpix2: number | null
  crval1: number | null
  crval2: number | null
  cdelt1: number | null
  cdelt2: number | null
  cd_matrix: number[][] | null
  pc_matrix: number[][] | null
  has_sip: boolean
  pixel_scale_deg: number | null
  pixel_scale_arcsec: number | null
  center_ra: number | null
  center_dec: number | null
  center_note: string | null
  projection: string | null
  naxis: number
  error: string | null
}

export interface HduSummary {
  index: number
  extname: string
  hdu_type: string
  has_data: boolean
  naxis: number
  shape: number[]
  bitpix: number | null
  dtype: string | null
  bunit: string | null
  table_columns: string[]
  wcs_summary: WcsSummary | null
  notes: string[]
}

export interface FitsInspectResult {
  obs_id: string
  reachable: boolean
  header_readable: boolean
  hdus_inspected: boolean
  pixel_data_loaded: boolean
  hdu_count: number
  hdus: HduSummary[]
  primary_image_hdu_index: number | null
  access_method: string
  error: string | null
}

export interface PixelToSkyResult {
  obs_id: string
  x_fits: number
  y_fits: number
  x_zero: number
  y_zero: number
  ra_deg: number
  dec_deg: number
  coordinate_frame: string
  pixel_convention: string
  source_hdu: string
  wcs_approximate: boolean
  wcs_note: string
}

export interface SkyToPixelResult {
  obs_id: string
  ra_deg: number
  dec_deg: number
  x_zero: number
  y_zero: number
  x_fits: number
  y_fits: number
  coordinate_frame: string
  pixel_convention: string
  source_hdu: string
  in_bounds: boolean
  wcs_approximate: boolean
  wcs_note: string
}

export interface CutoutResult {
  obs_id: string
  ra: number
  dec: number
  width_px: number
  height_px: number
  actual_shape: number[]
  center_x_fits: number
  center_y_fits: number
  crpix_parent: number[]
  crpix_cutout: number[]
  wcs_valid: boolean
  partial: boolean
  output_filename: string
  bunit: string | null
  source_hdu: string
  processing_note: string
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(apiUrl(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(API_TIMEOUT_MS),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`API ${res.status}: ${text.slice(0, 200) || res.statusText}`)
  }
  return res.json() as Promise<T>
}

export async function inspectFits(obsId: string): Promise<FitsInspectResult> {
  return apiFetch<FitsInspectResult>('/api/fits/inspect', { observation_id: obsId })
}

export async function getFitsWcs(obsId: string): Promise<{ obs_id: string; source_hdu: string; wcs: WcsSummary }> {
  return apiFetch(`/api/fits/${encodeURIComponent(obsId)}/wcs`)
}

export async function pixelToSky(obsId: string, x: number, y: number): Promise<PixelToSkyResult> {
  return apiFetch<PixelToSkyResult>(`/api/fits/${encodeURIComponent(obsId)}/pixel-to-sky`, { x, y })
}

export async function skyToPixel(obsId: string, ra: number, dec: number): Promise<SkyToPixelResult> {
  return apiFetch<SkyToPixelResult>(`/api/fits/${encodeURIComponent(obsId)}/sky-to-pixel`, { ra, dec })
}

export async function generateCutout(
  obsId: string,
  ra: number, dec: number,
  width_px: number, height_px: number,
): Promise<CutoutResult> {
  return apiPost<CutoutResult>(
    `/api/fits/${encodeURIComponent(obsId)}/cutout`,
    { ra, dec, width_px, height_px },
  )
}

// ── Image viewer API (Milestone 5) ────────────────────────────────

export interface ImageInfoResult {
  obs_id: string
  source_hdu: string
  naxis1: number
  naxis2: number
  dtype: string
  bunit: string | null
  data_min: number
  data_max: number
  data_mean: number
  data_median: number
  nan_count: number
  inf_count: number
  total_pixels: number
  wcs_valid: boolean
  pixel_scale_arcsec: number | null
}

export type StretchMode = 'zscale' | 'linear' | 'log' | 'asinh'

export function getPreviewUrl(obsId: string, stretch: StretchMode, size: number): string {
  return `${apiUrl(`/api/fits/${encodeURIComponent(obsId)}/preview`)}?stretch=${stretch}&size=${size}`
}

export async function getImageInfo(obsId: string): Promise<ImageInfoResult> {
  return apiFetch<ImageInfoResult>(`/api/fits/${encodeURIComponent(obsId)}/image-info`)
}

// ── Time Machine comparison API (Milestone 6) ─────────────────────

export interface EpochMeta {
  obs_id: string
  date_obs: string | null
  detector: string | null
  mission: string
  data_release: string
  ra: number
  dec: number
  naxis1: number | null
  naxis2: number | null
  bunit: string | null
  pixel_scale_arcsec: number | null
  wcs_valid: boolean
  available: boolean
  is_real: boolean
  unavailable_reason: string | null
}

export interface CompatibilityCheck {
  name: string
  status: string
  note: string | null
}

export interface CompareMeta {
  epoch_a: EpochMeta
  epoch_b: EpochMeta | null
  epochs_available: number
  comparison_possible: boolean
  compatibility_checks: CompatibilityCheck[]
  scientific_note: string
}

export async function getCompareMeta(obsId: string): Promise<CompareMeta> {
  return apiFetch<CompareMeta>(`/api/fits/${encodeURIComponent(obsId)}/compare-meta`)
}

// ── Source analysis API (Milestone 6) ────────────────────────────

export interface DetectedSource {
  source_id: number
  label: number
  x_centroid: number
  y_centroid: number
  x_fits: number
  y_fits: number
  ra_deg: number | null
  dec_deg: number | null
  wcs_approximate: boolean
  area_px: number
  peak_flux: number
  bbox_x0: number
  bbox_y0: number
  bbox_x1: number
  bbox_y1: number
  aperture_radius_px: number
  aperture_flux: number | null
  bunit: string | null
}

export interface AnalysisResult {
  obs_id: string
  source_hdu: string
  nsigma: number
  npixels_min: number
  aperture_radius_px: number
  box_size: number
  bkg_median: number
  bkg_rms_median: number
  n_sources: number
  sources: DetectedSource[]
  naxis1: number
  naxis2: number
  bunit: string | null
  nan_count: number
  sources_capped: boolean
  from_cache: boolean
  scientific_notes: string[]
}

export interface DetectParams {
  nsigma?: number
  npixels_min?: number
  aperture_radius_px?: number
  box_size?: number
}

export async function runDetection(obsId: string, params: DetectParams): Promise<AnalysisResult> {
  return apiPost<AnalysisResult>(`/api/analysis/${encodeURIComponent(obsId)}/detect`, params)
}

export async function getAnalysisResults(obsId: string, params: DetectParams): Promise<AnalysisResult> {
  return apiFetch<AnalysisResult>(`/api/analysis/${encodeURIComponent(obsId)}/results`, {
    ...(params.nsigma != null ? { nsigma: params.nsigma } : {}),
    ...(params.npixels_min != null ? { npixels_min: params.npixels_min } : {}),
    ...(params.aperture_radius_px != null ? { aperture_radius_px: params.aperture_radius_px } : {}),
    ...(params.box_size != null ? { box_size: params.box_size } : {}),
  } as Record<string, number>)
}

export async function getSourceDetail(obsId: string, sourceId: number, params: DetectParams): Promise<DetectedSource> {
  return apiFetch<DetectedSource>(
    `/api/analysis/${encodeURIComponent(obsId)}/sources/${sourceId}`,
    {
      ...(params.nsigma != null ? { nsigma: params.nsigma } : {}),
      ...(params.npixels_min != null ? { npixels_min: params.npixels_min } : {}),
      ...(params.aperture_radius_px != null ? { aperture_radius_px: params.aperture_radius_px } : {}),
      ...(params.box_size != null ? { box_size: params.box_size } : {}),
    } as Record<string, number>,
  )
}
