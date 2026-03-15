import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'

/**
 * Software Store — App-Katalog: Suchen, Installieren, Entfernen
 * Quelle: dbai_core.software_catalog (GitHub, APT, pip, npm, …)
 */
export default function SoftwareStore() {
  const [catalog, setCatalog] = useState([])
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('all')
  const [sourceFilter, setSourceFilter] = useState('all')
  const [tab, setTab] = useState('browse') // browse, installed, updates
  const [installing, setInstalling] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const data = await api.storeCatalog()
      setCatalog(data || [])
    } catch (err) {
      console.error('Store laden fehlgeschlagen:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const handleInstall = async (packageName, sourceType) => {
    setInstalling(packageName)
    try {
      await api.storeInstall(packageName, sourceType)
      setTimeout(refresh, 1000)
    } catch (err) {
      alert('Installation fehlgeschlagen: ' + err.message)
    }
    setInstalling(null)
  }

  const handleUninstall = async (packageName, sourceType) => {
    if (!confirm(`"${packageName}" wirklich entfernen?`)) return
    setInstalling(packageName)
    try {
      await api.storeUninstall(packageName, sourceType)
      setTimeout(refresh, 1000)
    } catch (err) {
      alert('Entfernung fehlgeschlagen: ' + err.message)
    }
    setInstalling(null)
  }

  const handleRefreshCatalog = async () => {
    setRefreshing(true)
    try {
      await api.storeRefresh()
      await refresh()
    } catch (err) {
      console.error(err)
    }
    setRefreshing(false)
  }

  // Filter
  const categories = ['all', ...new Set(catalog.map(c => c.category).filter(Boolean))].sort()
  const sources = ['all', ...new Set(catalog.map(c => c.source_type).filter(Boolean))].sort()

  const filtered = catalog.filter(pkg => {
    if (tab === 'installed' && pkg.install_state !== 'installed') return false
    if (tab === 'updates' && !(pkg.install_state === 'installed' && pkg.version !== pkg.latest_version && pkg.latest_version)) return false
    if (category !== 'all' && pkg.category !== category) return false
    if (sourceFilter !== 'all' && pkg.source_type !== sourceFilter) return false
    if (search) {
      const q = search.toLowerCase()
      return (pkg.package_name || '').toLowerCase().includes(q) ||
             (pkg.description || '').toLowerCase().includes(q) ||
             (pkg.tags || []).some(t => t.toLowerCase().includes(q))
    }
    return true
  })

  const installedCount = catalog.filter(p => p.install_state === 'installed').length
  const updatesCount = catalog.filter(p => p.install_state === 'installed' && p.version !== p.latest_version && p.latest_version).length

  const stateColors = {
    available: 'var(--text-secondary)',
    installed: 'var(--success)',
    installing: 'var(--warning)',
    updating: 'var(--warning)',
    removing: 'var(--warning)',
    broken: 'var(--danger)',
    blocked: 'var(--danger)',
  }

  const stateLabels = {
    available: 'Verfügbar',
    installed: 'Installiert',
    installing: 'Wird installiert…',
    updating: 'Wird aktualisiert…',
    removing: 'Wird entfernt…',
    broken: 'Defekt',
    blocked: 'Blockiert',
  }

  const sourceIcons = {
    apt: '📦', pip: '🐍', npm: '📗', github: '🐙',
    flatpak: '📋', snap: '🔶', cargo: '🦀', go: '🔵', custom: '⚙️',
  }

  if (loading) return <div style={{ padding: 20, color: 'var(--text-secondary)' }}>Lade Software-Katalog…</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', fontFamily: 'var(--font-sans)', fontSize: '13px' }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: '12px'
      }}>
        {/* Tabs */}
        <div style={{ display: 'flex', gap: '8px' }}>
          {[
            { id: 'browse', label: `🏪 Alle (${catalog.length})` },
            { id: 'installed', label: `✅ Installiert (${installedCount})` },
            { id: 'updates', label: `🔄 Updates (${updatesCount})` },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              padding: '6px 14px', borderRadius: 'var(--radius)',
              border: `1px solid ${tab === t.id ? 'var(--accent)' : 'var(--border)'}`,
              background: tab === t.id ? 'rgba(0,255,204,0.1)' : 'transparent',
              color: tab === t.id ? 'var(--accent)' : 'var(--text-secondary)',
              cursor: 'pointer', fontSize: '12px',
            }}>{t.label}</button>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        {/* Search */}
        <input
          type="text"
          placeholder="🔍 Suche…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            padding: '6px 12px', width: '200px',
            background: 'var(--bg-surface)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius)', color: 'var(--text-primary)',
            fontSize: '12px', fontFamily: 'var(--font-mono)',
          }}
        />

        {/* Category Filter */}
        <select value={category} onChange={e => setCategory(e.target.value)} style={{
          padding: '6px 10px', background: 'var(--bg-surface)',
          border: '1px solid var(--border)', borderRadius: 'var(--radius)',
          color: 'var(--text-primary)', fontSize: '12px',
        }}>
          {categories.map(c => (
            <option key={c} value={c}>{c === 'all' ? 'Alle Kategorien' : c}</option>
          ))}
        </select>

        {/* Source Filter */}
        <select value={sourceFilter} onChange={e => setSourceFilter(e.target.value)} style={{
          padding: '6px 10px', background: 'var(--bg-surface)',
          border: '1px solid var(--border)', borderRadius: 'var(--radius)',
          color: 'var(--text-primary)', fontSize: '12px',
        }}>
          {sources.map(s => (
            <option key={s} value={s}>{s === 'all' ? 'Alle Quellen' : s}</option>
          ))}
        </select>

        {/* Refresh */}
        <button onClick={handleRefreshCatalog} disabled={refreshing} style={{
          padding: '6px 12px', background: 'rgba(0,255,204,0.08)',
          border: '1px solid var(--accent)', borderRadius: 'var(--radius)',
          color: 'var(--accent)', cursor: refreshing ? 'wait' : 'pointer', fontSize: '12px',
        }}>
          {refreshing ? '⏳' : '🔄'} Katalog aktualisieren
        </button>
      </div>

      {/* Package Grid */}
      <div style={{
        flex: 1, overflow: 'auto', padding: '16px',
        display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
        gap: '12px', alignContent: 'start',
      }}>
        {filtered.length === 0 ? (
          <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
            {search ? `Keine Ergebnisse für "${search}"` : 'Keine Pakete in dieser Ansicht'}
          </div>
        ) : filtered.map(pkg => (
          <div key={`${pkg.package_name}-${pkg.source_type}`} style={{
            background: 'var(--bg-surface)', border: '1px solid var(--border)',
            borderRadius: '8px', padding: '14px',
            borderLeft: `3px solid ${stateColors[pkg.install_state] || 'var(--border)'}`,
            transition: 'border-color 0.2s',
          }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <span style={{ fontSize: '20px' }}>{sourceIcons[pkg.source_type] || '📦'}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
                  {pkg.package_name}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  {pkg.source_type} {pkg.version && `• v${pkg.version}`}
                </div>
              </div>
              <span style={{
                fontSize: '10px', padding: '2px 8px', borderRadius: '10px',
                background: `${stateColors[pkg.install_state]}22`,
                color: stateColors[pkg.install_state],
                border: `1px solid ${stateColors[pkg.install_state]}44`,
              }}>
                {stateLabels[pkg.install_state] || pkg.install_state}
              </span>
            </div>

            {/* Description */}
            <div style={{
              fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px',
              lineHeight: '1.4', maxHeight: '40px', overflow: 'hidden',
            }}>
              {pkg.description || 'Keine Beschreibung'}
            </div>

            {/* Tags */}
            {pkg.tags && pkg.tags.length > 0 && (
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '8px' }}>
                {pkg.tags.slice(0, 4).map(tag => (
                  <span key={tag} style={{
                    fontSize: '10px', padding: '1px 6px', borderRadius: '8px',
                    background: 'var(--bg-elevated)', color: 'var(--text-secondary)',
                    border: '1px solid var(--border)',
                  }}>{tag}</span>
                ))}
              </div>
            )}

            {/* Meta Row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
              {pkg.stars != null && (
                <span style={{ fontSize: '11px', color: 'var(--warning)' }}>⭐ {pkg.stars.toLocaleString()}</span>
              )}
              {pkg.license && (
                <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>📄 {pkg.license}</span>
              )}
              {pkg.install_size_mb != null && (
                <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>💾 {pkg.install_size_mb} MB</span>
              )}
              {pkg.ghost_recommendation != null && (
                <span style={{ fontSize: '11px', color: 'var(--accent)' }}>
                  👻 {Math.round(pkg.ghost_recommendation * 100)}%
                </span>
              )}
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: '8px' }}>
              {pkg.install_state === 'available' && (
                <button
                  onClick={() => handleInstall(pkg.package_name, pkg.source_type)}
                  disabled={installing === pkg.package_name}
                  style={{
                    flex: 1, padding: '6px', borderRadius: 'var(--radius)',
                    background: 'rgba(0,255,204,0.1)', border: '1px solid var(--accent)',
                    color: 'var(--accent)', cursor: 'pointer', fontSize: '12px',
                  }}
                >
                  {installing === pkg.package_name ? '⏳ Installiere…' : '📥 Installieren'}
                </button>
              )}
              {pkg.install_state === 'installed' && (
                <>
                  {pkg.latest_version && pkg.version !== pkg.latest_version && (
                    <button
                      onClick={() => handleInstall(pkg.package_name, pkg.source_type)}
                      disabled={installing === pkg.package_name}
                      style={{
                        flex: 1, padding: '6px', borderRadius: 'var(--radius)',
                        background: 'rgba(0,150,255,0.1)', border: '1px solid var(--info)',
                        color: 'var(--info)', cursor: 'pointer', fontSize: '12px',
                      }}
                    >
                      🔄 Update auf v{pkg.latest_version}
                    </button>
                  )}
                  <button
                    onClick={() => handleUninstall(pkg.package_name, pkg.source_type)}
                    disabled={installing === pkg.package_name}
                    style={{
                      padding: '6px 12px', borderRadius: 'var(--radius)',
                      background: 'rgba(255,68,68,0.1)', border: '1px solid var(--danger)',
                      color: 'var(--danger)', cursor: 'pointer', fontSize: '12px',
                    }}
                  >
                    🗑️ Entfernen
                  </button>
                </>
              )}
              {pkg.source_url && (
                <button
                  onClick={() => window.open(pkg.source_url, '_blank')}
                  style={{
                    padding: '6px 12px', borderRadius: 'var(--radius)',
                    background: 'transparent', border: '1px solid var(--border)',
                    color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '12px',
                  }}
                >
                  🔗
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
