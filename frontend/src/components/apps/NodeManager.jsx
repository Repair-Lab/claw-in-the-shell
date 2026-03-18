import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

const ICON_TYPES = [
  { value: 'circle', label: '⭕ Kreis' },
  { value: 'play', label: '▶️ Play (YouTube)' },
  { value: 'search', label: '🔍 Suche (Google)' },
  { value: 'nas', label: '💾 NAS/Storage' },
  { value: 'phone', label: '📱 Smartphone' },
  { value: 'server', label: '🖥️ Server' },
  { value: 'cloud', label: '☁️ Cloud' },
  { value: 'printer', label: '🖨️ Drucker' },
  { value: 'camera', label: '📷 Kamera' },
  { value: 'iot', label: '📡 IoT-Gerät' },
  { value: 'chat', label: '💬 Chat/Messenger' },
  { value: 'message', label: '✉️ Nachricht' },
]

const NODE_TYPES = [
  { value: 'service', label: 'Service' },
  { value: 'device', label: 'Gerät' },
  { value: 'cloud', label: 'Cloud' },
  { value: 'custom', label: 'Custom' },
]

const PRESET_COLORS = [
  '#ff2b2b', '#4285F4', '#00f5ff', '#00ff88',
  '#ff4b3a', '#9b59ff', '#f0c27b', '#ff6600',
  '#556677', '#cc66ff', '#ffaa00', '#ffffff',
]

function emptyNode() {
  return {
    node_key: '',
    label: '',
    node_type: 'service',
    icon_type: 'circle',
    color: '#00f5ff',
    glow_color: '',
    position_x: 400,
    position_y: 300,
    scale: 1.0,
    app_id: '',
    url: '',
    is_visible: true,
    sort_order: 0,
  }
}

