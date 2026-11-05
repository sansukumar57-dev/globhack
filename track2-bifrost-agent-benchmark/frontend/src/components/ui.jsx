import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Check,
  Minus,
  X,
} from 'lucide-react'
import { deltaLabel, fmtScore, statusLabel } from '../lib/format.js'

export function Logo({ compact = false }) {
  return (
    <div className={`logo${compact ? ' logo-compact' : ''}`}>
      <span className="logo-mark" aria-hidden="true">
        <span className="logo-bar logo-bar-1" />
        <span className="logo-bar logo-bar-2" />
        <span className="logo-bar logo-bar-3" />
      </span>
      {!compact && (
        <span className="logo-type">
          <span className="logo-word">Criterion</span>
          <span className="logo-sub">Agent benchmarks</span>
        </span>
      )}
    </div>
  )
}

export function AgentMark({ agent, size = 'md' }) {
  if (!agent) return null
  const color = agent.color || '#5A6472'
  const initials = agent.initials || agent.name?.slice(0, 2)?.toUpperCase() || 'AG'
  return (
    <span
      className={`agent-mark agent-mark-${size}`}
      style={{ '--agent-color': color, '--agent-tint': `${color}16` }}
      aria-hidden="true"
    >
      {initials}
    </span>
  )
}

export function StatusPill({ status, label, tone, dot = true }) {
  const resolvedTone = tone || (
    status === 'passed' || status === 'complete' ? 'good'
      : status === 'partial' || status === 'running' ? 'warn'
        : status === 'failed' || status === 'error' ? 'bad'
          : 'neutral'
  )
  return (
    <span className={`status-pill status-${resolvedTone}`}>
      {dot && <span className="status-dot" />}
      {label || statusLabel(status)}
    </span>
  )
}

export function Delta({ value, compact = false }) {
  const delta = deltaLabel(value)
  if (!delta) return <span className="delta delta-flat">new</span>
  if (delta.direction === 'flat') {
    return <span className="delta delta-flat"><Minus size={11} />{delta.text}</span>
  }
  const Icon = delta.direction === 'up' ? ArrowUpRight : ArrowDownRight
  return (
    <span className={`delta delta-${delta.direction}${compact ? ' delta-compact' : ''}`}>
      <Icon size={12} />
      {delta.text}
    </span>
  )
}

export function Sparkline({ points = [], color = '#1B1916', width = 92, height = 26 }) {
  const values = points.map((point) => (typeof point === 'number' ? point : point.score)).filter((v) => Number.isFinite(v))
  if (values.length === 0) return <span className="spark-empty">—</span>
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const pad = 3
  const step = values.length > 1 ? (width - pad * 2) / (values.length - 1) : 0
  const coords = values.map((value, index) => {
    const x = pad + index * step
    const y = height - pad - ((value - min) / range) * (height - pad * 2)
    return [x, y]
  })
  const path = coords.map(([x, y], index) => `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const last = coords[coords.length - 1]
  return (
    <svg className="sparkline" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Score history">
      <path d={path} fill="none" stroke={color} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r="2.5" fill={color} />
    </svg>
  )
}

export function ScoreRing({ value, size = 112, label = 'score', color = '#D9482B', suffix = '' }) {
  const safe = Math.max(0, Math.min(100, Number(value) || 0))
  const stroke = 8
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (safe / 100) * circumference
  return (
    <div className="score-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${label}: ${fmtScore(safe)}`}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--line)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          className="score-ring-progress"
        />
      </svg>
      <span className="score-ring-copy">
        <span className="score-ring-value">{fmtScore(safe)}<small>{suffix}</small></span>
        <span className="score-ring-label">{label}</span>
      </span>
    </div>
  )
}

export function ProgressBar({ value = 0, tone = 'accent', height = 6, label }) {
  const safe = Math.max(0, Math.min(100, Number(value) || 0))
  return (
    <div className="progress-wrap" aria-label={label || `${Math.round(safe)}%`}>
      <div className="progress-track" style={{ height }}>
        <div className={`progress-fill progress-${tone}`} style={{ transform: `scaleX(${safe / 100})` }} />
      </div>
    </div>
  )
}

export function CheckMark({ passed, size = 14 }) {
  return passed
    ? <span className="check-mark check-good"><Check size={size} strokeWidth={2.4} /></span>
    : <span className="check-mark check-bad"><X size={size} strokeWidth={2.4} /></span>
}

export function EmptyState({ icon: Icon = AlertTriangle, title, body, action }) {
  return (
    <div className="empty-state">
      <span className="empty-icon"><Icon size={20} /></span>
      <h3>{title}</h3>
      <p>{body}</p>
      {action}
    </div>
  )
}

export function Skeleton({ className = '', height, width }) {
  return <span className={`skeleton ${className}`} style={{ height, width }} aria-hidden="true" />
}

export function Eyebrow({ children, tone = 'default' }) {
  return <p className={`eyebrow eyebrow-${tone}`}><span className="eyebrow-mark" />{children}</p>
}

export function SectionHeading({ title, meta, action }) {
  return (
    <div className="section-heading">
      <div>
        <h2>{title}</h2>
        {meta && <p>{meta}</p>}
      </div>
      {action}
    </div>
  )
}
