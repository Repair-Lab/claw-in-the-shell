import React, { useState, useEffect } from 'react'
import { api } from '../../api'

/**
 * First-Boot Setup Wizard — Benutzer durch Ersteinrichtung führen
 * Einstellungen: Sprache, Timezone, Theme, LLM-Modell, Netzwerk
 */
export default function SetupWizard() {
  const [step, setStep] = useState(0)
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)
  const [themes, setThemes] = useState([])

  const [settings, setSettings] = useState({
    locale: 'de-DE',
    timezone: 'Europe/Berlin',
    theme: 'ghost-dark',
    hostname: 'dbai',
    defaultModel: 'qwen2.5-7b-instruct',
    enableTelemetry: true,
    enableAutoHeal: true,
    enableGhostSwap: true,
  })

  useEffect(() => {
    api.themes().then(t => setThemes(t || [])).catch(() => {})
  }, [])

  const update = (key, value) => setSettings(prev => ({ ...prev, [key]: value }))

  const steps = [
    { title: '🌍 Sprache & Region', description: 'Grundeinstellungen für dein System' },
    { title: '🎨 Erscheinungsbild', description: 'Wähle ein Theme für deinen Desktop' },
    { title: '🧠 KI-Konfiguration', description: 'Standard-Ghost und Autonomie-Level' },
    { title: '🛡️ System & Sicherheit', description: 'Self-Healing und Telemetrie' },
    { title: '✅ Zusammenfassung', description: 'Prüfe deine Einstellungen' },
  ]

  const handleFinish = async () => {
    setSaving(true)
    try {
      await api.setupComplete(settings)
      setDone(true)
    } catch (err) {
      alert('Setup fehlgeschlagen: ' + err.message)
    }
    setSaving(false)
  }

  if (done) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', height: '100%', gap: '16px',
        fontFamily: 'var(--font-sans)',
      }}>
        <span style={{ fontSize: '48px' }}>🎉</span>
        <h2 style={{ color: 'var(--accent)', margin: 0 }}>Setup abgeschlossen!</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
          DBAI ist jetzt konfiguriert. Der Desktop wird in wenigen Sekunden geladen.
        </p>
      </div>
    )
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      fontFamily: 'var(--font-sans)', fontSize: '13px',
    }}>
      {/* Progress Bar */}
      <div style={{
        padding: '16px 20px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: '12px',
      }}>
        {steps.map((s, i) => (
          <React.Fragment key={i}>
            <div
              onClick={() => i <= step && setStep(i)}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                cursor: i <= step ? 'pointer' : 'default',
                opacity: i <= step ? 1 : 0.4,
              }}
            >
              <div style={{
                width: '24px', height: '24px', borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '12px', fontWeight: 600,
                background: i < step ? 'var(--accent)' : i === step ? 'rgba(0,255,204,0.2)' : 'var(--bg-elevated)',
                color: i < step ? 'var(--bg-primary)' : i === step ? 'var(--accent)' : 'var(--text-secondary)',
                border: i === step ? '2px solid var(--accent)' : '1px solid var(--border)',
              }}>
                {i < step ? '✓' : i + 1}
              </div>
              <span style={{
                fontSize: '11px', color: i === step ? 'var(--accent)' : 'var(--text-secondary)',
                display: i === step ? 'block' : 'none',
              }}>
                {s.title}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div style={{
                flex: 1, height: '1px',
                background: i < step ? 'var(--accent)' : 'var(--border)',
              }} />
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Step Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '24px 32px' }}>
        <h2 style={{ color: 'var(--accent)', margin: '0 0 4px 0', fontSize: '18px' }}>{steps[step].title}</h2>
        <p style={{ color: 'var(--text-secondary)', margin: '0 0 24px 0', fontSize: '13px' }}>{steps[step].description}</p>

        {/* Step 0: Locale */}
        {step === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '400px' }}>
            <SettingRow label="Sprache">
              <select value={settings.locale} onChange={e => update('locale', e.target.value)} style={selectStyle}>
                <option value="de-DE">🇩🇪 Deutsch</option>
                <option value="en-US">🇺🇸 English</option>
                <option value="fr-FR">🇫🇷 Français</option>
              </select>
            </SettingRow>
            <SettingRow label="Zeitzone">
              <select value={settings.timezone} onChange={e => update('timezone', e.target.value)} style={selectStyle}>
                <option value="Europe/Berlin">Europe/Berlin (CET)</option>
                <option value="Europe/London">Europe/London (GMT)</option>
                <option value="America/New_York">America/New_York (EST)</option>
                <option value="America/Los_Angeles">America/Los_Angeles (PST)</option>
                <option value="Asia/Tokyo">Asia/Tokyo (JST)</option>
              </select>
            </SettingRow>
            <SettingRow label="Hostname">
              <input
                type="text" value={settings.hostname}
                onChange={e => update('hostname', e.target.value)}
                style={inputStyle}
              />
            </SettingRow>
          </div>
        )}

        {/* Step 1: Theme */}
        {step === 1 && (
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
            gap: '12px',
          }}>
            {themes.map(theme => (
              <div
                key={theme.name}
                onClick={() => update('theme', theme.name)}
                style={{
                  padding: '16px', borderRadius: '8px', cursor: 'pointer',
                  background: settings.theme === theme.name ? 'rgba(0,255,204,0.1)' : 'var(--bg-surface)',
                  border: `2px solid ${settings.theme === theme.name ? 'var(--accent)' : 'var(--border)'}`,
                  transition: 'all 0.2s',
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: '4px' }}>{theme.display_name || theme.name}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{theme.description || ''}</div>
                {/* Color preview */}
                {theme.colors && (
                  <div style={{ display: 'flex', gap: '4px', marginTop: '8px' }}>
                    {Object.values(theme.colors).slice(0, 6).map((c, i) => (
                      <div key={i} style={{
                        width: '20px', height: '20px', borderRadius: '4px',
                        background: c, border: '1px solid rgba(255,255,255,0.1)',
                      }} />
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Step 2: AI Config */}
        {step === 2 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '500px' }}>
            <SettingRow label="Standard-Modell">
              <select value={settings.defaultModel} onChange={e => update('defaultModel', e.target.value)} style={selectStyle}>
                <option value="qwen2.5-7b-instruct">Qwen 2.5 — 7B (Allrounder, Deutsch)</option>
                <option value="llama3-8b-instruct">Llama 3 — 8B (Reasoning)</option>
                <option value="mistral-7b-instruct">Mistral — 7B (Kreativ, Long Context)</option>
                <option value="phi3-mini">Phi-3 Mini — 3.8B (Schnell, Leicht)</option>
                <option value="codestral-22b">Codestral — 22B (Code, GPU)</option>
              </select>
            </SettingRow>
            <SettingRow label="Auto Ghost-Swap">
              <Toggle value={settings.enableGhostSwap} onChange={v => update('enableGhostSwap', v)} />
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                Ghost wechselt automatisch das Modell je nach Aufgabe
              </span>
            </SettingRow>
          </div>
        )}

        {/* Step 3: System & Security */}
        {step === 3 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '500px' }}>
            <SettingRow label="Self-Healing">
              <Toggle value={settings.enableAutoHeal} onChange={v => update('enableAutoHeal', v)} />
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                System repariert sich automatisch bei Problemen
              </span>
            </SettingRow>
            <SettingRow label="Telemetrie (lokal)">
              <Toggle value={settings.enableTelemetry} onChange={v => update('enableTelemetry', v)} />
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                Hardware-Metriken sammeln (nur lokal, kein Cloud-Upload)
              </span>
            </SettingRow>
          </div>
        )}

        {/* Step 4: Summary */}
        {step === 4 && (
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px',
            maxWidth: '600px',
          }}>
            <SummaryCard icon="🌍" label="Sprache" value={settings.locale} />
            <SummaryCard icon="🕐" label="Zeitzone" value={settings.timezone} />
            <SummaryCard icon="🎨" label="Theme" value={settings.theme} />
            <SummaryCard icon="🖥️" label="Hostname" value={settings.hostname} />
            <SummaryCard icon="🧠" label="Standard-Modell" value={settings.defaultModel} />
            <SummaryCard icon="🔄" label="Ghost-Swap" value={settings.enableGhostSwap ? 'An' : 'Aus'} />
            <SummaryCard icon="🛡️" label="Self-Healing" value={settings.enableAutoHeal ? 'An' : 'Aus'} />
            <SummaryCard icon="📊" label="Telemetrie" value={settings.enableTelemetry ? 'An' : 'Aus'} />
          </div>
        )}
      </div>

      {/* Footer: Navigation */}
      <div style={{
        padding: '12px 20px', borderTop: '1px solid var(--border)',
        display: 'flex', justifyContent: 'space-between',
      }}>
        <button
          onClick={() => setStep(Math.max(0, step - 1))}
          disabled={step === 0}
          style={{
            padding: '8px 20px', borderRadius: 'var(--radius)',
            background: 'transparent', border: '1px solid var(--border)',
            color: step === 0 ? 'var(--text-secondary)' : 'var(--text-primary)',
            cursor: step === 0 ? 'default' : 'pointer', fontSize: '13px',
          }}
        >
          ← Zurück
        </button>

        {step < steps.length - 1 ? (
          <button
            onClick={() => setStep(step + 1)}
            style={{
              padding: '8px 24px', borderRadius: 'var(--radius)',
              background: 'rgba(0,255,204,0.15)', border: '1px solid var(--accent)',
              color: 'var(--accent)', cursor: 'pointer', fontSize: '13px', fontWeight: 600,
            }}
          >
            Weiter →
          </button>
        ) : (
          <button
            onClick={handleFinish}
            disabled={saving}
            style={{
              padding: '8px 24px', borderRadius: 'var(--radius)',
              background: saving ? 'var(--bg-elevated)' : 'var(--accent)',
              border: '1px solid var(--accent)',
              color: saving ? 'var(--text-secondary)' : 'var(--bg-primary)',
              cursor: saving ? 'wait' : 'pointer', fontSize: '13px', fontWeight: 600,
            }}
          >
            {saving ? '⏳ Speichere…' : '✅ Setup abschließen'}
          </button>
        )}
      </div>
    </div>
  )
}

