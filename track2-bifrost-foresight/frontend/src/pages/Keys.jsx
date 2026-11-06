import { useCallback, useEffect, useState } from 'react'
import { ArrowRight, Loader2, Rocket, ShieldCheck } from 'lucide-react'
import { api, fmtUsd, fmtHoursLeft, toast } from '../api'
import { BudgetBar, StatusChip } from '../components/charts'
import { EmptyState, Loading, PageHeader, monogram, toneFor } from '../components/ui'

const POLICIES = [
  { value: 'observe', label: 'Observe · meter only' },
  { value: 'notify', label: 'Notify · webhook early warning' },
  { value: 'soft_cap', label: 'Soft cap · stop at 95% of budget' },
  { value: 'pacing', label: 'Pacing · auto-downgrade when exhaustion ≤ 24h' },
]

const DOWNGRADES = ['', 'gpt-4o-mini', 'gpt-4.1-mini', 'gpt-5-mini', 'claude-3-5-haiku', 'deepseek-chat', 'mistral-small', 'gemini-2.0-flash']

function stabilityLabel(value) {
  if (!value) return '—'
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export default function Keys({ refreshKey }) {
  const [keys, setKeys] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')

  const load = useCallback(async () => {
    try {
      const res = await api.keys()
      setKeys(res.keys)
    } catch {
      /* the top bar surfaces connectivity */
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load, refreshKey])

  const withBusy = async (id, fn) => {
    setBusy(id)
    try {
      await fn()
      await load()
    } catch (e) {
      toast(`Update failed: ${e.message}`)
    } finally {
      setBusy('')
    }
  }

  const changePolicy = (k, policy) => withBusy(k.vk, async () => {
    await api.updateKey(k.vk, { policy })
    toast(`Policy for ${k.name} → ${policy}`)
  })

  const changeDowngrade = (k, downgradeTo) => withBusy(k.vk, async () => {
    await api.updateKey(k.vk, { downgrade_to: downgradeTo })
    toast(`Downgrade target for ${k.name} → ${downgradeTo || 'unset'}`)
  })

  const toggleDowngrade = (k) => withBusy(k.vk, async () => {
    if (k.downgrade_active) {
      await api.releaseDowngrade(k.vk)
      toast(`Downgrade released for ${k.name}`)
    } else {
      await api.armDowngrade(k.vk, k.downgrade_to, 6)
      toast(`${k.name} downgraded to ${k.downgrade_to} for 6h`)
    }
  })

  const totalBudget = keys.reduce((sum, k) => sum + k.budget_usd, 0)
  const totalSpent = keys.reduce((sum, k) => sum + k.spent_usd, 0)
  const atRisk = keys.filter((k) => k.status !== 'healthy').length
  const spentPct = totalBudget > 0 ? Math.round((totalSpent / totalBudget) * 100) : 0

  const header = (
    <PageHeader
      eyebrow="Control · 02"
      title={<>The key{' '}<em>ledger</em>.</>}
      lede="Four keys, one rolling window. Set policy, arm a time-boxed downgrade, and watch the runway."
      actions={(
        <a className="btn btn-ghost" href="#simulator">
          Model savings <ArrowRight size={13} aria-hidden="true" />
        </a>
      )}
    />
  )

  if (loading) {
    return (
      <div className="page">
        {header}
        <Loading label="Loading virtual keys…" />
      </div>
    )
  }

  if (keys.length === 0) {
    return (
      <div className="page">
        {header}
        <div className="sheet">
          <EmptyState
            title="No keys on the ledger"
            detail="Seed the demo fleet from the Overview page to create the four virtual keys."
            action={<a className="btn btn-ghost" href="#overview">Open overview</a>}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      {header}

      <div className="tape three">
        <div className="tape-cell">
          <div className="tape-label">Keys</div>
          <div className="tape-value">{keys.length}</div>
          <div className="tape-context">{atRisk} at risk · {keys.length - atRisk} healthy</div>
        </div>
        <div className="tape-cell">
          <div className="tape-label">Committed budget</div>
          <div className="tape-value">{fmtUsd(totalBudget, 0)}</div>
          <div className="tape-context">rolling 30-day windows</div>
        </div>
        <div className="tape-cell">
          <div className="tape-label">Spent</div>
          <div className="tape-value">{fmtUsd(totalSpent, 0)}</div>
          <div className="tape-context">
            {spentPct}% of committed · {fmtUsd(Math.max(0, totalBudget - totalSpent), 0)} left
          </div>
        </div>
      </div>

      <section className="sheet">
        <div className="sheet-head">
          <div>
            <h2 className="sheet-title">Key ledger</h2>
            <p className="sheet-sub">Rolling 30-day budgets · policy and downgrade controls</p>
          </div>
          <span className="sheet-meta">{keys.length} keys</span>
        </div>

        <div className="key-list">
          {keys.map((k) => {
            const tone = toneFor(k.status)
            const busyHere = busy === k.vk
            const canArm = k.downgrade_active || Boolean(k.downgrade_to)
            return (
              <article
                className={`key-row ${tone}`}
                key={k.vk}
                aria-busy={busyHere}
              >
                <div className="key-row-top">
                  <span className="key-mark">{monogram(k.name)}</span>
                  <div className="key-row-heading">
                    <div className="key-title">{k.name}</div>
                    <div className="key-vk">{k.vk} · {k.team}</div>
                  </div>
                  <div className="key-row-badges">
                    {k.downgrade_active && <span className="tag tag-green">downgrade active</span>}
                    <StatusChip status={k.status} />
                  </div>
                </div>

                <div className="key-budget">
                  <BudgetBar pct={k.pct_used} tone={tone} large />
                  <span className="money">
                    {fmtUsd(k.spent_usd)} <span>of {fmtUsd(k.budget_usd, 0)}</span>
                  </span>
                  <span className="pct">{Math.round(k.pct_used * 100)}%</span>
                </div>

                <div className="key-row-stats">
                  <div className="key-stat">
                    <div className="key-stat-label">Burn · 6h</div>
                    <div className="key-stat-value">{fmtUsd(k.burn_rate_6h)}<small>/h</small></div>
                  </div>
                  <div className="key-stat">
                    <div className="key-stat-label">Runway</div>
                    <div className="key-stat-value">{fmtHoursLeft(k.hours_until_exhaustion)}</div>
                  </div>
                  <div className="key-stat">
                    <div className="key-stat-label">Projected · 30d</div>
                    <div className="key-stat-value">{fmtUsd(k.projected_30d_cost, 0)}</div>
                  </div>
                  <div className="key-stat">
                    <div className="key-stat-label">Stability</div>
                    <div className="key-stat-value">
                      {stabilityLabel(k.stability)}{' '}
                      <small>· {k.trend_pct_per_day >= 0 ? '+' : ''}{k.trend_pct_per_day}%/d</small>
                    </div>
                  </div>
                </div>

                <div className="key-controls">
                  <div className="field">
                    <label className="control-label" htmlFor={`policy-${k.vk}`}>Autopilot</label>
                    <select
                      id={`policy-${k.vk}`}
                      className="select policy"
                      value={k.policy}
                      disabled={busyHere}
                      onChange={(e) => changePolicy(k, e.target.value)}
                    >
                      {POLICIES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                    </select>
                  </div>
                  <div className="field">
                    <label className="control-label" htmlFor={`dg-${k.vk}`}>Downgrade to</label>
                    <select
                      id={`dg-${k.vk}`}
                      className="select"
                      value={k.downgrade_to}
                      disabled={busyHere}
                      onChange={(e) => changeDowngrade(k, e.target.value)}
                    >
                      {DOWNGRADES.map((m) => <option key={m} value={m}>{m || '—'}</option>)}
                    </select>
                  </div>
                  <div className="spacer" />
                  <button
                    className={`btn ${k.downgrade_active ? 'btn-ghost' : ''}`}
                    disabled={busyHere || !canArm}
                    title={canArm ? 'Arm a six-hour model downgrade' : 'Choose a downgrade target first'}
                    onClick={() => toggleDowngrade(k)}
                  >
                    {busyHere ? (
                      <><Loader2 className="spin" size={13} aria-hidden="true" /> Working…</>
                    ) : k.downgrade_active ? (
                      <><ShieldCheck size={13} aria-hidden="true" /> Release downgrade</>
                    ) : (
                      <><Rocket size={13} aria-hidden="true" /> Arm 6h</>
                    )}
                  </button>
                </div>

                {k.downgrade_active && (
                  <div className="key-armed">
                    <ShieldCheck size={13} aria-hidden="true" />
                    <span>Downgrade active — traffic routes to <b>{k.downgrade_to}</b> until the pacing window lifts.</span>
                  </div>
                )}
              </article>
            )
          })}
        </div>
      </section>
    </div>
  )
}
