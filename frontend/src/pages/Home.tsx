import { Link } from 'react-router-dom'
import { Telescope, Clock, FlaskConical, Archive, ArrowRight, ChevronRight } from 'lucide-react'

const MODULES = [
  {
    to: '/explorer',
    icon: Telescope,
    name: 'Cosmic Explorer',
    tagline: 'Navigate the sky',
    description: 'Search real SPHEREx observations by sky coordinates. Inspect FITS metadata, detector information, and observation footprints.',
    status: 'available' as const,
    color: '#22d3ee',
  },
  {
    to: '/time-machine',
    icon: Clock,
    name: 'Cosmic Time Machine',
    tagline: 'Compare across time',
    description: 'Inspect the one confirmed real epoch. Comparison controls remain unavailable until a second compatible observation is verified.',
    status: 'partial' as const,
    color: '#a78bfa',
  },
  {
    to: '/lab',
    icon: FlaskConical,
    name: 'Discovery Lab',
    tagline: 'Measure and investigate',
    description: 'Run source detection and aperture photometry on the genuine full-resolution SPHEREx image, with parameters and limitations disclosed.',
    status: 'available' as const,
    color: '#67e8f9',
  },
  {
    to: '/capsules',
    icon: Archive,
    name: 'Evidence Capsules',
    tagline: 'Preserve the record',
    description: 'Preview and export an explicitly labelled example capsule. Live analysis results are not yet saved into capsules.',
    status: 'partial' as const,
    color: '#c4b5fd',
  },
]

const WORKFLOW_STEPS = [
  { step: 'SELECT',  desc: 'Choose a sky region or target coordinates' },
  { step: 'EXPLORE', desc: 'Find and inspect real observations' },
  { step: 'REPLAY',  desc: 'Compare observations across time' },
  { step: 'ANALYZE', desc: 'Measure brightness, position, and quality' },
  { step: 'DOCUMENT', desc: 'Review limitations and export an example record' },
]

