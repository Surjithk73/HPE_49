import { useState, useRef, type KeyboardEvent } from 'react'
import { Send, Loader2, Sparkles } from 'lucide-react'

interface Props {
  onSubmit: (query: string) => void
  loading: boolean
  error: string | null
  initialValue?: string
}

const SUGGESTIONS = [
  'Show average CPU busy time per CPU',
  'List disk reads and writes per device',
  'Show total transaction count',
  'Compare CPU and process utilization',
  'Show file open counts per system',
]

export default function QueryInput({ onSubmit, loading, error, initialValue = '' }: Props) {
  const [value, setValue] = useState(initialValue)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSubmit = () => {
    const q = value.trim()
    if (!q || loading) return
    onSubmit(q)
  }

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Label */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Sparkles size={13} style={{ color: '#3b82f6' }} />
        <span style={{ fontSize: '11px', fontWeight: 600, color: '#555', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
          Natural Language Query
        </span>
      </div>

      {/* Input box */}
      <div style={{
        borderRadius: '10px',
        border: `1px solid ${error ? 'rgba(239,68,68,0.4)' : '#2a2a2a'}`,
        background: error ? 'rgba(239,68,68,0.05)' : '#161616',
        transition: 'border-color 0.15s',
      }}
        onFocus={() => {}} // handled by CSS :focus-within below
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask anything about your HPE NonStop performance data..."
          rows={3}
          disabled={loading}
          style={{
            width: '100%',
            resize: 'none',
            background: 'transparent',
            padding: '14px 16px',
            fontSize: '13px',
            color: '#f0f0f0',
            outline: 'none',
            fontFamily: 'inherit',
            opacity: loading ? 0.5 : 1,
          }}
        />
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderTop: '1px solid #2a2a2a',
          padding: '8px 16px',
        }}>
          <span style={{ fontSize: '11px', color: '#444' }}>Ctrl+Enter to run</span>
          <button
            onClick={handleSubmit}
            disabled={!value.trim() || loading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: '7px',
              background: !value.trim() || loading ? '#1a1a1a' : '#3b82f6',
              color: !value.trim() || loading ? '#444' : '#fff',
              border: 'none',
              cursor: !value.trim() || loading ? 'not-allowed' : 'pointer',
              fontSize: '12px',
              fontWeight: 600,
              fontFamily: 'inherit',
              transition: 'background 0.15s',
            }}
          >
            {loading
              ? <><Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> Generating...</>
              : <><Send size={12} /> Generate Report</>
            }
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          borderRadius: '8px',
          border: '1px solid rgba(239,68,68,0.3)',
          background: 'rgba(239,68,68,0.08)',
          padding: '10px 14px',
          fontSize: '12px',
          color: '#f87171',
        }}>
          {error}
        </div>
      )}

      {/* Suggestions */}
      {!value && !loading && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {SUGGESTIONS.map(s => (
            <button
              key={s}
              onClick={() => setValue(s)}
              style={{
                borderRadius: '999px',
                border: '1px solid #2a2a2a',
                background: '#161616',
                padding: '4px 12px',
                fontSize: '11px',
                color: '#666',
                cursor: 'pointer',
                fontFamily: 'inherit',
                transition: 'all 0.15s',
              }}
              onMouseEnter={e => {
                (e.target as HTMLElement).style.borderColor = 'rgba(59,130,246,0.4)'
                ;(e.target as HTMLElement).style.color = '#f0f0f0'
              }}
              onMouseLeave={e => {
                (e.target as HTMLElement).style.borderColor = '#2a2a2a'
                ;(e.target as HTMLElement).style.color = '#666'
              }}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
