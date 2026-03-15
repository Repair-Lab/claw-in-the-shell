import React, { useState, useRef, useEffect } from 'react'
import { api } from '../../api'

/**
 * Ghost Chat — Chat mit dem aktiven Ghost
 */
export default function GhostChat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [role, setRole] = useState('sysadmin')
  const [roles, setRoles] = useState([])
  const [loading, setLoading] = useState(false)
  const messagesRef = useRef(null)

  // Load available roles
  useEffect(() => {
    api.ghosts().then(data => {
      setRoles(data.roles || [])
      // Select first active ghost role
      if (data.active_ghosts?.length > 0) {
        setRole(data.active_ghosts[0].role_name)
      }
    }).catch(() => {})
  }, [])

  // Auto-scroll
  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight
    }
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || loading) return

    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setLoading(true)

    try {
      const result = await api.askGhost(role, userMsg)

      if (result.error) {
        setMessages(prev => [...prev, {
          role: 'system',
          content: `⚠️ ${result.error}${result.hint ? '\n💡 ' + result.hint : ''}`,
        }])
      } else {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: `⏳ Anfrage an ${result.model} gesendet (Task: ${result.task_id?.slice(0, 8)}...)\n` +
                   `Status: ${result.status}`,
        }])
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'system',
        content: `❌ Fehler: ${err.message}`,
      }])
    }

    setLoading(false)
  }

  const selectedRole = roles.find(r => r.name === role)

  return (
    <div className="chat-container">
      {/* Role Selector */}
      <div style={{
        display: 'flex', gap: '8px', marginBottom: '12px',
        paddingBottom: '12px', borderBottom: '1px solid var(--border)',
        alignItems: 'center',
      }}>
        <span className="text-xs text-muted">Ghost:</span>
        {roles.map(r => (
          <button
            key={r.name}
            onClick={() => setRole(r.name)}
            style={{
              padding: '4px 10px', borderRadius: 'var(--radius)',
              border: `1px solid ${role === r.name ? r.color || 'var(--accent)' : 'var(--border)'}`,
              background: role === r.name ? `${r.color || 'var(--accent)'}15` : 'transparent',
              color: role === r.name ? r.color || 'var(--accent)' : 'var(--text-secondary)',
              cursor: 'pointer', fontSize: '11px',
            }}
          >
            {r.icon} {r.display_name}
          </button>
        ))}
      </div>

      {/* System Prompt Info */}
      {selectedRole && (
        <div className="text-xs text-muted" style={{
          marginBottom: '12px', padding: '8px',
          background: 'var(--bg-surface)', borderRadius: 'var(--radius)',
        }}>
          💡 {selectedRole.description}
        </div>
      )}

      {/* Messages */}
      <div className="chat-messages" ref={messagesRef}>
        {messages.length === 0 && (
          <div className="text-muted" style={{ textAlign: 'center', marginTop: '40px' }}>
            <div style={{ fontSize: '48px', marginBottom: '12px' }}>👻</div>
            <p>Starte eine Konversation mit dem Ghost.</p>
            <p className="text-xs mt-2">
              Wähle eine Rolle und stelle eine Frage.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            {msg.content.split('\n').map((line, j) => (
              <div key={j}>{line}</div>
            ))}
          </div>
        ))}

        {loading && (
          <div className="chat-message assistant" style={{ opacity: 0.6 }}>
            ⏳ Ghost denkt nach...
          </div>
        )}
      </div>

      {/* Input */}
      <div className="chat-input">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendMessage()}
          placeholder={`Frage an ${selectedRole?.display_name || 'Ghost'}...`}
          disabled={loading}
          autoFocus
        />
        <button onClick={sendMessage} disabled={loading}>
          Senden
        </button>
      </div>
    </div>
  )
}
