import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'

/**
 * Health Dashboard — Self-Healing-Status, Alert-Regeln, Telemetrie
 */
export default function HealthDashboard() {
  const [health, setHealth] = useState([])
  const [healResult, setHealResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(() => {
    api.health().then(setHealth).catch(() => {})
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 10000)
    return () => clearInterval(interval)
  }, [refresh])

  const handleSelfHeal = async () => {
    setLoading(true)
    try {
      const result = await api.selfHeal()
      setHealResult(result)
      refresh()
    } catch (err) {
      setHealResult({ error: err.message })
    }
    setLoading(false)
  }

  const okCount = health.filter(h => h.status === 'ok').length
  const warnCount = health.filter(h => h.status === 'warning').length
  const critCount = health.filter(h => h.status === 'critical').length

  return (
    <div>
      {/* Summary */}
      <div className="flex gap-4" style={{ marginBottom: '16px' }}>
        <div className="sys-card" style={{ flex: 1, textAlign: 'center' }}>
          <h3>Gesund</h3>
          <div className="value" style={{ color: 'var(--success)' }}>{okCount}</div>
        </div>
        <div className="sys-card" style={{ flex: 1, textAlign: 'center' }}>
          <h3>Warnungen</h3>
          <div className="value" style={{ color: 'var(--warning)' }}>{warnCount}</div>
        </div>
        <div className="sys-card" style={{ flex: 1, textAlign: 'center' }}>
          <h3>Kritisch</h3>
          <div className="value" style={{ color: 'var(--danger)' }}>{critCount}</div>
        </div>
      </div>

      {/* Health Checks */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '16px' }}>
        {health.map((check, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', gap: '12px',
            padding: '10px 14px', background: 'var(--bg-surface)',
            border: '1px solid var(--border)', borderRadius: 'var(--radius)',
            borderLeft: `3px solid ${
              check.status === 'ok' ? 'var(--success)' :
              check.status === 'warning' ? 'var(--warning)' : 'var(--danger)'
            }`,
          }}>
            <span style={{ fontSize: '16px' }}>
              {check.status === 'ok' ? '✅' : check.status === 'warning' ? '⚠️' : '❌'}
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 500, fontSize: '12px' }}>{check.check_name}</div>
              <div className="text-xs text-muted">{check.message}</div>
            </div>
            {check.metric_value != null && (
              <div className="text-mono" style={{
                fontSize: '14px',
                color: check.status === 'ok' ? 'var(--accent)' :
                       check.status === 'warning' ? 'var(--warning)' : 'var(--danger)',
              }}>
                {check.metric_value}{check.metric_unit ? ` ${check.metric_unit}` : ''}
              </div>
            )}
            {check.duration_ms != null && (
              <span className="text-xs text-muted">{check.duration_ms}ms</span>
            )}
          </div>
        ))}
      </div>

      {/* Self-Heal Button */}
      <button
        onClick={handleSelfHeal}
        disabled={loading}
        style={{
          padding: '10px 24px',
          background: loading ? 'var(--bg-elevated)' : 'rgba(0,255,204,0.1)',
          border: '1px solid var(--accent)',
          borderRadius: 'var(--radius)',
          color: 'var(--accent)',
          cursor: loading ? 'wait' : 'pointer',
          fontSize: '13px', fontWeight: 600,
        }}
      >
        {loading ? '⏳ Self-Healing läuft...' : '🔧 Self-Heal ausführen'}
      </button>

      {/* Self-Heal Result */}
      {healResult && (
        <div style={{
          marginTop: '16px', padding: '12px',
          background: 'var(--bg-surface)', borderRadius: 'var(--radius)',
          border: '1px solid var(--border)',
          fontFamily: 'var(--font-mono)', fontSize: '11px',
          whiteSpace: 'pre-wrap', maxHeight: '200px', overflow: 'auto',
        }}>
          {JSON.stringify(healResult, null, 2)}
        </div>
      )}
    </div>
  )
}
