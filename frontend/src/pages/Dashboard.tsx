import { useState, useEffect, useCallback } from 'react'
import { BarChart2, Table2, AlertTriangle, Database, Cpu, BookOpen, TrendingUp, AreaChart, ScatterChart, Layers } from 'lucide-react'
import { Link } from 'react-router-dom'
import QueryInput, { type InputMode } from '../components/QueryInput'
import SQLPreview from '../components/SQLPreview'
import ResultsTable from '../components/ResultsTable'
import ChartView, { type ChartKind } from '../components/ChartView'
import ReportDownload from '../components/ReportDownload'
import QueryHistory from '../components/QueryHistory'
import { runQuery, runSqlDirect, getHistory, getHealth, type QueryResponse, type HistoryEntry, type HealthResponse } from '../lib/api'

const CHART_TYPES: { kind: ChartKind; label: string; icon: React.ReactNode }[] = [
  { kind: 'bar',         label: 'Bar',          icon: <BarChart2 size={12} /> },
  { kind: 'stacked-bar', label: 'Stacked',       icon: <Layers size={12} /> },
  { kind: 'line',        label: 'Line',          icon: <TrendingUp size={12} /> },
  { kind: 'area',        label: 'Area',          icon: <AreaChart size={12} /> },
  { kind: 'scatter',     label: 'Scatter',       icon: <ScatterChart size={12} /> },
]

