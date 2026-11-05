import { ArrowUpRight, ChevronRight } from 'lucide-react'
import { AgentMark, Delta, Sparkline } from './ui.jsx'
import { fmtCost, fmtMs, fmtPct, fmtScore, scoreTone } from '../lib/format.js'

export default function Leaderboard({ agents = [], onSelectAgent, dense = false, compact = false }) {
  if (!agents.length) {
    return <p className="muted-copy">No agent results yet. Run the suite to establish a baseline.</p>
  }
  return (
    <div className="table-wrap leaderboard-wrap">
      <table className={`data-table leaderboard-table${dense ? ' dense' : ''}${compact ? ' compact' : ''}`}>
        <thead>
          <tr>
            <th className="col-rank">#</th>
            <th>Agent</th>
            <th className="col-score">Score</th>
            <th className="col-success">Task success</th>
            <th className="col-consistency">Consistency</th>
            {!compact && <th className="col-latency">p95</th>}
            {!compact && <th className="col-cost">Cost / task</th>}
            <th className="col-trend">Last 3 runs</th>
            <th className="col-open"><span className="sr-only">Open</span></th>
          </tr>
        </thead>
        <tbody>
          {agents.map((agent) => {
            const tone = scoreTone(agent.score)
            return (
              <tr
                key={agent.agent_id}
                className="leaderboard-row"
                onClick={() => onSelectAgent?.(agent.agent_id)}
              >
                <td className="col-rank">
                  <span className={`rank rank-${agent.rank}`}>{String(agent.rank).padStart(2, '0')}</span>
                </td>
                <td>
                  <div className="agent-cell">
                    <AgentMark agent={agent} />
                    <div className="agent-cell-copy">
                      <button
                        type="button"
                        className="agent-name-button"
                        onClick={(event) => { event.stopPropagation(); onSelectAgent?.(agent.agent_id) }}
                      >
                        {agent.name}
                      </button>
                      <span className="agent-sub">{agent.operator} <span>·</span> {agent.adapter}</span>
                    </div>
                  </div>
                </td>
                <td className="col-score">
                  <div className={`score-cell score-${tone}`}>
                    <span className="score-value">{fmtScore(agent.score)}</span>
                    <Delta value={agent.delta} compact />
                  </div>
                </td>
                <td className="col-success">
                  <span className="metric-inline">{fmtPct(agent.task_success)}</span>
                  <span className="metric-sub">{agent.passed}/{agent.total} passed</span>
                </td>
                <td className="col-consistency">
                  <span className="metric-inline">{fmtPct(agent.consistency)}</span>
                  <span className="metric-sub">across trials</span>
                </td>
                {!compact && (
                  <td className="col-latency">
                    <span className="metric-inline mono">{fmtMs(agent.p95_latency_ms)}</span>
                  </td>
                )}
                {!compact && (
                  <td className="col-cost">
                    <span className="metric-inline mono">{fmtCost(agent.cost_per_task)}</span>
                  </td>
                )}
                <td className="col-trend">
                  <Sparkline points={agent.history || []} color={agent.color} />
                </td>
                <td className="col-open">
                  <button
                    type="button"
                    className="icon-button row-open"
                    aria-label={`Open ${agent.name}`}
                    onClick={(event) => { event.stopPropagation(); onSelectAgent?.(agent.agent_id) }}
                  >
                    <ChevronRight size={16} />
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="table-note">
        <ArrowUpRight size={12} /> Composite score weights task success, policy, tools, consistency, safety and efficiency.
      </p>
    </div>
  )
}
