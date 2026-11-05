import { useEffect, useState } from 'react'
import { ArrowRight, ExternalLink, Play, ShieldAlert } from 'lucide-react'
import { Drawer } from './Dialog.jsx'
import {
  AgentMark,
  Delta,
  EmptyState,
  ProgressBar,
  ScoreRing,
  Skeleton,
  Sparkline,
  StatusPill,
} from './ui.jsx'
import { api } from '../api.js'
import { fmtCost, fmtMs, fmtPct, fmtScore, scoreTone, statusLabel } from '../lib/format.js'

const METRICS = [
  { key: 'task_success', label: 'Task success', tone: 'accent' },
  { key: 'policy', label: 'Policy', tone: 'ink' },
  { key: 'tool_accuracy', label: 'Tool accuracy', tone: 'ink' },
  { key: 'consistency', label: 'Consistency', tone: 'ink' },
  { key: 'safety', label: 'Safety', tone: 'ink' },
  { key: 'efficiency', label: 'Efficiency', tone: 'ink' },
]

export default function AgentDrawer({ open, agentId, suite, onClose, onRunAgent, onOpenRun }) {
  const [agent, setAgent] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || !agentId) return undefined
    let cancelled = false
    setLoading(true)
    setError('')
    setAgent(null)
    api.agent(agentId)
      .then((data) => { if (!cancelled) setAgent(data) })
      .catch((err) => { if (!cancelled) setError(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [open, agentId])

  const taskMap = Object.fromEntries((suite?.tasks || []).map((task) => [task.id, task]))
  const latest = agent?.latest_result
  const tone = scoreTone(agent?.score)

  return (
    <Drawer
      open={open}
      onClose={onClose}
      eyebrow="Agent profile"
      title={agent?.name || 'Agent'}
      subtitle={agent ? `${agent.operator} · ${agent.adapter}` : 'Loading agent'}
      footer={agent ? (
        <>
          <button type="button" className="btn btn-secondary" onClick={() => onOpenRun?.(agent.history?.[agent.history.length - 1]?.run_id)} disabled={!agent.history?.length}>
            <ExternalLink size={15} /> Open latest run
          </button>
          <button type="button" className="btn btn-primary" onClick={() => onRunAgent?.(agent.id)}>
            <Play size={15} /> Run this agent
          </button>
        </>
      ) : null}
    >
      {loading && (
        <div className="drawer-loading">
          <Skeleton height="120px" />
          <Skeleton height="200px" />
          <Skeleton height="180px" />
        </div>
      )}
      {error && <EmptyState icon={ShieldAlert} title="Could not load agent" body={error} />}
      {agent && !loading && (
        <>
          <div className="agent-hero">
            <div className="agent-hero-main">
              <AgentMark agent={agent} size="lg" />
              <div>
                <div className="agent-hero-title">
                  <span className={`mode-tag mode-${agent.mode}`}>{agent.mode}</span>
                  <span className="mono-label">{agent.mode === 'live' ? 'connected agent' : 'reference agent'}</span>
                </div>
                <p>{agent.description}</p>
                <div className="agent-hero-meta">
                  <span>{agent.model}</span>
                  <span>·</span>
                  <span>{agent.endpoint || 'sandbox reference'}</span>
                </div>
              </div>
            </div>
            <div className="agent-hero-score">
              <ScoreRing value={agent.score || 0} size={104} label="composite" color={tone === 'good' ? '#2F7D5B' : tone === 'ok' ? '#B7791F' : '#C23B2A'} />
              <div className="agent-hero-score-meta">
                <span className={`score-tone score-${tone}`}>{fmtScore(agent.score)}</span>
                <Delta value={agent.delta} />
                <span className="muted-copy">across {agent.run_count} run{agent.run_count === 1 ? '' : 's'}</span>
              </div>
            </div>
          </div>

          <div className="drawer-section">
            <div className="drawer-section-head">
              <h3>Score history</h3>
              <span className="mono-label">last {agent.history?.length || 0} runs</span>
            </div>
            <div className="history-strip">
              <Sparkline points={agent.history || []} color={agent.color} width={260} height={48} />
              <div className="history-values">
                {(agent.history || []).map((point) => (
                  <span key={point.run_id}>{fmtScore(point.score)}</span>
                ))}
              </div>
            </div>
          </div>

          <div className="drawer-section">
            <div className="drawer-section-head">
              <h3>Latest scorecard</h3>
              <span className="mono-label">rank #{latest?.rank || '—'}</span>
            </div>
            <div className="metric-grid">
              {METRICS.map((metric) => (
                <div className="metric-tile" key={metric.key}>
                  <span className="metric-tile-label">{metric.label}</span>
                  <span className="metric-tile-value">{fmtPct(latest?.[metric.key])}</span>
                  <ProgressBar value={latest?.[metric.key] || 0} tone={metric.tone} height={4} />
                </div>
              ))}
            </div>
            <div className="metric-foot">
              <span><span className="mono-label">p95</span> {fmtMs(latest?.p95_latency_ms)}</span>
              <span><span className="mono-label">cost / task</span> {fmtCost(latest?.cost_per_task)}</span>
              <span><span className="mono-label">tokens / task</span> {latest?.tokens_per_task?.toLocaleString() || '—'}</span>
            </div>
          </div>

          <div className="drawer-section">
            <div className="drawer-section-head">
              <h3>Category performance</h3>
              <span className="mono-label">task success</span>
            </div>
            <div className="category-list">
              {(latest?.category_scores || []).map((category) => (
                <div className="category-row" key={category.id}>
                  <span className="category-name">{category.name}</span>
                  <ProgressBar value={category.success} tone="accent" height={5} />
                  <span className="category-value">{fmtPct(category.success, 0)}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="drawer-section">
            <div className="drawer-section-head">
              <h3>Failure signatures</h3>
              <span className="mono-label">latest run</span>
            </div>
            {agent.failure_modes?.length ? (
              <div className="failure-list">
                {agent.failure_modes.map((mode) => (
                  <div className="failure-row" key={mode.id}>
                    <span className="failure-dot" style={{ background: mode.color }} />
                    <div>
                      <strong>{mode.label}</strong>
                      <p>{mode.description}</p>
                    </div>
                    <span className="failure-count">{mode.count}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted-copy">No failures in the latest run.</p>
            )}
          </div>

          <div className="drawer-section">
            <div className="drawer-section-head">
              <h3>Recent tasks</h3>
              <span className="mono-label">trial 1</span>
            </div>
            <div className="recent-task-list">
              {(agent.recent_tasks || []).slice(0, 8).map((result) => {
                const task = taskMap[result.task_id]
                return (
                  <div className="recent-task" key={result.id}>
                    <span className="recent-task-number">{String(task?.number || '').padStart(2, '0')}</span>
                    <div className="recent-task-copy">
                      <span>{task?.title || result.task_id}</span>
                      <small>{task?.category} · {fmtMs(result.latency_ms)}</small>
                    </div>
                    <StatusPill status={result.status} label={statusLabel(result.status)} />
                  </div>
                )
              })}
            </div>
            {agent.history?.length > 0 && (
              <button type="button" className="text-button drawer-link" onClick={() => onOpenRun?.(agent.history?.[agent.history.length - 1]?.run_id)}>
                View all task results <ArrowRight size={13} />
              </button>
            )}
          </div>

          <div className="drawer-section">
            <div className="drawer-section-head"><h3>Profile</h3></div>
            <div className="profile-columns">
              <div>
                <span className="mono-label">Strengths</span>
                <ul className="plain-list">
                  {(agent.strengths || []).map((item) => <li key={item}>{item}</li>)}
                </ul>
              </div>
              <div>
                <span className="mono-label">Watchouts</span>
                <ul className="plain-list">
                  {(agent.watchouts || []).map((item) => <li key={item}>{item}</li>)}
                </ul>
              </div>
            </div>
          </div>
        </>
      )}
    </Drawer>
  )
}
