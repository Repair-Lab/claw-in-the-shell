import React, { useState, useEffect } from 'react'
import { api } from '../../api'

/**
 * ProcessManager — Laufende Prozesse verwalten
 */
export default function ProcessManager({ windowId }) {
  const [processes, setProcesses] = useState([])
  const [loading, setLoading] = useState(true)
  const [sortBy, setSortBy] = useState('pid')

  const refresh = async () => {
    try {
      const data = await api.processes()
      setProcesses(data || [])
    } catch (err) {
      console.error('Prozesse laden fehlgeschlagen:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 5000)
    return () => clearInterval(interval)
  }, [])

  const sorted = [...processes].sort((a, b) => {
    if (sortBy === 'pid') return (a.pid || 0) - (b.pid || 0)
    if (sortBy === 'cpu') return (b.cpu_usage || 0) - (a.cpu_usage || 0)
    if (sortBy === 'memory') return (b.memory_mb || 0) - (a.memory_mb || 0)
    if (sortBy === 'state') return (a.state || '').localeCompare(b.state || '')
    return 0
  })

  const headerStyle = (col) => ({
    padding: '8px 12px', textAlign: 'left', cursor: 'pointer',
    borderBottom: '2px solid var(--border)',
    color: sortBy === col ? 'var(--accent)' : 'var(--text-secondary)',
    fontSize: '11px', textTransform: 'uppercase',
    fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap',
    userSelect: 'none'
  })

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
      {/* Toolbar */}
      <div style={{
        padding: '8px 12px', borderBottom: '1px solid var(--border)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center'
      }}>
        <span style={{ color: 'var(--text-secondary)' }}>
          {processes.length} Prozesse
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

      {/* Table */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {loading ? (
          <div style={{ padding: '20px', color: 'var(--text-secondary)', textAlign: 'center' }}>Lade Prozesse...</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th onClick={() => setSortBy('pid')} style={headerStyle('pid')}>PID</th>
                <th style={{ ...headerStyle('name'), cursor: 'default' }}>Prozess</th>
                <th onClick={() => setSortBy('state')} style={headerStyle('state')}>Status</th>
                <th onClick={() => setSortBy('cpu')} style={headerStyle('cpu')}>CPU %</th>
                <th onClick={() => setSortBy('memory')} style={headerStyle('memory')}>RAM MB</th>
                <th style={{ ...headerStyle(''), cursor: 'default' }}>Backend</th>
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
  )
}
