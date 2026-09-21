import React, { useState, useRef, useEffect, useCallback } from 'react'

/**
 * GhostPlay — Media Player für GhostShell OS
 *
 * Beim Öffnen: Liste von Internet-Radiosendern (auswählen & hören).
 * Öffnet man ein Bild / Video / MP3 (via `extra` oder Datei-Öffnen),
 * gibt GhostPlay es wieder.
 *
 * extra: { mediaUrl, mediaType?, title? }
 *   mediaType: 'audio' | 'video' | 'image' | 'radio'  (wird sonst geraten)
 */

// ── Kuratierte, frei empfangbare Internet-Radiosender ──
const RADIO_STATIONS = [
  { id: 'groovesalad', name: 'SomaFM · Groove Salad', genre: 'Ambient / Downtempo', icon: '🌿', url: 'https://ice1.somafm.com/groovesalad-128-mp3' },
  { id: 'dronezone',   name: 'SomaFM · Drone Zone',   genre: 'Ambient / Space',     icon: '🛰️', url: 'https://ice1.somafm.com/dronezone-128-mp3' },
  { id: 'spacestation',name: 'SomaFM · Space Station',genre: 'Electronic',          icon: '🚀', url: 'https://ice1.somafm.com/spacestation-128-mp3' },
  { id: 'defcon',      name: 'SomaFM · DEF CON',      genre: 'Hacker / EDM',         icon: '💀', url: 'https://ice1.somafm.com/defcon256-256-mp3' },
  { id: 'secretagent', name: 'SomaFM · Secret Agent', genre: 'Lounge / Spy Jazz',    icon: '🕵️', url: 'https://ice1.somafm.com/secretagent-128-mp3' },
  { id: 'lush',        name: 'SomaFM · Lush',         genre: 'Vocal / Chill',        icon: '💫', url: 'https://ice1.somafm.com/lush-128-mp3' },
  { id: 'beatblender', name: 'SomaFM · Beat Blender', genre: 'Deep House',           icon: '🎛️', url: 'https://ice1.somafm.com/beatblender-128-mp3' },
  { id: 'indiepop',    name: 'SomaFM · Indie Pop Rocks', genre: 'Indie / Alt',       icon: '🎸', url: 'https://ice1.somafm.com/indiepop-128-mp3' },
  { id: 'rp-main',     name: 'Radio Paradise · Main', genre: 'Eclectic Mix',         icon: '🌈', url: 'https://stream.radioparadise.com/mp3-128' },
  { id: 'rp-rock',     name: 'Radio Paradise · Rock', genre: 'Rock',                 icon: '⚡', url: 'https://stream.radioparadise.com/rock-128' },
  { id: 'rp-mellow',   name: 'Radio Paradise · Mellow', genre: 'Chill / Mellow',     icon: '🌙', url: 'https://stream.radioparadise.com/mellow-128' },
  { id: 'swissjazz',   name: 'Radio Swiss Jazz',      genre: 'Jazz',                 icon: '🎷', url: 'https://stream.srg-ssr.ch/m/rsj/mp3_128' },
  { id: 'swissclassic',name: 'Radio Swiss Classic',   genre: 'Klassik',              icon: '🎻', url: 'https://stream.srg-ssr.ch/m/rsc_de/mp3_128' },
]

// ── Datei-Typ aus URL / Endung / MIME erraten ──
function guessMediaType(url = '', mime = '') {
  const u = url.toLowerCase().split('?')[0]
  if (mime.startsWith('audio/')) return 'audio'
  if (mime.startsWith('video/')) return 'video'
  if (mime.startsWith('image/')) return 'image'
  if (/\.(mp3|wav|ogg|oga|flac|aac|m4a|opus)$/.test(u)) return 'audio'
  if (/\.(mp4|webm|mkv|mov|avi|m4v|ogv)$/.test(u)) return 'video'
  if (/\.(png|jpe?g|gif|webp|bmp|svg|avif)$/.test(u)) return 'image'
  return 'audio'
}

