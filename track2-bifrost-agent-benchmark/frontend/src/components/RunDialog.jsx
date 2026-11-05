import { useEffect, useMemo, useState } from 'react'
import { Check, Play, Users } from 'lucide-react'
import { Modal } from './Dialog.jsx'
import { AgentMark, EmptyState } from './ui.jsx'
import { fmtScore } from '../lib/format.js'
import { api } from '../api.js'

const TRIALS = [
  { value: 1, label: '1 trial', note: 'Fast signal' },
  { value: 2, label: '2 trials', note: 'Recommended' },
  { value: 3, label: '3 trials', note: 'Consistency check' },
]

export default function RunDialog({ open, onClose, agents = [], initialAgentIds = null, onStarted }) {
  const readyAgents = useMemo(() => agents.filter((agent) => agent.status !== 'archived'), [agents])
  const [selected, setSelected] = useState([])
  const [trials, setTrials] = useState(2)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    const defaults = initialAgentIds?.length
      ? readyAgents.filter((agent) => initialAgentIds.includes(agent.id)).map((agent) => agent.id)
      : readyAgents.map((agent) => agent.id)
    setSelected(defaults)
    setTrials(2)
    setSubmitting(false)
    setError('')
  }, [open, initialAgentIds, readyAgents])

  const toggle = (id) => {
    setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id])
  }

  const allSelected = readyAgents.length > 0 && selected.length === readyAgents.length
  const taskRuns = selected.length * 18 * trials

  const submit = async () => {
    if (!selected.length) {
      setError('Select at least one agent.')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const run = await api.startRun({ agent_ids: selected, trials })
      onStarted?.(run)
      onClose?.()
    } catch (err) {
      setError(err.message || 'Could not start the benchmark.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      eyebrow="New benchmark"
      title="Run the shared suite"
      width="min(680px, calc(100vw - 32px))"
      footer={(
        <>
          <span className="modal-foot-note">
            <strong>{taskRuns}</strong> task runs
            {selected.length > 0 && <span> · {selected.length} agents × 18 tasks × {trials} trial{trials === 1 ? '' : 's'}</span>}
          </span>
          <div className="modal-foot-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={submitting}>Cancel</button>
            <button type="button" className="btn btn-primary" onClick={submit} disabled={submitting || !selected.length}>
              <Play size={15} />
              {submitting ? 'Starting…' : 'Start benchmark'}
            </button>
          </div>
        </>
      )}
    >
      {readyAgents.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No agents to run"
          body="Connect an agent or add a sandbox reference profile before starting a benchmark."
        />
      ) : (
        <>
          <div className="dialog-section">
            <div className="dialog-section-head">
              <div>
                <h3>Agents</h3>
                <p>The same tasks, checks and policy for every agent.</p>
              </div>
              <button
                type="button"
                className="text-button"
                onClick={() => setSelected(allSelected ? [] : readyAgents.map((agent) => agent.id))}
              >
                {allSelected ? 'Clear all' : 'Select all'}
              </button>
            </div>
            <div className="agent-picker">
              {readyAgents.map((agent) => {
                const active = selected.includes(agent.id)
                return (
                  <button
                    type="button"
                    key={agent.id}
                    className={`agent-pick${active ? ' selected' : ''}`}
                    onClick={() => toggle(agent.id)}
                    aria-pressed={active}
                  >
                    <span className={`picker-check${active ? ' checked' : ''}`}>{active && <Check size={12} strokeWidth={3} />}</span>
                    <AgentMark agent={agent} size="sm" />
                    <span className="agent-pick-copy">
                      <span className="agent-pick-name">{agent.name}</span>
                      <span className="agent-pick-sub">{agent.adapter}</span>
                    </span>
                    <span className="agent-pick-score">
                      {agent.score === null ? <span className="untested">untested</span> : fmtScore(agent.score)}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>

          <div className="dialog-section">
            <div className="dialog-section-head">
              <div>
                <h3>Trials</h3>
                <p>Repeat every task to measure run-to-run consistency.</p>
              </div>
            </div>
            <div className="segmented" role="radiogroup" aria-label="Trials">
              {TRIALS.map((option) => (
                <button
                  type="button"
                  key={option.value}
                  role="radio"
                  aria-checked={trials === option.value}
                  className={`segment${trials === option.value ? ' active' : ''}`}
                  onClick={() => setTrials(option.value)}
                >
                  <span>{option.label}</span>
                  <small>{option.note}</small>
                </button>
              ))}
            </div>
          </div>

          <div className="run-summary-box">
            <div>
              <span className="run-summary-label">Suite</span>
              <strong>Commerce support v3</strong>
            </div>
            <div>
              <span className="run-summary-label">Scoring</span>
              <strong>Deterministic rubric</strong>
            </div>
            <div>
              <span className="run-summary-label">Environment</span>
              <strong>Sandbox reference</strong>
            </div>
          </div>

          {error && <p className="form-error" role="alert">{error}</p>}
        </>
      )}
    </Modal>
  )
}
