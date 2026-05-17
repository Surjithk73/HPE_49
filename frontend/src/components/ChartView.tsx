import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend
} from 'recharts'

interface Props {
  chartType: 'bar' | 'line'
  columns: string[]
  rows: Record<string, unknown>[]
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      borderRadius: '8px', border: '1px solid #2a2a2a', background: '#1c1c1c',
      padding: '10px 14px', boxShadow: '0 8px 32px rgba(0,0,0,0.6)', fontSize: '12px',
    }}>
      <p style={{ marginBottom: '8px', color: '#888', fontWeight: 500 }}>{String(label)}</p>
      {payload.map((p: any, i: number) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '3px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: p.color, flexShrink: 0 }} />
          <span style={{ color: '#888' }}>{p.name}:</span>
          <span style={{ color: '#f0f0f0', fontWeight: 600 }}>
            {typeof p.value === 'number' ? p.value.toLocaleString() : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function ChartView({ chartType, columns, rows }: Props) {
  const xCol = columns.find(c =>
    c.includes('timestamp') || c.includes('name') || c.includes('num') || c.includes('device')
  ) || columns[0]

  const yColumns = columns.filter(c => {
    if (c === xCol) return false
    const sample = rows[0]?.[c]
    return typeof sample === 'number' || (typeof sample === 'string' && !isNaN(Number(sample)))
  })

  const data = rows.slice(0, 200).map(row => {
    const point: Record<string, unknown> = { [xCol]: row[xCol] }
    yColumns.forEach(c => { point[c] = typeof row[c] === 'number' ? row[c] : Number(row[c]) || 0 })
    return point
  })

  const axisStyle = { fill: '#555', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }

  return (
    <div style={{
      borderRadius: '10px', border: '1px solid #2a2a2a', background: '#161616',
      padding: '16px', animation: 'slideUp 0.25s ease-out',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
        <span style={{ fontSize: '11px', fontWeight: 600, color: '#555', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
          {chartType === 'bar' ? 'Bar Chart' : 'Line Chart'}
        </span>
        {rows.length > 200 && (
          <span style={{ fontSize: '11px', color: '#444' }}>
            (first 200 of {rows.length.toLocaleString()} rows)
          </span>
        )}
      </div>

      <ResponsiveContainer width="100%" height={300}>
        {chartType === 'bar' ? (
          <BarChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
            <CartesianGrid stroke="#222" strokeDasharray="3 3" />
            <XAxis dataKey={xCol} tick={axisStyle} tickLine={false} axisLine={{ stroke: '#2a2a2a' }} />
            <YAxis tick={axisStyle} tickLine={false} axisLine={false} tickFormatter={v => v.toLocaleString()} />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(59,130,246,0.05)' }} />
            {yColumns.length > 1 && <Legend wrapperStyle={{ fontSize: 11, color: '#666' }} />}
            {yColumns.map((col, i) => (
              <Bar key={col} dataKey={col} fill={COLORS[i % COLORS.length]} radius={[3, 3, 0, 0]} maxBarSize={48} />
            ))}
          </BarChart>
        ) : (
          <LineChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
            <CartesianGrid stroke="#222" strokeDasharray="3 3" />
            <XAxis dataKey={xCol} tick={axisStyle} tickLine={false} axisLine={{ stroke: '#2a2a2a' }} />
            <YAxis tick={axisStyle} tickLine={false} axisLine={false} tickFormatter={v => v.toLocaleString()} />
            <Tooltip content={<CustomTooltip />} />
            {yColumns.length > 1 && <Legend wrapperStyle={{ fontSize: 11, color: '#666' }} />}
            {yColumns.map((col, i) => (
              <Line key={col} type="monotone" dataKey={col} stroke={COLORS[i % COLORS.length]}
                strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
            ))}
          </LineChart>
        )}
      </ResponsiveContainer>

      <style>{`@keyframes slideUp { from { opacity:0; transform:translateY(8px) } to { opacity:1; transform:translateY(0) } }`}</style>
    </div>
  )
}
