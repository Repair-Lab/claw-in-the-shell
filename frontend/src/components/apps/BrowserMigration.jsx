import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

export default function BrowserMigration() {
  const { settings, schema, update, reset } = useAppSettings('browser_migration')
  const [showSettings, setShowSettings] = useState(false)
  const [profiles, setProfiles] = useState([])
  const [imported, setImported] = useState([])
  const [scanning, setScanning] = useState(false)
  const [importing, setImporting] = useState(null)
  const [log, setLog] = useState([])

  const scan = useCallback(async () => {
    setScanning(true)
    try {
      const result = await api.browserScan()
      setProfiles(result.profiles || [])
      setLog(prev => [...prev, `${result.profiles?.length || 0} Browser-Profile gefunden`])
    } catch (e) { setLog(prev => [...prev, `Fehler: ${e.message}`]) }
    finally { setScanning(false) }
  }, [])

  const loadStatus = useCallback(async () => {
    try {
      const result = await api.browserStatus()
      setImported(result.profiles || [])
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadStatus() }, [loadStatus])

  const [selectedTypes, setSelectedTypes] = useState({ bookmarks: true, history: true, passwords: false })

  const toggleType = (t) => setSelectedTypes(prev => ({ ...prev, [t]: !prev[t] }))

  const importProfile = async (p) => {
    const types = Object.entries(selectedTypes).filter(([, v]) => v).map(([k]) => k)
    if (types.length === 0) { alert('Mindestens einen Datentyp auswählen!'); return }
    setImporting(p.profile_path)
    setLog(prev => [...prev, `Importiere ${p.browser_type}/${p.profile_name} (${types.join(', ')})...`])
    try {
      const result = await api.browserImportSelective(p.browser_type, p.profile_name, p.profile_path, types)
      setLog(prev => [...prev, `✓ Import abgeschlossen: ${JSON.stringify(result.selective_import || {})}`])
      loadStatus()
    } catch (e) { setLog(prev => [...prev, `✗ ${e.message}`]) }
    finally { setImporting(null) }
  }

  const S = {
    container: { display: 'flex', flexDirection: 'column', height: '100%', background: '#0a0a14', color: '#c8d6e5', padding: '16px', overflow: 'auto' },
    h: { color: '#00ffcc', fontSize: '18px', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' },
    card: { background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '8px', padding: '12px', marginBottom: '8px' },
    btn: { padding: '6px 16px', border: '1px solid #00ffcc', background: 'transparent', color: '#00ffcc', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' },
    btnSm: { padding: '4px 10px', border: '1px solid #1a2a3a', background: '#111828', color: '#6688aa', borderRadius: '4px', cursor: 'pointer', fontSize: '11px' },
    tag: { display: 'inline-block', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', marginRight: '4px' },
    log: { background: '#060810', border: '1px solid #1a1a2e', borderRadius: '6px', padding: '8px', fontFamily: 'monospace', fontSize: '11px', maxHeight: '150px', overflow: 'auto', color: '#6688aa' },
  }

  const browserIcons = { chrome: '🌐', firefox: '🦊', chromium: '◆', brave: '🦁', edge: '📐', vivaldi: '🎵', opera: '🔴' }

  return (
    <div style={S.container}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div style={S.h}>🌐 Browser-Migration</div>
        <button style={{ ...S.btn, padding: '4px 10px' }} onClick={() => setShowSettings(!showSettings)}>⚙️</button>
      </div>
      {showSettings && <AppSettingsPanel settings={settings} schema={schema} onUpdate={update} onReset={reset} />}
      <p style={{ color: '#556', fontSize: '13px', marginBottom: '16px' }}>
        Importiert Bookmarks, History und Passwörter aus Chrome/Firefox in die Ghost Knowledge Base.
      </p>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', alignItems: 'center' }}>
        <button style={S.btn} onClick={scan} disabled={scanning}>
          {scanning ? '⏳ Scanne...' : '🔍 Browser scannen'}
        </button>
        <div style={{ display: 'flex', gap: '10px', marginLeft: '12px' }}>
          {[['bookmarks', '🔖 Bookmarks'], ['history', '📜 History'], ['passwords', '🔑 Passwörter']].map(([k, l]) => (
            <label key={k} style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', fontSize: '11px', color: selectedTypes[k] ? '#00ffcc' : '#556' }}>
              <input type="checkbox" checked={selectedTypes[k]} onChange={() => toggleType(k)} style={{ accentColor: '#00ffcc' }} />
              {l}
            </label>
          ))}
        </div>
      </div>

      {profiles.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <div style={{ color: '#6688aa', fontSize: '12px', marginBottom: '8px' }}>
            Gefundene Profile ({profiles.length}):
          </div>
          {profiles.map((p, i) => (
            <div key={i} style={{ ...S.card, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span style={{ fontSize: '16px', marginRight: '8px' }}>{browserIcons[p.browser_type] || '🌐'}</span>
                <strong style={{ color: '#d4d4d4' }}>{p.browser_type}</strong>
                <span style={{ color: '#556', marginLeft: '8px' }}>/ {p.profile_name}</span>
                <div style={{ fontSize: '11px', color: '#445', marginTop: '4px' }}>
                  {p.has_bookmarks && <span style={{ ...S.tag, background: '#0a2a1a', color: '#00ffcc' }}>Bookmarks</span>}
                  {p.has_history && <span style={{ ...S.tag, background: '#1a1a0a', color: '#ffaa00' }}>History</span>}
                  {p.has_passwords && <span style={{ ...S.tag, background: '#2a0a0a', color: '#ff4444' }}>Passwörter</span>}
                </div>
              </div>
              <button
                style={importing === p.profile_path ? { ...S.btnSm, borderColor: '#ffaa00', color: '#ffaa00' } : S.btn}
                onClick={() => importProfile(p)}
                disabled={!!importing}
              >
                {importing === p.profile_path ? '⏳ ...' : '📥 Import'}
              </button>
            </div>
          ))}
        </div>
      )}

      {imported.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <div style={{ color: '#6688aa', fontSize: '12px', marginBottom: '8px' }}>
            Importierte Profile ({imported.length}):
          </div>
          {imported.map((p, i) => (
            <div key={i} style={{ ...S.card, opacity: 0.8 }}>
              <span>{browserIcons[p.browser_type] || '🌐'}</span>{' '}
              <strong>{p.browser_type}</strong> / {p.profile_name}
              <span style={{ color: '#445', marginLeft: '12px', fontSize: '11px' }}>
                📑 {p.bookmark_count} | 📜 {p.history_count} | 🕐 {new Date(p.imported_at).toLocaleString('de-DE')}
              </span>
            </div>
          ))}
        </div>
      )}

      {log.length > 0 && (
        <div style={S.log}>
          {log.map((l, i) => <div key={i}>{l}</div>)}
        </div>
      )}
    </div>
  )
}
