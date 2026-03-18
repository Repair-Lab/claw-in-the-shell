import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

export default function ImmutableFS() {
  const { settings, schema, update, reset } = useAppSettings('immutable_fs')
  const [showSettings, setShowSettings] = useState(false)
  const [config, setConfig] = useState(null)
  const [snapshots, setSnapshots] = useState([])
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    try {
      const [c, s] = await Promise.all([api.immutableConfig(), api.immutableSnapshots()])
      setConfig(c)
      setSnapshots(s.snapshots || [])
    } catch { /* */ }
  }, [])

  useEffect(() => { load() }, [load])

  const enable = async (mode) => {
    setLoading(true)
    try { await api.immutableEnable(mode); await load() } catch { /* */ }
    finally { setLoading(false) }
  }

  const createSnapshot = async () => {
    const label = prompt('Snapshot-Name:')
    if (!label) return
    try { await api.immutableCreateSnapshot(label); await load() } catch { /* */ }
  }

  const deleteSnapshot = async (id) => {
    if (!confirm('Snapshot wirklich löschen?')) return
    try { await api.immutableDeleteSnapshot(id); await load() } catch { /* */ }
  }

  const restoreSnapshot = async (id) => {
    if (!confirm('Snapshot wiederherstellen? Aktuelle Änderungen gehen verloren!')) return
    try { await api.immutableRestoreSnapshot(id); alert('Wiederherstellung gestartet') } catch { /* */ }
  }

  const S = {
    container: { display: 'flex', flexDirection: 'column', height: '100%', background: '#0a0a14', color: '#c8d6e5', padding: '16px', overflow: 'auto' },
    h: { color: '#00ffcc', fontSize: '18px', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' },
    card: { background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '8px', padding: '14px', marginBottom: '10px' },
    btn: { padding: '6px 16px', border: '1px solid #00ffcc', background: 'transparent', color: '#00ffcc', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' },
    row: { display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #111828' },
    badge: (active) => ({ padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: 600, background: active ? 'rgba(0,255,204,0.15)' : 'rgba(100,100,100,0.15)', color: active ? '#00ffcc' : '#556' }),
  }

  const modes = [
    { key: 'full', name: 'Voll-Immutabel', desc: 'Alle Systemdateien werden per OverlayFS schreibgeschützt', icon: '🔒' },
    { key: 'partial', name: 'Teilweise', desc: 'Nur /etc und /usr sind geschützt, /home bleibt beschreibbar', icon: '🔐' },
    { key: 'off', name: 'Deaktiviert', desc: 'Normales beschreibbares Dateisystem', icon: '🔓' },
  ]

  return (
    <div style={S.container}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div style={S.h}>🛡️ Immutable Filesystem</div>
        <button style={{ ...S.btn, padding: '4px 10px' }} onClick={() => setShowSettings(!showSettings)}>⚙️</button>
      </div>
      {showSettings && <AppSettingsPanel settings={settings} schema={schema} onUpdate={update} onReset={reset} />}
      <p style={{ color: '#556', fontSize: '13px', marginBottom: '16px' }}>OverlayFS-basiertes schreibgeschütztes Root-Dateisystem mit Snapshot-Unterstützung.</p>

      <div style={S.card}>
        <div style={{ color: '#d4d4d4', fontWeight: 600, marginBottom: '10px' }}>Aktueller Modus</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <span style={{ fontSize: '20px' }}>{modes.find(m => m.key === config?.mode)?.icon || '❓'}</span>
          <span style={{ color: '#00ffcc', fontWeight: 600 }}>{config?.mode || 'Unbekannt'}</span>
        </div>
        {config && (
          <>
            <div style={S.row}><span style={{ color: '#556' }}>OverlayFS</span><span style={S.badge(config.overlay_active)}>
              {config.overlay_active ? 'Aktiv' : 'Inaktiv'}</span></div>
            <div style={S.row}><span style={{ color: '#556' }}>Schreibschicht</span><span style={{ color: '#d4d4d4' }}>{config.upper_dir || '—'}</span></div>
            <div style={S.row}><span style={{ color: '#556' }}>Arbeitslayer</span><span style={{ color: '#d4d4d4' }}>{config.work_dir || '—'}</span></div>
          </>
        )}
      </div>

      <div style={{ color: '#6688aa', fontSize: '12px', marginBottom: '8px' }}>Modus wechseln:</div>
      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
        {modes.map(m => (
          <div key={m.key} style={{ ...S.card, flex: '1 1 180px', cursor: 'pointer', borderColor: config?.mode === m.key ? '#00ffcc' : '#1a2a3a' }} onClick={() => enable(m.key)}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
              <span>{m.icon}</span>
              <strong style={{ color: '#d4d4d4', fontSize: '13px' }}>{m.name}</strong>
            </div>
            <div style={{ color: '#556', fontSize: '11px' }}>{m.desc}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <div style={S.h}><span>📸</span> Snapshots</div>
        <button style={S.btn} onClick={createSnapshot}>+ Snapshot</button>
      </div>
      {snapshots.length === 0 ? (
        <div style={{ color: '#334', textAlign: 'center', padding: '20px' }}>Keine Snapshots vorhanden</div>
      ) : (
        snapshots.map((s, i) => (
          <div key={i} style={S.card}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ color: '#d4d4d4', fontWeight: 600, fontSize: '13px' }}>{s.snapshot_name}</div>
                <div style={{ color: '#556', fontSize: '11px' }}>{new Date(s.created_at).toLocaleString()}</div>
              </div>
              <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                <span style={{ color: '#6688aa', fontSize: '11px' }}>{s.size_mb ? `${s.size_mb} MB` : ''}</span>
                <span style={S.badge(s.is_bootable)}>
                  {s.is_bootable ? 'Bootfähig' : 'Standard'}
                </span>
                <button style={{ background: 'none', border: 'none', color: '#4488ff', cursor: 'pointer', fontSize: '12px' }} onClick={() => restoreSnapshot(s.id)} title="Wiederherstellen">♻️</button>
                <button style={{ background: 'none', border: 'none', color: '#ff4444', cursor: 'pointer', fontSize: '12px' }} onClick={() => deleteSnapshot(s.id)} title="Löschen">🗑</button>
              </div>
            </div>
            {s.description && <div style={{ color: '#556', fontSize: '11px', marginTop: '4px' }}>{s.description}</div>}
          </div>
        ))
      )}
    </div>
  )
}
