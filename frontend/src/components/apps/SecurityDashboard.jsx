import React, { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

/**
 * SecurityDashboard — Security Center for DBAI
 * 
 * Displays:
 * - Overall security score & status
 * - Vulnerabilities (open/critical)
 * - Intrusion events (IDS)
 * - IP bans
 * - Threat intelligence
 * - Failed auth attempts
 * - Honeypot events
 * - Security baselines & compliance
 * - AI security status
 */

/* ─── Helpers ────────────────────────────────────────── */
const severityColor = (s) => {
  const map = { critical: '#ff4444', high: '#ff8844', medium: '#ffaa00', low: '#88cc44', info: '#4488ff' }
  return map[s?.toLowerCase()] || '#888'
}

const severityIcon = (s) => {
  const map = { critical: '🔴', high: '🟠', medium: '🟡', low: '🟢', info: '🔵' }
  return map[s?.toLowerCase()] || '⚪'
}

const statusColor = (s) => {
  const map = { open: '#ff8844', confirmed: '#ffaa00', mitigated: '#00cc88', resolved: '#4488ff', false_positive: '#888' }
  return map[s?.toLowerCase()] || '#888'
}

const formatTime = (t) => {
  if (!t) return '—'
  const d = new Date(t)
  return d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
}

const formatDate = (t) => {
  if (!t) return '—'
  const d = new Date(t)
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function ScoreRing({ score, size = 80, stroke = 8, label = '' }) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const pct = Math.min(Math.max(score || 0, 0), 100)
  const offset = c - (pct / 100) * c
  const color = pct >= 80 ? '#00ff88' : pct >= 50 ? '#ffaa00' : '#ff4444'
  return (
    <div style={{ position: 'relative', width: size, height: size, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={stroke} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={stroke} 
                strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round" style={{ transition: 'stroke-dashoffset 0.8s ease' }} />
      </svg>
      <div style={{ position: 'absolute', textAlign: 'center' }}>
        <div style={{ fontSize: size/4, fontWeight: 700, color: color }}>{pct.toFixed(0)}</div>
        {label && <div style={{ fontSize: 9, color: 'var(--text-secondary)' }}>{label}</div>}
      </div>
    </div>
  )
}

function StatCard({ icon, label, value, sub, color = 'var(--text-primary)', onClick }) {
  return (
    <div onClick={onClick} style={{
      flex: 1, minWidth: 120, padding: '12px 16px',
      background: 'var(--bg-surface)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius)', cursor: onClick ? 'pointer' : 'default',
      transition: 'all 0.2s',
    }}
    onMouseOver={e => onClick && (e.currentTarget.style.borderColor = 'var(--accent)', e.currentTarget.style.transform = 'translateY(-2px)')}
    onMouseOut={e => onClick && (e.currentTarget.style.borderColor = 'var(--border)', e.currentTarget.style.transform = '')}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span style={{ fontSize: 18 }}>{icon}</span>
        <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{label}</span>
      </div>
      <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

function VulnRow({ v, onMitigate }) {
  return (
    <div style={{
      padding: '10px 14px', borderBottom: '1px solid var(--border)',
      display: 'flex', alignItems: 'flex-start', gap: 10,
    }}>
      <span style={{ fontSize: 16, flexShrink: 0 }}>{severityIcon(v.severity)}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{v.title}</span>
          {v.cve_id && <span style={{ fontSize: 10, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{v.cve_id}</span>}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2, display: 'flex', gap: 12 }}>
          <span>Category: <b>{v.category || '—'}</b></span>
          {v.cvss_score != null && <span>CVSS: <b style={{ color: severityColor(v.severity) }}>{v.cvss_score}</b></span>}
          <span>Seit: {formatDate(v.first_seen_at)}</span>
        </div>
        {v.description && <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.4 }}>{v.description}</div>}
        {v.remediation && <div style={{ fontSize: 11, color: '#88ccaa', marginTop: 4 }}>💡 {v.remediation}</div>}
      </div>
      <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
        <span style={{
          padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
          background: `${statusColor(v.status)}22`, color: statusColor(v.status),
          border: `1px solid ${statusColor(v.status)}44`,
        }}>{v.status}</span>
        {v.status === 'open' && (
          <button onClick={() => onMitigate(v.id)} style={{
            padding: '4px 10px', background: 'rgba(0,255,136,0.1)',
            border: '1px solid #00cc88', borderRadius: 4,
            color: '#00cc88', fontSize: 10, cursor: 'pointer',
          }}>✅ Mitigieren</button>
        )}
      </div>
    </div>
  )
}

function IntrusionRow({ e }) {
  const sevColor = severityColor(e.severity || 'medium')
  return (
    <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 10, alignItems: 'flex-start' }}>
      <span style={{ fontSize: 16 }}>{e.severity === 'critical' ? '🚨' : e.severity === 'high' ? '⚠️' : '📋'}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 600 }}>{e.event_type || e.type || 'Unbekanntes Ereignis'}</div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {e.source_ip && <span>IP: <b style={{ fontFamily: 'var(--font-mono)' }}>{e.source_ip}</b></span>}
          {e.target && <span>Ziel: <b>{e.target}</b></span>}
          <span>{formatDate(e.detected_at)} {formatTime(e.detected_at)}</span>
        </div>
        {e.details && <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4, whiteSpace: 'pre-wrap', maxHeight: 60, overflow: 'hidden' }}>{typeof e.details === 'object' ? JSON.stringify(e.details, null, 0) : e.details}</div>}
      </div>
      <span style={{
        padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
        background: `${sevColor}22`, color: sevColor, border: `1px solid ${sevColor}44`,
      }}>{e.severity || 'info'}</span>
    </div>
  )
}

