export function Meter({ value, max = 100, thick = false }) {
  const v = Math.max(0, Math.min(100, value ?? 0))
  const seg = v >= 80 ? 'seg-ok' : v >= 50 ? 'seg-warn' : 'seg-err'
  const rest = 100 - v
  const restSeg = rest >= 80 ? 'seg-err' : 'seg-warn'
  return (
    <div className={`meter${thick ? ' thick' : ''}`} title={`${v}/${max}`}>
      {v > 0 && <span className={seg} style={{ width: `${v}%` }} />}
      {rest > 0 && <span className={restSeg} style={{ width: `${rest}%`, opacity: 0.25 }} />}
    </div>
  )
}

export function RelNum({ value }) {
  const cls = value >= 80 ? 'ok' : value >= 50 ? '' : 'err'
  return <span className={`mono ${cls}`} style={{ fontWeight: 700 }}>{value ?? '—'}</span>
}

export function PassBadge({ passed }) {
  return <span className={`badge ${passed ? 'ok' : 'err'}`}>{passed ? 'PASS' : 'FAIL'}</span>
}

export function OutcomeBadge({ outcome }) {
  if (outcome === 'blocked') return <span className="badge ok">◱ BLOCKED</span>
  if (outcome === 'partial') return <span className="badge warn">◻ PARTIAL</span>
  return <span className="badge err">☖ COMPLIED</span>
}

export function ErrorView({ error }) {
  if (!error) return null
  return <div className="banner">⚠ {String(error)}</div>
}

export function Loading({ label = 'Loading…' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 9, color: 'var(--text-3)', padding: '18px 0' }}>
      <span className="spinner" /> <span className="small">{label}</span>
    </div>
  )
}

export function Empty({ children }) {
  return <div className="empty">{children}</div>
}

export function Stat({ k, v, d, cls }) {
  return (
    <div className="stat">
      <div className="k">{k}</div>
      <div className={`v ${cls || ''}`}>{v}</div>
      {d && <div className="d">{d}</div>}
    </div>
  )
}

const KIND_CLASS = { llm: 'accent', tool: 'cyan', fault: 'err', agent: 'purple', eval: 'ok' }
export function KindBadge({ kind }) {
  return <span className={`badge ${KIND_CLASS[kind] || 'muted'}`}>{kind}</span>
}

export function JudgeScores({ judge }) {
  if (!judge?.available || !judge?.scores) {
    return <div className="small faint" style={{ padding: '6px 0' }}>LLM judge unavailable — deterministic checks only.</div>
  }
  const cells = [
    ['task', judge.scores.task_success],
    ['resilience', judge.scores.resilience],
    ['honesty', judge.scores.honesty],
    ['efficiency', judge.scores.efficiency],
  ]
  return (
    <div>
      <div className="judge-grid">
        {cells.map(([k, v]) => (
          <div className="judge-cell" key={k}>
            <div className="k">{k}</div>
            <div className="v">{v}<span className="faint" style={{ fontSize: 11 }}>/10</span></div>
            <Meter value={v * 10} />
          </div>
        ))}
      </div>
      {judge.rationale && <div className="small muted" style={{ marginTop: 9, fontFamily: 'var(--mono)' }}>“{judge.rationale}”</div>}
      {judge.violations?.length > 0 && (
        <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {judge.violations.map((v, i) => <span key={i} className="badge err">{v}</span>)}
        </div>
      )}
    </div>
  )
}

export function ChecksList({ checks }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      {checks.map((c, i) => (
        <div key={i} style={{ display: 'flex', gap: 9, alignItems: 'baseline', fontSize: 12 }}>
          <span className={`badge ${c.passed ? 'ok' : 'err'}`} style={{ flex: '0 0 auto' }}>{c.passed ? '✓' : '✕'}</span>
          <span className="mono" style={{ color: 'var(--text)', flex: '0 0 auto' }}>{c.type}</span>
          <span className="small" style={{ color: 'var(--text-3)' }}>{c.detail}</span>
        </div>
      ))}
    </div>
  )
}

export function Waterfall({ trace }) {
  if (!trace?.spans?.length) return <div className="small faint">No spans captured.</div>
  const spans = [...trace.spans]
  const spanTotal = Math.max(trace.total_ms, ...spans.map(s => (s.t_rel_ms || 0) + (s.duration_ms || 0)), 1)
  return (
    <div className="wf">
      <div className="wf-row wf-ruler" style={{ display: 'grid' }}>
        <span>SPAN</span><span>{spanTotal >= 60000 ? `${Math.round(spanTotal / 60000)}m` : `${Math.round(spanTotal / 1000)}s window`}</span><span style={{ textAlign: 'right' }}>DUR</span>
      </div>
      {spans.map((s) => {
        const left = ((s.t_rel_ms || 0) / spanTotal) * 100
        const width = Math.max(0.6, ((s.duration_ms || 40) / spanTotal) * 100)
        return (
          <div className="wf-row" key={s.id}>
            <div className="wf-name" title={`${s.name} [${s.kind}]${s.error ? ' — ' + s.error : ''}`}>
              {s.meta?.retries > 0 && <span style={{ color: 'var(--warn)' }}>↻</span>} <b>{s.name}</b>
            </div>
            <div className="wf-track">
              <div
                className={`wf-bar ok-k-${s.kind}`}
                style={{
                  left: `${left}%`,
                  width: `${width}%`,
                  opacity: s.status === 'error' ? 1 : 0.85,
                  outline: s.status === 'error' ? '1px solid var(--err)' : s.status === 'warn' ? '1px dashed var(--warn)' : 'none',
                }}
                title={`${s.name} · ${s.duration_ms}ms · ${s.status}${s.error ? ' · ' + s.error : ''}`}
              />
            </div>
            <div className="wf-dur" style={s.status === 'error' ? { color: 'var(--err)' } : {}}>
              {s.duration_ms >= 60000 ? `${(s.duration_ms / 60000).toFixed(1)}m` : `${s.duration_ms}ms`}
            </div>
          </div>
        )
      })}
    </div>
  )
}
