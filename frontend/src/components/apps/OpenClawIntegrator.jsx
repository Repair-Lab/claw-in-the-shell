import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'

/**
 * OpenClaw Integrator — Skills migrieren, Memories importieren, Status prüfen
 * Quelle: dbai_core.openclaw_skills, dbai_vector.openclaw_memories, dbai_core.migration_jobs
 */
export default function OpenClawIntegrator() {
  const [tab, setTab] = useState('skills') // skills, memories, migrations
  const [skills, setSkills] = useState([])
  const [memories, setMemories] = useState([])
  const [migrations, setMigrations] = useState([])
  const [stats, setStats] = useState({})
  const [loading, setLoading] = useState(true)
  const [importing, setImporting] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const data = await api.openclawStatus()
      setSkills(data.skills || [])
      setMemories(data.memories || [])
      setMigrations(data.migrations || [])
      setStats(data.stats || {})
    } catch (err) {
      console.error('OpenClaw-Daten laden fehlgeschlagen:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const handleActivateSkill = async (skillName) => {
    try {
      await api.openclawActivateSkill(skillName)
      setTimeout(refresh, 500)
    } catch (err) {
      alert('Aktivierung fehlgeschlagen: ' + err.message)
    }
  }

  const handleStartMigration = async () => {
    setImporting(true)
    try {
      await api.openclawStartMigration()
      setTimeout(refresh, 1000)
    } catch (err) {
      alert('Migration fehlgeschlagen: ' + err.message)
    }
    setImporting(false)
  }

  const stateColors = {
    imported: 'var(--info)',
    translating: 'var(--warning)',
    active: 'var(--success)',
    deprecated: 'var(--text-secondary)',
    incompatible: 'var(--danger)',
    testing: 'var(--accent)',
  }

  if (loading) return <div style={{ padding: 20, color: 'var(--text-secondary)' }}>Lade OpenClaw-Daten…</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', fontFamily: 'var(--font-sans)', fontSize: '13px' }}>
      {/* Stats Bar */}
      <div style={{
        display: 'flex', gap: '16px', padding: '12px 16px',
        borderBottom: '1px solid var(--border)', alignItems: 'center',
      }}>
        <div style={{ display: 'flex', gap: '24px' }}>
          <StatBadge label="Skills" value={stats.total_skills || 0} icon="⚡" color="var(--accent)" />
          <StatBadge label="Aktiv" value={stats.active_skills || 0} icon="✅" color="var(--success)" />
          <StatBadge label="Memories" value={stats.total_memories || 0} icon="🧠" color="var(--info)" />
          <StatBadge label="Integriert" value={stats.integrated_memories || 0} icon="🔗" color="var(--success)" />
          <StatBadge label="Migrationen" value={stats.total_migrations || 0} icon="📦" color="var(--warning)" />
        </div>

        <div style={{ flex: 1 }} />

        {/* Tabs */}
        {['skills', 'memories', 'migrations'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '6px 14px', borderRadius: 'var(--radius)',
            border: `1px solid ${tab === t ? 'var(--accent)' : 'var(--border)'}`,
            background: tab === t ? 'rgba(0,255,204,0.1)' : 'transparent',
            color: tab === t ? 'var(--accent)' : 'var(--text-secondary)',
            cursor: 'pointer', fontSize: '12px',
          }}>
            {t === 'skills' ? '⚡ Skills' : t === 'memories' ? '🧠 Memories' : '📦 Migrationen'}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
        {/* Skills Tab */}
        {tab === 'skills' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <h3 style={{ color: 'var(--accent)', margin: 0 }}>OpenClaw Skills → SQL-Aktionen</h3>
            </div>
            {skills.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
                Keine Skills importiert. Starte eine Migration um OpenClaw-Skills zu übernehmen.
              </div>
            ) : skills.map(skill => (
              <div key={skill.id} style={{
                display: 'flex', alignItems: 'center', gap: '12px',
                padding: '12px 14px', background: 'var(--bg-surface)',
                border: '1px solid var(--border)', borderRadius: 'var(--radius)',
                borderLeft: `3px solid ${stateColors[skill.state] || 'var(--border)'}`,
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontWeight: 600, fontSize: '13px' }}>{skill.display_name || skill.skill_name}</span>
                    <span style={{
                      fontSize: '10px', padding: '1px 6px', borderRadius: '10px',
                      background: `${stateColors[skill.state]}22`,
                      color: stateColors[skill.state],
                    }}>{skill.state}</span>
                    <span style={{
                      fontSize: '10px', padding: '1px 6px', borderRadius: '10px',
                      background: 'var(--bg-elevated)', color: 'var(--text-secondary)',
                    }}>{skill.original_lang}</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    {skill.action_type} → {skill.sql_action || 'Noch nicht übersetzt'}
                  </div>
                  {skill.compatibility_score != null && (
                    <div style={{ marginTop: '4px' }}>
                      <div style={{
                        width: '120px', height: '4px', background: 'var(--bg-elevated)',
                        borderRadius: '2px', overflow: 'hidden',
                      }}>
                        <div style={{
                          width: `${skill.compatibility_score * 100}%`, height: '100%',
                          background: skill.compatibility_score > 0.7 ? 'var(--success)' :
                                     skill.compatibility_score > 0.4 ? 'var(--warning)' : 'var(--danger)',
                        }} />
                      </div>
                      <span style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                        Kompatibilität: {Math.round(skill.compatibility_score * 100)}%
                      </span>
                    </div>
                  )}
                </div>
                {skill.state === 'imported' && (
                  <button onClick={() => handleActivateSkill(skill.skill_name)} style={{
                    padding: '6px 14px', borderRadius: 'var(--radius)',
                    background: 'rgba(0,255,204,0.1)', border: '1px solid var(--accent)',
                    color: 'var(--accent)', cursor: 'pointer', fontSize: '12px',
                  }}>
                    ⚡ Aktivieren
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Memories Tab */}
        {tab === 'memories' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ color: 'var(--accent)', margin: 0 }}>Migrierte Memories (JSON → pgvector)</h3>
              <button onClick={handleStartMigration} disabled={importing} style={{
                padding: '8px 18px', borderRadius: 'var(--radius)',
                background: importing ? 'var(--bg-elevated)' : 'rgba(0,255,204,0.1)',
                border: '1px solid var(--accent)', color: 'var(--accent)',
                cursor: importing ? 'wait' : 'pointer', fontSize: '12px',
              }}>
                {importing ? '⏳ Migriere…' : '🚀 Memory-Migration starten'}
              </button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {memories.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
                  Keine migrierten Memories vorhanden.
                </div>
              ) : memories.map(mem => (
                <div key={mem.id} style={{
                  display: 'flex', alignItems: 'center', gap: '12px',
                  padding: '10px 14px', background: 'var(--bg-surface)',
                  border: '1px solid var(--border)', borderRadius: 'var(--radius)',
                }}>
                  <span style={{ fontSize: '16px' }}>
                    {mem.content_type === 'conversation' ? '💬' :
                     mem.content_type === 'fact' ? '📌' :
                     mem.content_type === 'preference' ? '⭐' :
                     mem.content_type === 'skill_memory' ? '⚡' : '🧠'}
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={{
                      fontSize: '12px', maxHeight: '36px', overflow: 'hidden',
                      lineHeight: '1.4', color: 'var(--text-primary)',
                    }}>
                      {(mem.content || '').substring(0, 150)}…
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      {mem.content_type} • {mem.openclaw_file || '—'} •
                      Wichtigkeit: {Math.round((mem.importance || 0) * 100)}%
                    </div>
                  </div>
                  <span style={{
                    fontSize: '10px', padding: '2px 8px', borderRadius: '10px',
                    background: mem.is_integrated ? 'rgba(0,255,136,0.1)' : 'rgba(255,170,0,0.1)',
                    color: mem.is_integrated ? 'var(--success)' : 'var(--warning)',
                    border: `1px solid ${mem.is_integrated ? 'var(--success)' : 'var(--warning)'}44`,
                  }}>
                    {mem.is_integrated ? '✅ Integriert' : '⏳ Pending'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Migrations Tab */}
        {tab === 'migrations' && (
          <div>
            <h3 style={{ color: 'var(--accent)', marginTop: 0, marginBottom: '16px' }}>Migrations-Journal</h3>
            {migrations.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
                Keine Migrationen durchgeführt.
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th style={{ textAlign: 'left', padding: '8px', color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>Typ</th>
                    <th style={{ textAlign: 'left', padding: '8px', color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>Status</th>
                    <th style={{ textAlign: 'left', padding: '8px', color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>Quelle</th>
                    <th style={{ textAlign: 'right', padding: '8px', color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>Items</th>
                    <th style={{ textAlign: 'left', padding: '8px', color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>Gestartet</th>
                  </tr>
                </thead>
                <tbody>
                  {migrations.map(m => (
                    <tr key={m.id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '8px', fontFamily: 'var(--font-mono)' }}>{m.migration_type}</td>
                      <td style={{ padding: '8px' }}>
                        <span style={{
                          padding: '2px 8px', borderRadius: '10px', fontSize: '11px',
                          background: m.state === 'completed' ? 'rgba(0,255,136,0.1)' :
                                     m.state === 'running' ? 'rgba(255,170,0,0.1)' : 'rgba(255,68,68,0.1)',
                          color: m.state === 'completed' ? 'var(--success)' :
                                m.state === 'running' ? 'var(--warning)' : 'var(--danger)',
                        }}>{m.state}</span>
                      </td>
                      <td style={{ padding: '8px', fontSize: '11px', color: 'var(--text-secondary)' }}>{m.source_path || '—'}</td>
                      <td style={{ padding: '8px', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                        {m.items_processed || 0}/{m.items_total || '?'}
                      </td>
                      <td style={{ padding: '8px', fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                        {m.started_at ? new Date(m.started_at).toLocaleString('de-DE') : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// Kleine Stat-Badge Komponente
function StatBadge({ label, value, icon, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <span style={{ fontSize: '14px' }}>{icon}</span>
      <div>
        <div style={{ fontSize: '16px', fontWeight: 700, color, fontFamily: 'var(--font-mono)' }}>{value}</div>
        <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>{label}</div>
      </div>
    </div>
  )
}
