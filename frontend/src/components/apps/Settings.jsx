import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'

/**
 * Settings v2 — Vollständige System-Einstellungen
 * Tabs: Profil, Sprache, Theme, KI-Provider, Modelle, Ghost, Netzwerk, Hardware, Datenbank, Über
 */
export default function Settings({ windowId }) {
  const [tab, setTab] = useState('profile')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)
  const [user, setUser] = useState({})
  const [themes, setThemes] = useState([])
  const [locales, setLocales] = useState([])
  const [providers, setProviders] = useState([])
  const [models, setModels] = useState([])
  const [hardware, setHardware] = useState(null)

  const showToast = (msg, ok = true) => {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 3000)
  }

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [u, t, l, p, m] = await Promise.all([
        api.settingsUser().catch(() => ({})),
        api.themes().catch(() => []),
        api.i18nLocales().catch(() => []),
        api.llmProviders().catch(() => []),
        api.llmModels().catch(() => []),
      ])
      setUser(u || {}); setThemes(t || []); setLocales(l || [])
      setProviders(p || []); setModels(m || [])
    } catch (e) { console.error('Settings laden:', e) }
    setLoading(false)
  }, [])

  useEffect(() => { loadAll() }, [loadAll])

  const loadHardware = async () => {
    if (!hardware) {
      try { setHardware(await api.settingsHardware()) } catch { setHardware({}) }
    }
  }

  const saveUser = async (updates) => {
    setSaving(true)
    try {
      await api.settingsUpdateUser(updates)
      setUser(prev => ({ ...prev, ...updates }))
      showToast('Gespeichert')
    } catch (e) { showToast('Fehler: ' + e.message, false) }
    setSaving(false)
  }

  const tabs = [
    { id: 'profile', icon: '👤', label: 'Profil' },
    { id: 'language', icon: '🌍', label: 'Sprache' },
    { id: 'themes', icon: '🎨', label: 'Themes' },
    { id: 'providers', icon: '☁️', label: 'KI-Provider' },
    { id: 'models', icon: '🧠', label: 'Modelle' },
    { id: 'ghost', icon: '👻', label: 'Ghost' },
    { id: 'network', icon: '🌐', label: 'Netzwerk' },
    { id: 'hardware', icon: '🖥️', label: 'Hardware' },
    { id: 'database', icon: '🗄️', label: 'Datenbank' },
    { id: 'about', icon: 'ℹ️', label: 'Über DBAI' },
  ]

  return (
    <div style={{ display: 'flex', height: '100%', fontFamily: 'var(--font-sans)', fontSize: 13 }}>
      <div style={{ width: 180, borderRight: '1px solid var(--border)', padding: '8px 6px', display: 'flex', flexDirection: 'column', gap: 2, overflowY: 'auto' }}>
        {tabs.map(t => (
          <div key={t.id} onClick={() => { setTab(t.id); if (t.id === 'hardware') loadHardware() }}
            style={{ padding: '7px 10px', cursor: 'pointer', borderRadius: 6, background: tab === t.id ? 'var(--bg-elevated)' : 'transparent', color: tab === t.id ? 'var(--accent)' : 'var(--text-primary)', transition: 'all 0.2s', fontSize: 12.5, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 14 }}>{t.icon}</span> {t.label}
          </div>
        ))}
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '16px 24px', position: 'relative' }}>
        {toast && (
          <div style={{ position: 'fixed', top: 16, right: 24, zIndex: 9999, padding: '8px 16px', borderRadius: 8, fontSize: 12, fontWeight: 600, background: toast.ok ? 'rgba(0,255,128,0.15)' : 'rgba(255,60,60,0.15)', color: toast.ok ? '#0f8' : '#f55', border: `1px solid ${toast.ok ? 'rgba(0,255,128,0.3)' : 'rgba(255,60,60,0.3)'}` }}>
            {toast.ok ? '✅' : '❌'} {toast.msg}
          </div>
        )}
        {loading ? <div style={{ color: 'var(--text-secondary)', paddingTop: 40, textAlign: 'center' }}>⏳ Lade Einstellungen…</div> : (
          <>
            {tab === 'profile' && <ProfileTab user={user} saveUser={saveUser} />}
            {tab === 'language' && <LanguageTab user={user} locales={locales} saveUser={saveUser} />}
            {tab === 'themes' && <ThemesTab themes={themes} user={user} saveUser={saveUser} />}
            {tab === 'providers' && <ProvidersTab providers={providers} setProviders={setProviders} showToast={showToast} />}
            {tab === 'models' && <ModelsTab models={models} setModels={setModels} showToast={showToast} onRefresh={loadAll} />}
            {tab === 'ghost' && <GhostTab user={user} saveUser={saveUser} />}
            {tab === 'network' && <NetworkTab showToast={showToast} />}
            {tab === 'hardware' && <HardwareTab hardware={hardware} />}
            {tab === 'database' && <DatabaseTab />}
            {tab === 'about' && <AboutTab />}
          </>
        )}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════
