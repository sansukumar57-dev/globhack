import { useCallback, useEffect, useState } from 'react'
import { Activity, AlertTriangle, DollarSign, Flame, Gauge, ShieldAlert, Zap } from 'lucide-react'
import { api, fmtUsd, fmtHoursLeft, timeAgo } from '../api'
import { AreaChart, BudgetBar, StatusChip } from '../components/charts'

export default function Overview({ refreshKey }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      setData(await api.overview())
      setError('')
    } catch (e) {
      setError(e.message)
    }
  }, [])

  useEffect(() => { load() }, [load, refreshKey])

  if (error) return <div className="panel panel-pad empty">Failed to load overview: {error}</div>
  if (!data) return <div className="panel panel-pad empty">Loading fleet state…</div>

  const totalBudget = data.keys.reduce((s, k) => s + k.budget_usd, 0)
  const projectedPct = totalBudget > 0 ? data.projected_30d_cost / totalBudget : 0
  const worst = data.keys.find((k) => k.status === 'critical' || k.status === 'exhausted')

  return (
    <>
      <div className="kpi-grid">
        <div className="panel kpi">
          <div className="kpi-label"><DollarSign size={13} /> Spend today</div>
          <div className="kpi-value">{fmtUsd(data.spend_today)}</div>
          <div className="kpi-sub"><b>{data.requests_today}</b> metered requests · {fmtUsd(data.spend_window)} over 30d</div>
        </div>
        <div className="panel kpi">
          <div className="kpi-label"><Flame size={13} /> Burn rate · 6h</div>
          <div className="kpi-value">{fmtUsd(data.burn_rate_6h)}<span style={{ fontSize: 14, color: 'var(--muted)' }}>/h</span></div>
          <div className="kpi-sub">{fmtUsd(data.burn_rate_24h)}/h trailing 24h · <b>anomaly-inflated</b></div>
        </div>
        <div className="panel kpi">
          <div className="kpi-label"><Gauge size={13} /> Projected 30d cost</div>
          <div className="kpi-value">{fmtUsd(data.projected_30d_cost, 0)}</div>
          <div className="kpi-sub">vs <b>{fmtUsd(totalBudget, 0)}</b> fleet budget · <span className={projectedPct > 1 ? 'bad' : 'good'}>{(projectedPct * 100).toFixed(0)}%</span></div>
        </div>
        <div className="panel kpi">
          <div className="kpi-label"><ShieldAlert size={13} /> Keys at risk</div>
          <div className="kpi-value">{data.keys_critical + data.keys_watch}<span style={{ fontSize: 14, color: 'var(--muted)' }}> / {data.keys.length}</span></div>
          <div className="kpi-sub">{data.keys_critical > 0 ? <span className="bad">{worst?.name} critical</span> : <span className="good">none critical</span>}</div>
        </div>
      </div>

      <div className="overview-grid">
        <div className="panel panel-pad">
          <div className="panel-title">
            <span><Activity size={12} style={{ verticalAlign: -2, marginRight: 6 }} />Fleet spend · last 24h</span>
            <span className="hint">all virtual keys</span>
          </div>
          <AreaChart data={data.hourly_all} />

          <div className="panel-title" style={{ marginTop: 18 }}>
            <span><Zap size={12} style={{ verticalAlign: -2, marginRight: 6 }} />Budget health · rolling 30d</span>
            <span className="hint">Bifrost enforces at 100% — Foresight sees the cliff first</span>
          </div>
          <div className="budget-row">
            {data.keys.map((k) => (
              <div className="budget-item" key={k.vk}>
                <div className="budget-head">
                  <span className="key-dot" style={{ background: k.color }} />
                  <div>
                    <div className="budget-name">{k.name}</div>
                    <div className="budget-team">{k.team} · {k.policy} policy{k.downgrade_active ? ' · downgrade armed' : ''}</div>
                  </div>
                  <div className="budget-meta">
                    <span className="budget-spent"><b>{fmtUsd(k.spent_usd)}</b> / {fmtUsd(k.budget_usd, 0)}</span>
                    <StatusChip status={k.status} />
                  </div>
                </div>
                <BudgetBar pct={k.pct_used} />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10.5, color: 'var(--muted-2)' }} className="mono">
                  <span>{(k.pct_used * 100).toFixed(0)}% used · exhausts in {fmtHoursLeft(k.hours_until_exhaustion)}</span>
                  <span>burn {fmtUsd(k.burn_rate_6h)}/h · trend {k.trend_pct_per_day >= 0 ? '+' : ''}{k.trend_pct_per_day}%/d</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="panel panel-pad">
          <div className="panel-title">
            <span><AlertTriangle size={12} style={{ verticalAlign: -2, marginRight: 6 }} />Recent alerts</span>
            <span className="hint">{data.recent_alerts.length} in window</span>
          </div>
          <div className="alert-list">
            {data.recent_alerts.length === 0 && <div className="empty">No alerts. Quiet fleets make expensive surprises.</div>}
            {data.recent_alerts.map((a) => (
              <div className="alert-item" key={a.id}>
                <div className={`alert-icon alert-${a.severity === 'critical' ? 'critical' : a.severity === 'warning' ? 'warning' : 'info'}`}>
                  <AlertTriangle size={15} />
                </div>
                <div>
                  <div className="alert-title">{a.title}</div>
                  <div className="alert-detail">{a.detail}</div>
                  <div className="alert-time mono">{timeAgo(a.ts)} · {a.kind}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="panel-title" style={{ marginTop: 18 }}>Top models · 30d</div>
          <table className="table">
            <thead><tr><th>Model</th><th>Cost</th><th>Reqs</th></tr></thead>
            <tbody>
              {data.top_models.map((m) => (
                <tr key={m.model}>
                  <td className="mono"><b>{String(m.model).split('/').pop()}</b></td>
                  <td className="mono">{fmtUsd(m.cost)}</td>
                  <td className="mono">{m.requests}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
