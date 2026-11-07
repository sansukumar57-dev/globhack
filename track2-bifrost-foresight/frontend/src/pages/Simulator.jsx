import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowRight, Flame, Loader2 } from 'lucide-react'
import { api, fmtUsd } from '../api'
import { AreaChart } from '../components/charts'
import { EmptyState, Loading, PageHeader, monogram } from '../components/ui'

const TARGETS = ['gpt-4o-mini', 'gpt-4.1-mini', 'gpt-5-mini', 'claude-3-5-haiku', 'deepseek-chat', 'mistral-small', 'gemini-2.0-flash']

export default function Simulator({ refreshKey }) {
  const [keys, setKeys] = useState([])
  const [loading, setLoading] = useState(true)
  const [vk, setVk] = useState('')
  const [toModel, setToModel] = useState('gpt-4o-mini')
  const [shift, setShift] = useState(50)
  const [result, setResult] = useState(null)
  const [resultError, setResultError] = useState('')
  const [recos, setRecos] = useState([])
  const [recoTotal, setRecoTotal] = useState(0)
  const [stressMult, setStressMult] = useState(2)
  const [stressing, setStressing] = useState(false)
  const [stress, setStress] = useState(null)
  const [stressError, setStressError] = useState('')

  useEffect(() => {
    api.keys().then((res) => {
      setKeys(res.keys)
      setVk((current) => current || res.keys[0]?.vk || '')
    }).catch(() => {}).finally(() => setLoading(false))
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
      setResultError('')
      const res = await api.simulator({ vk, from_model: fromModel, to_model: toModel, shift_pct: shift })
      setResult(res)
    } catch (e) {
      setResultError(e.message)
    }
  }, [vk, fromModel, toModel, shift])

  const runStress = useCallback(async () => {
    if (!vk) return
    setStressing(true)
    setStressError('')
    try {
      setStress(await api.stress(vk, stressMult))
    } catch (e) {
      setStressError(e.message)
    } finally {
      setStressing(false)
    }
  }, [vk, stressMult])

  useEffect(() => { run() }, [run])

  const applyReco = (rec) => {
    setVk(rec.vk)
    setToModel(rec.target)
    setShift(100)
    if (window.innerWidth <= 760) {
      document.getElementById('sim-calculator')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  const header = (
    <PageHeader
      eyebrow="Planning · 04"
      title={<>Move traffic,{' '}<em>keep the budget</em>.</>}
      lede="Price a model shift against live unit economics before you touch the router. The range is the share of dominant-model traffic you move."
    />
  )

  if (loading) {
    return (
      <div className="page">
        {header}
        <Loading label="Pricing the what-if…" />
      </div>
    )
  }

  if (keys.length === 0) {
    return (
      <div className="page">
        {header}
        <div className="sheet">
          <EmptyState
            title="No traffic to price"
            detail="Seed the demo fleet from the Overview page first."
            action={<a className="btn btn-ghost" href="#overview">Open overview</a>}
          />
        </div>
      </div>
    )
  }

  const r = result
  const before = r ? r.projected_30d_after + r.savings_30d : 0
  const after = r ? r.projected_30d_after : 0
  const compareMax = Math.max(before, after, 1)

  return (
    <div className="page">
      {header}

      <section className="sheet stress">
        <div className="sheet-head">
          <div>
            <h2 className="sheet-title">Demand stress test</h2>
            <p className="sheet-sub">Same metered shape, a different demand regime — the trained committee answers</p>
          </div>
          <span className="sheet-meta">counterfactual</span>
        </div>

        <div className="stress-grid">
          <div className="stress-controls">
            <div className="field">
              <label className="control-label" htmlFor="stress-mult">
                Demand multiplier ·{' '}
                <b style={{ color: 'var(--ink)' }}>{stressMult.toFixed(2)}×</b>
              </label>
              <input
                id="stress-mult"
                className="slider"
                type="range"
                min={0.5}
                max={4}
                step={0.25}
                value={stressMult}
                onChange={(e) => setStressMult(Number(e.target.value))}
              />
              <div className="slider-scale">
                <span>0.5×</span>
                <span>1×</span>
                <span>2×</span>
                <span>3×</span>
                <span>4×</span>
              </div>
            </div>
            <button className="btn btn-accent" onClick={runStress} disabled={stressing || !vk}>
              {stressing
                ? <Loader2 className="spin" size={13} aria-hidden="true" />
                : <Flame size={13} aria-hidden="true" />}
              {stressing ? 'Rolling the committee…' : 'Run the committee'}
            </button>
            <p className="field-hint" style={{ marginTop: 12 }}>
              Re-runs the trained 24-member committee with this key's trailing buckets scaled by{' '}
              {stressMult.toFixed(2)}× and forecasts the fleet 24 hours forward. Trees saturate past the
              envelope they learned — saturation <i>is</i> the answer.
            </p>
            {stressError && <div className="form-status bad">Stress test unavailable: {stressError}</div>}
          </div>

          <div className="stress-output">
            {!stress ? (
              <EmptyState
                title="An unanswered question"
                detail="Price a demand regime with the same committee that set the p10–p90 band on the Overview. Fleet curve and cap impact under it — before your customers have a bad day."
              />
            ) : (
              <div className="stress-report">
                <div className="stress-stats">
                  <div className="calc-cell">
                    <b>{fmtUsd(stress.baseline.fleet_24h, 0)} → {fmtUsd(stress.stressed.fleet_24h, 0)}</b>
                    <span>fleet spend · 24h</span>
                  </div>
                  <div className="calc-cell">
                    <b className={stress.delta_pct > 0.5 ? 'bad' : 'good'}>
                      {stress.delta_pct >= 0 ? '+' : ''}{stress.delta_pct}%
                    </b>
                    <span>Δ vs baseline</span>
                  </div>
                  <div className="calc-cell">
                    <b>
                      {stress.stressed.risk[vk]?.remaining_usd != null
                        ? fmtUsd(stress.stressed.risk[vk].remaining_usd, 0)
                        : '—'}
                    </b>
                    <span>key remaining cap</span>
                  </div>
                </div>
                <AreaChart data={stress.hourly_all || []} forecast={stress.stressed.curve} />
                <p className="calc-note">
                  {(() => {
                    const r = stress.stressed.risk[vk]
                    if (!r) return 'Ensemble verdict unavailable for this key.'
                    const after = Math.round((r.p_24h ?? 0) * 100)
                    const rb = stress.baseline.risk[vk]
                    const before = rb ? Math.round((rb.p_24h ?? 0) * 100) : null
                    return (
                      <>
                        Under ×{stress.multiplier.toFixed(2)} demand the committee projects{' '}
                        {stress.delta_pct >= 0 ? '+' : ''}{stress.delta_pct}% fleet spend in 24h;{' '}
                        {selected?.name ?? 'this key'}'s paths breach its remaining ${fmtUsd(r.remaining_usd, 0)} cap
                        in 24h with probability <b>{after}%</b>
                        {before != null && before !== after ? ` (baseline ${before}%)` : ''}.
                      </>
                    )
                  })()}
                </p>
              </div>
            )}
          </div>
        </div>
      </section>

      <div className="sim-grid">
        <section className="sheet" id="sim-calculator">
          <div className="sheet-head">
            <div>
              <h2 className="sheet-title">Model shift calculator</h2>
              <p className="sheet-sub">Unit economics from the live model catalog</p>
            </div>
            <span className="sheet-meta">what-if</span>
          </div>
          <div className="sheet-body">
            <div className="field">
              <label className="control-label" htmlFor="sim-key">Virtual key</label>
              <select id="sim-key" className="select" value={vk} onChange={(e) => setVk(e.target.value)}>
                {keys.map((k) => (
                  <option key={k.vk} value={k.vk}>
                    {k.name} · {fmtUsd(k.spent_usd)} / {fmtUsd(k.budget_usd, 0)}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label className="control-label" htmlFor="sim-target">
                Shift <span className="mono">{fromModel.split('/').pop()}</span> traffic to
              </label>
              <select id="sim-target" className="select" value={toModel} onChange={(e) => setToModel(e.target.value)}>
                {TARGETS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>

            <div className="field">
              <label className="control-label" htmlFor="sim-shift">
                Share of traffic · <b style={{ color: 'var(--ink)' }}>{shift}%</b>
              </label>
              <input
                id="sim-shift"
                className="slider"
                type="range"
                min={0}
                max={100}
                step={5}
                value={shift}
                onChange={(e) => setShift(Number(e.target.value))}
              />
              <div className="slider-scale">
                <span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span>
              </div>
            </div>

            {resultError && <div className="form-status bad">Simulator unavailable: {resultError}</div>}

            {r && (
              <>
                <div className="calc-result">
                  <div className="calc-label">Projected savings · 30 days</div>
                  <div className="calc-amount">{fmtUsd(r.savings_30d)}</div>
                  <div className="calc-sub">
                    at {r.shift_pct}% shift · unit cost ×{r.unit_cost_ratio} · {r.to_model}
                  </div>
                  <div className="calc-grid">
                    <div className="calc-cell">
                      <b>{fmtUsd(r.savings_year, 0)}</b>
                      <span>12-month pace</span>
                    </div>
                    <div className="calc-cell">
                      <b>{fmtUsd(r.projected_30d_after, 0)}</b>
                      <span>Projected 30d after</span>
                    </div>
                  </div>
                </div>

                <div className="compare" aria-label="Projected 30-day spend before and after the shift">
                  <div className="compare-row">
                    <span className="compare-label">Before</span>
                    <div className="compare-track">
                      <span className="compare-fill" style={{ width: `${(before / compareMax) * 100}%` }} />
                    </div>
                    <span className="compare-value">{fmtUsd(before, 0)}</span>
                  </div>
                  <div className="compare-row">
                    <span className="compare-label">After</span>
                    <div className="compare-track">
                      <span className="compare-fill after" style={{ width: `${(after / compareMax) * 100}%` }} />
                    </div>
                    <span className="compare-value">{fmtUsd(after, 0)}</span>
                  </div>
                </div>

                <p className="calc-note">
                  Savings assume the shifted traffic is quality-neutral on {r.to_model} — validate
                  on your golden set first. Bifrost routes it deterministically once you set an alias
                  on the virtual key's provider config; Foresight only meters and forecasts.
                </p>
              </>
            )}
          </div>
        </section>

        <section className="sheet">
          <div className="sheet-head">
            <div>
              <h2 className="sheet-title">Fleet opportunities</h2>
              <p className="sheet-sub">Ranked by dominant-model spend</p>
            </div>
            <span className="sheet-meta">{fmtUsd(recoTotal)}/mo</span>
          </div>

          {recos.length === 0 ? (
            <EmptyState
              title="Already lean"
              detail="No obvious model substitutions on the current fleet."
            />
          ) : (
            <div className="reco-list">
              {recos.map((rec) => (
                <div className="reco-item" key={rec.vk}>
                  <div>
                    <div className="key-id">
                      <span className="key-mark">{monogram(rec.name)}</span>
                      <div className="key-name">{rec.name}</div>
                    </div>
                    <div className="reco-route">
                      {rec.dominant_model.split('/').pop()}
                      <ArrowRight size={10} aria-hidden="true" />
                      <span className="reco-target">{rec.target}</span>
                    </div>
                  </div>
                  <div className="reco-actions">
                    <div className="reco-save">
                      {fmtUsd(rec.savings_30d)}
                      <small>per 30d</small>
                    </div>
                    <button className="btn btn-ghost btn-sm" onClick={() => applyReco(rec)}>
                      Simulate
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="note">
            Foresight pairs this with the pacing policy: when a key is projected to breach, it
            downgrades automatically and lifts back when the budget window is safe.
          </div>
        </section>
      </div>
    </div>
  )
}
