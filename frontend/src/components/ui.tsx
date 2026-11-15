interface MetaRowProps {
  label: string
  value: string | number | null | undefined
  mono?: boolean
  highlight?: boolean
}

export function MetaRow({ label, value, mono, highlight }: MetaRowProps) {
  return (
    <div className="meta-row">
      <span className="meta-label">{label}</span>
      <span
        className={mono ? 'meta-value' : undefined}
        style={{
          fontSize: '0.8rem',
          color: highlight ? '#22d3ee' : value == null ? '#4a6080' : '#f0f4f8',
          fontFamily: mono ? 'var(--font-mono)' : undefined,
        }}
      >
        {value ?? '—'}
      </span>
    </div>
  )
}

interface BadgeProps {
  variant: 'demo' | 'live' | 'pending' | 'confirmed' | 'rejected' | 'unresolved'
  label?: string
}

export function Badge({ variant, label }: BadgeProps) {
  const labels: Record<string, string> = {
    demo: 'DEMO', live: 'LIVE', pending: 'PENDING',
    confirmed: 'CONFIRMED', rejected: 'REJECTED', unresolved: 'UNRESOLVED',
  }
  return <span className={`badge-${variant}`}>{label ?? labels[variant]}</span>
}

export function Divider() {
  return <div className="divider" style={{ margin: '16px 0' }} />
}

interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description: string
  action?: React.ReactNode
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '48px 24px', textAlign: 'center', gap: 12,
    }}>
      {icon && (
        <div style={{ color: 'rgba(34, 211, 238, 0.3)', marginBottom: 8 }}>{icon}</div>
      )}
      <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f0f4f8' }}>{title}</div>
      <div style={{ fontSize: '0.8rem', color: '#8899aa', maxWidth: 360, lineHeight: 1.6 }}>{description}</div>
      {action && <div style={{ marginTop: 8 }}>{action}</div>}
    </div>
  )
}

interface LoadingProps { label?: string }

export function Loading({ label = 'Loading…' }: LoadingProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '24px', color: '#8899aa', fontSize: '0.85rem' }}>
      <div style={{
        width: 16, height: 16, border: '2px solid rgba(34, 211, 238, 0.2)',
        borderTopColor: '#22d3ee', borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
      }} />
      {label}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

interface ErrorMsgProps { message: string }

export function ErrorMsg({ message }: ErrorMsgProps) {
  return (
    <div style={{
      padding: '12px 16px', borderRadius: 6,
      background: 'rgba(239, 68, 68, 0.08)',
      border: '1px solid rgba(239, 68, 68, 0.2)',
      color: '#f87171', fontSize: '0.82rem',
    }}>
      {message}
    </div>
  )
}

interface SectionLabelProps { children: React.ReactNode }

export function SectionLabel({ children }: SectionLabelProps) {
  return <div className="section-label">{children}</div>
}

interface LimitationListProps { items: string[] }

export function LimitationList({ items }: LimitationListProps) {
  return (
    <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
      {items.map((item, i) => (
        <li key={i} style={{ display: 'flex', gap: 8, fontSize: '0.8rem', color: '#8899aa', lineHeight: 1.5 }}>
          <span style={{ color: '#fbbf24', flexShrink: 0, marginTop: 2 }}>⚠</span>
          {item}
        </li>
      ))}
    </ul>
  )
}
