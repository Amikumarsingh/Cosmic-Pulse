// Core astronomical types for COSMIC PULSE

export interface Coordinates {
  ra: number   // Right Ascension in degrees
  dec: number  // Declination in degrees
}

export interface Observation {
  id: string
  observationId: string
  mission: string
  instrument: string
  detector: string
  ra: number
  dec: number
  epoch: string
  wavelengthMin: number
  wavelengthMax: number
  exposureTime: number
  fitsProductId: string | null
  fitsUrl: string | null
  previewUrl: string | null
  qualityFlag: number
  coverageStatus: 'available' | 'partial' | 'unavailable' | 'demo'
  notes: string
  isDemo?: boolean
}

export interface FitsExtension {
  name: string
  shape: [number, number] | null
  dtype: string | null
  description: string
}

export interface FitsMetadata {
  observationId: string
  filename: string
  extensions: FitsExtension[]
  wcsValid: boolean
  pixelScale: number | null  // arcsec/pixel
  inspectedAt: string
}

export type CandidateStatus = 'selected' | 'observations_retrieved' | 'analysis_completed' | 'flagged' | 'human_review' | 'confirmed' | 'rejected' | 'unresolved'

export interface Measurement {
  id: string
  type: 'flux' | 'position' | 'fwhm' | 'snr' | 'custom'
  value: number
  unit: string
  uncertainty: number | null
  qualityFlag: number
  notes: string
}

export interface Candidate {
  id: string
  investigationId: string
  ra: number
  dec: number
  status: CandidateStatus
  rankScore: number | null
  criteria: string[]
  measurements: Measurement[]
  humanReviewNotes: string
  createdAt: string
  updatedAt: string
}

export interface ProcessingStep {
  step: number
  name: string
  description: string
  softwareVersion: string
  parameters: Record<string, unknown>
  completedAt: string | null
}

export interface EvidenceCapsule {
  id: string
  investigationId: string
  targetCoordinates: Coordinates
  mission: string
  observationIds: string[]
  epochs: string[]
  fitsProductRefs: string[]
  processingSteps: ProcessingStep[]
  measurements: Measurement[]
  candidateStatus: CandidateStatus
  scientificLimitations: string[]
  humanReviewStatus: 'pending' | 'reviewed' | 'not_required'
  humanReviewNotes: string
  softwareVersions: Record<string, string>
  createdAt: string
  exportedAt: string | null
  isDemo: boolean
}

export interface Investigation {
  id: string
  title: string
  description: string
  targetCoordinates: Coordinates
  status: 'active' | 'completed' | 'archived'
  observations: Observation[]
  candidates: Candidate[]
  evidenceCapsule: EvidenceCapsule | null
  createdAt: string
  updatedAt: string
  isDemo: boolean
}

export interface ApiResponse<T> {
  data: T | null
  error: string | null
  loading: boolean
}

export interface SearchParams {
  ra: number
  dec: number
  radiusDeg: number
}
