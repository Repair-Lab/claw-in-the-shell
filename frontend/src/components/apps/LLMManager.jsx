import React, { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../../api'

/**
 * LLMManager v3 — Agent Orchestration & Mission Control
 * 
 * OpenClaw-style agent orchestration nativ in DBAI:
 * - GPU-basierte Agenten-Instanzen erstellen & dirigieren
 * - Modelle aus ghost_models verschiedenen Rollen zuweisen
 * - Multi-GPU / Multi-Instanz parallel betreiben
 * - Cron-Jobs für automatisierte Aufgaben
 * - Pipeline/Chain-Konfiguration
 * - Live GPU-Monitoring (VRAM, Temp, Auslastung)
 * - Modell-Benchmark & Disk-Scanner
 */

/* ─── Helpers ────────────────────────────────────────── */
const formatBytes = (b) => {
  if (!b && b !== 0) return '—'
  if (b >= 1073741824) return (b / 1073741824).toFixed(1) + ' GB'
  if (b >= 1048576) return (b / 1048576).toFixed(1) + ' MB'
  if (b >= 1024) return (b / 1024).toFixed(1) + ' KB'
  return b + ' B'
}

const formatMB = (mb) => {
  if (!mb && mb !== 0) return '—'
  if (mb >= 1024) return (mb / 1024).toFixed(1) + ' GB'
  return mb + ' MB'
}

const STATE_COLORS = {
  running: '#00ff88',
  starting: '#ffaa00',
  stopped: '#888',
  error: '#ff4444',
  stopping: '#ff8800',
}

const STATE_LABELS = {
  running: 'Läuft',
  starting: 'Startet…',
  stopped: 'Gestoppt',
  error: 'Fehler',
  stopping: 'Stoppt…',
}

const BACKENDS = [
  { value: 'llama.cpp', label: 'llama.cpp', icon: '🦙' },
  { value: 'vllm', label: 'vLLM', icon: '⚡' },
  { value: 'ollama', label: 'Ollama', icon: '🐪' },
  { value: 'custom', label: 'Benutzerdefiniert', icon: '🔧' },
]

const DEFAULT_WEBUIS = [
  { name: 'Ollama WebUI', icon: '🐪', desc: 'Chat-Interface für Ollama', port: 11434, url: 'http://localhost:3080' },
  { name: 'ComfyUI', icon: '🎨', desc: 'Stable Diffusion Node-Editor', port: 8188, url: 'http://localhost:8188' },
  { name: 'text-generation-webui', icon: '💬', desc: 'Gradio LLM Interface', port: 7860, url: 'http://localhost:7860' },
  { name: 'Stable Diffusion WebUI', icon: '🖼️', desc: 'AUTOMATIC1111 Forge', port: 7861, url: 'http://localhost:7861' },
  { name: 'LocalAI', icon: '🧠', desc: 'Drop-in OpenAI-Ersatz', port: 8080, url: 'http://localhost:8080' },
  { name: 'LM Studio', icon: '📡', desc: 'Desktop LLM Server', port: 1234, url: 'http://localhost:1234' },
  { name: 'Jan.ai', icon: '🤖', desc: 'Offline-first AI', port: 1337, url: 'http://localhost:1337' },
  { name: 'vLLM Server', icon: '⚡', desc: 'High-Throughput Serving', port: 8000, url: 'http://localhost:8000' },
]

/* ─── Sub-Components ─────────────────────────────────── */
function VramBar({ used, total, label, height = 18 }) {
  const pct = total > 0 ? Math.min((used / total) * 100, 100) : 0
  const color = pct > 90 ? '#ff4444' : pct > 70 ? '#ffaa00' : '#00ff88'
  return (
    <div style={{ width: '100%' }}>
      {label && <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '2px' }}>{label}</div>}
      <div style={{ height, background: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden', position: 'relative' }}>
        <div style={{ height: '100%', width: pct + '%', background: `linear-gradient(90deg, ${color}44, ${color})`, borderRadius: '4px', transition: 'width 0.5s' }} />
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', textShadow: '0 1px 2px rgba(0,0,0,0.8)' }}>
          {formatMB(used)} / {formatMB(total)} ({pct.toFixed(0)}%)
        </div>
      </div>
    </div>
  )
}

function QualityBar({ value, max = 100, color = '#00ffc8' }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <div style={{ width: '80px', height: '6px', background: 'rgba(255,255,255,0.08)', borderRadius: '3px', overflow: 'hidden' }}>
      <div style={{ height: '100%', width: pct + '%', background: color, borderRadius: '3px', transition: 'width 0.3s' }} />
    </div>
  )
}

function StateDot({ state }) {
  return (
    <span style={{
      display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%',
      background: STATE_COLORS[state] || '#888',
      boxShadow: state === 'running' ? `0 0 6px ${STATE_COLORS.running}` : 'none',
      animation: state === 'starting' ? 'pulse 1s infinite' : 'none',
    }} />
  )
}

