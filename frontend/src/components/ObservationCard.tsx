import type { Observation } from '../types'
import { MetaRow, Badge } from './ui'
import { ImageOff } from 'lucide-react'

interface Props {
  observation: Observation
  selected?: boolean
  onClick?: () => void
}

export default function ObservationCard({ observation, selected, onClick }: Props) {
  const coverageColor: Record<string, string> = {
    available: '#4ade80', partial: '#fbbf24', unavailable: '#f87171', demo: '#a78bfa',
  }

  return (
    <div
      onClick={onClick}
      style={{
        background: selected ? 'rgba(34, 211, 238, 0.06)' : 'rgba(6, 13, 24, 0.5)',
        border: `1px solid ${selected ? 'rgba(34, 211, 238, 0.35)' : 'rgba(34, 211, 238, 0.1)'}`,
        borderRadius: 7,
        padding: '14px 16px',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.15s',
      }}
      className={onClick ? 'glass-hover' : undefined}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={e => e.key === 'Enter' && onClick?.()}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <div>
          <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#f0f4f8', fontFamily: 'var(--font-mono)' }}>
            {observation.observationId}
          </div>
          <div style={{ fontSize: '0.72rem', color: '#8899aa', marginTop: 2 }}>
            {observation.mission} · {observation.detector}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {observation.isDemo && <Badge variant="demo" />}
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: coverageColor[observation.coverageStatus],
            boxShadow: `0 0 6px ${coverageColor[observation.coverageStatus]}`,
          }} title={`Coverage: ${observation.coverageStatus}`} />
        </div>
      </div>

      {/* Image preview area */}
      <div style={{
        height: 80, borderRadius: 5, marginBottom: 10,
        background: 'rgba(2, 4, 8, 0.6)',
        border: '1px solid rgba(34, 211, 238, 0.08)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {observation.previewUrl ? (
          <img src={observation.previewUrl} alt="Observation preview" style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain' }} />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, color: '#4a6080' }}>
            <ImageOff size={18} />
            <span style={{ fontSize: '0.65rem' }}>Preview unavailable</span>
          </div>
        )}
      </div>

      <MetaRow label="Epoch" value={new Date(observation.epoch).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })} />
      <MetaRow label="RA / Dec" value={observation.ra === 0 && observation.dec === 0 ? 'Not confirmed' : `${observation.ra.toFixed(4)}° / ${observation.dec.toFixed(4)}°`} mono />
      <MetaRow label="Wavelength" value={`${observation.wavelengthMin}–${observation.wavelengthMax} μm`} mono />
    </div>
  )
}
