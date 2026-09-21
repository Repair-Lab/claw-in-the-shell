import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'
import AppSettingsPanel from '../AppSettingsPanel'

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

  // ── Linux-System State ──
  const [display, setDisplay] = useState(null)
  const [sound, setSound] = useState(null)
  const [bluetooth, setBluetooth] = useState(null)
  const [power, setPower] = useState(null)
  const [keyboard, setKeyboard] = useState(null)
  const [mouse, setMouse] = useState(null)
  const [printers, setPrinters] = useState(null)
  const [storage, setStorage] = useState(null)
  const [users, setUsers] = useState(null)
  const [datetime, setDatetime] = useState(null)
  const [notifications, setNotifications] = useState(null)
  const [updates, setUpdates] = useState(null)
  const [security, setSecurity] = useState(null)
  const [accessibility, setAccessibility] = useState(null)

  const loadLinuxSettings = async (which) => {
    try {
      const r = await api.linuxSettings(which)
      const setters = { display: setDisplay, sound: setSound, bluetooth: setBluetooth, power: setPower, keyboard: setKeyboard, mouse: setMouse, printers: setPrinters, storage: setStorage, users: setUsers, datetime: setDatetime, notifications: setNotifications, updates: setUpdates, security: setSecurity, accessibility: setAccessibility }
      if (setters[which]) setters[which](r || {})
    } catch { const setters = { display: setDisplay, sound: setSound, bluetooth: setBluetooth, power: setPower, keyboard: setKeyboard, mouse: setMouse, printers: setPrinters, storage: setStorage, users: setUsers, datetime: setDatetime, notifications: setNotifications, updates: setUpdates, security: setSecurity, accessibility: setAccessibility }; if (setters[which]) setters[which]({}) }
  }

  const saveLinuxSetting = async (which, key, value) => {
    setSaving(true)
    try {
      await api.linuxSettingsUpdate(which, { [key]: value })
      showToast('Gespeichert')
      loadLinuxSettings(which)
    } catch (e) { showToast('Fehler: ' + e.message, false) }
    setSaving(false)
  }

  const tabSections = [
    { header: 'Persönlich', items: [
      { id: 'profile', icon: '👤', label: 'Profil' },
      { id: 'language', icon: '🌍', label: 'Sprache' },
      { id: 'themes', icon: '🎨', label: 'Themes' },
      { id: 'notifications', icon: '🔔', label: 'Benachrichtigungen' },
      { id: 'accessibility', icon: '♿', label: 'Barrierefreiheit' },
    ]},
    { header: 'System', items: [
      { id: 'display', icon: '🖥️', label: 'Anzeige' },
      { id: 'sound', icon: '🔊', label: 'Audio' },
      { id: 'keyboard', icon: '⌨️', label: 'Tastatur' },
      { id: 'mouse', icon: '🖱️', label: 'Maus & Touchpad' },
      { id: 'printers', icon: '🖨️', label: 'Drucker' },
      { id: 'bluetooth', icon: '🔵', label: 'Bluetooth' },
      { id: 'network', icon: '🌐', label: 'Netzwerk' },
      { id: 'power', icon: '🔋', label: 'Energie' },
      { id: 'storage', icon: '💽', label: 'Speicher' },
      { id: 'datetime', icon: '🕐', label: 'Datum & Uhrzeit' },
      { id: 'users', icon: '👥', label: 'Benutzer' },
      { id: 'security', icon: '🔒', label: 'Sicherheit' },
      { id: 'updates', icon: '🔄', label: 'Updates' },
    ]},
    { header: 'Hardware', items: [
      { id: 'hardware', icon: '🔧', label: 'Hardware-Info' },
    ]},
    { header: 'KI & Ghost', items: [
      { id: 'ghost', icon: '👻', label: 'Ghost' },
      { id: 'providers', icon: '☁️', label: 'KI-Provider' },
      { id: 'models', icon: '🧠', label: 'Modelle' },
    ]},
    { header: 'Datenbank', items: [
      { id: 'database', icon: '🗄️', label: 'PostgreSQL' },
      { id: 'app-settings', icon: '📱', label: 'App-Einstellungen' },
      { id: 'about', icon: 'ℹ️', label: 'Über DBAI' },
    ]},
  ]

  const handleTabClick = (id) => {
    setTab(id)
    if (id === 'hardware') loadHardware()
    const linuxTabs = ['display','sound','bluetooth','power','keyboard','mouse','printers','storage','users','datetime','notifications','updates','security','accessibility']
    if (linuxTabs.includes(id)) loadLinuxSettings(id)
  }

  return (
    <div style={{ display: 'flex', height: '100%', fontFamily: 'var(--font-sans)', fontSize: 13 }}>
      <div style={{ width: 190, borderRight: '1px solid var(--border)', padding: '8px 6px', display: 'flex', flexDirection: 'column', gap: 0, overflowY: 'auto' }}>
        {tabSections.map(section => (
          <div key={section.header}>
            <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1.2, padding: '10px 10px 4px', marginTop: 4 }}>{section.header}</div>
            {section.items.map(t => (
              <div key={t.id} onClick={() => handleTabClick(t.id)}
                style={{ padding: '6px 10px', cursor: 'pointer', borderRadius: 6, background: tab === t.id ? 'var(--bg-elevated)' : 'transparent', color: tab === t.id ? 'var(--accent)' : 'var(--text-primary)', transition: 'all 0.15s', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 13, width: 18, textAlign: 'center' }}>{t.icon}</span> {t.label}
              </div>
            ))}
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
            {tab === 'app-settings' && <AllAppSettingsTab />}
            {tab === 'display' && <DisplayTab data={display} onSave={(k,v) => saveLinuxSetting('display',k,v)} showToast={showToast} />}
            {tab === 'sound' && <SoundTab data={sound} onSave={(k,v) => saveLinuxSetting('sound',k,v)} />}
            {tab === 'bluetooth' && <BluetoothTab data={bluetooth} onSave={(k,v) => saveLinuxSetting('bluetooth',k,v)} showToast={showToast} />}
            {tab === 'power' && <PowerTab data={power} onSave={(k,v) => saveLinuxSetting('power',k,v)} />}
            {tab === 'keyboard' && <KeyboardTab data={keyboard} onSave={(k,v) => saveLinuxSetting('keyboard',k,v)} />}
            {tab === 'mouse' && <MouseTab data={mouse} onSave={(k,v) => saveLinuxSetting('mouse',k,v)} />}
            {tab === 'printers' && <PrintersTab data={printers} showToast={showToast} />}
            {tab === 'storage' && <StorageTab data={storage} />}
            {tab === 'users' && <UsersTab data={users} showToast={showToast} />}
            {tab === 'datetime' && <DateTimeTab data={datetime} onSave={(k,v) => saveLinuxSetting('datetime',k,v)} />}
            {tab === 'notifications' && <NotificationsTab user={user} saveUser={saveUser} />}
            {tab === 'updates' && <UpdatesTab data={updates} showToast={showToast} />}
            {tab === 'security' && <SecurityTab data={security} onSave={(k,v) => saveLinuxSetting('security',k,v)} />}
            {tab === 'accessibility' && <AccessibilityTab user={user} saveUser={saveUser} />}
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
//  LINUX SYSTEM TABS
// ═══════════════════════════════════════════════════════════════

function DisplayTab({ data, onSave, showToast }) {
  if (!data) return <div style={{ color: 'var(--text-secondary)' }}>Lade Display-Info…</div>
  const resolutions = data.available_resolutions || ['3840x2160','2560x1440','1920x1080','1680x1050','1600x900','1440x900','1366x768','1280x1024','1280x720','1024x768']
  const refreshRates = data.available_refresh_rates || ['60','75','120','144','165']
  const scalings = ['100%','125%','150%','175%','200%']
  return (
    <TabSection title="🖥️ Anzeige & Bildschirm">
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
        <InfoCard icon="🖥️" label="Monitor" value={data.monitor_name || 'Primär'} />
        <InfoCard icon="📐" label="Aktuell" value={data.current_resolution || '1920x1080'} />
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Auflösung</label>
        <select value={data.current_resolution || '1920x1080'} onChange={e => onSave('resolution', e.target.value)} style={selectStyle}>
          {resolutions.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Bildwiederholrate</label>
        <select value={data.refresh_rate || '60'} onChange={e => onSave('refresh_rate', e.target.value)} style={selectStyle}>
          {refreshRates.map(r => <option key={r} value={r}>{r} Hz</option>)}
        </select>
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Skalierung</label>
        <select value={data.scaling || '100%'} onChange={e => onSave('scaling', e.target.value)} style={selectStyle}>
          {scalings.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Helligkeit</label>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 11 }}>🔅</span>
          <input type="range" min="10" max="100" value={data.brightness || 80} onChange={e => onSave('brightness', parseInt(e.target.value))} style={{ flex: 1, accentColor: 'var(--accent)' }} />
          <span style={{ fontSize: 11 }}>🔆</span>
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', minWidth: 30 }}>{data.brightness || 80}%</span>
        </div>
      </div>
      <ToggleField label="Nachtmodus" hint="Reduziert Blaulicht für augenschonendes Arbeiten"
        value={data.night_mode || false} onChange={v => onSave('night_mode', v)} />
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Ausrichtung</label>
        <select value={data.orientation || 'landscape'} onChange={e => onSave('orientation', e.target.value)} style={selectStyle}>
          <option value="landscape">Querformat</option>
          <option value="portrait">Hochformat</option>
          <option value="landscape-flipped">Querformat (umgekehrt)</option>
          <option value="portrait-flipped">Hochformat (umgekehrt)</option>
        </select>
      </div>
      {data.monitors && data.monitors.length > 1 && (
        <div style={{ marginTop: 16 }}>
          <label style={labelStyle}>Multi-Monitor Anordnung</label>
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            {data.monitors.map((m, i) => (
              <div key={i} style={{ padding: 12, background: 'var(--bg-surface)', border: `2px solid ${m.primary ? 'var(--accent)' : 'var(--border)'}`, borderRadius: 8, textAlign: 'center', minWidth: 100 }}>
                <div style={{ fontSize: 24 }}>🖥️</div>
                <div style={{ fontSize: 11, fontWeight: 600 }}>{m.name || `Monitor ${i+1}`}</div>
                <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{m.resolution}</div>
                {m.primary && <div style={{ fontSize: 9, color: 'var(--accent)', marginTop: 4 }}>✓ Primär</div>}
              </div>
            ))}
          </div>
        </div>
      )}
    </TabSection>
  )
}

function SoundTab({ data, onSave }) {
  if (!data) return <div style={{ color: 'var(--text-secondary)' }}>Lade Audio-Info…</div>
  return (
    <TabSection title="🔊 Audio & Sound">
      <div style={{ marginBottom: 20 }}>
        <h4 style={{ color: 'var(--accent)', fontSize: 12, marginBottom: 8 }}>🔈 Ausgabe</h4>
        <div style={{ marginBottom: 12 }}>
          <label style={labelStyle}>Ausgabegerät</label>
          <select value={data.output_device || ''} onChange={e => onSave('output_device', e.target.value)} style={selectStyle}>
            {(data.output_devices || [{ id: 'default', name: 'Standard-Ausgabe' }]).map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </div>
        <div style={{ marginBottom: 12 }}>
          <label style={labelStyle}>Lautstärke</label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 14 }}>🔇</span>
            <input type="range" min="0" max="100" value={data.volume || 75} onChange={e => onSave('volume', parseInt(e.target.value))} style={{ flex: 1, accentColor: 'var(--accent)' }} />
            <span style={{ fontSize: 14 }}>🔊</span>
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', minWidth: 30 }}>{data.volume || 75}%</span>
          </div>
        </div>
        <ToggleField label="Stumm" hint="Gesamte Audioausgabe stummschalten" value={data.muted || false} onChange={v => onSave('muted', v)} />
      </div>
      <div style={{ marginBottom: 20 }}>
        <h4 style={{ color: 'var(--accent)', fontSize: 12, marginBottom: 8 }}>🎤 Eingabe</h4>
        <div style={{ marginBottom: 12 }}>
          <label style={labelStyle}>Eingabegerät</label>
          <select value={data.input_device || ''} onChange={e => onSave('input_device', e.target.value)} style={selectStyle}>
            {(data.input_devices || [{ id: 'default', name: 'Standard-Mikrofon' }]).map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </div>
        <div style={{ marginBottom: 12 }}>
          <label style={labelStyle}>Mikrofonpegel</label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 14 }}>🎤</span>
            <input type="range" min="0" max="100" value={data.input_volume || 80} onChange={e => onSave('input_volume', parseInt(e.target.value))} style={{ flex: 1, accentColor: '#a855f7' }} />
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: '#a855f7', minWidth: 30 }}>{data.input_volume || 80}%</span>
          </div>
        </div>
      </div>
      <ToggleField label="System-Sounds" hint="Klänge für Benachrichtigungen und Aktionen" value={data.system_sounds !== false} onChange={v => onSave('system_sounds', v)} />
      <ToggleField label="Startup-Sound" hint="Sound beim Hochfahren abspielen" value={data.startup_sound || false} onChange={v => onSave('startup_sound', v)} />
    </TabSection>
  )
}

