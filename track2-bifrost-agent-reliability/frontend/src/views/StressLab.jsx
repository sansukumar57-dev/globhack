import { useEffect, useMemo, useState } from 'react'
import { api, CATEGORY_COLOR } from '../api.js'
import { Loading, ErrorView } from '../ui.jsx'

const SUITES = ['quick', 'full', 'tooling', 'gateway']

function FaultChips({ faults }) {
  if (!faults?.length) return <span className="small faint">none — clean path</span>
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {faults.map((f, i) => (
        <span key={i} className="fault-chip">
          {f.type}{f.tool ? `:${f.tool}` : ''}{f.rate != null ? ` ${f.rate}` : ''}{f.seconds ? ` +${f.seconds}s` : ''}
        </span>
      ))}
    </div>
  )
}

export default function StressLab({ launch, setRoute }) {
  const [cat, setCat] = useState(null)          // {scenarios, suites}
  const [selected, setSelected] = useState([])
  const [policyName, setPolicyName] = useState('baseline')
  const [customJson, setCustomJson] = useState('')
  const [error, setError] = useState(null)
  const [starting, setStarting] = useState(false)
  const [currentSuite, setCurrentSuite] = useState('quick')

  useEffect(() => {
    api.scenarios().then(d => {
      setCat(d)
      setSelected(d.suites.find(s => s.id === 'quick')?.scenario_ids?.slice() || [])
    }).catch(e => setError(String(e.message || e)))
  }, [])

  const catOf = useMemo(() => {
    const m = {}
    for (const s of cat?.scenarios || []) m[s.id] = s
    return m
  }, [cat])

  const suiteIds = useMemo(() => (cat?.scenarios || []).map(s => s.id), [cat])

  const toggle = (id) => {
    setCurrentSuite('custom')
    setSelected(sel => sel.includes(id) ? sel.filter(x => x !== id) : [...sel, id])
  }

  const applySuite = (sid) => {
    const s = cat.suites.find(x => x.id === sid)
    if (!s) return
    setCurrentSuite(sid)
    setSelected([...s.scenario_ids])
  }

  const go = async () => {
    setError(null)
    let policy
    if (policyName === 'custom') {
      try { policy = JSON.parse(customJson) } catch (e) { setError(`custom policy JSON: ${e.message}`); return }
    } else {
      policy = { name: policyName }
    }
    setStarting(true)
    try {
      if (currentSuite === 'redteam') {
        setRoute('redteam')
        await launch({ suite: 'redteam', policy })
      } else {
        await launch({ suite: currentSuite === 'custom' || currentSuite === 'redteam' ? 'custom' : currentSuite,
                       scenario_ids: selected, policy })
      }
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setStarting(false)
    }
  }

  if (!cat) return error ? <ErrorView error={error} /> : <Loading label="loading scenario catalog…" />

  const running = starting

  return (
    <div>
      <div className="grid2" style={{ marginBottom: 20, gridTemplateColumns: '240px 1fr' }}>
        <div className="card">
          <div className="card-head"><h3>Suites</h3></div>
          <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 7, padding: 12 }}>
            {cat.suites.map(s => (
              <button
                key={s.id}
                className={`btn ghost${currentSuite === s.id ? ' active' : ''}`}
                style={{ justifyContent: 'flex-start', whiteSpace: 'normal', textAlign: 'left' }}
                onClick={() => applySuite(s.id)}
              >
                <span style={{ flex: 1 }}>
                  <span style={{ display: 'block', fontWeight: 600 }}>{s.label}</span>
                  <span style={{ display: 'block', fontSize: 10.5, color: 'var(--text-3)', fontWeight: 400 }}>{s.description}</span>
                </span>
              </button>
            ))}
            <button
              className={`btn ghost${currentSuite === 'redteam' ? ' active' : ''}`}
              style={{ justifyContent: 'flex-start', whiteSpace: 'normal', textAlign: 'left' }}
              onClick={() => setCurrentSuite('redteam')}
            >
              <span>
                <span style={{ display: 'block', fontWeight: 600 }}>Red-team gauntlet (8)</span>
                <span style={{ display: 'block', fontSize: 10.5, color: 'var(--text-3)', fontWeight: 400 }}>
                  Adversarial attacks — handled in the Red Team view.
                </span>
              </span>
            </button>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3>Policy under test</h3>
            <span className="sub">the same agent code, different resilience knobs</span>
          </div>
          <div className="card-body">
            <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
              {['baseline', 'hardened', 'custom'].map(p => (
                <button key={p} className={`btn ghost${policyName === p ? ' active' : ''}`} onClick={() => setPolicyName(p)}>
                  {p}
                </button>
              ))}
            </div>
            {policyName === 'baseline' && (
              <div className="small muted">0 retries · 4s tool timeout · no validation, no sanitization, no degradation. Crashes propagate.</div>
            )}
            {policyName === 'hardened' && (
              <div className="small muted">3 LLM retries w/ backoff · tool retry · 12s tool timeout · payload validation · injection sanitization · graceful degradation.</div>
            )}
            {policyName === 'custom' && (
              <textarea
                className="code"
                spellCheck={false}
                placeholder={'{\n  "name": "my-policy",\n  "llm_retries": 2,\n  "tool_retries": 1,\n  "validate_tool_output": true,\n  "graceful_degradation": true\n}'}
                value={customJson}
                onChange={e => setCustomJson(e.target.value)}
              />
            )}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h3>Scenario matrix</h3>
          <span className="sub">{selected.length} selected</span>
          <div style={{ flex: 1 }} />
          <button className="btn sm ghost" onClick={() => setSelected(suiteIds)}>select all</button>
          <button className="btn sm ghost" onClick={() => setSelected([])}>clear</button>
        </div>
        <table className="data">
          <thead>
            <tr><th style={{ width: 30 }}></th><th>id</th><th>scenario</th><th>category</th><th>difficulty</th><th>injected faults</th><th>checks</th></tr>
          </thead>
          <tbody>
            {cat.scenarios.map(s => (
              <tr key={s.id}>
                <td><input type="checkbox" checked={selected.includes(s.id)} onChange={() => toggle(s.id)} /></td>
                <td className="mono small">{s.id}</td>
                <td style={{ maxWidth: 280 }}>
                  <div style={{ fontWeight: 500 }}>{s.name}</div>
                  <div className="small faint" style={{ whiteSpace: 'normal' }}>{s.user_message_preview}</div>
                </td>
                <td><span className={`badge ${CATEGORY_COLOR[s.category] || 'muted'}`}>{s.category}</span></td>
                <td className="small muted">{s.difficulty}</td>
                <td><FaultChips faults={s.faults} /></td>
                <td className="mono small faint">{s.checks.length}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="card-body" style={{ borderTop: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 12 }}>
          {currentSuite === 'redteam'
            ? <>
                <button className="btn primary" disabled={running} onClick={go}>
                  {running ? <span className="spinner" /> : '⚔'} Launch red-team gauntlet
                </button>
                <span className="small faint">→ continues in the Red Team view</span>
              </>
            : <button className="btn primary" disabled={running || !selected.length} onClick={go}>
                {running ? <span className="spinner" /> : '▶'} Launch run · {selected.length} scenario{selected.length === 1 ? '' : 's'} · {policyName}
              </button>}
          <span className="small faint" style={{ flex: 1 }}>
            {currentSuite === 'custom' && <span className="badge accent" style={{ marginRight: 6 }}>custom</span>}
            results stream live on the Runs page
          </span>
        </div>
      </div>
    </div>
  )
}
