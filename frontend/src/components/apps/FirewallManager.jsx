import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'

export default function FirewallManager() {
  const [rules, setRules] = useState([])
  const [zones, setZones] = useState([])
  const [connections, setConnections] = useState([])
  const [tab, setTab] = useState('rules')
  const [showAdd, setShowAdd] = useState(false)
  const [newRule, setNewRule] = useState({ chain: 'INPUT', protocol: 'tcp', port: '', source_ip: '', action: 'DROP', description: '' })

  const load = useCallback(async () => {
    try {
      const [r, z, c] = await Promise.all([api.firewallRules(), api.firewallZones(), api.firewallConnections()])
      setRules(r.rules || [])
      setZones(z.zones || [])
      setConnections(c.connections || [])
    } catch { /* */ }
  }, [])

  useEffect(() => { load() }, [load])

  const addRule = async () => {
    if (!newRule.port && !newRule.source_ip) return
    try { await api.firewallAddRule(newRule); setShowAdd(false); setNewRule({ chain: 'INPUT', protocol: 'tcp', port: '', source_ip: '', action: 'DROP', description: '' }); await load() } catch { /* */ }
  }

  const applyRules = async () => {
    try { await api.firewallApply(); alert('Firewall-Regeln angewendet!') } catch { /* */ }
  }

  const actionColors = { ACCEPT: '#00ffcc', DROP: '#ff4444', REJECT: '#ffaa00', LOG: '#4488ff' }

  const S = {
    container: { display: 'flex', flexDirection: 'column', height: '100%', background: '#0a0a14', color: '#c8d6e5', padding: '16px', overflow: 'auto' },
    h: { color: '#00ffcc', fontSize: '18px', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' },
    card: { background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '8px', padding: '12px', marginBottom: '8px' },
    btn: { padding: '6px 16px', border: '1px solid #00ffcc', background: 'transparent', color: '#00ffcc', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' },
    tab: (active) => ({ padding: '6px 16px', border: '1px solid', borderColor: active ? '#00ffcc' : '#1a2a3a', background: active ? 'rgba(0,255,204,0.1)' : 'transparent', color: active ? '#00ffcc' : '#556', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }),
    input: { padding: '6px 10px', background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '6px', color: '#d4d4d4', fontSize: '12px', outline: 'none' },
    select: { padding: '6px 10px', background: '#0f1520', border: '1px solid #1a2a3a', borderRadius: '6px', color: '#d4d4d4', fontSize: '12px', outline: 'none' },
    th: { padding: '6px 8px', color: '#6688aa', fontSize: '11px', textAlign: 'left', borderBottom: '1px solid #1a2a3a' },
    td: { padding: '6px 8px', fontSize: '12px', borderBottom: '1px solid #111828' },
  }

  const stateColors = { ESTABLISHED: '#00ffcc', 'TIME_WAIT': '#ffaa00', LISTEN: '#4488ff', 'CLOSE_WAIT': '#ff4444' }

  return (
    <div style={S.container}>
      <div style={S.h}><span>🔥</span> Firewall & Netzwerk-Policy</div>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
        {[['rules', '📜 Regeln'], ['zones', '🌐 Zonen'], ['connections', '🔌 Verbindungen']].map(([k, l]) => (
          <button key={k} style={S.tab(tab === k)} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>

      {tab === 'rules' && (
        <>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
            <button style={S.btn} onClick={() => setShowAdd(!showAdd)}>+ Regel</button>
            <button style={{ ...S.btn, borderColor: '#ffaa00', color: '#ffaa00' }} onClick={applyRules}>⚡ Anwenden</button>
            <button style={{ ...S.btn, borderColor: '#556', color: '#556' }} onClick={load}>🔄</button>
          </div>

          {showAdd && (
            <div style={{ ...S.card, display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
              <select style={S.select} value={newRule.chain} onChange={e => setNewRule({ ...newRule, chain: e.target.value })}>
                <option value="INPUT">INPUT</option><option value="OUTPUT">OUTPUT</option><option value="FORWARD">FORWARD</option>
              </select>
              <select style={S.select} value={newRule.protocol} onChange={e => setNewRule({ ...newRule, protocol: e.target.value })}>
                <option value="tcp">TCP</option><option value="udp">UDP</option><option value="icmp">ICMP</option><option value="all">ALL</option>
              </select>
              <input style={{ ...S.input, width: '70px' }} value={newRule.port} onChange={e => setNewRule({ ...newRule, port: e.target.value })} placeholder="Port" />
              <input style={{ ...S.input, width: '120px' }} value={newRule.source_ip} onChange={e => setNewRule({ ...newRule, source_ip: e.target.value })} placeholder="Quell-IP" />
              <select style={S.select} value={newRule.action} onChange={e => setNewRule({ ...newRule, action: e.target.value })}>
                <option value="ACCEPT">ACCEPT</option><option value="DROP">DROP</option><option value="REJECT">REJECT</option><option value="LOG">LOG</option>
              </select>
              <input style={{ ...S.input, width: '150px' }} value={newRule.description} onChange={e => setNewRule({ ...newRule, description: e.target.value })} placeholder="Beschreibung..." />
              <button style={S.btn} onClick={addRule}>✓</button>
            </div>
          )}

          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>{['#', 'Chain', 'Proto', 'Port', 'Quelle', 'Aktion', 'Beschreibung'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {rules.map((r, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, color: '#556' }}>{r.priority || i + 1}</td>
                  <td style={S.td}>{r.chain}</td>
                  <td style={{ ...S.td, color: '#4488ff' }}>{r.protocol}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace' }}>{r.port || '*'}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace' }}>{r.source_ip || '*'}</td>
                  <td style={{ ...S.td, color: actionColors[r.action] || '#d4d4d4', fontWeight: 600 }}>{r.action}</td>
                  <td style={{ ...S.td, color: '#556' }}>{r.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rules.length === 0 && <div style={{ textAlign: 'center', padding: '20px', color: '#334' }}>Keine Firewall-Regeln konfiguriert</div>}
        </>
      )}

      {tab === 'zones' && (
        <>
          {zones.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '20px', color: '#334' }}>Keine Zonen definiert</div>
          ) : zones.map((z, i) => (
            <div key={i} style={S.card}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <strong style={{ color: '#d4d4d4' }}>{z.zone_name}</strong>
                <span style={{ padding: '2px 8px', borderRadius: '10px', fontSize: '10px', fontWeight: 600, background: z.is_active ? 'rgba(0,255,204,0.15)' : '#111', color: z.is_active ? '#00ffcc' : '#556' }}>
                  {z.is_active ? 'Aktiv' : 'Inaktiv'}
                </span>
              </div>
              <div style={{ display: 'flex', gap: '16px', fontSize: '11px', color: '#556' }}>
                <span>Policy: <span style={{ color: actionColors[z.default_policy] || '#d4d4d4' }}>{z.default_policy}</span></span>
                <span>Interfaces: {z.interfaces?.join(', ') || '—'}</span>
              </div>
              {z.description && <div style={{ color: '#445', fontSize: '11px', marginTop: '4px' }}>{z.description}</div>}
            </div>
          ))}
        </>
      )}

      {tab === 'connections' && (
        <>
          <button style={{ ...S.btn, marginBottom: '12px' }} onClick={load}>🔄 Aktualisieren</button>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>{['Proto', 'Lokal', 'Remote', 'Status', 'Prozess'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {connections.map((c, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, color: '#4488ff' }}>{c.protocol}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px' }}>{c.local_address}:{c.local_port}</td>
                  <td style={{ ...S.td, fontFamily: 'monospace', fontSize: '11px' }}>{c.remote_address || '*'}:{c.remote_port || '*'}</td>
                  <td style={{ ...S.td, color: stateColors[c.status] || '#556', fontWeight: 600, fontSize: '11px' }}>{c.status}</td>
                  <td style={{ ...S.td, color: '#6688aa', fontSize: '11px' }}>{c.process_name || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {connections.length === 0 && <div style={{ textAlign: 'center', padding: '20px', color: '#334' }}>Keine aktiven Verbindungen</div>}
        </>
      )}
    </div>
  )
}
