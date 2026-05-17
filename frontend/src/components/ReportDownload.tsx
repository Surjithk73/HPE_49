import { useState } from 'react'
import { FileText, FileSpreadsheet, File, Loader2, Download } from 'lucide-react'
import { exportReport } from '../lib/api'

interface Props {
  sql: string
  queryText: string
}

type Format = 'csv' | 'excel' | 'pdf'

const FORMATS: { id: Format; label: string; icon: typeof FileText }[] = [
  { id: 'csv',   label: 'CSV',   icon: FileText        },
  { id: 'excel', label: 'Excel', icon: FileSpreadsheet  },
  { id: 'pdf',   label: 'PDF',   icon: File             },
]

export default function ReportDownload({ sql, queryText }: Props) {
  const [loading, setLoading] = useState<Format | null>(null)
  const [error, setError] = useState<string | null>(null)

  const download = async (fmt: Format) => {
    setLoading(fmt)
    setError(null)
    try {
      await exportReport(sql, fmt, queryText)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(null)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Download size={13} style={{ color: '#666' }} />
        <span style={{ fontSize: '11px', fontWeight: 600, color: '#555', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
          Export Report
        </span>
      </div>
      <div style={{ display: 'flex', gap: '8px' }}>
        {FORMATS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => download(id)}
            disabled={loading !== null}
            style={{
              display: 'flex', alignItems: 'center', gap: '7px',
              border: '1px solid #2a2a2a', background: '#161616',
              borderRadius: '8px', padding: '8px 16px',
              fontSize: '12px', fontWeight: 500, color: '#888',
              cursor: loading !== null ? 'not-allowed' : 'pointer',
              opacity: loading !== null && loading !== id ? 0.5 : 1,
              fontFamily: 'inherit', transition: 'all 0.15s',
            }}
            onMouseEnter={e => {
              if (!loading) {
                (e.currentTarget as HTMLElement).style.borderColor = 'rgba(59,130,246,0.4)'
                ;(e.currentTarget as HTMLElement).style.color = '#f0f0f0'
              }
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.borderColor = '#2a2a2a'
              ;(e.currentTarget as HTMLElement).style.color = '#888'
            }}
          >
            {loading === id
              ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
              : <Icon size={12} />
            }
            {label}
          </button>
        ))}
      </div>
      {error && <p style={{ fontSize: '12px', color: '#f87171', margin: 0 }}>{error}</p>}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
