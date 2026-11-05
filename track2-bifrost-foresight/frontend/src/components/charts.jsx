import { useMemo } from 'react'

const W = 640
const H = 150
const PAD_Y = 18
const PAD_X = 4

export function AreaChart({ data }) {
  const { area, line, points } = useMemo(() => {
    if (!data || data.length === 0) return { area: '', line: '', points: [] }
    const max = Math.max(...data.map((d) => d.cost), 0.01)
    const innerW = W - PAD_X * 2
    const innerH = H - PAD_Y * 2
    const pts = data.map((d, i) => {
      const x = PAD_X + (i / (data.length - 1)) * innerW
      const y = PAD_Y + innerH - (d.cost / max) * innerH
      return [x, y]
    })
    const linePath = pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
    const areaPath = `${linePath} L${pts[pts.length - 1][0].toFixed(1)},${H - 2} L${pts[0][0].toFixed(1)},${H - 2} Z`
    return { area: areaPath, line: linePath, points: pts }
  }, [data])

  if (!data || data.length === 0) return <div className="empty">No usage in this window yet.</div>

  const max = Math.max(...data.map((d) => d.cost))
  return (
    <div style={{ width: '100%' }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Fleet spend, last 24 hours">
        <defs>
          <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#7c5cff" stopOpacity="0.42" />
            <stop offset="100%" stopColor="#f472b6" stopOpacity="0.02" />
          </linearGradient>
          <linearGradient id="lineStroke" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#7c5cff" />
            <stop offset="55%" stopColor="#a855f7" />
            <stop offset="100%" stopColor="#f472b6" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map((f) => (
          <line key={f} x1={PAD_X} x2={W - PAD_X} y1={PAD_Y + (H - PAD_Y * 2) * f} y2={PAD_Y + (H - PAD_Y * 2) * f}
                stroke="rgba(148,163,255,0.10)" strokeDasharray="3 5" />
        ))}
        <path d={area} fill="url(#areaFill)" />
        <path d={line} fill="none" stroke="url(#lineStroke)" strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round" />
        {points.length > 0 && (
          <circle cx={points[points.length - 1][0]} cy={points[points.length - 1][1]} r="3.4" fill="#f472b6" />
        )}
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--muted-2)', marginTop: 4 }} className="mono">
        <span>24h ago</span>
        <span>peak ${max.toFixed(2)}/h</span>
        <span>now</span>
      </div>
    </div>
  )
}

export function StatusChip({ status }) {
  const cls = { healthy: 'chip-healthy', watch: 'chip-watch', critical: 'chip-critical', exhausted: 'chip-exhausted' }[status] || 'chip-info'
  return <span className={`chip ${cls}`}>{status}</span>
}

export function BudgetBar({ pct }) {
  const p = Math.min(100, Math.max(0, pct * 100))
  const cls = p >= 90 ? 'critical' : p >= 70 ? 'hot' : ''
  return (
    <div className="bar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(p)} role="progressbar">
      <div className={`bar-fill ${cls}`} style={{ width: `${p}%` }} />
    </div>
  )
}
