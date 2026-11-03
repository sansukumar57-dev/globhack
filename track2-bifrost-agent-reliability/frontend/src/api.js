const API_BASE = 'http://localhost:8002'

async function jfetch(path, opts = {}) {
  const res = await fetch(API_BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const data = await res.json()
      if (data.detail) detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch { /* non-json error */ }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  health: () => jfetch('/api/health'),
  scenarios: () => jfetch('/api/scenarios'),
  attacks: () => jfetch('/api/attacks'),
  policy: () => jfetch('/api/agent/policy'),
  putPolicy: (policy) => jfetch('/api/agent/policy', { method: 'PUT', body: JSON.stringify({ policy }) }),
  start: (body) => jfetch('/api/executions', { method: 'POST', body: JSON.stringify(body) }),
  execs: () => jfetch('/api/executions'),
  exec: (id) => jfetch(`/api/executions/${id}`),
  run: (id) => jfetch(`/api/runs/${id}`),
  debug: (id) => jfetch(`/api/executions/${id}/debug`, { method: 'POST' }),
}

export function fmtMs(ms) {
  if (ms == null) return '—'
  if (ms < 1000) return `${Math.round(ms)}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`
}

export function fmtCost(c) {
  if (c == null || c === 0) return '$0'
  if (c < 0.01) return `$${c.toFixed(5)}`
  return `$${c.toFixed(4)}`
}

export function fmtTime(ts) {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export const CATEGORY_COLOR = {
  sanity: 'ok',
  tooling: 'cyan',
  gateway: 'accent',
  integrity: 'purple',
  redteam: 'err',
}
