import { NavLink, useLocation } from 'react-router-dom'
import { useState } from 'react'
import { Telescope, Clock, FlaskConical, Archive, Info, Menu, X, Zap } from 'lucide-react'

const NAV_ITEMS = [
  { to: '/explorer',    label: 'Explorer',       icon: Telescope,    title: 'Cosmic Explorer' },
  { to: '/time-machine', label: 'Time Machine',  icon: Clock,        title: 'Cosmic Time Machine' },
  { to: '/lab',         label: 'Discovery Lab',  icon: FlaskConical, title: 'Discovery Lab' },
  { to: '/capsules',    label: 'Capsules',        icon: Archive,      title: 'Evidence Capsules' },
  { to: '/about',       label: 'About',           icon: Info,         title: 'About' },
]

export default function Nav() {
  const [open, setOpen] = useState(false)
  const location = useLocation()

  return (
    <header
      style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 50,
        background: 'rgba(2, 4, 8, 0.85)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid rgba(34, 211, 238, 0.1)',
      }}
    >
      <div className="page-container" style={{ display: 'flex', alignItems: 'center', height: 56, gap: 32 }}>
        {/* Logo */}
        <NavLink to="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none', flexShrink: 0 }}>
          <div style={{
            width: 28, height: 28, borderRadius: '50%',
            background: 'radial-gradient(circle at 35% 35%, #22d3ee, #8b5cf6)',
            boxShadow: '0 0 12px rgba(34, 211, 238, 0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Zap size={14} color="#020408" strokeWidth={2.5} />
          </div>
          <span style={{ fontWeight: 700, fontSize: '0.95rem', letterSpacing: '0.06em', color: '#f0f4f8' }}>
            COSMIC<span style={{ color: '#22d3ee' }}> PULSE</span>
          </span>
        </NavLink>

        {/* Desktop nav */}
        <nav style={{ display: 'flex', gap: 2, flex: 1 }} className="hidden-mobile">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => {
            const active = location.pathname.startsWith(to)
            return (
              <NavLink
                key={to}
                to={to}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '6px 12px', borderRadius: 5,
                  fontSize: '0.8rem', fontWeight: active ? 600 : 400,
                  color: active ? '#22d3ee' : '#8899aa',
                  background: active ? 'rgba(34, 211, 238, 0.08)' : 'transparent',
                  border: active ? '1px solid rgba(34, 211, 238, 0.15)' : '1px solid transparent',
                  textDecoration: 'none',
                  transition: 'all 0.15s',
                }}
              >
                <Icon size={13} />
                {label}
              </NavLink>
            )
          })}
        </nav>

        {/* Status indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 'auto', flexShrink: 0 }}>
          <div className="badge-demo" style={{ fontSize: '0.6rem' }}>DEMO MODE</div>
        </div>

        {/* Mobile menu button */}
        <button
          onClick={() => setOpen(o => !o)}
          style={{ background: 'none', border: 'none', color: '#8899aa', cursor: 'pointer', padding: 4 }}
          className="show-mobile"
          aria-label="Toggle menu"
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div style={{
          background: 'rgba(2, 4, 8, 0.97)',
          borderTop: '1px solid rgba(34, 211, 238, 0.1)',
          padding: '12px 24px 16px',
        }}>
          {NAV_ITEMS.map(({ to, label, icon: Icon, title }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setOpen(false)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 0',
                borderBottom: '1px solid rgba(34, 211, 238, 0.06)',
                color: location.pathname.startsWith(to) ? '#22d3ee' : '#8899aa',
                textDecoration: 'none', fontSize: '0.875rem',
              }}
            >
              <Icon size={15} />
              <div>
                <div style={{ fontWeight: 500 }}>{label}</div>
                <div style={{ fontSize: '0.7rem', color: '#4a6080' }}>{title}</div>
              </div>
            </NavLink>
          ))}
        </div>
      )}

      <style>{`
        @media (min-width: 768px) { .hidden-mobile { display: flex !important; } .show-mobile { display: none !important; } }
        @media (max-width: 767px) { .hidden-mobile { display: none !important; } .show-mobile { display: flex !important; } }
      `}</style>
    </header>
  )
}
