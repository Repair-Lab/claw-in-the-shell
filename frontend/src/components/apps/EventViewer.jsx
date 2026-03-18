import React, { useState, useEffect, useRef } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

/**
 * Event Viewer — Live-Stream aller System-Events
 */
export default function EventViewer() {
  const { settings, schema, update: updateSetting, reset: resetSettings } = useAppSettings('event-viewer')
  const [showSettings, setShowSettings] = useState(false)
  const [events, setEvents] = useState([])
  const [filter, setFilter] = useState('')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const containerRef = useRef(null)

  const maxEvents = settings?.max_events ?? 200
  const refreshInterval = settings?.refresh_interval ?? 3000

  const refresh = () => {
    api.events(maxEvents, filter || null).then(setEvents).catch(() => {})
  }

  useEffect(() => {
    refresh()
    if (autoRefresh) {
      const interval = setInterval(refresh, refreshInterval)
      return () => clearInterval(interval)
    }
  }, [filter, autoRefresh, maxEvents, refreshInterval])

  // Listen for new events via WebSocket
  useEffect(() => {
    const handler = (e) => {
      setEvents(prev => [e.detail, ...prev].slice(0, maxEvents))
    }
    window.addEventListener('dbai:event', handler)
    return () => window.removeEventListener('dbai:event', handler)
  }, [maxEvents])

  const eventTypes = ['', 'keyboard', 'network', 'disk', 'power', 'thermal',
                       'process', 'system', 'error', 'llm']

  if (showSettings) {
    return (
      <div style={{ padding: '16px' }}>
        <button onClick={() => setShowSettings(false)} style={{ marginBottom: '12px', padding: '4px 12px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 'var(--radius)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '11px' }}>← Zurück</button>
        <AppSettingsPanel schema={schema} settings={settings} onUpdate={updateSetting} onReset={resetSettings} title="Event Viewer" />
      </div>
    )
  }

  return (
    <div>
      {/* Toolbar */}
      <div className="flex gap-2 items-center" style={{ marginBottom: '12px' }}>
        <select
          value={filter}
          onChange={e => setFilter(e.target.value)}
          style={{
            padding: '6px 12px', background: 'var(--bg-surface)',
            border: '1px solid var(--border)', borderRadius: 'var(--radius)',
            color: 'var(--text-primary)', fontSize: '12px', outline: 'none',
          }}
        >
          <option value="">Alle Events</option>
          {eventTypes.filter(Boolean).map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-xs text-muted" style={{ cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={e => setAutoRefresh(e.target.checked)}
          />
          Auto-Refresh
        </label>
        <button onClick={refresh} style={{
          padding: '6px 12px', background: 'transparent',
          border: '1px solid var(--border)', borderRadius: 'var(--radius)',
          color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '11px',
        }}>
          🔄 Refresh
        </button>
        <span className="text-xs text-muted" style={{ marginLeft: 'auto' }}>
          {events.length} Events
        </span>
        <button onClick={() => setShowSettings(true)} style={{ padding: '6px 12px', borderRadius: 'var(--radius)', border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '12px' }}>⚙️</button>
      </div>

      {/* Event List */}
      <div ref={containerRef} style={{ fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
        {events.map((ev, i) => (
          <div key={ev.id || i} style={{
            padding: '6px 12px', borderBottom: '1px solid var(--border)',
            display: 'flex', gap: '12px', alignItems: 'flex-start',
          }}>
            <span className="text-muted" style={{ flexShrink: 0, width: '70px' }}>
              {ev.ts ? new Date(ev.ts).toLocaleTimeString('de-DE') : ''}
            </span>
            <span style={{
              flexShrink: 0, width: '70px',
              color: ev.priority <= 3 ? 'var(--danger)' :
                     ev.priority <= 5 ? 'var(--warning)' : 'var(--text-secondary)',
            }}>
              [{ev.event_type}]
            </span>
            <span style={{ flexShrink: 0, width: '100px' }}>{ev.source}</span>
            <span className="text-muted" style={{
              flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {typeof ev.payload === 'object' ? JSON.stringify(ev.payload) : ev.payload}
            </span>
          </div>
        ))}
        {events.length === 0 && (
          <div className="text-muted p-4" style={{ textAlign: 'center' }}>
            Keine Events
          </div>
        )}
      </div>
    </div>
  )
}
