import { useState } from 'react'
import { Search } from 'lucide-react'

interface Props {
  onSearch: (ra: number, dec: number, radius: number) => void
  loading?: boolean
}

export default function CoordinateSearch({ onSearch, loading }: Props) {
  const [ra, setRa] = useState('')
  const [dec, setDec] = useState('')
  const [radius, setRadius] = useState('0.5')
  const [error, setError] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    const raNum = parseFloat(ra)
    const decNum = parseFloat(dec)
    const radNum = parseFloat(radius)
    if (isNaN(raNum) || raNum < 0 || raNum >= 360) { setError('RA must be 0–360 degrees'); return }
    if (isNaN(decNum) || decNum < -90 || decNum > 90) { setError('Dec must be −90 to +90 degrees'); return }
    if (isNaN(radNum) || radNum <= 0 || radNum > 5) { setError('Search radius must be 0–5 degrees'); return }
    onSearch(raNum, decNum, radNum)
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <div>
          <label style={{ display: 'block', fontSize: '0.7rem', color: '#8899aa', marginBottom: 4, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            Right Ascension (°)
          </label>
          <input
            className="input-field"
            type="number"
            step="any"
            min="0"
            max="360"
            placeholder="0.000"
            value={ra}
            onChange={e => setRa(e.target.value)}
            aria-label="Right Ascension in degrees"
          />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.7rem', color: '#8899aa', marginBottom: 4, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            Declination (°)
          </label>
          <input
            className="input-field"
            type="number"
            step="any"
            min="-90"
            max="90"
            placeholder="0.000"
            value={dec}
            onChange={e => setDec(e.target.value)}
            aria-label="Declination in degrees"
          />
        </div>
      </div>
      <div>
        <label style={{ display: 'block', fontSize: '0.7rem', color: '#8899aa', marginBottom: 4, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          Search Radius (°)
        </label>
        <input
          className="input-field"
          type="number"
          step="0.1"
          min="0.01"
          max="5"
          placeholder="0.5"
          value={radius}
          onChange={e => setRadius(e.target.value)}
          aria-label="Search radius in degrees"
        />
      </div>
      {error && (
        <div style={{ fontSize: '0.78rem', color: '#f87171', padding: '6px 10px', background: 'rgba(239,68,68,0.08)', borderRadius: 4 }}>
          {error}
        </div>
      )}
      <button
        type="submit"
        className="btn-primary"
        disabled={loading}
        style={{ justifyContent: 'center', opacity: loading ? 0.6 : 1 }}
      >
        <Search size={14} />
        {loading ? 'Searching…' : 'Search Observations'}
      </button>
    </form>
  )
}