//  TAB COMPONENTS
// ═══════════════════════════════════════════════════════════════

function ProfileTab({ user, saveUser }) {
  return (
    <TabSection title="👤 Profil & Konto">
      <Field label="Benutzername" value={user.username} disabled hint="Kann nicht geändert werden" />
      <Field label="Anzeigename" value={user.display_name_custom} onChange={v => saveUser({ display_name_custom: v })} />
      <Field label="Ghost-Name" value={user.ghost_name} onChange={v => saveUser({ ghost_name: v })} hint="Wie heißt dein KI-Assistent?" />
      <Field label="GitHub" value={user.github_username} onChange={v => saveUser({ github_username: v })} placeholder="octocat" />
      <Field label="GitHub Token" type="password" value="" onChange={v => v && saveUser({ github_token: v })} placeholder="ghp_..." hint="Verschlüsselt gespeichert" />
      <Field label="Neues Passwort" type="password" value="" onChange={v => v && saveUser({ password: v })} placeholder="Leer = nicht ändern" />
      <div style={{ marginTop: 16 }}>
        <label style={labelStyle}>Interessen</label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
          {interestOptions.map(opt => {
            const sel = (user.user_interests || []).includes(opt.id)
            return <Chip key={opt.id} label={`${opt.icon} ${opt.label}`} selected={sel}
              onClick={() => { const c = user.user_interests || []; saveUser({ user_interests: sel ? c.filter(i => i !== opt.id) : [...c, opt.id] }) }} />
          })}
        </div>
      </div>
      <div style={{ marginTop: 20, padding: 12, background: 'var(--bg-surface)', borderRadius: 8, border: '1px solid var(--border)', fontSize: 11, color: 'var(--text-secondary)' }}>
        Konto: {user.created_at ? new Date(user.created_at).toLocaleDateString('de-DE') : '—'} • Setup: {user.setup_completed ? '✅' : '⏳'}
      </div>
    </TabSection>
  )
}

function LanguageTab({ user, locales, saveUser }) {
  return (
    <TabSection title="🌍 Sprache & Region">
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Sprache</label>
        <select value={user.locale || 'de-DE'} onChange={e => saveUser({ locale: e.target.value })} style={selectStyle}>
          {locales.map(l => <option key={l.locale} value={l.locale}>{l.name}</option>)}
        </select>
      </div>
      <div>
        <label style={labelStyle}>Zeitzone</label>
        <select value={user.timezone || 'Europe/Berlin'} onChange={e => saveUser({ timezone: e.target.value })} style={selectStyle}>
          {timezones.map(tz => <option key={tz} value={tz}>{tz}</option>)}
        </select>
      </div>
    </TabSection>
  )
}

function ThemesTab({ themes, user, saveUser }) {
  return (
    <TabSection title="🎨 Themes">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
        {themes.map(t => (
          <div key={t.name} onClick={() => saveUser({ theme: t.name })}
            style={{ padding: 14, borderRadius: 8, cursor: 'pointer', background: user.theme === t.name ? 'rgba(0,255,204,0.1)' : 'var(--bg-surface)', border: `2px solid ${user.theme === t.name ? 'var(--accent)' : 'var(--border)'}`, transition: 'all 0.2s' }}>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{t.display_name || t.name}</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{t.description || ''}</div>
            {t.colors && <div style={{ display: 'flex', gap: 3, marginTop: 8 }}>{Object.values(t.colors).slice(0, 6).map((c, i) => <div key={i} style={{ width: 16, height: 16, borderRadius: 3, background: c, border: '1px solid rgba(255,255,255,0.1)' }} />)}</div>}
            {user.theme === t.name && <div style={{ fontSize: 10, color: 'var(--accent)', marginTop: 6 }}>✓ Aktiv</div>}
          </div>
        ))}
      </div>
    </TabSection>
  )
}

