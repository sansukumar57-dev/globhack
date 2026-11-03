import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import Overview from './views/Overview.jsx'
import StressLab from './views/StressLab.jsx'
import Runs from './views/Runs.jsx'
import RedTeam from './views/RedTeam.jsx'
import DebuggerView from './views/Debugger.jsx'
import PolicyView from './views/PolicyView.jsx'

const NAV = [
  { id: 'overview', label: 'Overview', ico: '⌘' },
  { id: 'lab', label: 'Stress Lab', ico: '☣' },
  { id: 'runs', label: 'Runs', ico: '≣', countFrom: 'execs' },
  { id: 'redteam', label: 'Red Team', ico: '⚔' },
  { id: 'debugger', label: 'Debugger', ico: '⚗' },
  { id: 'policy', label: 'Policy', ico: '⚙' },
]

const RUNNING_STATES = new Set(['queued', 'running'])

export default function App() {
  const [route, setRoute] = useState('overview')
  const [health, setHealth] = useState(null)
  const [execs, setExecs] = useState([])
  const [activeExecId, setActiveExecId] = useState(null)
  const [lastError, setLastError] = useState(null)

  const refreshExecs = useCallback(() => {
    api.execs().then(d => setExecs(d.executions || [])).catch(() => {})
  }, [])

  const openExec = useCallback((execId) => {
    setActiveExecId(execId)
    setRoute('runs')
  }, [])

  const launch = useCallback(async (payload) => {
    setLastError(null)
    try {
      const r = await api.start(payload)
      setActiveExecId(r.exec_id)
      refreshExecs()
      setRoute('runs')
      return r
    } catch (e) {
      setLastError(String(e.message || e))
      throw e
    }
  }, [refreshExecs])

  // initial load
  useEffect(() => {
    api.health().then(setHealth).catch(() => {})
    refreshExecs()
  }, [refreshExecs])

  // poll while any execution is still running
  useEffect(() => {
    const running = execs.some(e => RUNNING_STATES.has(e.status))
    if (!running) return undefined
    const t = setInterval(refreshExecs, 2500)
    return () => clearInterval(t)
  }, [execs, refreshExecs])

  // poll the open execution while it runs
  const activeExec = execs.find(e => e.exec_id === activeExecId)
  useEffect(() => {
    if (!activeExecId || !execs.find(e => e.exec_id === activeExecId)) return undefined
    if (!RUNNING_STATES.has(activeExec?.status)) return undefined
    const t = setInterval(refreshExecs, 2000)
    return () => clearInterval(t)
  }, [activeExecId, activeExec?.status, execs, refreshExecs])

  const navCount = (nav) => {
    if (nav.countFrom === 'execs') return execs.length || ''
    const n = nav.id === 'redteam'
      ? execs.filter(e => e.suite === 'redteam').length
      : nav.id === 'debugger'
        ? execs.filter(e => e.status === 'done' && e.summary && e.summary.pass_rate < 100).length
        : ''
    return n || ''
  }

  return (
    <div className="shell">
      <aside className="rail">
        <div className="brand">
          <div className="brand-name"><span className="glyph">⚡</span>Faultline</div>
          <div className="brand-sub">Agent Reliability</div>
        </div>
        <nav className="nav">
          {NAV.map(n => (
            <button
              key={n.id}
              className={`nav-item${route === n.id ? ' active' : ''}`}
              onClick={() => setRoute(n.id)}
            >
              <span className="ico">{n.ico.trim() || '≣'}</span>
              {n.label}
              {navCount(n) !== '' && <span className="count">{navCount(n)}</span>}
            </button>
          ))}
        </nav>
        <div className="rail-foot">
          <b>Track 2</b> · Bifrost / Maxim AI<br />
          <span title={health?.gateway?.note || ''}>gateway alcove: llm-observability</span>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <span className="crumb">faultline&nbsp;/&nbsp;</span>
          <span className="title">{NAV.find(n => n.id === route)?.label}</span>
          <div className="topbar-spacer" />
          {health && (
            <>
              <span className="chip" title={health.gateway?.note || ''}>
                <span className={`dot${health.has_provider_key ? '' : ' err'}`} />
                {health.provider} · {health.model}
              </span>
              <span className="chip" title={`LLM judge: ${health.judge_model}`}>judge · {health.judge_model}</span>
              <span className="chip" title="Bifrost by Maxim AI is OpenAI-compatible — set PROVIDER=bifrost to route runs through a Bifrost gateway">
                <span className="dot accent" />bifrost-ready
              </span>
            </>
          )}
        </header>

        {lastError && (
          <div style={{ padding: '10px 28px 0' }}>
            <div className="banner">⚠ {lastError} <button className="btn sm ghost" style={{ marginLeft: 8 }} onClick={() => setLastError(null)}>dismiss</button></div>
          </div>
        )}

        <div className="content">
          {route === 'overview' && <Overview health={health} execs={execs} launch={launch} openExec={openExec} setRoute={setRoute} />}
          {route === 'lab' && <StressLab launch={launch} setRoute={setRoute} execs={execs} />}
          {route === 'runs' && <Runs execs={execs} activeExecId={activeExecId} openExec={openExec} refreshExecs={refreshExecs} launch={launch} />}
          {route === 'redteam' && <RedTeam execs={execs.filter(e => e.suite === 'redteam')} launch={launch} openExec={openExec} />}
          {route === 'debugger' && <DebuggerView execs={execs} openExec={openExec} />}
          {route === 'policy' && <PolicyView onApplied={() => refreshExecs()} />}
        </div>
      </div>
    </div>
  )
}
