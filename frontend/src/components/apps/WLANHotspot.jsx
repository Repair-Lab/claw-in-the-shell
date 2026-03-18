import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

export default function WLANHotspot() {
  const { settings, schema, update, reset } = useAppSettings('wlan_hotspot')
  const [showSettings, setShowSettings] = useState(false)
  const [status, setStatus] = useState(null)
  const [ssid, setSsid] = useState('DBAI-Hotspot')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  const loadStatus = useCallback(async () => {
    try { const r = await api.hotspotStatus(); setStatus(r) } catch { /* */ }
  }, [])

  useEffect(() => { loadStatus() }, [loadStatus])

  const create = async () => {
    if (!ssid || password.length < 8) return
    setLoading(true)
    try { await api.hotspotCreate(ssid, password); await loadStatus() } catch { /* */ }
    finally { setLoading(false) }
  }

  const stop = async () => {
    setLoading(true)
    try { await api.hotspotStop(); await loadStatus() } catch { /* */ }
    finally { setLoading(false) }
  }

  const [showConfig, setShowConfig] = useState(false)
  const [cfgChannel, setCfgChannel] = useState('')
  const [cfgBand, setCfgBand] = useState('2.4')

  const saveConfig = async () => {
    try {
      const config = {}
      if (cfgChannel) config.channel = parseInt(cfgChannel)
      if (cfgBand) config.band = cfgBand
      await api.hotspotUpdateConfig(config)
      setShowConfig(false)
      loadStatus()
    } catch { /* */ }
  }

  const S = {
    container: { display: 'flex', flexDirection: 'column', height: '100%', background: '#0a0a14', color: '#c8d6e5', padding: '16px', overflow: 'auto' },
    h: { color: '#00ffcc', fontSize: '18px', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' },
    card: { background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '8px', padding: '16px', marginBottom: '12px' },
    btn: { padding: '8px 20px', border: '1px solid #00ffcc', background: 'transparent', color: '#00ffcc', borderRadius: '6px', cursor: 'pointer', fontSize: '13px' },
    btnDanger: { padding: '8px 20px', border: '1px solid #ff4444', background: 'transparent', color: '#ff4444', borderRadius: '6px', cursor: 'pointer', fontSize: '13px' },
    input: { padding: '8px 12px', background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '6px', color: '#d4d4d4', fontSize: '13px', outline: 'none', width: '100%', boxSizing: 'border-box' },
    label: { color: '#6688aa', fontSize: '12px', marginBottom: '4px', display: 'block' },
    stat: { display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #111828' },
  }

  const isActive = status?.active

  return (
    <div style={S.container}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div style={S.h}>📡 WLAN Hotspot</div>
        <button style={{ ...S.btn, padding: '4px 10px' }} onClick={() => setShowSettings(!showSettings)}>⚙️</button>
      </div>
      {showSettings && <AppSettingsPanel settings={settings} schema={schema} onUpdate={update} onReset={reset} />}

      <div style={S.card}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
          <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: isActive ? '#00ffcc' : '#444' }} />
          <span style={{ color: isActive ? '#00ffcc' : '#556', fontWeight: 600 }}>
            {isActive ? 'Aktiv' : 'Inaktiv'}
          </span>
        </div>
        {isActive && status && (
          <div>
            <div style={S.stat}>
              <span style={{ color: '#556' }}>SSID</span>
              <span style={{ color: '#d4d4d4' }}>{status.ssid}</span>
            </div>
            <div style={S.stat}>
              <span style={{ color: '#556' }}>Interface</span>
              <span style={{ color: '#d4d4d4' }}>{status.interface || '—'}</span>
            </div>
            <div style={S.stat}>
              <span style={{ color: '#556' }}>Band</span>
              <span style={{ color: '#d4d4d4' }}>{status.band || '2.4 GHz'}</span>
            </div>
            <div style={S.stat}>
              <span style={{ color: '#556' }}>IP</span>
              <span style={{ color: '#d4d4d4' }}>{status.ip || '10.42.0.1'}</span>
            </div>
            <div style={S.stat}>
              <span style={{ color: '#556' }}>Clients</span>
              <span style={{ color: '#00ccff' }}>{status.clients || 0}</span>
            </div>
          </div>
        )}
      </div>

      {!isActive ? (
        <div style={S.card}>
          <div style={{ color: '#d4d4d4', fontWeight: 600, marginBottom: '12px' }}>Hotspot erstellen</div>
          <div style={{ marginBottom: '12px' }}>
            <label style={S.label}>SSID</label>
            <input style={S.input} value={ssid} onChange={e => setSsid(e.target.value)} placeholder="Netzwerkname..." />
          </div>
          <div style={{ marginBottom: '12px' }}>
            <label style={S.label}>Passwort (min. 8 Zeichen)</label>
            <input style={S.input} type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Passwort..." />
          </div>
          <button style={S.btn} onClick={create} disabled={loading || !ssid || password.length < 8}>
            {loading ? '⏳ Starte...' : '📡 Hotspot starten'}
          </button>
        </div>
      ) : (
        <div>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
            <button style={S.btnDanger} onClick={stop} disabled={loading}>
              {loading ? '⏳ Stoppe...' : '⏹ Hotspot stoppen'}
            </button>
            <button style={S.btn} onClick={loadStatus}>🔄 Aktualisieren</button>
            <button style={{ ...S.btn, borderColor: '#4488ff', color: '#4488ff' }} onClick={() => setShowConfig(!showConfig)}>
              🔧 Konfiguration
            </button>
          </div>
          {showConfig && (
            <div style={S.card}>
              <div style={{ color: '#d4d4d4', fontWeight: 600, marginBottom: '10px' }}>Erweiterte Konfiguration</div>
              <div style={{ display: 'flex', gap: '8px', marginBottom: '8px', alignItems: 'center' }}>
                <label style={{ ...S.label, marginBottom: 0, minWidth: '60px' }}>Band</label>
                <select style={{ ...S.input, width: 'auto' }} value={cfgBand} onChange={e => setCfgBand(e.target.value)}>
                  <option value="2.4">2.4 GHz</option>
                  <option value="5">5 GHz</option>
                </select>
              </div>
              <div style={{ display: 'flex', gap: '8px', marginBottom: '8px', alignItems: 'center' }}>
                <label style={{ ...S.label, marginBottom: 0, minWidth: '60px' }}>Kanal</label>
                <input style={{ ...S.input, width: '80px' }} type="number" value={cfgChannel} onChange={e => setCfgChannel(e.target.value)} placeholder="Auto" min="1" max="165" />
              </div>
              <button style={S.btn} onClick={saveConfig}>💾 Speichern</button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
