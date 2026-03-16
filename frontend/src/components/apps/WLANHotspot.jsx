import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'

export default function WLANHotspot() {
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
      <div style={S.h}><span>📡</span> WLAN Hotspot</div>

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
        <div style={{ display: 'flex', gap: '8px' }}>
          <button style={S.btnDanger} onClick={stop} disabled={loading}>
            {loading ? '⏳ Stoppe...' : '⏹ Hotspot stoppen'}
          </button>
          <button style={S.btn} onClick={loadStatus}>🔄 Aktualisieren</button>
        </div>
      )}
    </div>
  )
}
