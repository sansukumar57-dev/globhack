import { useEffect, useState } from 'react'
import { api, fmtTime } from '../api.js'
import { Empty, Loading } from '../ui.jsx'

const CONF_COLOR = { high: 'err', medium: 'warn', low: 'muted' }

export default function DebuggerView({ execs }) {
  const [done, setDone] = useState([])
  const [selId, setSelId] = useState(null)
  const [structs, setStructs] = useState({})   // execId -> analysis
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const [appliedId, setAppliedId] = useState(null)

  useEffect(() => {
    const ds = execs
      .filter(e => e.status === 'done' && e.suite !== 'redteam')
      .sort((a, b) => {
        const pa = a.summary?.pass_rate ?? 100
        const pb = b.summary?.pass_rate ?? 100
        if (pa !== pb) return pa - pb          // most broken suite first
        return b.started_at - a.started_at
      })
    setDone(ds)
    if (!selId && ds.length) setSelId(ds[0].exec_id)
  }, [execs, selId])

  const analyze = async (execId) => {
    setErr(null); setBusy(true)
    try {
      const a = await api.debug(execId)
      setStructs(s => ({ ...s, [execId]: a }))
    } catch (e) {
      setErr(String(e.message || e))
    } finally {
      setBusy(false)
    }
  }

  const apply = async (execId, policy) => {
    setErr(null)
    try {
      await api.putPolicy(policy)
      setAppliedId(execId)
    } catch (e) {
      setErr(String(e.message || e))
    }
  }

  if (!done.length) return <Empty>No finished executions to debug yet — run a suite in the Stress Lab first.</Empty>

  const sel = done.find(e => e.exec_id === selId)
  const analysis = sel ? structs[sel.exec_id] : null

  return (
    <div>
      <div className="card" style={{ marginBottom: 18 }}>
        <div className="card-head"><h3>Pick a broken suite</h3><span className="sub">the debugger clusters failing runs into signatures</span></div>
        <table className="data">
          <thead><tr><th></th><th>exec</th><th>suite</th><th>policy</th><th>pass rate</th><th>reliability</th><th>started</th></tr></thead>
          <tbody>
            {done.map(e => (
              <tr key={e.exec_id} className="rowlink" onClick={() => setSelId(e.exec_id)}
                  style={e.exec_id === selId ? { background: 'var(--card-2)' } : undefined}>
                <td><input type="radio" checked={e.exec_id === selId} readOnly /></td>
                <td className="mono small">{e.exec_id}</td>
                <td>{e.suite}</td>
                <td><span className={`badge ${e.policy_name?.includes('hard') ? 'ok' : 'err'}`}>{e.policy_name}</span></td>
                <td className="mono small">{e.summary?.pass_rate ?? 0}%</td>
                <td className="mono small">{e.summary?.reliability ?? 0}</td>
                <td className="mono small faint">{fmtTime(e.started_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="card-body" style={{ borderTop: '1px solid var(--line)' }}>
          <button className="btn primary" disabled={busy || !sel} onClick={() => analyze(sel.exec_id)}>
            {busy ? <span className="spinner" /> : '⚗'} Debug {sel?.exec_id}
          </button>
          {sel && !analysis && !busy && (
            <span className="small faint" style={{ marginLeft: 10 }}>
              {sel.summary?.pass_rate === 100
                ? 'this suite fully passed — analyzing will confirm no hardening is required'
                : 'clusters failures → recommends policy patches → proposes a hardened policy'}
            </span>
          )}
        </div>
      </div>

      {err && <div className="banner">⚠ {err}</div>}

      {sel && !analysis && !busy && (
        <Empty>Hit “Debug {sel.exec_id}” to cluster this suite's failure signatures.</Empty>
      )}
      {busy && <Loading label="clustering failure signatures…" />}

      {analysis && (
        <div>
          <div className="banner ok" style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <span style={{ fontSize: 15 }}>⚗</span><span>{analysis.one_liner}</span>
          </div>

          {analysis.signatures?.length > 0 && (
            <>
              <div className="sect-label">Failure signatures</div>
              <div className="card">
                <table className="data">
                  <thead><tr><th>signature</th><th>count</th><th>scenarios</th><th>evidence</th></tr></thead>
                  <tbody>
                    {analysis.signatures.map(s => (
                      <tr key={s.type}>
                        <td><span className="badge err">{s.type}</span></td>
                        <td className="mono">{s.count}</td>
                        <td className="mono small">{s.scenario_ids.join(', ')}</td>
                        <td className="small muted" style={{ maxWidth: 320, whiteSpace: 'normal' }}>{s.details?.join(' · ')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {analysis.recommendations?.length > 0 && (
            <>
              <div className="sect-label">Recommended fixes</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {analysis.recommendations.map(rec => (
                  <div className="card pad" key={rec.id}>
                    <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                      <span className={`badge ${CONF_COLOR[rec.confidence] || 'muted'}`}>{rec.confidence}</span>
                      <span style={{ fontWeight: 700, fontSize: 13 }}>{rec.title}</span>
                      <span className="badge muted mono">{rec.count} run{rec.count === 1 ? '' : 's'}</span>
                      {Object.keys(rec.policy_patch || {}).length > 0 && (
                        <span className="mono small accent" style={{ marginLeft: 'auto', color: 'var(--accent)' }}>
                          patch: {Object.entries(rec.policy_patch).map(([k, v]) => `${k}=${v}`).join(' · ')}
                        </span>
                      )}
                    </div>
                    <div className="small muted" style={{ marginTop: 6 }}>{rec.detail}</div>
                    {rec.details?.length > 0 && (
                      <div className="small faint mono" style={{ marginTop: 4 }}>{rec.details[0]}</div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}

          <div className="sect-label">Auto-patched policy</div>
          <div className="grid2" style={{ gridTemplateColumns: '1fr 1fr' }}>
            <div className="card">
              <div className="card-head"><h3>Current · {sel.policy_name}</h3></div>
              <table className="data diff-table">
                <tbody>
                  {Object.entries(sel.policy || {}).map(([k, v]) => (
                    <tr key={k}><td className="faint">{k}</td><td className="mono">{String(v)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="card">
              <div className="card-head"><h3 style={{ color: 'var(--ok)' }}>Proposed · {analysis.proposed_policy?.name}</h3></div>
              <table className="data diff-table">
                <tbody>
                  {Object.entries(analysis.proposed_policy || {}).map(([k, v]) => {
                    const d = analysis.policy_delta?.[k]
                    return (
                      <tr key={k}>
                        <td className="faint">{k}</td>
                        <td className="mono">
                          {d ? <><span className="diff-old">{String(d.old)}</span> → <span className="diff-new">{String(d.new)}</span></> : String(v)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div style={{ marginTop: 14, display: 'flex', gap: 10, alignItems: 'center' }}>
            <button className="btn primary" onClick={() => apply(sel.exec_id, analysis.proposed_policy)}>
              ✓ Apply to working policy
            </button>
            {appliedId === sel?.exec_id
              ? <span className="small" style={{ color: 'var(--ok)' }}>applied — rerun the same suite with the working policy to A/B the delta</span>
              : <span className="small faint">writes to PUT /api/agent/policy (the suite launch uses the working policy when no override is set)</span>}
          </div>
        </div>
      )}
    </div>
  )
}
