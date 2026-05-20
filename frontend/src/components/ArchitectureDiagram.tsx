import { useState, useRef, useEffect } from 'react'

interface FlowNode {
  id: string
  label: string
  sublabel?: string
  color: string
  x: number
  y: number
  width: number
  height: number
}

interface FlowConnection {
  from: string
  to: string
  label?: string
  color: string
  dashed?: boolean
}

export default function ArchitectureDiagram() {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const [nodes, setNodes] = useState<FlowNode[]>([
    // Row 1 - Left to Right
    { id: 'input', label: 'Natural Language', sublabel: 'User Query', color: '#3b82f6', x: 40, y: 40, width: 180, height: 90 },
    { id: 'normalize', label: 'Normalizer', sublabel: 'Text Cleaning', color: '#8b5cf6', x: 290, y: 40, width: 180, height: 90 },
    { id: 'schema', label: 'Schema Linker', sublabel: 'Table Detection', color: '#a855f7', x: 540, y: 40, width: 180, height: 90 },

    // Row 2 - Right to Left
    { id: 'cache', label: 'Semantic Cache', sublabel: 'ChromaDB', color: '#f59e0b', x: 540, y: 230, width: 180, height: 90 },
    { id: 'prompt', label: 'Prompt Builder', sublabel: 'Context Assembly', color: '#10b981', x: 290, y: 230, width: 180, height: 90 },
    { id: 'llm', label: 'LLM Engine', sublabel: 'Gemini 3.1 Flash Lite', color: '#10b981', x: 40, y: 230, width: 180, height: 90 },

    // Row 3 - Left to Right
    { id: 'validator', label: 'SQL Validator', sublabel: 'Security Check', color: '#ef4444', x: 40, y: 420, width: 180, height: 90 },
    { id: 'executor', label: 'Query Executor', sublabel: 'PostgreSQL', color: '#06b6d4', x: 290, y: 420, width: 180, height: 90 },
    { id: 'report', label: 'Report Generator', sublabel: 'JSON/Excel/PDF', color: '#ec4899', x: 540, y: 420, width: 180, height: 90 },

    // Column 4
    { id: 'audit', label: 'Audit Logger', sublabel: 'SQLite', color: '#64748b', x: 790, y: 420, width: 180, height: 90 },
  ])

  const [dragging, setDragging] = useState<{ id: string; offsetX: number; offsetY: number } | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const connections: FlowConnection[] = [
    { from: 'input', to: 'normalize', color: '#3b82f6' },
    { from: 'normalize', to: 'schema', color: '#8b5cf6' },
    { from: 'schema', to: 'cache', label: 'Check', color: '#a855f7' },
    { from: 'cache', to: 'prompt', label: 'Miss', color: '#f59e0b' },
    { from: 'prompt', to: 'llm', color: '#10b981' },
    { from: 'llm', to: 'validator', color: '#10b981' },
    { from: 'validator', to: 'executor', label: 'Valid', color: '#ef4444' },
    { from: 'executor', to: 'report', color: '#06b6d4' },
    { from: 'report', to: 'audit', color: '#ec4899' },
    { from: 'cache', to: 'report', label: 'Cache Hit', color: '#f59e0b', dashed: true },
  ]

  const getNodeCenter = (nodeId: string) => {
    const node = nodes.find(n => n.id === nodeId)
    if (!node) return { x: 0, y: 0 }
    return { x: node.x + node.width / 2, y: node.y + node.height / 2 }
  }

  const createPath = (from: string, to: string) => {
    const start = getNodeCenter(from)
    const end = getNodeCenter(to)

    // Since all connected nodes share an X or Y coordinate in the snaking layout, 
    // a straightforward direct line looks perfect and avoids overlaps.
    return `M ${start.x} ${start.y} L ${end.x} ${end.y}`
  }

  const handleMouseDown = (e: React.MouseEvent, nodeId: string) => {
    if (!svgRef.current) return

    const svg = svgRef.current
    const pt = svg.createSVGPoint()
    pt.x = e.clientX
    pt.y = e.clientY
    const svgP = pt.matrixTransform(svg.getScreenCTM()?.inverse())

    const node = nodes.find(n => n.id === nodeId)
    if (node) {
      setDragging({
        id: nodeId,
        offsetX: svgP.x - node.x,
        offsetY: svgP.y - node.y
      })
    }
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!dragging || !svgRef.current) return

    const svg = svgRef.current
    const pt = svg.createSVGPoint()
    pt.x = e.clientX
    pt.y = e.clientY
    const svgP = pt.matrixTransform(svg.getScreenCTM()?.inverse())

    setNodes(prev => prev.map(node =>
      node.id === dragging.id
        ? { ...node, x: svgP.x - dragging.offsetX, y: svgP.y - dragging.offsetY }
        : node
    ))
  }

  const handleMouseUp = () => {
    setDragging(null)
  }

  useEffect(() => {
    if (dragging) {
      document.addEventListener('mouseup', handleMouseUp as any)
      return () => document.removeEventListener('mouseup', handleMouseUp as any)
    }
  }, [dragging])

  return (
    <div style={{
      width: '100%',
      overflowX: 'auto',
      overflowY: 'auto',
      background: '#0a0a0a',
      borderRadius: '16px',
      border: '1px solid #1c1c1c',
      padding: '40px',
      maxHeight: '700px'
    }}>
      <svg
        ref={svgRef}
        viewBox="0 0 1000 600"
        width="100%"
        height="100%"
        overflow="visible"
        style={{ display: 'block', margin: '0 auto', maxWidth: '1000px', cursor: dragging ? 'grabbing' : 'default' }}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
      >
        <defs>
          {/* Arrow markers for each color */}
          {['#3b82f6', '#8b5cf6', '#a855f7', '#f59e0b', '#10b981', '#ef4444', '#06b6d4', '#ec4899', '#64748b'].map(color => (
            <marker
              key={color}
              id={`arrow-${color.replace('#', '')}`}
              markerWidth="12"
              markerHeight="12"
              refX="11"
              refY="3"
              orient="auto"
              markerUnits="strokeWidth"
            >
              <path d="M0,0 L0,6 L9,3 z" fill={color} />
            </marker>
          ))}

          {/* Glow filters */}
          <filter id="glow">
            <feGaussianBlur stdDeviation="4" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* Animated gradient for connections */}
          <linearGradient id="flow-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="transparent" />
            <stop offset="50%" stopColor="white" stopOpacity="0.4" />
            <stop offset="100%" stopColor="transparent" />
            <animate attributeName="x1" values="-100%;100%" dur="2s" repeatCount="indefinite" />
            <animate attributeName="x2" values="0%;200%" dur="2s" repeatCount="indefinite" />
          </linearGradient>
        </defs>

        {/* Draw connections first (behind nodes) */}
        <g>
          {connections.map((conn, idx) => {
            const path = createPath(conn.from, conn.to)
            const isHovered = hoveredNode === conn.from || hoveredNode === conn.to
            const start = getNodeCenter(conn.from)
            const end = getNodeCenter(conn.to)
            const midX = (start.x + end.x) / 2
            const midY = (start.y + end.y) / 2

            return (
              <g key={idx}>
                {/* Connection path */}
                <path
                  d={path}
                  stroke={conn.color}
                  strokeWidth={isHovered ? "4" : "3"}
                  fill="none"
                  opacity={isHovered ? 1 : 0.5}
                  strokeDasharray={conn.dashed ? "8,4" : "0"}
                  markerEnd={`url(#arrow-${conn.color.replace('#', '')})`}
                  style={{ transition: 'all 0.3s' }}
                />

                {/* Animated flow effect */}
                {isHovered && (
                  <path
                    d={path}
                    stroke="url(#flow-gradient)"
                    strokeWidth="4"
                    fill="none"
                    opacity="0.8"
                  />
                )}

                {/* Connection label */}
                {conn.label && (
                  <g>
                    {(() => {
                      // Calculate label position based on connection type
                      let labelX = midX
                      let labelY = midY

                      // Special positioning for specific connections
                      if (conn.from === 'schema' && conn.to === 'cache') {
                        // "Check" label
                        labelX = start.x
                        labelY = (start.y + end.y) / 2
                      } else if (conn.from === 'cache' && conn.to === 'prompt') {
                        // "Miss" label
                        labelX = (start.x + end.x) / 2
                        labelY = start.y
                      } else if (conn.from === 'cache' && conn.to === 'report') {
                        // "Cache Hit" label
                        labelX = start.x
                        labelY = (start.y + end.y) / 2
                      } else if (conn.from === 'validator' && conn.to === 'executor') {
                        // "Valid" label
                        labelX = (start.x + end.x) / 2
                        labelY = start.y
                      }

                      return (
                        <>
                          <rect
                            x={labelX - 35}
                            y={labelY - 12}
                            width={70}
                            height={24}
                            rx="4"
                            fill="#0a0a0a"
                            stroke={conn.color}
                            strokeWidth="1"
                            opacity="0.95"
                          />
                          <text
                            x={labelX}
                            y={labelY + 4}
                            fill="#f0f0f0"
                            fontSize="11"
                            fontWeight="600"
                            textAnchor="middle"
                            style={{ pointerEvents: 'none' }}
                          >
                            {conn.label}
                          </text>
                        </>
                      )
                    })()}
                  </g>
                )}
              </g>
            )
          })}
        </g>

        {/* Draw nodes */}
        <g>
          {nodes.map((node) => {
            const isHovered = hoveredNode === node.id
            const isDragging = dragging?.id === node.id

            return (
              <g
                key={node.id}
                onMouseEnter={() => !dragging && setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                onMouseDown={(e) => handleMouseDown(e, node.id)}
                style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
              >
                {/* Node shadow/glow */}
                {(isHovered || isDragging) && (
                  <rect
                    x={node.x - 6}
                    y={node.y - 6}
                    width={node.width + 12}
                    height={node.height + 12}
                    rx="16"
                    fill={node.color}
                    opacity="0.3"
                    filter="url(#glow)"
                  />
                )}

                {/* Node background */}
                <rect
                  x={node.x}
                  y={node.y}
                  width={node.width}
                  height={node.height}
                  rx="12"
                  fill="#111"
                  stroke={node.color}
                  strokeWidth={isHovered || isDragging ? "3" : "2"}
                  style={{ transition: 'all 0.2s' }}
                />

                {/* Node accent bar */}
                <rect
                  x={node.x}
                  y={node.y}
                  width={node.width}
                  height="6"
                  rx="12"
                  fill={node.color}
                  opacity="0.9"
                />

                {/* Node label */}
                <text
                  x={node.x + node.width / 2}
                  y={node.y + 42}
                  fill="#f0f0f0"
                  fontSize="15"
                  fontWeight="700"
                  textAnchor="middle"
                  style={{ pointerEvents: 'none', userSelect: 'none' }}
                >
                  {node.label}
                </text>

                {/* Node sublabel */}
                {node.sublabel && (
                  <text
                    x={node.x + node.width / 2}
                    y={node.y + 62}
                    fill="#666"
                    fontSize="12"
                    textAnchor="middle"
                    style={{ pointerEvents: 'none', userSelect: 'none' }}
                  >
                    {node.sublabel}
                  </text>
                )}

                {/* Drag indicator */}
                {(isHovered || isDragging) && (
                  <g>
                    <circle
                      cx={node.x + node.width - 16}
                      cy={node.y + 16}
                      r="5"
                      fill={node.color}
                    >
                      {!isDragging && (
                        <animate attributeName="r" values="5;7;5" dur="1.5s" repeatCount="indefinite" />
                      )}
                    </circle>
                    <text
                      x={node.x + node.width / 2}
                      y={node.y + node.height - 12}
                      fill="#444"
                      fontSize="9"
                      textAnchor="middle"
                      style={{ pointerEvents: 'none', userSelect: 'none' }}
                    >
                      {isDragging ? 'DRAGGING' : 'DRAG TO MOVE'}
                    </text>
                  </g>
                )}
              </g>
            )
          })}
        </g>

        {/* Legend */}
        <g transform="translate(-100, 565)">
          <rect x="0" y="0" width="500" height="60" rx="8" fill="#111" stroke="#1c1c1c" strokeWidth="1" />
          <g transform="translate(10, 20)">
            <text x="0" y="0" fill="#888" fontSize="12" fontWeight="700">PIPELINE FLOW</text>

            <line x1="0" y1="18" x2="100" y2="18" stroke="#3b82f6" strokeWidth="3" markerEnd="url(#arrow-3b82f6)" />
            <text x="110" y="23" fill="#888" fontSize="11">Primary Path</text>

            <line x1="230" y1="18" x2="330" y2="18" stroke="#f59e0b" strokeWidth="3" strokeDasharray="8,4" markerEnd="url(#arrow-f59e0b)" />
            <text x="340" y="23" fill="#888" fontSize="11">Cache Hit (Fast)</text>
          </g>
        </g>
      </svg>
    </div>
  )
}
