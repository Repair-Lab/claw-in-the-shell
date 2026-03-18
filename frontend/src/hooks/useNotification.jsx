import React, { createContext, useContext, useState, useCallback, useRef } from 'react'

const NotificationContext = createContext(null)
let notifyId = 0

export function NotificationProvider({ children }) {
  const [notifications, setNotifications] = useState([])
  const timers = useRef({})

  const dismiss = useCallback((id) => {
    setNotifications(prev => prev.filter(n => n.id !== id))
    if (timers.current[id]) { clearTimeout(timers.current[id]); delete timers.current[id] }
  }, [])

  const notify = useCallback(({ type = 'info', title, message, duration = 4000 }) => {
    const id = ++notifyId
    setNotifications(prev => [...prev, { id, type, title, message, time: Date.now() }])
    if (duration > 0) {
      timers.current[id] = setTimeout(() => dismiss(id), duration)
    }
    return id
  }, [dismiss])

  const success = useCallback((title, message) => notify({ type: 'success', title, message }), [notify])
  const error = useCallback((title, message) => notify({ type: 'error', title, message, duration: 8000 }), [notify])
  const warning = useCallback((title, message) => notify({ type: 'warning', title, message, duration: 6000 }), [notify])
  const info = useCallback((title, message) => notify({ type: 'info', title, message }), [notify])

  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' }
  const colors = {
    success: { bg: '#0d2818', border: '#1a5c2e', text: '#4ade80' },
    error:   { bg: '#2d0a0a', border: '#5c1a1a', text: '#f87171' },
    warning: { bg: '#2d1f0a', border: '#5c3d1a', text: '#fbbf24' },
    info:    { bg: '#0a1a2d', border: '#1a3a5c', text: '#60a5fa' }
  }

  return (
    <NotificationContext.Provider value={{ notify, success, error, warning, info, dismiss }}>
      {children}
      {/* Toast Container */}
      <div style={{
        position: 'fixed', top: 16, right: 16, zIndex: 999999,
        display: 'flex', flexDirection: 'column', gap: 8,
        pointerEvents: 'none', maxWidth: 380
      }}>
        {notifications.map(n => {
          const c = colors[n.type] || colors.info
          return (
            <div key={n.id} style={{
              background: c.bg, border: `1px solid ${c.border}`, borderRadius: 10,
              padding: '12px 16px', display: 'flex', gap: 10, alignItems: 'flex-start',
              pointerEvents: 'auto', cursor: 'pointer', minWidth: 280,
              boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
              animation: 'slideInRight 0.3s ease-out'
            }} onClick={() => dismiss(n.id)}>
              <span style={{ fontSize: 18, flexShrink: 0 }}>{icons[n.type]}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                {n.title && <div style={{ fontWeight: 600, fontSize: 13, color: c.text, marginBottom: 2 }}>{n.title}</div>}
                {n.message && <div style={{ fontSize: 12, color: '#a0aec0', lineHeight: 1.4, wordBreak: 'break-word' }}>{n.message}</div>}
              </div>
              <span style={{ fontSize: 14, color: '#666', flexShrink: 0, lineHeight: 1 }}>×</span>
            </div>
          )
        })}
      </div>
      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
    </NotificationContext.Provider>
  )
}

export function useNotification() {
  const ctx = useContext(NotificationContext)
  if (!ctx) throw new Error('useNotification must be used within NotificationProvider')
  return ctx
}

export default NotificationContext
