import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowRight, BadgePercent, SlidersHorizontal, Sparkles } from 'lucide-react'
import { api, fmtUsd } from '../api'

const TARGETS = ['gpt-4o-mini', 'gpt-4.1-mini', 'gpt-5-mini', 'claude-3-5-haiku', 'deepseek-chat', 'mistral-small', 'gemini-2.0-flash']

export default function Simulator({ refreshKey }) {
  const [keys, setKeys] = useState([])
  const [vk, setVk] = useState('')
  const [toModel, setToModel] = useState('gpt-4o-mini')
  const [shift, setShift] = useState(50)
  const [result, setResult] = useState(null)
  const [recos, setRecos] = useState([])
  const [recoTotal, setRecoTotal] = useState(0)

  useEffect(() => {
    api.keys().then((res) => {
      setKeys(res.keys)
      setVk((current) => current || res.keys[0]?.vk || '')
    }).catch(() => {})
    api.recommendations().then((res) => {
      setRecos(res.recommendations)
      setRecoTotal(res.total_savings_30d)
    }).catch(() => {})
  }, [refreshKey])

  const selected = useMemo(() => keys.find((k) => k.vk === vk), [keys, vk])
  const fromModel = selected?.model_breakdown?.[0]?.model || 'acme-llm/gpt-4o'

  const run = useCallback(async () => {
    if (!vk) return
    try {
      setResult(await api.simulator({ vk, from_model: fromModel, to_model: toModel, shift_pct: shift }))
    } catch { /* keep last good result */ }
  }, [vk, fromModel, toModel, shift])

  useEffect(() => { run() }, [run])

  const r = result
  return (
    <div className="sim-grid">
      <div className="panel panel-pad">
        <div className="panel-title">
          <span><SlidersHorizontal size={12} style={{ verticalAlign: -2, marginRight: 6 }} />What-if · traffic right-sizing</span>
          <span className="hint">unit economics from the model catalog</span>
        </div>

        <div className="field">
          <label className="control-label" htmlFor="sim-key">Virtual key</label>
          <select id="sim-key" className="select" value={vk} onChange={(e) => setVk(e.target.value)}>
            {keys.map((k) => <option key={k.vk} value={k.vk}>{k.name} · {fmtUsd(k.spent_usd)} / {fmtUsd(k.budget_usd, 0)}</option>)}
          </select>
        </div>

        <div className="field">
          <label className="control-label">Route from <span className="mono" style={{ color: 'var(--violet)' }}>{fromModel.split('/').pop()}</span> →</label>
          <select className="select" value={toModel} onChange={(e) => setToModel(e.target.value)}>
            {TARGETS.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>

        <div className="field">
          <label className="control-label" htmlFor="sim-shift">Share of traffic to move · <b style={{ color: 'var(--text)' }}>{shift}%</b></label>
          <input id="sim-shift" className="slider" type="range" min={0} max={100} step={5} value={shift} onChange={(e) => setShift(Number(e.target.value))} />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--muted-2)' }} className="mono">
            <span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span>
          </div>
        </div>

        {r && (
          <>
            <div className="savings-hero">
              <div className="savings-label">Projected savings · 30d</div>
              <div className="savings-amount">{fmtUsd(r.savings_30d)}</div>
              <div className="savings-label" style={{ marginTop: 2 }}>at {r.shift_pct}% shift · unit cost ×{r.unit_cost_ratio}</div>
            </div>
            <div className="savings-grid">
              <div className="savings-cell"><b>{fmtUsd(r.savings_year, 0)}</b><span style={{ fontSize: 10, color: 'var(--muted-2)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>12-month pace</span></div>
              <div className="savings-cell"><b>{fmtUsd(r.projected_30d_after, 0)}</b><span style={{ fontSize: 10, color: 'var(--muted-2)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Projected 30d after</span></div>
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted-2)', lineHeight: 1.6 }}>
              Savings assume the shifted traffic is quality-neutral on {toModel} — validate on your golden set first.
              Bifrost routes it deterministically once you set an alias on the virtual key's provider config; Foresight only meters and forecasts.
            </div>
          </>
        )}
      </div>

      <div className="panel panel-pad">
        <div className="panel-title">
          <span><Sparkles size={12} style={{ verticalAlign: -2, marginRight: 6 }} />Fleet right-sizing</span>
          <span className="hint">{fmtUsd(recoTotal)}/mo on the table</span>
        </div>
        {recos.length === 0 && <div className="empty">No obvious right-sizing wins — the fleet is already lean.</div>}
        {recos.map((rec) => (
          <div className="reco-row" key={rec.vk}>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 12.5, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                <span className="key-dot" style={{ background: rec.color }} />{rec.name}
              </div>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--muted-2)', marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                {rec.dominant_model.split('/').pop()} <ArrowRight size={11} className="reco-arrow" /> <b style={{ color: 'var(--cyan)' }}>{rec.target}</b>
              </div>
            </div>
            <div className="reco-save">
              <BadgePercent size={12} style={{ verticalAlign: -2, marginRight: 4 }} />{fmtUsd(rec.savings_30d)}/mo
            </div>
          </div>
        ))}
        <div style={{ marginTop: 14, fontSize: 11, color: 'var(--muted-2)', lineHeight: 1.6 }}>
          Ranked by dominant-model spend. Foresight pairs this with the pacing policy: when a key is projected to breach,
          it downgrades automatically and lifts back when the budget window is safe.
        </div>
      </div>
    </div>
  )
}
