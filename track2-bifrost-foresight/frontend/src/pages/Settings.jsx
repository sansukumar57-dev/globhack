import { useCallback, useEffect, useState } from 'react'
import { BellRing, CheckCircle2, Inbox, Loader2, Save, Trash2 } from 'lucide-react'
import { api, timeAgo, toast } from '../api'
import { EmptyState, Loading, PageHeader } from '../components/ui'

const CURL = `curl "$FORESIGHT/v1/chat/completions" \\
  -H "Authorization: Bearer sk-bf-foresight-growth-0001" \\
  -H "Content-Type: application/json" \\
  -d '{"model": "acme-llm/gpt-4o", "messages": [{"role": "user", "content": "hello"}]}'`

function prettyBody(body) {
  try {
    return JSON.stringify(JSON.parse(body), null, 2)
  } catch {
    return body
  }
}

function CodeBlock({ label, code, onCopy }) {
  return (
    <div className="code-block">
      <div className="code-head">
        <span>{label}</span>
        <span className="spacer" />
        <button type="button" className="code-copy" onClick={() => onCopy(code)}>
          Copy
        </button>
      </div>
      <pre>{code}</pre>
    </div>
  )
}

export default function Settings({ refreshKey }) {
  const [settings, setSettings] = useState({})
  const [sink, setSink] = useState([])
  const [loading, setLoading] = useState(true)
  const [testResult, setTestResult] = useState(null)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)

  const load = useCallback(async () => {
    try {
      const [s, k] = await Promise.all([api.getSettings(), api.sink()])
      setSettings(s.settings)
      setSink(k.sink)
    } catch {
      /* the top bar surfaces connectivity */
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load, refreshKey])

  const set = (key) => (e) => setSettings({ ...settings, [key]: e.target.value })

  const save = async () => {
    setSaving(true)
    try {
      await api.putSettings(settings)
      toast('Settings saved')
      await load()
    } catch (e) {
      toast(`Save failed: ${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const sendTest = async () => {
    setTestResult(null)
    setTesting(true)
    try {
      const res = await api.testWebhook()
      setTestResult(res)
      toast(res.delivered ? 'Test webhook delivered to the sink' : 'Test webhook failed — check the URL')
      await load()
    } catch (e) {
      toast(`Test failed: ${e.message}`)
    } finally {
      setTesting(false)
    }
  }

  const clearSink = async () => {
    try {
      await api.clearSink()
      toast('Webhook sink cleared')
      await load()
    } catch (e) {
      toast(`Clear failed: ${e.message}`)
    }
  }

  const copyText = async (text) => {
    try {
      await navigator.clipboard.writeText(text)
      toast('Copied to clipboard')
    } catch {
      toast('Copy failed — select the text manually')
    }
  }

  const header = (
    <PageHeader
      eyebrow="Guardrails · 06"
      title={<>Set the{' '}<em>guardrails</em>.</>}
      lede="Alerting, caps, and the webhook your on-call actually reads. Foresight pages before the cap trips, not after."
    />
  )

  if (loading) {
    return (
      <div className="page">
        {header}
        <Loading label="Loading autopilot settings…" />
      </div>
    )
  }

  return (
    <div className="page">
      {header}

      <div className="settings-grid">
        <div className="settings-main">
          <section className="sheet">
            <div className="sheet-head">
              <div>
                <h2 className="sheet-title">Autopilot configuration</h2>
                <p className="sheet-sub">Policy thresholds and the alert destination</p>
              </div>
              <span className="sheet-meta">saved to sqlite</span>
            </div>

            <form className="sheet-body" onSubmit={(e) => { e.preventDefault(); save() }}>
              <div className="field">
                <label className="control-label" htmlFor="webhook">Alert webhook URL</label>
                <input
                  id="webhook"
                  className="input mono"
                  type="text"
                  value={settings.webhook_url ?? ''}
                  onChange={set('webhook_url')}
                  placeholder="https://hooks.slack.com/services/…"
                  spellCheck={false}
                />
                <div className="field-hint">
                  Default: the built-in sink at{' '}
                  <span className="mono">http://127.0.0.1:8400/api/webhook-sink</span> — Slack-compatible JSON.
                </div>
              </div>

              <div className="form-grid">
                <div className="field">
                  <label className="control-label" htmlFor="softcap">Soft cap fraction</label>
                  <input
                    id="softcap"
                    type="number"
                    step="0.01"
                    min="0.5"
                    max="0.99"
                    value={settings.soft_cap_pct ?? ''}
                    onChange={set('soft_cap_pct')}
                  />
                  <div className="field-hint">Hard-stop at this fraction of budget. Default 0.95.</div>
                </div>
                <div className="field">
                  <label className="control-label" htmlFor="horizon">Horizon alert · hours</label>
                  <input
                    id="horizon"
                    type="number"
                    step="1"
                    min="1"
                    value={settings.alert_horizon_hours ?? ''}
                    onChange={set('alert_horizon_hours')}
                  />
                  <div className="field-hint">Page when projected exhaustion is inside this many hours.</div>
                </div>
                <div className="field">
                  <label className="control-label" htmlFor="z">Anomaly z threshold</label>
                  <input
                    id="z"
                    type="number"
                    step="0.1"
                    min="2"
                    value={settings.anomaly_z ?? ''}
                    onChange={set('anomaly_z')}
                  />
                  <div className="field-hint">Flag hourly spend above this robust z-score.</div>
                </div>
                <div className="field">
                  <label className="control-label" htmlFor="pacing">Pacing downgrade · hours</label>
                  <input
                    id="pacing"
                    type="number"
                    step="1"
                    min="1"
                    value={settings.pacing_downgrade_hours ?? ''}
                    onChange={set('pacing_downgrade_hours')}
                  />
                  <div className="field-hint">How long a pacing downgrade holds before it lifts.</div>
                </div>
              </div>

              <div className="form-actions">
                <button className="btn" type="submit" disabled={saving}>
                  {saving ? <Loader2 className="spin" size={13} aria-hidden="true" /> : <Save size={13} aria-hidden="true" />}
                  {saving ? 'Saving…' : 'Save settings'}
                </button>
                <button className="btn btn-ghost" type="button" onClick={sendTest} disabled={testing}>
                  {testing ? <Loader2 className="spin" size={13} aria-hidden="true" /> : <BellRing size={13} aria-hidden="true" />}
                  {testing ? 'Sending…' : 'Send test webhook'}
                </button>
                {testResult && (
                  <span className={`form-status ${testResult.delivered ? 'ok' : 'bad'}`}>
                    delivered={String(testResult.delivered)} → {testResult.webhook_url}
                  </span>
                )}
              </div>
            </form>
          </section>

          <section className="sheet">
            <div className="sheet-head">
              <div>
                <h2 className="sheet-title">Drop-in integration</h2>
                <p className="sheet-sub">Same OpenAI SDK, one base URL change</p>
              </div>
              <span className="sheet-meta">zero code changes</span>
            </div>
            <div className="sheet-body">
              <CodeBlock label="curl" code={CURL} onCopy={copyText} />
              <p className="field-hint" style={{ marginTop: 12 }}>
                Point your existing OpenAI SDK at Foresight instead of Bifrost. Same endpoints, same
                headers, zero code changes — but every call is metered, forecasted and, when the
                policy says so, capped or downgraded.
              </p>
            </div>
          </section>
        </div>

        <section className="sheet">
          <div className="sheet-head">
            <div>
              <h2 className="sheet-title">Webhook sink</h2>
              <p className="sheet-sub">Last 20 payloads · what your Slack would receive</p>
            </div>
            <button className="btn btn-danger btn-sm" onClick={clearSink} disabled={sink.length === 0}>
              <Trash2 size={12} aria-hidden="true" /> Clear
            </button>
          </div>

          {sink.length === 0 ? (
            <EmptyState
              title="No webhooks yet."
              detail="Send a test payload or let a policy fire. The built-in sink captures the exact request body."
            />
          ) : (
            <div className="sink-list">
              {sink.map((item) => {
                const body = prettyBody(item.body)
                return (
                  <div className="sink-item" key={item.id}>
                    <div className="sink-head">
                      <Inbox size={11} aria-hidden="true" />
                      <span>#{item.id}</span>
                      <span>·</span>
                      <span>{timeAgo(item.ts)}</span>
                      <span className="spacer" />
                      <button type="button" className="code-copy" onClick={() => copyText(body)}>
                        Copy
                      </button>
                    </div>
                    <pre className="sink-code">{body}</pre>
                  </div>
                )
              })}
            </div>
          )}

          <div className="sink-foot">
            <CheckCircle2 size={13} aria-hidden="true" style={{ flex: 'none', marginTop: 1 }} />
            <span>Foresight pages the moment a budget is projected to breach — including the key, horizon, and effective burn rate.</span>
          </div>
        </section>
      </div>
    </div>
  )
}
