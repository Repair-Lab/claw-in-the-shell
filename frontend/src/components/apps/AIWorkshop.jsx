import React, { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

/**
 * KI Werkstatt — Eigene KI-Datenbanken bauen
 * 
 * Funktionen:
 * - Projekte erstellen & verwalten (Foto-DB, Video-Archiv, Wissens-DB, Smart-Home)
 * - Medien importieren (Bilder, Videos, Audio, Texte, PDFs)
 * - KI-gestützte Analyse (Auto-Tags, Beschreibungen, Transkription)
 * - Sammlungen & Smart-Collections
 * - Smart-Home-Integration (Alexa, Google Home, HomeAssistant)
 * - KI-Chat über eigene Datenbank
 * - Vorlagen für schnellen Start
 */
export default function AIWorkshop({ windowId }) {
  // ── Settings ──
  const { settings: appSettings, schema: appSchema, update: updateSetting, reset: resetSettings } = useAppSettings('ai-workshop')
  const [showSettings, setShowSettings] = useState(false)
  // ── State ──
  const [view, setView] = useState('projects')  // projects, create, detail, import, devices, chat, templates
  const [projects, setProjects] = useState([])
  const [templates, setTemplates] = useState([])
  const [currentProject, setCurrentProject] = useState(null)
  const [mediaItems, setMediaItems] = useState([])
  const [collections, setCollections] = useState([])
  const [devices, setDevices] = useState([])
  const [chatMessages, setChatMessages] = useState([])
  const [importJobs, setImportJobs] = useState([])
  const [customTables, setCustomTables] = useState([])
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState({})
  const [llmStatus, setLlmStatus] = useState(null)
  const [mlModels, setMlModels] = useState(null)
  const [errorMsg, setErrorMsg] = useState(null)

  // ── Laden ──
  const loadProjects = useCallback(async () => {
    try {
      const data = await api.workshopProjects()
      setProjects(data || [])
    } catch (err) {
      console.error('Projekte laden:', err)
      setProjects([])
    }
  }, [])

  const loadTemplates = useCallback(async () => {
    try {
      const data = await api.workshopTemplates()
      setTemplates(data || [])
    } catch (err) {
      console.error('Vorlagen laden:', err)
      setTemplates([])
    }
  }, [])

  const loadStats = useCallback(async () => {
    try {
      const data = await api.workshopStats()
      setStats(data || {})
    } catch (err) {
      setStats({})
    }
  }, [])

  const loadLlmStatus = useCallback(async () => {
    try {
      const data = await api.workshopLlmStatus()
      setLlmStatus(data)
    } catch { setLlmStatus({ has_provider: false, missing: ['LLM-Status konnte nicht geladen werden'] }) }
  }, [])

  const loadMlModels = useCallback(async () => {
    try {
      const data = await api.workshopMlModels()
      setMlModels(data)
    } catch { setMlModels(null) }
  }, [])

  useEffect(() => {
    Promise.all([loadProjects(), loadTemplates(), loadStats(), loadLlmStatus(), loadMlModels()])
      .finally(() => setLoading(false))
  }, [loadProjects, loadTemplates, loadStats, loadLlmStatus, loadMlModels])

  const loadProjectDetail = useCallback(async (projectId) => {
    try {
      const [detail, media, colls, devs, jobs, tables] = await Promise.all([
        api.workshopProject(projectId),
        api.workshopMedia(projectId),
        api.workshopCollections(projectId),
        api.workshopDevices(projectId),
        api.workshopImportJobs(projectId),
        api.workshopCustomTables(projectId),
      ])
      setCurrentProject(detail)
      setMediaItems(media || [])
      setCollections(colls || [])
      setDevices(devs || [])
      setImportJobs(jobs || [])
      setCustomTables(tables || [])
      setView('detail')
    } catch (err) {
      console.error('Projektdetail:', err)
    }
  }, [])

  if (loading) {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.loadingSpinner}>🔬</div>
        <div style={styles.loadingText}>KI Werkstatt wird geladen...</div>
      </div>
    )
  }

  return (
    <div style={styles.container}>
      {/* Sidebar */}
      <div style={styles.sidebar}>
        <div style={styles.sidebarHeader}>
          <span style={styles.sidebarTitle}>🔬 KI Werkstatt</span>
          <button style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: 'var(--text-secondary)' }} onClick={() => setShowSettings(!showSettings)}>⚙️</button>
        </div>
        {showSettings && <div style={{ padding: '0 8px 8px' }}><AppSettingsPanel settings={appSettings} schema={appSchema} onUpdate={updateSetting} onReset={resetSettings} /></div>}
        <nav style={styles.nav}>
          <NavItem icon="🏠" label="Meine Projekte" active={view === 'projects'} onClick={() => setView('projects')} />
          <NavItem icon="✨" label="Neues Projekt" active={view === 'create'} onClick={() => setView('create')} />
          <NavItem icon="📋" label="Vorlagen" active={view === 'templates'} onClick={() => setView('templates')} />
          <NavItem icon="🧠" label="ML & Training" active={view === 'ml-training'} onClick={() => { setView('ml-training'); loadMlModels() }} />
          {currentProject && (
            <>
              <div style={styles.navDivider} />
              <div style={styles.navSectionTitle}>📂 {currentProject.name}</div>
              <NavItem icon="📊" label="Übersicht" active={view === 'detail'} onClick={() => setView('detail')} indent />
              <NavItem icon="📥" label="Importieren" active={view === 'import'} onClick={() => setView('import')} indent />
              <NavItem icon="📁" label="Sammlungen" active={view === 'collections'} onClick={() => setView('collections')} indent />
              <NavItem icon="📱" label="Smart Home" active={view === 'devices'} onClick={() => setView('devices')} indent />
              <NavItem icon="�️" label="Datenbank" active={view === 'custom-tables'} onClick={() => setView('custom-tables')} indent />
              <NavItem icon="�💬" label="KI-Chat" active={view === 'chat'} onClick={() => setView('chat')} indent />
            </>
          )}
        </nav>

        {/* Stats */}
        <div style={styles.sidebarStats}>
          <StatBadge label="Projekte" value={stats.total_projects || projects.length} color="var(--accent)" />
          <StatBadge label="Medien" value={stats.total_items || 0} color="var(--info)" />
          <StatBadge label="Geräte" value={stats.total_devices || 0} color="var(--success)" />
        </div>
      </div>

      {/* Main Content */}
      <div style={styles.main}>
        {/* LLM Status Banner */}
        {llmStatus && !llmStatus.has_provider && (
          <div style={{
            padding: '12px 20px', background: 'rgba(255,170,0,0.08)',
            borderBottom: '1px solid rgba(255,170,0,0.2)', display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <span style={{ fontSize: 20 }}>⚠️</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--warning)' }}>Kein KI-Provider konfiguriert</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                {llmStatus.missing?.join(' • ') || 'KI-Chat, Auto-Tagging und ML-Funktionen benötigen einen LLM-Provider.'}
              </div>
              {llmStatus.recommendations?.map((r, i) => (
                <div key={i} style={{ fontSize: 11, color: 'var(--accent)', marginTop: 2 }}>💡 {r}</div>
              ))}
            </div>
          </div>
        )}

        {/* Error Toast */}
        {errorMsg && (
          <div style={{
            padding: '10px 16px', background: 'rgba(255,68,68,0.1)', borderBottom: '1px solid rgba(255,68,68,0.2)',
            display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--danger)',
          }}>
            <span>❌</span><span style={{ flex: 1 }}>{errorMsg}</span>
            <button onClick={() => setErrorMsg(null)} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>✕</button>
          </div>
        )}
        {view === 'projects' && (
          <ProjectsView
            projects={projects}
            onOpen={loadProjectDetail}
            onCreate={() => setView('create')}
            onRefresh={loadProjects}
            stats={stats}
          />
        )}
        {view === 'create' && (
          <CreateProjectView
            templates={templates}
            onCreated={(p) => { loadProjects(); loadProjectDetail(p.id) }}
            onCancel={() => setView('projects')}
          />
        )}
        {view === 'templates' && (
          <TemplatesView
            templates={templates}
            onUseTemplate={(t) => setView('create')}
          />
        )}
        {view === 'detail' && currentProject && (
          <ProjectDetailView
            project={currentProject}
            mediaItems={mediaItems}
            collections={collections}
            importJobs={importJobs}
            onRefresh={() => loadProjectDetail(currentProject.id)}
            onImport={() => setView('import')}
            onChat={() => setView('chat')}
          />
        )}
        {view === 'import' && currentProject && (
          <ImportView
            project={currentProject}
            importJobs={importJobs}
            onRefresh={() => loadProjectDetail(currentProject.id)}
          />
        )}
        {view === 'collections' && currentProject && (
          <CollectionsView
            project={currentProject}
            collections={collections}
            mediaItems={mediaItems}
            onRefresh={() => loadProjectDetail(currentProject.id)}
          />
        )}
        {view === 'devices' && currentProject && (
          <DevicesView
            project={currentProject}
            devices={devices}
            collections={collections}
            onRefresh={() => loadProjectDetail(currentProject.id)}
          />
        )}
        {view === 'custom-tables' && currentProject && (
          <CustomTablesView
            project={currentProject}
            customTables={customTables}
            onRefresh={() => loadProjectDetail(currentProject.id)}
          />
        )}
        {view === 'chat' && currentProject && (
          <ChatView
            project={currentProject}
            chatMessages={chatMessages}
            setChatMessages={setChatMessages}
            mediaItems={mediaItems}
          />
        )}
        {view === 'ml-training' && (
          <MLTrainingView
            mlModels={mlModels}
            llmStatus={llmStatus}
            onRefresh={loadMlModels}
          />
        )}
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════
   SUB-KOMPONENTEN
   ═══════════════════════════════════════════════════════════════ */

// ── Navigation Item ──
function NavItem({ icon, label, active, onClick, indent }) {
  return (
    <div
      onClick={onClick}
      style={{
        ...styles.navItem,
        paddingLeft: indent ? '28px' : '14px',
        background: active ? 'rgba(0,255,204,0.08)' : 'transparent',
        borderRight: active ? '2px solid var(--accent)' : '2px solid transparent',
        color: active ? 'var(--accent)' : 'var(--text-secondary)',
      }}
    >
      <span>{icon}</span>
      <span>{label}</span>
    </div>
  )
}

// ── Stat Badge ──
function StatBadge({ label, value, color }) {
  return (
    <div style={styles.statBadge}>
      <div style={{ ...styles.statValue, color }}>{value}</div>
      <div style={styles.statLabel}>{label}</div>
    </div>
  )
}

