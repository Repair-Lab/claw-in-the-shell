import React, { useState, useEffect } from 'react'
import { api } from '../../api'

/**
 * Settings — System-Konfiguration: Theme, Desktop, Benutzer, Netzwerk
 */
export default function Settings({ windowId }) {
  const [tab, setTab] = useState('general')
  const [config, setConfig] = useState([])
  const [themes, setThemes] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      const [configResult, themesData] = await Promise.all([
        api.sqlQuery("SELECT key, value, category, description FROM dbai_core.config ORDER BY category, key"),
        api.themes()
      ])
      setConfig(configResult.rows || [])
      setThemes(themesData || [])
    } catch (err) {
      console.error('Settings laden fehlgeschlagen:', err)
    } finally {
      setLoading(false)
    }
  }

  const tabs = [
    { id: 'general', label: '⚙️ Allgemein', icon: '⚙️' },
    { id: 'themes', label: '🎨 Themes', icon: '🎨' },
    { id: 'database', label: '🗄️ Datenbank', icon: '🗄️' },
    { id: 'about', label: 'ℹ️ Über DBAI', icon: 'ℹ️' },
  ]

  const categories = [...new Set(config.map(c => c.category))].sort()

  return (
    <div style={{ display: 'flex', height: '100%', fontFamily: 'var(--font-sans)', fontSize: '13px' }}>
      {/* Sidebar */}
      <div style={{
        width: '200px', borderRight: '1px solid var(--border)',
        padding: '12px', display: 'flex', flexDirection: 'column', gap: '4px'
      }}>
        {tabs.map(t => (
          <div
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              padding: '8px 12px', cursor: 'pointer', borderRadius: '6px',
              background: tab === t.id ? 'var(--bg-elevated)' : 'transparent',
              color: tab === t.id ? 'var(--accent)' : 'var(--text-primary)',
              transition: 'all 0.2s'
            }}
          >
            {t.label}
          </div>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '20px' }}>
        {loading ? (
          <div style={{ color: 'var(--text-secondary)' }}>Lade Einstellungen...</div>
        ) : (
          <>
            {tab === 'general' && (
              <div>
                <h3 style={{ color: 'var(--accent)', marginBottom: '16px' }}>Konfiguration</h3>
                {categories.map(cat => (
                  <div key={cat} style={{ marginBottom: '20px' }}>
                    <div style={{
                      fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-secondary)',
                      marginBottom: '8px', fontFamily: 'var(--font-mono)'
                    }}>{cat || 'Allgemein'}</div>
                    {config.filter(c => c.category === cat).map(c => (
                      <div key={c.key} style={{
                        padding: '8px 12px', marginBottom: '4px',
                        background: 'var(--bg-surface)', borderRadius: '6px',
                        border: '1px solid var(--border)'
                      }}>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--accent)' }}>
                          {c.key}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                          {c.description || '—'}
                        </div>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', marginTop: '4px', color: 'var(--text-primary)' }}>
                          {typeof c.value === 'object' ? JSON.stringify(c.value) : String(c.value)}
                        </div>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            )}

            {tab === 'themes' && (
              <div>
                <h3 style={{ color: 'var(--accent)', marginBottom: '16px' }}>Themes</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '12px' }}>
                  {themes.map(t => (
                    <div key={t.name} style={{
                      padding: '16px', background: 'var(--bg-surface)',
                      borderRadius: '8px', border: `1px solid ${t.is_default ? 'var(--accent)' : 'var(--border)'}`,
                      cursor: 'pointer'
                    }}>
                      <div style={{ fontWeight: 600, marginBottom: '4px' }}>{t.name}</div>
                      {t.colors && (
                        <div style={{ display: 'flex', gap: '4px', marginTop: '8px' }}>
                          {Object.entries(t.colors).slice(0, 6).map(([k, v]) => (
                            <div key={k} style={{
                              width: '20px', height: '20px', borderRadius: '4px',
                              background: v, border: '1px solid var(--border)'
                            }} title={k} />
                          ))}
                        </div>
                      )}
                      {t.is_default && (
                        <div style={{ fontSize: '10px', color: 'var(--accent)', marginTop: '8px' }}>✓ Aktiv</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {tab === 'database' && (
              <div>
                <h3 style={{ color: 'var(--accent)', marginBottom: '16px' }}>Datenbank-Info</h3>
                <DatabaseInfo />
              </div>
            )}

            {tab === 'about' && (
              <div style={{ maxWidth: '500px' }}>
                <div style={{ fontSize: '48px', marginBottom: '12px' }}>👻</div>
                <h2 style={{ color: 'var(--accent)', fontFamily: 'var(--font-display)' }}>DBAI</h2>
                <div style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>
                  Ghost in the Database — v0.7.0
                </div>
                <div style={{ fontSize: '12px', lineHeight: 1.8, color: 'var(--text-primary)' }}>
                  <p>DBAI (Database AI) ist ein tabellenbasiertes Betriebssystem, das vollständig auf PostgreSQL aufbaut.</p>
                  <p style={{ marginTop: '8px' }}>Alles ist eine Zeile. Jeder Prozess, jede Datei, jeder KI-Zustand — gespeichert in der Datenbank.</p>
                  <p style={{ marginTop: '8px' }}>The Ghost in the Database — Dein lokaler KI-Assistent, der in den Tabellen lebt.</p>
                </div>
                <div style={{ marginTop: '24px', fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                  <div>9 Schemas · ~70 Tabellen · RLS auf allem</div>
                  <div>PostgreSQL 16 · pgvector · FastAPI · React</div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function DatabaseInfo() {
  const [info, setInfo] = useState(null)

  useEffect(() => {
    api.sqlQuery(`
      SELECT
        (SELECT pg_database_size('dbai')) as db_size,
        (SELECT count(*) FROM information_schema.tables WHERE table_schema LIKE 'dbai_%') as table_count,
        (SELECT count(*) FROM information_schema.schemata WHERE schema_name LIKE 'dbai_%') as schema_count,
        (SELECT count(*) FROM pg_stat_activity WHERE datname='dbai') as connections,
        (SELECT version()) as pg_version
    `).then(r => setInfo(r.rows?.[0])).catch(() => {})
  }, [])

  if (!info) return <div style={{ color: 'var(--text-secondary)' }}>Lade...</div>

  const items = [
    { label: 'PostgreSQL', value: info.pg_version?.split(' ').slice(0, 2).join(' ') },
    { label: 'Datenbankgröße', value: `${(info.db_size / 1024 / 1024).toFixed(1)} MB` },
    { label: 'Schemas', value: info.schema_count },
    { label: 'Tabellen/Views', value: info.table_count },
    { label: 'Verbindungen', value: info.connections },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {items.map(item => (
        <div key={item.label} style={{
          padding: '10px 14px', background: 'var(--bg-surface)',
          borderRadius: '6px', border: '1px solid var(--border)',
          display: 'flex', justifyContent: 'space-between'
        }}>
          <span style={{ color: 'var(--text-secondary)' }}>{item.label}</span>
          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>{item.value}</span>
        </div>
      ))}
    </div>
  )
}
