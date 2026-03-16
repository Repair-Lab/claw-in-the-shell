import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'

export default function SynapticViewer() {
  const [stats, setStats] = useState(null)
  const [memories, setMemories] = useState([])
  const [filter, setFilter] = useState('all')
  const [view, setView] = useState('timeline')

  const loadStats = useCallback(async () => {
    try { setStats(await api.synapticStats()) } catch { /* ignore */ }
  }, [])

  const loadMemories = useCallback(async () => {
    try {
      const result = await api.synapticSearch(filter === 'all' ? null : filter)
      setMemories(result.memories || [])
    } catch { /* ignore */ }
  }, [filter])

  useEffect(() => { loadStats(); loadMemories() }, [loadStats, loadMemories])

  const consolidate = async () => {
    try {
      const result = await api.synapticConsolidate()
      loadStats()
      alert(`${result.consolidated || 0} Memories konsolidiert`)
    } catch { /* ignore */ }
  }

  const typeColors = {
    error: '#ff4444', security: '#ff6600', ghost_thought: '#cc44ff',
    user_action: '#4488ff', config_change: '#ffaa00', system_event: '#00ccff',
    performance: '#66ff99', hardware: '#ff8844', network: '#44ddff',
    login: '#00ffcc', file_change: '#8899aa', process: '#556',
  }

  const importanceBar = (v) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
      <div style={{ width: '40px', height: '4px', background: '#111828', borderRadius: '2px', overflow: 'hidden' }}>
        <div style={{ width: `${v * 100}%`, height: '100%', background: v > 0.7 ? '#ff4444' : v > 0.4 ? '#ffaa00' : '#00ffcc', borderRadius: '2px' }} />
      </div>
      <span style={{ fontSize: '10px', color: '#556' }}>{(v * 100).toFixed(0)}%</span>
    </div>
  )

  const valenceIndicator = (v) => {
    const color = v > 0.3 ? '#00ffcc' : v < -0.3 ? '#ff4444' : '#556'
    return <span style={{ color, fontSize: '12px' }}>{v > 0.3 ? '😊' : v < -0.3 ? '😟' : '😐'}</span>
  }

  const S = {
    container: { display: 'flex', flexDirection: 'column', height: '100%', background: '#0a0a14', color: '#c8d6e5', padding: '16px', overflow: 'auto' },
    h: { color: '#00ffcc', fontSize: '18px', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' },
    card: { background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '8px', padding: '12px', marginBottom: '8px' },
    btn: { padding: '6px 16px', border: '1px solid #00ffcc', background: 'transparent', color: '#00ffcc', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' },
    tabs: { display: 'flex', gap: '4px', marginBottom: '16px', flexWrap: 'wrap' },
    tab: (a) => ({ padding: '4px 10px', borderRadius: '4px', cursor: 'pointer', fontSize: '11px', background: a ? '#1a2a3a' : 'transparent', color: a ? '#00ffcc' : '#556', border: '1px solid ' + (a ? '#00ffcc33' : 'transparent') }),
  }

  const eventTypes = ['all', 'error', 'security', 'ghost_thought', 'user_action', 'system_event', 'performance', 'hardware', 'login']

  return (
    <div style={S.container}>
      <div style={S.h}><span>🧠</span> Synaptic Memory</div>

      {stats?.database && (
        <div style={{ ...S.card, display: 'flex', justifyContent: 'space-around', textAlign: 'center', marginBottom: '16px' }}>
          <div>
            <div style={{ color: '#00ffcc', fontSize: '22px', fontWeight: 700 }}>{stats.database.total || 0}</div>
            <div style={{ color: '#556', fontSize: '10px' }}>Gesamt</div>
          </div>
          <div>
            <div style={{ color: '#ffaa00', fontSize: '22px', fontWeight: 700 }}>{stats.database.unconsolidated || 0}</div>
            <div style={{ color: '#556', fontSize: '10px' }}>Kurzzeit</div>
          </div>
          <div>
            <div style={{ color: '#4488ff', fontSize: '22px', fontWeight: 700 }}>{stats.database.consolidated || 0}</div>
            <div style={{ color: '#556', fontSize: '10px' }}>Langzeit</div>
          </div>
          <div>
            <div style={{ color: '#cc44ff', fontSize: '22px', fontWeight: 700 }}>
              {stats.database.avg_importance ? (stats.database.avg_importance * 100).toFixed(0) + '%' : '—'}
            </div>
            <div style={{ color: '#556', fontSize: '10px' }}>Ø Wichtigkeit</div>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div style={S.tabs}>
          {eventTypes.map(t => (
            <div key={t} style={S.tab(filter === t)} onClick={() => setFilter(t)}>
              <span style={{ color: typeColors[t] || '#556' }}>●</span> {t === 'all' ? 'Alle' : t}
            </div>
          ))}
        </div>
        <button style={S.btn} onClick={consolidate}>🔄 Konsolidieren</button>
      </div>

      {memories.map((m, i) => (
        <div key={i} style={{ ...S.card, borderLeft: `3px solid ${typeColors[m.event_type] || '#334'}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <span style={{ color: typeColors[m.event_type] || '#556', fontSize: '11px', padding: '1px 6px', background: '#111828', borderRadius: '3px' }}>
                  {m.event_type}
                </span>
                <span style={{ color: '#d4d4d4', fontSize: '13px', fontWeight: 600 }}>{m.title}</span>
                {valenceIndicator(m.emotional_valence || 0)}
              </div>
              <div style={{ color: '#6688aa', fontSize: '12px', marginBottom: '6px' }}>{m.content?.substring(0, 200)}</div>
              <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                <span style={{ color: '#334', fontSize: '10px' }}>{m.source}</span>
                <span style={{ color: '#334', fontSize: '10px' }}>{new Date(m.created_at).toLocaleString('de-DE')}</span>
                {importanceBar(m.importance || 0)}
              </div>
            </div>
          </div>
        </div>
      ))}

      {memories.length === 0 && (
        <div style={{ textAlign: 'center', color: '#334', padding: '40px', fontSize: '14px' }}>
          Keine Synapsen gefunden. Die Pipeline sammelt automatisch Events.
        </div>
      )}
    </div>
  )
}
