import React, { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

/**
 * Ghost LLM Manager — Agent Orchestration, Ghost Hot-Swap & Mission Control
 * 
 * Vereint Ghost Manager + LLM Manager in einer App:
 * - KI-Modelle verwalten, Hot-Swap, Kompatibilität (Ghost Manager)
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
  { name: 'n8n', icon: '🔗', desc: 'Workflow-Automatisierung & AI Agents', port: 5678, url: 'http://localhost:5678', repo: 'https://github.com/n8n-io/n8n', installCmd: 'docker run -d --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n n8nio/n8n', category: 'automation' },
  { name: 'Ollama WebUI', icon: '🐪', desc: 'Chat-Interface für Ollama', port: 3080, url: 'http://localhost:3080', repo: 'https://github.com/open-webui/open-webui', installCmd: 'docker run -d --name open-webui -p 3080:8080 -v open-webui:/app/backend/data ghcr.io/open-webui/open-webui:main', category: 'chat' },
  { name: 'ComfyUI', icon: '🎨', desc: 'Stable Diffusion Node-Editor', port: 8188, url: 'http://localhost:8188', repo: 'https://github.com/comfyanonymous/ComfyUI', installCmd: 'git clone https://github.com/comfyanonymous/ComfyUI /opt/comfyui && cd /opt/comfyui && pip install -r requirements.txt && python main.py --port 8188', category: 'image' },
  { name: 'text-generation-webui', icon: '💬', desc: 'Gradio LLM Interface', port: 7860, url: 'http://localhost:7860', repo: 'https://github.com/oobabooga/text-generation-webui', installCmd: 'docker run -d --name textgen --gpus all -p 7860:7860 atinoda/text-generation-webui', category: 'chat' },
  { name: 'Stable Diffusion WebUI', icon: '🖼️', desc: 'AUTOMATIC1111 Forge', port: 7861, url: 'http://localhost:7861', repo: 'https://github.com/AUTOMATIC1111/stable-diffusion-webui', installCmd: 'docker run -d --name sd-webui --gpus all -p 7861:7860 sd-webui', category: 'image' },
  { name: 'LocalAI', icon: '🧠', desc: 'Drop-in OpenAI-Ersatz', port: 8080, url: 'http://localhost:8080', repo: 'https://github.com/mudler/LocalAI', installCmd: 'docker run -d --name localai --gpus all -p 8080:8080 localai/localai', category: 'api' },
  { name: 'LM Studio', icon: '📡', desc: 'Desktop LLM Server', port: 1234, url: 'http://localhost:1234', repo: 'https://lmstudio.ai', installCmd: null, category: 'desktop' },
  { name: 'Jan.ai', icon: '🤖', desc: 'Offline-first AI', port: 1337, url: 'http://localhost:1337', repo: 'https://github.com/janhq/jan', installCmd: null, category: 'desktop' },
  { name: 'vLLM Server', icon: '⚡', desc: 'High-Throughput Serving', port: 8000, url: 'http://localhost:8000', repo: 'https://github.com/vllm-project/vllm', installCmd: 'docker run -d --name vllm --gpus all -p 8000:8000 vllm/vllm-openai', category: 'api' },
  { name: 'VS Code Server', icon: '💻', desc: 'Code-Editor im Browser', port: 8443, url: 'http://localhost:8443', repo: 'https://github.com/coder/code-server', installCmd: 'curl -fsSL https://code-server.dev/install.sh | sh && code-server --port 8443 --auth none --bind-addr 0.0.0.0', category: 'dev' },
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
export default function GhostLLMManager({ windowId, onOpenWindow }) {
  const { settings: appSettings, schema: appSchema, update: updateAppSetting, reset: resetAppSettings } = useAppSettings('ghost-llm-manager')
  const [showAppSettings, setShowAppSettings] = useState(false)

  // ─── Persistenz-Keys (localStorage) ─────────
  const PERSIST_KEY = 'dbai_llm_manager_state'
  const loadPersisted = () => {
    try { return JSON.parse(localStorage.getItem(PERSIST_KEY)) || {} } catch { return {} }
  }
  const savePersisted = (patch) => {
    try {
      const current = loadPersisted()
      localStorage.setItem(PERSIST_KEY, JSON.stringify({ ...current, ...patch }))
    } catch {}
  }
  const persisted = loadPersisted()

  // ─── Tab-State (persistiert) ────────────────────
  const [tab, setTab] = useState(persisted.tab || appSettings?.default_tab || 'agents')

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
  const [scanPaths, setScanPaths] = useState('/home,/opt,/mnt,/mnt/nvme,/data')
  const [downloading, setDownloading] = useState(null)
  const [downloadRepo, setDownloadRepo] = useState('')
  const [vramBudget, setVramBudget] = useState(null)

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
  const [gpuBenchResult, setGpuBenchResult] = useState(null)
  const [gpuBenching, setGpuBenching] = useState(false)
  const [modelBenching, setModelBenching] = useState(null)
  const [modelStarting, setModelStarting] = useState(null)
  const [modelStopping, setModelStopping] = useState(null)
  const [selectedModelConfig, setSelectedModelConfig] = useState(null)
  const [modelRecommendation, setModelRecommendation] = useState(null)
  const [modelConfigOverrides, setModelConfigOverrides] = useState({})

  // ─── LLM Server (CPU/GPU) ────────
  const [llmServerStatus, setLlmServerStatus] = useState(null)
  const [llmServerRestarting, setLlmServerRestarting] = useState(false)

  // ─── VRAM Live-Monitoring ───────
  const [vramLive, setVramLive] = useState(null)
  const vramPollRef = useRef(null)

  // ─── Ghost Hot-Swap ───────────────
  const [ghostData, setGhostData] = useState({ active_ghosts: [], models: [], roles: [], compatibility: [] })
  const [ghostSwapping, setGhostSwapping] = useState(false)
  const [selectedGhostRole, setSelectedGhostRole] = useState(null)
  const [ghostTab, setGhostTab] = useState(persisted.ghostTab || 'roles')
  const [ghostHistory, setGhostHistory] = useState([])

  // ─── Rollen-Edit ──────────────────
  const [editingRole, setEditingRole] = useState(null)
  const [roleForm, setRoleForm] = useState({})
  const [roleSaving, setRoleSaving] = useState(false)

  // ─── Instanz-Erstellung ───────────
  const [instanceCreating, setInstanceCreating] = useState(false)

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

  const loadLlmServerStatus = useCallback(async () => {
    try {
      const data = await api.llmServerStatus()
      setLlmServerStatus(data)
    } catch (e) { console.error('LLM-Server Status:', e) }
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

  const loadGhosts = useCallback(async () => {
    try {
      const data = await api.ghosts()
      setGhostData(data || { active_ghosts: [], models: [], roles: [], compatibility: [] })
    } catch (e) { console.error('Ghosts laden:', e) }
  }, [])

  const loadGhostHistory = useCallback(async () => {
    try {
      const data = await api.ghostHistory(30)
      setGhostHistory(data || [])
    } catch (e) { console.error('Ghost-History laden:', e) }
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
      loadModels(), loadChains(), loadJobs(), loadBenchmarks(), loadVramBudget(),
      loadGhosts(), loadLlmServerStatus()
    ]).finally(() => {
      clearTimeout(timeout)
      setLoading(false)
    })
  }, [])

  // ─── Persistenz: Tab-Wechsel speichern ─────────
  useEffect(() => { savePersisted({ tab }) }, [tab])
  useEffect(() => { savePersisted({ ghostTab }) }, [ghostTab])
  useEffect(() => {
    if (selectedInstance) savePersisted({ selectedInstance })
  }, [selectedInstance])

  // ─── Persistenz: Gespeicherten selectedInstance wiederherstellen ───
  useEffect(() => {
    if (persisted.selectedInstance && instances.length > 0) {
      const exists = instances.find(i => i.id === persisted.selectedInstance)
      if (exists && !selectedInstance) {
        setSelectedInstance(persisted.selectedInstance)
        loadTasks(persisted.selectedInstance)
      }
    }
  }, [instances])

  // Auto-refresh GPU + instances + ghosts every 10s
  useEffect(() => {
    refreshRef.current = setInterval(() => {
      loadGpu()
      loadInstances()
      loadVramBudget()
      loadGhosts()
    }, 10000)
    return () => clearInterval(refreshRef.current)
  }, [loadGpu, loadInstances, loadGhosts])

  // Listen for ghost_swap events
  useEffect(() => {
    const handler = () => loadGhosts()
    window.addEventListener('dbai:ghost_swap', handler)
    return () => window.removeEventListener('dbai:ghost_swap', handler)
  }, [loadGhosts])

  /* ─── ACTION HANDLERS ────────────────────────────── */
  const confirmAndDo = (title, message, icon, action) => {
    setConfirmAction({ title, message, icon, action })
  }

  const handleCreateInstance = async () => {
    setInstanceCreating(true)
    // VRAM-Live-Polling starten
    if (vramPollRef.current) clearInterval(vramPollRef.current)
    vramPollRef.current = setInterval(async () => {
      try { const v = await api.vramLive(); setVramLive(v) } catch(e) {}
    }, 1000)
    try {
      const result = await api.agentsCreateInstance({ ...newInst, auto_start: true })
      if (result?.ok) {
        // Warte kurz damit VRAM-Polling den Ladevorgang zeigt
        await new Promise(r => setTimeout(r, 2000))
        setShowCreate(false)
        setNewInst({ model_id: '', role_id: '', gpu_index: 0, backend: 'llama.cpp', context_size: 4096, n_gpu_layers: 99, threads: 8, batch_size: 512 })
        await Promise.all([loadInstances(), loadGpu(), loadGhostModels(), loadModels()])
      } else {
        console.error('Instanz erstellen Ergebnis:', result)
      }
    } catch (e) { console.error('Instanz erstellen:', e) }
    // VRAM-Polling stoppen nach 5s
    setTimeout(() => {
      if (vramPollRef.current) { clearInterval(vramPollRef.current); vramPollRef.current = null }
    }, 5000)
    setInstanceCreating(false)
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
    confirmAndDo('Agent löschen', `Instanz "${inst.model_name || inst.model_id}" endgültig löschen?\nModell wird von GPU entladen und VRAM freigegeben.`, '🗑️', async () => {
      try {
        await api.agentsDeleteInstance(inst.id)
        if (selectedInstance === inst.id) { setSelectedInstance(null); setTasks([]) }
        // GPU + Modelle neu laden da VRAM jetzt frei ist
        await Promise.all([loadInstances(), loadGpu(), loadGhostModels(), loadModels()])
        setVramLive(null)
      } catch (e) { console.error('Löschen fehlgeschlagen:', e) }
    })
  }

  // ─── Rollen-Edit Handlers ───────────
  const handleEditRole = (role) => {
    setEditingRole(role.id || role.role_id)
    setRoleForm({
      display_name: role.display_name || role.role_name || role.name || '',
      description: role.description || '',
      icon: role.icon || '🎭',
      system_prompt: role.system_prompt || '',
      priority: role.priority || 5,
      is_critical: role.is_critical || false,
      accessible_schemas: Array.isArray(role.accessible_schemas) ? role.accessible_schemas.join(', ') : (role.accessible_schemas || ''),
      accessible_tables: Array.isArray(role.accessible_tables) ? role.accessible_tables.join(', ') : (role.accessible_tables || ''),
    })
  }

  const handleSaveRole = async (roleId) => {
    setRoleSaving(true)
    try {
      const payload = {
        display_name: roleForm.display_name,
        description: roleForm.description,
        icon: roleForm.icon,
        system_prompt: roleForm.system_prompt,
        priority: parseInt(roleForm.priority) || 5,
        is_critical: roleForm.is_critical,
        accessible_schemas: roleForm.accessible_schemas ? roleForm.accessible_schemas.split(',').map(s => s.trim()).filter(Boolean) : [],
        accessible_tables: roleForm.accessible_tables ? roleForm.accessible_tables.split(',').map(s => s.trim()).filter(Boolean) : [],
      }
      await api.agentsUpdateRole(roleId, payload)
      setEditingRole(null)
      setRoleForm({})
      await loadRoles()
    } catch (e) { console.error('Rolle speichern:', e) }
    setRoleSaving(false)
  }

  const handleCancelEditRole = () => {
    setEditingRole(null)
    setRoleForm({})
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

  const handleDownloadModel = async () => {
    if (!downloadRepo.trim()) return
    setDownloading(downloadRepo)
    try {
      const result = await api.llmDownloadModel(downloadRepo.trim(), '/mnt/nvme/models')
      if (result?.ok) {
        alert(`Download gestartet: ${downloadRepo}`)
        setDownloadRepo('')
        // Nach kurzer Wartezeit Modelle neu laden
        setTimeout(() => { loadModels(); loadGhostModels() }, 3000)
      } else {
        alert(`Fehler: ${result?.error || 'Unbekannt'}`)
      }
    } catch (e) { console.error('Download fehlgeschlagen:', e); alert('Download fehlgeschlagen: ' + e.message) }
    setDownloading(null)
  }

  const handleActivateModel = async (model) => {
    try {
      await api.llmActivateModel(model.id)
      await loadModels()
      await loadGhostModels()
      window.dispatchEvent(new CustomEvent('dbai:llm_model_change', { detail: { action: 'activate', model: model.name } }))
    } catch (e) { console.error('Aktivieren fehlgeschlagen:', e) }
  }

  const handleDeactivateModel = async (model) => {
    try {
      await api.llmDeactivateModel(model.id)
      await loadModels()
      await loadGhostModels()
      window.dispatchEvent(new CustomEvent('dbai:llm_model_change', { detail: { action: 'deactivate', model: model.name } }))
    } catch (e) { console.error('Deaktivieren fehlgeschlagen:', e) }
  }

  const loadVramBudget = useCallback(async () => {
    try {
      const data = await api.gpuVramBudget()
      setVramBudget(data)
      // Admin-Alert bei kritischem VRAM
      if (data?.alerts?.length > 0) {
        data.alerts.forEach(a => {
          if (a.alert === 'critical') {
            console.warn(`⚠️ VRAM KRITISCH: ${a.alert_message}`)
          }
        })
      }
    } catch (e) { /* nvidia-smi nicht verfügbar */ }
  }, [])

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
    const gpuIdx = gpuInfo.length > 0 ? gpuInfo[0].gpu_index : 0
    confirmAndDo('Benchmark starten', `GPU-Benchmark für dieses Modell starten?\nDie GPU-Leistung wird gemessen und optimale Einstellungen berechnet.`, '📊', async () => {
      setModelBenching(modelId)
      try {
        const result = await api.llmRunBenchmark(modelId, gpuIdx)
        await loadBenchmarks()
        if (result.recommended) {
          setModelRecommendation(result)
          setSelectedModelConfig(modelId)
        }
      } catch (e) { console.error('Benchmark fehlgeschlagen:', e) }
      setModelBenching(null)
    })
  }

  const handleGpuBenchmark = async () => {
    setGpuBenching(true)
    try {
      const result = await api.gpuBenchmark(gpuInfo.length > 0 ? gpuInfo[0].gpu_index : 0)
      setGpuBenchResult(result)
    } catch (e) { console.error('GPU-Benchmark fehlgeschlagen:', e) }
    setGpuBenching(false)
  }

  const handleServerRestart = async (device) => {
    setLlmServerRestarting(true)
    try {
      const config = {
        device: device,
        n_gpu_layers: device === 'gpu' ? 99 : 0,
        ctx_size: llmServerStatus?.ctx_size || 8192,
        threads: llmServerStatus?.threads || 12,
      }
      const result = await api.llmServerRestart(config)
      if (result?.ok) {
        await loadLlmServerStatus()
      }
    } catch (e) { console.error('Server-Neustart fehlgeschlagen:', e) }
    setLlmServerRestarting(false)
  }

  const handleServerRestartFull = async (config) => {
    setLlmServerRestarting(true)
    try {
      const result = await api.llmServerRestart(config)
      if (result?.ok) {
        await loadLlmServerStatus()
      }
    } catch (e) { console.error('Server-Neustart fehlgeschlagen:', e) }
    setLlmServerRestarting(false)
  }

  const handleStartModel = async (model) => {
    const gpuIdx = gpuInfo.length > 0 ? gpuInfo[0].gpu_index : 0
    setModelStarting(model.id)

    // ── VRAM-Live-Polling starten (alle 1s) ──
    if (vramPollRef.current) clearInterval(vramPollRef.current)
    vramPollRef.current = setInterval(async () => {
      try {
        const v = await api.vramLive()
        setVramLive(v)
      } catch(e) {}
    }, 1000)

    try {
      // GPU-Empfehlung holen oder Defaults nutzen
      let settings = {
        gpu_index: gpuIdx,
        n_gpu_layers: 99,
        context_size: 8192,
        batch_size: 512,
        threads: 10,
        backend: 'llama.cpp',
        device: 'gpu',
      }

      try {
        const rec = await api.gpuRecommend(model.id, gpuIdx)
        if (rec?.recommended) {
          settings = {
            gpu_index: gpuIdx,
            n_gpu_layers: modelConfigOverrides[model.id]?.n_gpu_layers ?? rec.recommended.n_gpu_layers,
            context_size: modelConfigOverrides[model.id]?.context_size ?? rec.recommended.context_size,
            batch_size: modelConfigOverrides[model.id]?.batch_size ?? rec.recommended.batch_size,
            threads: modelConfigOverrides[model.id]?.threads ?? rec.recommended.threads,
            backend: modelConfigOverrides[model.id]?.backend || 'llama.cpp',
            device: 'gpu',
          }
        }
      } catch (e) {
        console.warn('GPU-Empfehlung fehlgeschlagen, nutze Defaults:', e)
      }

      const result = await api.llmStartModel(model.id, settings)
      if (result?.ok) {
        // Warte kurz und stoppe VRAM-Polling
        await new Promise(r => setTimeout(r, 3000))
        await loadModels()
        await loadGhostModels()
        await loadInstances()
        await loadGpu()
        await loadLlmServerStatus()
      } else {
        console.error('Modell-Start Ergebnis:', result)
      }
    } catch (e) { console.error('Modell starten fehlgeschlagen:', e) }

    // VRAM-Polling stoppen nach 5s
    setTimeout(() => {
      if (vramPollRef.current) { clearInterval(vramPollRef.current); vramPollRef.current = null }
    }, 5000)
    setModelStarting(null)
  }

  const handleStopModel = async (model) => {
    setModelStopping(model.id)
    // VRAM-Polling stoppen
    if (vramPollRef.current) { clearInterval(vramPollRef.current); vramPollRef.current = null }
    try {
      await api.llmStopModel(model.id)
      await loadModels()
      await loadGhostModels()
      await loadInstances()
      await loadGpu()
      await loadLlmServerStatus()
      setVramLive(null)
    } catch (e) { console.error('Modell stoppen fehlgeschlagen:', e) }
    setModelStopping(null)
  }

  const handleShowModelConfig = async (model) => {
    const gpuIdx = gpuInfo.length > 0 ? gpuInfo[0].gpu_index : 0
    setSelectedModelConfig(selectedModelConfig === model.id ? null : model.id)
    setModelRecommendation(null)
    try {
      const rec = await api.gpuRecommend(model.id, gpuIdx)
      setModelRecommendation(rec)
    } catch (e) { console.error('GPU-Empfehlung fehlgeschlagen:', e) }
  }

  const openWebFrame = (url, title) => {
    if (onOpenWindow) onOpenWindow('webframe', { url, title })
  }

  // ─── Ghost Hot-Swap Handlers ────────────
  const handleGhostSwap = async (roleName, modelName) => {
    setGhostSwapping(true)
    try {
      await api.swapGhost(roleName, modelName, 'Manueller Wechsel via Ghost LLM Manager')
      setTimeout(loadGhosts, 500)
    } catch (err) {
      alert('Swap fehlgeschlagen: ' + err.message)
    }
    setGhostSwapping(false)
  }

  const getActiveModelForRole = (roleName) => {
    return ghostData.active_ghosts.find(g => g.role_name === roleName)
  }

  const getCompatModels = (roleName) => {
    return ghostData.compatibility
      .filter(c => c.role_name === roleName)
      .sort((a, b) => b.fitness_score - a.fitness_score)
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
                    <button style={S.btnDanger} onClick={() => handleDeleteInstance(inst)} title="Instanz löschen & GPU freigeben">🗑️ Entladen</button>
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

              {/* VRAM Live-Feedback während Instanz-Erstellung */}
              {instanceCreating && vramLive && (
                <div style={{ marginTop: '12px' }}>
                  <VramBar used={vramLive.used_mb || 0} total={vramLive.total_mb || 1} label="⏳ GPU wird geladen…" height={22} />
                </div>
              )}

              <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', marginTop: '16px' }}>
                <button style={S.btnPrimary} onClick={handleCreateInstance} disabled={!newInst.model_id || instanceCreating}>
                  {instanceCreating ? '⏳ Modell wird auf GPU geladen…' : '🚀 Instanz erstellen + GPU laden'}
                </button>
                <button style={S.btnSmall} onClick={() => setShowCreate(false)} disabled={instanceCreating}>Abbrechen</button>
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
      {/* ─── LLM Server Steuerung (CPU / GPU) ───────────────── */}
      <div style={{
        padding: '14px 16px', borderRadius: '10px', marginBottom: '12px',
        background: 'linear-gradient(135deg, rgba(136,68,255,0.08), rgba(0,200,255,0.06))',
        border: `1px solid ${llmServerStatus?.ok ? 'rgba(0,255,136,0.2)' : 'rgba(255,68,68,0.2)'}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap', marginBottom: '10px' }}>
          <span style={{ fontSize: '24px' }}>{llmServerStatus?.ok ? '🟢' : '🔴'}</span>
          <div style={{ flex: 1, minWidth: '200px' }}>
            <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>
              LLM Inferenz-Server
              <span style={{
                marginLeft: '8px', padding: '2px 8px', borderRadius: '4px', fontSize: '10px', fontWeight: 600,
                background: llmServerStatus?.ok ? 'rgba(0,255,136,0.12)' : 'rgba(255,68,68,0.12)',
                color: llmServerStatus?.ok ? '#00ff88' : '#ff4444',
              }}>
                {llmServerStatus?.ok ? 'Online' : 'Offline'}
              </span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
              {llmServerStatus?.ok ? (
                <>
                  Modell: <strong>{llmServerStatus.model_name}</strong>
                  {' · '}Gerät: <strong style={{ color: llmServerStatus.device === 'gpu' ? '#00ff88' : '#ffaa00' }}>
                    {llmServerStatus.device === 'gpu' ? `🎮 GPU (${llmServerStatus.n_gpu_layers} Layer)` : '🖥️ CPU'}
                  </strong>
                  {' · '}Kontext: {llmServerStatus.ctx_size?.toLocaleString()} · Threads: {llmServerStatus.threads}
                </>
              ) : (
                'Server nicht erreichbar – starte ihn mit GPU oder CPU'
              )}
            </div>
          </div>
        </div>

        {/* CPU / GPU Umschalter */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{
            display: 'inline-flex', borderRadius: '8px', overflow: 'hidden',
            border: '1px solid rgba(255,255,255,0.1)',
          }}>
            <button
              style={{
                padding: '7px 16px', border: 'none', cursor: 'pointer', fontSize: '12px', fontWeight: 600,
                background: (llmServerStatus?.device === 'gpu' || !llmServerStatus?.ok) ? 'rgba(0,255,136,0.15)' : 'rgba(255,255,255,0.04)',
                color: (llmServerStatus?.device === 'gpu' || !llmServerStatus?.ok) ? '#00ff88' : 'var(--text-secondary)',
                transition: 'all 0.2s',
              }}
              disabled={llmServerRestarting}
              onClick={() => handleServerRestart('gpu')}
              title="Modell auf GPU laden — schnell, nutzt VRAM"
            >
              🎮 GPU
            </button>
            <button
              style={{
                padding: '7px 16px', border: 'none', cursor: 'pointer', fontSize: '12px', fontWeight: 600,
                borderLeft: '1px solid rgba(255,255,255,0.1)',
                background: llmServerStatus?.device === 'cpu' ? 'rgba(255,170,0,0.15)' : 'rgba(255,255,255,0.04)',
                color: llmServerStatus?.device === 'cpu' ? '#ffaa00' : 'var(--text-secondary)',
                transition: 'all 0.2s',
              }}
              disabled={llmServerRestarting}
              onClick={() => handleServerRestart('cpu')}
              title="Modell auf CPU laden — langsam, kein VRAM nötig"
            >
              🖥️ CPU
            </button>
          </div>

          {llmServerRestarting && (
            <span style={{ fontSize: '12px', color: 'var(--accent)', animation: 'pulse 1s infinite' }}>
              ⏳ Server wird neu gestartet… (Modell wird geladen, kann bis zu 2 Min dauern)
            </span>
          )}

          {/* Erweiterte Einstellungen */}
          {llmServerStatus?.ok && (
            <div style={{ marginLeft: 'auto', display: 'flex', gap: '6px', alignItems: 'center' }}>
              <select
                style={{ ...S.select, width: '120px', fontSize: '11px' }}
                value={llmServerStatus?.ctx_size || 8192}
                onChange={e => handleServerRestartFull({
                  device: llmServerStatus.device,
                  n_gpu_layers: llmServerStatus.n_gpu_layers,
                  ctx_size: +e.target.value,
                  threads: llmServerStatus.threads,
                })}
                title="Kontext-Größe"
              >
                {[2048, 4096, 8192, 16384, 32768, 65536].map(v => (
                  <option key={v} value={v}>Ctx: {v.toLocaleString()}</option>
                ))}
              </select>
              <select
                style={{ ...S.select, width: '100px', fontSize: '11px' }}
                value={llmServerStatus?.threads || 12}
                onChange={e => handleServerRestartFull({
                  device: llmServerStatus.device,
                  n_gpu_layers: llmServerStatus.n_gpu_layers,
                  ctx_size: llmServerStatus.ctx_size,
                  threads: +e.target.value,
                })}
                title="CPU Threads"
              >
                {[4, 8, 12, 16, 24, 32].map(v => (
                  <option key={v} value={v}>{v} Threads</option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* GPU Benchmark Banner */}
      <div style={{
        padding: '12px 16px', borderRadius: '10px',
        background: 'linear-gradient(135deg, rgba(0,255,200,0.06), rgba(68,136,255,0.06))',
        border: '1px solid rgba(0,255,200,0.15)',
        display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap',
      }}>
        <span style={{ fontSize: '24px' }}>🎮</span>
        <div style={{ flex: 1, minWidth: '200px' }}>
          <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>GPU-Benchmark zuerst</div>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
            Messe die GPU-Leistung, um optimale Modell-Einstellungen zu berechnen (VRAM, Layer, Kontext)
          </div>
        </div>
        {gpuBenchResult?.ok && gpuBenchResult.gpus?.length > 0 && (
          <div style={{ fontSize: '11px', color: '#00ff88', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            {gpuBenchResult.gpus.map((g, i) => (
              <span key={i}>
                ✅ {g.name}: {g.vram_free_mb} MB frei · {g.memory_bandwidth_gbs} GB/s · {g.architecture}
              </span>
            ))}
          </div>
        )}
        <button style={S.btnPrimary} onClick={handleGpuBenchmark} disabled={gpuBenching}>
          {gpuBenching ? '⏳ Benchmark läuft…' : '🔥 GPU benchmarken'}
        </button>
      </div>

      {/* GPU Benchmark Ergebnis */}
      {gpuBenchResult?.ok && gpuBenchResult.gpus?.map((gpu, gi) => (
        <div key={gi} style={S.section}>
          <div style={S.sectionHeader}>
            <span>🖥️ {gpu.name} — {gpu.architecture}</span>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
              Treiber: {gpu.driver_version} · PCIe Gen{gpu.pcie_gen} x{gpu.pcie_width}
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: '8px', marginBottom: '12px' }}>
            {[
              { label: 'VRAM Frei', value: formatMB(gpu.vram_free_mb), color: '#00ff88' },
              { label: 'VRAM Gesamt', value: formatMB(gpu.vram_total_mb), color: 'var(--accent)' },
              { label: 'Bandbreite', value: `${gpu.memory_bandwidth_gbs} GB/s`, color: '#4488ff' },
              { label: 'Temperatur', value: `${gpu.temperature_c}°C`, color: gpu.temperature_c > 80 ? '#ff4444' : '#00ff88' },
              { label: 'Core Clock', value: `${gpu.clock_core_mhz} MHz`, color: 'var(--text-secondary)' },
              { label: 'Power', value: `${Math.round(gpu.power_draw_w)}/${Math.round(gpu.power_limit_w)} W`, color: 'var(--text-secondary)' },
            ].map((s, i) => (
              <div key={i} style={{ padding: '8px', background: 'rgba(0,0,0,0.2)', borderRadius: '6px', textAlign: 'center' }}>
                <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>{s.label}</div>
                <div style={{ fontSize: '14px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: s.color }}>{s.value}</div>
              </div>
            ))}
          </div>

          {/* Geschätzte Token-Geschwindigkeit */}
          <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '6px', fontWeight: 600 }}>
            Geschätzte Token/s nach Modellgröße:
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
            {Object.entries(gpu.estimated_token_speed).map(([key, tps]) => (
              <div key={key} style={{
                padding: '4px 10px', borderRadius: '6px', fontSize: '11px',
                background: tps > 40 ? 'rgba(0,255,136,0.1)' : tps > 20 ? 'rgba(255,170,0,0.1)' : 'rgba(255,68,68,0.1)',
                color: tps > 40 ? '#00ff88' : tps > 20 ? '#ffaa00' : '#ff4444',
                fontFamily: 'var(--font-mono)',
              }}>
                {key.replace('_', ' ')}: <strong>{tps} t/s</strong>
              </div>
            ))}
          </div>

          {/* Modell-Empfehlungen */}
          {gpu.model_recommendations?.length > 0 && (
            <>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '6px', fontWeight: 600 }}>
                Empfohlene Modellgrößen für diese GPU:
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {gpu.model_recommendations.map((rec, ri) => (
                  <div key={ri} style={{
                    padding: '6px 10px', borderRadius: '6px', fontSize: '11px',
                    background: rec.fits === 'full' ? 'rgba(0,255,136,0.08)' : 'rgba(255,170,0,0.08)',
                    border: `1px solid ${rec.fits === 'full' ? 'rgba(0,255,136,0.2)' : 'rgba(255,170,0,0.2)'}`,
                  }}>
                    <div style={{ fontWeight: 600, color: rec.fits === 'full' ? '#00ff88' : '#ffaa00' }}>
                      {rec.fits === 'full' ? '✅' : '⚠️'} {rec.label}
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      {rec.quant} · Ctx: {rec.context.toLocaleString()} · ~{rec.est_tps} t/s
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      ))}

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
          <div style={{ maxHeight: '250px', overflowY: 'auto' }}>
            {scanResults.map((r, i) => (
              <div key={i} style={S.scanRow}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '14px' }}>{r.type === 'huggingface_dir' ? '🤗' : '📄'}</span>
                    <span style={{ fontSize: '12px', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{r.filename || r.name}</span>
                    {r.type === 'huggingface_dir' && (
                      <span style={{ ...S.badge, fontSize: '9px', background: 'rgba(255,170,0,0.15)', color: '#ffaa00' }}>HF</span>
                    )}
                    {r.model_type && (
                      <span style={{ ...S.badge, fontSize: '9px' }}>{r.model_type}</span>
                    )}
                    {r.param_estimate && (
                      <span style={{ ...S.badge, fontSize: '9px', background: 'rgba(0,255,204,0.1)', color: 'var(--accent)' }}>{r.param_estimate}</span>
                    )}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                    {r.path} · {r.size_display || formatBytes(r.size)}
                    {r.has_weights === false && <span style={{ color: '#ff6644', marginLeft: '6px' }}>⚠ Keine Gewichte</span>}
                    {r.has_weights === true && <span style={{ color: '#00ff88', marginLeft: '6px' }}>✓ {r.weight_count} Gewichtsdatei(en)</span>}
                    {r.quantization && <span style={{ marginLeft: '6px' }}>· Quantisierung: {r.quantization}</span>}
                  </div>
                </div>
                <button style={S.btnSmall} onClick={() => handleAddModel({
                  ...r,
                  name: r.name_guess || r.filename,
                  model_path: r.path,
                  model_format: r.format || r.type,
                })}>+ Hinzufügen</button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Download von HuggingFace */}
      <div style={S.section}>
        <div style={S.sectionHeader}>
          <span>⬇️ Modell herunterladen</span>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <input
            style={{ ...S.input, flex: 1 }}
            value={downloadRepo}
            onChange={e => setDownloadRepo(e.target.value)}
            placeholder="HuggingFace Repo-ID (z.B. Qwen/Qwen2.5-7B-Instruct-GGUF)"
          />
          <button
            style={{ ...S.btnPrimary, whiteSpace: 'nowrap', opacity: downloading ? 0.5 : 1 }}
            onClick={handleDownloadModel}
            disabled={!!downloading || !downloadRepo.trim()}
          >
            {downloading ? '⏳ Lade…' : '⬇️ Download'}
          </button>
        </div>
        <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Zielverzeichnis: /mnt/nvme/models · Unterstützt: GGUF, SafeTensors, PyTorch
        </div>
      </div>

      {/* Model Registry — ALLE Modelle mit Start/Stop/Benchmark */}
      <div style={S.section}>
        <div style={S.sectionHeader}>
          <span>📦 Registrierte Modelle ({models.length})</span>
          <button style={S.btnSmall} onClick={loadModels}>↻</button>
        </div>
        {models.length === 0 ? (
          <div style={S.emptyState}>Keine Modelle registriert</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {models.map(m => {
              const isActive = m.state === 'active' || m.state === 'loaded'
              const isStarting = modelStarting === m.id
              const isStopping = modelStopping === m.id
              const isBenching = modelBenching === m.id
              const isConfigOpen = selectedModelConfig === m.id
              const hasGpu = gpuInfo.length > 0
              const gpu0 = gpuInfo[0] || {}

              return (
                <div key={m.id} style={{
                  padding: '12px 14px', background: 'var(--bg-surface)',
                  border: `1px solid ${isActive ? 'rgba(0,255,136,0.3)' : 'var(--border)'}`,
                  borderRadius: '10px',
                  boxShadow: isActive ? '0 0 15px rgba(0,255,136,0.06)' : 'none',
                }}>
                  {/* Model Header Row */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: '200px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {isActive && <StateDot state="running" />}
                        <span style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text-primary)' }}>{m.name}</span>
                        <span style={S.badge}>{m.format || m.model_format || '—'}</span>
                        {m.parameters || m.param_count ? (
                          <span style={{ ...S.badge, background: 'rgba(0,255,204,0.1)', color: 'var(--accent)' }}>
                            {m.parameters || m.param_count}
                          </span>
                        ) : null}
                      </div>
                      <div style={{ fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
                        {m.model_path || m.path || '—'}
                        {m.vram_required_mb > 0 && ` · VRAM: ${formatMB(m.vram_required_mb)}`}
                        {m.context_length > 0 && ` · Ctx: ${m.context_length?.toLocaleString()}`}
                      </div>
                    </div>

                    {/* Status Badge */}
                    <span style={{
                      ...S.badge, fontSize: '10px', fontWeight: 600,
                      background: isActive ? 'rgba(0,255,136,0.12)' : 'rgba(255,255,255,0.05)',
                      color: isActive ? '#00ff88' : 'var(--text-secondary)',
                    }}>
                      {isActive ? '● Geladen' : '○ Verfügbar'}
                    </span>

                    {/* Action Buttons */}
                    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                      {/* Start / Stop */}
                      {isActive ? (
                        <button
                          style={{ ...S.btnStop, opacity: isStopping ? 0.5 : 1 }}
                          onClick={() => handleStopModel(m)}
                          disabled={isStopping}
                          title="Modell stoppen & entladen"
                        >
                          {isStopping ? '⏳' : '⏹'} Stoppen
                        </button>
                      ) : (
                        <button
                          style={{ ...S.btnStart, opacity: isStarting ? 0.5 : 1 }}
                          onClick={() => handleStartModel(m)}
                          disabled={isStarting}
                          title="Modell auf GPU laden (Auto-Konfiguration)"
                        >
                          {isStarting ? '⏳' : '▶'} Starten
                        </button>
                      )}

                      {/* Benchmark */}
                      <button
                        style={{ ...S.btnSmall, opacity: isBenching ? 0.5 : 1 }}
                        onClick={() => handleRunBenchmark(m.id)}
                        disabled={isBenching}
                        title="GPU-Benchmark für dieses Modell"
                      >
                        {isBenching ? '⏳' : '📊'} Benchmark
                      </button>

                      {/* GPU Config */}
                      <button
                        style={{ ...S.btnSmall, background: isConfigOpen ? 'rgba(0,255,200,0.1)' : undefined }}
                        onClick={() => handleShowModelConfig(m)}
                        title="GPU-Einstellungen anzeigen"
                      >
                        ⚙️ GPU-Config
                      </button>

                      {/* Delete */}
                      <button style={S.btnDanger} onClick={() => handleRemoveModel(m)} title="Modell entfernen">🗑️</button>
                    </div>
                  </div>

                  {/* ── VRAM Echtzeit-Ladebalken (beim Laden/Entladen) ── */}
                  {(isStarting || (isActive && vramLive?.gpus?.[0])) && (() => {
                    const gpu = vramLive?.gpus?.[0] || (gpuInfo[0] ? { used_mb: gpuInfo[0].memory_used_mb, total_mb: gpuInfo[0].memory_total_mb, pct: Math.round(gpuInfo[0].memory_used_mb / gpuInfo[0].memory_total_mb * 100), util: gpuInfo[0].utilization, temp: gpuInfo[0].temperature, power_w: 0 } : null)
                    if (!gpu) return null
                    const llm = vramLive?.llm || {}
                    const color = gpu.pct > 90 ? '#ff4444' : gpu.pct > 70 ? '#ffaa00' : '#00ff88'
                    return (
                      <div style={{ marginTop: '10px', padding: '10px 12px', borderRadius: '8px', background: 'rgba(0,245,255,0.03)', border: '1px solid rgba(0,245,255,0.12)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                          <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-primary)' }}>
                            {isStarting ? '⏳ GPU wird geladen…' : `✅ ${llm.model || m.name} auf GPU`}
                          </span>
                          <span style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                            {gpu.temp}°C · {gpu.util}% · {gpu.power_w > 0 ? `${Math.round(gpu.power_w)}W` : ''}
                          </span>
                        </div>
                        <div style={{ height: '22px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', overflow: 'hidden', position: 'relative' }}>
                          <div style={{
                            height: '100%', width: `${gpu.pct}%`, borderRadius: '6px',
                            background: `linear-gradient(90deg, ${color}66, ${color})`,
                            transition: 'width 0.8s ease-out',
                            boxShadow: isStarting ? `0 0 12px ${color}44` : 'none',
                            animation: isStarting ? 'pulse 1.5s infinite' : 'none',
                          }} />
                          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#fff', textShadow: '0 1px 3px rgba(0,0,0,0.9)' }}>
                            {formatMB(gpu.used_mb)} / {formatMB(gpu.total_mb)} VRAM ({gpu.pct}%)
                          </div>
                        </div>
                        {llm.healthy !== undefined && (
                          <div style={{ marginTop: '4px', fontSize: '10px', color: llm.healthy ? '#00ff88' : '#ffaa00' }}>
                            {llm.healthy ? `● LLM-Server bereit (${llm.device?.toUpperCase()}, ${llm.gpu_layers} Layer)` : '○ LLM-Server startet…'}
                          </div>
                        )}
                      </div>
                    )
                  })()}

                  {/* GPU Configuration Panel (expandable) */}
                  {isConfigOpen && (
                    <div style={{
                      marginTop: '12px', padding: '12px', borderRadius: '8px',
                      background: 'rgba(0,255,200,0.03)', border: '1px solid rgba(0,255,200,0.12)',
                    }}>
                      <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent)', marginBottom: '10px' }}>
                        ⚙️ GPU-Konfiguration — {m.name}
                      </div>

                      {modelRecommendation?.recommended ? (() => {
                        const rec = modelRecommendation.recommended
                        const gpuData = modelRecommendation.gpu || {}
                        const overrides = modelConfigOverrides[m.id] || {}

                        return (
                          <div>
                            {/* GPU + Model Summary */}
                            <div style={{ display: 'flex', gap: '16px', marginBottom: '12px', flexWrap: 'wrap' }}>
                              <div style={{ flex: 1, minWidth: '150px' }}>
                                <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '4px' }}>GPU</div>
                                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                                  {gpuData.name || 'Unbekannt'}
                                </div>
                                <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                                  VRAM: {formatMB(gpuData.vram_free_mb || 0)} frei von {formatMB(gpuData.vram_total_mb || 0)}
                                  {gpuData.bandwidth_gbs ? ` · ${gpuData.bandwidth_gbs} GB/s` : ''}
                                </div>
                              </div>
                              <div style={{ flex: 1, minWidth: '150px' }}>
                                <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '4px' }}>Offload-Status</div>
                                <div style={{
                                  fontSize: '13px', fontWeight: 700,
                                  color: rec.fits_fully ? '#00ff88' : rec.offload_pct > 50 ? '#ffaa00' : '#ff4444',
                                }}>
                                  {rec.fits_fully ? '✅ Vollständig auf GPU' : `⚠️ ${rec.offload_pct}% auf GPU`}
                                </div>
                                <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                                  {rec.n_gpu_layers} / {rec.total_layers} Layer · {formatMB(rec.vram_needed_mb)} benötigt
                                </div>
                              </div>
                            </div>

                            {/* VRAM Visualisierung */}
                            <VramBar
                              used={rec.vram_needed_mb}
                              total={gpuData.vram_free_mb || rec.vram_available_mb}
                              label="VRAM-Belegung durch dieses Modell"
                              height={20}
                            />

                            {/* Konfiguration zum Anpassen */}
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '10px', marginTop: '12px' }}>
                              <label style={S.label}>
                                GPU-Layer ({rec.total_layers} max)
                                <input
                                  style={S.input}
                                  type="number"
                                  min={0}
                                  max={rec.total_layers}
                                  value={overrides.n_gpu_layers ?? rec.n_gpu_layers}
                                  onChange={e => setModelConfigOverrides(prev => ({
                                    ...prev,
                                    [m.id]: { ...(prev[m.id] || {}), n_gpu_layers: +e.target.value }
                                  }))}
                                />
                                <div style={{ fontSize: '9px', color: 'var(--text-secondary)' }}>
                                  Empfohlen: {rec.n_gpu_layers} — Mehr = schneller, mehr VRAM
                                </div>
                              </label>

                              <label style={S.label}>
                                Kontext-Größe
                                <select
                                  style={S.select}
                                  value={overrides.context_size ?? rec.context_size}
                                  onChange={e => setModelConfigOverrides(prev => ({
                                    ...prev,
                                    [m.id]: { ...(prev[m.id] || {}), context_size: +e.target.value }
                                  }))}
                                >
                                  {[2048, 4096, 8192, 16384, 32768, 65536, 131072].map(v => (
                                    <option key={v} value={v}>{v.toLocaleString()} Token</option>
                                  ))}
                                </select>
                                <div style={{ fontSize: '9px', color: 'var(--text-secondary)' }}>
                                  Empfohlen: {rec.context_size.toLocaleString()} — Größer = mehr VRAM
                                </div>
                              </label>

                              <label style={S.label}>
                                Batch-Größe
                                <select
                                  style={S.select}
                                  value={overrides.batch_size ?? rec.batch_size}
                                  onChange={e => setModelConfigOverrides(prev => ({
                                    ...prev,
                                    [m.id]: { ...(prev[m.id] || {}), batch_size: +e.target.value }
                                  }))}
                                >
                                  {[128, 256, 512, 1024, 2048].map(v => (
                                    <option key={v} value={v}>{v}</option>
                                  ))}
                                </select>
                                <div style={{ fontSize: '9px', color: 'var(--text-secondary)' }}>
                                  Empfohlen: {rec.batch_size}
                                </div>
                              </label>

                              <label style={S.label}>
                                Threads
                                <input
                                  style={S.input}
                                  type="number"
                                  min={1}
                                  max={64}
                                  value={overrides.threads ?? rec.threads}
                                  onChange={e => setModelConfigOverrides(prev => ({
                                    ...prev,
                                    [m.id]: { ...(prev[m.id] || {}), threads: +e.target.value }
                                  }))}
                                />
                                <div style={{ fontSize: '9px', color: 'var(--text-secondary)' }}>
                                  Empfohlen: {rec.threads}
                                </div>
                              </label>

                              <label style={S.label}>
                                Backend
                                <select
                                  style={S.select}
                                  value={overrides.backend || 'llama.cpp'}
                                  onChange={e => setModelConfigOverrides(prev => ({
                                    ...prev,
                                    [m.id]: { ...(prev[m.id] || {}), backend: e.target.value }
                                  }))}
                                >
                                  {BACKENDS.map(b => (
                                    <option key={b.value} value={b.value}>{b.icon} {b.label}</option>
                                  ))}
                                </select>
                              </label>
                            </div>

                            {/* Quick-Start */}
                            <div style={{ display: 'flex', gap: '8px', marginTop: '12px', alignItems: 'center' }}>
                              <button
                                style={S.btnPrimary}
                                onClick={() => handleStartModel(m)}
                                disabled={isStarting || isActive}
                              >
                                {isStarting ? '⏳ Wird geladen…' : isActive ? '✅ Läuft bereits' : '🚀 Mit diesen Einstellungen starten'}
                              </button>
                              <button
                                style={S.btnSmall}
                                onClick={() => {
                                  setModelConfigOverrides(prev => {
                                    const copy = { ...prev }
                                    delete copy[m.id]
                                    return copy
                                  })
                                }}
                              >
                                ↺ Zurücksetzen
                              </button>
                            </div>
                          </div>
                        )
                      })() : (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--text-secondary)', fontSize: '12px' }}>
                          <span style={{ animation: 'pulse 1s infinite' }}>⏳</span>
                          GPU-Empfehlung wird berechnet…
                        </div>
                      )}
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
              const roleId = r.id || r.role_id
              const isEditing = editingRole === roleId
              const assignedInstances = instances.filter(i => i.role_id === roleId)
              return (
                <div key={roleId} style={{ ...S.roleCard, borderLeft: isEditing ? '3px solid var(--accent)' : undefined }}>
                  {isEditing ? (
                    /* ─── EDIT MODE ─── */
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--accent)' }}>✏️ Rolle bearbeiten</div>
                      <div style={{ display: 'grid', gridTemplateColumns: '60px 1fr', gap: '8px', alignItems: 'center' }}>
                        <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Icon</label>
                        <input style={S.input} value={roleForm.icon || ''} onChange={e => setRoleForm(p => ({ ...p, icon: e.target.value }))} placeholder="🎭" />
                        <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Name</label>
                        <input style={S.input} value={roleForm.display_name || ''} onChange={e => setRoleForm(p => ({ ...p, display_name: e.target.value }))} placeholder="Anzeigename" />
                        <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Beschreibung</label>
                        <input style={S.input} value={roleForm.description || ''} onChange={e => setRoleForm(p => ({ ...p, description: e.target.value }))} placeholder="Rollenbeschreibung" />
                        <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Priorität</label>
                        <input style={S.input} type="number" min={1} max={100} value={roleForm.priority || 5} onChange={e => setRoleForm(p => ({ ...p, priority: +e.target.value }))} />
                        <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Kritisch</label>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', cursor: 'pointer' }}>
                          <input type="checkbox" checked={roleForm.is_critical || false} onChange={e => setRoleForm(p => ({ ...p, is_critical: e.target.checked }))} />
                          {roleForm.is_critical ? '🔴 Ja' : '🟢 Nein'}
                        </label>
                        <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Schemas</label>
                        <input style={S.input} value={roleForm.accessible_schemas || ''} onChange={e => setRoleForm(p => ({ ...p, accessible_schemas: e.target.value }))} placeholder="dbai_core, dbai_llm, …" />
                        <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Tabellen</label>
                        <input style={S.input} value={roleForm.accessible_tables || ''} onChange={e => setRoleForm(p => ({ ...p, accessible_tables: e.target.value }))} placeholder="ghost_models, agents, …" />
                      </div>
                      <div>
                        <label style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>System-Prompt</label>
                        <textarea
                          style={{ ...S.input, minHeight: '80px', resize: 'vertical', fontFamily: 'var(--font-mono)', fontSize: '11px' }}
                          value={roleForm.system_prompt || ''}
                          onChange={e => setRoleForm(p => ({ ...p, system_prompt: e.target.value }))}
                          placeholder="System-Prompt für diese Rolle…"
                        />
                      </div>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button style={S.btnPrimary} onClick={() => handleSaveRole(roleId)} disabled={roleSaving}>
                          {roleSaving ? '⏳ Speichert…' : '💾 Speichern'}
                        </button>
                        <button style={S.btnSmall} onClick={handleCancelEditRole}>Abbrechen</button>
                      </div>
                    </div>
                  ) : (
                    /* ─── READ MODE ─── */
                    <>
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
                        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                          {assignedInstances.length > 0 ? (
                            <span style={S.badgeGreen}>{assignedInstances.length} Agent{assignedInstances.length > 1 ? 'en' : ''}</span>
                          ) : (
                            <span style={S.badgeGray}>Kein Agent</span>
                          )}
                          <button style={{ ...S.btnSmall, padding: '4px 10px' }} onClick={() => handleEditRole(r)} title="Rolle bearbeiten">
                            ✏️ Bearbeiten
                          </button>
                        </div>
                      </div>
                      {r.description && (
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>{r.description}</div>
                      )}
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
                    </>
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

      {/* VRAM Budget & Monitoring */}
      <div style={S.section}>
        <div style={S.sectionHeader}>
          <span>📊 VRAM Budget</span>
          <button style={S.btnSmall} onClick={loadVramBudget}>↻</button>
        </div>
        {vramBudget?.gpus?.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {vramBudget.gpus.map((gpu, i) => (
              <div key={i} style={{
                ...S.gpuDetailCard,
                borderLeft: `3px solid ${gpu.alert === 'critical' ? '#ff4444' : gpu.alert === 'warning' ? '#ffaa00' : 'var(--accent)'}`,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <div>
                    <span style={{ fontWeight: 600, fontSize: '13px' }}>GPU {gpu.gpu_index}: {gpu.name}</span>
                    {gpu.alert !== 'ok' && (
                      <span style={{
                        ...S.badge, marginLeft: '8px', fontSize: '9px',
                        background: gpu.alert === 'critical' ? 'rgba(255,68,68,0.15)' : 'rgba(255,170,0,0.15)',
                        color: gpu.alert === 'critical' ? '#ff4444' : '#ffaa00',
                      }}>
                        {gpu.alert === 'critical' ? '🔴 KRITISCH' : '🟡 WARNUNG'}
                      </span>
                    )}
                  </div>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--accent)' }}>
                    {gpu.temp_c}°C · {gpu.utilization_pct}% GPU
                  </span>
                </div>
                <VramBar
                  used={gpu.vram_used_mb}
                  total={gpu.vram_total_mb}
                  label={`${Math.round(gpu.vram_used_mb)} / ${Math.round(gpu.vram_total_mb)} MB (${gpu.vram_pct}%)`}
                  height={20}
                />
                {gpu.alert_message && (
                  <div style={{
                    marginTop: '6px', padding: '6px 10px', borderRadius: '4px', fontSize: '11px',
                    background: gpu.alert === 'critical' ? 'rgba(255,68,68,0.1)' : 'rgba(255,170,0,0.1)',
                    color: gpu.alert === 'critical' ? '#ff4444' : '#ffaa00',
                    border: `1px solid ${gpu.alert === 'critical' ? 'rgba(255,68,68,0.3)' : 'rgba(255,170,0,0.3)'}`,
                  }}>
                    ⚠️ {gpu.alert_message}
                  </div>
                )}
              </div>
            ))}
            {/* Geladene Modelle */}
            {vramBudget.loaded_models?.length > 0 && (
              <div style={{ marginTop: '4px' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '6px', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
                  Geladene Modelle ({vramBudget.loaded_models.length})
                </div>
                {vramBudget.loaded_models.map((lm, i) => (
                  <div key={i} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '4px 8px', fontSize: '11px',
                    borderBottom: '1px solid var(--border)',
                  }}>
                    <span style={{ fontWeight: 500 }}>{lm.name}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                      GPU {lm.gpu_index} · {lm.required_vram_mb ? `${lm.required_vram_mb} MB` : '—'}
                    </span>
                  </div>
                ))}
              </div>
            )}
            {vramBudget.alerts?.length > 0 && (
              <div style={{
                padding: '10px 14px', borderRadius: 'var(--radius)', fontSize: '12px',
                background: 'rgba(255,68,68,0.08)', border: '1px solid rgba(255,68,68,0.25)',
                color: '#ff6644',
              }}>
                ⚠️ <strong>Admin-Hinweis:</strong> {vramBudget.alerts.length} GPU(s) mit hoher VRAM-Auslastung.
                Modelle entladen oder auf mehrere GPUs verteilen.
              </div>
            )}
          </div>
        ) : (
          <div style={S.emptyState}>
            Keine GPU-Daten verfügbar. nvidia-smi nicht erreichbar oder kein GPU vorhanden.
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
            <div key={i} style={{ ...S.webuiCard, position: 'relative' }}>
              <div style={{ fontSize: '28px' }}>{ui.icon}</div>
              <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>{ui.name}</div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', minHeight: '28px' }}>{ui.desc}</div>
              <div style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--accent)', marginBottom: '6px' }}>:{ui.port}</div>
              <div style={{ display: 'flex', gap: '4px', width: '100%' }}>
                <button
                  style={{ ...S.btnSmall, flex: 1, fontSize: '10px', padding: '4px 6px' }}
                  onClick={(e) => { e.stopPropagation(); openWebFrame(ui.url, ui.name) }}
                  title="Im Browser öffnen"
                >🌐 Öffnen</button>
                {ui.installCmd && (
                  <button
                    style={{ ...S.btnSmall, flex: 1, fontSize: '10px', padding: '4px 6px', background: 'rgba(0,255,136,0.1)', border: '1px solid rgba(0,255,136,0.3)', color: '#00ff88' }}
                    onClick={async (e) => {
                      e.stopPropagation()
                      if (!confirm(`${ui.name} installieren?\n\nBefehl:\n${ui.installCmd}`)) return
                      try {
                        const r = await api.installService(ui.name, ui.installCmd, ui.port)
                        alert(r.ok ? `✅ ${ui.name} installiert!` : `❌ Fehler: ${r.error}`)
                      } catch (err) { alert(`❌ Installation fehlgeschlagen: ${err.message}`) }
                    }}
                    title={`${ui.name} installieren`}
                  >⬇️ Install</button>
                )}
                {ui.repo && (
                  <button
                    style={{ ...S.btnSmall, fontSize: '10px', padding: '4px 6px' }}
                    onClick={(e) => { e.stopPropagation(); openWebFrame(ui.repo, `${ui.name} Repo`) }}
                    title="GitHub-Repo öffnen"
                  >🔗</button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )

  /* ─── TAB: BENCHMARKS ───────────────────────────── */
  const renderBenchmarks = () => (
    <div style={S.tabContent}>
      {/* GPU Benchmark Button */}
      <div style={{
        padding: '10px 14px', borderRadius: '8px',
        background: 'rgba(68,136,255,0.04)', border: '1px solid rgba(68,136,255,0.15)',
        display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap',
      }}>
        <span style={{ fontSize: '18px' }}>🔥</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>GPU-Hardware benchmarken</div>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
            Testet VRAM-Kapazität, Bandbreite und berechnet optimale Modell-Einstellungen
          </div>
        </div>
        <button style={S.btnPrimary} onClick={handleGpuBenchmark} disabled={gpuBenching}>
          {gpuBenching ? '⏳ Läuft…' : '🔥 GPU benchmarken'}
        </button>
      </div>

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
              Starte einen Benchmark im Modelle-Tab (📊-Button bei jedem Modell)
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {benchmarks.map((b, i) => {
              const ratingColors = {
                excellent: '#00ff88', good: '#00ffc8', fair: '#ffaa00', poor: '#ff4444',
              }
              const ratingLabels = {
                excellent: '🏆 Exzellent', good: '✅ Gut', fair: '⚠️ Mittel', poor: '❌ Langsam',
              }
              return (
                <div key={i} style={{
                  padding: '12px 14px', background: 'var(--bg-surface)',
                  border: '1px solid var(--border)', borderRadius: '10px',
                  borderLeft: `3px solid ${ratingColors[b.rating] || '#888'}`,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text-primary)' }}>
                        {b.model_name || '—'}
                      </span>
                      <span style={{
                        ...S.badge, fontSize: '10px',
                        background: `${ratingColors[b.rating] || '#888'}15`,
                        color: ratingColors[b.rating] || '#888',
                      }}>
                        {ratingLabels[b.rating] || b.rating}
                      </span>
                    </div>
                    <span style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                      {b.created_at ? new Date(b.created_at).toLocaleString('de-DE') : '—'}
                    </span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: '8px' }}>
                    <div style={{ textAlign: 'center', padding: '6px', background: 'rgba(0,0,0,0.2)', borderRadius: '6px' }}>
                      <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>Token/s</div>
                      <div style={{ fontSize: '16px', fontWeight: 700, color: ratingColors[b.rating] || '#00ffc8', fontFamily: 'var(--font-mono)' }}>
                        {b.tokens_per_second?.toFixed(1) || '—'}
                      </div>
                      <QualityBar value={b.tokens_per_second || 0} max={100} color={ratingColors[b.rating]} />
                    </div>
                    <div style={{ textAlign: 'center', padding: '6px', background: 'rgba(0,0,0,0.2)', borderRadius: '6px' }}>
                      <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>Prompt t/s</div>
                      <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>
                        {b.prompt_eval_tps?.toFixed(1) || '—'}
                      </div>
                    </div>
                    <div style={{ textAlign: 'center', padding: '6px', background: 'rgba(0,0,0,0.2)', borderRadius: '6px' }}>
                      <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>TTFT</div>
                      <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                        {b.time_to_first_token_ms ? Math.round(b.time_to_first_token_ms) + 'ms' : '—'}
                      </div>
                    </div>
                    <div style={{ textAlign: 'center', padding: '6px', background: 'rgba(0,0,0,0.2)', borderRadius: '6px' }}>
                      <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>GPU-Layer</div>
                      <div style={{ fontSize: '16px', fontWeight: 700, color: '#4488ff', fontFamily: 'var(--font-mono)' }}>
                        {b.n_gpu_layers ?? '—'}
                      </div>
                    </div>
                    <div style={{ textAlign: 'center', padding: '6px', background: 'rgba(0,0,0,0.2)', borderRadius: '6px' }}>
                      <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>Kontext</div>
                      <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                        {b.context_size?.toLocaleString() || '—'}
                      </div>
                    </div>
                    <div style={{ textAlign: 'center', padding: '6px', background: 'rgba(0,0,0,0.2)', borderRadius: '6px' }}>
                      <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>VRAM</div>
                      <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                        {b.vram_mb ? formatMB(b.vram_mb) : '—'}
                      </div>
                    </div>
                  </div>
                  {/* GPU + Details */}
                  <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '6px', fontFamily: 'var(--font-mono)' }}>
                    {b.gpu_name && `GPU: ${b.gpu_name} · `}
                    {b.quantization && `Quant: ${b.quantization} · `}
                    {b.batch_size && `Batch: ${b.batch_size} · `}
                    {b.backend && `Backend: ${b.backend}`}
                  </div>
                  {b.notes && (
                    <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '4px', opacity: 0.7 }}>
                      {b.notes}
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

  /* ─── TAB: GHOSTS (Hot-Swap) ────────────────────── */
  const renderGhosts = () => (
    <div style={S.tabContent}>
      {/* Ghost Sub-Tabs */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '4px' }}>
        {['roles', 'models', 'history'].map(t => (
          <button
            key={t}
            onClick={() => { setGhostTab(t); if (t === 'history') loadGhostHistory() }}
            style={{
              padding: '6px 16px', borderRadius: 'var(--radius)',
              border: `1px solid ${ghostTab === t ? 'var(--accent)' : 'var(--border)'}`,
              background: ghostTab === t ? 'rgba(0,255,204,0.1)' : 'transparent',
              color: ghostTab === t ? 'var(--accent)' : 'var(--text-secondary)',
              cursor: 'pointer', fontSize: '12px',
            }}
          >
            {t === 'roles' ? '🎭 Rollen' : t === 'models' ? '🧠 Modelle' : '📜 History'}
          </button>
        ))}
      </div>

      {/* Ghost Roles View */}
      {ghostTab === 'roles' && (
        <div style={S.section}>
          <div style={S.sectionHeader}>
            <span>👻 Ghost Hot-Swap ({ghostData.roles.length} Rollen)</span>
            <button style={S.btnSmall} onClick={loadGhosts}>↻</button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '10px' }}>
            {ghostData.roles.map(role => {
              const active = getActiveModelForRole(role.name)
              const compat = getCompatModels(role.name)
              return (
                <div
                  key={role.id}
                  style={{
                    ...S.roleCard,
                    borderLeft: active ? '3px solid var(--accent)' : '3px solid var(--border)',
                    cursor: 'pointer',
                  }}
                  onClick={() => setSelectedGhostRole(selectedGhostRole === role.name ? null : role.name)}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                    <span style={{ fontSize: '24px' }}>{role.icon}</span>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '14px', color: role.color || 'var(--text-primary)' }}>
                        {role.display_name}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                        {role.description}
                      </div>
                    </div>
                  </div>
                  {active ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '12px' }}>🧠 {active.model_display}</span>
                      <span style={S.badgeGreen}>● Aktiv</span>
                    </div>
                  ) : (
                    <span style={S.badgeGray}>○ Kein Ghost</span>
                  )}
                  {/* Expanded: Model Selection */}
                  {selectedGhostRole === role.name && (
                    <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid var(--border)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                        Ghost zuweisen:
                      </div>
                      {compat.map(c => (
                        <div
                          key={c.model_name}
                          onClick={(e) => { e.stopPropagation(); handleGhostSwap(role.name, c.model_name) }}
                          style={{
                            padding: '6px 10px', marginBottom: '4px', borderRadius: '6px',
                            border: '1px solid var(--border)', cursor: ghostSwapping ? 'wait' : 'pointer',
                            fontSize: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                            background: active?.model_name === c.model_name ? 'rgba(0,255,204,0.08)' : 'transparent',
                          }}
                        >
                          <span>{c.model_name}</span>
                          <span style={{
                            color: c.fitness_score > 0.8 ? '#00ff88' : c.fitness_score > 0.5 ? '#ffaa00' : '#ff4444',
                            fontFamily: 'var(--font-mono)',
                          }}>
                            {(c.fitness_score * 100).toFixed(0)}%
                          </span>
                        </div>
                      ))}
                      {compat.length === 0 && (
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Keine kompatiblen Modelle</div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
            {ghostData.roles.length === 0 && (
              <div style={S.emptyState}>Keine Ghost-Rollen definiert</div>
            )}
          </div>
        </div>
      )}

      {/* Ghost Models View */}
      {ghostTab === 'models' && (
        <div style={S.section}>
          <div style={S.sectionHeader}>
            <span>🧠 Ghost-Modelle ({ghostData.models.length})</span>
            <button style={S.btnSmall} onClick={loadGhosts}>↻</button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '10px' }}>
            {ghostData.models.map(model => (
              <div key={model.id} style={S.roleCard}>
                <div style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text-primary)' }}>{model.display_name}</div>
                <div style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', marginTop: '4px' }}>{model.name}</div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '8px', flexWrap: 'wrap' }}>
                  <span style={{ ...S.badge, background: model.is_loaded ? 'rgba(0,255,136,0.1)' : 'rgba(255,255,255,0.05)', color: model.is_loaded ? '#00ff88' : 'var(--text-secondary)' }}>
                    {model.is_loaded ? '● Geladen' : '○ Verfügbar'}
                  </span>
                  <span style={{ ...S.badge, fontSize: '10px' }}>
                    {model.parameter_count} · {model.quantization || 'F16'}
                  </span>
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '6px' }}>
                  Provider: {model.provider} · Ctx: {model.context_size}
                  {model.requires_gpu && ' · 🎮 GPU'}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  {model.total_requests} Anfragen · ⌀ {model.avg_latency_ms?.toFixed(0) || 0}ms
                </div>
                {model.capabilities && (
                  <div style={{ display: 'flex', gap: '4px', marginTop: '6px', flexWrap: 'wrap' }}>
                    {model.capabilities.map(cap => (
                      <span key={cap} style={{ padding: '1px 6px', fontSize: '9px', borderRadius: '8px', background: 'rgba(68,136,255,0.15)', color: 'var(--info)' }}>{cap}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {ghostData.models.length === 0 && (
              <div style={S.emptyState}>Keine Ghost-Modelle registriert</div>
            )}
          </div>
        </div>
      )}

      {/* Ghost History View */}
      {ghostTab === 'history' && (
        <div style={S.section}>
          <div style={S.sectionHeader}>
            <span>📜 Ghost Swap History</span>
            <button style={S.btnSmall} onClick={loadGhostHistory}>↻</button>
          </div>
          {ghostHistory.map((h, i) => (
            <div key={i} style={{
              padding: '10px 12px', borderBottom: '1px solid var(--border)',
              display: 'flex', gap: '12px', alignItems: 'center', fontSize: '12px',
            }}>
              <span>{h.success ? '✅' : '❌'}</span>
              <div style={{ flex: 1 }}>
                <div>
                  <strong>{h.role_name}</strong>: {h.old_model_name || '—'} → {h.new_model_name}
                </div>
                <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                  {h.swap_reason} · {h.swap_duration_ms}ms · {h.initiated_by}
                </div>
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                {new Date(h.ts).toLocaleString('de-DE')}
              </div>
            </div>
          ))}
          {ghostHistory.length === 0 && (
            <div style={S.emptyState}>Keine Ghost-Wechsel protokolliert</div>
          )}
        </div>
      )}
    </div>
  )

  /* ═══════════════════════════════════════════════════
     MAIN RENDER
     ═══════════════════════════════════════════════════ */
  const TABS = [
    { key: 'agents', icon: '🤖', label: 'Agenten' },
    { key: 'models', icon: '📦', label: 'Modelle' },
    { key: 'ghosts', icon: '👻', label: 'Ghosts' },
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
          <span style={{ fontSize: '20px' }}>👻</span>
          <span style={{ fontWeight: 700, fontSize: '15px' }}>Ghost LLM Manager</span>
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
        <div style={{ flex: 1 }} />
        <button onClick={() => setShowAppSettings(v => !v)} style={{ ...S.tabBtn, ...(showAppSettings ? S.tabBtnActive : {}) }}>
          <span>⚙️</span><span>Settings</span>
        </button>
      </div>

      {/* Content */}
      <div style={S.content}>
        {showAppSettings ? (
          <div style={{ padding: '16px', overflow: 'auto' }}>
            <AppSettingsPanel schema={appSchema} settings={appSettings} onUpdate={updateAppSetting} onReset={resetAppSettings} title="Ghost LLM Manager" />
          </div>
        ) : loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', gap: '12px' }}>
            <div style={{ fontSize: '36px', animation: 'pulse 1.5s infinite' }}>👻</div>
            <div style={{ fontSize: '13px', color: 'var(--accent)' }}>Ghost LLM Manager wird geladen…</div>
          </div>
        ) : (
          <>
            {tab === 'agents' && renderAgents()}
            {tab === 'models' && renderModels()}
            {tab === 'ghosts' && renderGhosts()}
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
