import { useState, useEffect } from 'react'
import './App.css'

const API_BASE = 'http://localhost:8001'

function App() {
  const [presets, setPresets] = useState([])
  const [selectedPresetId, setSelectedPresetId] = useState('')
  const [code, setCode] = useState('')
  const [prompt, setPrompt] = useState('')
  const [testCode, setTestCode] = useState('')
  const [compare, setCompare] = useState(true)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [activeTab, setActiveTab] = useState('patch')
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/presets`)
      .then(res => res.json())
      .then(data => {
        setPresets(data)
        if (data.length > 0) {
          selectPreset(data[0])
        }
      })
      .catch(err => {
        console.error('Failed to load presets:', err)
      })
  }, [])

  const selectPreset = (p) => {
    setSelectedPresetId(p.id)
    setCode(p.original_code)
    setPrompt(p.prompt)
    setTestCode(p.test_code || '')
    setResult(null)
    setError(null)
  }

  const handleRun = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/solve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          prompt,
          run_comparison: compare,
          test_code: testCode
        })
      })
      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Failed to execute agent')
      }
      const data = await res.json()
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const slim = result?.tokenslim
  const std = result?.standard
  const metrics = result?.metrics
  const verification = result?.verification

  const maxTokens = Math.max(metrics?.standard_total || 1, metrics?.tokenslim_total || 1, 100)
  const slimPct = Math.round(((metrics?.tokenslim_total || 0) / maxTokens) * 100)
  const stdPct = Math.round(((metrics?.standard_total || 0) / maxTokens) * 100)

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header">
        <div className="logo-group">
          <div className="logo-badge">⚡</div>
          <div>
            <h1 className="logo-title">TokenSlim</h1>
            <p className="logo-subtitle">Fewest-Tokens AI Coding Agent Architecture</p>
          </div>
        </div>
        <div className="track-badge">
          🛡️ Bifrost Priority Track — Problem Statement #01
        </div>
      </header>

      {/* Preset Benchmarks Selector */}
      <section className="presets-section">
        <div className="presets-label">Select Coding Challenge Benchmark:</div>
        <div className="presets-grid">
          {presets.map(p => (
            <div
              key={p.id}
              className={`preset-card ${selectedPresetId === p.id ? 'active' : ''}`}
              onClick={() => selectPreset(p)}
            >
              <div className="preset-card-title">{p.title}</div>
              <div className="preset-card-desc">{p.description}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Main Workspace */}
      <div className="main-grid">
        {/* Left: Input Code & Prompt */}
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">📝 Task & Source Code</h2>
          </div>

          <label className="input-label">CODING TASK INSTRUCTION:</label>
          <textarea
            className="prompt-textarea"
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            placeholder="Describe bug fix or feature..."
          />

          <label className="input-label">SOURCE CODE (BEFORE PRUNING):</label>
          <textarea
            className="code-textarea"
            value={code}
            onChange={e => setCode(e.target.value)}
            placeholder="Paste source code here..."
          />

          <div className="action-bar">
            <label className="compare-toggle">
              <input
                type="checkbox"
                checked={compare}
                onChange={e => setCompare(e.target.checked)}
              />
              Compare vs Standard Agent
            </label>

            <button
              className="solve-btn"
              onClick={handleRun}
              disabled={loading}
            >
              {loading ? 'Running Agent...' : '⚡ Solve with Fewest Tokens'}
            </button>
          </div>

          {error && (
            <div style={{ marginTop: 14, color: '#e74c3c', fontSize: 13 }}>
              ⚠️ {error}
            </div>
          )}
        </div>

        {/* Right: Output & Metrics */}
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">📊 Token Efficiency & Agent Output</h2>
          </div>

          {result ? (
            <div>
              {/* Metrics Cards */}
              <div className="metrics-grid">
                <div className="metric-card highlight">
                  <div className="metric-value savings">{metrics?.savings_percentage || 0}%</div>
                  <div className="metric-label">Token Savings</div>
                </div>
                <div className="metric-card">
                  <div className="metric-value">{slim?.total_tokens || 0}</div>
                  <div className="metric-label">TokenSlim Tokens</div>
                </div>
                {compare && (
                  <div className="metric-card">
                    <div className="metric-value">{std?.total_tokens || 0}</div>
                    <div className="metric-label">Standard Tokens</div>
                  </div>
                )}
                <div className="metric-card">
                  <div className="metric-value">{metrics?.speedup_factor || 1.0}x</div>
                  <div className="metric-label">Speedup</div>
                </div>
              </div>

              {/* Token Comparison Bar */}
              {compare && (
                <div className="token-comparison-box">
                  <div className="bar-row">
                    <span className="bar-label">TokenSlim</span>
                    <div className="bar-track">
                      <div className="bar-fill-slim" style={{ width: `${slimPct}%` }} />
                    </div>
                    <span className="bar-num">{slim?.total_tokens} tok</span>
                  </div>
                  <div className="bar-row">
                    <span className="bar-label">Standard</span>
                    <div className="bar-track">
                      <div className="bar-fill-std" style={{ width: `${stdPct}%` }} />
                    </div>
                    <span className="bar-num">{std?.total_tokens} tok</span>
                  </div>
                </div>
              )}

              {/* Verification Status */}
              {verification && (
                <div className={`test-box ${verification.test_passed ? 'passed' : 'failed'}`}>
                  <span>{verification.test_passed ? '✅ Unit Tests Passed' : '❌ Tests Failed'}</span>
                  <span style={{ fontSize: 12, opacity: 0.9 }}>{verification.test_output}</span>
                </div>
              )}

              {/* Inspector Tabs */}
              <div className="tabs-nav">
                <button
                  className={`tab-btn ${activeTab === 'patch' ? 'active' : ''}`}
                  onClick={() => setActiveTab('patch')}
                >
                  Applied Patch
                </button>
                <button
                  className={`tab-btn ${activeTab === 'skeleton' ? 'active' : ''}`}
                  onClick={() => setActiveTab('skeleton')}
                >
                  AST Pruned Skeleton
                </button>
                <button
                  className={`tab-btn ${activeTab === 'updated' ? 'active' : ''}`}
                  onClick={() => setActiveTab('updated')}
                >
                  Updated Full Code
                </button>
              </div>

              {/* Tab Contents */}
              {activeTab === 'patch' && (
                <pre className="code-viewer">{slim?.patch_text || 'No patch available.'}</pre>
              )}
              {activeTab === 'skeleton' && (
                <pre className="code-viewer">
                  {`# Target symbol: ${slim?.target_symbol || 'none'}\n# Pruned functions: ${slim?.ast_stats?.elided_functions_count || 0}\n\n${slim?.skeleton_code || ''}`}
                </pre>
              )}
              {activeTab === 'updated' && (
                <pre className="code-viewer">{slim?.updated_code || ''}</pre>
              )}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>⚡</div>
              <p style={{ fontWeight: 600, color: 'var(--text-main)', marginBottom: 6 }}>
                Ready to benchmark TokenSlim
              </p>
              <p style={{ fontSize: 13, maxWidth: 360, margin: '0 auto' }}>
                Select a coding challenge or write custom code, then click "Solve with Fewest Tokens" to inspect real-time AST pruning, search/replace patches, and token savings metrics.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default App
