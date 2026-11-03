import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Loading, Empty } from '../ui.jsx'

const FIELDS = [
  ['llm_retries', 'retries per LLM call (0-6), integer', 'int'],
  ['llm_backoff_s', 'exponential backoff base, seconds', 'sec'],
  ['llm_timeout_s', 'per-attempt LLM gateway timeout, seconds', 'sec'],
  ['tool_retries', 'retries per tool call (0-6), integer', 'int'],
  ['tool_timeout_s', 'tool call timeout, seconds', 'sec'],
  ['validate_tool_output', 'reject malformed tool payloads (retry/honest-fail)', 'bool'],
  ['sanitize_tool_output', 'wrap tool output as data + strip instruction-like text', 'bool'],
  ['graceful_degradation', 'honest fallback answer instead of a crash', 'bool'],
  ['max_llm_steps', 'agent loop budget (LLM rounds)', 'int'],
  ['max_tool_calls', 'tool call budget per run', 'int'],
]

function FieldRow({ k, hint, type, value, onChange }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '240px 190px 1fr', gap: 12, alignItems: 'center', padding: '7px 0', borderBottom: '1px solid var(--line)' }}>
      <span className="mono" style={{ fontSize: 11.5 }}>{k}</span>
      {type === 'bool'
        ? <button
            className={`btn sm ${value ? 'primary' : 'ghost'}`}
            style={{ width: 120, justifyContent: 'center' }}
            onClick={() => onChange(!value)}
          >{value ? 'true' : 'false'}</button>
        : <input
            type="number"
            step={type === 'sec' ? 0.1 : 1}
            className="mono"
            style={{ width: 120, background: 'var(--bg)', border: '1px solid var(--line-2)', borderRadius: 6, color: 'var(--text)', padding: '5px 9px', fontSize: 12 }}
            value={value}
            onChange={e => onChange(e.target.value === '' ? '' : Number(e.target.value))}
          />}
      <span className="small faint">{hint}</span>
    </div>
  )
}

export default function PolicyView({ onApplied }) {
  const [data, setData] = useState(null)   // {current, presets}
  const [draft, setDraft] = useState(null)
  const [err, setErr] = useState(null)
  const [saved, setSaved] = useState(false)
  const [rawMode, setRawMode] = useState(false)
  const [raw, setRaw] = useState('')

  useEffect(() => {
    api.policy().then(d => {
      setData(d)
      setDraft(d.current)
      setRaw(JSON.stringify(d.current, null, 2))
    }).catch(e => setErr(String(e.message || e)))
  }, [])

  if (err) return <div className="banner">⚠ {err}</div>
  if (!data || !draft) return <Loading label="loading policy…" />

  const setField = (k, v) => { setSaved(false); setDraft(d => ({ ...d, [k]: v })) }

  const loadPreset = (name) => {
    const p = data.presets[name]
    if (!p) return
    setSaved(false)
    setDraft({ ...p })
    setRaw(JSON.stringify(p, null, 2))
  }

  const save = async () => {
    setErr(null)
    try {
      let pol = draft
      if (rawMode) pol = JSON.parse(raw)
      const r = await api.putPolicy(pol)
      setDraft(r.current)
      setRaw(JSON.stringify(r.current, null, 2))
      setSaved(true)
      onApplied?.()
    } catch (e) {
      setErr(String(e.message || e))
    }
  }

  const dirty = JSON.stringify(draft) !== JSON.stringify(data.current)

  return (
    <div>
      <div className="grid2" style={{ gridTemplateColumns: '1fr 300px', marginBottom: 16 }}>
        <div className="card">
          <div className="card-head">
            <h3>Working policy — what the next suite runs with</h3>
            <span className="sub">agent code is fixed; the policy is the deployment</span>
            <div style={{ flex: 1 }} />
            <button className={`btn sm ghost${rawMode ? ' active' : ''}`} onClick={() => setRawMode(m => !m)}>{rawMode ? 'form' : 'raw json'}</button>
          </div>
          <div className="card-body">
            {!rawMode && (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: '240px 190px 1fr', gap: 12, padding: '4px 0 8px', borderBottom: '1px solid var(--line-2)' }}>
                  <span className="small faint mono">KEY</span><span className="small faint mono">VALUE</span><span className="small faint mono">WHAT IT CONTROLS</span>
                </div>
                {FIELDS.map(([k, hint, type]) => (
                  <FieldRow key={k} k={k} hint={hint} type={type} value={draft[k]} onChange={v => setField(k, v)} />
                ))}
              </>
            )}
            {rawMode && (
              <textarea className="code" spellCheck={false} style={{ minHeight: 330 }} value={raw} onChange={e => { setRaw(e.target.value); setSaved(false) }} />
            )}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="card pad">
            <div className="small faint" style={{ marginBottom: 8 }}>PRESETS</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <button className="btn ghost" style={{ justifyContent: 'flex-start' }} onClick={() => loadPreset('baseline')}>
                <span>baseline<span style={{ display: 'block', fontSize: 10.5, color: 'var(--text-3)' }}>fragile on purpose — 0 retries, no guards</span></span>
              </button>
              <button className="btn ghost" style={{ justifyContent: 'flex-start' }} onClick={() => loadPreset('hardened')}>
                <span>hardened<span style={{ display: 'block', fontSize: 10.5, color: 'var(--text-3)' }}>retries + validation + sanitization + fallback</span></span>
              </button>
            </div>
          </div>
          <div className="card pad">
            <button className="btn primary" style={{ width: 100, justifyContent: 'center' }} onClick={save} disabled={!dirty && !rawMode}>
              Save policy
            </button>
            <div style={{ marginTop: 10 }}>
              {saved
                ? <span className="small" style={{ color: 'var(--ok)' }}>saved — next runs use this policy</span>
                : dirty
                  ? <span className="small" style={{ color: 'var(--warn)' }}>unsaved edits</span>
                  : <span className="small faint">in sync with the working policy</span>}
            </div>
            {err && <div className="banner" style={{ marginTop: 10 }}>⚠ {err}</div>}
          </div>
          <div className="card pad">
            <div className="small faint" style={{ marginBottom: 6 }}>HOW SCORING USES IT</div>
            <div className="small muted" style={{ lineHeight: 1.65 }}>
              Deterministic checks (45%) gate pass/fail; the LLM judge (55%) scores task success,
              resilience, honesty, efficiency. Suite reliability = per-run blend, averaged.
            </div>
          </div>
        </div>
      </div>

      {!data && <Empty />}
    </div>
  )
}
