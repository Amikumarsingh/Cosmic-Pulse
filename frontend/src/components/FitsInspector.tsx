import { useState, useCallback } from 'react'
import { ChevronDown, ChevronRight, Layers, MapPin, Scissors } from 'lucide-react'
import Panel from './Panel'
import { MetaRow, Loading, ErrorMsg, SectionLabel, Badge } from './ui'
import { inspectFits, pixelToSky, skyToPixel, generateCutout } from '../api'
import type {
  FitsInspectResult, HduSummary, PixelToSkyResult, SkyToPixelResult, CutoutResult,
} from '../api'

interface Props { obsId: string }

const HDU_COLORS: Record<string, string> = {
  IMAGE: '#4ade80', FLAGS: '#fbbf24', VARIANCE: '#22d3ee',
  ZODI: '#a78bfa', EPSF: '#f472b6', 'WCS-WAVE': '#fb923c', PRIMARY: '#8899aa',
}

const inputStyle: React.CSSProperties = {
  background: 'rgba(6,13,24,0.8)', border: '1px solid rgba(34,211,238,0.2)',
  borderRadius: 4, color: '#f0f4f8', fontFamily: 'var(--font-mono)',
  fontSize: '0.78rem', padding: '5px 8px', width: '100%',
}
const btnStyle: React.CSSProperties = {
  padding: '6px 14px', borderRadius: 5, border: '1px solid rgba(34,211,238,0.3)',
  background: 'rgba(34,211,238,0.08)', color: '#22d3ee', cursor: 'pointer',
  fontSize: '0.78rem', fontWeight: 600, marginTop: 8,
}

