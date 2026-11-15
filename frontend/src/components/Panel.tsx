import type { ReactNode } from 'react'

interface Props {
  children: ReactNode
  title?: string
  badge?: string
  action?: ReactNode
  style?: React.CSSProperties
}

export default function Panel({ children, title, badge, action, style }: Props) {
  return (
    <div className="panel" style={style}>
      {(title || action) && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          {title && (
            <div className="panel-header" style={{ marginBottom: 0 }}>
              {title}
              {badge && <span className={`badge-${badge}`} style={{ marginLeft: 6 }}>{badge.toUpperCase()}</span>}
            </div>
          )}
          {action}
        </div>
      )}
      {children}
    </div>
  )
}
