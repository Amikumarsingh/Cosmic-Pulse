/**
 * DEMO DATA — clearly labelled, centralized.
 * All records marked isDemo: true.
 * Replace with real API calls in MILESTONE 4+.
 */

import type { Observation, EvidenceCapsule, Investigation, FitsMetadata } from '../types'

// The one genuine SPHEREx observation we have inspected.
// Source: SPHEREx DR1 Level-2, Observation ID 2025W17_4B_0001_1, Detector D1, 24 April 2025.
// FITS file NOT yet locally available — path unconfirmed.
export const KNOWN_SPHEREX_OBSERVATION: Observation = {
  id: 'obs-spherex-2025w17-d1',
  observationId: '2025W17_4B_0001_1',
  mission: 'SPHEREx',
  instrument: 'SPHEREx All-Sky Survey',
  detector: 'D1',
  ra: 0,      // Exact RA not yet confirmed from FITS WCS
  dec: 0,     // Exact Dec not yet confirmed from FITS WCS
  epoch: '2025-04-24T00:00:00Z',
  wavelengthMin: 0.75,
  wavelengthMax: 1.1,
  exposureTime: 0,   // Not yet extracted
  fitsProductId: '2025W17_4B_0001_1',
  fitsUrl: null,     // FITS file path not yet confirmed
  previewUrl: null,
  qualityFlag: 0,
  coverageStatus: 'demo',
  notes: 'Inspected FITS extensions: IMAGE, FLAGS, VARIANCE, ZODI, EPSF, WCS-WAVE. 128×128 pixel cutout extracted. Corrected cutout WCS tested for relative consistency. Absolute astrometric accuracy not verified.',
}

export const KNOWN_FITS_METADATA: FitsMetadata = {
  observationId: '2025W17_4B_0001_1',
  filename: '2025W17_4B_0001_1_D1.fits',
  extensions: [
    { name: 'IMAGE',    shape: [128, 128], dtype: 'float32', description: 'Science image data' },
    { name: 'FLAGS',    shape: [128, 128], dtype: 'int16',   description: 'Per-pixel quality flags' },
    { name: 'VARIANCE', shape: [128, 128], dtype: 'float32', description: 'Per-pixel variance (noise²)' },
    { name: 'ZODI',     shape: [128, 128], dtype: 'float32', description: 'Zodiacal light model — not subtracted' },
    { name: 'EPSF',     shape: null,       dtype: null,       description: 'Effective PSF model' },
    { name: 'WCS-WAVE', shape: null,       dtype: null,       description: 'Wavelength-dependent WCS' },
  ],
  wcsValid: true,
  pixelScale: null,  // Not yet extracted
  inspectedAt: '2025-04-24T00:00:00Z',
}

export const DEMO_OBSERVATIONS: Observation[] = [
  KNOWN_SPHEREX_OBSERVATION,
  {
    id: 'obs-demo-2',
    observationId: 'DEMO_OBS_002',
    mission: 'SPHEREx',
    instrument: 'SPHEREx All-Sky Survey',
    detector: 'D1',
    ra: 0,
    dec: 0,
    epoch: '2025-05-15T00:00:00Z',
    wavelengthMin: 0.75,
    wavelengthMax: 1.1,
    exposureTime: 0,
    fitsProductId: null,
    fitsUrl: null,
    previewUrl: null,
    qualityFlag: 0,
    coverageStatus: 'demo',
    notes: 'DEMO — second epoch placeholder. A compatible second observation has NOT yet been identified. Multi-epoch comparison is not yet possible.',
  },
]

export const DEMO_EVIDENCE_CAPSULE: EvidenceCapsule = {
  id: 'cap-demo-001',
  investigationId: 'inv-demo-001',
  targetCoordinates: { ra: 0, dec: 0 },
  mission: 'SPHEREx',
  observationIds: ['2025W17_4B_0001_1'],
  epochs: ['2025-04-24T00:00:00Z'],
  fitsProductRefs: ['2025W17_4B_0001_1_D1.fits'],
  processingSteps: [
    {
      step: 1,
      name: 'FITS Inspection',
      description: 'Opened SPHEREx DR1 Level-2 FITS file. Inspected all extensions.',
      softwareVersion: 'astropy 6.x',
      parameters: { extensions: ['IMAGE', 'FLAGS', 'VARIANCE', 'ZODI', 'EPSF', 'WCS-WAVE'] },
      completedAt: '2025-04-24T00:00:00Z',
    },
    {
      step: 2,
      name: 'Cutout Extraction',
      description: '128×128 pixel cutout extracted from IMAGE extension.',
      softwareVersion: 'astropy 6.x',
      parameters: { size: [128, 128], center: 'TBD' },
      completedAt: '2025-04-24T00:00:00Z',
    },
    {
      step: 3,
      name: 'WCS Consistency Check',
      description: 'Corrected cutout WCS tested for relative consistency. Absolute astrometric accuracy not verified.',
      softwareVersion: 'astropy 6.x',
      parameters: {},
      completedAt: '2025-04-24T00:00:00Z',
    },
  ],
  measurements: [],
  candidateStatus: 'human_review',
  scientificLimitations: [
    'Multi-epoch comparison has NOT yet been demonstrated.',
    'A suitable second observation has NOT yet been established.',
    'Relative WCS consistency is not proof of absolute astrometric accuracy.',
    'Calibration applicability remains unresolved.',
    'Some provenance associations remain unresolved.',
    'ZODI subtraction has NOT been applied — scientific justification not yet verified.',
  ],
  humanReviewStatus: 'pending',
  humanReviewNotes: '',
  softwareVersions: { astropy: '6.x', numpy: '1.x', python: '3.11+' },
  createdAt: '2025-04-24T00:00:00Z',
  exportedAt: null,
  isDemo: true,
}

export const DEMO_INVESTIGATION: Investigation = {
  id: 'inv-demo-001',
  title: 'SPHEREx DR1 Initial Inspection — 2025W17',
  description: 'First inspection of a genuine SPHEREx DR1 Level-2 observation. Single epoch only. Multi-epoch comparison pending.',
  targetCoordinates: { ra: 0, dec: 0 },
  status: 'active',
  observations: DEMO_OBSERVATIONS,
  candidates: [],
  evidenceCapsule: DEMO_EVIDENCE_CAPSULE,
  createdAt: '2025-04-24T00:00:00Z',
  updatedAt: '2025-04-24T00:00:00Z',
  isDemo: true,
}