function BluetoothTab({ data, onSave, showToast }) {
  if (!data) return <div style={{ color: 'var(--text-secondary)' }}>Lade Bluetooth-Info…</div>
  const [scanning, setScanning] = useState(false)
  const handleScan = async () => {
    setScanning(true)
    try { await api.linuxSettingsAction('bluetooth', 'scan'); showToast('Suche gestartet…') } catch { showToast('Fehler', false) }
    setTimeout(() => setScanning(false), 5000)
  }
  return (
    <TabSection title="🔵 Bluetooth">
      <ToggleField label="Bluetooth" hint="Bluetooth-Adapter ein/ausschalten" value={data.enabled || false} onChange={v => onSave('enabled', v)} />
      <ToggleField label="Sichtbar" hint="Gerät für andere sichtbar machen" value={data.discoverable || false} onChange={v => onSave('discoverable', v)} />
      <div style={{ marginTop: 16, marginBottom: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h4 style={{ color: 'var(--accent)', fontSize: 12 }}>Gekoppelte Geräte</h4>
          <SmallBtn label={scanning ? '📡 Suche…' : '🔍 Suchen'} onClick={handleScan} />
        </div>
      </div>
      {(data.paired_devices || []).length === 0 ? (
        <div style={{ color: 'var(--text-secondary)', fontSize: 12, padding: 20, textAlign: 'center' }}>Keine gekoppelten Geräte</div>
      ) : (data.paired_devices || []).map((d, i) => (
        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 12px', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 6, marginBottom: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 18 }}>{d.type === 'audio' ? '🎧' : d.type === 'keyboard' ? '⌨️' : d.type === 'mouse' ? '🖱️' : d.type === 'phone' ? '📱' : '🔗'}</span>
            <div><div style={{ fontWeight: 600, fontSize: 12 }}>{d.name}</div><div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{d.mac || ''} {d.connected ? '• Verbunden' : ''}</div></div>
          </div>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: d.connected ? '#22c55e' : '#555' }} />
        </div>
      ))}
    </TabSection>
  )
}

