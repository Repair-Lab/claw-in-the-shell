import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api'

/**
 * SQLExplorer — Datenbank als Dateisystem-Browser
 * 
 * Zeigt PostgreSQL-Schemas/Tabellen/Zeilen als Ordner-Hierarchie.
 * Ermöglicht inline Editing, Erstellen, Löschen mit Admin-Bestätigung.
 */
export default function SQLExplorer({ windowId }) {
  const [schemas, setSchemas] = useState([])
  const [currentPath, setCurrentPath] = useState([]) // ["schema", "table", "row_id"]
  const [items, setItems] = useState([])
  const [columns, setColumns] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingRow, setEditingRow] = useState(null)
  const [editValues, setEditValues] = useState({})
  const [confirmAction, setConfirmAction] = useState(null)
  const [newRowMode, setNewRowMode] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [tableStats, setTableStats] = useState(null)

  // ── Schemas laden ──
  const loadSchemas = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.sqlExplorerSchemas()
      setSchemas(data || [])
      setItems(data || [])
    } catch (err) {
      console.error('Schemas laden:', err)
      setSchemas([])
      setItems([])
    }
    setLoading(false)
  }, [])

  // ── Tabellen eines Schemas laden ──
  const loadTables = useCallback(async (schemaName) => {
    setLoading(true)
    try {
      const data = await api.sqlExplorerTables(schemaName)
      setItems(data || [])
      setColumns([])
      setTableStats(null)
    } catch (err) {
      console.error('Tabellen laden:', err)
      setItems([])
    }
    setLoading(false)
  }, [])

  // ── Zeilen einer Tabelle laden ──
  const loadRows = useCallback(async (schemaName, tableName) => {
    setLoading(true)
    try {
      const data = await api.sqlExplorerRows(schemaName, tableName)
      setItems(data.rows || [])
      setColumns(data.columns || [])
      setTableStats(data.stats || null)
    } catch (err) {
      console.error('Zeilen laden:', err)
      setItems([])
      setColumns([])
    }
    setLoading(false)
  }, [])

  // ── Initial laden ──
  useEffect(() => { loadSchemas() }, [loadSchemas])

  // ── Navigation ──
  const navigate = useCallback((level, name) => {
    setEditingRow(null)
    setNewRowMode(false)
    setSearchQuery('')

    if (level === 0) {
      // Root → Schemas
      setCurrentPath([])
      loadSchemas()
    } else if (level === 1) {
      // Schema → Tabellen
      setCurrentPath([name])
      loadTables(name)
    } else if (level === 2) {
      // Tabelle → Zeilen
      const schema = currentPath[0]
      setCurrentPath([schema, name])
      loadRows(schema, name)
    }
  }, [currentPath, loadSchemas, loadTables, loadRows])

  // ── Breadcrumb-Navigation ──
  const navigateTo = useCallback((pathIndex) => {
    if (pathIndex < 0) {
      navigate(0)
    } else if (pathIndex === 0) {
      navigate(1, currentPath[0])
    } else if (pathIndex === 1) {
      navigate(2, currentPath[1])
    }
  }, [currentPath, navigate])

  // ── Zeile bearbeiten ──
  const startEdit = (row) => {
    setEditingRow(row)
    setEditValues({ ...row })
  }

  const cancelEdit = () => {
    setEditingRow(null)
    setEditValues({})
    setNewRowMode(false)
  }

  const saveEdit = () => {
    if (!editingRow && !newRowMode) return
    setConfirmAction({
      type: newRowMode ? 'create' : 'update',
      schema: currentPath[0],
      table: currentPath[1],
      data: editValues,
      originalRow: editingRow,
      message: newRowMode
        ? `Neuen Eintrag in ${currentPath[0]}.${currentPath[1]} erstellen?`
        : `Eintrag in ${currentPath[0]}.${currentPath[1]} aktualisieren?`,
    })
  }

  const deleteRow = (row) => {
    setConfirmAction({
      type: 'delete',
      schema: currentPath[0],
      table: currentPath[1],
      data: row,
      message: `Eintrag aus ${currentPath[0]}.${currentPath[1]} wirklich löschen?`,
    })
  }

  const executeAction = async () => {
    if (!confirmAction) return
    const { type, schema, table, data, originalRow } = confirmAction
    try {
      if (type === 'update') {
        await api.sqlExplorerUpdate(schema, table, data)
      } else if (type === 'create') {
        await api.sqlExplorerInsert(schema, table, data)
      } else if (type === 'delete') {
        await api.sqlExplorerDelete(schema, table, data)
      }
      setConfirmAction(null)
      setEditingRow(null)
      setNewRowMode(false)
      setEditValues({})
      loadRows(schema, table)
    } catch (err) {
      alert('Aktion fehlgeschlagen: ' + err.message)
    }
  }

  const startNewRow = () => {
    const emptyRow = {}
    columns.forEach(col => { emptyRow[col.name] = '' })
    setNewRowMode(true)
    setEditingRow(null)
    setEditValues(emptyRow)
  }

  // ── Gefilterte Items ──
  const filteredItems = items.filter(item => {
    if (!searchQuery) return true
    const q = searchQuery.toLowerCase()
    return JSON.stringify(item).toLowerCase().includes(q)
  })

  // Welche Ebene?
  const level = currentPath.length // 0=schemas, 1=tables, 2=rows

  return (
    <div style={sx.container}>
      {/* Toolbar */}
      <div style={sx.toolbar}>
        {/* Breadcrumb */}
        <div style={sx.breadcrumb}>
          <span style={sx.breadcrumbItem} onClick={() => navigate(0)}>🗄️ dbai</span>
          {currentPath.map((p, i) => (
            <React.Fragment key={i}>
              <span style={sx.breadcrumbSep}>/</span>
              <span
                style={{ ...sx.breadcrumbItem, color: i === currentPath.length - 1 ? 'var(--accent)' : undefined }}
                onClick={() => navigateTo(i)}
              >
                {i === 0 ? '📁' : '📋'} {p}
              </span>
            </React.Fragment>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        {/* Suche */}
        <input
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          placeholder="🔍 Suche..."
          style={sx.searchInput}
        />

        {/* Aktionen */}
        {level === 2 && (
          <button onClick={startNewRow} style={sx.btnPrimary}>➕ Neuer Eintrag</button>
        )}
        <button onClick={() => level === 0 ? loadSchemas() : level === 1 ? loadTables(currentPath[0]) : loadRows(currentPath[0], currentPath[1])} style={sx.btnSecondary}>
          🔄
        </button>
      </div>

      {/* Table Stats */}
      {level === 2 && tableStats && (
        <div style={sx.statsBar}>
          <span>📋 {tableStats.row_count} Zeilen</span>
          <span>📊 {columns.length} Spalten</span>
          {tableStats.size && <span>💾 {tableStats.size}</span>}
          {tableStats.has_pk && <span>🔑 PK: {tableStats.pk_columns?.join(', ')}</span>}
        </div>
      )}

      {/* Content */}
      <div style={sx.content}>
        {loading ? (
          <div style={sx.loading}>⏳ Lade...</div>
        ) : (
          <>
            {/* Level 0: Schemas als Ordner */}
            {level === 0 && (
              <div style={sx.fileGrid}>
                {filteredItems.map((schema, i) => (
                  <div key={i} style={sx.fileItem} onDoubleClick={() => navigate(1, schema.schema_name)}>
                    <span style={sx.fileIcon}>📁</span>
                    <span style={sx.fileName}>{schema.schema_name}</span>
                    <span style={sx.fileMeta}>{schema.table_count} Tabellen</span>
                  </div>
                ))}
                {filteredItems.length === 0 && <div style={sx.empty}>Keine Schemas gefunden</div>}
              </div>
            )}

            {/* Level 1: Tabellen als Ordner */}
            {level === 1 && (
              <div style={sx.fileGrid}>
                {/* Back */}
                <div style={sx.fileItem} onDoubleClick={() => navigate(0)}>
                  <span style={sx.fileIcon}>⬆️</span>
                  <span style={sx.fileName}>..</span>
                  <span style={sx.fileMeta}>zurück</span>
                </div>
                {filteredItems.map((table, i) => (
                  <div key={i} style={sx.fileItem} onDoubleClick={() => navigate(2, table.table_name)}>
                    <span style={sx.fileIcon}>
                      {table.table_type === 'VIEW' ? '👁️' : '📋'}
                    </span>
                    <span style={sx.fileName}>{table.table_name}</span>
                    <span style={sx.fileMeta}>
                      {table.table_type === 'VIEW' ? 'View' : `~${table.row_estimate} Zeilen`}
                      {table.size && ` · ${table.size}`}
                    </span>
                  </div>
                ))}
                {filteredItems.length === 0 && <div style={sx.empty}>Keine Tabellen in diesem Schema</div>}
              </div>
            )}

            {/* Level 2: Zeilen als Tabelle */}
            {level === 2 && (
              <div style={sx.tableContainer}>
                {/* New Row Form */}
                {newRowMode && (
                  <div style={sx.editPanel}>
                    <h4 style={sx.editTitle}>➕ Neuer Eintrag</h4>
                    <div style={sx.editFields}>
                      {columns.map(col => (
                        <div key={col.name} style={sx.editField}>
                          <label style={sx.editLabel}>
                            {col.name}
                            <span style={sx.editType}>{col.data_type}</span>
                            {col.is_nullable === 'NO' && <span style={sx.editRequired}>*</span>}
                          </label>
                          <input
                            value={editValues[col.name] ?? ''}
                            onChange={e => setEditValues(prev => ({ ...prev, [col.name]: e.target.value }))}
                            style={sx.editInput}
                            placeholder={col.column_default || ''}
                          />
                        </div>
                      ))}
                    </div>
                    <div style={sx.editActions}>
                      <button onClick={cancelEdit} style={sx.btnSecondary}>Abbrechen</button>
                      <button onClick={saveEdit} style={sx.btnPrimary}>✅ Erstellen</button>
                    </div>
                  </div>
                )}

                {/* Data Table */}
                <table style={sx.table}>
                  <thead>
                    <tr>
                      <th style={sx.thAction}></th>
                      {columns.map(col => (
                        <th key={col.name} style={sx.th}>
                          <div>{col.name}</div>
                          <div style={sx.thType}>{col.data_type}</div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItems.map((row, ri) => {
                      const isEditing = editingRow && JSON.stringify(editingRow) === JSON.stringify(row)
                      return (
                        <tr key={ri} style={{ borderBottom: '1px solid var(--border)', background: isEditing ? 'rgba(0,255,204,0.03)' : 'transparent' }}>
                          <td style={sx.tdAction}>
                            {isEditing ? (
                              <div style={{ display: 'flex', gap: '4px' }}>
                                <button onClick={saveEdit} style={sx.microBtn} title="Speichern">✅</button>
                                <button onClick={cancelEdit} style={sx.microBtn} title="Abbrechen">❌</button>
                              </div>
                            ) : (
                              <div style={{ display: 'flex', gap: '4px' }}>
                                <button onClick={() => startEdit(row)} style={sx.microBtn} title="Bearbeiten">✏️</button>
                                <button onClick={() => deleteRow(row)} style={sx.microBtnDanger} title="Löschen">🗑️</button>
                              </div>
                            )}
                          </td>
                          {columns.map(col => (
                            <td key={col.name} style={sx.td}>
                              {isEditing ? (
                                <input
                                  value={editValues[col.name] ?? ''}
                                  onChange={e => setEditValues(prev => ({ ...prev, [col.name]: e.target.value }))}
                                  style={sx.cellInput}
                                />
                              ) : (
                                <CellValue value={row[col.name]} type={col.data_type} />
                              )}
                            </td>
                          ))}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                {filteredItems.length === 0 && (
                  <div style={sx.empty}>Keine Daten in dieser Tabelle</div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Confirmation Dialog */}
      {confirmAction && (
        <div style={sx.confirmOverlay}>
          <div style={sx.confirmDialog}>
            <div style={sx.confirmIcon}>
              {confirmAction.type === 'delete' ? '⚠️' : confirmAction.type === 'create' ? '➕' : '✏️'}
            </div>
            <h3 style={sx.confirmTitle}>Admin-Bestätigung erforderlich</h3>
            <p style={sx.confirmMessage}>{confirmAction.message}</p>

            {/* Preview of changes */}
            <div style={sx.confirmPreview}>
              {confirmAction.type === 'delete' ? (
                <div style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', maxHeight: '150px', overflow: 'auto' }}>
                  {Object.entries(confirmAction.data).slice(0, 5).map(([k, v]) => (
                    <div key={k}><span style={{ color: 'var(--danger)' }}>{k}:</span> {String(v ?? 'NULL').slice(0, 80)}</div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', maxHeight: '150px', overflow: 'auto' }}>
                  {Object.entries(confirmAction.data).filter(([,v]) => v !== '' && v != null).slice(0, 8).map(([k, v]) => (
                    <div key={k}><span style={{ color: 'var(--accent)' }}>{k}:</span> {String(v).slice(0, 80)}</div>
                  ))}
                </div>
              )}
            </div>

            <div style={sx.confirmActions}>
              <button onClick={() => setConfirmAction(null)} style={sx.btnSecondary}>Abbrechen</button>
              <button onClick={executeAction} style={confirmAction.type === 'delete' ? sx.btnDanger : sx.btnPrimary}>
                {confirmAction.type === 'delete' ? '🗑️ Löschen bestätigen' :
                 confirmAction.type === 'create' ? '➕ Erstellen bestätigen' : '✅ Änderung bestätigen'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Cell Value Renderer ──
function CellValue({ value, type }) {
  if (value === null || value === undefined) {
    return <span style={{ color: 'var(--text-secondary)', fontStyle: 'italic', fontSize: '11px' }}>NULL</span>
  }

  if (typeof value === 'boolean') {
    return <span style={{ color: value ? 'var(--success)' : 'var(--danger)' }}>{value ? '✅' : '❌'}</span>
  }

  if (typeof value === 'object') {
    return (
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--warning)' }} title={JSON.stringify(value, null, 2)}>
        {JSON.stringify(value).slice(0, 60)}{JSON.stringify(value).length > 60 ? '…' : ''}
      </span>
    )
  }

  const str = String(value)

  // UUID
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(str)) {
    return <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--info)' }}>{str.slice(0, 8)}…</span>
  }

  // Timestamp
  if (type?.includes('timestamp') || (str.includes('T') && str.includes('-') && str.length > 20)) {
    try {
      return <span style={{ fontSize: '11px' }}>{new Date(str).toLocaleString('de-DE')}</span>
    } catch {
      // fallthrough
    }
  }

  // Number
  if (type?.includes('int') || type?.includes('numeric') || type?.includes('float')) {
    return <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>{str}</span>
  }

  return <span style={{ fontSize: '12px' }} title={str.length > 80 ? str : undefined}>{str.slice(0, 80)}{str.length > 80 ? '…' : ''}</span>
}

// ═══ STYLES ═══
const sx = {
  container: { display: 'flex', flexDirection: 'column', height: '100%', fontFamily: 'var(--font-sans)', fontSize: '13px' },

  toolbar: {
    display: 'flex', alignItems: 'center', gap: '10px',
    padding: '10px 14px', borderBottom: '1px solid var(--border)',
    background: 'var(--bg-secondary)', flexWrap: 'wrap',
  },
  breadcrumb: { display: 'flex', alignItems: 'center', gap: '4px', fontSize: '13px' },
  breadcrumbItem: { cursor: 'pointer', color: 'var(--text-primary)', padding: '2px 4px', borderRadius: '4px' },
  breadcrumbSep: { color: 'var(--text-secondary)', fontSize: '12px' },
  searchInput: {
    padding: '6px 12px', width: '180px',
    background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius)', color: 'var(--text-primary)',
    fontSize: '12px', fontFamily: 'var(--font-mono)', outline: 'none',
  },
  btnPrimary: {
    padding: '6px 14px', background: 'rgba(0,255,204,0.1)',
    border: '1px solid var(--accent)', borderRadius: 'var(--radius)',
    color: 'var(--accent)', cursor: 'pointer', fontSize: '11px', fontWeight: 600,
  },
  btnSecondary: {
    padding: '6px 14px', background: 'transparent',
    border: '1px solid var(--border)', borderRadius: 'var(--radius)',
    color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '11px',
  },
  btnDanger: {
    padding: '6px 14px', background: 'rgba(255,68,68,0.1)',
    border: '1px solid var(--danger)', borderRadius: 'var(--radius)',
    color: 'var(--danger)', cursor: 'pointer', fontSize: '11px', fontWeight: 600,
  },

  statsBar: {
    display: 'flex', gap: '16px', padding: '6px 14px',
    borderBottom: '1px solid var(--border)', fontSize: '11px',
    color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)',
    background: 'var(--bg-secondary)',
  },

  content: { flex: 1, overflow: 'auto' },
  loading: { display: 'flex', justifyContent: 'center', padding: '40px', color: 'var(--text-secondary)' },
  empty: { textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' },

  // File Grid (Schemas + Tables)
  fileGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '8px', padding: '16px' },
  fileItem: {
    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px',
    padding: '16px 12px', cursor: 'pointer', borderRadius: '8px',
    background: 'var(--bg-surface)', border: '1px solid var(--border)',
    transition: 'all 0.15s', textAlign: 'center',
  },
  fileIcon: { fontSize: '32px' },
  fileName: { fontSize: '12px', fontWeight: 600, wordBreak: 'break-all' },
  fileMeta: { fontSize: '10px', color: 'var(--text-secondary)' },

  // Data Table
  tableContainer: { overflow: 'auto' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '12px' },
  th: {
    padding: '8px 10px', textAlign: 'left', position: 'sticky', top: 0,
    background: 'var(--bg-secondary)', borderBottom: '2px solid var(--border)',
    fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--accent)',
    fontWeight: 600,
  },
  thType: { fontSize: '9px', color: 'var(--text-secondary)', fontWeight: 400 },
  thAction: { width: '60px', padding: '8px', position: 'sticky', top: 0, background: 'var(--bg-secondary)', borderBottom: '2px solid var(--border)' },
  td: {
    padding: '6px 10px', maxWidth: '250px', overflow: 'hidden',
    textOverflow: 'ellipsis', whiteSpace: 'nowrap', verticalAlign: 'top',
  },
  tdAction: { padding: '4px 8px', verticalAlign: 'middle' },
  cellInput: {
    width: '100%', padding: '4px 6px', fontSize: '12px',
    background: 'var(--bg-elevated)', border: '1px solid var(--accent)',
    borderRadius: '4px', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)',
    outline: 'none',
  },
  microBtn: {
    width: '24px', height: '24px', border: '1px solid var(--border)',
    borderRadius: '4px', background: 'var(--bg-elevated)', cursor: 'pointer',
    fontSize: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  microBtnDanger: {
    width: '24px', height: '24px', border: '1px solid var(--danger)',
    borderRadius: '4px', background: 'rgba(255,68,68,0.05)', cursor: 'pointer',
    fontSize: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center',
  },

  // Edit Panel
  editPanel: {
    margin: '12px 16px', padding: '16px', background: 'var(--bg-surface)',
    border: '1px solid var(--accent)', borderRadius: '8px',
  },
  editTitle: { margin: '0 0 12px', fontSize: '14px', color: 'var(--accent)' },
  editFields: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '10px' },
  editField: { display: 'flex', flexDirection: 'column', gap: '4px' },
  editLabel: { fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' },
  editType: { fontWeight: 400, marginLeft: '6px', color: 'var(--text-secondary)', fontSize: '10px' },
  editRequired: { color: 'var(--danger)', marginLeft: '2px' },
  editInput: {
    padding: '6px 10px', background: 'var(--bg-elevated)',
    border: '1px solid var(--border)', borderRadius: 'var(--radius)',
    color: 'var(--text-primary)', fontSize: '12px', fontFamily: 'var(--font-mono)', outline: 'none',
  },
  editActions: { display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '12px' },

  // Confirmation Dialog
  confirmOverlay: {
    position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.6)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
  },
  confirmDialog: {
    background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: '12px', padding: '24px', maxWidth: '450px', width: '90%',
    boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
  },
  confirmIcon: { fontSize: '32px', textAlign: 'center', marginBottom: '12px' },
  confirmTitle: { fontSize: '16px', textAlign: 'center', margin: '0 0 8px', color: 'var(--text-primary)' },
  confirmMessage: { fontSize: '13px', textAlign: 'center', color: 'var(--text-secondary)', margin: '0 0 16px' },
  confirmPreview: {
    padding: '12px', background: 'var(--bg-primary)', borderRadius: '8px',
    border: '1px solid var(--border)', marginBottom: '16px',
  },
  confirmActions: { display: 'flex', gap: '8px', justifyContent: 'flex-end' },
}
