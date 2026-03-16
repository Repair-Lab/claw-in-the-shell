import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'

/**
 * KI-Werkstatt / Knowledge Base
 *
 * Tabs:
 *  - 📦 Module: Code-Module & ADRs durchsuchen
 *  - 🗂️ Importieren: Datei-Browser (USB, CD, Festplatten, Netzwerk)
 *  - 🐛 Fehler-Patterns: Bekannte Fehler & Lösungen
 *  - 📋 Report: System-Report
 */

const FORMAT_ICONS = {
  '.gguf': '🦙', '.bin': '📦', '.safetensors': '🔐',
  '.pt': '🔥', '.onnx': '⚡', '.pkl': '🥒',
  '.pdf': '📄', '.txt': '📝', '.md': '📝', '.csv': '📊',
  '.json': '⚙️', '.yaml': '⚙️', '.yml': '⚙️',
  '.zip': '🗜️', '.tar': '🗜️', '.gz': '🗜️', '.7z': '🗜️',
  '.mp4': '🎬', '.mp3': '🎵', '.wav': '🎵',
  '.jpg': '🖼️', '.jpeg': '🖼️', '.png': '🖼️', '.webp': '🖼️',
}

const MODEL_EXTS = ['.gguf', '.bin', '.safetensors', '.pt', '.onnx']

function formatSize(bytes) {
  if (bytes == null) return '—'
  if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(1) + ' GB'
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return bytes + ' B'
}

