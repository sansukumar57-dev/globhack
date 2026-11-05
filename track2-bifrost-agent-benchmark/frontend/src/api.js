const BASE = import.meta.env.VITE_API_BASE || '/api'

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const text = await response.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { detail: text }
  }
  if (!response.ok) {
    const message = data?.detail || `Request failed (${response.status})`
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message))
  }
  return data
}

export const api = {
  health: () => request('/health'),
  stats: () => request('/stats'),
  suite: () => request('/suite'),
  adapters: () => request('/adapters'),
  agents: () => request('/agents'),
  agent: (id) => request(`/agents/${encodeURIComponent(id)}`),
  addAgent: (payload) => request('/agents', { method: 'POST', body: JSON.stringify(payload) }),
  leaderboard: () => request('/leaderboard'),
  failures: () => request('/failures'),
  runs: () => request('/runs'),
  run: (id) => request(`/runs/${encodeURIComponent(id)}`),
  startRun: (payload) => request('/runs', { method: 'POST', body: JSON.stringify(payload) }),
}