function BanRow({ b, onUnban }) {
  return (
    <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 10, alignItems: 'center' }}>
      <span style={{ fontSize: 16 }}>🚫</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{b.ip_address || b.ip}</div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
          {b.reason || 'Kein Grund angegeben'} · {b.is_active ? 'Aktiv' : 'Inaktiv'}
        </div>
      </div>
      {b.is_active && (
        <button onClick={() => onUnban(b.id)} style={{
          padding: '4px 10px', background: 'rgba(255,170,0,0.1)',
          border: '1px solid #ffaa00', borderRadius: 4,
          color: '#ffaa00', fontSize: 10, cursor: 'pointer',
        }}>Freigeben</button>
      )}
    </div>
  )
}

function ThreatRow({ t }) {
  return (
    <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 10, alignItems: 'flex-start' }}>
      <span style={{ fontSize: 16 }}>{t.indicator_type === 'ip' ? '🌐' : t.indicator_type === 'domain' ? '🔗' : t.indicator_type === 'url' ? '📎' : '🎯'}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{t.indicator}</div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2, display: 'flex', gap: 12 }}>
          <span>{t.indicator_type || '—'}</span>
          {t.severity && <span style={{ color: severityColor(t.severity) }}>{t.severity}</span>}
          <span>Confidence: {t.confidence ?? '—'}%</span>
        </div>
        {t.source && <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 2 }}>Quelle: {t.source}</div>}
      </div>
      <span style={{
        padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
        background: t.is_active ? '#00cc8822' : '#88888822',
        color: t.is_active ? '#00cc88' : '#888',
        border: `1px solid ${t.is_active ? '#00cc8844' : '#88888844'}`,
      }}>{t.is_active ? 'Aktiv' : 'Inaktiv'}</span>
    </div>
  )
}

function BaselineRow({ b }) {
  return (
    <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 10, alignItems: 'center' }}>
      <span style={{ fontSize: 16 }}>{b.compliant ? '✅' : '❌'}</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 12, fontWeight: 600 }}>{b.control_name || b.name || 'Unbekannte Richtlinie'}</div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
          Framework: <b>{b.framework || '—'}</b> · {b.control_id || ''}
        </div>
      </div>
      <span style={{
        padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
        background: b.compliant ? '#00cc8822' : '#ff444422',
        color: b.compliant ? '#00cc88' : '#ff4444',
        border: `1px solid ${b.compliant ? '#00cc8844' : '#ff444444'}`,
      }}>{b.compliant ? 'Erfüllt' : 'Nicht erfüllt'}</span>
    </div>
  )
}

