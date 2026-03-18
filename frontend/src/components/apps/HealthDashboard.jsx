import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

/**
 * HealthDashboard — Self-Repair + Auto-Diagnose + LLM-Status
 *
 * Automatische Analyse von:
 * - Datenbank-Verbindung & Schema-Integrität
 * - LLM-Provider-Verfügbarkeit (Chat, Embedding, Vision)
 * - API-Endpoint-Erreichbarkeit
 * - Festplatten- & RAM-Nutzung
 * - App-Registrierung
 * - KI-Werkstatt-Bereitschaft
 */
export default function HealthDashboard() {
  const { settings, schema, update: updateSetting, reset: resetSettings } = useAppSettings('health-dashboard')
  const [showSettings, setShowSettings] = useState(false)
  const [diagnostics, setDiagnostics] = useState(null)
  const [basicHealth, setBasicHealth] = useState([])
  const [healResult, setHealResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [healing, setHealing] = useState(false)
  const [tab, setTab] = useState(settings?.default_tab || 'diagnostics')
  const [autoFixLog, setAutoFixLog] = useState([])

  const autoRefreshInterval = settings?.auto_refresh_interval ?? 30000
  const showFixHints = settings?.show_fix_hints !== false
  const showScoreBanner = settings?.show_score_banner !== false

  const runDiagnostics = useCallback(async () => {
    setLoading(true)
    try {
      const [diag, health] = await Promise.all([
        api.diagnostics().catch(() => null),
        api.health().catch(() => []),
      ])
      setDiagnostics(diag)
      setBasicHealth(health)
    } catch (err) {
      console.error('Diagnostics:', err)
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    runDiagnostics()
    const interval = setInterval(runDiagnostics, autoRefreshInterval)
    return () => clearInterval(interval)
  }, [runDiagnostics, autoRefreshInterval])

  const handleSelfHeal = async () => {
    setHealing(true)
    setAutoFixLog(prev => [...prev, { time: new Date().toISOString(), msg: '🔧 Self-Heal gestartet...' }])
    try {
      const result = await api.selfHeal()
      setHealResult(result)
      setAutoFixLog(prev => [...prev, { time: new Date().toISOString(), msg: '✅ Self-Heal abgeschlossen', data: result }])
      runDiagnostics()
    } catch (err) {
      setHealResult({ error: err.message })
      setAutoFixLog(prev => [...prev, { time: new Date().toISOString(), msg: `❌ Self-Heal Fehler: ${err.message}` }])
    }
    setHealing(false)
  }

  const summary = diagnostics?.summary || {}
  const checks = diagnostics?.checks || []

  const categoryLabels = {
    database: '🐘 Datenbank', llm: '🤖 KI / LLM', api: '🌐 API-Endpoints',
    workshop: '🧪 KI-Werkstatt', apps: '📱 Apps', system: '💻 System',
  }
  const statusIcon = (s) => s === 'ok' ? '✅' : s === 'warning' ? '⚠️' : s === 'critical' ? '❌' : 'ℹ️'
  const statusColor = (s) => s === 'ok' ? 'var(--success)' : s === 'warning' ? 'var(--warning)' : s === 'critical' ? 'var(--danger)' : 'var(--info)'

  const grouped = {}
  checks.forEach(c => {
    const cat = c.category || 'other'
    if (!grouped[cat]) grouped[cat] = []
    grouped[cat].push(c)
  })

  if (loading && !diagnostics) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', gap: 12 }}>
        <div style={{ fontSize: 48 }}>🔍</div>
        <div style={{ fontSize: 14, color: 'var(--text-secondary)' }}>Auto-Diagnose läuft...</div>
      </div>
    )
  }

  if (showSettings) {
    return (
      <div style={{ padding: '16px' }}>
        <button onClick={() => setShowSettings(false)} style={{ marginBottom: '12px', padding: '4px 12px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 'var(--radius)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '11px' }}>← Zurück</button>
        <AppSettingsPanel schema={schema} settings={settings} onUpdate={updateSetting} onReset={resetSettings} title="Health Dashboard" />
      </div>
    )
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', fontFamily: 'var(--font-sans)', fontSize: 13 }}>
      {/* Header */}
      <div style={{
        padding: '14px 20px', borderBottom: '1px solid var(--border)',
        background: 'var(--bg-secondary)', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>🛡️ Self-Repair & Diagnose</h2>
          <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
            Automatische Systemanalyse • Letzte Prüfung: {diagnostics?.timestamp ? new Date(diagnostics.timestamp).toLocaleTimeString('de') : '–'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => setShowSettings(true)} style={S.btnSecondary}>⚙️</button>
          <button onClick={runDiagnostics} disabled={loading} style={S.btnSecondary}>
            {loading ? '⏳' : '🔄'} Neu prüfen
          </button>
          <button onClick={handleSelfHeal} disabled={healing} style={S.btnPrimary}>
            {healing ? '⏳ Repariere...' : '🔧 Self-Heal'}
          </button>
        </div>
      </div>

      {/* Score Banner */}
      {showScoreBanner && (
      <div style={{
        padding: '16px 20px',
        background: summary.score >= 80 ? 'rgba(0,255,136,0.06)' : summary.score >= 50 ? 'rgba(255,170,0,0.06)' : 'rgba(255,68,68,0.06)',
        borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 20,
      }}>
        <div style={{
          width: 64, height: 64, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 22, fontWeight: 800,
          background: `conic-gradient(${summary.score >= 80 ? 'var(--success)' : summary.score >= 50 ? 'var(--warning)' : 'var(--danger)'} ${(summary.score || 0) * 3.6}deg, var(--bg-elevated) 0)`,
        }}>
          <div style={{
            width: 52, height: 52, borderRadius: '50%', background: 'var(--bg-primary)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-primary)',
          }}>
            {summary.score || 0}%
          </div>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>
            {summary.score >= 90 ? '🟢 System gesund' : summary.score >= 70 ? '🟡 Kleine Probleme' : summary.score >= 50 ? '🟠 Aufmerksamkeit nötig' : '🔴 Kritische Probleme'}
          </div>
          <div style={{ display: 'flex', gap: 16, fontSize: 12 }}>
            <span style={{ color: 'var(--success)' }}>✅ {summary.ok || 0} OK</span>
            <span style={{ color: 'var(--warning)' }}>⚠️ {summary.warnings || 0} Warnungen</span>
            <span style={{ color: 'var(--danger)' }}>❌ {summary.critical || 0} Kritisch</span>
          </div>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{summary.total || 0} Checks</div>
      </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)' }}>
        {[
          { id: 'diagnostics', label: '🔬 Diagnose', count: checks.length },
          { id: 'health', label: '💓 DB-Health', count: basicHealth.length },
          { id: 'log', label: '📋 Reparatur-Log', count: autoFixLog.length },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: '10px 20px', border: 'none', background: 'transparent', cursor: 'pointer',
            color: tab === t.id ? 'var(--accent)' : 'var(--text-secondary)', fontSize: 12,
            borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
          }}>
            {t.label} ({t.count})
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>
        {/* === DIAGNOSTICS TAB === */}
        {tab === 'diagnostics' && (
          <div>
            {checks.some(c => c.category === 'llm' && c.status === 'warning') && (
              <div style={{
                padding: '14px 16px', marginBottom: 16, borderRadius: 8,
                background: 'rgba(255,170,0,0.08)', border: '1px solid rgba(255,170,0,0.25)',
                display: 'flex', alignItems: 'flex-start', gap: 12,
              }}>
                <span style={{ fontSize: 24 }}>🤖</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, marginBottom: 4, color: 'var(--warning)' }}>
                    KI-Funktionen eingeschränkt
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    {checks.filter(c => c.category === 'llm' && c.status === 'warning').map(c => c.message).join(' • ')}
                  </div>
                  {checks.filter(c => c.fix_hint).slice(0, 3).map((c, i) => (
                    <div key={i} style={{ marginTop: 6, fontSize: 12, color: 'var(--accent)' }}>
                      💡 {c.fix_hint}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {Object.entries(grouped).map(([cat, items]) => (
              <div key={cat} style={{ marginBottom: 20 }}>
                <h3 style={{ fontSize: 14, marginBottom: 10, color: 'var(--text-primary)' }}>
                  {categoryLabels[cat] || cat}
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {items.map((check, i) => (
                    <div key={i} style={{
                      display: 'flex', alignItems: 'center', gap: 12,
                      padding: '10px 14px', background: 'var(--bg-surface)',
                      border: '1px solid var(--border)', borderRadius: 8,
                      borderLeft: `3px solid ${statusColor(check.status)}`,
                    }}>
                      <span style={{ fontSize: 16 }}>{statusIcon(check.status)}</span>
                      <span style={{ fontSize: 16 }}>{check.icon || '🔧'}</span>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, fontSize: 12 }}>{check.name}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{check.message}</div>
                        {showFixHints && check.fix_hint && (
                          <div style={{ fontSize: 11, color: 'var(--accent)', marginTop: 3 }}>
                            💡 Lösung: {check.fix_hint}
                          </div>
                        )}
                      </div>
                      {check.metric_value != null && (
                        <div style={{
                          fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)',
                          color: statusColor(check.status),
                        }}>
                          {check.metric_value}{check.metric_unit || ''}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}

            {checks.length === 0 && (
              <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>
                Keine Diagnose-Ergebnisse. Klicke "Neu prüfen".
              </div>
            )}
          </div>
        )}

        {/* === DB HEALTH TAB === */}
        {tab === 'health' && (
          <div>
            <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
              {[
                { label: 'Gesund', count: basicHealth.filter(h => h.status === 'ok').length, color: 'var(--success)' },
                { label: 'Warnungen', count: basicHealth.filter(h => h.status === 'warning').length, color: 'var(--warning)' },
                { label: 'Kritisch', count: basicHealth.filter(h => h.status === 'critical').length, color: 'var(--danger)' },
              ].map(c => (
                <div key={c.label} style={S.summaryCard}>
                  <h3 style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)' }}>{c.label}</h3>
                  <div style={{ fontSize: 28, fontWeight: 700, color: c.color }}>{c.count}</div>
                </div>
              ))}
            </div>

            {basicHealth.map((check, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '10px 14px', background: 'var(--bg-surface)',
                border: '1px solid var(--border)', borderRadius: 8,
                borderLeft: `3px solid ${statusColor(check.status)}`,
                marginBottom: 6,
              }}>
                <span style={{ fontSize: 16 }}>{statusIcon(check.status)}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 500, fontSize: 12 }}>{check.check_name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{check.message}</div>
                </div>
                {check.metric_value != null && (
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 14, color: statusColor(check.status) }}>
                    {check.metric_value}{check.metric_unit ? ` ${check.metric_unit}` : ''}
                  </div>
                )}
                {check.duration_ms != null && (
                  <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{check.duration_ms}ms</span>
                )}
              </div>
            ))}
          </div>
        )}

        {/* === LOG TAB === */}
        {tab === 'log' && (
          <div>
            {autoFixLog.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>
                <div style={{ fontSize: 36, marginBottom: 8 }}>📋</div>
                Noch keine Reparaturen durchgeführt. Klicke "Self-Heal" um zu starten.
              </div>
            ) : (
              autoFixLog.map((entry, i) => (
                <div key={i} style={{
                  padding: '10px 14px', background: 'var(--bg-surface)', borderRadius: 8,
                  border: '1px solid var(--border)', marginBottom: 6,
                  fontFamily: 'var(--font-mono)', fontSize: 12,
                }}>
                  <span style={{ color: 'var(--text-secondary)' }}>
                    [{new Date(entry.time).toLocaleTimeString('de')}]
                  </span>{' '}
                  {entry.msg}
                  {entry.data && (
                    <pre style={{
                      marginTop: 6, padding: 8, background: 'var(--bg-primary)',
                      borderRadius: 4, fontSize: 11, overflow: 'auto', maxHeight: 150,
                    }}>
                      {JSON.stringify(entry.data, null, 2)}
                    </pre>
                  )}
                </div>
              ))
            )}

            {healResult && (
              <div style={{
                marginTop: 16, padding: 12, background: 'var(--bg-surface)', borderRadius: 8,
                border: '1px solid var(--border)', fontFamily: 'var(--font-mono)', fontSize: 11,
                whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto',
              }}>
                <div style={{ fontWeight: 600, marginBottom: 6, fontSize: 12, color: 'var(--text-primary)' }}>
                  Letztes Self-Heal Ergebnis:
                </div>
                {JSON.stringify(healResult, null, 2)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

const S = {
  btnPrimary: {
    padding: '8px 16px', background: 'rgba(0,255,204,0.1)', border: '1px solid var(--accent)',
    borderRadius: 6, color: 'var(--accent)', cursor: 'pointer', fontSize: 12, fontWeight: 600,
  },
  btnSecondary: {
    padding: '8px 16px', background: 'transparent', border: '1px solid var(--border)',
    borderRadius: 6, color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 12,
  },
  summaryCard: {
    flex: 1, textAlign: 'center', padding: 16, background: 'var(--bg-surface)',
    border: '1px solid var(--border)', borderRadius: 8,
  },
}
