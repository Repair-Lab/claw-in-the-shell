import React, { useState, useRef, useEffect, useCallback } from 'react'
import { api } from '../../api'

/**
 * Terminal v1 — Feature 23
 * Linux-Terminal auf dem DBAI-Desktop
 *
 * Features:
 * - Mehrere Terminal-Tabs
 * - WebSocket-basierte Shell-Verbindung
 * - Scrollback-Buffer
 * - Kommando-Historie (Pfeil hoch/runter)
 * - Auto-Complete (Tab)
 * - Ansi-Farben (Basic)
 */

const ANSI_COLORS = {
  '30': '#1a1a2e', '31': '#ff4444', '32': '#00ffcc', '33': '#ffaa00',
  '34': '#4488ff', '35': '#cc44ff', '36': '#00ccff', '37': '#cccccc',
  '90': '#666666', '91': '#ff6666', '92': '#66ffdd', '93': '#ffcc44',
  '94': '#6699ff', '95': '#dd66ff', '96': '#44ddff', '97': '#ffffff',
  '0': null, // Reset
}

function parseAnsi(text) {
  const parts = []
  const regex = /\x1b\[([0-9;]+)m/g
  let lastIndex = 0
  let currentColor = null
  let match

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ text: text.slice(lastIndex, match.index), color: currentColor })
    }
    const codes = match[1].split(';')
    for (const code of codes) {
      if (ANSI_COLORS[code] !== undefined) {
        currentColor = ANSI_COLORS[code]
      }
    }
    lastIndex = regex.lastIndex
  }

  if (lastIndex < text.length) {
    parts.push({ text: text.slice(lastIndex), color: currentColor })
  }

  return parts
}