export default function KnowledgeBase() {
  const [tab, setTab] = useState('files')

  // ── File Browser State ──
  const [currentPath, setCurrentPath] = useState('/')
  const [entries, setEntries] = useState([])
  const [mounts, setMounts] = useState([])
  const [pathHistory, setPathHistory] = useState(['/'])
  const [historyIndex, setHistoryIndex] = useState(0)
  const [fbLoading, setFbLoading] = useState(false)
  const [fbError, setFbError] = useState(null)
  const [selected, setSelected] = useState(new Set())
  const [importResults, setImportResults] = useState([])
  const [importingModel, setImportingModel] = useState(null)
  const [showSidebar, setShowSidebar] = useState(true)
  const [filterExt, setFilterExt] = useState('')
  const [showOnlyModels, setShowOnlyModels] = useState(false)

  // ── Knowledge Base State ──
  const [modules, setModules] = useState([])
  const [errors, setErrors] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)

  // ── Initial Load ──
  useEffect(() => {
    api.fsMounts().then(setMounts).catch(() => setMounts([]))
    browsePath('/')
  }, [])

  useEffect(() => {
    if (tab === 'modules') api.kbModules?.().then(setModules).catch(() => {})
    if (tab === 'errors') api.errorPatterns?.().then(setErrors).catch(() => {})
  }, [tab])

  const browsePath = useCallback(async (path, addHistory = true) => {
    setFbLoading(true)
    setFbError(null)
    try {
      const data = await api.fsBrowse(path)
      setCurrentPath(data.path)
      setEntries(data.entries || [])
      setSelected(new Set())
      if (addHistory) {
        setPathHistory(prev => {
          const newHist = prev.slice(0, historyIndex + 1)
          return [...newHist, data.path]
        })
        setHistoryIndex(prev => prev + 1)
      }
    } catch (e) {
      setFbError(e.message || 'Zugriff verweigert')
    }
    setFbLoading(false)
  }, [historyIndex])

  const goBack = () => {
    if (historyIndex > 0) {
      const path = pathHistory[historyIndex - 1]
      setHistoryIndex(prev => prev - 1)
      browsePath(path, false)
    }
  }

  const goForward = () => {
    if (historyIndex < pathHistory.length - 1) {
      const path = pathHistory[historyIndex + 1]
      setHistoryIndex(prev => prev + 1)
      browsePath(path, false)
    }
  }

  const goUp = () => {
    const parts = currentPath.replace(/\/$/, '').split('/')
    if (parts.length > 1) {
      const parent = parts.slice(0, -1).join('/') || '/'
      browsePath(parent)
    }
  }

  const handleEntryClick = (entry) => {
    if (entry.is_dir) {
      browsePath(entry.path)
    }
  }

  const handleEntrySelect = (e, path) => {
    e.stopPropagation()
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  const handleImportModel = async (entry) => {
    setImportingModel(entry.path)
    try {
      const result = await api.llmAddModel({
        name: entry.name.replace(/\.[^.]+$/, ''),
        filename: entry.name,
        path: entry.path,
        model_path: entry.path,
        size: entry.size,
        format: entry.extension?.replace('.', '') || 'gguf',
      })
      setImportResults(prev => [
        { path: entry.path, name: entry.name, ok: true },
        ...prev.slice(0, 9),
      ])
    } catch (e) {
      setImportResults(prev => [
        { path: entry.path, name: entry.name, ok: false, error: e.message },
        ...prev.slice(0, 9),
      ])
    }
    setImportingModel(null)
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) { setSearchResults(null); return }
    const results = await api.kbSearch?.(searchQuery).catch(() => [])
    setSearchResults(results)
  }

  const pathParts = currentPath.replace(/\/$/, '').split('/').filter(Boolean)
  const filteredEntries = entries.filter(e => {
    if (showOnlyModels && !e.is_dir && !MODEL_EXTS.includes(e.extension)) return false
    if (filterExt && e.extension !== filterExt) return false
    return true
  })

  // ══════════════════════════════════════
  //  RENDER
  // ══════════════════════════════════════
  const TABS = [
    { id: 'files', icon: '🗂️', label: 'Importieren' },
    { id: 'modules', icon: '📦', label: 'Module' },
    { id: 'errors', icon: '🐛', label: 'Fehler' },
    { id: 'report', icon: '📋', label: 'Report' },
  ]

  return (
    <div style={sx.container}>
      {/* Tab Bar */}
      <div style={sx.tabBar}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => { setTab(t.id); setSearchResults(null) }} style={{
            ...sx.tabBtn, ...(tab === t.id ? sx.tabActive : {})
          }}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* ── FILE BROWSER TAB ── */}
      {tab === 'files' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Toolbar */}
          <div style={sx.fbToolbar}>
            <button style={sx.fbBtn} onClick={goBack} disabled={historyIndex <= 0} title="Zurück">◀</button>
            <button style={sx.fbBtn} onClick={goForward} disabled={historyIndex >= pathHistory.length - 1} title="Vor">▶</button>
            <button style={sx.fbBtn} onClick={goUp} disabled={currentPath === '/'} title="Übergeordnet">▲</button>
            <button style={sx.fbBtn} onClick={() => browsePath(currentPath)} title="Aktualisieren">↻</button>

            {/* Breadcrumb */}
            <div style={sx.breadcrumb}>
              <span style={sx.breadcrumbItem} onClick={() => browsePath('/')}>🖥️ /</span>
              {pathParts.map((part, i) => {
                const path = '/' + pathParts.slice(0, i + 1).join('/')
                return (
                  <React.Fragment key={i}>
                    <span style={{ color: '#3a4a5a' }}>/</span>
                    <span style={sx.breadcrumbItem} onClick={() => browsePath(path)}>{part}</span>
                  </React.Fragment>
                )
              })}
            </div>

            {/* Filter */}
            <button
              style={{ ...sx.fbBtn, ...(showOnlyModels ? { color: '#00ffc8', borderColor: 'rgba(0,255,200,0.3)', background: 'rgba(0,255,200,0.08)' } : {}) }}
              onClick={() => setShowOnlyModels(v => !v)} title="Nur KI-Modelle anzeigen"
            >🧠</button>
            <button style={sx.fbBtn} onClick={() => setShowSidebar(v => !v)} title="Seitenleiste">
              {showSidebar ? '⊟' : '⊞'}
            </button>
          </div>

          <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
            {/* Sidebar: Mountpoints / Schnellzugriff */}
            {showSidebar && (
              <div style={sx.sidebar}>
                <div style={sx.sidebarSection}>Schnellzugriff</div>
                {[
                  { label: '🏠 Home', path: '/home/worker' },
                  { label: '💿 Root', path: '/' },
                  { label: '📁 /media', path: '/media' },
                  { label: '📁 /mnt', path: '/mnt' },
                  { label: '📁 /tmp', path: '/tmp' },
                  { label: '📁 /opt', path: '/opt' },
                  { label: '📁 /data', path: '/data' },
                ].map((item) => (
                  <div key={item.path} style={sx.sidebarItem} onClick={() => browsePath(item.path)}>
                    {item.label}
                  </div>
                ))}

                {mounts.length > 0 && (
                  <>
                    <div style={{ ...sx.sidebarSection, marginTop: 8 }}>Laufwerke & Medien</div>
                    {mounts.map((m, i) => (
                      <div key={i} style={sx.sidebarItem} onClick={() => browsePath(m.mountpoint)}>
                        <span style={{ marginRight: 4 }}>{m.icon || '💾'}</span>
                        <div>
                          <div style={{ fontSize: 11, color: '#c0d0e0' }}>{m.label || m.name}</div>
                          {m.size && <div style={{ fontSize: 9, color: '#556677' }}>{m.size} · {m.fstype || m.type}</div>}
                        </div>
                      </div>
                    ))}
                  </>
                )}

                {importResults.length > 0 && (
                  <>
                    <div style={{ ...sx.sidebarSection, marginTop: 8 }}>Letzte Imports</div>
                    {importResults.map((r, i) => (
                      <div key={i} style={{ fontSize: 10, padding: '2px 8px', color: r.ok ? '#00ff88' : '#ff4444' }}>
                        {r.ok ? '✅' : '❌'} {r.name.substring(0, 18)}{r.name.length > 18 ? '…' : ''}
                      </div>
                    ))}
                  </>
                )}
              </div>
            )}

            {/* File List */}
            <div style={sx.fileList}>
              {fbLoading && (
                <div style={sx.loadingOverlay}>⏳ Lade…</div>
              )}
              {fbError && (
                <div style={{ color: '#ff4444', padding: '16px', fontSize: 12 }}>❌ {fbError}</div>
              )}

              {!fbLoading && !fbError && filteredEntries.length === 0 && (
                <div style={{ color: '#556677', padding: '24px', textAlign: 'center', fontSize: 13 }}>
                  Leeres Verzeichnis{showOnlyModels ? ' (keine KI-Modelle)' : ''}
                </div>
              )}

              {!fbLoading && filteredEntries.map((entry, i) => {
                const ext = entry.extension || ''
                const isModel = MODEL_EXTS.includes(ext)
                const icon = entry.is_dir
                  ? (entry.error ? '🔒' : '📁')
                  : (FORMAT_ICONS[ext] || '📄')
                const isSelected = selected.has(entry.path)

                return (
                  <div key={i} style={{
                    ...sx.fileRow,
                    background: isSelected ? 'rgba(0,255,200,0.06)' : undefined,
                    borderLeft: isModel ? '2px solid rgba(0,255,200,0.3)' : '2px solid transparent',
                  }}
                    onClick={() => handleEntryClick(entry)}
                    onContextMenu={(e) => { e.preventDefault(); handleEntrySelect(e, entry.path) }}
                  >
                    <span style={{ fontSize: 16, flexShrink: 0, width: 22 }}>{icon}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: 12, fontWeight: entry.is_dir ? 600 : 400,
                        color: entry.error ? '#556677' : entry.is_dir ? '#a8c8e8' : '#c8d8e8',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>{entry.name}</div>
                      {entry.error ? (
                        <div style={{ fontSize: 9, color: '#556677' }}>Kein Zugriff</div>
                      ) : !entry.is_dir && (
                        <div style={{ fontSize: 9, color: '#556677' }}>
                          {formatSize(entry.size)}
                          {ext && <span style={{ color: isModel ? '#00ffc8' : '#667788', marginLeft: 4 }}>{ext}</span>}
                        </div>
                      )}
                    </div>

                    {/* Import-Button für KI-Modelle */}
                    {isModel && !entry.error && (
                      <button
                        style={{
                          padding: '3px 8px', borderRadius: 5, fontSize: 10,
                          border: '1px solid rgba(0,255,200,0.3)', background: 'rgba(0,255,200,0.08)',
                          color: '#00ffc8', cursor: 'pointer', whiteSpace: 'nowrap',
                          opacity: importingModel === entry.path ? 0.6 : 1,
                        }}
                        onClick={(e) => { e.stopPropagation(); handleImportModel(entry) }}
                        disabled={importingModel === entry.path}
                        title={`"${entry.name}" als LLM-Modell importieren`}
                      >
                        {importingModel === entry.path ? '⏳' : '📥 Importieren'}
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* Status Bar */}
          <div style={sx.statusBar}>
            <span>{filteredEntries.filter(e => !e.is_dir).length} Dateien, {filteredEntries.filter(e => e.is_dir).length} Ordner</span>
            <span style={{ color: '#3a4a5a' }}>·</span>
            <span style={{ color: '#00ffc8' }}>
              {filteredEntries.filter(e => MODEL_EXTS.includes(e.extension)).length} KI-Modelle
            </span>
            {selected.size > 0 && (
              <>
                <span style={{ color: '#3a4a5a' }}>·</span>
                <span>{selected.size} ausgewählt</span>
              </>
            )}
            <span style={{ marginLeft: 'auto', fontFamily: 'monospace', fontSize: 10, color: '#3a4a5a' }}>
              {currentPath}
            </span>
          </div>
        </div>
      )}

      {/* ── MODULES TAB ── */}
      {tab === 'modules' && (
        <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              placeholder="Module durchsuchen…" style={sx.searchInput} />
            <button onClick={handleSearch} style={sx.searchBtn}>🔍</button>
          </div>
          {(searchResults || modules).map((m, i) => <ModuleRow key={i} module={m} />)}
          {modules.length === 0 && !searchResults && (
            <div style={{ color: '#556677', padding: 16 }}>Lade Module…</div>
          )}
        </div>
      )}

      {/* ── ERRORS TAB ── */}
      {tab === 'errors' && (
        <div style={{ flex: 1, overflow: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {errors.map((err, i) => (
            <div key={i} style={{
              padding: '10px 14px', background: 'var(--bg-surface)',
              border: '1px solid var(--border)', borderRadius: 6,
              borderLeft: `3px solid ${
                err.severity === 'critical' ? '#ff4444' :
                err.severity === 'high' ? '#ffaa00' : '#5588aa'
              }`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <strong style={{ fontSize: 13, color: '#e0e0e0' }}>{err.title}</strong>
                <span style={{
                  fontSize: 10, padding: '2px 6px', borderRadius: 10,
                  background: err.severity === 'critical' ? 'rgba(255,68,68,0.1)' :
                               err.severity === 'high' ? 'rgba(255,170,0,0.1)' : 'rgba(85,136,170,0.1)',
                  color: err.severity === 'critical' ? '#ff4444' :
                         err.severity === 'high' ? '#ffaa00' : '#5588aa',
                }}>{err.severity}</span>
              </div>
              {err.description && <div style={{ fontSize: 11, color: '#6688aa', marginTop: 4 }}>{err.description}</div>}
              {err.error_regex && (
                <div style={{ fontSize: 10, padding: '3px 7px', background: 'rgba(0,0,0,0.2)', borderRadius: 4, color: '#00ffc8', marginTop: 6, fontFamily: 'monospace' }}>
                  {err.error_regex}
                </div>
              )}
              {err.solution_short && (
                <div style={{ fontSize: 11, marginTop: 6, color: '#00cc88' }}>💡 {err.solution_short}</div>
              )}
            </div>
          ))}
          {errors.length === 0 && <div style={{ color: '#556677', padding: 16 }}>Lade Fehler-Patterns…</div>}
        </div>
      )}

      {/* ── REPORT TAB ── */}
      {tab === 'report' && <SystemReport />}
    </div>
  )
}

function ModuleRow({ module }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div style={{
      padding: '8px 10px', borderBottom: '1px solid rgba(255,255,255,0.04)',
      cursor: 'pointer', fontSize: 12,
    }} onClick={() => setExpanded(!expanded)}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{
            width: 7, height: 7, borderRadius: '50%', display: 'inline-block', flexShrink: 0,
            background: module.status === 'active' ? '#00cc88' :
                        module.status === 'deprecated' ? '#ffaa00' : '#556677',
          }} />
          <span style={{ fontFamily: 'monospace', color: '#00ffc8', fontSize: 11 }}>
            {module.file_path}
          </span>
        </div>
        <span style={{ fontSize: 10, color: '#556677' }}>{module.category} · {module.language}</span>
      </div>
      {expanded && (
        <div style={{ marginTop: 6, paddingLeft: 16, fontSize: 11, color: '#6688aa' }}>
          {module.description}
          {module.provides && (
            <div style={{ marginTop: 4, color: '#8899aa' }}>
              <strong>Provides:</strong> {Array.isArray(module.provides) ? module.provides.join(', ') : module.provides}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function SystemReport() {
  const [report, setReport] = useState(null)
  useEffect(() => { api.systemHealth?.().then(setReport).catch(console.error) }, [])
  if (!report) return <div style={{ color: '#556677', padding: 16 }}>Lade System-Report…</div>
  if (!report) return <div style={{ color: '#556677', padding: 16 }}>Lade System-Report…</div>
  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 12, fontFamily: 'monospace', fontSize: 11, color: '#8899aa', whiteSpace: 'pre-wrap' }}>
      {JSON.stringify(report, null, 2)}
    </div>
  )
}

/* ═══════════════════════════════════════
   STYLES
   ═══════════════════════════════════════ */
const sx = {
  container: {
    display: 'flex', flexDirection: 'column', height: '100%',
    background: 'var(--bg-primary)', color: 'var(--text-primary)',
    fontFamily: "'Inter', -apple-system, sans-serif", overflow: 'hidden',
  },
  tabBar: {
    display: 'flex', gap: 2, padding: '6px 10px',
    borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)',
    flexShrink: 0,
  },
  tabBtn: {
    padding: '5px 12px', border: '1px solid transparent', borderRadius: 6,
    background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer',
    fontSize: 12, whiteSpace: 'nowrap', transition: 'all 0.15s',
  },
  tabActive: {
    background: 'rgba(0,255,204,0.08)', color: '#00ffcc',
    border: '1px solid rgba(0,255,204,0.2)',
  },

  // File Browser
  fbToolbar: {
    display: 'flex', alignItems: 'center', gap: 3, padding: '5px 8px',
    background: '#0c0c16', borderBottom: '1px solid #1a1a2e', flexShrink: 0,
  },
  fbBtn: {
    width: 24, height: 24, border: '1px solid #2a2a40', borderRadius: 5,
    background: 'transparent', color: '#6688aa', cursor: 'pointer',
    fontSize: 11, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  breadcrumb: {
    display: 'flex', alignItems: 'center', gap: 2, flex: 1,
    fontSize: 11, fontFamily: 'monospace', overflow: 'hidden',
    padding: '0 6px',
  },
  breadcrumbItem: {
    color: '#7799aa', cursor: 'pointer', padding: '0 2px',
    borderRadius: 3, whiteSpace: 'nowrap',
  },

  sidebar: {
    width: 180, flexShrink: 0, borderRight: '1px solid #1a1a2e',
    overflowY: 'auto', background: '#0a0a12',
    paddingBottom: 16,
  },
  sidebarSection: {
    fontSize: 9, fontWeight: 700, color: '#3a5a7a', padding: '8px 10px 3px',
    textTransform: 'uppercase', letterSpacing: '0.08em',
  },
  sidebarItem: {
    display: 'flex', alignItems: 'center', gap: 6, padding: '5px 10px',
    fontSize: 11, color: '#6688aa', cursor: 'pointer', transition: 'all 0.1s',
  },

  fileList: {
    flex: 1, overflowY: 'auto', position: 'relative',
  },
  loadingOverlay: {
    padding: 24, textAlign: 'center', color: '#6688aa', fontSize: 13,
  },
  fileRow: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '5px 10px',
    cursor: 'default', fontSize: 12, transition: 'background 0.1s',
    borderBottom: '1px solid rgba(255,255,255,0.02)',
  },

  statusBar: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '3px 10px',
    borderTop: '1px solid #1a1a2e', background: '#08080e',
    fontSize: 10, color: '#6688aa', flexShrink: 0,
  },

  // Module search
  searchInput: {
    flex: 1, padding: '7px 10px', background: 'var(--bg-surface)',
    border: '1px solid var(--border)', borderRadius: 6,
    color: 'var(--text-primary)', fontFamily: 'monospace', fontSize: 12, outline: 'none',
  },
  searchBtn: {
    padding: '7px 14px', background: 'var(--accent)', border: 'none',
    borderRadius: 6, color: 'var(--bg-primary)', cursor: 'pointer', fontWeight: 600,
  },
}
