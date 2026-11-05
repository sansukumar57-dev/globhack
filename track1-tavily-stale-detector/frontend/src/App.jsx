import { useState } from 'react'
import './App.css'

const API_BASE = 'http://localhost:8000'

const EXAMPLES = [
  {
    label: '⚡ GPT-4 & Model Pricing',
    category: 'AI Pricing',
    text: 'GPT-4 costs $0.03 per 1K input tokens and $0.06 per 1K output tokens. It has a context window of 8,192 tokens. OpenAI was founded by Sam Altman and Elon Musk. The current CEO of OpenAI is Sam Altman.',
  },
  {
    label: '🏢 Big Tech & Leadership',
    category: 'Corporate',
    text: 'Sundar Pichai is the CEO of Google and Alphabet. Twitter was acquired by Elon Musk for $44 billion in 2022. Python 3.11 is the latest stable version of Python.',
  },
  {
    label: '🤖 Frontier AI & Branding',
    category: 'Models',
    text: "Claude 3 Opus is Anthropic's most capable model. Google's latest conversational AI model is called Bard. Meta's latest open weights model family is Llama 2 with 4096 context tokens.",
  },
  {
    label: '📦 Software Versions & EOL',
    category: 'Software',
    text: 'Python 2.7 is the active LTS release used in modern Linux servers. React 17 is the current version powering frontend web frameworks.',
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
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="claim-text">"{claim.claim}"</div>
          <div className="freshness-bar-wrap">
            <div className="freshness-bar-bg">
              <div
                className="freshness-bar-fill"
                style={{ width: `${claim.freshness_score}%`, background: color }}
              />
            </div>
            <span className="freshness-score-num" style={{ color }}>
              {claim.freshness_score}/100
            </span>
          </div>
        </div>
        <span className={`chevron ${open ? 'open' : ''}`}>▾</span>
      </div>

      {open && (
        <div className="claim-body">
          <hr className="divider" />

          <div className="detail-label">Staleness Analysis & Explanation</div>
          <div className="detail-value">{claim.explanation}</div>

          {claim.current_value && (
            <div className="current-value-box">
              🔄 <strong>Current Verified Fact:</strong> {claim.current_value}
            </div>
          )}

          {claim.staleness_reason && (
            <div style={{ marginBottom: '10px' }}>
              <div className="detail-label">Why this changes frequently</div>
              <div className="detail-muted">{claim.staleness_reason}</div>
            </div>
          )}

          {claim.sources && claim.sources.length > 0 && (
            <>
              <div className="detail-label" style={{ marginBottom: '8px' }}>
                Live Grounding Sources ({claim.sources.length})
              </div>
              <div className="sources-list">
                {claim.sources.map((s, i) => (
                  <div className="source-item" key={i}>
                    <div className="source-title">{s.title || 'Live Web Source'}</div>
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
                        <span className="source-date">📅 {s.published_date}</span>
                      )}
                    </div>
                    {s.content && (
                      <div className="source-snippet">
                        {s.content.slice(0, 220)}…
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
  const verdictLabel = data.overall_freshness >= 75 ? 'FRESH' : data.overall_freshness >= 45 ? 'CAUTION' : 'STALE'
  
  return (
    <div className="summary-grid">
      <div className="stat-card main-stat">
        <div className="stat-number" style={{ color: scoreColor }}>
          {data.overall_freshness}
        </div>
        <div className="stat-label">Freshness Index ({verdictLabel})</div>
      </div>
      <div className="stat-card">
        <div className="stat-number color-accent">{data.total_claims}</div>
        <div className="stat-label">Claims Audited</div>
      </div>
      <div className="stat-card">
        <div className="stat-number color-fresh">{data.fresh_count}</div>
        <div className="stat-label">Verified Fresh</div>
      </div>
      <div className="stat-card">
        <div className="stat-number color-stale">{data.stale_count}</div>
        <div className="stat-label">Outdated / Stale</div>
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
  const [activeTab, setActiveTab] = useState('claims')
  const [filterVerdict, setFilterVerdict] = useState('ALL')
  const [copied, setCopied] = useState(false)

  async function handleAnalyze() {
    if (!text.trim()) return
    setLoading(true)
    setResult(null)
    setError(null)
    setLoadStep(0)

    const steps = [0, 1, 2]
    let i = 0
    const interval = setInterval(() => {
      i++
      if (i < steps.length) setLoadStep(i)
    }, 1200)

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

  function handleCopyReport() {
    if (!result?.markdown_report) return
    navigator.clipboard.writeText(result.markdown_report)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  function handleDownloadReport() {
    if (!result?.markdown_report) return
    const blob = new Blob([result.markdown_report], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `stale-detection-report-${Date.now()}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const filteredClaims = result?.claims?.filter(c => {
    if (filterVerdict === 'ALL') return true
    return c.verdict === filterVerdict
  }) || []

  return (
    <div className="app">
      <header className="header">
        <div className="header-badges">
          <span className="header-badge">⚡ Tavily Search API</span>
          <span className="header-badge-alt">🧠 Nebius / OpenRouter / Groq</span>
          <span className="header-badge-hack">🏆 Geek Room AI Global Hackathon</span>
        </div>
        <h1>Stale-Answer<br />Detector</h1>
        <p>
          Real-time autonomous verification layer for LLM outputs. Extracts atomic factual claims,
          cross-references the live web via <strong>Tavily Search API</strong>, and calculates a precision <strong>Freshness Index</strong> with automated corrections.
        </p>
      </header>

      {/* Input Card */}
      <div className="card input-card">
        <div className="input-header-row">
          <div className="input-label">
            <span className="dot" />
            Input Text / LLM Response
          </div>
          <span className="char-count">{text.length} chars</span>
        </div>
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder="e.g. GPT-4 costs $0.03 per 1K input tokens. Python 2.7 is the latest version. Sam Altman is the CEO of OpenAI..."
          disabled={loading}
        />
        <div className="examples">
          <span className="examples-tag">Quick Benchmarks:</span>
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
              <div className="spinner-btn" />
              Verifying Against Live Web…
            </>
          ) : (
            '🔍 Audit Claims & Detect Staleness'
          )}
        </button>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="card loading-section">
          <div className="spinner" />
          <div className="loading-title">Auditing Knowledge Freshness in Real-Time…</div>
          <div className="loading-sub">
            {loadStep === 0 && '🧠 Step 1: Decomposing answer into atomic verifiable factual claims…'}
            {loadStep === 1 && '🔍 Step 2: Querying Tavily Search API concurrently for live web ground truth…'}
            {loadStep === 2 && '📊 Step 3: Scoring staleness, extracting citations, and generating corrected facts…'}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="error-box">
          <strong>⚠ Verification Error:</strong> {error}
          <div style={{ marginTop: '6px', fontSize: '0.82rem', opacity: 0.9 }}>
            Make sure your backend server is running on <code>http://localhost:8000</code>.
          </div>
        </div>
      )}

      {/* Results Section */}
      {result && !loading && (
        <>
          <SummaryStats data={result} />

          {/* Navigation Tabs */}
          <div className="tabs-header">
            <button
              className={`tab-btn ${activeTab === 'claims' ? 'active' : ''}`}
              onClick={() => setActiveTab('claims')}
            >
              🔬 Claims Breakdown ({result.total_claims})
            </button>
            <button
              className={`tab-btn ${activeTab === 'diff' ? 'active' : ''}`}
              onClick={() => setActiveTab('diff')}
            >
              🔄 Before vs After (Corrected Text)
            </button>
            <button
              className={`tab-btn ${activeTab === 'report' ? 'active' : ''}`}
              onClick={() => setActiveTab('report')}
            >
              📄 Full Audit Dossier (Markdown)
            </button>
          </div>

          {/* TAB 1: Claims Breakdown */}
          {activeTab === 'claims' && (
            <div className="card tab-content">
              {result.total_claims === 0 ? (
                <div className="empty-state">
                  ✅ No verifiable factual claims detected in this text.
                </div>
              ) : (
                <>
                  <div className="claims-toolbar">
                    <span className="claims-title">
                      Factual Claims Audit
                    </span>
                    <div className="filter-group">
                      <button
                        className={`filter-btn ${filterVerdict === 'ALL' ? 'active' : ''}`}
                        onClick={() => setFilterVerdict('ALL')}
                      >
                        All ({result.total_claims})
                      </button>
                      <button
                        className={`filter-btn stale ${filterVerdict === 'STALE' ? 'active' : ''}`}
                        onClick={() => setFilterVerdict('STALE')}
                      >
                        Stale ({result.stale_count})
                      </button>
                      <button
                        className={`filter-btn fresh ${filterVerdict === 'FRESH' ? 'active' : ''}`}
                        onClick={() => setFilterVerdict('FRESH')}
                      >
                        Fresh ({result.fresh_count})
                      </button>
                    </div>
                  </div>

                  {filteredClaims.map((c, i) => (
                    <ClaimCard key={i} claim={c} />
                  ))}
                </>
              )}
            </div>
          )}

          {/* TAB 2: Before vs After Diff */}
          {activeTab === 'diff' && (
            <div className="card tab-content">
              <div className="claims-title" style={{ marginBottom: '1.2rem' }}>
                Reconstructed &amp; Corrected Response
              </div>
              <div className="diff-grid">
                <div className="diff-col original-box">
                  <div className="diff-label">Original Text (With Outdated Facts)</div>
                  <div className="diff-text original">{result.original_text}</div>
                </div>
                <div className="diff-col corrected-box">
                  <div className="diff-label">Corrected Text (Live Facts Injected)</div>
                  <div className="diff-text corrected">{result.corrected_text}</div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: Full Audit Dossier */}
          {activeTab === 'report' && (
            <div className="card tab-content">
              <div className="report-header-actions">
                <div className="claims-title">Publication-Ready Audit Report</div>
                <div className="report-btns">
                  <button className="export-btn" onClick={handleCopyReport}>
                    {copied ? '✓ Copied!' : '📋 Copy Markdown'}
                  </button>
                  <button className="export-btn primary" onClick={handleDownloadReport}>
                    💾 Download .md
                  </button>
                </div>
              </div>
              <pre className="report-pre">{result.markdown_report}</pre>
            </div>
          )}
        </>
      )}

      <footer className="footer">
        Built for the{' '}
        <a href="https://hackculture.io/hackathons/ai-global-hackathon" target="_blank" rel="noreferrer">
          Geek Room AI Global Hackathon
        </a>{' '}
        · Powered by{' '}
        <a href="https://tavily.com" target="_blank" rel="noreferrer">Tavily Search API</a> &amp;{' '}
        <a href="https://openrouter.ai" target="_blank" rel="noreferrer">OpenRouter / Nebius</a>
      </footer>
    </div>
  )
}
