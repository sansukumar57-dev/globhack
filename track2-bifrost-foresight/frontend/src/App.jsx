import { useEffect, useState } from 'react'
import {
  LayoutDashboard, KeyRound, ScanSearch, FlaskConical, Radio, Settings as SettingsIcon,
  RefreshCw, Database, ExternalLink,
} from 'lucide-react'
import { api, onToast } from './api'
import Overview from './pages/Overview.jsx'
import Keys from './pages/Keys.jsx'
import Anomalies from './pages/Anomalies.jsx'
import Simulator from './pages/Simulator.jsx'
import Traffic from './pages/Traffic.jsx'
import Settings from './pages/Settings.jsx'

const NAV = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'keys', label: 'Virtual Keys', icon: KeyRound },
  { id: 'anomalies', label: 'Anomalies', icon: ScanSearch },
  { id: 'simulator', label: 'Right-sizing', icon: FlaskConical },
  { id: 'traffic', label: 'Live Traffic', icon: Radio },
  { id: 'settings', label: 'Autopilot', icon: SettingsIcon },
]

const PAGES = { Overview, Keys, Anomalies, Simulator, Traffic, Settings }
const TITLES = {
  overview: 'Gateway spend, forecasted',
  keys: 'Virtual keys & budgets',
  anomalies: 'Traffic anomaly detection',
  simulator: 'Cost right-sizing simulator',
  traffic: 'Live metered requests',
  settings: 'Autopilot & webhooks',
}

export default function App() {
  const [page, setPage] = useState('overview')
  const [refreshKey, setRefreshKey] = useState(0)
  const [bifrostOk, setBifrostOk] = useState(null)
  const [toastMsg, setToastMsg] = useState(null)
  const [reseeding, setReseeding] = useState(false)

  useEffect(() => onToast((msg) => {
    setToastMsg(msg)
    const t = setTimeout(() => setToastMsg(null), 4200)
    return () => clearTimeout(t)
  }), [])

  useEffect(() => {
    let mounted = true
    const check = async () => {
      try {
        const res = await fetch('/api/health')
        const body = await res.json()
        if (mounted) setBifrostOk(Boolean(body.bifrost_reachable))
      } catch {
        if (mounted) setBifrostOk(false)
      }
    }
    check()
    const t = setInterval(check, 10000)
    return () => { mounted = false; clearInterval(t) }
  }, [])

  useEffect(() => {
    const t = setInterval(() => setRefreshKey((k) => k + 1), 10000)
    return () => clearInterval(t)
  }, [])

  const reseed = async () => {
    setReseeding(true)
    try {
      await api.seed()
      setRefreshKey((k) => k + 1)
    } finally {
      setReseeding(false)
    }
  }

  const Active = PAGES[page.charAt(0).toUpperCase() + page.slice(1)]

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <svg className="brand-mark" viewBox="0 0 64 64" aria-hidden="true">
            <rect width="64" height="64" rx="14" fill="#0d1030" />
            <path d="M17 40 L25.5 40 L29.5 23 L36 40 L42.5 40 L46.5 31 L50 40"
                  fill="none" stroke="url(#brandGrad)" strokeWidth="3.6" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="53" cy="40" r="2.6" fill="#f472b6" />
            <defs>
              <linearGradient id="brandGrad" x1="17" y1="40" x2="53" y2="40" gradientUnits="userSpaceOnUse">
                <stop stopColor="#7c5cff" /><stop offset="0.5" stopColor="#a855f7" /><stop offset="1" stopColor="#f472b6" />
              </linearGradient>
            </defs>
          </svg>
          <div>
            <div className="brand-name"><em>Foresight</em></div>
            <div className="brand-sub">Predictive governance</div>
          </div>
        </div>

        <div className="nav-label">Console</div>
        {NAV.map((item) => {
          const Icon = item.icon
          return (
            <button key={item.id} className={`nav-item ${page === item.id ? 'active' : ''}`} onClick={() => setPage(item.id)}>
              <Icon size={16} />
              <span>{item.label}</span>
            </button>
          )
        })}

        <div className="sidebar-foot">
          <button className="btn btn-ghost btn-sm" onClick={reseed} disabled={reseeding}>
            <Database size={13} /> {reseeding ? 'Reseeding…' : 'Reseed demo data'}
          </button>
          <div className="powered">
            Extends <b>Bifrost OSS</b> — the Apache-2.0 AI gateway by Maxim.<br />
            Problem Statement <b>#04</b> · Geek Room × Bifrost Priority Track
            <a href="https://github.com/maximhq/bifrost" target="_blank" rel="noreferrer"
               style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 6, color: 'var(--violet)' }}>
              maximhq/bifrost <ExternalLink size={10} />
            </a>
          </div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <span className="crumb">Bifrost <b>Priority Track</b></span>
          <span className="topbar-title">{TITLES[page]}</span>
          <span className="topbar-spacer" />
          <span className="status-pill" title="Bifrost gateway connectivity">
            <span className={`status-dot ${bifrostOk === false ? 'off' : ''}`} />
            Bifrost {bifrostOk === null ? '…' : bifrostOk ? 'online · :8080' : 'offline'}
          </span>
          <button className="btn btn-ghost btn-sm" onClick={() => setRefreshKey((k) => k + 1)} title="Refresh now">
            <RefreshCw size={13} />
          </button>
        </header>

        <main className="content">
          <div className="content-inner">
            <Active refreshKey={refreshKey} />
          </div>
        </main>
      </div>

      {toastMsg && <div className="toast">{toastMsg}</div>}
    </div>
  )
}
