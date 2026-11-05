import { ArrowRight, Bot, Cable, Play, Plus, Radio, Terminal } from 'lucide-react'
import { AgentMark, Delta, EmptyState, Eyebrow, Sparkline, StatusPill } from '../components/ui.jsx'
import { fmtScore, scoreTone } from '../lib/format.js'

export default function Agents({ agents = [], adapters = [], onConnect, onOpenAgent, onRunAgent }) {
  return (
    <div className="page agents-page">
      <header className="page-head">
        <div>
          <Eyebrow>Agent registry</Eyebrow>
          <h1>Benchmark the agent,<br /><em>not the model.</em></h1>
          <p className="page-lede">
            Same tasks, same checks, whatever framework is underneath. Bring a Bifrost gateway, a LangGraph graph, a CrewAI crew or a plain HTTP endpoint.
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={onConnect}>
          <Plus size={15} /> Connect agent
        </button>
      </header>

      <div className="registry-summary">
        <div><span className="mono-label">Registered</span><strong>{agents.length}</strong><small>agents</small></div>
        <div><span className="mono-label">Adapters</span><strong>{adapters.length}</strong><small>supported</small></div>
        <div><span className="mono-label">Reference mode</span><strong>Sandbox</strong><small>deterministic</small></div>
        <div><span className="mono-label">Live traffic</span><strong>{agents.filter((agent) => agent.mode === 'live').length}</strong><small>endpoints</small></div>
      </div>

      {agents.length === 0 ? (
        <div className="panel"><EmptyState icon={Bot} title="No agents registered" body="Connect your first agent to establish a baseline." action={<button type="button" className="btn btn-secondary" onClick={onConnect}>Connect agent</button>} /></div>
      ) : (
        <div className="agent-card-grid">
          {agents.map((agent) => {
            const tone = scoreTone(agent.score)
            return (
              <article className="agent-card" key={agent.id}>
                <div className="agent-card-top">
                  <AgentMark agent={agent} size="md" />
                  <div className="agent-card-identity">
                    <h2>{agent.name}</h2>
                    <p>{agent.operator}</p>
                  </div>
                  <span className={`mode-tag mode-${agent.mode}`}>{agent.mode}</span>
                </div>
                <p className="agent-card-desc">{agent.description}</p>
                <div className="agent-card-score">
                  <div>
                    <span className={`score-tone score-${tone}`}>{agent.score === null ? '—' : fmtScore(agent.score)}</span>
                    <span className="score-denom">/100</span>
                    {agent.delta !== null && <Delta value={agent.delta} />}
                  </div>
                  <Sparkline points={agent.history || []} color={agent.color} width={110} height={30} />
                </div>
                <div className="agent-card-meta">
                  <span><Cable size={13} /> {agent.adapter}</span>
                  <span className="mono-label">{agent.run_count} run{agent.run_count === 1 ? '' : 's'}</span>
                </div>
                <div className="agent-card-tags">
                  {(agent.strengths || []).slice(0, 2).map((item) => <span className="tag" key={item}>{item}</span>)}
                  {(agent.watchouts || []).slice(0, 1).map((item) => <span className="tag tag-warn" key={item}>{item}</span>)}
                </div>
                <div className="agent-card-foot">
                  <button type="button" className="text-button" onClick={() => onOpenAgent(agent.id)}>
                    View profile <ArrowRight size={13} />
                  </button>
                  <button type="button" className="btn btn-secondary btn-small" onClick={() => onRunAgent(agent.id)}>
                    <Play size={13} /> Run
                  </button>
                </div>
              </article>
            )
          })}
        </div>
      )}

      <section className="panel adapters-panel">
        <div className="panel-heading-row">
          <div>
            <h2>Adapters</h2>
            <p>One task contract. Any agent framework. Live traffic can route through Bifrost.</p>
          </div>
          <span className="adapter-chip"><Radio size={13} /> Bifrost-ready</span>
        </div>
        <div className="adapter-list">
          {adapters.map((adapter) => (
            <div className="adapter-row" key={adapter.id}>
              <span className="adapter-icon"><Terminal size={15} /></span>
              <div className="adapter-copy">
                <strong>{adapter.name}</strong>
                <span>{adapter.description}</span>
              </div>
              <span className="adapter-kind">{adapter.kind}</span>
              <code>{adapter.contract}</code>
              <StatusPill status="complete" label="Ready" />
            </div>
          ))}
        </div>
        <div className="adapter-note">
          <span className="mono-label">Adapter contract</span>
          <p>
            Criterion sends one task per request and expects an answer, optional tool calls and check verdicts.
            Return <code>checks</code> for exact scoring; otherwise the platform falls back to a similarity rubric.
          </p>
        </div>
      </section>

      <p className="page-footnote">
        <Radio size={12} /> Sandbox agents use deterministic reference profiles. Live agents call the endpoint you register.
      </p>
    </div>
  )
}
