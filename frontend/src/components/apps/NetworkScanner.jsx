import React, { useState, useEffect } from 'react'
import { api } from '../../api'

/**
 * Netzwerk Scanner — Web-UIs im lokalen Netzwerk entdecken
 * Router, NAS, Drucker, Kameras, Smart Home, Roboter, AI-Server…
 */
export default function NetworkScanner() {
  const [devices, setDevices] = useState([])
  const [scanning, setScanning] = useState(false)
  const [lastScan, setLastScan] = useState(null)
  const [filter, setFilter] = useState('all')
  const [adding, setAdding] = useState(null)

  useEffect(() => {
    loadDevices()
  }, [])

  const loadDevices = async () => {
    try {
      const d = await api.networkDevices()
      setDevices(d || [])
    } catch { setDevices([]) }
  }

  const handleScan = async () => {
    setScanning(true)
    try {
      const r = await api.networkScan()
      setLastScan({ count: r.devices?.length || 0, subnet: r.subnet, ips: r.scanned_ips })
      await loadDevices()
    } catch (e) {
      setLastScan({ error: e.message })
    }
    setScanning(false)
  }

  const handleAddToDesktop = async (deviceId) => {
    setAdding(deviceId)
    try {
      await api.networkAddToDesktop(deviceId)
      await loadDevices()
    } catch {}
    setAdding(null)
  }

  const types = ['all', ...new Set(devices.map(d => d.device_type))]
  const filtered = filter === 'all' ? devices : devices.filter(d => d.device_type === filter)

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      fontFamily: 'var(--font-sans)', fontSize: 13,
    }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
      }}>
        <button onClick={handleScan} disabled={scanning} style={{
          padding: '6px 16px', borderRadius: 'var(--radius, 6px)', cursor: 'pointer',
          background: scanning ? 'var(--bg-elevated)' : 'rgba(0,255,204,0.12)',
          border: '1px solid var(--accent)', color: 'var(--accent)',
          fontSize: 12, fontWeight: 600,
        }}>
          {scanning ? '📡 Scanne…' : '🔍 Netzwerk scannen'}
        </button>

        <select value={filter} onChange={e => setFilter(e.target.value)} style={{
          padding: '5px 10px', background: 'var(--bg-surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius, 6px)', color: 'var(--text-primary)', fontSize: 12,
        }}>
          {types.map(t => (
            <option key={t} value={t}>
              {t === 'all' ? '🔗 Alle' : `${typeIcons[t] || '🔗'} ${typeLabels[t] || t}`}
            </option>
          ))}
        </select>

        <span style={{ fontSize: 11, color: 'var(--text-secondary)', marginLeft: 'auto' }}>
          {devices.length} Geräte bekannt
        </span>
      </div>

      {/* Scan-Ergebnis */}
      {lastScan && (
        <div style={{
          padding: '8px 16px', fontSize: 11,
          background: lastScan.error ? 'rgba(255,80,80,0.08)' : 'rgba(0,255,204,0.05)',
          borderBottom: '1px solid var(--border)',
          color: lastScan.error ? '#f55' : 'var(--text-secondary)',
        }}>
          {lastScan.error
            ? `❌ Scan fehlgeschlagen: ${lastScan.error}`
            : `✅ ${lastScan.count} Web-UIs gefunden • ${lastScan.subnet} • ${lastScan.ips} IPs geprüft`
          }
        </div>
      )}

      {/* Tabelle */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: '2px solid var(--border)', position: 'sticky', top: 0, background: 'var(--bg-primary)' }}>
              <th style={thStyle}>Typ</th>
              <th style={thStyle}>Name</th>
              <th style={thStyle}>IP</th>
              <th style={thStyle}>Port</th>
              <th style={thStyle}>Web-Titel</th>
              <th style={thStyle}>Status</th>
              <th style={thStyle}>Aktion</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(d => (
              <tr key={d.id} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={tdStyle}>
                  <span title={typeLabels[d.device_type] || d.device_type}>
                    {typeIcons[d.device_type] || '🔗'}
                  </span>
                </td>
                <td style={tdStyle}>{d.hostname || '—'}</td>
                <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)' }}>{d.ip}</td>
                <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)' }}>{d.web_port}</td>
                <td style={{ ...tdStyle, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {d.web_title || '—'}
                </td>
                <td style={tdStyle}>
                  <span style={{
                    display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                    background: d.is_reachable ? '#0f8' : '#f55', marginRight: 4,
                  }} />
                  {d.is_reachable ? 'online' : 'offline'}
                </td>
                <td style={tdStyle}>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <a href={d.web_url} target="_blank" rel="noopener noreferrer"
                      style={{ color: 'var(--accent)', textDecoration: 'none', fontSize: 11 }}>
                      🔗 Öffnen
                    </a>
                    {!d.added_to_desktop && (
                      <button onClick={() => handleAddToDesktop(d.id)}
                        disabled={adding === d.id}
                        style={{
                          background: 'none', border: 'none', color: 'var(--accent)',
                          cursor: 'pointer', fontSize: 11, padding: 0,
                        }}>
                        {adding === d.id ? '⏳' : '➕ Desktop'}
                      </button>
                    )}
                    {d.added_to_desktop && (
                      <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>✅ Auf Desktop</span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filtered.length === 0 && !scanning && (
          <div style={{
            padding: 40, textAlign: 'center', color: 'var(--text-secondary)',
          }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>🌐</div>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>Keine Geräte gefunden</div>
            <div style={{ fontSize: 12 }}>
              Klicke auf „Netzwerk scannen" um Geräte in deinem lokalen Netzwerk zu entdecken.
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

const typeIcons = {
  nas: '💾', router: '🌐', printer: '🖨️', camera: '📷',
  smarthome: '🏠', robot: '🤖', server: '🖥️', ai: '🧠',
  media: '🎬', dns: '🛡️', iot: '📡', phone: '📱', unknown: '🔗',
}

const typeLabels = {
  nas: 'NAS / Speicher', router: 'Router / Gateway', printer: 'Drucker',
  camera: 'Kamera', smarthome: 'Smart Home', robot: 'Roboter',
  server: 'Server', ai: 'KI / LLM', media: 'Medienserver',
  dns: 'DNS / Filter', iot: 'IoT-Gerät', phone: 'Smartphone', unknown: 'Unbekannt',
}

const thStyle = {
  padding: '8px 10px', textAlign: 'left', color: 'var(--text-secondary)',
  fontSize: 11, fontWeight: 600,
}

const tdStyle = {
  padding: '8px 10px', color: 'var(--text-primary)',
}
