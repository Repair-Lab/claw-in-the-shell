import React, { useState, useRef, useEffect, useCallback } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

// ═══════════════════════════════════════════════════════════════
// Ghost Mail — E-Mail Client mit Ghost LLM Integration
// ═══════════════════════════════════════════════════════════════

const FOLDERS = [
  { id: 'inbox',    icon: '📥', label: 'Posteingang' },
  { id: 'unread',   icon: '🔵', label: 'Ungelesen' },
  { id: 'starred',  icon: '⭐', label: 'Markiert' },
  { id: 'drafts',   icon: '📝', label: 'Entwürfe' },
  { id: 'sent',     icon: '📤', label: 'Gesendet' },
  { id: 'archived', icon: '📦', label: 'Archiv' },
]

const TONES = ['professionell', 'freundlich', 'kurz', 'formal']

export default function GhostMail({ windowId }) {
  const { settings, showSettings, setShowSettings } = useAppSettings('ghost-mail')

  // ── State ──
  const [folder, setFolder] = useState('inbox')
  const [messages, setMessages] = useState([])
  const [counts, setCounts] = useState({ total: 0, unread: 0, starred: 0 })
  const [selectedMail, setSelectedMail] = useState(null)
  const [loading, setLoading] = useState(false)
  const [view, setView] = useState('list') // list | read | compose
  const [accounts, setAccounts] = useState([])
  const [drafts, setDrafts] = useState([])
  const [sentMails, setSentMails] = useState([])

  // Compose State
  const [composeTo, setComposeTo] = useState('')
  const [composeCc, setComposeCc] = useState('')
  const [composeSubject, setComposeSubject] = useState('')
  const [composeBody, setComposeBody] = useState('')
  const [composeReplyTo, setComposeReplyTo] = useState(null)
  const [composeAccountId, setComposeAccountId] = useState(null)
  const [ghostLoading, setGhostLoading] = useState(false)
  const [ghostInstruction, setGhostInstruction] = useState('')
  const [showGhostPanel, setShowGhostPanel] = useState(false)
  const [selectedTone, setSelectedTone] = useState('professionell')

  // Account Config State
  const [showAccountConfig, setShowAccountConfig] = useState(false)
  const [newAccount, setNewAccount] = useState({
    account_name: '', email_address: '', display_name: '',
    imap_host: '', imap_port: 993, smtp_host: '', smtp_port: 587,
    auth_type: 'password', sync_enabled: false
  })

  // ── Data Loading ──
  const loadInbox = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.mailInbox({ folder })
      setMessages(data.messages || [])
      setCounts(data.counts || { total: 0, unread: 0, starred: 0 })
    } catch (e) { console.error('Inbox load failed:', e) }
    setLoading(false)
  }, [folder])

  const loadDrafts = useCallback(async () => {
    try {
      const d = await api.mailOutbox('draft')
      setDrafts(d || [])
    } catch (e) { console.error('Drafts load failed:', e) }
  }, [])

  const loadSent = useCallback(async () => {
    try {
      const d = await api.mailOutbox('sent')
      setSentMails(d || [])
    } catch (e) { console.error('Sent load failed:', e) }
  }, [])

  const loadAccounts = useCallback(async () => {
    try {
      const a = await api.mailAccounts()
      setAccounts(a || [])
      if (a?.length && !composeAccountId) setComposeAccountId(a[0].id)
    } catch (e) { console.error('Accounts load failed:', e) }
  }, [composeAccountId])

  useEffect(() => { loadAccounts() }, [])

  useEffect(() => {
    if (folder === 'drafts') loadDrafts()
    else if (folder === 'sent') loadSent()
    else loadInbox()
  }, [folder, loadInbox, loadDrafts, loadSent])

  // ── Mail Actions ──
  const openMail = async (mail) => {
    try {
      const full = await api.mailRead(mail.id)
      setSelectedMail(full)
      setView('read')
    } catch (e) { console.error(e) }
  }

  const toggleStar = async (id, current) => {
    await api.mailUpdate(id, { is_starred: !current })
    loadInbox()
  }

  const archiveMail = async (id) => {
    await api.mailUpdate(id, { is_archived: true })
    setView('list'); setSelectedMail(null)
    loadInbox()
  }

  const deleteMail = async (id) => {
    await api.mailUpdate(id, { is_deleted: true })
    setView('list'); setSelectedMail(null)
    loadInbox()
  }

  // ── Compose Actions ──
  const startCompose = (replyTo = null) => {
    setComposeReplyTo(replyTo)
    if (replyTo) {
      setComposeTo(replyTo.from_address || '')
      setComposeSubject(`Re: ${replyTo.subject || ''}`)
    } else {
      setComposeTo(''); setComposeSubject('')
    }
    setComposeCc(''); setComposeBody('')
    setShowGhostPanel(false); setGhostInstruction('')
    setView('compose')
  }

  const saveDraft = async () => {
    try {
      await api.mailCompose({
        account_id: composeAccountId,
        to: composeTo.split(',').map(s => s.trim()).filter(Boolean),
        cc: composeCc ? composeCc.split(',').map(s => s.trim()).filter(Boolean) : [],
        subject: composeSubject,
        body_text: composeBody,
        reply_to_id: composeReplyTo?.id,
        authored_by: 'human'
      })
      setView('list'); setFolder('drafts'); loadDrafts()
    } catch (e) { console.error(e) }
  }

  const sendMail = async (draftId) => {
    try {
      let id = draftId
      if (!id) {
        const draft = await api.mailCompose({
          account_id: composeAccountId,
          to: composeTo.split(',').map(s => s.trim()).filter(Boolean),
          cc: composeCc ? composeCc.split(',').map(s => s.trim()).filter(Boolean) : [],
          subject: composeSubject,
          body_text: composeBody,
          body_html: `<p>${composeBody.replace(/\n/g, '<br/>')}</p>`,
          reply_to_id: composeReplyTo?.id,
          authored_by: 'human'
        })
        id = draft.id
      }
      await api.mailSend(id)
      setView('list'); setFolder('sent'); loadSent()
    } catch (e) { alert(`Senden fehlgeschlagen: ${e.message}`) }
  }

  // ── Ghost LLM Actions ──
  const ghostCompose = async () => {
    if (!ghostInstruction.trim()) return
    setGhostLoading(true)
    try {
      const result = await api.mailGhostCompose(ghostInstruction, composeReplyTo?.id)
      if (result.subject) setComposeSubject(result.subject)
      if (result.body_text) setComposeBody(result.body_text)
    } catch (e) { console.error(e) }
    setGhostLoading(false)
  }

  const ghostImprove = async () => {
    if (!composeBody.trim()) return
    setGhostLoading(true)
    try {
      const result = await api.mailGhostImprove(composeBody, ghostInstruction || 'Verbessere Grammatik und Stil')
      if (result.body_text) setComposeBody(result.body_text)
      if (result.subject) setComposeSubject(result.subject)
    } catch (e) { console.error(e) }
    setGhostLoading(false)
  }

  const ghostReply = async () => {
    if (!selectedMail) return
    setGhostLoading(true)
    try {
      const result = await api.mailGhostReply(selectedMail.id, selectedTone)
      startCompose(selectedMail)
      if (result.subject) setComposeSubject(result.subject)
      if (result.body_text) setComposeBody(result.body_text)
    } catch (e) { console.error(e) }
    setGhostLoading(false)
  }

  const syncAccount = async (accountId) => {
    setLoading(true)
    try {
      const r = await api.mailSync(accountId)
      alert(`Sync abgeschlossen: ${r.new_messages} neue Nachrichten`)
      loadInbox()
    } catch (e) { alert(`Sync fehlgeschlagen: ${e.message}`) }
    setLoading(false)
  }

  // ── Settings Panel ──
  if (showSettings) return <AppSettingsPanel appId="ghost-mail" onClose={() => setShowSettings(false)} />

  // ── Styles ──
  const S = {
    container: { display: 'flex', height: '100%', background: '#0a0e14', color: '#c8d0d8', fontFamily: '-apple-system, system-ui, sans-serif', fontSize: 13, overflow: 'hidden' },
    sidebar: { width: 200, background: '#0d1117', borderRight: '1px solid #1a2332', display: 'flex', flexDirection: 'column', flexShrink: 0 },
    sidebarBtn: (active) => ({
      display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', cursor: 'pointer',
      background: active ? '#1a2332' : 'transparent', color: active ? '#00ffcc' : '#8090a0',
      border: 'none', textAlign: 'left', fontSize: 13, borderRadius: 4, margin: '1px 4px',
    }),
    content: { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' },
    toolbar: { display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid #1a2332', background: '#0d1117', flexShrink: 0 },
    btn: (primary) => ({
      padding: '5px 12px', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12,
      background: primary ? '#00ffcc' : '#1a2332', color: primary ? '#0a0e14' : '#8090a0',
      fontWeight: primary ? 600 : 400,
    }),
    mailRow: (read, selected) => ({
      display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', cursor: 'pointer',
      borderBottom: '1px solid #111820',
      background: selected ? '#1a2332' : 'transparent',
      fontWeight: read ? 400 : 600,
      color: read ? '#8090a0' : '#c8d0d8',
    }),
    input: { background: '#111820', border: '1px solid #1a2332', borderRadius: 4, padding: '6px 10px', color: '#c8d0d8', fontSize: 13, width: '100%', outline: 'none' },
    textarea: { background: '#111820', border: '1px solid #1a2332', borderRadius: 4, padding: '10px', color: '#c8d0d8', fontSize: 13, width: '100%', flex: 1, resize: 'none', outline: 'none', fontFamily: 'inherit' },
    badge: (n) => n > 0 ? { background: '#ff4444', color: '#fff', borderRadius: 10, padding: '1px 6px', fontSize: 11, marginLeft: 'auto' } : { display: 'none' },
    ghostPanel: { background: '#0f1520', border: '1px solid #1a3040', borderRadius: 8, padding: 12, margin: '0 12px 8px', display: 'flex', flexDirection: 'column', gap: 8 },
  }

  // ═══════════════════════════════════════════════════════════════
  // RENDER — Sidebar
  // ═══════════════════════════════════════════════════════════════
  return (
    <div style={S.container}>
      {/* ── Sidebar ── */}
      <div style={S.sidebar}>
        <button style={{ ...S.btn(true), margin: '8px', textAlign: 'center' }} onClick={() => startCompose()}>
          ✏️ Neue E-Mail
        </button>

        {FOLDERS.map(f => (
          <button key={f.id} style={S.sidebarBtn(folder === f.id)} onClick={() => { setFolder(f.id); setView('list') }}>
            <span>{f.icon}</span>
            <span>{f.label}</span>
            {f.id === 'inbox' && <span style={S.badge(counts.unread)}>{counts.unread}</span>}
            {f.id === 'unread' && <span style={S.badge(counts.unread)}>{counts.unread}</span>}
            {f.id === 'starred' && <span style={S.badge(counts.starred)}>{counts.starred}</span>}
          </button>
        ))}

        <div style={{ marginTop: 'auto', borderTop: '1px solid #1a2332', padding: 8 }}>
          <div style={{ color: '#506070', fontSize: 11, marginBottom: 6 }}>Konten</div>
          {accounts.map(a => (
            <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '4px 0', fontSize: 11 }}>
              <span style={{ color: a.sync_state === 'error' ? '#ff4444' : '#00ffcc' }}>●</span>
              <span style={{ color: '#8090a0', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.email_address || a.account_name}</span>
              <button style={{ ...S.btn(false), padding: '2px 5px', fontSize: 10 }} onClick={() => syncAccount(a.id)} title="Synchronisieren">🔄</button>
            </div>
          ))}
          <button style={{ ...S.btn(false), width: '100%', marginTop: 4, fontSize: 11 }} onClick={() => setShowAccountConfig(true)}>
            + Konto hinzufügen
          </button>
        </div>
      </div>

      {/* ── Content ── */}
      <div style={S.content}>

        {/* ═══ Account Config Modal ═══ */}
        {showAccountConfig && (
          <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ background: '#0d1117', border: '1px solid #1a2332', borderRadius: 8, padding: 20, width: 400, maxHeight: '80%', overflow: 'auto' }}>
              <h3 style={{ color: '#00ffcc', margin: '0 0 12px' }}>📧 E-Mail Konto hinzufügen</h3>
              {['account_name', 'email_address', 'display_name', 'imap_host', 'smtp_host'].map(f => (
                <div key={f} style={{ marginBottom: 8 }}>
                  <label style={{ color: '#607080', fontSize: 11, display: 'block', marginBottom: 2 }}>{f.replace(/_/g, ' ')}</label>
                  <input style={S.input} value={newAccount[f]} onChange={e => setNewAccount(p => ({ ...p, [f]: e.target.value }))} />
                </div>
              ))}
              <div style={{ display: 'flex', gap: 8 }}>
                <div style={{ flex: 1 }}>
                  <label style={{ color: '#607080', fontSize: 11 }}>IMAP Port</label>
                  <input style={S.input} type="number" value={newAccount.imap_port} onChange={e => setNewAccount(p => ({ ...p, imap_port: +e.target.value }))} />
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ color: '#607080', fontSize: 11 }}>SMTP Port</label>
                  <input style={S.input} type="number" value={newAccount.smtp_port} onChange={e => setNewAccount(p => ({ ...p, smtp_port: +e.target.value }))} />
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button style={S.btn(true)} onClick={async () => {
                  try { await api.mailAccountCreate(newAccount); loadAccounts(); setShowAccountConfig(false) }
                  catch (e) { alert(e.message) }
                }}>Speichern</button>
                <button style={S.btn(false)} onClick={() => setShowAccountConfig(false)}>Abbrechen</button>
              </div>
            </div>
          </div>
        )}

        {/* ═══ LIST VIEW ═══ */}
        {view === 'list' && (
          <>
            <div style={S.toolbar}>
              <span style={{ color: '#506070', fontSize: 12 }}>
                {FOLDERS.find(f => f.id === folder)?.icon} {FOLDERS.find(f => f.id === folder)?.label}
                {folder !== 'drafts' && folder !== 'sent' ? ` (${counts.total})` : ''}
              </span>
              <span style={{ flex: 1 }} />
              {loading && <span style={{ color: '#607080', fontSize: 11 }}>Lade…</span>}
              <button style={S.btn(false)} onClick={() => { if (folder === 'drafts') loadDrafts(); else if (folder === 'sent') loadSent(); else loadInbox() }}>🔄</button>
              <button style={S.btn(false)} onClick={() => setShowSettings(true)}>⚙️</button>
            </div>
            <div style={{ flex: 1, overflow: 'auto' }}>
              {folder === 'drafts' ? (
                drafts.length === 0 ? <div style={{ padding: 40, textAlign: 'center', color: '#506070' }}>Keine Entwürfe</div> :
                drafts.map(d => (
                  <div key={d.id} style={S.mailRow(true, false)} onClick={() => {
                    setComposeTo((d.to_addresses || []).join(', '))
                    setComposeSubject(d.subject || ''); setComposeBody(d.body_text || '')
                    setComposeAccountId(d.account_id); setView('compose')
                  }}>
                    <span style={{ color: '#607080', width: 26, textAlign: 'center' }}>📝</span>
                    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {d.subject || '(Kein Betreff)'}
                    </span>
                    <span style={{ color: '#506070', fontSize: 11 }}>{d.to_addresses?.[0] || ''}</span>
                  </div>
                ))
              ) : folder === 'sent' ? (
                sentMails.length === 0 ? <div style={{ padding: 40, textAlign: 'center', color: '#506070' }}>Keine gesendeten E-Mails</div> :
                sentMails.map(m => (
                  <div key={m.id} style={S.mailRow(true, false)}>
                    <span style={{ color: '#607080', width: 26, textAlign: 'center' }}>📤</span>
                    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {m.subject || '(Kein Betreff)'}
                    </span>
                    <span style={{ color: '#506070', fontSize: 11 }}>{(m.to_addresses || []).join(', ')}</span>
                  </div>
                ))
              ) : (
                messages.length === 0 ? <div style={{ padding: 40, textAlign: 'center', color: '#506070' }}>
                  {loading ? 'Lade E-Mails…' : 'Posteingang leer'}
                  {!loading && accounts.length === 0 && (
                    <div style={{ marginTop: 12 }}>
                      <button style={S.btn(true)} onClick={() => setShowAccountConfig(true)}>📧 E-Mail Konto einrichten</button>
                    </div>
                  )}
                </div> :
                messages.map(m => (
                  <div key={m.id} style={S.mailRow(m.is_read, selectedMail?.id === m.id)} onClick={() => openMail(m)}>
                    <button style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontSize: 14 }}
                      onClick={(e) => { e.stopPropagation(); toggleStar(m.id, m.is_starred) }}>
                      {m.is_starred ? '⭐' : '☆'}
                    </button>
                    <div style={{ flex: 1, overflow: 'hidden' }}>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <span style={{ fontWeight: m.is_read ? 400 : 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {m.from_name || m.from_address || 'Unbekannt'}
                        </span>
                        {m.auto_priority === 'urgent' && <span style={{ background: '#ff4444', color: '#fff', borderRadius: 4, padding: '0 4px', fontSize: 10 }}>URGENT</span>}
                        {m.needs_response && <span style={{ background: '#ff8800', color: '#fff', borderRadius: 4, padding: '0 4px', fontSize: 10 }}>Antwort nötig</span>}
                        <span style={{ color: '#506070', fontSize: 11, marginLeft: 'auto', flexShrink: 0 }}>
                          {m.received_at ? new Date(m.received_at).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''}
                        </span>
                      </div>
                      <div style={{ color: '#8090a0', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {m.subject || '(Kein Betreff)'}
                      </div>
                      {m.auto_summary && (
                        <div style={{ color: '#506070', fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginTop: 2 }}>
                          🤖 {m.auto_summary}
                        </div>
                      )}
                    </div>
                    {m.has_attachments && <span style={{ color: '#607080', fontSize: 12 }}>📎</span>}
                  </div>
                ))
              )}
            </div>
          </>
        )}

        {/* ═══ READ VIEW ═══ */}
        {view === 'read' && selectedMail && (
          <>
            <div style={S.toolbar}>
              <button style={S.btn(false)} onClick={() => { setView('list'); setSelectedMail(null) }}>← Zurück</button>
              <span style={{ flex: 1 }} />
              <button style={S.btn(true)} onClick={() => startCompose(selectedMail)}>↩️ Antworten</button>
              <button style={{ ...S.btn(false), background: '#1a2a3a' }} onClick={() => ghostReply()}>
                {ghostLoading ? '⏳' : '🤖'} Ghost Antwort
              </button>
              <select style={{ ...S.input, width: 'auto' }} value={selectedTone} onChange={e => setSelectedTone(e.target.value)}>
                {TONES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <button style={S.btn(false)} onClick={() => archiveMail(selectedMail.id)}>📦</button>
              <button style={S.btn(false)} onClick={() => deleteMail(selectedMail.id)}>🗑️</button>
            </div>
            <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
              <h2 style={{ color: '#e0e8f0', margin: '0 0 8px', fontSize: 18 }}>{selectedMail.subject}</h2>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#1a2332', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14 }}>
                  {(selectedMail.from_name || '?')[0]?.toUpperCase()}
                </div>
                <div>
                  <div style={{ fontWeight: 600 }}>{selectedMail.from_name || selectedMail.from_address}</div>
                  <div style={{ color: '#607080', fontSize: 11 }}>{selectedMail.from_address}</div>
                </div>
                <span style={{ color: '#506070', fontSize: 11, marginLeft: 'auto' }}>
                  {selectedMail.received_at ? new Date(selectedMail.received_at).toLocaleString('de-DE') : ''}
                </span>
              </div>
              <div style={{ color: '#607080', fontSize: 11, marginBottom: 12 }}>
                An: {(selectedMail.to_addresses || []).join(', ')}
                {selectedMail.cc_addresses?.length ? ` | CC: ${selectedMail.cc_addresses.join(', ')}` : ''}
              </div>

              {/* Auto-Tags & Sentiment */}
              {(selectedMail.auto_tags?.length > 0 || selectedMail.sentiment) && (
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 12 }}>
                  {selectedMail.auto_tags?.map(t => (
                    <span key={t} style={{ background: '#1a2332', color: '#00ccaa', borderRadius: 4, padding: '1px 6px', fontSize: 10 }}>{t}</span>
                  ))}
                  {selectedMail.sentiment && (
                    <span style={{
                      background: selectedMail.sentiment === 'positive' ? '#1a3a2a' : selectedMail.sentiment === 'negative' ? '#3a1a1a' : '#1a2a3a',
                      color: selectedMail.sentiment === 'positive' ? '#44ff88' : selectedMail.sentiment === 'negative' ? '#ff4444' : '#8090a0',
                      borderRadius: 4, padding: '1px 6px', fontSize: 10
                    }}>
                      {selectedMail.sentiment}
                    </span>
                  )}
                </div>
              )}

              {/* Ghost Auto-Summary */}
              {selectedMail.auto_summary && (
                <div style={{ background: '#0f1520', border: '1px solid #1a3040', borderRadius: 6, padding: 10, marginBottom: 12, fontSize: 12 }}>
                  <span style={{ color: '#00ccaa' }}>🤖 Zusammenfassung:</span> {selectedMail.auto_summary}
                </div>
              )}

              {/* Ghost Response (vorherige Antwortvorschläge) */}
              {selectedMail.ghost_response && (
                <div style={{ background: '#101a20', border: '1px solid #1a3a40', borderRadius: 6, padding: 10, marginBottom: 12, fontSize: 12 }}>
                  <div style={{ color: '#00ffcc', marginBottom: 4 }}>🤖 Ghost Antwortvorschlag:</div>
                  <div style={{ color: '#a0b0c0', whiteSpace: 'pre-wrap' }}>{selectedMail.ghost_response}</div>
                  <button style={{ ...S.btn(true), marginTop: 8, fontSize: 11 }} onClick={() => {
                    startCompose(selectedMail)
                    setComposeBody(selectedMail.ghost_response)
                  }}>
                    Vorschlag übernehmen
                  </button>
                </div>
              )}

              {/* Mail Body */}
              <div style={{ background: '#111820', borderRadius: 6, padding: 16, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                {selectedMail.body_html
                  ? <div dangerouslySetInnerHTML={{ __html: selectedMail.body_html }} />
                  : selectedMail.body_text || '(Kein Inhalt)'}
              </div>
            </div>
          </>
        )}

        {/* ═══ COMPOSE VIEW ═══ */}
        {view === 'compose' && (
          <>
            <div style={S.toolbar}>
              <button style={S.btn(false)} onClick={() => setView('list')}>← Verwerfen</button>
              <span style={{ flex: 1 }} />
              <button style={{ ...S.btn(false), background: '#1a2a3a' }} onClick={() => setShowGhostPanel(!showGhostPanel)}>
                🤖 Ghost LLM
              </button>
              <button style={S.btn(false)} onClick={saveDraft}>💾 Entwurf</button>
              <button style={S.btn(true)} onClick={() => sendMail()}>📤 Senden</button>
            </div>

            {/* Ghost LLM Panel */}
            {showGhostPanel && (
              <div style={S.ghostPanel}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ color: '#00ffcc', fontSize: 13 }}>🤖 Ghost E-Mail Assistent</span>
                  <span style={{ flex: 1 }} />
                  <button style={{ ...S.btn(false), padding: '2px 6px', fontSize: 11 }} onClick={() => setShowGhostPanel(false)}>✕</button>
                </div>
                <input
                  style={S.input}
                  placeholder="Was soll Ghost schreiben? z.B. 'Schreibe eine höfliche Absage' oder 'Antworte auf die Anfrage mit Terminvorschlag'"
                  value={ghostInstruction}
                  onChange={e => setGhostInstruction(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && ghostCompose()}
                />
                <div style={{ display: 'flex', gap: 6 }}>
                  <button style={S.btn(true)} onClick={ghostCompose} disabled={ghostLoading}>
                    {ghostLoading ? '⏳ Ghost schreibt…' : '✨ E-Mail schreiben'}
                  </button>
                  <button style={S.btn(false)} onClick={ghostImprove} disabled={ghostLoading || !composeBody}>
                    {ghostLoading ? '⏳' : '📝'} Text verbessern
                  </button>
                </div>
                {composeReplyTo && (
                  <div style={{ color: '#607080', fontSize: 11 }}>
                    ↩️ Antwort auf: {composeReplyTo.subject} (von {composeReplyTo.from_name || composeReplyTo.from_address})
                  </div>
                )}
              </div>
            )}

            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '0 12px 12px', gap: 6, overflow: 'auto' }}>
              {accounts.length > 1 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <label style={{ color: '#607080', fontSize: 12, width: 50 }}>Von:</label>
                  <select style={{ ...S.input, flex: 1 }} value={composeAccountId || ''} onChange={e => setComposeAccountId(e.target.value)}>
                    {accounts.map(a => <option key={a.id} value={a.id}>{a.display_name || a.email_address}</option>)}
                  </select>
                </div>
              )}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <label style={{ color: '#607080', fontSize: 12, width: 50 }}>An:</label>
                <input style={{ ...S.input, flex: 1 }} value={composeTo} onChange={e => setComposeTo(e.target.value)} placeholder="empfaenger@example.com" />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <label style={{ color: '#607080', fontSize: 12, width: 50 }}>CC:</label>
                <input style={{ ...S.input, flex: 1 }} value={composeCc} onChange={e => setComposeCc(e.target.value)} placeholder="optional" />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <label style={{ color: '#607080', fontSize: 12, width: 50 }}>Betreff:</label>
                <input style={{ ...S.input, flex: 1 }} value={composeSubject} onChange={e => setComposeSubject(e.target.value)} placeholder="Betreff" />
              </div>
              <textarea
                style={S.textarea}
                value={composeBody}
                onChange={e => setComposeBody(e.target.value)}
                placeholder="Schreibe deine E-Mail hier oder lass Ghost LLM für dich schreiben…"
              />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