function PowerTab({ data, onSave }) {
  if (!data) return <div style={{ color: 'var(--text-secondary)' }}>Lade Energie-Info…</div>
  return (
    <TabSection title="🔋 Energie & Stromversorgung">
      {data.battery_present && (
        <div style={{ padding: 16, background: 'var(--bg-surface)', borderRadius: 8, border: '1px solid var(--border)', marginBottom: 16, textAlign: 'center' }}>
          <div style={{ fontSize: 48 }}>{data.battery_percent > 80 ? '🔋' : data.battery_percent > 20 ? '🪫' : '⚠️'}</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--accent)', margin: '4px 0' }}>{data.battery_percent || 0}%</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{data.battery_status || 'Netzbetrieb'} {data.time_remaining ? `• ${data.time_remaining}` : ''}</div>
        </div>
      )}
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Bildschirm ausschalten nach</label>
        <select value={data.screen_off_minutes || '10'} onChange={e => onSave('screen_off_minutes', e.target.value)} style={selectStyle}>
          <option value="1">1 Minute</option><option value="5">5 Minuten</option><option value="10">10 Minuten</option><option value="15">15 Minuten</option><option value="30">30 Minuten</option><option value="60">1 Stunde</option><option value="never">Nie</option>
        </select>
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Bereitschaftsmodus nach</label>
        <select value={data.suspend_minutes || '30'} onChange={e => onSave('suspend_minutes', e.target.value)} style={selectStyle}>
          <option value="15">15 Minuten</option><option value="30">30 Minuten</option><option value="60">1 Stunde</option><option value="120">2 Stunden</option><option value="never">Nie</option>
        </select>
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Energieprofil</label>
        <select value={data.power_profile || 'balanced'} onChange={e => onSave('power_profile', e.target.value)} style={selectStyle}>
          <option value="performance">⚡ Höchstleistung</option><option value="balanced">⚖️ Ausgewogen</option><option value="powersave">🔋 Energiesparen</option>
        </select>
      </div>
      <ToggleField label="Deckel schließen = Bereitschaft" hint="Laptop geht in Bereitschaft wenn der Deckel geschlossen wird"
        value={data.lid_close_suspend !== false} onChange={v => onSave('lid_close_suspend', v)} />
    </TabSection>
  )
}

