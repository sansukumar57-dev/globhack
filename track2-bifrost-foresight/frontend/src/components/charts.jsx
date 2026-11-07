import { useMemo, useState } from 'react'
import { fmtUsd, timeAgo } from '../api'

const W = 760
const H = 238
const PAD = { left: 52, right: 14, top: 26, bottom: 28 }

function niceMax(value) {
  if (!value || value <= 0) return 1
  const exp = Math.floor(Math.log10(value))
  const base = 10 ** exp
  const n = value / base
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10
  return step * base
}

function axisMoney(value) {
  if (value === 0) return '$0'
  if (value < 1) return `$${value.toFixed(2)}`
  if (value < 10) return `$${value.toFixed(1)}`
  return `$${Math.round(value)}`
}

function clock(ts) {
  return new Date(ts * 1000).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function AreaChart({ data, forecast }) {
  const [hover, setHover] = useState(null)

  const chart = useMemo(() => {
    if (!data || data.length === 0) return null
    const fc = forecast && forecast.length > 0 ? forecast : null
    const all = fc ? [...data, ...fc] : data
    const histLen = data.length
    const maxCost = Math.max(
      ...all.map((d) => Math.max(Number(d.cost) || 0, Number(d.p90 ?? 0) || 0)),
      0.01,
    )
    const yMax = niceMax(maxCost)
    const innerW = W - PAD.left - PAD.right
    const innerH = H - PAD.top - PAD.bottom
    const x = (i) => PAD.left + (all.length > 1 ? (i / (all.length - 1)) * innerW : innerW / 2)
    const y = (value) => PAD.top + innerH - (Math.max(0, value) / yMax) * innerH
    const points = all.map((d, i) => [x(i), y(Number(d.cost) || 0)])
    const histPoints = points.slice(0, histLen)
    const line = histPoints
      .map(([px, py], i) => `${i === 0 ? 'M' : 'L'}${px.toFixed(1)},${py.toFixed(1)}`)
      .join(' ')
    const forecastPath = fc
      ? [histPoints[histPoints.length - 1], ...points.slice(histLen)]
          .map(([px, py], i) => `${i === 0 ? 'M' : 'L'}${px.toFixed(1)},${py.toFixed(1)}`)
          .join(' ')
      : null
    // Band polygon: p90 forward, then p10 reversed, anchored at the "now" divider.
    const hasBand = !!fc && fc.every((d) => Number.isFinite(Number(d.p10)) && Number.isFinite(Number(d.p90)))
    let bandPath = null
    if (hasBand) {
      const fut = points.slice(histLen)
      const top = [[x(histLen - 1), y(Number(fc[0].p90))]]
      fut.forEach((pt, k) => top.push([pt[0], y(Number(fc[k].p90))]))
      const bottom = [...top.slice(1)].reverse().map((_, k) => {
        const idx = fut.length - 1 - k
        return [fut[idx][0], y(Number(fc[idx].p10))]
      })
      bottom.push([top[0][0], y(Number(fc[0].p10))])
      bandPath = [...top, ...bottom]
        .map(([px, py], i) => `${i === 0 ? 'M' : 'L'}${px.toFixed(1)},${py.toFixed(1)}`)
        .join(' ') + ' Z'
    }
    const baseline = PAD.top + innerH
    const area = `${line} L${histPoints[histPoints.length - 1][0].toFixed(1)},${baseline} L${histPoints[0][0].toFixed(1)},${baseline} Z`
    let peakIndex = 0
    data.forEach((d, i) => {
      if ((Number(d.cost) || 0) > (Number(data[peakIndex].cost) || 0)) peakIndex = i
    })
    const ticks = [0, yMax / 2, yMax]
    return {
      points, line, area, yMax, innerW, innerH, x, y, ticks, peakIndex, baseline,
      histLen, forecastPath, bandPath, nowX: fc ? x(histLen - 1) : null,
    }
  }, [data, forecast])

  if (!chart || !data || data.length === 0) {
    return <div className="empty">No usage in this window yet.</div>
  }

  const projected = (i) => i >= chart.histLen

  const peak = data[chart.peakIndex]
  const [peakX, peakY] = chart.points[chart.peakIndex]
  const peakText = `${timeAgo(peak.hour)} · ${fmtUsd(peak.cost)}/h`
  const peakWidth = peakText.length * 5.2 + 16
  const peakLabelX = Math.min(
    Math.max(PAD.left, peakX - peakWidth / 2),
    W - PAD.right - peakWidth,
  )
  const peakLabelY = peakY > 50 ? peakY - 30 : peakY + 10

  const hoverPoint = hover != null ? chart.points[hover] : null
  const hoverData = hover != null
    ? (projected(hover) ? (forecast ? forecast[hover - chart.histLen] : null) : data[hover])
    : null
  const hoverText = hoverData
    ? `${clock(hoverData.hour)} · ${fmtUsd(hoverData.cost)}/h${
        projected(hover)
          ? (hoverData.p10 != null ? ` · band ${fmtUsd(hoverData.p10)}–${fmtUsd(hoverData.p90)}` : ' · projected')
          : ''
      }`
    : ''
  const hoverWidth = hoverText.length * 5.2 + 16
  const hoverX = hoverPoint
    ? Math.min(Math.max(PAD.left, hoverPoint[0] - hoverWidth / 2), W - PAD.right - hoverWidth)
    : 0

  const move = (event) => {
    const rect = event.currentTarget.getBoundingClientRect()
    const ratio = (event.clientX - rect.left) / rect.width
    const plotX = ratio * W
    const within = (plotX - PAD.left) / chart.innerW
    const total = chart.points.length
    const index = Math.round(within * (total - 1))
    setHover(Math.min(total - 1, Math.max(0, index)))
  }

  return (
    <div className="chart">
      <svg
        className="chart-svg"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Fleet spend over the last 24 hours. Peak ${fmtUsd(peak.cost)} per hour ${timeAgo(peak.hour)}.${chart.forecastPath ? ` Dashed line is the trained model median for the next 12 hours${chart.bandPath ? ', with a p10-p90 band' : ''}.` : ''}`}
      >
        {chart.ticks.map((tick) => {
          const ty = chart.y(tick)
          return (
            <g key={tick}>
              <line className="grid-line" x1={PAD.left} x2={W - PAD.right} y1={ty} y2={ty} />
              <text className="axis-label" x={PAD.left - 9} y={ty + 3} textAnchor="end">
                {axisMoney(tick)}
              </text>
            </g>
          )
        })}

        <line className="axis-line" x1={PAD.left} x2={W - PAD.right} y1={chart.baseline} y2={chart.baseline} />

        {chart.forecastPath && (
          <rect
            className="future-band"
            x={chart.nowX}
            y={PAD.top}
            width={W - PAD.right - chart.nowX}
            height={chart.innerH}
          />
        )}

        {chart.bandPath && <path className="band" d={chart.bandPath} />}

        <path className="area" d={chart.area} />
        <path className="line" d={chart.line} />
        {chart.forecastPath && <path className="line-dash" d={chart.forecastPath} />}

        {chart.forecastPath && (
          <line
            className="now-line"
            x1={chart.nowX}
            x2={chart.nowX}
            y1={PAD.top}
            y2={chart.baseline}
          />
        )}

        {hover == null && (
          <>
            <line
              className="peak-line"
              x1={peakX}
              x2={peakX}
              y1={peakY}
              y2={chart.baseline}
            />
            <circle className="peak-dot" cx={peakX} cy={peakY} r="3.2" />
            <g>
              <rect
                x={peakLabelX}
                y={peakLabelY}
                width={peakWidth}
                height={18}
                rx="2"
                className="chart-tip"
              />
              <text
                x={peakLabelX + 8}
                y={peakLabelY + 12.5}
                className="chart-tip-text"
              >
                {peakText}
              </text>
            </g>
          </>
        )}

        {hoverPoint && (
          <>
            <line
              className="focus-line"
              x1={hoverPoint[0]}
              x2={hoverPoint[0]}
              y1={PAD.top}
              y2={chart.baseline}
            />
            <circle className="focus-dot" cx={hoverPoint[0]} cy={hoverPoint[1]} r="3" />
            <g>
              <rect
                x={hoverX}
                y={5}
                width={hoverWidth}
                height={18}
                rx="2"
                className="chart-tip"
              />
              <text x={hoverX + 8} y={17.5} className="chart-tip-text">
                {hoverText}
              </text>
            </g>
          </>
        )}

        <rect
          className="hit"
          x={PAD.left}
          y={PAD.top}
          width={chart.innerW}
          height={chart.innerH}
          onMouseMove={move}
          onMouseLeave={() => setHover(null)}
        />

        {chart.forecastPath
          ? [
              [0, '24h ago', 'start'],
              [Math.floor((chart.histLen - 1) / 2), '12h ago', 'middle'],
              [chart.histLen - 1, 'now', 'middle'],
              [chart.points.length - 1, '+12h', 'end'],
            ].map(([index, label, anchor], i) => (
              <text
                key={i}
                className="axis-label"
                x={chart.points[index][0]}
                y={H - 7}
                textAnchor={anchor}
              >
                {label}
              </text>
            ))
          : [0, Math.floor((data.length - 1) / 2), data.length - 1].map((index, i) => {
              const [px] = chart.points[index]
              const anchor = i === 0 ? 'start' : i === 2 ? 'end' : 'middle'
              const label = i === 0 ? '24h ago' : i === 2 ? 'now' : '12h ago'
              return (
                <text
                  key={i}
                  className="axis-label"
                  x={px}
                  y={H - 7}
                  textAnchor={anchor}
                >
                  {label}
                </text>
              )
            })}
      </svg>
      <div className="chart-foot">
        <span className="chart-legend"><span className="swatch" /> Hourly spend</span>
        {chart.bandPath && (
          <span className="chart-legend"><span className="swatch band" /> p10–p90</span>
        )}
        {chart.forecastPath && (
          <span className="chart-legend"><span className="swatch dash" /> Model median</span>
        )}
        <span className="chart-legend"><span className="swatch peak" /> Peak</span>
        <span style={{ marginLeft: 'auto' }}>Hover for hourly detail</span>
      </div>
    </div>
  )
}

const STATUS_LABELS = {
  healthy: 'Healthy',
  watch: 'Watch',
  critical: 'Critical',
  exhausted: 'Exhausted',
}

export function StatusChip({ status }) {
  const cls = {
    healthy: 'chip-healthy',
    watch: 'chip-watch',
    critical: 'chip-critical',
    exhausted: 'chip-exhausted',
  }[status] || 'chip-info'
  return <span className={`chip ${cls}`}>{STATUS_LABELS[status] || status || 'Unknown'}</span>
}

export function BudgetBar({ pct, tone, large = false }) {
  const p = Math.min(100, Math.max(0, (Number(pct) || 0) * 100))
  const cls = tone || (p >= 90 ? 'critical' : p >= 70 ? 'watch' : '')
  return (
    <div
      className={`bar ${large ? 'lg' : ''}`}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(p)}
    >
      <span className={`bar-fill ${cls}`} style={{ width: `${p}%` }} />
      <i className="bar-cap" title="Soft cap at 95% of budget" />
    </div>
  )
}
