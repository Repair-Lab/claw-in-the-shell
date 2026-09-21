import React, { useState, useRef, useEffect, useMemo } from 'react'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'
import { api } from '../../api'

// Externe Domains, die iframe-Einbettung per X-Frame-Options / CSP blockieren
const EXTERNAL_BLOCKED_DOMAINS = [
  'whatsapp.com', 'web.whatsapp.com',
  'telegram.org', 'web.telegram.org',
  'github.com', 'gitlab.com',
  'google.com', 'google.de',
  'youtube.com', 'youtu.be',
  'discord.com', 'discord.gg',
  'twitter.com', 'x.com',
  'facebook.com', 'instagram.com',
  'reddit.com', 'twitch.tv',
  'spotify.com', 'open.spotify.com',
  'signal.org',
  'linkedin.com',
  'amazon.com', 'amazon.de',
]

function isBlockedExternal(url) {
  try {
    const hostname = new URL(url).hostname.toLowerCase()
    return EXTERNAL_BLOCKED_DOMAINS.some(d => hostname === d || hostname.endsWith('.' + d))
  } catch {
    return false
  }
}

function getDomainInfo(url) {
  try {
    const u = new URL(url)
    const host = u.hostname.toLowerCase()
    if (host.includes('whatsapp'))  return { name: 'WhatsApp Web', icon: '💬', color: '#25D366', hint: 'QR-Code im Browser-Tab scannen, um WhatsApp zu verbinden.' }
    if (host.includes('telegram'))  return { name: 'Telegram Web', icon: '✉️', color: '#0088cc', hint: 'QR-Code im Browser-Tab scannen, um Telegram zu verbinden.' }
    if (host.includes('github'))    return { name: 'GitHub', icon: '🐙', color: '#ffffff', hint: '' }
    if (host.includes('discord'))   return { name: 'Discord', icon: '💬', color: '#5865F2', hint: '' }
    if (host.includes('youtube'))   return { name: 'YouTube', icon: '▶️', color: '#ff0000', hint: '' }
    if (host.includes('spotify'))   return { name: 'Spotify', icon: '🎵', color: '#1DB954', hint: '' }
    if (host.includes('twitch'))   return { name: 'Twitch', icon: '🎮', color: '#9b59ff', hint: '' }
    if (host.includes('google'))   return { name: 'Google', icon: '🔍', color: '#4285F4', hint: '' }
    if (host.includes('signal'))   return { name: 'Signal', icon: '🔒', color: '#3A76F0', hint: '' }
    return { name: host, icon: '🌐', color: '#00f5ff', hint: '' }
  } catch {
    return { name: 'Externe Seite', icon: '🌐', color: '#00f5ff', hint: '' }
  }
}

/**
 * WebFrame — Eingebetteter Web-Browser im DBAI Desktop
 * 
 * Zeigt externe Web-Oberflächen (ComfyUI, Ollama, etc.) als iframe.
 * Erkennt blockierte Seiten und bietet "In neuem Tab öffnen" an.
 * 
 * FIX #2: Server-seitiger Proxy für Seiten, die iframes blockieren.
 * - Lädt Inhalte über /api/web-proxy/fetch
 * - Zeigt gerenderten HTML-Code (ohne iframes)
 * - Tracking-Schutz: blockiert bekannte Tracker-Domains
 */

// Tracking-Domains, die blockiert werden sollen
const TRACKER_DOMAINS = [
  'doubleclick.net', 'googlesyndication.com', 'google-analytics.com',
  'facebook.net', 'scorecardresearch.com', 'quantserve.com',
  'adnxs.com', 'criteo.com', 'taboola.com', 'outbrain.com',
  'amazon-adsystem.com', 'taboola.com', 'newrelic.com',
]

function isTracker(url) {
  try {
    const hostname = new URL(url).hostname.toLowerCase()
    return TRACKER_DOMAINS.some(d => hostname === d || hostname.endsWith('.' + d))
  } catch {
    return false
  }
}