function ProvidersTab({ providers, setProviders, showToast }) {
  const [editing, setEditing] = useState(null)
  const [apiKey, setApiKey] = useState('')
  const [apiBase, setApiBase] = useState('')
  const [testing, setTesting] = useState(null)

  const handleSave = async (pk) => {
    try {
      const u = {}
      if (apiKey) u.api_key = apiKey
      if (apiBase) u.api_base_url = apiBase
      u.is_enabled = true
      await api.llmProviderUpdate(pk, u)
      setProviders(prev => prev.map(p => p.provider_key === pk ? { ...p, is_configured: !!apiKey || p.is_configured, is_enabled: true, api_key_preview: apiKey ? apiKey.slice(0, 6) + '...' + apiKey.slice(-4) : p.api_key_preview } : p))
      setEditing(null); setApiKey(''); setApiBase('')
      showToast(`${pk} konfiguriert`)
    } catch (e) { showToast('Fehler: ' + e.message, false) }
  }

  const handleTest = async (pk) => {
    setTesting(pk)
    try {
      const r = await api.llmProviderTest(pk)
      showToast(r.ok ? `${pk} ✅ OK` : `${pk} — ${r.error}`, r.ok)
      setProviders(prev => prev.map(p => p.provider_key === pk ? { ...p, last_test_ok: r.ok } : p))
    } catch { showToast('Test fehlgeschlagen', false) }
    setTesting(null)
  }

  const handleToggle = async (pk, v) => {
    try { await api.llmProviderUpdate(pk, { is_enabled: v }); setProviders(prev => prev.map(p => p.provider_key === pk ? { ...p, is_enabled: v } : p)) } catch {}
  }

  const handleRemoveKey = async (pk) => {
    try { await api.llmProviderRemoveKey(pk); setProviders(prev => prev.map(p => p.provider_key === pk ? { ...p, api_key_preview: null, is_configured: false, is_enabled: false } : p)); showToast('Key entfernt') } catch {}
  }

  const renderProvider = (p) => (
    <div key={p.provider_key} style={{ padding: 14, background: 'var(--bg-surface)', borderRadius: 8, border: `1px solid ${p.is_enabled ? 'var(--accent)' : 'var(--border)'}`, transition: 'all 0.2s' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 20 }}>{p.icon}</span>
          <div>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{p.display_name}</div>
            <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{p.description}</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {p.is_configured && <span style={{ fontSize: 10, color: p.last_test_ok ? '#0f8' : 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{p.api_key_preview || '✓'}</span>}
          <Toggle value={p.is_enabled} onChange={v => handleToggle(p.provider_key, v)} />
        </div>
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 10, color: 'var(--text-secondary)' }}>
        {p.pricing_info && <span>💰 {p.pricing_info}</span>}
        {p.docs_url && <a href={p.docs_url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>📖 Docs</a>}
      </div>
      <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
        {p.supports_chat && <Badge label="Chat" />}
        {p.supports_vision && <Badge label="Vision" />}
        {p.supports_embedding && <Badge label="Embedding" />}
        {p.supports_tools && <Badge label="Tools" />}
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
        <SmallBtn label={editing === p.provider_key ? '✕ Schließen' : '🔑 API-Key'} onClick={() => { setEditing(editing === p.provider_key ? null : p.provider_key); setApiKey(''); setApiBase(p.api_base_url || '') }} />
        {p.is_configured && <>
          <SmallBtn label={testing === p.provider_key ? '⏳…' : '🧪 Testen'} onClick={() => handleTest(p.provider_key)} />
          <SmallBtn label="🗑️" onClick={() => handleRemoveKey(p.provider_key)} danger />
        </>}
      </div>
      {editing === p.provider_key && (
        <div style={{ marginTop: 10, padding: 12, background: 'var(--bg-primary)', borderRadius: 6, border: '1px solid var(--border)' }}>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'block', marginBottom: 3 }}>API-Key</label>
            <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder={p.api_key_preview || 'sk-... / nvapi-...'} style={inputStyle} />
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'block', marginBottom: 3 }}>Base URL</label>
            <input type="text" value={apiBase} onChange={e => setApiBase(e.target.value)} placeholder={p.api_base_url || 'https://api.example.com/v1'} style={inputStyle} />
          </div>
          <button onClick={() => handleSave(p.provider_key)} style={{ ...btnStyle, background: 'var(--accent)', color: 'var(--bg-primary)', fontWeight: 600 }}>💾 Speichern</button>
        </div>
      )}
    </div>
  )

  const cloud = providers.filter(p => p.provider_type === 'cloud')
  const local = providers.filter(p => p.provider_type === 'local')

  return (
    <TabSection title="☁️ KI-Provider">
      <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 16 }}>
        Konfiguriere Cloud-Anbieter und lokale Inference-Server. API-Keys werden verschlüsselt in der Datenbank gespeichert.
      </p>
      <h4 style={{ color: 'var(--accent)', fontSize: 12, marginBottom: 8 }}>Cloud-Provider</h4>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 20 }}>{cloud.map(renderProvider)}</div>
      <h4 style={{ color: 'var(--accent)', fontSize: 12, marginBottom: 8 }}>Lokale Backends</h4>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>{local.map(renderProvider)}</div>
    </TabSection>
  )
}

