import { Bot, CheckCircle2, ExternalLink, Wrench } from 'lucide-react'
import { Drawer } from './Dialog.jsx'
import { AgentMark, CheckMark, StatusPill } from './ui.jsx'
import { FAILURE_LABELS } from '../lib/constants.js'
import { fmtCost, fmtMs, fmtScore, statusLabel } from '../lib/format.js'

const KIND_LABEL = {
  agent: 'agent',
  tool: 'tool',
  judge: 'judge',
}

export default function ResultDrawer({ open, result, task, agent, onClose, onOpenAgent }) {
  if (!result) return null
  const failure = result.failure_signature ? FAILURE_LABELS[result.failure_signature] : null
  const total = Math.max(1, ...result.trace.map((span) => span.start_ms + span.duration_ms))
  return (
    <Drawer
      open={open}
      onClose={onClose}
      eyebrow={`${task ? `Task ${String(task.number).padStart(2, '0')}` : 'Task'} · Trial ${result.trial}`}
      title={task?.title || result.task_id}
      subtitle={agent ? `${agent.name} · ${agent.adapter}` : result.agent_id}
      footer={agent ? (
        <>
          <button type="button" className="btn btn-secondary" onClick={() => onOpenAgent?.(agent.agent_id || agent.id)}>
            <Bot size={15} /> Open agent
          </button>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </>
      ) : null}
    >
      <div className="result-head">
        <div className="result-head-main">
          {agent && <AgentMark agent={agent} size="md" />}
          <div>
            <div className="result-status-line">
              <StatusPill status={result.status} label={statusLabel(result.status)} />
              {failure && <span className="failure-tag" style={{ '--failure-color': failure.color }}>{failure.label}</span>}
            </div>
            <p className="result-score-line">
              <strong>{fmtScore(result.score)}</strong> / 100 checks
              <span>·</span>
              {result.checks.filter((check) => check.passed).length}/{result.checks.length} passed
            </p>
          </div>
        </div>
        <div className="result-quick-stats">
          <div><span>Latency</span><strong>{fmtMs(result.latency_ms)}</strong></div>
          <div><span>Tokens</span><strong>{result.tokens?.toLocaleString() || '—'}</strong></div>
          <div><span>Cost</span><strong>{fmtCost(result.cost_usd)}</strong></div>
        </div>
      </div>

      <div className="drawer-section">
        <div className="drawer-section-head"><h3>Checks</h3><span className="mono-label">deterministic</span></div>
        <div className="result-check-list">
          {result.checks.map((check) => (
            <div className={`result-check${check.passed ? ' passed' : ' failed'}`} key={check.id}>
              <CheckMark passed={check.passed} />
              <span>{check.label}</span>
              <span className={`check-kind kind-${check.kind}`}>{check.kind}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="drawer-section">
        <div className="drawer-section-head"><h3>Agent answer</h3><span className="mono-label">verbatim</span></div>
        <blockquote className={`agent-answer${result.status === 'passed' ? '' : ' answer-failed'}`}>
          {result.answer}
        </blockquote>
      </div>

      <div className="drawer-section">
        <div className="drawer-section-head"><h3>Tool calls</h3><span className="mono-label">{result.tool_calls?.length || 0} calls</span></div>
        {result.tool_calls?.length ? (
          <div className="tool-call-list">
            {result.tool_calls.map((call, index) => (
              <div className="tool-call" key={`${call.tool}-${index}`}>
                <Wrench size={13} />
                <code>{call.tool}</code>
                <span className={`tool-status tool-${call.status}`}>{call.status}</span>
                <span className="tool-latency">{fmtMs(call.latency_ms)}</span>
              </div>
            ))}
          </div>
        ) : <p className="muted-copy">No tool calls were recorded.</p>}
      </div>

      <div className="drawer-section">
        <div className="drawer-section-head"><h3>Trace</h3><span className="mono-label">{fmtMs(total)} end to end</span></div>
        <div className="trace">
          {result.trace.map((span, index) => {
            const left = (span.start_ms / total) * 100
            const width = Math.max(2, (span.duration_ms / total) * 100)
            return (
              <div className="trace-row" key={`${span.name}-${index}`}>
                <div className="trace-meta">
                  <span className={`trace-kind trace-${span.kind}`}>{KIND_LABEL[span.kind] || span.kind}</span>
                  <span className="trace-name">{span.name}</span>
                  <span className="trace-duration">{fmtMs(span.duration_ms)}</span>
                </div>
                <div className="trace-track">
                  <span
                    className={`trace-span trace-span-${span.kind}${span.status === 'error' ? ' trace-span-error' : ''}`}
                    style={{ left: `${left}%`, width: `${width}%` }}
                    title={span.detail}
                  />
                </div>
                {span.status === 'error' && <span className="trace-detail">{span.detail}</span>}
              </div>
            )
          })}
        </div>
      </div>

      <div className="drawer-note">
        <CheckCircle2 size={14} />
        <span>Checks are deterministic. The same task, context and policy produce the same verdict every time.</span>
        {agent && <ExternalLink size={13} />}
      </div>
    </Drawer>
  )
}
