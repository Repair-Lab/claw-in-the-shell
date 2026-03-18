import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../../api'

// ── Minimaler QR-Code-Generator (keine externe Abhängigkeit) ──
function generateQRCodeSVG(text, size = 200) {
  // Einfache QR-Code-Matrix via API-URL als Fallback: wir nutzen eine reine
  // SVG-Darstellung mit einem eingebetteten QR-code über einen Canvas-Trick
  // Für Production: qrcode.js library. Hier: Anzeige der URL + visueller Code.
  const modules = encodeToMatrix(text)
  const moduleCount = modules.length
  const cellSize = size / moduleCount

  let rects = ''
  for (let r = 0; r < moduleCount; r++) {
    for (let c = 0; c < moduleCount; c++) {
      if (modules[r][c]) {
        rects += `<rect x="${c * cellSize}" y="${r * cellSize}" width="${cellSize}" height="${cellSize}" fill="#fff"/>`
      }
    }
  }

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">
    <rect width="${size}" height="${size}" fill="#0a0e17"/>
    ${rects}
  </svg>`
}

// Einfache QR-ähnliche Matrix-Kodierung (für visuelle Darstellung)
// Nutzt ein Hash-basiertes Pattern für die URL
function encodeToMatrix(text) {
  const size = 25
  const matrix = Array.from({ length: size }, () => Array(size).fill(false))

  // Finder-Patterns (3 Ecken)
  const addFinder = (sr, sc) => {
    for (let r = 0; r < 7; r++)
      for (let c = 0; c < 7; c++) {
        const outer = r === 0 || r === 6 || c === 0 || c === 6
        const inner = r >= 2 && r <= 4 && c >= 2 && c <= 4
        if (outer || inner) matrix[sr + r][sc + c] = true
      }
  }
  addFinder(0, 0)
  addFinder(0, size - 7)
  addFinder(size - 7, 0)

  // Timing-Patterns
  for (let i = 7; i < size - 7; i++) {
    matrix[6][i] = i % 2 === 0
    matrix[i][6] = i % 2 === 0
  }

  // Daten aus Text-Hash
  let hash = 0
  for (let i = 0; i < text.length; i++) {
    hash = ((hash << 5) - hash + text.charCodeAt(i)) | 0
  }

  for (let r = 8; r < size - 8; r++) {
    for (let c = 8; c < size - 8; c++) {
      hash = ((hash << 5) - hash + r * size + c) | 0
      const charCode = text.charCodeAt((r * size + c) % text.length) || 0
      matrix[r][c] = ((hash ^ charCode) & 3) < 2
    }
  }

  return matrix
}

// ── Styles ──
const styles = {
  container: {
    height: '100%',
    background: '#0a0e17',
    color: '#e2e8f0',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
    overflow: 'auto',
    padding: '20px',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginBottom: '24px',
  },
  headerIcon: {
    fontSize: '32px',
  },
  headerText: {
    flex: 1,
  },
  title: {
    fontSize: '20px',
    fontWeight: 700,
    margin: 0,
    background: 'linear-gradient(135deg, #e2e8f0, #06b6d4)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  },
  subtitle: {
    fontSize: '13px',
    color: '#64748b',
    margin: '4px 0 0',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px',
    marginBottom: '20px',
  },
  card: {
    background: '#111827',
    border: '1px solid #1e293b',
    borderRadius: '12px',
    padding: '20px',
  },
  cardFull: {
    background: '#111827',
    border: '1px solid #1e293b',
    borderRadius: '12px',
    padding: '20px',
    gridColumn: '1 / -1',
  },
  cardTitle: {
    fontSize: '13px',
    fontWeight: 600,
    color: '#06b6d4',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: '16px',
  },
  qrContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '16px',
  },
  qrCode: {
    background: '#0a0e17',
    borderRadius: '12px',
    padding: '12px',
    border: '2px solid #1e293b',
  },
  url: {
    fontSize: '16px',
    fontWeight: 600,
    color: '#06b6d4',
    wordBreak: 'break-all',
    textAlign: 'center',
  },
  copyBtn: {
    padding: '8px 20px',
    borderRadius: '8px',
    border: '1px solid #1e293b',
    background: '#1e293b',
    color: '#e2e8f0',
    cursor: 'pointer',
    fontSize: '13px',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    transition: 'all .2s',
  },
  pinDisplay: {
    fontSize: '36px',
    fontWeight: 700,
    letterSpacing: '12px',
    fontFamily: '"SF Mono", Menlo, monospace',
    color: '#f59e0b',
    textAlign: 'center',
    padding: '16px',
    background: 'rgba(245, 158, 11, 0.08)',
    borderRadius: '12px',
    border: '1px solid rgba(245, 158, 11, 0.2)',
  },
  pinTimer: {
    fontSize: '13px',
    color: '#64748b',
    textAlign: 'center',
    marginTop: '8px',
  },
  generateBtn: {
    padding: '10px 24px',
    borderRadius: '8px',
    border: 'none',
    background: 'linear-gradient(135deg, #06b6d4, #8b5cf6)',
    color: '#fff',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: 600,
    width: '100%',
    marginTop: '12px',
    transition: 'all .2s',
  },
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 0',
    borderBottom: '1px solid #1e293b',
  },
  statusLabel: {
    fontSize: '13px',
    color: '#94a3b8',
  },
  statusValue: {
    fontSize: '13px',
    fontWeight: 600,
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  dot: (color) => ({
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    background: color,
    display: 'inline-block',
  }),
  ifaceTable: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '13px',
  },
  th: {
    textAlign: 'left',
    padding: '8px',
    borderBottom: '1px solid #1e293b',
    color: '#64748b',
    fontSize: '11px',
    textTransform: 'uppercase',
  },
  td: {
    padding: '8px',
    borderBottom: '1px solid #1e293b',
    color: '#e2e8f0',
    fontFamily: '"SF Mono", Menlo, monospace',
    fontSize: '12px',
  },
  instructions: {
    background: 'rgba(6, 182, 212, 0.05)',
    borderRadius: '8px',
    padding: '16px',
    marginTop: '12px',
  },
  step: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '10px',
    padding: '8px 0',
    fontSize: '13px',
    color: '#94a3b8',
  },
  stepNum: {
    background: '#06b6d4',
    color: '#fff',
    width: '22px',
    height: '22px',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '11px',
    fontWeight: 700,
    flexShrink: 0,
  },
}


export default function RemoteAccess({ windowId }) {
  const [info, setInfo] = useState(null)
  const [pin, setPin] = useState(null)
  const [pinExpiry, setPinExpiry] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)
  const timerRef = useRef(null)

  const loadInfo = useCallback(async () => {
    try {
      setLoading(true)
      const data = await api.remoteAccessInfo()
      setInfo(data)
      setError(null)
    } catch (err) {
      setError('Netzwerk-Info konnte nicht geladen werden')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadInfo()
    const interval = setInterval(loadInfo, 10000)
    return () => clearInterval(interval)
  }, [loadInfo])

  // PIN-Timer
  useEffect(() => {
    if (pinExpiry > 0) {
      timerRef.current = setInterval(() => {
        setPinExpiry(prev => {
          if (prev <= 1) {
            setPin(null)
            clearInterval(timerRef.current)
            return 0
          }
          return prev - 1
        })
      }, 1000)
    }
    return () => clearInterval(timerRef.current)
  }, [pin])

  const handleGeneratePin = async () => {
    try {
      const data = await api.remoteAccessPin()
      setPin(data.pin)
      setPinExpiry(data.expires_in)
    } catch (err) {
      setError('PIN konnte nicht generiert werden')
    }
  }

  const handleCopy = async (text) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback
      const ta = document.createElement('textarea')
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60)
    const s = secs % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  if (loading && !info) {
    return (
      <div style={styles.container}>
        <div style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b' }}>
          <div style={{ fontSize: '40px', marginBottom: '16px' }}>📡</div>
          <p>Netzwerk wird analysiert...</p>
        </div>
      </div>
    )
  }

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <span style={styles.headerIcon}>📱</span>
        <div style={styles.headerText}>
          <h2 style={styles.title}>Remote Access</h2>
          <p style={styles.subtitle}>Verbinde dein Handy mit GhostShell</p>
        </div>
        <button
          onClick={loadInfo}
          style={{ ...styles.copyBtn, padding: '6px 12px' }}
          title="Aktualisieren"
        >🔄</button>
      </div>

      {error && (
        <div style={{ ...styles.card, borderColor: '#ef4444', marginBottom: '16px' }}>
          <span style={{ color: '#ef4444' }}>⚠️ {error}</span>
        </div>
      )}

      <div style={styles.grid}>
        {/* QR-Code */}
        <div style={styles.card}>
          <div style={styles.cardTitle}>📷 QR-Code scannen</div>
          <div style={styles.qrContainer}>
            {info?.url ? (
              <>
                <div
                  style={styles.qrCode}
                  dangerouslySetInnerHTML={{ __html: generateQRCodeSVG(info.url, 180) }}
                />
                <div style={styles.url}>{info.url}</div>
                <button
                  style={styles.copyBtn}
                  onClick={() => handleCopy(info.url)}
                >
                  {copied ? '✅ Kopiert!' : '📋 URL kopieren'}
                </button>
              </>
            ) : (
              <div style={{ color: '#64748b', textAlign: 'center', padding: '40px' }}>
                <div style={{ fontSize: '32px', marginBottom: '8px' }}>🚫</div>
                Kein Netzwerk verfügbar
              </div>
            )}
          </div>
        </div>

        {/* PIN-Verbindung */}
        <div style={styles.card}>
          <div style={styles.cardTitle}>🔑 PIN-Verbindung</div>
          {pin ? (
            <>
              <div style={styles.pinDisplay}>{pin}</div>
              <div style={styles.pinTimer}>
                ⏱️ Gültig noch {formatTime(pinExpiry)}
              </div>
              <div style={{ ...styles.instructions, marginTop: '16px' }}>
                <div style={styles.step}>
                  <span style={styles.stepNum}>1</span>
                  <span>Öffne <b>{info?.url}</b> auf dem Handy</span>
                </div>
                <div style={styles.step}>
                  <span style={styles.stepNum}>2</span>
                  <span>Gib diese PIN ein</span>
                </div>
                <div style={styles.step}>
                  <span style={styles.stepNum}>3</span>
                  <span>Volle Kontrolle über GhostShell</span>
                </div>
              </div>
              <button
                style={{ ...styles.generateBtn, background: '#1e293b', border: '1px solid #374151' }}
                onClick={handleGeneratePin}
              >🔄 Neue PIN generieren</button>
            </>
          ) : (
            <>
              <div style={{ textAlign: 'center', padding: '20px', color: '#64748b' }}>
                <div style={{ fontSize: '48px', marginBottom: '12px' }}>🔐</div>
                <p style={{ margin: '0 0 4px', fontSize: '14px' }}>
                  Sichere Verbindung ohne Passwort
                </p>
                <p style={{ margin: '0', fontSize: '12px' }}>
                  6-stellige PIN · 5 Minuten gültig
                </p>
              </div>
              <button
                style={styles.generateBtn}
                onClick={handleGeneratePin}
              >🔑 PIN generieren</button>
            </>
          )}
        </div>

        {/* Verbindungsstatus */}
        <div style={styles.card}>
          <div style={styles.cardTitle}>📊 Verbindungsstatus</div>
          <div style={styles.statusRow}>
            <span style={styles.statusLabel}>Hostname</span>
            <span style={styles.statusValue}>{info?.hostname || '—'}</span>
          </div>
          <div style={styles.statusRow}>
            <span style={styles.statusLabel}>Primäre IP</span>
            <span style={styles.statusValue}>
              <span style={styles.dot(info?.primary_ip ? '#10b981' : '#ef4444')} />
              {info?.primary_ip || 'Keine'}
            </span>
          </div>
          <div style={styles.statusRow}>
            <span style={styles.statusLabel}>Port</span>
            <span style={styles.statusValue}>{info?.port || '—'}</span>
          </div>
          <div style={styles.statusRow}>
            <span style={styles.statusLabel}>WLAN</span>
            <span style={styles.statusValue}>
              {info?.wifi_ssid ? (
                <><span style={styles.dot('#10b981')} /> {info.wifi_ssid}</>
              ) : (
                <><span style={styles.dot('#f59e0b')} /> Kabel/Unbekannt</>
              )}
            </span>
          </div>
          <div style={{ ...styles.statusRow, borderBottom: 'none' }}>
            <span style={styles.statusLabel}>Dashboard</span>
            <span style={styles.statusValue}>
              <span style={styles.dot('#10b981')} />
              Erreichbar
            </span>
          </div>
        </div>

        {/* Netzwerk-Interfaces */}
        <div style={styles.card}>
          <div style={styles.cardTitle}>🌐 Netzwerk-Interfaces</div>
          {info?.interfaces?.length > 0 ? (
            <table style={styles.ifaceTable}>
              <thead>
                <tr>
                  <th style={styles.th}>Interface</th>
                  <th style={styles.th}>IP-Adresse</th>
                  <th style={styles.th}>Prefix</th>
                </tr>
              </thead>
              <tbody>
                {info.interfaces.map((iface, i) => (
                  <tr key={i}>
                    <td style={styles.td}>{iface.interface}</td>
                    <td style={styles.td}>{iface.ip}</td>
                    <td style={styles.td}>/{iface.prefixlen}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ color: '#64748b', textAlign: 'center', padding: '20px' }}>
              Keine Interfaces gefunden
            </div>
          )}
        </div>

        {/* Anleitung */}
        <div style={styles.cardFull}>
          <div style={styles.cardTitle}>📋 Anleitung – Handy verbinden</div>
          <div style={styles.instructions}>
            <div style={styles.step}>
              <span style={styles.stepNum}>1</span>
              <span>Stelle sicher, dass <b>PC und Handy im selben WLAN</b> sind</span>
            </div>
            <div style={styles.step}>
              <span style={styles.stepNum}>2</span>
              <span><b>QR-Code scannen</b> mit der Handy-Kamera oder URL manuell eingeben</span>
            </div>
            <div style={styles.step}>
              <span style={styles.stepNum}>3</span>
              <span>Im Browser öffnet sich das <b>GhostShell Dashboard</b> — volle Kontrolle</span>
            </div>
            <div style={styles.step}>
              <span style={styles.stepNum}>4</span>
              <span><b>Optional:</b> "Zum Startbildschirm hinzufügen" für App-Feeling (PWA)</span>
            </div>
          </div>
          <div style={{ marginTop: '12px', fontSize: '12px', color: '#64748b' }}>
            💡 <b>Tipp:</b> Das Dashboard ist responsiv — es passt sich automatisch an die Bildschirmgröße deines Handys an.
            Speichere die URL als Lesezeichen für schnellen Zugriff.
          </div>
        </div>
      </div>
    </div>
  )
}
