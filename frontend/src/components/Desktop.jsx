import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import { api } from '../api'
import useKeyboardShortcuts from '../hooks/useKeyboardShortcuts'
import SpotlightSearch from './SpotlightSearch'
import Window from './Window'
import SystemMonitor from './apps/SystemMonitor'
import GhostChat from './apps/GhostChat'
import KnowledgeBase from './apps/KnowledgeBase'
import EventViewer from './apps/EventViewer'
import SQLConsole from './apps/SQLConsole'
import HealthDashboard from './apps/HealthDashboard'
import FileBrowser from './apps/FileBrowser'
import Settings from './apps/Settings'
import ErrorAnalyzer from './apps/ErrorAnalyzer'
import SoftwareStore from './apps/SoftwareStore'
import OpenClawIntegrator from './apps/OpenClawIntegrator'
import GhostLLMManager from './apps/LLMManager'
import SetupWizard from './apps/SetupWizard'
import AIWorkshop from './apps/AIWorkshop'
import SQLExplorer from './apps/SQLExplorer'
import WebFrame from './apps/WebFrame'
import NodeManager from './apps/NodeManager'
import NetworkScanner from './apps/NetworkScanner'
import Terminal from './apps/Terminal'
import BrowserMigration from './apps/BrowserMigration'
import ConfigImporter from './apps/ConfigImporter'
import WorkspaceMapper from './apps/WorkspaceMapper'
import SynapticViewer from './apps/SynapticViewer'
import RAGManager from './apps/RAGManager'
import USBInstaller from './apps/USBInstaller'
import WLANHotspot from './apps/WLANHotspot'
import ImmutableFS from './apps/ImmutableFS'
import AnomalyDetector from './apps/AnomalyDetector'
import AppSandbox from './apps/AppSandbox'
import FirewallManager from './apps/FirewallManager'
import GhostUpdater from './apps/GhostUpdater'
import GhostMail from './apps/GhostMail'
import GhostBrowser from './apps/GhostBrowser'
import RemoteAccess from './apps/RemoteAccess'

// App-Komponenten Registry
const APP_COMPONENTS = {
  SystemMonitor,
  GhostLLMManager,
  GhostChat,
  KnowledgeBase,
  EventViewer,
  SQLConsole,
  HealthDashboard,
  FileBrowser,
  Settings,
  ErrorAnalyzer,
  SoftwareStore,
  OpenClawIntegrator,
  SetupWizard,
  AIWorkshop,
  SQLExplorer,
  WebFrame,
  NodeManager,
  NetworkScanner,
  Terminal,
  BrowserMigration,
  ConfigImporter,
  WorkspaceMapper,
  SynapticViewer,
  RAGManager,
  USBInstaller,
  WLANHotspot,
  ImmutableFS,
  AnomalyDetector,
  AppSandbox,
  FirewallManager,
  GhostUpdater,
  GhostMail,
  GhostBrowser,
  RemoteAccess,
}

// Icon-Mapping für Netzwerkknoten
const NODE_ICON_MAP = {
  circle: '⭕', play: '▶️', search: '🔍', nas: '💾', phone: '📱',
  server: '🖥️', cloud: '☁️', printer: '🖨️', camera: '📷', iot: '📡',
  chat: '💬', message: '✉️',
}

// Icons pro Seite (Cube-Grid ~16 Spalten x 9 Reihen bei 80px)
const ICONS_PER_PAGE = 120

/**
 * Desktop — Icon-Desktop mit Drag & Drop, Ordnern, Seiten und Aktualisieren-Button
 */
