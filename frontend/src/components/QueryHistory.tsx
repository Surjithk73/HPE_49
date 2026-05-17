import { History, Zap, Clock, ChevronRight } from 'lucide-react'
import type { HistoryEntry } from '../lib/api'

interface Props {
  history: HistoryEntry[]
  onSelect: (query: string) => void
}

export default function QueryHistory({ history, onSelect }: Props) {
  if (history.length === 0) {
    return (
      <div style={{
        borderRadius: '10px', border: '1px solid #2a2a2a', background: '#111',
        padding: '32px 16px', textAlign: 'center',
      }}>
        <History size={20} style={{ color: '#333', margin: '0 auto 8px' }} />
        <p style={{ fontSize: '12px', color: '#444', margin: 0 }}>No history yet</p>
      </div>
    )
  }

  return (
    <div style={{ borderRadius: '10px', border: '1px solid #2a2a2a', background: '#111', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        borderBottom: '1px solid #2a2a2a', padding: '10px 16px',
      }}>
        <History size={13} style={{ color: '#555' }} />
        <span style={{ fontSize: '11px', fontWeight: 600, color: '#555', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
          Recent Queries
        </span>
        <span style={{
          marginLeft: 'auto', background: '#1c1c1c', border: '1px solid #2a2a2a',
          borderRadius: '999px', padding: '1px 8px', fontSize: '11px', color: '#444',
        }}>
          {history.length}
        </span>
      </div>

      {/* List */}
      <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
        {history.map((entry, i) => (
          <button
            key={entry.id}
            onClick={() => onSelect(entry.original_input)}
            style={{
              width: '100%', padding: '12px 16px', textAlign: 'left',
              background: 'transparent', border: 'none', cursor: 'pointer',
              borderBottom: i < history.length - 1 ? '1px solid rgba(42,42,42,0.5)' : 'none',
              transition: 'background 0.1s', fontFamily: 'inherit',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = '#1c1c1c')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
              <p style={{
                flex: 1, margin: 0, fontSize: '12px', color: '#ccc',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {entry.original_input}
              </p>
              <ChevronRight size={12} style={{ color: '#333', flexShrink: 0, marginTop: '2px' }} />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '5px' }}>
              <span style={{ fontSize: '11px', color: '#444' }}>
                {new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
              {entry.row_count != null && (
                <span style={{ fontSize: '11px', color: '#444' }}>{entry.row_count.toLocaleString()} rows</span>
              )}
              {entry.cache_hit === 1 && (
                <span style={{ display: 'flex', alignItems: 'center', gap: '3px', fontSize: '11px', color: '#d97706' }}>
                  <Zap size={9} /> cached
                </span>
              )}
              {entry.execution_time_ms != null && (
                <span style={{ display: 'flex', alignItems: 'center', gap: '3px', fontSize: '11px', color: '#444' }}>
                  <Clock size={9} /> {entry.execution_time_ms}ms
                </span>
              )}
              {entry.domain_category && (
                <span style={{
                  border: '1px solid #2a2a2a', borderRadius: '999px',
                  padding: '1px 7px', fontSize: '10px', color: '#444', textTransform: 'capitalize',
                }}>
                  {entry.domain_category}
                </span>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
