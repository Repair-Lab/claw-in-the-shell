import React, { useState, useEffect } from 'react'
import { api } from '../../api'
import { useAppSettings } from '../../hooks/useAppSettings'
import AppSettingsPanel from '../AppSettingsPanel'

/**
 * FileBrowser — Durchsucht die Objekt-Registry (dbai_core.objects)
 * Dateien sind UUIDs, keine Pfade.
 */
export default function FileBrowser({ windowId }) {
  const { settings, schema: settingsSchema, update: updateSetting, reset: resetSettings } = useAppSettings('file-browser')
  const [showSettings, setShowSettings] = useState(false)
  const [objects, setObjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [schema, setSchema] = useState('all')
  const [schemas, setSchemas] = useState([])

  useEffect(() => {
    loadObjects()
    loadSchemas()
  }, [])

  const loadSchemas = async () => {
    try {
      const result = await api.sqlQuery(
        "SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'dbai_%' ORDER BY schema_name"
      )
      setSchemas(result.rows || [])
    } catch {}
  }

  const loadObjects = async () => {
    setLoading(true)
    try {
      const query = schema === 'all'
        ? "SELECT table_schema, table_name, table_type FROM information_schema.tables WHERE table_schema LIKE 'dbai_%' ORDER BY table_schema, table_name"
        : `SELECT table_schema, table_name, table_type FROM information_schema.tables WHERE table_schema = '${schema}' ORDER BY table_name`
      const result = await api.sqlQuery(query)
      setObjects(result.rows || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadObjects() }, [schema])

  const filtered = search
    ? objects.filter(o => o.table_name.toLowerCase().includes(search.toLowerCase()))
    : objects

  const [selectedTable, setSelectedTable] = useState(null)
  const [tableData, setTableData] = useState(null)
  const [tableLoading, setTableLoading] = useState(false)

  const inspectTable = async (schema, name) => {
    setSelectedTable(`${schema}.${name}`)
    setTableLoading(true)
    try {
      const result = await api.sqlQuery(`SELECT * FROM ${schema}.${name} LIMIT ${settings?.rows_per_page ?? 50}`)
      setTableData(result)
    } catch (err) {
      setTableData({ error: err.message })
    } finally {
      setTableLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', height: '100%', fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
      {showSettings ? (
        <div style={{ padding: '16px', width: '100%' }}>
          <button onClick={() => setShowSettings(false)} style={{ marginBottom: '12px', padding: '4px 12px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 'var(--radius)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '11px' }}>← Zurück</button>
          <AppSettingsPanel schema={settingsSchema} settings={settings} onUpdate={updateSetting} onReset={resetSettings} title="Datei-Browser" />
        </div>
      ) : (
      <>
      {/* Sidebar */}
      <div style={{
        width: '280px', borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', overflow: 'hidden'
      }}>
        {/* Search */}
        <div style={{ padding: '8px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', gap: '4px' }}>
          <input
            type="text" placeholder="🔍 Tabelle suchen..."
            value={search} onChange={e => setSearch(e.target.value)}
            style={{
              flex: 1, padding: '6px 8px', background: 'var(--bg-primary)',
              border: '1px solid var(--border)', borderRadius: '4px',
              color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontSize: '11px'
            }}
          />
          <button onClick={() => setShowSettings(true)} style={{ padding: '4px 8px', background: 'transparent', border: '1px solid var(--border)', borderRadius: '4px', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '11px' }}>⚙️</button>
          </div>
          <select
            value={schema} onChange={e => setSchema(e.target.value)}
            style={{
              width: '100%', marginTop: '4px', padding: '4px',
              background: 'var(--bg-primary)', border: '1px solid var(--border)',
              borderRadius: '4px', color: 'var(--text-primary)', fontSize: '11px'
            }}
          >
            <option value="all">Alle Schemas</option>
            {schemas.map(s => (
              <option key={s.schema_name} value={s.schema_name}>{s.schema_name}</option>
            ))}
          </select>
        </div>

        {/* Object list */}
        <div style={{ flex: 1, overflow: 'auto', padding: '4px' }}>
          {loading && <div style={{ padding: '12px', color: 'var(--text-secondary)' }}>Lade...</div>}
          {error && <div style={{ padding: '12px', color: 'var(--danger)' }}>{error}</div>}
          {filtered.map((obj, i) => (
            <div
              key={i}
              onClick={() => inspectTable(obj.table_schema, obj.table_name)}
              style={{
                padding: '4px 8px', cursor: 'pointer', borderRadius: '4px',
                background: selectedTable === `${obj.table_schema}.${obj.table_name}` ? 'var(--bg-elevated)' : 'transparent',
                display: 'flex', gap: '6px', alignItems: 'center'
              }}
            >
              <span style={{ color: obj.table_type === 'VIEW' ? 'var(--info)' : 'var(--accent)', fontSize: '10px' }}>
                {obj.table_type === 'VIEW' ? '👁' : '📋'}
              </span>
              <span style={{ color: 'var(--text-secondary)', fontSize: '10px' }}>{obj.table_schema}.</span>
              <span>{obj.table_name}</span>
            </div>
          ))}
          <div style={{ padding: '8px', color: 'var(--text-secondary)', fontSize: '10px' }}>
            {filtered.length} Objekte
          </div>
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '8px' }}>
        {!selectedTable && (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            <div style={{ fontSize: '48px', marginBottom: '12px' }}>📁</div>
            <div>Wähle eine Tabelle aus der Sidebar</div>
            <div style={{ fontSize: '10px', marginTop: '8px' }}>Doppelklick zum Inspizieren</div>
          </div>
        )}
        {selectedTable && tableLoading && (
          <div style={{ padding: '12px', color: 'var(--text-secondary)' }}>Lade {selectedTable}...</div>
        )}
        {selectedTable && tableData && !tableLoading && (
          <>
            <div style={{ marginBottom: '8px', color: 'var(--accent)', fontWeight: 600 }}>
              {selectedTable} — {tableData.rows?.length || 0} Zeilen (max {settings?.rows_per_page ?? 50})
            </div>
            {tableData.error ? (
              <div style={{ color: 'var(--danger)' }}>{tableData.error}</div>
            ) : tableData.rows?.length > 0 ? (
              <div style={{ overflow: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      {tableData.columns.map(col => (
                        <th key={col} style={{
                          padding: '4px 8px', textAlign: 'left',
                          borderBottom: '1px solid var(--border)',
                          color: 'var(--accent)', fontSize: '10px',
                          textTransform: 'uppercase', whiteSpace: 'nowrap'
                        }}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tableData.rows.map((row, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                        {tableData.columns.map(col => (
                          <td key={col} style={{
                            padding: '3px 8px', fontSize: '11px',
                            maxWidth: '200px', overflow: 'hidden',
                            textOverflow: 'ellipsis', whiteSpace: 'nowrap'
                          }}>
                            {typeof row[col] === 'object' ? JSON.stringify(row[col]) : String(row[col] ?? '')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ color: 'var(--text-secondary)' }}>Keine Daten</div>
            )}
          </>
        )}
      </div>
      </>
      )}
    </div>
  )
}
