import { useState, useEffect, useCallback } from 'react'
import { BarChart2, Table2, AlertTriangle, Database, Cpu, BookOpen, TrendingUp, AreaChart, ScatterChart, Layers, Activity, X, ChevronDown, Check, Sparkles, Send, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { HPELogo } from '../components/HPELogo'
import ThemeToggle from '../components/ThemeToggle'
import QueryInput, { type InputMode } from '../components/QueryInput'
import SQLPreview from '../components/SQLPreview'
import ResultsTable from '../components/ResultsTable'
import ChartView, { type ChartKind } from '../components/ChartView'
import ChartConfigPanel from '../components/ChartConfigPanel'
import { buildDefaultConfig, applyGlobalKind, type ChartConfig } from '../lib/chartConfig'
import ReportDownload from '../components/ReportDownload'
import PromptDebugPanel from '../components/PromptDebugPanel'
import QueryHistory from '../components/QueryHistory'
import { runSqlDirect, runImageQuery, getHistory, getHealth, setModel, acceptQueryCache, startPlannerQuery, answerPlannerQuery, forcePlannerQuery, runEditQuery, cancelBackendQuery, type QueryResponse, type PlannerResponse, type HistoryEntry, type HealthResponse } from '../lib/api'

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
  const [abortController, setAbortController] = useState<AbortController | null>(null)
  const [activeQueryId, setActiveQueryId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthFailed, setHealthFailed] = useState(false)
  const [viewMode, setViewMode] = useState<'chart' | 'table'>('table')
  const [chartKind, setChartKind] = useState<ChartKind>('bar')
  const [chartConfig, setChartConfig] = useState<ChartConfig | null>(null)
  const [currentQuery, setCurrentQuery] = useState('')

  const [hasCached, setHasCached] = useState(false)
  const [showCacheToast, setShowCacheToast] = useState(false)
  // Planner clarification flow
  const [clarifying, setClarifying] = useState<{ question: string; sessionId: string; plannerPrompt?: string } | null>(null)
  const [clarifyAnswer, setClarifyAnswer] = useState('')
  const [activeTargetDb, setActiveTargetDb] = useState('macht413')
  // Model switcher state
  const AVAILABLE_MODELS = [
    { id: 'gemini-3.1-flash-lite',            label: 'Gemini 3.1 Flash Lite',  badge: 'fast'    },
    { id: 'gemini-3.5-flash',                 label: 'Gemini 3.5 Flash',        badge: 'latest'  },
    { id: 'openai/gpt-oss-20b',               label: 'GPT OSS 20B',             badge: 'nvidia' },
    { id: 'qwen/qwen3-next-80b-a3b-instruct', label: 'Qwen 80B A3B',            badge: 'nvidia' },
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



  const handleAcceptCache = async () => {
    if (!result || !currentQuery || hasCached) return
    try {
      await acceptQueryCache(currentQuery, result.sql, result.row_count)
      setHasCached(true)
      setShowCacheToast(true)
      setTimeout(() => setShowCacheToast(false), 3000)
    } catch (err: any) {
      console.error('Failed to accept cache:', err)
      // Silently fail on export, no need to alert
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

  // Apply a finished (status=ready or single-shot) result to the UI.
  // The backend returns a 200 with an `error` field on query-logic failure, so
  // we always store the result to keep the debug panels visible.
  const applyResult = (res: QueryResponse) => {
    setResult(res)
    setHasCached(false)
    setShowCacheToast(false)
    if (res.error) {
      setError(res.error)
      return
    }
    // Auto-select chart kind based on data shape
    let kind: ChartKind | null = null
    if (res.chart_type === 'line') {
      kind = 'line'
    } else if (res.chart_type === 'bar') {
      // Only use stacked-bar when the numeric columns are clearly parts of a
      // whole (their names contain 'pct', 'percent', 'ratio', or 'share').
      const numericCols = (res.columns ?? []).filter(c => {
        const s = res.rows?.[0]?.[c]
        return typeof s === 'number' || (!isNaN(Number(s)) && s !== '')
      })
      const partsOfWhole = numericCols.length > 2 && numericCols.every(c => {
        const cl = c.toLowerCase()
        return cl.includes('pct') || cl.includes('percent') ||
               cl.includes('ratio') || cl.includes('share') ||
               cl.includes('fraction')
      })
      kind = partsOfWhole ? 'stacked-bar' : 'bar'
    }

    if (kind) {
      setChartKind(kind)
      setViewMode('chart')
      // Build the default chart configuration (live-only: resets each query).
      setChartConfig(buildDefaultConfig(res.columns ?? [], res.rows ?? [], kind))
    } else {
      setViewMode('table')
      setChartConfig(null)
    }
  }

  // Route a planner response: a clarifying turn shows the question UI; a ready
  // turn renders results. Both carry `debug_planner_prompt` so the planner's
  // contribution is always visible.
  const processPlannerResponse = async (res: PlannerResponse) => {
    if (res.status === 'clarifying') {
      setClarifying({
        question: res.question ?? 'Could you clarify your request?',
        sessionId: res.session_id,
        plannerPrompt: res.debug_planner_prompt,
      })
      setResult(null)
      return
    }
    setClarifying(null)
    applyResult(res)
    await refreshHistory()
  }

  const cancelQuery = () => {
    if (abortController) {
      abortController.abort()
      setAbortController(null)
    }
    if (activeQueryId) {
      cancelBackendQuery(activeQueryId)
      setActiveQueryId(null)
    }
  }

  const handleQuery = async (payload: string | File, mode: InputMode = 'nl', targetDb: string = 'macht413') => {
    setLoading(true)
    setError(null)
    setClarifying(null)
    setActiveTargetDb(targetDb)
    if (typeof payload === 'string') setCurrentQuery(payload)
    else setCurrentQuery(`[Image] ${payload.name}`)
    
    const controller = new AbortController()
    setAbortController(controller)
    const queryId = Date.now().toString()
    setActiveQueryId(queryId)
    
    try {
      // Natural-language queries go through the Planner pipeline (clarification +
      // IntentSpec). SQL and image modes keep their existing single-shot paths.
      if (mode === 'nl') {
        const res = await startPlannerQuery(payload as string, targetDb, controller.signal, queryId)
        await processPlannerResponse(res)
      } else {
        const res = mode === 'image' && payload instanceof File
          ? await runImageQuery(payload, targetDb, controller.signal)
          : await runSqlDirect(payload as string, targetDb, controller.signal)
        if (mode === 'image' && res.inferred_query) setCurrentQuery(res.inferred_query)
        applyResult(res)
        await refreshHistory()
      }
    } catch (e: any) {
      if (e.name === 'AbortError' || e.message?.includes('aborted')) {
        setError('Query cancelled by user.')
      } else {
        setError(e.message)
      }
    } finally {
      setLoading(false)
      setAbortController(null)
    }
  }

  // Submit the user's answer to a clarifying question.
  const handleClarifyAnswer = async () => {
    if (!clarifying || !clarifyAnswer.trim()) return
    setLoading(true)
    setError(null)
    const controller = new AbortController()
    setAbortController(controller)
    const queryId = Date.now().toString()
    setActiveQueryId(queryId)
    try {
      const res = await answerPlannerQuery(clarifying.sessionId, clarifyAnswer.trim(), controller.signal, queryId)
      setClarifyAnswer('')
      await processPlannerResponse(res)
    } catch (e: any) {
      setError(e.name === 'AbortError' ? 'Query cancelled by user.' : e.message)
    } finally {
      setLoading(false)
      setAbortController(null)
    }
  }

  // "Just run it" — skip remaining questions; the planner fills gaps with defaults.
  const handleClarifyForce = async () => {
    if (!clarifying) return
    setLoading(true)
    setError(null)
    const controller = new AbortController()
    setAbortController(controller)
    const queryId = Date.now().toString()
    setActiveQueryId(queryId)
    try {
      const res = await forcePlannerQuery(clarifying.sessionId, activeTargetDb, controller.signal, queryId)
      setClarifyAnswer('')
      await processPlannerResponse(res)
    } catch (e: any) {
      setError(e.name === 'AbortError' ? 'Query cancelled by user.' : e.message)
    } finally {
      setLoading(false)
      setAbortController(null)
    }
  }

  const [editInstruction, setEditInstruction] = useState('')
  const [isEditing, setIsEditing] = useState(false)

  const handleEditSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!editInstruction.trim() || !result || !result.sql) return
    
    setLoading(true)
    setError(null)
    setIsEditing(true)
    
    const controller = new AbortController()
    setAbortController(controller)
    const queryId = Date.now().toString()
    setActiveQueryId(queryId)
    
    try {
      const res = await runEditQuery(currentQuery, result.sql, editInstruction.trim(), activeTargetDb, controller.signal, queryId)
      applyResult(res)
      setEditInstruction('')
      await refreshHistory()
    } catch (e: any) {
      setError(e.name === 'AbortError' ? 'Query cancelled by user.' : e.message)
    } finally {
      setLoading(false)
      setIsEditing(false)
      setAbortController(null)
    }
  }

  // Always allow chart view when there's result data (guard against error response with no columns)
  const canChart = result && !result.error && (result.columns?.length ?? 0) >= 2

  return (
    <div style={{ minHeight: '100vh', background: 'var(--theme-bg)', color: 'var(--theme-tx-primary)', fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace' }}>
      
      {showCacheToast && (
        <div style={{
          position: 'fixed', top: '24px', left: '50%', transform: 'translateX(-50%)', zIndex: 9999,
          background: '#22c55e', color: '#fff', padding: '10px 20px', borderRadius: '8px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)', display: 'flex', alignItems: 'center', gap: '8px',
          fontSize: '14px', fontWeight: 600, animation: 'fadeIn 0.2s ease-out'
        }}>
          <Check size={16} /> Saved to AI cache
        </div>
      )}

      {/* ── Header ── */}
      <header style={{ borderBottom: '1px solid var(--theme-border)', background: 'var(--theme-surface-1)' }}>
        <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '56px' }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '12px', textDecoration: 'none' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <HPELogo width={98} height={28} />
            </div>
            <div>
              <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--theme-tx-primary)', letterSpacing: '-0.02em' }}>QueryCraft</div>
              <div style={{ fontSize: '11px', color: 'var(--theme-tx-secondary)' }}>HPE NonStop Performance Analytics</div>
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
                border: '1px solid var(--theme-border)',
                background: 'var(--theme-surface-2)',
                color: 'var(--theme-tx-primary)',
                fontSize: '12px',
                textDecoration: 'none',
                transition: 'all 0.2s',
                fontWeight: 500
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
                border: '1px solid var(--theme-border)',
                background: 'var(--theme-surface-2)',
                color: 'var(--theme-tx-primary)',
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
                border: '1px solid var(--theme-border)',
                background: 'var(--theme-surface-2)',
                color: 'var(--theme-tx-primary)',
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
                  border: `1px solid ${modelDropdownOpen ? 'rgba(59,130,246,0.5)' : 'var(--theme-border)'}`,
                  background: modelDropdownOpen ? 'rgba(59,130,246,0.08)' : 'var(--theme-surface-2)',
                  color: 'var(--theme-tx-primary)', fontSize: '12px', cursor: modelSwitching ? 'not-allowed' : 'pointer',
                  fontFamily: 'inherit', fontWeight: 500, transition: 'all 0.15s',
                  opacity: modelSwitching ? 0.6 : 1,
                }}
              >
                <Cpu size={13} style={{ color: 'var(--theme-accent)' }} />
                <span style={{ maxWidth: '140px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {AVAILABLE_MODELS.find(m => m.id === activeModel)?.label ?? activeModel}
                </span>
                <ChevronDown
                  size={11}
                  style={{
                    color: 'var(--theme-tx-muted)',
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
                    background: 'var(--theme-surface-1)', border: '1px solid var(--theme-border)',
                    borderRadius: '10px', overflow: 'hidden',
                    boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
                    animation: 'slideDown 0.15s ease-out',
                  }}>
                    <div style={{
                      padding: '8px 12px 6px',
                      fontSize: '10px', fontWeight: 600, color: 'var(--theme-tx-secondary)',
                      letterSpacing: '0.08em', textTransform: 'uppercase',
                      borderBottom: '1px solid var(--theme-border)',
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
                            color: isActive ? 'var(--theme-tx-primary)' : 'var(--theme-tx-secondary)',
                            fontSize: '12px', cursor: 'pointer',
                            fontFamily: 'inherit', textAlign: 'left',
                            transition: 'background 0.1s',
                            borderLeft: isActive ? '2px solid #3b82f6' : '2px solid transparent',
                          }}
                          onMouseEnter={e => {
                            if (!isActive) (e.currentTarget as HTMLElement).style.background = 'var(--theme-border)'
                          }}
                          onMouseLeave={e => {
                            if (!isActive) (e.currentTarget as HTMLElement).style.background = 'transparent'
                          }}
                        >
                          <span style={{ fontWeight: isActive ? 600 : 400 }}>{m.label}</span>
                          <span style={{
                            fontSize: '10px', padding: '2px 7px', borderRadius: '999px',
                            background: badgeColor[m.badge] ?? 'rgba(255,255,255,0.05)',
                            color: badgeText[m.badge] ?? 'var(--theme-tx-secondary)',
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
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '11px', color: 'var(--theme-tx-muted)' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: health.db_connected ? 'var(--theme-accent)' : '#ef4444' }} />
                  {health.db_connected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            )}
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* ── Main ── */}
      <main style={{ maxWidth: '1280px', margin: '0 auto', padding: '32px 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '24px', alignItems: 'start' }}>

          {/* Left column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

            {/* Query Input */}
            <div style={{ borderRadius: '12px', border: '1px solid var(--theme-border)', background: 'var(--theme-surface-1)', padding: '20px' }}>
              <QueryInput
                onSubmit={handleQuery}
                loading={loading}
                error={error}
                initialValue={currentQuery}
                onCancel={cancelQuery}
              />
            </div>

            {/* Clarifying question (Planner pipeline) */}
            {clarifying && (
              <div style={{
                display: 'flex', flexDirection: 'column', gap: '14px',
                borderRadius: '12px', border: '1px solid rgba(59,130,246,0.3)',
                background: 'rgba(59,130,246,0.05)', padding: '18px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Sparkles size={14} style={{ color: '#60a5fa' }} />
                  <span style={{ fontSize: '11px', fontWeight: 600, color: '#60a5fa', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                    Planner needs a clarification
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: '14px', color: 'var(--theme-tx-primary)', lineHeight: 1.5 }}>
                  {clarifying.question}
                </p>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'stretch' }}>
                  <input
                    value={clarifyAnswer}
                    onChange={e => setClarifyAnswer(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter' && !loading) handleClarifyAnswer() }}
                    placeholder="Type your answer…"
                    disabled={loading}
                    autoFocus
                    style={{
                      flex: 1, background: 'var(--theme-surface-2)', border: '1px solid var(--theme-border)',
                      borderRadius: '8px', padding: '10px 12px', fontSize: '13px',
                      color: 'var(--theme-tx-primary)', outline: 'none', fontFamily: 'inherit',
                    }}
                  />
                  <button
                    onClick={handleClarifyAnswer}
                    disabled={loading || !clarifyAnswer.trim()}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '6px',
                      padding: '0 16px', borderRadius: '8px', border: 'none',
                      background: loading || !clarifyAnswer.trim() ? 'var(--theme-surface-2)' : 'var(--theme-accent)',
                      color: loading || !clarifyAnswer.trim() ? 'var(--theme-tx-secondary)' : 'var(--theme-tx-primary)',
                      cursor: loading || !clarifyAnswer.trim() ? 'not-allowed' : 'pointer',
                      fontSize: '12px', fontWeight: 600, fontFamily: 'inherit',
                    }}
                  >
                    {loading
                      ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
                      : <Send size={12} />}
                    Answer
                  </button>
                  <button
                    onClick={handleClarifyForce}
                    disabled={loading}
                    title="Skip remaining questions — fill gaps with defaults"
                    style={{
                      display: 'flex', alignItems: 'center', gap: '6px',
                      padding: '0 14px', borderRadius: '8px',
                      border: '1px solid var(--theme-border)', background: 'transparent',
                      color: 'var(--theme-tx-secondary)', cursor: loading ? 'not-allowed' : 'pointer',
                      fontSize: '12px', fontWeight: 600, fontFamily: 'inherit',
                    }}
                  >
                    Just run it
                  </button>
                </div>

              </div>
            )}

            {/* Results */}
            {result && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <SQLPreview
                  sql={result.sql ?? ''}
                  cacheHit={result.cache_hit ?? false}
                  executionTimeMs={result.execution_time_ms ?? 0}
                  domain={result.domain ?? ''}
                />

                {/* Refine / Edit UI */}
                {!result.error && (
                  <form onSubmit={handleEditSubmit} style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                    <input 
                      type="text" 
                      value={editInstruction}
                      onChange={e => setEditInstruction(e.target.value)}
                      placeholder="Refine this query (e.g. 'Sort descending', 'Add column...')"
                      style={{ flex: 1, padding: '8px 12px', background: 'var(--theme-surface-2)', border: '1px solid var(--theme-border)', borderRadius: '6px', color: 'var(--theme-tx-primary)', fontSize: '13px' }}
                      disabled={isEditing || loading}
                    />
                    <button 
                      type="submit"
                      disabled={!editInstruction.trim() || isEditing || loading}
                      style={{ padding: '8px 16px', background: 'var(--theme-accent)', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}
                    >
                      {isEditing ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
                      Refine
                    </button>
                  </form>
                )}



                {/* SQL generator debug panel — always shown when a prompt was built */}
                {result.debug_prompt && (
                  <PromptDebugPanel prompt={result.debug_prompt} rawOutput={result.raw_llm_output} />
                )}

                {/* Stats + view controls — only shown when the query succeeded */}
                {!result.error && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                  <span style={{ fontSize: '12px', color: 'var(--theme-tx-secondary)' }}>
                    {(result.row_count ?? 0).toLocaleString()} rows returned
                  </span>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>

                    {/* Chart type picker — only visible in chart mode */}
                    {viewMode === 'chart' && canChart && (
                      <div style={{
                        display: 'flex', borderRadius: '8px',
                        border: '1px solid var(--theme-border)', background: 'var(--theme-surface-1)', padding: '3px', gap: '2px',
                      }}>
                        {CHART_TYPES.map(ct => (
                          <button
                            key={ct.kind}
                            onClick={() => {
                              setChartKind(ct.kind)
                              // Reset every series to the new baseline kind,
                              // keeping X-axis, order, colours, and visibility.
                              setChartConfig(c => (c ? applyGlobalKind(c, ct.kind) : c))
                            }}
                            title={ct.label}
                            style={{
                              display: 'flex', alignItems: 'center', gap: '4px',
                              borderRadius: '6px', padding: '5px 10px', fontSize: '11px',
                              border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                              background: chartKind === ct.kind ? 'var(--theme-border)' : 'transparent',
                              color: chartKind === ct.kind ? 'var(--theme-tx-primary)' : 'var(--theme-tx-muted)',
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
                        border: '1px solid var(--theme-border)', background: 'var(--theme-surface-2)', padding: '3px',
                      }}>
                        {(['chart', 'table'] as const).map(mode => (
                          <button
                            key={mode}
                            onClick={() => setViewMode(mode)}
                            style={{
                              display: 'flex', alignItems: 'center', gap: '5px',
                              borderRadius: '6px', padding: '5px 12px', fontSize: '11px',
                              border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                              background: viewMode === mode ? 'var(--theme-border)' : 'transparent',
                              color: viewMode === mode ? 'var(--theme-tx-primary)' : 'var(--theme-tx-muted)',
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
                )} {/* end !result.error stats block */}

                {!result.error && viewMode === 'chart' && canChart && chartConfig && (
                  <ChartConfigPanel
                    columns={result.columns ?? []}
                    rows={result.rows ?? []}
                    config={chartConfig}
                    onChange={setChartConfig}
                    hideSeriesKind={chartKind === 'scatter'}
                  />
                )}

                {!result.error && (viewMode === 'chart' && canChart
                  ? <ChartView chartType={chartKind} columns={result.columns ?? []} rows={result.rows ?? []} config={chartConfig ?? undefined} />
                  : <ResultsTable columns={result.columns ?? []} rows={result.rows ?? []} />
                )}



                {/* Download */}
                {!result.error && result.sql && (
                  <div style={{ borderRadius: '12px', border: '1px solid var(--theme-border)', background: 'var(--theme-surface-1)', padding: '16px' }}>
                    <ReportDownload sql={result.sql} queryText={currentQuery} onExport={handleAcceptCache} />
                  </div>
                )}
              </div>
            )}

            {/* Empty state */}
            {!result && !loading && !error && !clarifying && (
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                borderRadius: '12px', border: '1px dashed var(--theme-border)', padding: '80px 24px', textAlign: 'center',
              }}>
                <div style={{
                  width: '52px', height: '52px', borderRadius: '50%',
                  background: 'var(--theme-surface-2)', border: '1px solid var(--theme-border)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px',
                }}>
                  <BarChart2 size={22} style={{ color: 'var(--theme-tx-muted)' }} />
                </div>
                <p style={{ fontSize: '14px', fontWeight: 500, color: 'var(--theme-tx-muted)', margin: '0 0 6px' }}>
                  Ask a question to get started
                </p>
                <p style={{ fontSize: '12px', color: 'var(--theme-tx-muted)', margin: 0 }}>
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
