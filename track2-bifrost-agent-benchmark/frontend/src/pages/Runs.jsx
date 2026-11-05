import { useMemo, useState } from 'react'
import { ArrowRight, ListChecks, Play } from 'lucide-react'
import { AgentMark, EmptyState, Eyebrow, ProgressBar, StatusPill } from '../components/ui.jsx'
import { fmtDate, fmtMs, fmtPct, fmtScore, timeAgo } from '../lib/format.js'

const FILTERS = [
  { id: 'all', label: 'All runs' },
  { id: 'complete', label: 'Complete' },
  { id: 'running', label: 'Running' },
]

export default function Runs({ runs = [], onOpenRun, onRun }) {
  const [filter, setFilter] = useState('all')
  const filtered = useMemo(() => runs.filter((run) => {
    if (filter === 'all') return true
    if (filter === 'running') return run.status === 'running' || run.status === 'queued'
    return run.status === 'complete'
  }), [runs, filter])

  return (
    <div className="page runs-page">
      <header className="page-head">
        <div>
          <Eyebrow>Run ledger</Eyebrow>
          <h1>Every benchmark,<br /><em>on the record.</em></h1>
          <p className="page-lede">
            Runs are reproducible: the same suite, checks and policy for every agent. Open a run to inspect the traces.
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={onRun}>
          <Play size={15} /> Run benchmark
        </button>
      </header>

      <div className="filter-row">
        <div className="filter-tabs" role="tablist" aria-label="Filter runs">
          {FILTERS.map((item) => (
            <button
              type="button"
              key={item.id}
              role="tab"
              aria-selected={filter === item.id}
              className={`filter-tab${filter === item.id ? ' active' : ''}`}
              onClick={() => setFilter(item.id)}
            >
              {item.label}
              {item.id === 'running' && runs.some((run) => run.status === 'running') && <span className="filter-live-dot" />}
            </button>
          ))}
        </div>
        <span className="filter-count">{filtered.length} run{filtered.length === 1 ? '' : 's'}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="panel">
          <EmptyState
            icon={ListChecks}
            title={filter === 'running' ? 'No benchmarks running' : 'No runs in this view'}
            body={filter === 'running' ? 'Start a benchmark to see live progress here.' : 'Change the filter or run the suite to create a new record.'}
            action={<button type="button" className="btn btn-secondary" onClick={onRun}>Run benchmark</button>}
          />
        </div>
      ) : (
        <div className="panel run-ledger-panel">
          <div className="table-wrap">
            <table className="data-table run-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Status</th>
                  <th>Agents</th>
                  <th>Trials</th>
                  <th>Pass rate</th>
                  <th>Best agent</th>
                  <th className="col-latency">Duration</th>
                  <th>Started</th>
                  <th><span className="sr-only">Open</span></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((run) => {
                  const running = run.status === 'running' || run.status === 'queued'
                  const summary = run.summary
                  const best = run.agent_results?.[0]
                  return (
                    <tr key={run.id} className="run-row" onClick={() => onOpenRun(run.id)}>
                      <td>
                        <div className="run-id-cell">
                          <span className="run-id">{run.id}</span>
                          <span className="run-suite">Commerce support v3</span>
                        </div>
                      </td>
                      <td>
                        <div className="run-status-cell">
                          <StatusPill status={run.status} />
                          {running && (
                            <span className="run-progress-inline">
                              <ProgressBar value={(run.progress || 0) * 100} tone="warn" height={3} />
                              {Math.round((run.progress || 0) * 100)}%
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        <div className="agent-stack">
                          {(run.agent_results || []).slice(0, 4).map((agent) => (
                            <AgentMark key={agent.agent_id} agent={agent} size="xs" />
                          ))}
                          {!run.agent_results?.length && <span className="muted-copy">{run.agent_ids?.length || 0} selected</span>}
                        </div>
                      </td>
                      <td><span className="mono-value">{run.trials}</span></td>
                      <td>
                        {running ? (
                          <span className="muted-copy">in progress</span>
                        ) : (
                          <div className="run-pass-cell">
                            <span className="metric-inline">{fmtPct(summary?.pass_rate)}</span>
                            <span className="metric-sub">{summary?.total_executions || 0} task runs</span>
                          </div>
                        )}
                      </td>
                      <td>
                        {best ? (
                          <div className="best-cell">
                            <AgentMark agent={best} size="xs" />
                            <span>{best.name}</span>
                            <span className="best-score">{fmtScore(best.score)}</span>
                          </div>
                        ) : <span className="muted-copy">—</span>}
                      </td>
                      <td className="col-latency"><span className="mono-value">{summary ? fmtMs(summary.duration_ms) : '—'}</span></td>
                      <td>
                        <div className="time-cell">
                          <span>{timeAgo(run.created_at)}</span>
                          <small>{fmtDate(run.created_at)}</small>
                        </div>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="icon-button row-open"
                          aria-label={`Open ${run.id}`}
                          onClick={(event) => { event.stopPropagation(); onOpenRun(run.id) }}
                        >
                          <ArrowRight size={16} />
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
