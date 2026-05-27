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

/**
 * Capture the currently visible Recharts chart as a base64 PNG.
 *
 * Recharts renders an SVG inside a div with class "recharts-wrapper".
 * We serialize that SVG to a data URL, draw it onto an offscreen canvas,
 * and return the PNG bytes as a base64 string.
 *
 * Returns null if no chart is visible or capture fails — the PDF will
 * fall back to the server-side matplotlib chart in that case.
 */
async function captureChartImage(): Promise<string | null> {
  try {
    const wrapper = document.querySelector('.recharts-wrapper') as HTMLElement | null
    if (!wrapper) return null

    const svg = wrapper.querySelector('svg')
    if (!svg) return null

    const svgData = new XMLSerializer().serializeToString(svg)
    const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(svgBlob)

    return await new Promise<string | null>((resolve) => {
      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement('canvas')
        // Use the actual rendered dimensions for crisp output
        canvas.width  = svg.clientWidth  || 800
        canvas.height = svg.clientHeight || 360
        const ctx = canvas.getContext('2d')
        if (!ctx) { URL.revokeObjectURL(url); resolve(null); return }
        // White background so the chart is readable on the PDF white page
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, canvas.width, canvas.height)
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
        URL.revokeObjectURL(url)
        // Strip the "data:image/png;base64," prefix — backend expects raw base64
        resolve(canvas.toDataURL('image/png').split(',')[1])
      }
      img.onerror = () => { URL.revokeObjectURL(url); resolve(null) }
      img.src = url
    })
  } catch {
    return null
  }
}