// Hilfs-Komponenten
function SettingRow({ label, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>{label}</label>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>{children}</div>
    </div>
  )
}

function Toggle({ value, onChange }) {
  return (
    <div
      onClick={() => onChange(!value)}
      style={{
        width: '40px', height: '22px', borderRadius: '11px', cursor: 'pointer',
        background: value ? 'var(--accent)' : 'var(--bg-elevated)',
        border: `1px solid ${value ? 'var(--accent)' : 'var(--border)'}`,
        position: 'relative', transition: 'all 0.2s', flexShrink: 0,
      }}
    >
      <div style={{
        width: '16px', height: '16px', borderRadius: '50%',
        background: value ? 'var(--bg-primary)' : 'var(--text-secondary)',
        position: 'absolute', top: '2px',
        left: value ? '20px' : '2px',
        transition: 'left 0.2s',
      }} />
    </div>
  )
}

function SummaryCard({ icon, label, value }) {
  return (
    <div style={{
      padding: '12px', background: 'var(--bg-surface)',
      border: '1px solid var(--border)', borderRadius: '8px',
    }}>
      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>{icon} {label}</div>
      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{value}</div>
    </div>
  )
}

const selectStyle = {
  padding: '8px 12px', background: 'var(--bg-surface)',
  border: '1px solid var(--border)', borderRadius: 'var(--radius)',
  color: 'var(--text-primary)', fontSize: '13px', flex: 1,
}

const inputStyle = {
  padding: '8px 12px', background: 'var(--bg-surface)',
  border: '1px solid var(--border)', borderRadius: 'var(--radius)',
  color: 'var(--text-primary)', fontSize: '13px', fontFamily: 'var(--font-mono)', flex: 1,
}
