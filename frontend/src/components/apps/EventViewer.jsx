import React, { useState, useEffect, useRef } from 'react'
import { api } from '../../api'

/**
 * Event Viewer — Live-Stream aller System-Events
 */
export default function EventViewer() {
  const [events, setEvents] = useState([])
  const [filter, setFilter] = useState('')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const containerRef = useRef(null)

  const refresh = () => {
    api.events(200, filter || null).then(setEvents).catch(() => {})
  }

  useEffect(() => {
    refresh()
    if (autoRefresh) {
      const interval = setInterval(refresh, 3000)
      return () => clearInterval(interval)
    }
  }, [filter, autoRefresh])

  // Listen for new events via WebSocket
  useEffect(() => {
    const handler = (e) => {
      setEvents(prev => [e.detail, ...prev].slice(0, 200))
    }
    window.addEventListener('dbai:event', handler)
    return () => window.removeEventListener('dbai:event', handler)
  }, [])

  const eventTypes = ['', 'keyboard', 'network', 'disk', 'power', 'thermal',
                       'process', 'system', 'error', 'llm']

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
