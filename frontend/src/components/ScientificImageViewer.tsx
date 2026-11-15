import { useState, useCallback, useRef, useEffect } from 'react'
import { ZoomIn, ZoomOut, RotateCcw, Info, AlertTriangle } from 'lucide-react'
import { getPreviewUrl, getImageInfo } from '../api'
import type { ImageInfoResult, StretchMode } from '../api'
import { MetaRow, Loading, ErrorMsg, SectionLabel } from './ui'

interface Props {
  obsId: string
  initialStretch?: StretchMode
}

const STRETCHES: { value: StretchMode; label: string }[] = [
  { value: 'zscale', label: 'ZScale' },
  { value: 'linear', label: 'Linear' },
  { value: 'log',    label: 'Log' },
  { value: 'asinh',  label: 'Asinh' },
]

const PREVIEW_SIZE = 512

function fmt(v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return '—'
  return v.toExponential(4)
}

const btnBase: React.CSSProperties = {
  padding: '5px 10px', borderRadius: 4,
  border: '1px solid rgba(34,211,238,0.2)',
  background: 'rgba(34,211,238,0.06)', color: '#22d3ee',
  cursor: 'pointer', fontSize: '0.72rem',
  display: 'flex', alignItems: 'center', gap: 4,
}
const btnActive: React.CSSProperties = {
  ...btnBase,
  background: 'rgba(34,211,238,0.18)',
  borderColor: 'rgba(34,211,238,0.5)',
  color: '#f0f4f8', fontWeight: 700,
}

