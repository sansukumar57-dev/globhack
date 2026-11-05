import { useCallback, useEffect, useState } from 'react'
import { ArrowDownRight, ArrowUpRight, KeyRound, Rocket, ShieldCheck } from 'lucide-react'
import { api, fmtUsd, fmtHoursLeft, toast } from '../api'
import { BudgetBar, StatusChip } from '../components/charts'

const POLICIES = [
  { value: 'observe', label: 'Observe · meter only' },
  { value: 'notify', label: 'Notify · webhook early warning' },
  { value: 'soft_cap', label: 'Soft cap · stop at 95% of budget' },
  { value: 'pacing', label: 'Pacing · auto-downgrade when exhaustion ≤ 24h' },
]

const DOWNGRADES = ['', 'gpt-4o-mini', 'gpt-4.1-mini', 'gpt-5-mini', 'claude-3-5-haiku', 'deepseek-chat', 'mistral-small', 'gemini-2.0-flash']

export default function Keys({ refreshKey }) {
  const [keys, setKeys] = useState([])
  const [busy, setBusy] = useState('')

  const load = useCallback(async () => {
    try {
      const res = await api.keys()
      setKeys(res.keys)
    } catch { /* topbar surfaces connectivity */ }
  }, [])

  useEffect(() => { load() }, [load, refreshKey])

  const withBusy = async (id, fn) => {
    setBusy(id)
    try { await fn(); await load() } finally { setBusy('') }
  }

  const changePolicy = (k, policy) => withBusy(k.vk, async () => {
    await api.updateKey(k.vk, { policy })
    toast(`Policy for ${k.name} → ${policy}`)
  })

  const changeDowngrade = (k, downgrade_to) => withBusy(k.vk, async () => {
    await api.updateKey(k.vk, { downgrade_to })
    toast(`Downgrade target for ${k.name} → ${downgrade_to || 'unset'}`)
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

  return (
    <div className="keys-grid">
      {keys.map((k) => (
        <div className="panel key-card" key={k.vk}>
          <div className="key-head">
            <span className="key-dot" style={{ background: k.color, marginTop: 6 }} />
            <div style={{ minWidth: 0 }}>
              <div className="key-title">{k.name}</div>
              <div className="key-vk mono">{k.vk} · {k.team}</div>
            </div>
            <div style={{ marginLeft: 'auto' }}><StatusChip status={k.status} /></div>
          </div>

          <BudgetBar pct={k.pct_used} />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--muted-2)' }} className="mono">
            <span>{fmtUsd(k.spent_usd)} of {fmtUsd(k.budget_usd, 0)} · {(k.pct_used * 100).toFixed(0)}%</span>
            <span>{k.trend_pct_per_day >= 0 ? <ArrowUpRight size={11} style={{ verticalAlign: -1 }} /> : <ArrowDownRight size={11} style={{ verticalAlign: -1 }} />}{Math.abs(k.trend_pct_per_day)}%/d</span>
          </div>

          <div className="key-stats">
            <div className="key-stat">
              <div className="key-stat-label">Burn 6h</div>
              <div className="key-stat-value">{fmtUsd(k.burn_rate_6h)}<span style={{ fontSize: 10, color: 'var(--muted)' }}>/h</span></div>
            </div>
            <div className="key-stat">
              <div className="key-stat-label">Exhausts in</div>
              <div className="key-stat-value">{fmtHoursLeft(k.hours_until_exhaustion)}</div>
            </div>
            <div className="key-stat">
              <div className="key-stat-label">Projected 30d</div>
              <div className="key-stat-value">{fmtUsd(k.projected_30d_cost, 0)}</div>
            </div>
            <div className="key-stat">
              <div className="key-stat-label">Stability</div>
              <div className="key-stat-value" style={{ textTransform: 'capitalize' }}>{k.stability}</div>
            </div>
          </div>

          <div className="key-foot">
            <div>
              <label className="control-label" htmlFor={`policy-${k.vk}`}>Autopilot</label>
              <select id={`policy-${k.vk}`} className="select" value={k.policy} disabled={busy === k.vk}
                      onChange={(e) => changePolicy(k, e.target.value)}>
                {POLICIES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
            <div>
              <label className="control-label" htmlFor={`dg-${k.vk}`}>Downgrade to</label>
              <select id={`dg-${k.vk}`} className="select" value={k.downgrade_to} disabled={busy === k.vk}
                      onChange={(e) => changeDowngrade(k, e.target.value)}>
                {DOWNGRADES.map((m) => <option key={m} value={m}>{m || '—'}</option>)}
              </select>
            </div>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'flex-end' }}>
              <button className="btn btn-ghost btn-sm" disabled={busy === k.vk || (!k.downgrade_active && !k.downgrade_to)}
                      onClick={() => toggleDowngrade(k)}>
                {k.downgrade_active ? <><ShieldCheck size={13} /> Release</> : <><Rocket size={13} /> Arm 6h</>}
              </button>
            </div>
          </div>
          {k.downgrade_active && <div className="arm-note">Downgrade active — traffic routes to <b>{k.downgrade_to}</b> until the pacing window lifts.</div>}
        </div>
      ))}
    </div>
  )
}