function ModelsTab({ models, setModels, showToast, onRefresh }) {
  const [scanning, setScanning] = useState(false)
  const [scanResults, setScanResults] = useState([])

  const handleScan = async () => {
    setScanning(true)
    try {
      const r = await api.llmScanQuick()
      setScanResults(r.models || [])
      showToast(`${(r.models || []).length} Modelle gefunden`)
    } catch (e) { showToast('Scan fehlgeschlagen', false) }
    setScanning(false)
  }

  const handleIntegrate = async (m) => {
    try {
      await api.llmAddModel({ name: m.name_guess || m.filename, path: m.path, format: m.format, size: m.size })
      setScanResults(prev => prev.filter(x => x.path !== m.path))
      showToast(`${m.name_guess || m.filename} integriert`)
      if (onRefresh) onRefresh()
    } catch (e) { showToast('Fehler: ' + e.message, false) }
  }

  const handleRemove = async (id) => {
    try { await api.llmRemoveModel(id); setModels(prev => prev.filter(m => m.id !== id)); showToast('Entfernt') } catch {}
  }

  return (
    <TabSection title="🧠 Registrierte Modelle">
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button onClick={handleScan} disabled={scanning} style={{ ...btnStyle, background: 'rgba(0,255,204,0.1)', border: '1px solid var(--accent)', color: 'var(--accent)' }}>
          {scanning ? '⏳ Scanne…' : '🔍 Festplatten nach LLMs durchsuchen'}
        </button>
      </div>
      {scanResults.length > 0 && (
        <div style={{ marginBottom: 20, padding: 12, background: 'rgba(0,255,204,0.04)', border: '1px solid rgba(0,255,204,0.15)', borderRadius: 8 }}>
          <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 8, color: 'var(--accent)' }}>🔍 {scanResults.length} Modelle gefunden</div>
          {scanResults.map((m, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 10px', borderRadius: 6, marginBottom: 4, background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 12 }}>{m.name_guess || m.filename}</div>
                <div style={{ fontSize: 10, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{m.path} • {m.size_display} • {m.format}</div>
              </div>
              <SmallBtn label="➕ Integrieren" onClick={() => handleIntegrate(m)} />
            </div>
          ))}
        </div>
      )}
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 8 }}>{models.length} Modelle registriert</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {models.map(m => (
          <div key={m.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', borderRadius: 6, background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                {m.display_name || m.name}
                <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 3, background: m.status === 'active' ? 'rgba(0,255,128,0.15)' : 'rgba(255,255,255,0.05)', color: m.status === 'active' ? '#0f8' : 'var(--text-secondary)' }}>{m.status}</span>
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                {m.parameters && `${m.parameters} • `}{m.quantization && `${m.quantization} • `}{m.path}
              </div>
            </div>
            <SmallBtn label="🗑️" onClick={() => handleRemove(m.id)} danger />
          </div>
        ))}
      </div>
    </TabSection>
  )
}

