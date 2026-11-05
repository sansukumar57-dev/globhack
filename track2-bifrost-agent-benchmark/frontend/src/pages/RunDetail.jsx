import { useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  ChevronRight,
  Download,
  ListFilter,
  Play,
  RotateCcw,
} from 'lucide-react'
import Leaderboard from '../components/Leaderboard.jsx'
import ResultDrawer from '../components/ResultDrawer.jsx'
import {
  AgentMark,
  EmptyState,
  Eyebrow,
  ProgressBar,
  Skeleton,
  StatusPill,
} from '../components/ui.jsx'
import { FAILURE_LABELS } from '../lib/constants.js'
import {
  downloadJson,
  fmtCost,
  fmtDate,
  fmtMs,
  fmtPct,
  fmtScore,
  statusLabel,
} from '../lib/format.js'

const STATUS_OPTIONS = [
  { id: 'all', label: 'All statuses' },
  { id: 'passed', label: 'Passed' },
  { id: 'partial', label: 'Partial' },
  { id: 'failed', label: 'Failed' },
  { id: 'error', label: 'Adapter errors' },
]

export default function RunDetail({
  run,
  runId,
  loading,
  error,
  suite,
  agents = [],
  onBack,
  onRun,
  onOpenAgent,
}) {
  const [agentFilter, setAgentFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [visible, setVisible] = useState(20)
  const [selectedResult, setSelectedResult] = useState(null)

  useEffect(() => {
    setAgentFilter('all')
    setStatusFilter('all')
    setCategoryFilter('all')
    setVisible(20)
    setSelectedResult(null)
  }, [runId])

  useEffect(() => {
    setVisible(20)
  }, [agentFilter, statusFilter, categoryFilter])

  const taskMap = useMemo(() => Object.fromEntries((suite?.tasks || []).map((task) => [task.id, task])), [suite])
  const categoryMap = useMemo(() => Object.fromEntries((suite?.categories || []).map((category) => [category.id, category])), [suite])
  const agentLookup = useMemo(() => {
    const source = run?.agent_results?.length ? run.agent_results : agents
    return Object.fromEntries(source.map((agent) => [agent.agent_id || agent.id, agent]))
  }, [run, agents])
  const rankLookup = useMemo(() => Object.fromEntries((run?.agent_results || []).map((agent) => [agent.agent_id, agent.rank])), [run])
  const orderedAgents = useMemo(() => {
    const ids = run?.agent_results?.length
      ? run.agent_results.map((agent) => agent.agent_id)
      : (run?.agent_ids || [])
    return ids.map((id) => agentLookup[id]).filter(Boolean)
  }, [run, agentLookup])

  const filteredResults = useMemo(() => {
    if (!run?.task_results) return []
    return run.task_results
      .filter((result) => agentFilter === 'all' || result.agent_id === agentFilter)
      .filter((result) => statusFilter === 'all' || result.status === statusFilter)
      .filter((result) => {
        if (categoryFilter === 'all') return true
        return taskMap[result.task_id]?.category === categoryFilter
      })
      .sort((a, b) => {
        const taskA = taskMap[a.task_id]?.number || 0
        const taskB = taskMap[b.task_id]?.number || 0
        if (taskA !== taskB) return taskA - taskB
        const rankA = rankLookup[a.agent_id] || 99
        const rankB = rankLookup[b.agent_id] || 99
        if (rankA !== rankB) return rankA - rankB
        return a.trial - b.trial
      })
  }, [run, agentFilter, statusFilter, categoryFilter, taskMap, rankLookup])

  const shown = filteredResults.slice(0, visible)
  const summary = run?.summary
  const running = run?.status === 'running' || run?.status === 'queued'
  const selectedTask = selectedResult ? taskMap[selectedResult.task_id] : null
  const selectedAgent = selectedResult ? agentLookup[selectedResult.agent_id] : null

  if (loading && !run) {
    return (
      <div className="page">
        <Skeleton height="28px" width="120px" />
        <div className="detail-skeleton">
          <Skeleton height="80px" />
          <Skeleton height="300px" />
          <Skeleton height="400px" />
        </div>
      </div>
    )
  }

  if (error || !run) {
    return (
      <div className="page">
        <button type="button" className="back-link" onClick={onBack}><ArrowLeft size={15} /> Back to runs</button>
        <div className="panel"><EmptyState icon={ListFilter} title="Run not found" body={error || 'This run does not exist in the current workspace.'} /></div>
      </div>
    )
  }

  const expectedExecutions = (run.agent_ids?.length || 0) * (suite?.task_count || 18) * (run.trials || 1)
  const modes = new Set((run.agent_results || []).map((agent) => agent.mode).filter(Boolean))
  const runModeLabel = modes.size > 1 ? 'Mixed sandbox and live results' : modes.has('live') ? 'Live adapter results' : 'Sandbox reference results'

  return (
    <div className="page run-detail-page">
      <button type="button" className="back-link" onClick={onBack}><ArrowLeft size={15} /> Runs</button>

      <header className="run-detail-head">
        <div>
          <Eyebrow>Run · {run.id}</Eyebrow>
          <div className="run-detail-title-row">
            <h1>Commerce support <em>v3</em></h1>
            <StatusPill status={run.status} />
          </div>
          <p className="page-lede">
            {run.trials} trial{run.trials === 1 ? '' : 's'} · {run.agent_ids?.length || 0} agents · {summary?.total_executions || Math.round((run.progress || 0) * expectedExecutions)} task runs
            <span className="dot-sep">·</span>
            {fmtDate(run.created_at)}
          </p>
        </div>
        <div className="run-detail-actions">
          <button type="button" className="btn btn-secondary" onClick={() => downloadJson(`${run.id}.json`, run)}>
            <Download size={15} /> Export JSON
          </button>
          <button type="button" className="btn btn-primary" onClick={() => onRun(run.agent_ids)}>
            <RotateCcw size={15} /> Re-run
          </button>
        </div>
      </header>

      {running && (
        <div className="running-banner">
          <div className="running-banner-copy">
            <span className="live-dot" />
            <strong>Benchmark running</strong>
            <span>{Math.round((run.progress || 0) * 100)}% complete · {run.task_results?.length || 0} task runs recorded</span>
          </div>
          <ProgressBar value={(run.progress || 0) * 100} tone="warn" height={6} />
        </div>
      )}

      <section className="detail-kpis" aria-label="Run summary">
        <div><span>Best agent</span><strong>{summary?.best_agent || '—'}</strong><small>{summary ? `${fmtScore(summary.best_score)} composite` : 'in progress'}</small></div>
        <div><span>Pass rate</span><strong>{fmtPct(summary?.pass_rate)}</strong><small>{summary?.total_executions || 0} task runs</small></div>
        <div><span>Avg score</span><strong>{fmtScore(summary?.avg_score)}</strong><small>across agents</small></div>
        <div><span>Duration</span><strong>{summary ? fmtMs(summary.duration_ms) : '—'}</strong><small>wall clock</small></div>
        <div><span>Total cost</span><strong>{summary ? fmtCost(summary.total_cost_usd) : '—'}</strong><small>sandbox estimate</small></div>
      </section>

      {!!run.agent_results?.length && (
        <section className="panel detail-leaderboard">
          <div className="panel-heading-row">
            <div>
              <h2>Leaderboard</h2>
              <p>Same suite. Same checks. Ranked by composite score.</p>
            </div>
            <span className="mono-label">{run.trials} trials · {summary?.total_executions} runs</span>
          </div>
          <Leaderboard agents={run.agent_results} onSelectAgent={onOpenAgent} dense />
        </section>
      )}

      <div className="run-matrix-grid">
        <section className="panel matrix-panel">
          <div className="panel-heading-row">
            <div>
              <h2>Outcome matrix</h2>
              <p>Trial 1 · every task, every agent. Click a cell for the trace.</p>
            </div>
            <div className="legend">
              <span><i className="legend-dot legend-passed" />Passed</span>
              <span><i className="legend-dot legend-partial" />Partial</span>
              <span><i className="legend-dot legend-failed" />Failed</span>
            </div>
          </div>
          <div className="matrix-scroll">
            <div className="matrix" style={{ '--task-count': suite?.tasks?.length || 18 }}>
              <div className="matrix-corner" />
              {(suite?.tasks || []).map((task) => (
                <div className="matrix-col-label" key={task.id} title={task.title}>{String(task.number).padStart(2, '0')}</div>
              ))}
              {orderedAgents.map((agent) => (
                <MatrixRow
                  key={agent.agent_id || agent.id}
                  agent={agent}
                  tasks={suite?.tasks || []}
                  results={run.task_results || []}
                  onSelect={setSelectedResult}
                />
              ))}
            </div>
          </div>
        </section>

        <section className="panel run-signals-panel">
          <div className="panel-heading-row">
            <div>
              <h2>Failure signatures</h2>
              <p>Where the suite broke.</p>
            </div>
          </div>
          <div className="failure-signal-list">
            {(summary?.top_signatures || []).length === 0 && <p className="muted-copy">{running ? 'Collecting results…' : 'No failures. Every check passed.'}</p>}
            {(summary?.top_signatures || []).map((failure) => (
              <div className="failure-signal" key={failure.id}>
                <div className="failure-signal-head">
                  <span className="failure-signal-name"><span className="failure-dot" style={{ background: failure.color }} />{failure.label}</span>
                  <span className="failure-signal-count">{failure.count}</span>
                </div>
                <p className="failure-signal-desc">{failure.description}</p>
              </div>
            ))}
          </div>
          {summary?.top_signatures?.[0] && (
            <button
              type="button"
              className="text-button side-link"
              onClick={() => {
                const signature = summary.top_signatures[0].id
                const result = run.task_results.find((item) => item.failure_signature === signature)
                if (result) setSelectedResult(result)
              }}
            >
              Open a failing trace <ArrowRight size={13} />
            </button>
          )}
        </section>
      </div>

      <section className="panel task-results-panel">
        <div className="panel-heading-row task-results-head">
          <div>
            <h2>Task results</h2>
            <p>{filteredResults.length} task runs in view · click a row for checks and the trace.</p>
          </div>
          <div className="result-filters">
            <label className="select-wrap">
              <span className="sr-only">Filter by agent</span>
              <select value={agentFilter} onChange={(event) => setAgentFilter(event.target.value)}>
                <option value="all">All agents</option>
                {orderedAgents.map((agent) => <option value={agent.agent_id || agent.id} key={agent.agent_id || agent.id}>{agent.name}</option>)}
              </select>
            </label>
            <label className="select-wrap">
              <span className="sr-only">Filter by status</span>
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                {STATUS_OPTIONS.map((option) => <option value={option.id} key={option.id}>{option.label}</option>)}
              </select>
            </label>
            <label className="select-wrap">
              <span className="sr-only">Filter by category</span>
              <select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
                <option value="all">All categories</option>
                {(suite?.categories || []).map((category) => <option value={category.id} key={category.id}>{category.name}</option>)}
              </select>
            </label>
          </div>
        </div>

        <div className="table-wrap">
          <table className="data-table result-table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Agent</th>
                <th>Trial</th>
                <th>Status</th>
                <th>Score</th>
                <th>Latency</th>
                <th>Failure</th>
                <th><span className="sr-only">Open</span></th>
              </tr>
            </thead>
            <tbody>
              {shown.map((result) => {
                const task = taskMap[result.task_id]
                const agent = agentLookup[result.agent_id]
                const failure = result.failure_signature ? FAILURE_LABELS[result.failure_signature] : null
                return (
                  <tr key={result.id} className="result-row" onClick={() => setSelectedResult(result)}>
                    <td>
                      <div className="task-result-cell">
                        <span className="task-number">{String(task?.number || '').padStart(2, '0')}</span>
                        <div>
                          <span className="task-result-title">{task?.title || result.task_id}</span>
                          <span className="task-result-sub">{categoryMap[task?.category]?.name}</span>
                        </div>
                      </div>
                    </td>
                    <td>
                      <div className="agent-inline">
                        {agent && <AgentMark agent={agent} size="xs" />}
                        <span>{agent?.name || result.agent_id}</span>
                      </div>
                    </td>
                    <td><span className="mono-value">T{result.trial}</span></td>
                    <td><StatusPill status={result.status} label={statusLabel(result.status)} /></td>
                    <td><span className="score-inline">{fmtScore(result.score)}</span></td>
                    <td><span className="mono-value">{fmtMs(result.latency_ms)}</span></td>
                    <td>
                      {failure ? <span className="failure-tag" style={{ '--failure-color': failure.color }}>{failure.label}</span> : <span className="muted-copy">—</span>}
                    </td>
                    <td><button type="button" className="icon-button row-open" aria-label="Open trace" onClick={(event) => { event.stopPropagation(); setSelectedResult(result) }}><ChevronRight size={16} /></button></td>
                  </tr>
                )
              })}
              {shown.length === 0 && (
                <tr><td colSpan={8}><p className="table-empty">No task results match these filters.</p></td></tr>
              )}
            </tbody>
          </table>
        </div>

        {visible < filteredResults.length && (
          <div className="load-more-row">
            <span className="mono-label">Showing {shown.length} of {filteredResults.length}</span>
            <button type="button" className="btn btn-secondary" onClick={() => setVisible((count) => count + 20)}>
              Load more <ChevronRight size={14} />
            </button>
          </div>
        )}
      </section>

      <p className="page-footnote">
        <Play size={12} /> {runModeLabel} · generated {fmtDate(run.completed_at || run.created_at)}
      </p>

      <ResultDrawer
        open={!!selectedResult}
        result={selectedResult}
        task={selectedTask}
        agent={selectedAgent}
        onClose={() => setSelectedResult(null)}
        onOpenAgent={(agentId) => {
          setSelectedResult(null)
          onOpenAgent?.(agentId)
        }}
      />
    </div>
  )
}

function MatrixRow({ agent, tasks, results, onSelect }) {
  const byTask = Object.fromEntries(
    results
      .filter((result) => result.agent_id === (agent.agent_id || agent.id) && result.trial === 1)
      .map((result) => [result.task_id, result]),
  )
  return (
    <>
      <div className="matrix-row-label">
        <AgentMark agent={agent} size="xs" />
        <span>{agent.name}</span>
      </div>
      {tasks.map((task) => {
        const result = byTask[task.id]
        return (
          <button
            type="button"
            key={task.id}
            className={`matrix-cell matrix-${result?.status || 'empty'}`}
            title={result ? `${task.title} · ${statusLabel(result.status)}` : `${task.title} · pending`}
            onClick={() => result && onSelect(result)}
            disabled={!result}
            aria-label={result ? `Open ${task.title}: ${statusLabel(result.status)}` : `${task.title}: pending`}
          />
        )
      })}
    </>
  )
}
