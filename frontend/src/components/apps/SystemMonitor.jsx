import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

/**
 * System Monitor — Live-Hardware-Metriken + Prozess-Manager
 * Vereint Übersicht, Prozesse, Health und Prozess-Verwaltung
 * Aktualisiert sich via WebSocket-Events
 */
export default function SystemMonitor() {
  const { settings, schema, loading: sLoading, update: updateSetting, reset: resetSettings } = useAppSettings('system-monitor')
  const [showSettings, setShowSettings] = useState(false)
  const [status, setStatus] = useState(null)
  const [processes, setProcesses] = useState([])
  const [health, setHealth] = useState([])
  const [tab, setTab] = useState('overview') // overview, processes, health, manager

  // Prozess-Manager State
  const [pmProcesses, setPmProcesses] = useState([])
  const [pmLoading, setPmLoading] = useState(true)
  const [sortBy, setSortBy] = useState(settings?.default_sort || 'pid')

  const refreshInterval = settings?.refresh_interval ?? 5000
  const warningThreshold = settings?.warning_threshold ?? 70
  const criticalThreshold = settings?.critical_threshold ?? 90

  // Initial load
  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, refreshInterval)
    return () => clearInterval(interval)
  }, [refreshInterval])

  // Listen for metrics updates
  useEffect(() => {
    const handler = (e) => setStatus(prev => ({ ...prev, ...e.detail }))
    window.addEventListener('dbai:metrics', handler)
    return () => window.removeEventListener('dbai:metrics', handler)
  }, [])

  const refresh = useCallback(() => {
    api.systemStatus().then(setStatus).catch(() => {})
    if (tab === 'processes') api.processes().then(setProcesses).catch(() => {})
    if (tab === 'health') api.health().then(setHealth).catch(() => {})
    if (tab === 'manager') {
      api.processes().then(d => { setPmProcesses(d || []); setPmLoading(false) }).catch(() => setPmLoading(false))
    }
  }, [tab])

  useEffect(() => { refresh() }, [tab])

  const meterClass = (pct) => pct > criticalThreshold ? 'danger' : pct > warningThreshold ? 'warning' : ''

  // Prozess-Manager Sortierung
  const sorted = [...pmProcesses].sort((a, b) => {
    if (sortBy === 'pid') return (a.pid || 0) - (b.pid || 0)
    if (sortBy === 'cpu') return (b.cpu_usage || 0) - (a.cpu_usage || 0)
    if (sortBy === 'memory') return (b.memory_mb || 0) - (a.memory_mb || 0)
    if (sortBy === 'state') return (a.state || '').localeCompare(b.state || '')
    return 0
  })

  const pmHeaderStyle = (col) => ({
    padding: '8px 12px', textAlign: 'left', cursor: 'pointer',
    borderBottom: '2px solid var(--border)',
    color: sortBy === col ? 'var(--accent)' : 'var(--text-secondary)',
    fontSize: '11px', textTransform: 'uppercase',
    fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap',
    userSelect: 'none'
  })

  if (showSettings) {
    return (
      <div style={{ padding: '16px' }}>
        <button onClick={() => setShowSettings(false)} style={{ marginBottom: '12px', padding: '4px 12px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 'var(--radius)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '11px' }}>← Zurück</button>
        <AppSettingsPanel schema={schema} settings={settings} onUpdate={updateSetting} onReset={resetSettings} title="System Monitor" />
      </div>
    )
  }

  return (
    <div>
      {/* Tabs */}
      <div className="flex gap-2" style={{ marginBottom: '16px', flexWrap: 'wrap' }}>
        {['overview', 'processes', 'health', 'manager'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '6px 16px', borderRadius: 'var(--radius)',
              border: `1px solid ${tab === t ? 'var(--accent)' : 'var(--border)'}`,
              background: tab === t ? 'rgba(0,255,204,0.1)' : 'transparent',
              color: tab === t ? 'var(--accent)' : 'var(--text-secondary)',
              cursor: 'pointer', fontSize: '12px',
            }}
          >
            {t === 'overview' ? '📊 Übersicht' : t === 'processes' ? '⚙️ Prozesse' : t === 'health' ? '🏥 Health' : '🔧 Prozess-Manager'}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <button onClick={() => setShowSettings(true)} style={{ padding: '6px 12px', borderRadius: 'var(--radius)', border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '12px' }}>⚙️</button>
      </div>

      {tab === 'overview' && status && (
        <div className="sys-monitor">
          <MetricCard
            title="CPU" icon="🔲"
            value={status.cpu_usage_percent ?? '-'}
            unit="%" meterClass={meterClass}
          />
          <MetricCard
            title="Memory" icon="💾"
            value={status.memory_usage_percent ?? '-'}
            unit="%" meterClass={meterClass}
          />
          <MetricCard
            title="Disk" icon="💿"
            value={status.disk_usage_percent ?? '-'}
            unit="%" meterClass={meterClass}
          />
          <div className="sys-card">
            <h3>📡 Netzwerk</h3>
            <div className="text-mono text-accent" style={{ fontSize: '14px' }}>
              {status.network_interfaces ?? '-'} Interface(s)
            </div>
          </div>
        </div>
      )}

      {tab === 'overview' && !status && (
        <div className="text-muted p-4">Lade System-Status...</div>
      )}

      {tab === 'processes' && (
        <div style={{ overflow: 'auto', fontSize: '12px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Name', 'Typ', 'Status', 'Priorität', 'PID', 'Heartbeat'].map(h => (
                  <th key={h} style={{
                    padding: '6px 12px', textAlign: 'left',
                    borderBottom: '1px solid var(--border)',
                    color: 'var(--accent)', fontFamily: 'var(--font-mono)',
                    fontSize: '10px', textTransform: 'uppercase',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {processes.map((p, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '6px 12px', fontWeight: 500 }}>{p.name}</td>
                  <td style={{ padding: '6px 12px' }} className="text-mono text-xs">{p.process_type}</td>
                  <td style={{ padding: '6px 12px' }}>
                    <span style={{
                      padding: '1px 6px', borderRadius: '8px', fontSize: '10px',
                      background: p.state === 'running' ? 'rgba(0,255,136,0.15)' :
                                  p.state === 'crashed' ? 'rgba(255,68,68,0.15)' : 'rgba(102,136,170,0.15)',
                      color: p.state === 'running' ? 'var(--success)' :
                             p.state === 'crashed' ? 'var(--danger)' : 'var(--text-secondary)',
                    }}>{p.state}</span>
                  </td>
                  <td style={{ padding: '6px 12px' }} className="text-mono">{p.priority}</td>
                  <td style={{ padding: '6px 12px' }} className="text-mono text-xs">{p.pid ?? '-'}</td>
                  <td style={{ padding: '6px 12px' }} className="text-xs text-muted">
                    {p.last_heartbeat ? new Date(p.last_heartbeat).toLocaleTimeString('de-DE') : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {processes.length === 0 && (
            <div className="text-muted p-4">Keine Prozesse registriert</div>
          )}
        </div>
      )}

      {tab === 'health' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {health.map((check, i) => (
            <div key={i} className="sys-card" style={{
              display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 16px',
              borderLeft: `3px solid ${
                check.status === 'ok' ? 'var(--success)' :
                check.status === 'warning' ? 'var(--warning)' : 'var(--danger)'
              }`,
            }}>
              <span style={{ fontSize: '18px' }}>
                {check.status === 'ok' ? '✅' : check.status === 'warning' ? '⚠️' : '❌'}
              </span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 500, fontSize: '13px' }}>{check.check_name}</div>
                <div className="text-xs text-muted">{check.message}</div>
              </div>
              {check.metric_value != null && (
                <div className="text-mono text-accent" style={{ fontSize: '14px' }}>
                  {check.metric_value}{check.metric_unit ? ` ${check.metric_unit}` : ''}
                </div>
              )}
            </div>
          ))}
          {health.length === 0 && (
            <div className="text-muted p-4">Lade Health-Checks...</div>
          )}
          <button
            onClick={() => api.selfHeal().then(refresh)}
            style={{
              alignSelf: 'flex-start', padding: '8px 16px', marginTop: '8px',
              background: 'rgba(0,255,204,0.1)', border: '1px solid var(--accent)',
              borderRadius: 'var(--radius)', color: 'var(--accent)',
              cursor: 'pointer', fontSize: '12px',
            }}
          >
            🔧 Self-Heal ausführen
          </button>
        </div>
      )}

      {/* Prozess-Manager Tab (ehemals eigene App) */}
      {tab === 'manager' && (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column', fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
          {/* Toolbar */}
          <div style={{
            padding: '8px 12px', borderBottom: '1px solid var(--border)',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center'
          }}>
            <span style={{ color: 'var(--text-secondary)' }}>
              {pmProcesses.length} Prozesse
            </span>
            <button
              onClick={refresh}
              style={{
                padding: '4px 12px', background: 'var(--bg-elevated)',
                border: '1px solid var(--border)', borderRadius: '4px',
                color: 'var(--text-primary)', cursor: 'pointer', fontSize: '11px'
              }}
            >
              ↻ Aktualisieren
            </button>
          </div>

          {/* Prozess-Tabelle */}
          <div style={{ flex: 1, overflow: 'auto' }}>
            {pmLoading ? (
              <div style={{ padding: '20px', color: 'var(--text-secondary)', textAlign: 'center' }}>Lade Prozesse...</div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th onClick={() => setSortBy('pid')} style={pmHeaderStyle('pid')}>PID</th>
                    <th style={{ ...pmHeaderStyle('name'), cursor: 'default' }}>Prozess</th>
                    <th onClick={() => setSortBy('state')} style={pmHeaderStyle('state')}>Status</th>
                    <th onClick={() => setSortBy('cpu')} style={pmHeaderStyle('cpu')}>CPU %</th>
                    <th onClick={() => setSortBy('memory')} style={pmHeaderStyle('memory')}>RAM MB</th>
                    <th style={{ ...pmHeaderStyle(''), cursor: 'default' }}>Backend</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((proc, i) => (
                    <tr key={i} style={{
                      borderBottom: '1px solid var(--border)',
                      background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)'
                    }}>
                      <td style={{ padding: '6px 12px', color: 'var(--text-secondary)' }}>{proc.pid}</td>
                      <td style={{ padding: '6px 12px', fontWeight: 500 }}>
                        {proc.application_name || proc.query?.substring(0, 40) || '—'}
                      </td>
                      <td style={{ padding: '6px 12px' }}>
                        <span style={{
                          padding: '2px 6px', borderRadius: '3px', fontSize: '10px',
                          background: proc.state === 'active' ? 'rgba(0,255,136,0.15)' :
                                      proc.state === 'idle' ? 'rgba(102,136,170,0.15)' :
                                      'rgba(255,170,0,0.15)',
                          color: proc.state === 'active' ? 'var(--success)' :
                                 proc.state === 'idle' ? 'var(--text-secondary)' :
                                 'var(--warning)'
                        }}>
                          {proc.state || '?'}
                        </span>
                      </td>
                      <td style={{ padding: '6px 12px', textAlign: 'right' }}>
                        {proc.cpu_usage != null ? proc.cpu_usage.toFixed(1) : '—'}
                      </td>
                      <td style={{ padding: '6px 12px', textAlign: 'right' }}>
                        {proc.memory_mb != null ? proc.memory_mb.toFixed(1) : '—'}
                      </td>
                      <td style={{ padding: '6px 12px', color: 'var(--text-secondary)', fontSize: '10px' }}>
                        {proc.backend_type || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function MetricCard({ title, icon, value, unit, meterClass }) {
  const numVal = parseFloat(value) || 0
  return (
    <div className="sys-card">
      <h3>{icon} {title}</h3>
      <div>
        <span className="value">{typeof value === 'number' ? value.toFixed(1) : value}</span>
        <span className="unit">{unit}</span>
      </div>
      <div className="meter">
        <div
          className={`meter-fill ${meterClass(numVal)}`}
          style={{ width: `${Math.min(100, numVal)}%` }}
        />
      </div>
    </div>
  )
}
