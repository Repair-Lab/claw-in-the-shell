import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

/**
 * Ghost Manager — KI-Modelle verwalten, Hot-Swap, Kompatibilität
 */
export default function GhostManager() {
  const { settings, schema, update: updateSetting, reset: resetSettings } = useAppSettings('ghost-manager')
  const [showSettings, setShowSettings] = useState(false)
  const [data, setData] = useState({ active_ghosts: [], models: [], roles: [], compatibility: [] })
  const [swapping, setSwapping] = useState(false)
  const [selectedRole, setSelectedRole] = useState(null)
  const [tab, setTab] = useState(settings?.default_tab || 'roles')

  const refreshInterval = settings?.refresh_interval ?? 30000
  const showFitnessScore = settings?.show_fitness_score !== false

  const refresh = useCallback(() => {
    api.ghosts().then(setData).catch(console.error)
  }, [])

  useEffect(() => {
    refresh()
    const handler = () => refresh()
    window.addEventListener('dbai:ghost_swap', handler)
    let interval
    if (settings?.auto_refresh !== false) {
      interval = setInterval(refresh, refreshInterval)
    }
    return () => {
      window.removeEventListener('dbai:ghost_swap', handler)
      if (interval) clearInterval(interval)
    }
  }, [refresh, refreshInterval, settings?.auto_refresh])

  const handleSwap = async (roleName, modelName) => {
    setSwapping(true)
    try {
      await api.swapGhost(roleName, modelName, 'Manueller Wechsel via Ghost Manager')
      setTimeout(refresh, 500)
    } catch (err) {
      alert('Swap fehlgeschlagen: ' + err.message)
    }
    setSwapping(false)
  }

  const getActiveModelForRole = (roleName) => {
    return data.active_ghosts.find(g => g.role_name === roleName)
  }

  const getCompatModels = (roleName) => {
    return data.compatibility
      .filter(c => c.role_name === roleName)
      .sort((a, b) => b.fitness_score - a.fitness_score)
  }

  return (
    <div>
      {showSettings ? (
        <div style={{ padding: '16px' }}>
          <button onClick={() => setShowSettings(false)} style={{ marginBottom: '12px', padding: '4px 12px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 'var(--radius)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '11px' }}>← Zurück</button>
          <AppSettingsPanel schema={schema} settings={settings} onUpdate={updateSetting} onReset={resetSettings} title="Ghost Manager" />
        </div>
      ) : (
      <>
      {/* Tabs */}
      <div className="flex gap-2" style={{ marginBottom: '16px' }}>
        {['roles', 'models', 'history'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '6px 16px', borderRadius: 'var(--radius)',
              border: `1px solid ${tab === t ? 'var(--accent)' : 'var(--border)'}`,
              background: tab === t ? 'rgba(0,255,204,0.1)' : 'transparent',
              color: tab === t ? 'var(--accent)' : 'var(--text-secondary)',
              cursor: 'pointer', fontSize: '12px',
            }}
          >
            {t === 'roles' ? '🎭 Rollen' : t === 'models' ? '🧠 Modelle' : '📜 History'}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <button onClick={() => setShowSettings(true)} style={{ padding: '6px 12px', borderRadius: 'var(--radius)', border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '12px' }}>⚙️</button>
      </div>

      {/* Roles View */}
      {tab === 'roles' && (
        <div className="ghost-grid">
          {data.roles.map(role => {
            const active = getActiveModelForRole(role.name)
            const compat = getCompatModels(role.name)

            return (
              <div
                key={role.id}
                className={`ghost-card ${active ? 'active' : ''}`}
                onClick={() => setSelectedRole(selectedRole === role.name ? null : role.name)}
              >
                <div className="role-icon">{role.icon}</div>
                <div className="role-name" style={{ color: role.color }}>
                  {role.display_name}
                </div>
                <div className="text-xs text-muted" style={{ marginBottom: '8px' }}>
                  {role.description}
                </div>

                {active ? (
                  <>
                    <div className="model-name">🧠 {active.model_display}</div>
                    <span className="status active">● Aktiv</span>
                  </>
                ) : (
                  <span className="status inactive">○ Kein Ghost</span>
                )}

                {/* Expanded: Model Selection */}
                {selectedRole === role.name && (
                  <div style={{
                    marginTop: '12px', paddingTop: '12px',
                    borderTop: '1px solid var(--border)',
                  }}>
                    <div className="text-xs text-muted" style={{ marginBottom: '8px' }}>
                      Ghost zuweisen:
                    </div>
                    {compat.map(c => (
                      <div
                        key={c.model_name}
                        onClick={(e) => {
                          e.stopPropagation()
                          handleSwap(role.name, c.model_name)
                        }}
                        style={{
                          padding: '6px 10px', marginBottom: '4px',
                          borderRadius: 'var(--radius)',
                          border: '1px solid var(--border)',
                          cursor: swapping ? 'wait' : 'pointer',
                          fontSize: '12px',
                          display: 'flex', justifyContent: 'space-between',
                          alignItems: 'center',
                          background: active?.model_name === c.model_name
                            ? 'rgba(0,255,204,0.08)' : 'transparent',
                        }}
                      >
                        <span>{c.model_name}</span>
                        {showFitnessScore && (
                        <span style={{
                          color: c.fitness_score > 0.8 ? 'var(--success)' :
                                 c.fitness_score > 0.5 ? 'var(--warning)' : 'var(--danger)',
                          fontFamily: 'var(--font-mono)',
                        }}>
                          {(c.fitness_score * 100).toFixed(0)}%
                        </span>
                        )}
                      </div>
                    ))}
                    {compat.length === 0 && (
                      <div className="text-xs text-muted">Keine kompatiblen Modelle</div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Models View */}
      {tab === 'models' && (
        <div className="ghost-grid">
          {data.models.map(model => (
            <div key={model.id} className="ghost-card">
              <div className="role-name">{model.display_name}</div>
              <div className="model-name">{model.name}</div>
              <div className="flex gap-2 items-center mt-2" style={{ flexWrap: 'wrap' }}>
                <span className={`status ${model.is_loaded ? 'active' : 'inactive'}`}>
                  {model.is_loaded ? '● Geladen' : '○ Verfügbar'}
                </span>
                <span className="text-xs text-mono text-muted">
                  {model.parameter_count} · {model.quantization || 'F16'}
                </span>
              </div>
              <div className="text-xs text-muted mt-2">
                Provider: {model.provider} · Ctx: {model.context_size}
                {model.requires_gpu && ' · 🎮 GPU'}
              </div>
              <div className="text-xs text-muted mt-2">
                {model.total_requests} Anfragen · ⌀ {model.avg_latency_ms?.toFixed(0) || 0}ms
              </div>
              {model.capabilities && (
                <div className="flex gap-2 mt-2" style={{ flexWrap: 'wrap' }}>
                  {model.capabilities.map(cap => (
                    <span key={cap} style={{
                      padding: '1px 6px', fontSize: '9px',
                      borderRadius: '8px',
                      background: 'rgba(68,136,255,0.15)',
                      color: 'var(--info)',
                    }}>{cap}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* History View */}
      {tab === 'history' && <GhostHistory />}
      </>
      )}
    </div>
  )
}

function GhostHistory() {
  const [history, setHistory] = useState([])
  useEffect(() => {
    api.ghostHistory(30).then(setHistory).catch(console.error)
  }, [])

  return (
    <div style={{ fontSize: '12px' }}>
      {history.map((h, i) => (
        <div key={i} style={{
          padding: '10px 12px', borderBottom: '1px solid var(--border)',
          display: 'flex', gap: '12px', alignItems: 'center',
        }}>
          <span>{h.success ? '✅' : '❌'}</span>
          <div style={{ flex: 1 }}>
            <div>
              <strong>{h.role_name}</strong>: {h.old_model_name || '—'} → {h.new_model_name}
            </div>
            <div className="text-xs text-muted">
              {h.swap_reason} · {h.swap_duration_ms}ms · {h.initiated_by}
            </div>
          </div>
          <div className="text-xs text-muted">
            {new Date(h.ts).toLocaleString('de-DE')}
          </div>
        </div>
      ))}
      {history.length === 0 && (
        <div className="text-muted p-4">Keine Ghost-Wechsel protokolliert</div>
      )}
    </div>
  )
}
