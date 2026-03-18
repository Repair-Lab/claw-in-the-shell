import React, { useState, useMemo } from 'react'

/**
 * AppSettingsPanel — generisches Settings-UI, gerendert aus JSON-Schema
 * 
 * Props:
 *   schema    — { key: { type, label, group, description, options, min, max, step, unit, default } }
 *   settings  — { key: value }  (aktuelle Werte)
 *   onUpdate  — (key, value) => void
 *   onReset   — () => void
 */
export default function AppSettingsPanel({ schema, settings, onUpdate, onReset, title }) {
  const [activeGroup, setActiveGroup] = useState(null)

  // Gruppiere Settings nach group-Feld
  const groups = useMemo(() => {
    if (!schema) return {}
    const g = {}
    for (const [key, def] of Object.entries(schema)) {
      const group = def.group || 'Allgemein'
      if (!g[group]) g[group] = []
      g[group].push({ key, ...def })
    }
    return g
  }, [schema])

  const groupNames = Object.keys(groups)

  if (!schema || Object.keys(schema).length === 0) {
    return (
      <div style={{ padding: '20px', color: 'var(--text-secondary)', textAlign: 'center' }}>
        Keine Einstellungen verfügbar
      </div>
    )
  }

  // Default: erste Gruppe
  const currentGroup = activeGroup || groupNames[0]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '12px' }}>
      {/* Header */}
      {title && (
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '0 0 12px 0', borderBottom: '1px solid var(--border)',
        }}>
          <h3 style={{ margin: 0, fontSize: '14px', color: 'var(--accent)' }}>
            ⚙️ {title}
          </h3>
          {onReset && (
            <button onClick={onReset} style={resetBtnStyle}>
              ↻ Zurücksetzen
            </button>
          )}
        </div>
      )}

      <div style={{ display: 'flex', gap: '12px', flex: 1, minHeight: 0 }}>
        {/* Gruppen-Sidebar (nur wenn >1 Gruppe) */}
        {groupNames.length > 1 && (
          <div style={{
            minWidth: '140px', maxWidth: '180px', overflow: 'auto',
            borderRight: '1px solid var(--border)', paddingRight: '12px',
          }}>
            {groupNames.map(name => (
              <button
                key={name}
                onClick={() => setActiveGroup(name)}
                style={{
                  display: 'block', width: '100%', textAlign: 'left',
                  padding: '8px 12px', marginBottom: '2px',
                  borderRadius: 'var(--radius)', border: 'none',
                  background: currentGroup === name ? 'rgba(0,255,204,0.1)' : 'transparent',
                  color: currentGroup === name ? 'var(--accent)' : 'var(--text-secondary)',
                  cursor: 'pointer', fontSize: '12px',
                  transition: 'all 0.15s',
                }}
              >
                {name}
              </button>
            ))}
          </div>
        )}

        {/* Settings-Liste */}
        <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {(groups[currentGroup] || []).map(def => (
            <SettingRow
              key={def.key}
              def={def}
              value={settings?.[def.key]}
              onChange={(val) => onUpdate(def.key, val)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

/** Einzelne Setting-Zeile */
function SettingRow({ def, value, onChange }) {
  const currentVal = value !== undefined ? value : def.default

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '12px',
      padding: '8px 12px', borderRadius: 'var(--radius)',
      background: 'rgba(255,255,255,0.02)',
      minHeight: '40px',
    }}>
      {/* Label + Description */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>
          {def.label}
        </div>
        {def.description && (
          <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '1px' }}>
            {def.description}
          </div>
        )}
      </div>

      {/* Input */}
      <div style={{ flexShrink: 0, minWidth: '140px', textAlign: 'right' }}>
        {def.type === 'boolean' && (
          <Toggle checked={!!currentVal} onChange={onChange} />
        )}
        {def.type === 'select' && (
          <SelectInput options={def.options || []} value={currentVal} onChange={onChange} />
        )}
        {def.type === 'number' && (
          <NumberInput
            value={currentVal}
            onChange={onChange}
            min={def.min}
            max={def.max}
            step={def.step}
            unit={def.unit}
          />
        )}
        {def.type === 'string' && (
          <TextInput value={currentVal || ''} onChange={onChange} />
        )}
        {def.type === 'color' && (
          <input
            type="color"
            value={currentVal || '#000000'}
            onChange={e => onChange(e.target.value)}
            style={{ width: '40px', height: '28px', border: 'none', cursor: 'pointer', background: 'transparent' }}
          />
        )}
      </div>
    </div>
  )
}

/** Toggle-Switch (boolean) */
function Toggle({ checked, onChange }) {
  return (
    <div
      onClick={() => onChange(!checked)}
      style={{
        width: '44px', height: '24px', borderRadius: '12px',
        background: checked ? 'var(--accent)' : 'var(--border)',
        cursor: 'pointer', position: 'relative',
        transition: 'background 0.2s',
      }}
    >
      <div style={{
        width: '18px', height: '18px', borderRadius: '50%',
        background: '#fff', position: 'absolute', top: '3px',
        left: checked ? '23px' : '3px',
        transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
      }} />
    </div>
  )
}

/** Select-Dropdown */
function SelectInput({ options, value, onChange }) {
  return (
    <select
      value={value ?? ''}
      onChange={e => {
        let val = e.target.value
        // Parse numeric values
        const numVal = Number(val)
        if (!isNaN(numVal) && val !== '' && typeof options[0]?.value === 'number') {
          val = numVal
        }
        onChange(val)
      }}
      style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius)', color: 'var(--text-primary)',
        padding: '4px 8px', fontSize: '12px', minWidth: '120px',
        outline: 'none', cursor: 'pointer',
      }}
    >
      {options.map(opt => (
        <option key={String(opt.value)} value={opt.value}>{opt.label}</option>
      ))}
    </select>
  )
}

/** Number-Input mit Slider */
function NumberInput({ value, onChange, min, max, step, unit }) {
  const numVal = Number(value) || min || 0
  const hasRange = min !== undefined && max !== undefined

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      {hasRange && (
        <input
          type="range"
          min={min}
          max={max}
          step={step || 1}
          value={numVal}
          onChange={e => onChange(Number(e.target.value))}
          style={{ width: '80px', accentColor: 'var(--accent)' }}
        />
      )}
      <input
        type="number"
        value={numVal}
        min={min}
        max={max}
        step={step || 1}
        onChange={e => onChange(Number(e.target.value))}
        style={{
          width: '60px', background: 'var(--bg-surface)',
          border: '1px solid var(--border)', borderRadius: 'var(--radius)',
          color: 'var(--text-primary)', padding: '4px 6px',
          fontSize: '12px', textAlign: 'right', outline: 'none',
          fontFamily: 'var(--font-mono)',
        }}
      />
      {unit && <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{unit}</span>}
    </div>
  )
}

/** Text-Input */
function TextInput({ value, onChange }) {
  const [local, setLocal] = useState(value)

  return (
    <input
      type="text"
      value={local}
      onChange={e => setLocal(e.target.value)}
      onBlur={() => onChange(local)}
      onKeyDown={e => { if (e.key === 'Enter') onChange(local) }}
      style={{
        width: '100%', maxWidth: '200px',
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        color: 'var(--text-primary)',
        padding: '4px 8px', fontSize: '12px', outline: 'none',
      }}
    />
  )
}

const resetBtnStyle = {
  padding: '4px 12px', fontSize: '11px',
  background: 'transparent', border: '1px solid var(--border)',
  borderRadius: 'var(--radius)', color: 'var(--text-secondary)',
  cursor: 'pointer',
}
