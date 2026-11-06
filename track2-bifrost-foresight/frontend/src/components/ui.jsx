export function PageHeader({ eyebrow, title, lede, actions }) {
  return (
    <header className="page-head">
      <div>
        <div className="page-eyebrow">{eyebrow}</div>
        <h1 className="page-title">{title}</h1>
        {lede && <p className="page-lede">{lede}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  )
}

export function Loading({ label = 'Reading the ledger…' }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="loading-dot" />
      {label}
    </div>
  )
}

export function EmptyState({ title, detail, action }) {
  return (
    <div className="empty">
      <div className="empty-title">{title}</div>
      {detail && <p className="empty-detail">{detail}</p>}
      {action}
    </div>
  )
}

export function monogram(name = '') {
  return name.trim().charAt(0).toUpperCase() || '·'
}

export function toneFor(status) {
  if (status === 'critical' || status === 'exhausted') return 'critical'
  if (status === 'watch') return 'watch'
  return ''
}