export default function ReportDownload({ sql, queryText }: Props) {
  const [loading, setLoading] = useState<Format | null>(null)
  const [error, setError] = useState<string | null>(null)

  // PDF options modal state
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [includeChart, setIncludeChart] = useState(true)
  const [includeTable, setIncludeTable] = useState(true)
  const [chartMode, setChartMode] = useState<'auto' | 'custom'>('auto')
  const [customCharts, setCustomCharts] = useState<string[]>(['bar'])

  const download = async (fmt: Format) => {
    if (fmt === 'pdf') {
      setIsModalOpen(true)
      return
    }
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

  const handlePdfExport = async () => {
    setIsModalOpen(false)
    setLoading('pdf')
    setError(null)
    try {
      const chartTypes = includeChart
        ? (chartMode === 'auto' ? ['auto'] : customCharts)
        : []

      // Capture the UI chart so the PDF matches exactly what the user sees.
      // Falls back to server-side matplotlib if capture fails or chart is hidden.
      const chartImageBase64 = includeChart ? await captureChartImage() : null

      await exportReport(sql, 'pdf', queryText, includeChart, includeTable, chartTypes, chartImageBase64 ?? undefined)
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

      {/* PDF Export Preferences Modal */}
      {isModalOpen && (
        <div className="pdf-modal-overlay">
          <div className="pdf-modal-container">
            <h3 className="pdf-modal-title">PDF Export Options</h3>
            <p className="pdf-modal-subtitle">Customize the layout and contents of your PDF report.</p>

            {/* Option 1: Include Table */}
            <div className="pdf-modal-section">
              <label className="pdf-option-label">
                <input
                  type="checkbox"
                  className="pdf-custom-checkbox"
                  checked={includeTable}
                  onChange={(e) => setIncludeTable(e.target.checked)}
                />
                <div className="pdf-option-info">
                  <span className="pdf-option-title">Include Data Table</span>
                  <span className="pdf-option-desc">Render the query result rows as a structured table.</span>
                </div>
              </label>
            </div>

            {/* Option 2: Include Chart */}
            <div className="pdf-modal-section">
              <label className="pdf-option-label">
                <input
                  type="checkbox"
                  className="pdf-custom-checkbox"
                  checked={includeChart}
                  onChange={(e) => setIncludeChart(e.target.checked)}
                />
                <div className="pdf-option-info">
                  <span className="pdf-option-title">Include Visualizations (Charts)</span>
                  <span className="pdf-option-desc">Embed server-side charts based on query results.</span>
                </div>
              </label>

              {/* Suboptions for Chart Types */}
              {includeChart && (
                <div className="pdf-chart-suboptions">
                  <label className="pdf-sub-radio-label">
                    <input
                      type="radio"
                      name="chartMode"
                      className="pdf-custom-radio"
                      checked={chartMode === 'auto'}
                      onChange={() => setChartMode('auto')}
                    />
                    <span>Auto-predict best chart (Recommended)</span>
                  </label>

                  <label className="pdf-sub-radio-label">
                    <input
                      type="radio"
                      name="chartMode"
                      className="pdf-custom-radio"
                      checked={chartMode === 'custom'}
                      onChange={() => setChartMode('custom')}
                    />
                    <span>Select custom chart types:</span>
                  </label>

                  {chartMode === 'custom' && (
                    <div className="pdf-custom-charts-list">
                      <label className="pdf-sub-checkbox-label">
                        <input
                          type="checkbox"
                          className="pdf-custom-checkbox-mini"
                          checked={customCharts.includes('bar')}
                          onChange={(e) => {
                            if (e.target.checked) setCustomCharts([...customCharts, 'bar'])
                            else setCustomCharts(customCharts.filter(c => c !== 'bar'))
                          }}
                        />
                        <span>Bar Chart</span>
                      </label>
                      <label className="pdf-sub-checkbox-label">
                        <input
                          type="checkbox"
                          className="pdf-custom-checkbox-mini"
                          checked={customCharts.includes('line')}
                          onChange={(e) => {
                            if (e.target.checked) setCustomCharts([...customCharts, 'line'])
                            else setCustomCharts(customCharts.filter(c => c !== 'line'))
                          }}
                        />
                        <span>Line Chart</span>
                      </label>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Modal Actions */}
            <div className="pdf-modal-actions">
              <button
                type="button"
                className="pdf-btn-cancel"
                onClick={() => setIsModalOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="pdf-btn-generate"
                disabled={!includeTable && (!includeChart || (chartMode === 'custom' && customCharts.length === 0))}
                onClick={handlePdfExport}
              >
                Generate PDF
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Styled JSX Stylesheet */}
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .pdf-modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.75);
          backdrop-filter: blur(8px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 9999;
          animation: fadeIn 0.25s ease-out;
        }

        .pdf-modal-container {
          background: linear-gradient(145deg, #18181b 0%, #09090b 100%);
          border: 1px solid rgba(255, 255, 255, 0.08);
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.8), inset 0 1px 0 rgba(255, 255, 255, 0.05);
          border-radius: 16px;
          width: 420px;
          padding: 28px;
          color: #f4f4f5;
          font-family: inherit;
          animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .pdf-modal-title {
          margin: 0 0 6px 0;
          font-size: 18px;
          font-weight: 600;
          letter-spacing: -0.01em;
          background: linear-gradient(to right, #3b82f6, #60a5fa);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .pdf-modal-subtitle {
          margin: 0 0 24px 0;
          font-size: 12px;
          color: #71717a;
          line-height: 1.5;
        }

        .pdf-modal-section {
          border-bottom: 1px solid rgba(255, 255, 255, 0.04);
          padding: 16px 0;
        }
        .pdf-modal-section:first-of-type {
          padding-top: 0;
        }
        .pdf-modal-section:last-of-type {
          border-bottom: none;
          padding-bottom: 0;
        }

        .pdf-option-label {
          display: flex;
          align-items: flex-start;
          gap: 14px;
          cursor: pointer;
          user-select: none;
        }

        .pdf-option-info {
          display: flex;
          flex-direction: column;
          gap: 3px;
        }

        .pdf-option-title {
          font-size: 14px;
          font-weight: 500;
          color: #e4e4e7;
        }

        .pdf-option-desc {
          font-size: 11px;
          color: #71717a;
          line-height: 1.4;
        }

        /* Custom Checkbox Styling */
        .pdf-custom-checkbox {
          appearance: none;
          width: 18px;
          height: 18px;
          border: 1px solid #3f3f46;
          border-radius: 4px;
          background: #18181b;
          cursor: pointer;
          position: relative;
          transition: all 0.2s;
          flex-shrink: 0;
          margin-top: 2px;
        }
        .pdf-custom-checkbox:checked {
          background: #3b82f6;
          border-color: #3b82f6;
          box-shadow: 0 0 10px rgba(59, 130, 246, 0.4);
        }
        .pdf-custom-checkbox:checked::after {
          content: "✓";
          position: absolute;
          color: white;
          font-size: 12px;
          font-weight: bold;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
        }

        /* Custom Radio button Styling */
        .pdf-custom-radio {
          appearance: none;
          width: 16px;
          height: 16px;
          border: 1px solid #3f3f46;
          border-radius: 50%;
          background: #18181b;
          cursor: pointer;
          position: relative;
          transition: all 0.2s;
          flex-shrink: 0;
        }
        .pdf-custom-radio:checked {
          background: #18181b;
          border-color: #3b82f6;
          box-shadow: 0 0 8px rgba(59, 130, 246, 0.3);
        }
        .pdf-custom-radio:checked::after {
          content: "";
          position: absolute;
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #3b82f6;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
        }

        .pdf-chart-suboptions {
          margin-left: 32px;
          margin-top: 14px;
          border-left: 2px solid rgba(255, 255, 255, 0.05);
          padding-left: 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .pdf-sub-radio-label {
          display: flex;
          align-items: center;
          gap: 10px;
          font-size: 13px;
          color: #d4d4d8;
          cursor: pointer;
          user-select: none;
        }

        .pdf-custom-charts-list {
          display: flex;
          gap: 20px;
          margin-left: 26px;
          margin-top: 4px;
        }

        .pdf-sub-checkbox-label {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 12px;
          color: #a1a1aa;
          cursor: pointer;
          user-select: none;
        }

        .pdf-custom-checkbox-mini {
          appearance: none;
          width: 15px;
          height: 15px;
          border: 1px solid #3f3f46;
          border-radius: 3px;
          background: #18181b;
          cursor: pointer;
          position: relative;
          transition: all 0.2s;
          flex-shrink: 0;
        }
        .pdf-custom-checkbox-mini:checked {
          background: #3b82f6;
          border-color: #3b82f6;
        }
        .pdf-custom-checkbox-mini:checked::after {
          content: "✓";
          position: absolute;
          color: white;
          font-size: 10px;
          font-weight: bold;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
        }

        .pdf-modal-actions {
          display: flex;
          justify-content: flex-end;
          gap: 12px;
          margin-top: 32px;
        }

        .pdf-btn-cancel {
          background: transparent;
          border: 1px solid #27272a;
          border-radius: 8px;
          padding: 10px 18px;
          font-size: 13px;
          font-weight: 500;
          color: #a1a1aa;
          cursor: pointer;
          transition: all 0.2s;
        }
        .pdf-btn-cancel:hover {
          background: #27272a;
          color: #f4f4f5;
        }

        .pdf-btn-generate {
          background: #3b82f6;
          border: none;
          border-radius: 8px;
          padding: 10px 20px;
          font-size: 13px;
          font-weight: 600;
          color: white;
          cursor: pointer;
          box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);
          transition: all 0.2s;
        }
        .pdf-btn-generate:hover:not(:disabled) {
          background: #2563eb;
          box-shadow: 0 6px 16px rgba(59, 130, 246, 0.4);
          transform: translateY(-1px);
        }
        .pdf-btn-generate:active:not(:disabled) {
          transform: translateY(0);
        }
        .pdf-btn-generate:disabled {
          background: #27272a;
          color: #71717a;
          cursor: not-allowed;
          box-shadow: none;
        }

        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        @keyframes slideUp {
          from { transform: translateY(16px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
      `}</style>
    </div>
  )
}
