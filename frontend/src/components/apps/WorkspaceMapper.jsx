import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'

export default function WorkspaceMapper() {
  const [stats, setStats] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [scanning, setScanning] = useState(false)
  const [scanResult, setScanResult] = useState(null)
  const [scanPath, setScanPath] = useState('')
  const [view, setView] = useState('overview')

  const loadStats = useCallback(async () => {
    try { setStats(await api.workspaceStats()) } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadStats() }, [loadStats])

  const startScan = async () => {
    setScanning(true)
    try {
      const paths = scanPath ? scanPath.split(',').map(s => s.trim()) : undefined
      const result = await api.workspaceScan(paths)
      setScanResult(result)
      loadStats()
    } catch { /* ignore */ }
    finally { setScanning(false) }
  }

  const search = async () => {
    if (!searchQuery.trim()) return
    try {
      const results = await api.workspaceSearch(searchQuery)
      setSearchResults(results.files || [])
    } catch { /* ignore */ }
  }

  const formatSize = (bytes) => {
    if (!bytes) return '0 B'
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
  }

  const catIcons = { code: '💻', document: '📄', image: '🖼️', video: '🎬', audio: '🎵', archive: '📦', config: '⚙️', data: '📊', web: '🌐', model: '🧠', other: '📁' }
  const catColors = { code: '#00ffcc', document: '#4488ff', image: '#cc44ff', video: '#ff4444', audio: '#ffaa00', archive: '#ff8844', config: '#44ddff', data: '#66ff99', web: '#ff66cc', model: '#aa88ff', other: '#556' }

  const S = {
    container: { display: 'flex', flexDirection: 'column', height: '100%', background: '#0a0a14', color: '#c8d6e5', padding: '16px', overflow: 'auto' },
    h: { color: '#00ffcc', fontSize: '18px', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' },
    card: { background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '8px', padding: '12px', marginBottom: '8px' },
    btn: { padding: '6px 16px', border: '1px solid #00ffcc', background: 'transparent', color: '#00ffcc', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' },
    input: { padding: '6px 12px', background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '6px', color: '#d4d4d4', fontSize: '13px', outline: 'none', flex: 1 },
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: '8px', marginBottom: '16px' },
    stat: { background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '8px', padding: '10px', textAlign: 'center' },
    tabs: { display: 'flex', gap: '4px', marginBottom: '16px' },
    tab: (active) => ({ padding: '6px 14px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', background: active ? '#1a2a3a' : 'transparent', color: active ? '#00ffcc' : '#556', border: active ? '1px solid #00ffcc33' : '1px solid transparent' }),
  }

  return (
    <div style={S.container}>
      <div style={S.h}><span>📂</span> Workspace Mapping</div>

      <div style={S.tabs}>
        <div style={S.tab(view === 'overview')} onClick={() => setView('overview')}>Übersicht</div>
        <div style={S.tab(view === 'scan')} onClick={() => setView('scan')}>Scannen</div>
        <div style={S.tab(view === 'search')} onClick={() => setView('search')}>Suche</div>
      </div>

      {view === 'overview' && stats && (
        <>
          {stats.total && (
            <div style={{ ...S.card, display: 'flex', justifyContent: 'space-around', textAlign: 'center' }}>
              <div><div style={{ color: '#00ffcc', fontSize: '24px', fontWeight: 700 }}>{stats.total.files?.toLocaleString()}</div><div style={{ color: '#556', fontSize: '11px' }}>Dateien</div></div>
              <div><div style={{ color: '#4488ff', fontSize: '24px', fontWeight: 700 }}>{formatSize(stats.total.total_size)}</div><div style={{ color: '#556', fontSize: '11px' }}>Gesamt</div></div>
              <div><div style={{ color: '#ffaa00', fontSize: '24px', fontWeight: 700 }}>{stats.total.categories}</div><div style={{ color: '#556', fontSize: '11px' }}>Kategorien</div></div>
            </div>
          )}
          <div style={S.grid}>
            {(stats.by_category || []).map((cat, i) => (
              <div key={i} style={S.stat}>
                <div style={{ fontSize: '20px' }}>{catIcons[cat.category] || '📁'}</div>
                <div style={{ color: catColors[cat.category] || '#556', fontSize: '12px', fontWeight: 600 }}>{cat.category}</div>
                <div style={{ color: '#d4d4d4', fontSize: '16px', fontWeight: 700 }}>{cat.file_count}</div>
                <div style={{ color: '#445', fontSize: '10px' }}>
                  {cat.file_ext && <span>.{cat.file_ext}</span>}
                  {cat.total_size && <span> · {formatSize(cat.total_size)}</span>}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {view === 'scan' && (
        <div style={S.card}>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
            <input style={S.input} value={scanPath} onChange={e => setScanPath(e.target.value)} placeholder="Pfade (kommagetrennt, leer = Home)" />
            <button style={S.btn} onClick={startScan} disabled={scanning}>
              {scanning ? '⏳ Scanne...' : '🔍 Scan starten'}
            </button>
          </div>
          {scanResult && (
            <div style={{ fontSize: '13px', color: '#8899aa' }}>
              <div>✓ <span style={{ color: '#00ffcc' }}>{scanResult.files}</span> Dateien indexiert</div>
              <div>✓ <span style={{ color: '#4488ff' }}>{scanResult.dirs}</span> Verzeichnisse</div>
              <div>✓ <span style={{ color: '#ffaa00' }}>{formatSize(scanResult.total_size)}</span> Gesamtgröße</div>
              {scanResult.errors > 0 && <div>⚠ <span style={{ color: '#ff4444' }}>{scanResult.errors}</span> Fehler</div>}
            </div>
          )}
        </div>
      )}

      {view === 'search' && (
        <>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
            <input
              style={S.input}
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Dateiname oder Pfad suchen..."
              onKeyDown={e => e.key === 'Enter' && search()}
            />
            <button style={S.btn} onClick={search}>🔍</button>
          </div>
          {searchResults.length > 0 && (
            <div>
              {searchResults.map((f, i) => (
                <div key={i} style={{ ...S.card, fontSize: '12px', display: 'flex', justifyContent: 'space-between' }}>
                  <div>
                    <span style={{ marginRight: '6px' }}>{catIcons[f.category] || '📁'}</span>
                    <span style={{ color: '#d4d4d4' }}>{f.file_name}</span>
                    <div style={{ color: '#445', fontSize: '10px', marginTop: '2px' }}>{f.file_path}</div>
                  </div>
                  <div style={{ textAlign: 'right', color: '#556', fontSize: '11px' }}>
                    <div>{formatSize(f.file_size)}</div>
                    {f.line_count && <div>{f.line_count} Zeilen</div>}
                    {f.language && <div style={{ color: catColors.code }}>{f.language}</div>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
