import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'

/**
 * OpenClaw Integrator — Verbindung zum OpenClaw-System
 * Liest live aus ~/.openclaw/ und zeigt Agenten, Cron-Jobs,
 * Addons, Integrationen, Gateway-Status und Skills.
 */

const AGENT_ICONS = {
  main: '🦞', worker: '⚡', brain: '🧠', content: '🎨', researcher: '📚', coder: '💻',
}

const ADDON_ICONS = {
  'n8n': '🔗', 'comfyui': '🎨', 'video-factory': '🎬', 'openhands': '🤖',
  'harbor': '⚓', 'grafana': '📊', 'minio': '💾', 'qdrant': '🔷',
  'qdrant-ui': '🔷', 'vllm-brain': '🧠', 'crewai': '👥', 'kling-video': '📹',
  'argocd': '🔄', 'gitea': '🐙', 'woodpecker': '🪵', 'prometheus': '📈',
  'longhorn': '🦬', 'k8s-dashboard': '☸️', 'llm-router': '🛤️',
  'system-library': '📚', 'alertmanager': '🔔',
}

const TAB_ITEMS = [
  { id: 'overview', label: '🦞 Übersicht' },
  { id: 'agents', label: '👥 Agenten' },
  { id: 'cron', label: '⏰ Cron-Jobs' },
  { id: 'addons', label: '🧩 Addons' },
  { id: 'integrations', label: '🔗 Verbindungen' },
  { id: 'skills', label: '⚡ Skills' },
  { id: 'memory', label: '🧠 Memory' },
]

