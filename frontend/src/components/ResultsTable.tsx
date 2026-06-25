import { useState, useMemo } from 'react'
import { ChevronUp, ChevronDown, ChevronsUpDown, ChevronLeft, ChevronRight } from 'lucide-react'

interface Props {
  columns: string[]
  rows: Record<string, unknown>[]
}

const PAGE_SIZE = 50

export default function ResultsTable({ columns, rows }: Props) {
  const [page, setPage] = useState(0)
  const [sortCol, setSortCol] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  const sorted = useMemo(() => {
    if (!sortCol) return rows
    return [...rows].sort((a, b) => {
      const av = a[sortCol], bv = b[sortCol]
      if (av == null) return 1
      if (bv == null) return -1
      const cmp = av < bv ? -1 : av > bv ? 1 : 0
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [rows, sortCol, sortDir])

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE)
  const pageRows = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  const handleSort = (col: string) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(col); setSortDir('asc') }
    setPage(0)
  }

  const fmt = (v: unknown): string => {
    if (v == null) return '—'
    if (typeof v === 'number') return v.toLocaleString()
    return String(v)
  }

  return (
    <div style={{
      borderRadius: '10px', border: '1px solid var(--theme-border)',
      background: 'var(--theme-surface-2)', overflow: 'hidden',
      animation: 'slideUp 0.25s ease-out',
    }}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
          <thead>
            <tr style={{ background: 'var(--theme-border)', borderBottom: '1px solid var(--theme-border)' }}>
              {columns.map(col => (
                <th
                  key={col}
                  onClick={() => handleSort(col)}
                  style={{
                    padding: '10px 16px', textAlign: 'left', fontWeight: 500,
                    color: '#666', cursor: 'pointer', whiteSpace: 'nowrap',
                    userSelect: 'none', transition: 'color 0.15s',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.color = 'var(--theme-tx-primary)')}
                  onMouseLeave={e => (e.currentTarget.style.color = '#666')}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    {col}
                    {sortCol === col
                      ? sortDir === 'asc'
                        ? <ChevronUp size={11} style={{ color: 'var(--theme-accent)' }} />
                        : <ChevronDown size={11} style={{ color: 'var(--theme-accent)' }} />
                      : <ChevronsUpDown size={11} style={{ opacity: 0.3 }} />
                    }
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} style={{ padding: '48px 16px', textAlign: 'center', color: 'var(--theme-tx-secondary)' }}>
                  No results returned
                </td>
              </tr>
            ) : pageRows.map((row, i) => (
              <tr
                key={i}
                style={{ borderBottom: '1px solid rgba(42,42,42,0.5)', transition: 'background 0.1s' }}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--theme-border)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                {columns.map(col => (
                  <td key={col} style={{ padding: '9px 16px', color: 'var(--theme-tx-primary)', whiteSpace: 'nowrap', fontFamily: 'inherit' }}>
                    {fmt(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        borderTop: '1px solid var(--theme-border)', padding: '10px 16px',
      }}>
        <span style={{ fontSize: '11px', color: 'var(--theme-tx-secondary)' }}>
          Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, sorted.length)} of {sorted.length.toLocaleString()} rows
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            style={{
              border: '1px solid var(--theme-border)', background: 'transparent', borderRadius: '6px',
              padding: '5px', color: '#666', cursor: page === 0 ? 'not-allowed' : 'pointer',
              opacity: page === 0 ? 0.3 : 1, display: 'flex', alignItems: 'center',
            }}
          >
            <ChevronLeft size={12} />
          </button>
          <span style={{ padding: '0 8px', fontSize: '11px', color: 'var(--theme-tx-muted)' }}>
            {page + 1} / {Math.max(1, totalPages)}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            style={{
              border: '1px solid var(--theme-border)', background: 'transparent', borderRadius: '6px',
              padding: '5px', color: '#666', cursor: page >= totalPages - 1 ? 'not-allowed' : 'pointer',
              opacity: page >= totalPages - 1 ? 0.3 : 1, display: 'flex', alignItems: 'center',
            }}
          >
            <ChevronRight size={12} />
          </button>
        </div>
      </div>

      <style>{`@keyframes slideUp { from { opacity:0; transform:translateY(8px) } to { opacity:1; transform:translateY(0) } }`}</style>
    </div>
  )
}
