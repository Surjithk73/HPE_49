import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { Send, Loader2, Sparkles, Code2 } from 'lucide-react'

export type InputMode = 'nl' | 'sql'

interface Props {
  onSubmit: (query: string, mode: InputMode) => void
  loading: boolean
  error: string | null
  initialValue?: string
  initialMode?: InputMode
}

const MAX_QUERY_LENGTH = 2000   // characters — prevents runaway API calls

const NL_SUGGESTIONS = [
  'Show average CPU busy time per CPU',
  'List disk reads and writes per device',
  'Show total transaction count',
  'Compare CPU and process utilization',
  'Show file open counts per system',
]

const SQL_SUGGESTIONS = [
  'SELECT cpu_num, AVG(cpu_busy_time * 100.0 / NULLIF(delta_time, 0)) AS avg_cpu_pct FROM macht413.cpu GROUP BY cpu_num ORDER BY cpu_num',
  'SELECT device_name, SUM(reads) AS total_reads, SUM(writes) AS total_writes FROM macht413.disc GROUP BY device_name ORDER BY total_reads DESC',
  'SELECT process_name, cpu_busy_time, pres_pages_end FROM macht413.proc ORDER BY cpu_busy_time DESC LIMIT 20',
]

// Very lightweight SQL keyword highlighter — returns spans as a string
// We render it in a read-only overlay div behind the textarea
export function highlightSQL(sql: string): string {
  const keywords = /\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|GROUP BY|ORDER BY|HAVING|LIMIT|AS|AND|OR|NOT|IN|IS|NULL|DISTINCT|COUNT|SUM|AVG|MAX|MIN|NULLIF|CASE|WHEN|THEN|ELSE|END|WITH|UNION|ALL|BY)\b/gi
  const strings  = /'[^']*'/g
  const numbers  = /\b\d+(\.\d+)?\b/g
  const schema   = /\bmacht413\.\w+/g

  return sql
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(schema,   m => `<span style="color:#10b981">${m}</span>`)
    .replace(keywords, m => `<span style="color:#60a5fa;font-weight:600">${m.toUpperCase()}</span>`)
    .replace(strings,  m => `<span style="color:#f59e0b">${m}</span>`)
    .replace(numbers,  m => `<span style="color:#a78bfa">${m}</span>`)
}

