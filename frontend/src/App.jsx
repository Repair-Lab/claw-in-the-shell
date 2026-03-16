import React, { useState, useEffect, useCallback, useRef } from 'react'
import { api, createWebSocket } from './api'
import BootScreen from './components/BootScreen'
import LoginScreen from './components/LoginScreen'
import Desktop from './components/Desktop'
import SetupWizard from './components/apps/SetupWizard'

// ═══════════════════════════════════════════════════════════════
// App States: BOOT → LOGIN → SETUP (if needed) → DESKTOP
// ═══════════════════════════════════════════════════════════════
const PHASE_BOOT   = 'boot'
const PHASE_LOGIN  = 'login'
const PHASE_SETUP  = 'setup'
const PHASE_DESKTOP = 'desktop'

export default function App() {
  const [phase, setPhase] = useState(PHASE_BOOT)
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(null)
  const [desktopState, setDesktopState] = useState(null)
  const [notifications, setNotifications] = useState([])
  const wsRef = useRef(null)

  // ── Check existing session ──
  useEffect(() => {
    const savedToken = localStorage.getItem('dbai_token')
    if (savedToken) {
      api.me()
        .then(userData => {
          setUser(userData)
          setToken(savedToken)
          // Prüfe ob Setup abgeschlossen
          api.setupStatus()
            .then(status => {
              if (!status.setup_completed) {
                setPhase(PHASE_SETUP)
              } else {
                setPhase(PHASE_DESKTOP)
              }
            })
            .catch(() => setPhase(PHASE_DESKTOP))
        })
        .catch(() => {
          localStorage.removeItem('dbai_token')
          // Show boot → login
        })
    }
  }, [])

  // ── Boot Complete ──
  const handleBootComplete = useCallback(() => {
    setPhase(PHASE_LOGIN)
  }, [])

  // ── Login ──
  const handleLogin = useCallback(async (username, password) => {
    const result = await api.login(username, password)
    if (result.success) {
      localStorage.setItem('dbai_token', result.token)
      setToken(result.token)
      setUser(result.user)
      // Prüfe ob Setup abgeschlossen
      try {
        const status = await api.setupStatus()
        if (!status.setup_completed) {
          setPhase(PHASE_SETUP)
          return { success: true }
        }
      } catch {}
      setPhase(PHASE_DESKTOP)
      return { success: true }
    }
    return { success: false, error: result.error || 'Login fehlgeschlagen' }
  }, [])

  // ── Setup Complete ──
  const handleSetupComplete = useCallback(() => {
    setPhase(PHASE_DESKTOP)
  }, [])

  // ── Logout ──
  const handleLogout = useCallback(async () => {
    try { await api.logout() } catch {}
    localStorage.removeItem('dbai_token')
    if (wsRef.current) wsRef.current.close()
    setUser(null)
    setToken(null)
    setDesktopState(null)
    setPhase(PHASE_LOGIN)
  }, [])

  // ── Load Desktop ──
  useEffect(() => {
    if (phase === PHASE_DESKTOP && token) {
      api.desktop()
        .then(state => {
          if (state && !state.error) {
            setDesktopState(state)
          } else {
            console.error('Desktop state error:', state?.error)
            setDesktopState({ apps: [], windows: [], notifications: [], desktop: {}, theme: {}, ghosts: [], user: {} })
          }
        })
        .catch(err => {
          console.error('Desktop laden fehlgeschlagen:', err)
          setDesktopState({ apps: [], windows: [], notifications: [], desktop: {}, theme: {}, ghosts: [], user: {} })
        })
    }
  }, [phase, token])

  // ── WebSocket ──
  useEffect(() => {
    if (phase !== PHASE_DESKTOP || !token) return

    const ws = createWebSocket(
      token,
      (msg) => {
        // Handle WebSocket messages
        if (msg.type === 'metrics') {
          // Update system metrics (propagate via custom event)
          window.dispatchEvent(new CustomEvent('dbai:metrics', { detail: msg.data }))
        }
        else if (msg.type === 'notify') {
          if (msg.channel === 'ghost_swap') {
            window.dispatchEvent(new CustomEvent('dbai:ghost_swap', { detail: msg.payload }))
            addNotification({
              title: 'Ghost-Swap',
              message: `${msg.payload.old_model || '—'} → ${msg.payload.new_model}`,
              icon: '👻',
              severity: 'ghost',
            })
          }
          else if (msg.channel === 'alert_fired') {
            addNotification({
              title: 'Alert',
              message: msg.payload.message || 'Alert ausgelöst',
              icon: '⚠️',
              severity: msg.payload.severity || 'warning',
            })
          }
          else if (msg.channel === 'system_event') {
            window.dispatchEvent(new CustomEvent('dbai:event', { detail: msg.payload }))
          }
        }
        else if (msg.type === 'window_opened' || msg.type === 'window_closed') {
          window.dispatchEvent(new CustomEvent('dbai:window', { detail: msg }))
        }
      },
      () => {
        // Reconnect after 3s
        setTimeout(() => {
          if (phase === PHASE_DESKTOP && token) {
            console.log('[WS] Reconnecting...')
          }
        }, 3000)
      }
    )

    wsRef.current = ws

    return () => {
      ws.close()
    }
  }, [phase, token])

  // ── Notifications ──
  const addNotification = useCallback((notif) => {
    const id = Date.now()
    setNotifications(prev => [...prev, { ...notif, id }])
    // Auto-dismiss after 8s
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id))
    }, 8000)
  }, [])

  const dismissNotification = useCallback((id) => {
    setNotifications(prev => prev.filter(n => n.id !== id))
  }, [])

  // ── Render ──
  return (
    <>
      {phase === PHASE_BOOT && (
        <BootScreen onComplete={handleBootComplete} />
      )}

      {phase === PHASE_LOGIN && (
        <LoginScreen onLogin={handleLogin} />
      )}

      {phase === PHASE_SETUP && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 9999,
          background: 'var(--bg-primary, #0a0e14)',
          display: 'flex', flexDirection: 'column',
        }}>
          <div style={{
            padding: '8px 16px', borderBottom: '1px solid var(--border, #1a1f2e)',
            display: 'flex', alignItems: 'center', gap: 8,
            background: 'var(--bg-surface, #111622)',
          }}>
            <span style={{ fontSize: 18 }}>👻</span>
            <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--accent, #00ffcc)' }}>
              DBAI — Ersteinrichtung
            </span>
          </div>
          <div style={{ flex: 1 }}>
            <SetupWizard onComplete={handleSetupComplete} />
          </div>
        </div>
      )}

      {phase === PHASE_DESKTOP && desktopState && (
        <Desktop
          user={user}
          desktopState={desktopState}
          onLogout={handleLogout}
        />
      )}

      {/* Notification Popups */}
      {notifications.length > 0 && (
        <div className="notification-popup">
          {notifications.map(n => (
            <div
              key={n.id}
              className={`notification-item severity-${n.severity}`}
              onClick={() => dismissNotification(n.id)}
            >
              <span style={{ fontSize: '20px' }}>{n.icon}</span>
              <div>
                <div style={{ fontWeight: 600, fontSize: '12px' }}>{n.title}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  {n.message}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
