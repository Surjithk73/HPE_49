const API_BASE = 'http://localhost:8000'

export interface QueryResponse {
  sql: string
  columns: string[]
  rows: Record<string, unknown>[]
  row_count: number
  execution_time_ms: number
  cache_hit: boolean
  chart_type: 'line' | 'bar' | 'table'
  domain: string
  error?: string
}

export interface HistoryEntry {
  id: number
  timestamp: string
  original_input: string
  normalized_input: string
  domain_category: string
  generated_sql: string
  validation_passed: number
  cache_hit: number
  row_count: number | null
  execution_time_ms: number | null
}

export interface SchemaTable {
  table_name: string
  column_count: number
  description: string
}

export interface CacheEntry {
  id: string
  query: string
  sql: string
}

export interface CacheResponse {
  count: number
  entries: CacheEntry[]
}

export interface HealthResponse {
  status: string
  db_connected: boolean
  cache_ready: boolean
  llm_model: string
  cache_entries: number
  schema_tables: number
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function runQuery(query: string): Promise<QueryResponse> {
  return request<QueryResponse>('/api/query', {
    method: 'POST',
    body: JSON.stringify({ query }),
  })
}

export async function exportReport(
  sql: string,
  format: 'csv' | 'excel' | 'pdf',
  queryText: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sql, format, query_text: queryText }),
  })
  if (!res.ok) throw new Error(`Export failed: ${res.statusText}`)
  const blob = await res.blob()
  const ext = format === 'excel' ? 'xlsx' : format
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `querycraft_report.${ext}`
  a.click()
  URL.revokeObjectURL(url)
}

export async function getHistory(): Promise<HistoryEntry[]> {
  return request<HistoryEntry[]>('/api/history')
}

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/api/health')
}

export async function getSchema(): Promise<SchemaTable[]> {
  return request<SchemaTable[]>('/api/schema')
}

export async function getCache(): Promise<CacheResponse> {
  return request<CacheResponse>('/api/cache')
}

export async function deleteCacheEntry(query: string): Promise<void> {
  await request<void>(`/api/cache/query?query=${encodeURIComponent(query)}`, {
    method: 'DELETE',
  })
}

export async function clearCache(): Promise<void> {
  await request<void>('/api/cache', {
    method: 'DELETE',
  })
}
