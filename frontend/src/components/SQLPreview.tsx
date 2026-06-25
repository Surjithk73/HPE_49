import { useState } from 'react'
import { Copy, Check, Zap, Clock } from 'lucide-react'

interface Props {
  sql: string
  cacheHit: boolean
  executionTimeMs: number
  domain: string
}

export default function SQLPreview({ sql, cacheHit, executionTimeMs, domain }: Props) {
  const [copied, setCopied] = useState(false)
  // Format SQL with newlines before major clauses for better readability
  const formatSQL = (rawSql: string): string => {
    let formatted = rawSql.replace(/\s+/g, ' ').trim()
    const clauses = [
      'SELECT',
      'FROM',
      'WHERE',
      'GROUP BY',
      'ORDER BY',
      'LIMIT',
      'LEFT JOIN',
      'RIGHT JOIN',
      'INNER JOIN',
      'JOIN',
      'HAVING',
      'UNION'
    ]
    clauses.forEach(clause => {
      const regex = new RegExp(`\\b${clause}\\b`, 'gi')
      formatted = formatted.replace(regex, (match) => `\n${match}`)
    })
    return formatted.trim()
  }

  const formattedSql = formatSQL(sql)

  const copy = async () => {
    await navigator.clipboard.writeText(formattedSql)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Simple keyword highlighting with digits replaced first to avoid matching style attributes
  const highlighted = formattedSql
    .replace(/\b(\d+)\b/g, '<span style="color:#fbbf24">$1</span>')
    .replace(/\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|LIMIT|JOIN|ON|AS|AVG|SUM|COUNT|MAX|MIN|DISTINCT|AND|OR|NOT|IN|HAVING|LEFT|RIGHT|INNER|OUTER)\b/g,
      '<span style="color:#60a5fa;font-weight:600">$1</span>')
    .replace(/(macht413\.\w+)/g, '<span style="color:#34d399">$1</span>')

  return (
    <div style={{
      borderRadius: '10px',
      border: '1px solid var(--theme-border)',
      background: 'var(--theme-surface-2)',
      overflow: 'hidden',
      animation: 'slideUp 0.25s ease-out',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid var(--theme-border)',
        padding: '10px 16px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--theme-tx-muted)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            Generated SQL
          </span>
          {cacheHit && (
            <span style={{
              display: 'flex', alignItems: 'center', gap: '4px',
              border: '1px solid rgba(251,191,36,0.3)', background: 'rgba(251,191,36,0.08)',
              borderRadius: '999px', padding: '2px 8px', fontSize: '11px', color: '#fbbf24',
            }}>
              <Zap size={9} /> Cached
            </span>
          )}
          <span style={{
            border: '1px solid var(--theme-border)', background: 'var(--theme-border)',
            borderRadius: '999px', padding: '2px 8px', fontSize: '11px', color: 'var(--theme-tx-muted)', textTransform: 'capitalize',
          }}>
            {domain}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: 'var(--theme-tx-secondary)' }}>
            <Clock size={10} /> {executionTimeMs}ms
          </span>
          <button
            onClick={copy}
            style={{
              display: 'flex', alignItems: 'center', gap: '5px',
              border: '1px solid var(--theme-border)', background: 'var(--theme-border)',
              borderRadius: '6px', padding: '4px 10px', fontSize: '11px',
              color: copied ? '#34d399' : 'var(--theme-tx-secondary)', cursor: 'pointer', fontFamily: 'inherit',
              transition: 'all 0.15s',
            }}
          >
            {copied ? <><Check size={11} /> Copied</> : <><Copy size={11} /> Copy</>}
          </button>
        </div>
      </div>

      {/* SQL */}
      <div style={{ overflowX: 'auto', padding: '16px' }}>
        <pre
          style={{ fontFamily: 'inherit', fontSize: '12px', lineHeight: 1.7, color: 'var(--theme-tx-primary)', margin: 0, whiteSpace: 'pre-wrap' }}
          dangerouslySetInnerHTML={{ __html: highlighted }}
        />
      </div>

      <style>{`@keyframes slideUp { from { opacity:0; transform:translateY(8px) } to { opacity:1; transform:translateY(0) } }`}</style>
    </div>
  )
}
