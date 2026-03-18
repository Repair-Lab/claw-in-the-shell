import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

export default function USBInstaller() {
  const { settings, schema, update, reset } = useAppSettings('usb_installer')
  const [showSettings, setShowSettings] = useState(false)
  const [devices, setDevices] = useState([])
  const [jobs, setJobs] = useState([])
  const [imagePath, setImagePath] = useState('')
  const [selectedDevice, setSelectedDevice] = useState(null)
  const [method, setMethod] = useState('dd')
  const [scanning, setScanning] = useState(false)

  const loadDevices = useCallback(async () => {
    setScanning(true)
    try { const r = await api.usbDevices(); setDevices(r.devices || []) } catch { /* */ }
    finally { setScanning(false) }
  }, [])

  const loadJobs = useCallback(async () => {
    try { const r = await api.usbJobs(); setJobs(r.jobs || []) } catch { /* */ }
  }, [])

  useEffect(() => { loadDevices(); loadJobs() }, [loadDevices, loadJobs])

  const flash = async () => {
    if (!selectedDevice || !imagePath) return
    try {
      await api.usbFlash(selectedDevice, imagePath, method)
      loadJobs()
    } catch { /* */ }
  }

  const cancelJob = async (id) => {
    try { await api.usbCancelJob(id); loadJobs() } catch { /* */ }
  }

  const formatSize = (b) => { if (!b) return '?'; const u = ['B','KB','MB','GB','TB']; const i = Math.floor(Math.log(b)/Math.log(1024)); return `${(b/Math.pow(1024,i)).toFixed(1)} ${u[i]}` }

  const S = {
    container: { display: 'flex', flexDirection: 'column', height: '100%', background: '#0a0a14', color: '#c8d6e5', padding: '16px', overflow: 'auto' },
    h: { color: '#00ffcc', fontSize: '18px', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' },
    card: { background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '8px', padding: '12px', marginBottom: '8px' },
    btn: { padding: '6px 16px', border: '1px solid #00ffcc', background: 'transparent', color: '#00ffcc', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' },
    input: { padding: '6px 12px', background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '6px', color: '#d4d4d4', fontSize: '13px', outline: 'none', flex: 1 },
    select: { padding: '6px 12px', background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '6px', color: '#d4d4d4', fontSize: '13px', outline: 'none' },
  }

  const statusColors = { pending: '#556', preparing: '#ffaa00', flashing: '#4488ff', verifying: '#cc44ff', completed: '#00ffcc', failed: '#ff4444' }

  return (
    <div style={S.container}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div style={S.h}>💾 USB Installer</div>
        <button style={{ ...S.btn, padding: '4px 10px' }} onClick={() => setShowSettings(!showSettings)}>⚙️</button>
      </div>
      {showSettings && <AppSettingsPanel settings={settings} schema={schema} onUpdate={update} onReset={reset} />}
      <p style={{ color: '#556', fontSize: '13px', marginBottom: '16px' }}>ISO/IMG auf USB-Stick flashen (dd/Ventoy).</p>

      <button style={{ ...S.btn, marginBottom: '16px' }} onClick={loadDevices} disabled={scanning}>
        {scanning ? '⏳' : '🔍'} USB-Geräte erkennen
      </button>

      {devices.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <div style={{ color: '#6688aa', fontSize: '12px', marginBottom: '8px' }}>USB-Geräte:</div>
          {devices.map((d, i) => (
            <div key={i} style={{ ...S.card, cursor: 'pointer', borderColor: selectedDevice === d.device_path ? '#00ffcc' : '#1a2a3a' }} onClick={() => setSelectedDevice(d.device_path)}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <div>
                  <strong style={{ color: '#d4d4d4' }}>{d.device_path}</strong>
                  <span style={{ color: '#556', marginLeft: '8px' }}>{d.vendor} {d.model}</span>
                </div>
                <span style={{ color: '#00ccff' }}>{formatSize(d.size_bytes)}</span>
              </div>
              {d.is_mounted && <div style={{ color: '#ffaa00', fontSize: '11px', marginTop: '4px' }}>⚠ Gemountet: {d.mount_point}</div>}
            </div>
          ))}
        </div>
      )}

      {selectedDevice && (
        <div style={S.card}>
          <div style={{ color: '#d4d4d4', fontWeight: 600, marginBottom: '8px' }}>Flash-Konfiguration</div>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
            <input style={S.input} value={imagePath} onChange={e => setImagePath(e.target.value)} placeholder="Pfad zum ISO/IMG..." />
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <select style={S.select} value={method} onChange={e => setMethod(e.target.value)}>
              <option value="dd">dd (Standard)</option>
              <option value="ventoy">Ventoy</option>
            </select>
            <span style={{ color: '#556', fontSize: '11px' }}>→ {selectedDevice}</span>
            <button style={{ ...S.btn, borderColor: '#ff4444', color: '#ff4444' }} onClick={flash}>
              ⚡ Flashen
            </button>
          </div>
        </div>
      )}

      {jobs.length > 0 && (
        <div style={{ marginTop: '16px' }}>
          <div style={{ color: '#6688aa', fontSize: '12px', marginBottom: '8px' }}>Flash-Jobs:</div>
          {jobs.map((j, i) => (
            <div key={i} style={S.card}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: '#d4d4d4', fontSize: '12px' }}>{j.image_path?.split('/').pop()}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ color: statusColors[j.status] || '#556', fontSize: '11px', fontWeight: 600 }}>{j.status}</span>
                  {(j.status === 'pending' || j.status === 'flashing' || j.status === 'preparing') && (
                    <button style={{ ...S.btn, fontSize: '10px', padding: '2px 8px', borderColor: '#ff4444', color: '#ff4444' }} onClick={() => cancelJob(j.id)}>✗</button>
                  )}
                </div>
              </div>
              {j.progress > 0 && j.progress < 1 && (
                <div style={{ marginTop: '6px', height: '4px', background: '#111828', borderRadius: '2px' }}>
                  <div style={{ width: `${j.progress * 100}%`, height: '100%', background: '#4488ff', borderRadius: '2px', transition: 'width 0.5s' }} />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
