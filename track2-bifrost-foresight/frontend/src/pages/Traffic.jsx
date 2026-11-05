import { useCallback, useEffect, useState } from 'react'
import { Radio, Zap, Loader2 } from 'lucide-react'
import { api, fmtUsd, timeAgo, toast } from '../api'

export default function Traffic({ refreshKey }) {
  const [requests, setRequests] = useState([])
  const [firing, setFiring] = useState(false)

  const load = useCallback(async () => {
    try {
      const res = await api.requests(60)
      setRequests(res.requests)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [load, refreshKey])

  const fire = async () => {
    setFiring(true)
    try {
      const res = await api.replayLive(8)
      const ok = res.results.filter((r) => r.status < 400).length
      toast(`Fired ${res.fired} live requests through Foresight → Bifrost — ${ok} accepted`)
      await load()
    } catch (e) {
      toast(`Replay failed: ${e.message}`)
    } finally {
      setFiring(false)
    }
  }

  return (
    <div className="panel panel-pad">
      <div className="panel-title">
        <span><Radio size={12} style={{ verticalAlign: -2, marginRight: 6 }} />Live metered traffic</span>
        <button className="btn btn-sm" onClick={fire} disabled={firing}>
          {firing ? <Loader2 size={13} className="spin" /> : <Zap size={13} />}
          {firing ? 'Firing…' : 'Fire 8 live requests'}
        </button>
      </div>
      <div style={{ fontSize: 11, color: 'var(--muted-2)', marginBottom: 10 }}>
        Real round trips: this button calls <span className="mono">127.0.0.1:8400/v1/chat/completions</span> → Bifrost OSS → the demo upstream.
        Every response is metered, priced and attributed to its virtual key.
      </div>
      <table className="table">
        <thead>
          <tr><th>Time</th><th>Key</th><th>Model</th><th>Tokens</th><th>Cost</th><th>Latency</th><th>Source</th></tr>
        </thead>
        <tbody>
          {requests.length === 0 && (
            <tr><td colSpan={7} className="empty">No metered requests yet — hit “Fire 8 live requests”.</td></tr>
          )}
          {requests.map((r) => (
            <tr key={r.id}>
              <td className="mono">{timeAgo(r.ts)}</td>
              <td><b>{r.key_name || r.vk?.slice(0, 12)}</b></td>
              <td className="mono">{String(r.model).split('/').pop()}</td>
              <td className="mono">{(r.prompt_tokens + r.completion_tokens).toLocaleString()}</td>
              <td className="mono">{fmtUsd(r.cost_usd, 4)}</td>
              <td className="mono">{r.latency_ms}ms</td>
              <td><span className="tag">{r.source}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
      <style>{'.spin { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }'}</style>
    </div>
  )
}