export default function ScientificImageViewer({ obsId, initialStretch = 'zscale' }: Props) {
  const [stretch, setStretch] = useState<StretchMode>(initialStretch)
  const [pendingStretch, setPendingStretch] = useState<StretchMode>(initialStretch)
  const [imgSrc, setImgSrc] = useState<string | null>(null)
  const [imgLoading, setImgLoading] = useState(false)
  const [imgError, setImgError] = useState('')
  const [info, setInfo] = useState<ImageInfoResult | null>(null)
  const [infoLoading, setInfoLoading] = useState(false)
  const [showInfo, setShowInfo] = useState(false)

  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [dragging, setDragging] = useState(false)
  const dragStart = useRef<{ mx: number; my: number; px: number; py: number } | null>(null)
  const [hoverPos, setHoverPos] = useState<{ x: number; y: number } | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const stretchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const loadPreview = useCallback((s: StretchMode) => {
    setImgLoading(true)
    setImgError('')
    let url: string
    try {
      url = getPreviewUrl(obsId, s, PREVIEW_SIZE)
    } catch (e) {
      setImgError(e instanceof Error ? e.message : 'Preview configuration is unavailable.')
      setImgLoading(false)
      return
    }
    const img = new Image()
    img.onload = () => { setImgSrc(url); setImgLoading(false) }
    img.onerror = () => {
      setImgError('Preview failed. The FITS file may not be cached yet — try again in a moment.')
      setImgLoading(false)
    }
    img.src = url
  }, [obsId])

  const loadInfo = useCallback(async () => {
    setInfoLoading(true)
    try { setInfo(await getImageInfo(obsId)) }
    catch { /* info is optional */ }
    finally { setInfoLoading(false) }
  }, [obsId])

  useEffect(() => {
    loadPreview(stretch)
    loadInfo()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleStretchChange = (s: StretchMode) => {
    setPendingStretch(s)
    if (stretchTimer.current) clearTimeout(stretchTimer.current)
    stretchTimer.current = setTimeout(() => { setStretch(s); loadPreview(s) }, 300)
  }

  const resetView = () => { setZoom(1); setPan({ x: 0, y: 0 }) }

  const onMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return
    setDragging(true)
    dragStart.current = { mx: e.clientX, my: e.clientY, px: pan.x, py: pan.y }
  }
  const onMouseMove = (e: React.MouseEvent) => {
    if (dragging && dragStart.current) {
      setPan({
        x: dragStart.current.px + (e.clientX - dragStart.current.mx),
        y: dragStart.current.py + (e.clientY - dragStart.current.my),
      })
    }
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect()
      const cx = (e.clientX - rect.left - rect.width / 2 - pan.x) / zoom
      const cy = (e.clientY - rect.top - rect.height / 2 - pan.y) / zoom
      const ix = Math.round(cx + PREVIEW_SIZE / 2)
      const iy = Math.round(cy + PREVIEW_SIZE / 2)
      setHoverPos(ix >= 0 && ix < PREVIEW_SIZE && iy >= 0 && iy < PREVIEW_SIZE ? { x: ix, y: iy } : null)
    }
  }
  const onMouseUp = () => { setDragging(false); dragStart.current = null }
  const onMouseLeave = () => { setDragging(false); dragStart.current = null; setHoverPos(null) }
  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault()
    setZoom(z => Math.max(0.25, Math.min(8, z * (e.deltaY < 0 ? 1.15 : 0.87))))
  }

  const scale = info ? info.naxis1 / PREVIEW_SIZE : 4
  const fitsPx = hoverPos ? { x: Math.round(hoverPos.x * scale + 1), y: Math.round(hoverPos.y * scale + 1) } : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', borderRadius: 8, overflow: 'hidden', border: '1px solid rgba(34,211,238,0.12)' }}>

      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', padding: '10px 14px', background: 'rgba(6,13,24,0.85)', borderBottom: '1px solid rgba(34,211,238,0.1)' }}>
        <div style={{ display: 'flex', gap: 4 }}>
          {STRETCHES.map(s => (
            <button key={s.value} onClick={() => handleStretchChange(s.value)}
              style={pendingStretch === s.value ? btnActive : btnBase}>
              {s.label}
            </button>
          ))}
        </div>
        <div style={{ width: 1, height: 20, background: 'rgba(34,211,238,0.15)', margin: '0 2px' }} />
        <button onClick={() => setZoom(z => Math.min(8, z * 1.5))} style={btnBase} title="Zoom in"><ZoomIn size={13} /></button>
        <button onClick={() => setZoom(z => Math.max(0.25, z / 1.5))} style={btnBase} title="Zoom out"><ZoomOut size={13} /></button>
        <button onClick={resetView} style={btnBase} title="Reset view"><RotateCcw size={13} /></button>
        <span style={{ fontSize: '0.7rem', color: '#4a6080', fontFamily: 'var(--font-mono)' }}>{(zoom * 100).toFixed(0)}%</span>
        <div style={{ flex: 1 }} />
        <button onClick={() => { setShowInfo(v => !v); if (!info && !infoLoading) loadInfo() }}
          style={showInfo ? btnActive : btnBase} title="Image statistics">
          <Info size={13} /> Stats
        </button>
      </div>

      {/* Viewer + stats */}
      <div style={{ display: 'flex' }}>
        <div ref={containerRef} onMouseDown={onMouseDown} onMouseMove={onMouseMove}
          onMouseUp={onMouseUp} onMouseLeave={onMouseLeave} onWheel={onWheel}
          style={{ flex: 1, height: 480, overflow: 'hidden', position: 'relative', background: '#020408', cursor: dragging ? 'grabbing' : 'crosshair', userSelect: 'none' }}>

          {imgLoading && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
              <Loading label="Rendering FITS IMAGE HDU…" />
              <div style={{ fontSize: '0.72rem', color: '#4a6080', textAlign: 'center', maxWidth: 280 }}>
                First load requires full FITS download (~62 MB). Subsequent loads use cache.
              </div>
            </div>
          )}

          {imgError && !imgLoading && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 24, gap: 12 }}>
              <AlertTriangle size={28} color="#fbbf24" />
              <ErrorMsg message={imgError} />
              <button onClick={() => loadPreview(stretch)} style={{ ...btnBase, marginTop: 4 }}>Retry</button>
            </div>
          )}

          {imgSrc && !imgLoading && (
            <img src={imgSrc} alt={`SPHEREx IMAGE HDU — ${stretch} stretch`} draggable={false}
              style={{ position: 'absolute', left: '50%', top: '50%',
                transform: `translate(calc(-50% + ${pan.x}px), calc(-50% + ${pan.y}px)) scale(${zoom})`,
                transformOrigin: 'center center',
                imageRendering: zoom > 2 ? 'pixelated' : 'auto',
                width: PREVIEW_SIZE, height: PREVIEW_SIZE, display: 'block' }} />
          )}

          {hoverPos && fitsPx && (
            <div style={{ position: 'absolute', bottom: 10, left: 10, background: 'rgba(2,4,8,0.88)', border: '1px solid rgba(34,211,238,0.2)', borderRadius: 4, padding: '4px 10px', fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: '#22d3ee', pointerEvents: 'none' }}>
              FITS ({fitsPx.x}, {fitsPx.y})
              {info?.wcs_valid && <span style={{ color: '#fbbf24', marginLeft: 8, fontSize: '0.65rem' }}>FITS pixel; sky WCS not independently calibrated</span>}
            </div>
          )}

          {imgSrc && !imgLoading && (
            <div style={{ position: 'absolute', top: 10, right: 10, background: 'rgba(2,4,8,0.75)', border: '1px solid rgba(34,211,238,0.12)', borderRadius: 4, padding: '3px 8px', fontSize: '0.65rem', color: '#8899aa', fontFamily: 'var(--font-mono)', pointerEvents: 'none' }}>
              {stretch.toUpperCase()} · {info?.bunit ?? 'unit unavailable'} · IMAGE HDU
            </div>
          )}
        </div>

        {showInfo && (
          <div style={{ width: 220, borderLeft: '1px solid rgba(34,211,238,0.1)', background: 'rgba(6,13,24,0.85)', padding: '12px 14px', overflowY: 'auto', flexShrink: 0 }}>
            <SectionLabel>Image Statistics</SectionLabel>
            {infoLoading && <Loading label="Loading…" />}
            {info && (
              <div style={{ marginTop: 8 }}>
                <MetaRow label="Source" value="IMAGE HDU" mono />
                <MetaRow label="Dimensions" value={`${info.naxis1}×${info.naxis2}`} mono />
                <MetaRow label="dtype" value={info.dtype} mono />
                <MetaRow label="BUNIT" value={info.bunit ?? '—'} mono highlight />
                <MetaRow label="Pixel scale" value={info.pixel_scale_arcsec != null ? `${info.pixel_scale_arcsec.toFixed(4)}"` : '—'} mono />
                <div style={{ margin: '8px 0 4px', borderTop: '1px solid rgba(34,211,238,0.08)', paddingTop: 8 }}>
                  <SectionLabel>Pixel values</SectionLabel>
                </div>
                <MetaRow label="Min" value={fmt(info.data_min)} mono />
                <MetaRow label="Max" value={fmt(info.data_max)} mono />
                <MetaRow label="Mean" value={fmt(info.data_mean)} mono />
                <MetaRow label="Median" value={fmt(info.data_median)} mono />
                <MetaRow label="NaN px" value={String(info.nan_count)} mono />
                <MetaRow label="Inf px" value={String(info.inf_count)} mono />
                <MetaRow label="Total px" value={info.total_pixels.toLocaleString()} mono />
                <div style={{ marginTop: 10, padding: '8px 10px', background: 'rgba(251,191,36,0.04)', border: '1px solid rgba(251,191,36,0.12)', borderRadius: 4 }}>
                  <div style={{ fontSize: '0.65rem', color: '#8899aa', lineHeight: 1.6 }}>
                    Stretch affects display only. Original pixel values unchanged.
                    {info.wcs_valid && ' Sky coordinates use the product TAN-SIP WCS; astrometric calibration is not independently verified.'}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Caption */}
      <div style={{ padding: '6px 14px', background: 'rgba(6,13,24,0.7)', borderTop: '1px solid rgba(34,211,238,0.08)', fontSize: '0.65rem', color: '#4a6080', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <span>SPHEREx DR1 · {obsId} · IMAGE HDU · 2040×2040 px · float32 · {info?.bunit ?? 'unit unavailable'}</span>
        <span>Scroll to zoom · drag to pan</span>
        <span style={{ color: '#fbbf24' }}>Display only — no background subtraction applied</span>
      </div>
    </div>
  )
}
