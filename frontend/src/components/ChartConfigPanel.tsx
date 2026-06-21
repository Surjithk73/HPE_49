import { useState } from 'react'
import { Settings2, ChevronUp, ChevronDown, Eye, EyeOff } from 'lucide-react'
import {
  reconcileForXChange,
  type ChartConfig,
  type SeriesConfig,
  type SeriesKind,
} from '../lib/chartConfig'

interface Props {
  columns: string[]
  rows: Record<string, unknown>[]
  config: ChartConfig
  onChange: (next: ChartConfig) => void
  // When true (scatter mode) only the first two visible series matter and
  // per-series kind is irrelevant — we hide the kind control to avoid confusion.
  hideSeriesKind?: boolean
}

const SERIES_KINDS: SeriesKind[] = ['line', 'bar', 'area']

const fmtLabel = (value: string) =>
  value.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

const selectStyle: React.CSSProperties = {
  background: '#161616', color: '#ccc', border: '1px solid #2a2a2a',
  borderRadius: '6px', padding: '4px 8px', fontSize: '11px',
  fontFamily: 'inherit', cursor: 'pointer',
}

const iconBtnStyle = (disabled: boolean): React.CSSProperties => ({
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  background: 'transparent', border: 'none', padding: '2px',
  color: disabled ? '#333' : '#777', cursor: disabled ? 'default' : 'pointer',
})

export default function ChartConfigPanel({ columns, rows, config, onChange, hideSeriesKind }: Props) {
  const [open, setOpen] = useState(false)

  const updateSeries = (idx: number, patch: Partial<SeriesConfig>) => {
    const series = config.series.map((s, i) => (i === idx ? { ...s, ...patch } : s))
    onChange({ ...config, series })
  }

  const move = (idx: number, dir: -1 | 1) => {
    const j = idx + dir
    if (j < 0 || j >= config.series.length) return
    const series = [...config.series]
    ;[series[idx], series[j]] = [series[j], series[idx]]
    onChange({ ...config, series })
  }

  const changeX = (newX: string) => {
    onChange(reconcileForXChange(config, newX, columns, rows))
  }

  return (
    <div style={{
      border: '1px solid #2a2a2a', background: '#111', borderRadius: '8px',
      fontSize: '11px', fontFamily: 'JetBrains Mono, monospace', color: '#888',
    }}>
      {/* Header / toggle */}
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: '6px', width: '100%',
          background: 'transparent', border: 'none', cursor: 'pointer',
          color: open ? '#f0f0f0' : '#777', padding: '8px 12px',
          fontFamily: 'inherit', fontSize: '11px',
        }}
      >
        <Settings2 size={12} />
        <span>Configure chart</span>
        <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center' }}>
          {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </span>
      </button>

      {open && (
        <div style={{ padding: '4px 12px 12px', borderTop: '1px solid #1c1c1c' }}>
          {/* X-axis */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: '10px 0' }}>
            <span style={{ width: '64px', color: '#666' }}>X-axis</span>
            <select value={config.xColumn} onChange={e => changeX(e.target.value)} style={selectStyle}>
              {columns.map(c => (
                <option key={c} value={c}>{fmtLabel(c)}</option>
              ))}
            </select>
          </div>

          {/* Series */}
          <div style={{ color: '#666', marginBottom: '6px' }}>Series</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {config.series.map((s, i) => (
              <div key={s.column} style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                opacity: s.visible ? 1 : 0.45,
              }}>
                {/* reorder */}
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <button title="Move up" onClick={() => move(i, -1)} disabled={i === 0} style={iconBtnStyle(i === 0)}>
                    <ChevronUp size={11} />
                  </button>
                  <button title="Move down" onClick={() => move(i, 1)} disabled={i === config.series.length - 1} style={iconBtnStyle(i === config.series.length - 1)}>
                    <ChevronDown size={11} />
                  </button>
                </div>

                {/* visibility */}
                <button
                  title={s.visible ? 'Hide series' : 'Show series'}
                  onClick={() => updateSeries(i, { visible: !s.visible })}
                  style={iconBtnStyle(false)}
                >
                  {s.visible ? <Eye size={13} /> : <EyeOff size={13} />}
                </button>

                {/* color */}
                <input
                  type="color"
                  value={s.color}
                  title="Series colour"
                  onChange={e => updateSeries(i, { color: e.target.value })}
                  style={{
                    width: '22px', height: '22px', padding: 0, border: '1px solid #2a2a2a',
                    borderRadius: '4px', background: 'transparent', cursor: 'pointer',
                  }}
                />

                {/* name */}
                <span style={{ flex: 1, color: '#ccc', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {fmtLabel(s.column)}
                </span>

                {/* per-series kind */}
                {!hideSeriesKind && (
                  <select
                    value={s.kind}
                    onChange={e => updateSeries(i, { kind: e.target.value as SeriesKind })}
                    style={selectStyle}
                  >
                    {SERIES_KINDS.map(k => (
                      <option key={k} value={k}>{k}</option>
                    ))}
                  </select>
                )}
              </div>
            ))}
            {config.series.length === 0 && (
              <span style={{ color: '#555' }}>No numeric columns available to plot.</span>
            )}
          </div>

          {hideSeriesKind && (
            <div style={{ color: '#555', marginTop: '8px' }}>
              Scatter uses the first two visible series as X and Y.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
