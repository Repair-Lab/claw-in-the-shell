import React, { useState, useRef, useEffect, useCallback } from 'react'

/**
 * ContextMenu — Right-Click Kontextmenü für Desktop-Icons
 * 
 * Usage:
 *   <div onContextMenu={(e) => showMenu(e, item)}>
 * 
 *   const [menu, setMenu] = useState(null)
 *   const showMenu = (e, item) => {
 *     e.preventDefault()
 *     setMenu({ x: e.clientX, y: e.clientY, item })
 *   }
 */
export default function ContextMenu({ menu, onClose, actions, onAction }) {
  const ref = useRef(null)
  const [position, setPosition] = useState(null)

  // Position berechnen (Screen-Edges vermeiden)
  useEffect(() => {
    if (!menu) { setPosition(null); return }
    const el = ref.current
    if (!el) return

    const { x, y } = menu
    const rect = el.getBoundingClientRect()
    const vw = window.innerWidth
    const vh = window.innerHeight

    let px = x, py = y
    // Right edge
    if (x + rect.width > vw - 8) px = vw - rect.width - 8
    // Bottom edge
    if (y + rect.height > vh - 8) py = vh - rect.height - 8

    setPosition({ top: Math.max(8, py), left: Math.max(8, px) })
  }, [menu])

  // Click outside close
  useEffect(() => {
    if (!menu) return
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menu, onClose])

  // Escape key close
  useEffect(() => {
    if (!menu) return
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [menu, onClose])

  if (!menu || !position) return null

  const { item } = menu

  // Standard-Aktionen je Item-Typ (werden über onAction verdrahtet)
  const defaultActions = (item) => {
    const base = []
    if (item.type === 'app') {
      base.push(
        { label: '🚀 Öffnen', icon: '▶️', action: 'open', separator: true },
        { label: 'ℹ️ Info', icon: 'ℹ️', action: 'info' },
      )
    } else if (item.type === 'folder') {
      base.push(
        { label: '📂 Öffnen', icon: '📂', action: 'open', separator: true },
        { label: '✏️ Umbenennen', icon: '✏️', action: 'rename' },
        { label: '📤 Apps zurück auf Desktop', icon: '📤', action: 'empty' },
        { label: '❌ Löschen', icon: '❌', action: 'delete', danger: true },
      )
    } else if (item.type === 'node') {
      base.push(
        { label: '🔗 Öffnen', icon: '🔗', action: 'open', separator: true },
        { label: 'ℹ️ Info', icon: 'ℹ️', action: 'info' },
        { label: '🗑️ Entfernen', icon: '🗑️', action: 'delete', danger: true },
      )
    }
    // Custom actions mergen
    const custom = (actions?.(item) || []).map(a => ({ ...a, custom: true }))
    return [...base, ...custom]
  }

  const items = defaultActions(item)

  return (
    <div
      ref={ref}
      style={{
        position: 'fixed',
        top: position.top,
        left: position.left,
        zIndex: 999998,
        background: 'rgba(18, 22, 30, 0.97)',
        border: '1px solid rgba(0, 245, 255, 0.2)',
        borderRadius: 10,
        padding: '6px',
        minWidth: 200,
        boxShadow: '0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px rgba(0,245,255,0.05)',
        backdropFilter: 'blur(20px)',
        animation: 'ctxMenuIn 0.15s ease-out',
      }}
    >
      <div style={{
        padding: '8px 12px 6px',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        marginBottom: 4,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#e0e8f0', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 16 }}>{item.icon || '📦'}</span>
          <span>{item.name}</span>
        </div>
        <div style={{ fontSize: 10, color: '#606870', marginTop: 2 }}>
          {item.type === 'app' ? 'Anwendung' : item.type === 'folder' ? `Ordner · ${item.items?.length || 0} Apps` : 'Netzwerkknoten'}
        </div>
      </div>

      {items.map((act, i) => (
        <React.Fragment key={act.action}>
          {act.separator && i > 0 && (
            <div style={{ height: 1, background: 'rgba(255,255,255,0.06)', margin: '4px 8px' }} />
          )}
          <button
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              width: '100%',
              padding: '8px 12px',
              border: 'none',
              background: 'none',
              color: act.danger ? '#ff6b6b' : '#c0c8d0',
              cursor: 'pointer',
              fontSize: 13,
              borderRadius: 6,
              textAlign: 'left',
            }}
            onMouseEnter={(e) => {
              e.target.style.background = act.danger ? 'rgba(255,68,68,0.1)' : 'rgba(0,245,255,0.08)'
            }}
            onMouseLeave={(e) => { e.target.style.background = 'none' }}
            onClick={() => {
              onClose()
              if (act.handler) act.handler(item)
              else if (onAction) onAction(act.action, item)
            }}
          >
            <span style={{ fontSize: 14, width: 20, textAlign: 'center' }}>{act.icon}</span>
            <span>{act.label}</span>
          </button>
        </React.Fragment>
      ))}

      <style>{`
        @keyframes ctxMenuIn {
          from { opacity: 0; transform: scale(0.95); }
          to { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  )
}

/**
 * Hook: useContextMenu
 * 
 *   const { menu, showMenu, hideMenu } = useContextMenu()
 *   <div onContextMenu={(e) => showMenu(e, item)}>...</div>
 *   <ContextMenu menu={menu} onClose={hideMenu} actions={(item) => [...]} />
 */
export function useContextMenu() {
  const [menu, setMenu] = useState(null)

  const showMenu = useCallback((e, item) => {
    e.preventDefault()
    e.stopPropagation()
    setMenu({ x: e.clientX, y: e.clientY, item })
  }, [])

  const hideMenu = useCallback(() => setMenu(null), [])

  return { menu, showMenu, hideMenu }
}
