import {
  ResponsiveContainer,
  ComposedChart, Bar, Line, Area,
  ScatterChart, Scatter, ZAxis,
  XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ReferenceLine,
} from 'recharts'
import { COLORS, buildDefaultConfig, type ChartConfig, type SeriesConfig } from '../lib/chartConfig'

export type ChartKind = 'bar' | 'stacked-bar' | 'line' | 'area' | 'scatter'

interface Props {
  chartType: ChartKind
  columns: string[]
  rows: Record<string, unknown>[]
  // Optional explicit configuration. When omitted, sensible defaults are derived.
  config?: ChartConfig
}

// ── Tooltip ──────────────────────────────────────────────────────────────────
const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      borderRadius: '8px', border: '1px solid #2a2a2a', background: '#1a1a1a',
      padding: '10px 14px', boxShadow: '0 8px 32px rgba(0,0,0,0.7)', fontSize: '12px',
      fontFamily: 'JetBrains Mono, monospace',
    }}>
      <p style={{ marginBottom: '8px', color: '#aaa', fontWeight: 600, borderBottom: '1px solid #2a2a2a', paddingBottom: '6px' }}>
        {String(label)}
      </p>
      {payload.map((p: any, i: number) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: p.color, flexShrink: 0 }} />
          <span style={{ color: '#777', flex: 1 }}>{p.name}</span>
          <span style={{ color: '#f0f0f0', fontWeight: 600, marginLeft: '12px' }}>
            {typeof p.value === 'number'
              ? p.value % 1 === 0 ? p.value.toLocaleString() : p.value.toFixed(3)
              : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

// ── Axis tick formatter ───────────────────────────────────────────────────────
const fmtY = (v: number) =>
  v >= 1000000 ? `${(v / 1000000).toFixed(1)}M`
  : v >= 1000 ? `${(v / 1000).toFixed(1)}K`
  : v % 1 === 0 ? String(v)
  : v.toFixed(2)

// ── Legend formatter ─────────────────────────────────────────────────────────
const fmtLegend = (value: string) =>
  value.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

// ── Main component ────────────────────────────────────────────────────────────
export default function ChartView({ chartType, columns, rows, config }: Props) {
  // Fall back to derived defaults when no explicit config is supplied.
  const cfg = config ?? buildDefaultConfig(columns, rows, chartType)
  const xCol = cfg.xColumn
  // Visible series, in configured order (defines line1, line2, …)
  const series: SeriesConfig[] = cfg.series.filter(s => s.visible)
  const yColumns = series.map(s => s.column)

  // Cap at 200 rows for rendering performance
  const data = rows.slice(0, 200).map(row => {
    const point: Record<string, unknown> = {
      [xCol]: row[xCol] !== null && row[xCol] !== undefined ? String(row[xCol]) : '—',
    }
    yColumns.forEach(c => {
      const v = row[c]
      point[c] = typeof v === 'number' ? v : (v !== null && v !== undefined && !isNaN(Number(v)) ? Number(v) : 0)
    })
    return point
  })

  // Compute reference lines (average of each y column) for bar overlays
  const averages: Record<string, number> = {}
  yColumns.forEach(col => {
    const vals = data.map(d => d[col] as number).filter(v => !isNaN(v))
    averages[col] = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0
  })

  const axisStyle = { fill: '#666', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }
  const gridStyle = { stroke: '#222', strokeDasharray: '3 3' }
  const axisLine  = { stroke: '#2a2a2a' }

  const commonProps = {
    data,
    margin: { top: 8, right: 24, left: 8, bottom: 72 },
  }

  // Auto-skip ticks when there are many data points to prevent label overlap
  const tickInterval = data.length > 100 ? Math.ceil(data.length / 15)
    : data.length > 40 ? Math.ceil(data.length / 20)
    : 0

  // Truncate long tick labels (e.g. timestamps)
  const fmtXTick = (v: string) => {
    const s = String(v)
    return s.length > 12 ? s.slice(0, 12) + '…' : s
  }

  const xAxisProps = {
    dataKey: xCol,
    tick: { ...axisStyle, angle: -45, textAnchor: 'end' as const, dy: 8 },
    tickLine: false,
    axisLine: axisLine,
    interval: tickInterval,
    tickFormatter: fmtXTick,
  }

  const yAxisProps = {
    tick: axisStyle,
    tickLine: false,
    axisLine: false,
    tickFormatter: fmtY,
    width: 56,
  }

  const legendProps = {
    verticalAlign: 'top' as const,
    align: 'center' as const,
    wrapperStyle: { fontSize: 11, color: '#888', paddingBottom: '16px', lineHeight: '22px' },
    iconSize: 10,
    formatter: fmtLegend,
  }

  // ── Scatter ─────────────────────────────────────────────────────────────────
  // Special 2-axis mode: uses the first two visible series as X/Y.
  if (chartType === 'scatter') {
    const xNum = yColumns[0] || xCol
    const yNum = yColumns[1] || yColumns[0]
    const scatterColor = series[0]?.color ?? COLORS[0]
    const scatterData = data.map(d => ({ x: Number(d[xNum]) || 0, y: Number(d[yNum]) || 0, label: d[xCol] }))

    return (
      <ChartShell rows={rows} cap={200}>
        <ResponsiveContainer width="100%" height={360}>
          <ScatterChart margin={{ top: 8, right: 24, left: 8, bottom: 8 }}>
            <CartesianGrid {...gridStyle} />
            <XAxis type="number" dataKey="x" name={xNum} tick={axisStyle} tickLine={false}
              axisLine={axisLine} tickFormatter={fmtY} label={{ value: fmtLegend(xNum), position: 'insideBottom', offset: -4, fill: '#555', fontSize: 11 }} />
            <YAxis type="number" dataKey="y" name={yNum} tick={axisStyle} tickLine={false}
              axisLine={false} tickFormatter={fmtY} width={56} />
            <ZAxis range={[40, 40]} />
            <Tooltip cursor={{ strokeDasharray: '3 3' }} content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const d = payload[0].payload
              return (
                <div style={{ borderRadius: '8px', border: '1px solid #2a2a2a', background: '#1a1a1a', padding: '10px 14px', fontSize: '12px' }}>
                  <p style={{ color: '#aaa', marginBottom: '4px' }}>{String(d.label)}</p>
                  <p style={{ color: '#f0f0f0' }}>{fmtLegend(xNum)}: <b>{fmtY(d.x)}</b></p>
                  <p style={{ color: '#f0f0f0' }}>{fmtLegend(yNum)}: <b>{fmtY(d.y)}</b></p>
                </div>
              )
            }} />
            <Scatter data={scatterData} fill={scatterColor} fillOpacity={0.8} />
          </ScatterChart>
        </ResponsiveContainer>
      </ChartShell>
    )
  }

  // ── Composed (bar / line / area / combo / stacked-bar) ──────────────────────
  // A single ComposedChart renders each series per its own kind, enabling combo
  // charts. For stacked-bar, all series are forced to stacked bars.
  const stacked = chartType === 'stacked-bar'
  const showLegend = series.length > 1 || stacked

  return (
    <ChartShell rows={rows} cap={200}>
      <ResponsiveContainer width="100%" height={360}>
        <ComposedChart {...commonProps} barCategoryGap="20%">
          <defs>
            {series.map((s, i) => (
              <linearGradient key={s.column} id={`grad-${i}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor={s.color} stopOpacity={0.25} />
                <stop offset="95%" stopColor={s.color} stopOpacity={0.02} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid {...gridStyle} />
          <XAxis {...xAxisProps} />
          <YAxis {...yAxisProps} />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
          {showLegend && <Legend {...legendProps} />}

          {series.map((s, i) => {
            const effectiveKind = stacked ? 'bar' : s.kind
            if (effectiveKind === 'bar') {
              return (
                <Bar key={s.column} dataKey={s.column}
                  stackId={stacked ? 'a' : undefined}
                  fill={s.color}
                  radius={stacked
                    ? (i === series.length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0])
                    : [3, 3, 0, 0]}
                  maxBarSize={stacked ? undefined : 40}
                />
              )
            }
            if (effectiveKind === 'area') {
              return (
                <Area key={s.column} type="monotone" dataKey={s.column}
                  stroke={s.color} strokeWidth={2}
                  fill={`url(#grad-${i})`}
                  dot={false} activeDot={{ r: 5 }}
                />
              )
            }
            return (
              <Line key={s.column} type="monotone" dataKey={s.column}
                stroke={s.color}
                strokeWidth={2} dot={data.length < 30 ? { r: 3, fill: s.color } : false}
                activeDot={{ r: 5 }}
              />
            )
          })}

          {/* Average reference lines for bar series (grouped bar only) */}
          {!stacked && series
            .filter(s => s.kind === 'bar')
            .slice(0, 3)
            .map(s => (
              <ReferenceLine key={`ref-${s.column}`} y={averages[s.column]}
                stroke={s.color} strokeDasharray="6 3"
                strokeWidth={1.5} strokeOpacity={0.6}
              />
            ))}
        </ComposedChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}

// ── Wrapper with row cap notice ───────────────────────────────────────────────
function ChartShell({ rows, cap, children }: { rows: unknown[], cap: number, children: React.ReactNode }) {
  return (
    <div style={{ position: 'relative', overflow: 'hidden' }}>
      {rows.length > cap && (
        <div style={{ position: 'absolute', top: 0, right: 0, fontSize: '11px', color: '#444', zIndex: 1 }}>
          showing first {cap} of {rows.length.toLocaleString()} rows
        </div>
      )}
      {children}
    </div>
  )
}