export default function Desktop({ user, desktopState, tabInfo, onLogout }) {
  const [windows, setWindows] = useState([])
  const [apps, setApps] = useState(desktopState?.apps || [])
  const [theme] = useState(desktopState?.theme || {})
  const [nextZ, setNextZ] = useState(10)
  const desktopRef = useRef(null)
  const [clock, setClock] = useState(new Date())
  const [refreshing, setRefreshing] = useState(false)
  const [nodes, setNodes] = useState([])
  const [resetConfirm, setResetConfirm] = useState(null) // node zum Zurücksetzen
  const longPressRef = useRef(null)
  const [showSpotlight, setShowSpotlight] = useState(false)

  // Keyboard Shortcuts
  useKeyboardShortcuts({
    'open-terminal': () => openApp('terminal'),
    'open-file-browser': () => openApp('file-browser'),
    'open-ghost-chat': () => openApp('ghost-chat'),
    'open-spotlight': () => setShowSpotlight(true),
    'open-settings': () => openApp('settings'),
    'open-system-monitor': () => openApp('system-monitor'),
    'open-llm-manager': () => openApp('llm-manager'),
    'close-spotlight': () => setShowSpotlight(false),
    'close-window': () => {
      const focused = windows.find(w => w.focused)
      if (focused) setWindows(prev => prev.filter(w => w.id !== focused.id))
    },
  })

  // Active ghosts for taskbar
  const [activeGhosts, setActiveGhosts] = useState(desktopState?.ghosts || [])

  // ── Live System-Metriken ──
  const [metrics, setMetrics] = useState({ cpu: 0, ram: 0, gpu: 0, gpu_temp: 0 })
  const metricsHistory = useRef({ cpu: [], ram: [], gpu: [] })
  const HISTORY_LEN = 20

  useEffect(() => {
    let mounted = true
    const poll = () => {
      api.systemMetrics().then(d => {
        if (!mounted) return
        const cpu = d.cpu_percent ?? d.cpu ?? 0
        const ram = d.memory_percent ?? d.ram ?? 0
        const gpu = d.gpu_percent ?? d.gpu_utilization ?? d.gpu ?? 0
        const gpu_temp = d.gpu_temp ?? d.gpu_temperature ?? 0
        setMetrics({ cpu, ram, gpu, gpu_temp })
        const h = metricsHistory.current
        h.cpu = [...h.cpu.slice(-(HISTORY_LEN - 1)), cpu]
        h.ram = [...h.ram.slice(-(HISTORY_LEN - 1)), ram]
        h.gpu = [...h.gpu.slice(-(HISTORY_LEN - 1)), gpu]
      }).catch(() => {})
    }
    poll()
    const interval = setInterval(poll, 3000)
    return () => { mounted = false; clearInterval(interval) }
  }, [])

  // ── Desktop-Seiten (Pagination) ──
  const [currentPage, setCurrentPage] = useState(0)

  // ── Ordner-System — Tab-isoliert ──
  // Im DB-Mode kommen Ordner aus desktopState.tab, Fallback: sessionStorage
  const [folders, setFolders] = useState(() => {
    const tabFolders = desktopState?.tab?.folders
    if (tabFolders && typeof tabFolders === 'object' && Object.keys(tabFolders).length > 0) return tabFolders
    try { return JSON.parse(sessionStorage.getItem('dbai_folders') || '{}') } catch { return {} }
  })
  const [openFolder, setOpenFolder] = useState(null) // welcher Ordner ist offen

  // ── Icon-Reihenfolge — Tab-isoliert ──
  const [iconOrder, setIconOrder] = useState(() => {
    const tabOrder = desktopState?.tab?.icon_order
    if (Array.isArray(tabOrder) && tabOrder.length > 0) return tabOrder
    try { return JSON.parse(sessionStorage.getItem('dbai_icon_order') || 'null') } catch { return null }
  })

  // ── Drag & Drop ──
  const [dragItem, setDragItem] = useState(null)      // { type: 'app'|'folder', id }
  const [dragOverItem, setDragOverItem] = useState(null)
  const [dropIndicator, setDropIndicator] = useState(null) // index wo eingefügt wird

  // Persistenz — Tab-isoliert (sessionStorage + DB-Sync)
  const syncTimerRef = useRef(null)
  useEffect(() => {
    sessionStorage.setItem('dbai_folders', JSON.stringify(folders))
    // DB-Sync (debounced)
    clearTimeout(syncTimerRef.current)
    syncTimerRef.current = setTimeout(() => {
      const tabId = api.getTabId?.()
      if (tabId) api.tabUpdate?.(tabId, { folders }).catch(() => {})
    }, 2000)
  }, [folders])
  useEffect(() => {
    if (iconOrder) {
      sessionStorage.setItem('dbai_icon_order', JSON.stringify(iconOrder))
      clearTimeout(syncTimerRef.current)
      syncTimerRef.current = setTimeout(() => {
        const tabId = api.getTabId?.()
        if (tabId) api.tabUpdate?.(tabId, { icon_order: iconOrder }).catch(() => {})
      }, 2000)
    }
  }, [iconOrder])

  // Icon-Order initialisieren / synchronisieren wenn Apps + Knoten sich ändern
  useEffect(() => {
    const appsInFolders = new Set(Object.values(folders).flatMap(f => f.items))
    const freeApps = apps.filter(a => !appsInFolders.has(a.app_id)).map(a => a.app_id)
    const folderIds = Object.keys(folders).map(id => `folder:${id}`)
    const nodeIds = nodes.map(n => `node:${n.node_key}`)

    if (!iconOrder) {
      setIconOrder([...freeApps, ...folderIds, ...nodeIds])
    } else {
      // Neue Apps/Knoten hinzufügen, entfernte entfernen
      const currentIds = new Set(iconOrder)
      const validApps = new Set(freeApps)
      const validFolders = new Set(folderIds)
      const validNodes = new Set(nodeIds)
      const allValid = new Set([...validApps, ...validFolders, ...validNodes])

      let updated = iconOrder.filter(id => allValid.has(id))
      // Neue hinzufügen
      for (const id of freeApps) {
        if (!currentIds.has(id)) updated.push(id)
      }
      for (const id of folderIds) {
        if (!currentIds.has(id)) updated.push(id)
      }
      for (const id of nodeIds) {
        if (!currentIds.has(id)) updated.push(id)
      }
      if (updated.length !== iconOrder.length || updated.some((v, i) => v !== iconOrder[i])) {
        setIconOrder(updated)
      }
    }
  }, [apps, folders, nodes])

  // Berechnete Icon-Liste für aktuelle Seite
  const displayItems = useMemo(() => {
    if (!iconOrder) return []
    return iconOrder.map(id => {
      if (id.startsWith('folder:')) {
        const fid = id.replace('folder:', '')
        const folder = folders[fid]
        if (!folder) return null
        return { type: 'folder', id: fid, name: folder.name, icon: folder.icon || '📁', items: folder.items }
      }
      if (id.startsWith('node:')) {
        const nkey = id.replace('node:', '')
        const node = nodes.find(n => n.node_key === nkey)
        if (!node) return null
        return { type: 'node', id: node.node_key, name: node.label, icon: NODE_ICON_MAP[node.icon_type] || '⭕', node }
      }
      const app = apps.find(a => a.app_id === id)
      if (!app) return null
      return { type: 'app', id: app.app_id, name: app.name, icon: app.icon, app }
    }).filter(Boolean)
  }, [iconOrder, folders, apps, nodes])

  const totalPages = Math.max(1, Math.ceil(displayItems.length / ICONS_PER_PAGE))
  const pageItems = displayItems.slice(currentPage * ICONS_PER_PAGE, (currentPage + 1) * ICONS_PER_PAGE)

  // ── Aktualisieren-Funktion ──
  const refreshDesktop = useCallback(() => {
    setRefreshing(true)
    Promise.all([
      api.desktop().then(data => { if (data.apps) setApps(data.apps) }),
      api.desktopNodes().then(data => { if (data.nodes) setNodes(data.nodes) })
    ]).catch(() => {}).finally(() => {
      setTimeout(() => setRefreshing(false), 400)
    })
  }, [])

  // ── Netzwerkknoten initial laden ──
  useEffect(() => {
    api.desktopNodes().then(data => setNodes(data.nodes || [])).catch(() => {})
  }, [])

  // Uhr
  useEffect(() => {
    const timer = setInterval(() => setClock(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  // Ghost-Swap Events
  useEffect(() => {
    const handler = () => {
      api.ghosts().then(data => setActiveGhosts(data.active_ghosts || []))
        .catch(() => {})
    }
    window.addEventListener('dbai:ghost_swap', handler)
    return () => window.removeEventListener('dbai:ghost_swap', handler)
  }, [])

  // Apply theme CSS variables
  useEffect(() => {
    if (theme.colors) {
      const root = document.documentElement
      Object.entries(theme.colors).forEach(([key, value]) => {
        root.style.setProperty(`--${key.replace(/_/g, '-')}`, value)
      })
    }
  }, [theme])

  // ── Window Management ──
  const openApp = useCallback((appId, extra) => {
    if (!extra) {
      const existing = windows.find(w => w.appId === appId)
      if (existing) {
        focusWindow(existing.id)
        return
      }
    }

    const app = apps.find(a => a.app_id === appId)
    const appInfo = app || { app_id: appId, name: extra?.title || appId, icon: '🌐', source_type: 'component', source_target: extra?.component || appId }

    // WebFrame-Apps: URL automatisch aus Beschreibung oder fester Map laden
    const WEBFRAME_URLS = {
      'vscode': 'http://localhost:8443',
      'n8n': 'http://localhost:5678',
    }
    let resolvedExtra = extra || null
    if (appInfo.source_target === 'WebFrame' && !extra?.url && WEBFRAME_URLS[appId]) {
      resolvedExtra = { url: WEBFRAME_URLS[appId], title: appInfo.name, ...(extra || {}) }
    }

    const z = nextZ + 1
    setNextZ(z)

    const newWindow = {
      id: `win-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      appId: appInfo.app_id,
      appName: extra?.title || appInfo.name,
      appIcon: appInfo.icon,
      sourceType: appInfo.source_type,
      sourceTarget: appInfo.source_target || '',
      component: extra?.component || appInfo.source_target || '',
      x: 80 + (windows.length % 5) * 40,
      y: 60 + (windows.length % 5) * 40,
      width: appInfo.default_width || 800,
      height: appInfo.default_height || 600,
      state: 'normal',
      focused: true,
      extra: resolvedExtra,
      z,
    }

    setWindows(prev => prev.map(w => ({ ...w, focused: false })).concat(newWindow))
  }, [windows, apps, nextZ])

  const closeWindow = useCallback((windowId) => {
    setWindows(prev => prev.filter(w => w.id !== windowId))
  }, [])

  const focusWindow = useCallback((windowId) => {
    const z = nextZ + 1
    setNextZ(z)
    setWindows(prev => prev.map(w =>
      w.id === windowId
        ? { ...w, focused: true, z, state: w.state === 'minimized' ? 'normal' : w.state }
        : { ...w, focused: false }
    ))
  }, [nextZ])

  const minimizeWindow = useCallback((windowId) => {
    setWindows(prev => prev.map(w =>
      w.id === windowId ? { ...w, state: 'minimized', focused: false } : w
    ))
  }, [])

  const maximizeWindow = useCallback((windowId) => {
    setWindows(prev => prev.map(w =>
      w.id === windowId
        ? { ...w, state: w.state === 'maximized' ? 'normal' : 'maximized' }
        : w
    ))
  }, [])

  const updateWindowPosition = useCallback((windowId, x, y) => {
    setWindows(prev => prev.map(w =>
      w.id === windowId ? { ...w, x, y } : w
    ))
  }, [])

  const updateWindowSize = useCallback((windowId, width, height) => {
    setWindows(prev => prev.map(w =>
      w.id === windowId ? { ...w, width, height } : w
    ))
  }, [])

  // ── Hilfsfunktion: orderId für Icon-Order ──
  const getOrderId = (item) => item.type === 'folder' ? `folder:${item.id}` : item.type === 'node' ? `node:${item.id}` : item.id

  // ── Drag & Drop Handlers ──
  const handleDragStart = useCallback((e, item) => {
    const orderId = getOrderId(item)
    setDragItem({ type: item.type, id: item.id, orderId })
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', orderId)
  }, [])

  const handleDragOver = useCallback((e, item, index) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    const orderId = getOrderId(item)
    setDragOverItem(orderId)
    setDropIndicator(currentPage * ICONS_PER_PAGE + index)
  }, [currentPage])

  const handleDragLeave = useCallback(() => {
    setDragOverItem(null)
    setDropIndicator(null)
  }, [])

  const handleDrop = useCallback((e, targetItem) => {
    e.preventDefault()
    if (!dragItem) return

    const targetOrderId = getOrderId(targetItem)

    // Nicht auf sich selbst
    if (dragItem.orderId === targetOrderId) {
      setDragItem(null)
      setDragOverItem(null)
      setDropIndicator(null)
      return
    }

    // Fall 1: App auf App → Ordner erstellen
    if (dragItem.type === 'app' && targetItem.type === 'app') {
      const folderId = `f${Date.now()}`
      const folderName = 'Neuer Ordner'
      setFolders(prev => ({
        ...prev,
        [folderId]: { name: folderName, icon: '📁', items: [targetItem.id, dragItem.id] }
      }))
      setIconOrder(prev => {
        let updated = prev.filter(id => id !== dragItem.orderId && id !== targetOrderId)
        const targetIdx = prev.indexOf(targetOrderId)
        const insertAt = updated.length >= targetIdx ? targetIdx : updated.length
        updated.splice(insertAt, 0, `folder:${folderId}`)
        return updated
      })
    }
    // Fall 2: App auf Ordner → App in den Ordner
    else if (dragItem.type === 'app' && targetItem.type === 'folder') {
      setFolders(prev => ({
        ...prev,
        [targetItem.id]: { ...prev[targetItem.id], items: [...(prev[targetItem.id]?.items || []), dragItem.id] }
      }))
      setIconOrder(prev => prev.filter(id => id !== dragItem.orderId))
    }
    // Fall 3: Ordner/App verschieben (Reihenfolge)
    else {
      setIconOrder(prev => {
        const updated = prev.filter(id => id !== dragItem.orderId)
        const targetIdx = updated.indexOf(targetOrderId)
        if (targetIdx >= 0) {
          updated.splice(targetIdx, 0, dragItem.orderId)
        } else {
          updated.push(dragItem.orderId)
        }
        return updated
      })
    }

    setDragItem(null)
    setDragOverItem(null)
    setDropIndicator(null)
  }, [dragItem])

  const handleDragEnd = useCallback(() => {
    setDragItem(null)
    setDragOverItem(null)
    setDropIndicator(null)
  }, [])

  // ── Ordner öffnen / schließen ──
  const handleFolderOpen = useCallback((folderId) => {
    setOpenFolder(folderId)
  }, [])

  const handleFolderClose = useCallback(() => {
    setOpenFolder(null)
  }, [])

  // App aus Ordner entfernen (zurück auf Desktop)
  const handleRemoveFromFolder = useCallback((folderId, appId) => {
    setFolders(prev => {
      const folder = prev[folderId]
      if (!folder) return prev
      const newItems = folder.items.filter(id => id !== appId)
      if (newItems.length === 0) {
        // Leerer Ordner → entfernen
        const { [folderId]: _, ...rest } = prev
        setIconOrder(o => o.filter(id => id !== `folder:${folderId}`).concat(appId))
        return rest
      }
      return { ...prev, [folderId]: { ...folder, items: newItems } }
    })
    if (!iconOrder.includes(appId)) {
      setIconOrder(prev => [...prev, appId])
    }
  }, [iconOrder])

  // Ordner umbenennen
  const handleRenameFolder = useCallback((folderId, newName) => {
    setFolders(prev => ({
      ...prev,
      [folderId]: { ...prev[folderId], name: newName }
    }))
  }, [])

  // ── Long-Press (3s) zum Zurücksetzen von Netzwerkknoten ──
  const handleLongPressStart = useCallback((item) => {
    if (item.type !== 'node' || !item.node) return
    longPressRef.current = setTimeout(() => {
      setResetConfirm(item.node)
    }, 3000)
  }, [])

  const handleLongPressEnd = useCallback(() => {
    if (longPressRef.current) {
      clearTimeout(longPressRef.current)
      longPressRef.current = null
    }
  }, [])

  const handleResetNode = useCallback(async (node) => {
    try {
      await api.desktopNodeDelete(node.id)
      setResetConfirm(null)
      refreshDesktop()
    } catch (e) {
      console.error('Knoten-Reset fehlgeschlagen:', e)
    }
  }, [refreshDesktop])

  return (
    <div className="desktop">
      <div className="desktop-area" ref={desktopRef}>
        {/* Desktop Icons */}
        <div className="desktop-icons">
          {pageItems.map((item, index) => {
            const orderId = getOrderId(item)
            const isDragOver = dragOverItem === orderId
            const isNode = item.type === 'node'
            return (
              <div
                key={orderId}
                className={`desktop-icon${isDragOver ? ' drag-over' : ''}${dragItem?.orderId === orderId ? ' dragging' : ''}${isNode ? ' node-icon' : ''}`}
                draggable
                onDragStart={(e) => handleDragStart(e, item)}
                onDragOver={(e) => handleDragOver(e, item, index)}
                onDragLeave={handleDragLeave}
                onDrop={(e) => handleDrop(e, item)}
                onDragEnd={handleDragEnd}
                onMouseDown={() => handleLongPressStart(item)}
                onMouseUp={handleLongPressEnd}
                onMouseLeave={handleLongPressEnd}
                onTouchStart={() => handleLongPressStart(item)}
                onTouchEnd={handleLongPressEnd}
                onDoubleClick={() => {
                  if (item.type === 'folder') {
                    handleFolderOpen(item.id)
                  } else if (item.type === 'node' && item.node) {
                    if (item.node.url) {
                      openApp(item.node.app_id || 'web-frame', {
                        component: 'WebFrame',
                        title: item.node.label,
                        url: item.node.url,
                      })
                    } else if (item.node.app_id) {
                      openApp(item.node.app_id)
                    }
                  } else {
                    openApp(item.id)
                  }
                }}
              >
                <span className="icon" style={isNode ? {
                  background: `radial-gradient(circle, ${item.node?.color || '#00f5ff'}44, transparent)`,
                  borderRadius: '50%',
                  textShadow: `0 0 10px ${item.node?.color || '#00f5ff'}`,
                  boxShadow: `0 0 12px ${item.node?.color || '#00f5ff'}33`,
                } : undefined}>
                  {item.icon}
                  {item.type === 'folder' && item.items.length > 0 && (
                    <span className="folder-badge">{item.items.length}</span>
                  )}
                </span>
                <span className="label">{item.name}</span>
              </div>
            )
          })}
        </div>

        {/* Reset-Bestätigung für Netzwerkknoten */}
        {resetConfirm && (
          <div className="folder-overlay" onClick={() => setResetConfirm(null)}>
            <div className="node-reset-popup" onClick={e => e.stopPropagation()}>
              <div className="node-reset-header">
                <span style={{ fontSize: 28 }}>{NODE_ICON_MAP[resetConfirm.icon_type] || '⭕'}</span>
                <span style={{ fontWeight: 700, fontSize: 16 }}>{resetConfirm.label}</span>
              </div>
              <p style={{ color: '#b0b8c0', fontSize: 13, margin: '8px 0 16px', textAlign: 'center' }}>
                Diesen Netzwerkknoten zurücksetzen?<br/>
                <span style={{ fontSize: 11, color: '#6688aa' }}>Der Knoten wird entfernt und kann über die Schnellvorlagen neu erstellt werden.</span>
              </p>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
                <button className="node-reset-btn cancel" onClick={() => setResetConfirm(null)}>Abbrechen</button>
                <button className="node-reset-btn confirm" onClick={() => handleResetNode(resetConfirm)}>🔄 Zurücksetzen</button>
              </div>
            </div>
          </div>
        )}

        {/* Seiten-Navigation */}
        {totalPages > 1 && (
          <div className="desktop-pages">
            {Array.from({ length: totalPages }).map((_, i) => (
              <button
                key={i}
                className={`desktop-page-dot${i === currentPage ? ' active' : ''}`}
                onClick={() => setCurrentPage(i)}
                title={`Seite ${i + 1}`}
              />
            ))}
          </div>
        )}

        {/* Aktualisieren-Button */}
        <button
          className={`desktop-refresh-btn${refreshing ? ' spinning' : ''}`}
          onClick={refreshDesktop}
          title="Desktop aktualisieren"
        >
          🔄
        </button>

        {/* Ordner-Popup */}
        {openFolder && folders[openFolder] && (
          <div className="folder-overlay" onClick={handleFolderClose}>
            <div className="folder-popup" onClick={(e) => e.stopPropagation()}>
              <div className="folder-popup-header">
                <input
                  className="folder-name-input"
                  value={folders[openFolder].name}
                  onChange={(e) => handleRenameFolder(openFolder, e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && e.target.blur()}
                />
                <button className="folder-close-btn" onClick={handleFolderClose}>✕</button>
              </div>
              <div className="folder-popup-grid">
                {folders[openFolder].items.map(appId => {
                  const app = apps.find(a => a.app_id === appId)
                  if (!app) return null
                  return (
                    <div
                      key={appId}
                      className="desktop-icon"
                      onDoubleClick={() => { openApp(appId); handleFolderClose() }}
                    >
                      <span className="icon">{app.icon}</span>
                      <span className="label">{app.name}</span>
                      <button
                        className="folder-remove-btn"
                        onClick={(e) => { e.stopPropagation(); handleRemoveFromFolder(openFolder, appId) }}
                        title="Aus Ordner entfernen"
                      >✕</button>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )}

        {/* Windows */}
        {windows.filter(w => w.state !== 'minimized').map(win => (
          <Window
            key={win.id}
            window={win}
            onClose={() => closeWindow(win.id)}
            onFocus={() => focusWindow(win.id)}
            onMinimize={() => minimizeWindow(win.id)}
            onMaximize={() => maximizeWindow(win.id)}
            onMove={(x, y) => updateWindowPosition(win.id, x, y)}
            onResize={(w, h) => updateWindowSize(win.id, w, h)}
          >
            {renderAppContent(win, openApp, refreshDesktop)}
          </Window>
        ))}
      </div>

      {/* Taskbar */}
      <div className="taskbar">
        <div className="taskbar-start" onClick={() => openApp('ghost-chat')}>
          👻 {tabInfo?.hostname || 'DBAI'}
        </div>
        <div
          style={{ cursor: 'pointer', padding: '0 8px', fontSize: 16, opacity: 0.8, borderLeft: '1px solid rgba(255,255,255,0.1)', borderRight: '1px solid rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center' }}
          onClick={() => window.open(window.location.origin, '_blank')}
          title="Neuen Desktop-Tab öffnen"
        >
          ＋
        </div>
        <div style={{ cursor: 'pointer', padding: '0 8px', fontSize: 14, opacity: 0.7 }} onClick={() => setShowSpotlight(true)} title="App-Suche (Ctrl+K)">
          🔍
        </div>

        <div className="taskbar-apps">
          {windows.map(win => (
            <div
              key={win.id}
              className={`taskbar-app ${win.focused ? 'focused' : ''} ${win.state !== 'minimized' ? 'active' : ''}`}
              onClick={() => focusWindow(win.id)}
            >
              <span>{win.appIcon}</span>
              <span>{win.appName}</span>
            </div>
          ))}
        </div>

        <div className="taskbar-status">
          {/* Live-Stats Mini-Graphen */}
          <div className="taskbar-metrics" onClick={() => openApp('system-monitor')} title="System Monitor öffnen">
            <TaskbarMiniGraph label="CPU" value={metrics.cpu} history={metricsHistory.current.cpu} color="#00f5ff" />
            <TaskbarMiniGraph label="RAM" value={metrics.ram} history={metricsHistory.current.ram} color="#a855f7" />
            <TaskbarMiniGraph label="GPU" value={metrics.gpu} history={metricsHistory.current.gpu} color="#22c55e" suffix={metrics.gpu_temp > 0 ? `${Math.round(metrics.gpu_temp)}°` : null} />
          </div>

          {activeGhosts.length > 0 && (
            <div className="taskbar-ghost" onClick={() => openApp('ghost-manager')}>
              👻 {activeGhosts[0]?.model_display || 'No Ghost'}
            </div>
          )}
          <span style={{ cursor: 'pointer' }} onClick={onLogout} title="Abmelden">
            {user?.display_name || user?.username}
          </span>
          <span>
            {clock.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
          </span>
          <PowerMenu onLogout={onLogout} />
        </div>
      </div>

      {/* Spotlight Search */}
      {showSpotlight && (
        <SpotlightSearch
          apps={apps}
          onLaunch={(appId) => openApp(appId)}
          onClose={() => setShowSpotlight(false)}
        />
      )}
    </div>
  )
}

// ── Render App Content ──
function renderAppContent(win, openApp, refreshDesktop) {
  const Component = APP_COMPONENTS[win.component]
  if (Component) {
    // NodeManager bekommt onRefreshNodes, um den Desktop nach Änderungen zu aktualisieren
    const extraProps = win.component === 'NodeManager' ? { onRefreshNodes: refreshDesktop } : {}
    return <Component windowId={win.id} extra={win.extra} {...extraProps} onOpenWindow={(opts) => openApp(opts.app_id || opts.component, opts)} />
  }

  // SQL-View Apps
  if (win.sourceType === 'sql_view' && win.sourceTarget) {
    return <SQLViewApp viewName={win.sourceTarget} />
  }

  // Terminal
  if (win.sourceType === 'terminal') {
    return <SQLConsole windowId={win.id} />
  }

  return (
    <div className="p-4 text-muted">
      <p>App-Komponente "{win.component}" noch nicht implementiert.</p>
      <p className="text-xs mt-2">Source: {win.sourceType} / {win.sourceTarget}</p>
    </div>
  )
}

// Simple SQL View renderer
function SQLViewApp({ viewName }) {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.sqlQuery(`SELECT * FROM ${viewName} LIMIT 100`)
      .then(result => setData(result.rows || []))
      .catch(err => console.error(err))
      .finally(() => setLoading(false))
  }, [viewName])

  if (loading) return <div className="p-4 text-muted">Lade...</div>

  if (data.length === 0) return <div className="p-4 text-muted">Keine Daten</div>

  const columns = Object.keys(data[0])

  return (
    <div style={{ overflow: 'auto', fontSize: '12px' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col} style={{
                padding: '8px 12px', textAlign: 'left',
                borderBottom: '1px solid var(--border)',
                color: 'var(--accent)', fontFamily: 'var(--font-mono)',
                fontSize: '11px', textTransform: 'uppercase',
              }}>
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
              {columns.map(col => (
                <td key={col} style={{
                  padding: '6px 12px', fontFamily: 'var(--font-mono)',
                  fontSize: '11px', maxWidth: '300px', overflow: 'hidden',
                  textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {typeof row[col] === 'object' ? JSON.stringify(row[col]) : String(row[col] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Power Menu (Ausschalten / Neustart / Abmelden) ──
function PowerMenu({ onLogout }) {
  const [open, setOpen] = useState(false)
  const [confirm, setConfirm] = useState(null) // 'shutdown' | 'reboot'
  const [powerState, setPowerState] = useState(null) // 'shutting_down' | 'rebooting'
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) { setOpen(false); setConfirm(null) } }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const exec = async (action) => {
    try {
      if (action === 'logout') { onLogout(); return }
      setPowerState(action === 'shutdown' ? 'shutting_down' : 'rebooting')
      setOpen(false); setConfirm(null)
      if (action === 'shutdown') await api.powerShutdown()
      else if (action === 'reboot') await api.powerReboot()
      // Bei Reboot: nach 3s automatisch versuchen neu zu laden
      if (action === 'reboot') {
        setTimeout(() => {
          const tryReload = () => {
            fetch('/api/health').then(r => { if (r.ok) window.location.reload() }).catch(() => setTimeout(tryReload, 2000))
          }
          tryReload()
        }, 3000)
      }
    } catch (e) {
      console.error('Power action failed:', e)
      setPowerState(null)
    }
  }

  // ── Fullscreen Overlay bei Shutdown/Reboot ──
  if (powerState) {
    const isShutdown = powerState === 'shutting_down'
    return (
      <div style={{
        position: 'fixed', inset: 0, zIndex: 999999,
        background: '#0a0e14',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        animation: 'fadeIn 0.5s ease',
      }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>{isShutdown ? '⏻' : '🔄'}</div>
        <div style={{ color: '#b0b8c0', fontSize: 18, fontWeight: 300, marginBottom: 8 }}>
          {isShutdown ? 'System wird ausgeschaltet…' : 'System wird neu gestartet…'}
        </div>
        <div style={{ color: '#606870', fontSize: 13 }}>
          {isShutdown ? 'Du kannst dieses Fenster schließen.' : 'Bitte warten — die Seite lädt automatisch neu.'}
        </div>
        {!isShutdown && (
          <div style={{ marginTop: 24 }}>
            <div style={{
              width: 32, height: 32, border: '3px solid #2a3a4a',
              borderTopColor: '#00ffcc', borderRadius: '50%',
              animation: 'spin 1s linear infinite',
            }} />
          </div>
        )}
        <style>{`
          @keyframes spin { to { transform: rotate(360deg) } }
          @keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }
        `}</style>
      </div>
    )
  }

  const PS = {
    btn: { background: 'none', border: 'none', color: '#e0e0e0', cursor: 'pointer', fontSize: 16, padding: '4px 8px', borderRadius: 4, display: 'flex', alignItems: 'center', gap: 4 },
    menu: { position: 'absolute', bottom: '100%', right: 0, marginBottom: 8, background: '#1a1a2e', border: '1px solid #2a3a4a', borderRadius: 8, padding: 6, minWidth: 180, zIndex: 99999, boxShadow: '0 -4px 20px rgba(0,0,0,0.6)' },
    item: { display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 6, cursor: 'pointer', fontSize: 13, color: '#d0d0d0', border: 'none', background: 'none', width: '100%', textAlign: 'left' },
    sep: { height: 1, background: '#2a3a4a', margin: '4px 0' },
    confirmBox: { padding: '10px 12px', textAlign: 'center' },
    confirmBtn: { padding: '6px 16px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600 },
  }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button onClick={() => { setOpen(!open); setConfirm(null) }} style={PS.btn} title="Ein/Aus">⏻</button>
      {open && (
        <div style={PS.menu}>
          {!confirm ? (<>
            <button style={PS.item} onMouseEnter={e => e.target.style.background='rgba(0,255,204,0.08)'} onMouseLeave={e => e.target.style.background='none'} onClick={() => exec('logout')}>🚪 Abmelden</button>
            <div style={PS.sep} />
            <button style={PS.item} onMouseEnter={e => e.target.style.background='rgba(255,170,0,0.08)'} onMouseLeave={e => e.target.style.background='none'} onClick={() => setConfirm('reboot')}>🔄 Neustart</button>
            <button style={PS.item} onMouseEnter={e => e.target.style.background='rgba(255,68,68,0.08)'} onMouseLeave={e => e.target.style.background='none'} onClick={() => setConfirm('shutdown')}>⏻ Ausschalten</button>
          </>) : (
            <div style={PS.confirmBox}>
              <div style={{ fontSize: 24, marginBottom: 6 }}>{confirm === 'shutdown' ? '⏻' : '🔄'}</div>
              <div style={{ fontSize: 13, color: '#b0b8c0', marginBottom: 10 }}>
                {confirm === 'shutdown' ? 'System wirklich ausschalten?' : 'System wirklich neustarten?'}
              </div>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
                <button style={{ ...PS.confirmBtn, background: '#2a3a4a', color: '#d0d0d0' }} onClick={() => setConfirm(null)}>Abbrechen</button>
                <button style={{ ...PS.confirmBtn, background: confirm === 'shutdown' ? '#dc2626' : '#f59e0b', color: '#fff' }} onClick={() => exec(confirm)}>
                  {confirm === 'shutdown' ? 'Ausschalten' : 'Neustarten'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Taskbar Mini-Graph (SVG Sparkline + Zahl) ──
function TaskbarMiniGraph({ label, value, history, color, suffix }) {
  const w = 48, h = 20
  const points = history.length > 1
    ? history.map((v, i) => {
        const x = (i / (history.length - 1)) * w
        const y = h - (Math.min(v, 100) / 100) * h
        return `${x},${y}`
      }).join(' ')
    : null

  const pct = Math.round(value)
  const isHigh = pct > 85
  const isMed = pct > 60

  return (
    <div className="taskbar-mini-stat">
      <span className="taskbar-mini-label">{label}</span>
      <svg width={w} height={h} className="taskbar-mini-svg">
        {/* Hintergrund-Linie */}
        <line x1="0" y1={h} x2={w} y2={h} stroke={color} strokeOpacity="0.15" strokeWidth="1" />
        {/* Füllung unter der Kurve */}
        {points && (
          <polygon
            points={`0,${h} ${points} ${w},${h}`}
            fill={color}
            fillOpacity="0.12"
          />
        )}
        {/* Sparkline */}
        {points && (
          <polyline
            points={points}
            fill="none"
            stroke={color}
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
      </svg>
      <span className="taskbar-mini-value" style={{ color: isHigh ? '#ef4444' : isMed ? '#f59e0b' : color }}>
        {pct}%
      </span>
      {suffix && <span className="taskbar-mini-suffix">{suffix}</span>}
    </div>
  )
}
