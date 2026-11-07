import { useCallback, useEffect, useMemo, useState } from 'react'
import { Database } from 'lucide-react'
import { api, fmtUsd, fmtHoursLeft, timeAgo } from '../api'
import { AreaChart, BudgetBar, StatusChip } from '../components/charts'
import { EmptyState, Loading, PageHeader, monogram, toneFor } from '../components/ui'

const STATUS_RANK = { critical: 0, exhausted: 0, watch: 1, healthy: 2 }

export default function Overview({ refreshKey, onReseed, reseeding }) {
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

  const sortedKeys = useMemo(() => {
    if (!data) return []
    return [...data.keys].sort((a, b) => {
      const rank = (STATUS_RANK[a.status] ?? 3) - (STATUS_RANK[b.status] ?? 3)
      return rank || b.pct_used - a.pct_used
    })
  }, [data])

  const header = (
    <PageHeader
      eyebrow="Operations · 01"
      title={<>Fleet spend,{' '}<em>forecasted</em>.</>}
      lede="A live read on gateway spend, budget runway, and the next key to breach. Every number is metered, priced, and attributable."
      actions={onReseed && (
        <button className="btn btn-ghost" onClick={onReseed} disabled={reseeding}>
          <Database size={13} aria-hidden="true" />
          {reseeding ? 'Reseeding…' : 'Reseed demo data'}
        </button>
      )}
    />
  )

  if (error && !data) {
    return (
      <div className="page">
        {header}
        <div className="sheet">
          <EmptyState
            title="The ledger is out of reach"
            detail={`The console API did not answer: ${error}`}
            action={<button className="btn btn-ghost" onClick={load}>Retry</button>}
          />
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="page">
        {header}
        <Loading label="Reading the fleet ledger…" />
      </div>
    )
  }

  const atRisk = sortedKeys.filter((k) => k.status !== 'healthy')
  const critical = sortedKeys.filter((k) => k.status === 'critical' || k.status === 'exhausted')
  const next = atRisk.find((k) => k.hours_until_exhaustion != null) || atRisk[0]
  const totalBudget = data.keys.reduce((sum, k) => sum + k.budget_usd, 0)
  const projectedPct = totalBudget > 0 ? data.projected_30d_cost / totalBudget : 0
  const effectiveBurn = Math.max(data.burn_rate_6h, data.burn_rate_24h)
  const alerts = data.recent_alerts || []
  const topModels = data.top_models || []
  const modelRisk = data.model_risk || {}
  const riskFor = (k) => {
    const r = modelRisk[k.vk]
    return r && (r.p_48h != null || r.p_24h != null) ? r : null
  }

  const conditionSub = critical.length > 0
    ? `${critical[0].name} is at ${Math.round(critical[0].pct_used * 100)}% of budget${atRisk.length > 1 ? ` · ${atRisk.length - 1} more on watch` : ''}.`
    : atRisk.length > 0
      ? `${atRisk[0].name} is at ${Math.round(atRisk[0].pct_used * 100)}% of budget. No key is critical.`
      : 'Every key is inside its rolling 30-day budget.'

  return (
    <div className="page">
      {header}

      <div className={`condition ${critical.length === 0 ? 'is-clear' : ''}`}>
        <div>
          <div className="condition-label">Fleet condition</div>
          <div className="condition-main">
            {critical.length > 0 ? (
              <>
                <span className="condition-hot">{critical.length} critical</span>
                <span className="condition-sep">·</span>
                {atRisk.length - critical.length} on watch
              </>
            ) : atRisk.length > 0 ? (
              <>{atRisk.length} on watch</>
            ) : (
              'All keys inside budget'
            )}
          </div>
          <div className="condition-sub">{conditionSub}</div>
        </div>
        <div className="condition-right">
          <div className="condition-label">Next breach</div>
          <div className="condition-main">{next ? next.name : 'No projected breach'}</div>
          <div className="condition-sub">
            {next
              ? `exhausts in ${fmtHoursLeft(next.hours_until_exhaustion)} at ${fmtUsd(next.burn_rate_effective ?? next.burn_rate_24h)}/h`
              : 'inside the rolling 30-day window'}
          </div>
        </div>
        <a className="condition-link" href="#keys">Open ledger →</a>
      </div>

      <div className="tape">
        <div className="tape-cell">
          <div className="tape-label">Spend today</div>
          <div className="tape-value">{fmtUsd(data.spend_today)}</div>
          <div className="tape-context">
            <b>{data.requests_today}</b> metered requests · {fmtUsd(data.spend_window)} over 30d
          </div>
        </div>
        <div className="tape-cell">
          <div className="tape-label" title="Exhaustion ETA uses the higher of the 6h and 24h burn rates.">
            Effective burn
          </div>
          <div className="tape-value">{fmtUsd(effectiveBurn)}<span className="unit">/h</span></div>
          <div className="tape-context">
            6h {fmtUsd(data.burn_rate_6h)}/h · 24h {fmtUsd(data.burn_rate_24h)}/h
          </div>
        </div>
        <div className="tape-cell">
          <div className="tape-label">Projected · 30d</div>
          <div className="tape-value">{fmtUsd(data.projected_30d_cost, 0)}</div>
          <div className="tape-context">
            vs {fmtUsd(totalBudget, 0)} fleet budget ·{' '}
            <span className={projectedPct > 1 ? 'bad' : 'good'}>
              {(projectedPct * 100).toFixed(0)}%
            </span>
          </div>
        </div>
        <div className="tape-cell">
          <div className="tape-label">Keys at risk</div>
          <div className="tape-value">{atRisk.length}<span className="unit"> / {data.keys.length}</span></div>
          <div className="tape-context">
            {critical.length > 0
              ? <><span className="bad">{critical[0].name}</span> critical</>
              : <span className="good">no critical keys</span>}
          </div>
        </div>
      </div>

      <div className="overview-grid">
        <div className="overview-main">
          <section className="sheet">
            <div className="sheet-head">
              <div>
                <h2 className="sheet-title">Fleet burn</h2>
                <p className="sheet-sub">
                  {data.model_forecast
                    ? 'Hourly spend across all virtual keys · solid metered, dashed model median, band p10–p90'
                    : 'Hourly spend across all virtual keys · last 24 hours'}
                </p>
              </div>
              <span className="sheet-meta">
                {data.model_meta ? `${data.model_meta.keys_used} keys · +${data.model_meta.hours}h · ×${data.model_meta.committee} ` : ''}1h buckets
              </span>
            </div>
            <div className="sheet-body">
              <AreaChart data={data.hourly_all} forecast={data.model_forecast} paths={data.model_paths} />
            </div>
          </section>

          <section className="sheet">
            <div className="sheet-head">
              <div>
                <h2 className="sheet-title">Budget health</h2>
                <p className="sheet-sub">Rolling 30-day window · Bifrost enforces at 100%</p>
              </div>
              <a className="sheet-meta" href="#keys">Manage keys →</a>
            </div>
            <div className="table-wrap">
              <table className="table budget-table">
                <thead>
                  <tr>
                    <th scope="col">Key</th>
                    <th scope="col">Policy</th>
                    <th scope="col" className="r">Spend / budget</th>
                    <th scope="col">Used</th>
                    <th scope="col" className="r">Runway</th>
                    <th scope="col" className="r">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedKeys.map((k) => {
                    const tone = toneFor(k.status)
                    return (
                      <tr key={k.vk} className={tone === 'critical' ? 'critical-row' : ''}>
                        <td>
                          <div className="key-id">
                            <span className="key-mark">{monogram(k.name)}</span>
                            <div>
                              <div className="key-name">{k.name}</div>
                              <div className="key-team">{k.team}</div>
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className="tag">{k.policy.replace('_', ' ')}</span>
                          {k.downgrade_active && <span className="sub">downgraded → {k.downgrade_to}</span>}
                        </td>
                        <td className="r">
                          <span className="spend-cell">
                            <b>{fmtUsd(k.spent_usd)}</b> <span>/ {fmtUsd(k.budget_usd, 0)}</span>
                          </span>
                        </td>
                        <td>
                          <div className="used-cell">
                            <BudgetBar pct={k.pct_used} tone={tone} />
                            <span className="used-pct">{Math.round(k.pct_used * 100)}%</span>
                          </div>
                        </td>
                        <td className="r">
                          <div className="runway">
                            {fmtHoursLeft(k.hours_until_exhaustion)}
                            <small>{fmtUsd(k.burn_rate_effective ?? k.burn_rate_24h)}/h eff.</small>
                          </div>
                        </td>
                        <td className="r"><StatusChip status={k.status} /></td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <aside className="overview-side">
          <section className="sheet">
            <div className="sheet-head">
              <div>
                <h2 className="sheet-title">Attention</h2>
                <p className="sheet-sub">Keys with a projected breach</p>
              </div>
              <span className="sheet-meta">{atRisk.length} of {data.keys.length}</span>
            </div>
            <div className="attention-list">
              {atRisk.length === 0 && (
                <EmptyState
                  title="All clear"
                  detail="No key is projected to exhaust inside the alert horizon."
                />
              )}
              {atRisk.map((k) => (
                <a className={`attention-item ${toneFor(k.status)}`} href="#keys" key={k.vk}>
                  <div className="attention-top">
                    <span className="key-mark">{monogram(k.name)}</span>
                    <span className="attention-name">{k.name}</span>
                    <StatusChip status={k.status} />
                  </div>
                  <div className="attention-meta">
                    <span>{fmtUsd(k.spent_usd)} / {fmtUsd(k.budget_usd, 0)}</span>
                    <span>{fmtHoursLeft(k.hours_until_exhaustion)} left</span>
                    <span>{fmtUsd(k.burn_rate_effective ?? k.burn_rate_24h)}/h</span>
                  </div>
                  <div className="attention-note">
                    {k.stability} burn · {k.trend_pct_per_day >= 0 ? '+' : ''}{k.trend_pct_per_day}%/day trend ·{' '}
                    {k.policy.replace('_', ' ')} policy
                  </div>
                  {riskFor(k) && (() => {
                    const r = riskFor(k)
                    const p = r.p_48h ?? r.p_24h
                    const cum = r.median_cum_48h ?? r.median_cum_24h
                    const h = data.model_meta?.horizon ?? 48
                    return (
                      <div
                        className="attention-risk"
                        title={`Share of trained committee paths whose projected spend crosses ${k.name}'s remaining cap inside ${h}h.`}
                      >
                        ensemble paths <b>{fmtUsd(cum, 0)}</b> vs <b>{fmtUsd(r.remaining_usd, 0)}</b> cap ·
                        breach <b>{Math.round((p ?? 0) * 100)}%</b> / {h}h
                      </div>
                    )
                  })()}
                </a>
              ))}
            </div>
          </section>

          <section className="sheet">
            <div className="sheet-head">
              <div>
                <h2 className="sheet-title">Recent alerts</h2>
                <p className="sheet-sub">Pages, caps, and horizon warnings</p>
              </div>
              <span className="sheet-meta">{alerts.length} in window</span>
            </div>
            <div className="timeline">
              {alerts.length === 0 && (
                <EmptyState title="Quiet" detail="No alerts in the current window." />
              )}
              {alerts.map((a) => {
                const severity = a.severity === 'critical' ? 'critical' : a.severity === 'warning' ? 'warning' : 'info'
                return (
                  <div className="timeline-item" key={a.id}>
                    <div className="timeline-time">{timeAgo(a.ts)}</div>
                    <div className="timeline-rail">
                      <span className={`timeline-dot ${severity}`} />
                    </div>
                    <div>
                      <div className="timeline-title">{a.title}</div>
                      <div className="timeline-detail">{a.detail}</div>
                      <div className="timeline-meta">{a.kind.replaceAll('_', ' ')}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          </section>

          <section className="sheet">
            <div className="sheet-head">
              <div>
                <h2 className="sheet-title">Top models</h2>
                <p className="sheet-sub">Rolling 30 days</p>
              </div>
              <span className="sheet-meta">{topModels.length}</span>
            </div>
            {topModels.length === 0 ? (
              <EmptyState title="No usage yet" detail="Metered model spend will appear here." />
            ) : (
              <div className="table-wrap">
                <table className="table compact">
                  <thead>
                    <tr>
                      <th scope="col">Model</th>
                      <th scope="col" className="r">Cost</th>
                      <th scope="col" className="r">Requests</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topModels.map((m) => (
                      <tr key={m.model}>
                        <td className="mono strong">{String(m.model).split('/').pop()}</td>
                        <td className="r num">{fmtUsd(m.cost, 0)}</td>
                        <td className="r num">{m.requests}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </aside>
      </div>
    </div>
  )
}
