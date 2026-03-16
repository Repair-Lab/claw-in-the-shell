import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'

export default function AppSandbox() {
  const [profiles, setProfiles] = useState([])
  const [running, setRunning] = useState([])
  const [appName, setAppName] = useState('')
  const [exePath, setExePath] = useState('')
  const [selProfile, setSelProfile] = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    try {
      const [p, r] = await Promise.all([api.sandboxProfiles(), api.sandboxRunning()])
      setProfiles(p.profiles || [])
      setRunning(r.running || [])
      if (p.profiles?.length && !selProfile) setSelProfile(p.profiles[0].profile_name)
    } catch { /* */ }
  }, [selProfile])

  useEffect(() => { load() }, [load])

  const launch = async () => {
    if (!appName || !exePath || !selProfile) return
    setLoading(true)
    try { await api.sandboxLaunch(appName, exePath, selProfile); setAppName(''); setExePath(''); await load() } catch { /* */ }
    finally { setLoading(false) }
  }

  const stopApp = async (pid) => {
    try { await api.sandboxStop(pid); await load() } catch { /* */ }
  }

  const S = {
    container: { display: 'flex', flexDirection: 'column', height: '100%', background: '#0a0a14', color: '#c8d6e5', padding: '16px', overflow: 'auto' },
    h: { color: '#00ffcc', fontSize: '18px', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' },
    card: { background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '8px', padding: '12px', marginBottom: '8px' },
    btn: { padding: '6px 16px', border: '1px solid #00ffcc', background: 'transparent', color: '#00ffcc', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' },
    input: { padding: '6px 12px', background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '6px', color: '#d4d4d4', fontSize: '13px', outline: 'none', flex: 1 },
    select: { padding: '6px 12px', background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '6px', color: '#d4d4d4', fontSize: '13px', outline: 'none' },
    badge: (active) => ({ padding: '2px 8px', borderRadius: '10px', fontSize: '10px', fontWeight: 600, background: active ? 'rgba(0,255,204,0.15)' : 'rgba(100,100,100,0.15)', color: active ? '#00ffcc' : '#556' }),
    permBadge: (perm) => ({ padding: '1px 6px', borderRadius: '8px', fontSize: '9px', fontWeight: 600, marginRight: '4px', background: perm ? 'rgba(68,136,255,0.15)' : 'rgba(255,68,68,0.15)', color: perm ? '#4488ff' : '#ff4444' }),
  }

  return (
    <div style={S.container}>
      <div style={S.h}><span>📦</span> App Sandboxing</div>
      <p style={{ color: '#556', fontSize: '13px', marginBottom: '16px' }}>Firejail/cgroup-basierte Isolation für Anwendungen.</p>

      {/* Launch Form */}
      <div style={S.card}>
        <div style={{ color: '#d4d4d4', fontWeight: 600, marginBottom: '10px' }}>App in Sandbox starten</div>
        <div style={{ display: 'flex', gap: '6px', marginBottom: '8px' }}>
          <input style={S.input} value={appName} onChange={e => setAppName(e.target.value)} placeholder="App-Name..." />
          <input style={{ ...S.input, flex: 2 }} value={exePath} onChange={e => setExePath(e.target.value)} placeholder="Pfad zur Executable..." />
        </div>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <select style={S.select} value={selProfile} onChange={e => setSelProfile(e.target.value)}>
            {profiles.map(p => <option key={p.profile_name} value={p.profile_name}>{p.profile_name}</option>)}
          </select>
          <button style={S.btn} onClick={launch} disabled={loading}>
            {loading ? '⏳' : '▶️'} Starten
          </button>
        </div>
      </div>

      {/* Running */}
      {running.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <div style={{ color: '#6688aa', fontSize: '12px', marginBottom: '8px' }}>Laufende Sandbox-Apps:</div>
          {running.map((r, i) => (
            <div key={i} style={S.card}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <strong style={{ color: '#d4d4d4' }}>{r.app_name}</strong>
                  <span style={{ color: '#556', marginLeft: '8px', fontSize: '11px' }}>PID: {r.pid}</span>
                  <span style={S.badge(true)}>{r.profile_name}</span>
                </div>
                <button style={{ ...S.btn, borderColor: '#ff4444', color: '#ff4444', padding: '3px 10px' }}
                  onClick={() => stopApp(r.pid)}>⏹ Stop</button>
              </div>
              <div style={{ display: 'flex', gap: '8px', marginTop: '6px', fontSize: '10px', color: '#445' }}>
                <span>CPU: {r.cpu_percent || 0}%</span>
                <span>RAM: {r.memory_mb || 0} MB</span>
                <span>Seit: {new Date(r.started_at).toLocaleTimeString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Profiles */}
      <div style={{ color: '#6688aa', fontSize: '12px', marginBottom: '8px' }}>Sandbox-Profile:</div>
      {profiles.map((p, i) => (
        <div key={i} style={S.card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <strong style={{ color: '#d4d4d4' }}>{p.profile_name}</strong>
            <span style={S.badge(p.is_default)}>
              {p.is_default ? 'Standard' : 'Benutzerdefiniert'}
            </span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2px', marginBottom: '4px' }}>
            {[
              ['Netzwerk', p.permissions?.network],
              ['Dateisystem', p.permissions?.filesystem],
              ['Display', p.permissions?.display],
              ['Audio', p.permissions?.audio],
              ['IPC', p.permissions?.ipc],
            ].map(([name, val]) => (
              <span key={name} style={S.permBadge(val)}>{val ? '✓' : '✗'} {name}</span>
            ))}
          </div>
          {p.description && <div style={{ color: '#556', fontSize: '11px' }}>{p.description}</div>}
        </div>
      ))}
    </div>
  )
}
