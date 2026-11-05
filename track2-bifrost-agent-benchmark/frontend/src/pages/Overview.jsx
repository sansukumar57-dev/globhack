import {
  ArrowRight,
  ArrowUpRight,
  Clock3,
  Coins,
  ShieldAlert,
  Target,
} from 'lucide-react'
import Leaderboard from '../components/Leaderboard.jsx'
import {
  Delta,
  Eyebrow,
  ProgressBar,
  ScoreRing,
  SectionHeading,
  StatusPill,
} from '../components/ui.jsx'
import { fmtCost, fmtDate, fmtMs, fmtPct, fmtScore, scoreTone, timeAgo } from '../lib/format.js'

export default function Overview({
  health,
  leaderboard,
  suite,
  failures,
  onRun,
  onOpenAgent,
  onOpenRun,
  onOpenSuite,
}) {
  const agents = leaderboard?.agents || []
  const run = leaderboard?.run
  const summary = run?.summary
  const best = agents[0]
  const bestTone = scoreTone(best?.score)
  const total = summary?.total_executions || 0
  const passed = Math.round(((summary?.pass_rate || 0) / 100) * total)
  const avgCost = total ? (summary?.total_cost_usd || 0) / total : 0
  const topFailure = summary?.top_signatures?.[0]
  const failureList = (failures?.length ? failures : summary?.top_signatures || []).slice(0, 3)

  const categoryAverages = (suite?.categories || []).map((category) => {
    const values = agents
      .map((agent) => agent.category_scores?.find((item) => item.id === category.id)?.success)
      .filter((value) => typeof value === 'number')
    const average = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0
    return { ...category, average }
  })

  return (
    <div className="page overview-page">
      <section className="hero">
        <div className="hero-copy">
          <Eyebrow>Suite 03 · Commerce support</Eyebrow>
          <h1>The same 18 tasks.<br /><em>Every agent.</em></h1>
          <p className="hero-lede">
            Criterion runs support agents through real refunds, recoveries and safety escalations,
            then scores the work — not the model name behind it.
          </p>
          <div className="hero-actions">
            <button type="button" className="btn btn-primary" onClick={onRun}>
              Run a benchmark <ArrowRight size={16} />
            </button>
            <button type="button" className="text-button" onClick={onOpenSuite}>
              Inspect the suite <ArrowUpRight size={14} />
            </button>
          </div>
          <div className="hero-meta">
            <span><span className="live-dot" /> {health?.judge?.mode === 'deterministic-rubric' ? 'Deterministic sandbox' : 'Live judge'}</span>
            <span>·</span>
            <span>{health?.gateway?.configured ? 'Bifrost gateway connected' : 'Bifrost-ready'}</span>
            <span>·</span>
            <span>Last run {run ? timeAgo(run.created_at) : '—'}</span>
          </div>
        </div>

        <aside className="latest-card">
          <div className="latest-card-top">
            <span className="mono-label"><span className="live-dot" /> Latest benchmark</span>
            {run && <StatusPill status={run.status} />}
          </div>
          {best ? (
            <>
              <div className="latest-winner">
                <ScoreRing
                  value={best.score}
                  size={124}
                  label="best composite"
                  color={bestTone === 'good' ? '#2F7D5B' : bestTone === 'ok' ? '#B7791F' : '#C23B2A'}
                />
                <div className="latest-winner-copy">
                  <span className="latest-winner-kicker">Top agent</span>
                  <h2>{best.name}</h2>
                  <p>{best.operator}</p>
                  <div className="latest-winner-delta">
                    <Delta value={best.delta} />
                    <span>vs previous run</span>
                  </div>
                </div>
              </div>
              <div className="latest-card-stats">
                <div><span>Pass rate</span><strong>{fmtPct(summary?.pass_rate)}</strong></div>
                <div><span>Task runs</span><strong>{total}</strong></div>
                <div><span>Duration</span><strong>{fmtMs(summary?.duration_ms)}</strong></div>
              </div>
              <button type="button" className="latest-card-link" onClick={() => onOpenRun(run.id)}>
                Open run {run.id.replace('run-', '')} <ArrowRight size={14} />
              </button>
            </>
          ) : (
            <p className="muted-copy">No completed benchmark yet.</p>
          )}
        </aside>
      </section>

      <section className="kpi-strip" aria-label="Latest benchmark summary">
        <div className="kpi">
          <span className="kpi-label"><Target size={13} /> Best score</span>
          <span className="kpi-value">{fmtScore(best?.score)}<small>/100</small></span>
          <span className="kpi-sub">
            {best
              ? (typeof best.delta === 'number'
                ? `${best.name} · ${best.delta > 0 ? '+' : ''}${fmtScore(best.delta)} vs last run`
                : `${best.name} · first benchmark`)
              : '—'}
          </span>
        </div>
        <div className="kpi">
          <span className="kpi-label"><ShieldAlert size={13} /> Task pass rate</span>
          <span className="kpi-value">{fmtPct(summary?.pass_rate)}</span>
          <span className="kpi-sub">{passed} of {total} task runs passed</span>
        </div>
        <div className="kpi">
          <span className="kpi-label"><Coins size={13} /> Avg cost / task</span>
          <span className="kpi-value">{fmtCost(avgCost)}</span>
          <span className="kpi-sub">across {agents.length} agents</span>
        </div>
        <div className="kpi">
          <span className="kpi-label"><Clock3 size={13} /> Top failure</span>
          <span className="kpi-value kpi-value-text">{topFailure?.label || '—'}</span>
          <span className="kpi-sub">{topFailure ? `${topFailure.count} failed task runs` : 'No failures yet'}</span>
        </div>
      </section>

      <div className="overview-grid">
        <section className="panel leaderboard-panel">
          <SectionHeading
            title="Leaderboard"
            meta={`Latest run · ${run?.trials || 2} trials · ${total} task runs`}
            action={(
              <button type="button" className="text-button" onClick={() => onOpenRun(run?.id)} disabled={!run}>
                Open run <ArrowRight size={13} />
              </button>
            )}
          />
          <Leaderboard agents={agents} onSelectAgent={onOpenAgent} compact />
        </section>

        <div className="overview-side">
          <section className="panel side-panel">
            <SectionHeading
              title="Failure signals"
              meta={topFailure ? `${topFailure.count} failed runs cluster here` : 'No failures in the latest run'}
            />
            <div className="failure-signal-list">
              {failureList.length === 0 && <p className="muted-copy">Every check passed. Try a harder suite.</p>}
              {failureList.map((failure) => {
                const max = failureList[0]?.count || 1
                return (
                  <div className="failure-signal" key={failure.id}>
                    <div className="failure-signal-head">
                      <span className="failure-signal-name">
                        <span className="failure-dot" style={{ background: failure.color }} />
                        {failure.label}
                      </span>
                      <span className="failure-signal-count">{failure.count}</span>
                    </div>
                    <ProgressBar value={(failure.count / max) * 100} tone="danger" height={4} />
                  </div>
                )
              })}
            </div>
            <button type="button" className="text-button side-link" onClick={() => onOpenRun(run?.id)} disabled={!run}>
              See the failing traces <ArrowRight size={13} />
            </button>
          </section>

          <section className="panel side-panel">
            <SectionHeading title="Suite coverage" meta={`${suite?.task_count || 18} tasks across 4 categories`} />
            <div className="coverage-list">
              {categoryAverages.map((category) => (
                <div className="coverage-row" key={category.id}>
                  <div className="coverage-copy">
                    <span>{category.name}</span>
                    <small>{fmtPct(category.average, 0)} avg success</small>
                  </div>
                  <ProgressBar value={category.average} tone="accent" height={5} />
                </div>
              ))}
            </div>
            <button type="button" className="text-button side-link" onClick={onOpenSuite}>
              Inspect all tasks <ArrowRight size={13} />
            </button>
          </section>
        </div>
      </div>

      {run && (
        <p className="page-footnote">
          <span className="live-dot" /> Run {run.id} completed {fmtDate(run.completed_at)}.
          Reference agents run in a deterministic sandbox; connect a live HTTP adapter to benchmark your own agent.
        </p>
      )}
    </div>
  )
}
