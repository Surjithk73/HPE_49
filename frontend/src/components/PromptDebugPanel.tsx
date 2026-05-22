import { useState } from 'react'
import { Bug, ChevronDown, ChevronUp, Copy, Check } from 'lucide-react'

interface Props {
  prompt: string
}

export default function PromptDebugPanel({ prompt }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied] = useState(false)

  const isCacheHit = prompt.startsWith('[Cache Hit]')

  const copyPrompt = async () => {
    await navigator.clipboard.writeText(prompt)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Highlight sections of the prompt for readability
  const highlightPrompt = (text: string): string => {
    if (isCacheHit) return text

    return text
      // Section headers (STRICT RULES:, SCHEMA CONTEXT:, etc.)
      .replace(/^(STRICT RULES:|SCHEMA CONTEXT:|USER REQUEST:|SQL:|EXAMPLES.*:)/gm,
        '<span style="color:#f59e0b;font-weight:700">$1</span>')
      // System instruction line
      .replace(/^(You are a SQL expert.*?)$/m,
        '<span style="color:#60a5fa;font-weight:600">$1</span>')
      .replace(/^(Generate a single valid.*?)$/m,
        '<span style="color:#60a5fa">$1</span>')
      // Bullet rules (lines starting with -)
      .replace(/^(- .*)$/gm,
        '<span style="color:#94a3b8">$1</span>')
      // SQL keywords in schema context
      .replace(/\b(CREATE TABLE|TEXT|BIGINT|BOOLEAN|TIMESTAMP|DOUBLE PRECISION|INTEGER|NUMERIC)\b/g,
        '<span style="color:#c084fc">$1</span>')
      // Table references
      .replace(/(macht413\.\w+)/g,
        '<span style="color:#34d399">$1</span>')
      // SQL comments
      .replace(/(--.*?)$/gm,
        '<span style="color:#555">$1</span>')
      // INPUT/OUTPUT in few-shot examples
      .replace(/^(INPUT:.*?)$/gm,
        '<span style="color:#38bdf8;font-weight:600">$1</span>')
      .replace(/^(OUTPUT:)$/gm,
        '<span style="color:#38bdf8;font-weight:600">$1</span>')
      // Example headers
      .replace(/^(### Example \d+)$/gm,
        '<span style="color:#fb923c;font-weight:600">$1</span>')
  }

  return (
    <div style={{
      borderRadius: '10px',
      border: `1px solid ${expanded ? 'rgba(168,85,247,0.3)' : '#2a2a2a'}`,
      background: expanded ? 'rgba(168,85,247,0.03)' : '#161616',
      overflow: 'hidden',
      animation: 'slideUp 0.25s ease-out',
      transition: 'border-color 0.2s, background 0.2s',
    }}>
      {/* Header — always visible, acts as toggle */}
      <button
        onClick={() => setExpanded(e => !e)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
          padding: '10px 16px',
          border: 'none',
          borderBottom: expanded ? '1px solid rgba(168,85,247,0.15)' : 'none',
          background: 'transparent',
          cursor: 'pointer',
          fontFamily: 'inherit',
          transition: 'all 0.15s',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '22px', height: '22px', borderRadius: '6px',
            background: 'rgba(168,85,247,0.1)', border: '1px solid rgba(168,85,247,0.25)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Bug size={11} style={{ color: '#a855f7' }} />
          </div>
          <span style={{
            fontSize: '11px', fontWeight: 600, color: '#a855f7',
            letterSpacing: '0.08em', textTransform: 'uppercase',
          }}>
            Debug — LLM Prompt
          </span>
          {isCacheHit && (
            <span style={{
              fontSize: '10px', color: '#fbbf24',
              border: '1px solid rgba(251,191,36,0.3)', background: 'rgba(251,191,36,0.08)',
              borderRadius: '999px', padding: '1px 8px',
            }}>
              cache hit
            </span>
          )}
        </div>
        <div style={{ color: '#555', display: 'flex', alignItems: 'center' }}>
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </button>

      {/* Expandable content */}
      {expanded && (
        <div style={{ padding: '12px 16px', position: 'relative' }}>
          {/* Copy button */}
          <div style={{
            position: 'absolute', top: '12px', right: '16px', zIndex: 2,
          }}>
            <button
              onClick={copyPrompt}
              style={{
                display: 'flex', alignItems: 'center', gap: '5px',
                border: '1px solid #2a2a2a', background: '#1c1c1c',
                borderRadius: '6px', padding: '4px 10px', fontSize: '11px',
                color: copied ? '#34d399' : '#888', cursor: 'pointer',
                fontFamily: 'inherit', transition: 'all 0.15s',
              }}
            >
              {copied ? <><Check size={11} /> Copied</> : <><Copy size={11} /> Copy</>}
            </button>
          </div>

          {/* Prompt content */}
          <div style={{
            overflowX: 'auto',
            maxHeight: '500px',
            overflowY: 'auto',
            scrollbarWidth: 'thin',
            scrollbarColor: '#333 transparent',
          }}>
            <pre
              style={{
                fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace',
                fontSize: '11px',
                lineHeight: 1.65,
                color: '#cbd5e1',
                margin: 0,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                paddingRight: '80px',
              }}
              dangerouslySetInnerHTML={{ __html: highlightPrompt(prompt) }}
            />
          </div>

          {/* Footer stats */}
          {!isCacheHit && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '12px',
              borderTop: '1px solid rgba(168,85,247,0.1)',
              marginTop: '12px', paddingTop: '10px',
              fontSize: '10px', color: '#555',
            }}>
              <span>{prompt.length.toLocaleString()} characters</span>
              <span style={{ color: '#333' }}>·</span>
              <span>~{Math.ceil(prompt.length / 4).toLocaleString()} tokens (est.)</span>
            </div>
          )}
        </div>
      )}

      <style>{`@keyframes slideUp { from { opacity:0; transform:translateY(8px) } to { opacity:1; transform:translateY(0) } }`}</style>
    </div>
  )
}
