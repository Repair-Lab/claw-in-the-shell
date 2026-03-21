import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

/* ─────────── Hilfsfunktionen ─────────── */
const fmtDate = (d) => d ? new Date(d).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'
const severity = (s) => ({ critical: '#ff2255', high: '#ff4444', medium: '#ffaa00', low: '#4488ff', info: '#6688aa' }[s] || '#556')
const pct = (v) => v != null ? `${Math.round(v)}%` : '—'
const riskColor = (r) => ({ critical: '#ff2255', high: '#ff4444', medium: '#ffaa00', low: '#4488ff', info: '#6688aa' }[r] || '#556')

export default function FirewallManager() {
  const { settings, schema, update, reset } = useAppSettings('firewall_manager')
  const [showSettings, setShowSettings] = useState(false)

  /* ── Firewall (orig) ── */
  const [rules, setRules] = useState([])
  const [zones, setZones] = useState([])
  const [connections, setConnections] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [newRule, setNewRule] = useState({ chain: 'INPUT', protocol: 'tcp', port: '', source_ip: '', action: 'DROP', description: '' })

  /* ── Security ── */
  const [secStatus, setSecStatus] = useState(null)
  const [vulns, setVulns] = useState([])
  const [vulnFilter, setVulnFilter] = useState('open')
  const [intrusions, setIntrusions] = useState([])
  const [intrusionHours, setIntrusionHours] = useState(24)
  const [bans, setBans] = useState([])
  const [newBan, setNewBan] = useState({ ip: '', reason: '', hours: 24 })
  const [showBanForm, setShowBanForm] = useState(false)
  const [scans, setScans] = useState([])
  const [threats, setThreats] = useState([])
  const [threatLookup, setThreatLookup] = useState('')
  const [threatResult, setThreatResult] = useState(null)
  const [baselines, setBaselines] = useState([])
  const [responses, setResponses] = useState([])
  const [honeypot, setHoneypot] = useState([])
  const [honeypotHours, setHoneypotHours] = useState(24)
  const [failedAuth, setFailedAuth] = useState([])
  const [authHours, setAuthHours] = useState(24)

  /* ── Security-AI ── */
  const [aiStatus, setAiStatus] = useState(null)
  const [aiTasks, setAiTasks] = useState([])
  const [aiLog, setAiLog] = useState([])
  const [aiConfig, setAiConfig] = useState([])
  const [aiAnalyzeType, setAiAnalyzeType] = useState('risk_scoring')
  const [aiAnalyzeIp, setAiAnalyzeIp] = useState('')
  const [ghostRoles, setGhostRoles] = useState([])
  const [ghostModels, setGhostModels] = useState([])
  const [aiProcessing, setAiProcessing] = useState(false)
  const [aiActiveTaskId, setAiActiveTaskId] = useState(null)
  const [aiResult, setAiResult] = useState(null)
  const [ghostSwapping, setGhostSwapping] = useState(false)

  /* ── Zusätzliche Subsysteme ── */
  const [tls, setTls] = useState([])
  const [cves, setCves] = useState([])
  const [sinkhole, setSinkhole] = useState([])
  const [newSinkhole, setNewSinkhole] = useState({ domain: '', reason: '' })
  const [showSinkholeForm, setShowSinkholeForm] = useState(false)
  const [rateLimits, setRateLimits] = useState([])
  const [networkTraffic, setNetworkTraffic] = useState([])
  const [trafficHours, setTrafficHours] = useState(1)
  const [permissions, setPermissions] = useState([])
  const [metrics, setMetrics] = useState([])

  const [tab, setTab] = useState('dashboard')
  const [msg, setMsg] = useState(null)

  /* ── Loader ── */
  const flash = (m, ok = true) => { setMsg({ text: m, ok }); setTimeout(() => setMsg(null), 3000) }

  const loadFirewall = useCallback(async () => {
    try {
      const [r, z, c] = await Promise.all([api.firewallRules(), api.firewallZones(), api.firewallConnections()])
      setRules(r.rules || [])
      setZones(z.zones || [])
      setConnections(c.connections || [])
    } catch { /* */ }
  }, [])

  const loadDashboard = useCallback(async () => {
    try { const s = await api.securityStatus(); setSecStatus(s) } catch { setSecStatus(null) }
  }, [])
  const loadVulns = useCallback(async () => {
    try { const d = await api.securityVulnerabilities(vulnFilter); setVulns(d.vulnerabilities || d || []) } catch { setVulns([]) }
  }, [vulnFilter])
  const loadIntrusions = useCallback(async () => {
    try { const d = await api.securityIntrusions(intrusionHours); setIntrusions(d.intrusions || d.events || d || []) } catch { setIntrusions([]) }
  }, [intrusionHours])
  const loadBans = useCallback(async () => {
    try { const d = await api.securityBans(); setBans(d.bans || d || []) } catch { setBans([]) }
  }, [])
  const loadScans = useCallback(async () => {
    try { const d = await api.securityScans(); setScans(d.scans || d || []) } catch { setScans([]) }
  }, [])
  const loadThreats = useCallback(async () => {
    try { const d = await api.securityThreats(); setThreats(d.threats || d || []) } catch { setThreats([]) }
  }, [])
  const loadBaselines = useCallback(async () => {
    try { const d = await api.securityBaselines(); setBaselines(d.baselines || d || []) } catch { setBaselines([]) }
  }, [])
  const loadResponses = useCallback(async () => {
    try { const d = await api.securityResponses(50); setResponses(d.responses || d || []) } catch { setResponses([]) }
  }, [])
  const loadHoneypot = useCallback(async () => {
    try { const d = await api.securityHoneypot(honeypotHours); setHoneypot(d.honeypot_events || d.events || d || []) } catch { setHoneypot([]) }
  }, [honeypotHours])
  const loadFailedAuth = useCallback(async () => {
    try { const d = await api.securityFailedAuth(authHours); setFailedAuth(d.failed_auth || d.events || d || []) } catch { setFailedAuth([]) }
  }, [authHours])

  /* ── Security-AI Loader ── */
  const loadAiStatus = useCallback(async () => {
    try { const d = await api.securityAiStatus(); setAiStatus(d) } catch { setAiStatus(null) }
  }, [])
  const loadAiTasks = useCallback(async () => {
    try { const d = await api.securityAiTasks(null, 30); setAiTasks(d.tasks || []) } catch { setAiTasks([]) }
  }, [])
  const loadAiLog = useCallback(async () => {
    try { const d = await api.securityAiLog(30); setAiLog(d.log || []) } catch { setAiLog([]) }
  }, [])
  const loadAiConfig = useCallback(async () => {
    try { const d = await api.securityAiConfig(); setAiConfig(d.config || []) } catch { setAiConfig([]) }
  }, [])
  const loadGhostInfo = useCallback(async () => {
    try {
      const [r, m] = await Promise.all([api.securityGhostRoles(), api.securityGhostModels()])
      setGhostRoles(r.roles || [])
      setGhostModels(m.models || [])
    } catch { /* */ }
  }, [])

  /* ── Subsystem-Loader ── */
  const loadTls = useCallback(async () => {
    try { const d = await api.securityTls(); setTls(d.certificates || []) } catch { setTls([]) }
  }, [])
  const loadCves = useCallback(async () => {
    try { const d = await api.securityCve(); setCves(d.cves || []) } catch { setCves([]) }
  }, [])
  const loadSinkhole = useCallback(async () => {
    try { const d = await api.securityDnsSinkhole(); setSinkhole(d.sinkhole || []) } catch { setSinkhole([]) }
  }, [])
  const loadRateLimits = useCallback(async () => {
    try { const d = await api.securityRateLimits(); setRateLimits(d.rate_limits || []) } catch { setRateLimits([]) }
  }, [])
  const loadNetworkTraffic = useCallback(async () => {
    try { const d = await api.securityNetworkTraffic(trafficHours); setNetworkTraffic(d.traffic || []) } catch { setNetworkTraffic([]) }
  }, [trafficHours])
  const loadPermissions = useCallback(async () => {
    try { const d = await api.securityPermissions(); setPermissions(d.permissions || []) } catch { setPermissions([]) }
  }, [])
  const loadMetrics = useCallback(async () => {
    try { const d = await api.securityMetrics(); setMetrics(d.metrics || []) } catch { setMetrics([]) }
  }, [])

  /* initial load */
  useEffect(() => { loadFirewall(); loadDashboard() }, [loadFirewall, loadDashboard])

  /* tab-specific loads */
  useEffect(() => {
    const m = {
      rules: loadFirewall, zones: loadFirewall, connections: loadFirewall,
      dashboard: loadDashboard, vulns: loadVulns, intrusions: loadIntrusions,
      bans: loadBans, scans: loadScans, threats: loadThreats,
      baselines: loadBaselines, responses: loadResponses,
      honeypot: loadHoneypot, auth: loadFailedAuth,
      ai: () => { loadAiStatus(); loadAiTasks(); loadAiLog(); loadGhostInfo() },
      aiConfig: loadAiConfig,
      tls: loadTls, cve: loadCves, sinkhole: loadSinkhole,
      ratelimit: loadRateLimits, traffic: loadNetworkTraffic,
      perms: loadPermissions, metrics: loadMetrics,
    }
    m[tab]?.()
  }, [tab, loadFirewall, loadDashboard, loadVulns, loadIntrusions, loadBans, loadScans, loadThreats, loadBaselines, loadResponses, loadHoneypot, loadFailedAuth, loadAiStatus, loadAiTasks, loadAiLog, loadAiConfig, loadGhostInfo, loadTls, loadCves, loadSinkhole, loadRateLimits, loadNetworkTraffic, loadPermissions, loadMetrics])

  /* ── Actions ── */
  const addRule = async () => {
    if (!newRule.port && !newRule.source_ip) return
    try { await api.firewallAddRule(newRule); setShowAdd(false); setNewRule({ chain: 'INPUT', protocol: 'tcp', port: '', source_ip: '', action: 'DROP', description: '' }); flash('Regel hinzugefügt'); await loadFirewall() } catch { flash('Fehler', false) }
  }
  const applyRules = async () => { try { await api.firewallApply(); flash('Firewall-Regeln angewendet') } catch { flash('Fehler', false) } }
  const deleteRule = async (id) => { if (!confirm('Regel wirklich löschen?')) return; try { await api.firewallDeleteRule(id); flash('Gelöscht'); await loadFirewall() } catch { flash('Fehler', false) } }
  const mitigateVuln = async (id) => { try { await api.securityMitigateVuln(id); flash('Schwachstelle mitigiert'); loadVulns() } catch { flash('Fehler', false) } }
  const banIp = async () => {
    if (!newBan.ip) return
    try { await api.securityBanIp(newBan.ip, newBan.reason || 'Manueller Ban', newBan.hours); setShowBanForm(false); setNewBan({ ip: '', reason: '', hours: 24 }); flash('IP gebannt'); loadBans() } catch { flash('Fehler', false) }
  }
  const unbanIp = async (id) => { if (!confirm('Ban aufheben?')) return; try { await api.securityUnban(id); flash('Ban aufgehoben'); loadBans() } catch { flash('Fehler', false) } }
  const lookupThreat = async () => {
    if (!threatLookup) return
    try { const d = await api.securityThreatScore(threatLookup); setThreatResult(d) } catch { setThreatResult({ error: 'Nicht gefunden' }) }
  }

  /* ── AI Actions ── */
  const triggerAiAnalysis = async () => {
    try {
      setAiProcessing(true); setAiResult(null)
      const d = await api.securityAiAnalyze(aiAnalyzeType)
      flash(`KI-Analyse gestartet mit ${d.model || 'LLM'}: ${d.task_id?.substring(0,8)}`)
      setAiActiveTaskId(d.task_id)
      // Auto-Polling starten
      _pollTask(d.task_id)
    } catch (e) {
      setAiProcessing(false)
      flash(e?.message?.includes('503') ? 'LLM-Server nicht aktiv — erst Modell laden!' : 'Fehler', false)
    }
  }
  const triggerIpAnalysis = async () => {
    if (!aiAnalyzeIp) return
    try {
      setAiProcessing(true); setAiResult(null)
      const d = await api.securityAiAnalyzeIp(aiAnalyzeIp)
      flash(`IP-Analyse für ${aiAnalyzeIp} gestartet mit ${d.model || 'LLM'}`)
      setAiActiveTaskId(d.task_id); setAiAnalyzeIp('')
      _pollTask(d.task_id)
    } catch (e) {
      setAiProcessing(false)
      flash(e?.message?.includes('503') ? 'LLM-Server nicht aktiv — erst Modell laden!' : 'Fehler', false)
    }
  }
  const _pollTask = async (taskId) => {
    // Poll alle 2 Sekunden bis completed/failed
    for (let i = 0; i < 90; i++) {
      await new Promise(r => setTimeout(r, 2000))
      try {
        const d = await api.securityAiTaskDetail(taskId)
        if (d.task?.state === 'completed') {
          setAiResult(d.task)
          setAiProcessing(false); setAiActiveTaskId(null)
          loadAiTasks(); loadAiLog(); loadAiStatus()
          flash(`✅ Analyse fertig — Risiko: ${d.task.risk_level || 'info'}`)
          return
        } else if (d.task?.state === 'failed') {
          setAiResult(d.task)
          setAiProcessing(false); setAiActiveTaskId(null)
          loadAiTasks()
          flash(`❌ Analyse fehlgeschlagen: ${d.task.error_message?.substring(0,80) || 'Unbekannt'}`, false)
          return
        }
      } catch { /* weiter pollen */ }
    }
    setAiProcessing(false); setAiActiveTaskId(null)
    flash('⏱ Analyse-Timeout nach 3 Minuten', false)
    loadAiTasks()
  }
  const updateAiConfig = async (key, value) => {
    try { await api.securityAiConfigUpdate(key, value); flash('Config aktualisiert'); loadAiConfig() } catch { flash('Fehler', false) }
  }
  const swapGhost = async (modelName) => {
    try {
      setGhostSwapping(true)
      flash(`Lade ${modelName}... (kann 30-120s dauern)`)
      const d = await api.securityGhostSwap(modelName, 'UI — Security-Modellwechsel')
      if (d.model_loaded) {
        flash(`✅ ${d.display_name || modelName} geladen — Security-Ghost bereit`)
      } else if (d.status === 'error') {
        flash(`❌ Modell konnte nicht geladen werden: ${d.error || ''}`, false)
      } else {
        flash(`⚠ DB aktualisiert, aber Modell nicht physisch geladen`, false)
      }
      loadAiStatus(); loadGhostInfo()
    } catch { flash('Ghost-Swap fehlgeschlagen', false) } finally { setGhostSwapping(false) }
  }
  const addSinkholeRule = async () => {
    if (!newSinkhole.domain) return
    try { await api.securityDnsSinkholeAdd(newSinkhole.domain, newSinkhole.reason || 'Manuell'); setShowSinkholeForm(false); setNewSinkhole({ domain: '', reason: '' }); flash('Sinkhole-Regel hinzugefügt'); loadSinkhole() } catch { flash('Fehler', false) }
  }
  const deleteSinkholeRule = async (id) => { try { await api.securityDnsSinkholeDelete(id); flash('Deaktiviert'); loadSinkhole() } catch { flash('Fehler', false) } }

  /* ── Styles ── */
  const actionColors = { ACCEPT: '#00ffcc', DROP: '#ff4444', REJECT: '#ffaa00', LOG: '#4488ff' }
  const stateColors = { ESTABLISHED: '#00ffcc', TIME_WAIT: '#ffaa00', LISTEN: '#4488ff', CLOSE_WAIT: '#ff4444' }

  const S = {
    container: { display: 'flex', flexDirection: 'column', height: '100%', background: '#0a0a14', color: '#c8d6e5', padding: '16px', overflow: 'auto', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' },
    h: { color: '#00ffcc', fontSize: '18px', fontWeight: 700, marginBottom: '0', display: 'flex', alignItems: 'center', gap: '8px' },
    card: { background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '8px', padding: '12px', marginBottom: '8px' },
    btn: { padding: '6px 16px', border: '1px solid #00ffcc', background: 'transparent', color: '#00ffcc', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', transition: 'all .15s' },
    btnDanger: { padding: '6px 16px', border: '1px solid #ff4444', background: 'transparent', color: '#ff4444', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' },
    btnWarn: { padding: '6px 16px', border: '1px solid #ffaa00', background: 'transparent', color: '#ffaa00', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' },
    btnMuted: { padding: '6px 16px', border: '1px solid #334', background: 'transparent', color: '#556', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' },
    btnAi: { padding: '6px 16px', border: '1px solid #a855f7', background: 'rgba(168,85,247,0.08)', color: '#a855f7', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: 600 },
    tab: (active) => ({ padding: '5px 12px', border: '1px solid', borderColor: active ? '#00ffcc' : '#1a2a3a', background: active ? 'rgba(0,255,204,0.1)' : 'transparent', color: active ? '#00ffcc' : '#556', borderRadius: '6px', cursor: 'pointer', fontSize: '11px', whiteSpace: 'nowrap' }),
    tabAi: (active) => ({ padding: '5px 12px', border: '1px solid', borderColor: active ? '#a855f7' : '#1a2a3a', background: active ? 'rgba(168,85,247,0.12)' : 'transparent', color: active ? '#a855f7' : '#556', borderRadius: '6px', cursor: 'pointer', fontSize: '11px', whiteSpace: 'nowrap', fontWeight: active ? 600 : 400 }),
    input: { padding: '6px 10px', background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '6px', color: '#d4d4d4', fontSize: '12px', outline: 'none' },
    select: { padding: '6px 10px', background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '6px', color: '#d4d4d4', fontSize: '12px', outline: 'none' },
    th: { padding: '6px 8px', color: '#6688aa', fontSize: '11px', textAlign: 'left', borderBottom: '1px solid #1a2a3a', fontWeight: 600 },
    td: { padding: '6px 8px', fontSize: '12px', borderBottom: '1px solid #111828' },
    badge: (color) => ({ display: 'inline-block', padding: '2px 8px', borderRadius: '10px', fontSize: '10px', fontWeight: 600, background: `${color}18`, color, border: `1px solid ${color}44` }),
    label: { fontSize: '11px', color: '#6688aa', fontWeight: 600, marginBottom: '4px', display: 'block' },
    metric: { textAlign: 'center', padding: '12px' },
    metricVal: { fontSize: '28px', fontWeight: 700, fontFamily: 'monospace' },
    metricLabel: { fontSize: '11px', color: '#6688aa', marginTop: '4px' },
    empty: { textAlign: 'center', padding: '24px', color: '#334', fontSize: '13px' },
    grid3: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px', marginBottom: '12px' },
    grid4: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '8px', marginBottom: '12px' },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' },
    aiGlow: { boxShadow: '0 0 12px rgba(168,85,247,0.15)', borderColor: '#a855f744' },
  }

  /* ── Tab-Definitionen ── */
  const tabs = [
    ['dashboard', '🛡️ Dashboard'],
    ['ai', '🤖 KI-Monitor'],
    ['aiConfig', '⚙️ KI-Config'],
    ['rules', '📜 Regeln'],
    ['zones', '🌐 Zonen'],
    ['connections', '🔌 Verbindungen'],
    ['vulns', '🔍 Schwachstellen'],
    ['intrusions', '🚨 IDS'],
    ['bans', '🚫 IP-Bans'],
    ['scans', '📡 Scans'],
    ['threats', '☠️ Bedrohungen'],
    ['baselines', '📋 Baselines'],
    ['responses', '⚡ Responses'],
    ['honeypot', '🍯 Honeypot'],
    ['auth', '🔐 Auth-Log'],
    ['tls', '🔒 TLS'],
    ['cve', '🐛 CVE'],
    ['sinkhole', '🕳️ DNS-Sinkhole'],
    ['ratelimit', '⏱️ Rate-Limits'],
    ['traffic', '📶 Traffic'],
    ['perms', '🔑 Berechtigungen'],
    ['metrics', '📊 Metriken'],
  ]

  /* helper: config value */
  const cfgVal = (key) => {
    const c = aiConfig.find(x => x.key === key)
    if (!c) return '—'
    const v = c.value
    if (typeof v === 'object') return JSON.stringify(v)
    return String(v).replace(/^"|"$/g, '')
  }

  /* ─────────────────────── RENDER ─────────────────────── */
  return (
    <div style={S.container}>
      {/* CSS Animationen für KI-Processing */}
      <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
      `}</style>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div style={S.h}>🛡️ Firewall & Security-Immunsystem</div>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          {msg && <span style={{ fontSize: '11px', color: msg.ok ? '#00ffcc' : '#ff4444', padding: '4px 10px', background: msg.ok ? 'rgba(0,255,204,0.08)' : 'rgba(255,68,68,0.08)', borderRadius: '6px' }}>{msg.text}</span>}
          <button style={{ ...S.btn, padding: '4px 10px' }} onClick={() => setShowSettings(!showSettings)}>⚙️</button>
        </div>
      </div>
      {showSettings && <AppSettingsPanel settings={settings} schema={schema} onUpdate={update} onReset={reset} />}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '16px', flexWrap: 'wrap' }}>
        {tabs.map(([k, l]) => {
          const isAi = k === 'ai' || k === 'aiConfig'
          return <button key={k} style={isAi ? S.tabAi(tab === k) : S.tab(tab === k)} onClick={() => setTab(k)}>{l}</button>
        })}
      </div>

      {/* ═══════════ DASHBOARD ═══════════ */}
      {tab === 'dashboard' && (
        <>
          {secStatus ? (
            <>
              <div style={S.grid4}>
                {[
                  ['Security-Score', pct(secStatus.security?.compliance_pct || secStatus.security_score), (secStatus.security?.compliance_pct || secStatus.security_score || 0) > 70 ? '#00ffcc' : '#ffaa00'],
                  ['Offene Schwachstellen', secStatus.security?.open_vulns ?? secStatus.open_vulnerabilities ?? '—', '#ff4444'],
                  ['Aktive IP-Bans', secStatus.security?.active_bans ?? secStatus.active_bans ?? '—', '#ffaa00'],
                  ['Intrusions (24h)', secStatus.security?.ids_24h ?? secStatus.intrusions_24h ?? '—', '#4488ff'],
                ].map(([label, val, color]) => (
                  <div key={label} style={{ ...S.card, ...S.metric }}>
                    <div style={{ ...S.metricVal, color }}>{val}</div>
                    <div style={S.metricLabel}>{label}</div>
                  </div>
                ))}
              </div>
              <div style={S.grid3}>
                {[
                  ['Scans (24h)', secStatus.security?.scans_24h ?? secStatus.active_scans ?? 0, '#00ffcc'],
                  ['Firewall-Regeln', secStatus.total_rules ?? rules.length, '#6688aa'],
                  ['Threat-Indikatoren', secStatus.security?.threat_indicators ?? secStatus.threat_count ?? '—', '#d4d4d4'],
                  ['Honeypot (24h)', secStatus.security?.honeypot_24h ?? 0, '#ffaa00'],
                  ['Auth-Fails (24h)', secStatus.security?.failed_auth_24h ?? 0, '#ff4444'],
                ].map(([label, val, color]) => (
                  <div key={label} style={{ ...S.card, ...S.metric }}>
                    <div style={{ ...S.metricVal, color, fontSize: '22px' }}>{val}</div>
                    <div style={S.metricLabel}>{label}</div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div style={S.empty}>
              <div style={{ fontSize: '32px', marginBottom: '8px' }}>🛡️</div>
              Lade Security-Dashboard...
              <div style={{ marginTop: '8px' }}><button style={S.btn} onClick={loadDashboard}>🔄 Aktualisieren</button></div>
            </div>
          )}
        </>
      )}

      {/* ═══════════ KI-MONITOR ═══════════ */}
      {tab === 'ai' && (
        <>
          {/* AI Ghost Status Card */}
          <div style={{ ...S.card, ...S.aiGlow, marginBottom: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <span style={{ fontSize: '22px' }}>🤖</span>
                <div>
                  <div style={{ fontWeight: 700, color: '#a855f7', fontSize: '14px' }}>Security Monitor Ghost</div>
                  <div style={{ fontSize: '11px', color: '#6688aa' }}>
                    Modell: <span style={{ color: '#d4d4d4' }}>{aiStatus?.ghost?.model_display || aiStatus?.ghost?.model_name || '—'}</span>
                    {aiStatus?.ghost?.parameter_count && <span> ({aiStatus.ghost.parameter_count})</span>}
                    {aiStatus?.ghost?.quantization && <span> [{aiStatus.ghost.quantization}]</span>}
                  </div>
                </div>
              </div>
              <span style={S.badge(aiStatus?.ghost?.ghost_state === 'active' ? '#00ffcc' : aiStatus?.ghost?.ghost_state === 'activating' ? '#ffaa00' : '#ff4444')}>
                {aiStatus?.ghost?.ghost_state || 'inaktiv'}
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '8px' }}>
              {[
                ['Ausstehend', aiStatus?.ai_status?.pending_tasks ?? 0, '#ffaa00'],
                ['In Arbeit', aiStatus?.ai_status?.processing_tasks ?? 0, '#4488ff'],
                ['Erledigt (24h)', aiStatus?.ai_status?.completed_24h ?? 0, '#00ffcc'],
                ['Auto-Aktionen (24h)', aiStatus?.ai_status?.auto_executed_24h ?? 0, '#a855f7'],
                ['Tokens (24h)', aiStatus?.ai_status?.tokens_24h ?? 0, '#d4d4d4'],
                ['Ø Latenz', `${aiStatus?.ai_status?.avg_analysis_ms ?? 0}ms`, '#6688aa'],
              ].map(([label, val, color]) => (
                <div key={label} style={{ textAlign: 'center', padding: '6px' }}>
                  <div style={{ fontSize: '18px', fontWeight: 700, color, fontFamily: 'monospace' }}>{val}</div>
                  <div style={{ fontSize: '10px', color: '#556' }}>{label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Ghost-Modell wechseln */}
          <div style={{ ...S.card, marginBottom: '12px' }}>
            <div style={{ ...S.label, marginBottom: '8px' }}>Ghost-Modell für Security-Rolle wechseln</div>
            {ghostSwapping && (
              <div style={{ padding: '8px', background: 'rgba(168,85,247,0.08)', borderRadius: '6px', marginBottom: '8px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⏳</span>
                <span style={{ color: '#a855f7', fontSize: '12px' }}>Modell wird geladen... (GPU VRAM wird allokiert, kann 30-120s dauern)</span>
              </div>
            )}
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {ghostModels.map(m => (
                <button key={m.name} disabled={ghostSwapping} style={{
                  ...S.btn,
                  borderColor: (aiStatus?.ghost?.model_name === m.name) ? '#a855f7' : '#1a2a3a',
                  color: (aiStatus?.ghost?.model_name === m.name) ? '#a855f7' : '#556',
                  background: (aiStatus?.ghost?.model_name === m.name) ? 'rgba(168,85,247,0.08)' : 'transparent',
                  fontSize: '11px', padding: '4px 10px',
                  opacity: ghostSwapping ? 0.5 : 1, cursor: ghostSwapping ? 'wait' : 'pointer',
                }} onClick={() => swapGhost(m.name)}>
                  {m.display_name || m.name} {m.parameter_count && `(${m.parameter_count})`}
                  {m.is_loaded && ' ✓'}
                </button>
              ))}
              {ghostModels.length === 0 && <span style={{ fontSize: '11px', color: '#556' }}>Keine Modelle verfügbar</span>}
            </div>
          </div>

          {/* Manuelle Analyse */}
          <div style={{ ...S.card, marginBottom: '12px' }}>
            <div style={{ ...S.label, marginBottom: '8px' }}>🔬 Manuelle KI-Analyse starten</div>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
              <select style={S.select} value={aiAnalyzeType} onChange={e => setAiAnalyzeType(e.target.value)} disabled={aiProcessing}>
                <option value="risk_scoring">🎯 Risikobewertung</option>
                <option value="periodic_report">📋 Sicherheitsbericht</option>
                <option value="baseline_audit">📋 Baseline-Audit</option>
                <option value="anomaly_detection">🔍 Anomalie-Erkennung</option>
                <option value="log_analysis">📝 Log-Analyse</option>
                <option value="policy_recommendation">📜 Policy-Empfehlung</option>
                <option value="network_forensics">🌐 Netzwerk-Forensik</option>
              </select>
              <button style={{ ...S.btnAi, opacity: aiProcessing ? 0.5 : 1, cursor: aiProcessing ? 'wait' : 'pointer' }} onClick={triggerAiAnalysis} disabled={aiProcessing}>
                {aiProcessing ? '⏳ Analysiert...' : '🤖 Analyse starten'}
              </button>
              <span style={{ color: '#1a2a3a' }}>|</span>
              <input style={{ ...S.input, width: '140px' }} value={aiAnalyzeIp} onChange={e => setAiAnalyzeIp(e.target.value)} placeholder="IP analysieren..." onKeyDown={e => e.key === 'Enter' && !aiProcessing && triggerIpAnalysis()} disabled={aiProcessing} />
              <button style={{ ...S.btnAi, opacity: aiProcessing ? 0.5 : 1 }} onClick={triggerIpAnalysis} disabled={aiProcessing}>🔎 IP-Analyse</button>
            </div>
            {aiProcessing && (
              <div style={{ marginTop: '10px', padding: '10px', background: 'rgba(168,85,247,0.06)', border: '1px solid rgba(168,85,247,0.2)', borderRadius: '6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '16px', animation: 'pulse 1.5s ease-in-out infinite' }}>🧠</span>
                  <div>
                    <div style={{ color: '#a855f7', fontSize: '12px', fontWeight: 600 }}>Security-Ghost analysiert...</div>
                    <div style={{ color: '#6688aa', fontSize: '11px' }}>Modell: {aiStatus?.ghost?.model_display || aiStatus?.ghost?.model_name || 'LLM'} | Task: {aiActiveTaskId?.substring(0,8) || '...'}</div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* AI Analyse-Ergebnis */}
          {aiResult && (
            <div style={{ ...S.card, marginBottom: '12px', border: `1px solid ${aiResult.state === 'completed' ? riskColor(aiResult.risk_level) : '#ff4444'}33` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <span style={{ fontSize: '16px' }}>{aiResult.state === 'completed' ? '📊' : '❌'}</span>
                  <div>
                    <span style={{ fontWeight: 700, color: aiResult.state === 'completed' ? '#00ffcc' : '#ff4444', fontSize: '13px' }}>
                      {aiResult.state === 'completed' ? 'Analyse-Ergebnis' : 'Analyse fehlgeschlagen'}
                    </span>
                    <span style={{ color: '#556', fontSize: '11px', marginLeft: '10px' }}>{aiResult.task_type} | {aiResult.processing_ms ? `${aiResult.processing_ms}ms` : '—'}</span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                  {aiResult.risk_level && <span style={S.badge(riskColor(aiResult.risk_level))}>{aiResult.risk_level}</span>}
                  {aiResult.confidence != null && <span style={{ fontSize: '11px', color: '#6688aa', fontFamily: 'monospace' }}>{Math.round(aiResult.confidence * 100)}%</span>}
                  <button style={{ ...S.btnMuted, fontSize: '10px', padding: '2px 6px' }} onClick={() => setAiResult(null)}>✕</button>
                </div>
              </div>
              {aiResult.state === 'failed' && aiResult.error_message && (
                <div style={{ color: '#ff6666', fontSize: '12px', padding: '6px', background: 'rgba(255,68,68,0.06)', borderRadius: '4px' }}>
                  {aiResult.error_message}
                </div>
              )}
              {aiResult.ai_assessment && (
                <div style={{ fontSize: '12px', color: '#c8d6e5', lineHeight: '1.5', maxHeight: '300px', overflow: 'auto', padding: '8px', background: '#080c14', borderRadius: '4px', whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>
                  {aiResult.ai_assessment}
                </div>
              )}
              {aiResult.recommended_actions && aiResult.recommended_actions.length > 0 && (
                <div style={{ marginTop: '8px' }}>
                  <div style={{ fontSize: '11px', color: '#a855f7', fontWeight: 600, marginBottom: '4px' }}>Empfohlene Aktionen:</div>
                  {(typeof aiResult.recommended_actions === 'string' ? JSON.parse(aiResult.recommended_actions) : aiResult.recommended_actions).map((a, i) => (
                    <div key={i} style={{ fontSize: '11px', color: '#c8d6e5', padding: '3px 6px', background: 'rgba(168,85,247,0.06)', borderRadius: '3px', marginBottom: '3px' }}>
                      <span style={{ color: '#ffaa00' }}>{a.action}</span> → <span style={{ color: '#d4d4d4' }}>{a.target || ''}</span> {a.reason && <span style={{ color: '#6688aa' }}>({a.reason})</span>}
                    </div>
                  ))}
                  {aiResult.auto_executed && <div style={{ fontSize: '11px', color: '#a855f7', marginTop: '4px' }}>⚡ Auto-Aktionen wurden ausgeführt</div>}
                </div>
              )}
            </div>
          )}

          {/* AI-Tasks */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <div style={S.label}>Letzte KI-Analysen</div>
            <button style={S.btnMuted} onClick={loadAiTasks}>🔄</button>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '16px' }}>
            <thead><tr>{['Zeit', 'Typ', 'Status', 'Risiko', 'Konfidenz', 'Auto', 'Dauer', 'Bewertung'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {aiTasks.map((t, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, fontSize: '11px', color: '#556', whiteSpace: 'nowrap' }}>{fmtDate(t.created_at)}</td>
                  <td style={{ ...S.td, fontSize: '11px' }}>{t.task_type}</td>
                  <td style={S.td}><span style={S.badge(t.state === 'completed' ? '#00ffcc' : t.state === 'processing' ? '#4488ff' : t.state === 'failed' ? '#ff4444' : '#ffaa00')}>{t.state}</span></td>
                  <td style={S.td}>{t.risk_level ? <span style={S.badge(riskColor(t.risk_level))}>{t.risk_level}</span> : '—'}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px' }}>{t.confidence != null ? `${Math.round(t.confidence * 100)}%` : '—'}</td>
                  <td style={S.td}>{t.auto_executed ? <span style={S.badge('#a855f7')}>Ja</span> : '—'}</td>
                  <td style={{ ...S.td, fontSize: '11px', color: '#6688aa' }}>{t.processing_ms ? `${t.processing_ms}ms` : '—'}</td>
                  <td style={{ ...S.td, fontSize: '11px', maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.ai_assessment?.substring(0, 120) || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {aiTasks.length === 0 && <div style={S.empty}>Noch keine KI-Analysen durchgeführt</div>}

          {/* AI Analysis Log */}
          {aiLog.length > 0 && (
            <>
              <div style={{ ...S.label, marginBottom: '6px' }}>Analyse-Protokoll</div>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead><tr>{['Zeit', 'Typ', 'Risiko', 'Tokens', 'Modell', 'Dauer'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
                <tbody>
                  {aiLog.map((l, i) => (
                    <tr key={i}>
                      <td style={{ ...S.td, fontSize: '11px', color: '#556' }}>{fmtDate(l.ts)}</td>
                      <td style={{ ...S.td, fontSize: '11px' }}>{l.analysis_type}</td>
                      <td style={S.td}>{l.risk_level ? <span style={S.badge(riskColor(l.risk_level))}>{l.risk_level}</span> : '—'}</td>
                      <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px' }}>{l.tokens_used || 0}</td>
                      <td style={{ ...S.td, fontSize: '11px', color: '#6688aa' }}>{l.model_name || '—'}</td>
                      <td style={{ ...S.td, fontSize: '11px' }}>{l.duration_ms ? `${l.duration_ms}ms` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </>
      )}

      {/* ═══════════ KI-CONFIG ═══════════ */}
      {tab === 'aiConfig' && (
        <>
          <div style={S.header}>
            <div style={{ fontSize: '13px', color: '#a855f7', fontWeight: 600 }}>🤖 Security-KI Konfiguration</div>
            <button style={S.btnMuted} onClick={loadAiConfig}>🔄</button>
          </div>

          {/* Schnell-Toggles */}
          <div style={{ ...S.card, ...S.aiGlow, marginBottom: '12px' }}>
            <div style={{ ...S.label, marginBottom: '10px' }}>Schnelleinstellungen</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>
              {[
                ['ai_enabled', 'KI-Analyse aktiviert', '🤖'],
                ['auto_response_enabled', 'Auto-Response aktiviert', '⚡'],
                ['auto_ban_enabled', 'Auto-Ban erlaubt', '🚫'],
                ['auto_mitigate_enabled', 'Auto-Mitigation erlaubt', '🔧'],
              ].map(([key, label, icon]) => {
                const val = cfgVal(key)
                const isOn = val === 'true' || val === true
                return (
                  <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: '#0a0e18', borderRadius: '6px', border: `1px solid ${isOn ? '#00ffcc33' : '#1a2a3a'}` }}>
                    <span style={{ fontSize: '12px' }}>{icon} {label}</span>
                    <button style={{ padding: '3px 12px', border: `1px solid ${isOn ? '#00ffcc' : '#ff4444'}`, background: isOn ? 'rgba(0,255,204,0.1)' : 'rgba(255,68,68,0.08)', color: isOn ? '#00ffcc' : '#ff4444', borderRadius: '12px', cursor: 'pointer', fontSize: '11px', fontWeight: 600 }}
                      onClick={() => updateAiConfig(key, !isOn ? 'true' : 'false')}>
                      {isOn ? 'AN' : 'AUS'}
                    </button>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Alle Configs */}
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['Schlüssel', 'Wert', 'Kategorie', 'Beschreibung', 'Aktualisiert'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {aiConfig.map((c, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px', color: '#a855f7' }}>{c.key}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{typeof c.value === 'object' ? JSON.stringify(c.value) : String(c.value)}</td>
                  <td style={{ ...S.td, fontSize: '11px', color: '#6688aa' }}>{c.category}</td>
                  <td style={{ ...S.td, fontSize: '11px', color: '#556', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.description || '—'}</td>
                  <td style={{ ...S.td, fontSize: '11px', color: '#556' }}>{fmtDate(c.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {aiConfig.length === 0 && <div style={S.empty}>Keine KI-Konfiguration gefunden</div>}
        </>
      )}

      {/* ═══════════ FIREWALL-REGELN ═══════════ */}
      {tab === 'rules' && (
        <>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
            <button style={S.btn} onClick={() => setShowAdd(!showAdd)}>+ Regel</button>
            <button style={S.btnWarn} onClick={applyRules}>⚡ Anwenden</button>
            <button style={S.btnMuted} onClick={loadFirewall}>🔄</button>
          </div>
          {showAdd && (
            <div style={{ ...S.card, display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
              <select style={S.select} value={newRule.chain} onChange={e => setNewRule({ ...newRule, chain: e.target.value })}>
                <option value="INPUT">INPUT</option><option value="OUTPUT">OUTPUT</option><option value="FORWARD">FORWARD</option>
              </select>
              <select style={S.select} value={newRule.protocol} onChange={e => setNewRule({ ...newRule, protocol: e.target.value })}>
                <option value="tcp">TCP</option><option value="udp">UDP</option><option value="icmp">ICMP</option><option value="all">ALL</option>
              </select>
              <input style={{ ...S.input, width: '70px' }} value={newRule.port} onChange={e => setNewRule({ ...newRule, port: e.target.value })} placeholder="Port" />
              <input style={{ ...S.input, width: '120px' }} value={newRule.source_ip} onChange={e => setNewRule({ ...newRule, source_ip: e.target.value })} placeholder="Quell-IP" />
              <select style={S.select} value={newRule.action} onChange={e => setNewRule({ ...newRule, action: e.target.value })}>
                <option value="ACCEPT">ACCEPT</option><option value="DROP">DROP</option><option value="REJECT">REJECT</option><option value="LOG">LOG</option>
              </select>
              <input style={{ ...S.input, width: '150px' }} value={newRule.description} onChange={e => setNewRule({ ...newRule, description: e.target.value })} placeholder="Beschreibung..." />
              <button style={S.btn} onClick={addRule}>✓</button>
            </div>
          )}
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['#', 'Chain', 'Proto', 'Port', 'Quelle', 'Aktion', 'Beschreibung', ''].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {rules.map((r, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, color: '#556' }}>{r.priority || i + 1}</td>
                  <td style={S.td}>{r.chain}</td>
                  <td style={{ ...S.td, color: '#4488ff' }}>{r.protocol}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace' }}>{r.port || '*'}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace' }}>{r.source_ip || '*'}</td>
                  <td style={{ ...S.td, color: actionColors[r.action] || '#d4d4d4', fontWeight: 600 }}>{r.action}</td>
                  <td style={{ ...S.td, color: '#556' }}>{r.description}</td>
                  <td style={S.td}><button style={{ background: 'none', border: 'none', color: '#ff4444', cursor: 'pointer', fontSize: '14px' }} onClick={() => deleteRule(r.id)} title="Löschen">🗑</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {rules.length === 0 && <div style={S.empty}>Keine Firewall-Regeln konfiguriert</div>}
        </>
      )}

      {/* ═══════════ ZONEN ═══════════ */}
      {tab === 'zones' && (
        <>
          <div style={{ marginBottom: '12px' }}><button style={S.btnMuted} onClick={loadFirewall}>🔄</button></div>
          {zones.length === 0 ? <div style={S.empty}>Keine Zonen definiert</div> : zones.map((z, i) => (
            <div key={i} style={S.card}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <strong style={{ color: '#d4d4d4' }}>{z.zone_name}</strong>
                <span style={S.badge(z.is_active ? '#00ffcc' : '#556')}>{z.is_active ? 'Aktiv' : 'Inaktiv'}</span>
              </div>
              <div style={{ display: 'flex', gap: '16px', fontSize: '11px', color: '#556' }}>
                <span>Policy: <span style={{ color: actionColors[z.default_policy] || '#d4d4d4' }}>{z.default_policy}</span></span>
                <span>Interfaces: {z.interfaces?.join(', ') || '—'}</span>
              </div>
            </div>
          ))}
        </>
      )}

      {/* ═══════════ VERBINDUNGEN ═══════════ */}
      {tab === 'connections' && (
        <>
          <div style={{ marginBottom: '12px' }}><button style={S.btnMuted} onClick={loadFirewall}>🔄</button></div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['Proto', 'Lokal', 'Remote', 'Status', 'Prozess'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {connections.map((c, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, color: '#4488ff' }}>{c.protocol}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px' }}>{c.local_address}:{c.local_port}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px' }}>{c.remote_address || '*'}:{c.remote_port || '*'}</td>
                  <td style={{ ...S.td, color: stateColors[c.status] || '#556', fontWeight: 600, fontSize: '11px' }}>{c.status}</td>
                  <td style={{ ...S.td, color: '#6688aa', fontSize: '11px' }}>{c.process_name || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {connections.length === 0 && <div style={S.empty}>Keine aktiven Verbindungen</div>}
        </>
      )}

      {/* ═══════════ SCHWACHSTELLEN ═══════════ */}
      {tab === 'vulns' && (
        <>
          <div style={S.header}>
            <div style={{ display: 'flex', gap: '6px' }}>
              {['open', 'mitigated', 'false_positive', 'all'].map(f => (
                <button key={f} style={S.tab(vulnFilter === f)} onClick={() => setVulnFilter(f)}>
                  {f === 'all' ? 'Alle' : f === 'open' ? '🔴 Offen' : f === 'mitigated' ? '✅ Mitigiert' : '⚪ False+'}
                </button>
              ))}
            </div>
            <button style={S.btnMuted} onClick={loadVulns}>🔄</button>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['Schwere', 'Kategorie', 'Titel', 'Ziel', 'CVE', 'Gefunden', 'Status', ''].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {vulns.map((v, i) => (
                <tr key={i}>
                  <td style={S.td}><span style={S.badge(severity(v.severity))}>{v.severity}</span></td>
                  <td style={{ ...S.td, fontSize: '11px', color: '#6688aa' }}>{v.category || '—'}</td>
                  <td style={{ ...S.td, maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{v.title || '—'}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px' }}>{v.affected_target || '—'}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px', color: v.cve_id ? '#ffaa00' : '#334' }}>{v.cve_id || '—'}</td>
                  <td style={{ ...S.td, fontSize: '11px', color: '#556' }}>{fmtDate(v.first_seen_at)}</td>
                  <td style={S.td}><span style={S.badge(v.status === 'open' ? '#ff4444' : '#00ffcc')}>{v.status}</span></td>
                  <td style={S.td}>{v.status === 'open' && <button style={{ background: 'none', border: 'none', color: '#00ffcc', cursor: 'pointer', fontSize: '12px' }} onClick={() => mitigateVuln(v.id)} title="Mitigieren">✔</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {vulns.length === 0 && <div style={S.empty}>Keine Schwachstellen gefunden 🎉</div>}
        </>
      )}

      {/* ═══════════ IDS / INTRUSIONS ═══════════ */}
      {tab === 'intrusions' && (
        <>
          <div style={S.header}>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              <span style={S.label}>Zeitraum:</span>
              <select style={S.select} value={intrusionHours} onChange={e => setIntrusionHours(+e.target.value)}>
                <option value={1}>1h</option><option value={6}>6h</option><option value={24}>24h</option><option value={72}>3d</option><option value={168}>7d</option>
              </select>
            </div>
            <button style={S.btnMuted} onClick={loadIntrusions}>🔄</button>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['Zeit', 'Typ', 'Quell-IP', 'Ziel', 'Signatur', 'Prio', 'Aktion'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {intrusions.map((ev, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, fontSize: '11px', color: '#556', whiteSpace: 'nowrap' }}>{fmtDate(ev.detected_at)}</td>
                  <td style={{ ...S.td, fontSize: '11px' }}>{ev.event_type || '—'}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px' }}>{ev.source_ip || '—'}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px' }}>{ev.dest_ip || '—'}:{ev.dest_port || '*'}</td>
                  <td style={{ ...S.td, fontSize: '11px', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ev.signature_name || '—'}</td>
                  <td style={S.td}><span style={S.badge(ev.priority <= 1 ? '#ff2255' : ev.priority <= 2 ? '#ff4444' : '#ffaa00')}>{ev.priority}</span></td>
                  <td style={{ ...S.td, fontSize: '11px', color: '#6688aa' }}>{ev.action_taken || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {intrusions.length === 0 && <div style={S.empty}>Keine Intrusion-Events 🎉</div>}
        </>
      )}

      {/* ═══════════ IP-BANS ═══════════ */}
      {tab === 'bans' && (
        <>
          <div style={S.header}>
            <button style={S.btnDanger} onClick={() => setShowBanForm(!showBanForm)}>+ IP bannen</button>
            <button style={S.btnMuted} onClick={loadBans}>🔄</button>
          </div>
          {showBanForm && (
            <div style={{ ...S.card, display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
              <input style={{ ...S.input, width: '140px' }} value={newBan.ip} onChange={e => setNewBan({ ...newBan, ip: e.target.value })} placeholder="IP-Adresse" />
              <input style={{ ...S.input, width: '200px' }} value={newBan.reason} onChange={e => setNewBan({ ...newBan, reason: e.target.value })} placeholder="Grund..." />
              <span style={{ fontSize: '11px', color: '#6688aa' }}>h:</span>
              <input style={{ ...S.input, width: '60px' }} type="number" value={newBan.hours} onChange={e => setNewBan({ ...newBan, hours: +e.target.value })} />
              <button style={S.btnDanger} onClick={banIp}>🚫 Bannen</button>
            </div>
          )}
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['IP', 'Grund', 'Quelle', 'Gebannt', 'Ablauf', ''].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {bans.map((b, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontWeight: 600 }}>{b.ip_address}</td>
                  <td style={{ ...S.td, fontSize: '11px' }}>{b.reason || '—'}</td>
                  <td style={{ ...S.td, fontSize: '11px', color: b.source === 'ai_monitor' ? '#a855f7' : '#6688aa' }}>{b.source || '—'}</td>
                  <td style={{ ...S.td, fontSize: '11px', color: '#556' }}>{fmtDate(b.banned_at)}</td>
                  <td style={{ ...S.td, fontSize: '11px', color: b.expires_at ? '#ffaa00' : '#334' }}>{b.expires_at ? fmtDate(b.expires_at) : 'Permanent'}</td>
                  <td style={S.td}><button style={{ background: 'none', border: 'none', color: '#00ffcc', cursor: 'pointer', fontSize: '12px' }} onClick={() => unbanIp(b.id)} title="Entsperren">🔓</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {bans.length === 0 && <div style={S.empty}>Keine aktiven IP-Bans</div>}
        </>
      )}

      {/* ═══════════ SCANS ═══════════ */}
      {tab === 'scans' && (
        <>
          <div style={S.header}>
            <div style={{ fontSize: '13px', color: '#6688aa' }}>Scan-Jobs</div>
            <button style={S.btnMuted} onClick={loadScans}>🔄</button>
          </div>
          {scans.map((s, i) => (
            <div key={i} style={S.card}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <strong style={{ color: '#d4d4d4', fontSize: '13px' }}>{s.scan_type}</strong>
                <span style={S.badge(s.status === 'completed' ? '#00ffcc' : s.status === 'running' ? '#4488ff' : '#ffaa00')}>{s.status}</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px', fontSize: '11px', color: '#556' }}>
                <span>Ziel: <span style={{ color: '#d4d4d4', fontFamily: 'monospace' }}>{s.target || '—'}</span></span>
                <span>Cron: <span style={{ color: '#d4d4d4' }}>{s.schedule_cron || '—'}</span></span>
                <span>Findings: <span style={{ color: s.findings_count > 0 ? '#ffaa00' : '#00ffcc' }}>{s.findings_count ?? 0}</span></span>
              </div>
            </div>
          ))}
          {scans.length === 0 && <div style={S.empty}>Keine Scan-Jobs</div>}
        </>
      )}

      {/* ═══════════ BEDROHUNGEN ═══════════ */}
      {tab === 'threats' && (
        <>
          <div style={S.header}>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              <input style={{ ...S.input, width: '160px' }} value={threatLookup} onChange={e => setThreatLookup(e.target.value)} placeholder="IP prüfen..." onKeyDown={e => e.key === 'Enter' && lookupThreat()} />
              <button style={S.btn} onClick={lookupThreat}>🔎</button>
            </div>
            <button style={S.btnMuted} onClick={loadThreats}>🔄</button>
          </div>
          {threatResult && (
            <div style={{ ...S.card, borderColor: threatResult.error ? '#ff4444' : '#1a2a3a', marginBottom: '12px' }}>
              {threatResult.error ? <div style={{ color: '#ff4444', fontSize: '12px' }}>{threatResult.error}</div> : (
                <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                  <div style={S.metric}>
                    <div style={{ fontSize: '22px', fontWeight: 700, color: (threatResult.threat_score || 0) > 70 ? '#ff4444' : (threatResult.threat_score || 0) > 30 ? '#ffaa00' : '#00ffcc' }}>{threatResult.threat_score || 0}</div>
                    <div style={S.metricLabel}>Score</div>
                  </div>
                  <div style={{ fontSize: '12px' }}>
                    <div>IP: <span style={{ fontFamily: 'monospace', color: '#d4d4d4' }}>{threatResult.ip}</span></div>
                  </div>
                </div>
              )}
            </div>
          )}
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['Typ', 'IOC', 'Bedrohung', 'Konfidenz', 'Quelle', 'Hits', 'Zuletzt'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {threats.map((t, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, fontSize: '11px' }}>{t.ioc_type || '—'}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px', maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.ioc_value || '—'}</td>
                  <td style={{ ...S.td, fontSize: '11px' }}>{t.threat_type || '—'}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px' }}>{t.confidence != null ? `${Math.round(t.confidence * 100)}%` : '—'}</td>
                  <td style={{ ...S.td, fontSize: '11px', color: '#6688aa' }}>{t.source || '—'}</td>
                  <td style={{ ...S.td, fontWeight: 600 }}>{t.hit_count ?? 0}</td>
                  <td style={{ ...S.td, fontSize: '11px', color: '#556' }}>{fmtDate(t.last_seen_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {threats.length === 0 && <div style={S.empty}>Keine Threat-Intelligence</div>}
        </>
      )}

      {/* ═══════════ BASELINES ═══════════ */}
      {tab === 'baselines' && (
        <>
          <div style={S.header}>
            <div style={{ fontSize: '13px', color: '#6688aa' }}>CIS-Baselines</div>
            <button style={S.btnMuted} onClick={loadBaselines}>🔄</button>
          </div>
          {(() => {
            const pass = baselines.filter(b => b.compliant).length
            const total = baselines.length
            return total > 0 && (
              <div style={{ ...S.card, display: 'flex', gap: '16px', alignItems: 'center', marginBottom: '12px' }}>
                <div style={S.metric}>
                  <div style={{ fontSize: '24px', fontWeight: 700, color: pass === total ? '#00ffcc' : '#ffaa00' }}>{Math.round(pass / total * 100)}%</div>
                  <div style={S.metricLabel}>Compliance</div>
                </div>
                <div style={{ fontSize: '12px' }}><span style={{ color: '#00ffcc' }}>✓ {pass}</span> · <span style={{ color: '#ff4444' }}>✗ {total - pass}</span> · {total} total</div>
              </div>
            )
          })()}
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['Komponente', 'Check', 'Erwartet', 'Aktuell', 'Schwere', 'Status'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {baselines.map((b, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, fontSize: '11px', color: '#6688aa' }}>{b.component}</td>
                  <td style={{ ...S.td, fontSize: '11px' }}>{b.check_name}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px', color: '#4488ff' }}>{b.expected_value}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px', color: b.compliant ? '#00ffcc' : '#ff4444' }}>{b.current_value}</td>
                  <td style={S.td}><span style={S.badge(severity(b.severity))}>{b.severity}</span></td>
                  <td style={S.td}><span style={S.badge(b.compliant ? '#00ffcc' : '#ff4444')}>{b.compliant ? 'PASS' : 'FAIL'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {baselines.length === 0 && <div style={S.empty}>Keine Baselines</div>}
        </>
      )}

      {/* ═══════════ RESPONSES ═══════════ */}
      {tab === 'responses' && (
        <>
          <div style={S.header}>
            <div style={{ fontSize: '13px', color: '#6688aa' }}>Automatische Sicherheitsreaktionen</div>
            <button style={S.btnMuted} onClick={loadResponses}>🔄</button>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['Zeit', 'Trigger', 'Typ', 'Beschreibung', 'Erfolg'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {responses.map((r, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, fontSize: '11px', color: '#556', whiteSpace: 'nowrap' }}>{fmtDate(r.executed_at)}</td>
                  <td style={{ ...S.td, fontSize: '11px', color: r.trigger_type === 'ai_analysis' ? '#a855f7' : '#6688aa' }}>{r.trigger_type || '—'}</td>
                  <td style={S.td}><span style={S.badge(r.response_type === 'auto_ban' ? '#ff4444' : '#4488ff')}>{r.response_type || '—'}</span></td>
                  <td style={{ ...S.td, fontSize: '11px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.description || '—'}</td>
                  <td style={S.td}><span style={S.badge(r.success !== false ? '#00ffcc' : '#ff4444')}>{r.success !== false ? 'OK' : 'Fehler'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {responses.length === 0 && <div style={S.empty}>Keine Responses</div>}
        </>
      )}

      {/* ═══════════ HONEYPOT ═══════════ */}
      {tab === 'honeypot' && (
        <>
          <div style={S.header}>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              <span style={S.label}>Zeitraum:</span>
              <select style={S.select} value={honeypotHours} onChange={e => setHoneypotHours(+e.target.value)}>
                <option value={1}>1h</option><option value={6}>6h</option><option value={24}>24h</option><option value={72}>3d</option><option value={168}>7d</option>
              </select>
            </div>
            <button style={S.btnMuted} onClick={loadHoneypot}>🔄</button>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['Zeit', 'Quell-IP', 'Typ', 'Interaktion'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {honeypot.map((h, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, fontSize: '11px', color: '#556' }}>{fmtDate(h.detected_at)}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px', fontWeight: 600 }}>{h.source_ip || '—'}</td>
                  <td style={{ ...S.td, fontSize: '11px' }}>{h.honeypot_type || '—'}</td>
                  <td style={{ ...S.td, fontSize: '11px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#ffaa00' }}>{h.interaction || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {honeypot.length === 0 && <div style={S.empty}>Keine Honeypot-Events</div>}
        </>
      )}

      {/* ═══════════ AUTH-LOG ═══════════ */}
      {tab === 'auth' && (
        <>
          <div style={S.header}>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              <span style={S.label}>Zeitraum:</span>
              <select style={S.select} value={authHours} onChange={e => setAuthHours(+e.target.value)}>
                <option value={1}>1h</option><option value={6}>6h</option><option value={24}>24h</option><option value={72}>3d</option><option value={168}>7d</option>
              </select>
            </div>
            <button style={S.btnMuted} onClick={loadFailedAuth}>🔄</button>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['Quell-IP', 'Typ', 'Versuche', 'Letzter Versuch'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {failedAuth.map((a, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px', fontWeight: 600 }}>{a.source_ip || '—'}</td>
                  <td style={{ ...S.td, fontSize: '11px', color: '#6688aa' }}>{a.auth_type || '—'}</td>
                  <td style={{ ...S.td, fontWeight: 600, color: (a.attempts || 0) > 5 ? '#ff4444' : '#d4d4d4' }}>{a.attempts || 1}</td>
                  <td style={{ ...S.td, fontSize: '11px', color: '#556' }}>{fmtDate(a.last_attempt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {failedAuth.length === 0 && <div style={S.empty}>Keine fehlgeschlagenen Authentifizierungen 🎉</div>}
        </>
      )}

      {/* ═══════════ TLS-ZERTIFIKATE ═══════════ */}
      {tab === 'tls' && (
        <>
          <div style={S.header}>
            <div style={{ fontSize: '13px', color: '#6688aa' }}>TLS-Zertifikat-Überwachung</div>
            <button style={S.btnMuted} onClick={loadTls}>🔄</button>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['Domain', 'Aussteller', 'Gültig ab', 'Ablauf', 'Status', 'Geprüft'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {tls.map((t, i) => {
                const expiring = t.expires_at && new Date(t.expires_at) < new Date(Date.now() + 30 * 86400000)
                return (
                  <tr key={i}>
                    <td style={{ ...S.td, fontWeight: 600 }}>{t.domain}</td>
                    <td style={{ ...S.td, fontSize: '11px', color: '#6688aa' }}>{t.issuer || '—'}</td>
                    <td style={{ ...S.td, fontSize: '11px', color: '#556' }}>{fmtDate(t.issued_at)}</td>
                    <td style={{ ...S.td, fontSize: '11px', color: expiring ? '#ff4444' : '#00ffcc' }}>{fmtDate(t.expires_at)}</td>
                    <td style={S.td}><span style={S.badge(t.is_valid ? '#00ffcc' : '#ff4444')}>{t.is_valid ? 'Gültig' : 'Ungültig'}</span></td>
                    <td style={{ ...S.td, fontSize: '11px', color: '#556' }}>{fmtDate(t.last_checked_at)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {tls.length === 0 && <div style={S.empty}>Keine TLS-Zertifikate überwacht</div>}
        </>
      )}

      {/* ═══════════ CVE-TRACKING ═══════════ */}
      {tab === 'cve' && (
        <>
          <div style={S.header}>
            <div style={{ fontSize: '13px', color: '#6688aa' }}>CVE-Tracking</div>
            <button style={S.btnMuted} onClick={loadCves}>🔄</button>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['CVE-ID', 'Titel', 'CVSS', 'Paket', 'Version', 'Fix', 'Gepatcht'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {cves.map((c, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px', color: '#ffaa00', fontWeight: 600 }}>{c.cve_id}</td>
                  <td style={{ ...S.td, fontSize: '11px', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.title || '—'}</td>
                  <td style={S.td}><span style={S.badge(c.cvss_score >= 9 ? '#ff2255' : c.cvss_score >= 7 ? '#ff4444' : c.cvss_score >= 4 ? '#ffaa00' : '#4488ff')}>{c.cvss_score ?? '—'}</span></td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px' }}>{c.affected_pkg || '—'}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px', color: '#556' }}>{c.affected_ver || '—'}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px', color: c.fixed_ver ? '#00ffcc' : '#334' }}>{c.fixed_ver || '—'}</td>
                  <td style={S.td}><span style={S.badge(c.is_patched ? '#00ffcc' : '#ff4444')}>{c.is_patched ? 'Ja' : 'Nein'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {cves.length === 0 && <div style={S.empty}>Keine CVEs getrackt</div>}
        </>
      )}

      {/* ═══════════ DNS-SINKHOLE ═══════════ */}
      {tab === 'sinkhole' && (
        <>
          <div style={S.header}>
            <button style={S.btnDanger} onClick={() => setShowSinkholeForm(!showSinkholeForm)}>+ Domain blockieren</button>
            <button style={S.btnMuted} onClick={loadSinkhole}>🔄</button>
          </div>
          {showSinkholeForm && (
            <div style={{ ...S.card, display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
              <input style={{ ...S.input, width: '220px' }} value={newSinkhole.domain} onChange={e => setNewSinkhole({ ...newSinkhole, domain: e.target.value })} placeholder="Domain-Pattern (z.B. *.malware.com)" />
              <input style={{ ...S.input, width: '200px' }} value={newSinkhole.reason} onChange={e => setNewSinkhole({ ...newSinkhole, reason: e.target.value })} placeholder="Grund..." />
              <button style={S.btnDanger} onClick={addSinkholeRule}>🕳️ Blockieren</button>
            </div>
          )}
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['Domain-Pattern', 'Grund', 'Quelle', 'Hits', 'Aktiv', ''].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {sinkhole.map((s, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px', fontWeight: 600, color: '#d4d4d4' }}>{s.domain_pattern}</td>
                  <td style={{ ...S.td, fontSize: '11px' }}>{s.reason || '—'}</td>
                  <td style={{ ...S.td, fontSize: '11px', color: '#6688aa' }}>{s.source || '—'}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px', color: '#ffaa00' }}>{s.hit_count ?? 0}</td>
                  <td style={S.td}><span style={S.badge(s.is_active ? '#00ffcc' : '#556')}>{s.is_active ? 'Ja' : 'Nein'}</span></td>
                  <td style={S.td}>{s.is_active && <button style={{ background: 'none', border: 'none', color: '#ff4444', cursor: 'pointer', fontSize: '12px' }} onClick={() => deleteSinkholeRule(s.id)} title="Deaktivieren">🗑</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {sinkhole.length === 0 && <div style={S.empty}>Keine DNS-Sinkhole-Regeln</div>}
        </>
      )}

      {/* ═══════════ RATE-LIMITS ═══════════ */}
      {tab === 'ratelimit' && (
        <>
          <div style={S.header}>
            <div style={{ fontSize: '13px', color: '#6688aa' }}>Rate-Limiting</div>
            <button style={S.btnMuted} onClick={loadRateLimits}>🔄</button>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['Typ', 'Ziel', 'Max Req', 'Fenster (s)', 'Aktuell', 'Blockiert', 'Bis'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {rateLimits.map((r, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, fontSize: '11px' }}>{r.target_type}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px' }}>{r.target_value}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px', color: '#4488ff' }}>{r.max_requests}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px' }}>{r.window_seconds}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px', color: r.current_count > r.max_requests * 0.8 ? '#ff4444' : '#00ffcc' }}>{r.current_count || 0}</td>
                  <td style={S.td}><span style={S.badge(r.is_blocked ? '#ff4444' : '#00ffcc')}>{r.is_blocked ? 'Ja' : 'Nein'}</span></td>
                  <td style={{ ...S.td, fontSize: '11px', color: '#556' }}>{r.blocked_until ? fmtDate(r.blocked_until) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rateLimits.length === 0 && <div style={S.empty}>Keine Rate-Limits konfiguriert</div>}
        </>
      )}

      {/* ═══════════ NETWORK-TRAFFIC ═══════════ */}
      {tab === 'traffic' && (
        <>
          <div style={S.header}>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              <span style={S.label}>Zeitraum:</span>
              <select style={S.select} value={trafficHours} onChange={e => setTrafficHours(+e.target.value)}>
                <option value={1}>1h</option><option value={6}>6h</option><option value={24}>24h</option>
              </select>
            </div>
            <button style={S.btnMuted} onClick={loadNetworkTraffic}>🔄</button>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['Zeit', 'Quelle', 'Ziel', 'Proto', 'Gesendet', 'Empfangen', 'Verdächtig'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {networkTraffic.map((t, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, fontSize: '11px', color: '#556', whiteSpace: 'nowrap' }}>{fmtDate(t.recorded_at)}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px' }}>{t.source_ip}:{t.source_port}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px' }}>{t.dest_ip}:{t.dest_port}</td>
                  <td style={{ ...S.td, color: '#4488ff', fontSize: '11px' }}>{t.protocol || '—'}</td>
                  <td style={{ ...S.td, fontSize: '11px' }}>{t.bytes_sent ? `${(t.bytes_sent / 1024).toFixed(1)}KB` : '—'}</td>
                  <td style={{ ...S.td, fontSize: '11px' }}>{t.bytes_received ? `${(t.bytes_received / 1024).toFixed(1)}KB` : '—'}</td>
                  <td style={S.td}><span style={S.badge(t.is_suspicious ? '#ff4444' : '#00ffcc')}>{t.is_suspicious ? 'Ja' : 'Nein'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {networkTraffic.length === 0 && <div style={S.empty}>Kein Netzwerk-Traffic aufgezeichnet</div>}
        </>
      )}

      {/* ═══════════ BERECHTIGUNGEN ═══════════ */}
      {tab === 'perms' && (
        <>
          <div style={S.header}>
            <div style={{ fontSize: '13px', color: '#6688aa' }}>Permission-Audit</div>
            <button style={S.btnMuted} onClick={loadPermissions}>🔄</button>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['Schema', 'Tabelle', 'Rolle', 'Berechtigung', 'Gewährt', 'Geprüft'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {permissions.map((p, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px' }}>{p.schema_name}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px' }}>{p.table_name}</td>
                  <td style={{ ...S.td, fontSize: '11px', color: '#6688aa' }}>{p.role_name}</td>
                  <td style={{ ...S.td, fontSize: '11px' }}>{p.privilege_type}</td>
                  <td style={S.td}><span style={S.badge(p.is_granted ? '#00ffcc' : '#ff4444')}>{p.is_granted ? 'Ja' : 'Nein'}</span></td>
                  <td style={{ ...S.td, fontSize: '11px', color: '#556' }}>{fmtDate(p.checked_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {permissions.length === 0 && <div style={S.empty}>Kein Permission-Audit</div>}
        </>
      )}

      {/* ═══════════ METRIKEN ═══════════ */}
      {tab === 'metrics' && (
        <>
          <div style={S.header}>
            <div style={{ fontSize: '13px', color: '#6688aa' }}>Security-Metriken</div>
            <button style={S.btnMuted} onClick={loadMetrics}>🔄</button>
          </div>
          {metrics.length > 0 ? (
            <div style={S.grid3}>
              {metrics.slice(0, 12).map((m, i) => (
                <div key={i} style={{ ...S.card, ...S.metric }}>
                  <div style={{ ...S.metricVal, fontSize: '22px', color: '#00ffcc' }}>{typeof m.metric_value === 'number' ? m.metric_value.toFixed(1) : m.metric_value}</div>
                  <div style={S.metricLabel}>{m.metric_name} {m.metric_unit && `(${m.metric_unit})`}</div>
                  <div style={{ fontSize: '10px', color: '#334', marginTop: '2px' }}>{fmtDate(m.recorded_at)}</div>
                </div>
              ))}
            </div>
          ) : <div style={S.empty}>Keine Security-Metriken aufgezeichnet</div>}
          {metrics.length > 12 && (
            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '8px' }}>
              <thead><tr>{['Metrik', 'Wert', 'Einheit', 'Zeitpunkt'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
              <tbody>
                {metrics.slice(12).map((m, i) => (
                  <tr key={i}>
                    <td style={{ ...S.td, fontSize: '11px' }}>{m.metric_name}</td>
                    <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px', color: '#00ffcc' }}>{m.metric_value}</td>
                    <td style={{ ...S.td, fontSize: '11px', color: '#6688aa' }}>{m.metric_unit || '—'}</td>
                    <td style={{ ...S.td, fontSize: '11px', color: '#556' }}>{fmtDate(m.recorded_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  )
}