export default function Dashboard() {
  const [result, setResult] = useState<QueryResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthFailed, setHealthFailed] = useState(false)
  const [viewMode, setViewMode] = useState<'chart' | 'table'>('table')
  const [chartKind, setChartKind] = useState<ChartKind>('bar')
  const [currentQuery, setCurrentQuery] = useState('')

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealthFailed(true))
  }, [])

  const refreshHistory = useCallback(async () => {
    try { setHistory(await getHistory()) } catch { /* silent */ }
  }, [])

  useEffect(() => { refreshHistory() }, [refreshHistory])

  const handleQuery = async (query: string, mode: InputMode = 'nl') => {
    setLoading(true)
    setError(null)
    setCurrentQuery(query)
    try {
      const res = mode === 'sql' ? await runSqlDirect(query) : await runQuery(query)
      setResult(res)
      // Auto-select chart kind based on data shape
      if (res.chart_type === 'line') {
        setChartKind('line')
        setViewMode('chart')
      } else if (res.chart_type === 'bar') {
        // Use stacked bar if multiple numeric columns (like CPU utilization breakdown)
        const numericCols = res.columns.filter(c => {
          const s = res.rows[0]?.[c]
          return typeof s === 'number' || (!isNaN(Number(s)) && s !== '')
        })
        setChartKind(numericCols.length > 2 ? 'stacked-bar' : 'bar')
        setViewMode('chart')
      } else {
        setViewMode('table')
      }
      await refreshHistory()
    } catch (e: any) {
      setError(e.message)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  // Always allow chart view when there's result data
  const canChart = result && result.columns.length >= 2

  return (
    <div style={{ minHeight: '100vh', background: '#0a0a0a', color: '#f0f0f0', fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace' }}>

      {/* ── Header ── */}
      <header style={{ borderBottom: '1px solid #1c1c1c', background: '#111' }}>
        <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '56px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '32px', height: '32px', borderRadius: '8px',
              background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Cpu size={15} style={{ color: '#3b82f6' }} />
            </div>
            <div>
              <div style={{ fontSize: '14px', fontWeight: 700, color: '#f0f0f0', letterSpacing: '-0.02em' }}>QueryCraft</div>
              <div style={{ fontSize: '11px', color: '#444' }}>HPE NonStop Performance Analytics</div>
            </div>
          </div>

          {/* Status + Links */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <Link 
              to="/cache"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 14px',
                borderRadius: '8px',
                border: '1px solid #2a2a2a',
                background: '#161616',
                color: '#f0f0f0',
                fontSize: '12px',
                textDecoration: 'none',
                transition: 'all 0.2s',
                fontWeight: 500
              }}
            >
              <Database size={14} />
              Cache ({health?.cache_entries || 0})
            </Link>

            <Link 
              to="/how-it-works"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 14px',
                borderRadius: '8px',
                border: '1px solid #2a2a2a',
                background: '#161616',
                color: '#f0f0f0',
                fontSize: '12px',
                textDecoration: 'none',
                transition: 'all 0.2s',
                fontWeight: 500
              }}
            >
              <BookOpen size={14} />
              How It Works
            </Link>
            
            {healthFailed && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                border: '1px solid rgba(251,191,36,0.3)', background: 'rgba(251,191,36,0.08)',
                borderRadius: '7px', padding: '5px 12px', fontSize: '12px', color: '#fbbf24',
              }}>
                <AlertTriangle size={12} /> Backend unreachable
              </div>
            )}
            {health && !healthFailed && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '11px', color: '#555' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: health.db_connected ? '#10b981' : '#ef4444' }} />
                  {health.db_connected ? 'Connected' : 'Disconnected'}
                </span>
                <span style={{ color: '#2a2a2a' }}>·</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Database size={11} /> {health.schema_tables} tables
                </span>
                <span style={{ color: '#2a2a2a' }}>·</span>
                <span style={{ color: '#444' }}>{health.llm_model}</span>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ── Main ── */}
      <main style={{ maxWidth: '1280px', margin: '0 auto', padding: '32px 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '24px', alignItems: 'start' }}>

          {/* Left column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

            {/* Query Input */}
            <div style={{ borderRadius: '12px', border: '1px solid #1c1c1c', background: '#111', padding: '20px' }}>
              <QueryInput
                onSubmit={handleQuery}
                loading={loading}
                error={error}
                initialValue={currentQuery}
              />
            </div>

            {/* Results */}
            {result && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <SQLPreview
                  sql={result.sql}
                  cacheHit={result.cache_hit}
                  executionTimeMs={result.execution_time_ms}
                  domain={result.domain}
                />

                {/* Stats + view controls */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                  <span style={{ fontSize: '12px', color: '#444' }}>
                    {result.row_count.toLocaleString()} rows returned
                  </span>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>

                    {/* Chart type picker — only visible in chart mode */}
                    {viewMode === 'chart' && canChart && (
                      <div style={{
                        display: 'flex', borderRadius: '8px',
                        border: '1px solid #2a2a2a', background: '#111', padding: '3px', gap: '2px',
                      }}>
                        {CHART_TYPES.map(ct => (
                          <button
                            key={ct.kind}
                            onClick={() => setChartKind(ct.kind)}
                            title={ct.label}
                            style={{
                              display: 'flex', alignItems: 'center', gap: '4px',
                              borderRadius: '6px', padding: '5px 10px', fontSize: '11px',
                              border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                              background: chartKind === ct.kind ? '#2a2a2a' : 'transparent',
                              color: chartKind === ct.kind ? '#f0f0f0' : '#555',
                              transition: 'all 0.15s',
                            }}
                          >
                            {ct.icon}
                            <span>{ct.label}</span>
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Chart / Table toggle */}
                    {canChart && (
                      <div style={{
                        display: 'flex', borderRadius: '8px',
                        border: '1px solid #2a2a2a', background: '#161616', padding: '3px',
                      }}>
                        {(['chart', 'table'] as const).map(mode => (
                          <button
                            key={mode}
                            onClick={() => setViewMode(mode)}
                            style={{
                              display: 'flex', alignItems: 'center', gap: '5px',
                              borderRadius: '6px', padding: '5px 12px', fontSize: '11px',
                              border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                              background: viewMode === mode ? '#2a2a2a' : 'transparent',
                              color: viewMode === mode ? '#f0f0f0' : '#555',
                              transition: 'all 0.15s',
                            }}
                          >
                            {mode === 'chart' ? <BarChart2 size={11} /> : <Table2 size={11} />}
                            {mode === 'chart' ? 'Chart' : 'Table'}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {viewMode === 'chart' && canChart
                  ? <ChartView chartType={chartKind} columns={result.columns} rows={result.rows} />
                  : <ResultsTable columns={result.columns} rows={result.rows} />
                }

                {/* Download */}
                <div style={{ borderRadius: '12px', border: '1px solid #1c1c1c', background: '#111', padding: '16px' }}>
                  <ReportDownload sql={result.sql} queryText={currentQuery} />
                </div>
              </div>
            )}

            {/* Empty state */}
            {!result && !loading && !error && (
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                borderRadius: '12px', border: '1px dashed #1c1c1c', padding: '80px 24px', textAlign: 'center',
              }}>
                <div style={{
                  width: '52px', height: '52px', borderRadius: '50%',
                  background: '#161616', border: '1px solid #2a2a2a',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px',
                }}>
                  <BarChart2 size={22} style={{ color: '#333' }} />
                </div>
                <p style={{ fontSize: '14px', fontWeight: 500, color: '#555', margin: '0 0 6px' }}>
                  Ask a question to get started
                </p>
                <p style={{ fontSize: '12px', color: '#333', margin: 0 }}>
                  Results will appear here
                </p>
              </div>
            )}
          </div>

          {/* Right column — History */}
          <aside>
            <QueryHistory history={history} onSelect={q => { setCurrentQuery(q); handleQuery(q, 'nl') }} />
          </aside>
        </div>
      </main>
    </div>
  )
}