export default function Home() {
  return (
    <div style={{ paddingTop: 56 }}>
      {/* Hero */}
      <section
        className="star-field nebula-glow"
        style={{
          minHeight: '92vh',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          textAlign: 'center', padding: '80px 24px 60px',
          position: 'relative', overflow: 'hidden',
        }}
      >
        {/* Subtle radial glow behind title */}
        <div style={{
          position: 'absolute', top: '40%', left: '50%', transform: 'translate(-50%, -50%)',
          width: 600, height: 400,
          background: 'radial-gradient(ellipse, rgba(34, 211, 238, 0.06) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        <div className="fade-in" style={{ position: 'relative', maxWidth: 720 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 24 }}>
            <div style={{
              width: 40, height: 40, borderRadius: '50%',
              background: 'radial-gradient(circle at 35% 35%, #22d3ee, #8b5cf6)',
              boxShadow: '0 0 24px rgba(34, 211, 238, 0.5)',
            }} />
            <span style={{ fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.2em', color: '#22d3ee', textTransform: 'uppercase' }}>
              Cosmic Pulse
            </span>
          </div>

          <h1 style={{
            fontSize: 'clamp(2.4rem, 6vw, 4.2rem)',
            fontWeight: 800, lineHeight: 1.1,
            color: '#f0f4f8', margin: '0 0 8px',
            letterSpacing: '-0.02em',
          }}>
            The universe is not
            <br />
            <span className="text-gradient-cyan">a picture.</span>
          </h1>
          <h2 style={{
            fontSize: 'clamp(1.6rem, 4vw, 2.8rem)',
            fontWeight: 300, color: 'rgba(240, 244, 248, 0.6)',
            margin: '0 0 28px', letterSpacing: '-0.01em',
          }}>
            It's an unfolding story.
          </h2>

          <p style={{
            fontSize: '1.05rem', color: '#8899aa', lineHeight: 1.7,
            maxWidth: 560, margin: '0 auto 40px',
          }}>
            Explore real astronomical observations, investigate possible changes,
            and preserve the evidence behind every discovery.
          </p>

          <div style={{ display: 'flex', gap: 14, justifyContent: 'center', flexWrap: 'wrap' }}>
            <Link to="/explorer" className="btn-primary" style={{ padding: '13px 32px', fontSize: '0.9rem' }}>
              Start an Investigation
              <ArrowRight size={16} />
            </Link>
            <Link to="/about" className="btn-secondary" style={{ padding: '13px 32px', fontSize: '0.9rem' }}>
              Explore the Platform
            </Link>
          </div>

          <p style={{ fontSize: '0.72rem', color: '#4a6080', lineHeight: 1.6, maxWidth: 620, margin: '24px auto 0' }}>
            Research prototype using one SPHEREx DR1 observation. Source detections are measurements, not confirmed discoveries or transients; astrometric calibration is not independently verified.
          </p>

          <div style={{ marginTop: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
            <div className="badge-demo">DEMO MODE</div>
            <span style={{ fontSize: '0.75rem', color: '#4a6080' }}>
              SPHEREx DR1 · Observation 2025W17_4B_0001_1 · Single epoch
            </span>
          </div>
        </div>

        {/* Scroll indicator */}
        <div style={{
          position: 'absolute', bottom: 32, left: '50%', transform: 'translateX(-50%)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
          color: '#4a6080', fontSize: '0.65rem', letterSpacing: '0.1em',
        }}>
          <span>SCROLL</span>
          <div style={{ width: 1, height: 32, background: 'linear-gradient(to bottom, rgba(34,211,238,0.4), transparent)' }} />
        </div>
      </section>

      {/* Workflow */}
      <section style={{ padding: '80px 24px', background: 'rgba(6, 13, 24, 0.5)' }}>
        <div className="page-container">
          <div style={{ textAlign: 'center', marginBottom: 48 }}>
            <div className="section-label" style={{ justifyContent: 'center', display: 'flex', marginBottom: 8 }}>Investigation Workflow</div>
            <h2 style={{ fontSize: '1.8rem', fontWeight: 700, color: '#f0f4f8', margin: 0 }}>
              From observation to evidence
            </h2>
          </div>

          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            gap: 0, flexWrap: 'wrap',
          }}>
            {WORKFLOW_STEPS.map((w, i) => (
              <div key={w.step} style={{ display: 'flex', alignItems: 'center' }}>
                <div style={{ textAlign: 'center', padding: '0 16px' }}>
                  <div style={{
                    width: 48, height: 48, borderRadius: '50%',
                    background: 'rgba(34, 211, 238, 0.08)',
                    border: '1px solid rgba(34, 211, 238, 0.25)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    margin: '0 auto 10px',
                    fontSize: '0.7rem', fontWeight: 700, color: '#22d3ee',
                  }}>
                    {i + 1}
                  </div>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.1em', color: '#22d3ee', marginBottom: 4 }}>
                    {w.step}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: '#8899aa', maxWidth: 100 }}>{w.desc}</div>
                </div>
                {i < WORKFLOW_STEPS.length - 1 && (
                  <ChevronRight size={16} color="rgba(34, 211, 238, 0.3)" style={{ flexShrink: 0 }} />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Modules */}
      <section style={{ padding: '80px 24px' }}>
        <div className="page-container">
          <div style={{ textAlign: 'center', marginBottom: 48 }}>
            <div className="section-label" style={{ justifyContent: 'center', display: 'flex', marginBottom: 8 }}>Platform Modules</div>
            <h2 style={{ fontSize: '1.8rem', fontWeight: 700, color: '#f0f4f8', margin: 0 }}>
              Four tools, one investigation
            </h2>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: 20,
          }}>
            {MODULES.map(({ to, icon: Icon, name, tagline, description, status, color }) => (
              <Link
                key={to}
                to={to}
                style={{ textDecoration: 'none' }}
              >
                <div
                  className="glass glass-hover"
                  style={{
                    borderRadius: 10, padding: '28px 24px',
                    height: '100%', display: 'flex', flexDirection: 'column', gap: 14,
                    transition: 'all 0.2s',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{
                      width: 44, height: 44, borderRadius: 10,
                      background: `rgba(${color === '#22d3ee' ? '34,211,238' : color === '#a78bfa' ? '167,139,250' : color === '#67e8f9' ? '103,232,249' : '196,181,253'}, 0.1)`,
                      border: `1px solid ${color}22`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <Icon size={20} color={color} />
                    </div>
                    <span style={{
                      fontSize: '0.62rem', fontWeight: 600, letterSpacing: '0.08em',
                      padding: '3px 8px', borderRadius: 4,
                      background: status === 'available' ? 'rgba(34,211,238,0.1)' : 'rgba(251,191,36,0.1)',
                      color: status === 'available' ? '#22d3ee' : '#fbbf24',
                      border: `1px solid ${status === 'available' ? 'rgba(34,211,238,0.2)' : 'rgba(251,191,36,0.2)'}`,
                    }}>
                      {status === 'available' ? 'AVAILABLE' : 'IN PROGRESS'}
                    </span>
                  </div>

                  <div>
                    <div style={{ fontSize: '0.65rem', color: '#8899aa', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 4 }}>
                      {tagline}
                    </div>
                    <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#f0f4f8' }}>{name}</div>
                  </div>

                  <p style={{ fontSize: '0.82rem', color: '#8899aa', lineHeight: 1.6, margin: 0, flex: 1 }}>
                    {description}
                  </p>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: color, fontSize: '0.78rem', fontWeight: 500 }}>
                    Open <ArrowRight size={13} />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Scientific foundation */}
      <section style={{ padding: '80px 24px', background: 'rgba(6, 13, 24, 0.5)' }}>
        <div className="page-container" style={{ maxWidth: 800 }}>
          <div style={{ textAlign: 'center', marginBottom: 40 }}>
            <div className="section-label" style={{ justifyContent: 'center', display: 'flex', marginBottom: 8 }}>Scientific Foundation</div>
            <h2 style={{ fontSize: '1.8rem', fontWeight: 700, color: '#f0f4f8', margin: 0 }}>
              What we know so far
            </h2>
          </div>

          <div className="panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div className="panel-header" style={{ marginBottom: 0 }}>Confirmed Evidence</div>
              <div className="badge-demo">REAL PRODUCT</div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 20 }}>
              {[
                { label: 'Observation ID', value: '2025W17_4B_0001_1' },
                { label: 'Mission', value: 'SPHEREx DR1' },
                { label: 'Detector', value: 'D1' },
                { label: 'Observation Date', value: '24 April 2025' },
                { label: 'Cutout Size', value: '128 × 128 pixels' },
                { label: 'FITS Extensions', value: '6 inspected' },
              ].map(({ label, value }) => (
                <div key={label} style={{
                  background: 'rgba(34, 211, 238, 0.04)',
                  border: '1px solid rgba(34, 211, 238, 0.1)',
                  borderRadius: 6, padding: '12px 14px',
                }}>
                  <div style={{ fontSize: '0.65rem', color: '#8899aa', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 4 }}>{label}</div>
                  <div style={{ fontSize: '0.88rem', fontWeight: 600, color: '#22d3ee', fontFamily: 'var(--font-mono)' }}>{value}</div>
                </div>
              ))}
            </div>

            <div style={{ padding: '14px 16px', background: 'rgba(251, 191, 36, 0.05)', border: '1px solid rgba(251, 191, 36, 0.15)', borderRadius: 6 }}>
              <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#fbbf24', letterSpacing: '0.08em', marginBottom: 8 }}>⚠ KNOWN LIMITATIONS</div>
              <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 4 }}>
                {[
                  'Multi-epoch comparison has NOT yet been demonstrated.',
                  'A suitable second observation has NOT yet been established.',
                  'Relative WCS consistency is not proof of absolute astrometric accuracy.',
                  'Calibration applicability remains unresolved.',
                ].map((item, i) => (
                  <li key={i} style={{ fontSize: '0.78rem', color: '#8899aa', display: 'flex', gap: 8 }}>
                    <span style={{ color: '#fbbf24', flexShrink: 0 }}>·</span> {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer style={{
        padding: '32px 24px',
        borderTop: '1px solid rgba(34, 211, 238, 0.08)',
        textAlign: 'center',
      }}>
        <div className="page-container">
          <div style={{ fontSize: '0.75rem', color: '#4a6080', lineHeight: 1.8 }}>
            <div style={{ marginBottom: 4 }}>
              <span style={{ color: '#22d3ee', fontWeight: 600 }}>COSMIC PULSE</span>
              {' '}· NASA Space Apps Challenge 2026 · Challenge 12: Planet X and SPHEREx
            </div>
            <div>
              Built with SPHEREx DR1 Level-2 data · Scientific integrity preserved · No fabricated observations
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
