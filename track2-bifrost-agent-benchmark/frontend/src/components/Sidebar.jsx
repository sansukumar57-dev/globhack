import {
  Bot,
  ClipboardList,
  Gauge,
  ListChecks,
  Plus,
  Radio,
} from 'lucide-react'
import { Logo } from './ui.jsx'
import { fmtNumber } from '../lib/format.js'

const NAV = [
  { id: 'overview', label: 'Overview', icon: Gauge },
  { id: 'runs', label: 'Runs', icon: ListChecks, countKey: 'runs' },
  { id: 'agents', label: 'Agents', icon: Bot, countKey: 'agents' },
  { id: 'tasks', label: 'Suite', icon: ClipboardList, countKey: 'tasks' },
]

export default function Sidebar({ route, setRoute, stats, health, onRun }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <Logo />
      </div>

      <nav className="sidebar-nav" aria-label="Primary navigation">
        <p className="nav-label">Workspace</p>
        {NAV.map((item) => {
          const Icon = item.icon
          const active = route === item.id || (route === 'run' && item.id === 'runs')
          const count = item.countKey ? stats?.[item.countKey] : null
          return (
            <button
              key={item.id}
              type="button"
              className={`nav-item${active ? ' active' : ''}`}
              onClick={() => setRoute(item.id)}
              aria-current={active ? 'page' : undefined}
            >
              <Icon size={16} strokeWidth={1.9} />
              <span>{item.label}</span>
              {count !== null && count !== undefined && <span className="nav-count">{fmtNumber(count)}</span>}
            </button>
          )
        })}
      </nav>

      <div className="sidebar-rule" />

      <div className="sidebar-suite">
        <div className="suite-kicker"><span className="live-dot" />Active suite</div>
        <p className="suite-name">Commerce support <span>v3</span></p>
        <p className="suite-meta">18 tasks · 4 categories</p>
        <button type="button" className="sidebar-suite-link" onClick={() => setRoute('tasks')}>
          Inspect the suite <span aria-hidden="true">↗</span>
        </button>
      </div>

      <div className="sidebar-foot">
        <button type="button" className="sidebar-run" onClick={onRun}>
          <Plus size={15} /> New benchmark
        </button>
        <div className="environment">
          <span className="environment-dot" />
          <span>Sandbox</span>
          <span className="environment-sep">·</span>
          <span className="environment-muted" title={health?.gateway?.note || 'Bifrost-ready adapters'}>
            <Radio size={12} /> Bifrost-ready
          </span>
        </div>
        <p className="version">criterion v{health?.version || '0.3.0'}</p>
      </div>
    </aside>
  )
}
