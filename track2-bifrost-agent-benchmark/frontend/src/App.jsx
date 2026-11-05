import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Info, RotateCcw } from 'lucide-react'
import Sidebar from './components/Sidebar.jsx'
import Topbar from './components/Topbar.jsx'
import RunDialog from './components/RunDialog.jsx'
import ConnectAgentDialog from './components/ConnectAgentDialog.jsx'
import AgentDrawer from './components/AgentDrawer.jsx'
import TaskDrawer from './components/TaskDrawer.jsx'
import { EmptyState, Skeleton } from './components/ui.jsx'
import Overview from './pages/Overview.jsx'
import Runs from './pages/Runs.jsx'
import RunDetail from './pages/RunDetail.jsx'
import Agents from './pages/Agents.jsx'
import Suite from './pages/Suite.jsx'
import { api } from './api.js'

function LoadingPage() {
  return (
    <div className="page loading-page">
      <Skeleton height="20px" width="180px" />
      <Skeleton height="64px" width="72%" />
      <Skeleton height="24px" width="54%" />
      <div className="loading-grid">
        <Skeleton height="280px" />
        <Skeleton height="280px" />
      </div>
    </div>
  )
}

export default function App() {
  const [route, setRoute] = useState('overview')
  const [runId, setRunId] = useState(null)
  const [health, setHealth] = useState(null)
  const [stats, setStats] = useState(null)
  const [suite, setSuite] = useState(null)
  const [adapters, setAdapters] = useState([])
  const [leaderboard, setLeaderboard] = useState(null)
  const [failures, setFailures] = useState([])
  const [runs, setRuns] = useState([])
  const [agents, setAgents] = useState([])
  const [booting, setBooting] = useState(true)
  const [fatalError, setFatalError] = useState('')

  const [runDialogOpen, setRunDialogOpen] = useState(false)
  const [runDialogAgentIds, setRunDialogAgentIds] = useState(null)
  const [connectOpen, setConnectOpen] = useState(false)
  const [agentDrawerId, setAgentDrawerId] = useState(null)
  const [taskDrawerId, setTaskDrawerId] = useState(null)
  const [toast, setToast] = useState(null)
  const toastTimer = useRef(null)

  const [activeRun, setActiveRun] = useState(null)
  const [activeRunLoading, setActiveRunLoading] = useState(false)
  const [activeRunError, setActiveRunError] = useState('')

  const notify = useCallback((message, tone = 'info') => {
    setToast({ message, tone, id: Date.now() })
    if (toastTimer.current) window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToast(null), 4200)
  }, [])

  const loadDashboard = useCallback(async (initial = false) => {
    if (initial) setBooting(true)
    const settled = await Promise.allSettled([
      api.health(),
      api.stats(),
      api.suite(),
      api.adapters(),
      api.leaderboard(),
      api.failures(),
      api.runs(),
      api.agents(),
    ])
    const [h, s, su, ad, lb, f, rs, ag] = settled
    if (h.status === 'fulfilled') setHealth(h.value)
    if (s.status === 'fulfilled') setStats(s.value)
    if (su.status === 'fulfilled') setSuite(su.value)
    if (ad.status === 'fulfilled') setAdapters(ad.value.adapters || [])
    if (lb.status === 'fulfilled') setLeaderboard(lb.value)
    if (f.status === 'fulfilled') setFailures(f.value.failures || [])
    if (rs.status === 'fulfilled') setRuns(rs.value.runs || [])
    if (ag.status === 'fulfilled') setAgents(ag.value.agents || [])
    const failed = settled.filter((item) => item.status === 'rejected')
    if (failed.length === settled.length) {
      setFatalError(failed[0].reason?.message || 'The Criterion API is not reachable.')
    } else {
      setFatalError('')
    }
    if (initial) setBooting(false)
  }, [])

  useEffect(() => {
    loadDashboard(true)
  }, [loadDashboard])

  const fetchRun = useCallback(async (id, silent = false) => {
    if (!id) return
    if (!silent) setActiveRunLoading(true)
    setActiveRunError('')
    try {
      const data = await api.run(id)
      setActiveRun(data)
      if (data.status === 'complete') {
        api.leaderboard().then(setLeaderboard).catch(() => {})
        api.failures().then((value) => setFailures(value.failures || [])).catch(() => {})
        api.agents().then((value) => setAgents(value.agents || [])).catch(() => {})
        api.stats().then(setStats).catch(() => {})
      }
    } catch (err) {
      setActiveRunError(err.message || 'Could not load this run.')
    } finally {
      if (!silent) setActiveRunLoading(false)
    }
  }, [])

  useEffect(() => {
    if (route !== 'run' || !runId) return
    setActiveRun(null)
    fetchRun(runId)
  }, [route, runId, fetchRun])

  const anyRunning = runs.some((run) => run.status === 'running' || run.status === 'queued')
  useEffect(() => {
    if (!anyRunning) return undefined
    const timer = window.setInterval(async () => {
      try {
        const data = await api.runs()
        setRuns(data.runs || [])
        const stillRunning = (data.runs || []).some((run) => run.status === 'running' || run.status === 'queued')
        if (!stillRunning) loadDashboard(false)
      } catch {
        // The active run poll will surface connection errors.
      }
    }, 1400)
    return () => window.clearInterval(timer)
  }, [anyRunning, loadDashboard])

  const activeRunning = activeRun?.status === 'running' || activeRun?.status === 'queued'
  useEffect(() => {
    if (route !== 'run' || !runId || !activeRunning) return undefined
    const timer = window.setInterval(() => fetchRun(runId, true), 1000)
    return () => window.clearInterval(timer)
  }, [route, runId, activeRunning, fetchRun])

  const navigate = (next) => {
    setRoute(next)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const openRun = (id) => {
    if (!id) return
    setRunId(id)
    setRoute('run')
    window.scrollTo({ top: 0 })
  }

  const openRunDialog = (agentIds = null) => {
    setRunDialogAgentIds(agentIds)
    setRunDialogOpen(true)
  }

  const handleStarted = (run) => {
    setRuns((current) => [run, ...current])
    setRunId(run.id)
    setRoute('run')
    setActiveRun(null)
    notify(`Benchmark ${run.id.replace('run-', '')} started`, 'info')
  }

  const handleAgentCreated = async (agent) => {
    notify(`${agent.name} added. Run its first benchmark.`, 'success')
    await loadDashboard(false)
    setAgentDrawerId(agent.id)
  }

  const handleOpenAgentRun = (agentId) => {
    setAgentDrawerId(null)
    openRunDialog([agentId])
  }

  const handleOpenAgentFromRun = (agentId) => {
    if (!agentId) return
    setAgentDrawerId(agentId)
  }

  const selectedTask = suite?.tasks?.find((task) => task.id === taskDrawerId) || null
  const selectedTaskCategory = suite?.categories?.find((category) => category.id === selectedTask?.category) || null

  return (
    <div className="app-shell">
      <Sidebar
        route={route}
        setRoute={navigate}
        stats={stats}
        health={health}
        onRun={() => openRunDialog()}
      />
      <div className="main-shell">
        <Topbar
          route={route}
          health={health}
          runningCount={runs.filter((run) => run.status === 'running' || run.status === 'queued').length}
          onRun={() => openRunDialog()}
          onConnect={() => setConnectOpen(true)}
        />

        {fatalError && (
          <div className="api-error">
            <EmptyState
              icon={AlertTriangle}
              title="Criterion API is offline"
              body={`${fatalError} Start the backend on port 8012, then retry.`}
              action={<button type="button" className="btn btn-primary" onClick={() => loadDashboard(true)}><RotateCcw size={15} /> Retry connection</button>}
            />
          </div>
        )}

        {!fatalError && booting && <LoadingPage />}

        {!fatalError && !booting && route === 'overview' && (
          <Overview
            health={health}
            leaderboard={leaderboard}
            suite={suite}
            failures={failures}
            onRun={() => openRunDialog()}
            onOpenAgent={setAgentDrawerId}
            onOpenRun={openRun}
            onOpenSuite={() => navigate('tasks')}
          />
        )}

        {!fatalError && !booting && route === 'runs' && (
          <Runs
            runs={runs}
            onOpenRun={openRun}
            onRun={() => openRunDialog()}
          />
        )}

        {!fatalError && !booting && route === 'run' && (
          <RunDetail
            run={activeRun}
            runId={runId}
            loading={activeRunLoading}
            error={activeRunError}
            suite={suite}
            agents={agents}
            onBack={() => navigate('runs')}
            onRun={(agentIds) => openRunDialog(agentIds)}
            onOpenAgent={handleOpenAgentFromRun}
          />
        )}

        {!fatalError && !booting && route === 'agents' && (
          <Agents
            agents={agents}
            adapters={adapters}
            onConnect={() => setConnectOpen(true)}
            onOpenAgent={setAgentDrawerId}
            onRunAgent={(agentId) => openRunDialog([agentId])}
          />
        )}

        {!fatalError && !booting && route === 'tasks' && (
          <Suite
            suite={suite}
            onOpenTask={(task) => setTaskDrawerId(task.id)}
            onRun={() => openRunDialog()}
          />
        )}
      </div>

      <RunDialog
        open={runDialogOpen}
        onClose={() => setRunDialogOpen(false)}
        agents={agents}
        initialAgentIds={runDialogAgentIds}
        onStarted={handleStarted}
      />

      <ConnectAgentDialog
        open={connectOpen}
        onClose={() => setConnectOpen(false)}
        adapters={adapters}
        onCreated={handleAgentCreated}
      />

      <AgentDrawer
        open={!!agentDrawerId}
        agentId={agentDrawerId}
        suite={suite}
        onClose={() => setAgentDrawerId(null)}
        onRunAgent={handleOpenAgentRun}
        onOpenRun={(id) => { setAgentDrawerId(null); openRun(id) }}
      />

      <TaskDrawer
        open={!!taskDrawerId}
        task={selectedTask}
        category={selectedTaskCategory}
        onClose={() => setTaskDrawerId(null)}
      />

      {toast && (
        <div className={`toast toast-${toast.tone}`} role="status" key={toast.id}>
          {toast.tone === 'success' ? <CheckCircle2 size={16} /> : toast.tone === 'info' ? <Info size={16} /> : <AlertTriangle size={16} />}
          <span>{toast.message}</span>
          <button type="button" className="toast-close" onClick={() => setToast(null)} aria-label="Dismiss notification">×</button>
        </div>
      )}
    </div>
  )
}
