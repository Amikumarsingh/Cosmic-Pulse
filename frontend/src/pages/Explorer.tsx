import { useState, useCallback } from 'react'
import { Telescope, Info, Wifi, WifiOff, RefreshCw, Cpu } from 'lucide-react'
import FitsInspector from '../components/FitsInspector'
import ScientificImageViewer from '../components/ScientificImageViewer'
import Panel from '../components/Panel'
import CoordinateSearch from '../components/CoordinateSearch'
import { MetaRow, Badge, EmptyState, Loading, LimitationList, SectionLabel, ErrorMsg } from '../components/ui'
import {
  searchObservationsArchive, getObservationDetail,
  findRepeatObservations, checkHealth,
} from '../api'
import type { ArchiveObservation, ObservationDetail, RepeatObsResult } from '../types/archive'
import type { HealthStatus } from '../api'

type BackendStatus = (HealthStatus & { online: boolean }) | null

export default function Explorer() {
  const [searchResult, setSearchResult] = useState<{
    results: ArchiveObservation[]
    count: number
    tap_available: boolean
    tap_error: string | null
  } | null>(null)
  const [selected, setSelected] = useState<ObservationDetail | null>(null)
  const [repeats, setRepeats] = useState<RepeatObsResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState('')
  const [backendStatus, setBackendStatus] = useState<BackendStatus>(null)
  const [statusChecked, setStatusChecked] = useState(false)
  const [activeTab, setActiveTab] = useState<'detail' | 'fits'>('detail')

  const checkBackend = useCallback(async () => {
    const status = await checkHealth()
    setBackendStatus(status)
    setStatusChecked(true)
  }, [])

  const handleSearch = useCallback(async (ra: number, dec: number, radius: number) => {
    setLoading(true)
    setError('')
    setSelected(null)
    setRepeats(null)

    // Check backend on first search
    if (!statusChecked) await checkBackend()

    try {
      const result = await searchObservationsArchive({ ra, dec, radiusDeg: radius })
      setSearchResult(result)
      // Auto-load detail for first result
      if (result.results.length > 0) {
        await loadDetail(result.results[0].obs_id)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Search failed')
      setSearchResult(null)
    } finally {
      setLoading(false)
    }
  }, [statusChecked, checkBackend])

  const loadDetail = useCallback(async (obsId: string) => {
    setDetailLoading(true)
    try {
      const detail = await getObservationDetail(obsId)
      setSelected(detail)
      // Load repeat observations
      const rep = await findRepeatObservations(obsId, 0.5)
      setRepeats(rep)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load observation detail')
    } finally {
      setDetailLoading(false)
    }
  }, [])

  const verificationColor: Record<string, string> = {
    FITS_MAGIC_OK: '#4ade80',
    BYTE_RANGE_OK: '#22d3ee',
    HEADER_OK: '#fbbf24',
    URL_EXISTS: '#8899aa',
    UNKNOWN: '#f87171',
  }

  const classificationColor: Record<string, string> = {
    SPATIAL_OVERLAP_CONFIRMED: '#22d3ee',
    INSUFFICIENT_METADATA: '#fbbf24',
    NOT_COMPATIBLE: '#f87171',
  }

  return (
    <div style={{ paddingTop: 56, minHeight: '100vh' }}>
      {/* Page header */}
      <div style={{
        borderBottom: '1px solid rgba(34, 211, 238, 0.1)',
        padding: '28px 24px 20px',
        background: 'rgba(6, 13, 24, 0.4)',
      }}>
        <div className="page-container">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6, flexWrap: 'wrap' }}>
            <Telescope size={20} color="#22d3ee" />
            <h1 style={{ margin: 0, fontSize: '1.3rem', fontWeight: 700, color: '#f0f4f8' }}>
              Cosmic Explorer
            </h1>
            {backendStatus && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                {backendStatus.online
                  ? <Wifi size={13} color="#4ade80" />
                  : <WifiOff size={13} color="#f87171" />}
                <span style={{ fontSize: '0.7rem', color: backendStatus.online ? '#4ade80' : '#f87171' }}>
                  {backendStatus.online ? `Backend v${backendStatus.version}` : 'Backend offline'}
                </span>
                {backendStatus.online && (
                  <span style={{ fontSize: '0.7rem', color: backendStatus.fits_accessible ? '#4ade80' : '#fbbf24' }}>
                    · FITS {backendStatus.fits_verification_level}
                  </span>
                )}
              </div>
            )}
          </div>
          <p style={{ margin: 0, fontSize: '0.85rem', color: '#8899aa', maxWidth: 600 }}>
            Search real SPHEREx DR1 observations by sky coordinates. Connected to IRSA archive.
          </p>
        </div>
      </div>

      <div className="page-container" style={{ padding: '24px 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 20, alignItems: 'start' }}>

          {/* Left column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <Panel title="Coordinate Search">
              <CoordinateSearch onSearch={handleSearch} loading={loading} />
              <div style={{ marginTop: 12, padding: '10px 12px', background: 'rgba(34, 211, 238, 0.04)', borderRadius: 5, border: '1px solid rgba(34, 211, 238, 0.1)' }}>
                <div style={{ fontSize: '0.68rem', color: '#8899aa', lineHeight: 1.6 }}>
                  <div style={{ color: '#22d3ee', fontWeight: 600, marginBottom: 4 }}>KNOWN OBSERVATION</div>
                  RA: 160.6152° · Dec: 30.6691°
                  <br />
                  <span style={{ color: '#4a6080' }}>Search radius ≥ 0.1° to include it</span>
                </div>
              </div>
              {!statusChecked && (
                <button
                  onClick={checkBackend}
                  className="btn-ghost"
                  style={{ marginTop: 8, width: '100%', justifyContent: 'center' }}
                >
                  <RefreshCw size={12} /> Check backend status
                </button>
              )}
            </Panel>

            {/* Search results */}
            {loading && <Loading label="Querying IRSA archive…" />}
            {error && <ErrorMsg message={error} />}

            {searchResult && !loading && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <SectionLabel>{searchResult.count} result{searchResult.count !== 1 ? 's' : ''}</SectionLabel>
                  {!searchResult.tap_available && (
                    <span style={{ fontSize: '0.65rem', color: '#fbbf24' }}>TAP unavailable</span>
                  )}
                </div>

                {searchResult.count === 0 ? (
                  <EmptyState
                    icon={<Telescope size={28} />}
                    title="No observations found"
                    description="No SPHEREx observations found at these coordinates. Try RA: 160.6152, Dec: 30.6691 to find the known observation."
                  />
                ) : (
                  searchResult.results.map(obs => (
                    <div
                      key={obs.obs_id}
                      onClick={() => loadDetail(obs.obs_id)}
                      style={{
                        padding: '12px 14px', borderRadius: 7, cursor: 'pointer',
                        background: selected?.obs_id === obs.obs_id
                          ? 'rgba(34, 211, 238, 0.07)' : 'rgba(6, 13, 24, 0.5)',
                        border: `1px solid ${selected?.obs_id === obs.obs_id
                          ? 'rgba(34, 211, 238, 0.35)' : 'rgba(34, 211, 238, 0.1)'}`,
                        transition: 'all 0.15s',
                      }}
                      className="glass-hover"
                      role="button"
                      tabIndex={0}
                      onKeyDown={e => e.key === 'Enter' && loadDetail(obs.obs_id)}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: '#22d3ee', fontWeight: 600 }}>
                          {obs.obs_id}
                        </span>
                        {!obs.is_demo && <Badge variant="confirmed" label="REAL" />}
                        {obs.is_demo && <Badge variant="demo" />}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: '#8899aa' }}>
                        {obs.mission} · {obs.detector} · {obs.data_release}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: '#4a6080', marginTop: 3, fontFamily: 'var(--font-mono)' }}>
                        RA {obs.ra.toFixed(4)}° · Dec {obs.dec.toFixed(4)}°
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Right column — detail */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {detailLoading && <Loading label="Loading observation detail…" />}

            {selected && !detailLoading && (
              <div style={{ display: 'flex', gap: 0, marginBottom: 16, borderBottom: '1px solid rgba(34,211,238,0.12)' }}>
                {(['detail', 'fits'] as const).map(tab => (
                  <button key={tab} onClick={() => setActiveTab(tab)} style={{
                    padding: '8px 18px', border: 'none', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600,
                    background: 'transparent',
                    color: activeTab === tab ? '#22d3ee' : '#8899aa',
                    borderBottom: activeTab === tab ? '2px solid #22d3ee' : '2px solid transparent',
                  }}>
                    {tab === 'detail' ? <><Telescope size={12} style={{ marginRight: 5 }} />Observation</> : <><Cpu size={12} style={{ marginRight: 5 }} />FITS Inspector</>}
                  </button>
                ))}
              </div>
            )}

            {selected && !detailLoading && activeTab === 'fits' && (
              <FitsInspector obsId={selected.obs_id} />
            )}

            {selected && !detailLoading && activeTab === 'detail' ? (
              <>
                {/* Scientific image viewer */}
                <ScientificImageViewer obsId={selected.obs_id} />

                {/* Metadata grid */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <Panel title="Observation">
                    <MetaRow label="ID" value={selected.obs_id} mono />
                    <MetaRow label="Mission" value={selected.mission} />
                    <MetaRow label="Release" value={selected.data_release} />
                    <MetaRow label="Detector" value={selected.detector} mono highlight />
                    <MetaRow label="Calib level" value={String(selected.calib_level)} mono />
                    <MetaRow label="Date (UTC)" value={selected.date_obs?.replace('T', ' ').slice(0, 19) ?? '—'} mono />
                  </Panel>

                  <Panel title="Coordinates & WCS">
                    <MetaRow label="RA (J2000)" value={`${selected.ra.toFixed(6)}°`} mono highlight />
                    <MetaRow label="Dec (J2000)" value={`${selected.dec.toFixed(6)}°`} mono highlight />
                    <MetaRow label="NAXIS1" value={selected.naxis1 ? `${selected.naxis1} px` : '—'} mono />
                    <MetaRow label="NAXIS2" value={selected.naxis2 ? `${selected.naxis2} px` : '—'} mono />
                    <MetaRow label="BUNIT" value={selected.bunit ?? '—'} mono />
                    <MetaRow label="WCS type" value={selected.wcs_ctype1 ?? '—'} mono />
                  </Panel>
                </div>

                {/* FITS product access */}
                {selected.access && (
                  <Panel title="FITS Product Access">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                      <div style={{
                        width: 10, height: 10, borderRadius: '50%', flexShrink: 0,
                        background: verificationColor[selected.access.verification_level] ?? '#8899aa',
                        boxShadow: `0 0 6px ${verificationColor[selected.access.verification_level] ?? '#8899aa'}`,
                      }} />
                      <span style={{
                        fontSize: '0.78rem', fontWeight: 600,
                        color: verificationColor[selected.access.verification_level] ?? '#8899aa',
                      }}>
                        {selected.access.verification_level}
                      </span>
                    </div>
                    <MetaRow label="HTTP status" value={String(selected.access.http_status)} mono />
                    <MetaRow label="File size" value={selected.access.content_length_bytes
                      ? `${(selected.access.content_length_bytes / 1_048_576).toFixed(1)} MB` : '—'} mono />
                    <MetaRow label="Content type" value={selected.access.content_type ?? '—'} mono />
                    <MetaRow label="Byte-range" value={selected.access.byte_range_works ? 'Supported' : 'No'} />
                    <MetaRow label="FITS magic" value={selected.access.fits_magic_valid ? 'Valid (SIMPLE)' : 'Not verified'} />
                    {selected.access.error && (
                      <div style={{ marginTop: 8 }}>
                        <ErrorMsg message={selected.access.error} />
                      </div>
                    )}
                  </Panel>
                )}

                {/* FITS extensions */}
                {selected.known_extensions.length > 0 && (
                  <Panel title="FITS Extensions">
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {selected.known_extensions.map(ext => (
                        <div key={ext} style={{
                          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                          padding: '7px 10px', borderRadius: 5,
                          background: 'rgba(34, 211, 238, 0.03)',
                          border: '1px solid rgba(34, 211, 238, 0.08)',
                        }}>
                          <div>
                            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: '#22d3ee', fontWeight: 600 }}>
                              {ext}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                    <p style={{ fontSize: '0.68rem', color: '#4a6080', margin: '10px 0 0' }}>
                      Header dimensions, units, and WCS are read from the FITS product in the FITS Inspector tab.
                    </p>
                  </Panel>
                )}

                {/* Repeat observations */}
                {repeats && (
                  <Panel title="Repeat Observation Investigation">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                      <div style={{
                        padding: '3px 10px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 700,
                        background: `${classificationColor[repeats.classification] ?? '#8899aa'}18`,
                        color: classificationColor[repeats.classification] ?? '#8899aa',
                        border: `1px solid ${classificationColor[repeats.classification] ?? '#8899aa'}30`,
                      }}>
                        {repeats.classification.replace(/_/g, ' ')}
                      </div>
                      {!repeats.tap_available && (
                        <span style={{ fontSize: '0.68rem', color: '#fbbf24' }}>
                          TAP unavailable
                        </span>
                      )}
                    </div>

                    <p style={{ fontSize: '0.78rem', color: '#8899aa', lineHeight: 1.6, margin: '0 0 12px' }}>
                      {repeats.explanation}
                    </p>

                    {repeats.candidates_found > 0 && (
                      <div style={{ marginBottom: 12 }}>
                        <SectionLabel>Candidates ({repeats.candidates_found})</SectionLabel>
                        {repeats.candidates.map(c => (
                          <div key={c.obs_id} style={{
                            padding: '8px 10px', borderRadius: 5, marginTop: 6,
                            background: 'rgba(34, 211, 238, 0.03)',
                            border: '1px solid rgba(34, 211, 238, 0.08)',
                          }}>
                            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: '#22d3ee' }}>
                              {c.obs_id}
                            </div>
                            <div style={{ fontSize: '0.7rem', color: '#8899aa', marginTop: 3 }}>
                              {c.t_min_iso ?? c.t_min_mjd ?? '—'} · {c.band ?? '—'}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    <div style={{ padding: '10px 12px', background: 'rgba(251, 191, 36, 0.04)', border: '1px solid rgba(251, 191, 36, 0.12)', borderRadius: 5 }}>
                      <div style={{ fontSize: '0.7rem', color: '#8899aa', display: 'flex', gap: 6 }}>
                        <Info size={11} color="#fbbf24" style={{ flexShrink: 0, marginTop: 1 }} />
                        {repeats.scientific_note}
                      </div>
                    </div>

                    <div style={{ marginTop: 12 }}>
                      <SectionLabel>Compatibility Checks</SectionLabel>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 6 }}>
                        {Object.entries(repeats.compatibility_checks).map(([k, v]) => (
                          <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                            <span style={{ color: '#8899aa' }}>{k.replace(/_/g, ' ')}</span>
                            <span style={{
                              color: v === 'CONFIRMED' ? '#4ade80' : v === 'NOT_CHECKED' ? '#4a6080' : '#fbbf24',
                              fontFamily: 'var(--font-mono)', fontSize: '0.7rem',
                            }}>{v}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </Panel>
                )}

                <Panel title="Data Availability">
                  <LimitationList items={[
                    'IRSA TAP sync returns 502 for data queries (server-side issue).',
                    'Coordinate search falls back to known observation when TAP unavailable.',
                    'Repeat observation compatibility not yet verified.',
                    'TAN-SIP/PC WCS terms applied; product astrometry not independently verified.',
                    'Image preview requires full FITS download (~62 MB, cached after first load).',
                  ]} />
                </Panel>
              </>
            ) : !detailLoading && !loading && activeTab === 'detail' && (
              <div style={{
                height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center',
                border: '1px dashed rgba(34, 211, 238, 0.15)', borderRadius: 8,
              }}>
                <EmptyState
                  icon={<Telescope size={36} />}
                  title="No observation selected"
                  description="Search for observations using the coordinate panel. Try RA: 160.6152, Dec: 30.6691 to find the confirmed SPHEREx observation."
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
