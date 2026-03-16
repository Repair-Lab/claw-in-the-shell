import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'

export default function AnomalyDetector() {
  const [detections, setDetections] = useState([])
  const [models, setModels] = useState([])
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const severity = filter !== 'all' ? filter : undefined
      const [d, m] = await Promise.all([api.anomalyDetections(50, severity), api.anomalyModels()])
      setDetections(d.detections || [])
      setModels(m.models || [])
    } catch { /* */ }
    finally { setLoading(false) }
  }, [filter])

  useEffect(() => { load() }, [load])

  const sevColors = { info: '#4488ff', warning: '#ffaa00', critical: '#ff4444', resolved: '#00ffcc' }

  const S = {
    container: { display: 'flex', flexDirection: 'column', height: '100%', background: '#0a0a14', color: '#c8d6e5', padding: '16px', overflow: 'auto' },
    h: { color: '#00ffcc', fontSize: '18px', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' },
    card: { background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '8px', padding: '12px', marginBottom: '8px' },
    btn: { padding: '5px 12px', border: '1px solid #1a2a3a', background: 'transparent', color: '#d4d4d4', borderRadius: '6px', cursor: 'pointer', fontSize: '11px' },
    activeBtn: { padding: '5px 12px', border: '1px solid #00ffcc', background: 'rgba(0,255,204,0.1)', color: '#00ffcc', borderRadius: '6px', cursor: 'pointer', fontSize: '11px' },
    badge: (sev) => ({ padding: '2px 8px', borderRadius: '10px', fontSize: '10px', fontWeight: 600, background: `${sevColors[sev] || '#556'}22`, color: sevColors[sev] || '#556' }),
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '8px', marginBottom: '16px' },
  }

  const stats = {
    total: detections.length,
    critical: detections.filter(d => d.severity === 'critical').length,
    warning: detections.filter(d => d.severity === 'warning').length,
    recent: detections.filter(d => { const h = (Date.now() - new Date(d.detected_at).getTime()) / 3600000; return h < 1 }).length,
  }

  return (
    <div style={S.container}>
      <div style={S.h}><span>🔬</span> Anomalie-Erkennung</div>

      <div style={S.grid}>
        {[
          { label: 'Gesamt', val: stats.total, color: '#4488ff' },
          { label: 'Kritisch', val: stats.critical, color: '#ff4444' },
          { label: 'Warnungen', val: stats.warning, color: '#ffaa00' },
          { label: 'Letzte Stunde', val: stats.recent, color: '#00ffcc' },
        ].map((s, i) => (
          <div key={i} style={S.card}>
            <div style={{ color: '#556', fontSize: '11px' }}>{s.label}</div>
            <div style={{ color: s.color, fontSize: '22px', fontWeight: 700 }}>{s.val}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '6px', marginBottom: '12px', flexWrap: 'wrap' }}>
        {['all', 'info', 'warning', 'critical', 'resolved'].map(f => (
          <button key={f} style={filter === f ? S.activeBtn : S.btn} onClick={() => setFilter(f)}>
            {f === 'all' ? 'Alle' : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
        <button style={S.btn} onClick={load}>🔄</button>
      </div>

      {models.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <div style={{ color: '#6688aa', fontSize: '12px', marginBottom: '6px' }}>Modelle:</div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {models.map((m, i) => (
              <div key={i} style={{ ...S.card, display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '6px 10px' }}>
                <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: m.is_active ? '#00ffcc' : '#444' }} />
                <span style={{ color: '#d4d4d4', fontSize: '12px' }}>{m.model_name}</span>
                <span style={{ color: '#556', fontSize: '10px' }}>σ={m.config?.threshold || '?'}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '20px', color: '#556' }}>⏳ Lade...</div>
      ) : detections.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '30px', color: '#334' }}>Keine Anomalien erkannt — System läuft normal ✓</div>
      ) : (
        detections.map((d, i) => (
          <div key={i} style={S.card}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                  <span style={S.badge(d.severity)}>{d.severity}</span>
                  <span style={{ color: '#d4d4d4', fontSize: '13px', fontWeight: 600 }}>{d.metric_name}</span>
                </div>
                <div style={{ color: '#556', fontSize: '11px' }}>{d.description}</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ color: '#00ccff', fontSize: '16px', fontWeight: 700 }}>{d.anomaly_score?.toFixed(2)}</div>
                <div style={{ color: '#556', fontSize: '10px' }}>Score</div>
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '6px', fontSize: '10px', color: '#445' }}>
              <span>Wert: {d.metric_value}</span>
              <span>Erwartet: {d.expected_value?.toFixed(1)}</span>
              <span>{new Date(d.detected_at).toLocaleString()}</span>
            </div>
          </div>
        ))
      )}
    </div>
  )
}
