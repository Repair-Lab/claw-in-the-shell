import React, { useState } from 'react'

/**
 * Login-Screen — Cyberpunk-Login gegen die users-Tabelle
 */
export default function LoginScreen({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!username || !password) {
      setError('Benutzername und Passwort erforderlich')
      return
    }

    setLoading(true)
    setError('')

    try {
      const result = await onLogin(username, password)
      if (!result.success) {
        setError(result.error || 'Login fehlgeschlagen')
      }
    } catch (err) {
      setError(err.message || 'Verbindungsfehler')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-screen">
      {/* Subtle background effect */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at center, rgba(0,255,204,0.03) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      <form className="login-card" onSubmit={handleSubmit}>
        <div style={{ fontSize: '48px', marginBottom: '12px' }}>👻</div>
        <h1>DBAI</h1>
        <div className="subtitle">Ghost in the Database — v0.3.0</div>

        <input
          type="text"
          placeholder="Benutzername"
          value={username}
          onChange={e => setUsername(e.target.value)}
          autoFocus
          autoComplete="username"
        />

        <input
          type="password"
          placeholder="Passwort"
          value={password}
          onChange={e => setPassword(e.target.value)}
          autoComplete="current-password"
        />

        <button type="submit" disabled={loading}>
          {loading ? '⏳ Authentifizierung...' : '🔐 Einloggen'}
        </button>

        {error && <div className="error">{error}</div>}

        <div style={{ marginTop: '24px', fontSize: '10px', color: 'var(--text-secondary)' }}>
          Nur lokale Verbindungen. Keine externen APIs.
        </div>
      </form>
    </div>
  )
}