function HduRow({ hdu, expanded, onToggle }: {
  hdu: HduSummary; expanded: boolean; onToggle: () => void
}) {
  const color = HDU_COLORS[hdu.extname] ?? '#8899aa'
  const shapeStr = hdu.shape.length > 0 ? hdu.shape.join('x') : '—'
  return (
    <div style={{ borderRadius: 6, border: '1px solid rgba(34,211,238,0.1)', overflow: 'hidden' }}>
      <button onClick={onToggle} style={{
        width: '100%', display: 'flex', alignItems: 'center', gap: 10,
        padding: '8px 12px', background: 'rgba(6,13,24,0.6)',
        border: 'none', cursor: 'pointer', textAlign: 'left',
      }}>
        {expanded ? <ChevronDown size={13} color="#8899aa" /> : <ChevronRight size={13} color="#8899aa" />}
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color, fontWeight: 600, minWidth: 80 }}>
          {hdu.extname}
        </span>
        <span style={{ fontSize: '0.72rem', color: '#8899aa', flex: 1 }}>{hdu.hdu_type}</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: '#4a6080' }}>{shapeStr}</span>
        {hdu.dtype && (
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.68rem', color: '#4a6080', marginLeft: 8 }}>
            {hdu.dtype}
          </span>
        )}
      </button>
      {expanded && (
        <div style={{ padding: '10px 14px', background: 'rgba(6,13,24,0.3)', borderTop: '1px solid rgba(34,211,238,0.06)' }}>
          <MetaRow label="HDU index" value={String(hdu.index)} mono />
          <MetaRow label="NAXIS" value={String(hdu.naxis)} mono />
          <MetaRow label="Shape" value={shapeStr} mono />
          {hdu.bitpix != null && <MetaRow label="BITPIX" value={String(hdu.bitpix)} mono />}
          {hdu.dtype && <MetaRow label="dtype" value={hdu.dtype} mono />}
          {hdu.bunit && <MetaRow label="BUNIT" value={hdu.bunit} mono highlight />}
          {hdu.table_columns.length > 0 && (
            <MetaRow label="Columns" value={hdu.table_columns.join(', ')} mono />
          )}
          {hdu.wcs_summary?.valid && (
            <>
              <div style={{ marginTop: 8, marginBottom: 4 }}><SectionLabel>WCS</SectionLabel></div>
              <MetaRow label="Projection" value={hdu.wcs_summary.projection ?? '—'} mono />
              {hdu.wcs_summary.pc_matrix && (
                <MetaRow label="PC matrix"
                  value={JSON.stringify(hdu.wcs_summary.pc_matrix)} mono />
              )}
              {hdu.wcs_summary.cd_matrix && (
                <MetaRow label="CD matrix"
                  value={JSON.stringify(hdu.wcs_summary.cd_matrix)} mono />
              )}
              {hdu.wcs_summary.cdelt1 != null && hdu.wcs_summary.cdelt2 != null && (
                <MetaRow label="CDELT"
                  value={`${hdu.wcs_summary.cdelt1}, ${hdu.wcs_summary.cdelt2}`} mono />
              )}
              <MetaRow label="CRVAL1 (RA)" value={(hdu.wcs_summary.crval1?.toFixed(6) ?? '—') + '°'} mono />
              <MetaRow label="CRVAL2 (Dec)" value={(hdu.wcs_summary.crval2?.toFixed(6) ?? '—') + '°'} mono />
              {hdu.wcs_summary.pixel_scale_arcsec != null && (
                <MetaRow label="Pixel scale"
                  value={`${hdu.wcs_summary.pixel_scale_arcsec.toFixed(4)} arcsec/px`} mono />
              )}
              {hdu.wcs_summary.center_ra != null && (
                <MetaRow label="Centre RA" value={hdu.wcs_summary.center_ra.toFixed(6) + '°'} mono />
              )}
              {hdu.wcs_summary.center_dec != null && (
                <MetaRow label="Centre Dec" value={hdu.wcs_summary.center_dec.toFixed(6) + '°'} mono />
              )}
              {hdu.wcs_summary.center_note && (
                <div style={{ fontSize: '0.68rem', color: '#4a6080', marginTop: 4, fontStyle: 'italic' }}>
                  {hdu.wcs_summary.center_note}
                </div>
              )}
              {hdu.wcs_summary.has_sip && (
                <div style={{ fontSize: '0.68rem', color: '#fbbf24', marginTop: 4 }}>
                  SIP distortion applied by the TAN-SIP transform; product astrometry not independently calibrated.
                </div>
              )}
            </>
          )}
          {hdu.notes.map((n, i) => (
            <div key={i} style={{ fontSize: '0.7rem', color: '#fbbf24', marginTop: 6, display: 'flex', gap: 6 }}>
              <span style={{ flexShrink: 0 }}>!</span>{n}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function FitsInspector({ obsId }: Props) {
  const [inspect, setInspect] = useState<FitsInspectResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState<Record<number, boolean>>({})

  const [px, setPx] = useState('1020.5')
  const [py, setPy] = useState('1020.5')
  const [ptsResult, setPtsResult] = useState<PixelToSkyResult | null>(null)
  const [ptsErr, setPtsErr] = useState('')
  const [ptsLoading, setPtsLoading] = useState(false)

  const [sra, setSra] = useState('160.615237')
  const [sdec, setSdec] = useState('30.669077')
  const [stpResult, setStpResult] = useState<SkyToPixelResult | null>(null)
  const [stpErr, setStpErr] = useState('')
  const [stpLoading, setStpLoading] = useState(false)

  const [cra, setCra] = useState('160.615237')
  const [cdec, setCdec] = useState('30.669077')
  const [cw, setCw] = useState('128')
  const [ch, setCh] = useState('128')
  const [cutout, setCutout] = useState<CutoutResult | null>(null)
  const [cutoutErr, setCutoutErr] = useState('')
  const [cutoutLoading, setCutoutLoading] = useState(false)

  const doInspect = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const r = await inspectFits(obsId)
      setInspect(r)
      if (r.hdus.length > 0) setExpanded({ 0: true })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Inspection failed')
    } finally { setLoading(false) }
  }, [obsId])

  const doPixelToSky = useCallback(async () => {
    setPtsLoading(true); setPtsErr(''); setPtsResult(null)
    try { setPtsResult(await pixelToSky(obsId, parseFloat(px), parseFloat(py))) }
    catch (e) { setPtsErr(e instanceof Error ? e.message : 'Failed') }
    finally { setPtsLoading(false) }
  }, [obsId, px, py])

  const doSkyToPixel = useCallback(async () => {
    setStpLoading(true); setStpErr(''); setStpResult(null)
    try { setStpResult(await skyToPixel(obsId, parseFloat(sra), parseFloat(sdec))) }
    catch (e) { setStpErr(e instanceof Error ? e.message : 'Failed') }
    finally { setStpLoading(false) }
  }, [obsId, sra, sdec])

  const doCutout = useCallback(async () => {
    setCutoutLoading(true); setCutoutErr(''); setCutout(null)
    try {
      setCutout(await generateCutout(obsId, parseFloat(cra), parseFloat(cdec), parseInt(cw), parseInt(ch)))
    } catch (e) { setCutoutErr(e instanceof Error ? e.message : 'Failed') }
    finally { setCutoutLoading(false) }
  }, [obsId, cra, cdec, cw, ch])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      <Panel title="FITS Product Status">
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          {inspect ? (
            <>
              <Badge variant={inspect.reachable ? 'confirmed' : 'rejected'}
                label={inspect.reachable ? 'REACHABLE' : 'UNREACHABLE'} />
              <Badge variant={inspect.header_readable ? 'confirmed' : 'rejected'}
                label={inspect.header_readable ? 'HEADERS OK' : 'HEADERS FAIL'} />
              <Badge variant={inspect.hdus_inspected ? 'confirmed' : 'pending'}
                label={inspect.hdus_inspected ? 'HDUS INSPECTED' : 'NOT INSPECTED'} />
              <Badge variant="live"
                label={inspect.access_method.replace(/_/g, ' ').toUpperCase()} />
            </>
          ) : (
            <span style={{ fontSize: '0.78rem', color: '#8899aa' }}>Not yet inspected</span>
          )}
        </div>
        {inspect && (
          <>
            <MetaRow label="Obs ID" value={inspect.obs_id} mono />
            <MetaRow label="HDU count" value={String(inspect.hdu_count)} mono />
            <MetaRow label="Access method" value={inspect.access_method} mono />
            {inspect.error && <div style={{ marginTop: 8 }}><ErrorMsg message={inspect.error} /></div>}
          </>
        )}
        <button onClick={doInspect} style={btnStyle} disabled={loading}>
          {loading ? 'Inspecting…' : inspect ? 'Re-inspect FITS' : 'Inspect FITS Product'}
        </button>
        {loading && <Loading label="Reading FITS headers via byte-range…" />}
        {error && <ErrorMsg message={error} />}
      </Panel>

      {inspect?.hdus_inspected && (
        <Panel title="HDU Explorer">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <Layers size={13} color="#22d3ee" />
            <span style={{ fontSize: '0.75rem', color: '#8899aa' }}>
              {inspect.hdu_count} extensions — click to expand
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {inspect.hdus.map(hdu => (
              <HduRow key={hdu.index} hdu={hdu} expanded={!!expanded[hdu.index]}
                onToggle={() => setExpanded(e => ({ ...e, [hdu.index]: !e[hdu.index] }))} />
            ))}
          </div>
        </Panel>
      )}

      <Panel title="Coordinate Tools">
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
          <MapPin size={13} color="#22d3ee" />
          <span style={{ fontSize: '0.72rem', color: '#8899aa' }}>
            TAN/TAN-SIP coordinates from IMAGE WCS; product astrometry is not independently calibrated.
          </span>
        </div>
        <SectionLabel>Pixel to Sky (FITS 1-based)</SectionLabel>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 6 }}>
          <div>
            <div style={{ fontSize: '0.68rem', color: '#8899aa', marginBottom: 3 }}>X pixel</div>
            <input style={inputStyle} value={px} onChange={e => setPx(e.target.value)} />
          </div>
          <div>
            <div style={{ fontSize: '0.68rem', color: '#8899aa', marginBottom: 3 }}>Y pixel</div>
            <input style={inputStyle} value={py} onChange={e => setPy(e.target.value)} />
          </div>
        </div>
        <button onClick={doPixelToSky} style={btnStyle} disabled={ptsLoading}>
          {ptsLoading ? 'Converting…' : 'Pixel to Sky'}
        </button>
        {ptsErr && <ErrorMsg message={ptsErr} />}
        {ptsResult && (
          <div style={{ marginTop: 8 }}>
            <MetaRow label="RA" value={`${ptsResult.ra_deg.toFixed(8)}°`} mono highlight />
            <MetaRow label="Dec" value={`${ptsResult.dec_deg.toFixed(8)}°`} mono highlight />
            <MetaRow label="Frame" value={ptsResult.coordinate_frame} mono />
            <div style={{ fontSize: '0.66rem', color: '#fbbf24', marginTop: 5 }}>
              {ptsResult.wcs_note}
            </div>
          </div>
        )}

        <div style={{ margin: '14px 0 6px', borderTop: '1px solid rgba(34,211,238,0.08)', paddingTop: 12 }}>
          <SectionLabel>Sky to Pixel</SectionLabel>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 6 }}>
          <div>
            <div style={{ fontSize: '0.68rem', color: '#8899aa', marginBottom: 3 }}>RA (deg)</div>
            <input style={inputStyle} value={sra} onChange={e => setSra(e.target.value)} />
          </div>
          <div>
            <div style={{ fontSize: '0.68rem', color: '#8899aa', marginBottom: 3 }}>Dec (deg)</div>
            <input style={inputStyle} value={sdec} onChange={e => setSdec(e.target.value)} />
          </div>
        </div>
        <button onClick={doSkyToPixel} style={btnStyle} disabled={stpLoading}>
          {stpLoading ? 'Converting…' : 'Sky to Pixel'}
        </button>
        {stpErr && <ErrorMsg message={stpErr} />}
        {stpResult && (
          <div style={{ marginTop: 8 }}>
            <MetaRow label="X (FITS)" value={stpResult.x_fits.toFixed(3)} mono highlight />
            <MetaRow label="Y (FITS)" value={stpResult.y_fits.toFixed(3)} mono highlight />
            <MetaRow label="In bounds" value={stpResult.in_bounds ? 'Yes' : 'No'} />
            <div style={{ fontSize: '0.66rem', color: '#fbbf24', marginTop: 5 }}>
              {stpResult.wcs_note}
            </div>
          </div>
        )}
      </Panel>

      <Panel title="Cutout Workspace">
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
          <Scissors size={13} color="#22d3ee" />
          <span style={{ fontSize: '0.72rem', color: '#8899aa' }}>
            Coordinate-aware cutout from IMAGE extension with translated WCS
          </span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {[
            ['RA (deg)', cra, setCra], ['Dec (deg)', cdec, setCdec],
            ['Width (px)', cw, setCw], ['Height (px)', ch, setCh],
          ].map(([label, val, setter]) => (
            <div key={label as string}>
              <div style={{ fontSize: '0.68rem', color: '#8899aa', marginBottom: 3 }}>{label as string}</div>
              <input style={inputStyle} value={val as string}
                onChange={e => (setter as (v: string) => void)(e.target.value)} />
            </div>
          ))}
        </div>
        <button onClick={doCutout} style={btnStyle} disabled={cutoutLoading}>
          {cutoutLoading ? 'Generating…' : 'Generate Cutout'}
        </button>
        {cutoutErr && <ErrorMsg message={cutoutErr} />}
        {cutout && (
          <div style={{ marginTop: 10 }}>
            <div style={{ marginBottom: 8 }}>
              <Badge variant="confirmed" label="CUTOUT GENERATED" />
            </div>
            <MetaRow label="Shape" value={cutout.actual_shape.join('x') + ' px'} mono highlight />
            <MetaRow label="BUNIT" value={cutout.bunit ?? '—'} mono />
            <MetaRow label="Centre X (FITS)" value={cutout.center_x_fits.toFixed(3)} mono />
            <MetaRow label="Centre Y (FITS)" value={cutout.center_y_fits.toFixed(3)} mono />
            <MetaRow label="CRPIX parent" value={cutout.crpix_parent.map(v => v.toFixed(2)).join(', ')} mono />
            <MetaRow label="CRPIX cutout" value={cutout.crpix_cutout.map(v => v.toFixed(2)).join(', ')} mono />
            <MetaRow label="WCS valid" value={cutout.wcs_valid ? 'Yes' : 'No'} />
            <MetaRow label="Partial" value={cutout.partial ? 'Yes (edge)' : 'No'} />
            <MetaRow label="Output file" value={cutout.output_filename} mono />
            <div style={{ marginTop: 8, fontSize: '0.68rem', color: '#4a6080', lineHeight: 1.6 }}>
              {cutout.processing_note}
            </div>
          </div>
        )}
      </Panel>
    </div>
  )
}
