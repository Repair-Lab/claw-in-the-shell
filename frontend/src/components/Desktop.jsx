import React, { useState, useCallback, useRef, useEffect } from 'react'
import { api } from '../api'
import Window from './Window'
import SystemMonitor from './apps/SystemMonitor'
import GhostManager from './apps/GhostManager'
import GhostChat from './apps/GhostChat'
import KnowledgeBase from './apps/KnowledgeBase'
import EventViewer from './apps/EventViewer'
import SQLConsole from './apps/SQLConsole'
import HealthDashboard from './apps/HealthDashboard'
import FileBrowser from './apps/FileBrowser'
import ProcessManager from './apps/ProcessManager'
import Settings from './apps/Settings'
import ErrorAnalyzer from './apps/ErrorAnalyzer'
import SoftwareStore from './apps/SoftwareStore'
import OpenClawIntegrator from './apps/OpenClawIntegrator'
import LLMManager from './apps/LLMManager'
import SetupWizard from './apps/SetupWizard'

// App-Komponenten Registry
const APP_COMPONENTS = {
  SystemMonitor,
  GhostManager,
  GhostChat,
  KnowledgeBase,
  EventViewer,
  SQLConsole,
  HealthDashboard,
  FileBrowser,
  ProcessManager,
  Settings,
  ErrorAnalyzer,
  SoftwareStore,
  OpenClawIntegrator,
  LLMManager,
  SetupWizard,
}

/**
 * Desktop — Window Manager, Taskbar, Icons
 */
export default function Desktop({ user, desktopState, onLogout }) {
  const [windows, setWindows] = useState([])
  const [apps] = useState(desktopState?.apps || [])
  const [theme] = useState(desktopState?.theme || {})
  const [nextZ, setNextZ] = useState(10)
  const desktopRef = useRef(null)
  const [clock, setClock] = useState(new Date())

  // Uhr
  useEffect(() => {
    const timer = setInterval(() => setClock(new Date()), 1000)
    return () => clearInterval(timer)
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
  const openApp = useCallback((appId) => {
    // Check if already open
    const existing = windows.find(w => w.appId === appId)
    if (existing) {
      focusWindow(existing.id)
      return
    }

    const app = apps.find(a => a.app_id === appId)
    if (!app) return

    const z = nextZ + 1
    setNextZ(z)

    const newWindow = {
      id: `win-${Date.now()}`,
      appId: app.app_id,
      appName: app.name,
      appIcon: app.icon,
      sourceType: app.source_type,
      sourceTarget: app.source_target || '',
      component: app.source_target || '',
      x: 80 + (windows.length % 5) * 40,
      y: 60 + (windows.length % 5) * 40,
      width: app.default_width || 800,
      height: app.default_height || 600,
      state: 'normal', // normal, minimized, maximized
      focused: true,
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

  // Desktop Icons from config
  const desktopIcons = desktopState?.desktop?.icons || []

  // Active ghosts for taskbar
  const [activeGhosts, setActiveGhosts] = useState(desktopState?.ghosts || [])
  useEffect(() => {
    const handler = () => {
      api.ghosts().then(data => setActiveGhosts(data.active_ghosts || []))
        .catch(() => {})
    }
    window.addEventListener('dbai:ghost_swap', handler)
    return () => window.removeEventListener('dbai:ghost_swap', handler)
  }, [])

  return (
    <div className="desktop">
      {/* Desktop Area */}
      <div className="desktop-area" ref={desktopRef}>
        {/* Desktop Icons */}
        <div className="desktop-icons">
          {desktopIcons.map((icon, i) => (
            <div
              key={i}
              className="desktop-icon"
              onDoubleClick={() => openApp(icon.app_id)}
            >
              <span className="icon">
                {apps.find(a => a.app_id === icon.app_id)?.icon || '📦'}
              </span>
              <span className="label">{icon.label}</span>
            </div>
          ))}
        </div>

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
            {renderAppContent(win)}
          </Window>
        ))}
      </div>

      {/* Taskbar */}
      <div className="taskbar">
        {/* Start Button */}
        <div className="taskbar-start" onClick={() => openApp('ghost-chat')}>
          👻 DBAI
        </div>

        {/* Open Windows */}
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

        {/* Status Area */}
        <div className="taskbar-status">
          {/* Active Ghost */}
          {activeGhosts.length > 0 && (
            <div className="taskbar-ghost" onClick={() => openApp('ghost-manager')}>
              👻 {activeGhosts[0]?.model_display || 'No Ghost'}
            </div>
          )}

          {/* User */}
          <span
            style={{ cursor: 'pointer' }}
            onClick={onLogout}
            title="Abmelden"
          >
            {user?.display_name || user?.username}
          </span>

          {/* Clock */}
          <span>
            {clock.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      </div>
    </div>
  )
}

// ── Render App Content ──
function renderAppContent(win) {
  const Component = APP_COMPONENTS[win.component]
  if (Component) {
    return <Component windowId={win.id} />
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
