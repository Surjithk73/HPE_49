import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Database, Trash2, RefreshCw, Cpu, AlertTriangle, X, CheckCircle2, Loader2 } from 'lucide-react'
import { getCache, deleteCacheEntry, clearCache, type CacheEntry } from '../lib/api'

// ── Confirm dialog (replaces browser confirm()) ───────────────────────────────
interface ConfirmDialogProps {
  message: string
  detail?: string
  confirmLabel?: string
  danger?: boolean
  onConfirm: () => void
  onCancel: () => void
}

function ConfirmDialog({ message, detail, confirmLabel = 'Confirm', danger = false, onConfirm, onCancel }: ConfirmDialogProps) {
  return (
    <div
      onClick={onCancel}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 200, padding: '24px',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: '#111', border: '1px solid #2a2a2a', borderRadius: '12px',
          padding: '24px', width: '100%', maxWidth: '400px',
          fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
          <AlertTriangle size={16} style={{ color: danger ? '#ef4444' : '#fbbf24', flexShrink: 0 }} />
          <span style={{ fontSize: '14px', fontWeight: 600, color: '#f0f0f0' }}>{message}</span>
        </div>
        {detail && (
          <p style={{ fontSize: '12px', color: '#666', margin: '0 0 20px', lineHeight: 1.6 }}>{detail}</p>
        )}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
          <button
            onClick={onCancel}
            style={{
              padding: '7px 16px', borderRadius: '7px', border: '1px solid #2a2a2a',
              background: 'transparent', color: '#888', fontSize: '12px',
              cursor: 'pointer', fontFamily: 'inherit',
            }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            style={{
              padding: '7px 16px', borderRadius: '7px', border: 'none',
              background: danger ? '#ef4444' : '#3b82f6', color: '#fff',
              fontSize: '12px', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
            }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Toast notification ────────────────────────────────────────────────────────
interface ToastProps { message: string; type: 'success' | 'error' }

function Toast({ message, type }: ToastProps) {
  return (
    <div style={{
      position: 'fixed', bottom: '24px', right: '24px', zIndex: 300,
      display: 'flex', alignItems: 'center', gap: '8px',
      background: type === 'success' ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
      border: `1px solid ${type === 'success' ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
      borderRadius: '8px', padding: '10px 16px',
      fontSize: '12px', color: type === 'success' ? '#34d399' : '#f87171',
      fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace',
      animation: 'slideUp 0.25s ease-out',
    }}>
      {type === 'success'
        ? <CheckCircle2 size={13} />
        : <AlertTriangle size={13} />
      }
      {message}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function CacheManagement() {
  const [entries, setEntries]     = useState<CacheEntry[]>([])
  const [loading, setLoading]     = useState(true)
  const [deleting, setDeleting]   = useState<string | null>(null)
  const [toast, setToast]         = useState<ToastProps | null>(null)
  const [confirm, setConfirm]     = useState<ConfirmDialogProps | null>(null)

  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3000)
  }

  const loadCache = async () => {
    setLoading(true)
    try {
      const data = await getCache()
      setEntries(data.entries)
    } catch (err) {
      showToast('Failed to load cache', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadCache() }, [])

  const handleDelete = (entry: CacheEntry) => {
    setConfirm({
      message: 'Delete this cache entry?',
      detail: entry.query.length > 100 ? entry.query.slice(0, 100) + '…' : entry.query,
      confirmLabel: 'Delete',
      danger: true,
      onCancel: () => setConfirm(null),
      onConfirm: async () => {
        setConfirm(null)
        setDeleting(entry.query)
        try {
          await deleteCacheEntry(entry.query)
          await loadCache()
          showToast('Entry deleted', 'success')
        } catch {
          showToast('Failed to delete entry', 'error')
        } finally {
          setDeleting(null)
        }
      },
    })
  }

  const handleClearAll = () => {
    setConfirm({
      message: `Clear all ${entries.length} cached entries?`,
      detail: 'This removes every cached query–SQL pair. The cache will rebuild as new queries are run.',
      confirmLabel: 'Clear All',
      danger: true,
      onCancel: () => setConfirm(null),
      onConfirm: async () => {
        setConfirm(null)
        setLoading(true)
        try {
          await clearCache()
          await loadCache()
          showToast('Cache cleared', 'success')
        } catch {
          showToast('Failed to clear cache', 'error')
          setLoading(false)
        }
      },
    })
  }

  return (
    <div style={{
      minHeight: '100vh', background: '#0a0a0a', color: '#f0f0f0',
      fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace',
    }}>

      {/* Header */}
      <header style={{ borderBottom: '1px solid #1c1c1c', background: '#111' }}>
        <div style={{
          maxWidth: '1280px', margin: '0 auto', padding: '0 24px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '56px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '32px', height: '32px', borderRadius: '8px',
              background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Cpu size={15} style={{ color: '#3b82f6' }} />
            </div>
            <div>
              <div style={{ fontSize: '14px', fontWeight: 700, letterSpacing: '-0.02em' }}>QueryCraft</div>
              <div style={{ fontSize: '11px', color: '#444' }}>Cache Management</div>
            </div>
          </div>
          <Link
            to="/"
            style={{
              padding: '7px 14px', borderRadius: '8px', border: '1px solid #2a2a2a',
              background: '#161616', color: '#f0f0f0', fontSize: '12px',
              textDecoration: 'none', fontWeight: 500,
            }}
          >
            ← Dashboard
          </Link>
        </div>
      </header>

      <main style={{ maxWidth: '1280px', margin: '0 auto', padding: '32px 24px' }}>

        {/* Stats bar */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          borderRadius: '10px', border: '1px solid #1c1c1c', background: '#111',
          padding: '16px 20px', marginBottom: '24px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Database size={15} style={{ color: '#3b82f6' }} />
            <span style={{ fontSize: '13px', color: '#888' }}>
              <span style={{ fontSize: '20px', fontWeight: 700, color: '#f0f0f0' }}>
                {loading ? '—' : entries.length}
              </span>
              {' '}cached {entries.length === 1 ? 'entry' : 'entries'}
            </span>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={loadCache}
              disabled={loading}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '7px 14px', borderRadius: '7px', border: '1px solid #2a2a2a',
                background: '#161616', color: loading ? '#444' : '#f0f0f0',
                fontSize: '12px', cursor: loading ? 'not-allowed' : 'pointer',
                fontFamily: 'inherit', fontWeight: 500,
              }}
            >
              {loading
                ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
                : <RefreshCw size={12} />
              }
              Refresh
            </button>
            <button
              onClick={handleClearAll}
              disabled={loading || entries.length === 0}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '7px 14px', borderRadius: '7px', border: '1px solid rgba(239,68,68,0.3)',
                background: 'rgba(239,68,68,0.08)', color: loading || entries.length === 0 ? '#555' : '#f87171',
                fontSize: '12px', cursor: loading || entries.length === 0 ? 'not-allowed' : 'pointer',
                fontFamily: 'inherit', fontWeight: 500,
              }}
            >
              <Trash2 size={12} />
              Clear All
            </button>
          </div>
        </div>

        {/* Empty state */}
        {!loading && entries.length === 0 && (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', borderRadius: '12px',
            border: '1px dashed #1c1c1c', padding: '80px 24px', textAlign: 'center',
          }}>
            <div style={{
              width: '52px', height: '52px', borderRadius: '50%',
              background: '#161616', border: '1px solid #2a2a2a',
              display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px',
            }}>
              <Database size={22} style={{ color: '#333' }} />
            </div>
            <p style={{ fontSize: '14px', fontWeight: 500, color: '#555', margin: '0 0 6px' }}>
              Cache is empty
            </p>
            <p style={{ fontSize: '12px', color: '#333', margin: 0 }}>
              Run queries from the dashboard to populate it
            </p>
          </div>
        )}

        {/* Loading skeleton */}
        {loading && entries.length === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {[1, 2, 3].map(i => (
              <div key={i} style={{
                borderRadius: '10px', border: '1px solid #1c1c1c',
                background: '#111', padding: '20px', opacity: 0.5,
              }}>
                <div style={{ height: '14px', background: '#1c1c1c', borderRadius: '4px', width: '60%', marginBottom: '12px' }} />
                <div style={{ height: '10px', background: '#1c1c1c', borderRadius: '4px', width: '90%' }} />
              </div>
            ))}
          </div>
        )}

        {/* Entry list */}
        {entries.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {entries.map(entry => (
              <div
                key={entry.id}
                style={{
                  borderRadius: '10px', border: '1px solid #1c1c1c',
                  background: '#111', padding: '20px',
                  opacity: deleting === entry.query ? 0.5 : 1,
                  transition: 'opacity 0.2s',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>

                    {/* Query */}
                    <div style={{ marginBottom: '12px' }}>
                      <span style={{
                        fontSize: '10px', fontWeight: 600, color: '#3b82f6',
                        letterSpacing: '0.08em', textTransform: 'uppercase',
                      }}>
                        Query
                      </span>
                      <p style={{
                        margin: '4px 0 0', fontSize: '13px', color: '#f0f0f0',
                        lineHeight: 1.5, wordBreak: 'break-word',
                      }}>
                        {entry.query}
                      </p>
                    </div>

                    {/* SQL */}
                    <div>
                      <span style={{
                        fontSize: '10px', fontWeight: 600, color: '#10b981',
                        letterSpacing: '0.08em', textTransform: 'uppercase',
                      }}>
                        Cached SQL
                      </span>
                      <pre style={{
                        margin: '4px 0 0', fontSize: '11px', color: '#888',
                        background: '#0a0a0a', border: '1px solid #1c1c1c',
                        borderRadius: '6px', padding: '10px 12px',
                        overflowX: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                        lineHeight: 1.6,
                      }}>
                        {entry.sql}
                      </pre>
                    </div>

                    {/* ID */}
                    <div style={{ marginTop: '10px' }}>
                      <span style={{ fontSize: '10px', color: '#333', fontFamily: 'monospace' }}>
                        id: {entry.id.slice(0, 16)}…
                      </span>
                    </div>
                  </div>

                  {/* Delete button */}
                  <button
                    onClick={() => handleDelete(entry)}
                    disabled={deleting === entry.query}
                    title="Delete this cache entry"
                    style={{
                      flexShrink: 0, width: '32px', height: '32px',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      borderRadius: '7px', border: '1px solid rgba(239,68,68,0.2)',
                      background: 'rgba(239,68,68,0.06)', color: '#f87171',
                      cursor: deleting === entry.query ? 'not-allowed' : 'pointer',
                      transition: 'all 0.15s',
                    }}
                    onMouseEnter={e => {
                      if (!deleting) {
                        (e.currentTarget as HTMLElement).style.background = 'rgba(239,68,68,0.2)'
                        ;(e.currentTarget as HTMLElement).style.borderColor = 'rgba(239,68,68,0.5)'
                      }
                    }}
                    onMouseLeave={e => {
                      (e.currentTarget as HTMLElement).style.background = 'rgba(239,68,68,0.06)'
                      ;(e.currentTarget as HTMLElement).style.borderColor = 'rgba(239,68,68,0.2)'
                    }}
                  >
                    {deleting === entry.query
                      ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} />
                      : <X size={13} />
                    }
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Confirm dialog */}
      {confirm && <ConfirmDialog {...confirm} />}

      {/* Toast */}
      {toast && <Toast {...toast} />}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes slideUp { from { opacity:0; transform:translateY(8px) } to { opacity:1; transform:translateY(0) } }
      `}</style>
    </div>
  )
}