export default function OpenClawIntegrator() {
  const [tab, setTab] = useState('overview')
  const [live, setLive] = useState(null)
  const [dbStatus, setDbStatus] = useState(null)
  const [gateway, setGateway] = useState(null)
  const [loading, setLoading] = useState(true)
  const [migrating, setMigrating] = useState(false)

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [liveData, statusData, gw] = await Promise.all([
        api.openclawLive().catch(() => null),
        api.openclawStatus().catch(() => null),
        api.openclawGatewayStatus().catch(() => ({ online: false })),
      ])
      setLive(liveData)
      setDbStatus(statusData)
      setGateway(gw)
    } catch (e) {
      console.error('OpenClaw laden fehlgeschlagen:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadAll() }, [loadAll])

  const handleMigration = async () => {
    setMigrating(true)
    try {
      await api.openclawStartMigration()
      setTimeout(loadAll, 2000)
    } catch (e) {
      alert('Migration fehlgeschlagen: ' + e.message)
    }
    setMigrating(false)
  }

  const handleActivateSkill = async (name) => {
    try {
      await api.openclawActivateSkill(name)
      loadAll()
    } catch (e) {
      alert('Aktivierung fehlgeschlagen: ' + e.message)
    }
  }

  if (loading) return <div style={sx.loadingState}>⏳ Lade OpenClaw-Konfiguration…</div>
  if (!live?.installed) return (
    <div style={sx.loadingState}>
      <div style={{ fontSize: 48 }}>🦞</div>
      <div style={{ fontSize: 16, fontWeight: 600, marginTop: 12 }}>OpenClaw nicht gefunden</div>
      <div style={{ color: '#6688aa', fontSize: 13, marginTop: 6 }}>
        Kein <code>~/.openclaw/</code> Verzeichnis auf diesem System.
      </div>
    </div>
  )

  const agents = live.agents || []
  const agentsMeta = live.agents_meta || {}
  const cronJobs = live.cron_jobs || []
  const addons = live.addons || []
  const integrations = live.integrations || {}
  const k8s = live.kubernetes || {}
  const memCfg = live.memory || {}
  const stats = dbStatus?.stats || {}
  const skills = dbStatus?.skills || []
  const memories = dbStatus?.memories || []

  return (
    <div style={sx.container}>
      {/* Tab-Leiste */}
      <div style={sx.tabBar}>
        {TAB_ITEMS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            ...sx.tab, ...(tab === t.id ? sx.tabActive : {}),
          }}>{t.label}</button>
        ))}
        <div style={{ flex: 1 }} />
        <button onClick={loadAll} style={sx.refreshBtn}>🔄</button>
      </div>

      <div style={sx.content}>
        {/* ── ÜBERSICHT ── */}
        {tab === 'overview' && (
          <div style={sx.overviewGrid}>
            <div style={sx.card}>
              <div style={sx.cardTitle}>🌐 Gateway</div>
              <div style={sx.statusRow}>
                <span style={{ ...sx.statusDot, background: gateway?.online ? '#00ff88' : '#ff4444' }} />
                <span style={{ color: gateway?.online ? '#00ff88' : '#ff6666' }}>
                  {gateway?.online ? 'Online' : 'Offline'}
                </span>
                <span style={sx.metaText}>Port {live.gateway?.port || '18788'}</span>
              </div>
              <div style={sx.metaText}>Auth: {live.gateway?.auth_mode || '-'}</div>
            </div>

            <div style={sx.card}>
              <div style={sx.cardTitle}>👥 Agenten</div>
              <div style={sx.bigNum}>{agents.length}</div>
              <div style={sx.agentMini}>
                {agents.map(a => (
                  <span key={a.id} title={`${a.name} (${a.role})`} style={{ fontSize: 18 }}>
                    {AGENT_ICONS[a.role] || '🤖'}
                  </span>
                ))}
              </div>
            </div>

            <div style={sx.card}>
              <div style={sx.cardTitle}>⏰ Cron-Jobs</div>
              <div style={sx.bigNum}>{cronJobs.length}</div>
              <div style={sx.metaText}>{cronJobs.filter(j => j.enabled).length} aktiv</div>
            </div>

            <div style={sx.card}>
              <div style={sx.cardTitle}>🧩 Addons</div>
              <div style={sx.bigNum}>{addons.length}</div>
              <div style={sx.metaText}>{addons.filter(a => !a.disabled).length} aktiviert</div>
            </div>

            <div style={sx.card}>
              <div style={sx.cardTitle}>☸️ Kubernetes</div>
              <div style={sx.metaText}>Namespace: {k8s.namespace || '-'}</div>
              {k8s.nodes && Object.entries(k8s.nodes).map(([name, node]) => (
                <div key={name} style={sx.k8sNode}>
                  <span style={{ fontWeight: 600, color: '#e0e0e0' }}>{name}</span>
                  <span style={sx.metaText}>{node.ip}</span>
                  <span style={{ color: '#00f5ff', fontSize: 11 }}>{node.gpu}</span>
                </div>
              ))}
            </div>

            <div style={sx.card}>
              <div style={sx.cardTitle}>🧠 Memory</div>
              <div style={sx.metaText}>LanceDB: {memCfg.lancedb ? '✅' : '❌'}</div>
              <div style={sx.metaText}>Auto-Capture: {memCfg.auto_capture ? '✅' : '❌'}</div>
              <div style={sx.metaText}>Auto-Recall: {memCfg.auto_recall ? '✅' : '❌'}</div>
              <div style={sx.metaText}>Embedding: {memCfg.embedding_model || '-'}</div>
              <div style={sx.metaText}>Dimensionen: {memCfg.dimensions || '-'}</div>
            </div>

            {live.storage?.nvme && (
              <div style={sx.card}>
                <div style={sx.cardTitle}>💾 Storage</div>
                <div style={sx.metaText}>NVMe: {live.storage.nvme.mount}</div>
                <div style={sx.metaText}>
                  {live.storage.nvme.used} / {live.storage.nvme.total}
                  {live.storage.nvme.free && <span> ({live.storage.nvme.free} frei)</span>}
                </div>
              </div>
            )}

            <div style={sx.card}>
              <div style={sx.cardTitle}>📊 DBAI-Bridge</div>
              <div style={sx.metaText}>Skills: {stats.total_skills || 0} ({stats.active_skills || 0} aktiv)</div>
              <div style={sx.metaText}>Memories: {stats.total_memories || 0} ({stats.integrated_memories || 0} integriert)</div>
              <div style={sx.metaText}>Migrationen: {stats.total_migrations || 0}</div>
            </div>
          </div>
        )}

        {/* ── AGENTEN ── */}
        {tab === 'agents' && (
          <div style={sx.agentGrid}>
            {agents.map(agent => {
              const meta = agentsMeta[agent.id] || {}
              return (
                <div key={agent.id} style={sx.agentCard}>
                  <div style={sx.agentHeader}>
                    <span style={{ fontSize: 32 }}>{AGENT_ICONS[agent.role] || '🤖'}</span>
                    <div>
                      <div style={sx.agentName}>{agent.name}</div>
                      <div style={sx.agentRole}>{agent.role}</div>
                    </div>
                  </div>
                  <div style={sx.agentModel}>{agent.model}</div>
                  {meta.node && (
                    <div style={sx.metaText}>
                      Node: <span style={{ color: '#00f5ff' }}>{meta.node}</span>
                      {meta.gpu && <span> • {meta.gpu}</span>}
                    </div>
                  )}
                  {agent.personality && (
                    <div style={{ fontSize: 12, color: '#6688aa', marginTop: 6, lineHeight: 1.4 }}>
                      {agent.personality.substring(0, 120)}…
                    </div>
                  )}
                  <div style={sx.agentTags}>
                    {(agent.skills || []).slice(0, 5).map(s => (
                      <span key={s} style={sx.skillTag}>{s}</span>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* ── CRON-JOBS ── */}
        {tab === 'cron' && (
          <div style={sx.listContainer}>
            <div style={sx.sectionHeader}>
              ⏰ Automatische Tasks ({cronJobs.length})
              <span style={{ fontSize: 11, color: '#6688aa', marginLeft: 8 }}>
                Cron: {live.cron_enabled ? '✅ aktiv' : '❌ deaktiviert'}
              </span>
            </div>
            {cronJobs.map(job => (
              <div key={job.id} style={sx.cronCard}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ ...sx.statusDot, background: job.enabled ? '#00ff88' : '#555' }} />
                  <div>
                    <div style={{ fontWeight: 600, color: '#e0e0e0', fontSize: 13 }}>{job.name}</div>
                    <div style={{ fontSize: 11, color: '#6688aa' }}>{job.description}</div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 16, marginTop: 8, flexWrap: 'wrap' }}>
                  <span style={sx.cronMeta}>📅 {job.schedule}</span>
                  <span style={sx.cronMeta}>🤖 {job.agent_id}</span>
                  {job.last_status && (
                    <span style={{
                      ...sx.cronMeta,
                      color: job.last_status === 'success' ? '#00ff88' : '#ff6666',
                    }}>
                      {job.last_status === 'success' ? '✅' : '❌'} {job.last_status}
                    </span>
                  )}
                  {job.last_duration_ms && (
                    <span style={sx.cronMeta}>⏱ {(job.last_duration_ms / 1000).toFixed(1)}s</span>
                  )}
                </div>
              </div>
            ))}
            {cronJobs.length === 0 && (
              <div style={sx.emptyState}>Keine Cron-Jobs konfiguriert.</div>
            )}
          </div>
        )}

        {/* ── ADDONS ── */}
        {tab === 'addons' && (
          <div style={sx.addonGrid}>
            {addons.map((addon, i) => {
              const name = typeof addon === 'string' ? addon : addon.name || addon.id || `addon-${i}`
              const slug = name.toLowerCase().replace(/\s+/g, '-')
              const disabled = typeof addon === 'object' && addon.disabled
              const url = typeof addon === 'object' ? addon.url : null
              return (
                <div key={i} style={{
                  ...sx.addonCard,
                  opacity: disabled ? 0.4 : 1,
                  borderColor: disabled ? '#1a1a2e' : '#2a2a40',
                }}>
                  <span style={{ fontSize: 24 }}>{ADDON_ICONS[slug] || '🧩'}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, color: '#e0e0e0', fontSize: 13 }}>{name}</div>
                    {url && <div style={{ fontSize: 11, color: '#6688aa' }}>{url}</div>}
                  </div>
                  <span style={{
                    fontSize: 10, padding: '2px 8px', borderRadius: 10,
                    background: disabled ? '#1a1a2e' : 'rgba(0,255,136,0.08)',
                    color: disabled ? '#555' : '#00ff88',
                  }}>
                    {disabled ? 'Aus' : 'Aktiv'}
                  </span>
                </div>
              )
            })}
          </div>
        )}

        {/* ── INTEGRATIONEN ── */}
        {tab === 'integrations' && (
          <div style={sx.listContainer}>
            <div style={sx.sectionHeader}>🔗 Verbundene Dienste</div>
            {Object.entries(integrations).map(([key, val]) => {
              const isObj = typeof val === 'object' && val !== null
              const fields = isObj ? Object.entries(val) : []
              const icons = { telegram: '📱', huggingface: '🤗', n8n: '🔗', chrome: '🌐' }
              return (
                <div key={key} style={sx.integrationCard}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                    <span style={{ fontSize: 22 }}>{icons[key] || '🔗'}</span>
                    <span style={{ fontWeight: 700, color: '#e0e0e0', fontSize: 14, textTransform: 'capitalize' }}>
                      {key}
                    </span>
                    <span style={{
                      fontSize: 10, padding: '2px 8px', borderRadius: 10,
                      background: 'rgba(0,255,136,0.08)', color: '#00ff88',
                    }}>Verbunden</span>
                  </div>
                  {fields.map(([fk, fv]) => (
                    <div key={fk} style={{ fontSize: 12, color: '#6688aa', padding: '2px 0' }}>
                      <span style={{ color: '#8899aa' }}>{fk}:</span>{' '}
                      <span style={{ color: '#b0c8e0' }}>
                        {typeof fv === 'boolean' ? (fv ? '✅' : '❌') :
                         typeof fv === 'object' ? JSON.stringify(fv).substring(0, 60) :
                         String(fv).substring(0, 80)}
                      </span>
                    </div>
                  ))}
                </div>
              )
            })}
            {Object.keys(integrations).length === 0 && (
              <div style={sx.emptyState}>Keine Integrationen konfiguriert.</div>
            )}
          </div>
        )}

        {/* ── SKILLS ── */}
        {tab === 'skills' && (
          <div style={sx.listContainer}>
            <div style={sx.sectionHeader}>
              ⚡ Skills ({skills.length})
              {live.skills_dir?.length > 0 && (
                <span style={{ fontSize: 11, color: '#6688aa', marginLeft: 8 }}>
                  Auf Disk: {live.skills_dir.join(', ')}
                </span>
              )}
            </div>
            {skills.map(skill => (
              <div key={skill.id} style={sx.skillCard}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 18 }}>
                    {skill.state === 'active' ? '✅' : skill.state === 'imported' ? '📥' : '🧪'}
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, color: '#e0e0e0' }}>
                      {skill.display_name || skill.skill_name}
                    </div>
                    <div style={{ fontSize: 11, color: '#6688aa' }}>
                      {skill.action_type} • {skill.original_lang || '-'}
                      {skill.compatibility_score != null && (
                        <span> • Kompatibilität: {Math.round(skill.compatibility_score * 100)}%</span>
                      )}
                    </div>
                  </div>
                  {skill.state !== 'active' && (
                    <button onClick={() => handleActivateSkill(skill.skill_name)} style={sx.activateBtn}>
                      Aktivieren
                    </button>
                  )}
                </div>
              </div>
            ))}
            {skills.length === 0 && (
              <div style={sx.emptyState}>Noch keine Skills importiert. Starte eine Migration.</div>
            )}
          </div>
        )}

        {/* ── MEMORY ── */}
        {tab === 'memory' && (
          <div style={sx.listContainer}>
            <div style={sx.sectionHeader}>
              🧠 Memories ({memories.length})
              <button onClick={handleMigration} disabled={migrating} style={{
                ...sx.activateBtn, marginLeft: 12,
              }}>
                {migrating ? '⏳ Migriere…' : '📥 Neue Migration'}
              </button>
            </div>
            {memories.slice(0, 50).map(m => (
              <div key={m.id} style={sx.memoryCard}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span style={{ fontSize: 14 }}>{m.is_integrated ? '✅' : '⏳'}</span>
                  <span style={{ fontSize: 12, color: '#b0c8e0', fontWeight: 500 }}>
                    {m.content_type || 'text'}
                  </span>
                  <span style={{ fontSize: 11, color: '#556677' }}>
                    {m.openclaw_file || m.openclaw_id}
                  </span>
                </div>
                <div style={{
                  fontSize: 12, color: '#6688aa', marginTop: 4,
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>
                  {(m.content || '').substring(0, 120)}
                </div>
              </div>
            ))}
            {memories.length === 0 && (
              <div style={sx.emptyState}>Noch keine Memories migriert.</div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const sx = {
  container: {
    display: 'flex', flexDirection: 'column', height: '100%',
    fontFamily: "'Inter', -apple-system, sans-serif", fontSize: 13, color: '#e0e0e0',
    background: '#0a0a14',
  },
  loadingState: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', height: '100%', color: '#6688aa', gap: 8,
  },
  tabBar: {
    display: 'flex', gap: 2, padding: '8px 12px', borderBottom: '1px solid #1a1a2e',
    background: '#0e0e1a', overflowX: 'auto', flexShrink: 0,
  },
  tab: {
    padding: '6px 12px', borderRadius: 8, border: '1px solid transparent',
    background: 'transparent', color: '#6688aa', cursor: 'pointer',
    fontSize: 12, fontWeight: 500, whiteSpace: 'nowrap', transition: 'all 0.2s',
  },
  tabActive: {
    background: 'rgba(255,100,50,0.1)', color: '#ff8844',
    border: '1px solid rgba(255,100,50,0.25)',
  },
  refreshBtn: {
    padding: '6px 10px', borderRadius: 8, border: '1px solid #1a1a2e',
    background: 'transparent', color: '#6688aa', cursor: 'pointer', fontSize: 14,
  },
  content: { flex: 1, overflow: 'auto', padding: 16 },
  overviewGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
    gap: 12, alignContent: 'start',
  },
  card: {
    background: '#12121e', border: '1px solid #1a1a2e', borderRadius: 12, padding: 16,
  },
  cardTitle: { fontSize: 13, fontWeight: 600, color: '#8899aa', marginBottom: 10 },
  statusRow: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 },
  statusDot: { width: 8, height: 8, borderRadius: '50%', flexShrink: 0 },
  bigNum: { fontSize: 28, fontWeight: 700, color: '#e0e0e0' },
  metaText: { fontSize: 11, color: '#556677', marginTop: 2 },
  agentMini: { display: 'flex', gap: 6, marginTop: 8 },
  k8sNode: {
    display: 'flex', gap: 8, fontSize: 12, padding: '4px 0', borderBottom: '1px solid #1a1a2e',
  },
  agentGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
    gap: 12, alignContent: 'start',
  },
  agentCard: {
    background: '#12121e', border: '1px solid #1a1a2e', borderRadius: 12, padding: 16,
  },
  agentHeader: { display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 },
  agentName: { fontSize: 16, fontWeight: 700, color: '#e0e0e0' },
  agentRole: { fontSize: 12, color: '#ff8844', textTransform: 'uppercase', fontWeight: 600 },
  agentModel: {
    fontSize: 12, color: '#00f5ff', fontFamily: "'JetBrains Mono', monospace",
    padding: '4px 8px', background: 'rgba(0,245,255,0.05)', borderRadius: 6, display: 'inline-block',
  },
  agentTags: { display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 8 },
  skillTag: {
    fontSize: 10, padding: '2px 8px', borderRadius: 10,
    background: 'rgba(255,136,68,0.08)', color: '#ff8844', border: '1px solid rgba(255,136,68,0.15)',
  },
  listContainer: { display: 'flex', flexDirection: 'column', gap: 8 },
  sectionHeader: {
    fontSize: 14, fontWeight: 600, color: '#8899aa', padding: '4px 0',
    marginBottom: 4, display: 'flex', alignItems: 'center',
  },
  cronCard: {
    background: '#12121e', border: '1px solid #1a1a2e', borderRadius: 10, padding: 14,
  },
  cronMeta: { fontSize: 11, color: '#6688aa' },
  addonGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
    gap: 8, alignContent: 'start',
  },
  addonCard: {
    display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px',
    background: '#12121e', border: '1px solid #2a2a40', borderRadius: 10,
  },
  integrationCard: {
    background: '#12121e', border: '1px solid #1a1a2e', borderRadius: 10, padding: 14,
  },
  skillCard: {
    background: '#12121e', border: '1px solid #1a1a2e', borderRadius: 10, padding: 12,
  },
  activateBtn: {
    padding: '5px 14px', borderRadius: 8, border: '1px solid rgba(255,136,68,0.3)',
    background: 'rgba(255,136,68,0.08)', color: '#ff8844',
    fontSize: 12, cursor: 'pointer', fontWeight: 500,
  },
  memoryCard: {
    background: '#12121e', border: '1px solid #1a1a2e', borderRadius: 8, padding: 10,
  },
  emptyState: {
    textAlign: 'center', padding: 40, color: '#556677', fontSize: 13,
  },
}
