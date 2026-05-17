import { useState, useEffect } from 'react'
import { getCache, deleteCacheEntry, clearCache, type CacheEntry } from '../lib/api'

export default function CacheManagement() {
  const [entries, setEntries] = useState<CacheEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)

  const loadCache = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await getCache()
      setEntries(data.entries)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load cache')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCache()
  }, [])

  const handleDelete = async (query: string) => {
    if (!confirm(`Delete this cache entry?\n\n"${query.substring(0, 100)}..."`)) {
      return
    }

    try {
      setDeleting(query)
      await deleteCacheEntry(query)
      await loadCache() // Reload to show updated list
    } catch (err) {
      alert(`Failed to delete: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setDeleting(null)
    }
  }

  const handleClearAll = async () => {
    if (!confirm(`Clear ALL ${entries.length} cached entries?\n\nThis cannot be undone.`)) {
      return
    }

    try {
      setLoading(true)
      await clearCache()
      await loadCache()
    } catch (err) {
      alert(`Failed to clear cache: ${err instanceof Error ? err.message : 'Unknown error'}`)
      setLoading(false)
    }
  }

  if (loading && entries.length === 0) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center text-white">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-white mb-4"></div>
            <p>Loading cache...</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-4xl font-bold text-white mb-2">Cache Management</h1>
              <p className="text-slate-300">
                View and manage cached query→SQL mappings
              </p>
            </div>
            <a
              href="/"
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
            >
              ← Back to Dashboard
            </a>
          </div>

          {/* Stats & Actions */}
          <div className="flex items-center justify-between bg-slate-800/50 backdrop-blur-sm rounded-lg p-4 border border-slate-700">
            <div className="text-white">
              <span className="text-2xl font-bold">{entries.length}</span>
              <span className="text-slate-400 ml-2">cached {entries.length === 1 ? 'entry' : 'entries'}</span>
            </div>
            <div className="flex gap-3">
              <button
                onClick={loadCache}
                disabled={loading}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Refresh
              </button>
              <button
                onClick={handleClearAll}
                disabled={loading || entries.length === 0}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                Clear All
              </button>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-200">
            <p className="font-semibold">Error loading cache</p>
            <p className="text-sm">{error}</p>
          </div>
        )}

        {/* Empty State */}
        {entries.length === 0 && !loading && (
          <div className="text-center py-16 bg-slate-800/30 rounded-lg border border-slate-700">
            <svg className="w-16 h-16 mx-auto text-slate-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
            </svg>
            <h3 className="text-xl font-semibold text-white mb-2">Cache is Empty</h3>
            <p className="text-slate-400">
              Run some queries to populate the cache
            </p>
          </div>
        )}

        {/* Cache Entries */}
        {entries.length > 0 && (
          <div className="space-y-4">
            {entries.map((entry) => (
              <div
                key={entry.id}
                className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700 p-6 hover:border-slate-600 transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    {/* Query */}
                    <div className="mb-4">
                      <div className="flex items-center gap-2 mb-2">
                        <svg className="w-5 h-5 text-blue-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                        </svg>
                        <span className="text-sm font-semibold text-slate-400 uppercase tracking-wide">Query</span>
                      </div>
                      <p className="text-white text-lg font-medium break-words">
                        {entry.query}
                      </p>
                    </div>

                    {/* SQL */}
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <svg className="w-5 h-5 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                        </svg>
                        <span className="text-sm font-semibold text-slate-400 uppercase tracking-wide">Cached SQL</span>
                      </div>
                      <pre className="text-sm text-slate-300 bg-slate-900/50 p-4 rounded border border-slate-700 overflow-x-auto">
                        {entry.sql}
                      </pre>
                    </div>
                  </div>

                  {/* Delete Button */}
                  <button
                    onClick={() => handleDelete(entry.query)}
                    disabled={deleting === entry.query}
                    className="flex-shrink-0 p-2 bg-red-600/20 hover:bg-red-600 disabled:bg-red-900/20 disabled:cursor-not-allowed text-red-400 hover:text-white rounded-lg transition-colors group"
                    title="Delete this cache entry"
                  >
                    {deleting === entry.query ? (
                      <div className="w-5 h-5 border-2 border-red-400 border-t-transparent rounded-full animate-spin"></div>
                    ) : (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    )}
                  </button>
                </div>

                {/* Entry ID (for debugging) */}
                <div className="mt-4 pt-4 border-t border-slate-700">
                  <span className="text-xs text-slate-500 font-mono">ID: {entry.id}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
