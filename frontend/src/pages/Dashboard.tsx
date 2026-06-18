import { useState, useEffect, useCallback } from 'react'
import { BarChart2, Table2, AlertTriangle, Database, Cpu, BookOpen, TrendingUp, AreaChart, ScatterChart, Layers, Activity, X, ChevronDown, Check } from 'lucide-react'
import { Link } from 'react-router-dom'
import QueryInput, { type InputMode } from '../components/QueryInput'
import SQLPreview from '../components/SQLPreview'
import ResultsTable from '../components/ResultsTable'
import ChartView, { type ChartKind } from '../components/ChartView'
import ReportDownload from '../components/ReportDownload'
import AIExplanation from '../components/AIExplanation'
import PromptDebugPanel from '../components/PromptDebugPanel'
import QueryHistory from '../components/QueryHistory'
import { runQuery, runSqlDirect, runImageQuery, getHistory, getHealth, runRetryAnalysis, setModel, acceptQueryCache, type QueryResponse, type HistoryEntry, type HealthResponse, type RetryAnalysisReport } from '../lib/api'

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
  const [retryReport, setRetryReport] = useState<RetryAnalysisReport | null>(null)
  const [retryLoading, setRetryLoading] = useState(false)
  const [retryError, setRetryError] = useState<string | null>(null)
  const [retryOpen, setRetryOpen] = useState(false)
  const [cacheDecision, setCacheDecision] = useState<'pending' | 'accepted' | 'rejected'>('pending')
  // Model switcher state
  const AVAILABLE_MODELS = [
    { id: 'gemini-3.1-flash-lite',  label: 'Gemini 3.1 Flash Lite',  badge: 'fast'    },
    { id: 'gemini-3.5-flash',       label: 'Gemini 3.5 Flash',        badge: 'latest'  },
    { id: 'qwen/qwen3-next-80b-a3b-instruct', label: 'Qwen 80 Billion', badge: 'accurate' },
    { id: 'openai/gpt-oss-20b',     label: 'GPT OSS',                 badge: 'balanced' }
  ]
  const [activeModel, setActiveModel] = useState<string>(
    health?.llm_model ?? 'gemini-3.1-flash-lite'
  )
  const [modelSwitching, setModelSwitching] = useState(false)
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false)

  const handleModelSwitch = async (modelId: string) => {
    setModelDropdownOpen(false)
    if (modelId === activeModel || modelSwitching) return
    setModelSwitching(true)
    try {
      const res = await setModel(modelId)
      setActiveModel(res.model)
    } catch {
      // silently ignore — model stays unchanged
    } finally {
      setModelSwitching(false)
    }
  }

  const handleRetryAnalysis = async () => {
    setRetryOpen(true)
    setRetryLoading(true)
    setRetryError(null)
    try {
      const report = await runRetryAnalysis()
      setRetryReport(report)
    } catch (e: any) {
      setRetryError(e.message)
    } finally {
      setRetryLoading(false)
    }
  }

  const handleAcceptCache = async () => {
    if (!result || !currentQuery) return
    try {
      await acceptQueryCache(currentQuery, result.sql, result.row_count)
      setCacheDecision('accepted')
    } catch (err: any) {
      console.error('Failed to accept cache:', err)
      alert(err.message || 'Failed to save to cache')
    }
  }

  useEffect(() => {
    getHealth().then(h => {
      setHealth(h)
      if (h.llm_model) setActiveModel(h.llm_model)
    }).catch(() => setHealthFailed(true))
  }, [])

  const refreshHistory = useCallback(async () => {
    try { setHistory(await getHistory()) } catch { /* silent */ }
  }, [])

  useEffect(() => { refreshHistory() }, [refreshHistory])

  const handleQuery = async (payload: string | File, mode: InputMode = 'nl', targetDb: string = 'macht413') => {
    setLoading(true)
    setError(null)
    if (typeof payload === 'string') setCurrentQuery(payload)
    else setCurrentQuery(`[Image] ${payload.name}`)
    try {
      const res =
        mode === 'image' && payload instanceof File ? await runImageQuery(payload, targetDb)
        : mode === 'sql' ? await runSqlDirect(payload as string, targetDb)
        : await runQuery(payload as string, targetDb)
      if (mode === 'image' && res.inferred_query) setCurrentQuery(res.inferred_query)
      setResult(res)
      setCacheDecision('pending')
      // Auto-select chart kind based on data shape
      if (res.chart_type === 'line') {
        setChartKind('line')
        setViewMode('chart')
      } else if (res.chart_type === 'bar') {
        // Only use stacked-bar when the numeric columns are clearly parts of a
        // whole (their names contain 'pct', 'percent', 'ratio', or 'share').
        // For independent metrics (cpu_busy_time, intr_busy_time, etc.) a
        // grouped bar is more honest — stacked bars imply the values sum to 100%.
        const numericCols = res.columns.filter(c => {
          const s = res.rows[0]?.[c]
          return typeof s === 'number' || (!isNaN(Number(s)) && s !== '')
        })
        const partsOfWhole = numericCols.length > 2 && numericCols.every(c => {
          const cl = c.toLowerCase()
          return cl.includes('pct') || cl.includes('percent') ||
                 cl.includes('ratio') || cl.includes('share') ||
                 cl.includes('fraction')
        })
        setChartKind(partsOfWhole ? 'stacked-bar' : 'bar')
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
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '12px', textDecoration: 'none' }}>
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
          </Link>

          {/* Status + Links */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <Link 
              to="/databases"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 14px',
                borderRadius: '8px',
                background: '#222',
                color: '#fff',
                fontSize: '12px',
                textDecoration: 'none',
                transition: 'all 0.2s',
                fontWeight: 600
              }}
            >
              Databases
            </Link>

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

            <button
              onClick={handleRetryAnalysis}
              title="Analyze the audit log for queries that exhausted the retry budget"
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
                cursor: 'pointer',
                fontFamily: 'inherit',
                fontWeight: 500,
                transition: 'all 0.2s',
              }}
            >
              <Activity size={14} />
              Retry Analysis
            </button>

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

            {/* ── Model selector ── */}
            <div style={{ position: 'relative' }}>
              <button
                onClick={() => setModelDropdownOpen(o => !o)}
                disabled={modelSwitching}
                style={{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  padding: '8px 14px', borderRadius: '8px',
                  border: `1px solid ${modelDropdownOpen ? 'rgba(59,130,246,0.5)' : '#2a2a2a'}`,
                  background: modelDropdownOpen ? 'rgba(59,130,246,0.08)' : '#161616',
                  color: '#f0f0f0', fontSize: '12px', cursor: modelSwitching ? 'not-allowed' : 'pointer',
                  fontFamily: 'inherit', fontWeight: 500, transition: 'all 0.15s',
                  opacity: modelSwitching ? 0.6 : 1,
                }}
              >
                <Cpu size={13} style={{ color: '#3b82f6' }} />
                <span style={{ maxWidth: '140px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {AVAILABLE_MODELS.find(m => m.id === activeModel)?.label ?? activeModel}
                </span>
                <ChevronDown
                  size={11}
                  style={{
                    color: '#555',
                    transform: modelDropdownOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 0.15s',
                  }}
                />
              </button>

              {modelDropdownOpen && (
                <>
                  {/* Click-away backdrop */}
                  <div
                    onClick={() => setModelDropdownOpen(false)}
                    style={{ position: 'fixed', inset: 0, zIndex: 49 }}
                  />
                  <div style={{
                    position: 'absolute', top: 'calc(100% + 6px)', right: 0,
                    zIndex: 50, minWidth: '220px',
                    background: '#111', border: '1px solid #2a2a2a',
                    borderRadius: '10px', overflow: 'hidden',
                    boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
                    animation: 'slideDown 0.15s ease-out',
                  }}>
                    <div style={{
                      padding: '8px 12px 6px',
                      fontSize: '10px', fontWeight: 600, color: '#444',
                      letterSpacing: '0.08em', textTransform: 'uppercase',
                      borderBottom: '1px solid #1c1c1c',
                    }}>
                      Select Model
                    </div>
                    {AVAILABLE_MODELS.map(m => {
                      const isActive = m.id === activeModel
                      const badgeColor: Record<string, string> = {
                        fast:     'rgba(16,185,129,0.15)',
                        balanced: 'rgba(59,130,246,0.15)',
                        smart:    'rgba(168,85,247,0.15)',
                        latest:   'rgba(251,191,36,0.15)',
                        preview:  'rgba(239,68,68,0.15)',
                      }
                      const badgeText: Record<string, string> = {
                        fast:     '#34d399',
                        balanced: '#60a5fa',
                        smart:    '#c084fc',
                        latest:   '#fbbf24',
                        preview:  '#f87171',
                      }
                      return (
                        <button
                          key={m.id}
                          onClick={() => handleModelSwitch(m.id)}
                          style={{
                            width: '100%', display: 'flex', alignItems: 'center',
                            justifyContent: 'space-between', gap: '8px',
                            padding: '10px 12px', border: 'none',
                            background: isActive ? 'rgba(59,130,246,0.08)' : 'transparent',
                            color: isActive ? '#f0f0f0' : '#888',
                            fontSize: '12px', cursor: 'pointer',
                            fontFamily: 'inherit', textAlign: 'left',
                            transition: 'background 0.1s',
                            borderLeft: isActive ? '2px solid #3b82f6' : '2px solid transparent',
                          }}
                          onMouseEnter={e => {
                            if (!isActive) (e.currentTarget as HTMLElement).style.background = '#1c1c1c'
                          }}
                          onMouseLeave={e => {
                            if (!isActive) (e.currentTarget as HTMLElement).style.background = 'transparent'
                          }}
                        >
                          <span style={{ fontWeight: isActive ? 600 : 400 }}>{m.label}</span>
                          <span style={{
                            fontSize: '10px', padding: '2px 7px', borderRadius: '999px',
                            background: badgeColor[m.badge] ?? 'rgba(255,255,255,0.05)',
                            color: badgeText[m.badge] ?? '#888',
                            fontWeight: 600, letterSpacing: '0.04em',
                          }}>
                            {m.badge}
                          </span>
                        </button>
                      )
                    })}
                  </div>
                </>
              )}
            </div>
            {/* ── end model selector ── */}
            
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

                {/* Debug: show the exact prompt sent to the LLM and raw output */}
                {result.debug_prompt && (
                  <PromptDebugPanel prompt={result.debug_prompt} rawOutput={result.raw_llm_output} />
                )}

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

                {!result.cache_hit && cacheDecision !== 'rejected' && (
                  <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '16px', background: '#111', border: '1px solid #1c1c1c', borderRadius: '12px',
                    marginTop: '8px'
                  }}>
                    <div>
                      <h4 style={{ margin: '0 0 4px', fontSize: '13px', color: '#f0f0f0', fontWeight: 600 }}>Train the AI</h4>
                      <p style={{ margin: 0, fontSize: '12px', color: '#888' }}>
                        {cacheDecision === 'pending' ? 'Would you like to add this successful query to the system cache?' : 'Query successfully added to the cache.'}
                      </p>
                    </div>
                    {cacheDecision === 'pending' ? (
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          onClick={() => setCacheDecision('rejected')}
                          style={{
                            padding: '6px 12px', background: 'transparent', border: '1px solid #2a2a2a',
                            color: '#888', borderRadius: '6px', fontSize: '12px', cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '6px',
                          }}
                        >
                          <X size={12} /> Reject
                        </button>
                        <button
                          onClick={handleAcceptCache}
                          style={{
                            padding: '6px 12px', background: '#a855f7', border: '1px solid #a855f7',
                            color: '#fff', borderRadius: '6px', fontSize: '12px', cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600
                          }}
                        >
                          <Check size={12} /> Accept
                        </button>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#22c55e', fontSize: '12px', fontWeight: 600 }}>
                        <Check size={14} /> Added
                      </div>
                    )}
                  </div>
                )}

                <AIExplanation sql={result.sql} queryText={currentQuery} columns={result.columns} rows={result.rows} />

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
            <QueryHistory history={history} onSelect={q => { setCurrentQuery(q); handleQuery(q, 'nl', 'macht413') }} />
          </aside>
        </div>
      </main>

      {/* Retry Analysis modal */}
      {retryOpen && (
        <div
          onClick={() => setRetryOpen(false)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
            display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
            padding: '64px 24px', zIndex: 100, overflowY: 'auto',
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              width: '100%', maxWidth: '880px', background: '#111',
              border: '1px solid #2a2a2a', borderRadius: '12px',
              padding: '24px', color: '#f0f0f0', fontFamily: 'inherit',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Activity size={16} style={{ color: '#3b82f6' }} />
                <h2 style={{ fontSize: '15px', fontWeight: 700, margin: 0 }}>Retry Analysis</h2>
              </div>
              <button
                onClick={() => setRetryOpen(false)}
                style={{
                  background: 'transparent', border: 'none', color: '#555',
                  cursor: 'pointer', padding: '4px', display: 'flex',
                }}
              >
                <X size={16} />
              </button>
            </div>

            {retryLoading && (
              <p style={{ fontSize: '12px', color: '#777', margin: 0 }}>Analyzing audit log…</p>
            )}

            {retryError && !retryLoading && (
              <div style={{
                fontSize: '12px', color: '#fbbf24',
                border: '1px solid rgba(251,191,36,0.3)', background: 'rgba(251,191,36,0.08)',
                borderRadius: '8px', padding: '10px 12px',
              }}>
                {retryError}
              </div>
            )}

            {retryReport && !retryLoading && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div style={{ fontSize: '12px', color: '#888', lineHeight: 1.5 }}>
                  {retryReport.summary}
                </div>

                {retryReport.total_failures === 0 && (
                  <p style={{ fontSize: '12px', color: '#555' }}>
                    No failed queries in the audit log yet. Failed queries appear here
                    once the retry loop exhausts its budget.
                  </p>
                )}

                {retryReport.buckets.map(b => (
                  <div
                    key={b.key}
                    style={{
                      border: '1px solid #1c1c1c', borderRadius: '10px',
                      background: '#161616', padding: '14px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <div style={{ fontSize: '13px', fontWeight: 600 }}>{b.label}</div>
                      <span style={{
                        fontSize: '11px', color: '#3b82f6',
                        background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)',
                        borderRadius: '999px', padding: '2px 10px',
                      }}>
                        {b.count}x
                      </span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#888', marginBottom: '8px' }}>
                      Fix in: <code style={{ color: '#cbd5e1' }}>{b.fix_surface}</code>
                    </div>
                    <div style={{
                      fontSize: '12px', color: '#cbd5e1', lineHeight: 1.55,
                      borderLeft: '2px solid #2a2a2a', paddingLeft: '10px', marginBottom: '10px',
                    }}>
                      {b.recommendation}
                    </div>
                    {b.samples.length > 0 && (
                      <details>
                        <summary style={{ fontSize: '11px', color: '#666', cursor: 'pointer' }}>
                          {b.samples.length} example{b.samples.length !== 1 ? 's' : ''}
                        </summary>
                        <ul style={{ margin: '8px 0 0', padding: '0 0 0 16px', fontSize: '11px', color: '#999', lineHeight: 1.5 }}>
                          {b.samples.map(s => (
                            <li key={s.id} style={{ marginBottom: '6px' }}>
                              <span style={{ color: '#555' }}>#{s.id}</span>{' '}
                              <span style={{ color: '#cbd5e1' }}>{s.original_input.slice(0, 120)}</span>
                              {s.original_input.length > 120 && '…'}
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </div>
                ))}

                {retryReport.unclassified.length > 0 && (
                  <div style={{
                    border: '1px solid #1c1c1c', borderRadius: '10px',
                    background: '#161616', padding: '14px',
                  }}>
                    <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                      Unclassified ({retryReport.unclassified.length})
                    </div>
                    <p style={{ fontSize: '11px', color: '#888', margin: 0 }}>
                      These don't match any known failure pattern. Add a new bucket to{' '}
                      <code style={{ color: '#cbd5e1' }}>backend/jobs/retry_analysis.py</code>.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      <style>{`
        @keyframes slideDown {
          from { opacity: 0; transform: translateY(-6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}
