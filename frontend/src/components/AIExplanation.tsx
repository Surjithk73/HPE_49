import { useState } from 'react'
import { Sparkles, Copy, Check, AlertCircle, X, Loader2, Cpu } from 'lucide-react'
import { explainResults } from '../lib/api'

interface Props {
  sql: string
  queryText: string
  columns: string[]
  rows: Record<string, unknown>[]
}

const LOADING_STATUSES = [
  'Reading dataset schema...',
  'Extracting metric columns...',
  'Correlating records across systems...',
  'Scanning values for outlier patterns...',
  'Generating performance explanation...',
]

export default function AIExplanation({ sql, queryText, columns, rows }: Props) {
  const [explanation, setExplanation] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [loadingStatusIdx, setLoadingStatusIdx] = useState(0)

  const handleExplain = async () => {
    setLoading(true)
    setError(null)
    setExplanation(null)
    setLoadingStatusIdx(0)

    // Interval to cycle through loading statuses for premium user experience
    const interval = setInterval(() => {
      setLoadingStatusIdx((prev) => (prev + 1) % LOADING_STATUSES.length)
    }, 1800)

    try {
      const res = await explainResults(sql, queryText, columns, rows)
      setExplanation(res.explanation)
    } catch (e: any) {
      setError(e.message || 'Failed to generate explanation. Please try again.')
    } finally {
      clearInterval(interval)
      setLoading(false)
    }
  }

  const handleCopy = () => {
    if (!explanation) return
    navigator.clipboard.writeText(explanation)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Parses basic markdown elements (**bold**, bullet points) into custom styled JSX elements
  const formatResponse = (text: string) => {
    return text.split('\n').map((line, idx) => {
      let cleanLine = line.trim()
      if (!cleanLine) return <div key={idx} className="ai-para-spacer" />

      const isBullet = cleanLine.startsWith('-') || cleanLine.startsWith('*')
      if (isBullet) {
        cleanLine = cleanLine.substring(1).trim()
      }

      // Format bold text wraps (**word**)
      const parts = cleanLine.split('**')
      const formattedContent = parts.map((part, pIdx) => {
        if (pIdx % 2 === 1) {
          return (
            <strong key={pIdx} className="ai-bold-highlight">
              {part}
            </strong>
          )
        }
        return part
      })

      if (isBullet) {
        return (
          <li key={idx} className="ai-bullet-item">
            {formattedContent}
          </li>
        )
      }

      return (
        <p key={idx} className="ai-para-text">
          {formattedContent}
        </p>
      )
    })
  }

  return (
    <div className="ai-explanation-wrapper">
      {!explanation && !loading && (
        <button
          type="button"
          onClick={handleExplain}
          className="ai-btn-trigger"
        >
          <Sparkles size={14} className="ai-sparkles-icon" />
          <span>Explain Results & Detect Outliers (AI)</span>
        </button>
      )}

      {loading && (
        <div className="ai-card-loading">
          <div className="ai-loading-header">
            <Loader2 size={16} className="ai-spinner" />
            <span className="ai-loading-title">AI Performance Analysis</span>
          </div>
          <p className="ai-loading-status">
            {LOADING_STATUSES[loadingStatusIdx]}
          </p>
          <div className="ai-loading-bar-bg">
            <div 
              className="ai-loading-bar-fill" 
              style={{ width: `${((loadingStatusIdx + 1) / LOADING_STATUSES.length) * 100}%` }}
            />
          </div>
        </div>
      )}

      {error && (
        <div className="ai-card-error">
          <AlertCircle size={16} className="ai-error-icon" />
          <div className="ai-error-body">
            <p className="ai-error-text">{error}</p>
            <button type="button" onClick={handleExplain} className="ai-btn-retry">
              Retry Analysis
            </button>
          </div>
          <button type="button" onClick={() => setError(null)} className="ai-btn-close-error">
            <X size={14} />
          </button>
        </div>
      )}

      {explanation && !loading && (
        <div className="ai-card-result">
          <div className="ai-result-header">
            <div className="ai-result-header-left">
              <Cpu size={15} className="ai-cpu-icon animate-pulse" />
              <h4 className="ai-result-title">AI Performance Insights</h4>
            </div>
            <div className="ai-result-header-right">
              <button
                type="button"
                onClick={handleCopy}
                className="ai-btn-copy"
                title="Copy insights to clipboard"
              >
                {copied ? <Check size={13} style={{ color: '#10b981' }} /> : <Copy size={13} />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
              <button
                type="button"
                onClick={() => setExplanation(null)}
                className="ai-btn-dismiss"
                title="Dismiss analysis"
              >
                <X size={13} />
              </button>
            </div>
          </div>

          <div className="ai-result-content">
            {formatResponse(explanation)}
          </div>
        </div>
      )}

      <style>{`
        .ai-explanation-wrapper {
          margin-top: 14px;
          font-family: inherit;
        }

        .ai-btn-trigger {
          display: flex;
          align-items: center;
          gap: 8px;
          background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(147, 51, 234, 0.1) 100%);
          border: 1px solid rgba(147, 51, 234, 0.3);
          border-radius: 8px;
          padding: 10px 18px;
          color: #d8b4fe;
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
          box-shadow: 0 4px 12px rgba(147, 51, 234, 0.05);
        }
        .ai-btn-trigger:hover {
          background: linear-gradient(135deg, rgba(59, 130, 246, 0.2) 0%, rgba(147, 51, 234, 0.2) 100%);
          border-color: rgba(147, 51, 234, 0.6);
          box-shadow: 0 4px 20px rgba(147, 51, 234, 0.15);
          transform: translateY(-1px);
          color: #e9d5ff;
        }
        .ai-btn-trigger:active {
          transform: translateY(0);
        }

        .ai-sparkles-icon {
          color: #c084fc;
          animation: pulse 2s infinite;
        }

        /* Loading Card */
        .ai-card-loading {
          background: linear-gradient(145deg, #18181b 0%, #0d0d0d 100%);
          border: 1px dashed rgba(147, 51, 234, 0.2);
          border-radius: 12px;
          padding: 20px;
          display: flex;
          flex-direction: column;
          gap: 8px;
          animation: slideUp 0.35s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .ai-loading-header {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .ai-spinner {
          animation: spin 1s linear infinite;
          color: #c084fc;
        }

        .ai-loading-title {
          font-size: 13px;
          font-weight: 600;
          color: #e4e4e7;
        }

        .ai-loading-status {
          margin: 0;
          font-size: 12px;
          color: #a1a1aa;
          min-height: 18px;
          transition: all 0.2s;
        }

        .ai-loading-bar-bg {
          height: 3px;
          background: #27272a;
          border-radius: 10px;
          overflow: hidden;
          width: 100%;
          margin-top: 4px;
        }

        .ai-loading-bar-fill {
          height: 100%;
          background: linear-gradient(to right, #3b82f6, #9333ea);
          border-radius: 10px;
          transition: width 0.4s ease;
        }

        /* Error Card */
        .ai-card-error {
          background: rgba(239, 68, 68, 0.05);
          border: 1px solid rgba(239, 68, 68, 0.2);
          border-radius: 12px;
          padding: 16px;
          display: flex;
          align-items: flex-start;
          gap: 12px;
          animation: slideUp 0.3s ease-out;
        }

        .ai-error-icon {
          color: #f87171;
          margin-top: 2px;
          flex-shrink: 0;
        }

        .ai-error-body {
          display: flex;
          flex-direction: column;
          gap: 8px;
          flex-grow: 1;
        }

        .ai-error-text {
          margin: 0;
          font-size: 12px;
          color: #fca5a5;
          line-height: 1.5;
        }

        .ai-btn-retry {
          align-self: flex-start;
          background: rgba(239, 68, 68, 0.15);
          border: 1px solid rgba(239, 68, 68, 0.3);
          border-radius: 6px;
          padding: 5px 12px;
          font-size: 11px;
          font-weight: 600;
          color: #fca5a5;
          cursor: pointer;
          transition: all 0.15s;
        }
        .ai-btn-retry:hover {
          background: rgba(239, 68, 68, 0.25);
          border-color: rgba(239, 68, 68, 0.5);
          color: #fee2e2;
        }

        .ai-btn-close-error {
          background: transparent;
          border: none;
          color: #71717a;
          cursor: pointer;
          padding: 0;
          transition: color 0.15s;
        }
        .ai-btn-close-error:hover {
          color: #d4d4d8;
        }

        /* Result Card */
        .ai-card-result {
          background: linear-gradient(145deg, #111113 0%, #080809 100%);
          border: 1px solid rgba(255, 255, 255, 0.05);
          box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
          border-radius: 12px;
          padding: 20px;
          animation: slideUp 0.35s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .ai-result-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          border-bottom: 1px solid rgba(255, 255, 255, 0.04);
          padding-bottom: 12px;
          margin-bottom: 16px;
        }

        .ai-result-header-left {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .ai-cpu-icon {
          color: #a855f7;
        }

        .ai-result-title {
          margin: 0;
          font-size: 14px;
          font-weight: 600;
          letter-spacing: -0.01em;
          background: linear-gradient(to right, #c084fc, #818cf8);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .ai-result-header-right {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .ai-btn-copy {
          display: flex;
          align-items: center;
          gap: 6px;
          background: #18181b;
          border: 1px solid #27272a;
          border-radius: 6px;
          padding: 6px 12px;
          font-size: 11px;
          font-weight: 500;
          color: #a1a1aa;
          cursor: pointer;
          transition: all 0.15s;
        }
        .ai-btn-copy:hover {
          border-color: #3f3f46;
          color: #f4f4f5;
        }

        .ai-btn-dismiss {
          background: transparent;
          border: none;
          color: #52525b;
          cursor: pointer;
          padding: 4px;
          border-radius: 4px;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.15s;
        }
        .ai-btn-dismiss:hover {
          background: rgba(255, 255, 255, 0.05);
          color: #a1a1aa;
        }

        .ai-result-content {
          font-size: 13px;
          color: #d4d4d8;
          line-height: 1.6;
        }

        .ai-para-text {
          margin: 0 0 12px 0;
        }
        .ai-para-text:last-child {
          margin-bottom: 0;
        }

        .ai-bullet-item {
          margin-left: 18px;
          margin-bottom: 8px;
          list-style-type: square;
          color: #d4d4d8;
        }
        .ai-bullet-item::marker {
          color: #a855f7;
        }

        .ai-para-spacer {
          height: 10px;
        }

        .ai-bold-highlight {
          color: #93c5fd;
          font-weight: 600;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        @keyframes slideUp {
          from { transform: translateY(12px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: .5; }
        }
      `}</style>
    </div>
  )
}
