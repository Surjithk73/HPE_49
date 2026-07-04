import { useState, useRef, useEffect, type KeyboardEvent, type ChangeEvent } from 'react'
import { Send, Loader2, Sparkles, Code2, Image as ImageIcon, Upload, Square } from 'lucide-react'
import { getDatabases } from '../lib/api'

export type InputMode = 'nl' | 'sql' | 'image'

interface Props {
  onSubmit: (payload: string | File, mode: InputMode, targetDb: string) => void
  loading: boolean
  error: string | null
  initialValue?: string
  initialMode?: InputMode
  onCancel?: () => void
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

export default function QueryInput({ onSubmit, loading, error, initialValue = '', initialMode = 'nl', onCancel }: Props) {
  const [mode, setMode]   = useState<InputMode>(initialMode)
  const [value, setValue] = useState(initialValue)
  const [availableDbs, setAvailableDbs] = useState<string[]>([])
  const [targetDb, setTargetDb] = useState('')
  const [imageFile, setImageFile] = useState<File | null>(null)

  useEffect(() => {
    getDatabases().then(dbs => {
      setAvailableDbs(dbs)
    }).catch(console.error)
  }, [])
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const textareaRef       = useRef<HTMLTextAreaElement>(null)
  const fileInputRef      = useRef<HTMLInputElement>(null)

  // Sync initialValue when parent changes it (e.g. history re-run)
  useEffect(() => { setValue(initialValue) }, [initialValue])

  // Revoke preview URL when it changes / on unmount
  useEffect(() => {
    return () => { if (imagePreview) URL.revokeObjectURL(imagePreview) }
  }, [imagePreview])

  // Paste support — only active in image mode
  useEffect(() => {
    if (mode !== 'image') return
    const onPaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items
      if (!items) return
      for (const item of items) {
        if (item.kind === 'file' && item.type.startsWith('image/')) {
          const f = item.getAsFile()
          if (f) { e.preventDefault(); handleFile(f); return }
        }
      }
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode])

  const handleSubmit = () => {
    if (loading) return
    if (!targetDb) {
      alert("Please select a node/database before querying.")
      return
    }
    if (mode === 'image') {
      if (!imageFile) return
      onSubmit(imageFile, mode, targetDb)
      return
    }
    const q = value.trim()
    if (!q) return
    if (q.length > MAX_QUERY_LENGTH) return   // guard — button is also disabled
    onSubmit(q, mode, targetDb)
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
    if (m !== 'image') {
      setImageFile(null)
      if (imagePreview) { URL.revokeObjectURL(imagePreview); setImagePreview(null) }
    }
    if (m !== 'image') {
      setTimeout(() => textareaRef.current?.focus(), 50)
    }
  }

  const handleFile = (f: File | null | undefined) => {
    if (!f) return
    if (!f.type.startsWith('image/')) return
    if (imagePreview) URL.revokeObjectURL(imagePreview)
    setImageFile(f)
    setImagePreview(URL.createObjectURL(f))
  }

  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    handleFile(e.target.files?.[0])
  }

  const isSql = mode === 'sql'
  const isImage = mode === 'image'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>