// ═══ PROJECTS VIEW ═══
function ProjectsView({ projects, onOpen, onCreate, onRefresh, stats }) {
  const typeIcons = {
    media_collection: '📸',
    knowledge_base: '📚',
    smart_home: '🏠',
    personal_assistant: '🤖',
    custom: '⚙️',
  }

  const stateColors = {
    draft: 'var(--text-secondary)',
    building: 'var(--warning)',
    ready: 'var(--success)',
    published: 'var(--accent)',
    archived: 'var(--text-secondary)',
  }

  const stateLabels = {
    draft: 'Entwurf',
    building: 'Wird aufgebaut',
    ready: 'Bereit',
    published: 'Veröffentlicht',
    archived: 'Archiviert',
  }

  return (
    <div style={styles.viewContainer}>
      {/* Header */}
      <div style={styles.viewHeader}>
        <div>
          <h2 style={styles.viewTitle}>Meine KI-Datenbanken</h2>
          <p style={styles.viewSubtitle}>
            Erstelle und verwalte deine eigenen KI-gestützten Datenbanken
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={onRefresh} style={styles.btnSecondary}>🔄 Aktualisieren</button>
          <button onClick={onCreate} style={styles.btnPrimary}>✨ Neues Projekt</button>
        </div>
      </div>

      {/* Stats Cards */}
      <div style={styles.statsGrid}>
        <div style={styles.statsCard}>
          <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--accent)' }}>
            {projects.length}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Projekte</div>
        </div>
        <div style={styles.statsCard}>
          <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--info)' }}>
            {stats.total_items || 0}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Medien-Dateien</div>
        </div>
        <div style={styles.statsCard}>
          <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--success)' }}>
            {stats.total_indexed || 0}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>KI-indexiert</div>
        </div>
        <div style={styles.statsCard}>
          <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--warning)' }}>
            {stats.total_devices || 0}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Smart-Home Geräte</div>
        </div>
      </div>

      {/* Projects Grid */}
      {projects.length === 0 ? (
        <div style={styles.emptyState}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>🔬</div>
          <h3 style={{ color: 'var(--text-primary)', marginBottom: '8px' }}>
            Willkommen in der KI Werkstatt!
          </h3>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '16px', maxWidth: '400px' }}>
            Hier kannst du eigene KI-Datenbanken bauen. Sammle Bilder, Videos und Texte —
            die KI hilft dir beim Organisieren und du kannst alles auf deinem Smart-Home nutzen.
          </p>
          <button onClick={onCreate} style={styles.btnPrimary}>✨ Erstes Projekt erstellen</button>
        </div>
      ) : (
        <div style={styles.projectsGrid}>
          {projects.map(p => (
            <div key={p.id} style={styles.projectCard} onClick={() => onOpen(p.id)}>
              <div style={styles.projectCardHeader}>
                <span style={{ fontSize: '24px' }}>{p.icon || typeIcons[p.project_type] || '📦'}</span>
                <span style={{
                  fontSize: '10px', padding: '2px 8px', borderRadius: '10px',
                  background: stateColors[p.state] + '22',
                  color: stateColors[p.state],
                  border: `1px solid ${stateColors[p.state]}44`,
                }}>
                  {stateLabels[p.state] || p.state}
                </span>
              </div>
              <h3 style={styles.projectCardTitle}>{p.name}</h3>
              <p style={styles.projectCardDesc}>{p.description || 'Keine Beschreibung'}</p>
              <div style={styles.projectCardStats}>
                <span>📷 {p.total_items || 0} Dateien</span>
                <span>📁 {p.collection_count || 0} Sammlungen</span>
                {p.smart_home_enabled && <span>📱 Smart-Home</span>}
              </div>
              <div style={styles.projectCardFooter}>
                <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  {typeIcons[p.project_type]} {p.project_type?.replace('_', ' ')}
                </span>
                <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  {p.total_size_mb ? `${p.total_size_mb} MB` : ''}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ═══ CREATE PROJECT VIEW ═══
function CreateProjectView({ templates, onCreated, onCancel }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [projectType, setProjectType] = useState('media_collection')
  const [icon, setIcon] = useState('🧠')
  const [selectedTemplate, setSelectedTemplate] = useState(null)
  const [smartHome, setSmartHome] = useState(false)
  const [aiAutoTag, setAiAutoTag] = useState(true)
  const [aiAutoDescribe, setAiAutoDescribe] = useState(true)
  const [creating, setCreating] = useState(false)
  const [step, setStep] = useState(1)
  const [createError, setCreateError] = useState(null)

  const projectTypes = [
    { id: 'media_collection', icon: '📸', name: 'Medien-Sammlung', desc: 'Fotos, Videos, Audio organisieren' },
    { id: 'knowledge_base', icon: '📚', name: 'Wissens-Datenbank', desc: 'Texte, PDFs, Notizen verknüpfen' },
    { id: 'smart_home', icon: '🏠', name: 'Smart-Home Zentrale', desc: 'Geräte steuern mit KI' },
    { id: 'personal_assistant', icon: '🤖', name: 'Persönlicher Assistent', desc: 'Dein eigener KI-Helfer' },
    { id: 'custom', icon: '⚙️', name: 'Benutzerdefiniert', desc: 'Eigene Konfiguration' },
  ]

  const iconChoices = ['🧠', '📸', '🎬', '🎵', '📚', '🏠', '🤖', '🍳', '💼', '🎮', '🔬', '🌍', '❤️', '⭐', '🚀', '🎨']

  const handleCreate = async () => {
    if (!name.trim()) return
    setCreating(true)
    try {
      const result = await api.workshopCreateProject({
        name: name.trim(),
        description: description.trim(),
        icon,
        project_type: projectType,
        smart_home_enabled: smartHome,
        ai_config: {
          embedding_model: 'all-MiniLM-L6-v2',
          chat_model: 'qwen2.5-7b-instruct',
          auto_tag: aiAutoTag,
          auto_describe: aiAutoDescribe,
          language: 'de',
        },
        template_id: selectedTemplate,
      })
      if (result?.id) onCreated(result)
      else throw new Error('Keine Projekt-ID erhalten')
    } catch (err) {
      console.error('Projekt erstellen:', err)
      // Show inline error instead of alert
      setCreateError(err.message || 'Projekt erstellen fehlgeschlagen')
    }
    setCreating(false)
  }

  return (
    <div style={styles.viewContainer}>
      <div style={styles.viewHeader}>
        <div>
          <h2 style={styles.viewTitle}>✨ Neues KI-Projekt erstellen</h2>
          <p style={styles.viewSubtitle}>Schritt {step} von 3</p>
        </div>
        <button onClick={onCancel} style={styles.btnSecondary}>← Zurück</button>
      </div>

      {/* Progress */}
      <div style={styles.progressBar}>
        <div style={{ ...styles.progressFill, width: `${(step / 3) * 100}%` }} />
      </div>

      {/* Create Error */}
      {createError && (
        <div style={{
          margin: '12px 20px 0', padding: '10px 14px', borderRadius: 8,
          background: 'rgba(255,68,68,0.08)', border: '1px solid rgba(255,68,68,0.25)',
          display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--danger)',
        }}>
          <span>❌</span><span style={{ flex: 1 }}>{createError}</span>
          <button onClick={() => setCreateError(null)} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>✕</button>
        </div>
      )}

      {/* Step 1: Typ wählen */}
      {step === 1 && (
        <div style={{ padding: '20px' }}>
          <h3 style={{ marginBottom: '16px', color: 'var(--text-primary)' }}>
            Was möchtest du bauen?
          </h3>

          {/* Von Vorlage */}
          {templates.filter(t => t.is_featured).length > 0 && (
            <div style={{ marginBottom: '24px' }}>
              <h4 style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
                📋 Schnellstart mit Vorlage
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '10px' }}>
                {templates.filter(t => t.is_featured).map(t => (
                  <div
                    key={t.id}
                    onClick={() => {
                      setSelectedTemplate(t.id)
                      setProjectType(t.project_type)
                      setIcon(t.icon)
                      setName(t.name)
                      setDescription(t.description)
                    }}
                    style={{
                      ...styles.typeCard,
                      borderColor: selectedTemplate === t.id ? 'var(--accent)' : 'var(--border)',
                      background: selectedTemplate === t.id ? 'rgba(0,255,204,0.05)' : 'var(--bg-surface)',
                    }}
                  >
                    <span style={{ fontSize: '24px' }}>{t.icon}</span>
                    <strong style={{ fontSize: '13px' }}>{t.name}</strong>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{t.description}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Oder manuell wählen */}
          <h4 style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
            🔧 Oder wähle einen Projekttyp
          </h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '10px' }}>
            {projectTypes.map(pt => (
              <div
                key={pt.id}
                onClick={() => { setProjectType(pt.id); setIcon(pt.icon); setSelectedTemplate(null) }}
                style={{
                  ...styles.typeCard,
                  borderColor: projectType === pt.id && !selectedTemplate ? 'var(--accent)' : 'var(--border)',
                  background: projectType === pt.id && !selectedTemplate ? 'rgba(0,255,204,0.05)' : 'var(--bg-surface)',
                }}
              >
                <span style={{ fontSize: '24px' }}>{pt.icon}</span>
                <strong style={{ fontSize: '13px' }}>{pt.name}</strong>
                <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{pt.desc}</span>
              </div>
            ))}
          </div>

          <div style={{ marginTop: '20px', textAlign: 'right' }}>
            <button onClick={() => setStep(2)} style={styles.btnPrimary}>Weiter →</button>
          </div>
        </div>
      )}

      {/* Step 2: Details */}
      {step === 2 && (
        <div style={{ padding: '20px' }}>
          <h3 style={{ marginBottom: '16px', color: 'var(--text-primary)' }}>
            Projekt-Details
          </h3>

          <div style={styles.formGroup}>
            <label style={styles.formLabel}>Icon</label>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {iconChoices.map(ic => (
                <div
                  key={ic}
                  onClick={() => setIcon(ic)}
                  style={{
                    width: '36px', height: '36px', display: 'flex', alignItems: 'center',
                    justifyContent: 'center', borderRadius: '8px', cursor: 'pointer',
                    border: icon === ic ? '2px solid var(--accent)' : '1px solid var(--border)',
                    background: icon === ic ? 'rgba(0,255,204,0.1)' : 'var(--bg-surface)',
                    fontSize: '18px',
                  }}
                >{ic}</div>
              ))}
            </div>
          </div>

          <div style={styles.formGroup}>
            <label style={styles.formLabel}>Projektname *</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="z.B. Meine Urlaubsfotos"
              style={styles.formInput}
              autoFocus
            />
          </div>

          <div style={styles.formGroup}>
            <label style={styles.formLabel}>Beschreibung</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Worum geht es in diesem Projekt?"
              style={{ ...styles.formInput, height: '80px', resize: 'vertical' }}
            />
          </div>

          <div style={{ display: 'flex', gap: '8px', marginTop: '20px', justifyContent: 'space-between' }}>
            <button onClick={() => setStep(1)} style={styles.btnSecondary}>← Zurück</button>
            <button onClick={() => name.trim() && setStep(3)} disabled={!name.trim()} style={styles.btnPrimary}>Weiter →</button>
          </div>
        </div>
      )}

      {/* Step 3: KI & Smart-Home */}
      {step === 3 && (
        <div style={{ padding: '20px' }}>
          <h3 style={{ marginBottom: '16px', color: 'var(--text-primary)' }}>
            KI & Smart-Home Einstellungen
          </h3>

          <div style={{ ...styles.formGroup, background: 'var(--bg-surface)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border)' }}>
            <h4 style={{ fontSize: '14px', marginBottom: '12px', color: 'var(--accent)' }}>🤖 KI-Funktionen</h4>
            <ToggleOption
              label="Automatisches Tagging"
              desc="KI erkennt Inhalte und vergibt automatisch Tags"
              checked={aiAutoTag}
              onChange={setAiAutoTag}
            />
            <ToggleOption
              label="Automatische Beschreibungen"
              desc="KI beschreibt den Inhalt jeder Datei"
              checked={aiAutoDescribe}
              onChange={setAiAutoDescribe}
            />
          </div>

          <div style={{ ...styles.formGroup, background: 'var(--bg-surface)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border)', marginTop: '16px' }}>
            <h4 style={{ fontSize: '14px', marginBottom: '12px', color: 'var(--accent)' }}>📱 Smart-Home</h4>
            <ToggleOption
              label="Smart-Home Anbindung aktivieren"
              desc="Verknüpfe mit Alexa, Google Home oder HomeAssistant"
              checked={smartHome}
              onChange={setSmartHome}
            />
            {smartHome && (
              <div style={{ marginTop: '12px', padding: '12px', background: 'rgba(0,255,204,0.05)', borderRadius: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                💡 Du kannst nach dem Erstellen Geräte verbinden und Automatisierungen einrichten.
                Zum Beispiel: Fotos als Diashow auf dem Fernseher, oder Musik über Alexa abspielen.
              </div>
            )}
          </div>

          <div style={{ display: 'flex', gap: '8px', marginTop: '20px', justifyContent: 'space-between' }}>
            <button onClick={() => setStep(2)} style={styles.btnSecondary}>← Zurück</button>
            <button onClick={handleCreate} disabled={creating || !name.trim()} style={styles.btnPrimary}>
              {creating ? '⏳ Erstelle...' : '🚀 Projekt erstellen'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Toggle Option ──
function ToggleOption({ label, desc, checked, onChange }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
      <div>
        <div style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{label}</div>
        {desc && <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>{desc}</div>}
      </div>
      <div
        onClick={() => onChange(!checked)}
        style={{
          width: '40px', height: '22px', borderRadius: '11px', cursor: 'pointer',
          background: checked ? 'var(--accent)' : 'var(--bg-elevated)',
          border: `1px solid ${checked ? 'var(--accent)' : 'var(--border)'}`,
          position: 'relative', transition: 'all 0.2s',
        }}
      >
        <div style={{
          width: '16px', height: '16px', borderRadius: '50%',
          background: checked ? 'var(--bg-primary)' : 'var(--text-secondary)',
          position: 'absolute', top: '2px',
          left: checked ? '20px' : '2px',
          transition: 'all 0.2s',
        }} />
      </div>
    </div>
  )
}

// ═══ TEMPLATES VIEW ═══
function TemplatesView({ templates, onUseTemplate }) {
  return (
    <div style={styles.viewContainer}>
      <div style={styles.viewHeader}>
        <div>
          <h2 style={styles.viewTitle}>📋 Vorlagen</h2>
          <p style={styles.viewSubtitle}>Starte schnell mit einer vorgefertigten Konfiguration</p>
        </div>
      </div>

      <div style={{ padding: '20px', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
        {templates.map(t => (
          <div key={t.id} style={styles.templateCard}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
              <span style={{ fontSize: '32px' }}>{t.icon}</span>
              <div>
                <h3 style={{ fontSize: '15px', color: 'var(--text-primary)', margin: 0 }}>{t.name}</h3>
                <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{t.category}</span>
              </div>
              {t.is_featured && <span style={styles.featuredBadge}>⭐ Empfohlen</span>}
            </div>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '12px' }}>{t.description}</p>
            
            {/* Setup Steps */}
            {t.setup_steps && (
              <div style={{ marginBottom: '12px' }}>
                {(typeof t.setup_steps === 'string' ? JSON.parse(t.setup_steps) : t.setup_steps).map((s, i) => (
                  <div key={i} style={styles.setupStep}>
                    <span style={styles.stepNumber}>{s.step || i + 1}</span>
                    <div>
                      <div style={{ fontSize: '12px', fontWeight: 600 }}>{s.title}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{s.description}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <button onClick={() => onUseTemplate(t)} style={{ ...styles.btnPrimary, width: '100%' }}>
              Diese Vorlage verwenden
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

// ═══ PROJECT DETAIL VIEW ═══
function ProjectDetailView({ project, mediaItems, collections, importJobs, onRefresh, onImport, onChat }) {
  const [tab, setTab] = useState('overview') // overview, media, search
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [mediaFilter, setMediaFilter] = useState('all')

  const handleSearch = async () => {
    if (!searchQuery.trim()) { setSearchResults(null); return }
    try {
      const results = await api.workshopSearch(project.id, searchQuery)
      setSearchResults(results || [])
    } catch (err) {
      console.error('Suche:', err)
    }
  }

  const filteredMedia = mediaItems.filter(m => {
    if (mediaFilter === 'all') return true
    return m.file_type === mediaFilter
  })

  const typeCounts = {}
  mediaItems.forEach(m => { typeCounts[m.file_type] = (typeCounts[m.file_type] || 0) + 1 })

  return (
    <div style={styles.viewContainer}>
      {/* Header */}
      <div style={styles.viewHeader}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '28px' }}>{project.icon}</span>
          <div>
            <h2 style={styles.viewTitle}>{project.name}</h2>
            <p style={styles.viewSubtitle}>{project.description}</p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={onChat} style={styles.btnSecondary}>💬 KI-Chat</button>
          <button onClick={onImport} style={styles.btnPrimary}>📥 Importieren</button>
        </div>
      </div>

      {/* Tabs */}
      <div style={styles.tabBar}>
        {[
          { id: 'overview', icon: '📊', label: 'Übersicht' },
          { id: 'media', icon: '🖼️', label: `Medien (${mediaItems.length})` },
          { id: 'search', icon: '🔍', label: 'KI-Suche' },
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              ...styles.tabButton,
              borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
              color: tab === t.id ? 'var(--accent)' : 'var(--text-secondary)',
            }}
          >{t.icon} {t.label}</button>
        ))}
      </div>

      {/* Overview Tab */}
      {tab === 'overview' && (
        <div style={{ padding: '20px' }}>
          <div style={styles.statsGrid}>
            <div style={styles.statsCard}>
              <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--accent)' }}>
                {project.total_items || 0}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Gesamt-Dateien</div>
            </div>
            <div style={styles.statsCard}>
              <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--info)' }}>
                {project.embedding_count || 0}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>KI-Embeddings</div>
            </div>
            <div style={styles.statsCard}>
              <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--success)' }}>
                {collections.length}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Sammlungen</div>
            </div>
            <div style={styles.statsCard}>
              <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--warning)' }}>
                {project.total_size_mb ? `${project.total_size_mb} MB` : '0 MB'}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Speicher</div>
            </div>
          </div>

          {/* Media Type Distribution */}
          {Object.keys(typeCounts).length > 0 && (
            <div style={{ ...styles.statsCard, marginTop: '16px', padding: '16px' }}>
              <h4 style={{ fontSize: '13px', marginBottom: '12px', color: 'var(--text-primary)' }}>
                Medien-Typen
              </h4>
              <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                {Object.entries(typeCounts).map(([type, count]) => (
                  <div key={type} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>{type === 'image' ? '🖼️' : type === 'video' ? '🎬' : type === 'audio' ? '🎵' : type === 'text' ? '📄' : type === 'pdf' ? '📑' : '📎'}</span>
                    <span style={{ fontSize: '12px' }}>{type}: <strong>{count}</strong></span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent Imports */}
          {importJobs.length > 0 && (
            <div style={{ marginTop: '16px' }}>
              <h4 style={{ fontSize: '13px', marginBottom: '8px', color: 'var(--text-primary)' }}>
                Letzte Import-Aufträge
              </h4>
              {importJobs.slice(0, 5).map(job => (
                <div key={job.id} style={styles.importJobRow}>
                  <span style={{ fontSize: '12px' }}>
                    {job.state === 'complete' ? '✅' : job.state === 'error' ? '❌' : '⏳'}
                  </span>
                  <span style={{ fontSize: '12px', flex: 1 }}>{job.source_path}</span>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                    {job.processed_files}/{job.total_files} Dateien
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Quick Actions */}
          <div style={{ marginTop: '20px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <button onClick={onImport} style={styles.quickAction}>📥 Dateien importieren</button>
            <button onClick={onChat} style={styles.quickAction}>💬 KI fragen</button>
            <button onClick={onRefresh} style={styles.quickAction}>🔄 Aktualisieren</button>
          </div>
        </div>
      )}

      {/* Media Tab */}
      {tab === 'media' && (
        <div style={{ padding: '0' }}>
          {/* Filter Bar */}
          <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--border)', display: 'flex', gap: '8px', alignItems: 'center' }}>
            {['all', 'image', 'video', 'audio', 'text', 'pdf'].map(f => (
              <button
                key={f}
                onClick={() => setMediaFilter(f)}
                style={{
                  ...styles.filterChip,
                  background: mediaFilter === f ? 'rgba(0,255,204,0.1)' : 'transparent',
                  borderColor: mediaFilter === f ? 'var(--accent)' : 'var(--border)',
                  color: mediaFilter === f ? 'var(--accent)' : 'var(--text-secondary)',
                }}
              >
                {f === 'all' ? '📋 Alle' : f === 'image' ? '🖼️ Bilder' : f === 'video' ? '🎬 Videos' :
                 f === 'audio' ? '🎵 Audio' : f === 'text' ? '📄 Texte' : '📑 PDFs'}
                {f !== 'all' && typeCounts[f] ? ` (${typeCounts[f]})` : f === 'all' ? ` (${mediaItems.length})` : ''}
              </button>
            ))}
          </div>

          {/* Media Grid */}
          <div style={styles.mediaGrid}>
            {filteredMedia.length === 0 ? (
              <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
                Keine Dateien in dieser Ansicht. Importiere zuerst Medien.
              </div>
            ) : filteredMedia.map(item => (
              <MediaCard key={item.id} item={item} />
            ))}
          </div>
        </div>
      )}

      {/* Search Tab */}
      {tab === 'search' && (
        <div style={{ padding: '20px' }}>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
            <input
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              placeholder="Suche mit natürlicher Sprache... z.B. 'Fotos vom Strand im Sommer'"
              style={{ ...styles.formInput, flex: 1 }}
            />
            <button onClick={handleSearch} style={styles.btnPrimary}>🔍 Suchen</button>
          </div>

          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
            💡 Die KI versteht natürliche Sprache. Frage nach Inhalten, Stimmungen, Orten oder Zeiträumen.
          </div>

          {searchResults && (
            <div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
                {searchResults.length} Ergebnis(se) für "{searchQuery}"
              </div>
              <div style={styles.mediaGrid}>
                {searchResults.map(item => <MediaCard key={item.id} item={item} />)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Media Card ──
function MediaCard({ item }) {
  const [expanded, setExpanded] = useState(false)

  const typeIcons = { image: '🖼️', video: '🎬', audio: '🎵', text: '📄', pdf: '📑', document: '📎', url: '🔗' }
  const stateColors = { pending: 'var(--warning)', processing: 'var(--info)', indexed: 'var(--success)', error: 'var(--danger)' }

  return (
    <div style={styles.mediaCard} onClick={() => setExpanded(!expanded)}>
      {/* Thumbnail/Icon */}
      <div style={styles.mediaThumbnail}>
        <span style={{ fontSize: '28px' }}>{typeIcons[item.file_type] || '📎'}</span>
      </div>

      {/* Info */}
      <div style={{ padding: '10px' }}>
        <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {item.title || item.file_name}
        </div>
        
        {/* Tags */}
        {(item.ai_tags?.length > 0 || item.tags?.length > 0) && (
          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '4px' }}>
            {(item.ai_tags || item.tags || []).slice(0, 3).map((tag, i) => (
              <span key={i} style={styles.tag}>{tag}</span>
            ))}
          </div>
        )}

        {/* Status */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '10px', color: stateColors[item.state] || 'var(--text-secondary)' }}>
            {item.state === 'indexed' ? '✅ Indexiert' : item.state === 'processing' ? '⏳ Verarbeite...' :
             item.state === 'error' ? '❌ Fehler' : '⏸️ Wartend'}
          </span>
          <span style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
            {item.file_type}
          </span>
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div style={styles.mediaExpanded}>
          {item.ai_description && (
            <div style={styles.mediaDetail}>
              <strong>🤖 KI-Beschreibung:</strong> {item.ai_description}
            </div>
          )}
          {item.ai_caption && (
            <div style={styles.mediaDetail}>
              <strong>📝 Untertitel:</strong> {item.ai_caption}
            </div>
          )}
          {item.width && item.height && (
            <div style={styles.mediaDetail}>
              <strong>📐 Größe:</strong> {item.width}×{item.height}
            </div>
          )}
          {item.duration_sec && (
            <div style={styles.mediaDetail}>
              <strong>⏱️ Dauer:</strong> {Math.floor(item.duration_sec / 60)}:{String(Math.floor(item.duration_sec % 60)).padStart(2, '0')}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ═══ IMPORT VIEW ═══
function ImportView({ project, importJobs, onRefresh }) {
  const [sourceType, setSourceType] = useState('local_folder')
  const [sourcePath, setSourcePath] = useState('')
  const [importing, setImporting] = useState(false)

  const sourceTypes = [
    { id: 'local_folder', icon: '📁', name: 'Lokaler Ordner', desc: 'Ordner auf dem Server' },
    { id: 'url', icon: '🔗', name: 'URL / Webseite', desc: 'Bilder/Texte von einer URL laden' },
    { id: 'google_photos', icon: '📸', name: 'Google Photos', desc: 'Aus Google Photos importieren' },
    { id: 'nas', icon: '🗄️', name: 'NAS / Netzwerk', desc: 'Von Synology, QNAP etc.' },
    { id: 'dropbox', icon: '☁️', name: 'Cloud-Speicher', desc: 'Dropbox, OneDrive, etc.' },
    { id: 'usb', icon: '💾', name: 'USB / SD-Karte', desc: 'Von externem Speicher' },
  ]

  const handleStartImport = async () => {
    if (!sourcePath.trim()) return
    setImporting(true)
    try {
      await api.workshopStartImport(project.id, {
        source_type: sourceType,
        source_path: sourcePath,
      })
      setSourcePath('')
      setTimeout(onRefresh, 1000)
    } catch (err) {
      alert('Import fehlgeschlagen: ' + err.message)
    }
    setImporting(false)
  }

  return (
    <div style={styles.viewContainer}>
      <div style={styles.viewHeader}>
        <div>
          <h2 style={styles.viewTitle}>📥 Dateien importieren</h2>
          <p style={styles.viewSubtitle}>in: {project.icon} {project.name}</p>
        </div>
      </div>

      <div style={{ padding: '20px' }}>
        {/* Quelle wählen */}
        <h3 style={{ fontSize: '14px', marginBottom: '12px', color: 'var(--text-primary)' }}>
          1. Import-Quelle wählen
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '10px', marginBottom: '20px' }}>
          {sourceTypes.map(st => (
            <div
              key={st.id}
              onClick={() => setSourceType(st.id)}
              style={{
                ...styles.typeCard,
                borderColor: sourceType === st.id ? 'var(--accent)' : 'var(--border)',
                background: sourceType === st.id ? 'rgba(0,255,204,0.05)' : 'var(--bg-surface)',
                padding: '12px',
              }}
            >
              <span style={{ fontSize: '20px' }}>{st.icon}</span>
              <strong style={{ fontSize: '12px' }}>{st.name}</strong>
              <span style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>{st.desc}</span>
            </div>
          ))}
        </div>

        {/* Pfad eingeben */}
        <h3 style={{ fontSize: '14px', marginBottom: '12px', color: 'var(--text-primary)' }}>
          2. {sourceType === 'url' ? 'URL eingeben' : sourceType === 'local_folder' ? 'Ordnerpfad eingeben' : 'Verbindung konfigurieren'}
        </h3>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
          <input
            value={sourcePath}
            onChange={e => setSourcePath(e.target.value)}
            placeholder={sourceType === 'url' ? 'https://example.com/gallery' : sourceType === 'local_folder' ? '/home/user/Bilder' : 'Pfad oder Verbindungsstring'}
            style={{ ...styles.formInput, flex: 1 }}
          />
          <button
            onClick={handleStartImport}
            disabled={importing || !sourcePath.trim()}
            style={styles.btnPrimary}
          >
            {importing ? '⏳' : '🚀'} Import starten
          </button>
        </div>

        {/* Tip */}
        <div style={styles.tipBox}>
          💡 <strong>Tipp:</strong> Die KI analysiert alle importierten Dateien automatisch — 
          Bilder werden mit Tags versehen, Videos transkribiert und Texte indexiert. 
          Du kannst danach alles per natürlicher Sprache durchsuchen.
        </div>

        {/* Import History */}
        {importJobs.length > 0 && (
          <div style={{ marginTop: '24px' }}>
            <h3 style={{ fontSize: '14px', marginBottom: '12px', color: 'var(--text-primary)' }}>
              Import-Verlauf
            </h3>
            {importJobs.map(job => (
              <div key={job.id} style={styles.importJobCard}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '13px', fontWeight: 600 }}>
                    {job.state === 'complete' ? '✅' : job.state === 'error' ? '❌' : '⏳'} {job.source_path}
                  </span>
                  <span style={styles.importState(job.state)}>{job.state}</span>
                </div>
                {job.total_files > 0 && (
                  <div style={{ marginBottom: '6px' }}>
                    <div style={styles.importProgressBar}>
                      <div style={{
                        ...styles.importProgressFill,
                        width: `${(job.processed_files / job.total_files) * 100}%`,
                      }} />
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                      {job.processed_files} / {job.total_files} verarbeitet
                      {job.failed_files > 0 && <span style={{ color: 'var(--danger)' }}> · {job.failed_files} fehlgeschlagen</span>}
                    </div>
                  </div>
                )}
                {job.error_message && (
                  <div style={{ fontSize: '11px', color: 'var(--danger)', marginTop: '4px' }}>
                    ❌ {job.error_message}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ═══ COLLECTIONS VIEW ═══
function CollectionsView({ project, collections, mediaItems, onRefresh }) {
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [newType, setNewType] = useState('album')
  const [creating, setCreating] = useState(false)

  const handleCreateCollection = async () => {
    if (!newName.trim()) return
    setCreating(true)
    try {
      await api.workshopCreateCollection(project.id, {
        name: newName,
        description: newDesc,
        collection_type: newType,
      })
      setNewName('')
      setNewDesc('')
      setShowCreate(false)
      onRefresh()
    } catch (err) {
      alert(err.message)
    }
    setCreating(false)
  }

  const collectionTypes = {
    album: { icon: '📷', label: 'Album' },
    playlist: { icon: '🎵', label: 'Playlist' },
    folder: { icon: '📁', label: 'Ordner' },
    smart_collection: { icon: '🔮', label: 'Smart-Sammlung' },
    favorites: { icon: '⭐', label: 'Favoriten' },
  }

  return (
    <div style={styles.viewContainer}>
      <div style={styles.viewHeader}>
        <div>
          <h2 style={styles.viewTitle}>📁 Sammlungen</h2>
          <p style={styles.viewSubtitle}>{collections.length} Sammlungen in {project.name}</p>
        </div>
        <button onClick={() => setShowCreate(true)} style={styles.btnPrimary}>➕ Neue Sammlung</button>
      </div>

      <div style={{ padding: '20px' }}>
        {/* Create Form */}
        {showCreate && (
          <div style={{ ...styles.statsCard, marginBottom: '20px', padding: '16px' }}>
            <h4 style={{ marginBottom: '12px', color: 'var(--accent)' }}>Neue Sammlung erstellen</h4>
            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Name</label>
              <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="z.B. Urlaub 2025" style={styles.formInput} />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Beschreibung</label>
              <input value={newDesc} onChange={e => setNewDesc(e.target.value)} placeholder="Optional" style={styles.formInput} />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Typ</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                {Object.entries(collectionTypes).map(([id, ct]) => (
                  <button
                    key={id}
                    onClick={() => setNewType(id)}
                    style={{
                      ...styles.filterChip,
                      borderColor: newType === id ? 'var(--accent)' : 'var(--border)',
                      color: newType === id ? 'var(--accent)' : 'var(--text-secondary)',
                      background: newType === id ? 'rgba(0,255,204,0.1)' : 'transparent',
                    }}
                  >{ct.icon} {ct.label}</button>
                ))}
              </div>
            </div>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button onClick={() => setShowCreate(false)} style={styles.btnSecondary}>Abbrechen</button>
              <button onClick={handleCreateCollection} disabled={creating || !newName.trim()} style={styles.btnPrimary}>
                {creating ? '⏳' : '✅'} Erstellen
              </button>
            </div>
          </div>
        )}

        {/* Collections Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '12px' }}>
          {collections.map(coll => (
            <div key={coll.id} style={styles.collectionCard}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                <span style={{ fontSize: '24px' }}>{collectionTypes[coll.collection_type]?.icon || '📁'}</span>
                <div>
                  <div style={{ fontSize: '14px', fontWeight: 600 }}>{coll.name}</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                    {collectionTypes[coll.collection_type]?.label || coll.collection_type}
                  </div>
                </div>
              </div>
              {coll.description && (
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '0 0 8px' }}>{coll.description}</p>
              )}
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                {coll.item_count || 0} Elemente
              </div>
            </div>
          ))}

          {collections.length === 0 && !showCreate && (
            <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
              Noch keine Sammlungen. Erstelle eine, um deine Medien zu organisieren.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ═══ DEVICES VIEW ═══
function DevicesView({ project, devices, collections, onRefresh }) {
  const [showAdd, setShowAdd] = useState(false)
  const [deviceName, setDeviceName] = useState('')
  const [deviceType, setDeviceType] = useState('tv')
  const [platform, setPlatform] = useState('alexa')
  const [ipAddress, setIpAddress] = useState('')
  const [adding, setAdding] = useState(false)

  const platforms = [
    { id: 'alexa', icon: '🔵', name: 'Amazon Alexa', desc: 'Echo, Fire TV, etc.' },
    { id: 'google_home', icon: '🔴', name: 'Google Home', desc: 'Nest, Chromecast, etc.' },
    { id: 'homeassistant', icon: '🏠', name: 'HomeAssistant', desc: 'Open-Source Smart-Home' },
    { id: 'apple_homekit', icon: '🍎', name: 'Apple HomeKit', desc: 'Siri, HomePod, Apple TV' },
    { id: 'mqtt', icon: '📡', name: 'MQTT', desc: 'IoT-Protokoll direkt' },
    { id: 'custom', icon: '⚙️', name: 'Benutzerdefiniert', desc: 'API / Webhook' },
  ]

  const deviceTypes = [
    { id: 'tv', icon: '📺', name: 'Fernseher / Display' },
    { id: 'speaker', icon: '🔊', name: 'Lautsprecher' },
    { id: 'display', icon: '🖼️', name: 'Smart Display' },
    { id: 'light', icon: '💡', name: 'Beleuchtung' },
    { id: 'switch', icon: '🔌', name: 'Schalter' },
    { id: 'other', icon: '📱', name: 'Sonstiges' },
  ]

  const handleAddDevice = async () => {
    if (!deviceName.trim()) return
    setAdding(true)
    try {
      await api.workshopAddDevice(project.id, {
        device_name: deviceName,
        device_type: deviceType,
        platform: platform,
        ip_address: ipAddress || null,
      })
      setDeviceName('')
      setIpAddress('')
      setShowAdd(false)
      onRefresh()
    } catch (err) {
      alert(err.message)
    }
    setAdding(false)
  }

  return (
    <div style={styles.viewContainer}>
      <div style={styles.viewHeader}>
        <div>
          <h2 style={styles.viewTitle}>📱 Smart-Home Geräte</h2>
          <p style={styles.viewSubtitle}>Verbinde deine Geräte mit deiner KI-Datenbank</p>
        </div>
        <button onClick={() => setShowAdd(true)} style={styles.btnPrimary}>➕ Gerät hinzufügen</button>
      </div>

      <div style={{ padding: '20px' }}>
        {/* Info Box */}
        <div style={styles.tipBox}>
          📺 <strong>So funktioniert's:</strong> Verbinde deine Smart-Home-Geräte, um deine Medien darauf anzuzeigen.
          Zum Beispiel: Fotos als Diashow auf dem Fernseher, Musik über Alexa abspielen, oder Rezepte vorlesen lassen.
        </div>

        {/* Add Device Form */}
        {showAdd && (
          <div style={{ ...styles.statsCard, marginTop: '16px', marginBottom: '16px', padding: '16px' }}>
            <h4 style={{ marginBottom: '12px', color: 'var(--accent)' }}>Neues Gerät verbinden</h4>
            
            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Plattform</label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                {platforms.map(p => (
                  <div
                    key={p.id}
                    onClick={() => setPlatform(p.id)}
                    style={{
                      ...styles.typeCard,
                      padding: '10px',
                      borderColor: platform === p.id ? 'var(--accent)' : 'var(--border)',
                      background: platform === p.id ? 'rgba(0,255,204,0.05)' : 'var(--bg-surface)',
                    }}
                  >
                    <span>{p.icon}</span>
                    <strong style={{ fontSize: '11px' }}>{p.name}</strong>
                  </div>
                ))}
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Gerätetyp</label>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {deviceTypes.map(dt => (
                  <button
                    key={dt.id}
                    onClick={() => setDeviceType(dt.id)}
                    style={{
                      ...styles.filterChip,
                      borderColor: deviceType === dt.id ? 'var(--accent)' : 'var(--border)',
                      color: deviceType === dt.id ? 'var(--accent)' : 'var(--text-secondary)',
                      background: deviceType === dt.id ? 'rgba(0,255,204,0.1)' : 'transparent',
                    }}
                  >{dt.icon} {dt.name}</button>
                ))}
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Gerätename *</label>
              <input value={deviceName} onChange={e => setDeviceName(e.target.value)} placeholder="z.B. Wohnzimmer TV" style={styles.formInput} />
            </div>

            <div style={styles.formGroup}>
              <label style={styles.formLabel}>IP-Adresse (optional)</label>
              <input value={ipAddress} onChange={e => setIpAddress(e.target.value)} placeholder="z.B. 192.168.1.100" style={styles.formInput} />
            </div>

            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button onClick={() => setShowAdd(false)} style={styles.btnSecondary}>Abbrechen</button>
              <button onClick={handleAddDevice} disabled={adding || !deviceName.trim()} style={styles.btnPrimary}>
                {adding ? '⏳' : '🔗'} Verbinden
              </button>
            </div>
          </div>
        )}

        {/* Devices List */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '12px', marginTop: '16px' }}>
          {devices.map(dev => (
            <div key={dev.id} style={styles.deviceCard}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '28px' }}>
                  {dev.device_type === 'tv' ? '📺' : dev.device_type === 'speaker' ? '🔊' :
                   dev.device_type === 'display' ? '🖼️' : dev.device_type === 'light' ? '💡' : '📱'}
                </span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '14px', fontWeight: 600 }}>{dev.device_name}</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                    {platforms.find(p => p.id === dev.platform)?.name || dev.platform}
                    {dev.ip_address && ` · ${dev.ip_address}`}
                  </div>
                </div>
                <div style={{
                  width: '10px', height: '10px', borderRadius: '50%',
                  background: dev.is_connected ? 'var(--success)' : 'var(--danger)',
                }} />
              </div>

              {/* Capabilities */}
              {dev.capabilities && Object.keys(dev.capabilities).length > 0 && (
                <div style={{ marginTop: '10px', display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                  {Object.entries(dev.capabilities).filter(([,v]) => v).map(([k]) => (
                    <span key={k} style={{ ...styles.tag, fontSize: '10px' }}>
                      {k === 'display_images' ? '🖼️' : k === 'play_video' ? '🎬' : 
                       k === 'play_audio' ? '🎵' : k === 'tts' ? '🗣️' : '⚙️'} {k.replace('_', ' ')}
                    </span>
                  ))}
                </div>
              )}

              {/* Quick Actions */}
              <div style={{ marginTop: '10px', display: 'flex', gap: '6px' }}>
                <button style={{ ...styles.filterChip, fontSize: '10px' }}>🔄 Testen</button>
                <button style={{ ...styles.filterChip, fontSize: '10px' }}>📷 Diashow</button>
                <button style={{ ...styles.filterChip, fontSize: '10px' }}>⚙️ Regeln</button>
              </div>
            </div>
          ))}

          {devices.length === 0 && !showAdd && (
            <div style={{ gridColumn: '1 / -1', ...styles.emptyState }}>
              <div style={{ fontSize: '36px', marginBottom: '12px' }}>📱</div>
              <h3 style={{ color: 'var(--text-primary)', fontSize: '14px', marginBottom: '8px' }}>
                Noch keine Geräte verbunden
              </h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginBottom: '16px', maxWidth: '360px' }}>
                Verbinde Alexa, Google Home, deinen Fernseher oder andere Smart-Home-Geräte, 
                um deine KI-Datenbank überall nutzen zu können.
              </p>
              <button onClick={() => setShowAdd(true)} style={styles.btnPrimary}>➕ Erstes Gerät verbinden</button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ═══ CUSTOM TABLES VIEW (Benutzerdefinierte Datenbanken) ═══
function CustomTablesView({ project, customTables, onRefresh }) {
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [newCols, setNewCols] = useState([{ name: '', type: 'text', required: false }])
  const [activeTable, setActiveTable] = useState(null)
  const [rows, setRows] = useState([])
  const [editRow, setEditRow] = useState(null) // {data} or null for new

  const COL_TYPES = ['text', 'number', 'boolean', 'date', 'url', 'email', 'select', 'tags']

  const loadRows = useCallback(async (tid) => {
    try { setRows(await api.workshopCustomRows(project.id, tid) || []) }
    catch { setRows([]) }
  }, [project.id])

  const openTable = (t) => { setActiveTable(t); loadRows(t.id); setEditRow(null) }

  const createTable = async () => {
    const cols = newCols.filter(c => c.name.trim())
    if (!newName.trim() || cols.length === 0) return
    await api.workshopCreateCustomTable(project.id, { table_name: newName, description: newDesc, columns: cols })
    setCreating(false); setNewName(''); setNewDesc(''); setNewCols([{ name: '', type: 'text', required: false }])
    onRefresh()
  }

  const deleteTable = async (tid) => {
    if (!confirm('Tabelle und alle Daten löschen?')) return
    await api.workshopDeleteCustomTable(project.id, tid)
    if (activeTable?.id === tid) { setActiveTable(null); setRows([]) }
    onRefresh()
  }

  const saveRow = async (data) => {
    if (editRow?.id) await api.workshopUpdateCustomRow(project.id, activeTable.id, editRow.id, data)
    else await api.workshopAddCustomRow(project.id, activeTable.id, data)
    setEditRow(null); loadRows(activeTable.id)
  }

  const deleteRow = async (rid) => {
    await api.workshopDeleteCustomRow(project.id, activeTable.id, rid)
    loadRows(activeTable.id)
  }

  const S = {
    wrap: { display: 'flex', height: '100%', gap: 0 },
    sidebar: { width: 260, borderRight: '1px solid var(--border)', padding: 16, overflowY: 'auto', background: 'var(--bg-secondary)' },
    main: { flex: 1, padding: 20, overflowY: 'auto' },
    tableItem: (a) => ({ padding: '10px 12px', borderRadius: 8, cursor: 'pointer', marginBottom: 4, background: a ? 'rgba(0,255,204,0.1)' : 'transparent', border: a ? '1px solid var(--accent)' : '1px solid transparent', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }),
    input: { width: '100%', padding: '8px 10px', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-primary)', fontSize: 13, outline: 'none', boxSizing: 'border-box' },
    btn: (c) => ({ padding: '6px 14px', background: c || 'var(--accent)', color: c === 'transparent' ? 'var(--text-secondary)' : '#111', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 12, fontWeight: 600 }),
    delBtn: { background: 'none', border: 'none', color: 'var(--error)', cursor: 'pointer', fontSize: 14, padding: '2px 6px' },
    th: { textAlign: 'left', padding: '8px 10px', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', borderBottom: '2px solid var(--border)' },
    td: { padding: '8px 10px', fontSize: 13, color: 'var(--text-primary)', borderBottom: '1px solid var(--border)' },
  }

  return (
    <div style={S.wrap}>
      {/* Tabellen-Sidebar */}
      <div style={S.sidebar}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>🗄️ Tabellen</span>
          <button onClick={() => setCreating(!creating)} style={S.btn(creating ? '#666' : undefined)}>{creating ? '✕' : '+ Neu'}</button>
        </div>

        {creating && (
          <div style={{ padding: 12, background: 'var(--bg-surface)', borderRadius: 8, marginBottom: 12, border: '1px solid var(--border)' }}>
            <input placeholder="Tabellenname" value={newName} onChange={e => setNewName(e.target.value)} style={{ ...S.input, marginBottom: 6 }} />
            <input placeholder="Beschreibung (optional)" value={newDesc} onChange={e => setNewDesc(e.target.value)} style={{ ...S.input, marginBottom: 8 }} />
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>Spalten:</div>
            {newCols.map((col, i) => (
              <div key={i} style={{ display: 'flex', gap: 4, marginBottom: 4 }}>
                <input placeholder="Name" value={col.name} onChange={e => { const c = [...newCols]; c[i].name = e.target.value; setNewCols(c) }} style={{ ...S.input, flex: 1 }} />
                <select value={col.type} onChange={e => { const c = [...newCols]; c[i].type = e.target.value; setNewCols(c) }} style={{ ...S.input, width: 80 }}>
                  {COL_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
                <button onClick={() => setNewCols(newCols.filter((_, j) => j !== i))} style={S.delBtn}>✕</button>
              </div>
            ))}
            <button onClick={() => setNewCols([...newCols, { name: '', type: 'text', required: false }])} style={{ ...S.btn('transparent'), fontSize: 11, padding: '4px 8px' }}>+ Spalte</button>
            <div style={{ marginTop: 8 }}>
              <button onClick={createTable} style={S.btn()} disabled={!newName.trim()}>Erstellen</button>
            </div>
          </div>
        )}

        {customTables.length === 0 && !creating && (
          <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)', fontSize: 13 }}>Noch keine Tabellen. Klicke "+ Neu".</div>
        )}

        {customTables.map(t => (
          <div key={t.id} style={S.tableItem(activeTable?.id === t.id)} onClick={() => openTable(t)}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>📋 {t.table_name}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{(t.columns || []).length} Spalten · {t.row_count || 0} Zeilen</div>
            </div>
            <button onClick={e => { e.stopPropagation(); deleteTable(t.id) }} style={S.delBtn} title="Löschen">🗑</button>
          </div>
        ))}
      </div>

      {/* Tabellen-Inhalt */}
      <div style={S.main}>
        {!activeTable ? (
          <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>🗄️</div>
            <div style={{ fontSize: 16, fontWeight: 500 }}>Benutzerdefinierte Datenbank</div>
            <div style={{ fontSize: 13, marginTop: 6 }}>Wähle eine Tabelle oder erstelle eine neue.</div>
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 18, color: 'var(--text-primary)' }}>📋 {activeTable.table_name}</h3>
                {activeTable.description && <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>{activeTable.description}</div>}
              </div>
              <button onClick={() => setEditRow({ data: {} })} style={S.btn()}>+ Zeile hinzufügen</button>
            </div>

            {/* Inline Row Editor */}
            {editRow && (
              <RowEditor columns={activeTable.columns || []} row={editRow} onSave={saveRow} onCancel={() => setEditRow(null)} />
            )}

            {/* Daten-Tabelle */}
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {(activeTable.columns || []).map(c => <th key={c.name} style={S.th}>{c.name} <span style={{ opacity: 0.5, fontSize: 10 }}>({c.type})</span></th>)}
                    <th style={{ ...S.th, width: 80 }}>Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(r => (
                    <tr key={r.id}>
                      {(activeTable.columns || []).map(c => (
                        <td key={c.name} style={S.td}>{renderCellValue(r.data?.[c.name], c.type)}</td>
                      ))}
                      <td style={S.td}>
                        <button onClick={() => setEditRow(r)} style={{ ...S.delBtn, color: 'var(--accent)' }} title="Bearbeiten">✏️</button>
                        <button onClick={() => deleteRow(r.id)} style={S.delBtn} title="Löschen">🗑</button>
                      </td>
                    </tr>
                  ))}
                  {rows.length === 0 && (
                    <tr><td colSpan={999} style={{ ...S.td, textAlign: 'center', color: 'var(--text-muted)', padding: 30 }}>Keine Daten. Klicke "+ Zeile hinzufügen".</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ── Hilfskomponenten für Custom Tables ──
function RowEditor({ columns, row, onSave, onCancel }) {
  const [data, setData] = useState(row.data || {})
  const S = {
    wrap: { padding: 14, background: 'var(--bg-surface)', borderRadius: 8, border: '1px solid var(--accent)', marginBottom: 14 },
    input: { width: '100%', padding: '7px 10px', background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-primary)', fontSize: 13, outline: 'none', boxSizing: 'border-box' },
  }
  return (
    <div style={S.wrap}>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(columns.length, 3)}, 1fr)`, gap: 8, marginBottom: 10 }}>
        {columns.map(c => (
          <div key={c.name}>
            <label style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 2, display: 'block' }}>{c.name}</label>
            {c.type === 'boolean' ? (
              <select value={data[c.name] || ''} onChange={e => setData({ ...data, [c.name]: e.target.value === 'true' })} style={S.input}>
                <option value="">—</option><option value="true">Ja</option><option value="false">Nein</option>
              </select>
            ) : c.type === 'number' ? (
              <input type="number" value={data[c.name] ?? ''} onChange={e => setData({ ...data, [c.name]: parseFloat(e.target.value) || 0 })} style={S.input} />
            ) : c.type === 'date' ? (
              <input type="date" value={data[c.name] || ''} onChange={e => setData({ ...data, [c.name]: e.target.value })} style={S.input} />
            ) : (
              <input value={data[c.name] || ''} onChange={e => setData({ ...data, [c.name]: e.target.value })} style={S.input} placeholder={c.type} />
            )}
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={() => onSave(data)} style={{ padding: '6px 16px', background: 'var(--accent)', color: '#111', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>{row.id ? 'Speichern' : 'Hinzufügen'}</button>
        <button onClick={onCancel} style={{ padding: '6px 16px', background: '#444', color: '#ccc', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 12 }}>Abbrechen</button>
      </div>
    </div>
  )
}

function renderCellValue(val, type) {
  if (val === null || val === undefined) return <span style={{ opacity: 0.3 }}>—</span>
  if (type === 'boolean') return val ? '✅' : '❌'
  if (type === 'url') return <a href={val} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>{val.length > 40 ? val.slice(0, 40) + '…' : val}</a>
  if (type === 'tags' && Array.isArray(val)) return val.map(t => <span key={t} style={{ padding: '2px 6px', background: 'var(--bg-surface)', borderRadius: 4, fontSize: 11, marginRight: 3 }}>{t}</span>)
  return String(val)
}

// ═══ CHAT VIEW ═══
function ChatView({ project, chatMessages, setChatMessages, mediaItems }) {
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const chatEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    // Load chat history
    api.workshopChatHistory(project.id)
      .then(data => setChatMessages(data || []))
      .catch(() => {})
  }, [project.id, setChatMessages])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  const handleSend = async () => {
    if (!input.trim() || sending) return
    const userMsg = input.trim()
    setInput('')
    setSending(true)

    // Add user message optimistically
    setChatMessages(prev => [...prev, { role: 'user', content: userMsg, created_at: new Date().toISOString() }])

    try {
      const result = await api.workshopChat(project.id, userMsg)
      if (result?.response) {
        setChatMessages(prev => [...prev, {
          role: 'assistant',
          content: result.response,
          referenced_items: result.referenced_items || [],
          created_at: new Date().toISOString(),
        }])
      }
    } catch (err) {
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: '❌ Fehler: ' + err.message,
        created_at: new Date().toISOString(),
      }])
    }
    setSending(false)
    inputRef.current?.focus()
  }

  const suggestions = [
    `Zeige mir alle ${project.project_type === 'media_collection' ? 'Fotos' : 'Dokumente'} vom letzten Monat`,
    'Welche Tags kommen am häufigsten vor?',
    'Erstelle eine Zusammenfassung meiner Sammlung',
    'Finde ähnliche Inhalte zu meinem letzten Import',
  ]

  return (
    <div style={styles.chatContainer}>
      {/* Chat Header */}
      <div style={styles.chatHeader}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '20px' }}>💬</span>
          <div>
            <div style={{ fontSize: '14px', fontWeight: 600 }}>KI-Chat</div>
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
              Frage die KI über deine {project.name}-Datenbank
            </div>
          </div>
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
          {mediaItems.length} Dateien im Kontext
        </div>
      </div>

      {/* Messages */}
      <div style={styles.chatMessages}>
        {chatMessages.length === 0 && (
          <div style={{ textAlign: 'center', padding: '30px' }}>
            <div style={{ fontSize: '36px', marginBottom: '12px' }}>🤖</div>
            <h3 style={{ fontSize: '15px', color: 'var(--text-primary)', marginBottom: '8px' }}>
              Frage deine KI-Datenbank!
            </h3>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
              Die KI kennt alle deine importierten Dateien und kann dir Fragen dazu beantworten.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'center' }}>
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => { setInput(s); inputRef.current?.focus() }}
                  style={styles.suggestionChip}
                >{s}</button>
              ))}
            </div>
          </div>
        )}

        {chatMessages.map((msg, i) => (
          <div
            key={i}
            style={{
              ...styles.chatBubble,
              alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
              background: msg.role === 'user' ? 'rgba(0,255,204,0.1)' : 'var(--bg-surface)',
              borderColor: msg.role === 'user' ? 'var(--accent)' : 'var(--border)',
              maxWidth: '75%',
            }}
          >
            <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
              {msg.role === 'user' ? '👤 Du' : '🤖 KI-Assistent'}
            </div>
            <div style={{ fontSize: '13px', whiteSpace: 'pre-wrap' }}>{msg.content}</div>
            {msg.referenced_items?.length > 0 && (
              <div style={{ marginTop: '8px', fontSize: '10px', color: 'var(--text-secondary)' }}>
                📎 {msg.referenced_items.length} Datei(en) referenziert
              </div>
            )}
          </div>
        ))}

        {sending && (
          <div style={{ ...styles.chatBubble, alignSelf: 'flex-start', background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>🤖 Denke nach...</div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input */}
      <div style={styles.chatInputBar}>
        <input
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder={`Frage über ${project.name} stellen...`}
          style={styles.chatInput}
          disabled={sending}
        />
        <button
          onClick={handleSend}
          disabled={sending || !input.trim()}
          style={styles.chatSendBtn}
        >
          {sending ? '⏳' : '📤'}
        </button>
      </div>
    </div>
  )
}


// ═══ ML TRAINING VIEW ═══
function MLTrainingView({ mlModels, llmStatus, onRefresh }) {
  const [tab, setTab] = useState('models')    // models, training, inference, settings
  const [trainingCfg, setTrainingCfg] = useState({
    model: 'all-MiniLM-L6-v2', dataset: '', epochs: 10, batchSize: 32,
    learningRate: 0.001, optimizer: 'adam', scheduler: 'cosine',
    warmupSteps: 100, maxSeqLen: 512, fp16: true, evalSteps: 500,
    saveSteps: 1000, gradAccum: 1, weightDecay: 0.01,
  })
  const [inferenceInput, setInferenceInput] = useState('')
  const [inferenceResult, setInferenceResult] = useState(null)

  const activeModels = mlModels?.active_models || []
  const architectures = mlModels?.available_architectures || []
  const gpu = mlModels?.gpu_available || { available: false }
  const providers = llmStatus?.active_providers || []

  const mlTabs = [
    { id: 'models', label: '🤖 Modelle', desc: 'Aktive & verfügbare Modelle' },
    { id: 'training', label: '🎯 Training', desc: 'Modell trainieren / Fine-Tuning' },
    { id: 'inference', label: '⚡ Inferenz', desc: 'Modell testen & Vorhersagen' },
    { id: 'settings', label: '⚙️ Einstellungen', desc: 'Hyperparameter & Konfiguration' },
  ]

  return (
    <div style={styles.viewContainer}>
      <div style={styles.viewHeader}>
        <div>
          <h2 style={styles.viewTitle}>🧠 Machine Learning & Training</h2>
          <p style={styles.viewSubtitle}>
            {activeModels.length} aktive Modelle •{' '}
            {gpu.available ? `GPU: ${gpu.name} (${gpu.used_mb || 0}/${gpu.total_mb || 0} MB)` : 'CPU-Modus'}
          </p>
        </div>
        <button onClick={onRefresh} style={styles.btnSecondary}>🔄 Aktualisieren</button>
      </div>

      {/* ML Sub-Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)' }}>
        {mlTabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: '10px 20px', border: 'none', background: 'transparent', cursor: 'pointer',
            color: tab === t.id ? 'var(--accent)' : 'var(--text-secondary)', fontSize: 12,
            borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
          }}>
            {t.label}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: 20 }}>
        {/* ── MODELS TAB ── */}
        {tab === 'models' && (
          <div>
            {/* GPU Status Card */}
            <div style={{
              padding: 16, borderRadius: 8, marginBottom: 20,
              background: gpu.available ? 'rgba(0,255,136,0.06)' : 'rgba(255,170,0,0.06)',
              border: `1px solid ${gpu.available ? 'rgba(0,255,136,0.2)' : 'rgba(255,170,0,0.2)'}`,
              display: 'flex', alignItems: 'center', gap: 16,
            }}>
              <span style={{ fontSize: 28 }}>{gpu.available ? '🎮' : '💻'}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, fontSize: 14 }}>
                  {gpu.available ? gpu.name : 'Keine GPU erkannt'}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  {gpu.available
                    ? `VRAM: ${gpu.used_mb} / ${gpu.total_mb} MB belegt • Auslastung: ${gpu.utilization}%`
                    : 'Training läuft auf CPU — langsamer, aber funktionsfähig'}
                </div>
              </div>
              {gpu.available && gpu.total_mb > 0 && (
                <div style={{ width: 80 }}>
                  <div style={{ height: 6, background: 'var(--bg-elevated)', borderRadius: 3 }}>
                    <div style={{
                      height: 6, borderRadius: 3,
                      width: `${Math.min((gpu.used_mb / gpu.total_mb) * 100, 100)}%`,
                      background: gpu.used_mb / gpu.total_mb > 0.9 ? 'var(--danger)' : 'var(--success)',
                    }} />
                  </div>
                  <div style={{ fontSize: 10, textAlign: 'center', marginTop: 2, color: 'var(--text-secondary)' }}>
                    {Math.round((gpu.used_mb / gpu.total_mb) * 100)}%
                  </div>
                </div>
              )}
            </div>

            {/* Active LLM Providers */}
            {providers.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <h3 style={{ fontSize: 14, marginBottom: 10, color: 'var(--text-primary)' }}>☁️ Cloud-Provider</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 10 }}>
                  {providers.map(p => (
                    <div key={p.key} style={{
                      padding: '12px 16px', background: 'var(--bg-surface)', borderRadius: 8,
                      border: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12,
                    }}>
                      <span style={{ fontSize: 24 }}>{p.icon || '🤖'}</span>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, fontSize: 12 }}>{p.name}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'flex', gap: 6, marginTop: 2 }}>
                          {p.chat && <span style={{ color: 'var(--success)' }}>💬 Chat</span>}
                          {p.embedding && <span style={{ color: 'var(--accent)' }}>🔢 Embedding</span>}
                          {p.vision && <span style={{ color: 'var(--info)' }}>👁️ Vision</span>}
                        </div>
                      </div>
                      <span style={{ fontSize: 8, color: p.tested_ok ? 'var(--success)' : 'var(--text-secondary)' }}>●</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Active Local Models */}
            {activeModels.filter(m => m.source === 'local').length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <h3 style={{ fontSize: 14, marginBottom: 10, color: 'var(--text-primary)' }}>🖥️ Lokale Modelle</h3>
                {activeModels.filter(m => m.source === 'local').map((m, i) => (
                  <div key={i} style={{
                    padding: '12px 16px', background: 'var(--bg-surface)', borderRadius: 8,
                    border: '1px solid var(--border)', marginBottom: 6,
                    display: 'flex', alignItems: 'center', gap: 12,
                  }}>
                    <span style={{ fontSize: 20 }}>{m.is_loaded ? '🟢' : '⚪'}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: 12 }}>{m.model_name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                        {m.model_size_mb ? `${m.model_size_mb} MB` : ''} {m.is_loaded ? '• Geladen' : '• Nicht geladen'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Available Architectures */}
            <h3 style={{ fontSize: 14, marginBottom: 10, color: 'var(--text-primary)' }}>📦 Verfügbare Architekturen</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
              {architectures.map((arch, i) => (
                <div key={i} style={{
                  padding: '12px 16px', background: 'var(--bg-surface)', borderRadius: 8,
                  border: '1px solid var(--border)',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 600, fontSize: 12 }}>{arch.name}</span>
                    <span style={{
                      fontSize: 10, padding: '2px 8px', borderRadius: 10,
                      background: 'rgba(0,255,204,0.1)', color: 'var(--accent)', border: '1px solid rgba(0,255,204,0.2)',
                    }}>
                      {arch.type}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>{arch.desc}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }}>
                    💾 {arch.size_mb} MB
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── TRAINING TAB ── */}
        {tab === 'training' && (
          <div>
            <div style={{
              padding: 16, borderRadius: 8, marginBottom: 20,
              background: 'rgba(0,255,204,0.04)', border: '1px solid rgba(0,255,204,0.15)',
            }}>
              <h3 style={{ margin: '0 0 8px', fontSize: 14, color: 'var(--text-primary)' }}>🎯 Training starten</h3>
              <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)' }}>
                Wähle ein Basis-Modell und konfiguriere das Training. Die Daten kommen aus deinen Projekten.
              </p>
            </div>

            {/* Model Selection */}
            <div style={{ marginBottom: 16 }}>
              <label style={mlStyles.label}>Basis-Modell:</label>
              <select value={trainingCfg.model} onChange={e => setTrainingCfg(c => ({ ...c, model: e.target.value }))}
                style={mlStyles.select}>
                {architectures.map(a => (
                  <option key={a.name} value={a.name}>{a.name} ({a.type}, {a.size_mb} MB)</option>
                ))}
              </select>
            </div>

            {/* Dataset */}
            <div style={{ marginBottom: 16 }}>
              <label style={mlStyles.label}>Datensatz (Projekt-ID oder Pfad):</label>
              <input value={trainingCfg.dataset} onChange={e => setTrainingCfg(c => ({ ...c, dataset: e.target.value }))}
                placeholder="z.B. Projekt-ID oder /data/dataset.csv" style={mlStyles.input} />
            </div>

            {/* Grid config */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 16 }}>
              <div>
                <label style={mlStyles.label}>Epochen:</label>
                <input type="number" value={trainingCfg.epochs}
                  onChange={e => setTrainingCfg(c => ({ ...c, epochs: parseInt(e.target.value) || 1 }))}
                  style={mlStyles.input} min={1} max={1000} />
              </div>
              <div>
                <label style={mlStyles.label}>Batch-Größe:</label>
                <input type="number" value={trainingCfg.batchSize}
                  onChange={e => setTrainingCfg(c => ({ ...c, batchSize: parseInt(e.target.value) || 1 }))}
                  style={mlStyles.input} min={1} max={512} />
              </div>
              <div>
                <label style={mlStyles.label}>Lernrate:</label>
                <input type="number" value={trainingCfg.learningRate} step="0.0001"
                  onChange={e => setTrainingCfg(c => ({ ...c, learningRate: parseFloat(e.target.value) || 0.001 }))}
                  style={mlStyles.input} />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
              <div>
                <label style={mlStyles.label}>Optimizer:</label>
                <select value={trainingCfg.optimizer} onChange={e => setTrainingCfg(c => ({ ...c, optimizer: e.target.value }))}
                  style={mlStyles.select}>
                  <option value="adam">Adam</option>
                  <option value="adamw">AdamW</option>
                  <option value="sgd">SGD</option>
                  <option value="adagrad">Adagrad</option>
                  <option value="rmsprop">RMSprop</option>
                </select>
              </div>
              <div>
                <label style={mlStyles.label}>Scheduler:</label>
                <select value={trainingCfg.scheduler} onChange={e => setTrainingCfg(c => ({ ...c, scheduler: e.target.value }))}
                  style={mlStyles.select}>
                  <option value="cosine">Cosine Annealing</option>
                  <option value="linear">Lineare Abnahme</option>
                  <option value="constant">Konstant</option>
                  <option value="polynomial">Polynomial</option>
                </select>
              </div>
            </div>

            {/* Advanced */}
            <details style={{ marginBottom: 16 }}>
              <summary style={{ cursor: 'pointer', fontSize: 12, color: 'var(--accent)', marginBottom: 8 }}>
                ⚙️ Erweiterte Einstellungen
              </summary>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, padding: '12px 0' }}>
                <div>
                  <label style={mlStyles.label}>Warmup-Schritte:</label>
                  <input type="number" value={trainingCfg.warmupSteps}
                    onChange={e => setTrainingCfg(c => ({ ...c, warmupSteps: parseInt(e.target.value) || 0 }))}
                    style={mlStyles.input} />
                </div>
                <div>
                  <label style={mlStyles.label}>Max Sequenzlänge:</label>
                  <input type="number" value={trainingCfg.maxSeqLen}
                    onChange={e => setTrainingCfg(c => ({ ...c, maxSeqLen: parseInt(e.target.value) || 128 }))}
                    style={mlStyles.input} />
                </div>
                <div>
                  <label style={mlStyles.label}>Gradient Accumulation:</label>
                  <input type="number" value={trainingCfg.gradAccum}
                    onChange={e => setTrainingCfg(c => ({ ...c, gradAccum: parseInt(e.target.value) || 1 }))}
                    style={mlStyles.input} />
                </div>
                <div>
                  <label style={mlStyles.label}>Weight Decay:</label>
                  <input type="number" value={trainingCfg.weightDecay} step="0.001"
                    onChange={e => setTrainingCfg(c => ({ ...c, weightDecay: parseFloat(e.target.value) || 0 }))}
                    style={mlStyles.input} />
                </div>
                <div>
                  <label style={mlStyles.label}>Eval Steps:</label>
                  <input type="number" value={trainingCfg.evalSteps}
                    onChange={e => setTrainingCfg(c => ({ ...c, evalSteps: parseInt(e.target.value) || 100 }))}
                    style={mlStyles.input} />
                </div>
                <div>
                  <label style={mlStyles.label}>Save Steps:</label>
                  <input type="number" value={trainingCfg.savSteps}
                    onChange={e => setTrainingCfg(c => ({ ...c, saveSteps: parseInt(e.target.value) || 500 }))}
                    style={mlStyles.input} />
                </div>
              </div>
              <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
                  <input type="checkbox" checked={trainingCfg.fp16}
                    onChange={e => setTrainingCfg(c => ({ ...c, fp16: e.target.checked }))} />
                  FP16 Mixed Precision {gpu.available ? '' : '(benötigt GPU)'}
                </label>
              </div>
            </details>

            {/* Start Training Button */}
            <button style={{
              padding: '12px 28px', background: 'rgba(0,255,204,0.1)', border: '1px solid var(--accent)',
              borderRadius: 8, color: 'var(--accent)', cursor: 'pointer', fontSize: 14, fontWeight: 700,
              width: '100%',
            }}>
              🚀 Training starten
            </button>
            <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 8, textAlign: 'center' }}>
              {gpu.available
                ? `GPU: ${gpu.name} — Beschleunigtes Training verfügbar`
                : 'CPU-Modus — Training möglich, aber langsamer'}
            </p>
          </div>
        )}

        {/* ── INFERENCE TAB ── */}
        {tab === 'inference' && (
          <div>
            <div style={{
              padding: 16, borderRadius: 8, marginBottom: 20,
              background: 'rgba(0,255,204,0.04)', border: '1px solid rgba(0,255,204,0.15)',
            }}>
              <h3 style={{ margin: '0 0 8px', fontSize: 14, color: 'var(--text-primary)' }}>⚡ Modell testen</h3>
              <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)' }}>
                Teste ein geladenes Modell mit deinen Eingaben. Unterstützt Text, Embedding und Klassifikation.
              </p>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={mlStyles.label}>Modell auswählen:</label>
              <select style={mlStyles.select}>
                {activeModels.length > 0
                  ? activeModels.map((m, i) => (
                    <option key={i} value={m.model_name}>{m.model_name} ({m.source})</option>
                  ))
                  : <option>Kein Modell verfügbar</option>
                }
              </select>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={mlStyles.label}>Eingabe:</label>
              <textarea
                value={inferenceInput}
                onChange={e => setInferenceInput(e.target.value)}
                placeholder="Text eingeben zum Testen..."
                style={{ ...mlStyles.input, height: 120, resize: 'vertical', fontFamily: 'var(--font-mono)' }}
              />
            </div>

            <button style={{
              padding: '10px 24px', background: 'rgba(0,255,204,0.1)', border: '1px solid var(--accent)',
              borderRadius: 8, color: 'var(--accent)', cursor: 'pointer', fontSize: 13, fontWeight: 600,
            }}>
              ⚡ Ausführen
            </button>

            {inferenceResult && (
              <div style={{
                marginTop: 16, padding: 16, background: 'var(--bg-surface)',
                border: '1px solid var(--border)', borderRadius: 8,
                fontFamily: 'var(--font-mono)', fontSize: 12, whiteSpace: 'pre-wrap',
              }}>
                {typeof inferenceResult === 'string' ? inferenceResult : JSON.stringify(inferenceResult, null, 2)}
              </div>
            )}
          </div>
        )}

        {/* ── SETTINGS TAB ── */}
        {tab === 'settings' && (
          <div>
            <h3 style={{ fontSize: 14, marginBottom: 16, color: 'var(--text-primary)' }}>⚙️ ML-Konfiguration</h3>

            {/* General Settings */}
            <div style={{
              padding: 16, background: 'var(--bg-surface)', borderRadius: 8,
              border: '1px solid var(--border)', marginBottom: 16,
            }}>
              <h4 style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--text-primary)' }}>Allgemein</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={mlStyles.label}>Standard-Embedding-Modell:</label>
                  <select style={mlStyles.select}>
                    <option value="all-MiniLM-L6-v2">all-MiniLM-L6-v2 (384 Dim.)</option>
                    <option value="bge-small-en">BGE Small EN v1.5</option>
                    <option value="multilingual">Multilingual MiniLM L12</option>
                    <option value="openai">OpenAI text-embedding-3-small</option>
                  </select>
                </div>
                <div>
                  <label style={mlStyles.label}>Standard-Chat-Modell:</label>
                  <select style={mlStyles.select}>
                    {providers.length > 0
                      ? providers.filter(p => p.chat).map(p => (
                        <option key={p.key} value={p.key}>{p.name}</option>
                      ))
                      : <option>Kein Chat-Provider</option>
                    }
                  </select>
                </div>
              </div>
            </div>

            {/* Vector Search */}
            <div style={{
              padding: 16, background: 'var(--bg-surface)', borderRadius: 8,
              border: '1px solid var(--border)', marginBottom: 16,
            }}>
              <h4 style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--text-primary)' }}>🔍 Vektorsuche (pgvector)</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={mlStyles.label}>Distanz-Metrik:</label>
                  <select style={mlStyles.select}>
                    <option value="cosine">Kosinus-Ähnlichkeit</option>
                    <option value="l2">Euklidische Distanz (L2)</option>
                    <option value="inner_product">Inner Product</option>
                  </select>
                </div>
                <div>
                  <label style={mlStyles.label}>Top-K Ergebnisse:</label>
                  <input type="number" defaultValue={10} min={1} max={100} style={mlStyles.input} />
                </div>
              </div>
            </div>

            {/* Auto-Processing */}
            <div style={{
              padding: 16, background: 'var(--bg-surface)', borderRadius: 8,
              border: '1px solid var(--border)', marginBottom: 16,
            }}>
              <h4 style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--text-primary)' }}>🤖 Auto-Verarbeitung</h4>
              {[
                { label: 'Auto-Tagging neuer Medien', desc: 'Automatisch Tags generieren beim Import', defaultChecked: true },
                { label: 'Auto-Beschreibung', desc: 'KI-Beschreibungen für Bilder und Texte', defaultChecked: true },
                { label: 'Duplikat-Erkennung', desc: 'Ähnliche Dateien per Embedding erkennen', defaultChecked: false },
                { label: 'Sprache Auto-Detect', desc: 'Sprache automatisch erkennen', defaultChecked: true },
                { label: 'OCR bei Bildern', desc: 'Text aus Bildern extrahieren', defaultChecked: false },
                { label: 'Audio-Transkription', desc: 'Sprache in Audio/Video automatisch zu Text', defaultChecked: false },
              ].map((opt, i) => (
                <label key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0',
                  borderBottom: '1px solid var(--border)', cursor: 'pointer', fontSize: 12,
                }}>
                  <input type="checkbox" defaultChecked={opt.defaultChecked} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500 }}>{opt.label}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{opt.desc}</div>
                  </div>
                </label>
              ))}
            </div>

            {/* Performance */}
            <div style={{
              padding: 16, background: 'var(--bg-surface)', borderRadius: 8,
              border: '1px solid var(--border)',
            }}>
              <h4 style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--text-primary)' }}>⚡ Performance</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                <div>
                  <label style={mlStyles.label}>Max. Worker-Threads:</label>
                  <input type="number" defaultValue={4} min={1} max={32} style={mlStyles.input} />
                </div>
                <div>
                  <label style={mlStyles.label}>Max. Batch bei Import:</label>
                  <input type="number" defaultValue={50} min={1} max={1000} style={mlStyles.input} />
                </div>
                <div>
                  <label style={mlStyles.label}>Embedding Cache (MB):</label>
                  <input type="number" defaultValue={512} min={64} max={8192} style={mlStyles.input} />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

const mlStyles = {
  label: { display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4, fontWeight: 500 },
  input: {
    width: '100%', padding: '8px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border)',
    borderRadius: 6, color: 'var(--text-primary)', fontSize: 12, boxSizing: 'border-box',
  },
  select: {
    width: '100%', padding: '8px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border)',
    borderRadius: 6, color: 'var(--text-primary)', fontSize: 12, boxSizing: 'border-box',
  },
}


/* ═══════════════════════════════════════════════════════════════
   STYLES
   ═══════════════════════════════════════════════════════════════ */
const styles = {
  container: {
    display: 'flex', height: '100%', fontFamily: 'var(--font-sans)', fontSize: '13px',
    background: 'var(--bg-primary)',
  },

  // ── Sidebar ──
  sidebar: {
    width: '220px', borderRight: '1px solid var(--border)',
    display: 'flex', flexDirection: 'column', background: 'var(--bg-secondary)',
    flexShrink: 0,
  },
  sidebarHeader: {
    padding: '14px 16px', borderBottom: '1px solid var(--border)',
    display: 'flex', alignItems: 'center', gap: '8px',
  },
  sidebarTitle: { fontSize: '14px', fontWeight: 700, color: 'var(--accent)' },
  nav: { flex: 1, overflow: 'auto', padding: '8px 0' },
  navItem: {
    padding: '8px 14px', cursor: 'pointer', display: 'flex', gap: '8px',
    alignItems: 'center', fontSize: '12px', transition: 'all 0.15s',
    borderRight: '2px solid transparent',
  },
  navDivider: { height: '1px', background: 'var(--border)', margin: '8px 14px' },
  navSectionTitle: { fontSize: '11px', color: 'var(--text-secondary)', padding: '4px 14px', fontWeight: 600 },
  sidebarStats: {
    padding: '12px', borderTop: '1px solid var(--border)',
    display: 'flex', justifyContent: 'space-around',
  },
  statBadge: { textAlign: 'center' },
  statValue: { fontSize: '16px', fontWeight: 700 },
  statLabel: { fontSize: '9px', color: 'var(--text-secondary)', textTransform: 'uppercase' },

  // ── Main ──
  main: { flex: 1, overflow: 'auto' },

  // ── View ──
  viewContainer: { height: '100%', display: 'flex', flexDirection: 'column' },
  viewHeader: {
    padding: '16px 20px', borderBottom: '1px solid var(--border)',
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    background: 'var(--bg-secondary)',
  },
  viewTitle: { fontSize: '18px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' },
  viewSubtitle: { fontSize: '12px', color: 'var(--text-secondary)', margin: '2px 0 0' },

  // ── Stats ──
  statsGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px', marginBottom: '16px' },
  statsCard: {
    background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: '8px', padding: '14px', textAlign: 'center',
  },

  // ── Buttons ──
  btnPrimary: {
    padding: '8px 16px', background: 'rgba(0,255,204,0.1)',
    border: '1px solid var(--accent)', borderRadius: 'var(--radius)',
    color: 'var(--accent)', cursor: 'pointer', fontSize: '12px', fontWeight: 600,
    transition: 'all 0.2s',
  },
  btnSecondary: {
    padding: '8px 16px', background: 'transparent',
    border: '1px solid var(--border)', borderRadius: 'var(--radius)',
    color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '12px',
    transition: 'all 0.2s',
  },

  // ── Progress ──
  progressBar: {
    height: '3px', background: 'var(--bg-elevated)', margin: '0',
  },
  progressFill: {
    height: '100%', background: 'var(--accent)', transition: 'width 0.3s ease',
    borderRadius: '0 2px 2px 0',
  },

  // ── Form ──
  formGroup: { marginBottom: '14px' },
  formLabel: { display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px', fontWeight: 600 },
  formInput: {
    width: '100%', padding: '10px 14px',
    background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius)', color: 'var(--text-primary)',
    fontSize: '13px', fontFamily: 'var(--font-sans)', outline: 'none',
  },

  // ── Type Card ──
  typeCard: {
    padding: '14px', borderRadius: '8px', cursor: 'pointer',
    border: '1px solid var(--border)', transition: 'all 0.2s',
    display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'center',
    textAlign: 'center',
  },

  // ── Projects Grid ──
  projectsGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: '14px', padding: '0 20px 20px',
  },
  projectCard: {
    background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: '10px', padding: '16px', cursor: 'pointer',
    transition: 'all 0.2s', borderLeft: '3px solid var(--accent)',
  },
  projectCardHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' },
  projectCardTitle: { fontSize: '15px', fontWeight: 600, margin: '0 0 4px', color: 'var(--text-primary)' },
  projectCardDesc: { fontSize: '12px', color: 'var(--text-secondary)', margin: '0 0 12px' },
  projectCardStats: { display: 'flex', gap: '12px', fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '8px' },
  projectCardFooter: { display: 'flex', justifyContent: 'space-between', paddingTop: '8px', borderTop: '1px solid var(--border)' },

  // ── Empty State ──
  emptyState: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', padding: '50px 20px',
    textAlign: 'center',
  },

  // ── Tabs ──
  tabBar: {
    display: 'flex', borderBottom: '1px solid var(--border)',
    background: 'var(--bg-secondary)',
  },
  tabButton: {
    padding: '10px 20px', border: 'none', background: 'transparent',
    color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '12px',
    borderBottom: '2px solid transparent', transition: 'all 0.2s',
  },

  // ── Filter ──
  filterChip: {
    padding: '5px 12px', border: '1px solid var(--border)',
    borderRadius: '20px', background: 'transparent',
    color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '11px',
    transition: 'all 0.2s',
  },

  // ── Media ──
  mediaGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
    gap: '10px', padding: '16px 20px',
  },
  mediaCard: {
    background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: '8px', overflow: 'hidden', cursor: 'pointer',
    transition: 'all 0.2s',
  },
  mediaThumbnail: {
    height: '80px', background: 'var(--bg-elevated)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  mediaExpanded: { padding: '10px', borderTop: '1px solid var(--border)', background: 'var(--bg-elevated)' },
  mediaDetail: { fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' },

  // ── Tags ──
  tag: {
    padding: '1px 6px', borderRadius: '4px', fontSize: '10px',
    background: 'rgba(0,255,204,0.08)', border: '1px solid rgba(0,255,204,0.2)',
    color: 'var(--accent)',
  },

  // ── Template ──
  templateCard: {
    background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: '10px', padding: '16px',
  },
  featuredBadge: {
    fontSize: '10px', padding: '2px 8px', borderRadius: '10px',
    background: 'rgba(255,170,0,0.1)', color: 'var(--warning)',
    border: '1px solid rgba(255,170,0,0.3)', marginLeft: 'auto',
  },
  setupStep: {
    display: 'flex', gap: '10px', alignItems: 'flex-start',
    padding: '6px 0', fontSize: '12px',
  },
  stepNumber: {
    width: '20px', height: '20px', borderRadius: '50%',
    background: 'var(--accent)', color: 'var(--bg-primary)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: '11px', fontWeight: 700, flexShrink: 0,
  },

  // ── Quick Action ──
  quickAction: {
    padding: '10px 16px', background: 'var(--bg-surface)',
    border: '1px solid var(--border)', borderRadius: '8px',
    color: 'var(--text-primary)', cursor: 'pointer', fontSize: '12px',
    transition: 'all 0.2s',
  },

  // ── Import ──
  importJobRow: {
    display: 'flex', gap: '8px', alignItems: 'center',
    padding: '8px 0', borderBottom: '1px solid var(--border)',
  },
  importJobCard: {
    padding: '12px', background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: '8px', marginBottom: '8px',
  },
  importState: (state) => ({
    fontSize: '10px', padding: '2px 8px', borderRadius: '10px',
    background: state === 'complete' ? 'rgba(0,255,136,0.1)' : state === 'error' ? 'rgba(255,68,68,0.1)' : 'rgba(255,170,0,0.1)',
    color: state === 'complete' ? 'var(--success)' : state === 'error' ? 'var(--danger)' : 'var(--warning)',
  }),
  importProgressBar: {
    height: '4px', background: 'var(--bg-elevated)', borderRadius: '2px',
  },
  importProgressFill: {
    height: '100%', background: 'var(--accent)', borderRadius: '2px',
    transition: 'width 0.3s',
  },

  // ── Tip Box ──
  tipBox: {
    padding: '14px 16px', background: 'rgba(0,255,204,0.04)',
    border: '1px solid rgba(0,255,204,0.15)', borderRadius: '8px',
    fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5,
  },

  // ── Collections ──
  collectionCard: {
    padding: '14px', background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: '8px', cursor: 'pointer', transition: 'all 0.2s',
  },

  // ── Devices ──
  deviceCard: {
    padding: '16px', background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: '10px',
  },

  // ── Chat ──
  chatContainer: { display: 'flex', flexDirection: 'column', height: '100%' },
  chatHeader: {
    padding: '12px 20px', borderBottom: '1px solid var(--border)',
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    background: 'var(--bg-secondary)',
  },
  chatMessages: {
    flex: 1, overflow: 'auto', padding: '16px 20px',
    display: 'flex', flexDirection: 'column', gap: '10px',
  },
  chatBubble: {
    padding: '10px 14px', borderRadius: '10px',
    border: '1px solid var(--border)', maxWidth: '80%',
  },
  chatInputBar: {
    padding: '12px 16px', borderTop: '1px solid var(--border)',
    display: 'flex', gap: '8px', background: 'var(--bg-secondary)',
  },
  chatInput: {
    flex: 1, padding: '10px 14px',
    background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: '20px', color: 'var(--text-primary)',
    fontSize: '13px', fontFamily: 'var(--font-sans)', outline: 'none',
  },
  chatSendBtn: {
    width: '40px', height: '40px', borderRadius: '50%',
    background: 'var(--accent)', border: 'none',
    cursor: 'pointer', fontSize: '16px', display: 'flex',
    alignItems: 'center', justifyContent: 'center',
    color: 'var(--bg-primary)',
  },
  suggestionChip: {
    padding: '8px 16px', background: 'var(--bg-surface)',
    border: '1px solid var(--border)', borderRadius: '20px',
    color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '12px',
    transition: 'all 0.2s', maxWidth: '400px',
  },

  // ── Loading ──
  loadingContainer: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', height: '100%', gap: '12px',
  },
  loadingSpinner: { fontSize: '48px', animation: 'spin 2s linear infinite' },
  loadingText: { fontSize: '14px', color: 'var(--text-secondary)' },
}
