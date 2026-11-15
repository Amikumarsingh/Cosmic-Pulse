import { useState, useCallback } from 'react'
import { FlaskConical, AlertTriangle, CheckCircle, Play, Info } from 'lucide-react'
import Panel from '../components/Panel'
import { MetaRow, Badge, LimitationList, SectionLabel, Loading, ErrorMsg } from '../components/ui'
import { runDetection } from '../api'
import type { AnalysisResult, DetectedSource } from '../api'

const KNOWN_OBS_ID = '2025W17_4B_0001_1'

const QUALITY_FLAGS = [
  { name: 'IMAGE', status: 'available', description: 'Science image data present' },
  { name: 'FLAGS', status: 'caution', description: 'Co-indexed 2040×2040 mask; bit definitions unverified, not applied' },
  { name: 'VARIANCE', status: 'caution', description: 'BUNIT MJy2 / sr2; semantics unverified, not used' },
  { name: 'ZODI', status: 'caution', description: 'Zodiacal light model — NOT subtracted' },
  { name: 'EPSF', status: 'available', description: 'PSF model present' },
  { name: 'WCS-WAVE', status: 'available', description: 'Wavelength WCS present' },
]

const statusColor: Record<string, string> = {
  available: '#4ade80', caution: '#fbbf24', missing: '#f87171',
}

function fmt(v: number | null | undefined, digits = 3): string {
  if (v == null || !isFinite(v)) return '—'
  return v.toExponential(digits)
}

function fmtCoord(v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return '—'
  return v.toFixed(6) + '°'
}

const inputStyle: React.CSSProperties = {
  background: 'rgba(2,4,8,0.6)',
  border: '1px solid rgba(34,211,238,0.2)',
  borderRadius: 4, color: '#f0f4f8',
  padding: '5px 8px', fontSize: '0.8rem',
  width: '100%', outline: 'none',
  fontFamily: 'var(--font-mono)',
}

