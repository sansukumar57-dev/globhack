const BASE = ''

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'content-type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!res.ok) {
    let detail = `${res.status}`
    try {
      const body = await res.json()
      detail = body?.detail || body?.error?.message || detail
    } catch { /* non-JSON error body */ }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return res.json()
}

export const api = {
  overview: () => req('/api/overview'),
  keys: () => req('/api/keys'),
  key: (vk) => req(`/api/keys/${encodeURIComponent(vk)}`),
  updateKey: (vk, patch) => req(`/api/keys/${encodeURIComponent(vk)}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  armDowngrade: (vk, target, hours = 6) => req(`/api/keys/${encodeURIComponent(vk)}/downgrade`, { method: 'POST', body: JSON.stringify({ model: target, hours }) }),
  releaseDowngrade: (vk) => req(`/api/keys/${encodeURIComponent(vk)}/release`, { method: 'POST', body: '{}' }),
  anomalies: () => req('/api/anomalies'),
  alerts: (limit = 50) => req(`/api/alerts?limit=${limit}`),
  requests: (limit = 60) => req(`/api/requests?limit=${limit}`),
  simulator: (payload) => req('/api/simulator', { method: 'POST', body: JSON.stringify(payload) }),
  recommendations: () => req('/api/recommendations'),
  getSettings: () => req('/api/settings'),
  putSettings: (patch) => req('/api/settings', { method: 'PUT', body: JSON.stringify(patch) }),
  testWebhook: () => req('/api/settings/test-webhook', { method: 'POST', body: '{}' }),
  sink: () => req('/api/webhook-sink'),
  clearSink: () => req('/api/webhook-sink', { method: 'DELETE' }),
  seed: () => req('/api/seed', { method: 'POST', body: '{}' }),
  replayLive: (n = 8, vk = 'sk-bf-foresight-growth-0001', model = 'acme-llm/gpt-4o') =>
    req('/api/replay/live', { method: 'POST', body: JSON.stringify({ n, vk, model }) }),
}

// Shared formatting helpers
export const fmtUsd = (v, digits = 2) =>
  `$${Number(v || 0).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })}`

export const fmtTs = (ts) => {
  const d = new Date(ts * 1000)
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export const timeAgo = (ts) => {
  const diff = Date.now() / 1000 - ts
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export const fmtHoursLeft = (h) => {
  if (h == null) return '—'
  if (h >= 24 * 30) return '>30d'
  if (h >= 24) return `${Math.floor(h / 24)}d ${Math.round(h % 24)}h`
  return `${Math.round(h)}h`
}

// Tiny toast bus — pages can call toast('saved') without prop drilling.
const toastBus = new EventTarget()
export function toast(message) {
  toastBus.dispatchEvent(new CustomEvent('toast', { detail: message }))
}
export function onToast(handler) {
  const listener = (e) => handler(e.detail)
  toastBus.addEventListener('toast', listener)
  return () => toastBus.removeEventListener('toast', listener)
}