export default function QueryInput({ onSubmit, loading, error, initialValue = '', initialMode = 'nl' }: Props) {
  const [mode, setMode]   = useState<InputMode>(initialMode)
  const [value, setValue] = useState(initialValue)
  const textareaRef       = useRef<HTMLTextAreaElement>(null)

  // Sync initialValue when parent changes it (e.g. history re-run)
  useEffect(() => { setValue(initialValue) }, [initialValue])

  const handleSubmit = () => {
    const q = value.trim()
    if (!q || loading) return
    if (q.length > MAX_QUERY_LENGTH) return   // guard — button is also disabled
    onSubmit(q, mode)
  }

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const switchMode = (m: InputMode) => {
    setMode(m)
    setValue('')
    setTimeout(() => textareaRef.current?.focus(), 50)
  }

  const isSql = mode === 'sql'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>

      {/* ── Mode toggle ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{
          display: 'flex', borderRadius: '8px',
          border: '1px solid #2a2a2a', background: '#0d0d0d', padding: '3px', gap: '2px',
        }}>
          {/* NL button */}
          <button
            onClick={() => switchMode('nl')}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              borderRadius: '6px', padding: '5px 14px', fontSize: '11px',
              border: 'none', cursor: 'pointer', fontFamily: 'inherit',
              fontWeight: 600, letterSpacing: '0.05em',
              background: !isSql ? 'rgba(59,130,246,0.15)' : 'transparent',
              color:      !isSql ? '#60a5fa' : '#555',
              transition: 'all 0.15s',
            }}
          >
            <Sparkles size={11} />
            Natural Language
          </button>

          {/* SQL button */}
          <button
            onClick={() => switchMode('sql')}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              borderRadius: '6px', padding: '5px 14px', fontSize: '11px',
              border: 'none', cursor: 'pointer', fontFamily: 'inherit',
              fontWeight: 600, letterSpacing: '0.05em',
              background: isSql ? 'rgba(16,185,129,0.15)' : 'transparent',
              color:      isSql ? '#34d399' : '#555',
              transition: 'all 0.15s',
            }}
          >
            <Code2 size={11} />
            SQL Query
          </button>
        </div>

        {/* Mode hint */}
        <span style={{ fontSize: '11px', color: '#333' }}>
          {isSql ? 'Direct SQL — bypasses LLM' : 'AI-powered — generates SQL for you'}
        </span>
      </div>

      {/* ── Input box ── */}
      <div style={{
        borderRadius: '10px',
        border: `1px solid ${error ? 'rgba(239,68,68,0.4)' : isSql ? 'rgba(16,185,129,0.2)' : '#2a2a2a'}`,
        background: error ? 'rgba(239,68,68,0.05)' : '#161616',
        transition: 'border-color 0.15s',
        position: 'relative',
      }}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKey}
          placeholder={
            isSql
              ? 'SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 10000'
              : 'Ask anything about your HPE NonStop performance data...'
          }
          rows={isSql ? 5 : 3}
          disabled={loading}
          spellCheck={false}
          maxLength={MAX_QUERY_LENGTH}
          style={{
            width: '100%',
            resize: isSql ? 'vertical' : 'none',
            background: 'transparent',
            padding: '14px 16px',
            fontSize: isSql ? '12px' : '13px',
            color: '#f0f0f0',
            outline: 'none',
            fontFamily: isSql ? 'JetBrains Mono, Fira Code, Consolas, monospace' : 'inherit',
            opacity: loading ? 0.5 : 1,
            lineHeight: 1.6,
            letterSpacing: isSql ? '0.01em' : 'normal',
          }}
        />

        {/* SQL mode: schema reminder badge */}
        {isSql && value === '' && (
          <div style={{
            position: 'absolute', top: '10px', right: '12px',
            fontSize: '10px', color: '#2a2a2a', pointerEvents: 'none',
            fontFamily: 'JetBrains Mono, monospace',
          }}>
            schema: macht413
          </div>
        )}

        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          borderTop: '1px solid #1c1c1c', padding: '8px 16px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '11px', color: '#333' }}>
              {isSql ? 'Only SELECT statements · Ctrl+Enter to run' : 'Ctrl+Enter to run'}
            </span>
            {/* Character counter — turns amber near limit, red at limit */}
            {value.length > 0 && (
              <span style={{
                fontSize: '10px',
                color: value.length >= MAX_QUERY_LENGTH
                  ? '#ef4444'
                  : value.length >= MAX_QUERY_LENGTH * 0.85
                    ? '#fbbf24'
                    : '#333',
                transition: 'color 0.2s',
              }}>
                {value.length}/{MAX_QUERY_LENGTH}
              </span>
            )}
          </div>
          <button
            onClick={handleSubmit}
            disabled={!value.trim() || loading || value.length > MAX_QUERY_LENGTH}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '6px 14px', borderRadius: '7px',
              background: !value.trim() || loading || value.length > MAX_QUERY_LENGTH
                ? '#1a1a1a'
                : isSql ? '#059669' : '#3b82f6',
              color: !value.trim() || loading || value.length > MAX_QUERY_LENGTH ? '#444' : '#fff',
              border: 'none',
              cursor: !value.trim() || loading || value.length > MAX_QUERY_LENGTH ? 'not-allowed' : 'pointer',
              fontSize: '12px', fontWeight: 600, fontFamily: 'inherit',
              transition: 'background 0.15s',
            }}
          >
            {loading
              ? <><Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> Running...</>
              : isSql
                ? <><Code2 size={12} /> Run SQL</>
                : <><Send size={12} /> Generate Report</>
            }
          </button>
        </div>
      </div>

      {/* ── Error ── */}
      {error && (
        <div style={{
          borderRadius: '8px', border: '1px solid rgba(239,68,68,0.3)',
          background: 'rgba(239,68,68,0.08)', padding: '10px 14px',
          fontSize: '12px', color: '#f87171', fontFamily: 'inherit',
        }}>
          {error}
        </div>
      )}

      {/* ── Suggestions ── */}
      {!value && !loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <span style={{ fontSize: '10px', color: '#333', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            {isSql ? 'Example queries' : 'Try asking'}
          </span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {(isSql ? SQL_SUGGESTIONS : NL_SUGGESTIONS).map(s => (
              <button
                key={s}
                onClick={() => setValue(s)}
                style={{
                  borderRadius: isSql ? '6px' : '999px',
                  border: `1px solid ${isSql ? 'rgba(16,185,129,0.15)' : '#2a2a2a'}`,
                  background: '#161616',
                  padding: isSql ? '6px 10px' : '4px 12px',
                  fontSize: '11px', color: '#555',
                  cursor: 'pointer', fontFamily: isSql ? 'JetBrains Mono, monospace' : 'inherit',
                  transition: 'all 0.15s',
                  textAlign: 'left',
                  maxWidth: isSql ? '100%' : 'none',
                  whiteSpace: isSql ? 'nowrap' : 'normal',
                  overflow: 'hidden', textOverflow: 'ellipsis',
                }}
                onMouseEnter={e => {
                  const el = e.currentTarget
                  el.style.borderColor = isSql ? 'rgba(16,185,129,0.4)' : 'rgba(59,130,246,0.4)'
                  el.style.color = '#f0f0f0'
                }}
                onMouseLeave={e => {
                  const el = e.currentTarget
                  el.style.borderColor = isSql ? 'rgba(16,185,129,0.15)' : '#2a2a2a'
                  el.style.color = '#555'
                }}
              >
                {isSql ? s.slice(0, 80) + (s.length > 80 ? '…' : '') : s}
              </button>
            ))}
          </div>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
