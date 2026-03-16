import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'

export default function RAGManager() {
  const [stats, setStats] = useState(null)
  const [sources, setSources] = useState([])
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [querying, setQuerying] = useState(false)
  const [view, setView] = useState('sources')

  const loadData = useCallback(async () => {
    try {
      const [s, st] = await Promise.all([api.ragSources(), api.ragStats()])
      setSources(s.sources || [])
      setStats(st)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const doQuery = async () => {
    if (!query.trim()) return
    setQuerying(true)
    try {
      const r = await api.ragQuery(query)
      setResult(r)
    } catch { /* ignore */ }
    finally { setQuerying(false) }
  }

  const toggleSource = async (name, enabled) => {
    try {
      await api.ragToggleSource(name, !enabled)
      loadData()
    } catch { /* ignore */ }
  }

  const reindex = async (name) => {
    try {
      const r = await api.ragReindex(name)
      alert(`${r.chunks || 0} Chunks reindexiert`)
      loadData()
    } catch { /* ignore */ }
  }

  const S = {
    container: { display: 'flex', flexDirection: 'column', height: '100%', background: '#0a0a14', color: '#c8d6e5', padding: '16px', overflow: 'auto' },
    h: { color: '#00ffcc', fontSize: '18px', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' },
    card: { background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '8px', padding: '12px', marginBottom: '8px' },
    btn: { padding: '6px 16px', border: '1px solid #00ffcc', background: 'transparent', color: '#00ffcc', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' },
    input: { padding: '6px 12px', background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '6px', color: '#d4d4d4', fontSize: '13px', outline: 'none', flex: 1 },
    tabs: { display: 'flex', gap: '4px', marginBottom: '16px' },
    tab: (a) => ({ padding: '6px 14px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', background: a ? '#1a2a3a' : 'transparent', color: a ? '#00ffcc' : '#556', border: '1px solid ' + (a ? '#00ffcc33' : 'transparent') }),
  }

  return (
    <div style={S.container}>
      <div style={S.h}><span>🔗</span> RAG Pipeline</div>
      <p style={{ color: '#556', fontSize: '13px', marginBottom: '16px' }}>
        Retrieval-Augmented-Generation: Relevante Chunks aus der Wissensbasis in Ghost-Prompts injizieren.
      </p>

      <div style={S.tabs}>
        <div style={S.tab(view === 'sources')} onClick={() => setView('sources')}>Quellen</div>
        <div style={S.tab(view === 'query')} onClick={() => setView('query')}>Abfrage</div>
        <div style={S.tab(view === 'stats')} onClick={() => setView('stats')}>Statistiken</div>
      </div>

      {view === 'sources' && (
        <>
          {sources.map((s, i) => (
            <div key={i} style={{ ...S.card, display: 'flex', justifyContent: 'space-between', alignItems: 'center', opacity: s.enabled ? 1 : 0.5 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ color: s.enabled ? '#00ffcc' : '#ff4444', fontSize: '8px' }}>●</span>
                  <strong style={{ color: '#d4d4d4' }}>{s.source_name}</strong>
                  <span style={{ color: '#445', fontSize: '11px' }}>({s.source_type})</span>
                </div>
                <div style={{ fontSize: '11px', color: '#556', marginTop: '4px' }}>
                  Chunks: <span style={{ color: '#00ccff' }}>{s.chunk_count || 0}</span>
                  {s.total_tokens && <span> · Tokens: {s.total_tokens.toLocaleString()}</span>}
                  {' · '}Priorität: {s.priority}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button
                  style={{ ...S.btn, fontSize: '11px', padding: '3px 8px', borderColor: s.enabled ? '#ff4444' : '#00ffcc', color: s.enabled ? '#ff4444' : '#00ffcc' }}
                  onClick={() => toggleSource(s.source_name, s.enabled)}
                >
                  {s.enabled ? '✗ Aus' : '✓ An'}
                </button>
                <button
                  style={{ ...S.btn, fontSize: '11px', padding: '3px 8px', borderColor: '#4488ff', color: '#4488ff' }}
                  onClick={() => reindex(s.source_name)}
                >
                  ↻ Reindex
                </button>
              </div>
            </div>
          ))}
        </>
      )}

      {view === 'query' && (
        <>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
            <input
              style={S.input}
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Frage an die Wissensbasis..."
              onKeyDown={e => e.key === 'Enter' && doQuery()}
            />
            <button style={S.btn} onClick={doQuery} disabled={querying}>
              {querying ? '⏳' : '🔍'}
            </button>
          </div>

          {result && (
            <>
              <div style={{ ...S.card, borderColor: '#00ffcc33' }}>
                <div style={{ color: '#00ffcc', fontSize: '12px', fontWeight: 600, marginBottom: '8px' }}>
                  {result.stats?.chunks_found || 0} Chunks · {result.stats?.total_tokens || 0} Tokens · {result.stats?.latency_ms || 0}ms
                </div>
              </div>
              {(result.chunks || []).map((c, i) => (
                <div key={i} style={S.card}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ color: '#4488ff', fontSize: '11px' }}>{c.source}</span>
                    <span style={{ color: '#00ffcc', fontSize: '11px' }}>Score: {c.score?.toFixed(3)}</span>
                  </div>
                  <div style={{ color: '#8899aa', fontSize: '12px', whiteSpace: 'pre-wrap' }}>{c.content}</div>
                </div>
              ))}
            </>
          )}
        </>
      )}

      {view === 'stats' && stats && (
        <div style={S.card}>
          <div style={{ color: '#d4d4d4', fontWeight: 600, marginBottom: '8px' }}>Pipeline-Statistiken</div>
          {stats.query_stats && (
            <div style={{ fontSize: '12px', color: '#8899aa' }}>
              <div>Queries: <span style={{ color: '#00ffcc' }}>{stats.query_stats.total_queries || 0}</span></div>
              <div>Ø Latenz: <span style={{ color: '#ffaa00' }}>{stats.query_stats.avg_latency || 0}ms</span></div>
              <div>Ø Chunks: <span style={{ color: '#4488ff' }}>{(stats.query_stats.avg_chunks || 0).toFixed(1)}</span></div>
            </div>
          )}
          {stats.pipeline && (
            <div style={{ fontSize: '12px', color: '#8899aa', marginTop: '8px' }}>
              <div>Cache Hits: {stats.pipeline.cache_hits || 0}</div>
              <div>Total Retrieved: {stats.pipeline.chunks_retrieved || 0}</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
