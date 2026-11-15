import { useState, useEffect, useCallback, useRef } from 'react'
import { Clock, AlertTriangle, Layers, Play, Pause, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react'
import Panel from '../components/Panel'
import ScientificImageViewer from '../components/ScientificImageViewer'
import { MetaRow, Badge, LimitationList, SectionLabel, Loading, ErrorMsg } from '../components/ui'
import { apiUrl } from '../api'

interface EpochMeta {
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

interface CompatibilityCheck {
  name: string
  status: string
  note: string | null
}

interface CompareMeta {
  epoch_a: EpochMeta
  epoch_b: EpochMeta | null
  epochs_available: number
  comparison_possible: boolean
  compatibility_checks: CompatibilityCheck[]
  scientific_note: string
}

const checkColor: Record<string, string> = {
  CONFIRMED: '#4ade80',
  PENDING: '#fbbf24',
  NOT_CHECKED: '#4a6080',
  FAILED: '#f87171',
}

export default function TimeMachine() {
  const [meta, setMeta] = useState<CompareMeta | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [blinkActive, setBlinkActive] = useState(false)
  const [blinkFrame, setBlinkFrame] = useState<'a' | 'b'>('a')
  const [mode, setMode] = useState<'side-by-side' | 'blink' | 'slider'>('side-by-side')
  const blinkRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const KNOWN_OBS_ID = '2025W17_4B_0001_1'

  const fetchMeta = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const r = await fetch(
        apiUrl(`/api/fits/${encodeURIComponent(KNOWN_OBS_ID)}/compare-meta`),
        { signal: AbortSignal.timeout(180_000) },
      )
      if (!r.ok) throw new Error(`API ${r.status}`)
      setMeta(await r.json())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load comparison metadata')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchMeta() }, [fetchMeta])

  useEffect(() => {
    if (blinkActive && meta?.comparison_possible) {
      blinkRef.current = setInterval(() => setBlinkFrame(f => f === 'a' ? 'b' : 'a'), 800)
    } else {
      if (blinkRef.current) clearInterval(blinkRef.current)
      setBlinkFrame('a')
    }
    return () => { if (blinkRef.current) clearInterval(blinkRef.current) }
  }, [blinkActive, meta?.comparison_possible])

  const canCompare = meta?.comparison_possible ?? false

  return (
    <div style={{ paddingTop: 56, minHeight: '100vh' }}>
      {/* Page header */}
      <div style={{ borderBottom: '1px solid rgba(167, 139, 250, 0.15)', padding: '28px 24px 20px', background: 'rgba(6, 13, 24, 0.4)' }}>
        <div className="page-container">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6, flexWrap: 'wrap' }}>
            <Clock size={20} color="#a78bfa" />
            <h1 style={{ margin: 0, fontSize: '1.3rem', fontWeight: 700, color: '#f0f4f8' }}>Cosmic Time Machine</h1>
            <Badge variant="demo" />
            {meta && (
              <span style={{ fontSize: '0.7rem', color: '#4ade80', marginLeft: 4 }}>
                {meta.epochs_available} epoch{meta.epochs_available !== 1 ? 's' : ''} confirmed
              </span>
            )}
          </div>
          <p style={{ margin: 0, fontSize: '0.85rem', color: '#8899aa', maxWidth: 600 }}>
            Compare observations across time. Select two compatible epochs to investigate changes in brightness, position, or morphology.
          </p>
        </div>
      </div>

      {/* Warning banner */}
      {(!meta || !meta.comparison_possible) && (
        <div style={{ background: 'rgba(251, 191, 36, 0.05)', borderBottom: '1px solid rgba(251, 191, 36, 0.15)', padding: '12px 24px' }}>
          <div className="page-container">
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <AlertTriangle size={15} color="#fbbf24" style={{ flexShrink: 0, marginTop: 1 }} />
              <p style={{ margin: 0, fontSize: '0.8rem', color: '#8899aa', lineHeight: 1.6 }}>
                <strong style={{ color: '#fbbf24' }}>Multi-epoch comparison is not yet available.</strong>
                {' '}Only one genuine SPHEREx observation has been confirmed (2025W17_4B_0001_1, 24 April 2025).
                Epoch A is shown below using the real FITS data.
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="page-container" style={{ padding: '24px 24px' }}>
        {loading && <Loading label="Loading comparison metadata…" />}
        {error && (
          <div style={{ marginBottom: 16 }}>
            <ErrorMsg message={error} />
            <button onClick={fetchMeta} className="btn-ghost" style={{ marginTop: 8 }}>
              <RefreshCw size={12} /> Retry
            </button>
          </div>
        )}

        {meta && (
          <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: 20, alignItems: 'start' }}>

            {/* Left sidebar */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

              <Panel title="Observation Timeline">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                  {[
                    { epoch: meta.epoch_a, label: 'Epoch A' },
                    { epoch: meta.epoch_b, label: 'Epoch B' },
                  ].map(({ epoch, label }, i) => (
                    <div key={label} style={{ display: 'flex', gap: 12, paddingBottom: i === 0 ? 16 : 0 }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
                        <div style={{
                          width: 12, height: 12, borderRadius: '50%', flexShrink: 0,
                          background: epoch?.available ? '#22d3ee' : 'rgba(34,211,238,0.15)',
                          border: `2px solid ${epoch?.available ? '#22d3ee' : 'rgba(34,211,238,0.3)'}`,
                          boxShadow: epoch?.available ? '0 0 8px rgba(34,211,238,0.4)' : 'none',
                        }} />
                        {i === 0 && <div style={{ width: 1, flex: 1, background: 'rgba(34,211,238,0.15)', marginTop: 4 }} />}
                      </div>
                      <div style={{ paddingBottom: 4 }}>
                        <div style={{ fontSize: '0.78rem', fontWeight: 600, color: epoch?.available ? '#f0f4f8' : '#4a6080', marginBottom: 2 }}>{label}</div>
                        <div style={{ fontSize: '0.72rem', color: epoch?.available ? '#8899aa' : '#4a6080', marginBottom: 4 }}>
                          {epoch?.date_obs?.slice(0, 10) ?? 'Not yet identified'}
                        </div>
                        {epoch ? (
                          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: '#22d3ee' }}>{epoch.obs_id}</div>
                        ) : (
                          <div style={{ fontSize: '0.65rem', color: '#4a6080', fontStyle: 'italic' }}>Awaiting identification</div>
                        )}
                        {epoch?.is_real && <div style={{ marginTop: 4 }}><Badge variant="confirmed" label="REAL DATA" /></div>}
                        {!epoch && <div style={{ marginTop: 4 }}><Badge variant="pending" label="PENDING" /></div>}
                      </div>
                    </div>
                  ))}
                </div>
              </Panel>

              <Panel title="Compatibility Checks">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {meta.compatibility_checks.map(c => (
                    <div key={c.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', fontSize: '0.75rem', gap: 8 }}>
                      <span style={{ color: '#8899aa', flex: 1 }}>{c.name}</span>
                      <span style={{ color: checkColor[c.status] ?? '#8899aa', fontFamily: 'var(--font-mono)', fontSize: '0.68rem', flexShrink: 0 }}>
                        {c.status.replace(/_/g, ' ')}
                      </span>
                    </div>
                  ))}
                </div>
              </Panel>

              {meta.epoch_a && (
                <Panel title="Epoch A Metadata">
                  <MetaRow label="Obs ID" value={meta.epoch_a.obs_id} mono />
                  <MetaRow label="Date" value={meta.epoch_a.date_obs?.slice(0, 10) ?? '—'} mono />
                  <MetaRow label="Detector" value={meta.epoch_a.detector ?? '—'} mono highlight />
                  <MetaRow label="Mission" value={meta.epoch_a.mission} />
                  <MetaRow label="Release" value={meta.epoch_a.data_release} />
                  <MetaRow label="RA" value={`${meta.epoch_a.ra.toFixed(5)}°`} mono />
                  <MetaRow label="Dec" value={`${meta.epoch_a.dec.toFixed(5)}°`} mono />
                  <MetaRow label="BUNIT" value={meta.epoch_a.bunit ?? '—'} mono />
                  <MetaRow label="Pixel scale" value={meta.epoch_a.pixel_scale_arcsec != null ? `${meta.epoch_a.pixel_scale_arcsec.toFixed(4)}"` : '—'} mono />
                </Panel>
              )}
            </div>

            {/* Right: comparison workspace */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

              {/* Comparison controls */}
              <Panel title="Comparison Controls">
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                  <button
                    className="btn-ghost"
                    onClick={() => setMode('side-by-side')}
                    disabled={!canCompare}
                    style={{ opacity: canCompare ? 1 : 0.4, cursor: canCompare ? 'pointer' : 'not-allowed',
                      ...(mode === 'side-by-side' && canCompare ? { borderColor: 'rgba(34,211,238,0.4)', color: '#22d3ee' } : {}) }}
                  >
                    <Layers size={13} /> Side by Side
                  </button>
                  <button
                    className="btn-ghost"
                    onClick={() => {
                      if (!canCompare) return
                      setMode('blink')
                      setBlinkActive(a => !a)
                    }}
                    disabled={!canCompare}
                    style={{ opacity: canCompare ? 1 : 0.4, cursor: canCompare ? 'pointer' : 'not-allowed',
                      ...(mode === 'blink' && canCompare ? { borderColor: 'rgba(34,211,238,0.4)', color: '#22d3ee' } : {}) }}
                  >
                    {blinkActive ? <Pause size={13} /> : <Play size={13} />} Blink Compare
                  </button>
                  <button
                    className="btn-ghost"
                    disabled
                    style={{ opacity: 0.4, cursor: 'not-allowed' }}
                  >
                    <ChevronLeft size={13} /><ChevronRight size={13} /> Slider
                  </button>
                  <div style={{ marginLeft: 'auto', fontSize: '0.72rem', color: '#4a6080' }}>
                    {canCompare ? `Blink: Epoch ${blinkFrame.toUpperCase()}` : 'Awaiting second epoch'}
                  </div>
                </div>
              </Panel>

              {/* Epoch panels */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                {/* Epoch A — real FITS viewer */}
                <div>
                  <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <SectionLabel>Epoch A — {meta.epoch_a.date_obs?.slice(0, 10) ?? '24 Apr 2025'}</SectionLabel>
                    <Badge variant="confirmed" label="REAL DATA" />
                  </div>
                  {(!canCompare || mode !== 'blink' || blinkFrame === 'a') && (
                    <ScientificImageViewer obsId={meta.epoch_a.obs_id} />
                  )}
                  {canCompare && mode === 'blink' && blinkFrame === 'b' && (
                    <div style={{ height: 200, background: '#020408', borderRadius: 8, border: '1px solid rgba(34,211,238,0.1)' }} />
                  )}
                </div>

                {/* Epoch B — not yet available */}
                <div>
                  <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <SectionLabel>Epoch B</SectionLabel>
                    <Badge variant="pending" label="AWAITING DATA" />
                  </div>
                  <div style={{
                    borderRadius: 8, overflow: 'hidden',
                    border: '1px dashed rgba(251,191,36,0.2)',
                    background: 'rgba(2,4,8,0.4)',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                    gap: 10, minHeight: 200, padding: 24, textAlign: 'center',
                  }}>
                    <AlertTriangle size={28} color="rgba(251,191,36,0.35)" />
                    <div style={{ fontSize: '0.82rem', color: '#fbbf24', fontWeight: 500 }}>Second epoch required</div>
                    <div style={{ fontSize: '0.72rem', color: '#4a6080', maxWidth: 200 }}>
                      A compatible SPHEREx observation has not yet been identified.
                    </div>
                  </div>
                </div>
              </div>

              {/* Difference analysis */}
              <Panel title="Difference Analysis">
                <div style={{ padding: '20px', textAlign: 'center', background: 'rgba(2,4,8,0.3)', border: '1px dashed rgba(34,211,238,0.1)', borderRadius: 6 }}>
                  <div style={{ fontSize: '0.85rem', color: '#4a6080', marginBottom: 8 }}>Difference image unavailable</div>
                  <div style={{ fontSize: '0.75rem', color: '#4a6080' }}>
                    Requires two scientifically compatible observations with verified WCS alignment.
                  </div>
                </div>
              </Panel>

              {/* Scientific note from backend */}
              <Panel title="Scientific Limitations">
                <div style={{ fontSize: '0.78rem', color: '#8899aa', lineHeight: 1.7, marginBottom: 12 }}>
                  {meta.scientific_note}
                </div>
                <LimitationList items={[
                  'Multi-epoch comparison has NOT yet been demonstrated.',
                  'A suitable second observation has NOT yet been established.',
                  'Only scientifically compatible observations may be compared.',
                  'WCS alignment must be verified before any difference analysis.',
                  'Calibration compatibility must be confirmed before comparison.',
                ]} />
              </Panel>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
