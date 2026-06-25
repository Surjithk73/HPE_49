import { Database, Cpu, Search, Sparkles, Zap, Shield, ArrowRight, Server, FileText, CheckCircle2, Code2, BarChart3 } from 'lucide-react'
import { Link } from 'react-router-dom'
import ArchitectureDiagram from '../components/ArchitectureDiagram'
import { HPELogo } from '../components/HPELogo'
import ThemeToggle from '../components/ThemeToggle'

export default function HowItWorks() {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--theme-bg)', color: 'var(--theme-tx-primary)', fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace' }}>
      
      {/* Header */}
      <header style={{ borderBottom: '1px solid var(--theme-border)', background: 'var(--theme-surface-1)' }}>
        <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '56px' }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '12px', textDecoration: 'none' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <HPELogo width={98} height={28} />
            </div>
            <div>
              <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--theme-tx-primary)', letterSpacing: '-0.02em' }}>QueryCraft</div>
              <div style={{ fontSize: '11px', color: 'var(--theme-tx-secondary)' }}>HPE NonStop Performance Analytics</div>
            </div>
          </Link>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
            <Link to="/dashboard" style={{ padding: '8px 14px', borderRadius: '8px', background: 'var(--theme-surface-2)', border: '1px solid var(--theme-border-bright)', color: 'var(--theme-tx-primary)', fontSize: '12px', textDecoration: 'none', fontWeight: 600 }}>
              Back to Dashboard
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section style={{ borderBottom: '1px solid var(--theme-border)', background: 'linear-gradient(180deg, var(--theme-surface-1) 0%, var(--theme-bg) 100%)' }}>
        <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '80px 24px', textAlign: 'center' }}>
          <div style={{ 
            display: 'inline-block',
            padding: '6px 14px', 
            borderRadius: '20px', 
            border: '1px solid rgba(59,130,246,0.2)', 
            background: 'rgba(59,130,246,0.05)',
            fontSize: '11px',
            color: 'var(--theme-accent)',
            marginBottom: '24px',
            fontWeight: 600,
            letterSpacing: '0.5px'
          }}>
            SYSTEM ARCHITECTURE
          </div>
          <h1 style={{ fontSize: '48px', fontWeight: 800, margin: '0 0 16px', letterSpacing: '-0.03em', lineHeight: 1.1 }}>
            How QueryCraft Works
          </h1>
          <p style={{ fontSize: '18px', color: '#666', maxWidth: '700px', margin: '0 auto', lineHeight: 1.6 }}>
            A sophisticated natural language to SQL pipeline powered by AI, designed for HPE NonStop performance analysis
          </p>
        </div>
      </section>

      {/* Main Content */}
      <main style={{ maxWidth: '1280px', margin: '0 auto', padding: '60px 24px' }}>
        
        {/* Overview */}
        <section style={{ marginBottom: '80px' }}>
          <h2 style={{ fontSize: '32px', fontWeight: 700, marginBottom: '24px', letterSpacing: '-0.02em' }}>
            System Overview
          </h2>
          <p style={{ fontSize: '16px', color: 'var(--theme-tx-secondary)', lineHeight: 1.8, marginBottom: '40px' }}>
            QueryCraft transforms natural language questions into optimized SQL queries, executes them against a PostgreSQL database containing HPE NonStop performance metrics, and returns structured reports. The system uses a multi-stage pipeline with AI-powered query generation, semantic caching, and comprehensive validation.
          </p>

          {/* Architecture Diagram */}
          <div style={{ marginBottom: '40px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '24px', textAlign: 'center', color: 'var(--theme-accent)' }}>
              Interactive Pipeline Architecture
            </h3>
            <ArchitectureDiagram />
            <p style={{ fontSize: '12px', color: '#666', textAlign: 'center', marginTop: '16px', fontStyle: 'italic' }}>
              Hover over nodes to highlight connections • Blue path = Primary flow • Orange dashed = Cache hit shortcut
            </p>
          </div>

          {/* Tech Stack */}
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', 
            gap: '20px' 
          }}>
            {[
              { title: 'Frontend', tech: 'React + TypeScript + Vite', desc: 'Modern UI with real-time query execution' },
              { title: 'Backend', tech: 'FastAPI + Python 3.10+', desc: 'High-performance async API server' },
              { title: 'Database', tech: 'PostgreSQL 16+', desc: '212K+ rows across 9 performance tables' },
              { title: 'AI Engine', tech: 'Google Gemini 3.1 Flash Lite', desc: 'Fast, accurate SQL generation' },
              { title: 'Caching', tech: 'ChromaDB + Embeddings', desc: 'Semantic similarity matching' },
              { title: 'Validation', tech: 'SQLGlot Parser', desc: 'Multi-layer security checks' }
            ].map((item, idx) => (
              <div key={idx} style={{
                borderRadius: '12px',
                border: '1px solid var(--theme-border)',
                background: 'var(--theme-surface-1)',
                padding: '20px'
              }}>
                <div style={{ fontSize: '12px', color: 'var(--theme-accent)', fontWeight: 600, marginBottom: '8px' }}>
                  {item.title}
                </div>
                <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '8px', color: 'var(--theme-tx-primary)' }}>
                  {item.tech}
                </div>
                <div style={{ fontSize: '12px', color: '#666', lineHeight: 1.5 }}>
                  {item.desc}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Pipeline Stages */}
        <section style={{ marginBottom: '80px' }}>
          <h2 style={{ fontSize: '32px', fontWeight: 700, marginBottom: '32px', letterSpacing: '-0.02em' }}>
            Pipeline Stages Explained
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {[
              {
                num: '01',
                title: 'Query Normalization',
                desc: 'Cleans and standardizes the natural language input: lowercases, strips whitespace, expands HPE-specific abbreviations (e.g. "disk" → "disc", "proc" → "process"), and detects the domain category (cpu, disc, proc, tmf, etc.).',
                tech: 'normalizer.py',
                color: 'var(--theme-accent)'
              },
              {
                num: '02',
                title: 'Semantic Cache Check',
                desc: 'Converts the normalized query to an embedding vector using BAAI/bge-large-en-v1.5 (1024-dim) and searches ChromaDB for semantically similar past queries. Returns cached SQL immediately if cosine similarity ≥ 95%, skipping the LLM entirely. Entity extraction (numbers, quoted values, key terms) enforces exact match on top of cosine similarity to prevent false hits.',
                tech: 'cache.py + ChromaDB',
                color: '#f59e0b'
              },
              {
                num: '03',
                title: 'Schema Linking',
                desc: 'On a cache miss, uses hybrid retrieval (BM25 lexical + BGE-large dense vector + Reciprocal Rank Fusion) to identify relevant tables and columns. Selects top 1–3 tables and up to 20 relevant columns per table. For single-domain queries, automatically injects a companion reference table (e.g. cpu for proc queries) so the LLM always has the correct denominator columns.',
                tech: 'schema_linker.py',
                color: '#8b5cf6'
              },
              {
                num: '04',
                title: 'Prompt Building',
                desc: 'Constructs a comprehensive prompt including filtered schema DDL with counter-type formula hints per column, 48 few-shot NL→SQL examples, counter math rules (correct denominator formulas for all 7 counter types), and cross-table join rules.',
                tech: 'prompt_builder.py',
                color: '#10b981'
              },
              {
                num: '05',
                title: 'LLM Query Generation',
                desc: 'Sends the assembled prompt to Google Gemini 3.1 Flash Lite which generates optimized SQL. Extracts clean SQL from the response and retries up to 2 times with error feedback if validation fails.',
                tech: 'llm_engine.py + Gemini API',
                color: '#10b981'
              },
              {
                num: '06',
                title: 'SQL Validation',
                desc: 'Multi-layer security using SQLGlot AST parsing: (1) Valid syntax, (2) SELECT-only — blocks INSERT/UPDATE/DELETE/DROP/ALTER, (3) Injection pattern detection, (4) Auto-adds macht413 schema prefix, (5) Validates table and column existence.',
                tech: 'validator.py + SQLGlot',
                color: '#ef4444'
              },
              {
                num: '07',
                title: 'Query Execution',
                desc: 'Executes validated SQL against PostgreSQL as a read-only role (querycraft_user) with a 30-second statement timeout and a 10,000-row LIMIT enforced at the executor level. Measures execution time precisely.',
                tech: 'executor.py + psycopg2',
                color: '#06b6d4'
              },
              {
                num: '08',
                title: 'Report Generation',
                desc: 'Formats results into structured JSON with column metadata, row data, auto-detected chart type (line/bar/table), and execution statistics. Supports in-memory CSV, Excel (openpyxl), and PDF (reportlab) export with no temp files on disk.',
                tech: 'report_generator.py',
                color: '#ec4899'
              },
              {
                num: '09',
                title: 'Audit Logging',
                desc: 'Records every query execution to a SQLite database including timestamp, original and normalized query, generated SQL, validation result, cache hit status, row count, and execution time. Enables compliance tracking and history replay.',
                tech: 'audit/query_log.py',
                color: '#64748b'
              }
            ].map((stage) => (
              <div key={stage.num} style={{
                borderRadius: '12px',
                border: '1px solid var(--theme-border)',
                background: 'var(--theme-surface-1)',
                padding: '28px',
                display: 'flex',
                gap: '24px',
                alignItems: 'flex-start'
              }}>
                <div style={{
                  width: '60px',
                  height: '60px',
                  borderRadius: '12px',
                  border: `1px solid ${stage.color}33`,
                  background: `${stage.color}11`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '20px',
                  fontWeight: 800,
                  color: stage.color,
                  flexShrink: 0
                }}>
                  {stage.num}
                </div>
                <div style={{ flex: 1 }}>
                  <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '8px', color: 'var(--theme-tx-primary)' }}>
                    {stage.title}
                  </h3>
                  <p style={{ fontSize: '14px', color: 'var(--theme-tx-secondary)', lineHeight: 1.7, marginBottom: '12px' }}>
                    {stage.desc}
                  </p>
                  <div style={{
                    display: 'inline-block',
                    padding: '4px 10px',
                    borderRadius: '6px',
                    background: 'var(--theme-surface-2)',
                    border: '1px solid var(--theme-border)',
                    fontSize: '11px',
                    color: '#666',
                    fontFamily: 'monospace'
                  }}>
                    {stage.tech}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Key Features */}
        <section style={{ marginBottom: '80px' }}>
          <h2 style={{ fontSize: '32px', fontWeight: 700, marginBottom: '32px', letterSpacing: '-0.02em' }}>
            Key Features
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
            {[
              {
                icon: Zap,
                title: 'Semantic Caching',
                desc: 'ChromaDB stores query embeddings and matches similar queries with 95%+ cosine similarity, dramatically reducing LLM API calls and response time.',
                stats: '~200ms cache hits vs ~2s LLM calls'
              },
              {
                icon: Shield,
                title: 'Multi-Layer Security',
                desc: 'SQLGlot parsing, whitelist validation, SQL injection prevention, and read-only enforcement ensure safe query execution.',
                stats: '100% protection against malicious queries'
              },
              {
                icon: Code2,
                title: 'Few-Shot Learning',
                desc: '48 hand-crafted examples teach the LLM complex multi-table JOINs, aggregations, counter-type math formulas, and HPE NonStop-specific query patterns.',
                stats: '14 simple + 34 complex/pattern examples'
              },
              {
                icon: Database,
                title: 'Rich Schema Context',
                desc: '883-line enriched schema with column descriptions, data types, counter types, and join hints guides accurate SQL generation.',
                stats: '9 tables, 600+ columns documented'
              },
              {
                icon: BarChart3,
                title: 'Smart Chart Detection',
                desc: 'Automatically detects time-series and aggregation patterns to suggest bar/line charts for visualization.',
                stats: 'Auto-detects chart type from SQL'
              },
              {
                icon: FileText,
                title: 'Export Capabilities',
                desc: 'Generate Excel spreadsheets and PDF reports with formatted tables, metadata, and execution statistics.',
                stats: 'XLSX + PDF export ready'
              }
            ].map((feature, idx) => (
              <div key={idx} style={{
                borderRadius: '12px',
                border: '1px solid var(--theme-border)',
                background: 'var(--theme-surface-1)',
                padding: '24px'
              }}>
                <div style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '10px',
                  background: 'var(--theme-blue-tint)',
                  border: '1px solid rgba(59,130,246,0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '16px'
                }}>
                  <feature.icon size={22} style={{ color: 'var(--theme-accent)' }} />
                </div>
                <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '8px', color: 'var(--theme-tx-primary)' }}>
                  {feature.title}
                </h3>
                <p style={{ fontSize: '13px', color: 'var(--theme-tx-secondary)', lineHeight: 1.6, marginBottom: '12px' }}>
                  {feature.desc}
                </p>
                <div style={{ fontSize: '11px', color: 'var(--theme-accent)', fontWeight: 600 }}>
                  {feature.stats}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Data Flow */}
        <section style={{ marginBottom: '80px' }}>
          <h2 style={{ fontSize: '32px', fontWeight: 700, marginBottom: '32px', letterSpacing: '-0.02em' }}>
            Data Flow Example
          </h2>

          <div style={{
            borderRadius: '16px',
            border: '1px solid var(--theme-border)',
            background: 'var(--theme-surface-1)',
            padding: '32px'
          }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {[
                {
                  step: 'User Input',
                  content: '"Show me CPU usage for processes with high memory consumption"',
                  type: 'Natural Language',
                  color: 'var(--theme-accent)'
                },
                {
                  step: 'Schema Linking',
                  content: 'Identified tables: proc (cpu_busy_time, pres_pages_end), cpu (cpu_num)',
                  type: 'Analysis',
                  color: '#8b5cf6'
                },
                {
                  step: 'Cache Check',
                  content: 'No similar query found (cosine similarity < 95%)',
                  type: 'Cache Miss',
                  color: '#f59e0b'
                },
                {
                  step: 'Generated SQL',
                  content: 'SELECT p.process_name, p.cpu_busy_time / NULLIF(p.delta_time, 0) * 100 AS cpu_pct, p.pres_pages_end AS memory_pages FROM macht413.proc p WHERE p.pres_pages_end > 1000 ORDER BY cpu_pct DESC LIMIT 10000;',
                  type: 'SQL Query',
                  color: '#10b981'
                },
                {
                  step: 'Validation',
                  content: '✓ SELECT only ✓ Valid tables ✓ Valid columns ✓ No injection',
                  type: 'Security Check',
                  color: '#ef4444'
                },
                {
                  step: 'Execution',
                  content: '1,247 rows returned in 156ms',
                  type: 'Database Result',
                  color: '#06b6d4'
                },
                {
                  step: 'Report',
                  content: 'JSON response with columns, rows, chart_type: "table", execution_time_ms: 156',
                  type: 'Formatted Output',
                  color: '#ec4899'
                }
              ].map((item, idx) => (
                <div key={idx}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}>
                    <div style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '8px',
                      border: `1px solid ${item.color}33`,
                      background: `${item.color}11`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0
                    }}>
                      <CheckCircle2 size={16} style={{ color: item.color }} />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                        <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--theme-tx-primary)' }}>
                          {item.step}
                        </span>
                        <span style={{
                          padding: '2px 8px',
                          borderRadius: '4px',
                          background: 'var(--theme-surface-2)',
                          border: '1px solid var(--theme-border)',
                          fontSize: '10px',
                          color: '#666'
                        }}>
                          {item.type}
                        </span>
                      </div>
                      <div style={{
                        padding: '12px 16px',
                        borderRadius: '8px',
                        background: 'var(--theme-bg)',
                        border: '1px solid var(--theme-border)',
                        fontSize: '12px',
                        color: 'var(--theme-tx-secondary)',
                        fontFamily: 'monospace',
                        lineHeight: 1.6,
                        overflowX: 'auto'
                      }}>
                        {item.content}
                      </div>
                    </div>
                  </div>
                  {idx < 6 && (
                    <div style={{
                      width: '1px',
                      height: '24px',
                      background: 'var(--theme-border)',
                      marginLeft: '16px'
                    }} />
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Performance Stats */}
        <section>
          <h2 style={{ fontSize: '32px', fontWeight: 700, marginBottom: '32px', letterSpacing: '-0.02em' }}>
            Performance Metrics
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px' }}>
            {[
              { label: 'Cache Hit Rate', value: '~40%', desc: 'Queries served from cache' },
              { label: 'Avg Response Time', value: '~1.2s', desc: 'Including LLM generation' },
              { label: 'Cache Response', value: '~200ms', desc: 'Semantic cache hits' },
              { label: 'Database Rows', value: '212,689', desc: 'Across 9 tables' },
              { label: 'Few-Shot Examples', value: '48', desc: '14 simple + 34 complex/pattern' },
              { label: 'Schema Columns', value: '600+', desc: 'Fully documented' }
            ].map((stat, idx) => (
              <div key={idx} style={{
                borderRadius: '12px',
                border: '1px solid var(--theme-border)',
                background: 'var(--theme-surface-1)',
                padding: '24px',
                textAlign: 'center'
              }}>
                <div style={{ fontSize: '32px', fontWeight: 800, color: 'var(--theme-accent)', marginBottom: '8px', letterSpacing: '-0.02em' }}>
                  {stat.value}
                </div>
                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--theme-tx-primary)', marginBottom: '4px' }}>
                  {stat.label}
                </div>
                <div style={{ fontSize: '11px', color: '#666' }}>
                  {stat.desc}
                </div>
              </div>
            ))}
          </div>
        </section>

      </main>

      {/* Footer */}
      <footer style={{ borderTop: '1px solid var(--theme-border)', background: 'var(--theme-surface-1)', padding: '32px 24px', textAlign: 'center' }}>
        <div style={{ maxWidth: '1280px', margin: '0 auto' }}>
          <p style={{ fontSize: '12px', color: 'var(--theme-tx-secondary)', margin: 0 }}>
            QueryCraft v1.0.0 — HPE NonStop Performance Report Generator
          </p>
        </div>
      </footer>
    </div>
  )
}
