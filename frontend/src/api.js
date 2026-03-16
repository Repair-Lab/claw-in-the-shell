const API_BASE = '/api'

async function request(path, options = {}) {
  const token = localStorage.getItem('dbai_token')
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })

  if (res.status === 401) {
    localStorage.removeItem('dbai_token')
    window.location.reload()
    throw new Error('Nicht authentifiziert')
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'API-Fehler')
  }

  return res.json()
}

export const api = {
  // Auth
  login: (username, password) =>
    request('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  me: () => request('/auth/me'),

  // Boot
  bootSequence: () => request('/boot/sequence'),

  // Desktop
  desktop: () => request('/desktop'),
  apps: () => request('/apps'),
  setTheme: (name) => request(`/desktop/theme/${name}`, { method: 'PATCH' }),

  // Windows
  openWindow: (appId) => request(`/windows/open/${appId}`, { method: 'POST' }),
  updateWindow: (id, data) => request(`/windows/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  closeWindow: (id) => request(`/windows/${id}`, { method: 'DELETE' }),

  // Ghosts
  ghosts: () => request('/ghosts'),
  swapGhost: (role, model, reason) =>
    request('/ghosts/swap', { method: 'POST', body: JSON.stringify({ role, model, reason }) }),
  askGhost: (role, question, context = {}) =>
    request('/ghosts/ask', { method: 'POST', body: JSON.stringify({ role, question, context }) }),
  ghostHistory: (limit = 50) => request(`/ghosts/history?limit=${limit}`),

  // System
  systemStatus: () => request('/system/status'),
  systemMetrics: () => request('/system/metrics'),
  processes: () => request('/system/processes'),
  health: () => request('/system/health'),
  selfHeal: () => request('/system/self-heal', { method: 'POST' }),

  // Knowledge
  modules: () => request('/knowledge/modules'),
  searchModules: (q) => request(`/knowledge/search?q=${encodeURIComponent(q)}`),
  errors: () => request('/knowledge/errors'),
  systemReport: () => request('/knowledge/report'),

  // Events
  events: (limit = 100, type = null) =>
    request(`/events?limit=${limit}${type ? `&event_type=${type}` : ''}`),

  // SQL Console
  sqlQuery: (query) =>
    request('/sql/query', { method: 'POST', body: JSON.stringify({ query }) }),

  // Notifications
  notifications: () => request('/notifications'),
  dismissNotification: (id) => request(`/notifications/${id}/dismiss`, { method: 'PATCH' }),

  // Themes
  themes: () => request('/themes'),

  // Software Store
  storeCatalog: () => request('/store/catalog'),
  storeInstall: (pkg, source) =>
    request('/store/install', { method: 'POST', body: JSON.stringify({ package_name: pkg, source_type: source }) }),
  storeUninstall: (pkg, source) =>
    request('/store/uninstall', { method: 'POST', body: JSON.stringify({ package_name: pkg, source_type: source }) }),
  storeRefresh: () => request('/store/refresh', { method: 'POST' }),
  storeGithubSearch: (q) => request(`/store/github/search?q=${encodeURIComponent(q)}`),
  storeGithubInstall: (repo) =>
    request('/store/github/install', { method: 'POST', body: JSON.stringify(repo) }),

  // OpenClaw Integrator
  openclawStatus: () => request('/openclaw/status'),
  openclawActivateSkill: (name) =>
    request('/openclaw/skills/activate', { method: 'POST', body: JSON.stringify({ skill_name: name }) }),
  openclawStartMigration: () =>
    request('/openclaw/migrate', { method: 'POST' }),
  openclawLive: () => request('/openclaw/live'),
  openclawGatewayStatus: () => request('/openclaw/gateway/status'),

  // Agent Orchestration (Mission Control)
  agentsGpu: () => request('/agents/gpu'),
  agentsInstances: () => request('/agents/instances'),
  agentsCreateInstance: (data) =>
    request('/agents/instances', { method: 'POST', body: JSON.stringify(data) }),
  agentsUpdateInstance: (id, data) =>
    request(`/agents/instances/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  agentsDeleteInstance: (id) =>
    request(`/agents/instances/${id}`, { method: 'DELETE' }),
  agentsStartInstance: (id) =>
    request(`/agents/instances/${id}/start`, { method: 'POST' }),
  agentsStopInstance: (id) =>
    request(`/agents/instances/${id}/stop`, { method: 'POST' }),
  agentsTasks: (instanceId) => request(`/agents/tasks/${instanceId}`),
  agentsCreateTask: (data) =>
    request('/agents/tasks', { method: 'POST', body: JSON.stringify(data) }),
  agentsDeleteTask: (id) =>
    request(`/agents/tasks/${id}`, { method: 'DELETE' }),
  agentsScheduledJobs: () => request('/agents/scheduled-jobs'),
  agentsCreateJob: (data) =>
    request('/agents/scheduled-jobs', { method: 'POST', body: JSON.stringify(data) }),
  agentsDeleteJob: (id) =>
    request(`/agents/scheduled-jobs/${id}`, { method: 'DELETE' }),
  agentsRoles: () => request('/agents/roles'),
  agentsAssignRole: (instanceId, roleId) =>
    request('/agents/assign-role', { method: 'POST', body: JSON.stringify({ instance_id: instanceId, role_id: roleId }) }),

  // File System Browser
  fsBrowse: (path = '/') => request(`/fs/browse?path=${encodeURIComponent(path)}`),
  fsMounts: () => request('/fs/mounts'),

  // OpenClaw → Ghost Import
  openclawImportToGhost: () =>
    request('/openclaw/import-to-ghost', { method: 'POST' }),

  // LLM Manager v2
  llmStatus: () => request('/llm/status'),
  llmBenchmark: (model) =>
    request('/llm/benchmark', { method: 'POST', body: JSON.stringify({ model_name: model }) }),
  llmUpdateConfig: (key, value) =>
    request('/llm/config', { method: 'PATCH', body: JSON.stringify({ key, value }) }),
  llmModels: () => request('/llm/models'),
  llmAddModel: (data) =>
    request('/llm/models', { method: 'POST', body: JSON.stringify(data) }),
  llmRemoveModel: (id) =>
    request(`/llm/models/${id}`, { method: 'DELETE' }),
  llmScanDisks: (paths) =>
    request('/llm/scan', { method: 'POST', body: JSON.stringify({ paths }) }),
  llmRunBenchmark: (modelId) =>
    request(`/llm/models/${modelId}/benchmark`, { method: 'POST' }),
  llmBenchmarkResults: () => request('/llm/benchmarks'),
  llmChains: () => request('/llm/chains'),
  llmCreateChain: (data) =>
    request('/llm/chains', { method: 'POST', body: JSON.stringify(data) }),
  llmDeleteChain: (id) =>
    request(`/llm/chains/${id}`, { method: 'DELETE' }),
  llmAddChainStep: (chainId, data) =>
    request(`/llm/chains/${chainId}/steps`, { method: 'POST', body: JSON.stringify(data) }),
  llmWebUIs: () => request('/llm/webuis'),

  // SQL Explorer
  sqlExplorerSchemas: () => request('/sql-explorer/schemas'),
  sqlExplorerTables: (schema) => request(`/sql-explorer/tables/${schema}`),
  sqlExplorerRows: (schema, table) => request(`/sql-explorer/rows/${schema}/${table}`),
  sqlExplorerUpdate: (schema, table, data) =>
    request(`/sql-explorer/rows/${schema}/${table}`, { method: 'PATCH', body: JSON.stringify(data) }),
  sqlExplorerInsert: (schema, table, data) =>
    request(`/sql-explorer/rows/${schema}/${table}`, { method: 'POST', body: JSON.stringify(data) }),
  sqlExplorerDelete: (schema, table, data) =>
    request(`/sql-explorer/rows/${schema}/${table}`, { method: 'DELETE', body: JSON.stringify(data) }),

  // Desktop Nodes & Scene (SVG-Desktop)
  desktopNodes: () => request('/desktop/nodes'),
  desktopNodesAll: () => request('/desktop/nodes/all'),
  desktopNodeCreate: (data) =>
    request('/desktop/nodes', { method: 'POST', body: JSON.stringify(data) }),
  desktopNodeUpdate: (id, data) =>
    request(`/desktop/nodes/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  desktopNodeDelete: (id) =>
    request(`/desktop/nodes/${id}`, { method: 'DELETE' }),
  desktopScene: () => request('/desktop/scene'),
  desktopSceneUpdate: (key, value) =>
    request(`/desktop/scene/${key}`, { method: 'PATCH', body: JSON.stringify({ scene_value: value }) }),

  // Setup Wizard
  setupComplete: (settings) =>
    request('/setup/complete', { method: 'POST', body: JSON.stringify(settings) }),
  setupStatus: () => request('/setup/status'),

  // i18n (Mehrsprachigkeit)
  i18n: (locale) => request(`/i18n/${locale}`),
  i18nLocales: () => request('/i18n/locales/available'),

  // Network Scanner
  networkScan: () => request('/network/scan', { method: 'POST' }),
  networkDevices: () => request('/network/devices'),
  networkAddToDesktop: (deviceId) =>
    request(`/network/devices/${deviceId}/add-to-desktop`, { method: 'POST' }),

  // Ghost Learning
  learningSave: (data) =>
    request('/learning/save', { method: 'POST', body: JSON.stringify(data) }),
  learningProfile: () => request('/learning/profile'),
  learningSystemPrompt: () => request('/learning/system-prompt-context'),

  // KI Werkstatt (AI Workshop)
  workshopProjects: () => request('/workshop/projects'),
  workshopProject: (id) => request(`/workshop/projects/${id}`),
  workshopCreateProject: (data) =>
    request('/workshop/projects', { method: 'POST', body: JSON.stringify(data) }),
  workshopDeleteProject: (id) =>
    request(`/workshop/projects/${id}`, { method: 'DELETE' }),
  workshopMedia: (projectId) => request(`/workshop/projects/${projectId}/media`),
  workshopSearch: (projectId, query) =>
    request(`/workshop/projects/${projectId}/search?q=${encodeURIComponent(query)}`),
  workshopCollections: (projectId) => request(`/workshop/projects/${projectId}/collections`),
  workshopCreateCollection: (projectId, data) =>
    request(`/workshop/projects/${projectId}/collections`, { method: 'POST', body: JSON.stringify(data) }),
  workshopDevices: (projectId) => request(`/workshop/projects/${projectId}/devices`),
  workshopAddDevice: (projectId, data) =>
    request(`/workshop/projects/${projectId}/devices`, { method: 'POST', body: JSON.stringify(data) }),
  workshopImportJobs: (projectId) => request(`/workshop/projects/${projectId}/imports`),
  workshopStartImport: (projectId, data) =>
    request(`/workshop/projects/${projectId}/imports`, { method: 'POST', body: JSON.stringify(data) }),
  workshopChat: (projectId, message) =>
    request(`/workshop/projects/${projectId}/chat`, { method: 'POST', body: JSON.stringify({ message }) }),
  workshopChatHistory: (projectId) => request(`/workshop/projects/${projectId}/chat`),
  workshopTemplates: () => request('/workshop/templates'),
  workshopStats: () => request('/workshop/stats'),

  // Settings (Einstellungen v2)
  settingsUser: () => request('/settings/user'),
  settingsUpdateUser: (data) =>
    request('/settings/user', { method: 'PATCH', body: JSON.stringify(data) }),
  settingsSystem: () => request('/settings/system'),
  settingsUpdateSystem: (data) =>
    request('/settings/system', { method: 'PATCH', body: JSON.stringify(data) }),
  settingsHardware: () => request('/settings/hardware'),

  // LLM Providers
  llmProviders: () => request('/llm/providers'),
  llmProviderUpdate: (key, data) =>
    request(`/llm/providers/${key}`, { method: 'PATCH', body: JSON.stringify(data) }),
  llmProviderTest: (key) =>
    request(`/llm/providers/${key}/test`, { method: 'POST' }),
  llmProviderRemoveKey: (key) =>
    request(`/llm/providers/${key}/key`, { method: 'DELETE' }),
  llmScanQuick: () =>
    request('/llm/scan-quick', { method: 'POST' }),

  // Browser Migration (Feature 11)
  browserScan: () => request('/browser/scan', { method: 'POST' }),
  browserImport: (type, name, path) =>
    request('/browser/import', { method: 'POST', body: JSON.stringify({ browser_type: type, profile_name: name, profile_path: path }) }),
  browserStatus: () => request('/browser/status'),

  // Config Import (Feature 12)
  configScan: () => request('/config/scan', { method: 'POST' }),
  configImport: () => request('/config/import', { method: 'POST' }),
  configStatus: () => request('/config/status'),

  // Workspace Mapping (Feature 13)
  workspaceScan: (paths) =>
    request('/workspace/scan', { method: 'POST', body: JSON.stringify({ paths }) }),
  workspaceSearch: (q) => request(`/workspace/search?q=${encodeURIComponent(q)}`),
  workspaceStats: () => request('/workspace/stats'),

  // Synaptic Memory (Feature 14)
  synapticStats: () => request('/synaptic/stats'),
  synapticSearch: (type) => request(`/synaptic/search${type ? `?type=${type}` : ''}`),
  synapticConsolidate: () => request('/synaptic/consolidate', { method: 'POST' }),

  // RAG Pipeline (Feature 15)
  ragSources: () => request('/rag/sources'),
  ragStats: () => request('/rag/stats'),
  ragQuery: (q) =>
    request('/rag/query', { method: 'POST', body: JSON.stringify({ question: q }) }),
  ragToggleSource: (name, enabled) =>
    request(`/rag/sources/${name}/toggle`, { method: 'PATCH', body: JSON.stringify({ enabled }) }),
  ragReindex: (name) =>
    request(`/rag/sources/${name}/reindex`, { method: 'POST' }),

  // USB Installer (Feature 16)
  usbDevices: () => request('/usb/devices'),
  usbFlash: (device, image, method) =>
    request('/usb/flash', { method: 'POST', body: JSON.stringify({ device_path: device, image_path: image, method }) }),
  usbJobs: () => request('/usb/jobs'),

  // WLAN Hotspot (Feature 17)
  hotspotCreate: (ssid, password) =>
    request('/hotspot/create', { method: 'POST', body: JSON.stringify({ ssid, password }) }),
  hotspotStop: () => request('/hotspot/stop', { method: 'POST' }),
  hotspotStatus: () => request('/hotspot/status'),

  // Immutable Filesystem (Feature 18)
  immutableConfig: () => request('/immutable/config'),
  immutableEnable: (mode) =>
    request('/immutable/enable', { method: 'POST', body: JSON.stringify({ mode }) }),
  immutableSnapshots: () => request('/immutable/snapshots'),

  // Anomaly Detection (Feature 20)
  anomalyDetections: (limit, severity) =>
    request(`/anomaly/detections?limit=${limit || 50}${severity ? `&severity=${severity}` : ''}`),
  anomalyModels: () => request('/anomaly/models'),

  // App Sandboxing (Feature 21)
  sandboxProfiles: () => request('/sandbox/profiles'),
  sandboxLaunch: (app, exe, profile) =>
    request('/sandbox/launch', { method: 'POST', body: JSON.stringify({ app_name: app, executable_path: exe, profile_name: profile }) }),
  sandboxRunning: () => request('/sandbox/running'),
  sandboxStop: (pid) => request(`/sandbox/stop/${pid}`, { method: 'POST' }),

  // Firewall & Netzwerk-Policy (Feature 22)
  firewallRules: () => request('/firewall/rules'),
  firewallAddRule: (data) =>
    request('/firewall/rules', { method: 'POST', body: JSON.stringify(data) }),
  firewallApply: () => request('/firewall/apply', { method: 'POST' }),
  firewallZones: () => request('/firewall/zones'),
  firewallConnections: () => request('/firewall/connections'),

  // Terminal (Feature 23)
  terminalExec: (cmd, cwd) =>
    request('/terminal/exec', { method: 'POST', body: JSON.stringify({ command: cmd, cwd }) }),

  // CI/CD & OTA Updates
  updaterStatus: () => request('/updates/status'),
  updaterReleases: () => request('/updates/releases'),
  updaterChannels: () => request('/updates/channels'),
  updaterCheck: () => request('/updates/check', { method: 'POST' }),
  updaterApply: (version) =>
    request('/updates/apply', { method: 'POST', body: JSON.stringify({ version }) }),
  updaterCreateRelease: (data) =>
    request('/updates/release', { method: 'POST', body: JSON.stringify(data) }),

  // Migrations
  migrationsStatus: () => request('/migrations/status'),
  migrationsHistory: () => request('/migrations/history'),
  migrationsPending: () => request('/migrations/pending'),
  migrationsApply: (dryRun) =>
    request('/migrations/apply', { method: 'POST', body: JSON.stringify({ dry_run: dryRun }) }),
  migrationsRollback: () => request('/migrations/rollback', { method: 'POST' }),

  // Build Pipeline
  pipelineHistory: () => request('/pipeline/history'),
  pipelineRun: (branch) =>
    request('/pipeline/run', { method: 'POST', body: JSON.stringify({ branch: branch || 'main' }) }),

  // OTA Nodes
  otaNodes: () => request('/ota/nodes'),
  otaJobs: () => request('/ota/jobs'),

  // Hardware-Simulator
  simulatorStatus: () => request('/simulator/status'),
  simulatorStart: () => request('/simulator/start', { method: 'POST' }),
  simulatorStop: () => request('/simulator/stop', { method: 'POST' }),
  simulatorAnomaly: (anomaly) =>
    request('/simulator/anomaly', { method: 'POST', body: JSON.stringify({ anomaly }) }),
  simulatorProfiles: () => request('/simulator/profiles'),
  simulatorSetProfile: (profile) =>
    request('/simulator/profile', { method: 'POST', body: JSON.stringify({ profile }) }),
}

// WebSocket Verbindung
export function createWebSocket(token, onMessage, onClose) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(`${protocol}//${window.location.host}/ws/${token}`)

  ws.onopen = () => console.log('[WS] Verbunden')
  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      onMessage(data)
    } catch (err) {
      console.error('[WS] Parse-Fehler:', err)
    }
  }
  ws.onerror = (e) => console.error('[WS] Fehler:', e)
  ws.onclose = (e) => {
    console.log('[WS] Getrennt:', e.code)
    if (onClose) onClose(e)
  }

  // Ping alle 30s
  const pingInterval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }))
    }
  }, 30000)

  const original = ws.close.bind(ws)
  ws.close = () => {
    clearInterval(pingInterval)
    original()
  }

  return ws
}