function KeyboardTab({ data, onSave }) {
  if (!data) return <div style={{ color: 'var(--text-secondary)' }}>Lade…</div>
  const layouts = data.available_layouts || ['de','us','fr','es','it','ru','ar','jp','kr','zh','tr']
  return (
    <TabSection title="⌨️ Tastatur">
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Tastaturlayout</label>
        <select value={data.layout || 'de'} onChange={e => onSave('layout', e.target.value)} style={selectStyle}>
          {layouts.map(l => <option key={l} value={l}>{l.toUpperCase()} — {layoutNames[l] || l}</option>)}
        </select>
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Wiederholrate</label>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 11 }}>Langsam</span>
          <input type="range" min="100" max="800" value={data.repeat_rate || 400} onChange={e => onSave('repeat_rate', parseInt(e.target.value))} style={{ flex: 1, accentColor: 'var(--accent)' }} />
          <span style={{ fontSize: 11 }}>Schnell</span>
        </div>
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Verzögerung bis Wiederholung</label>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 11 }}>Kurz</span>
          <input type="range" min="100" max="1000" value={data.repeat_delay || 500} onChange={e => onSave('repeat_delay', parseInt(e.target.value))} style={{ flex: 1, accentColor: 'var(--accent)' }} />
          <span style={{ fontSize: 11 }}>Lang</span>
        </div>
      </div>
      <ToggleField label="Num Lock beim Start" hint="Numerische Tastatur automatisch aktivieren" value={data.num_lock || false} onChange={v => onSave('num_lock', v)} />
      <ToggleField label="Caps Lock Warnung" hint="Anzeige bei aktiviertem Caps Lock" value={data.caps_warning !== false} onChange={v => onSave('caps_warning', v)} />
    </TabSection>
  )
}

