import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'

/**
 * System Monitor — Live-Hardware-Metriken
 * Aktualisiert sich via WebSocket-Events
 */
export default function SystemMonitor() {
  const [status, setStatus] = useState(null)
  const [processes, setProcesses] = useState([])
  const [health, setHealth] = useState([])
  const [tab, setTab] = useState('overview') // overview, processes, health

  // Initial load
  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 5000)
    return () => clearInterval(interval)
  }, [])

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
  }, [tab])

  useEffect(() => { refresh() }, [tab])

  const meterClass = (pct) => pct > 90 ? 'danger' : pct > 70 ? 'warning' : ''

  return (
    <div>
      {/* Tabs */}
      <div className="flex gap-2" style={{ marginBottom: '16px' }}>
        {['overview', 'processes', 'health'].map(t => (
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
            {t === 'overview' ? '📊 Übersicht' : t === 'processes' ? '⚙️ Prozesse' : '🏥 Health'}
          </button>
        ))}
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