function fmtTime(s) {
  if (!isFinite(s) || s < 0) return '0:00'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

export default function GhostPlay({ windowId, extra }) {
  // Aktuelles Medium: { kind: 'radio'|'audio'|'video'|'image', src, title, station? }
  const [media, setMedia] = useState(null)
  const [playing, setPlaying] = useState(false)
  const [volume, setVolume] = useState(0.8)
  const [muted, setMuted] = useState(false)
  const [progress, setProgress] = useState({ current: 0, duration: 0 })
  const [status, setStatus] = useState('') // Lade/Fehler-Text
  const [dragOver, setDragOver] = useState(false)
  const [search, setSearch] = useState('')

  const mediaRef = useRef(null)     // <audio> / <video> Element
  const fileInputRef = useRef(null)
  const objectUrlRef = useRef(null) // aktuell erzeugte Object-URL zum Aufräumen

  // ── Medium aus `extra` übernehmen (z.B. "Öffnen mit GhostPlay") ──
  useEffect(() => {
    if (extra?.mediaUrl) {
      const kind = extra.mediaType && ['audio', 'video', 'image', 'radio'].includes(extra.mediaType)
        ? extra.mediaType
        : guessMediaType(extra.mediaUrl)
      openMedia({
        kind: kind === 'radio' ? 'radio' : kind,
        src: extra.mediaUrl,
        title: extra.title || extra.mediaUrl.split('/').pop() || 'Medium',
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extra?.mediaUrl])

  // ── Object-URL aufräumen beim Unmount ──
  useEffect(() => () => {
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current)
  }, [])

  // ── Lautstärke auf Element anwenden ──
  useEffect(() => {
    const el = mediaRef.current
    if (el) { el.volume = volume; el.muted = muted }
  }, [volume, muted, media])

  const openMedia = useCallback((m) => {
    // Vorherige Object-URL freigeben
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current)
      objectUrlRef.current = null
    }
    setStatus('')
    setProgress({ current: 0, duration: 0 })
    setMedia(m)
    setPlaying(false)
  }, [])

  const playStation = useCallback((station) => {
    openMedia({ kind: 'radio', src: station.url, title: station.name, station })
  }, [openMedia])

  const handleFiles = useCallback((fileList) => {
    const file = fileList && fileList[0]
    if (!file) return
    const kind = guessMediaType(file.name, file.type)
    const objUrl = URL.createObjectURL(file)
    objectUrlRef.current = objUrl
    openMedia({ kind, src: objUrl, title: file.name })
  }, [openMedia])

  // ── Play/Pause Steuerung ──
  const togglePlay = useCallback(() => {
    const el = mediaRef.current
    if (!el) return
    if (el.paused) {
      const p = el.play()
      if (p && p.catch) p.catch(err => setStatus('⚠ Wiedergabe blockiert: ' + err.message))
    } else {
      el.pause()
    }
  }, [])

  const stopMedia = useCallback(() => {
    const el = mediaRef.current
    if (el) { el.pause(); el.currentTime = 0 }
    setPlaying(false)
  }, [])

  const backToRadio = useCallback(() => {
    stopMedia()
    if (objectUrlRef.current) { URL.revokeObjectURL(objectUrlRef.current); objectUrlRef.current = null }
    setMedia(null)
    setStatus('')
  }, [stopMedia])

  const seek = useCallback((e) => {
    const el = mediaRef.current
    if (!el || !isFinite(el.duration)) return
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
    el.currentTime = ratio * el.duration
  }, [])

  // ── Media-Element Events ──
  const onTimeUpdate = () => {
    const el = mediaRef.current
    if (el) setProgress({ current: el.currentTime, duration: el.duration || 0 })
  }

  // ── Drag & Drop ──
  const onDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer?.files?.length) handleFiles(e.dataTransfer.files)
  }

  const filteredStations = search
    ? RADIO_STATIONS.filter(s =>
        s.name.toLowerCase().includes(search.toLowerCase()) ||
        s.genre.toLowerCase().includes(search.toLowerCase()))
    : RADIO_STATIONS

  const isStream = media?.kind === 'radio'
  const isAV = media && (media.kind === 'audio' || media.kind === 'video' || media.kind === 'radio')

  return (
    <div
      style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-primary)', color: 'var(--text-primary)', fontFamily: 'var(--font-sans)' }}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
    >
      {/* ── Kopfzeile ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
        <span style={{ fontSize: 20 }}>🎵</span>
        <strong style={{ fontFamily: 'var(--font-display)', letterSpacing: 1 }}>GhostPlay</strong>
        {media && (
          <button onClick={backToRadio} style={btnStyle} title="Zurück zur Senderliste">📻 Radio</button>
        )}
        <div style={{ flex: 1 }} />
        <button onClick={() => fileInputRef.current?.click()} style={btnStyle} title="Datei öffnen (Bild / Video / MP3)">📂 Datei öffnen</button>
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*,video/*,image/*"
          style={{ display: 'none' }}
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {/* ── Inhalt ── */}
      <div style={{ flex: 1, overflow: 'auto', position: 'relative' }}>
        {/* Drag-Overlay */}
        {dragOver && (
          <div style={{ position: 'absolute', inset: 0, zIndex: 20, background: 'rgba(0,255,204,0.08)', border: '2px dashed var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, color: 'var(--accent)', pointerEvents: 'none' }}>
            📥 Datei hier ablegen, um sie abzuspielen
          </div>
        )}

        {/* ── Ansicht: Radioliste (Standard) ── */}
        {!media && (
          <div style={{ padding: 14 }}>
            <div style={{ marginBottom: 12 }}>
              <input
                type="text"
                placeholder="🔍 Sender suchen…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', color: 'var(--text-primary)', fontSize: 13 }}
              />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 10 }}>
              {filteredStations.map(st => (
                <div
                  key={st.id}
                  onDoubleClick={() => playStation(st)}
                  onClick={() => playStation(st)}
                  style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 10, background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', cursor: 'pointer', transition: 'var(--transition)' }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.boxShadow = '0 0 10px var(--glow)' }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.boxShadow = 'none' }}
                >
                  <span style={{ fontSize: 24 }}>{st.icon}</span>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{st.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{st.genre}</div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <span style={{ fontSize: 16, color: 'var(--accent)' }}>▶</span>
                </div>
              ))}
            </div>
            {filteredStations.length === 0 && (
              <div style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: 30 }}>Kein Sender gefunden.</div>
            )}
          </div>
        )}

        {/* ── Ansicht: Bild ── */}
        {media?.kind === 'image' && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', padding: 16 }}>
            <img
              src={media.src}
              alt={media.title}
              style={{ maxWidth: '100%', maxHeight: 'calc(100% - 30px)', objectFit: 'contain', borderRadius: 'var(--radius)', boxShadow: '0 0 20px rgba(0,0,0,0.5)' }}
              onError={() => setStatus('⚠ Bild konnte nicht geladen werden.')}
            />
            <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-secondary)' }}>{media.title}</div>
          </div>
        )}

        {/* ── Ansicht: Video ── */}
        {media?.kind === 'video' && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', padding: 16 }}>
            <video
              ref={mediaRef}
              src={media.src}
              controls
              autoPlay
              style={{ maxWidth: '100%', maxHeight: 'calc(100% - 30px)', borderRadius: 'var(--radius)', background: '#000' }}
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              onTimeUpdate={onTimeUpdate}
              onLoadedMetadata={onTimeUpdate}
              onError={() => setStatus('⚠ Video konnte nicht geladen werden.')}
            />
            <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-secondary)' }}>{media.title}</div>
          </div>
        )}

        {/* ── Ansicht: Audio / Radio (Cover-Karte) ── */}
        {(media?.kind === 'audio' || media?.kind === 'radio') && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', padding: 24, textAlign: 'center' }}>
            <div style={{
              width: 180, height: 180, borderRadius: '50%',
              background: 'radial-gradient(circle, var(--bg-elevated), var(--bg-surface))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 72, border: '2px solid var(--accent)',
              boxShadow: playing ? '0 0 30px var(--glow)' : 'none',
              animation: playing ? 'ghostplay-pulse 2.5s ease-in-out infinite' : 'none',
            }}>
              {media.station?.icon || (isStream ? '📻' : '🎵')}
            </div>
            <div style={{ marginTop: 18, fontSize: 16, fontWeight: 600 }}>{media.title}</div>
            {isStream && <div style={{ fontSize: 12, color: 'var(--accent)', marginTop: 4 }}>● LIVE STREAM</div>}
            <audio
              ref={mediaRef}
              src={media.src}
              autoPlay
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              onWaiting={() => setStatus('⏳ Puffern…')}
              onPlaying={() => setStatus('')}
              onTimeUpdate={onTimeUpdate}
              onLoadedMetadata={onTimeUpdate}
              onError={() => setStatus('⚠ Stream/Datei konnte nicht geladen werden.')}
            />
          </div>
        )}
      </div>

      {/* ── Statuszeile ── */}
      {status && (
        <div style={{ padding: '4px 14px', fontSize: 12, color: status.startsWith('⚠') ? 'var(--danger)' : 'var(--text-secondary)', background: 'var(--bg-surface)' }}>{status}</div>
      )}

      {/* ── Steuerleiste (nur für Audio/Radio; Video nutzt native Controls) ── */}
      {isAV && media?.kind !== 'video' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px', borderTop: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
          <button onClick={togglePlay} style={{ ...btnStyle, fontSize: 18, width: 40, height: 40, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {playing ? '⏸' : '▶'}
          </button>
          {!isStream && (
            <button onClick={stopMedia} style={{ ...btnStyle, fontSize: 14 }}>⏹</button>
          )}

          {/* Fortschritt (nur bei Datei, nicht bei Live-Stream) */}
          {!isStream ? (
            <>
              <span style={{ fontSize: 11, color: 'var(--text-secondary)', minWidth: 34, textAlign: 'right' }}>{fmtTime(progress.current)}</span>
              <div onClick={seek} style={{ flex: 1, height: 6, background: 'var(--bg-elevated)', borderRadius: 3, cursor: 'pointer', overflow: 'hidden' }}>
                <div style={{ width: `${progress.duration ? (progress.current / progress.duration) * 100 : 0}%`, height: '100%', background: 'var(--accent)' }} />
              </div>
              <span style={{ fontSize: 11, color: 'var(--text-secondary)', minWidth: 34 }}>{fmtTime(progress.duration)}</span>
            </>
          ) : (
            <div style={{ flex: 1, fontSize: 12, color: 'var(--text-secondary)' }}>{media.station?.genre || 'Internet-Radio'}</div>
          )}

          {/* Lautstärke */}
          <button onClick={() => setMuted(m => !m)} style={{ ...btnStyle, fontSize: 14 }} title={muted ? 'Ton an' : 'Stumm'}>
            {muted || volume === 0 ? '🔇' : volume < 0.5 ? '🔉' : '🔊'}
          </button>
          <input
            type="range" min="0" max="1" step="0.01" value={muted ? 0 : volume}
            onChange={(e) => { setVolume(parseFloat(e.target.value)); setMuted(false) }}
            style={{ width: 90, accentColor: 'var(--accent)' }}
          />
        </div>
      )}

      <style>{`
        @keyframes ghostplay-pulse {
          0%, 100% { transform: scale(1); box-shadow: 0 0 20px var(--glow); }
          50% { transform: scale(1.04); box-shadow: 0 0 36px var(--glow); }
        }
      `}</style>
    </div>
  )
}

const btnStyle = {
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border)',
  color: 'var(--text-primary)',
  cursor: 'pointer',
  padding: '6px 12px',
  borderRadius: 'var(--radius)',
  fontSize: 12,
  transition: 'var(--transition)',
}