export default function DiscoveryLab() {
  const [nsigma, setNsigma] = useState(3.0)
  const [npixels, setNpixels] = useState(5)
  const [aperture, setAperture] = useState(3.0)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<DetectedSource | null>(null)

  const handleRun = useCallback(async () => {
    setRunning(true)
    setError('')
    setSelected(null)
    try {
      const r = await runDetection(KNOWN_OBS_ID, {
        nsigma,
        npixels_min: npixels,
        aperture_radius_px: aperture,
        box_size: 64,
      })
      setResult(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Detection failed')
    } finally {
      setRunning(false)
    }
  }, [nsigma, npixels, aperture])

  return (
    <div style={{ paddingTop: 56, minHeight: '100vh' }}>
      {/* Page header */}
      <div style={{ borderBottom: '1px solid rgba(103,232,249,0.15)', padding: '28px 24px 20px', background: 'rgba(6,13,24,0.4)' }}>
        <div className="page-container">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
            <FlaskConical size={20} color="#67e8f9" />
            <h1 style={{ margin: 0, fontSize: '1.3rem', fontWeight: 700, color: '#f0f4f8' }}>Discovery Lab</h1>
            {result && !result.from_cache && <Badge variant="confirmed" label="LIVE ANALYSIS" />}
            {result?.from_cache && <Badge variant="demo" label="CACHED" />}
          </div>
          <p style={{ margin: 0, fontSize: '0.85rem', color: '#8899aa', maxWidth: 600 }}>
            Source detection and aperture photometry on the full-resolution 2040×2040 SPHEREx IMAGE HDU.
            Background estimated via sigma-clipped tiled median. No calibration corrections applied.
          </p>
        </div>
      </div>

      <div className="page-container" style={{ padding: '24px 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 20, alignItems: 'start' }}>

          {/* Left: controls + quality */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            <Panel title="Detection Parameters">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div>
                  <SectionLabel>Detection threshold (σ)</SectionLabel>
                  <input type="number" min={0.5} max={20} step={0.5} value={nsigma}
                    onChange={e => setNsigma(parseFloat(e.target.value) || 3.0)}
                    style={{ ...inputStyle, marginTop: 4 }} />
                  <div style={{ fontSize: '0.65rem', color: '#4a6080', marginTop: 3 }}>
                    Multiples of background RMS. Lower = more sources, more noise.
                  </div>
                </div>
                <div>
                  <SectionLabel>Min source area (px)</SectionLabel>
                  <input type="number" min={1} max={500} step={1} value={npixels}
                    onChange={e => setNpixels(parseInt(e.target.value) || 5)}
                    style={{ ...inputStyle, marginTop: 4 }} />
                </div>
                <div>
                  <SectionLabel>Aperture radius (px)</SectionLabel>
                  <input type="number" min={0.5} max={20} step={0.5} value={aperture}
                    onChange={e => setAperture(parseFloat(e.target.value) || 3.0)}
                    style={{ ...inputStyle, marginTop: 4 }} />
                  <div style={{ fontSize: '0.65rem', color: '#4a6080', marginTop: 3 }}>
                    Circular aperture on background-subtracted data.
                  </div>
                </div>
                <button
                  onClick={handleRun}
                  disabled={running}
                  className="btn-ghost"
                  style={{
                    marginTop: 4, justifyContent: 'center', width: '100%',
                    opacity: running ? 0.6 : 1,
                    borderColor: 'rgba(103,232,249,0.3)', color: '#67e8f9',
                  }}
                >
                  {running
                    ? <><FlaskConical size={13} /> Running…</>
                    : <><Play size={13} /> Run Detection</>}
                </button>
                <div style={{ fontSize: '0.65rem', color: '#4a6080', lineHeight: 1.5 }}>
                  Requires full FITS download (~62 MB, cached after first run).
                  Results cached per parameter set.
                </div>
              </div>
            </Panel>

            {result && (
              <Panel title="Background Statistics">
                <MetaRow label="Bkg median" value={fmt(result.bkg_median)} mono />
                <MetaRow label="Bkg RMS median" value={fmt(result.bkg_rms_median)} mono />
                <MetaRow label="BUNIT" value={result.bunit ?? '—'} mono highlight />
                <MetaRow label="Image size" value={`${result.naxis1}×${result.naxis2}`} mono />
                <MetaRow label="NaN/Inf px" value={String(result.nan_count)} mono />
                <MetaRow label="From cache" value={result.from_cache ? 'Yes' : 'No'} />
              </Panel>
            )}

            <Panel title="Data Quality">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {QUALITY_FLAGS.map(flag => (
                  <div key={flag.name} style={{
                    display: 'flex', alignItems: 'flex-start', gap: 8,
                    padding: '7px 10px', borderRadius: 5,
                    background: 'rgba(6,13,24,0.4)',
                    border: '1px solid rgba(34,211,238,0.06)',
                  }}>
                    <div style={{
                      width: 7, height: 7, borderRadius: '50%', flexShrink: 0, marginTop: 4,
                      background: statusColor[flag.status],
                      boxShadow: `0 0 5px ${statusColor[flag.status]}`,
                    }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#f0f4f8', fontFamily: 'var(--font-mono)' }}>{flag.name}</div>
                      <div style={{ fontSize: '0.63rem', color: '#8899aa', lineHeight: 1.4 }}>{flag.description}</div>
                    </div>
                    {flag.status === 'caution' && <AlertTriangle size={11} color="#fbbf24" style={{ flexShrink: 0, marginTop: 3 }} />}
                    {flag.status === 'available' && <CheckCircle size={11} color="#4ade80" style={{ flexShrink: 0, marginTop: 3 }} />}
                  </div>
                ))}
              </div>
            </Panel>
          </div>

          {/* Right: results */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {running && (
              <div style={{ padding: 24 }}>
                <Loading label="Running source detection on 2040×2040 IMAGE HDU…" />
                <div style={{ fontSize: '0.72rem', color: '#4a6080', marginTop: 8, textAlign: 'center' }}>
                  First run requires full FITS download (~62 MB). Background estimation + detection may take 10–30 s.
                </div>
              </div>
            )}

            {error && !running && <ErrorMsg message={error} />}

            {!result && !running && !error && (
              <div style={{
                height: 300, display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', gap: 12,
                border: '1px dashed rgba(103,232,249,0.15)', borderRadius: 8,
              }}>
                <FlaskConical size={36} color="rgba(103,232,249,0.2)" />
                <div style={{ fontSize: '0.85rem', color: '#4a6080' }}>Configure parameters and click Run Detection</div>
                <div style={{ fontSize: '0.72rem', color: '#4a6080', maxWidth: 320, textAlign: 'center' }}>
                  Analysis runs on the full-resolution SPHEREx IMAGE HDU (2040×2040 px, float32, MJy / sr).
                </div>
              </div>
            )}

            {result && !running && (
              <>
                {/* Summary */}
                <Panel title="Detection Summary">
                  <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'center' }}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '2rem', fontWeight: 700, color: '#67e8f9', fontFamily: 'var(--font-mono)', lineHeight: 1 }}>
                        {result.n_sources}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: '#8899aa', marginTop: 4 }}>
                        {result.sources_capped ? 'qualifying sources (catalogue capped)' : 'qualifying sources'}
                      </div>
                    </div>
                    <div style={{ flex: 1, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                      <div style={{ fontSize: '0.75rem', color: '#8899aa' }}>
                        <span style={{ color: '#f0f4f8', fontFamily: 'var(--font-mono)' }}>{result.nsigma}σ</span> threshold
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#8899aa' }}>
                        min <span style={{ color: '#f0f4f8', fontFamily: 'var(--font-mono)' }}>{result.npixels_min}</span> px
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#8899aa' }}>
                        aperture <span style={{ color: '#f0f4f8', fontFamily: 'var(--font-mono)' }}>{result.aperture_radius_px}</span> px
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#8899aa' }}>
                        IMAGE HDU · <span style={{ color: '#f0f4f8', fontFamily: 'var(--font-mono)' }}>{result.bunit ?? '?'}</span>
                      </div>
                    </div>
                  </div>
                </Panel>

                {/* Source table */}
                {result.n_sources > 0 && (
                  <Panel title={`Source Catalogue (${result.sources.length} shown, sorted by peak flux)`}>
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.72rem' }}>
                        <thead>
                          <tr style={{ borderBottom: '1px solid rgba(34,211,238,0.15)' }}>
                            {['#', 'x (FITS 1-based)', 'y (FITS 1-based)', 'RA (approx °)', 'Dec (approx °)', 'Area', 'Peak flux', 'Ap. flux', 'Unit'].map(h => (
                              <th key={h} style={{ padding: '5px 8px', textAlign: 'left', color: '#8899aa', fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {result.sources.map(s => (
                            <tr
                              key={s.source_id}
                              onClick={() => setSelected(s.source_id === selected?.source_id ? null : s)}
                              style={{
                                cursor: 'pointer',
                                background: selected?.source_id === s.source_id
                                  ? 'rgba(103,232,249,0.07)' : 'transparent',
                                borderBottom: '1px solid rgba(34,211,238,0.05)',
                              }}
                            >
                              <td style={{ padding: '5px 8px', color: '#67e8f9', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{s.source_id}</td>
                              <td style={{ padding: '5px 8px', color: '#f0f4f8', fontFamily: 'var(--font-mono)' }}>{s.x_fits.toFixed(1)}</td>
                              <td style={{ padding: '5px 8px', color: '#f0f4f8', fontFamily: 'var(--font-mono)' }}>{s.y_fits.toFixed(1)}</td>
                              <td style={{ padding: '5px 8px', color: '#22d3ee', fontFamily: 'var(--font-mono)' }}>{s.ra_deg != null ? s.ra_deg.toFixed(4) : '—'}</td>
                              <td style={{ padding: '5px 8px', color: '#22d3ee', fontFamily: 'var(--font-mono)' }}>{s.dec_deg != null ? s.dec_deg.toFixed(4) : '—'}</td>
                              <td style={{ padding: '5px 8px', color: '#8899aa', fontFamily: 'var(--font-mono)' }}>{s.area_px}</td>
                              <td style={{ padding: '5px 8px', color: '#f0f4f8', fontFamily: 'var(--font-mono)' }}>{fmt(s.peak_flux)}</td>
                              <td style={{ padding: '5px 8px', color: '#f0f4f8', fontFamily: 'var(--font-mono)' }}>{fmt(s.aperture_flux)}</td>
                              <td style={{ padding: '5px 8px', color: '#4a6080' }}>{s.bunit ?? '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {result.sources.length < result.n_sources && (
                      <div style={{ marginTop: 8, fontSize: '0.68rem', color: '#fbbf24' }}>
                        Showing {result.sources.length} of {result.n_sources} qualifying detections; catalogue contains the 200 brightest by peak flux.
                      </div>
                    )}
                  </Panel>
                )}

                {result.n_sources === 0 && (
                  <Panel title="Detection Result">
                    <div style={{ padding: '20px', textAlign: 'center', color: '#8899aa', fontSize: '0.82rem' }}>
                      No sources detected above {result.nsigma}σ with minimum area {result.npixels_min} px.
                      Try lowering the threshold or minimum area.
                    </div>
                  </Panel>
                )}

                {/* Selected source detail */}
                {selected && (
                  <Panel title={`Source #${selected.source_id} — Detail`}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                      <div>
                        <SectionLabel>Position</SectionLabel>
                        <MetaRow label="x (FITS 1-based)" value={selected.x_fits.toFixed(3)} mono highlight />
                        <MetaRow label="y (FITS 1-based)" value={selected.y_fits.toFixed(3)} mono highlight />
                        <MetaRow label="RA (approx)" value={fmtCoord(selected.ra_deg)} mono />
                        <MetaRow label="Dec (approx)" value={fmtCoord(selected.dec_deg)} mono />
                        {selected.wcs_approximate && (
                          <div style={{ marginTop: 6, fontSize: '0.65rem', color: '#fbbf24', display: 'flex', gap: 5, alignItems: 'flex-start' }}>
                            <AlertTriangle size={10} style={{ flexShrink: 0, marginTop: 1 }} />
                            TAN-SIP WCS applied, including the PC matrix. Product astrometry is not independently calibrated.
                          </div>
                        )}
                      </div>
                      <div>
                        <SectionLabel>Morphology</SectionLabel>
                        <MetaRow label="Area" value={`${selected.area_px} px`} mono />
                        <MetaRow label="Peak flux" value={`${fmt(selected.peak_flux)} ${selected.bunit ?? ''}`} mono />
                        <MetaRow label="BBox x" value={`${selected.bbox_x0}–${selected.bbox_x1}`} mono />
                        <MetaRow label="BBox y" value={`${selected.bbox_y0}–${selected.bbox_y1}`} mono />
                      </div>
                    </div>
                    <div style={{ marginTop: 12 }}>
                      <SectionLabel>Aperture Photometry</SectionLabel>
                      <MetaRow label="Aperture radius" value={`${selected.aperture_radius_px} px`} mono />
                      <MetaRow
                        label="Aperture flux (bkg-sub)"
                        value={selected.aperture_flux == null
                          ? 'Unavailable (edge or invalid pixels)'
                          : `${fmt(selected.aperture_flux)} ${selected.bunit ?? ''}`}
                        mono highlight
                      />
                      <div style={{ marginTop: 8, padding: '8px 10px', background: 'rgba(251,191,36,0.04)', border: '1px solid rgba(251,191,36,0.12)', borderRadius: 4 }}>
                        <div style={{ fontSize: '0.65rem', color: '#8899aa', lineHeight: 1.6, display: 'flex', gap: 6 }}>
                          <Info size={10} color="#fbbf24" style={{ flexShrink: 0, marginTop: 2 }} />
                          No photometric uncertainty reported. VARIANCE extension semantics unverified for this product.
                          ZODI not subtracted. No calibration corrections applied.
                        </div>
                      </div>
                    </div>
                  </Panel>
                )}

                {/* Scientific notes from backend */}
                <Panel title="Scientific Limitations">
                  <LimitationList items={result.scientific_notes} />
                </Panel>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
