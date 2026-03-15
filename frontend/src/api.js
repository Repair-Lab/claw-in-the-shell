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

  // OpenClaw Integrator
  openclawStatus: () => request('/openclaw/status'),
  openclawActivateSkill: (name) =>
    request('/openclaw/skills/activate', { method: 'POST', body: JSON.stringify({ skill_name: name }) }),
  openclawStartMigration: () =>
    request('/openclaw/migrate', { method: 'POST' }),

  // LLM Manager
  llmStatus: () => request('/llm/status'),
  llmBenchmark: (model) =>
    request('/llm/benchmark', { method: 'POST', body: JSON.stringify({ model_name: model }) }),
  llmUpdateConfig: (key, value) =>
    request('/llm/config', { method: 'PATCH', body: JSON.stringify({ key, value }) }),

  // Setup Wizard
  setupComplete: (settings) =>
    request('/setup/complete', { method: 'POST', body: JSON.stringify(settings) }),
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
