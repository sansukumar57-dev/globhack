import { useCallback, useEffect, useState } from 'react'
import { api, fmtTs, fmtUsd, timeAgo } from '../api'
import { EmptyState, Loading, PageHeader, monogram } from '../components/ui'

export default function Anomalies({ refreshKey }) {
  const [data, setData] = useState({ anomalies: [], threshold: 3.5, window_days: 7 })
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      setData(await api.anomalies())
    } catch {
      /* the top bar surfaces connectivity */
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load, refreshKey])

  const header = (
    <PageHeader
      eyebrow="Detection · 03"
      title={<>Outliers,{' '}<em>in context</em>.</>}
      lede="Same-hour baselines separate a real spike from a busy Tuesday. The forecast layer handles drift; this layer catches the step change."
    />
  )

  if (loading) {
    return (
      <div className="page">
        {header}
        <Loading label="Scanning hourly buckets…" />
      </div>
    )
  }

  const anomalies = data.anomalies || []

  return (
    <div className="page">
      {header}

      <div className="tape three">
        <div className="tape-cell">
          <div className="tape-label">Flagged buckets</div>
          <div className="tape-value">{anomalies.length}</div>
          <div className="tape-context">trailing {data.window_days} days</div>
        </div>
        <div className="tape-cell">
          <div className="tape-label">Threshold</div>
          <div className="tape-value">z ≥ {data.threshold}</div>
          <div className="tape-context">robust median / MAD</div>
        </div>
        <div className="tape-cell">
          <div className="tape-label">Baseline</div>
          <div className="tape-value">21 days</div>
          <div className="tape-context">same hour of day, per key</div>
        </div>
      </div>

      <section className="sheet">
        <div className="sheet-head">
          <div>
            <h2 className="sheet-title">Traffic anomalies</h2>
            <p className="sheet-sub">Same hour-of-day robust z · flagged in the trailing {data.window_days} days</p>
          </div>
          <span className="sheet-meta">{anomalies.length} flagged</span>
        </div>

        {anomalies.length === 0 ? (
          <EmptyState
            title="No outliers."
            detail="Every hourly bucket sits inside its expected same-hour envelope. The detector is still watching."
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Key</th>
                  <th scope="col" className="r">Hour cost</th>
                  <th scope="col" className="r">Baseline</th>
                  <th scope="col" className="r">Multiple</th>
                  <th scope="col" className="r">z-score</th>
                  <th scope="col" className="r"><span className="sr-only">Action</span></th>
                </tr>
              </thead>
              <tbody>
                {anomalies.map((a) => (
                  <tr key={`${a.vk}-${a.hour}`}>
                    <td>
                      <div className="strong">{timeAgo(a.hour)}</div>
                      <span className="sub">{fmtTs(a.hour)}</span>
                    </td>
                    <td>
                      <div className="key-id">
                        <span className="key-mark">{monogram(a.key_name)}</span>
                        <div>
                          <div className="key-name">{a.key_name}</div>
                          <div className="key-team">{a.team}</div>
                        </div>
                      </div>
                    </td>
                    <td className="r num strong">{fmtUsd(a.cost)}</td>
                    <td className="r num">{fmtUsd(a.baseline)}</td>
                    <td className="r"><span className="ratio">{a.ratio}×</span></td>
                    <td className="r"><span className="zscore">{a.z.toFixed(1)}σ</span></td>
                    <td className="r"><a className="btn-link" href="#keys">Inspect key →</a></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {(data.model_scores || []).length > 0 && (
        <section className="sheet">
          <div className="sheet-head">
            <div>
              <h2 className="sheet-title">Model residual scan</h2>
              <p className="sheet-sub">Trained expectation head · (actual − expected) / σ over the last 48h</p>
            </div>
            <span className="sheet-meta">residual σ = {data.model_sigma}</span>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Key</th>
                  <th scope="col" className="r">Hour cost</th>
                  <th scope="col" className="r">Model expected</th>
                  <th scope="col" className="r">Residual z</th>
                </tr>
              </thead>
              <tbody>
                {data.model_scores.map((s) => (
                  <tr key={`${s.vk}-${s.hour}`}>
                    <td>
                      <div className="strong">{timeAgo(s.hour)}</div>
                      <span className="sub">{fmtTs(s.hour)}</span>
                    </td>
                    <td>
                      <div className="key-id">
                        <span className="key-mark">{monogram(s.key_name || s.vk)}</span>
                        <div>
                          <div className="key-name">{s.key_name || s.vk}</div>
                          <div className="key-team">{s.team}</div>
                        </div>
                      </div>
                    </td>
                    <td className="r num strong">{fmtUsd(s.actual)}</td>
                    <td className="r num">{fmtUsd(s.expected)}</td>
                    <td className="r"><span className="zscore">{s.model_z.toFixed(1)}σ</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="sheet">
        <div className="sheet-head">
          <div>
            <h2 className="sheet-title">Method</h2>
            <p className="sheet-sub">Why a 2pm spike is judged against 2pms</p>
          </div>
          <span className="sheet-meta">median / MAD</span>
        </div>
        <div className="method">
          <div>
            <h3>How it detects</h3>
            <p>
              For every key and every hour, compare the bucket to the same hour-of-day across the
              trailing 21 days. The median is the baseline; the median absolute deviation is the
              spread. Business-hours traffic is judged against business-hours baselines, so an
              overnight median never hides a daytime spike.
            </p>
          </div>
          <div>
            <h3>What it catches</h3>
            <p>
              A sudden multiple of the expected hour is the signature of a runaway agent loop or a
              leaked credential. Gradual drift belongs to the forecast layer; this detector is for
              the step change. Flagged buckets are surfaced in the trailing {data.window_days} days
              at z ≥ {data.threshold}.
            </p>
          </div>
          <div>
            <h3>The trained eye</h3>
            <p>
              On top of the statistical pass, the trained expectation head predicts what this key
              should have spent given its recent shape, then scores the residual in units of its own
              validation error. Segments the robust z misses — drift that walked into the envelope —
              show up here first.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
