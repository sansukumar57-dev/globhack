import { useCallback, useEffect, useState } from 'react'
import { Loader2, Zap } from 'lucide-react'
import { api, fmtTs, fmtUsd, timeAgo, toast } from '../api'
import { EmptyState, PageHeader, monogram } from '../components/ui'

export default function Traffic({ refreshKey }) {
  const [requests, setRequests] = useState([])
  const [loaded, setLoaded] = useState(false)
  const [firing, setFiring] = useState(false)

  const load = useCallback(async () => {
    try {
      const res = await api.requests(60)
      setRequests(res.requests)
    } catch {
      /* the top bar surfaces connectivity */
    } finally {
      setLoaded(true)
    }
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

  const header = (
    <PageHeader
      eyebrow="Telemetry · 05"
      title={<>The wire,{' '}<em>live</em>.</>}
      lede="Real round trips through Foresight → Bifrost → the demo upstream. Every response is metered, priced, and attributed to its virtual key."
      actions={(
        <button className="btn" onClick={fire} disabled={firing}>
          {firing ? <Loader2 className="spin" size={13} aria-hidden="true" /> : <Zap size={13} aria-hidden="true" />}
          {firing ? 'Firing…' : 'Fire 8 live requests'}
        </button>
      )}
    />
  )

  return (
    <div className="page">
      {header}

      <section className="sheet">
        <div className="traffic-bar">
          <span className="traffic-live"><span className="dot" /> live</span>
          <span>{requests.length} most recent</span>
          <span className="spacer" />
          <span>auto-refresh · 5s</span>
          <span className="traffic-endpoint">127.0.0.1:8400/v1/chat/completions</span>
        </div>

        {!loaded ? (
          <div className="empty">Reading the wire…</div>
        ) : requests.length === 0 ? (
          <EmptyState
            title="No requests yet."
            detail="Fire eight live requests and watch the chain meter, price, and attribute every token."
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Time</th>
                  <th scope="col">Key</th>
                  <th scope="col">Model</th>
                  <th scope="col" className="r">Tokens</th>
                  <th scope="col" className="r">Cost</th>
                  <th scope="col" className="r">Latency</th>
                  <th scope="col">Source</th>
                </tr>
              </thead>
              <tbody>
                {requests.map((r) => {
                  const tokens = (r.prompt_tokens || 0) + (r.completion_tokens || 0)
                  const live = r.source === 'live'
                  return (
                    <tr key={r.id}>
                      <td>
                        <div className="strong">{timeAgo(r.ts)}</div>
                        <span className="sub">{fmtTs(r.ts)}</span>
                      </td>
                      <td>
                        <div className="key-id">
                          <span className="key-mark">{monogram(r.key_name || r.vk || '')}</span>
                          <div className="key-name">{r.key_name || r.vk?.slice(0, 12)}</div>
                        </div>
                      </td>
                      <td className="mono">{String(r.model).split('/').pop()}</td>
                      <td className="r num">{tokens.toLocaleString()}</td>
                      <td className="r num">{fmtUsd(r.cost_usd, 4)}</td>
                      <td className="r num">{r.latency_ms}ms</td>
                      <td><span className={`tag ${live ? 'tag-green' : ''}`}>{r.source}</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
