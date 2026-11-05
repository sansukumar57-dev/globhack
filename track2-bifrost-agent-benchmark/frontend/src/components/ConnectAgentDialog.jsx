import { useEffect, useState } from 'react'
import { ArrowUpRight, Code2, Plus, Radio, Terminal } from 'lucide-react'
import { Modal } from './Dialog.jsx'
import { api } from '../api.js'

const SANDBOX_PROFILES = [
  { id: 'balanced', label: 'Balanced', note: 'Middle-of-the-road agent' },
  { id: 'careful', label: 'Careful', note: 'Policy-first, slower' },
  { id: 'fast', label: 'Fast', note: 'Low latency, more shortcuts' },
  { id: 'budget', label: 'Budget', note: 'Cheapest loop' },
  { id: 'frontier', label: 'Frontier', note: 'Largest context, highest cost' },
]

const CONTRACT = `POST {your_endpoint}
{
  "task": { "id": "...", "prompt": "...", "context": "..." },
  "trial": 1,
  "expected_checks": [{ "id": "policy", "kind": "policy" }]
}

200 OK
{
  "answer": "I've refunded the duplicate charge...",
  "checks": { "policy": true, "outcome": true },
  "tool_calls": [{ "tool": "issue_refund", "status": "ok" }],
  "tokens": 1840,
  "cost_usd": 0.014,
  "latency_ms": 2180
}`

export default function ConnectAgentDialog({ open, onClose, adapters = [], onCreated }) {
  const [form, setForm] = useState({
    name: '',
    operator: '',
    adapter: 'bifrost',
    model: '',
    endpoint: '',
    description: '',
    mode: 'sandbox',
    sandbox_profile: 'balanced',
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setForm({
      name: '',
      operator: '',
      adapter: 'bifrost',
      model: '',
      endpoint: '',
      description: '',
      mode: 'sandbox',
      sandbox_profile: 'balanced',
    })
    setSubmitting(false)
    setError('')
  }, [open])

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }))

  const submit = async (event) => {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const agent = await api.addAgent(form)
      onCreated?.(agent)
      onClose?.()
    } catch (err) {
      setError(err.message || 'Could not add the agent.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      eyebrow="Agent registry"
      title="Connect an agent"
      width="min(640px, calc(100vw - 32px))"
      footer={(
        <>
          <span className="modal-foot-note">
            <Radio size={13} /> Sandbox mode is reproducible. Live mode calls your endpoint.
          </span>
          <div className="modal-foot-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={submitting}>Cancel</button>
            <button type="submit" form="connect-agent-form" className="btn btn-primary" disabled={submitting}>
              <Plus size={15} />
              {submitting ? 'Adding…' : 'Add agent'}
            </button>
          </div>
        </>
      )}
    >
      <form id="connect-agent-form" className="form-stack" onSubmit={submit}>
        <div className="form-grid">
          <label className="field">
            <span>Agent name</span>
            <input
              value={form.name}
              onChange={(event) => update('name', event.target.value)}
              placeholder="e.g. Atlas Support"
              required
              minLength={2}
              maxLength={48}
            />
          </label>
          <label className="field">
            <span>Operator</span>
            <input
              value={form.operator}
              onChange={(event) => update('operator', event.target.value)}
              placeholder="e.g. Platform team"
              maxLength={48}
            />
          </label>
          <label className="field">
            <span>Adapter</span>
            <select value={form.adapter} onChange={(event) => update('adapter', event.target.value)}>
              {adapters.length === 0 && <option value="bifrost">Bifrost gateway</option>}
              {adapters.map((adapter) => (
                <option value={adapter.id} key={adapter.id}>{adapter.name} · {adapter.kind}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Model or stack</span>
            <input
              value={form.model}
              onChange={(event) => update('model', event.target.value)}
              placeholder="e.g. gpt-4.1 / custom graph"
              maxLength={48}
            />
          </label>
        </div>

        <div className="field">
          <span>Run mode</span>
          <div className="segmented segmented-small" role="radiogroup" aria-label="Run mode">
            <button
              type="button"
              role="radio"
              aria-checked={form.mode === 'sandbox'}
              className={`segment${form.mode === 'sandbox' ? ' active' : ''}`}
              onClick={() => update('mode', 'sandbox')}
            >
              <span>Sandbox</span>
              <small>Reference profile</small>
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={form.mode === 'live'}
              className={`segment${form.mode === 'live' ? ' active' : ''}`}
              onClick={() => update('mode', 'live')}
            >
              <span>Live endpoint</span>
              <small>HTTP adapter</small>
            </button>
          </div>
        </div>

        {form.mode === 'sandbox' ? (
          <label className="field">
            <span>Sandbox profile</span>
            <select value={form.sandbox_profile} onChange={(event) => update('sandbox_profile', event.target.value)}>
              {SANDBOX_PROFILES.map((profile) => (
                <option value={profile.id} key={profile.id}>{profile.label} — {profile.note}</option>
              ))}
            </select>
            <small className="field-hint">A deterministic reference behavior for demoing the platform before your endpoint is wired up.</small>
          </label>
        ) : (
          <label className="field">
            <span>Endpoint</span>
            <input
              type="url"
              value={form.endpoint}
              onChange={(event) => update('endpoint', event.target.value)}
              placeholder="https://your-agent.example.com/run"
              required
            />
            <small className="field-hint">Criterion sends one task per request and expects the adapter contract below.</small>
          </label>
        )}

        <label className="field">
          <span>Description</span>
          <textarea
            value={form.description}
            onChange={(event) => update('description', event.target.value)}
            placeholder="What is this agent built to do?"
            rows={2}
            maxLength={180}
          />
        </label>

        <details className="contract">
          <summary><Terminal size={14} /> Adapter contract <span className="contract-arrow">→</span></summary>
          <pre>{CONTRACT}</pre>
          <p><Code2 size={13} /> Return <code>checks</code> for exact scoring. If omitted, Criterion falls back to a similarity rubric.</p>
        </details>

        {error && <p className="form-error" role="alert">{error}</p>}
        <p className="form-disclaimer">
          <ArrowUpRight size={13} /> Agents are isolated. Criterion never exposes your endpoint to other workspace members in this demo.
        </p>
      </form>
    </Modal>
  )
}
