import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'

export default function ConfigImporter() {
  const [scanResult, setScanResult] = useState(null)
  const [importResult, setImportResult] = useState(null)
  const [scanning, setScanning] = useState(false)
  const [importing, setImporting] = useState(false)
  const [status, setStatus] = useState(null)
  const [expanded, setExpanded] = useState(null)

  const loadStatus = useCallback(async () => {
    try { setStatus(await api.configStatus()) } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadStatus() }, [loadStatus])

  const scan = async () => {
    setScanning(true)
    try {
      const result = await api.configScan()
      setScanResult(result)
    } catch { /* ignore */ }
    finally { setScanning(false) }
  }

  const importAll = async () => {
    setImporting(true)
    try {
      const result = await api.configImport()
      setImportResult(result)
      loadStatus()
    } catch { /* ignore */ }
    finally { setImporting(false) }
  }

  const categoryIcons = {
    wifi: '📶', keyboard: '⌨️', locale: '🌍', timezone: '🕐', display: '🖥️',
    audio: '🔊', shell: '💻', users: '👥', network: '🌐', ssh: '🔐',
    systemd: '⚙️', fstab: '💾', dns: '📡', hosts: '📋', cron: '⏰',
  }

  const S = {
    container: { display: 'flex', flexDirection: 'column', height: '100%', background: '#0a0a14', color: '#c8d6e5', padding: '16px', overflow: 'auto' },
    h: { color: '#00ffcc', fontSize: '18px', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' },
    card: { background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '8px', padding: '12px', marginBottom: '8px', cursor: 'pointer', transition: 'border-color 0.15s' },
    btn: { padding: '6px 16px', border: '1px solid #00ffcc', background: 'transparent', color: '#00ffcc', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' },
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '8px', marginBottom: '16px' },
    stat: { background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '8px', padding: '10px', textAlign: 'center' },
  }

  return (
    <div style={S.container}>
      <div style={S.h}><span>⚙️</span> System Config Import</div>
      <p style={{ color: '#556', fontSize: '13px', marginBottom: '16px' }}>
        Scannt /etc/ und ~/.config/ — WLAN, Tastatur, User-Rechte, Shell-Config, Systemd-Services.
      </p>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
        <button style={S.btn} onClick={scan} disabled={scanning}>
          {scanning ? '⏳ Scanne...' : '🔍 System scannen'}
        </button>
        {scanResult && (
          <button style={{ ...S.btn, borderColor: '#ffaa00', color: '#ffaa00' }} onClick={importAll} disabled={importing}>
            {importing ? '⏳ Importiere...' : '📥 Alles importieren'}
          </button>
        )}
      </div>

      {status?.configs && (
        <div style={S.grid}>
          {status.configs.map((c, i) => (
            <div key={i} style={S.stat}>
              <div style={{ fontSize: '20px' }}>{categoryIcons[c.config_type] || '📄'}</div>
              <div style={{ color: '#d4d4d4', fontSize: '13px', fontWeight: 600 }}>{c.config_type}</div>
              <div style={{ color: '#00ffcc', fontSize: '18px', fontWeight: 700 }}>{c.count}</div>
            </div>
          ))}
        </div>
      )}

      {scanResult && Object.entries(scanResult).filter(([k]) => !k.startsWith('_')).map(([cat, items]) => {
        const arr = Array.isArray(items) ? items : (items && typeof items === 'object' ? [items] : [])
        if (arr.length === 0) return null
        return (
          <div key={cat}
            style={{ ...S.card, borderColor: expanded === cat ? '#00ffcc' : '#1a2a3a' }}
            onClick={() => setExpanded(expanded === cat ? null : cat)}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span style={{ marginRight: '8px' }}>{categoryIcons[cat] || '📄'}</span>
                <strong style={{ color: '#d4d4d4' }}>{cat}</strong>
                <span style={{ color: '#445', marginLeft: '8px', fontSize: '12px' }}>({arr.length})</span>
              </div>
              <span style={{ color: '#445' }}>{expanded === cat ? '▼' : '▶'}</span>
            </div>
            {expanded === cat && (
              <div style={{ marginTop: '8px', fontSize: '12px' }}>
                {arr.map((item, j) => (
                  <div key={j} style={{ padding: '4px 0', borderTop: j > 0 ? '1px solid #111828' : 'none', color: '#8899aa' }}>
                    <span style={{ color: '#00ccff' }}>{item.name || item.ssid || item.key || '—'}</span>
                    {item.value && <span style={{ color: '#556', marginLeft: '8px' }}>{String(item.value).substring(0, 80)}</span>}
                    {item.source_path && <span style={{ color: '#334', marginLeft: '8px', fontSize: '10px' }}>({item.source_path})</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}

      {importResult && (
        <div style={{ ...S.card, borderColor: '#00ffcc' }}>
          <div style={{ color: '#00ffcc', fontWeight: 600, marginBottom: '8px' }}>✓ Import abgeschlossen</div>
          {Object.entries(importResult).map(([k, v]) => (
            <div key={k} style={{ fontSize: '12px', color: '#8899aa' }}>
              {categoryIcons[k] || '📄'} {k}: <span style={{ color: '#00ffcc' }}>{v}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
