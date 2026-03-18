import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

// ─── Ghost Updater ───────────────────────────────────────────────
// CI/CD Dashboard & OTA Update-Kanal für GhostShell OS.
// Zeigt: Aktueller Status, verfügbare Updates, Releases, Migrationen,
//        Pipeline-History, verbundene Nodes, Update-Jobs.
// ─────────────────────────────────────────────────────────────────

export default function GhostUpdater() {
  const { settings, schema, update, reset } = useAppSettings('ghost_updater')
  const [showSettings, setShowSettings] = useState(false)
  const [tab, setTab] = useState('overview')
  const [status, setStatus] = useState(null)
  const [releases, setReleases] = useState([])
  const [channels, setChannels] = useState([])
  const [migrations, setMigrations] = useState([])
  const [pending, setPending] = useState([])
  const [migrationStatus, setMigrationStatus] = useState(null)
  const [pipelines, setPipelines] = useState([])
  const [nodes, setNodes] = useState([])
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(false)
  const [actionResult, setActionResult] = useState(null)

  // Release-Dialog
  const [showRelease, setShowRelease] = useState(false)
  const [releaseForm, setReleaseForm] = useState({
    version: '', channel: 'stable', release_notes: ''
  })

  // ─── Daten laden ───
  const loadOverview = useCallback(async () => {
    try {
      const s = await api.updaterStatus()
      setStatus(s)
    } catch (e) { console.error('Status-Fehler:', e) }
  }, [])

  const loadReleases = useCallback(async () => {
    try {
      const r = await api.updaterReleases()
      setReleases(Array.isArray(r) ? r : [])
      const c = await api.updaterChannels()
      setChannels(Array.isArray(c) ? c : [])
    } catch (e) { console.error(e) }
  }, [])

  const loadMigrations = useCallback(async () => {
    try {
      const [h, p, s] = await Promise.all([
        api.migrationsHistory(),
        api.migrationsPending(),
        api.migrationsStatus(),
      ])
      setMigrations(Array.isArray(h) ? h : [])
      setPending(Array.isArray(p) ? p : [])
      setMigrationStatus(s)
    } catch (e) { console.error(e) }
  }, [])

  const loadPipeline = useCallback(async () => {
    try {
      const p = await api.pipelineHistory()
      setPipelines(Array.isArray(p) ? p : [])
    } catch (e) { console.error(e) }
  }, [])

  const loadNodes = useCallback(async () => {
    try {
      const [n, j] = await Promise.all([
        api.otaNodes(),
        api.otaJobs(),
      ])
      setNodes(Array.isArray(n) ? n : [])
      setJobs(Array.isArray(j) ? j : [])
    } catch (e) { console.error(e) }
  }, [])

  useEffect(() => {
    loadOverview()
    const iv = setInterval(loadOverview, 30000)
    return () => clearInterval(iv)
  }, [loadOverview])

  useEffect(() => {
    if (tab === 'releases') loadReleases()
    if (tab === 'migrations') loadMigrations()
    if (tab === 'pipeline') loadPipeline()
    if (tab === 'nodes') loadNodes()
  }, [tab])

  // ─── Aktionen ───
  const checkForUpdates = async () => {
    setLoading(true)
    try {
      const r = await api.updaterCheck()
      setActionResult(r)
      loadOverview()
    } catch (e) { setActionResult({ error: e.message }) }
    setLoading(false)
  }

  const applyUpdate = async (version) => {
    if (!confirm(`Update auf v${version || 'latest'} anwenden?\n\nDies wird:\n• Git Pull ausführen\n• SQL-Migrationen anwenden\n• Frontend neu bauen\n• Bei Fehler: Automatischer Rollback`)) return
    setLoading(true)
    setActionResult(null)
    try {
      const r = await api.updaterApply(version)
      setActionResult(r)
      loadOverview()
    } catch (e) { setActionResult({ error: e.message }) }
    setLoading(false)
  }

  const runPipeline = async () => {
    setLoading(true)
    try {
      const r = await api.pipelineRun()
      setActionResult(r)
      loadPipeline()
    } catch (e) { setActionResult({ error: e.message }) }
    setLoading(false)
  }

  const applyMigrations = async (dryRun = false) => {
    setLoading(true)
    try {
      const r = await api.migrationsApply(dryRun)
      setActionResult(r)
      loadMigrations()
    } catch (e) { setActionResult({ error: e.message }) }
    setLoading(false)
  }

  const rollbackMigration = async () => {
    if (!confirm('Letzte Migration zurückrollen?')) return
    setLoading(true)
    try {
      const r = await api.migrationsRollback()
      setActionResult(r)
      loadMigrations()
    } catch (e) { setActionResult({ error: e.message }) }
    setLoading(false)
  }

  const createRelease = async () => {
    if (!releaseForm.version) return
    setLoading(true)
    try {
      const r = await api.updaterCreateRelease(releaseForm)
      setActionResult(r)
      setShowRelease(false)
      setReleaseForm({ version: '', channel: 'stable', release_notes: '' })
      loadReleases()
    } catch (e) { setActionResult({ error: e.message }) }
    setLoading(false)
  }

  // ─── Styles ───
  const S = {
    container: { padding: 16, height: '100%', overflow: 'auto', background: '#0a0a14', color: '#c8d0d8' },
    tabs: { display: 'flex', gap: 2, marginBottom: 16, borderBottom: '1px solid #1a2a3a', paddingBottom: 8 },
    tab: (active) => ({
      padding: '8px 16px', cursor: 'pointer', border: 'none', borderRadius: '6px 6px 0 0',
      background: active ? '#0f1520' : 'transparent', color: active ? '#00ffcc' : '#6a7a8a',
      fontWeight: active ? 600 : 400, fontSize: 13, transition: 'all 0.2s',
    }),
    card: { background: '#0f1520', borderRadius: 8, border: '1px solid #1a2a3a', padding: 16, marginBottom: 12 },
    cardTitle: { color: '#00ffcc', fontSize: 14, fontWeight: 600, marginBottom: 10 },
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, marginBottom: 16 },
    stat: { background: '#0f1520', borderRadius: 8, border: '1px solid #1a2a3a', padding: 14, textAlign: 'center' },
    statValue: { fontSize: 28, fontWeight: 700, color: '#00ffcc' },
    statLabel: { fontSize: 11, color: '#6a7a8a', marginTop: 4, textTransform: 'uppercase' },
    btn: (color = '#00ffcc') => ({
      padding: '8px 16px', border: `1px solid ${color}`, borderRadius: 6, cursor: 'pointer',
      background: 'transparent', color, fontSize: 12, fontWeight: 600, transition: 'all 0.2s',
    }),
    btnPrimary: {
      padding: '10px 20px', border: 'none', borderRadius: 6, cursor: 'pointer',
      background: 'linear-gradient(135deg, #00ffcc, #00cc99)', color: '#0a0a14',
      fontSize: 13, fontWeight: 700, transition: 'all 0.2s',
    },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
    th: { textAlign: 'left', padding: '8px 10px', borderBottom: '1px solid #1a2a3a', color: '#6a7a8a', fontSize: 11, textTransform: 'uppercase' },
    td: { padding: '8px 10px', borderBottom: '1px solid #0d1520' },
    badge: (color) => ({
      display: 'inline-block', padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600,
      background: color + '22', color, border: `1px solid ${color}44`,
    }),
    resultBox: (ok) => ({
      background: ok ? '#00ffcc11' : '#ff444411', border: `1px solid ${ok ? '#00ffcc' : '#ff4444'}44`,
      borderRadius: 8, padding: 12, marginBottom: 12, fontSize: 12,
    }),
    input: {
      width: '100%', padding: '8px 12px', background: '#0a0a14', border: '1px solid #1a2a3a',
      borderRadius: 6, color: '#c8d0d8', fontSize: 13, outline: 'none',
    },
    textarea: {
      width: '100%', padding: '8px 12px', background: '#0a0a14', border: '1px solid #1a2a3a',
      borderRadius: 6, color: '#c8d0d8', fontSize: 13, outline: 'none', minHeight: 80, resize: 'vertical',
    },
    overlay: {
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    },
    modal: {
      background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: 12,
      padding: 24, width: 420, maxWidth: '90vw',
    },
  }

  const statusColor = (s) => {
    if (!s) return '#6a7a8a'
    const map = {
      success: '#00ffcc', online: '#00ffcc', published: '#00ffcc',
      running: '#ffa500', updating: '#ffa500', applying: '#ffa500', downloading: '#ffa500', queued: '#ffa500',
      pending: '#ffa500', warning: '#ffa500',
      failed: '#ff4444', error: '#ff4444', rolled_back: '#ff8844', rollback: '#ff8844',
      offline: '#6a7a8a', cancelled: '#6a7a8a', skipped: '#6a7a8a',
    }
    return map[s] || '#6a7a8a'
  }

  const fmtTime = (t) => {
    if (!t) return '—'
    const d = new Date(t)
    return d.toLocaleDateString('de-DE') + ' ' + d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
  }

  const fmtDuration = (ms) => {
    if (!ms) return '—'
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  // ─── Tab: Übersicht ───
  const renderOverview = () => (
    <>
      {/* Update-Banner */}
      {status?.available_update && (
        <div style={{ ...S.card, border: '1px solid #00ffcc44', background: '#00ffcc08' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#00ffcc', marginBottom: 4 }}>
                🚀 Ghost-Evolution verfügbar: v{status.available_update.version}
              </div>
              <div style={{ fontSize: 12, color: '#8a9aaa' }}>
                {status.available_update.release_notes || 'Neue Version bereit zur Installation'}
                {status.available_update.is_critical && (
                  <span style={S.badge('#ff4444')}> Sicherheitsupdate</span>
                )}
              </div>
            </div>
            <button
              style={S.btnPrimary}
              disabled={loading}
              onClick={() => applyUpdate(status.available_update.version)}
            >
              {loading ? '⏳ Wird angewendet...' : '🔄 Jetzt updaten'}
            </button>
          </div>
        </div>
      )}

      {/* Status-Cards */}
      <div style={S.grid}>
        <div style={S.stat}>
          <div style={S.statValue}>{status?.current_version || '—'}</div>
          <div style={S.statLabel}>Aktuelle Version</div>
        </div>
        <div style={S.stat}>
          <div style={{ ...S.statValue, color: status?.node?.status === 'online' ? '#00ffcc' : '#ff4444' }}>
            {status?.node?.status || '—'}
          </div>
          <div style={S.statLabel}>Node-Status</div>
        </div>
        <div style={S.stat}>
          <div style={S.statValue}>
            {status?.migration_status?.current_schema_version || '—'}
          </div>
          <div style={S.statLabel}>Schema-Version</div>
        </div>
        <div style={S.stat}>
          <div style={{ ...S.statValue, color: status?.migration_status?.failed > 0 ? '#ff4444' : '#00ffcc' }}>
            {status?.migration_status?.successful || 0}
          </div>
          <div style={S.statLabel}>Migrationen erfolgreich</div>
        </div>
      </div>

      {/* Aktionen */}
      <div style={S.card}>
        <div style={S.cardTitle}>⚡ Schnellaktionen</div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button style={S.btn()} onClick={checkForUpdates} disabled={loading}>
            🔍 Auf Updates prüfen
          </button>
          <button style={S.btn('#ffa500')} onClick={runPipeline} disabled={loading}>
            🔨 CI-Pipeline starten
          </button>
          <button style={S.btn('#88aaff')} onClick={() => applyMigrations(true)} disabled={loading}>
            📋 Dry-Run Migrationen
          </button>
          <button style={S.btn('#ff8844')} onClick={() => applyUpdate()} disabled={loading}>
            🔄 Manuelles Update
          </button>
        </div>
      </div>

      {/* Action Result */}
      {actionResult && (
        <div style={S.resultBox(!actionResult.error && actionResult.status !== 'failed')}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>
            {actionResult.status === 'success' ? '✅ Erfolgreich' :
             actionResult.error ? '❌ Fehler' :
             actionResult.available !== undefined ? (actionResult.available ? '🆕 Update verfügbar' : '✅ Kein Update verfügbar') :
             `ℹ️ Status: ${actionResult.status || 'unbekannt'}`}
          </div>
          {actionResult.error && <div style={{ color: '#ff6666' }}>{actionResult.error}</div>}
          {actionResult.version && <div>Version: <strong>{actionResult.version}</strong></div>}
          {actionResult.duration_ms && <div>Dauer: {fmtDuration(actionResult.duration_ms)}</div>}
          {actionResult.steps && (
            <div style={{ marginTop: 8 }}>
              {actionResult.steps.map((s, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, padding: '3px 0' }}>
                  <span style={{ color: statusColor(s.status) }}>
                    {s.status === 'success' ? '✓' : s.status === 'failed' ? '✗' : s.status === 'skipped' ? '○' : '●'}
                  </span>
                  <span>{s.name}</span>
                  <span style={{ color: '#6a7a8a', marginLeft: 'auto' }}>{fmtDuration(s.duration_ms)}</span>
                </div>
              ))}
            </div>
          )}
          {actionResult.results && Array.isArray(actionResult.results) && (
            <div style={{ marginTop: 6 }}>
              {actionResult.results.map((r, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, padding: '2px 0' }}>
                  <span style={{ color: statusColor(r.status) }}>
                    {r.status === 'success' ? '✓' : r.status === 'failed' ? '✗' : '●'}
                  </span>
                  <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{r.file}</span>
                  {r.error && <span style={{ color: '#ff6666', fontSize: 11 }}>{r.error}</span>}
                </div>
              ))}
            </div>
          )}
          <button style={{ ...S.btn('#6a7a8a'), marginTop: 8, fontSize: 11 }} onClick={() => setActionResult(null)}>
            Schließen
          </button>
        </div>
      )}

      {/* Update-Flow Diagramm */}
      <div style={S.card}>
        <div style={S.cardTitle}>🔄 Update-Flow (Atomic OTA)</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', fontSize: 12 }}>
          {['git push', '→', 'CI Pipeline', '→', 'Build & Test', '→', 'Release', '→',
            'OTA Check', '→', 'Download', '→', 'Backup', '→', 'Migrationen', '→',
            'Frontend Build', '→', 'Healthcheck', '→', 'Live ✓'].map((s, i) => (
            <span key={i} style={{
              padding: s === '→' ? 0 : '4px 10px',
              background: s === '→' ? 'transparent' : '#1a2a3a',
              borderRadius: 4, color: s === '→' ? '#3a4a5a' : (s === 'Live ✓' ? '#00ffcc' : '#c8d0d8'),
              fontWeight: s === 'Live ✓' ? 700 : 400,
            }}>
              {s}
            </span>
          ))}
        </div>
        <div style={{ marginTop: 10, fontSize: 11, color: '#6a7a8a' }}>
          Bei Fehler in jedem Schritt → Automatischer Rollback auf vorherige Version
        </div>
      </div>
    </>
  )

  // ─── Tab: Releases ───
  const renderReleases = () => (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#00ffcc' }}>📦 Releases</div>
        <button style={S.btnPrimary} onClick={() => setShowRelease(true)}>+ Neues Release</button>
      </div>

      {/* Kanäle */}
      {channels.length > 0 && (
        <div style={{ ...S.card, marginBottom: 12 }}>
          <div style={S.cardTitle}>📡 Update-Kanäle</div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {channels.map((c, i) => (
              <div key={i} style={{
                padding: '8px 14px', borderRadius: 6,
                border: `1px solid ${c.is_active ? '#00ffcc44' : '#1a2a3a'}`,
                background: c.is_default ? '#00ffcc11' : '#0a0a14',
              }}>
                <div style={{ fontWeight: 600, fontSize: 13 }}>
                  {c.channel_name} {c.is_default && <span style={S.badge('#00ffcc')}>Standard</span>}
                </div>
                <div style={{ fontSize: 11, color: '#6a7a8a' }}>{c.description}</div>
                {c.branch && <div style={{ fontSize: 10, color: '#4a5a6a' }}>Branch: {c.branch}</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Releases-Tabelle */}
      <table style={S.table}>
        <thead>
          <tr>
            <th style={S.th}>Version</th>
            <th style={S.th}>Kanal</th>
            <th style={S.th}>Schema</th>
            <th style={S.th}>Commit</th>
            <th style={S.th}>Autor</th>
            <th style={S.th}>Veröffentlicht</th>
            <th style={S.th}>Flags</th>
          </tr>
        </thead>
        <tbody>
          {releases.map((r, i) => (
            <tr key={i} style={{ cursor: 'pointer' }} onClick={() => setActionResult({
              status: 'info', version: r.version,
              release_notes: r.release_notes, commit: r.commit_hash
            })}>
              <td style={S.td}><strong style={{ color: '#00ffcc' }}>v{r.version}</strong></td>
              <td style={S.td}><span style={S.badge('#88aaff')}>{r.channel}</span></td>
              <td style={S.td}>{r.schema_version || '—'}</td>
              <td style={{ ...S.td, fontFamily: 'monospace', fontSize: 11 }}>
                {r.commit_hash ? r.commit_hash.slice(0, 8) : '—'}
              </td>
              <td style={S.td}>{r.author || '—'}</td>
              <td style={S.td}>{fmtTime(r.published_at)}</td>
              <td style={S.td}>
                {r.is_critical && <span style={S.badge('#ff4444')}>Critical</span>}
                {r.requires_restart && <span style={{ ...S.badge('#ffa500'), marginLeft: 4 }}>Restart</span>}
              </td>
            </tr>
          ))}
          {releases.length === 0 && (
            <tr><td colSpan={7} style={{ ...S.td, textAlign: 'center', color: '#4a5a6a' }}>Keine Releases vorhanden</td></tr>
          )}
        </tbody>
      </table>

      {/* Release-Dialog */}
      {showRelease && (
        <div style={S.overlay} onClick={() => setShowRelease(false)}>
          <div style={S.modal} onClick={(e) => e.stopPropagation()}>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#00ffcc', marginBottom: 16 }}>
              🚀 Neues Release erstellen
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 11, color: '#6a7a8a', display: 'block', marginBottom: 4 }}>Version *</label>
              <input style={S.input} placeholder="z.B. 0.9.0"
                value={releaseForm.version}
                onChange={(e) => setReleaseForm(f => ({ ...f, version: e.target.value }))} />
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 11, color: '#6a7a8a', display: 'block', marginBottom: 4 }}>Kanal</label>
              <select style={S.input} value={releaseForm.channel}
                onChange={(e) => setReleaseForm(f => ({ ...f, channel: e.target.value }))}>
                <option value="stable">stable</option>
                <option value="beta">beta</option>
                <option value="nightly">nightly</option>
                <option value="dev">dev</option>
              </select>
            </div>
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 11, color: '#6a7a8a', display: 'block', marginBottom: 4 }}>Release-Notes</label>
              <textarea style={S.textarea} placeholder="Was ist neu in dieser Version?"
                value={releaseForm.release_notes}
                onChange={(e) => setReleaseForm(f => ({ ...f, release_notes: e.target.value }))} />
            </div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button style={S.btn('#6a7a8a')} onClick={() => setShowRelease(false)}>Abbrechen</button>
              <button style={S.btnPrimary} onClick={createRelease} disabled={loading || !releaseForm.version}>
                {loading ? '⏳...' : '📦 Veröffentlichen'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )

  // ─── Tab: Migrationen ───
  const renderMigrations = () => (
    <>
      {/* Status-Übersicht */}
      {migrationStatus && (
        <div style={S.grid}>
          <div style={S.stat}>
            <div style={S.statValue}>{migrationStatus.total_migrations || 0}</div>
            <div style={S.statLabel}>Gesamt</div>
          </div>
          <div style={S.stat}>
            <div style={{ ...S.statValue, color: '#00ffcc' }}>{migrationStatus.successful || 0}</div>
            <div style={S.statLabel}>Erfolgreich</div>
          </div>
          <div style={S.stat}>
            <div style={{ ...S.statValue, color: migrationStatus.failed > 0 ? '#ff4444' : '#6a7a8a' }}>
              {migrationStatus.failed || 0}
            </div>
            <div style={S.statLabel}>Fehlgeschlagen</div>
          </div>
          <div style={S.stat}>
            <div style={{ ...S.statValue, color: '#ffa500' }}>{migrationStatus.pending || 0}</div>
            <div style={S.statLabel}>Ausstehend</div>
          </div>
        </div>
      )}

      {/* Pending */}
      {pending.length > 0 && (
        <div style={{ ...S.card, border: '1px solid #ffa50044' }}>
          <div style={{ ...S.cardTitle, color: '#ffa500' }}>⏳ Ausstehende Migrationen ({pending.length})</div>
          {pending.map((p, i) => (
            <div key={i} style={{ padding: '6px 0', borderBottom: '1px solid #1a2a3a', display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{p.file}</span>
              <span style={{ color: '#6a7a8a', fontSize: 11 }}>#{p.number}</span>
            </div>
          ))}
          <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
            <button style={S.btn('#ffa500')} onClick={() => applyMigrations(true)} disabled={loading}>
              📋 Dry-Run
            </button>
            <button style={S.btnPrimary} onClick={() => applyMigrations(false)} disabled={loading}>
              ▶️ Jetzt anwenden
            </button>
          </div>
        </div>
      )}

      {/* Aktionen */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
        <button style={S.btn('#ff8844')} onClick={rollbackMigration} disabled={loading}>
          ↩️ Letzte zurückrollen
        </button>
        <button style={S.btn()} onClick={loadMigrations} disabled={loading}>
          🔄 Aktualisieren
        </button>
      </div>

      {/* History */}
      <table style={S.table}>
        <thead>
          <tr>
            <th style={S.th}>#</th>
            <th style={S.th}>Schema-Datei</th>
            <th style={S.th}>Status</th>
            <th style={S.th}>Richtung</th>
            <th style={S.th}>Dauer</th>
            <th style={S.th}>Angewendet</th>
            <th style={S.th}>Von</th>
          </tr>
        </thead>
        <tbody>
          {migrations.map((m, i) => (
            <tr key={i}>
              <td style={S.td}>{m.schema_number}</td>
              <td style={{ ...S.td, fontFamily: 'monospace', fontSize: 11 }}>{m.schema_file}</td>
              <td style={S.td}><span style={S.badge(statusColor(m.status))}>{m.status}</span></td>
              <td style={S.td}>{m.direction}</td>
              <td style={S.td}>{fmtDuration(m.duration_ms)}</td>
              <td style={S.td}>{fmtTime(m.finished_at)}</td>
              <td style={S.td}>{m.applied_by || '—'}</td>
            </tr>
          ))}
          {migrations.length === 0 && (
            <tr><td colSpan={7} style={{ ...S.td, textAlign: 'center', color: '#4a5a6a' }}>Keine Migrationen aufgezeichnet</td></tr>
          )}
        </tbody>
      </table>
    </>
  )

  // ─── Tab: Pipeline ───
  const renderPipeline = () => (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#00ffcc' }}>🔨 Build-Pipeline</div>
        <button style={S.btnPrimary} onClick={runPipeline} disabled={loading}>
          {loading ? '⏳ Läuft...' : '▶️ Pipeline starten'}
        </button>
      </div>

      {/* Pipeline-Schritte Legende */}
      <div style={{ ...S.card, fontSize: 12 }}>
        <div style={S.cardTitle}>Pipeline-Schritte</div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {['Python Syntax Check', 'SQL Validierung', 'Frontend Build', 'Tests'].map((s, i) => (
            <span key={i} style={{ color: '#8a9aaa' }}>
              {i + 1}. {s}
            </span>
          ))}
        </div>
      </div>

      {/* Pipeline-History */}
      <table style={S.table}>
        <thead>
          <tr>
            <th style={S.th}>Build</th>
            <th style={S.th}>Branch</th>
            <th style={S.th}>Commit</th>
            <th style={S.th}>Trigger</th>
            <th style={S.th}>Status</th>
            <th style={S.th}>Dauer</th>
            <th style={S.th}>Gestartet</th>
            <th style={S.th}>Schritte</th>
          </tr>
        </thead>
        <tbody>
          {pipelines.map((p, i) => {
            const steps = Array.isArray(p.steps) ? p.steps : (typeof p.steps === 'string' ? JSON.parse(p.steps || '[]') : [])
            return (
              <tr key={i} style={{ cursor: 'pointer' }} onClick={() => setActionResult({
                status: p.status, steps, duration_ms: p.duration_ms, error: p.error_message
              })}>
                <td style={S.td}>#{p.build_number || i + 1}</td>
                <td style={S.td}>{p.branch}</td>
                <td style={{ ...S.td, fontFamily: 'monospace', fontSize: 11 }}>
                  {p.commit_hash ? p.commit_hash.slice(0, 8) : '—'}
                </td>
                <td style={S.td}>{p.trigger_type}</td>
                <td style={S.td}><span style={S.badge(statusColor(p.status))}>{p.status}</span></td>
                <td style={S.td}>{fmtDuration(p.duration_ms)}</td>
                <td style={S.td}>{fmtTime(p.started_at)}</td>
                <td style={S.td}>
                  {steps.map((s, j) => (
                    <span key={j} style={{ color: statusColor(s.status), marginRight: 4 }} title={s.name}>
                      {s.status === 'success' ? '●' : s.status === 'failed' ? '✗' : '○'}
                    </span>
                  ))}
                </td>
              </tr>
            )
          })}
          {pipelines.length === 0 && (
            <tr><td colSpan={8} style={{ ...S.td, textAlign: 'center', color: '#4a5a6a' }}>Keine Pipeline-Runs vorhanden</td></tr>
          )}
        </tbody>
      </table>
    </>
  )

  // ─── Tab: Nodes ───
  const renderNodes = () => (
    <>
      <div style={{ fontSize: 14, fontWeight: 600, color: '#00ffcc', marginBottom: 12 }}>
        📡 Verbundene Nodes (OTA-Empfänger)
      </div>

      {/* Nodes */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12, marginBottom: 16 }}>
        {nodes.map((n, i) => (
          <div key={i} style={{ ...S.card, borderColor: statusColor(n.status) + '44' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <strong style={{ color: '#c8d0d8' }}>{n.node_name}</strong>
              <span style={S.badge(statusColor(n.status))}>{n.status}</span>
            </div>
            <div style={{ fontSize: 11, color: '#6a7a8a', lineHeight: 1.8 }}>
              <div>🖥️ {n.hostname || '—'} ({n.ip_address || '—'})</div>
              <div>📦 Version: <strong style={{ color: '#00ffcc' }}>v{n.current_version || '?'}</strong></div>
              <div>📡 Kanal: {n.channel}</div>
              <div>🔄 Auto-Update: {n.auto_update ? '✅ Aktiv' : '❌ Aus'}</div>
              <div>🕐 Letzter Check: {fmtTime(n.last_checkin)}</div>
              {n.target_version && (
                <div style={{ color: '#ffa500' }}>🎯 Ziel: v{n.target_version}</div>
              )}
            </div>
          </div>
        ))}
        {nodes.length === 0 && (
          <div style={{ ...S.card, textAlign: 'center', color: '#4a5a6a' }}>
            Keine Nodes registriert. Der erste Node wird beim Start automatisch hinzugefügt.
          </div>
        )}
      </div>

      {/* Update-Jobs */}
      <div style={{ fontSize: 14, fontWeight: 600, color: '#00ffcc', marginBottom: 12 }}>📋 Update-Jobs</div>
      <table style={S.table}>
        <thead>
          <tr>
            <th style={S.th}>Node</th>
            <th style={S.th}>Von</th>
            <th style={S.th}>Nach</th>
            <th style={S.th}>Status</th>
            <th style={S.th}>Fortschritt</th>
            <th style={S.th}>Dauer</th>
            <th style={S.th}>Gestartet</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((j, i) => (
            <tr key={i}>
              <td style={S.td}>{j.node_name || '—'}</td>
              <td style={S.td}>v{j.from_version || '?'}</td>
              <td style={S.td}><strong style={{ color: '#00ffcc' }}>v{j.to_version}</strong></td>
              <td style={S.td}><span style={S.badge(statusColor(j.status))}>{j.status}</span></td>
              <td style={S.td}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ flex: 1, height: 6, background: '#1a2a3a', borderRadius: 3 }}>
                    <div style={{
                      width: `${j.progress || 0}%`, height: '100%', borderRadius: 3,
                      background: j.status === 'failed' ? '#ff4444' : '#00ffcc',
                      transition: 'width 0.5s',
                    }} />
                  </div>
                  <span style={{ fontSize: 10, color: '#6a7a8a' }}>{j.progress || 0}%</span>
                </div>
              </td>
              <td style={S.td}>{fmtDuration(j.duration_ms)}</td>
              <td style={S.td}>{fmtTime(j.started_at)}</td>
            </tr>
          ))}
          {jobs.length === 0 && (
            <tr><td colSpan={7} style={{ ...S.td, textAlign: 'center', color: '#4a5a6a' }}>Keine Update-Jobs</td></tr>
          )}
        </tbody>
      </table>
    </>
  )

  // ─── Hauptrender ───
  const tabs = [
    { id: 'overview',   label: '📊 Übersicht' },
    { id: 'releases',   label: '📦 Releases' },
    { id: 'migrations', label: '🗃️ Migrationen' },
    { id: 'pipeline',   label: '🔨 Pipeline' },
    { id: 'nodes',      label: '📡 Nodes' },
  ]

  return (
    <div style={S.container}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <span style={{ fontSize: 22 }}>🚀</span>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#00ffcc' }}>Ghost Updater</div>
          <div style={{ fontSize: 11, color: '#6a7a8a' }}>CI/CD Pipeline & OTA Update-Kanal</div>
        </div>
        {loading && (
          <div style={{ marginLeft: 'auto', color: '#ffa500', fontSize: 12, animation: 'pulse 1s infinite' }}>
            ⏳ Verarbeitung...
          </div>
        )}
        <button style={{ marginLeft: loading ? '8px' : 'auto', background: '#1a2a3a', border: '1px solid #2a3a4a', borderRadius: 6, padding: '4px 10px', cursor: 'pointer', color: '#8a9aaa' }} onClick={() => setShowSettings(!showSettings)}>⚙️</button>
      </div>
      {showSettings && <AppSettingsPanel settings={settings} schema={schema} onUpdate={update} onReset={reset} />}

      {/* Tabs */}
      <div style={S.tabs}>
        {tabs.map(t => (
          <button key={t.id} style={S.tab(tab === t.id)}
            onClick={() => { setTab(t.id); setActionResult(null) }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab-Inhalt */}
      {tab === 'overview' && renderOverview()}
      {tab === 'releases' && renderReleases()}
      {tab === 'migrations' && renderMigrations()}
      {tab === 'pipeline' && renderPipeline()}
      {tab === 'nodes' && renderNodes()}
    </div>
  )
}
