import React, { useState, useRef, useEffect } from 'react'
import { api } from '../api'

/**
 * NotificationCenter — Notification Center (wie Windows 11 / macOS)
 * 
 * Zeigt alle aktiven + vergangenen Notifications in einem Panel.
 * Wird über Taskbar-Button oder Click auf Toast geöffnet.
 */
export default function NotificationCenter({ onClose }) {
  const [tabs, setTabs] = useState('all') // 'all' | 'system' | 'apps'
  const [expanded, setExpanded] = useState(new Set())
  const ref = useRef(null)

  // Mock-Notifications für Demo (in Realbetrieb aus DB/API)
  const [notifications, setNotifications] = useState([
    { id: 1, type: 'success', title: 'Ghost Browser Task abgeschlossen', message: 'Task cf98766b erfolgreich abgeschlossen (6.4s, 4 Screenshots)', time: Date.now() - 120000, source: 'ghost-browser' },
    { id: 2, type: 'info', title: 'LLM Router verbunden', message: 'Qwen3.8-27B (GPU) bereit auf :11502', time: Date.now() - 300000, source: 'system' },
    { id: 3, type: 'warning', title: 'GPU Temperatur hoch', message: 'GPU: 82°C — Last reduzieren empfohlen', time: Date.now() - 600000, source: 'system' },
    { id: 4, type: 'error', title: 'SMB Verbindung fehlgeschlagen', message: 'Windows (172.16.16.113) — Firewall blockiert ausgehend', time: Date.now() - 900000, source: 'network' },
    { id: 5, type: 'success', title: 'MML/Vision installiert', message: 'Bild-Upload in Ghost Chat aktiviert', time: Date.now() - 1800000, source: 'apps' },
    { id: 6, type: 'info', title: 'Desktop aktualisiert', message: '12 Apps, 3 Knoten geladen', time: Date.now() - 3600000, source: 'system' },
  ])

  // Click outside close
  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  // Escape close
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const filtered = notifications.filter(n => {
    if (tabs === 'all') return true
    if (tabs === 'system') return n.source === 'system'
    return n.source !== 'system'
  })

  const clearAll = () => setNotifications([])

  const timeAgo = (ts) => {
    const diff = Math.floor((Date.now() - ts) / 1000)
    if (diff < 60) return `${diff}s ago`
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
    return `${Math.floor(diff / 86400)}d ago`
  }

  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' }
  const colors = {
    success: { bg: 'rgba(13,40,24,0.6)', border: '#1a5c2e', icon: '#4ade80' },
    error:   { bg: 'rgba(45,10,10,0.6)', border: '#5c1a1a', icon: '#f87171' },
    warning: { bg: 'rgba(45,31,10,0.6)', border: '#5c3d1a', icon: '#fbbf24' },
    info:    { bg: 'rgba(10,26,45,0.6)', border: '#1a3a5c', icon: '#60a5fa' },
  }

  return (
    <div
      ref={ref}
      style={{
        position: 'fixed',
        top: 48,
        right: 8,
        zIndex: 999997,
        width: 380,
        maxHeight: 'calc(100vh - 80px)',
        background: 'rgba(14, 18, 26, 0.98)',
        border: '1px solid rgba(0, 245, 255, 0.15)',
        borderRadius: 14,
        boxShadow: '0 12px 48px rgba(0,0,0,0.7), 0 0 0 1px rgba(0,245,255,0.05)',
        backdropFilter: 'blur(24px)',
        display: 'flex',
        flexDirection: 'column',
        animation: 'notifPanelIn 0.25s ease-out',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div style={{
        padding: '14px 16px',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#e0e8f0' }}>
            🔔 Benachrichtigungen
          </div>
          <div style={{ fontSize: 11, color: '#606870', marginTop: 2 }}>
            {notifications.length} aktiv · {notifications.filter(n => n.type !== 'info').length} wichtig
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            style={{
              background: 'rgba(255,68,68,0.1)',
              border: '1px solid rgba(255,68,68,0.2)',
              color: '#ff6b6b',
              cursor: 'pointer',
              fontSize: 11,
              padding: '5px 10px',
              borderRadius: 6,
              fontWeight: 600,
            }}
            onClick={clearAll}
          >
            🗑️ Alle löschen
          </button>
          <button
            style={{
              background: 'none',
              border: '1px solid rgba(255,255,255,0.15)',
              color: '#a0a8b0',
              cursor: 'pointer',
              fontSize: 14,
              width: 28,
              height: 28,
              borderRadius: 6,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            onClick={onClose}
          >
            ✕
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex',
        gap: 2,
        padding: '8px 12px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}>
        {['all', 'system', 'apps'].map(tab => (
          <button
            key={tab}
            style={{
              background: tabs === tab ? 'rgba(0,245,255,0.1)' : 'none',
              border: 'none',
              color: tabs === tab ? '#00f5ff' : '#707880',
              cursor: 'pointer',
              fontSize: 12,
              padding: '6px 14px',
              borderRadius: 6,
              fontWeight: tabs === tab ? 600 : 400,
              textTransform: 'capitalize',
            }}
            onClick={() => setTabs(tab)}
          >
            {tab === 'all' ? 'Alle' : tab === 'system' ? 'System' : 'Apps'}
          </button>
        ))}
      </div>

      {/* Notification List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
        {filtered.length === 0 ? (
          <div style={{
            padding: '40px 20px',
            textAlign: 'center',
            color: '#505860',
          }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>🔕</div>
            <div style={{ fontSize: 14, fontWeight: 500 }}>Keine Benachrichtigungen</div>
            <div style={{ fontSize: 12, marginTop: 6 }}>Alles ist ruhig. Gut so.</div>
          </div>
        ) : (
          filtered.map(n => {
            const c = colors[n.type] || colors.info
            const isExpanded = expanded.has(n.id)
            return (
              <div
                key={n.id}
                style={{
                  background: c.bg,
                  border: `1px solid ${c.border}`,
                  borderRadius: 10,
                  padding: '10px 12px',
                  marginBottom: 6,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onClick={() => {
                  setExpanded(prev => {
                    const next = new Set(prev)
                    if (next.has(n.id)) next.delete(n.id)
                    else next.add(n.id)
                    return next
                  })
                }}
              >
                <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                  <span style={{ fontSize: 20, flexShrink: 0, lineHeight: 1.2 }}>
                    {icons[n.type]}
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'flex-start',
                      gap: 8,
                    }}>
                      <div style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: c.icon,
                        lineHeight: 1.3,
                      }}>
                        {n.title}
                      </div>
                      <span style={{
                        fontSize: 10,
                        color: '#505860',
                        flexShrink: 0,
                        whiteSpace: 'nowrap',
                      }}>
                        {timeAgo(n.time)}
                      </span>
                    </div>
                    <div style={{
                      fontSize: 12,
                      color: '#a0a8b0',
                      marginTop: 4,
                      lineHeight: 1.4,
                      display: isExpanded ? 'block' : '-webkit-box',
                      WebkitLineClamp: isExpanded ? 'unset' : 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                    }}>
                      {n.message}
                    </div>
                    <div style={{
                      marginTop: 6,
                      display: 'flex',
                      gap: 8,
                      alignItems: 'center',
                    }}>
                      <span style={{
                        fontSize: 10,
                        color: '#606870',
                        background: 'rgba(255,255,255,0.05)',
                        padding: '2px 8px',
                        borderRadius: 4,
                      }}>
                        {n.source}
                      </span>
                      {isExpanded && (
                        <span style={{
                          fontSize: 10,
                          color: '#505860',
                          fontStyle: 'italic',
                        }}>
                          {new Date(n.time).toLocaleString('de-DE')}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>

      <style>{`
        @keyframes notifPanelIn {
          from { opacity: 0; transform: translateY(-8px) scale(0.98); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>
    </div>
  )
}
