import React, { useState, useEffect } from 'react'
import { api } from '../../api'

/**
 * Knowledge Base — Module, ADRs, Glossar, Error-Patterns durchsuchen
 */
export default function KnowledgeBase() {
  const [tab, setTab] = useState('modules') // modules, errors, report
  const [modules, setModules] = useState([])
  const [errors, setErrors] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)

  useEffect(() => {
    if (tab === 'modules') api.modules().then(setModules).catch(() => {})
    if (tab === 'errors') api.errors().then(setErrors).catch(() => {})
  }, [tab])

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults(null)
      return
    }
    const results = await api.searchModules(searchQuery)
    setSearchResults(results)
  }

  return (
    <div>
      {/* Search */}
      <div className="flex gap-2" style={{ marginBottom: '16px' }}>
        <input
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="Module durchsuchen..."
          style={{
            flex: 1, padding: '8px 12px',
            background: 'var(--bg-surface)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius)', color: 'var(--text-primary)',
            fontFamily: 'var(--font-mono)', fontSize: '12px', outline: 'none',
          }}
        />
        <button onClick={handleSearch} style={{
          padding: '8px 16px', background: 'var(--accent)',
          border: 'none', borderRadius: 'var(--radius)',
          color: 'var(--bg-primary)', cursor: 'pointer', fontWeight: 600,
        }}>
          🔍
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2" style={{ marginBottom: '16px' }}>
        {['modules', 'errors', 'report'].map(t => (
          <button
            key={t}
            onClick={() => { setTab(t); setSearchResults(null) }}
            style={{
              padding: '6px 16px', borderRadius: 'var(--radius)',
              border: `1px solid ${tab === t ? 'var(--accent)' : 'var(--border)'}`,
              background: tab === t ? 'rgba(0,255,204,0.1)' : 'transparent',
              color: tab === t ? 'var(--accent)' : 'var(--text-secondary)',
              cursor: 'pointer', fontSize: '12px',
            }}
          >
            {t === 'modules' ? '📦 Module' : t === 'errors' ? '🐛 Fehler' : '📋 Report'}
          </button>
        ))}
      </div>

      {/* Search Results */}
      {searchResults && (
        <div style={{ marginBottom: '16px' }}>
          <div className="text-xs text-muted" style={{ marginBottom: '8px' }}>
            {searchResults.length} Ergebnis(se) für "{searchQuery}"
          </div>
          {searchResults.map((r, i) => (
            <ModuleRow key={i} module={r} />
          ))}
        </div>
      )}

      {/* Modules */}
      {tab === 'modules' && !searchResults && (
        <div>
          {modules.map((m, i) => <ModuleRow key={i} module={m} />)}
          {modules.length === 0 && <div className="text-muted p-4">Lade Module...</div>}
        </div>
      )}

      {/* Error Patterns */}
      {tab === 'errors' && !searchResults && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {errors.map((err, i) => (
            <div key={i} style={{
              padding: '12px 16px', background: 'var(--bg-surface)',
              border: '1px solid var(--border)', borderRadius: 'var(--radius)',
              borderLeft: `3px solid ${
                err.severity === 'critical' ? 'var(--danger)' :
                err.severity === 'high' ? 'var(--warning)' : 'var(--info)'
              }`,
            }}>
              <div className="flex justify-between items-center">
                <strong style={{ fontSize: '13px' }}>{err.title}</strong>
                <span className="text-xs text-mono" style={{
                  color: err.severity === 'critical' ? 'var(--danger)' :
                         err.severity === 'high' ? 'var(--warning)' : 'var(--text-secondary)',
                }}>{err.severity}</span>
              </div>
              <div className="text-xs text-muted mt-2">{err.description}</div>
              <div className="text-xs text-mono mt-2" style={{
                padding: '4px 8px', background: 'var(--bg-primary)',
                borderRadius: '4px', color: 'var(--accent)',
              }}>
                Regex: {err.error_regex}
              </div>
              {err.solution_short && (
                <div className="text-xs mt-2" style={{ color: 'var(--success)' }}>
                  💡 {err.solution_short}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* System Report */}
      {tab === 'report' && <SystemReport />}
    </div>
  )
}

function ModuleRow({ module }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      style={{
        padding: '8px 12px', borderBottom: '1px solid var(--border)',
        cursor: 'pointer', fontSize: '12px',
      }}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex justify-between items-center">
        <div className="flex gap-2 items-center">
          <span style={{
            width: '8px', height: '8px', borderRadius: '50%', display: 'inline-block',
            background: module.status === 'active' ? 'var(--success)' :
                        module.status === 'deprecated' ? 'var(--warning)' : 'var(--text-secondary)',
          }} />
          <span className="text-mono" style={{ color: 'var(--accent)' }}>
            {module.file_path}
          </span>
        </div>
        <span className="text-xs text-muted">{module.category} · {module.language}</span>
      </div>
      {expanded && (
        <div style={{ marginTop: '8px', paddingLeft: '20px' }}>
          <div className="text-xs text-muted">{module.description}</div>
          {module.provides && (
            <div className="text-xs mt-2">
              <strong>Provides:</strong> {Array.isArray(module.provides) ? module.provides.join(', ') : module.provides}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function SystemReport() {
  const [report, setReport] = useState(null)
  useEffect(() => {
    api.systemReport().then(setReport).catch(console.error)
  }, [])

  if (!report) return <div className="text-muted p-4">Lade System-Report...</div>

  return (
    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', whiteSpace: 'pre-wrap' }}>
      {JSON.stringify(report, null, 2)}
    </div>
  )
}
