import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'

/**
 * LLM Manager — Modelle verwalten, downloaden, benchmarken, konfigurieren
 * Erweiterte Ansicht gegenüber GhostManager: Fokus auf Model-Lifecycle
 */
export default function LLMManager() {
  const [tab, setTab] = useState('models') // models, benchmarks, config, downloads
  const [models, setModels] = useState([])
  const [benchmarks, setBenchmarks] = useState([])
  const [config, setConfig] = useState([])
  const [activeGhosts, setActiveGhosts] = useState([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const data = await api.llmStatus()
      setModels(data.models || [])
      setBenchmarks(data.benchmarks || [])
      setConfig(data.config || [])
      setActiveGhosts(data.active_ghosts || [])
    } catch (err) {
      console.error('LLM-Daten laden fehlgeschlagen:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    window.addEventListener('dbai:ghost_swap', refresh)
    return () => window.removeEventListener('dbai:ghost_swap', refresh)
  }, [refresh])

  const handleBenchmark = async (modelName) => {
    try {
      await api.llmBenchmark(modelName)
      setTimeout(refresh, 2000)
    } catch (err) {
      alert('Benchmark fehlgeschlagen: ' + err.message)
    }
  }

  const handleUpdateConfig = async (key, value) => {
    try {
      await api.llmUpdateConfig(key, value)
      setTimeout(refresh, 500)
    } catch (err) {
      alert('Konfiguration fehlgeschlagen: ' + err.message)
    }
  }

  const providerColors = {
    'llama.cpp': 'var(--accent)',
    'vllm': '#ff6600',
    'ollama': '#00aaff',
    'openai': '#74aa9c',
  }

  if (loading) return <div style={{ padding: 20, color: 'var(--text-secondary)' }}>Lade LLM-Daten…</div>

  // Stats
  const totalModels = models.length
  const gpuModels = models.filter(m => m.requires_gpu).length
  const cpuModels = totalModels - gpuModels
  const totalVRAM = models.reduce((sum, m) => sum + (m.required_vram_mb || 0), 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', fontFamily: 'var(--font-sans)', fontSize: '13px' }}>
      {/* Header */}
      <div style={{
        display: 'flex', gap: '16px', padding: '12px 16px',
        borderBottom: '1px solid var(--border)', alignItems: 'center',
      }}>
        {/* Stats */}
        <div style={{ display: 'flex', gap: '20px' }}>
          <MiniStat icon="🧠" label="Modelle" value={totalModels} />
          <MiniStat icon="🎮" label="GPU" value={gpuModels} />
          <MiniStat icon="💻" label="CPU" value={cpuModels} />
          <MiniStat icon="📊" label="VRAM ges." value={`${(totalVRAM / 1024).toFixed(1)} GB`} />
          <MiniStat icon="👻" label="Aktiv" value={activeGhosts.length} color="var(--success)" />
        </div>

        <div style={{ flex: 1 }} />

        {/* Tabs */}
        {['models', 'benchmarks', 'config'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '6px 14px', borderRadius: 'var(--radius)',
            border: `1px solid ${tab === t ? 'var(--accent)' : 'var(--border)'}`,
            background: tab === t ? 'rgba(0,255,204,0.1)' : 'transparent',
            color: tab === t ? 'var(--accent)' : 'var(--text-secondary)',
            cursor: 'pointer', fontSize: '12px',
          }}>
            {t === 'models' ? '🧠 Modelle' : t === 'benchmarks' ? '📊 Benchmarks' : '⚙️ Konfiguration'}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
        {/* Models Tab */}
        {tab === 'models' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {models.map(model => {
              const isActive = activeGhosts.some(g => g.model_name === model.name)
              return (
                <div key={model.id} style={{
                  display: 'flex', alignItems: 'center', gap: '16px',
                  padding: '14px 16px', background: 'var(--bg-surface)',
                  border: `1px solid ${isActive ? 'var(--accent)' : 'var(--border)'}`,
                  borderRadius: '8px',
                  borderLeft: `3px solid ${providerColors[model.provider] || 'var(--border)'}`,
                }}>
                  {/* Model Info */}
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-primary)' }}>
                        {model.display_name || model.name}
                      </span>
                      {isActive && (
                        <span style={{
                          fontSize: '10px', padding: '2px 8px', borderRadius: '10px',
                          background: 'rgba(0,255,204,0.15)', color: 'var(--accent)',
                          border: '1px solid rgba(0,255,204,0.3)',
                        }}>● AKTIV</span>
                      )}
                    </div>
                    <div style={{
                      display: 'flex', gap: '12px', marginTop: '6px', fontSize: '11px',
                      color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)',
                    }}>
                      <span>📦 {model.parameter_count}</span>
                      <span>🔧 {model.quantization}</span>
                      <span>📝 {model.context_size?.toLocaleString() || '?'} ctx</span>
                      <span>🏷️ {model.provider}</span>
                      {model.requires_gpu && <span style={{ color: 'var(--warning)' }}>🎮 GPU</span>}
                    </div>
                    {/* Capabilities */}
                    <div style={{ display: 'flex', gap: '4px', marginTop: '6px', flexWrap: 'wrap' }}>
                      {(model.capabilities || []).map(cap => (
                        <span key={cap} style={{
                          fontSize: '10px', padding: '1px 6px', borderRadius: '8px',
                          background: 'var(--bg-elevated)', color: 'var(--text-secondary)',
                          border: '1px solid var(--border)',
                        }}>{cap}</span>
                      ))}
                    </div>
                  </div>

                  {/* Resource Requirements */}
                  <div style={{
                    display: 'flex', flexDirection: 'column', alignItems: 'flex-end',
                    gap: '4px', minWidth: '120px',
                  }}>
                    <ResourceBar label="VRAM" value={model.required_vram_mb} max={96000} unit="MB" color="var(--accent)" />
                    <ResourceBar label="RAM" value={model.required_ram_mb} max={128000} unit="MB" color="var(--info)" />
                  </div>

                  {/* Actions */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <button onClick={() => handleBenchmark(model.name)} style={{
                      padding: '5px 12px', borderRadius: 'var(--radius)',
                      background: 'rgba(0,255,204,0.08)', border: '1px solid var(--accent)',
                      color: 'var(--accent)', cursor: 'pointer', fontSize: '11px',
                      whiteSpace: 'nowrap',
                    }}>
                      📊 Benchmark
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Benchmarks Tab */}
        {tab === 'benchmarks' && (
          <div>
            <h3 style={{ color: 'var(--accent)', marginTop: 0, marginBottom: '16px' }}>Benchmark-Ergebnisse</h3>
            {benchmarks.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
                Noch keine Benchmarks durchgeführt. Klicke bei einem Modell auf "📊 Benchmark".
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    {['Modell', 'Tokens/s', 'TTFT (ms)', 'VRAM (MB)', 'Datum'].map(h => (
                      <th key={h} style={{
                        textAlign: 'left', padding: '8px', color: 'var(--accent)',
                        fontFamily: 'var(--font-mono)', fontSize: '11px',
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {benchmarks.map((b, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '8px', fontWeight: 500 }}>{b.model_display || b.model_name}</td>
                      <td style={{ padding: '8px', fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>
                        {b.tokens_per_second?.toFixed(1) || '—'}
                      </td>
                      <td style={{ padding: '8px', fontFamily: 'var(--font-mono)' }}>
                        {b.time_to_first_token_ms?.toFixed(0) || '—'}
                      </td>
                      <td style={{ padding: '8px', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                        {b.gpu_vram_mb || '—'}
                      </td>
                      <td style={{ padding: '8px', fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                        {b.benchmark_date ? new Date(b.benchmark_date).toLocaleDateString('de-DE') : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Config Tab */}
        {tab === 'config' && (
          <div>
            <h3 style={{ color: 'var(--accent)', marginTop: 0, marginBottom: '16px' }}>LLM-Konfiguration</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {config.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
                  Keine LLM-Konfiguration vorhanden.
                </div>
              ) : config.map((c, i) => (
                <div key={i} style={{
                  padding: '12px 14px', background: 'var(--bg-surface)',
                  border: '1px solid var(--border)', borderRadius: 'var(--radius)',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--accent)' }}>
                        {c.key}
                      </span>
                      {c.description && (
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                          {c.description}
                        </div>
                      )}
                    </div>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-primary)' }}>
                      {typeof c.value === 'object' ? JSON.stringify(c.value) : String(c.value ?? '')}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// Hilfs-Komponenten
function MiniStat({ icon, label, value, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <span style={{ fontSize: '14px' }}>{icon}</span>
      <div>
        <div style={{ fontSize: '15px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: color || 'var(--text-primary)' }}>{value}</div>
        <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>{label}</div>
      </div>
    </div>
  )
}

function ResourceBar({ label, value, max, unit, color }) {
  const pct = Math.min((value || 0) / max * 100, 100)
  return (
    <div style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', marginBottom: '2px' }}>
        <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
        <span style={{ fontFamily: 'var(--font-mono)', color }}>{value?.toLocaleString() || 0} {unit}</span>
      </div>
      <div style={{ width: '120px', height: '4px', background: 'var(--bg-elevated)', borderRadius: '2px', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: '2px' }} />
      </div>
    </div>
  )
}

function QualityBar({ value }) {
  if (value == null) return <span style={{ color: 'var(--text-secondary)' }}>—</span>
  const pct = Math.round(value * 100)
  const color = pct > 70 ? 'var(--success)' : pct > 40 ? 'var(--warning)' : 'var(--danger)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <div style={{ width: '60px', height: '4px', background: 'var(--bg-elevated)', borderRadius: '2px', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color }} />
      </div>
      <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color }}>{pct}%</span>
    </div>
  )
}