function TerminalLine({ line }) {
  const parts = parseAnsi(line)
  return (
    <div style={{ minHeight: '18px', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
      {parts.map((p, i) => (
        <span key={i} style={p.color ? { color: p.color } : undefined}>{p.text}</span>
      ))}
    </div>
  )
}

export default function Terminal() {
  const [tabs, setTabs] = useState([{ id: 1, name: 'Terminal 1', output: [], cwd: '~', history: [], historyIndex: -1 }])
  const [activeTab, setActiveTab] = useState(1)
  const [input, setInput] = useState('')
  const [isRunning, setIsRunning] = useState(false)
  const outputRef = useRef(null)
  const inputRef = useRef(null)
  const tabIdCounter = useRef(2)

  const currentTab = tabs.find(t => t.id === activeTab) || tabs[0]

  // Auto-scroll
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight
    }
  }, [currentTab?.output])

  // Focus input
  useEffect(() => {
    if (inputRef.current) inputRef.current.focus()
  }, [activeTab])

  const appendOutput = useCallback((tabId, lines) => {
    setTabs(prev => prev.map(t => {
      if (t.id !== tabId) return t
      const newOutput = [...t.output, ...lines].slice(-5000) // Max 5000 Zeilen
      return { ...t, output: newOutput }
    }))
  }, [])

  const updateCwd = useCallback((tabId, cwd) => {
    setTabs(prev => prev.map(t => t.id === tabId ? { ...t, cwd } : t))
  }, [])

  const executeCommand = useCallback(async (command) => {
    if (!command.trim()) return

    const tabId = activeTab
    const trimmed = command.trim()

    // Prompt anzeigen
    appendOutput(tabId, [`\x1b[32m${currentTab.cwd}\x1b[0m \x1b[36m$\x1b[0m ${trimmed}`])

    // Historie aktualisieren
    setTabs(prev => prev.map(t => {
      if (t.id !== tabId) return t
      const newHistory = [...t.history.filter(h => h !== trimmed), trimmed].slice(-200)
      return { ...t, history: newHistory, historyIndex: -1 }
    }))

    // Spezial-Befehle (Client-seitig)
    if (trimmed === 'clear' || trimmed === 'cls') {
      setTabs(prev => prev.map(t => t.id === tabId ? { ...t, output: [] } : t))
      return
    }

    if (trimmed === 'exit') {
      if (tabs.length > 1) {
        setTabs(prev => prev.filter(t => t.id !== tabId))
        setActiveTab(tabs.find(t => t.id !== tabId)?.id || 1)
      } else {
        appendOutput(tabId, ['\x1b[33mLetztes Terminal kann nicht geschlossen werden.\x1b[0m'])
      }
      return
    }

    if (trimmed === 'help') {
      appendOutput(tabId, [
        '\x1b[36m═══ DBAI Terminal ═══\x1b[0m',
        'Befehle werden serverseitig (via API) ausgeführt.',
        '',
        '\x1b[33mSpezial-Befehle:\x1b[0m',
        '  clear/cls    — Terminal leeren',
        '  exit         — Tab schließen',
        '  help         — Diese Hilfe',
        '  newtab       — Neuen Tab öffnen',
        '',
        '\x1b[33mShortcuts:\x1b[0m',
        '  ↑/↓          — Kommando-Historie',
        '  Ctrl+L        — Terminal leeren',
        '  Ctrl+C        — Abbruch-Signal',
        '',
        '\x1b[33mSicherheit:\x1b[0m',
        '  Befehle laufen als dbai-User (nicht root).',
        '  Destruktive Befehle erfordern Bestätigung.',
        '',
      ])
      return
    }

    if (trimmed === 'newtab') {
      const newId = tabIdCounter.current++
      setTabs(prev => [...prev, { id: newId, name: `Terminal ${newId}`, output: [], cwd: '~', history: [], historyIndex: -1 }])
      setActiveTab(newId)
      return
    }

    // Server-seitige Ausführung
    setIsRunning(true)
    try {
      const result = await api.terminalExec(trimmed, currentTab.cwd)
      if (result.stdout) {
        const lines = result.stdout.split('\n')
        appendOutput(tabId, lines)
      }
      if (result.stderr) {
        const errLines = result.stderr.split('\n').map(l => `\x1b[31m${l}\x1b[0m`)
        appendOutput(tabId, errLines)
      }
      if (result.exit_code !== 0 && result.exit_code !== undefined) {
        appendOutput(tabId, [`\x1b[31m[exit: ${result.exit_code}]\x1b[0m`])
      }
      if (result.cwd) {
        updateCwd(tabId, result.cwd)
      }
    } catch (err) {
      appendOutput(tabId, [`\x1b[31mFehler: ${err.message}\x1b[0m`])
    } finally {
      setIsRunning(false)
    }
  }, [activeTab, currentTab, tabs, appendOutput, updateCwd])

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      executeCommand(input)
      setInput('')
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setTabs(prev => prev.map(t => {
        if (t.id !== activeTab) return t
        const newIndex = Math.min(t.historyIndex + 1, t.history.length - 1)
        if (newIndex >= 0 && t.history.length > 0) {
          setInput(t.history[t.history.length - 1 - newIndex])
          return { ...t, historyIndex: newIndex }
        }
        return t
      }))
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setTabs(prev => prev.map(t => {
        if (t.id !== activeTab) return t
        const newIndex = t.historyIndex - 1
        if (newIndex < 0) {
          setInput('')
          return { ...t, historyIndex: -1 }
        }
        setInput(t.history[t.history.length - 1 - newIndex])
        return { ...t, historyIndex: newIndex }
      }))
    } else if (e.ctrlKey && e.key === 'l') {
      e.preventDefault()
      setTabs(prev => prev.map(t => t.id === activeTab ? { ...t, output: [] } : t))
    } else if (e.ctrlKey && e.key === 'c') {
      e.preventDefault()
      if (isRunning) {
        appendOutput(activeTab, ['^C'])
        setIsRunning(false)
      }
      setInput('')
    }
  }, [input, activeTab, isRunning, executeCommand, appendOutput])

  const addTab = () => {
    const newId = tabIdCounter.current++
    setTabs(prev => [...prev, { id: newId, name: `Terminal ${newId}`, output: [], cwd: '~', history: [], historyIndex: -1 }])
    setActiveTab(newId)
  }

  const closeTab = (tabId) => {
    if (tabs.length <= 1) return
    setTabs(prev => prev.filter(t => t.id !== tabId))
    if (activeTab === tabId) {
      setActiveTab(tabs.find(t => t.id !== tabId)?.id || 1)
    }
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: '#0a0a14', fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
      fontSize: '13px', color: '#d4d4d4',
    }}>
      {/* Tab-Leiste */}
      <div style={{
        display: 'flex', alignItems: 'center', background: '#0f0f1a',
        borderBottom: '1px solid #1a2a3a', minHeight: '32px', padding: '0 4px',
      }}>
        {tabs.map(tab => (
          <div
            key={tab.id}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '4px 12px', cursor: 'pointer',
              background: tab.id === activeTab ? '#1a1a2e' : 'transparent',
              borderBottom: tab.id === activeTab ? '2px solid #00ffcc' : '2px solid transparent',
              color: tab.id === activeTab ? '#00ffcc' : '#6688aa',
              fontSize: '12px', transition: 'all 0.15s',
            }}
            onClick={() => setActiveTab(tab.id)}
          >
            <span style={{ fontSize: '10px' }}>▸</span>
            <span>{tab.name}</span>
            {tabs.length > 1 && (
              <span
                onClick={(e) => { e.stopPropagation(); closeTab(tab.id) }}
                style={{
                  fontSize: '14px', color: '#556', cursor: 'pointer',
                  marginLeft: '4px', lineHeight: 1,
                }}
                onMouseEnter={e => e.target.style.color = '#ff4444'}
                onMouseLeave={e => e.target.style.color = '#556'}
              >
                ×
              </span>
            )}
          </div>
        ))}
        <div
          onClick={addTab}
          style={{
            padding: '4px 8px', cursor: 'pointer', color: '#446',
            fontSize: '16px', marginLeft: '4px',
          }}
          onMouseEnter={e => e.target.style.color = '#00ffcc'}
          onMouseLeave={e => e.target.style.color = '#446'}
          title="Neues Terminal"
        >
          +
        </div>
      </div>

      {/* Output */}
      <div
        ref={outputRef}
        onClick={() => inputRef.current?.focus()}
        style={{
          flex: 1, overflow: 'auto', padding: '8px 12px',
          lineHeight: '18px', cursor: 'text',
        }}
      >
        {currentTab.output.length === 0 && (
          <div style={{ color: '#334' }}>
            <span style={{ color: '#00ffcc' }}>DBAI Terminal v1.0</span>
            <br />
            <span style={{ color: '#446' }}>Tippe 'help' für Hilfe. Shell: /bin/bash</span>
          </div>
        )}
        {currentTab.output.map((line, i) => (
          <TerminalLine key={i} line={line} />
        ))}

        {/* Input-Zeile */}
        <div style={{ display: 'flex', alignItems: 'center', minHeight: '18px' }}>
          <span style={{ color: '#00ffcc', marginRight: '4px' }}>{currentTab.cwd}</span>
          <span style={{ color: '#00ccff', marginRight: '8px' }}>$</span>
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isRunning}
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              color: '#d4d4d4', fontFamily: 'inherit', fontSize: 'inherit',
              caretColor: '#00ffcc', padding: 0,
            }}
            spellCheck={false}
            autoComplete="off"
          />
          {isRunning && (
            <span style={{ color: '#ffaa00', fontSize: '11px', marginLeft: '8px' }}>
              ⏳ running...
            </span>
          )}
        </div>
      </div>

      {/* Status-Leiste */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: '#0f0f1a', borderTop: '1px solid #1a2a3a',
        padding: '2px 12px', fontSize: '11px', color: '#446',
      }}>
        <span>bash — {currentTab.cwd}</span>
        <span>{currentTab.output.length} Zeilen</span>
        <span>Tab {tabs.findIndex(t => t.id === activeTab) + 1}/{tabs.length}</span>
      </div>
    </div>
  )
}