function GhostTab({ user, saveUser }) {
  return (
    <TabSection title="👻 Ghost-Einstellungen">
      <ToggleField label="Auto Ghost-Swap" hint="Ghost wechselt automatisch das Modell je nach Aufgabe"
        value={user.preferences?.auto_ghost_swap !== false} onChange={v => saveUser({ preferences: { auto_ghost_swap: v } })} />
      <ToggleField label="Self-Healing" hint="System repariert sich automatisch bei Problemen"
        value={user.preferences?.auto_heal !== false} onChange={v => saveUser({ preferences: { auto_heal: v } })} />
      <ToggleField label="Telemetrie (lokal)" hint="Hardware-Metriken sammeln — kein Cloud"
        value={user.preferences?.telemetry !== false} onChange={v => saveUser({ preferences: { telemetry: v } })} />
      <Field label="Standard-Modell" value={user.preferences?.default_model || 'qwen2.5-7b-instruct'}
        onChange={v => saveUser({ preferences: { default_model: v } })} />
    </TabSection>
  )
}

function NetworkTab({ showToast }) {
  const [devices, setDevices] = useState([])
  const [scanning, setScanning] = useState(false)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => { api.networkDevices().then(d => { setDevices(d || []); setLoaded(true) }).catch(() => setLoaded(true)) }, [])

  const handleScan = async () => {
    setScanning(true)
    try { const r = await api.networkScan(); setDevices(r.devices || []); showToast(`${(r.devices || []).length} Geräte`) } catch { showToast('Fehler', false) }
    setScanning(false)
  }

  return (
    <TabSection title="🌐 Netzwerk">
      <button onClick={handleScan} disabled={scanning} style={{ ...btnStyle, background: 'rgba(0,255,204,0.1)', border: '1px solid var(--accent)', color: 'var(--accent)', marginBottom: 16 }}>
        {scanning ? '📡 Scanne…' : '🔍 Netzwerk scannen'}
      </button>
      {!loaded ? <div style={{ color: 'var(--text-secondary)' }}>Lade…</div> : devices.length === 0 ? (
        <div style={{ color: 'var(--text-secondary)', fontSize: 12 }}>Keine Geräte. Starte einen Scan.</div>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead><tr style={{ borderBottom: '1px solid var(--border)' }}><th style={thStyle}>Typ</th><th style={thStyle}>IP</th><th style={thStyle}>Name</th><th style={thStyle}>Port</th></tr></thead>
          <tbody>{devices.map((d, i) => (
            <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
              <td style={tdStyle}>{typeIcons[d.device_type] || '🔗'}</td>
              <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)' }}>{d.ip}</td>
              <td style={tdStyle}>{d.title || d.hostname || '—'}</td>
              <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)' }}>{d.port}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </TabSection>
  )
}

function HardwareTab({ hardware }) {
  if (!hardware) return <div style={{ color: 'var(--text-secondary)' }}>Lade Hardware-Info…</div>
  return (
    <TabSection title="🖥️ Hardware">
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
        <InfoCard icon="🏠" label="Hostname" value={hardware.hostname} />
        <InfoCard icon="💻" label="OS" value={hardware.os} />
        <InfoCard icon="⚙️" label="Arch" value={hardware.arch} />
        <InfoCard icon="🧵" label="CPU Kerne" value={hardware.cpu_count} />
        <InfoCard icon="🐍" label="Python" value={hardware.python} />
        <InfoCard icon="💾" label="RAM" value={hardware.ram_mb ? `${(hardware.ram_mb / 1024).toFixed(1)} GB` : '—'} />
        <InfoCard icon="📀" label="Disk" value={hardware.disk_total_gb ? `${hardware.disk_total_gb} GB` : '—'} />
        <InfoCard icon="📀" label="Frei" value={hardware.disk_free_gb ? `${hardware.disk_free_gb} GB` : '—'} />
      </div>
      {hardware.gpus?.length > 0 && <>
        <h4 style={{ color: 'var(--accent)', fontSize: 12, marginBottom: 8 }}>GPUs</h4>
        {hardware.gpus.map((gpu, i) => (
          <div key={i} style={{ padding: 12, background: 'var(--bg-surface)', borderRadius: 8, border: '1px solid var(--border)', marginBottom: 6 }}>
            <div style={{ fontWeight: 600, fontSize: 13 }}>🎮 {gpu.name}</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>VRAM: {(gpu.vram_mb / 1024).toFixed(0)} GB • Treiber: {gpu.driver} • {gpu.temp_c}°C</div>
          </div>
        ))}
      </>}
    </TabSection>
  )
}

function DatabaseTab() {
  const [info, setInfo] = useState(null)
  useEffect(() => {
    api.sqlQuery(`SELECT (SELECT pg_database_size('dbai')) as db_size, (SELECT count(*) FROM information_schema.tables WHERE table_schema LIKE 'dbai_%') as table_count, (SELECT count(*) FROM information_schema.schemata WHERE schema_name LIKE 'dbai_%') as schema_count, (SELECT count(*) FROM pg_stat_activity WHERE datname='dbai') as connections, (SELECT version()) as pg_version`).then(r => setInfo(r.rows?.[0])).catch(() => {})
  }, [])
  if (!info) return <div style={{ color: 'var(--text-secondary)' }}>Lade…</div>
  return (
    <TabSection title="🗄️ Datenbank">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <InfoCard icon="🐘" label="PostgreSQL" value={info.pg_version?.split(' ').slice(0, 2).join(' ')} />
        <InfoCard icon="📊" label="Größe" value={`${(info.db_size / 1024 / 1024).toFixed(1)} MB`} />
        <InfoCard icon="📁" label="Schemas" value={info.schema_count} />
        <InfoCard icon="📋" label="Tabellen" value={info.table_count} />
        <InfoCard icon="🔌" label="Verbindungen" value={info.connections} />
      </div>
    </TabSection>
  )
}

function AboutTab() {
  return (
    <TabSection title="ℹ️ Über DBAI">
      <div style={{ maxWidth: 500 }}>
        <div style={{ fontSize: 48, marginBottom: 8 }}>👻</div>
        <h2 style={{ color: 'var(--accent)', fontFamily: 'var(--font-display)', margin: '0 0 4px' }}>DBAI</h2>
        <div style={{ color: 'var(--text-secondary)', marginBottom: 16, fontSize: 13 }}>Ghost in the Database — v0.8.0</div>
        <div style={{ fontSize: 12, lineHeight: 1.8, color: 'var(--text-primary)' }}>
          <p>DBAI ist ein tabellenbasiertes Betriebssystem auf PostgreSQL-Basis.</p>
          <p style={{ marginTop: 6 }}>Alles ist eine Zeile — Prozesse, Dateien, KI-Zustände, Hardware-Metriken.</p>
          <p style={{ marginTop: 6 }}>Bare-Metal: Linux als unsichtbarer Übersetzer, PostgreSQL als Kernel, der Ghost als Bewusstsein.</p>
        </div>
        <div style={{ marginTop: 20, fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', lineHeight: 1.8 }}>
          <div>9 Schemas · ~70 Tabellen · RLS</div>
          <div>PostgreSQL 16 · pgvector · FastAPI · React</div>
          <div>12 Sprachen · 20+ Apps · 12 KI-Provider</div>
          <div>Bare-Metal Simulation · Headless Host OS</div>
        </div>
      </div>
    </TabSection>
  )
}

// ═══════════════════════════════════════════════════════════════
//  HELPERS
// ═══════════════════════════════════════════════════════════════

function TabSection({ title, children }) {
  return <div><h3 style={{ color: 'var(--accent)', fontSize: 16, margin: '0 0 16px' }}>{title}</h3>{children}</div>
}

function Field({ label, value, onChange, type = 'text', placeholder, hint, disabled }) {
  const [local, setLocal] = useState(value || '')
  const [mod, setMod] = useState(false)
  useEffect(() => { setLocal(value || ''); setMod(false) }, [value])
  const save = () => { if (mod && onChange && local !== (value || '')) { onChange(local); setMod(false) } }
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={labelStyle}>{label}</label>
      <input type={type} value={local} onChange={e => { setLocal(e.target.value); setMod(true) }} onBlur={save} onKeyDown={e => e.key === 'Enter' && save()} placeholder={placeholder} disabled={disabled} style={{ ...inputStyle, opacity: disabled ? 0.5 : 1 }} />
      {hint && <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 2 }}>{hint}</div>}
    </div>
  )
}

function Toggle({ value, onChange }) {
  return (
    <div onClick={() => onChange(!value)} style={{ width: 36, height: 20, borderRadius: 10, cursor: 'pointer', background: value ? 'var(--accent)' : 'var(--bg-elevated)', border: `1px solid ${value ? 'var(--accent)' : 'var(--border)'}`, position: 'relative', transition: 'all 0.2s', flexShrink: 0 }}>
      <div style={{ width: 14, height: 14, borderRadius: '50%', background: value ? 'var(--bg-primary)' : 'var(--text-secondary)', position: 'absolute', top: 2, left: value ? 18 : 2, transition: 'left 0.2s' }} />
    </div>
  )
}

function ToggleField({ label, hint, value, onChange }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', marginBottom: 6, background: 'var(--bg-surface)', borderRadius: 6, border: '1px solid var(--border)' }}>
      <div><div style={{ fontWeight: 600, fontSize: 12 }}>{label}</div>{hint && <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 2 }}>{hint}</div>}</div>
      <Toggle value={value} onChange={onChange} />
    </div>
  )
}

