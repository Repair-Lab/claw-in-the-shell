import React, { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../../api'

/**
 * Software Store — GitHub-Installer + interner Katalog
 * Suche nach GitHub-Repos, ein Klick → installiert.
 * Interne Pakete (apt, pip, npm) separat in Tab "System".
 */

const LANG_COLORS = {
  Python: '#3572A5', JavaScript: '#f1e05a', TypeScript: '#2b7489',
  Rust: '#dea584', Go: '#00ADD8', C: '#555555', 'C++': '#f34b7d',
  Java: '#b07219', Ruby: '#701516', Shell: '#89e051', Lua: '#000080',
  'Jupyter Notebook': '#DA5B0B', HTML: '#e34c26', CSS: '#563d7c',
  Swift: '#F05138', Kotlin: '#A97BFF', Dart: '#00B4AB', PHP: '#4F5D95',
}

const CATEGORIES = [
  { id: 'trending', label: '🔥 Trending', query: 'stars:>1000 pushed:>2025-01-01' },
  { id: 'ai', label: '🤖 KI / ML', query: 'topic:machine-learning OR topic:ai OR topic:llm stars:>100' },
  { id: 'tools', label: '🔧 Tools', query: 'topic:cli OR topic:devtools OR topic:utility stars:>500' },
  { id: 'selfhost', label: '🏠 Self-Hosted', query: 'topic:self-hosted OR topic:selfhosted stars:>200' },
  { id: 'automation', label: '⚡ Automation', query: 'topic:automation OR topic:homelab stars:>200' },
]

export default function SoftwareStore() {
  const [tab, setTab] = useState('github') // github | installed | system
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [catalog, setCatalog] = useState([])
  const [loading, setLoading] = useState(true)
  const [installing, setInstalling] = useState(null)
  const [activeCategory, setActiveCategory] = useState(null)
  const [searchError, setSearchError] = useState('')
  const searchTimeout = useRef(null)

  // Lade internen Katalog
  const loadCatalog = useCallback(async () => {
    try {
      const data = await api.storeCatalog()
      setCatalog(data || [])
    } catch (e) {
      console.error('Katalog-Fehler:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadCatalog() }, [loadCatalog])

  // GitHub-Suche (debounced)
  const doGithubSearch = useCallback(async (query) => {
    if (!query || query.length < 2) {
      setSearchResults([])
      return
    }
    setSearching(true)
    setSearchError('')
    try {
      const data = await api.storeGithubSearch(query)
      if (data.error) setSearchError(data.error)
      setSearchResults(data.items || [])
    } catch (e) {
      setSearchError(e.message)
      setSearchResults([])
    } finally {
      setSearching(false)
    }
  }, [])

  const handleSearchInput = (val) => {
    setSearch(val)
    setActiveCategory(null)
    if (searchTimeout.current) clearTimeout(searchTimeout.current)
    searchTimeout.current = setTimeout(() => doGithubSearch(val), 500)
  }

  const handleCategoryClick = (cat) => {
    setActiveCategory(cat.id)
    setSearch('')
    doGithubSearch(cat.query)
  }

  const handleGithubInstall = async (repo) => {
    setInstalling(repo.full_name)
    try {
      await api.storeGithubInstall(repo)
      await loadCatalog()
    } catch (e) {
      alert('Installation fehlgeschlagen: ' + e.message)
    }
    setInstalling(null)
  }

  const handleInternalInstall = async (pkg) => {
    setInstalling(pkg.package_name)
    try {
      await api.storeInstall(pkg.package_name, pkg.source_type)
      await loadCatalog()
    } catch (e) {
      alert('Installation fehlgeschlagen: ' + e.message)
    }
    setInstalling(null)
  }

  const handleUninstall = async (pkg) => {
    if (!confirm(`"${pkg.display_name || pkg.package_name}" wirklich entfernen?`)) return
    setInstalling(pkg.package_name)
    try {
      await api.storeUninstall(pkg.package_name, pkg.source_type)
      await loadCatalog()
    } catch (e) {
      alert('Entfernung fehlgeschlagen: ' + e.message)
    }
    setInstalling(null)
  }

  const installedGithub = catalog.filter(p => p.source_type === 'github' && p.install_state === 'installed')
  const installedInternal = catalog.filter(p => p.source_type !== 'github' && p.install_state === 'installed')
  const systemPkgs = catalog.filter(p => p.source_type !== 'github')

  const isInstalled = (fullName) => catalog.some(
    p => p.package_name === fullName && p.source_type === 'github' && p.install_state === 'installed'
  )

  return (
    <div style={sx.container}>
      {/* ── Top Bar ── */}
      <div style={sx.topBar}>
        <div style={sx.storeLogo}>
          <span style={{ fontSize: 22 }}>🐙</span>
          <span style={sx.storeTitle}>Software Store</span>
        </div>

        <div style={sx.tabs}>
          {[
            { id: 'github', label: '🐙 GitHub', count: null },
            { id: 'installed', label: '✅ Installiert', count: installedGithub.length + installedInternal.length },
            { id: 'system', label: '📦 System', count: systemPkgs.length },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              ...sx.tab,
              ...(tab === t.id ? sx.tabActive : {}),
            }}>
              {t.label}
              {t.count != null && <span style={sx.tabBadge}>{t.count}</span>}
            </button>
          ))}
        </div>

        <div style={{ flex: 1 }} />
      </div>

      {/* ── GitHub Tab ── */}
      {tab === 'github' && (
        <div style={sx.content}>
          <div style={sx.searchSection}>
            <div style={sx.searchBar}>
              <span style={sx.searchIcon}>🔍</span>
              <input
                style={sx.searchInput}
                value={search}
                onChange={e => handleSearchInput(e.target.value)}
                placeholder="GitHub-Repository suchen… z.B. 'ollama', 'comfyui', 'home-assistant'"
              />
              {searching && <span style={sx.searchSpinner}>⏳</span>}
            </div>

            <div style={sx.categoryRow}>
              {CATEGORIES.map(cat => (
                <button key={cat.id} onClick={() => handleCategoryClick(cat)}
                  style={{
                    ...sx.categoryBtn,
                    ...(activeCategory === cat.id ? sx.categoryBtnActive : {}),
                  }}>
                  {cat.label}
                </button>
              ))}
            </div>
          </div>

          {searchError && <div style={sx.errorBar}>⚠️ {searchError}</div>}

          <div style={sx.repoGrid}>
            {searchResults.length === 0 && !searching && !search && !activeCategory && (
              <div style={sx.emptyState}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>🐙</div>
                <div style={{ fontSize: 16, fontWeight: 600, color: '#e0e0e0', marginBottom: 6 }}>
                  GitHub Repos suchen & installieren
                </div>
                <div style={{ fontSize: 13, color: '#6688aa', maxWidth: 400, lineHeight: 1.6 }}>
                  Finde Open-Source-Tools, KI-Modelle und Software.
                  Suche direkt oder wähle eine Kategorie – ein Klick auf "Installieren" reicht.
                </div>
              </div>
            )}

            {searchResults.length === 0 && !searching && (search || activeCategory) && (
              <div style={sx.emptyState}>
                <div style={{ fontSize: 32 }}>🔍</div>
                <div style={{ color: '#6688aa', marginTop: 8 }}>Keine Ergebnisse</div>
              </div>
            )}

            {searchResults.map(repo => (
              <RepoCard
                key={repo.full_name}
                repo={repo}
                installed={isInstalled(repo.full_name)}
                installing={installing === repo.full_name}
                onInstall={() => handleGithubInstall(repo)}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── Installiert Tab ── */}
      {tab === 'installed' && (
        <div style={sx.content}>
          <div style={sx.sectionTitle}>🐙 GitHub-Repos ({installedGithub.length})</div>
          <div style={sx.repoGrid}>
            {installedGithub.length === 0 && (
              <div style={sx.emptyState}>
                <div style={{ fontSize: 32 }}>📭</div>
                <div style={{ color: '#6688aa', marginTop: 8 }}>Noch keine GitHub-Repos installiert.</div>
              </div>
            )}
            {installedGithub.map(pkg => (
              <InstalledCard key={pkg.id} pkg={pkg} installing={installing === pkg.package_name}
                onUninstall={() => handleUninstall(pkg)} />
            ))}
          </div>

          {installedInternal.length > 0 && (
            <>
              <div style={{ ...sx.sectionTitle, marginTop: 20 }}>
                📦 System-Pakete ({installedInternal.length})
              </div>
              <div style={sx.repoGrid}>
                {installedInternal.map(pkg => (
                  <InstalledCard key={pkg.id} pkg={pkg} installing={installing === pkg.package_name}
                    onUninstall={() => handleUninstall(pkg)} />
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── System Tab ── */}
      {tab === 'system' && (
        <div style={sx.content}>
          <div style={sx.repoGrid}>
            {systemPkgs.map(pkg => (
              <SystemCard key={pkg.id} pkg={pkg}
                installing={installing === pkg.package_name}
                onInstall={() => handleInternalInstall(pkg)}
                onUninstall={() => handleUninstall(pkg)} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Sub-Komponenten
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function RepoCard({ repo, installed, installing, onInstall }) {
  const langColor = LANG_COLORS[repo.language] || '#6688aa'
  return (
    <div style={sx.repoCard}>
      <div style={sx.repoHeader}>
        <img src={repo.owner_avatar} alt="" style={sx.avatar}
          onError={e => { e.target.style.display = 'none' }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={sx.repoName} title={repo.full_name}>
            <span style={{ color: '#6688aa' }}>{repo.owner}/</span>
            <span style={{ color: '#e0e0e0' }}>{repo.name}</span>
          </div>
          <div style={sx.repoDesc}>{repo.description || 'Keine Beschreibung'}</div>
        </div>
      </div>
      <div style={sx.repoMeta}>
        <span style={sx.metaItem}>⭐ {formatNum(repo.stars)}</span>
        <span style={sx.metaItem}>🔀 {formatNum(repo.forks)}</span>
        {repo.language && (
          <span style={sx.metaItem}>
            <span style={{ ...sx.langDot, background: langColor }} />
            {repo.language}
          </span>
        )}
        {repo.license && <span style={sx.metaItem}>📄 {repo.license}</span>}
      </div>
      {repo.topics && repo.topics.length > 0 && (
        <div style={sx.topicRow}>
          {repo.topics.slice(0, 5).map(t => (
            <span key={t} style={sx.topic}>{t}</span>
          ))}
          {repo.topics.length > 5 && <span style={sx.topicMore}>+{repo.topics.length - 5}</span>}
        </div>
      )}
      <div style={sx.repoActions}>
        {installed ? (
          <button style={sx.btnInstalled} disabled>✅ Installiert</button>
        ) : (
          <button style={sx.btnInstall} onClick={onInstall} disabled={installing}>
            {installing ? '⏳ Installiere…' : '📥 Installieren'}
          </button>
        )}
        <button style={sx.btnLink} onClick={() => window.open(repo.html_url, '_blank')}>
          🔗 GitHub
        </button>
      </div>
    </div>
  )
}

function InstalledCard({ pkg, installing, onUninstall }) {
  const isGithub = pkg.source_type === 'github'
  return (
    <div style={sx.repoCard}>
      <div style={sx.repoHeader}>
        <span style={{ fontSize: 24, marginRight: 8 }}>{isGithub ? '🐙' : '📦'}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ ...sx.repoName, color: '#e0e0e0' }}>{pkg.display_name || pkg.package_name}</div>
          <div style={sx.repoDesc}>{pkg.description || ''}</div>
        </div>
      </div>
      <div style={sx.repoMeta}>
        {pkg.stars != null && <span style={sx.metaItem}>⭐ {formatNum(pkg.stars)}</span>}
        <span style={sx.metaItem}>{pkg.source_type}</span>
        {pkg.version && <span style={sx.metaItem}>v{pkg.version}</span>}
        {pkg.install_size_mb && <span style={sx.metaItem}>💾 {pkg.install_size_mb}MB</span>}
      </div>
      <div style={sx.repoActions}>
        <button style={sx.btnRemove} onClick={onUninstall} disabled={installing}>
          {installing ? '⏳' : '🗑️'} Entfernen
        </button>
        {pkg.homepage && (
          <button style={sx.btnLink} onClick={() => window.open(pkg.homepage, '_blank')}>🔗</button>
        )}
      </div>
    </div>
  )
}

function SystemCard({ pkg, installing, onInstall, onUninstall }) {
  const sourceIcons = { apt: '📦', pip: '🐍', npm: '📗', flatpak: '📋', snap: '🔶', cargo: '🦀', go: '🔵' }
  const isInst = pkg.install_state === 'installed'
  return (
    <div style={{ ...sx.repoCard, borderLeft: `3px solid ${isInst ? '#00ff88' : '#2a2a40'}` }}>
      <div style={sx.repoHeader}>
        <span style={{ fontSize: 24, marginRight: 8 }}>{sourceIcons[pkg.source_type] || '📦'}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ ...sx.repoName, color: '#e0e0e0' }}>{pkg.display_name || pkg.package_name}</div>
          <div style={sx.repoDesc}>{pkg.description || ''}</div>
        </div>
        <span style={{
          fontSize: 10, padding: '2px 8px', borderRadius: 10,
          background: isInst ? 'rgba(0,255,136,0.1)' : 'rgba(100,100,150,0.1)',
          color: isInst ? '#00ff88' : '#6688aa',
          border: `1px solid ${isInst ? '#00ff8844' : '#2a2a40'}`,
        }}>
          {isInst ? 'Installiert' : 'Verfügbar'}
        </span>
      </div>
      <div style={sx.repoMeta}>
        <span style={sx.metaItem}>{pkg.source_type}</span>
        {pkg.version && <span style={sx.metaItem}>v{pkg.version}</span>}
        {pkg.category && <span style={sx.metaItem}>{pkg.category}</span>}
      </div>
      <div style={sx.repoActions}>
        {isInst ? (
          <button style={sx.btnRemove} onClick={onUninstall} disabled={installing}>
            {installing ? '⏳' : '🗑️'} Entfernen
          </button>
        ) : (
          <button style={sx.btnInstall} onClick={onInstall} disabled={installing}>
            {installing ? '⏳ Installiere…' : '📥 Installieren'}
          </button>
        )}
      </div>
    </div>
  )
}

function formatNum(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n || 0)
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Styles
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const sx = {
  container: {
    display: 'flex', flexDirection: 'column', height: '100%',
    fontFamily: "'Inter', -apple-system, sans-serif", fontSize: 13, color: '#e0e0e0',
    background: '#0a0a14',
  },
  topBar: {
    display: 'flex', alignItems: 'center', gap: 16, padding: '10px 16px',
    borderBottom: '1px solid #1a1a2e', background: '#0e0e1a',
  },
  storeLogo: { display: 'flex', alignItems: 'center', gap: 8 },
  storeTitle: { fontSize: 16, fontWeight: 700, color: '#e0e0e0' },
  tabs: { display: 'flex', gap: 4 },
  tab: {
    padding: '6px 14px', borderRadius: 8, border: '1px solid transparent',
    background: 'transparent', color: '#6688aa', cursor: 'pointer',
    fontSize: 12, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 6,
    transition: 'all 0.2s',
  },
  tabActive: {
    background: 'rgba(0,255,204,0.08)', color: '#00ffcc',
    border: '1px solid rgba(0,255,204,0.2)',
  },
  tabBadge: {
    fontSize: 10, padding: '1px 6px', borderRadius: 10,
    background: 'rgba(255,255,255,0.08)', color: '#8899aa',
  },
  content: { flex: 1, overflow: 'auto', padding: 16 },
  searchSection: { marginBottom: 16 },
  searchBar: {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '10px 16px', background: '#12121e',
    border: '1px solid #1a1a2e', borderRadius: 12, marginBottom: 12,
  },
  searchIcon: { fontSize: 16, color: '#6688aa' },
  searchInput: {
    flex: 1, border: 'none', background: 'transparent', outline: 'none',
    color: '#e0e0e0', fontSize: 14, fontFamily: "'Inter', sans-serif",
  },
  searchSpinner: { fontSize: 14 },
  categoryRow: { display: 'flex', gap: 8, flexWrap: 'wrap' },
  categoryBtn: {
    padding: '6px 14px', borderRadius: 20, border: '1px solid #1a1a2e',
    background: '#12121e', color: '#8899aa', cursor: 'pointer',
    fontSize: 12, fontWeight: 500, transition: 'all 0.2s',
  },
  categoryBtnActive: {
    background: 'rgba(0,255,204,0.1)', color: '#00ffcc',
    border: '1px solid rgba(0,255,204,0.3)',
  },
  errorBar: {
    padding: '8px 16px', background: 'rgba(255,68,68,0.08)',
    border: '1px solid rgba(255,68,68,0.2)', borderRadius: 8,
    color: '#ff6666', fontSize: 12, marginBottom: 12,
  },
  repoGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
    gap: 12, alignContent: 'start',
  },
  repoCard: {
    background: '#12121e', border: '1px solid #1a1a2e', borderRadius: 12,
    padding: 16, display: 'flex', flexDirection: 'column', gap: 10,
    transition: 'border-color 0.2s, box-shadow 0.2s',
  },
  repoHeader: { display: 'flex', alignItems: 'flex-start', gap: 10 },
  avatar: { width: 32, height: 32, borderRadius: 8, flexShrink: 0 },
  repoName: {
    fontSize: 13, fontWeight: 600, fontFamily: "'JetBrains Mono', monospace",
    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
  },
  repoDesc: {
    fontSize: 12, color: '#6688aa', lineHeight: 1.4,
    display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
    overflow: 'hidden', marginTop: 2,
  },
  repoMeta: { display: 'flex', gap: 12, flexWrap: 'wrap' },
  metaItem: {
    fontSize: 11, color: '#6688aa', display: 'flex', alignItems: 'center', gap: 4,
  },
  langDot: { width: 8, height: 8, borderRadius: '50%', display: 'inline-block' },
  topicRow: { display: 'flex', gap: 4, flexWrap: 'wrap' },
  topic: {
    fontSize: 10, padding: '2px 8px', borderRadius: 12,
    background: 'rgba(0,150,255,0.08)', color: '#4488cc',
    border: '1px solid rgba(0,150,255,0.15)',
  },
  topicMore: { fontSize: 10, color: '#556677', padding: '2px 4px' },
  repoActions: { display: 'flex', gap: 8, marginTop: 'auto' },
  btnInstall: {
    flex: 1, padding: '8px 16px', borderRadius: 8, border: 'none',
    background: 'linear-gradient(135deg, #00aa88, #00ccaa)',
    color: '#0a0a0f', fontWeight: 700, fontSize: 13, cursor: 'pointer',
    transition: 'all 0.2s', boxShadow: '0 2px 10px rgba(0,170,136,0.2)',
  },
  btnInstalled: {
    flex: 1, padding: '8px 16px', borderRadius: 8,
    border: '1px solid #00ff8844', background: 'rgba(0,255,136,0.05)',
    color: '#00ff88', fontWeight: 600, fontSize: 13, cursor: 'default',
  },
  btnRemove: {
    padding: '8px 14px', borderRadius: 8, border: '1px solid rgba(255,68,68,0.3)',
    background: 'rgba(255,68,68,0.05)', color: '#ff6666',
    fontSize: 12, cursor: 'pointer', fontWeight: 500,
  },
  btnLink: {
    padding: '8px 12px', borderRadius: 8, border: '1px solid #1a1a2e',
    background: 'transparent', color: '#6688aa', fontSize: 12, cursor: 'pointer',
  },
  sectionTitle: {
    fontSize: 14, fontWeight: 600, color: '#8899aa', marginBottom: 12,
    padding: '4px 0', borderBottom: '1px solid #1a1a2e',
  },
  emptyState: {
    gridColumn: '1 / -1', display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center', padding: 60, textAlign: 'center',
  },
}
