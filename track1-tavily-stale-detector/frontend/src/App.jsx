import { useState } from 'react'
import './App.css'

const API_BASE = 'http://localhost:8000'

const EXAMPLES = [
  {
    label: 'GPT-4 pricing',
    text: 'GPT-4 costs $0.03 per 1K input tokens and $0.06 per 1K output tokens. It has a context window of 8,192 tokens. OpenAI was founded by Sam Altman and Elon Musk. The current CEO of OpenAI is Sam Altman.',
  },
  {
    label: 'Tech leadership',
    text: 'Sundar Pichai is the CEO of Google and Alphabet. Twitter was acquired by Elon Musk for $44 billion in 2022. Microsoft has a market cap of over $2 trillion. Python 3.11 is the latest stable version of Python.',
  },
  {
    label: 'AI Models',
    text: 'Claude 3 Opus is Anthropic\'s most capable model. GPT-4 is OpenAI\'s flagship model. The Llama 2 model from Meta supports context lengths up to 4096 tokens. Google\'s latest model is called Bard.',
  },
]

function getFreshnessColor(score) {
  if (score >= 75) return 'var(--fresh)'
  if (score >= 45) return 'var(--warn)'
  return 'var(--stale)'
}

function ClaimCard({ claim }) {
  const [open, setOpen] = useState(false)
  const color = getFreshnessColor(claim.freshness_score)

  return (
    <div className={`claim-card ${claim.verdict}`}>
      <div className="claim-header" onClick={() => setOpen(o => !o)}>
        <span className={`verdict-badge ${claim.verdict}`}>
          {claim.verdict === 'FRESH' ? '✓' : claim.verdict === 'STALE' ? '⚠' : '?'}
          {' '}{claim.verdict}
        </span>
        <div style={{ flex: 1 }}>
          <div className="claim-text">"{claim.claim}"</div>
          <div className="freshness-bar-wrap">
            <div className="freshness-bar-bg">
              <div
                className="freshness-bar-fill"
                style={{ width: `${claim.freshness_score}%`, background: color }}
              />
            </div>
            <span className="freshness-score-num" style={{ color }}>
              {claim.freshness_score}
            </span>
          </div>
        </div>
        <span className={`chevron ${open ? 'open' : ''}`}>▾</span>
      </div>

      {open && (
        <div className="claim-body">
          <hr className="divider" />

          <div className="detail-label">Explanation</div>
          <div className="detail-value">{claim.explanation}</div>

          {claim.staleness_reason && (
            <>
              <div className="detail-label">Why it might be stale</div>
              <div className="detail-muted">{claim.staleness_reason}</div>
            </>
          )}

          {claim.current_value && (
            <div className="current-value-box">
              🔄 <strong>Current value:</strong> {claim.current_value}
            </div>
          )}

          {claim.sources.length > 0 && (
            <>
              <div className="detail-label" style={{ marginBottom: '8px' }}>
                Live Sources ({claim.sources.length})
              </div>
              <div className="sources-list">
                {claim.sources.map((s, i) => (
                  <div className="source-item" key={i}>
                    <div className="source-title">{s.title || 'Untitled'}</div>
                    <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                      <a
                        href={s.url}
                        target="_blank"
                        rel="noreferrer"
                        className="source-url"
                      >
                        {s.url}
                      </a>
                      {s.published_date && (
                        <span className="source-date">{s.published_date}</span>
                      )}
                    </div>
                    {s.content && (
                      <div className="source-snippet">
                        {s.content.slice(0, 200)}…
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function SummaryStats({ data }) {
  const scoreColor = getFreshnessColor(data.overall_freshness)
  return (
    <div className="summary-grid">
      <div className="stat-card">
        <div className="stat-number" style={{ color: scoreColor }}>
          {data.overall_freshness}
        </div>
        <div className="stat-label">Freshness Score</div>
      </div>
      <div className="stat-card">
        <div className="stat-number color-accent">{data.total_claims}</div>
        <div className="stat-label">Claims Found</div>
      </div>
      <div className="stat-card">
        <div className="stat-number color-fresh">{data.fresh_count}</div>
        <div className="stat-label">Fresh</div>
      </div>
      <div className="stat-card">
        <div className="stat-number color-stale">{data.stale_count}</div>
        <div className="stat-label">Stale</div>
      </div>
      <div className="stat-card">
        <div className="stat-number color-muted">{data.unverifiable_count}</div>
        <div className="stat-label">Unverifiable</div>
      </div>
    </div>
  )
}

export default function App() {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loadStep, setLoadStep] = useState(0)

  async function handleAnalyze() {
    if (!text.trim()) return
    setLoading(true)
    setResult(null)
    setError(null)
    setLoadStep(0)

    // Animate loading steps
    const steps = [0, 1, 2]
    let i = 0
    const interval = setInterval(() => {
      i++
      if (i < steps.length) setLoadStep(i)
    }, 2000)

    try {
      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Server error')
      }
      const data = await res.json()
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      clearInterval(interval)
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-badge">
          ⚡ Tavily × Nebius — AI Global Hackathon
        </div>
        <h1>Stale Answer<br />Detector</h1>
        <p>
          Paste any LLM-generated answer. We'll extract every factual claim,
          search live sources, and give each one a <strong>freshness score</strong>.
        </p>
      </header>

      {/* Input Card */}
      <div className="card">
        <div className="input-label">
          <span className="dot" />
          Paste LLM Answer
        </div>
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder="e.g. GPT-4 costs $0.03 per 1K tokens. Sam Altman is the CEO of OpenAI. Python 3.11 is the latest version..."
          disabled={loading}
        />
        <div className="examples">
          <span style={{ fontSize: '0.78rem', color: 'var(--muted)', alignSelf: 'center' }}>Try:</span>
          {EXAMPLES.map(ex => (
            <button
              key={ex.label}
              className="example-btn"
              onClick={() => setText(ex.text)}
              disabled={loading}
            >
              {ex.label}
            </button>
          ))}
        </div>
        <button
          className="submit-btn"
          onClick={handleAnalyze}
          disabled={loading || !text.trim()}
        >
          {loading ? (
            <>
              <div className="spinner" style={{ width: 18, height: 18, margin: 0, borderWidth: 2 }} />
              Analyzing…
            </>
          ) : (
            '🔍 Detect Stale Claims'
          )}
        </button>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="card loading-section">
          <div className="spinner" />
          <div className="loading-title">Verifying claims in real-time…</div>
          <div className="loading-sub" style={{ marginTop: 8 }}>
            {loadStep === 0 && '🧠 Extracting factual claims with LLM…'}
            {loadStep === 1 && '🔍 Searching live web sources via Tavily…'}
            {loadStep === 2 && '📊 Scoring freshness per claim…'}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="error-box">⚠ Error: {error}</div>
      )}

      {/* Results */}
      {result && !loading && (
        <>
          <SummaryStats data={result} />

          <div className="card">
            {result.total_claims === 0 ? (
              <div className="empty-state">
                ✅ No verifiable factual claims found in this text.
              </div>
            ) : (
              <>
                <div className="claims-title">
                  🔬 Claims Analysis
                  <span style={{ fontSize: '0.8rem', color: 'var(--muted)', fontWeight: 400 }}>
                    — click a claim to expand
                  </span>
                </div>
                {result.claims.map((c, i) => (
                  <ClaimCard key={i} claim={c} />
                ))}
              </>
            )}
          </div>
        </>
      )}

      <footer className="footer">
        Built for the{' '}
        <a href="https://hackculture.io/hackathons/ai-global-hackathon" target="_blank" rel="noreferrer">
          AI Global Hackathon
        </a>{' '}
        · Powered by{' '}
        <a href="https://tavily.com" target="_blank" rel="noreferrer">Tavily</a> &amp;{' '}
        <a href="https://nebius.com" target="_blank" rel="noreferrer">Nebius</a>
      </footer>
    </div>
  )
}
