import { useCallback, useEffect, useState } from 'react'
import { TrendingUp, ScanSearch, Radar } from 'lucide-react'
import { api, fmtUsd, fmtTs, timeAgo } from '../api'

export default function Anomalies({ refreshKey }) {
  const [data, setData] = useState({ anomalies: [], threshold: 3.5, window_days: 7 })

  const load = useCallback(async () => {
    try {
      setData(await api.anomalies())
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { load() }, [load, refreshKey])

  return (
    <div className="panel panel-pad">
      <div className="panel-title">
        <span><ScanSearch size={12} style={{ verticalAlign: -2, marginRight: 6 }} />Traffic anomalies · trailing {data.window_days}d</span>
        <span className="hint">same hour-of-day robust z (median/MAD) · threshold z ≥ {data.threshold}</span>
      </div>
      {data.anomalies.length === 0 && (
        <div className="empty">
          <Radar size={26} style={{ opacity: 0.4, marginBottom: 8 }} />
          <div>No outliers. Every hour sits inside its expected envelope.</div>
        </div>
      )}
      <div className="alert-list">
        {data.anomalies.map((a) => (
          <div className="anomaly-item" key={`${a.vk}-${a.hour}`}>
            <div className="anomaly-z">{a.z.toFixed(1)}<span style={{ fontSize: 11, display: 'block', color: 'var(--muted)' }}>σ</span></div>
            <div style={{ minWidth: 0 }}>
              <div className="alert-title">{a.key_name} burned {fmtUsd(a.cost)} — <span className="anomaly-ratio">{a.ratio}×</span> its {fmtTs(a.hour)} baseline</div>
              <div className="alert-detail">Baseline ${a.baseline.toFixed(2)}/h for this hour-of-day over the trailing 21 days. Signature of a runaway agent loop or a leaked credential, not organic growth.</div>
              <div className="alert-time mono">{timeAgo(a.hour)} · {a.team} · same hour-of-day detector</div>
            </div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 14, display: 'flex', gap: 10, alignItems: 'center', color: 'var(--muted-2)', fontSize: 11 }}>
        <TrendingUp size={13} />
        Seasonality-aware detection: business-hours traffic is judged against business-hours baselines, so a 2pm spike never hides behind an overnight median.
      </div>
    </div>
  )
}
