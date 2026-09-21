import React, { useState, useRef } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

/**
 * SQL Console — Direkte SQL-Abfragen (nur SELECT)
 */
export default function SQLConsole() {
  const { settings, schema, update: updateSetting, reset: resetSettings } = useAppSettings('sql-console')
  const [showSettings, setShowSettings] = useState(false)
  const [query, setQuery] = useState('SELECT * FROM dbai_knowledge.vw_module_overview LIMIT 20;')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState([])
  const textareaRef = useRef(null)

  const maxHistory = settings?.max_history ?? 20
  const fontSize = settings?.font_size ?? 13
  const highlightNull = settings?.highlight_null !== false

  const execute = async () => {
    if (!query.trim() || loading) return

    setLoading(true)
    setError('')

    try {
      const data = await api.sqlQuery(query)
      setResult(data)
      setHistory(prev => [query, ...prev.filter(q => q !== query)].slice(0, maxHistory))
    } catch (err) {
      setError(err.message)
      setResult(null)
    }

    setLoading(false)
  }

  const columns = result?.rows?.length > 0 ? Object.keys(result.rows[0]) : []

  if (showSettings) {
    return (
      <div style={{ padding: '16px' }}>
        <button onClick={() => setShowSettings(false)} style={{ marginBottom: '12px', padding: '4px 12px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 'var(--radius)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '11px' }}>← Zurück</button>
        <AppSettingsPanel schema={schema} settings={settings} onUpdate={updateSetting} onReset={resetSettings} title="SQL Console" />
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Query Input */}
      <div style={{ marginBottom: '12px' }}>
        <textarea
          ref={textareaRef}
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
              e.preventDefault()
              execute()
            }
          }}
          style={{
            width: '100%', minHeight: '80px', maxHeight: '200px',
            padding: '12px', background: 'var(--bg-surface)',
            border: '1px solid var(--border)', borderRadius: 'var(--radius)',
            color: 'var(--accent)', fontFamily: 'var(--font-mono)',
            fontSize: `${fontSize}px`, outline: 'none', resize: 'vertical',
          }}
          placeholder="SELECT * FROM ..."
        />
        <div className="flex justify-between items-center mt-2">
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button onClick={execute} disabled={loading} style={{
              padding: '8px 20px', background: 'var(--accent)',
              border: 'none', borderRadius: 'var(--radius)',
              color: 'var(--bg-primary)', fontWeight: 600,
              cursor: loading ? 'wait' : 'pointer', fontSize: '12px',
            }}>
              {loading ? '⏳' : '▶'} Ausführen (Ctrl+Enter)
            </button>
            <button onClick={() => setShowSettings(true)} style={{ padding: '6px 12px', borderRadius: 'var(--radius)', border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '12px' }}>⚙️</button>
          </div>
          {result && (
            <span className="text-xs text-muted">
              {result.count} Zeilen · {result.duration_ms}ms
            </span>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          padding: '10px 14px', marginBottom: '12px',
          background: 'rgba(255,68,68,0.1)', border: '1px solid var(--danger)',
          borderRadius: 'var(--radius)', color: 'var(--danger)',
          fontSize: '12px', fontFamily: 'var(--font-mono)',
        }}>
          {error}
        </div>
      )}

      {/* Results Table */}
      {result?.rows && (
        <div style={{ flex: 1, overflow: 'auto', fontSize: '11px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {columns.map(col => (
                  <th key={col} style={{
                    padding: '6px 10px', textAlign: 'left',
                    borderBottom: '2px solid var(--border)',
                    color: 'var(--accent)', fontFamily: 'var(--font-mono)',
                    fontSize: '10px', textTransform: 'uppercase',
                    position: 'sticky', top: 0,
                    background: 'var(--bg-secondary)',
                  }}>
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.map((row, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                  {columns.map(col => (
                    <td key={col} style={{
                      padding: '4px 10px', fontFamily: 'var(--font-mono)',
                      maxWidth: '300px', overflow: 'hidden',
                      textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {row[col] === null ? (highlightNull ? <span className="text-muted">NULL</span> : '') :
                       typeof row[col] === 'object' ? JSON.stringify(row[col]) :
                       String(row[col])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* History */}
      {history.length > 0 && !result && (
        <div style={{ fontSize: '11px' }}>
          <div className="text-xs text-muted" style={{ marginBottom: '8px' }}>Letzte Abfragen:</div>
          {history.map((q, i) => (
            <div
              key={i}
              onClick={() => setQuery(q)}
              style={{
                padding: '6px 10px', cursor: 'pointer',
                borderBottom: '1px solid var(--border)',
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-secondary)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}
            >
              {q}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
