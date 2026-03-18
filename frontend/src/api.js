const API_BASE = '/api'

// ── Tab-Isolation: Jeder Browser-Tab bekommt eine einzigartige ID ──
function getTabId() {
  let tabId = sessionStorage.getItem('dbai_tab_id')
  if (!tabId) {
    tabId = `tab-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    sessionStorage.setItem('dbai_tab_id', tabId)
  }
  return tabId
}

async function request(path, options = {}) {
  const token = localStorage.getItem('dbai_token')
  const headers = {
    'Content-Type': 'application/json',
    'X-Tab-Id': getTabId(),
    ...options.headers,
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })

  if (res.status === 401) {
    localStorage.removeItem('dbai_token')
    // Kein window.location.reload() — App.jsx .catch() handler regelt den UI-Zustand
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

  // Tab-Instanzen (Virtual Desktops)
  tabRegister: (tabId, hostname, label) =>
    request('/tabs/register', { method: 'POST', body: JSON.stringify({ tab_id: tabId, hostname, label }) }),
  tabList: () => request('/tabs'),
  tabUpdate: (tabId, data) =>
    request(`/tabs/${tabId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  tabHeartbeat: (tabId) =>
    request(`/tabs/${tabId}/heartbeat`, { method: 'POST' }),
  tabClose: (tabId) =>
    request(`/tabs/${tabId}`, { method: 'DELETE' }),
  getTabId,

  // Windows
  openWindow: (appId) => request(`/windows/open/${appId}`, { method: 'POST' }),
  updateWindow: (id, data) => request(`/windows/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  closeWindow: (id) => request(`/windows/${id}`, { method: 'DELETE' }),

  // Ghosts
  ghosts: () => request('/ghosts'),
  swapGhost: (role, model, reason) =>
    request('/ghosts/swap', { method: 'POST', body: JSON.stringify({ role, model, reason }) }),
  askGhost: (role, question, context = {}, model = null) =>
    request('/ghosts/ask', { method: 'POST', body: JSON.stringify({ role, question, context, ...(model ? { model } : {}) }) }),
  ghostHistory: (limit = 50) => request(`/ghosts/history?limit=${limit}`),

  // System
  systemStatus: () => request('/system/status'),
  systemMetrics: () => request('/system/metrics'),
  processes: () => request('/system/processes'),
  health: () => request('/system/health'),
  selfHeal: () => request('/system/self-heal', { method: 'POST' }),

  // Repair / Self-Healing
  healthSimple: () => request('/health'),
  repairQueue: () => request('/repair/queue'),
  repairPending: () => request('/repair/pending'),
  repairApprove: (id) => request(`/repair/approve/${id}`, { method: 'POST' }),
  repairReject: (id) => request(`/repair/reject/${id}`, { method: 'POST' }),
  repairExecute: (id) => request(`/repair/execute/${id}`, { method: 'POST' }),
  repairEnforcementLog: () => request('/repair/enforcement-log'),
  repairSchemaIntegrity: () => request('/repair/schema-integrity'),
  repairImmutableRegistry: () => request('/repair/immutable-registry'),
  repairWebsocketCommands: () => request('/repair/websocket-commands'),

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
  llmDownloadModel: (repo_id, target_dir, filename) =>
    request('/llm/download', { method: 'POST', body: JSON.stringify({ repo_id, target_dir, filename }) }),
  llmActivateModel: (id) =>
    request(`/llm/models/${id}/activate`, { method: 'POST' }),
  llmDeactivateModel: (id) =>
    request(`/llm/models/${id}/deactivate`, { method: 'POST' }),
  gpuVramBudget: () => request('/gpu/vram-budget'),
  gpuBenchmark: (gpu_index = 0) =>
    request('/gpu/benchmark', { method: 'POST', body: JSON.stringify({ gpu_index }) }),
  gpuRecommend: (modelId, gpu_index = 0) =>
    request(`/gpu/recommend/${modelId}`, { method: 'POST', body: JSON.stringify({ gpu_index }) }),
  llmRunBenchmark: (modelId, gpu_index = 0) =>
    request(`/llm/models/${modelId}/benchmark`, { method: 'POST', body: JSON.stringify({ gpu_index }) }),
  llmStartModel: (modelId, settings = {}) =>
    request(`/llm/models/${modelId}/start`, { method: 'POST', body: JSON.stringify(settings) }),
  llmStopModel: (modelId) =>
    request(`/llm/models/${modelId}/stop`, { method: 'POST' }),
  llmServerStatus: () => request('/llm/server/status'),
  llmServerRestart: (config = {}) =>
    request('/llm/server/restart', { method: 'POST', body: JSON.stringify(config) }),
  llmServerStop: () =>
    request('/llm/server/stop', { method: 'POST' }),
  installService: (name, command, port) =>
    request('/services/install', { method: 'POST', body: JSON.stringify({ name, command, port }) }),
  vramLive: () => request('/gpu/vram-live'),
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

  // Remote Access / Mobile Connect
  remoteAccessInfo: () => request('/remote-access/info'),
  remoteAccessPin: () => request('/remote-access/pin'),
  remoteAccessVerifyPin: (pin) =>
    request('/remote-access/verify-pin', { method: 'POST', body: JSON.stringify({ pin }) }),

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

  // System Diagnostics (erweitert)
  diagnostics: () => request('/system/diagnostics'),

  // KI Werkstatt (AI Workshop)
  workshopLlmStatus: () => request('/workshop/llm-status'),
  workshopMlModels: () => request('/workshop/ml-models'),
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

  // Linux System Settings (Display, Sound, Bluetooth, Power, Keyboard etc.)
  linuxSettings: (which) => request(`/settings/linux/${which}`),
  linuxSettingsUpdate: (which, data) =>
    request(`/settings/linux/${which}`, { method: 'PUT', body: JSON.stringify(data) }),
  linuxSettingsAction: (which, action) =>
    request(`/settings/linux/${which}/action`, { method: 'POST', body: JSON.stringify({ action }) }),

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
  browserImportSelective: (type, name, path, dataTypes) =>
    request('/browser/import/selective', { method: 'POST', body: JSON.stringify({ browser_type: type, profile_name: name, profile_path: path, data_types: dataTypes }) }),

  // Ghost Browser (Feature 56)
  ghostBrowser: {
    listTasks: (status = null, limit = 50) => request(`/ghost-browser/tasks${status ? `?status=${encodeURIComponent(status)}&limit=${limit}` : `?limit=${limit}`}`),
    createTask: (data) => request('/ghost-browser/tasks', { method: 'POST', body: JSON.stringify(data) }),
    getTask: (taskId) => request(`/ghost-browser/tasks/${taskId}`),
    getSteps: (taskId) => request(`/ghost-browser/tasks/${taskId}/steps`),
    runTask: (taskId) => request(`/ghost-browser/tasks/${taskId}/run`, { method: 'POST' }),
    cancelTask: (taskId) => request(`/ghost-browser/tasks/${taskId}/cancel`, { method: 'POST' }),
    deleteTask: (taskId) => request(`/ghost-browser/tasks/${taskId}`, { method: 'DELETE' }),
    presets: () => request('/ghost-browser/presets'),
    quick: (data) => request('/ghost-browser/quick', { method: 'POST', body: JSON.stringify(data) }),
    result: (taskId) => request(`/ghost-browser/results/${taskId}`),
    screenshotUrl: (taskId, step) => `/api/ghost-browser/screenshots/${taskId}/${step}`,
  },

  // Config Import (Feature 12)
  configScan: () => request('/config/scan', { method: 'POST' }),
  configImport: () => request('/config/import', { method: 'POST' }),
  configStatus: () => request('/config/status'),
  configImportSelective: (categories) =>
    request('/config/import/selective', { method: 'POST', body: JSON.stringify({ categories }) }),

  // Workspace Mapping (Feature 13)
  workspaceScan: (paths) =>
    request('/workspace/scan', { method: 'POST', body: JSON.stringify({ paths }) }),
  workspaceSearch: (q) => request(`/workspace/search?q=${encodeURIComponent(q)}`),
  workspaceStats: () => request('/workspace/stats'),
  workspaceOpenFile: (path) =>
    request('/workspace/open', { method: 'POST', body: JSON.stringify({ path }) }),

  // Synaptic Memory (Feature 14)
  synapticStats: () => request('/synaptic/stats'),
  synapticSearch: (type) => request(`/synaptic/search${type ? `?type=${type}` : ''}`),
  synapticConsolidate: () => request('/synaptic/consolidate', { method: 'POST' }),
  synapticDeleteMemory: (id) =>
    request(`/synaptic/memories/${id}`, { method: 'DELETE' }),

  // RAG Pipeline (Feature 15)
  ragSources: () => request('/rag/sources'),
  ragStats: () => request('/rag/stats'),
  ragQuery: (q) =>
    request('/rag/query', { method: 'POST', body: JSON.stringify({ question: q }) }),
  ragToggleSource: (name, enabled) =>
    request(`/rag/sources/${name}/toggle`, { method: 'PATCH', body: JSON.stringify({ enabled }) }),
  ragReindex: (name) =>
    request(`/rag/sources/${name}/reindex`, { method: 'POST' }),
  ragAddSource: (name, type, path) =>
    request('/rag/sources', { method: 'POST', body: JSON.stringify({ source_name: name, source_type: type, source_path: path }) }),
  ragDeleteSource: (name) =>
    request(`/rag/sources/${name}`, { method: 'DELETE' }),

  // USB Installer (Feature 16)
  usbDevices: () => request('/usb/devices'),
  usbFlash: (device, image, method) =>
    request('/usb/flash', { method: 'POST', body: JSON.stringify({ device_path: device, image_path: image, method }) }),
  usbJobs: () => request('/usb/jobs'),
  usbCancelJob: (id) =>
    request(`/usb/jobs/${id}`, { method: 'DELETE' }),
  usbJobProgress: (id) => request(`/usb/jobs/${id}/progress`),

  // WLAN Hotspot (Feature 17)
  hotspotCreate: (ssid, password) =>
    request('/hotspot/create', { method: 'POST', body: JSON.stringify({ ssid, password }) }),
  hotspotStop: () => request('/hotspot/stop', { method: 'POST' }),
  hotspotStatus: () => request('/hotspot/status'),
  hotspotUpdateConfig: (config) =>
    request('/hotspot/config', { method: 'PATCH', body: JSON.stringify(config) }),

  // Immutable Filesystem (Feature 18)
  immutableConfig: () => request('/immutable/config'),
  immutableEnable: (mode) =>
    request('/immutable/enable', { method: 'POST', body: JSON.stringify({ mode }) }),
  immutableSnapshots: () => request('/immutable/snapshots'),
  immutableCreateSnapshot: (label) =>
    request('/immutable/snapshots', { method: 'POST', body: JSON.stringify({ label }) }),
  immutableDeleteSnapshot: (id) =>
    request(`/immutable/snapshots/${id}`, { method: 'DELETE' }),
  immutableRestoreSnapshot: (id) =>
    request(`/immutable/snapshots/${id}/restore`, { method: 'POST' }),

  // Anomaly Detection (Feature 20)
  anomalyDetections: (limit, severity) =>
    request(`/anomaly/detections?limit=${limit || 50}${severity ? `&severity=${severity}` : ''}`),
  anomalyModels: () => request('/anomaly/models'),
  anomalyResolve: (id, resolution) =>
    request(`/anomaly/detections/${id}/resolve`, { method: 'POST', body: JSON.stringify({ resolution }) }),

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
  firewallDeleteRule: (id) =>
    request(`/firewall/rules/${id}`, { method: 'DELETE' }),

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

  // Power Management
  powerShutdown: () => request('/power/shutdown', { method: 'POST' }),
  powerReboot: () => request('/power/reboot', { method: 'POST' }),

  // Export CSV/JSON
  exportTable: (schema, table, format = 'json') =>
    request(`/export/${schema}/${table}?format=${format}`),
  exportTableCSV: (schema, table) =>
    fetch(`${API_BASE}/export/${schema}/${table}?format=csv`, { headers: { Authorization: `Bearer ${localStorage.getItem('dbai_token')}` } }),
  exportLogs: (format = 'json', limit = 500) =>
    request(`/export/logs?format=${format}&limit=${limit}`),

  // User Management
  listUsers: () => request('/users'),
  createUser: (data) =>
    request('/users', { method: 'POST', body: JSON.stringify(data) }),
  updateUser: (id, data) =>
    request(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteUser: (id) =>
    request(`/users/${id}`, { method: 'DELETE' }),

  // Audit-Trail & Backup
  auditLog: (limit = 100) => request(`/audit/log?limit=${limit}`),
  auditChanges: (limit = 100) => request(`/audit/changes?limit=${limit}`),
  backupTrigger: () => request('/backup/trigger', { method: 'POST' }),
  backupStatus: () => request('/backup/status'),

  // Workshop Custom Tables (benutzerdefinierte Datenbanken)
  workshopCustomTables: (pid) => request(`/workshop/projects/${pid}/custom-tables`),
  workshopCreateCustomTable: (pid, data) =>
    request(`/workshop/projects/${pid}/custom-tables`, { method: 'POST', body: JSON.stringify(data) }),
  workshopDeleteCustomTable: (pid, tid) =>
    request(`/workshop/projects/${pid}/custom-tables/${tid}`, { method: 'DELETE' }),
  workshopCustomRows: (pid, tid) => request(`/workshop/projects/${pid}/custom-tables/${tid}/rows`),
  workshopAddCustomRow: (pid, tid, data) =>
    request(`/workshop/projects/${pid}/custom-tables/${tid}/rows`, { method: 'POST', body: JSON.stringify({ data }) }),
  workshopUpdateCustomRow: (pid, tid, rid, data) =>
    request(`/workshop/projects/${pid}/custom-tables/${tid}/rows/${rid}`, { method: 'PUT', body: JSON.stringify({ data }) }),
  workshopDeleteCustomRow: (pid, tid, rid) =>
    request(`/workshop/projects/${pid}/custom-tables/${tid}/rows/${rid}`, { method: 'DELETE' }),

  // Per-App Settings (Schema 39/40)
  appSettings: (appId) => request(`/apps/${appId}/settings`),
  appSettingsUpdate: (appId, settings) =>
    request(`/apps/${appId}/settings`, { method: 'PATCH', body: JSON.stringify(settings) }),
  appSettingsReset: (appId) =>
    request(`/apps/${appId}/settings`, { method: 'DELETE' }),
  appSettingsSchema: (appId) => request(`/apps/${appId}/settings/schema`),
  allAppSettings: () => request('/apps/settings/all'),

  // Hardware-Simulator
  simulatorStatus: () => request('/simulator/status'),
  simulatorStart: () => request('/simulator/start', { method: 'POST' }),
  simulatorStop: () => request('/simulator/stop', { method: 'POST' }),
  simulatorAnomaly: (anomaly) =>
    request('/simulator/anomaly', { method: 'POST', body: JSON.stringify({ anomaly }) }),
  simulatorProfiles: () => request('/simulator/profiles'),
  simulatorSetProfile: (profile) =>
    request('/simulator/profile', { method: 'POST', body: JSON.stringify({ profile }) }),

  // ── Ghost Mail ──
  mailAccounts: () => request('/mail/accounts'),
  mailAccountCreate: (data) =>
    request('/mail/accounts', { method: 'POST', body: JSON.stringify(data) }),
  mailAccountDelete: (id) =>
    request(`/mail/accounts/${id}`, { method: 'DELETE' }),
  mailInbox: (params = {}) => {
    const q = new URLSearchParams()
    if (params.account_id) q.set('account_id', params.account_id)
    if (params.folder) q.set('folder', params.folder)
    if (params.limit) q.set('limit', params.limit)
    if (params.offset) q.set('offset', params.offset)
    return request(`/mail/inbox?${q}`)
  },
  mailRead: (id) => request(`/mail/inbox/${id}`),
  mailUpdate: (id, flags) =>
    request(`/mail/inbox/${id}`, { method: 'PATCH', body: JSON.stringify(flags) }),
  mailOutbox: (state) => request(`/mail/outbox${state ? '?state=' + state : ''}`),
  mailCompose: (data) =>
    request('/mail/compose', { method: 'POST', body: JSON.stringify(data) }),
  mailDraftUpdate: (id, data) =>
    request(`/mail/outbox/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  mailDraftDelete: (id) =>
    request(`/mail/outbox/${id}`, { method: 'DELETE' }),
  mailSend: (id) =>
    request(`/mail/send/${id}`, { method: 'POST' }),
  mailGhostCompose: (instruction, replyToId) =>
    request('/mail/ghost-compose', { method: 'POST', body: JSON.stringify({ instruction, reply_to_id: replyToId }) }),
  mailGhostImprove: (bodyText, instruction) =>
    request('/mail/ghost-improve', { method: 'POST', body: JSON.stringify({ body_text: bodyText, instruction }) }),
  mailGhostReply: (mailId, tone) =>
    request('/mail/ghost-reply', { method: 'POST', body: JSON.stringify({ mail_id: mailId, tone }) }),
  mailSync: (accountId) =>
    request(`/mail/sync/${accountId}`, { method: 'POST' }),
}

// WebSocket Verbindung — Tab-isoliert
export function createWebSocket(token, onMessage, onClose) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const tabId = getTabId()
  const ws = new WebSocket(`${protocol}//${window.location.host}/ws/${token}?tab_id=${tabId}`)

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
