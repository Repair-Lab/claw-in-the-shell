import React, { useState, useEffect } from 'react'
import { api } from '../../api'
import AppSettingsPanel from '../AppSettingsPanel'
import { useAppSettings } from '../../hooks/useAppSettings'

export default function GhostBrowser({ windowId, extra, onOpenWindow }) {
  const { settings, schema, update: updateSetting } = useAppSettings('ghost-browser')
  const [tab, setTab] = useState(settings?.default_tab || 'tasks')
  const [presets, setPresets] = useState([])
  const [tasks, setTasks] = useState([])
  const [selectedTask, setSelectedTask] = useState(null)
  const [prompt, setPrompt] = useState('')
  const [targetUrl, setTargetUrl] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => { loadPresets(); loadTasks() }, [])

  async function loadPresets() {
    try {
      const res = await api.ghostBrowser.presets()
      setPresets(res.presets || [])
    } catch (e) { console.error(e) }
  }

  async function loadTasks() {
    try {
      const res = await api.ghostBrowser.listTasks(null, 50)
      setTasks(res.tasks || [])
    } catch (e) { console.error(e) }
  }

  async function createQuick() {
    if (!prompt.trim()) return alert('Bitte Prompt eingeben')
    setLoading(true)
    try {
      const res = await api.ghostBrowser.quick({ prompt, target_url: targetUrl, max_pages: settings?.max_pages || 10, max_duration_s: settings?.max_duration || 120, output_format: settings?.output_format || 'markdown' })
      // started in background
      loadTasks()
      setTab('tasks')
      alert('Task gestartet: ' + (res.task_id || ''))
    } catch (e) { alert('Fehler: ' + e.message) }
    setLoading(false)
  }

  async function runTask(taskId) {
    try {
      await api.ghostBrowser.runTask(taskId)
      loadTasks()
    } catch (e) { alert('Fehler: ' + e.message) }
  }

  async function cancelTask(taskId) {
    try {
      await api.ghostBrowser.cancelTask(taskId)
      loadTasks()
    } catch (e) { alert('Fehler: ' + e.message) }
  }

  async function deleteTask(taskId) {
    if (!confirm('Task wirklich löschen?')) return
    try {
      await api.ghostBrowser.deleteTask(taskId)
      setSelectedTask(null)
      loadTasks()
    } catch (e) { alert('Fehler: ' + e.message) }
  }

  async function showTaskDetails(taskId) {
    try {
      const t = await api.ghostBrowser.getTask(taskId)
      const s = await api.ghostBrowser.getSteps(taskId)
      setSelectedTask({ ...t, steps: s.steps || [] })
    } catch (e) { alert('Fehler: ' + e.message) }
  }

  function downloadResult(taskId) {
    window.open(`/api/ghost-browser/results/${taskId}`, '_blank')
  }

  return (
    <div style={{ padding: 14, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        {['tasks','presets','history','create'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{ padding: '6px 12px' }}>{t === 'tasks' ? 'Aufgaben' : t === 'presets' ? 'Presets' : t === 'create' ? 'Neuer Task' : 'History'}</button>
        ))}
        <div style={{ flex: 1 }} />
        <button onClick={loadTasks} style={{ padding: '6px 10px' }}>🔄 Aktualisieren</button>
      </div>

      <div style={{ flex: 1, overflow: 'auto', border: '1px solid var(--border)', borderRadius: 8, padding: 12, background: 'var(--bg-primary)' }}>
        {tab === 'presets' && (
          <div>
            {presets.map(p => (
              <div key={p.id} style={{ padding: 8, borderBottom: '1px solid var(--border)' }}>
                <div style={{ fontWeight: 700 }}>{p.icon} {p.name}</div>
                <div className="text-xs text-muted">{p.description}</div>
                <div style={{ marginTop: 8 }}>
                  <button onClick={() => { setPrompt(p.prompt_template); setTargetUrl(p.default_url); setTab('create') }} style={{ padding: '6px 10px' }}>Auswahl</button>
                </div>
              </div>
            ))}
            {presets.length === 0 && <div className="text-muted">Keine Presets</div>}
          </div>
        )}

        {tab === 'create' && (
          <div>
            <div style={{ marginBottom: 8 }}>
              <input placeholder="Ziel-URL (optional)" value={targetUrl} onChange={e => setTargetUrl(e.target.value)} style={{ width: '100%', padding: 8 }} />
            </div>
            <div style={{ marginBottom: 8 }}>
              <textarea placeholder="Prompt an Ghost" value={prompt} onChange={e => setPrompt(e.target.value)} style={{ width: '100%', height: 140, padding: 8 }} />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={createQuick} disabled={loading} style={{ padding: '8px 14px' }}>▶️ Quick starten</button>
              <button onClick={() => { setPrompt(''); setTargetUrl('') }} style={{ padding: '8px 14px' }}>Zurücksetzen</button>
            </div>
          </div>
        )}

        {tab === 'tasks' && (
          <div>
            {tasks.map(t => (
              <div key={t.id} style={{ padding: 10, borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700 }}>{t.task_type} · {t.status}</div>
                  <div className="text-xs text-muted">{t.prompt?.slice(0, 120)}</div>
                  <div className="text-xs text-muted">{new Date(t.created_at).toLocaleString('de-DE')}</div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => showTaskDetails(t.id)} style={{ padding: '6px 10px' }}>Details</button>
                  {t.status === 'queued' && <button onClick={() => runTask(t.id)} style={{ padding: '6px 10px' }}>Start</button>}
                  {t.status === 'running' && <button onClick={() => cancelTask(t.id)} style={{ padding: '6px 10px' }}>Abbrechen</button>}
                  {t.status === 'completed' && <button onClick={() => downloadResult(t.id)} style={{ padding: '6px 10px' }}>Herunterladen</button>}
                  <button onClick={() => deleteTask(t.id)} style={{ padding: '6px 10px' }}>🗑️</button>
                </div>
              </div>
            ))}
            {tasks.length === 0 && <div className="text-muted p-4">Keine Tasks</div>}
          </div>
        )}

        {selectedTask && (
          <div style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
            <h3>Task Details</h3>
            <div><strong>Status:</strong> {selectedTask.status}</div>
            <div style={{ marginTop: 8 }}><strong>Prompt:</strong><div className="text-xs text-muted">{selectedTask.prompt}</div></div>
            <div style={{ marginTop: 8 }}><strong>Steps:</strong></div>
            <div>
              {selectedTask.steps.map((s, i) => (
                <div key={s.id} style={{ padding: 6, borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 40 }}>{s.step_number}</div>
                  <div style={{ flex: 1 }}>{s.action} {s.selector ? `@${s.selector}` : ''}</div>
                  {s.screenshot_path && (
                    <img src={api.ghostBrowser.screenshotUrl(selectedTask.id, s.step_number)} alt="ss" style={{ width: 120, height: 80, objectFit: 'cover', borderRadius: 6 }} />
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
