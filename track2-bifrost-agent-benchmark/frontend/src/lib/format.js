export function fmtScore(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return Number(value).toFixed(digits)
}

export function fmtPct(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return `${Number(value).toFixed(digits)}%`
}

export function fmtMs(value) {
  if (value === null || value === undefined) return '—'
  const ms = Number(value)
  if (ms < 1000) return `${Math.round(ms)}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const minutes = Math.floor(ms / 60000)
  const seconds = Math.round((ms % 60000) / 1000)
  return `${minutes}m ${seconds}s`
}

export function fmtCost(value) {
  if (value === null || value === undefined) return '—'
  const n = Number(value)
  if (n < 0.01) return `$${n.toFixed(4)}`
  return `$${n.toFixed(3)}`
}

export function fmtNumber(value) {
  if (value === null || value === undefined) return '—'
  return Number(value).toLocaleString('en-US')
}

export function fmtDate(iso, options = {}) {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    ...options,
  }).format(date)
}

export function timeAgo(iso) {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  const diff = Date.now() - date.getTime()
  const minutes = Math.round(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 7) return `${days}d ago`
  return fmtDate(iso, { year: 'numeric' })
}

export function deltaLabel(value) {
  if (value === null || value === undefined) return null
  const n = Number(value)
  if (n === 0) return { text: '0.0', direction: 'flat' }
  return { text: `${n > 0 ? '+' : ''}${n.toFixed(1)}`, direction: n > 0 ? 'up' : 'down' }
}

export function statusLabel(status) {
  const labels = {
    passed: 'Passed',
    partial: 'Partial',
    failed: 'Failed',
    error: 'Adapter error',
    complete: 'Complete',
    running: 'Running',
    queued: 'Queued',
    failed_run: 'Failed',
  }
  return labels[status] || status
}

export function downloadJson(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export function scoreTone(score) {
  if (score === null || score === undefined) return 'neutral'
  if (score >= 90) return 'good'
  if (score >= 75) return 'ok'
  return 'bad'
}
