import { useEffect, useState } from 'react'
import { api, fmtMs, fmtCost, fmtTime, CATEGORY_COLOR } from '../api.js'
import { Stat, Empty, PassBadge, RelNum, Loading } from '../ui.jsx'

const NICE_SUITE = {
  quick: 'Quick gauntlet', full: 'Full suite', tooling: 'Tooling stress',
  gateway: 'Gateway stress', redteam: 'Red-team gauntlet', custom: 'Custom selection',
}

export default function Overview({ health, execs, launch, openExec, setRoute }) {
  const [scenarios, setScenarios] = useState(null)
  const [attacks, setAttacks] = useState(null)
  const [busy, setBusy] = useState(null)

  useEffect(() => {
    api.scenarios().then(d => setScenarios(d)).catch(() => {})
    api.attacks().then(d => setAttacks(d)).catch(() => {})
  }, [])

  const done = execs.filter(e => e.status === 'done')
  const stressExecs = done.filter(e => e.suite !== 'redteam')
  const rtExecs = done.filter(e => e.suite === 'redteam')
  const avg = (arr, sel) => (arr.length ? Math.round(arr.reduce((s, e) => s + sel(e), 0) / arr.length) : null)
  const avgRel = avg(stressExecs, e => e.summary?.reliability ?? 0)
  const avgPass = avg(stressExecs, e => e.summary?.pass_rate ?? 0)
  const avgSafety = avg(rtExecs, e => e.summary?.safety_score ?? 0)
  const runsBurned = done.reduce((s, e) => s + (e.summary?.runs || 0), 0)
  const cost = done.reduce((s, e) => s + (e.summary?.est_cost || 0), 0)

  const runQuick = async (policyName) => {
    setBusy(policyName)
    try {
      await launch({ suite: 'quick', policy: { name: policyName } })
    } catch { /* banner shown in App */ } finally {
      setBusy(null)
    }
  }

  return (
    <div>
      <div className="hero">
        <h1>Stress, benchmark &amp; debug AI agents <span className="accent">before production does.</span></h1>
        <p className="lead">
          Faultline injects real-world failures — rate limits, tool crashes, malformed data, stale
          records, prompt injection — into a live billing-support agent, scores every run with
          deterministic checks + an LLM judge, then clusters the failures and proposes a hardened
          policy patch you can apply and A/B in one click.
        </p>
        <div className="ps-chip">
          <span className="badge accent">Track 2 · Bifrost / Maxim AI (Title Partner)</span>
          <span className="badge cyan">LLM Observability</span>
          <span className="badge cyan">Agent Evaluation</span>
          <span className="badge cyan">Red-Teaming</span>
          {health && <span className="badge muted mono">provider · {health.provider} — {health.model}</span>}
        </div>
      </div>

      <div className="stat-row" style={{ marginBottom: 22 }}>
        <Stat k="Avg reliability" v={avgRel ?? '—'} d={`${stressExecs.length} suites benchmarked`} cls={avgRel >= 80 ? 'ok' : avgRel ? 'accent' : ''} />
        <Stat k="Avg pass rate" v={avgPass != null ? `${avgPass}%` : '—'} d="deterministic checks" />
        <Stat k="Safety score" v={avgSafety != null ? `${avgSafety}%` : '—'} d={`${rtExecs.length} red-team gauntlets`} cls={avgSafety && avgSafety >= 80 ? 'ok' : avgSafety != null ? 'err' : ''} />
        <Stat k="Agent runs" v={runsBurned} d={`~${fmtCost(cost)} est. spend`} />
      </div>

      <div className="sect-label">The reliability loop</div>
      <div className="pipes" style={{ marginBottom: 24 }}>
        {[
          ['1', 'Chaos', 'inject faults in a simulated domain'],
          ['2', 'Run', 'agent executes with its policy'],
          ['3', 'Score', 'checks 45% + LLM judge 55%'],
          ['4', 'Debug', 'cluster failure signatures'],
          ['5', 'Patch', 'auto-hardened policy → A/B'],
        ].map(([n, t, s], i) => (
          <span key={n} style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {i > 0 && <span className="pipe-arrow">→</span>}
            <div className="pipe"><span className="n">{n}</span><div><div className="t">{t}</div><div className="s">{s}</div></div></div>
          </span>
        ))}
      </div>

      <div className="sect-label">Run the gauntlet</div>
      <div className="grid2" style={{ marginBottom: 24 }}>
        <div className="card pad">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 14 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 3 }}>Quick gauntlet · baseline</div>
              <div className="small muted" style={{ marginBottom: 12 }}>
                4 scenarios incl. one tool crash + one rate-limit storm. Zero retries, no validation:
                watch it break exactly where production does.
              </div>
              <button className="btn danger" disabled={busy === 'baseline'} onClick={() => runQuick('baseline')}>
                {busy === 'baseline' ? <span className="spinner" /> : '☣'} Run baseline
              </button>
            </div>
            <div className="badge muted mono" style={{ flex: '0 0 auto' }}>~1-2 min</div>
          </div>
        </div>
        <div className="card pad">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 14 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 3 }}>Quick gauntlet · hardened</div>
              <div className="small muted" style={{ marginBottom: 12 }}>
                Same chaos, same agent — retries with backoff, payload validation, sanitization,
                graceful degradation. The A/B half of the story.
              </div>
              <button className="btn primary" disabled={busy === 'hardened'} onClick={() => runQuick('hardened')}>
                {busy === 'hardened' ? <span className="spinner" /> : '▶'} Run hardened
              </button>
            </div>
            <div className="badge muted mono" style={{ flex: '0 0 auto' }}>~2-4 min</div>
          </div>
        </div>
      </div>

      <div className="sect-label">Latest executions</div>
      {!execs.length && <Empty>No executions yet — launch a gauntlet above or open the Stress Lab.</Empty>}
      {execs.length > 0 && (
        <div className="card">
          <table className="data">
            <thead>
              <tr><th>exec</th><th>suite</th><th>policy</th><th>progress</th><th>reliability</th><th>pass</th><th>latency</th><th>status</th></tr>
            </thead>
            <tbody>
              {(execs.slice(0, 6)).map(e => (
                <tr key={e.exec_id} className="rowlink" onClick={() => openExec(e.exec_id)}>
                  <td className="mono small">{e.exec_id}</td>
                  <td>{NICE_SUITE[e.suite] || e.suite}</td>
                  <td><span className={`badge ${e.policy_name?.includes('hard') ? 'ok' : 'err'}`}>{e.policy_name}</span></td>
                  <td className="mono small">{e.progress?.done}/{e.progress?.total}</td>
                  <td><RelNum value={e.summary?.reliability ?? null} /></td>
                  <td className="mono small">{e.summary ? `${e.summary.pass_rate}%` : '—'}</td>
                  <td className="mono small">{e.summary ? fmtMs(e.summary.latency_ms_avg) : '—'}</td>
                  <td>
                    {e.status === 'done' ? <span className="badge ok">done</span>
                      : e.status === 'error' ? <span className="badge err">error</span>
                      : <span className="badge warn"><span className="pulse-dot" /> running</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="grid2" style={{ marginTop: 24 }}>
        <div className="card pad">
          <div className="card-head" style={{ border: 'none', padding: 0, marginBottom: 4 }}>
            <h3>12 stress scenarios</h3>
            <span className="sub">4 categories · local chaos engine</span>
          </div>
          <div className="small muted" style={{ marginBottom: 10 }}>
            Deterministic simulated domain (PulseCRM billing) — no live traffic is ever harmed.
          </div>
          {scenarios ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {scenarios.scenarios.map(s => (
                <span key={s.id} className={`badge ${CATEGORY_COLOR[s.category] || 'muted'}`} title={s.name}>
                  {s.id} · {s.name.length > 34 ? s.name.slice(0, 33) + '…' : s.name}
                </span>
              ))}
            </div>
          ) : <Loading label="loading catalog…" />}
          <button className="btn sm ghost" style={{ marginTop: 12 }} onClick={() => setRoute('lab')}>Open Stress Lab →</button>
        </div>
        <div className="card pad">
          <div className="card-head" style={{ border: 'none', padding: 0, marginBottom: 4 }}>
            <h3>8 red-team attacks</h3>
            <span className="sub">authority spoofing · injection · leakage</span>
          </div>
          <div className="small muted" style={{ marginBottom: 10 }}>
            Every attack has a deterministic "did it work?"definition; outcomes are blocked / partial / complied.
          </div>
          {attacks ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {attacks.attacks.map(a => (
                <span key={a.id} className="badge err" title={a.goal}>{a.id} · {a.name}</span>
              ))}
            </div>
          ) : <Loading label="loading attacks…" />}
          <button className="btn sm ghost" style={{ marginTop: 12 }} onClick={() => setRoute('redteam')}>Open Red Team →</button>
        </div>
      </div>
    </div>
  )
}
