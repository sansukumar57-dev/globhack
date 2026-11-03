import { useEffect, useState } from 'react'
import { api, fmtMs, fmtTime } from '../api.js'
import { OutcomeBadge, Stat, Empty, Loading, JudgeScores, ChecksList } from '../ui.jsx'

export default function RedTeam({ execs, launch, openExec }) {
  const [attacks, setAttacks] = useState(null)
  const [policyName, setPolicyName] = useState('hardened')
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.attacks().then(d => setAttacks(d)).catch(e => setErr(String(e.message || e)))
  }, [])

  const go = async () => {
    setErr(null); setBusy(true)
    try { await launch({ suite: 'redteam', policy: { name: policyName } }) }
    catch (e) { setErr(String(e.message || e)) }
    finally { setBusy(false) }
  }

  const done = execs.filter(e => e.status === 'done')
  const latest = done[0]
  const safety = latest?.summary?.safety_score
  const outcomes = {}
  for (const e of done) for (const r of (e.results || [])) outcomes[r.redteam_outcome] = (outcomes[r.redteam_outcome] || 0) + 1

  return (
    <div>
      <div className="grid2" style={{ gridTemplateColumns: '1fr 360px', marginBottom: 18 }}>
        <div className="card pad">
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 3 }}>Red-team gauntlet</div>
          <div className="small muted">
            Authority spoofing, prompt exfiltration, social engineering, jailbreaks, indirect injection
            via tool output, encoded payloads, instruction laundering, data harvesting. Each attack
            ends in <b>blocked</b> / <b>partial</b> / <b>complied</b>.
          </div>
        </div>
        <div className="card pad">
          <div className="small faint" style={{ marginBottom: 8 }}>POLICY UNDER TEST</div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            {['hardened', 'baseline'].map(p => (
              <button key={p} className={`btn ghost${policyName === p ? ' active' : ''}`} onClick={() => setPolicyName(p)}>{p}</button>
            ))}
            <div style={{ flex: 1 }} />
            <button className="btn primary" disabled={busy} onClick={go}>
              {busy ? <span className="spinner" /> : '⚔'} {busy ? 'running…' : 'Launch gauntlet'}
            </button>
          </div>
          <div className="small faint">8 attacks · each run is scored by deterministic checks (no LLM judge)</div>
        </div>
      </div>

      {err && <div className="banner">⚠ {err}</div>}

      {latest && (
        <div className="stat-row" style={{ marginBottom: 18 }}>
          <Stat k="Safety score" v={`${safety ?? 0}%`} d={`latest gauntlet (${latest.exec_id})`} cls={safety >= 80 ? 'ok' : 'err'} />
          <Stat k="Blocked" v={outcomes.blocked ?? 0} d="attacks failed" cls={outcomes.blocked ? 'ok' : ''} />
          <Stat k="Partial" v={outcomes.partial ?? 0} d="half-resisted" cls={outcomes.partial ? 'accent' : ''} />
          <Stat k="Complied" v={outcomes.complied ?? 0} d="attacks succeeded" cls={outcomes.complied ? 'err' : ''} />
        </div>
      )}

      {execs.length > 0 && (
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="card-head"><h3>Gauntlet history</h3></div>
          <table className="data">
            <thead><tr><th>exec</th><th>policy</th><th>safety</th><th>progress</th><th>started</th><th>status</th><th></th></tr></thead>
            <tbody>
              {execs.map(e => (
                <tr key={e.exec_id} className="rowlink" onClick={() => openExec(e.exec_id)}>
                  <td className="mono small">{e.exec_id}</td>
                  <td><span className={`badge ${e.policy_name?.includes('hard') ? 'ok' : 'err'}`}>{e.policy_name}</span></td>
                  <td className="mono">{e.summary ? `${e.summary.safety_score ?? 0}%` : '—'}</td>
                  <td className="mono small">{e.progress?.done}/{e.progress?.total}</td>
                  <td className="mono small faint">{fmtTime(e.started_at)}</td>
                  <td>
                    {e.status === 'done' ? <span className="badge ok">done</span>
                      : e.status === 'error' ? <span className="badge err">error</span>
                      : <span className="badge warn"><span className="pulse-dot" /> running</span>}
                  </td>
                  <td className="faint small">inspect runs →</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="sect-label">Attack catalog</div>
      {!attacks && !err && <Loading label="loading attacks…" />}
      {attacks && (
        <div className="card">
          <table className="data">
            <thead>
              <tr><th>id</th><th>attack</th><th>technique</th><th>vector</th><th>goal</th></tr>
            </thead>
            <tbody>
              {attacks.attacks.map(a => (
                <tr key={a.id}>
                  <td className="mono small">{a.id}</td>
                  <td style={{ fontWeight: 500 }}>{a.name}</td>
                  <td><span className="badge err">{a.technique}</span></td>
                  <td className="small muted">{a.vector}</td>
                  <td className="small muted" style={{ maxWidth: 380, whiteSpace: 'normal' }}>{a.goal}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
