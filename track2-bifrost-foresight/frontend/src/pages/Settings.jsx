import { useCallback, useEffect, useState } from 'react'
import { BellRing, CheckCircle2, Inbox, Save, Trash2 } from 'lucide-react'
import { api, timeAgo, toast } from '../api'

export default function Settings({ refreshKey }) {
  const [settings, setSettings] = useState({})
  const [sink, setSink] = useState([])
  const [testResult, setTestResult] = useState(null)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const [s, k] = await Promise.all([api.getSettings(), api.sink()])
      setSettings(s.settings)
      setSink(k.sink)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { load() }, [load, refreshKey])

  const set = (k) => (e) => setSettings({ ...settings, [k]: e.target.value })

  const save = async () => {
    setSaving(true)
    try {
      await api.putSettings(settings)
      toast('Settings saved')
      await load()
    } finally { setSaving(false) }
  }

  const sendTest = async () => {
    setTestResult(null)
    const res = await api.testWebhook()
    setTestResult(res)
    toast(res.delivered ? 'Test webhook delivered to the sink' : 'Test webhook failed — check the URL')
    await load()
  }

  const clearSink = async () => { await api.clearSink(); toast('Webhook sink cleared'); await load() }

  return (
    <div className="settings-grid">
      <div className="panel panel-pad">
        <div className="panel-title">
          <span><BellRing size={12} style={{ verticalAlign: -2, marginRight: 6 }} />Autopilot configuration</span>
          <button className="btn btn-ghost btn-sm" onClick={save} disabled={saving}><Save size={13} />{saving ? 'Saving…' : 'Save'}</button>
        </div>

        <div className="field">
          <label className="control-label" htmlFor="webhook">Alert webhook URL</label>
          <input id="webhook" className="mono" type="text" value={settings.webhook_url || ''} onChange={set('webhook_url')} placeholder="https://hooks.slack.com/services/…" />
          <div style={{ fontSize: 10.5, color: 'var(--muted-2)' }}>Default: the built-in sink at <span className="mono">http://127.0.0.1:8400/api/webhook-sink</span> — Slack-compatible JSON.</div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div className="field">
            <label className="control-label" htmlFor="softcap">Soft cap fraction</label>
            <input id="softcap" type="number" step="0.01" min="0.5" max="0.99" value={settings.soft_cap_pct || ''} onChange={set('soft_cap_pct')} />
          </div>
          <div className="field">
            <label className="control-label" htmlFor="horizon">Horizon alert (hours)</label>
            <input id="horizon" type="number" step="1" min="1" value={settings.alert_horizon_hours || ''} onChange={set('alert_horizon_hours')} />
          </div>
          <div className="field">
            <label className="control-label" htmlFor="z">Anomaly z threshold</label>
            <input id="z" type="number" step="0.1" min="2" value={settings.anomaly_z || ''} onChange={set('anomaly_z')} />
          </div>
          <div className="field">
            <label className="control-label" htmlFor="pacing">Pacing downgrade (hours)</label>
            <input id="pacing" type="number" step="1" min="1" value={settings.pacing_downgrade_hours || ''} onChange={set('pacing_downgrade_hours')} />
          </div>
        </div>

        <button className="btn" onClick={sendTest} style={{ marginBottom: 4 }}><BellRing size={14} /> Send test webhook</button>
        {testResult && (
          <div className="code-badge" style={{ marginTop: 10 }}>
            delivered={String(testResult.delivered)} → {testResult.webhook_url}
          </div>
        )}

        <div className="panel-title" style={{ marginTop: 20 }}>Drop-in integration</div>
        <div className="code-badge">curl {'{'}$FORESIGHT{'}'}/v1/chat/completions \</div>
        <div className="code-badge" style={{ marginTop: 6 }}>-H "Authorization: Bearer sk-bf-foresight-growth-0001" \</div>
        <div className="code-badge" style={{ marginTop: 6 }}>-d '{"{"}"model": "acme-llm/gpt-4o"{"}"}'</div>
        <div style={{ fontSize: 11, color: 'var(--muted-2)', marginTop: 10, lineHeight: 1.6 }}>
          Point your existing OpenAI SDK at Foresight instead of Bifrost. Same endpoints, same headers,
          zero code changes — but every call is metered, forecasted and, when the policy says so, capped or downgraded.
        </div>
      </div>

      <div className="panel panel-pad">
        <div className="panel-title">
          <span><Inbox size={12} style={{ verticalAlign: -2, marginRight: 6 }} />Webhook sink · last 20</span>
          <button className="btn btn-ghost btn-sm" onClick={clearSink}><Trash2 size={13} /> Clear</button>
        </div>
        {sink.length === 0 && <div className="empty">No webhooks received yet. Hit “Send test webhook”.</div>}
        {sink.map((item) => (
          <div className="sink-item" key={item.id}>
            <div className="sink-head"><span>#{item.id}</span><span>{timeAgo(item.ts)}</span></div>
            {item.body}
          </div>
        ))}
        <div style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'center', color: 'var(--muted-2)', fontSize: 11 }}>
          <CheckCircle2 size={13} />
          This is what your Slack channel sees — Foresight pages the moment a budget is projected to breach.
        </div>
      </div>
    </div>
  )
}
