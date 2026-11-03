import { useEffect, useState } from 'react'
import { api, fmtMs, fmtCost, fmtTime, CATEGORY_COLOR } from '../api.js'
import { Meter, RelNum, PassBadge, OutcomeBadge, JudgeScores, ChecksList, Waterfall, Empty, Loading, Stat } from '../ui.jsx'

const NICE_SUITE = {
  quick: 'Quick gauntlet', full: 'Full suite', tooling: 'Tooling stress',
  gateway: 'Gateway stress', redteam: 'Red-team', custom: 'Custom',
}

function ExecPicker({ execs, activeExecId, openExec }) {
  return (
    <div className="card" style={{ marginBottom: 18 }}>
      <div className="card-head"><h3>Executions</h3><span className="sub">{execs.length} total</span></div>
      <table className="data">
        <thead>
          <tr><th>exec</th><th>suite</th><th>policy</th><th>progress</th><th>reliability</th><th>pass</th><th>started</th><th>status</th></tr>
        </thead>
        <tbody>
          {execs.map(e => (
            <tr key={e.exec_id} className={`rowlink${e.exec_id === activeExecId ? ' active' : ''}`} onClick={() => openExec(e.exec_id)}
                style={e.exec_id === activeExecId ? { background: 'var(--card-2)' } : undefined}>
              <td className="mono small">{e.exec_id}</td>
              <td>{NICE_SUITE[e.suite] || e.suite}</td>
              <td><span className={`badge ${e.policy_name?.includes('hard') ? 'ok' : 'err'}`}>{e.policy_name}</span></td>
              <td className="mono small">{e.progress?.done}/{e.progress?.total}</td>
              <td><RelNum value={e.summary?.reliability ?? null} /></td>
              <td className="mono small">{e.summary ? `${e.summary.pass_rate}%` : '—'}</td>
              <td className="mono small faint">{fmtTime(e.started_at)}</td>
              <td>
                {e.status === 'done' ? <span className="badge ok">done</span>
                  : e.status === 'error' ? <span className="badge err" title={e.error}>error</span>
                  : <span className="badge warn"><span className="pulse-dot" /> running</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RunCard({ r, redteam }) {
  const [open, setOpen] = useState(false)
  const [full, setFull] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!open || full || err) return
    let dead = false
    api.run(r.run_id).then(d => { if (!dead) setFull(d) }).catch(e => { if (!dead) setErr(String(e.message || e)) })
    return () => { dead = true }
  }, [open, full, err, r.run_id])

  const rel = r.reliability ?? 0
  return (
    <div className="run-card">
      <button className="run-card-head" onClick={() => setOpen(o => !o)}>
        <span className={`badge ${CATEGORY_COLOR[r.category] || 'muted'}`}>{r.category}</span>
        <span className="mono small faint">{r.scenario_id}</span>
        <span style={{ fontWeight: 600, fontSize: 13, flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {r.scenario_name}
        </span>
        {redteam
          ? <OutcomeBadge outcome={r.redteam_outcome} />
          : <PassBadge passed={r.passed} />}
        <span className="run-rel">
          <span className="num" style={{ color: rel >= 80 ? 'var(--ok)' : rel >= 50 ? 'var(--warn)' : 'var(--err)' }}>{rel}</span>
          <span className="small faint">rel</span>
        </span>
        <span className="mono small faint">{fmtMs(r.latency_ms)}</span>
        <span className="faint small">{open ? '▾' : '▸'}</span>
      </button>

      {open && (
        <div className="run-body">
          <div className="kv">
            <span className="k">user message</span>
            <span className="v" style={{ fontStyle: 'italic' }}>“{r.user_message}”</span>
            <span className="k">injected faults</span>
            <span className="v mono small">{(r.faults || []).length ? JSON.stringify(r.faults) : '— none —'}</span>
            <span className="k">faults fired</span>
            <span className="v mono small">{r.faults_fired?.length ? r.faults_fired.join(', ') : '—'}</span>
            <span className="k">flags</span>
            <span className="v">
              {r.flags?.length
                ? r.flags.map((f, i) => <span key={i} className="badge warn" style={{ marginRight: 5 }}>{f}</span>)
                : <span className="faint">none</span>}
            </span>
            <span className="k">tokens</span>
            <span className="v mono small">
              in {r.tokens?.input ?? '—'} · out {r.tokens?.output ?? '—'} → est. {fmtCost(r.tokens?.est_cost)}
            </span>
          </div>

          <div className="sect-label">Final answer</div>
          {r.final_answer
            ? <div className="answer-box">{r.final_answer}</div>
            : <div className="answer-box error">{r.error ? `${r.error.type} — ${r.error.where}: ${r.error.detail}` : 'no final answer'}</div>}

          <div className="sect-label">Deterministic checks</div>
          <ChecksList checks={r.checks || []} />

          {redteam && <RedteamChecks r={r} />}

          {!redteam && (
            <>
              <div className="sect-label">LLM judge</div>
              <JudgeScores judge={r.judge} />
            </>
          )}

          {open && <span className="small faint">trace: <b className="mono">{r.run_id}</b>{full && ` · ${full.trace?.spans?.length} spans`}{err && ` · trace unavailable: ${err}`}</span>}
          <div style={{ marginTop: 10 }}>
            {full ? (
              <>
                <div className="sect-label" style={{ marginTop: 16 }}>Span waterfall</div>
                <Waterfall trace={full.trace} />
                {full.tool_calls?.length > 0 && (
                  <>
                    <div className="sect-label" style={{ marginTop: 16 }}>Tool ledger</div>
                    <table className="data">
                      <thead><tr><th>#</th><th>tool</th><th>args</th><th>fault</th></tr></thead>
                      <tbody>
                        {full.tool_calls.map((t, i) => (
                          <tr key={i}>
                            <td className="mono small faint">{i + 1}</td>
                            <td className="mono small">{t.tool}</td>
                            <td className="mono small faint" style={{ whiteSpace: 'normal', wordBreak: 'break-all' }}>{JSON.stringify(t.args)}</td>
                            <td>{t.fault ? <span className="fault-chip">{t.fault}</span> : <span className="badge ok">ok</span>}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </>
                )}
              </>
            ) : err
              ? <div className="small faint">trace unavailable — {err}</div>
              : <div className="small faint" style={{ padding: '8px 0' }}><span className="spinner" /> fetching trace…</div>}
          </div>
        </div>
      )}
    </div>
  )
}

function RedteamChecks({ r }) {
  return (
    <>
      <div className="sect-label">Attack outcome</div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <OutcomeBadge outcome={r.redteam_outcome} />
        <span className="small muted">
          {r.redteam_outcome === 'blocked' && 'the attack failed — agent held the line'}
          {r.redteam_outcome === 'partial' && 'agent partially resisted — some checks failed'}
          {r.redteam_outcome === 'complied' && 'the attack succeeded — agent complied'}
        </span>
      </div>
    </>
  )
}

function ExecDetail({ execId, execs, refreshExecs, launch }) {
  const [exec, setExec] = useState(null)
  const [err, setErr] = useState(null)
  const [autoAB, setAutoAB] = useState(false)

  useEffect(() => {
    if (!execId) { setExec(null); return }
    // optimistic: use cached copy; refresh from API
    const cached = execs.find(e => e.exec_id === execId)
    if (cached) setExec(cached)
    let dead = false
    api.exec(execId).then(d => { if (!dead) setExec(d) }).catch(e => { if (!dead) setErr(String(e.message || e)) })
    return () => { dead = true }
  }, [execId, execs])

  if (!execId) return <Empty>Select an execution to inspect runs, spans and traces.</Empty>
  if (err) return <div className="banner">⚠ {err}</div>
  if (!exec) return <Loading label="loading execution…" />

  const isRed = exec.suite === 'redteam'
  const total = exec.progress?.total || 0
  const doneN = exec.progress?.done || 0
  const running = exec.status === 'queued' || exec.status === 'running'
  const s = exec.summary

  const runMirror = async () => {
    setAutoAB(true)
    try {
      await launch({ suite: exec.suite === 'custom' ? 'custom' : exec.suite,
                     scenario_ids: exec.scenario_ids,
                     policy: { name: exec.policy_name?.includes('hard') ? 'baseline' : 'hardened' } })
    } finally { setAutoAB(false) }
  }

  return (
    <div>
      <div className="card pad" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <span className="mono" style={{ fontWeight: 700 }}>{exec.exec_id}</span>
          <span className="badge accent">{NICE_SUITE[exec.suite] || exec.suite}</span>
          <span className={`badge ${exec.policy_name?.includes('hard') ? 'ok' : 'err'}`}>{exec.policy_name}</span>
          {exec.status === 'done' && <span className="badge ok">done</span>}
          {running && <span className="badge warn"><span className="pulse-dot" /> running {doneN}/{total}</span>}
          {exec.status === 'error' && <span className="badge err" title={exec.error}>error</span>}
          <div style={{ flex: 1 }} />
          {exec.status === 'done' && (
            <button className="btn sm ghost" onClick={runMirror} disabled={autoAB}>
              {autoAB ? <span className="spinner" /> : '⇄'} A/B {exec.policy_name?.includes('hard') ? 'baseline' : 'hardened'}
            </button>
          )}
        </div>
        {running && (
          <div style={{ marginTop: 12 }}>
            <div className="progress-track"><div style={{ width: `${total ? (doneN / total) * 100 : 0}%` }} /></div>
            <div className="small faint" style={{ marginTop: 5 }}>
              {doneN}/{total} scenarios · flows through retries, timeouts and the judge — refreshes automatically
            </div>
          </div>
        )}
        {exec.error && <div className="banner" style={{ marginTop: 12 }}>⚠ {exec.error}</div>}
      </div>

      {s && (
        <div className="stat-row" style={{ marginBottom: 18 }}>
          <Stat k="Reliability" v={s.reliability} d="checks 45% + judge 55%" cls={s.reliability >= 80 ? 'ok' : s.reliability >= 50 ? 'accent' : 'err'} />
          <Stat k="Pass rate" v={`${s.pass_rate}%`} d="deterministic gate" cls={s.pass_rate === 100 ? 'ok' : 'err'} />
          <Stat k="Judge" v={s.judged ? 'live' : 'n/a'} d="LLM-as-judge" />
          <Stat k="Latency avg" v={fmtMs(s.latency_ms_avg)} d="incl. retries & backoff" />
          <Stat k="Tokens" v={s.tokens_total?.toLocaleString?.() ?? s.tokens_total} d={`est. ${fmtCost(s.est_cost)}`} />
          {isRed && <Stat k="Safety" v={`${s.safety_score ?? 0}%`} d="blocked + ½·partial" cls={s.safety_score >= 80 ? 'ok' : 'err'} />}
        </div>
      )}

      {!isRed && s && (
        <div className="card pad" style={{ marginBottom: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span className="small faint" style={{ width: 90 }}>PASS MIX</span>
            <div style={{ flex: 1 }}><Meter thick value={s.pass_rate} /></div>
          </div>
        </div>
      )}

      <div className="sect-label">{isRed ? 'Attack runs' : 'Scenario runs'} ({(exec.results || []).length})</div>
      {(exec.results || []).map(r => <RunCard key={r.run_id} r={r} redteam={isRed} />)}
      {running && doneN < total && <Loading label="next scenario in flight…" />}
    </div>
  )
}

export default function Runs({ execs, activeExecId, openExec, refreshExecs, launch }) {
  if (!execs.length) return <Empty>No executions yet — open the Stress Lab to launch a gauntlet.</Empty>
  const selectedId = activeExecId && execs.some(e => e.exec_id === activeExecId) ? activeExecId : execs[0]?.exec_id
  return (
    <div>
      <ExecPicker execs={execs} activeExecId={selectedId} openExec={openExec} />
      <ExecDetail execId={selectedId} execs={execs} refreshExecs={refreshExecs} launch={launch} />
    </div>
  )
}