/* ═══════════════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════════════ */
export default function LLMManager({ windowId, onOpenWindow }) {
  // ─── Tab-State ────────────────────
  const [tab, setTab] = useState('agents')

  // ─── Agents ───────────────────────
  const [instances, setInstances] = useState([])
  const [gpuInfo, setGpuInfo] = useState([])
  const [roles, setRoles] = useState([])
  const [ghostModels, setGhostModels] = useState([])
  const [showCreate, setShowCreate] = useState(false)
  const [newInst, setNewInst] = useState({
    model_id: '', role_id: '', gpu_index: 0, backend: 'ollama',
    context_size: 4096, n_gpu_layers: 99, threads: 8, batch_size: 512,
  })

  // ─── Models / Scanner ─────────────
  const [models, setModels] = useState([])
  const [scanResults, setScanResults] = useState([])
  const [scanning, setScanning] = useState(false)
  const [scanPaths, setScanPaths] = useState('/home,/opt,/mnt,/data')

  // ─── Pipelines (Chains) ───────────
  const [chains, setChains] = useState([])
  const [newChainName, setNewChainName] = useState('')

  // ─── Jobs ─────────────────────────
  const [jobs, setJobs] = useState([])
  const [showCreateJob, setShowCreateJob] = useState(false)
  const [newJob, setNewJob] = useState({
    name: '', cron_expr: '*/30 * * * *', instance_id: '', task_prompt: '', enabled: true,
  })

  // ─── Tasks (per instance) ────────
  const [selectedInstance, setSelectedInstance] = useState(null)
  const [tasks, setTasks] = useState([])
  const [showCreateTask, setShowCreateTask] = useState(false)
  const [newTask, setNewTask] = useState({
    task_type: 'chat', name: '', description: '', system_prompt: '', priority: 5,
  })

  // ─── Benchmarks ───────────────────
  const [benchmarks, setBenchmarks] = useState([])

  // ─── Global ───────────────────────
  const [loading, setLoading] = useState(true)
  const [confirmAction, setConfirmAction] = useState(null)
  const refreshRef = useRef(null)

  /* ─── LOAD FUNCTIONS ─────────────────────────────── */
  const loadInstances = useCallback(async () => {
    try {
      const data = await api.agentsInstances()
      setInstances(data || [])
    } catch (e) { console.error('Instanzen laden:', e) }
  }, [])

  const loadGpu = useCallback(async () => {
    try {
      const data = await api.agentsGpu()
      // Server returns {gpus: [...]} with fields: index, vram_total_mb, etc.
      const gpus = (data?.gpus || data || []).map(g => ({
        gpu_index: g.index ?? g.gpu_index ?? 0,
        name: g.name || 'GPU',
        memory_total_mb: g.vram_total_mb ?? g.memory_total_mb ?? 0,
        memory_used_mb: g.vram_used_mb ?? g.memory_used_mb ?? 0,
        memory_free_mb: g.vram_free_mb ?? g.memory_free_mb ?? 0,
        utilization: g.utilization_pct ?? g.utilization ?? 0,
        temperature: g.temp_c ?? g.temperature ?? 0,
        driver_version: g.driver_version || '',
        cuda_version: g.cuda_version || '',
      }))
      setGpuInfo(gpus)
    } catch (e) { console.error('GPU-Info laden:', e) }
  }, [])

  const loadRoles = useCallback(async () => {
    try {
      const data = await api.agentsRoles()
      setRoles(data || [])
    } catch (e) { console.error('Rollen laden:', e) }
  }, [])

  const loadGhostModels = useCallback(async () => {
    try {
      const raw = await api.llmModels()
      // Normalize field names: size→vram_required_mb, status→state, path→model_path
      const data = (raw || []).map(m => ({
        ...m,
        vram_required_mb: m.vram_required_mb || (m.size ? Math.round(m.size / 1048576) : 0),
        state: m.state || m.status || 'inactive',
        model_path: m.model_path || m.path || '',
        model_format: m.model_format || m.format || '',
        param_count: m.param_count || m.parameters || '',
      }))
      setGhostModels(data)
    } catch (e) { console.error('Ghost-Modelle laden:', e) }
  }, [])

  const loadModels = useCallback(async () => {
    try {
      const raw = await api.llmModels()
      const data = (raw || []).map(m => ({
        ...m,
        vram_required_mb: m.vram_required_mb || (m.size ? Math.round(m.size / 1048576) : 0),
        state: m.state || m.status || 'inactive',
        model_path: m.model_path || m.path || '',
        model_format: m.model_format || m.format || '',
        param_count: m.param_count || m.parameters || '',
      }))
      setModels(data)
    } catch (e) { console.error('Modelle laden:', e) }
  }, [])

  const loadChains = useCallback(async () => {
    try {
      const data = await api.llmChains()
      setChains(data || [])
    } catch (e) { console.error('Chains laden:', e) }
  }, [])

  const loadJobs = useCallback(async () => {
    try {
      const data = await api.agentsScheduledJobs()
      setJobs(data || [])
    } catch (e) { console.error('Jobs laden:', e) }
  }, [])

  const loadBenchmarks = useCallback(async () => {
    try {
      const data = await api.llmBenchmarkResults()
      setBenchmarks(Array.isArray(data) ? data : [])
    } catch (e) { console.error('Benchmarks laden:', e); setBenchmarks([]) }
  }, [])

  const loadTasks = useCallback(async (instId) => {
    if (!instId) return
    try {
      const data = await api.agentsTasks(instId)
      setTasks(data || [])
    } catch (e) { console.error('Tasks laden:', e) }
  }, [])

  // Initial load with timeout safety
  useEffect(() => {
    setLoading(true)
    const timeout = setTimeout(() => setLoading(false), 5000) // Safety timeout
    Promise.all([
      loadInstances(), loadGpu(), loadRoles(), loadGhostModels(),
      loadModels(), loadChains(), loadJobs(), loadBenchmarks()
    ]).finally(() => {
      clearTimeout(timeout)
      setLoading(false)
    })
  }, [])

  // Auto-refresh GPU + instances every 10s
  useEffect(() => {
    refreshRef.current = setInterval(() => {
      loadGpu()
      loadInstances()
    }, 10000)
    return () => clearInterval(refreshRef.current)
  }, [loadGpu, loadInstances])

  /* ─── ACTION HANDLERS ────────────────────────────── */
  const confirmAndDo = (title, message, icon, action) => {
    setConfirmAction({ title, message, icon, action })
  }

  const handleCreateInstance = async () => {
    try {
      await api.agentsCreateInstance(newInst)
      setShowCreate(false)
      setNewInst({ model_id: '', role_id: '', gpu_index: 0, backend: 'ollama', context_size: 4096, n_gpu_layers: 99, threads: 8, batch_size: 512 })
      await loadInstances()
    } catch (e) { console.error('Instanz erstellen:', e) }
  }

  const handleStartInstance = (inst) => {
    confirmAndDo('Agent starten', `"${inst.model_name || inst.model_id}" als ${inst.role_name || 'Agent'} auf GPU ${inst.gpu_index} starten?`, '🚀', async () => {
      try {
        await api.agentsStartInstance(inst.id)
        await loadInstances()
        await loadGpu()
      } catch (e) { console.error('Start fehlgeschlagen:', e) }
    })
  }

  const handleStopInstance = (inst) => {
    confirmAndDo('Agent stoppen', `"${inst.model_name || inst.model_id}" stoppen?`, '⏹️', async () => {
      try {
        await api.agentsStopInstance(inst.id)
        await loadInstances()
        await loadGpu()
      } catch (e) { console.error('Stop fehlgeschlagen:', e) }
    })
  }

  const handleDeleteInstance = (inst) => {
    confirmAndDo('Agent löschen', `Instanz "${inst.model_name || inst.model_id}" endgültig löschen?\nAlle zugehörigen Tasks werden ebenfalls entfernt.`, '🗑️', async () => {
      try {
        await api.agentsDeleteInstance(inst.id)
        if (selectedInstance === inst.id) { setSelectedInstance(null); setTasks([]) }
        await loadInstances()
      } catch (e) { console.error('Löschen fehlgeschlagen:', e) }
    })
  }

  const handleAssignRole = async (instId, roleId) => {
    try {
      await api.agentsAssignRole(instId, roleId)
      await loadInstances()
    } catch (e) { console.error('Rolle zuweisen:', e) }
  }

  const handleScan = async () => {
    setScanning(true)
    try {
      const data = await api.llmScanDisks(scanPaths.split(',').map(s => s.trim()).filter(Boolean))
      setScanResults(data || [])
    } catch (e) { console.error('Scan fehlgeschlagen:', e) }
    setScanning(false)
  }

  const handleAddModel = (model) => {
    confirmAndDo('Modell registrieren', `"${model.name || model.filename}" zur Datenbank hinzufügen?`, '📦', async () => {
      try {
        await api.llmAddModel(model)
        await loadModels()
        await loadGhostModels()
      } catch (e) { console.error('Modell hinzufügen:', e) }
    })
  }

  const handleRemoveModel = (model) => {
    confirmAndDo('Modell entfernen', `"${model.name}" aus der Datenbank entfernen?`, '🗑️', async () => {
      try {
        await api.llmRemoveModel(model.id)
        await loadModels()
        await loadGhostModels()
      } catch (e) { console.error('Modell entfernen:', e) }
    })
  }

  const handleCreateChain = async () => {
    if (!newChainName.trim()) return
    try {
      await api.llmCreateChain({ name: newChainName.trim(), description: '', steps: [] })
      setNewChainName('')
      await loadChains()
    } catch (e) { console.error('Chain erstellen:', e) }
  }

  const handleDeleteChain = (chain) => {
    confirmAndDo('Pipeline löschen', `Pipeline "${chain.name}" löschen?`, '🗑️', async () => {
      try {
        await api.llmDeleteChain(chain.id)
        await loadChains()
      } catch (e) { console.error('Chain löschen:', e) }
    })
  }

  const handleCreateTask = async () => {
    if (!selectedInstance) return
    try {
      await api.agentsCreateTask({ ...newTask, instance_id: selectedInstance })
      setShowCreateTask(false)
      setNewTask({ task_type: 'chat', name: '', description: '', system_prompt: '', priority: 5 })
      await loadTasks(selectedInstance)
    } catch (e) { console.error('Task erstellen:', e) }
  }

  const handleDeleteTask = (task) => {
    confirmAndDo('Task löschen', `Task "${task.name}" löschen?`, '🗑️', async () => {
      try {
        await api.agentsDeleteTask(task.id)
        await loadTasks(selectedInstance)
      } catch (e) { console.error('Task löschen:', e) }
    })
  }

  const handleCreateJob = async () => {
    try {
      await api.agentsCreateJob(newJob)
      setShowCreateJob(false)
      setNewJob({ name: '', cron_expr: '*/30 * * * *', instance_id: '', task_prompt: '', enabled: true })
      await loadJobs()
    } catch (e) { console.error('Job erstellen:', e) }
  }

  const handleDeleteJob = (job) => {
    confirmAndDo('Job löschen', `Cron-Job "${job.name}" löschen?`, '🗑️', async () => {
      try {
        await api.agentsDeleteJob(job.id)
        await loadJobs()
      } catch (e) { console.error('Job löschen:', e) }
    })
  }

  const handleRunBenchmark = (modelId) => {
    confirmAndDo('Benchmark starten', 'Benchmark für dieses Modell starten? Das kann einige Minuten dauern.', '📊', async () => {
      try {
        await api.llmRunBenchmark(modelId)
        await loadBenchmarks()
      } catch (e) { console.error('Benchmark fehlgeschlagen:', e) }
    })
  }

  const openWebFrame = (url, title) => {
    if (onOpenWindow) onOpenWindow('webframe', { url, title })
  }

  // ─── OpenClaw Import ────────────────────
  const [ocImporting, setOcImporting] = useState(false)
  const [ocImportResult, setOcImportResult] = useState(null)

  const handleOpenClawImport = async () => {
    setOcImporting(true)
    setOcImportResult(null)
    try {
      const result = await api.openclawImportToGhost()
      setOcImportResult(result)
      if (result.ok) {
        await loadGhostModels()
        await loadModels()
        await loadInstances()
        await loadRoles()
      }
    } catch (e) {
      setOcImportResult({ ok: false, error: e.message })
    }
    setOcImporting(false)
  }

  /* ─── TAB: AGENTS ───────────────────────────────── */
  const renderAgents = () => {
    const running = instances.filter(i => i.state === 'running')
    const stopped = instances.filter(i => i.state !== 'running')

    return (
      <div style={S.tabContent}>
        {/* OpenClaw Import Banner */}
        <div style={{
          padding: '10px 14px', borderRadius: '8px',
          background: 'rgba(0,200,255,0.04)', border: '1px solid rgba(0,200,255,0.15)',
          display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap',
        }}>
          <span style={{ fontSize: '18px' }}>🦅</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>OpenClaw → Ghost Import</div>
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
              Importiert alle OpenClaw-Modelle und Agenten automatisch als Ghost-Instanzen
            </div>
          </div>
          {ocImportResult && (
            <div style={{ fontSize: '11px', color: ocImportResult.ok ? '#00ff88' : '#ff4444' }}>
              {ocImportResult.ok
                ? `✅ ${ocImportResult.total_models} Modelle, ${ocImportResult.total_agents} Agenten importiert`
                : `❌ ${ocImportResult.error}`}
            </div>
          )}
          <button style={S.btnPrimary} onClick={handleOpenClawImport} disabled={ocImporting}>
            {ocImporting ? '⏳ Importiere…' : '📥 OpenClaw importieren'}
          </button>
        </div>

        {/* GPU Übersicht */}
        <div style={S.section}>
          <div style={S.sectionHeader}>
            <span>🖥️ GPU-Ressourcen</span>
            <button style={S.btnSmall} onClick={loadGpu}>↻ Refresh</button>
          </div>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            {gpuInfo.length === 0 ? (
              <div style={S.emptyState}>Keine GPU erkannt</div>
            ) : gpuInfo.map((gpu, i) => {
              const gpuInstances = instances.filter(inst => inst.gpu_index === gpu.gpu_index && inst.state === 'running')
              const allocatedVram = gpuInstances.reduce((sum, inst) => sum + (inst.vram_allocated_mb || 0), 0)
              return (
                <div key={i} style={S.gpuCard}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)' }}>GPU {gpu.gpu_index}</span>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{gpu.temperature}°C | {gpu.utilization}%</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>{gpu.name}</div>
                  <VramBar used={gpu.memory_used_mb} total={gpu.memory_total_mb} label="VRAM gesamt" />
                  {gpuInstances.length > 0 && (
                    <div style={{ marginTop: '6px' }}>
                      <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '2px' }}>
                        {gpuInstances.length} Agent{gpuInstances.length > 1 ? 'en' : ''} aktiv · {formatMB(allocatedVram)} zugewiesen
                      </div>
                      {gpuInstances.map(inst => (
                        <div key={inst.id} style={{ fontSize: '10px', color: '#00ff88', fontFamily: 'var(--font-mono)', padding: '1px 0' }}>
                          ● {inst.model_name || 'Modell'} → {inst.role_name || 'Frei'}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Aktive Agenten */}
        <div style={S.section}>
          <div style={S.sectionHeader}>
            <span>🤖 Agenten-Instanzen ({instances.length})</span>
            <button style={S.btnPrimary} onClick={() => setShowCreate(true)}>+ Neue Instanz</button>
          </div>

          {instances.length === 0 ? (
            <div style={S.emptyState}>
              <div style={{ fontSize: '48px', marginBottom: '12px' }}>🤖</div>
              <div>Keine Agenten konfiguriert</div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '6px' }}>
                Erstelle eine neue Instanz, um ein Modell auf einer GPU zu starten
              </div>
            </div>
          ) : (
            <div style={S.instanceGrid}>
              {instances.map(inst => (
                <div key={inst.id} style={{
                  ...S.instanceCard,
                  borderColor: inst.state === 'running' ? '#00ff8844' : 'var(--border)',
                  boxShadow: inst.state === 'running' ? '0 0 20px rgba(0,255,136,0.08)' : 'none',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <StateDot state={inst.state} />
                      <span style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text-primary)' }}>
                        {inst.model_name || `Modell #${inst.model_id}`}
                      </span>
                    </div>
                    <span style={{
                      fontSize: '10px', padding: '2px 8px', borderRadius: '10px',
                      background: (STATE_COLORS[inst.state] || '#888') + '22',
                      color: STATE_COLORS[inst.state] || '#888',
                      fontWeight: 600,
                    }}>
                      {STATE_LABELS[inst.state] || inst.state}
                    </span>
                  </div>

                  <div style={S.instanceMeta}>
                    <div>🎭 <strong>Rolle:</strong> {inst.role_name || '—'}</div>
                    <div>🖥️ <strong>GPU:</strong> {inst.gpu_name || `GPU ${inst.gpu_index}`}</div>
                    <div>⚙️ <strong>Backend:</strong> {inst.backend}</div>
                    <div>📐 <strong>Kontext:</strong> {(inst.context_size || 0).toLocaleString()} Token</div>
                    {inst.vram_allocated_mb > 0 && (
                      <div>💾 <strong>VRAM:</strong> {formatMB(inst.vram_allocated_mb)}</div>
                    )}
                    {inst.api_endpoint && (
                      <div>🔗 <strong>API:</strong> <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px' }}>{inst.api_endpoint}</span></div>
                    )}
                    {inst.pid && (
                      <div>🔢 <strong>PID:</strong> {inst.pid}</div>
                    )}
                  </div>

                  {/* Role Selector */}
                  <div style={{ marginTop: '8px' }}>
                    <select
                      style={S.select}
                      value={inst.role_id || ''}
                      onChange={(e) => handleAssignRole(inst.id, e.target.value)}
                    >
                      <option value="">— Rolle zuweisen —</option>
                      {roles.map(r => (
                        <option key={r.id || r.role_id} value={r.id || r.role_id}>
                          {r.display_name || r.role_name || r.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Stats */}
                  {inst.state === 'running' && inst.requests_total > 0 && (
                    <div style={{ marginTop: '6px', fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                      Anfragen: {inst.requests_total} · Token: {(inst.tokens_generated || 0).toLocaleString()} · Fehler: {inst.errors_total || 0}
                    </div>
                  )}

                  {/* Actions */}
                  <div style={S.instanceActions}>
                    {inst.state === 'stopped' || inst.state === 'error' ? (
                      <button style={S.btnStart} onClick={() => handleStartInstance(inst)}>▶ Starten</button>
                    ) : inst.state === 'running' ? (
                      <button style={S.btnStop} onClick={() => handleStopInstance(inst)}>⏹ Stoppen</button>
                    ) : null}
                    <button style={S.btnSmall} onClick={() => {
                      setSelectedInstance(inst.id)
                      loadTasks(inst.id)
                      setShowCreateTask(false)
                    }}>📋 Tasks</button>
                    <button style={S.btnDanger} onClick={() => handleDeleteInstance(inst)}>🗑️</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Task-Bereich für ausgewählte Instanz */}
        {selectedInstance && (
          <div style={S.section}>
            <div style={S.sectionHeader}>
              <span>📋 Tasks für Instanz #{selectedInstance}</span>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button style={S.btnSmall} onClick={() => setShowCreateTask(true)}>+ Task</button>
                <button style={S.btnSmall} onClick={() => { setSelectedInstance(null); setTasks([]) }}>✕ Schließen</button>
              </div>
            </div>
            {tasks.length === 0 && !showCreateTask ? (
              <div style={{ ...S.emptyState, padding: '16px' }}>Keine Tasks zugewiesen</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {tasks.map(t => (
                  <div key={t.id} style={S.taskRow}>
                    <span style={{ fontSize: '11px', padding: '2px 6px', borderRadius: '4px', background: 'rgba(0,255,200,0.1)', color: '#00ffc8', fontFamily: 'var(--font-mono)' }}>
                      {t.task_type}
                    </span>
                    <span style={{ flex: 1, fontSize: '12px', color: 'var(--text-primary)' }}>{t.name}</span>
                    <span style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>P{t.priority}</span>
                    <button style={S.btnDanger} onClick={() => handleDeleteTask(t)}>✕</button>
                  </div>
                ))}
              </div>
            )}

            {/* Create Task Form */}
            {showCreateTask && (
              <div style={S.formCard}>
                <div style={{ fontSize: '13px', fontWeight: 700, marginBottom: '8px', color: 'var(--text-primary)' }}>Neuer Task</div>
                <div style={S.formGrid}>
                  <label style={S.label}>Typ
                    <select style={S.select} value={newTask.task_type} onChange={e => setNewTask(p => ({ ...p, task_type: e.target.value }))}>
                      {['chat', 'code', 'analysis', 'creative', 'embedding', 'vision', 'custom'].map(t => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </label>
                  <label style={S.label}>Name
                    <input style={S.input} value={newTask.name} onChange={e => setNewTask(p => ({ ...p, name: e.target.value }))} placeholder="Task-Name" />
                  </label>
                  <label style={S.label}>Priorität (1-10)
                    <input style={S.input} type="number" min={1} max={10} value={newTask.priority} onChange={e => setNewTask(p => ({ ...p, priority: +e.target.value }))} />
                  </label>
                </div>
                <label style={S.label}>System-Prompt
                  <textarea style={{ ...S.input, minHeight: '60px', resize: 'vertical' }} value={newTask.system_prompt} onChange={e => setNewTask(p => ({ ...p, system_prompt: e.target.value }))} placeholder="Optionaler System-Prompt…" />
                </label>
                <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                  <button style={S.btnPrimary} onClick={handleCreateTask}>Erstellen</button>
                  <button style={S.btnSmall} onClick={() => setShowCreateTask(false)}>Abbrechen</button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Create Instance Modal */}
        {showCreate && (
          <div style={S.confirmOverlay} onClick={(e) => e.target === e.currentTarget && setShowCreate(false)}>
            <div style={{ ...S.confirmDialog, maxWidth: '600px' }}>
              <div style={{ fontSize: '20px', textAlign: 'center', marginBottom: '8px' }}>🤖 Neue Agenten-Instanz</div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', textAlign: 'center', marginBottom: '16px' }}>
                Wähle ein Modell, weise eine Rolle zu und starte den Agenten auf einer GPU
              </div>

              <div style={S.formGrid}>
                <label style={S.label}>📦 Modell *
                  <select style={S.select} value={newInst.model_id} onChange={e => setNewInst(p => ({ ...p, model_id: e.target.value }))}>
                    <option value="">— Modell wählen —</option>
                    {ghostModels.map(m => (
                      <option key={m.id} value={m.id}>
                        {m.name} {m.vram_required_mb ? `(${formatMB(m.vram_required_mb)})` : ''}
                      </option>
                    ))}
                  </select>
                </label>

                <label style={S.label}>🎭 Rolle
                  <select style={S.select} value={newInst.role_id} onChange={e => setNewInst(p => ({ ...p, role_id: e.target.value }))}>
                    <option value="">— Rolle wählen —</option>
                    {roles.map(r => (
                      <option key={r.id || r.role_id} value={r.id || r.role_id}>
                        {r.display_name || r.role_name || r.name}
                      </option>
                    ))}
                  </select>
                </label>

                <label style={S.label}>🖥️ GPU
                  <select style={S.select} value={newInst.gpu_index} onChange={e => setNewInst(p => ({ ...p, gpu_index: +e.target.value }))}>
                    {gpuInfo.length === 0 ? (
                      <option value={0}>GPU 0 (Standard)</option>
                    ) : gpuInfo.map(g => (
                      <option key={g.gpu_index} value={g.gpu_index}>
                        GPU {g.gpu_index}: {g.name} — {formatMB(g.memory_free_mb)} frei
                      </option>
                    ))}
                  </select>
                </label>

                <label style={S.label}>⚙️ Backend
                  <select style={S.select} value={newInst.backend} onChange={e => setNewInst(p => ({ ...p, backend: e.target.value }))}>
                    {BACKENDS.map(b => (
                      <option key={b.value} value={b.value}>{b.icon} {b.label}</option>
                    ))}
                  </select>
                </label>

                <label style={S.label}>Kontext-Größe
                  <select style={S.select} value={newInst.context_size} onChange={e => setNewInst(p => ({ ...p, context_size: +e.target.value }))}>
                    {[2048, 4096, 8192, 16384, 32768, 65536, 131072].map(v => (
                      <option key={v} value={v}>{v.toLocaleString()} Token</option>
                    ))}
                  </select>
                </label>

                <label style={S.label}>GPU-Layer
                  <input style={S.input} type="number" min={0} max={200} value={newInst.n_gpu_layers} onChange={e => setNewInst(p => ({ ...p, n_gpu_layers: +e.target.value }))} />
                </label>

                <label style={S.label}>Threads
                  <input style={S.input} type="number" min={1} max={64} value={newInst.threads} onChange={e => setNewInst(p => ({ ...p, threads: +e.target.value }))} />
                </label>

                <label style={S.label}>Batch-Größe
                  <select style={S.select} value={newInst.batch_size} onChange={e => setNewInst(p => ({ ...p, batch_size: +e.target.value }))}>
                    {[128, 256, 512, 1024, 2048].map(v => (
                      <option key={v} value={v}>{v}</option>
                    ))}
                  </select>
                </label>
              </div>

              {/* VRAM Preview */}
              {newInst.model_id && (() => {
                const model = ghostModels.find(m => String(m.id) === String(newInst.model_id))
                const gpu = gpuInfo.find(g => g.gpu_index === newInst.gpu_index)
                if (!model) return null
                const vramNeeded = model.vram_required_mb || 0
                const vramFree = gpu ? gpu.memory_free_mb : 0
                const fits = vramFree >= vramNeeded || !gpu
                return (
                  <div style={{ marginTop: '12px', padding: '10px', borderRadius: '8px', background: fits ? 'rgba(0,255,136,0.06)' : 'rgba(255,68,68,0.06)', border: `1px solid ${fits ? '#00ff8844' : '#ff444444'}` }}>
                    <div style={{ fontSize: '12px', fontWeight: 600, color: fits ? '#00ff88' : '#ff4444' }}>
                      {fits ? '✅ Modell passt auf GPU' : '⚠️ Möglicherweise nicht genug VRAM'}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                      Benötigt: {formatMB(vramNeeded)} · Frei: {gpu ? formatMB(vramFree) : 'unbekannt'}
                    </div>
                  </div>
                )
              })()}

              <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', marginTop: '16px' }}>
                <button style={S.btnPrimary} onClick={handleCreateInstance} disabled={!newInst.model_id}>
                  🚀 Instanz erstellen
                </button>
                <button style={S.btnSmall} onClick={() => setShowCreate(false)}>Abbrechen</button>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  /* ─── TAB: MODELS ───────────────────────────────── */
  const renderModels = () => (
    <div style={S.tabContent}>
      {/* Scanner */}
      <div style={S.section}>
        <div style={S.sectionHeader}>
          <span>🔍 Festplatten-Scanner</span>
          <button style={S.btnPrimary} onClick={handleScan} disabled={scanning}>
            {scanning ? '⏳ Scanne…' : '🔍 Scannen'}
          </button>
        </div>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
          <input
            style={{ ...S.input, flex: 1 }}
            value={scanPaths}
            onChange={e => setScanPaths(e.target.value)}
            placeholder="Pfade (kommagetrennt)"
          />
        </div>
        {scanResults.length > 0 && (
          <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
            {scanResults.map((r, i) => (
              <div key={i} style={S.scanRow}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{r.filename || r.name}</div>
                  <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>{r.path} · {formatBytes(r.size)}</div>
                </div>
                <button style={S.btnSmall} onClick={() => handleAddModel(r)}>+ Hinzufügen</button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Model Registry */}
      <div style={S.section}>
        <div style={S.sectionHeader}>
          <span>📦 Registrierte Modelle ({models.length})</span>
          <button style={S.btnSmall} onClick={loadModels}>↻</button>
        </div>
        {models.length === 0 ? (
          <div style={S.emptyState}>Keine Modelle registriert</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={S.table}>
              <thead>
                <tr>
                  <th style={S.th}>Name</th>
                  <th style={S.th}>Format</th>
                  <th style={S.th}>VRAM</th>
                  <th style={S.th}>Parameter</th>
                  <th style={S.th}>Status</th>
                  <th style={S.th}>Aktionen</th>
                </tr>
              </thead>
              <tbody>
                {models.map(m => (
                  <tr key={m.id}>
                    <td style={S.td}>
                      <div style={{ fontWeight: 600 }}>{m.name}</div>
                      <div style={{ fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{m.model_path || '—'}</div>
                    </td>
                    <td style={S.td}><span style={S.badge}>{m.format || m.model_format || '—'}</span></td>
                    <td style={S.td}>{m.vram_required_mb ? formatMB(m.vram_required_mb) : '—'}</td>
                    <td style={S.td}>{m.parameters || m.param_count || '—'}</td>
                    <td style={S.td}>
                      <span style={{ ...S.badge, background: m.state === 'active' ? 'rgba(0,255,136,0.1)' : 'rgba(255,255,255,0.05)', color: m.state === 'active' ? '#00ff88' : 'var(--text-secondary)' }}>
                        {m.state || 'inaktiv'}
                      </span>
                    </td>
                    <td style={S.td}>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        <button style={S.btnSmall} onClick={() => handleRunBenchmark(m.id)} title="Benchmark">📊</button>
                        <button style={S.btnDanger} onClick={() => handleRemoveModel(m)} title="Entfernen">🗑️</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )

  /* ─── TAB: ROLES ────────────────────────────────── */
  const renderRoles = () => (
    <div style={S.tabContent}>
      <div style={S.section}>
        <div style={S.sectionHeader}>
          <span>🎭 Ghost-Rollen ({roles.length})</span>
          <button style={S.btnSmall} onClick={loadRoles}>↻</button>
        </div>
        {roles.length === 0 ? (
          <div style={S.emptyState}>Keine Rollen definiert</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {roles.map(r => {
              const assignedInstances = instances.filter(i => i.role_id === (r.id || r.role_id))
              return (
                <div key={r.id || r.role_id} style={S.roleCard}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{ fontSize: '24px' }}>{r.icon || '🎭'}</span>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text-primary)' }}>
                          {r.display_name || r.role_name || r.name}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                          Priorität: {r.priority || '—'} · {r.is_critical ? '🔴 Kritisch' : '🟢 Normal'}
                        </div>
                      </div>
                    </div>
                    <div>
                      {assignedInstances.length > 0 ? (
                        <span style={S.badgeGreen}>{assignedInstances.length} Agent{assignedInstances.length > 1 ? 'en' : ''}</span>
                      ) : (
                        <span style={S.badgeGray}>Kein Agent</span>
                      )}
                    </div>
                  </div>
                  {r.system_prompt && (
                    <div style={S.promptBox}>
                      <div style={{ fontSize: '10px', color: 'var(--accent)', marginBottom: '4px' }}>System-Prompt:</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', maxHeight: '80px', overflow: 'auto' }}>
                        {r.system_prompt}
                      </div>
                    </div>
                  )}
                  {(r.accessible_schemas || r.accessible_tables) && (
                    <div style={{ marginTop: '6px', fontSize: '10px', color: 'var(--text-secondary)' }}>
                      {r.accessible_schemas && <span>Schemas: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>{Array.isArray(r.accessible_schemas) ? r.accessible_schemas.join(', ') : r.accessible_schemas}</span> · </span>}
                      {r.accessible_tables && <span>Tabellen: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>{Array.isArray(r.accessible_tables) ? r.accessible_tables.join(', ') : r.accessible_tables}</span></span>}
                    </div>
                  )}
                  {assignedInstances.length > 0 && (
                    <div style={{ marginTop: '6px' }}>
                      {assignedInstances.map(inst => (
                        <div key={inst.id} style={{ fontSize: '11px', display: 'flex', gap: '6px', alignItems: 'center', padding: '3px 0' }}>
                          <StateDot state={inst.state} />
                          <span style={{ color: 'var(--text-primary)' }}>{inst.model_name || 'Modell'}</span>
                          <span style={{ color: 'var(--text-secondary)' }}>GPU {inst.gpu_index}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )

  /* ─── TAB: JOBS ─────────────────────────────────── */
  const renderJobs = () => (
    <div style={S.tabContent}>
      <div style={S.section}>
        <div style={S.sectionHeader}>
          <span>⏰ Geplante Jobs ({jobs.length})</span>
          <button style={S.btnPrimary} onClick={() => setShowCreateJob(true)}>+ Neuer Job</button>
        </div>

        {jobs.length === 0 && !showCreateJob ? (
          <div style={S.emptyState}>
            <div style={{ fontSize: '48px', marginBottom: '12px' }}>⏰</div>
            <div>Keine geplanten Jobs</div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '6px' }}>
              Plane automatisierte Aufgaben mit Cron-Ausdrücken
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {jobs.map(j => (
              <div key={j.id} style={S.jobRow}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1 }}>
                  <span style={{ fontSize: '18px' }}>{j.enabled ? '🟢' : '🔴'}</span>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>{j.name}</div>
                    <div style={{ fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                      {j.cron_expr} · Agent: {j.instance_model_name || j.instance_id || '—'} · Rolle: {j.role_name || '—'}
                    </div>
                    {j.last_run_at && (
                      <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                        Letzter Lauf: {new Date(j.last_run_at).toLocaleString('de-DE')} · Status: {j.last_status || '—'} · Läufe: {j.run_count || 0}
                      </div>
                    )}
                  </div>
                </div>
                <button style={S.btnDanger} onClick={() => handleDeleteJob(j)}>🗑️</button>
              </div>
            ))}
          </div>
        )}

        {/* Create Job Form */}
        {showCreateJob && (
          <div style={S.formCard}>
            <div style={{ fontSize: '13px', fontWeight: 700, marginBottom: '8px', color: 'var(--text-primary)' }}>Neuer Cron-Job</div>
            <div style={S.formGrid}>
              <label style={S.label}>Name
                <input style={S.input} value={newJob.name} onChange={e => setNewJob(p => ({ ...p, name: e.target.value }))} placeholder="Job-Name" />
              </label>
              <label style={S.label}>Cron-Ausdruck
                <input style={S.input} value={newJob.cron_expr} onChange={e => setNewJob(p => ({ ...p, cron_expr: e.target.value }))} placeholder="*/30 * * * *" />
              </label>
              <label style={S.label}>Agenten-Instanz
                <select style={S.select} value={newJob.instance_id} onChange={e => setNewJob(p => ({ ...p, instance_id: e.target.value }))}>
                  <option value="">— Instanz wählen —</option>
                  {instances.map(i => (
                    <option key={i.id} value={i.id}>
                      {i.model_name || `#${i.id}`} ({i.role_name || 'Frei'})
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label style={S.label}>Aufgabe / Prompt
              <textarea style={{ ...S.input, minHeight: '60px', resize: 'vertical' }} value={newJob.task_prompt} onChange={e => setNewJob(p => ({ ...p, task_prompt: e.target.value }))} placeholder="Was soll der Agent tun?" />
            </label>
            <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
              <button style={S.btnPrimary} onClick={handleCreateJob}>Erstellen</button>
              <button style={S.btnSmall} onClick={() => setShowCreateJob(false)}>Abbrechen</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )

  /* ─── TAB: PIPELINES ────────────────────────────── */
  const renderPipelines = () => (
    <div style={S.tabContent}>
      <div style={S.section}>
        <div style={S.sectionHeader}>
          <span>🔗 Pipelines / Chains ({chains.length})</span>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input style={S.input} value={newChainName} onChange={e => setNewChainName(e.target.value)} placeholder="Neue Pipeline…" onKeyDown={e => e.key === 'Enter' && handleCreateChain()} />
            <button style={S.btnPrimary} onClick={handleCreateChain} disabled={!newChainName.trim()}>+ Erstellen</button>
          </div>
        </div>

        {chains.length === 0 ? (
          <div style={S.emptyState}>
            <div style={{ fontSize: '48px', marginBottom: '12px' }}>🔗</div>
            <div>Keine Pipelines konfiguriert</div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '6px' }}>
              Verknüpfe mehrere Modell-Instanzen zu einer Pipeline
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {chains.map(c => (
              <div key={c.id} style={S.chainCard}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)' }}>{c.name}</div>
                    {c.description && <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{c.description}</div>}
                  </div>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                    <span style={S.badge}>{(c.steps || []).length} Schritte</span>
                    <button style={S.btnDanger} onClick={() => handleDeleteChain(c)}>🗑️</button>
                  </div>
                </div>
                {(c.steps || []).length > 0 && (
                  <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
                    {c.steps.map((step, si) => (
                      <React.Fragment key={si}>
                        {si > 0 && <span style={{ color: 'var(--accent)' }}>→</span>}
                        <span style={S.chainStep}>{step.model_name || step.name || `Schritt ${si + 1}`}</span>
                      </React.Fragment>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )

  /* ─── TAB: GPU ──────────────────────────────────── */
  const renderGpu = () => (
    <div style={S.tabContent}>
      <div style={S.section}>
        <div style={S.sectionHeader}>
          <span>🖥️ GPU-Monitor</span>
          <button style={S.btnSmall} onClick={loadGpu}>↻ Refresh</button>
        </div>
        {gpuInfo.length === 0 ? (
          <div style={S.emptyState}>Keine GPUs erkannt — nvidia-smi nicht verfügbar?</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {gpuInfo.map(gpu => {
              const gpuInstances = instances.filter(i => i.gpu_index === gpu.gpu_index)
              const runningCount = gpuInstances.filter(i => i.state === 'running').length
              return (
                <div key={gpu.gpu_index} style={S.gpuDetailCard}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '16px', color: 'var(--text-primary)' }}>
                        GPU {gpu.gpu_index}: {gpu.name}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                        {gpu.driver_version && `Treiber: ${gpu.driver_version} · `}
                        {gpu.cuda_version && `CUDA: ${gpu.cuda_version}`}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '24px', fontWeight: 700, color: gpu.temperature > 80 ? '#ff4444' : gpu.temperature > 65 ? '#ffaa00' : '#00ff88', fontFamily: 'var(--font-mono)' }}>
                        {gpu.temperature}°C
                      </div>
                      <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>Temperatur</div>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                    <div>
                      <VramBar used={gpu.memory_used_mb} total={gpu.memory_total_mb} label="VRAM-Auslastung" height={24} />
                    </div>
                    <div>
                      <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '2px' }}>GPU-Auslastung</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div style={{ flex: 1, height: '24px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden', position: 'relative' }}>
                          <div style={{
                            height: '100%', width: (gpu.utilization || 0) + '%',
                            background: `linear-gradient(90deg, #00ffc844, #00ffc8)`,
                            borderRadius: '4px', transition: 'width 0.5s',
                          }} />
                          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', textShadow: '0 1px 2px rgba(0,0,0,0.8)' }}>
                            {gpu.utilization || 0}%
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                    {runningCount} laufende{runningCount !== 1 ? '' : 'r'} Agent{runningCount !== 1 ? 'en' : ''} auf dieser GPU
                  </div>

                  {gpuInstances.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {gpuInstances.map(inst => (
                        <div key={inst.id} style={{
                          display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 10px',
                          background: 'rgba(255,255,255,0.03)', borderRadius: '6px', fontSize: '12px',
                        }}>
                          <StateDot state={inst.state} />
                          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{inst.model_name || 'Modell'}</span>
                          <span style={{ color: 'var(--accent)' }}>→</span>
                          <span style={{ color: 'var(--text-secondary)' }}>{inst.role_name || 'Frei'}</span>
                          {inst.vram_allocated_mb > 0 && (
                            <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-secondary)' }}>
                              {formatMB(inst.vram_allocated_mb)}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* WebUI Links */}
      <div style={S.section}>
        <div style={S.sectionHeader}>
          <span>🌐 LLM Web-Interfaces</span>
        </div>
        <div style={S.webuiGrid}>
          {DEFAULT_WEBUIS.map((ui, i) => (
            <div key={i} style={S.webuiCard} onClick={() => openWebFrame(ui.url, ui.name)}>
              <div style={{ fontSize: '28px' }}>{ui.icon}</div>
              <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>{ui.name}</div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{ui.desc}</div>
              <div style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>:{ui.port}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )

  /* ─── TAB: BENCHMARKS ───────────────────────────── */
  const renderBenchmarks = () => (
    <div style={S.tabContent}>
      <div style={S.section}>
        <div style={S.sectionHeader}>
          <span>📊 Benchmark-Ergebnisse ({benchmarks.length})</span>
          <button style={S.btnSmall} onClick={loadBenchmarks}>↻</button>
        </div>
        {benchmarks.length === 0 ? (
          <div style={S.emptyState}>
            <div style={{ fontSize: '48px', marginBottom: '12px' }}>📊</div>
            <div>Keine Benchmark-Daten</div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '6px' }}>
              Starte einen Benchmark im Modelle-Tab
            </div>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={S.table}>
              <thead>
                <tr>
                  <th style={S.th}>Modell</th>
                  <th style={S.th}>Token/s</th>
                  <th style={S.th}>TTFT</th>
                  <th style={S.th}>Speicher</th>
                  <th style={S.th}>Score</th>
                  <th style={S.th}>Datum</th>
                </tr>
              </thead>
              <tbody>
                {benchmarks.map((b, i) => (
                  <tr key={i}>
                    <td style={S.td}>{b.model_name || b.model || '—'}</td>
                    <td style={S.td}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{b.tokens_per_second ? b.tokens_per_second.toFixed(1) : '—'}</span>
                        <QualityBar value={b.tokens_per_second || 0} max={100} />
                      </div>
                    </td>
                    <td style={S.td}>{b.time_to_first_token ? b.time_to_first_token.toFixed(0) + 'ms' : '—'}</td>
                    <td style={S.td}>{b.memory_used_mb ? formatMB(b.memory_used_mb) : '—'}</td>
                    <td style={S.td}>
                      <span style={{ fontWeight: 700, color: '#00ffc8' }}>{b.overall_score ? b.overall_score.toFixed(1) : '—'}</span>
                    </td>
                    <td style={S.td}>{b.created_at ? new Date(b.created_at).toLocaleDateString('de-DE') : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )

  /* ═══════════════════════════════════════════════════
     MAIN RENDER
     ═══════════════════════════════════════════════════ */
  const TABS = [
    { key: 'agents', icon: '🤖', label: 'Agenten' },
    { key: 'models', icon: '📦', label: 'Modelle' },
    { key: 'roles', icon: '🎭', label: 'Rollen' },
    { key: 'jobs', icon: '⏰', label: 'Jobs' },
    { key: 'pipelines', icon: '🔗', label: 'Pipelines' },
    { key: 'gpu', icon: '🖥️', label: 'GPU' },
    { key: 'benchmarks', icon: '📊', label: 'Bench' },
  ]

  return (
    <div style={S.container}>
      {/* Header */}
      <div style={S.header}>
        <div style={S.headerLeft}>
          <span style={{ fontSize: '20px' }}>🧠</span>
          <span style={{ fontWeight: 700, fontSize: '15px' }}>Mission Control</span>
          <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
            {instances.filter(i => i.state === 'running').length} aktiv · {gpuInfo.length} GPU{gpuInfo.length !== 1 ? 's' : ''}
          </span>
        </div>
        <div style={S.headerRight}>
          {gpuInfo.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
              <span>VRAM:</span>
              <VramBar used={gpuInfo[0]?.memory_used_mb || 0} total={gpuInfo[0]?.memory_total_mb || 1} height={12} />
            </div>
          )}
        </div>
      </div>

      {/* Tab Bar */}
      <div style={S.tabBar}>
        {TABS.map(t => (
          <button
            key={t.key}
            style={{ ...S.tabBtn, ...(tab === t.key ? S.tabBtnActive : {}) }}
            onClick={() => setTab(t.key)}
          >
            <span>{t.icon}</span>
            <span>{t.label}</span>
            {t.key === 'agents' && instances.filter(i => i.state === 'running').length > 0 && (
              <span style={S.tabBadge}>{instances.filter(i => i.state === 'running').length}</span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={S.content}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', gap: '12px' }}>
            <div style={{ fontSize: '36px', animation: 'pulse 1.5s infinite' }}>🧠</div>
            <div style={{ fontSize: '13px', color: 'var(--accent)' }}>Mission Control wird geladen…</div>
          </div>
        ) : (
          <>
            {tab === 'agents' && renderAgents()}
            {tab === 'models' && renderModels()}
            {tab === 'roles' && renderRoles()}
            {tab === 'jobs' && renderJobs()}
            {tab === 'pipelines' && renderPipelines()}
            {tab === 'gpu' && renderGpu()}
            {tab === 'benchmarks' && renderBenchmarks()}
          </>
        )}
      </div>

      {/* Confirm Dialog */}
      {confirmAction && (
        <div style={S.confirmOverlay} onClick={(e) => e.target === e.currentTarget && setConfirmAction(null)}>
          <div style={S.confirmDialog}>
            <div style={{ fontSize: '32px', textAlign: 'center', marginBottom: '8px' }}>{confirmAction.icon}</div>
            <div style={{ fontSize: '16px', fontWeight: 700, textAlign: 'center', color: 'var(--text-primary)', marginBottom: '6px' }}>{confirmAction.title}</div>
            <div style={{ fontSize: '13px', textAlign: 'center', color: 'var(--text-secondary)', marginBottom: '16px', whiteSpace: 'pre-line' }}>{confirmAction.message}</div>
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
              <button style={S.btnPrimary} onClick={() => { confirmAction.action(); setConfirmAction(null) }}>Bestätigen</button>
              <button style={S.btnSmall} onClick={() => setConfirmAction(null)}>Abbrechen</button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════
   STYLES
   ═══════════════════════════════════════════════════════ */
const S = {
  container: { display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-primary)', color: 'var(--text-primary)' },

  header: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '10px 16px', borderBottom: '1px solid var(--border)',
    background: 'linear-gradient(180deg, rgba(0,255,200,0.03) 0%, transparent 100%)',
  },
  headerLeft: { display: 'flex', alignItems: 'center', gap: '10px' },
  headerRight: { display: 'flex', alignItems: 'center', gap: '12px', minWidth: '200px' },

  tabBar: {
    display: 'flex', gap: '2px', padding: '6px 12px',
    borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)',
    overflowX: 'auto', flexShrink: 0,
  },
  tabBtn: {
    padding: '6px 12px', border: 'none', borderRadius: '6px',
    background: 'transparent', color: 'var(--text-secondary)',
    cursor: 'pointer', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '5px',
    whiteSpace: 'nowrap', transition: 'all 0.2s',
  },
  tabBtnActive: { background: 'rgba(0,255,200,0.1)', color: '#00ffc8', fontWeight: 600 },
  tabBadge: {
    fontSize: '9px', fontWeight: 700, background: '#00ff88', color: '#000',
    borderRadius: '8px', padding: '1px 5px', minWidth: '14px', textAlign: 'center',
  },

  content: { flex: 1, overflow: 'auto', position: 'relative' },
  tabContent: { padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: '16px' },

  section: {
    background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)',
    borderRadius: '10px', padding: '14px',
  },
  sectionHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    marginBottom: '12px', fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)',
  },

  emptyState: {
    textAlign: 'center', padding: '32px 16px', color: 'var(--text-secondary)',
    fontSize: '13px',
  },

  // GPU Cards
  gpuCard: {
    flex: '1 1 260px', padding: '12px', background: 'rgba(0,255,200,0.03)',
    border: '1px solid rgba(0,255,200,0.1)', borderRadius: '8px',
    display: 'flex', flexDirection: 'column', gap: '6px',
  },
  gpuDetailCard: {
    padding: '16px', background: 'rgba(0,255,200,0.02)',
    border: '1px solid rgba(0,255,200,0.12)', borderRadius: '10px',
  },

  // Instance Cards
  instanceGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '12px' },
  instanceCard: {
    padding: '14px', background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: '10px', display: 'flex', flexDirection: 'column', gap: '4px',
  },
  instanceMeta: { fontSize: '12px', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '2px' },
  instanceActions: { display: 'flex', gap: '6px', marginTop: '10px', flexWrap: 'wrap' },

  // Role Cards
  roleCard: {
    padding: '14px', background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: '10px',
  },
  promptBox: {
    padding: '8px 10px', background: 'rgba(0,0,0,0.2)', borderRadius: '6px',
    border: '1px solid rgba(255,255,255,0.05)', marginTop: '6px',
  },

  // Job Rows
  jobRow: {
    display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 12px',
    background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '8px',
  },

  // Task Rows
  taskRow: {
    display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 10px',
    background: 'rgba(255,255,255,0.03)', borderRadius: '6px',
  },

  // Chain Cards
  chainCard: {
    padding: '12px', background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: '8px',
  },
  chainStep: {
    padding: '4px 8px', background: 'rgba(0,255,200,0.08)', border: '1px solid rgba(0,255,200,0.15)',
    borderRadius: '4px', fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)',
  },

  // WebUI Grid
  webuiGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '10px' },
  webuiCard: {
    padding: '14px', background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: '8px', textAlign: 'center', cursor: 'pointer',
    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px',
    transition: 'all 0.2s',
  },

  // Scan Row
  scanRow: {
    display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 10px',
    borderBottom: '1px solid var(--border)',
  },

  // Table
  table: { width: '100%', borderCollapse: 'collapse' },
  th: {
    padding: '10px', textAlign: 'left', borderBottom: '2px solid var(--border)',
    fontSize: '11px', fontWeight: 700, color: 'var(--accent)', fontFamily: 'var(--font-mono)',
    background: 'var(--bg-surface)',
  },
  td: { padding: '10px', fontSize: '12px', verticalAlign: 'middle', borderBottom: '1px solid rgba(255,255,255,0.03)' },

  // Badges
  badge: {
    fontSize: '10px', padding: '2px 8px', borderRadius: '10px',
    background: 'rgba(255,255,255,0.05)', fontFamily: 'var(--font-mono)',
  },
  badgeGreen: {
    fontSize: '10px', padding: '2px 8px', borderRadius: '10px',
    background: 'rgba(0,255,136,0.1)', color: '#00ff88', fontWeight: 600,
  },
  badgeGray: {
    fontSize: '10px', padding: '2px 8px', borderRadius: '10px',
    background: 'rgba(255,255,255,0.05)', color: 'var(--text-secondary)',
  },

  // Forms
  formCard: {
    marginTop: '12px', padding: '14px', background: 'rgba(0,255,200,0.03)',
    border: '1px solid rgba(0,255,200,0.1)', borderRadius: '10px',
  },
  formGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '10px' },
  label: { display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '11px', color: 'var(--text-secondary)' },
  input: {
    padding: '7px 10px', background: 'var(--bg-primary)', border: '1px solid var(--border)',
    borderRadius: '6px', color: 'var(--text-primary)', fontSize: '12px',
    fontFamily: 'var(--font-mono)', outline: 'none',
  },
  select: {
    padding: '7px 10px', background: 'var(--bg-primary)', border: '1px solid var(--border)',
    borderRadius: '6px', color: 'var(--text-primary)', fontSize: '12px',
    fontFamily: 'var(--font-mono)', outline: 'none',
  },

  // Buttons
  btnPrimary: {
    padding: '6px 14px', background: 'linear-gradient(135deg, #00ffc8, #00cc99)',
    border: 'none', borderRadius: '6px', color: '#000', fontWeight: 700,
    fontSize: '12px', cursor: 'pointer', whiteSpace: 'nowrap',
  },
  btnSmall: {
    padding: '4px 10px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)',
    borderRadius: '6px', color: 'var(--text-primary)', fontSize: '11px', cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  btnStart: {
    padding: '5px 12px', background: 'rgba(0,255,136,0.1)', border: '1px solid rgba(0,255,136,0.3)',
    borderRadius: '6px', color: '#00ff88', fontSize: '11px', fontWeight: 600, cursor: 'pointer',
  },
  btnStop: {
    padding: '5px 12px', background: 'rgba(255,170,0,0.1)', border: '1px solid rgba(255,170,0,0.3)',
    borderRadius: '6px', color: '#ffaa00', fontSize: '11px', fontWeight: 600, cursor: 'pointer',
  },
  btnDanger: {
    padding: '4px 8px', background: 'rgba(255,68,68,0.08)', border: '1px solid rgba(255,68,68,0.2)',
    borderRadius: '6px', color: '#ff4444', fontSize: '11px', cursor: 'pointer',
  },

  // Confirm Dialog
  confirmOverlay: {
    position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.6)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
  },
  confirmDialog: {
    background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: '12px', padding: '24px', maxWidth: '450px', width: '90%',
    boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
  },
}
