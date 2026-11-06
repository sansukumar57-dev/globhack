import { useEffect, useState } from 'react'
import {
  LayoutDashboard, KeyRound, ScanSearch, FlaskConical, Radio, Settings as SettingsIcon,
  RefreshCw,
} from 'lucide-react'
import { api, onToast, toast } from './api'
import Overview from './pages/Overview.jsx'
import Keys from './pages/Keys.jsx'
import Anomalies from './pages/Anomalies.jsx'
import Simulator from './pages/Simulator.jsx'
import Traffic from './pages/Traffic.jsx'
import Settings from './pages/Settings.jsx'

const NAV = [
  {
    group: 'Monitor',
    items: [
      { id: 'overview', label: 'Overview', icon: LayoutDashboard },
      { id: 'keys', label: 'Virtual keys', icon: KeyRound },
      { id: 'anomalies', label: 'Anomalies', icon: ScanSearch },
      { id: 'traffic', label: 'Live traffic', icon: Radio },
    ],
  },
  {
    group: 'Plan',
    items: [
      { id: 'simulator', label: 'Right-sizing', icon: FlaskConical },
      { id: 'settings', label: 'Autopilot', icon: SettingsIcon },
    ],
  },
]

const PAGES = { Overview, Keys, Anomalies, Simulator, Traffic, Settings }
const PAGE_LABELS = {
  overview: 'Overview',
  keys: 'Virtual keys',
  anomalies: 'Anomalies',
  simulator: 'Right-sizing',
  traffic: 'Live traffic',
  settings: 'Autopilot',
}

function readPage() {
  const id = window.location.hash.replace(/^#\/?/, '')
  return PAGES[id.charAt(0).toUpperCase() + id.slice(1)] ? id : 'overview'
}

export default function App() {
  const [page, setPage] = useState(readPage)
  const [refreshKey, setRefreshKey] = useState(0)
  const [lastUpdated, setLastUpdated] = useState(() => Date.now())
  const [now, setNow] = useState(() => Date.now())
  const [bifrostOk, setBifrostOk] = useState(null)
  const [toastMsg, setToastMsg] = useState(null)
  const [reseeding, setReseeding] = useState(false)

  useEffect(() => {
    let timer
    const off = onToast((msg) => {
      setToastMsg(msg)
      clearTimeout(timer)
      timer = setTimeout(() => setToastMsg(null), 4200)
    })
    return () => {
      off()
      clearTimeout(timer)
    }
  }, [])

  useEffect(() => {
    if (!window.location.hash) window.history.replaceState(null, '', '#overview')
    const sync = () => setPage(readPage())
    window.addEventListener('hashchange', sync)
    sync()
    return () => window.removeEventListener('hashchange', sync)
  }, [])

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
    return () => {
      mounted = false
      clearInterval(t)
    }
  }, [])

  useEffect(() => {
    const t = setInterval(() => {
      setRefreshKey((k) => k + 1)
      setLastUpdated(Date.now())
    }, 10000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])

  const refresh = () => {
    setRefreshKey((k) => k + 1)
    setLastUpdated(Date.now())
  }

  const reseed = async () => {
    setReseeding(true)
    try {
      await api.seed()
      refresh()
      toast('Demo data reseeded')
    } catch (e) {
      toast(`Reseed failed: ${e.message}`)
    } finally {
      setReseeding(false)
    }
  }

  const Active = PAGES[page.charAt(0).toUpperCase() + page.slice(1)] || Overview
  const updatedAgo = Math.max(0, Math.floor((now - lastUpdated) / 1000))
  const liveLabel = bifrostOk === false
    ? 'gateway offline'
    : updatedAgo < 2
      ? 'live · just now'
      : `live · updated ${updatedAgo}s ago`

  return (
    <>
      <a className="skip-link" href="#main-content">Skip to console</a>
      <div className="shell">
        <aside className="sidebar">
          <div className="brand">
            <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
              <rect x=".5" y=".5" width="31" height="31" rx="4" fill="none" stroke="#5a5449" />
              <path
                d="M6.5 21.5h4.2l2.5-9.5 3.6 13 3.1-8h4.6"
                fill="none"
                stroke="#eee9de"
                strokeWidth="1.7"
                strokeLinecap="square"
                strokeLinejoin="miter"
              />
              <circle cx="25.5" cy="17" r="2" fill="#b23a0c" />
            </svg>
            <div>
              <div className="brand-name">Foresight</div>
              <div className="brand-sub">Spend desk</div>
            </div>
          </div>

          {NAV.map((group) => (
            <div className="nav-group" key={group.group}>
              <div className="nav-label">{group.group}</div>
              {group.items.map((item) => {
                const Icon = item.icon
                const active = page === item.id
                return (
                  <a
                    key={item.id}
                    href={`#${item.id}`}
                    className={`nav-item ${active ? 'active' : ''}`}
                    aria-current={active ? 'page' : undefined}
                    aria-label={item.label}
                    title={item.label}
                  >
                    <Icon aria-hidden="true" />
                    <span>{item.label}</span>
                  </a>
                )
              })}
            </div>
          ))}

          <div className="nav-spacer" />

          <div className="sidebar-foot">
            <div className={`gateway ${bifrostOk === false ? 'off' : ''}`} title="Bifrost gateway connectivity">
              <span className="dot" />
              <span className="gateway-label">
                Bifrost {bifrostOk === null ? 'checking' : bifrostOk ? 'gateway online' : 'gateway offline'}
              </span>
            </div>
            <div className="sidebar-note">
              Extends{' '}
              <a href="https://github.com/maximhq/bifrost" target="_blank" rel="noreferrer">
                Bifrost OSS ↗
              </a>
              <br />
              Problem #04 · Geek Room × Bifrost
            </div>
          </div>
        </aside>

        <div className="main">
          <header className="topbar">
            <span className="crumb">
              Bifrost Priority Track <span className="sep">/</span> <b>{PAGE_LABELS[page]}</b>
            </span>
            <span className="topbar-spacer" />
            <span className="live" title="The console refreshes every 10 seconds">
              <span className={`live-dot ${bifrostOk === false ? 'off' : ''}`} />
              {liveLabel}
            </span>
            <span className="topbar-divider" />
            <button className="icon-btn" onClick={refresh} aria-label="Refresh console data" title="Refresh now">
              <RefreshCw size={13} aria-hidden="true" />
            </button>
          </header>

          <main className="content" id="main-content" tabIndex={-1}>
            <div className="content-inner">
              <Active
                refreshKey={refreshKey}
                onReseed={reseed}
                reseeding={reseeding}
              />
            </div>
          </main>
        </div>
      </div>

      {toastMsg && <div className="toast" role="status" aria-live="polite">{toastMsg}</div>}
    </>
  )
}
