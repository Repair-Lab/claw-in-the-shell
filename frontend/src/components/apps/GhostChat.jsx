import React, { useState, useRef, useEffect, useCallback } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

/**
 * Ghost Chat v3 — Multi-Agent Chat mit Tabs
 *
 * Features:
 * - Mehrere Chat-Sessions parallel (Browser-Tab-Stil)
 * - Jeder Tab kann einer anderen Rolle/Agent zugewiesen werden
 * - Live-Synchronisierung mit Ghost LLM Manager (Events)
 * - Ein LLM bedient alles ODER mehrere LLM-Instanzen parallel
 * - Inline Modell-Zuweisung / Hot-Swap direkt aus dem Chat
 * - Einstellungen: Persönlichkeit, Modell, Memory, System-Prompt
 */

const SETTINGS_TABS = [
  { id: 'personality', label: '🎭 Persönlichkeit' },
  { id: 'model', label: '🧠 Modell' },
  { id: 'memory', label: '💾 Memory' },
  { id: 'system', label: '⚙️ System-Prompt' },
]

let chatIdCounter = 1

export default function GhostChat() {
  const { settings: appSettings, schema: appSchema, update: updateAppSetting, reset: resetAppSettings } = useAppSettings('ghost-chat')
  const [showAppSettings, setShowAppSettings] = useState(false)
  // ── Multi-Tab Chat State ──
  const [chatTabs, setChatTabs] = useState([
    { id: chatIdCounter++, role: 'sysadmin', title: 'Sysadmin', messages: [], pinned: false },
  ])
  const [activeChatId, setActiveChatId] = useState(1)
  const [showSettings, setShowSettings] = useState(false)
  const [settingsTab, setSettingsTab] = useState('personality')

  // ── Shared State ──
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [roles, setRoles] = useState([])
  const [instances, setInstances] = useState([])
  const [config, setConfig] = useState([])
  const [models, setModels] = useState([])
  const [activeGhosts, setActiveGhosts] = useState([])
  const [ghostRolesCompat, setGhostRolesCompat] = useState([])
  const [swapping, setSwapping] = useState(false)
  const messagesRef = useRef(null)
  const refreshRef = useRef(null)

  // ── Settings State ──
  const [editPrompt, setEditPrompt] = useState('')
  const [editPersonality, setEditPersonality] = useState('')
  const [memoryEnabled, setMemoryEnabled] = useState(true)
  const [contextWindow, setContextWindow] = useState(8192)
  const [temperature, setTemperature] = useState(0.7)
  const [selectedModel, setSelectedModel] = useState('')

  // Current active chat
  const activeChat = chatTabs.find(t => t.id === activeChatId)

  // ── Load Data ──
  const loadData = useCallback(async () => {
    try {
      const [ghostData, llmData, agentData] = await Promise.all([
        api.ghosts().catch(() => ({ roles: [], active_ghosts: [], models: [], compatibility: [] })),
        api.llmStatus().catch(() => ({ models: [], config: [] })),
        api.agentsInstances().catch(() => []),
      ])
      setRoles(ghostData.roles || [])
      setActiveGhosts(ghostData.active_ghosts || [])
      setGhostRolesCompat(ghostData.compatibility || [])
      // Merge: ghost_models + llmStatus models (dedupliziert)
      const ghostModels = ghostData.models || []
      const llmModels = llmData.models || []
      const merged = [...ghostModels]
      llmModels.forEach(lm => {
        if (!merged.find(gm => gm.name === lm.name)) merged.push(lm)
      })
      setModels(merged)
      setConfig(llmData.config || [])
      setInstances(Array.isArray(agentData) ? agentData : [])

      // Auto-select first active ghost's role
      if (ghostData.active_ghosts?.length > 0 && chatTabs.length === 1 && chatTabs[0].messages.length === 0) {
        const firstRole = ghostData.active_ghosts[0].role_name
        setChatTabs(prev => prev.map((t, i) => i === 0 ? {
          ...t,
          role: firstRole,
          title: ghostData.roles?.find(r => r.name === firstRole)?.display_name || firstRole,
        } : t))
      }

      // Load settings from config
      const cfg = (llmData.config || [])
      const get = (key) => cfg.find(c => c.key === key)?.value
      if (get('ghost_system_prompt')) setEditPrompt(get('ghost_system_prompt'))
      if (get('ghost_personality')) setEditPersonality(get('ghost_personality'))
      if (get('ghost_temperature')) setTemperature(parseFloat(get('ghost_temperature')) || 0.7)
      if (get('ghost_context_window')) setContextWindow(parseInt(get('ghost_context_window')) || 8192)
      if (get('ghost_memory_enabled')) setMemoryEnabled(get('ghost_memory_enabled') !== 'false')
      if (get('ghost_default_model')) setSelectedModel(get('ghost_default_model'))
    } catch (err) {
      console.error('Ghost Chat load error:', err)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  // ── Live sync with Ghost LLM Manager ──
  useEffect(() => {
    const handleGhostSwap = () => loadData()
    const handleLLMChange = () => loadData()
    window.addEventListener('dbai:ghost_swap', handleGhostSwap)
    window.addEventListener('dbai:llm_model_change', handleLLMChange)
    return () => {
      window.removeEventListener('dbai:ghost_swap', handleGhostSwap)
      window.removeEventListener('dbai:llm_model_change', handleLLMChange)
    }
  }, [loadData])

  // ── Auto-refresh every 30s ──
  useEffect(() => {
    refreshRef.current = setInterval(loadData, 30000)
    return () => clearInterval(refreshRef.current)
  }, [loadData])

  // ── Ghost swap from chat ──
  const handleQuickSwap = async (roleName, modelName) => {
    setSwapping(true)
    try {
      await api.swapGhost(roleName, modelName, 'Quick-Swap via Ghost Chat')
      window.dispatchEvent(new CustomEvent('dbai:ghost_swap'))
      await loadData()
    } catch (err) {
      console.error('Ghost-Swap fehlgeschlagen:', err)
    }
    setSwapping(false)
  }

  const getActiveGhostForRole = (roleName) => {
    return activeGhosts.find(g => g.role_name === roleName)
  }

  const getCompatModelsForRole = (roleName) => {
    return ghostRolesCompat
      .filter(c => c.role_name === roleName)
      .sort((a, b) => b.fitness_score - a.fitness_score)
  }

  // Auto-scroll
  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight
    }
  }, [chatTabs, activeChatId])

  // ── Chat Tab Actions ──
  const addChatTab = (roleName) => {
    const role = roles.find(r => r.name === roleName) || roles[0]
    if (!role) return
    const newId = chatIdCounter++
    setChatTabs(prev => [...prev, {
      id: newId,
      role: role.name,
      title: role.display_name || role.name,
      messages: [],
      pinned: false,
    }])
    setActiveChatId(newId)
  }

  const closeChatTab = (id) => {
    if (chatTabs.length <= 1) return // mindestens 1 Tab
    setChatTabs(prev => {
      const filtered = prev.filter(t => t.id !== id)
      if (activeChatId === id) {
        setActiveChatId(filtered[filtered.length - 1].id)
      }
      return filtered
    })
  }

  const changeTabRole = (tabId, roleName) => {
    const role = roles.find(r => r.name === roleName)
    setChatTabs(prev => prev.map(t => t.id === tabId ? {
      ...t,
      role: roleName,
      title: role?.display_name || roleName,
    } : t))
  }

  const clearTabMessages = (tabId) => {
    setChatTabs(prev => prev.map(t => t.id === tabId ? { ...t, messages: [] } : t))
  }

  // ── Send Message ──
  const sendMessage = async () => {
    if (!input.trim() || loading || !activeChat) return
    const userMsg = input.trim()
    setInput('')

    // Add user message
    setChatTabs(prev => prev.map(t => t.id === activeChatId
      ? { ...t, messages: [...t.messages, { role: 'user', content: userMsg, time: new Date() }] }
      : t
    ))

    setLoading(true)
    try {
      const result = await api.askGhost(activeChat.role, userMsg, {}, selectedModel || null)
      const aiMsg = result.error
        ? `⚠️ ${result.error}${result.hint ? '\n💡 ' + result.hint : ''}`
        : result.response || result.answer || `⏳ Anfrage an ${result.model} gesendet (Task: ${result.task_id?.slice(0, 8)}...)\nStatus: ${result.status}`

      setChatTabs(prev => prev.map(t => t.id === activeChatId
        ? { ...t, messages: [...t.messages, { role: 'assistant', content: aiMsg, time: new Date(), model: result.model }] }
        : t
      ))
    } catch (err) {
      setChatTabs(prev => prev.map(t => t.id === activeChatId
        ? { ...t, messages: [...t.messages, { role: 'system', content: `❌ Fehler: ${err.message}`, time: new Date() }] }
        : t
      ))
    }
    setLoading(false)
  }

  // ── Broadcast: Send to ALL open tabs ──
  const broadcastMessage = async () => {
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')

    // Add user message to all tabs
    setChatTabs(prev => prev.map(t => ({
      ...t,
      messages: [...t.messages, { role: 'user', content: userMsg, time: new Date(), broadcast: true }]
    })))

    setLoading(true)
    const results = await Promise.allSettled(
      chatTabs.map(async (tab) => {
        try {
          const result = await api.askGhost(tab.role, userMsg)
          return { tabId: tab.id, result }
        } catch (err) {
          return { tabId: tab.id, error: err.message }
        }
      })
    )

    setChatTabs(prev => prev.map(t => {
      const res = results.find(r => r.value?.tabId === t.id || r.reason?.tabId === t.id)
      const val = res?.value || res?.reason
      if (!val) return t
      const aiMsg = val.error
        ? `❌ ${val.error}`
        : val.result?.response || val.result?.answer || `⏳ Task: ${val.result?.task_id?.slice(0, 8)}… (${val.result?.model})`
      return {
        ...t,
        messages: [...t.messages, { role: 'assistant', content: aiMsg, time: new Date(), model: val.result?.model }]
      }
    }))
    setLoading(false)
  }

  const saveConfig = async (key, value) => {
    try {
      await api.llmUpdateConfig(key, String(value))
    } catch (e) {
      console.error('Config speichern fehlgeschlagen:', e)
    }
  }

  const selectedRole = roles.find(r => r.name === activeChat?.role)
  const runningInstances = instances.filter(i => i.state === 'running')

  // ═══════════════════════════════════════
  //  RENDER
  // ═══════════════════════════════════════
  return (
    <div style={sx.container}>
      {/* ── Top Bar: Chat Tabs ── */}
      <div style={sx.chatTabBar}>
        <div style={sx.chatTabList}>
          {chatTabs.map(tab => {
            const tabRole = roles.find(r => r.name === tab.role)
            return (
              <div
                key={tab.id}
                style={{
                  ...sx.chatTab,
                  ...(tab.id === activeChatId ? sx.chatTabActive : {}),
                  borderBottomColor: tab.id === activeChatId ? (tabRole?.color || '#00ffcc') : 'transparent',
                }}
                onClick={() => { setActiveChatId(tab.id); setShowSettings(false) }}
              >
                <span style={{ fontSize: '12px' }}>{tabRole?.icon || '👻'}</span>
                <span style={sx.chatTabTitle}>{tab.title}</span>
                <span style={{ fontSize: '9px', color: '#556677' }}>({tab.messages.filter(m => m.role === 'assistant').length})</span>
                {chatTabs.length > 1 && (
                  <button
                    style={sx.chatTabClose}
                    onClick={(e) => { e.stopPropagation(); closeChatTab(tab.id) }}
                    title="Tab schließen"
                  >×</button>
                )}
              </div>
            )
          })}
        </div>
        <div style={sx.chatTabActions}>
          {/* New Tab Dropdown */}
          <div style={{ position: 'relative' }}>
            <button style={sx.addTabBtn} title="Neuen Chat-Tab öffnen"
              onClick={() => {
                if (roles.length > 0) addChatTab(roles[0].name)
              }}
            >+</button>
          </div>
          <button
            style={{ ...sx.settingsBtn, ...(showSettings ? { background: 'rgba(0,255,204,0.1)', color: '#00ffcc' } : {}) }}
            onClick={() => setShowSettings(!showSettings)}
            title="Chat-Einstellungen"
          >⚙️</button>
          <button
            style={{ ...sx.settingsBtn, ...(showAppSettings ? { background: 'rgba(0,255,204,0.1)', color: '#00ffcc' } : {}) }}
            onClick={() => setShowAppSettings(!showAppSettings)}
            title="App-Einstellungen"
          >🔧</button>
        </div>
      </div>

      {/* ── App Settings Panel ── */}
      {showAppSettings ? (
        <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
          <AppSettingsPanel schema={appSchema} settings={appSettings} onUpdate={updateAppSetting} onReset={resetAppSettings} title="Ghost Chat" />
        </div>
      ) : showSettings ? (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={sx.settingsTabBar}>
            {SETTINGS_TABS.map(t => (
              <button key={t.id} onClick={() => setSettingsTab(t.id)} style={{
                ...sx.sTab, ...(settingsTab === t.id ? sx.sTabActive : {}),
              }}>{t.label}</button>
            ))}
          </div>

          <div style={sx.settingsContent}>
            {/* Persönlichkeit */}
            {settingsTab === 'personality' && (
              <>
                <div style={sx.settingHeader}>🎭 Ghost-Persönlichkeit</div>
                <p style={sx.settingDesc}>Ton, Stil und Charakter des Ghosts definieren.</p>

                <div style={sx.settingGroup}>
                  <label style={sx.label}>Verfügbare Rollen</label>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {roles.map(r => (
                      <div key={r.name} style={sx.personalityCard}>
                        <span style={{ fontSize: 18 }}>{r.icon}</span>
                        <div>
                          <div style={{ fontWeight: 600, color: r.color || '#e0e0e0', fontSize: 12 }}>{r.display_name}</div>
                          <div style={{ fontSize: 10, color: '#6688aa' }}>{r.description?.substring(0, 50)}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div style={sx.settingGroup}>
                  <label style={sx.label}>Persönlichkeits-Prompt</label>
                  <textarea value={editPersonality} onChange={e => setEditPersonality(e.target.value)}
                    placeholder="Du bist freundlich, technisch versiert…" style={sx.textarea} rows={5} />
                  <button onClick={() => saveConfig('ghost_personality', editPersonality)} style={sx.saveBtn}>💾 Speichern</button>
                </div>

                <div style={sx.settingGroup}>
                  <label style={sx.label}>Temperatur</label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <input type="range" min="0" max="2" step="0.1" value={temperature}
                      onChange={e => setTemperature(parseFloat(e.target.value))}
                      onMouseUp={() => saveConfig('ghost_temperature', temperature)}
                      style={{ flex: 1 }} />
                    <span style={sx.rangeValue}>{temperature.toFixed(1)}</span>
                  </div>
                  <div style={sx.settingHint}>0 = Deterministisch · 0.7 = Kreativ · 2.0 = Sehr zufällig</div>
                </div>
              </>
            )}

            {/* Modell */}
            {settingsTab === 'model' && (
              <>
                <div style={sx.settingHeader}>🧠 Modell-Auswahl & Ghost-Status</div>
                <p style={sx.settingDesc}>Modelle pro Rolle zuweisen. Änderungen sind sofort im Chat aktiv.</p>

                {/* Ghost-Status pro Rolle */}
                <div style={sx.settingGroup}>
                  <label style={sx.label}>👻 Ghost-Status pro Rolle</label>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {roles.map(role => {
                      const active = getActiveGhostForRole(role.name)
                      const compat = getCompatModelsForRole(role.name)
                      return (
                        <div key={role.name} style={{
                          padding: '10px 12px', borderRadius: 8, 
                          background: active ? 'rgba(0,255,136,0.04)' : 'rgba(255,68,68,0.04)',
                          border: `1px solid ${active ? 'rgba(0,255,136,0.2)' : 'rgba(255,68,68,0.2)'}`,
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                            <span style={{ fontSize: 16 }}>{role.icon}</span>
                            <span style={{ fontWeight: 600, fontSize: 12, color: role.color || '#e0e0e0' }}>{role.display_name}</span>
                            {active ? (
                              <span style={{ fontSize: 10, color: '#00ff88', marginLeft: 'auto' }}>● {active.model_display || active.model_name}</span>
                            ) : (
                              <span style={{ fontSize: 10, color: '#ff4444', marginLeft: 'auto' }}>○ Kein Ghost aktiv</span>
                            )}
                          </div>
                          {/* Inline-Swap: kompatible Modelle */}
                          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                            {(compat.length > 0 ? compat : models).slice(0, 6).map(m => {
                              const modelName = m.model_name || m.name
                              const isActive = active?.model_name === modelName
                              return (
                                <button
                                  key={modelName}
                                  disabled={swapping}
                                  onClick={() => handleQuickSwap(role.name, modelName)}
                                  style={{
                                    padding: '3px 8px', borderRadius: 5, fontSize: 10,
                                    border: `1px solid ${isActive ? '#00ffcc' : '#2a2a40'}`,
                                    background: isActive ? 'rgba(0,255,204,0.1)' : 'transparent',
                                    color: isActive ? '#00ffcc' : '#6688aa',
                                    cursor: swapping ? 'wait' : 'pointer',
                                    transition: 'all 0.15s',
                                  }}
                                >
                                  {isActive ? '✓ ' : ''}{m.display_name || modelName}
                                  {m.fitness_score && <span style={{ marginLeft: 4, color: m.fitness_score > 0.8 ? '#00ff88' : '#ffaa00' }}>
                                    {(m.fitness_score * 100).toFixed(0)}%
                                  </span>}
                                </button>
                              )
                            })}
                          </div>
                        </div>
                      )
                    })}
                    {roles.length === 0 && <div style={{ fontSize: 12, color: '#556677' }}>Keine Rollen gefunden</div>}
                  </div>
                </div>

                {runningInstances.length > 0 && (
                  <div style={sx.settingGroup}>
                    <label style={sx.label}>🟢 Aktive Agenten-Instanzen (Mission Control)</label>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {runningInstances.map(inst => (
                        <div key={inst.id} style={sx.instanceRow}>
                          <span style={{ color: '#00ff88', fontSize: 10 }}>●</span>
                          <span style={{ fontWeight: 600, fontSize: 12, color: '#e0e0e0' }}>{inst.model_name || 'Modell'}</span>
                          <span style={{ color: '#00ffcc', fontSize: 11 }}>→ {inst.role_name || 'Frei'}</span>
                          <span style={{ color: '#556677', fontSize: 10, marginLeft: 'auto', fontFamily: 'monospace' }}>
                            GPU {inst.gpu_index} · {inst.backend}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div style={sx.settingGroup}>
                  <label style={sx.label}>Alle verfügbaren Modelle ({models.length})</label>
                  <div style={sx.modelGrid}>
                    {models.map(m => {
                      const isSelected = selectedModel === m.name
                      const isLoaded = m.is_loaded || m.state === 'active'
                      return (
                        <div key={m.id || m.name} onClick={() => {
                          setSelectedModel(m.name)
                          saveConfig('ghost_default_model', m.name)
                        }} style={{
                          ...sx.modelCard,
                          borderColor: isSelected ? '#00ffcc' : '#1a1a2e',
                          background: isSelected ? 'rgba(0,255,204,0.05)' : '#12121e',
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                            {isLoaded && <span style={{ fontSize: 8, color: '#00ff88' }}>●</span>}
                            <div style={{ fontWeight: 600, color: '#e0e0e0', fontSize: 12 }}>{m.display_name || m.name}</div>
                          </div>
                          <div style={{ fontSize: 10, color: '#00f5ff', fontFamily: 'monospace' }}>{m.provider || m.type || '-'}</div>
                          {m.quantization && <div style={{ fontSize: 9, color: '#8899aa' }}>{m.parameter_count} · {m.quantization}</div>}
                          {(m.context_window || m.context_size) && <div style={{ fontSize: 9, color: '#556677' }}>Ctx: {m.context_window || m.context_size}</div>}
                        </div>
                      )
                    })}
                    {models.length === 0 && <div style={{ fontSize: 12, color: '#556677' }}>Keine Modelle. Gehe zum Ghost LLM Manager.</div>}
                  </div>
                </div>

                <div style={sx.settingGroup}>
                  <label style={sx.label}>Kontext-Fenster</label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <input type="range" min="1024" max="131072" step="1024" value={contextWindow}
                      onChange={e => setContextWindow(parseInt(e.target.value))}
                      onMouseUp={() => saveConfig('ghost_context_window', contextWindow)}
                      style={{ flex: 1 }} />
                    <span style={sx.rangeValue}>{(contextWindow / 1024).toFixed(0)}K</span>
                  </div>
                </div>
              </>
            )}

            {/* Memory */}
            {settingsTab === 'memory' && (
              <>
                <div style={sx.settingHeader}>💾 Memory & Konversation</div>
                <p style={sx.settingDesc}>Bestimme ob und wie Konversationen gespeichert werden.</p>

                <div style={sx.settingGroup}>
                  <div style={sx.toggleRow}>
                    <label style={sx.label}>Memory aktiviert</label>
                    <button onClick={() => {
                      const v = !memoryEnabled; setMemoryEnabled(v); saveConfig('ghost_memory_enabled', v)
                    }} style={{
                      ...sx.toggleBtn,
                      background: memoryEnabled ? 'rgba(0,255,136,0.15)' : '#1a1a2e',
                      color: memoryEnabled ? '#00ff88' : '#555',
                      borderColor: memoryEnabled ? '#00ff8844' : '#2a2a40',
                    }}>
                      {memoryEnabled ? '✅ An' : '❌ Aus'}
                    </button>
                  </div>
                  <div style={sx.settingHint}>Wenn aktiviert, merkt sich der Ghost Konversationen.</div>
                </div>

                <div style={sx.settingGroup}>
                  <label style={sx.label}>Vergleich: OpenClaw vs. DBAI</label>
                  <div style={sx.compareTable}>
                    {[
                      ['Feature', 'OpenClaw', 'DBAI Ghost'],
                      ['Backend', 'LanceDB', 'pgvector'],
                      ['Auto-Capture', '✅', memoryEnabled ? '✅' : '❌'],
                      ['Auto-Recall', '✅', memoryEnabled ? '✅' : '❌'],
                      ['Embedding', 'NVIDIA 1024d', 'pgvector 1536d'],
                    ].map((row, i) => (
                      <div key={i} style={{ ...sx.compareRow, fontWeight: i === 0 ? 600 : 400 }}>
                        {row.map((cell, j) => <span key={j} style={j === 0 ? sx.compareLabel : sx.compareVal}>{cell}</span>)}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}

            {/* System-Prompt */}
            {settingsTab === 'system' && (
              <>
                <div style={sx.settingHeader}>⚙️ System-Prompt</div>
                <p style={sx.settingDesc}>Kernverhalten des Ghost definieren (SOUL.md-Äquivalent).</p>

                <div style={sx.settingGroup}>
                  <label style={sx.label}>System-Prompt (wird bei jeder Nachricht mitgesendet)</label>
                  <textarea value={editPrompt} onChange={e => setEditPrompt(e.target.value)}
                    placeholder="Du bist Ghost, der System-Manager für DBAI…"
                    style={{ ...sx.textarea, minHeight: 180 }} rows={10} />
                  <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                    <button onClick={() => saveConfig('ghost_system_prompt', editPrompt)} style={sx.saveBtn}>💾 Speichern</button>
                    <button onClick={() => {
                      const def = 'Du bist Ghost, der System-Manager für DBAI.\nDu hilfst bei Systemverwaltung, Datenbank-Queries und Hardware-Überwachung.\nDu antwortest auf Deutsch und bist technisch präzise.'
                      setEditPrompt(def); saveConfig('ghost_system_prompt', def)
                    }} style={sx.resetBtn}>🔄 Standard</button>
                  </div>
                </div>

                <div style={sx.settingGroup}>
                  <label style={sx.label}>Aktuelle Konfiguration</label>
                  <div style={sx.configTable}>
                    {config.filter(c => c.category === 'ghost' || c.category === 'llm').map(c => (
                      <div key={c.key} style={sx.configRow}>
                        <span style={{ color: '#8899aa', fontFamily: 'monospace', fontSize: 10 }}>{c.key}</span>
                        <span style={{ color: '#b0c8e0', fontSize: 11 }}>
                          {(c.value || '').substring(0, 50)}{(c.value || '').length > 50 ? '…' : ''}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      ) : (
        /* ── Chat Area ── */
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Role selector for active tab */}
          {activeChat && (
            <div style={sx.roleBar}>
              <span style={{ fontSize: 11, color: '#6688aa', marginRight: 4 }}>Agent:</span>
              {roles.map(r => {
                const hasGhost = getActiveGhostForRole(r.name)
                return (
                  <button key={r.name} onClick={() => changeTabRole(activeChatId, r.name)} style={{
                    ...sx.roleBtn,
                    ...(activeChat.role === r.name ? {
                      borderColor: r.color || '#00ffcc',
                      background: `${r.color || '#00ffcc'}15`,
                      color: r.color || '#00ffcc',
                    } : {}),
                    opacity: hasGhost ? 1 : 0.5,
                  }}>
                    {r.icon} {r.display_name}
                    {!hasGhost && <span style={{ fontSize: 8, marginLeft: 2 }}>○</span>}
                  </button>
                )
              })}
              {activeChat.messages.length > 0 && (
                <button style={sx.clearBtn} onClick={() => clearTabMessages(activeChatId)} title="Chat leeren">🗑️</button>
              )}
            </div>
          )}

          {/* Active Ghost status / warning */}
          {selectedRole && (() => {
            const activeGhost = getActiveGhostForRole(activeChat?.role)
            return activeGhost ? (
              <div style={sx.promptHint}>
                <span>{selectedRole.icon} {selectedRole.display_name}</span>
                <span style={{ color: '#556677', margin: '0 6px' }}>·</span>
                <span style={{ color: '#00ff88' }}>🧠 {activeGhost.model_display || activeGhost.model_name}</span>
                <span style={{ color: '#556677', margin: '0 6px' }}>·</span>
                <span>{selectedRole.description}</span>
                {runningInstances.find(i => i.role_name === selectedRole.name) && (
                  <>
                    <span style={{ color: '#556677', margin: '0 6px' }}>·</span>
                    <span style={{ color: '#00ff88' }}>🟢 GPU</span>
                  </>
                )}
              </div>
            ) : (
              <div style={{
                ...sx.promptHint,
                background: 'rgba(255,68,68,0.06)', borderBottom: '1px solid rgba(255,68,68,0.2)',
              }}>
                <span>⚠️ <strong>{selectedRole.display_name}</strong> hat keinen aktiven Ghost</span>
                <span style={{ color: '#556677', margin: '0 6px' }}>·</span>
                <span style={{ fontSize: 10, color: '#ff8866' }}>Modell zuweisen:</span>
                {getCompatModelsForRole(activeChat?.role).slice(0, 4).map(c => (
                  <button
                    key={c.model_name}
                    disabled={swapping}
                    onClick={() => handleQuickSwap(activeChat.role, c.model_name)}
                    style={{
                      padding: '1px 6px', borderRadius: 4, fontSize: 9, marginLeft: 4,
                      border: '1px solid rgba(0,255,204,0.3)', background: 'rgba(0,255,204,0.08)',
                      color: '#00ffcc', cursor: swapping ? 'wait' : 'pointer',
                    }}
                  >{c.model_name}</button>
                ))}
                {getCompatModelsForRole(activeChat?.role).length === 0 && models.slice(0, 3).map(m => (
                  <button
                    key={m.name}
                    disabled={swapping}
                    onClick={() => handleQuickSwap(activeChat.role, m.name)}
                    style={{
                      padding: '1px 6px', borderRadius: 4, fontSize: 9, marginLeft: 4,
                      border: '1px solid rgba(0,255,204,0.3)', background: 'rgba(0,255,204,0.08)',
                      color: '#00ffcc', cursor: swapping ? 'wait' : 'pointer',
                    }}
                  >{m.display_name || m.name}</button>
                ))}
              </div>
            )
          })()}

          {/* Multi-agent status bar */}
          {chatTabs.length > 1 && (
            <div style={sx.multiAgentBar}>
              <span style={{ fontSize: 10, color: '#6688aa' }}>
                📡 {chatTabs.length} Agenten aktiv
              </span>
              <span style={{ fontSize: 10, color: '#556677' }}>
                {chatTabs.map(t => {
                  const r = roles.find(rl => rl.name === t.role)
                  return r?.icon || '👻'
                }).join(' ')}
              </span>
            </div>
          )}

          {/* Messages */}
          <div className="chat-messages" ref={messagesRef} style={{ flex: 1, overflow: 'auto' }}>
            {activeChat?.messages.length === 0 && (
              <div style={sx.emptyChat}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>👻</div>
                <p style={{ fontWeight: 600 }}>Starte eine Konversation</p>
                <p style={{ fontSize: 11, color: '#556677', marginTop: 4, maxWidth: 300 }}>
                  Wähle eine Rolle und stelle eine Frage. Öffne mehrere Tabs mit <strong>+</strong> für parallele Agenten.
                </p>
                {roles.length > 0 && (
                  <div style={{ display: 'flex', gap: 6, marginTop: 16, flexWrap: 'wrap', justifyContent: 'center' }}>
                    {roles.map(r => (
                      <button key={r.name} onClick={() => { changeTabRole(activeChatId, r.name) }} style={{
                        ...sx.roleBtn,
                        padding: '6px 12px',
                        ...(activeChat?.role === r.name ? {
                          borderColor: r.color || '#00ffcc',
                          background: `${r.color || '#00ffcc'}15`,
                          color: r.color || '#00ffcc',
                        } : {}),
                      }}>
                        {r.icon} {r.display_name}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
            {activeChat?.messages.map((msg, i) => (
              <div key={i} className={`chat-message ${msg.role}`}>
                {msg.broadcast && <span style={{ fontSize: 9, color: '#ffaa00', marginRight: 4 }}>📡 Broadcast</span>}
                {msg.content.split('\n').map((line, j) => (
                  <div key={j}>{line}</div>
                ))}
                {msg.model && <div style={{ fontSize: 9, color: '#556677', marginTop: 2 }}>via {msg.model}</div>}
              </div>
            ))}
            {loading && (
              <div className="chat-message assistant" style={{ opacity: 0.6 }}>
                <span style={{ animation: 'pulse 1s infinite' }}>⏳</span> Ghost denkt nach...
              </div>
            )}
          </div>

          {/* Input Bar */}
          <div style={sx.inputBar}>
            <div className="chat-input" style={{ flex: 1, display: 'flex' }}>
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) sendMessage()
                  if (e.key === 'Enter' && e.shiftKey) broadcastMessage()
                }}
                placeholder={`Frage an ${selectedRole?.display_name || 'Ghost'}… (Shift+Enter = an alle)`}
                disabled={loading}
                autoFocus
                style={{ flex: 1 }}
              />
              <button onClick={sendMessage} disabled={loading} title="An aktuellen Agent senden">
                Senden
              </button>
              {chatTabs.length > 1 && (
                <button onClick={broadcastMessage} disabled={loading}
                  style={{ background: 'rgba(255,170,0,0.15)', color: '#ffaa00', borderColor: 'rgba(255,170,0,0.3)' }}
                  title="An ALLE Agenten senden (Broadcast)">
                  📡
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Quick-launch role tabs */}
      {!showSettings && roles.length > 0 && (
        <div style={sx.quickLaunch}>
          <span style={{ fontSize: 10, color: '#556677' }}>Neuer Agent:</span>
          {roles.map(r => (
            <button key={r.name} onClick={() => addChatTab(r.name)} style={sx.quickBtn} title={`Neuen ${r.display_name}-Tab öffnen`}>
              {r.icon}
            </button>
          ))}
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

/* ═══════════════════════════════════════
   STYLES
   ═══════════════════════════════════════ */
const sx = {
  container: {
    display: 'flex', flexDirection: 'column', height: '100%',
    fontFamily: "'Inter', -apple-system, sans-serif", fontSize: 13,
  },

  // ── Chat Tab Bar (like browser tabs) ──
  chatTabBar: {
    display: 'flex', alignItems: 'center', background: '#08080e',
    borderBottom: '1px solid #1a1a2e', padding: '0 6px', minHeight: 34, flexShrink: 0,
  },
  chatTabList: {
    display: 'flex', flex: 1, gap: 1, overflowX: 'auto', alignItems: 'flex-end',
    scrollbarWidth: 'none',
  },
  chatTab: {
    display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px',
    background: '#0e0e1a', borderRadius: '6px 6px 0 0', cursor: 'pointer',
    fontSize: 11, color: '#6688aa', whiteSpace: 'nowrap', transition: 'all 0.15s',
    borderBottom: '2px solid transparent', minWidth: 0,
  },
  chatTabActive: {
    background: '#14142a', color: '#e0e0e0',
  },
  chatTabTitle: {
    fontSize: 11, fontWeight: 500, maxWidth: 100, overflow: 'hidden',
    textOverflow: 'ellipsis', whiteSpace: 'nowrap',
  },
  chatTabClose: {
    border: 'none', background: 'transparent', color: '#556677',
    cursor: 'pointer', fontSize: 12, padding: '0 2px', lineHeight: 1,
    borderRadius: 3,
  },
  chatTabActions: {
    display: 'flex', gap: 4, alignItems: 'center', marginLeft: 6, flexShrink: 0,
  },
  addTabBtn: {
    width: 22, height: 22, border: '1px solid #2a2a40', borderRadius: 6,
    background: 'transparent', color: '#6688aa', cursor: 'pointer',
    fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
    lineHeight: 1,
  },
  settingsBtn: {
    width: 22, height: 22, border: '1px solid #2a2a40', borderRadius: 6,
    background: 'transparent', color: '#6688aa', cursor: 'pointer',
    fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
  },

  // ── Role Bar ──
  roleBar: {
    display: 'flex', gap: 5, padding: '6px 10px',
    borderBottom: '1px solid #1a1a2e', alignItems: 'center', flexWrap: 'wrap',
  },
  roleBtn: {
    padding: '2px 7px', borderRadius: 5, border: '1px solid #2a2a40',
    background: 'transparent', color: '#6688aa', cursor: 'pointer', fontSize: 10,
    whiteSpace: 'nowrap', transition: 'all 0.15s',
  },
  clearBtn: {
    marginLeft: 'auto', border: 'none', background: 'transparent',
    color: '#556677', cursor: 'pointer', fontSize: 11, padding: '2px 4px',
  },
  promptHint: {
    fontSize: 10, color: '#6688aa', padding: '4px 10px',
    background: '#0a0a14', borderBottom: '1px solid #1a1a2e',
    display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 2,
  },
  multiAgentBar: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '3px 10px', background: 'rgba(255,170,0,0.03)',
    borderBottom: '1px solid rgba(255,170,0,0.1)',
  },
  emptyChat: {
    textAlign: 'center', marginTop: 40, color: '#6688aa',
  },

  // ── Input Bar ──
  inputBar: {
    padding: '6px 8px', borderTop: '1px solid #1a1a2e', background: '#0a0a14',
  },

  // ── Quick Launch ──
  quickLaunch: {
    display: 'flex', gap: 4, padding: '4px 10px', alignItems: 'center',
    background: '#08080e', borderTop: '1px solid #1a1a2e',
  },
  quickBtn: {
    width: 24, height: 24, border: '1px solid #2a2a40', borderRadius: 6,
    background: 'transparent', cursor: 'pointer', fontSize: 12,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    transition: 'all 0.15s',
  },

  // ── Settings ──
  settingsTabBar: {
    display: 'flex', gap: 2, padding: '6px 10px', borderBottom: '1px solid #1a1a2e',
    background: '#0e0e1a', flexShrink: 0,
  },
  sTab: {
    padding: '4px 8px', borderRadius: 5, border: '1px solid transparent',
    background: 'transparent', color: '#6688aa', cursor: 'pointer',
    fontSize: 10, whiteSpace: 'nowrap', transition: 'all 0.2s',
  },
  sTabActive: {
    background: 'rgba(0,255,204,0.08)', color: '#00ffcc',
    border: '1px solid rgba(0,255,204,0.2)',
  },
  settingsContent: { flex: 1, overflow: 'auto', padding: 16 },
  settingHeader: { fontSize: 14, fontWeight: 700, color: '#e0e0e0', marginBottom: 4 },
  settingDesc: { fontSize: 11, color: '#6688aa', marginBottom: 12, lineHeight: 1.5 },
  settingGroup: {
    marginBottom: 14, padding: 12, background: '#12121e',
    border: '1px solid #1a1a2e', borderRadius: 8,
  },
  label: { display: 'block', fontSize: 11, fontWeight: 600, color: '#8899aa', marginBottom: 6 },
  textarea: {
    width: '100%', padding: 10, background: '#0a0a14', border: '1px solid #2a2a40',
    borderRadius: 6, color: '#e0e0e0', fontSize: 12, fontFamily: "'JetBrains Mono', monospace",
    resize: 'vertical', outline: 'none', lineHeight: 1.5, boxSizing: 'border-box',
  },
  saveBtn: {
    padding: '6px 14px', borderRadius: 6, border: 'none',
    background: 'linear-gradient(135deg, #00aa88, #00ccaa)',
    color: '#0a0a0f', fontWeight: 700, fontSize: 11, cursor: 'pointer', marginTop: 6,
  },
  resetBtn: {
    padding: '6px 12px', borderRadius: 6, border: '1px solid #2a2a40',
    background: 'transparent', color: '#6688aa', fontSize: 11, cursor: 'pointer', marginTop: 6,
  },
  rangeValue: {
    fontSize: 13, fontWeight: 700, color: '#00ffcc', fontFamily: 'monospace',
    minWidth: 40, textAlign: 'right',
  },
  settingHint: { fontSize: 10, color: '#556677', marginTop: 4 },
  toggleRow: { display: 'flex', alignItems: 'center', justifyContent: 'space-between' },
  toggleBtn: {
    padding: '5px 12px', borderRadius: 6, border: '1px solid',
    fontWeight: 600, fontSize: 11, cursor: 'pointer',
  },
  personalityCard: {
    display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px',
    background: '#0a0a14', border: '1px solid #1a1a2e', borderRadius: 6,
  },
  modelGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 6,
  },
  modelCard: {
    padding: 10, borderRadius: 6, border: '1px solid', cursor: 'pointer',
    transition: 'all 0.2s',
  },
  instanceRow: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
    background: '#0a0a14', borderRadius: 6, border: '1px solid rgba(0,255,136,0.1)',
  },
  compareTable: {
    background: '#0a0a14', borderRadius: 6, border: '1px solid #1a1a2e', overflow: 'hidden',
  },
  compareRow: {
    display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', padding: '6px 10px',
    borderBottom: '1px solid #1a1a2e', fontSize: 11,
  },
  compareLabel: { color: '#8899aa', fontWeight: 500 },
  compareVal: { color: '#b0c8e0', textAlign: 'center' },
  configTable: { display: 'flex', flexDirection: 'column', gap: 3 },
  configRow: {
    display: 'flex', justifyContent: 'space-between', padding: '4px 8px',
    background: '#0a0a14', borderRadius: 4, border: '1px solid #1a1a2e',
  },
}