/* ─── Main Component ─────────────────────────────────── */
export default function SecurityDashboard() {
  const { settings, schema, update: updateSetting, reset: resetSettings } = useAppSettings('security-dashboard')
  const [showSettings, setShowSettings] = useState(false)
  const [tab, setTab] = useState(settings?.default_tab || 'overview')
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState(null)
  const [vulns, setVulns] = useState([])
  const [intrusions, setIntrusions] = useState([])
  const [bans, setBans] = useState([])
  const [threats, setThreats] = useState([])
  const [baselines, setBaselines] = useState([])
  const [honeypot, setHoneypot] = useState([])
  const [failedAuth, setFailedAuth] = useState([])
  const [aiStatus, setAiStatus] = useState(null)
  const [mitigating, setMitigating] = useState(false)

  const autoRefresh = settings?.auto_refresh_interval ?? 60000
  const refreshTimer = useRef(null)

  const loadAll = useCallback(async () => {
    try {
      const [st, vuln, intr, ban, threat, baseline, honey, auth, ai] = await Promise.all([
        api.securityStatus().catch(() => null),
        api.securityVulnerabilities('open', null, 50).catch(() => ({ vulnerabilities: [] })),
        api.securityIntrusions(24, 50).catch(() => ({ intrusions: [] })),
        api.securityBans().catch(() => ({ bans: [] })),
        api.securityThreats().catch(() => ({ threats: [] })),
        api.securityBaselines().catch(() => ({ baselines: [] })),
        api.securityHoneypot(24).catch(() => ({ events: [] })),
        api.securityFailedAuth(24).catch(() => ({ attempts: [] })),
        api.securityAiStatus().catch(() => null),
      ])
      setStatus(st?.security || null)
      setVulns(vuln?.vulnerabilities || [])
      setIntrusions(intr?.intrusions || [])
      setBans(ban?.bans || ban?.active_bans || [])
      setThreats(threat?.threats || [])
      setBaselines(baseline?.baselines || [])
      setHoneypot(honey?.events || [])
      setFailedAuth(auth?.attempts || [])
      setAiStatus(ai?.ai || ai)
    } catch (e) {
      console.error('Security load error:', e)
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    loadAll()
    refreshTimer.current = setInterval(loadAll, autoRefresh)
    return () => clearInterval(refreshTimer.current)
  }, [loadAll, autoRefresh])

  const handleMitigate = async (vulnId) => {
    setMitigating(true)
    try {
      await api.securityMitigateVuln(vulnId, 'mitigated')
      loadAll()
    } catch (e) {
      console.error('Mitigate error:', e)
    }
    setMitigating(false)
  }

  const handleUnban = async (banId) => {
    try {
      await api.securityUnban(banId)
      loadAll()
    } catch (e) {
      console.error('Unban error:', e)
    }
  }

  // Compute security score
  const openVulns = status?.open_vulns || vulns.length
  const criticalVulns = status?.critical_vulns || vulns.filter(v => v.severity === 'critical').length
  const activeBans = status?.active_bans || bans.filter(b => b.is_active).length
  const ids24h = status?.ids_24h || intrusions.length
  const failedAuth24h = status?.failed_auth_24h || failedAuth.length
  const compliancePct = status?.compliance_pct || 0
  const threatIndicators = status?.threat_indicators || threats.length
  const honeypot24h = status?.honeypot_24h || honeypot.length

  const securityScore = Math.max(0, Math.min(100,
    100 - (criticalVulns * 20) - (openVulns * 5) - (ids24h * 3) - (failedAuth24h * 1)
  ))

  const tabs = [
    { id: 'overview', label: 'Übersicht', icon: '📊' },
    { id: 'vulnerabilities', label: 'Schwachstellen', icon: '🛡️' },
    { id: 'intrusions', label: 'Intrusionen', icon: '🚨' },
    { id: 'bans', label: 'IP-Bans', icon: '🚫' },
    { id: 'threats', label: 'Threat Intel', icon: '🎯' },
    { id: 'baselines', label: 'Compliance', icon: '📋' },
    { id: 'honeypot', label: 'Honeypot', icon: '🍯' },
    { id: 'failed-auth', label: 'Failed Auth', icon: '🔑' },
  ]

  if (showSettings) {
    return (
      <div style={{ padding: '16px' }}>
        <button onClick={() => setShowSettings(false)} style={{ marginBottom: '12px', padding: '4px 12px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 'var(--radius)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '11px' }}>← Zurück</button>
        <AppSettingsPanel schema={schema} settings={settings} onUpdate={updateSetting} onReset={resetSettings} title="Security Dashboard" />
      </div>
    )
  }

  if (loading && !status) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', gap: 12 }}>
        <div style={{ fontSize: 48 }}>🔍</div>
        <div style={{ fontSize: 14, color: 'var(--text-secondary)' }}>Security-Status lade...</div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', fontFamily: 'var(--font-sans)' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <ScoreRing score={securityScore} size={56} stroke={6} label="Score" />
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>Security Center</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
              {openVulns} offene Schwachstellen · {activeBans} IP-Bans · {threatIndicators} Threat Indicators
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button onClick={loadAll} style={{ padding: '6px 12px', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', color: 'var(--text-secondary)', fontSize: 12, cursor: 'pointer' }}>🔄 Aktualisieren</button>
          <button onClick={() => setShowSettings(true)} style={{ padding: '6px 12px', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', color: 'var(--text-secondary)', fontSize: 12, cursor: 'pointer' }}>⚙️</button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, padding: '8px 16px', borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)', overflowX: 'auto' }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: '6px 14px', border: '1px solid', borderRadius: 'var(--radius)',
            background: tab === t.id ? 'rgba(0,255,204,0.1)' : 'transparent',
            borderColor: tab === t.id ? 'var(--accent)' : 'var(--border)',
            color: tab === t.id ? 'var(--accent)' : 'var(--text-secondary)',
            fontSize: 12, cursor: 'pointer', whiteSpace: 'nowrap',
          }}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
        {tab === 'overview' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Stat Cards */}
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <StatCard icon="🛡️" label="Offene Schwachstellen" value={openVulns} sub={`${criticalVulns} kritisch`} color={criticalVulns > 0 ? '#ff4444' : openVulns > 0 ? '#ffaa00' : '#00ff88'} onClick={() => setTab('vulnerabilities')} />
              <StatCard icon="🚨" label="IDS Events (24h)" value={ids24h} color={ids24h > 0 ? '#ff8844' : '#00ff88'} onClick={() => setTab('intrusions')} />
              <StatCard icon="🚫" label="Aktive IP-Bans" value={activeBans} onClick={() => setTab('bans')} />
              <StatCard icon="🔑" label="Failed Auth (24h)" value={failedAuth24h} color={failedAuth24h > 10 ? '#ff8844' : 'var(--text-primary)'} onClick={() => setTab('failed-auth')} />
              <StatCard icon="🎯" label="Threat Indicators" value={threatIndicators} onClick={() => setTab('threats')} />
              <StatCard icon="🍯" label="Honeypot (24h)" value={honeypot24h} color={honeypot24h > 0 ? '#ffaa00' : '#00ff88'} onClick={() => setTab('honeypot')} />
            </div>

            {/* Compliance + AI Status */}
            <div style={{ display: 'flex', gap: 16 }}>
              <div style={{ flex: 1, padding: '16px', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                  <span style={{ fontSize: 18 }}>📋</span>
                  <span style={{ fontSize: 14, fontWeight: 600 }}>Compliance</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  <ScoreRing score={compliancePct} size={72} stroke={7} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, color: 'var(--text-primary)' }}>{baselines.filter(b => b.compliant).length} / {baselines.length} Richtlinien erfüllt</div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                      {baselines.length === 0 ? 'Keine Baselines konfiguriert' : `${(100 - compliancePct).toFixed(0)}% Abweichungen`}
                    </div>
                  </div>
                </div>
              </div>
              <div style={{ flex: 1, padding: '16px', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                  <span style={{ fontSize: 18 }}>🤖</span>
                  <span style={{ fontSize: 14, fontWeight: 600 }}>AI Security</span>
                </div>
                {aiStatus ? (
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                    {aiStatus.model && <div>Modell: <b style={{ color: 'var(--text-primary)' }}>{aiStatus.model}</b></div>}
                    {aiStatus.status && <div>Status: <b style={{ color: aiStatus.status === 'active' ? '#00ff88' : '#ffaa00' }}>{aiStatus.status}</b></div>}
                    {aiStatus.last_scan && <div>Letzter Scan: {formatDate(aiStatus.last_scan)} {formatTime(aiStatus.last_scan)}</div>}
                    {aiStatus.threats_detected && <div>Detects: <b>{aiStatus.threats_detected}</b></div>}
                  </div>
                ) : (
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>AI Security nicht konfiguriert</div>
                )}
              </div>
            </div>

            {/* Recent Intrusions */}
            {intrusions.length > 0 && (
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
                  🚨 Letzte Intrusion Events
                </div>
                <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
                  {intrusions.slice(0, 5).map((e, i) => <IntrusionRow key={i} e={e} />)}
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'vulnerabilities' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ margin: 0, fontSize: 16 }}>Schwachstellen ({vulns.length})</h3>
              <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{criticalVulns} kritisch · {vulns.filter(v => v.severity === 'high').length} high · {vulns.filter(v => v.severity === 'medium').length} medium</span>
            </div>
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
              {vulns.length === 0 ? (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  <div style={{ fontSize: 40, marginBottom: 8 }}>✅</div>
                  Keine offenen Schwachstellen gefunden
                </div>
              ) : (
                vulns.map((v, i) => <VulnRow key={v.id || i} v={v} onMitigate={handleMitigate} />)
              )}
            </div>
          </div>
        )}

        {tab === 'intrusions' && (
          <div>
            <h3 style={{ marginBottom: 12, fontSize: 16 }}>Intrusion Events (24h) — {intrusions.length}</h3>
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
              {intrusions.length === 0 ? (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  <div style={{ fontSize: 40, marginBottom: 8 }}>✅</div>
                  Keine Intrusion Events in den letzten 24 Stunden
                </div>
              ) : (
                intrusions.map((e, i) => <IntrusionRow key={i} e={e} />)
              )}
            </div>
          </div>
        )}

        {tab === 'bans' && (
          <div>
            <h3 style={{ marginBottom: 12, fontSize: 16 }}>IP-Bans — {bans.length}</h3>
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
              {bans.length === 0 ? (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  <div style={{ fontSize: 40, marginBottom: 8 }}>✅</div>
                  Keine aktiven IP-Bans
                </div>
              ) : (
                bans.map((b, i) => <BanRow key={b.id || i} b={b} onUnban={handleUnban} />)
              )}
            </div>
          </div>
        )}

        {tab === 'threats' && (
          <div>
            <h3 style={{ marginBottom: 12, fontSize: 16 }}>Threat Intelligence — {threats.length}</h3>
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
              {threats.length === 0 ? (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  <div style={{ fontSize: 40, marginBottom: 8 }}>🎯</div>
                  Keine Threat Indicators
                </div>
              ) : (
                threats.map((t, i) => <ThreatRow key={i} t={t} />)
              )}
            </div>
          </div>
        )}

        {tab === 'baselines' && (
          <div>
            <h3 style={{ marginBottom: 12, fontSize: 16 }}>Security Baselines — {baselines.length}</h3>
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
              {baselines.length === 0 ? (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  <div style={{ fontSize: 40, marginBottom: 8 }}>📋</div>
                  Keine Security Baselines konfiguriert
                </div>
              ) : (
                baselines.map((b, i) => <BaselineRow key={i} b={b} />)
              )}
            </div>
          </div>
        )}

        {tab === 'honeypot' && (
          <div>
            <h3 style={{ marginBottom: 12, fontSize: 16 }}>Honeypot Events (24h) — {honeypot.length}</h3>
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
              {honeypot.length === 0 ? (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  <div style={{ fontSize: 40, marginBottom: 8 }}>🍯</div>
                  Keine Honeypot Events
                </div>
              ) : (
                honeypot.map((h, i) => (
                  <div key={i} style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 10, alignItems: 'center' }}>
                    <span style={{ fontSize: 16 }}>🐝</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, fontWeight: 600 }}>{h.event_type || h.type || 'Honeypot Trigger'}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                        {h.source_ip && <span>IP: <b>{h.source_ip}</b></span>}
                        <span> · {formatDate(h.detected_at)} {formatTime(h.detected_at)}</span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {tab === 'failed-auth' && (
          <div>
            <h3 style={{ marginBottom: 12, fontSize: 16 }}>Failed Auth Attempts (24h) — {failedAuth.length}</h3>
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
              {failedAuth.length === 0 ? (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  <div style={{ fontSize: 40, marginBottom: 8 }}>✅</div>
                  Keine fehlgeschlagenen Auth-Versuche
                </div>
              ) : (
                failedAuth.map((a, i) => (
                  <div key={i} style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 10, alignItems: 'center' }}>
                    <span style={{ fontSize: 16 }}>🔑</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, fontWeight: 600 }}>{a.username || a.user || 'Unbekannter User'}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                        {a.ip_address && <span>IP: <b style={{ fontFamily: 'var(--font-mono)' }}>{a.ip_address}</b></span>}
                        <span> · {formatDate(a.attempt_at)} {formatTime(a.attempt_at)}</span>
                      </div>
                    </div>
                    <span style={{
                      padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                      background: '#ff444422', color: '#ff4444', border: '1px solid #ff444444',
                    }}>Gefehlschlagen</span>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
