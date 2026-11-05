import { Plus, Plug, Radio } from 'lucide-react'
import { StatusPill } from './ui.jsx'

const TITLES = {
  overview: 'Overview',
  runs: 'Runs',
  run: 'Run detail',
  agents: 'Agents',
  tasks: 'Suite',
}

export default function Topbar({ route, health, runningCount = 0, onRun, onConnect }) {
  return (
    <header className="topbar">
      <div className="topbar-title">
        <span className="topbar-crumb">criterion /</span>
        <span className="topbar-page">{TITLES[route] || 'Overview'}</span>
        {runningCount > 0 && (
          <span className="topbar-running"><span className="live-dot" />{runningCount} running</span>
        )}
      </div>

      <div className="topbar-actions">
        <span className="topbar-chip sandbox-chip" title={health?.gateway?.note || 'Reference agents run in a deterministic sandbox'}>
          <span className="sandbox-dot" />
          {health?.judge?.mode === 'deterministic-rubric' ? 'Sandbox' : 'Live'}
        </span>
        <span className="topbar-chip gateway-chip" title={health?.gateway?.note || 'Bifrost-ready'}>
          <Radio size={13} />
          Bifrost-ready
        </span>
        <button type="button" className="btn btn-secondary topbar-connect" onClick={onConnect}>
          <Plug size={15} />
          <span>Connect agent</span>
        </button>
        <button type="button" className="btn btn-primary" onClick={onRun}>
          <Plus size={16} />
          <span>Run benchmark</span>
        </button>
      </div>
    </header>
  )
}
