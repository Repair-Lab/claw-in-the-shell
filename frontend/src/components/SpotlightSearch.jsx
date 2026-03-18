import React, { useState, useEffect, useRef, useCallback } from 'react'

export default function SpotlightSearch({ apps = [], onLaunch, onClose }) {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef(null)

  const filtered = apps.filter(app => {
    if (!query.trim()) return true
    const q = query.toLowerCase()
    return (app.name || '').toLowerCase().includes(q) ||
           (app.app_id || '').toLowerCase().includes(q) ||
           (app.description || '').toLowerCase().includes(q)
  }).slice(0, 12)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  const launch = useCallback((app) => {
    if (onLaunch) onLaunch(app.app_id || app.id)
    if (onClose) onClose()
  }, [onLaunch, onClose])

  const onKeyDown = useCallback((e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(i => Math.min(i + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && filtered[selectedIndex]) {
      e.preventDefault()
      launch(filtered[selectedIndex])
    } else if (e.key === 'Escape') {
      if (onClose) onClose()
    }
  }, [filtered, selectedIndex, launch, onClose])

  return (
    <div style={S.overlay} onClick={onClose}>
      <div style={S.modal} onClick={e => e.stopPropagation()}>
        <div style={S.inputWrap}>
          <span style={S.searchIcon}>🔍</span>
          <input
            ref={inputRef}
            style={S.input}
            placeholder="App suchen... (Ctrl+K)"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
          />
          {query && <button style={S.clearBtn} onClick={() => setQuery('')}>×</button>}
        </div>
        <div style={S.results}>
          {filtered.length === 0 && (
            <div style={S.empty}>Keine Apps gefunden</div>
          )}
          {filtered.map((app, i) => (
            <div
              key={app.app_id || app.id || i}
              style={{ ...S.item, ...(i === selectedIndex ? S.itemSelected : {}) }}
              onClick={() => launch(app)}
              onMouseEnter={() => setSelectedIndex(i)}
            >
              <span style={S.appIcon}>{app.icon || '📦'}</span>
              <div style={S.appInfo}>
                <div style={S.appName}>{app.name || app.app_id}</div>
                {app.description && <div style={S.appDesc}>{app.description}</div>}
              </div>
              <span style={S.appShortcut}>↵</span>
            </div>
          ))}
        </div>
        <div style={S.footer}>
          <span>↑↓ Navigation</span>
          <span>↵ Öffnen</span>
          <span>Esc Schließen</span>
        </div>
      </div>
    </div>
  )
}

const S = {
  overlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
    display: 'flex', justifyContent: 'center', alignItems: 'flex-start',
    paddingTop: '15vh', zIndex: 999998, backdropFilter: 'blur(4px)'
  },
  modal: {
    background: '#1a1e2e', border: '1px solid #2a3a4a', borderRadius: 16,
    width: 520, maxHeight: '60vh', display: 'flex', flexDirection: 'column',
    boxShadow: '0 20px 60px rgba(0,0,0,0.5)', overflow: 'hidden'
  },
  inputWrap: {
    display: 'flex', alignItems: 'center', padding: '12px 16px',
    borderBottom: '1px solid #2a3a4a', gap: 10
  },
  searchIcon: { fontSize: 18, opacity: 0.6 },
  input: {
    flex: 1, background: 'none', border: 'none', outline: 'none',
    fontSize: 16, color: '#e0e6ed', fontFamily: 'inherit'
  },
  clearBtn: {
    background: 'none', border: 'none', color: '#666', fontSize: 18,
    cursor: 'pointer', padding: '0 4px'
  },
  results: {
    flex: 1, overflow: 'auto', padding: '8px 0'
  },
  empty: {
    padding: '24px 16px', textAlign: 'center', color: '#556', fontSize: 14
  },
  item: {
    display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px',
    cursor: 'pointer', transition: 'background 0.1s'
  },
  itemSelected: {
    background: '#252a3a'
  },
  appIcon: { fontSize: 22, width: 36, textAlign: 'center' },
  appInfo: { flex: 1, minWidth: 0 },
  appName: { fontSize: 14, fontWeight: 600, color: '#e0e6ed' },
  appDesc: { fontSize: 11, color: '#6a7a8a', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' },
  appShortcut: { fontSize: 12, color: '#4a5a6a', padding: '2px 6px', background: '#1e2636', borderRadius: 4, border: '1px solid #2a3a4a' },
  footer: {
    display: 'flex', gap: 16, padding: '8px 16px', borderTop: '1px solid #2a3a4a',
    fontSize: 11, color: '#4a5a6a', justifyContent: 'center'
  }
}