export default function WebFrame({ windowId, extra }) {
  const { settings, schema, update: updateSetting, reset: resetSettings } = useAppSettings('web-frame')
  const [showSettings, setShowSettings] = useState(false)
  const initialUrl = extra?.url || settings?.default_url || 'about:blank'
  const title = extra?.title || 'Web Browser'
  const [url, setUrl] = useState(initialUrl)
  const [inputUrl, setInputUrl] = useState(initialUrl)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [iframeBlocked, setIframeBlocked] = useState(false)
  const [useProxy, setUseProxy] = useState(settings?.use_proxy || false)
  const [proxyContent, setProxyContent] = useState(null)
  const [proxyBlocked, setProxyBlocked] = useState([])
  const iframeRef = useRef(null)

  const blocked = useMemo(() => isBlockedExternal(url), [url])
  const domainInfo = useMemo(() => getDomainInfo(url), [url])

  // Wenn die URL eine bekannte blockierte externe Seite ist, direkt anzeigen
  useEffect(() => {
    setIframeBlocked(blocked)
    if (blocked) setLoading(false)
  }, [blocked])

  // Fallback-Timer: iframe gilt nach 5s ohne onLoad als blockiert
  useEffect(() => {
    if (blocked || !loading) return
    const timeout = setTimeout(() => {
      setIframeBlocked(true)
      setLoading(false)
    }, 5000)
    return () => clearTimeout(timeout)
  }, [url, loading, blocked])

  // Lade über Proxy, wenn aktiviert
  useEffect(() => {
    if (!useProxy || !url || url === 'about:blank') return
    if (blocked) return // Nicht blockierte Seiten direkt laden
    
    const loadViaProxy = async () => {
      try {
        setLoading(true)
        setError(false)
        setProxyContent(null)
        setProxyBlocked([])
        
        const proxyUrl = `/api/web-proxy/fetch?url=${encodeURIComponent(url)}`
        const res = await fetch(proxyUrl)
        
        if (res.ok) {
          const html = await res.text()
          setProxyContent(html)
          setLoading(false)
        } else {
          const err = await res.json().catch(() => ({ detail: 'Fehler beim Laden' }))
          setError(true)
          setLoading(false)
        }
      } catch (e) {
        setError(true)
        setLoading(false)
      }
    }
    
    loadViaProxy()
  }, [useProxy, url, blocked])

  const navigate = (targetUrl) => {
    let normalized = targetUrl.trim()
    if (normalized && !normalized.startsWith('http://') && !normalized.startsWith('https://')) {
      normalized = 'http://' + normalized
    }
    setUrl(normalized)
    setInputUrl(normalized)
    setLoading(true)
    setError(false)
    setIframeBlocked(false)
    setProxyContent(null)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      navigate(inputUrl)
    }
  }

  const reload = () => {
    if (useProxy) {
      // Proxy-Reload
      setUrl(url) // Trigger useEffect
    } else if (iframeRef.current) {
      setLoading(true)
      setError(false)
      iframeRef.current.src = url
    }
  }

  const goBack = () => {
    // Browser-History im iframe nicht steuerbar; Fallback auf initialUrl
    navigate(initialUrl)
  }

  // Render proxy content (simplified HTML render)
  const renderProxyContent = () => {
    if (!proxyContent) return null
    
    // Simple HTML sanitization: remove scripts, iframes, objects
    let safeHtml = proxyContent
      .replace(/<script[\s\S]*?<\/script>/gi, '')
      .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
      .replace(/<object[\s\S]*?<\/object>/gi, '')
      .replace(/<embed[\s\S]*?<\/embed>/gi, '')
      .replace(/on\w+="[^"]*"/gi, '') // Remove inline event handlers
      .replace(/src="http[^"]*"/g, 'src=""') // Block external resources
    
    return (
      <div 
        style={sx.proxyContent}
        dangerouslySetInnerHTML={{ __html: safeHtml }}
      />
    )
  }

  return (
    <div style={sx.container}>
      {/* Toolbar */}
      <div style={sx.toolbar}>
        <button onClick={goBack} style={sx.navBtn} title="Zurück">⬅️</button>
        <button onClick={reload} style={sx.navBtn} title="Neu laden">🔄</button>

        <div style={sx.urlBar}>
          {loading && <span style={sx.loadingDot}>⏳</span>}
          <input
            value={inputUrl}
            onChange={e => setInputUrl(e.target.value)}
            onKeyDown={handleKeyDown}
            style={sx.urlInput}
            placeholder="URL eingeben..."
          />
        </div>

        <button onClick={() => navigate(inputUrl)} style={sx.goBtn}>↗️</button>
        
        {/* Proxy Toggle */}
        <button
          onClick={() => setUseProxy(!useProxy)}
          style={{
            ...sx.navBtn,
            background: useProxy ? 'rgba(0,255,204,0.2)' : 'var(--bg-surface)',
            border: useProxy ? '1px solid var(--accent)' : '1px solid var(--border)',
          }}
          title={useProxy ? "Proxy aktiv (Tracking-Schutz)" : "Proxy inaktiv"}
        >
          {useProxy ? '🛡️' : '🌐'}
        </button>
        
        <button onClick={() => setShowSettings(true)} style={sx.navBtn} title="Einstellungen">⚙️</button>
        <button onClick={() => window.open(url, '_blank')} style={sx.navBtn} title="Extern öffnen">🔗</button>
      </div>

      {/* Proxy Status Bar */}
      {useProxy && (
        <div style={sx.proxyStatusBar}>
          <span style={sx.proxyStatusLabel}>🛡️ Proxy-Modus aktiv</span>
          <span style={sx.proxyStatusHint}>Tracking blockiert, externe Ressourcen entfernt</span>
        </div>
      )}

      {/* Service Info */}
      {title && title !== 'Web Browser' && (
        <div style={sx.serviceBar}>
          <span style={sx.serviceLabel}>🌐 {title}</span>
          <span style={sx.serviceUrl}>{url}</span>
        </div>
      )}

      {/* Content Area */}
      <div style={sx.iframeContainer}>
        {showSettings ? (
          <div style={{ padding: '16px', overflow: 'auto', height: '100%' }}>
            <button onClick={() => setShowSettings(false)} style={{ marginBottom: '12px', padding: '4px 12px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 'var(--radius)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '11px' }}>← Zurück</button>
            <AppSettingsPanel schema={schema} settings={settings} onUpdate={updateSetting} onReset={resetSettings} title="Web Browser" />
          </div>
        ) : useProxy && proxyContent ? (
          renderProxyContent()
        ) : (iframeBlocked || blocked) ? (
          <div style={sx.blockedState}>
            <div style={{
              width: 80, height: 80, borderRadius: '50%',
              background: `radial-gradient(circle, ${domainInfo.color}33, transparent)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 40, boxShadow: `0 0 30px ${domainInfo.color}22`,
              marginBottom: 16,
            }}>
              {domainInfo.icon}
            </div>
            <h3 style={{ color: '#e0e0e0', margin: '0 0 6px', fontSize: 18, fontWeight: 700 }}>
              {domainInfo.name}
            </h3>
            <p style={{ color: '#8899aa', fontSize: 13, margin: '0 0 8px', textAlign: 'center', maxWidth: 360 }}>
              Diese Seite blockiert die Einbettung in iframes aus Sicherheitsgründen.
              {domainInfo.hint && <><br/><span style={{ color: '#b0c8e0' }}>{domainInfo.hint}</span></>}
            </p>
            
            {/* Proxy Button */}
            <button
              onClick={() => setUseProxy(true)}
              style={{
                padding: '10px 24px', background: 'linear-gradient(135deg, #00ffcc, #00cc99)',
                border: 'none', borderRadius: 8, color: '#0a0a0f',
                fontWeight: 700, fontSize: 14, cursor: 'pointer', marginTop: 12,
                boxShadow: '0 0 20px rgba(0,255,204,0.3)',
                transition: 'all 0.2s ease',
              }}
              onMouseOver={e => e.target.style.transform = 'translateY(-2px)'}
              onMouseOut={e => e.target.style.transform = ''}
            >
              🛡️ Über Proxy laden (Tracking-Schutz)
            </button>
            
            <button
              onClick={() => window.open(url, '_blank')}
              style={{
                padding: '10px 24px', background: `linear-gradient(135deg, ${domainInfo.color}, ${domainInfo.color}bb)`,
                border: 'none', borderRadius: 8, color: domainInfo.color === '#ffffff' ? '#0a0a0f' : '#fff',
                fontWeight: 700, fontSize: 14, cursor: 'pointer', marginTop: 8,
                boxShadow: `0 0 20px ${domainInfo.color}33`,
                transition: 'all 0.2s ease',
              }}
              onMouseOver={e => e.target.style.transform = 'translateY(-2px)'}
              onMouseOut={e => e.target.style.transform = ''}
            >
              🔗 In neuem Tab öffnen
            </button>
            
            <p style={{ color: '#556677', fontSize: 11, marginTop: 16 }}>
              Tipp: Lokale Dienste (ComfyUI, Ollama, etc.) funktionieren im iframe.
            </p>
          </div>
        ) : error ? (
          <div style={sx.errorState}>
            <div style={{ fontSize: '48px' }}>🚫</div>
            <h3 style={{ color: 'var(--text-primary)', margin: '12px 0 6px' }}>Verbindung fehlgeschlagen</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '13px', margin: 0 }}>
              Dienst unter <code style={{ color: 'var(--accent)' }}>{url}</code> nicht erreichbar.
            </p>
            <p style={{ color: 'var(--text-secondary)', fontSize: '11px', marginTop: '8px' }}>
              Stelle sicher, dass der Dienst läuft und der Port korrekt ist.
            </p>
            <button onClick={reload} style={{ ...sx.goBtn, marginTop: '16px' }}>🔄 Erneut versuchen</button>
          </div>
        ) : (
          <>
            <iframe
              ref={iframeRef}
              src={url}
              style={sx.iframe}
              title={title}
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
              onLoad={() => { setLoading(false); setIframeBlocked(false) }}
              onError={() => { setLoading(false); setError(true) }}
            />
            {loading && (
              <div style={sx.loadingOverlay}>
                <div style={{ fontSize: '32px' }}>⏳</div>
                <p style={{ color: 'var(--text-secondary)' }}>Lade {title}...</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ═══ STYLES ═══
const sx = {
  container: { display: 'flex', flexDirection: 'column', height: '100%', fontFamily: 'var(--font-sans)' },

  toolbar: {
    display: 'flex', alignItems: 'center', gap: '6px',
    padding: '8px 10px', borderBottom: '1px solid var(--border)',
    background: 'var(--bg-secondary)',
  },
  navBtn: {
    width: '30px', height: '30px', border: '1px solid var(--border)',
    borderRadius: 'var(--radius)', background: 'var(--bg-surface)',
    cursor: 'pointer', fontSize: '14px', display: 'flex',
    alignItems: 'center', justifyContent: 'center',
  },
  urlBar: {
    flex: 1, display: 'flex', alignItems: 'center', gap: '6px',
    padding: '0 10px', background: 'var(--bg-elevated)',
    border: '1px solid var(--border)', borderRadius: 'var(--radius)',
    height: '30px',
  },
  loadingDot: { fontSize: '12px' },
  urlInput: {
    flex: 1, border: 'none', background: 'transparent',
    color: 'var(--text-primary)', fontSize: '12px',
    fontFamily: 'var(--font-mono)', outline: 'none',
  },
  goBtn: {
    padding: '6px 12px', background: 'rgba(0,255,204,0.1)',
    border: '1px solid var(--accent)', borderRadius: 'var(--radius)',
    color: 'var(--accent)', cursor: 'pointer', fontSize: '14px',
  },

  serviceBar: {
    display: 'flex', alignItems: 'center', gap: '10px',
    padding: '4px 12px', borderBottom: '1px solid var(--border)',
    background: 'rgba(0,255,204,0.02)', fontSize: '11px',
  },
  serviceLabel: { fontWeight: 600, color: 'var(--accent)' },
  serviceUrl: { color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' },

  proxyContent: {
    flex: 1, overflow: 'auto', padding: '20px',
    background: '#ffffff', color: '#1a1a1a',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    lineHeight: 1.6,
  },
  proxyStatusBar: {
    display: 'flex', alignItems: 'center', gap: '10px',
    padding: '6px 12px', borderBottom: '1px solid var(--border)',
    background: 'rgba(0,255,204,0.05)', fontSize: '11px',
  },
  proxyStatusLabel: { fontWeight: 600, color: 'var(--accent)' },
  proxyStatusHint: { color: 'var(--text-secondary)' },

  iframeContainer: { flex: 1, position: 'relative', overflow: 'hidden' },
  iframe: {
    width: '100%', height: '100%', border: 'none',
    background: '#ffffff',
  },

  loadingOverlay: {
    position: 'absolute', inset: 0, background: 'var(--bg-primary)',
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', gap: '8px',
  },

  errorState: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', height: '100%', textAlign: 'center',
    padding: '40px',
  },

  blockedState: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', height: '100%', textAlign: 'center',
    padding: '40px', background: 'linear-gradient(180deg, #0a0a14, #0e1020)',
  },
}