function Chip({ label, selected, onClick }) {
  return <div onClick={onClick} style={{ padding: '4px 10px', borderRadius: 14, cursor: 'pointer', fontSize: 11, transition: 'all 0.2s', background: selected ? 'rgba(0,255,204,0.15)' : 'var(--bg-surface)', border: `1px solid ${selected ? 'var(--accent)' : 'var(--border)'}`, color: selected ? 'var(--accent)' : 'var(--text-secondary)' }}>{label}</div>
}

function InfoCard({ icon, label, value }) {
  return (
    <div style={{ padding: '10px 12px', background: 'var(--bg-surface)', borderRadius: 6, border: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{icon} {label}</span>
      <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)', fontSize: 12 }}>{value ?? '—'}</span>
    </div>
  )
}

function Badge({ label }) {
  return <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 3, background: 'rgba(0,255,204,0.08)', color: 'var(--accent)', border: '1px solid rgba(0,255,204,0.15)' }}>{label}</span>
}

function SmallBtn({ label, onClick, danger }) {
  return <button onClick={onClick} style={{ padding: '3px 8px', borderRadius: 4, border: `1px solid ${danger ? 'rgba(255,60,60,0.3)' : 'var(--border)'}`, background: danger ? 'rgba(255,60,60,0.08)' : 'var(--bg-elevated)', color: danger ? '#f55' : 'var(--text-primary)', fontSize: 10, cursor: 'pointer' }}>{label}</button>
}