export default function NodeManager({ onRefreshNodes }) {
  const { settings, schema, update: updateSetting, reset: resetSettings } = useAppSettings('node-manager')
  const [showSettings, setShowSettings] = useState(false)
  const [nodes, setNodes] = useState([])
  const [loading, setLoading] = useState(true)
  const [editNode, setEditNode] = useState(null) // null = Liste, object = Bearbeiten/Neu
  const [isNew, setIsNew] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const loadNodes = useCallback(() => {
    setLoading(true)
    api.desktopNodesAll()
      .then(d => setNodes(d.nodes || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadNodes() }, [loadNodes])

  const handleSave = async () => {
    setError('')
    setSaving(true)
    try {
      if (isNew) {
        const body = { ...editNode }
        if (!body.glow_color) delete body.glow_color
        if (!body.app_id) delete body.app_id
        if (!body.url) delete body.url
        await api.desktopNodeCreate(body)
        setSuccess(`"${body.label}" erstellt!`)
      } else {
        const { id, created_at, updated_at, ...body } = editNode
        if (!body.glow_color) body.glow_color = null
        if (!body.app_id) body.app_id = null
        if (!body.url) body.url = null
        await api.desktopNodeUpdate(id, body)
        setSuccess(`"${body.label}" gespeichert!`)
      }
      setEditNode(null)
      setIsNew(false)
      loadNodes()
      if (onRefreshNodes) onRefreshNodes()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (node) => {
    if (!confirm(`"${node.label}" wirklich löschen?`)) return
    try {
      await api.desktopNodeDelete(node.id)
      setSuccess(`"${node.label}" gelöscht`)
      loadNodes()
      if (onRefreshNodes) onRefreshNodes()
    } catch (e) {
      setError(e.message)
    }
  }

  const startNew = () => {
    setEditNode(emptyNode())
    setIsNew(true)
    setError('')
    setSuccess('')
  }

  const startEdit = (node) => {
    setEditNode({ ...node, glow_color: node.glow_color || '' })
    setIsNew(false)
    setError('')
    setSuccess('')
  }

  // Auto-clear success
  useEffect(() => {
    if (success) {
      const t = setTimeout(() => setSuccess(''), 3000)
      return () => clearTimeout(t)
    }
  }, [success])

  const s = {
    container: { padding: 16, fontFamily: "'Inter', sans-serif", fontSize: 13, color: '#e0e0e0', height: '100%', display: 'flex', flexDirection: 'column' },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
    title: { fontSize: 18, fontWeight: 700, color: '#f0c27b' },
    btn: { padding: '6px 16px', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: 12 },
    btnPrimary: { background: 'linear-gradient(135deg, #00aa88, #00ffcc)', color: '#0a0a0f' },
    btnDanger: { background: '#ff4444', color: '#fff' },
    btnSecondary: { background: '#252540', color: '#e0e0e0', border: '1px solid #1a3a4a' },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
    th: { textAlign: 'left', padding: '8px 10px', borderBottom: '1px solid #1a3a4a', color: '#6688aa', fontWeight: 500, textTransform: 'uppercase', fontSize: 10, letterSpacing: 1 },
    td: { padding: '8px 10px', borderBottom: '1px solid #1a3a4a22' },
    colorDot: (c) => ({ display: 'inline-block', width: 14, height: 14, borderRadius: '50%', background: c, marginRight: 6, verticalAlign: 'middle', boxShadow: `0 0 6px ${c}55` }),
    input: { width: '100%', padding: '8px 12px', background: '#0a0a0f', border: '1px solid #1a3a4a', borderRadius: 6, color: '#e0e0e0', fontFamily: "'JetBrains Mono', monospace", fontSize: 12, outline: 'none' },
    select: { width: '100%', padding: '8px 12px', background: '#0a0a0f', border: '1px solid #1a3a4a', borderRadius: 6, color: '#e0e0e0', fontSize: 12, outline: 'none' },
    label: { display: 'block', marginBottom: 4, color: '#6688aa', fontSize: 11, fontWeight: 500 },
    formGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 },
    error: { color: '#ff4444', fontSize: 12, marginBottom: 8 },
    success: { color: '#00ff88', fontSize: 12, marginBottom: 8 },
    colorPalette: { display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 },
    colorSwatch: (c, active) => ({ width: 24, height: 24, borderRadius: '50%', background: c, cursor: 'pointer', border: active ? '2px solid #fff' : '2px solid transparent', boxShadow: active ? `0 0 8px ${c}` : 'none' }),
    scrollArea: { flex: 1, overflow: 'auto' },
  }

  // ── Bearbeiten/Neu-Formular ──
  if (editNode) {
    return (
      <div style={s.container}>
        <div style={s.header}>
          <span style={s.title}>{isNew ? '➕ Neuer Knoten' : `✏️ ${editNode.label} bearbeiten`}</span>
          <button style={{ ...s.btn, ...s.btnSecondary }} onClick={() => { setEditNode(null); setIsNew(false) }}>← Zurück</button>
        </div>
        {error && <div style={s.error}>⚠️ {error}</div>}

        <div style={s.scrollArea}>
          <div style={s.formGrid}>
            <div>
              <label style={s.label}>Schlüssel (unique)</label>
              <input style={s.input} value={editNode.node_key} placeholder="z.B. spotify"
                onChange={e => setEditNode(p => ({ ...p, node_key: e.target.value }))} disabled={!isNew} />
            </div>
            <div>
              <label style={s.label}>Anzeigename</label>
              <input style={s.input} value={editNode.label} placeholder="z.B. Spotify"
                onChange={e => setEditNode(p => ({ ...p, label: e.target.value }))} />
            </div>
            <div>
              <label style={s.label}>Typ</label>
              <select style={s.select} value={editNode.node_type}
                onChange={e => setEditNode(p => ({ ...p, node_type: e.target.value }))}>
                {NODE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label style={s.label}>Icon</label>
              <select style={s.select} value={editNode.icon_type}
                onChange={e => setEditNode(p => ({ ...p, icon_type: e.target.value }))}>
                {ICON_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label style={s.label}>Position X (0–1920)</label>
              <input style={s.input} type="number" min="0" max="1920"
                value={editNode.position_x}
                onChange={e => setEditNode(p => ({ ...p, position_x: parseFloat(e.target.value) || 0 }))} />
            </div>
            <div>
              <label style={s.label}>Position Y (0–1080)</label>
              <input style={s.input} type="number" min="0" max="1080"
                value={editNode.position_y}
                onChange={e => setEditNode(p => ({ ...p, position_y: parseFloat(e.target.value) || 0 }))} />
            </div>
            <div>
              <label style={s.label}>Skalierung</label>
              <input style={s.input} type="number" min="0.1" max="5" step="0.1"
                value={editNode.scale}
                onChange={e => setEditNode(p => ({ ...p, scale: parseFloat(e.target.value) || 1 }))} />
            </div>
            <div>
              <label style={s.label}>Sortierung</label>
              <input style={s.input} type="number"
                value={editNode.sort_order}
                onChange={e => setEditNode(p => ({ ...p, sort_order: parseInt(e.target.value) || 0 }))} />
            </div>
            <div>
              <label style={s.label}>App-ID (optional, z.B. web-frame)</label>
              <input style={s.input} value={editNode.app_id || ''} placeholder="web-frame"
                onChange={e => setEditNode(p => ({ ...p, app_id: e.target.value }))} />
            </div>
            <div>
              <label style={s.label}>URL (für WebFrame)</label>
              <input style={s.input} value={editNode.url || ''} placeholder="https://..."
                onChange={e => setEditNode(p => ({ ...p, url: e.target.value }))} />
            </div>
          </div>

          {/* Farbwahl */}
          <div style={{ marginBottom: 16 }}>
            <label style={s.label}>Farbe</label>
            <div style={s.colorPalette}>
              {PRESET_COLORS.map(c => (
                <div key={c} style={s.colorSwatch(c, editNode.color === c)}
                  onClick={() => setEditNode(p => ({ ...p, color: c }))} />
              ))}
              <input type="color" value={editNode.color}
                onChange={e => setEditNode(p => ({ ...p, color: e.target.value }))}
                style={{ width: 24, height: 24, border: 'none', padding: 0, cursor: 'pointer', borderRadius: '50%' }} />
            </div>
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={s.label}>Glow-Farbe (optional, Standard = Hauptfarbe)</label>
            <div style={s.colorPalette}>
              <div style={s.colorSwatch('transparent', !editNode.glow_color)}
                onClick={() => setEditNode(p => ({ ...p, glow_color: '' }))} title="Standard" />
              {PRESET_COLORS.map(c => (
                <div key={c} style={s.colorSwatch(c, editNode.glow_color === c)}
                  onClick={() => setEditNode(p => ({ ...p, glow_color: c }))} />
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <input type="checkbox" checked={editNode.is_visible}
              onChange={e => setEditNode(p => ({ ...p, is_visible: e.target.checked }))} />
            <label style={{ ...s.label, margin: 0 }}>Sichtbar auf Desktop</label>
          </div>

          {/* Vorschau-Info */}
          <div style={{ background: '#0a0a0f', border: '1px solid #1a3a4a', borderRadius: 8, padding: 12, marginBottom: 16 }}>
            <div style={{ fontSize: 11, color: '#6688aa', marginBottom: 6 }}>VORSCHAU</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 40, height: 40, borderRadius: '50%', background: editNode.color, boxShadow: `0 0 12px ${editNode.glow_color || editNode.color}55`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ fontSize: 16 }}>{ICON_TYPES.find(t => t.value === editNode.icon_type)?.label?.charAt(0) || '⭕'}</span>
              </div>
              <div>
                <div style={{ fontWeight: 600 }}>{editNode.label || '(kein Name)'}</div>
                <div style={{ fontSize: 11, color: '#6688aa' }}>{editNode.node_type} · {editNode.icon_type} · ({Math.round(editNode.position_x)}, {Math.round(editNode.position_y)})</div>
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', paddingTop: 8, borderTop: '1px solid #1a3a4a' }}>
          <button style={{ ...s.btn, ...s.btnSecondary }} onClick={() => { setEditNode(null); setIsNew(false) }}>Abbrechen</button>
          <button style={{ ...s.btn, ...s.btnPrimary }} onClick={handleSave} disabled={saving || !editNode.node_key || !editNode.label}>
            {saving ? '⏳ Speichern...' : isNew ? '✅ Erstellen' : '💾 Speichern'}
          </button>
        </div>
      </div>
    )
  }

  // ── Node-Liste ──
  return (
    <div style={s.container}>
      <div style={s.header}>
        <span style={s.title}>🔧 Netzwerk-Knoten</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={{ ...s.btn, ...s.btnPrimary }} onClick={startNew}>+ Neuer Knoten</button>
          <button style={s.btn} onClick={() => setShowSettings(!showSettings)} title="Einstellungen">⚙️</button>
        </div>
      </div>

      {showSettings && (
        <div style={{ marginBottom: 12 }}>
          <AppSettingsPanel schema={schema} settings={settings} onUpdate={updateSetting} onReset={resetSettings} title="Node-Manager" />
        </div>
      )}

      {error && <div style={s.error}>⚠️ {error}</div>}
      {success && <div style={s.success}>✅ {success}</div>}

      <div style={{ fontSize: 11, color: '#6688aa', marginBottom: 12 }}>
        {nodes.length} Knoten · Neuen Knoten hinzufügen = sofort auf dem Desktop sichtbar
      </div>

      <div style={s.scrollArea}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#6688aa' }}>⏳ Lade...</div>
        ) : (
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>Farbe</th>
                <th style={s.th}>Schlüssel</th>
                <th style={s.th}>Label</th>
                <th style={s.th}>Icon</th>
                <th style={s.th}>Typ</th>
                <th style={s.th}>Position</th>
                <th style={s.th}>Sichtbar</th>
                <th style={s.th}>Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {nodes.map(node => (
                <tr key={node.id} style={{ opacity: node.is_visible ? 1 : 0.5 }}>
                  <td style={s.td}><span style={s.colorDot(node.color)} /></td>
                  <td style={{ ...s.td, fontFamily: "'JetBrains Mono', monospace" }}>{node.node_key}</td>
                  <td style={s.td}>{node.label}</td>
                  <td style={s.td}>{ICON_TYPES.find(t => t.value === node.icon_type)?.label || node.icon_type}</td>
                  <td style={s.td}>{node.node_type}</td>
                  <td style={{ ...s.td, fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>
                    {Math.round(node.position_x)}, {Math.round(node.position_y)}
                  </td>
                  <td style={s.td}>{node.is_visible ? '✅' : '❌'}</td>
                  <td style={s.td}>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button style={{ ...s.btn, ...s.btnSecondary, padding: '3px 8px' }}
                        onClick={() => startEdit(node)}>✏️</button>
                      <button style={{ ...s.btn, ...s.btnDanger, padding: '3px 8px' }}
                        onClick={() => handleDelete(node)}>🗑️</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Schnell-Hinzufügen Vorlagen */}
      <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid #1a3a4a' }}>
        <div style={{ fontSize: 11, color: '#6688aa', marginBottom: 6 }}>⚡ SCHNELL-VORLAGEN</div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {[
            { key: 'whatsapp', label: 'WhatsApp', icon: 'chat', color: '#25D366', url: 'https://web.whatsapp.com', desc: 'QR-Code scannen & verbinden' },
            { key: 'telegram', label: 'Telegram', icon: 'message', color: '#0088cc', url: 'https://web.telegram.org', desc: 'QR-Code scannen & verbinden' },
            { key: 'twitch', label: 'Twitch', icon: 'play', color: '#9b59ff', url: 'https://www.twitch.tv' },
            { key: 'github', label: 'GitHub', icon: 'circle', color: '#ffffff', url: 'https://github.com' },
            { key: 'spotify', label: 'Spotify', icon: 'circle', color: '#1DB954', url: 'https://open.spotify.com' },
            { key: 'discord', label: 'Discord', icon: 'chat', color: '#5865F2', url: 'https://discord.com' },
            { key: 'signal', label: 'Signal', icon: 'message', color: '#3A76F0', url: 'https://signal.org', desc: 'Sicherer Messenger' },
            { key: 'homeserver', label: 'Home Server', icon: 'server', color: '#00ff88', url: '' },
            { key: 'ipcam', label: 'IP-Kamera', icon: 'camera', color: '#ff6600', url: '' },
            { key: 'iot-hub', label: 'IoT Hub', icon: 'iot', color: '#00f5ff', url: '' },
            { key: 'cloud-backup', label: 'Cloud Backup', icon: 'cloud', color: '#4488ff', url: '' },
          ].filter(t => !nodes.find(n => n.node_key === t.key)).map(tmpl => (
            <button key={tmpl.key}
              style={{ ...s.btn, ...s.btnSecondary, display: 'flex', alignItems: 'center', gap: 4, padding: '4px 10px' }}
              onClick={() => {
                setEditNode({
                  ...emptyNode(),
                  node_key: tmpl.key,
                  label: tmpl.label,
                  icon_type: tmpl.icon,
                  color: tmpl.color,
                  url: tmpl.url,
                  app_id: tmpl.url ? 'web-frame' : '',
                  position_x: 200 + Math.random() * 1500,
                  position_y: 200 + Math.random() * 600,
                })
                setIsNew(true)
              }}>
              <span style={s.colorDot(tmpl.color)} />
              {tmpl.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