function MouseTab({ data, onSave }) {
  if (!data) return <div style={{ color: 'var(--text-secondary)' }}>Lade…</div>
  return (
    <TabSection title="🖱️ Maus & Touchpad">
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Zeigergeschwindigkeit</label>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 11 }}>🐢</span>
          <input type="range" min="1" max="20" value={data.speed || 10} onChange={e => onSave('speed', parseInt(e.target.value))} style={{ flex: 1, accentColor: 'var(--accent)' }} />
          <span style={{ fontSize: 11 }}>🐇</span>
        </div>
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Scroll-Geschwindigkeit</label>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 11 }}>Langsam</span>
          <input type="range" min="1" max="10" value={data.scroll_speed || 5} onChange={e => onSave('scroll_speed', parseInt(e.target.value))} style={{ flex: 1, accentColor: 'var(--accent)' }} />
          <span style={{ fontSize: 11 }}>Schnell</span>
        </div>
      </div>
      <ToggleField label="Natürliches Scrollen" hint="Scroll-Richtung umkehren (Touchpad-Stil)" value={data.natural_scroll || false} onChange={v => onSave('natural_scroll', v)} />
      <ToggleField label="Linke Hand" hint="Primär- und Sekundärtaste tauschen" value={data.left_handed || false} onChange={v => onSave('left_handed', v)} />
      <div style={{ marginTop: 16 }}>
        <label style={labelStyle}>Doppelklick-Geschwindigkeit</label>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 11 }}>Langsam</span>
          <input type="range" min="200" max="800" value={data.double_click_speed || 400} onChange={e => onSave('double_click_speed', parseInt(e.target.value))} style={{ flex: 1, accentColor: 'var(--accent)' }} />
          <span style={{ fontSize: 11 }}>Schnell</span>
        </div>
      </div>
      <div style={{ marginTop: 12 }}>
        <label style={labelStyle}>Zeigergröße</label>
        <select value={data.cursor_size || 'default'} onChange={e => onSave('cursor_size', e.target.value)} style={selectStyle}>
          <option value="small">Klein (16px)</option><option value="default">Standard (24px)</option><option value="large">Groß (32px)</option><option value="xlarge">Sehr groß (48px)</option>
        </select>
      </div>
    </TabSection>
  )
}

function PrintersTab({ data, showToast }) {
  if (!data) return <div style={{ color: 'var(--text-secondary)' }}>Lade…</div>
  const [scanning, setScanning] = useState(false)
  const handleScan = async () => {
    setScanning(true)
    try { await api.linuxSettingsAction('printers', 'scan'); showToast('Suche läuft…') } catch { showToast('Fehler', false) }
    setTimeout(() => setScanning(false), 3000)
  }
  return (
    <TabSection title="🖨️ Drucker & Scanner">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{(data.printers || []).length} Drucker gefunden</div>
        <SmallBtn label={scanning ? '📡 Suche…' : '➕ Drucker suchen'} onClick={handleScan} />
      </div>
      {(data.printers || []).length === 0 ? (
        <div style={{ padding: 30, textAlign: 'center', color: 'var(--text-secondary)', fontSize: 12 }}>Keine Drucker konfiguriert. Klicke auf „Drucker suchen".</div>
      ) : (data.printers || []).map((p, i) => (
        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px', background: 'var(--bg-surface)', border: `1px solid ${p.is_default ? 'var(--accent)' : 'var(--border)'}`, borderRadius: 8, marginBottom: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 24 }}>🖨️</span>
            <div>
              <div style={{ fontWeight: 600, fontSize: 12 }}>{p.name}</div>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{p.driver || 'Auto'} • {p.status || 'Bereit'}</div>
            </div>
          </div>
          {p.is_default && <span style={{ fontSize: 10, color: 'var(--accent)' }}>✓ Standard</span>}
        </div>
      ))}
    </TabSection>
  )
}

function StorageTab({ data }) {
  if (!data) return <div style={{ color: 'var(--text-secondary)' }}>Lade…</div>
  return (
    <TabSection title="💽 Speicher & Laufwerke">
      {(data.disks || []).map((d, i) => {
        const usedPct = d.total_gb > 0 ? Math.round((d.used_gb / d.total_gb) * 100) : 0
        return (
          <div key={i} style={{ padding: 14, background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 8, marginBottom: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 20 }}>{d.type === 'ssd' ? '💾' : d.type === 'nvme' ? '⚡' : d.removable ? '📀' : '🖴'}</span>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 12 }}>{d.name || d.device}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{d.mount || '/'} • {d.fs || 'ext4'}</div>
                </div>
              </div>
              <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>{d.total_gb || 0} GB</span>
            </div>
            <div style={{ background: 'var(--bg-primary)', borderRadius: 4, height: 8, overflow: 'hidden' }}>
              <div style={{ height: '100%', borderRadius: 4, background: usedPct > 90 ? '#ef4444' : usedPct > 70 ? '#f59e0b' : 'var(--accent)', width: `${usedPct}%`, transition: 'width 0.3s' }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }}>
              <span>{d.used_gb || 0} GB belegt</span>
              <span>{d.free_gb || 0} GB frei ({usedPct}%)</span>
            </div>
          </div>
        )
      })}
      {(data.disks || []).length === 0 && <div style={{ color: 'var(--text-secondary)', fontSize: 12, textAlign: 'center', padding: 20 }}>Keine Laufwerke erkannt</div>}
    </TabSection>
  )
}

