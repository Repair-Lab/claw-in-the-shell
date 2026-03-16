import React, { useState, useEffect } from 'react'
import { api } from '../../api'

/**
 * Setup-Wizard v3 — Ersteinrichtung mit vollständiger KI-Provider-Konfiguration
 * 0. Willkommen  1. Sprache  2. Theme  3. KI-Provider & Modelle  4. GitHub  5. Netzwerk  6. Zusammenfassung
 */
export default function SetupWizard({ onComplete }) {
  const [step, setStep] = useState(0)
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)
  const [themes, setThemes] = useState([])
  const [locales, setLocales] = useState([])
  const [scanning, setScanning] = useState(false)
  const [networkDevices, setNetworkDevices] = useState([])
  const [providers, setProviders] = useState([])
  const [scanResults, setScanResults] = useState([])
  const [diskScanning, setDiskScanning] = useState(false)
  const [ocStatus, setOcStatus] = useState(null)
  const [ocChecking, setOcChecking] = useState(false)
  const [ocImporting, setOcImporting] = useState(false)
  const [ocImportResult, setOcImportResult] = useState(null)
  const [providerKeys, setProviderKeys] = useState({}) // { nvidia: { key: '', base: '' }, ... }
  const [testingProvider, setTestingProvider] = useState(null)
  const [aiSubTab, setAiSubTab] = useState('cloud') // cloud | local | openclaw

  const GHOST_AVATARS = [
    { id:'phantom',  icon:'👻', name:'Phantom',   desc:'Vielseitig & anpassbar', color:'#00ffc8', glow:'0 0 40px rgba(0,255,200,0.3)', gradient:'radial-gradient(circle, rgba(0,255,200,0.2), transparent)' },
    { id:'architect', icon:'⚙️', name:'Architect',  desc:'System & Infrastruktur',  color:'#a855f7', glow:'0 0 40px rgba(168,85,247,0.3)', gradient:'radial-gradient(circle, rgba(168,85,247,0.2), transparent)' },
    { id:'oracle',    icon:'🔮', name:'Oracle',     desc:'Wissen & Analyse',        color:'#3b82f6', glow:'0 0 40px rgba(59,130,246,0.3)', gradient:'radial-gradient(circle, rgba(59,130,246,0.2), transparent)' },
    { id:'sentinel',  icon:'🛡️', name:'Sentinel',   desc:'Sicherheit & Schutz',     color:'#ef4444', glow:'0 0 40px rgba(239,68,68,0.3)',  gradient:'radial-gradient(circle, rgba(239,68,68,0.2), transparent)' },
    { id:'muse',      icon:'✨', name:'Muse',       desc:'Kreativ & inspirierend',  color:'#f59e0b', glow:'0 0 40px rgba(245,158,11,0.3)', gradient:'radial-gradient(circle, rgba(245,158,11,0.2), transparent)' },
  ]

  const [settings, setSettings] = useState({
    userName: '', ghostName: 'Ghost', callMe: '', ghostAvatar: 'phantom',
    locale: 'de-DE', timezone: 'Europe/Berlin', theme: 'ghost-dark',
    hostname: 'dbai', defaultModel: '',
    enableTelemetry: true, enableAutoHeal: true, enableGhostSwap: true,
    githubUsername: '', githubToken: '', interests: [],
  })

  useEffect(() => {
    api.themes().then(t => setThemes(t || [])).catch(() => {})
    api.i18nLocales().then(l => setLocales(l || [])).catch(() =>
      setLocales([
        {locale:'de-DE',name:'🇩🇪 Deutsch'},{locale:'en-US',name:'🇺🇸 English'},
        {locale:'fr-FR',name:'🇫🇷 Français'},{locale:'es-ES',name:'🇪🇸 Español'},
        {locale:'ja-JP',name:'🇯🇵 日本語'},{locale:'ko-KR',name:'🇰🇷 한국어'},
        {locale:'zh-CN',name:'🇨🇳 中文'},{locale:'ar-SA',name:'🇸🇦 العربية'},
        {locale:'ru-RU',name:'🇷🇺 Русский'},{locale:'tr-TR',name:'🇹🇷 Türkçe'},
        {locale:'pt-BR',name:'🇧🇷 Português'},{locale:'hi-IN',name:'🇮🇳 हिन्दी'},
      ])
    )
    api.llmProviders().then(p => setProviders(p || [])).catch(() => {})
  }, [])

  const update = (key, value) => setSettings(prev => ({ ...prev, [key]: value }))

  const steps = [
    { icon: '👋', title: 'Willkommen', desc: 'Stell dich vor' },
    { icon: '🌍', title: 'Sprache', desc: 'Sprache und Zeitzone' },
    { icon: '🎨', title: 'Theme', desc: 'Erscheinungsbild' },
    { icon: '🧠', title: 'KI-Konfiguration', desc: 'Provider, Modelle & OpenClaw' },
    { icon: '🐙', title: 'GitHub', desc: 'GitHub verbinden' },
    { icon: '🌐', title: 'Netzwerk', desc: 'Geräte entdecken' },
    { icon: '✅', title: 'Fertig', desc: 'Zusammenfassung' },
  ]

  const interestOptions = [
    {id:'coding',icon:'💻',label:'Programmierung'},{id:'ai_ml',icon:'🤖',label:'KI & ML'},
    {id:'homelab',icon:'🖥️',label:'Homelab'},{id:'iot',icon:'📡',label:'IoT'},
    {id:'gaming',icon:'🎮',label:'Gaming'},{id:'creative',icon:'🎨',label:'Kreativ'},
    {id:'science',icon:'🔬',label:'Wissenschaft'},{id:'robotics',icon:'🦾',label:'Robotik'},
    {id:'security',icon:'🔒',label:'Sicherheit'},{id:'data',icon:'📊',label:'Daten'},
  ]

  const toggleInterest = (id) => {
    setSettings(prev => ({ ...prev, interests: prev.interests.includes(id) ? prev.interests.filter(i => i !== id) : [...prev.interests, id] }))
  }

  // === Provider Helpers ===
  const updateProviderKey = (pk, field, val) => {
    setProviderKeys(prev => ({ ...prev, [pk]: { ...prev[pk], [field]: val } }))
  }

  const handleTestProvider = async (pk) => {
    const kd = providerKeys[pk]
    if (!kd?.key) return
    setTestingProvider(pk)
    try {
      // Erst speichern, dann testen
      await api.llmProviderUpdate(pk, { api_key: kd.key, is_enabled: true, ...(kd.base ? { api_base_url: kd.base } : {}) })
      const r = await api.llmProviderTest(pk)
      setProviders(prev => prev.map(p => p.provider_key === pk ? { ...p, is_configured: true, is_enabled: true, last_test_ok: r.ok, api_key_preview: kd.key.slice(0,6)+'...'+kd.key.slice(-4) } : p))
    } catch {}
    setTestingProvider(null)
  }

  const handleSaveProvider = async (pk) => {
    const kd = providerKeys[pk]
    if (!kd?.key) return
    try {
      await api.llmProviderUpdate(pk, { api_key: kd.key, is_enabled: true, ...(kd.base ? { api_base_url: kd.base } : {}) })
      setProviders(prev => prev.map(p => p.provider_key === pk ? { ...p, is_configured: true, is_enabled: true, api_key_preview: kd.key.slice(0,6)+'...'+kd.key.slice(-4) } : p))
    } catch {}
  }

  const handleToggleProvider = (pk, enabled) => {
    setProviders(prev => prev.map(p => p.provider_key === pk ? { ...p, is_enabled: enabled } : p))
  }

  // === Disk Scan ===
  const handleDiskScan = async () => {
    setDiskScanning(true)
    try {
      const r = await api.llmScanQuick()
      setScanResults(r.models || [])
    } catch { setScanResults([]) }
    setDiskScanning(false)
  }

  const handleIntegrateModel = (m) => {
    setScanResults(prev => prev.filter(x => x.path !== m.path))
    // Will be saved during finish via settings.localModels
    setSettings(prev => ({ ...prev, localModels: [...(prev.localModels || []), m] }))
  }

  // === OpenClaw ===
  const handleCheckOpenClaw = async () => {
    setOcChecking(true)
    try { setOcStatus(await api.openclawStatus()) } catch { setOcStatus({ connected: false }) }
    setOcChecking(false)
  }
  const handleImportOpenClaw = async () => {
    setOcImporting(true)
    try { setOcImportResult(await api.openclawImportToGhost()) } catch (e) { setOcImportResult({ ok: false, error: e.message }) }
    setOcImporting(false)
  }

  // === Network ===
  const handleNetworkScan = async () => {
    setScanning(true)
    try { const r = await api.networkScan(); setNetworkDevices(r.devices || []) } catch { setNetworkDevices([]) }
    setScanning(false)
  }

  // === Finish (Theatralische Installation) ===
  const [installPhase, setInstallPhase] = useState(-1)
  const [installLines, setInstallLines] = useState([])

  const INSTALL_PHASES = [
    { icon: '◆', label: 'SEARCHING FOR SUITABLE SHELL', color: '#00f5ff', lines: [
      'Scanning hardware interfaces…',
      'CPU: detected [COMPATIBLE]',
      'GPU: detected [NEURAL LINK READY]',
      'Memory: mapped [OK]',
    ]},
    { icon: '◆', label: 'CONSTRUCTING RELATIONAL BACKBONE', color: '#a855f7', lines: [
      'Initializing PostgreSQL kernel…',
      'Creating schemas: dbai_core, dbai_llm, dbai_ui…',
      'Seeding system tables…',
      'Row-level security: activated',
    ]},
    { icon: '⟡', label: 'ESTABLISHING NEURAL BRIDGE', color: '#22c55e', lines: [
      'Loading LLM provider config…',
      'Scanning local model registry…',
      'Synaptic pathways: connected',
      'Ghost autonomy: online',
    ]},
    { icon: '⟡', label: `AWAKENING ${settings.ghostName.toUpperCase()}`, color: '#f59e0b', lines: [
      `Personality matrix: ${settings.ghostName}`,
      `Language core: ${settings.locale}`,
      `Interests vector: ${settings.interests.length} dimensions`,
      'Ghost consciousness: initialized',
    ]},
    { icon: '✦', label: 'SYSTEM READY', color: '#00ffc8', lines: [
      `Welcome, ${settings.userName || 'User'}.`,
      `${settings.ghostName} is alive.`,
    ]},
  ]

  const handleFinish = async () => {
    setSaving(true)
    setInstallPhase(0)
    setInstallLines([])

    // Phase-Animation starten
    for (let p = 0; p < INSTALL_PHASES.length; p++) {
      setInstallPhase(p)
      const phase = INSTALL_PHASES[p]
      for (const line of phase.lines) {
        await new Promise(r => setTimeout(r, 180 + Math.random() * 120))
        setInstallLines(prev => [...prev, { text: line, color: phase.color, icon: phase.icon }])
      }
      await new Promise(r => setTimeout(r, 300))

      // Echte Daten bei Phase 1 speichern
      if (p === 1) {
        try {
          const providerConfig = {}
          providers.forEach(prov => {
            const kd = providerKeys[prov.provider_key]
            if (prov.is_configured || prov.is_enabled || kd?.key) {
              providerConfig[prov.provider_key] = {
                enabled: prov.is_enabled,
                api_key: kd?.key || null,
                api_base_url: kd?.base || prov.api_base_url,
              }
            }
          })
          const finalSettings = { ...settings, providers: providerConfig, localModels: settings.localModels || [] }
          await api.setupComplete(finalSettings)
        } catch (err) {
          console.error('Setup save error:', err)
        }
      }
    }

    await new Promise(r => setTimeout(r, 1200))
    setDone(true)
    setTimeout(() => { if (onComplete) onComplete() }, 1500)
    setSaving(false)
  }

  // Theatralische Installations-Anmiation
  if (installPhase >= 0 && !done) {
    const currentPhase = INSTALL_PHASES[Math.min(installPhase, INSTALL_PHASES.length - 1)]
    return (
      <div style={{ display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',height:'100%',background:'#000',fontFamily:'var(--font-mono)',position:'relative',overflow:'hidden' }}>
        {/* Pulsierender Kern */}
        <div style={{ width:80,height:80,borderRadius:'50%',background:`radial-gradient(circle, ${currentPhase.color}33, transparent)`,boxShadow:`0 0 60px ${currentPhase.color}22`,display:'flex',alignItems:'center',justifyContent:'center',marginBottom:24,transition:'all 0.6s ease' }}>
          <span style={{ fontSize:28,color:currentPhase.color,textShadow:`0 0 20px ${currentPhase.color}` }}>👻</span>
        </div>

        {/* Aktuelle Phase */}
        <div style={{ fontSize:13,fontWeight:700,letterSpacing:3,color:currentPhase.color,marginBottom:24,textTransform:'uppercase',textShadow:`0 0 10px ${currentPhase.color}44`,transition:'all 0.4s ease' }}>
          {currentPhase.icon}  {currentPhase.label}…
        </div>

        {/* Log-Zeilen */}
        <div style={{ maxWidth:500,width:'100%',padding:'0 32px',maxHeight:200,overflow:'hidden',maskImage:'linear-gradient(transparent 0%, black 20%)' }}>
          {installLines.map((line, i) => (
            <div key={i} style={{ fontSize:11,lineHeight:1.8,color:line.color,opacity:0.7,animation:'bootFadeIn 0.3s ease',whiteSpace:'nowrap' }}>
              {line.icon}  {line.text}
            </div>
          ))}
        </div>

        {/* Progress */}
        <div style={{ position:'absolute',bottom:0,left:0,right:0,height:2,background:'rgba(255,255,255,0.03)' }}>
          <div style={{ height:'100%',background:`linear-gradient(90deg, ${currentPhase.color}66, ${currentPhase.color})`,width:`${((installPhase + 1) / INSTALL_PHASES.length) * 100}%`,transition:'width 0.4s ease',boxShadow:`0 0 12px ${currentPhase.color}` }} />
        </div>
      </div>
    )
  }

  if (done) {
    return (
      <div style={{ display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',height:'100%',gap:16,fontFamily:'var(--font-sans)',background:'#000' }}>
        <div style={{ width:90,height:90,borderRadius:'50%',background:'radial-gradient(circle, rgba(0,255,204,0.4), transparent)',boxShadow:'0 0 80px rgba(0,255,204,0.2)',display:'flex',alignItems:'center',justifyContent:'center',animation:'corePulse 2s ease-in-out infinite' }}>
          <span style={{ fontSize:36,textShadow:'0 0 20px var(--accent)' }}>👻</span>
        </div>
        <h2 style={{ color:'var(--accent)',margin:0,fontSize:22,fontFamily:'var(--font-display)',letterSpacing:2 }}>Willkommen, {settings.userName || 'User'}</h2>
        <p style={{ color:'var(--text-secondary)',fontSize:13,textAlign:'center',maxWidth:300 }}>
          {settings.ghostName} ist erwacht. Der Desktop wird geladen…
        </p>
        <div style={{ width:200,height:2,background:'var(--border)',borderRadius:2,overflow:'hidden',marginTop:8 }}>
          <div style={{ width:'100%',height:'100%',background:'var(--accent)',animation:'bootFadeIn 0.5s ease' }} />
        </div>
      </div>
    )
  }

  const configuredProviders = providers.filter(p => p.is_configured)
  const enabledLocalModels = settings.localModels || []

  return (
    <div style={{ display:'flex',flexDirection:'column',height:'100%',fontFamily:'var(--font-sans)',fontSize:13 }}>
      {/* Progress */}
      <div style={{ padding:'12px 16px',borderBottom:'1px solid var(--border)',display:'flex',alignItems:'center',gap:4,overflowX:'auto' }}>
        {steps.map((s,i) => (
          <React.Fragment key={i}>
            <div onClick={() => i <= step && setStep(i)} style={{ display:'flex',alignItems:'center',gap:4,cursor:i<=step?'pointer':'default',opacity:i<=step?1:0.35,whiteSpace:'nowrap',transition:'all 0.3s' }}>
              <div style={{ width:26,height:26,borderRadius:'50%',display:'flex',alignItems:'center',justifyContent:'center',fontSize:i<step?11:14,background:i<step?'var(--accent)':i===step?'rgba(0,255,204,0.15)':'var(--bg-elevated)',color:i<step?'var(--bg-primary)':'var(--text-primary)',border:i===step?'2px solid var(--accent)':'1px solid var(--border)',transition:'all 0.3s' }}>
                {i < step ? '✓' : s.icon}
              </div>
              {i === step && <span style={{ fontSize:11,color:'var(--accent)',fontWeight:600 }}>{s.title}</span>}
            </div>
            {i < steps.length - 1 && <div style={{ flex:1,minWidth:12,height:1,background:i<step?'var(--accent)':'var(--border)',transition:'background 0.3s' }} />}
          </React.Fragment>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex:1,overflow:'auto',padding:'24px 32px' }}>
        <h2 style={{ color:'var(--accent)',margin:'0 0 4px',fontSize:20 }}>{steps[step].icon} {steps[step].title}</h2>
        <p style={{ color:'var(--text-secondary)',margin:'0 0 24px',fontSize:13 }}>{steps[step].desc}</p>

        {/* === Step 0: Willkommen === */}
        {step === 0 && (
          <div style={{ display:'flex',flexDirection:'column',gap:20,maxWidth:480 }}>
            <div style={{ padding:20,background:'rgba(0,255,204,0.05)',border:'1px solid rgba(0,255,204,0.2)',borderRadius:12,textAlign:'center' }}>
              <div style={{ fontSize:48,marginBottom:8 }}>👻</div>
              <p style={{ color:'var(--text-primary)',margin:0,fontSize:15 }}>Hi! Ich bin dein persönlicher KI-Assistent.<br/>Lass uns dein System einrichten.</p>
            </div>

            {/* Ghost Avatar-Selector */}
            <div>
              <label style={{ fontSize:12,fontWeight:600,color:'var(--text-primary)',marginBottom:10,display:'block' }}>Ghost-Persönlichkeit wählen</label>
              <div style={{ display:'grid',gridTemplateColumns:'repeat(5, 1fr)',gap:10 }}>
                {GHOST_AVATARS.map(av => {
                  const sel = settings.ghostAvatar === av.id
                  return (
                    <div key={av.id} onClick={() => { update('ghostAvatar', av.id); if (!settings.ghostName || GHOST_AVATARS.some(a => a.name === settings.ghostName)) update('ghostName', av.name) }} style={{ display:'flex',flexDirection:'column',alignItems:'center',gap:8,padding:'16px 8px',borderRadius:12,cursor:'pointer',background:sel ? `rgba(${av.color === '#00ffc8' ? '0,255,200' : av.color === '#a855f7' ? '168,85,247' : av.color === '#3b82f6' ? '59,130,246' : av.color === '#ef4444' ? '239,68,68' : '245,158,11'},0.08)` : 'var(--bg-surface)',border:`2px solid ${sel ? av.color : 'var(--border)'}`,transition:'all 0.3s ease',transform:sel ? 'scale(1.04)' : 'scale(1)' }}>
                      <div style={{ width:52,height:52,borderRadius:'50%',background:av.gradient,boxShadow:sel ? av.glow : 'none',display:'flex',alignItems:'center',justifyContent:'center',transition:'all 0.3s ease' }}>
                        <span style={{ fontSize:24 }}>{av.icon}</span>
                      </div>
                      <div style={{ fontSize:12,fontWeight:600,color:sel ? av.color : 'var(--text-primary)',transition:'color 0.3s' }}>{av.name}</div>
                      <div style={{ fontSize:10,color:'var(--text-secondary)',textAlign:'center' }}>{av.desc}</div>
                    </div>
                  )
                })}
              </div>
            </div>

            <Row label="Dein Name"><input type="text" value={settings.userName} onChange={e => update('userName', e.target.value)} placeholder="z.B. Max" style={inputStyle} autoFocus /></Row>
            <Row label="Wie soll ich dich nennen?"><input type="text" value={settings.callMe} onChange={e => update('callMe', e.target.value)} placeholder="Max, Chef, Boss…" style={inputStyle} /></Row>
            <Row label="Mein Name (Ghost)"><input type="text" value={settings.ghostName} onChange={e => update('ghostName', e.target.value)} placeholder="Ghost, Jarvis, Nova…" style={inputStyle} /></Row>
            <div>
              <label style={{ fontSize:12,fontWeight:600,color:'var(--text-primary)',marginBottom:8,display:'block' }}>Interessen</label>
              <div style={{ display:'flex',flexWrap:'wrap',gap:8 }}>
                {interestOptions.map(opt => (
                  <div key={opt.id} onClick={() => toggleInterest(opt.id)} style={{ padding:'6px 12px',borderRadius:16,cursor:'pointer',fontSize:12,display:'flex',alignItems:'center',gap:4,background:settings.interests.includes(opt.id)?'rgba(0,255,204,0.15)':'var(--bg-surface)',border:`1px solid ${settings.interests.includes(opt.id)?'var(--accent)':'var(--border)'}`,color:settings.interests.includes(opt.id)?'var(--accent)':'var(--text-secondary)',transition:'all 0.2s' }}>
                    {opt.icon} {opt.label}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* === Step 1: Sprache === */}
        {step === 1 && (
          <div style={{ display:'flex',flexDirection:'column',gap:16,maxWidth:450 }}>
            <Row label="Sprache"><select value={settings.locale} onChange={e => update('locale', e.target.value)} style={selectStyle}>{locales.map(l => <option key={l.locale} value={l.locale}>{l.name}</option>)}</select></Row>
            <Row label="Zeitzone"><select value={settings.timezone} onChange={e => update('timezone', e.target.value)} style={selectStyle}>
              {['Europe/Berlin','Europe/London','Europe/Paris','Europe/Moscow','America/New_York','America/Los_Angeles','Asia/Tokyo','Asia/Shanghai','Asia/Kolkata','Asia/Dubai','Australia/Sydney','Pacific/Auckland'].map(tz => <option key={tz} value={tz}>{tz}</option>)}
            </select></Row>
            <Row label="Hostname"><input type="text" value={settings.hostname} onChange={e => update('hostname', e.target.value)} style={inputStyle} /></Row>
          </div>
        )}

        {/* === Step 2: Theme === */}
        {step === 2 && (
          <div style={{ display:'grid',gridTemplateColumns:'repeat(auto-fill, minmax(200px, 1fr))',gap:12 }}>
            {themes.map(t => (
              <div key={t.name} onClick={() => update('theme', t.name)} style={{ padding:16,borderRadius:10,cursor:'pointer',background:settings.theme===t.name?'rgba(0,255,204,0.1)':'var(--bg-surface)',border:`2px solid ${settings.theme===t.name?'var(--accent)':'var(--border)'}`,transition:'all 0.2s' }}>
                <div style={{ fontWeight:600,marginBottom:4 }}>{t.display_name || t.name}</div>
                <div style={{ fontSize:11,color:'var(--text-secondary)' }}>{t.description || ''}</div>
                {t.colors && <div style={{ display:'flex',gap:3,marginTop:8 }}>{Object.values(t.colors).slice(0,6).map((c,i) => <div key={i} style={{ width:18,height:18,borderRadius:4,background:c,border:'1px solid rgba(255,255,255,0.1)' }} />)}</div>}
              </div>
            ))}
          </div>
        )}

        {/* === Step 3: KI-KONFIGURATION (KOMPLETT) === */}
        {step === 3 && (
          <div style={{ maxWidth: 680 }}>
            {/* Sub-Tabs */}
            <div style={{ display:'flex',gap:4,marginBottom:20,borderBottom:'1px solid var(--border)',paddingBottom:8 }}>
              {[{id:'cloud',icon:'☁️',label:'Cloud-Provider'},{id:'local',icon:'💾',label:'Lokale Modelle'},{id:'openclaw',icon:'🐾',label:'OpenClaw'}].map(st => (
                <button key={st.id} onClick={() => setAiSubTab(st.id)} style={{ padding:'6px 14px',borderRadius:6,border:'none',cursor:'pointer',fontSize:12,fontWeight:aiSubTab===st.id?600:400,background:aiSubTab===st.id?'rgba(0,255,204,0.15)':'transparent',color:aiSubTab===st.id?'var(--accent)':'var(--text-secondary)',transition:'all 0.2s' }}>
                  {st.icon} {st.label}
                </button>
              ))}
            </div>

            {/* Cloud Provider */}
            {aiSubTab === 'cloud' && (
              <div>
                <p style={{ fontSize:12,color:'var(--text-secondary)',marginBottom:16 }}>
                  Gib API-Keys für die Provider ein, die du nutzen möchtest. Alle Keys werden verschlüsselt in der Datenbank gespeichert.
                </p>
                <div style={{ display:'flex',flexDirection:'column',gap:8 }}>
                  {providers.filter(p => p.provider_type === 'cloud').map(p => (
                    <ProviderCard key={p.provider_key} provider={p}
                      keyData={providerKeys[p.provider_key] || {}}
                      onUpdateKey={(f,v) => updateProviderKey(p.provider_key, f, v)}
                      onSave={() => handleSaveProvider(p.provider_key)}
                      onTest={() => handleTestProvider(p.provider_key)}
                      onToggle={(v) => handleToggleProvider(p.provider_key, v)}
                      testing={testingProvider === p.provider_key}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Lokale Modelle */}
            {aiSubTab === 'local' && (
              <div>
                <p style={{ fontSize:12,color:'var(--text-secondary)',marginBottom:12 }}>
                  Durchsuche deine Festplatten nach LLM-Modellen (.gguf, .safetensors, .bin). Gefundene Modelle können direkt integriert werden.
                </p>

                {/* Lokale Backends */}
                <h4 style={{ color:'var(--accent)',fontSize:12,marginBottom:8 }}>Lokale Inference-Server</h4>
                <div style={{ display:'flex',flexDirection:'column',gap:6,marginBottom:16 }}>
                  {providers.filter(p => p.provider_type === 'local').map(p => (
                    <div key={p.provider_key} style={{ display:'flex',alignItems:'center',justifyContent:'space-between',padding:'8px 12px',background:'var(--bg-surface)',borderRadius:6,border:'1px solid var(--border)' }}>
                      <div style={{ display:'flex',alignItems:'center',gap:8 }}>
                        <span style={{ fontSize:16 }}>{p.icon}</span>
                        <div>
                          <div style={{ fontWeight:600,fontSize:12 }}>{p.display_name}</div>
                          <div style={{ fontSize:10,color:'var(--text-secondary)' }}>{p.description}</div>
                        </div>
                      </div>
                      <Toggle value={p.is_enabled} onChange={v => handleToggleProvider(p.provider_key, v)} />
                    </div>
                  ))}
                </div>

                {/* Disk Scan */}
                <h4 style={{ color:'var(--accent)',fontSize:12,marginBottom:8 }}>Festplatten-Scan</h4>
                <button onClick={handleDiskScan} disabled={diskScanning} style={{ ...btnPrimary, marginBottom:12 }}>
                  {diskScanning ? '⏳ Scanne Festplatten…' : '🔍 Nach LLM-Modellen suchen'}
                </button>

                {scanResults.length > 0 && (
                  <div style={{ padding:12,background:'rgba(0,255,204,0.04)',border:'1px solid rgba(0,255,204,0.15)',borderRadius:8,marginBottom:12 }}>
                    <div style={{ fontWeight:600,fontSize:12,color:'var(--accent)',marginBottom:8 }}>🔍 {scanResults.length} Modelle gefunden</div>
                    {scanResults.map((m,i) => (
                      <div key={i} style={{ display:'flex',justifyContent:'space-between',alignItems:'center',padding:'6px 10px',borderRadius:6,marginBottom:4,background:'var(--bg-surface)',border:'1px solid var(--border)' }}>
                        <div>
                          <div style={{ fontWeight:600,fontSize:12 }}>{m.name_guess || m.filename}</div>
                          <div style={{ fontSize:10,color:'var(--text-secondary)',fontFamily:'var(--font-mono)' }}>{m.size_display} • {m.format} • {m.path}</div>
                        </div>
                        <button onClick={() => handleIntegrateModel(m)} style={btnSmall}>➕</button>
                      </div>
                    ))}
                  </div>
                )}

                {enabledLocalModels.length > 0 && (
                  <div>
                    <div style={{ fontSize:11,color:'var(--text-secondary)',marginBottom:4 }}>✅ {enabledLocalModels.length} Modelle zum Integrieren vorgemerkt</div>
                    {enabledLocalModels.map((m,i) => (
                      <div key={i} style={{ padding:'4px 10px',fontSize:11,color:'var(--accent)',background:'rgba(0,255,204,0.05)',border:'1px solid rgba(0,255,204,0.15)',borderRadius:4,marginBottom:2 }}>
                        {m.name_guess || m.filename} — {m.size_display}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* OpenClaw */}
            {aiSubTab === 'openclaw' && (
              <div style={{ maxWidth:500 }}>
                <div style={{ padding:16,background:'var(--bg-surface)',border:'1px solid var(--border)',borderRadius:10,display:'flex',alignItems:'center',gap:12,marginBottom:16 }}>
                  <span style={{ fontSize:32 }}>🐾</span>
                  <div>
                    <div style={{ fontWeight:600,marginBottom:2 }}>OpenClaw Integration</div>
                    <div style={{ fontSize:11,color:'var(--text-secondary)' }}>Falls OpenClaw vorhanden, können wir dessen Agenten und Modelle importieren.</div>
                  </div>
                </div>
                <button onClick={handleCheckOpenClaw} disabled={ocChecking} style={btnPrimary}>
                  {ocChecking ? '⏳ Prüfe…' : '🔍 OpenClaw Status prüfen'}
                </button>
                {ocStatus && (
                  <div style={{ marginTop:12,padding:12,borderRadius:8,background:ocStatus.connected?'rgba(0,255,128,0.08)':'rgba(255,80,80,0.08)',border:`1px solid ${ocStatus.connected?'rgba(0,255,128,0.3)':'rgba(255,80,80,0.3)'}`,fontSize:12 }}>
                    {ocStatus.connected ? (<>
                      <div style={{ color:'#0f8',fontWeight:600 }}>✅ OpenClaw verbunden</div>
                      <div style={{ marginTop:6,color:'var(--text-secondary)' }}>Gateway: {ocStatus.gateway_url || '—'} • Agenten: {ocStatus.agents_total || 0}</div>
                      {!ocImportResult && <button onClick={handleImportOpenClaw} disabled={ocImporting} style={{ ...btnSmall,marginTop:8 }}>{ocImporting ? '⏳…' : '📥 Importieren'}</button>}
                      {ocImportResult?.ok && <div style={{ marginTop:8,color:'#0f8' }}>✅ {ocImportResult.total_models} Modelle + {ocImportResult.total_agents} Agenten</div>}
                    </>) : <div style={{ color:'#f55' }}>❌ OpenClaw nicht erreichbar</div>}
                  </div>
                )}
              </div>
            )}

            {/* Ghost-Autonomie (immer sichtbar unten) */}
            <div style={{ marginTop:24,paddingTop:16,borderTop:'1px solid var(--border)' }}>
              <h4 style={{ color:'var(--accent)',fontSize:12,marginBottom:10 }}>Ghost-Autonomie</h4>
              <ToggleRow label="Auto Ghost-Swap" hint="Modell je nach Aufgabe wechseln" value={settings.enableGhostSwap} onChange={v => update('enableGhostSwap', v)} />
              <ToggleRow label="Self-Healing" hint="Automatische Reparatur" value={settings.enableAutoHeal} onChange={v => update('enableAutoHeal', v)} />
              <ToggleRow label="Telemetrie (lokal)" hint="Hardware-Metriken sammeln" value={settings.enableTelemetry} onChange={v => update('enableTelemetry', v)} />
            </div>

            {/* Status-Zusammenfassung */}
            <div style={{ marginTop:16,padding:12,background:'var(--bg-surface)',borderRadius:8,border:'1px solid var(--border)',fontSize:11,color:'var(--text-secondary)' }}>
              ☁️ {configuredProviders.length} Provider konfiguriert
              {enabledLocalModels.length > 0 && ` • 💾 ${enabledLocalModels.length} lokale Modelle`}
              {ocImportResult?.ok && ` • 🐾 OpenClaw importiert`}
            </div>
          </div>
        )}

        {/* === Step 4: GitHub === */}
        {step === 4 && (
          <div style={{ display:'flex',flexDirection:'column',gap:20,maxWidth:500 }}>
            <div style={{ padding:16,background:'var(--bg-surface)',border:'1px solid var(--border)',borderRadius:10,display:'flex',alignItems:'center',gap:12 }}>
              <span style={{ fontSize:32 }}>🐙</span>
              <div>
                <div style={{ fontWeight:600,marginBottom:2 }}>GitHub verbinden</div>
                <div style={{ fontSize:11,color:'var(--text-secondary)' }}>Optional: Software-Installation, Code-Review, Backups.</div>
              </div>
            </div>
            <Row label="GitHub Benutzername"><input type="text" value={settings.githubUsername} onChange={e => update('githubUsername', e.target.value)} placeholder="octocat" style={inputStyle} /></Row>
            <Row label="Personal Access Token"><input type="password" value={settings.githubToken} onChange={e => update('githubToken', e.target.value)} placeholder="ghp_..." style={inputStyle} /><span style={{ fontSize:10,color:'var(--text-secondary)' }}>Verschlüsselt gespeichert.</span></Row>
            <Hint>Du kannst dies später in den Einstellungen konfigurieren.</Hint>
          </div>
        )}

        {/* === Step 5: Netzwerk === */}
        {step === 5 && (
          <div style={{ display:'flex',flexDirection:'column',gap:16 }}>
            <div style={{ padding:16,background:'var(--bg-surface)',border:'1px solid var(--border)',borderRadius:10,display:'flex',alignItems:'center',gap:12 }}>
              <span style={{ fontSize:32 }}>🌐</span>
              <div>
                <div style={{ fontWeight:600,marginBottom:2 }}>Netzwerk-Geräte entdecken</div>
                <div style={{ fontSize:11,color:'var(--text-secondary)' }}>Router, NAS, Drucker, Smart Home, Roboter…</div>
              </div>
            </div>
            <button onClick={handleNetworkScan} disabled={scanning} style={btnPrimary}>
              {scanning ? '📡 Scanne…' : '🔍 Netzwerk-Scan starten'}
            </button>
            {networkDevices.length > 0 && (
              <div style={{ overflowX:'auto' }}>
                <table style={{ width:'100%',borderCollapse:'collapse',fontSize:12 }}>
                  <thead><tr style={{ borderBottom:'1px solid var(--border)' }}><th style={thStyle}>Typ</th><th style={thStyle}>IP</th><th style={thStyle}>Name</th><th style={thStyle}>Port</th></tr></thead>
                  <tbody>{networkDevices.map((d,i) => (
                    <tr key={i} style={{ borderBottom:'1px solid var(--border)' }}>
                      <td style={tdStyle}>{typeIcons[d.device_type]||'🔗'}</td>
                      <td style={{ ...tdStyle,fontFamily:'var(--font-mono)' }}>{d.ip}</td>
                      <td style={tdStyle}>{d.title||d.hostname||'—'}</td>
                      <td style={{ ...tdStyle,fontFamily:'var(--font-mono)' }}>{d.port}</td>
                    </tr>
                  ))}</tbody>
                </table>
                <div style={{ fontSize:11,color:'var(--text-secondary)',marginTop:8 }}>{networkDevices.length} Geräte gefunden.</div>
              </div>
            )}
            {!scanning && networkDevices.length===0 && <Hint>Du kannst den Scan auch später durchführen.</Hint>}
          </div>
        )}

        {/* === Step 6: Zusammenfassung === */}
        {step === 6 && (
          <div style={{ maxWidth:600 }}>
            <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:20 }}>
              <SCard icon="👤" label="Name" value={settings.userName || '—'} />
              <SCard icon="👻" label="Ghost" value={settings.ghostName} />
              <SCard icon="🌍" label="Sprache" value={locales.find(l => l.locale === settings.locale)?.name || settings.locale} />
              <SCard icon="🕐" label="Zeitzone" value={settings.timezone} />
              <SCard icon="🎨" label="Theme" value={settings.theme} />
              <SCard icon="☁️" label="KI-Provider" value={`${configuredProviders.length} aktiv`} />
              <SCard icon="💾" label="Lokale Modelle" value={`${enabledLocalModels.length} integriert`} />
              <SCard icon="🐙" label="GitHub" value={settings.githubUsername || 'Nicht verbunden'} />
              <SCard icon="🐾" label="OpenClaw" value={ocImportResult?.ok ? `${ocImportResult.total_agents} Agenten` : 'Nicht verbunden'} />
              <SCard icon="🌐" label="Netzwerk" value={`${networkDevices.length} Geräte`} />
            </div>
            <div style={{ padding:16,background:'rgba(0,255,204,0.06)',border:'1px solid rgba(0,255,204,0.2)',borderRadius:10,textAlign:'center' }}>
              <div style={{ fontSize:24,marginBottom:6 }}>🚀</div>
              <div style={{ fontWeight:600,color:'var(--accent)' }}>Alles bereit!</div>
              <div style={{ fontSize:12,color:'var(--text-secondary)',marginTop:4 }}>Setup abschließen um {settings.ghostName} zu aktivieren.</div>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div style={{ padding:'12px 20px',borderTop:'1px solid var(--border)',display:'flex',justifyContent:'space-between',alignItems:'center' }}>
        <button onClick={() => setStep(Math.max(0, step - 1))} disabled={step===0} style={{ ...btnStyle,background:'transparent',border:'1px solid var(--border)',color:step===0?'var(--text-secondary)':'var(--text-primary)',cursor:step===0?'default':'pointer' }}>← Zurück</button>
        <span style={{ fontSize:11,color:'var(--text-secondary)' }}>{step + 1} / {steps.length}</span>
        {step < steps.length - 1 ? (
          <button onClick={() => setStep(step + 1)} style={{ ...btnStyle,background:'rgba(0,255,204,0.15)',border:'1px solid var(--accent)',color:'var(--accent)',fontWeight:600 }}>Weiter →</button>
        ) : (
          <button onClick={handleFinish} disabled={saving} style={{ ...btnStyle,background:saving?'var(--bg-elevated)':'var(--accent)',border:'1px solid var(--accent)',color:saving?'var(--text-secondary)':'var(--bg-primary)',fontWeight:600 }}>{saving ? '⏳ Speichere…' : '✅ Setup abschließen'}</button>
        )}
      </div>
    </div>
  )
}

// ─── Provider Card (für Step 3) ───
function ProviderCard({ provider: p, keyData, onUpdateKey, onSave, onTest, onToggle, testing }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ padding:12,background:'var(--bg-surface)',borderRadius:8,border:`1px solid ${p.is_configured?'var(--accent)':'var(--border)'}` }}>
      <div style={{ display:'flex',justifyContent:'space-between',alignItems:'center' }}>
        <div style={{ display:'flex',alignItems:'center',gap:8 }}>
          <span style={{ fontSize:18 }}>{p.icon}</span>
          <div>
            <div style={{ fontWeight:600,fontSize:12 }}>{p.display_name}</div>
            <div style={{ fontSize:10,color:'var(--text-secondary)' }}>{p.pricing_info}</div>
          </div>
        </div>
        <div style={{ display:'flex',alignItems:'center',gap:6 }}>
          {p.is_configured && <span style={{ fontSize:10,color:p.last_test_ok?'#0f8':'var(--text-secondary)',fontFamily:'var(--font-mono)' }}>{p.api_key_preview || '✓'}</span>}
          <Toggle value={p.is_enabled} onChange={onToggle} />
        </div>
      </div>
      <div style={{ display:'flex',gap:4,marginTop:6,flexWrap:'wrap' }}>
        {p.supports_chat && <Badge label="Chat" />}
        {p.supports_vision && <Badge label="Vision" />}
        {p.supports_embedding && <Badge label="Embedding" />}
        {p.supports_tools && <Badge label="Tools" />}
        {p.docs_url && <a href={p.docs_url} target="_blank" rel="noreferrer" style={{ fontSize:9,color:'var(--accent)',textDecoration:'none' }}>📖 Docs</a>}
      </div>
      <div style={{ marginTop:6 }}>
        <button onClick={() => setOpen(!open)} style={btnSmall}>{open ? '✕' : '🔑'} API-Key</button>
        {p.is_configured && <button onClick={onTest} disabled={testing} style={{ ...btnSmall,marginLeft:4 }}>{testing ? '⏳' : '🧪'}</button>}
      </div>
      {open && (
        <div style={{ marginTop:8,padding:10,background:'var(--bg-primary)',borderRadius:6,border:'1px solid var(--border)' }}>
          <input type="password" value={keyData.key || ''} onChange={e => onUpdateKey('key', e.target.value)} placeholder={p.api_key_preview || 'API-Key eingeben…'} style={{ ...inputStyle,marginBottom:6 }} />
          <input type="text" value={keyData.base || ''} onChange={e => onUpdateKey('base', e.target.value)} placeholder={p.api_base_url || 'Base URL (optional)'} style={{ ...inputStyle,marginBottom:6 }} />
          <button onClick={() => { onSave(); setOpen(false) }} style={{ padding:'4px 12px',borderRadius:4,border:'none',background:'var(--accent)',color:'var(--bg-primary)',fontSize:11,cursor:'pointer',fontWeight:600 }}>💾 Speichern</button>
        </div>
      )}
    </div>
  )
}

// ─── Hilfs-Komponenten ───
function Row({ label, children }) {
  return <div style={{ display:'flex',flexDirection:'column',gap:6 }}><label style={{ fontSize:12,fontWeight:600,color:'var(--text-primary)' }}>{label}</label><div style={{ display:'flex',alignItems:'center',gap:8 }}>{children}</div></div>
}
function Toggle({ value, onChange }) {
  return <div onClick={() => onChange(!value)} style={{ width:40,height:22,borderRadius:11,cursor:'pointer',background:value?'var(--accent)':'var(--bg-elevated)',border:`1px solid ${value?'var(--accent)':'var(--border)'}`,position:'relative',transition:'all 0.2s',flexShrink:0 }}><div style={{ width:16,height:16,borderRadius:'50%',background:value?'var(--bg-primary)':'var(--text-secondary)',position:'absolute',top:2,left:value?20:2,transition:'left 0.2s' }}/></div>
}
function ToggleRow({ label, hint, value, onChange }) {
  return <div style={{ display:'flex',alignItems:'center',justifyContent:'space-between',padding:'8px 12px',marginBottom:4,background:'var(--bg-surface)',borderRadius:6,border:'1px solid var(--border)' }}><div><div style={{ fontWeight:600,fontSize:12 }}>{label}</div>{hint && <div style={{ fontSize:10,color:'var(--text-secondary)' }}>{hint}</div>}</div><Toggle value={value} onChange={onChange} /></div>
}
function SCard({ icon, label, value }) {
  return <div style={{ padding:12,background:'var(--bg-surface)',border:'1px solid var(--border)',borderRadius:8 }}><div style={{ fontSize:11,color:'var(--text-secondary)',marginBottom:3 }}>{icon} {label}</div><div style={{ fontSize:13,fontWeight:600,color:'var(--text-primary)',fontFamily:'var(--font-mono)',wordBreak:'break-all' }}>{value}</div></div>
}
function Badge({ label }) {
  return <span style={{ fontSize:9,padding:'1px 5px',borderRadius:3,background:'rgba(0,255,204,0.08)',color:'var(--accent)',border:'1px solid rgba(0,255,204,0.15)' }}>{label}</span>
}
function Hint({ children }) {
  return <div style={{ padding:12,background:'rgba(255,204,0,0.08)',border:'1px solid rgba(255,204,0,0.2)',borderRadius:8,fontSize:12,color:'var(--text-secondary)' }}>💡 {children}</div>
}

const typeIcons = { nas:'💾',router:'🌐',printer:'🖨️',camera:'📷',smarthome:'🏠',robot:'🤖',server:'🖥️',ai:'🧠',media:'🎬',dns:'🛡️',iot:'📡',phone:'📱',unknown:'🔗' }
const btnStyle = { padding:'8px 20px',borderRadius:'var(--radius, 6px)',cursor:'pointer',fontSize:13,border:'none' }
const btnPrimary = { ...btnStyle, background:'rgba(0,255,204,0.1)',border:'1px solid var(--accent)',color:'var(--accent)' }
const btnSmall = { padding:'3px 8px',borderRadius:4,border:'1px solid var(--border)',background:'var(--bg-elevated)',color:'var(--text-primary)',fontSize:10,cursor:'pointer' }
const selectStyle = { padding:'8px 12px',background:'var(--bg-surface)',border:'1px solid var(--border)',borderRadius:'var(--radius, 6px)',color:'var(--text-primary)',fontSize:13,flex:1 }
const inputStyle = { padding:'8px 12px',background:'var(--bg-surface)',border:'1px solid var(--border)',borderRadius:'var(--radius, 6px)',color:'var(--text-primary)',fontSize:13,fontFamily:'var(--font-mono)',flex:1,width:'100%',boxSizing:'border-box' }
const thStyle = { padding:'8px 10px',textAlign:'left',color:'var(--text-secondary)',fontSize:11,fontWeight:600 }
const tdStyle = { padding:'8px 10px',color:'var(--text-primary)' }
