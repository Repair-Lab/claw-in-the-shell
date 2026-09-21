import { useEffect, useCallback, useRef } from 'react'

// Globale Shortcut-Registry
const registry = new Map()

// Standard-Shortcuts definieren
const DEFAULT_SHORTCUTS = {
  'Ctrl+T':      { action: 'open-terminal',        label: 'Terminal öffnen' },
  'Ctrl+E':      { action: 'open-file-browser',    label: 'Datei-Browser öffnen' },
  'Ctrl+G':      { action: 'open-ghost-chat',      label: 'Ghost Chat öffnen' },
  'Ctrl+K':      { action: 'open-spotlight',       label: 'App-Suche öffnen' },
  'Ctrl+,':      { action: 'open-settings',        label: 'Einstellungen öffnen' },
  'Ctrl+M':      { action: 'open-system-monitor',  label: 'System Monitor öffnen' },
  'Ctrl+L':      { action: 'open-llm-manager',     label: 'LLM Manager öffnen' },
  'Ctrl+Shift+Q': { action: 'close-window',        label: 'Fenster schließen' },
  'Ctrl+Shift+R': { action: 'reload-app',          label: 'App neu laden' },
  'Alt+Tab':     { action: 'cycle-windows',        label: 'Fenster wechseln' },
  'Escape':      { action: 'close-spotlight',       label: 'Suche schließen' },
}

function keyToString(e) {
  const parts = []
  if (e.ctrlKey || e.metaKey) parts.push('Ctrl')
  if (e.shiftKey) parts.push('Shift')
  if (e.altKey) parts.push('Alt')
  const key = e.key === ' ' ? 'Space' : e.key.length === 1 ? e.key.toUpperCase() : e.key
  if (!['Control', 'Shift', 'Alt', 'Meta'].includes(e.key)) parts.push(key)
  return parts.join('+')
}

export function useKeyboardShortcuts(handlers = {}) {
  const handlersRef = useRef(handlers)
  handlersRef.current = handlers

  useEffect(() => {
    function onKeyDown(e) {
      const combo = keyToString(e)
      const shortcut = DEFAULT_SHORTCUTS[combo]
      if (!shortcut) return

      const handler = handlersRef.current[shortcut.action]
      if (handler) {
        e.preventDefault()
        e.stopPropagation()
        handler(e)
      }
    }
    window.addEventListener('keydown', onKeyDown, true)
    return () => window.removeEventListener('keydown', onKeyDown, true)
  }, [])

  return { shortcuts: DEFAULT_SHORTCUTS }
}

export function getShortcutList() {
  return Object.entries(DEFAULT_SHORTCUTS).map(([combo, info]) => ({
    combo,
    ...info
  }))
}

export default useKeyboardShortcuts
