// Archive-specific types matching FastAPI response models (Milestone 3)

export interface ProductAccess {
  url: string
  http_status: number
  content_length_bytes: number | null
  content_type: string | null
  accept_ranges: boolean
  byte_range_works: boolean
  fits_magic_valid: boolean
  verification_level: string
  error: string | null
}

export interface ArchiveObservation {
  obs_id: string
  ra: number
  dec: number
  date_obs: string | null
  detector: string
  mission: string
  data_release: string
  calib_level: number
  naxis1: number | null
  naxis2: number | null
  bunit: string | null
  fits_url: string | null
  fits_size_bytes: number | null
  source: string
  is_demo: boolean
}

export interface ObservationDetail extends ArchiveObservation {
  access: ProductAccess | null
  known_extensions: string[]
  wcs_ctype1: string | null
  wcs_ctype2: string | null
}

export interface ArchiveSearchResult {
  results: ArchiveObservation[]
  count: number
  tap_available: boolean
  tap_error: string | null
  search_ra: number
  search_dec: number
  search_radius_deg: number
}

export interface CompatibilityChecks {
  spatial_overlap: string
  temporal_separation: string
  detector_compatibility: string
  wavelength_compatibility: string
  calibration_compatibility: string
  wcs_alignment: string
}

export interface RepeatCandidate {
  obs_id: string
  ra: number | null
  dec: number | null
  t_min_mjd: string | null
  t_min_iso: string | null
  band: string | null
  calib_level: string | null
  access_url: string | null
}

export interface RepeatObsResult {
  reference_obs_id: string
  reference_ra: number
  reference_dec: number
  search_radius_deg: number
  tap_available: boolean
  tap_error: string | null
  candidates_found: number
  candidates: RepeatCandidate[]
  classification: string
  explanation: string
  compatibility_checks: CompatibilityChecks
  scientific_note: string
}