// Constants
const interestOptions = [
  { id: 'coding', icon: '💻', label: 'Programmierung' },
  { id: 'ai_ml', icon: '🤖', label: 'KI & ML' },
  { id: 'homelab', icon: '🖥️', label: 'Homelab' },
  { id: 'iot', icon: '📡', label: 'IoT' },
  { id: 'gaming', icon: '🎮', label: 'Gaming' },
  { id: 'creative', icon: '🎨', label: 'Kreativ' },
  { id: 'science', icon: '🔬', label: 'Wissenschaft' },
  { id: 'robotics', icon: '🦾', label: 'Robotik' },
  { id: 'security', icon: '🔒', label: 'Sicherheit' },
  { id: 'data', icon: '📊', label: 'Daten' },
]
const timezones = ['Europe/Berlin','Europe/London','Europe/Paris','Europe/Moscow','America/New_York','America/Los_Angeles','America/Chicago','Asia/Tokyo','Asia/Shanghai','Asia/Kolkata','Asia/Dubai','Australia/Sydney','Pacific/Auckland']
const typeIcons = { nas:'💾', router:'🌐', printer:'🖨️', camera:'📷', smarthome:'🏠', robot:'🤖', server:'🖥️', ai:'🧠', media:'🎬', dns:'🛡️', iot:'📡', phone:'📱', unknown:'🔗' }
const labelStyle = { fontSize: 11, fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: 4 }
const inputStyle = { padding: '7px 10px', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-primary)', fontSize: 12, fontFamily: 'var(--font-mono)', width: '100%', boxSizing: 'border-box' }
const selectStyle = { padding: '7px 10px', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-primary)', fontSize: 12, width: '100%' }
const btnStyle = { padding: '7px 16px', borderRadius: 6, cursor: 'pointer', fontSize: 12, border: 'none' }
const thStyle = { padding: '6px 8px', textAlign: 'left', color: 'var(--text-secondary)', fontSize: 10, fontWeight: 600 }
const tdStyle = { padding: '6px 8px', color: 'var(--text-primary)' }
