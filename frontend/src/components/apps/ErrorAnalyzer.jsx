import React, { useState, useEffect } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

/**
 * ErrorAnalyzer — Fehler-Log durchsuchen, Patterns matchen, Runbooks anzeigen
 */
export default function ErrorAnalyzer({ windowId }) {
  const { settings, schema, update: updateSetting, reset: resetSettings } = useAppSettings('error-analyzer')
  const [showSettings, setShowSettings] = useState(false)
  const [errors, setErrors] = useState([])
  const [patterns, setPatterns] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('errors')
  const [selectedError, setSelectedError] = useState(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [errResult, patResult] = await Promise.all([
        api.errors(),
        api.sqlQuery("SELECT * FROM dbai_knowledge.error_patterns ORDER BY pattern_name")
      ])
      setErrors(errResult || [])
      setPatterns(patResult.rows || [])
    } catch (err) {
      console.error('Error data laden fehlgeschlagen:', err)
    } finally {
      setLoading(false)
    }
  }

  const severityColor = (sev) => {
    switch (sev) {
      case 'critical': return 'var(--danger)'
      case 'warning': return 'var(--warning)'
      case 'info': return 'var(--info)'
      default: return 'var(--text-secondary)'
    }
  }

  if (showSettings) {
    return (
      <div style={{ padding: '16px' }}>
        <button onClick={() => setShowSettings(false)} style={{ marginBottom: '12px', padding: '4px 12px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 'var(--radius)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '11px' }}>← Zurück</button>
        <AppSettingsPanel schema={schema} settings={settings} onUpdate={updateSetting} onReset={resetSettings} title="Error Analyzer" />
      </div>
    )
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
      {/* Tabs */}
      <div style={{
        display: 'flex', borderBottom: '1px solid var(--border)', padding: '0 8px'
      }}>
        {[
          { id: 'errors', label: '🔴 Fehler-Log' },
          { id: 'patterns', label: '🔍 Error Patterns' },
          { id: 'runbooks', label: '📖 Runbooks' }
        ].map(t => (
          <div
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              padding: '10px 16px', cursor: 'pointer',
              borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
              color: tab === t.id ? 'var(--accent)' : 'var(--text-secondary)',
              fontSize: '11px'
            }}
          >
            {t.label}
          </div>
        ))}
        <div style={{ flex: 1 }} />
        <button onClick={() => setShowSettings(true)} style={{ padding: '4px 12px', background: 'transparent', border: '1px solid var(--border)', borderRadius: '4px', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '10px', margin: '4px 0' }}>⚙️</button>
        <button
          onClick={loadData}
          style={{
            padding: '4px 12px', background: 'transparent', border: '1px solid var(--border)',
            borderRadius: '4px', color: 'var(--text-primary)', cursor: 'pointer',
            fontSize: '10px', margin: '4px 0'
          }}
        >↻ Aktualisieren</button>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '8px' }}>
        {loading ? (
          <div style={{ padding: '20px', color: 'var(--text-secondary)', textAlign: 'center' }}>Lade...</div>
        ) : (
          <>
            {tab === 'errors' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {errors.length === 0 ? (
                  <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                    <div style={{ fontSize: '32px', marginBottom: '8px' }}>✅</div>
                    Keine Fehler erfasst
                  </div>
                ) : errors.map((err, i) => (
                  <div key={i} style={{
                    padding: '8px 12px', background: 'var(--bg-surface)',
                    borderRadius: '4px', border: '1px solid var(--border)',
                    borderLeft: `3px solid ${severityColor(err.severity)}`,
                    cursor: 'pointer'
                  }}
                  onClick={() => setSelectedError(selectedError === i ? null : i)}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 500 }}>{err.error_code || err.pattern_name || 'Error'}</span>
                      <span style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                        {err.created_at ? new Date(err.created_at).toLocaleString('de-DE') : ''}
                      </span>
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      {err.message || err.description || '—'}
                    </div>
                    {selectedError === i && err.context && (
                      <pre style={{
                        marginTop: '8px', padding: '8px', background: 'var(--bg-primary)',
                        borderRadius: '4px', fontSize: '10px', overflow: 'auto', maxHeight: '200px'
                      }}>
                        {typeof err.context === 'object' ? JSON.stringify(err.context, null, 2) : err.context}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            )}

            {tab === 'patterns' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {patterns.map((p, i) => (
                  <div key={i} style={{
                    padding: '12px', background: 'var(--bg-surface)',
                    borderRadius: '6px', border: '1px solid var(--border)'
                  }}>
                    <div style={{ fontWeight: 600, color: 'var(--accent)', marginBottom: '4px' }}>
                      {p.pattern_name}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      {p.description || '—'}
                    </div>
                    {p.regex_pattern && (
                      <div style={{
                        marginTop: '6px', padding: '4px 8px', background: 'var(--bg-primary)',
                        borderRadius: '3px', fontSize: '10px', fontFamily: 'var(--font-mono)',
                        color: 'var(--warning)'
                      }}>
                        {p.regex_pattern}
                      </div>
                    )}
                    {p.suggested_action && (
                      <div style={{ marginTop: '6px', fontSize: '11px' }}>
                        <span style={{ color: 'var(--info)' }}>💡 </span>
                        {p.suggested_action}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {tab === 'runbooks' && (
              <RunbookList />
            )}
          </>
        )}
      </div>
    </div>
  )
}

function RunbookList() {
  const [runbooks, setRunbooks] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.sqlQuery("SELECT * FROM dbai_knowledge.runbook_steps ORDER BY runbook_id, step_order")
      .then(r => setRunbooks(r.rows || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ color: 'var(--text-secondary)' }}>Lade Runbooks...</div>

  const grouped = runbooks.reduce((acc, step) => {
    const id = step.runbook_id || 'unknown'
    if (!acc[id]) acc[id] = []
    acc[id].push(step)
    return acc
  }, {})

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {Object.entries(grouped).map(([id, steps]) => (
        <div key={id} style={{
          padding: '12px', background: 'var(--bg-surface)',
          borderRadius: '6px', border: '1px solid var(--border)'
        }}>
          <div style={{ fontWeight: 600, color: 'var(--accent)', marginBottom: '8px' }}>
            📖 Runbook #{id}
          </div>
          {steps.map((step, i) => (
            <div key={i} style={{
              padding: '4px 0', fontSize: '11px',
              display: 'flex', gap: '8px', alignItems: 'flex-start'
            }}>
              <span style={{
                minWidth: '20px', height: '20px', borderRadius: '50%',
                background: 'var(--bg-elevated)', display: 'flex',
                alignItems: 'center', justifyContent: 'center',
                fontSize: '10px', color: 'var(--accent)'
              }}>{step.step_order}</span>
              <div>
                <div style={{ fontWeight: 500 }}>{step.title || step.action_type}</div>
                <div style={{ color: 'var(--text-secondary)', fontSize: '10px' }}>
                  {step.description || step.action_payload || ''}
                </div>
              </div>
            </div>
          ))}
        </div>
      ))}
      {Object.keys(grouped).length === 0 && (
        <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-secondary)' }}>
          Keine Runbooks definiert
        </div>
      )}
    </div>
  )
}