      {/* ── Mode toggle ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{
          display: 'flex', borderRadius: '8px',
          border: '1px solid var(--theme-border)', background: 'var(--theme-surface-2)', padding: '3px', gap: '2px',
        }}>
          {/* NL button */}
          <button
            onClick={() => switchMode('nl')}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              borderRadius: '6px', padding: '5px 14px', fontSize: '11px',
              border: 'none', cursor: 'pointer', fontFamily: 'inherit',
              fontWeight: 600, letterSpacing: '0.05em',
              background: mode === 'nl' ? 'rgba(16,185,129,0.15)' : 'transparent',
              color:      mode === 'nl' ? 'var(--theme-tab-sql-text)' : 'var(--theme-tx-muted)',
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
              background: mode === 'sql' ? 'rgba(16,185,129,0.15)' : 'transparent',
              color:      mode === 'sql' ? 'var(--theme-tab-sql-text)' : 'var(--theme-tx-muted)',
              transition: 'all 0.15s',
            }}
          >
            <Code2 size={11} />
            SQL Query
          </button>

          {/* Image button */}
          <button
            onClick={() => switchMode('image')}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              borderRadius: '6px', padding: '5px 14px', fontSize: '11px',
              border: 'none', cursor: 'pointer', fontFamily: 'inherit',
              fontWeight: 600, letterSpacing: '0.05em',
              background: mode === 'image' ? 'rgba(147,51,234,0.15)' : 'transparent',
              color:      mode === 'image' ? 'var(--theme-tab-img-text)' : 'var(--theme-tx-muted)',
              transition: 'all 0.15s',
            }}
          >
            <ImageIcon size={11} />
            Image
          </button>
        </div>

        {/* Mode hint and DB Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '11px', color: 'var(--theme-tx-muted)' }}>
            {isImage ? 'Chart image — Gemini infers an NL question, then SQL'
              : isSql ? 'Direct SQL — bypasses LLM'
              : 'AI-powered — generates SQL for you'}
          </span>
          <select 
            value={targetDb}
            onChange={(e) => setTargetDb(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              background: 'var(--theme-bg)',
              border: targetDb ? '1px solid var(--theme-border-bright)' : '1px solid #ef4444',
              color: targetDb ? 'var(--theme-tx-primary)' : '#ef4444',
              fontSize: '12px',
              outline: 'none',
              cursor: 'pointer',
              minWidth: '140px',
              boxShadow: targetDb ? 'none' : '0 0 0 1px rgba(239,68,68,0.2)'
            }}
          >
            <option value="" disabled>-- Select Node --</option>
            {availableDbs.map(db => (
              <option key={db} value={db}>{db}</option>
            ))}
          </select>
        </div>
      </div>

      {/* ── Input box ── */}
      <div style={{
        borderRadius: '10px',
        border: `1px solid ${error
          ? 'rgba(239,68,68,0.4)'
          : isImage ? 'rgba(168,85,247,0.2)'
          : isSql ? 'rgba(16,185,129,0.2)' : 'var(--theme-border)'}`,
        background: error ? 'rgba(239,68,68,0.05)' : 'var(--theme-surface-2)',
        transition: 'border-color 0.15s',
        position: 'relative',
      }}>
        {isImage ? (
          <div
            onDragOver={e => { e.preventDefault() }}
            onDrop={e => { e.preventDefault(); handleFile(e.dataTransfer.files?.[0]) }}
            onClick={() => fileInputRef.current?.click()}
            style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', gap: '10px',
              padding: imagePreview ? '14px' : '32px 16px',
              cursor: loading ? 'default' : 'pointer',
              opacity: loading ? 0.5 : 1,
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              style={{ display: 'none' }}
              onChange={onFileChange}
              disabled={loading}
            />
            {imagePreview ? (
              <>
                <img
                  src={imagePreview}
                  alt="upload preview"
                  style={{ maxWidth: '100%', maxHeight: '240px', borderRadius: '6px', border: '1px solid var(--theme-border)' }}
                />
                <span style={{ fontSize: '11px', color: '#666' }}>
                  {imageFile?.name} — click to replace
                </span>
              </>
            ) : (
              <>
                <Upload size={20} style={{ color: '#c084fc' }} />
                <span style={{ fontSize: '12px', color: 'var(--theme-tx-muted)' }}>
                  Drop, paste (Ctrl+V), or click to choose a chart screenshot
                </span>
                <span style={{ fontSize: '10px', color: 'var(--theme-tx-secondary)' }}>
                  PNG / JPG · max 8 MB
                </span>
              </>
            )}
          </div>
        ) : (
        <>
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
            color: 'var(--theme-tx-primary)',
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
            fontSize: '10px', color: 'var(--theme-border)', pointerEvents: 'none',
            fontFamily: 'JetBrains Mono, monospace',
          }}>
            schema: {targetDb}
          </div>
        )}
        </>
        )}

        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          borderTop: '1px solid var(--theme-border)', padding: '8px 16px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '11px', color: 'var(--theme-tx-muted)' }}>
              {isImage
                ? (imageFile ? 'Ready — click Analyze Image' : 'Pick or drop a chart image')
                : isSql ? 'Only SELECT statements · Ctrl+Enter to run'
                : 'Ctrl+Enter to run'}
            </span>
            {/* Character counter — turns amber near limit, red at limit */}
            {!isImage && value.length > 0 && (
              <span style={{
                fontSize: '10px',
                color: value.length >= MAX_QUERY_LENGTH
                  ? '#ef4444'
                  : value.length >= MAX_QUERY_LENGTH * 0.85
                    ? '#fbbf24'
                    : 'var(--theme-border-bright)',
                transition: 'color 0.2s',
              }}>
                {value.length}/{MAX_QUERY_LENGTH}
              </span>
            )}
          </div>
          {(() => {
            if (loading && onCancel) {
              return (
                <button
                  onClick={onCancel}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    padding: '6px', borderRadius: '7px',
                    background: 'rgba(239,68,68,0.15)',
                    color: '#ef4444',
                    border: '1px solid rgba(239,68,68,0.3)',
                    cursor: 'pointer',
                    fontSize: '12px', fontWeight: 600, fontFamily: 'inherit',
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(239,68,68,0.25)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'rgba(239,68,68,0.15)'}
                >
                  <Square size={12} fill="currentColor" />
                </button>
              )
            }

            const disabled = loading
              || (isImage ? !imageFile : !value.trim() || value.length > MAX_QUERY_LENGTH)
            const bg = disabled
              ? 'var(--theme-surface-2)'
              : isImage ? '#9333ea'
              : isSql ? '#059669'
              : 'var(--theme-accent)'
            return (
              <button
                className={!disabled ? "hpe-gradient-btn" : ""}
                onClick={handleSubmit}
                disabled={disabled}
                style={{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  padding: '6px 14px', borderRadius: '7px',
                  background: bg,
                  color: disabled ? 'var(--theme-tx-secondary)' : 'var(--theme-tx-primary)',
                  border: 'none',
                  cursor: disabled ? 'not-allowed' : 'pointer',
                  fontSize: '12px', fontWeight: 600, fontFamily: 'inherit',
                  transition: 'background 0.15s',
                }}
              >
                {loading
                  ? <><Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> Running...</>
                  : isImage
                    ? <><ImageIcon size={12} /> Analyze Image</>
                    : isSql
                      ? <><Code2 size={12} /> Run SQL</>
                      : <><Send size={12} /> Generate Report</>
                }
              </button>
            )
          })()}
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
      {!isImage && !value && !loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <span style={{ fontSize: '10px', color: 'var(--theme-tx-muted)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            {isSql ? 'Example queries' : 'Try asking'}
          </span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {(isSql ? SQL_SUGGESTIONS : NL_SUGGESTIONS).map(s => (
              <button
                key={s}
                onClick={() => setValue(s)}
                style={{
                  borderRadius: isSql ? '6px' : '999px',
                  border: `1px solid ${isSql ? 'rgba(16,185,129,0.15)' : 'var(--theme-border)'}`,
                  background: 'var(--theme-surface-2)',
                  padding: isSql ? '6px 10px' : '4px 12px',
                  fontSize: '11px', color: 'var(--theme-tx-muted)',
                  cursor: 'pointer', fontFamily: isSql ? 'JetBrains Mono, monospace' : 'inherit',
                  transition: 'all 0.15s',
                  textAlign: 'left',
                  maxWidth: isSql ? '100%' : 'none',
                  whiteSpace: isSql ? 'nowrap' : 'normal',
                  overflow: 'hidden', textOverflow: 'ellipsis',
                }}
                onMouseEnter={e => {
                  const el = e.currentTarget
                  el.style.borderColor = isSql ? 'rgba(16,185,129,0.4)' : 'var(--theme-accent)'
                  el.style.color = 'var(--theme-tx-primary)'
                }}
                onMouseLeave={e => {
                  const el = e.currentTarget
                  el.style.borderColor = isSql ? 'rgba(16,185,129,0.15)' : 'var(--theme-border)'
                  el.style.color = 'var(--theme-tx-muted)'
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