function UsersTab({ data, showToast }) {
  if (!data) return <div style={{ color: 'var(--text-secondary)' }}>Lade…</div>
  return (
    <TabSection title="👥 Benutzer & Gruppen">
      {(data.users || []).map((u, i) => (
        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 12px', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 6, marginBottom: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 22, width: 32, height: 32, background: 'var(--bg-elevated)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {u.is_admin ? '👑' : '👤'}
            </span>
            <div>
              <div style={{ fontWeight: 600, fontSize: 12 }}>{u.name || u.username}</div>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                {u.username} • UID {u.uid || '?'} • {u.is_admin ? 'Administrator' : 'Benutzer'}
                {u.groups && ` • ${u.groups}`}
              </div>
            </div>
          </div>
          {u.logged_in && <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e' }} title="Angemeldet" />}
        </div>
      ))}
      {(data.users || []).length === 0 && <div style={{ color: 'var(--text-secondary)', fontSize: 12, textAlign: 'center', padding: 20 }}>Keine Benutzer geladen</div>}
    </TabSection>
  )
}

function DateTimeTab({ data, onSave }) {
  if (!data) return <div style={{ color: 'var(--text-secondary)' }}>Lade…</div>
  return (
    <TabSection title="🕐 Datum & Uhrzeit">
      <div style={{ padding: 20, background: 'var(--bg-surface)', borderRadius: 8, border: '1px solid var(--border)', textAlign: 'center', marginBottom: 16 }}>
        <div style={{ fontSize: 36, fontFamily: 'var(--font-mono)', color: 'var(--accent)', fontWeight: 700 }}>
          {data.time || new Date().toLocaleTimeString('de-DE')}
        </div>
        <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
          {data.date || new Date().toLocaleDateString('de-DE', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
        </div>
      </div>
      <ToggleField label="Automatisch einstellen" hint="Zeit und Datum über NTP-Server synchronisieren" value={data.ntp_enabled !== false} onChange={v => onSave('ntp_enabled', v)} />
      <div style={{ marginTop: 12 }}>
        <label style={labelStyle}>Zeitzone</label>
        <select value={data.timezone || 'Europe/Berlin'} onChange={e => onSave('timezone', e.target.value)} style={selectStyle}>
          {timezones.map(tz => <option key={tz} value={tz}>{tz}</option>)}
        </select>
      </div>
      <div style={{ marginTop: 12 }}>
        <label style={labelStyle}>Uhrzeitformat</label>
        <select value={data.time_format || '24h'} onChange={e => onSave('time_format', e.target.value)} style={selectStyle}>
          <option value="24h">24-Stunden (14:30)</option>
          <option value="12h">12-Stunden (2:30 PM)</option>
        </select>
      </div>
    </TabSection>
  )
}

function NotificationsTab({ user, saveUser }) {
  return (
    <TabSection title="🔔 Benachrichtigungen">
      <ToggleField label="Benachrichtigungen" hint="Desktop-Benachrichtigungen aktivieren" value={user.preferences?.notifications !== false} onChange={v => saveUser({ preferences: { notifications: v } })} />
      <ToggleField label="Sound bei Benachrichtigung" hint="Akustisches Signal abspielen" value={user.preferences?.notification_sound !== false} onChange={v => saveUser({ preferences: { notification_sound: v } })} />
      <ToggleField label="Bitte nicht stören" hint="Alle Benachrichtigungen unterdrücken" value={user.preferences?.do_not_disturb || false} onChange={v => saveUser({ preferences: { do_not_disturb: v } })} />
      <ToggleField label="Ghost-Events anzeigen" hint="Benachrichtigungen bei Ghost-Aktionen" value={user.preferences?.notify_ghost !== false} onChange={v => saveUser({ preferences: { notify_ghost: v } })} />
      <ToggleField label="System-Warnungen" hint="Kritische Systemwarnungen anzeigen" value={user.preferences?.notify_system !== false} onChange={v => saveUser({ preferences: { notify_system: v } })} />
      <ToggleField label="Update-Hinweise" hint="Über verfügbare Updates informieren" value={user.preferences?.notify_updates !== false} onChange={v => saveUser({ preferences: { notify_updates: v } })} />
    </TabSection>
  )
}

function UpdatesTab({ data, showToast }) {
  if (!data) return <div style={{ color: 'var(--text-secondary)' }}>Lade…</div>
  const [checking, setChecking] = useState(false)
  const handleCheck = async () => {
    setChecking(true)
    try { await api.linuxSettingsAction('updates', 'check'); showToast('Prüfe auf Updates…') } catch { showToast('Fehler', false) }
    setTimeout(() => setChecking(false), 5000)
  }
  return (
    <TabSection title="🔄 System-Updates">
      <div style={{ padding: 16, background: 'var(--bg-surface)', borderRadius: 8, border: '1px solid var(--border)', marginBottom: 16, textAlign: 'center' }}>
        <div style={{ fontSize: 36 }}>{data.updates_available ? '📦' : '✅'}</div>
        <div style={{ fontSize: 14, fontWeight: 600, color: data.updates_available ? '#f59e0b' : '#22c55e', marginTop: 8 }}>
          {data.updates_available ? `${data.update_count || 0} Updates verfügbar` : 'System ist aktuell'}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
          Letzte Prüfung: {data.last_check || 'Noch nie'}
        </div>
        <button onClick={handleCheck} disabled={checking} style={{ ...btnStyle, background: 'rgba(0,255,204,0.1)', border: '1px solid var(--accent)', color: 'var(--accent)', marginTop: 12 }}>
          {checking ? '⏳ Prüfe…' : '🔍 Jetzt prüfen'}
        </button>
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>GhostShell Version</label>
        <div style={{ padding: 10, background: 'var(--bg-surface)', borderRadius: 6, border: '1px solid var(--border)', fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>
          {data.ghost_version || 'v0.8.0'} • Kernel {data.kernel_version || '6.1.0-44'}
        </div>
      </div>
      <ToggleField label="Automatische Updates" hint="Sicherheitsupdates automatisch installieren" value={data.auto_update || false} onChange={() => {}} />
    </TabSection>
  )
}

function SecurityTab({ data, onSave }) {
  if (!data) return <div style={{ color: 'var(--text-secondary)' }}>Lade…</div>
  return (
    <TabSection title="🔒 Sicherheit & Datenschutz">
      <ToggleField label="Firewall (ufw)" hint="Netzwerk-Firewall aktivieren" value={data.firewall_enabled || false} onChange={v => onSave('firewall_enabled', v)} />
      <ToggleField label="SSH-Zugang" hint="Remote-Zugriff über SSH erlauben" value={data.ssh_enabled || false} onChange={v => onSave('ssh_enabled', v)} />
      <ToggleField label="Automatische Bildschirmsperre" hint="Bildschirm nach Inaktivität sperren" value={data.screen_lock !== false} onChange={v => onSave('screen_lock', v)} />
      <div style={{ marginTop: 12 }}>
        <label style={labelStyle}>Bildschirm sperren nach</label>
        <select value={data.lock_timeout || '5'} onChange={e => onSave('lock_timeout', e.target.value)} style={selectStyle}>
          <option value="1">1 Minute</option><option value="2">2 Minuten</option><option value="5">5 Minuten</option><option value="10">10 Minuten</option><option value="15">15 Minuten</option><option value="30">30 Minuten</option>
        </select>
      </div>
      <div style={{ marginTop: 16 }}>
        <h4 style={{ color: 'var(--accent)', fontSize: 12, marginBottom: 8 }}>Zertifikate & Schlüssel</h4>
        <InfoCard icon="🔑" label="SSH-Schlüssel" value={data.ssh_keys_count || 0} />
        <InfoCard icon="📜" label="TLS-Zertifikate" value={data.certs_count || 0} />
        <InfoCard icon="🛡️" label="GPG-Schlüssel" value={data.gpg_keys_count || 0} />
      </div>
    </TabSection>
  )
}

function AccessibilityTab({ user, saveUser }) {
  return (
    <TabSection title="♿ Barrierefreiheit">
      <ToggleField label="Hoher Kontrast" hint="Erhöhter Kontrast für bessere Lesbarkeit" value={user.preferences?.high_contrast || false} onChange={v => saveUser({ preferences: { high_contrast: v } })} />
      <ToggleField label="Große Schrift" hint="Systemweite Schriftvergrößerung" value={user.preferences?.large_text || false} onChange={v => saveUser({ preferences: { large_text: v } })} />
      <ToggleField label="Animationen reduzieren" hint="Weniger Bewegungseffekte" value={user.preferences?.reduce_motion || false} onChange={v => saveUser({ preferences: { reduce_motion: v } })} />
      <ToggleField label="Bildschirmtastatur" hint="Virtuelle Tastatur bei Bedarf einblenden" value={user.preferences?.on_screen_keyboard || false} onChange={v => saveUser({ preferences: { on_screen_keyboard: v } })} />
      <ToggleField label="Screenreader" hint="Bildschirminhalt vorlesen (TTS)" value={user.preferences?.screen_reader || false} onChange={v => saveUser({ preferences: { screen_reader: v } })} />
      <div style={{ marginTop: 12 }}>
        <label style={labelStyle}>Zeigergröße</label>
        <select value={user.preferences?.cursor_size || 'default'} onChange={e => saveUser({ preferences: { cursor_size: e.target.value } })} style={selectStyle}>
          <option value="small">Klein</option><option value="default">Standard</option><option value="large">Groß</option><option value="xlarge">Sehr groß</option>
        </select>
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
const layoutNames = { de:'Deutsch', us:'Englisch (US)', fr:'Französisch', es:'Spanisch', it:'Italienisch', ru:'Russisch', ar:'Arabisch', jp:'Japanisch', kr:'Koreanisch', zh:'Chinesisch', tr:'Türkisch', gb:'Englisch (UK)', pt:'Portugiesisch', pl:'Polnisch', nl:'Niederländisch', sv:'Schwedisch' }
const labelStyle = { fontSize: 11, fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: 4 }
const inputStyle = { padding: '7px 10px', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-primary)', fontSize: 12, fontFamily: 'var(--font-mono)', width: '100%', boxSizing: 'border-box' }
const selectStyle = { padding: '7px 10px', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-primary)', fontSize: 12, width: '100%' }
const btnStyle = { padding: '7px 16px', borderRadius: 6, cursor: 'pointer', fontSize: 12, border: 'none' }
const thStyle = { padding: '6px 8px', textAlign: 'left', color: 'var(--text-secondary)', fontSize: 10, fontWeight: 600 }
const tdStyle = { padding: '6px 8px', color: 'var(--text-primary)' }

/** App-Einstellungen — Alle registrierten Apps und ihre Settings */
function AllAppSettingsTab() {
  const [apps, setApps] = useState([])
  const [selectedApp, setSelectedApp] = useState(null)
  const [appSchemas, setAppSchemas] = useState({})
  const [appSettingsData, setAppSettingsData] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadApps()
  }, [])

  const loadApps = async () => {
    setLoading(true)
    try {
      const all = await api.allAppSettings()
      setApps(all || [])
    } catch (e) { console.error('App settings laden:', e) }
    setLoading(false)
  }

  const loadAppSettings = async (appId) => {
    if (appSchemas[appId]) {
      setSelectedApp(appId)
      return
    }
    try {
      const [schemaRes, settingsRes] = await Promise.all([
        api.appSettingsSchema(appId),
        api.appSettings(appId),
      ])
      setAppSchemas(prev => ({ ...prev, [appId]: schemaRes.schema || {} }))
      setAppSettingsData(prev => ({ ...prev, [appId]: settingsRes.settings || {} }))
      setSelectedApp(appId)
    } catch (e) { console.error('App settings laden:', e) }
  }

  const updateSetting = async (appId, key, value) => {
    setAppSettingsData(prev => ({
      ...prev,
      [appId]: { ...prev[appId], [key]: value }
    }))
    try {
      await api.appSettingsUpdate(appId, { [key]: value })
    } catch (e) { console.error('Setting speichern:', e) }
  }

  const resetApp = async (appId) => {
    try {
      await api.appSettingsReset(appId)
      const settingsRes = await api.appSettings(appId)
      setAppSettingsData(prev => ({ ...prev, [appId]: settingsRes.settings || {} }))
    } catch (e) { console.error('Reset fehlgeschlagen:', e) }
  }

  if (loading) return <div style={{ padding: 20, color: 'var(--text-secondary)' }}>Lade App-Einstellungen...</div>

  const selectedAppObj = apps.find(a => a.app_id === selectedApp)

  return (
    <div>
      <h2 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 700 }}>📱 App-Einstellungen</h2>
      <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '0 0 16px' }}>Individuelle Einstellungen für jede installierte App.</p>

      <div style={{ display: 'flex', gap: 16 }}>
        {/* App Liste */}
        <div style={{ width: 200, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {apps.map(app => (
            <div
              key={app.app_id}
              onClick={() => loadAppSettings(app.app_id)}
              style={{
                padding: '8px 12px', borderRadius: 6, cursor: 'pointer',
                background: selectedApp === app.app_id ? 'rgba(0,255,204,0.1)' : 'transparent',
                border: selectedApp === app.app_id ? '1px solid var(--accent)' : '1px solid transparent',
                display: 'flex', alignItems: 'center', gap: 8,
                transition: 'all 0.15s',
              }}
            >
              <span style={{ fontSize: 16 }}>{app.icon || '📱'}</span>
              <div>
                <div style={{ fontSize: 12, fontWeight: 500, color: selectedApp === app.app_id ? 'var(--accent)' : 'var(--text-primary)' }}>
                  {app.display_name || app.app_id}
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                  {app.has_settings ? '⚙️ Konfigurierbar' : '— Standard'}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Settings Panel */}
        <div style={{ flex: 1, minHeight: 300 }}>
          {selectedApp && appSchemas[selectedApp] ? (
            <AppSettingsPanel
              schema={appSchemas[selectedApp]}
              settings={appSettingsData[selectedApp] || {}}
              onUpdate={(key, value) => updateSetting(selectedApp, key, value)}
              onReset={() => resetApp(selectedApp)}
              title={selectedAppObj?.display_name || selectedApp}
            />
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-secondary)', flexDirection: 'column', gap: 8 }}>
              <span style={{ fontSize: 32 }}>📱</span>
              <span style={{ fontSize: 13 }}>Wähle eine App aus der Liste</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
