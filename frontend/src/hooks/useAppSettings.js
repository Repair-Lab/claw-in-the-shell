import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../api'

/**
 * useAppSettings — Custom Hook für Per-App Settings
 * 
 * Lädt Settings + Schema vom Server, bietet update/reset-Methoden.
 * Automatisches Debouncing bei Updates (500ms).
 * 
 * Usage:
 *   const { settings, schema, update, reset, loading } = useAppSettings('system-monitor')
 *   // settings.refresh_interval_ms → 5000
 *   // update({ refresh_interval_ms: 3000 })
 */
export function useAppSettings(appId) {
  const [settings, setSettings] = useState(null)
  const [schema, setSchema] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const debounceRef = useRef(null)

  // Initial Load
  useEffect(() => {
    if (!appId) return
    setLoading(true)
    Promise.all([
      api.appSettings(appId).catch(() => ({})),
      api.appSettingsSchema(appId).catch(() => ({ schema: {}, defaults: {} }))
    ]).then(([settingsData, schemaData]) => {
      setSettings(settingsData)
      setSchema(schemaData.schema || {})
      setLoading(false)
    }).catch(err => {
      setError(err.message)
      setLoading(false)
    })
  }, [appId])

  // Update: Setzt lokal sofort, debounced zum Server
  const update = useCallback((patch) => {
    setSettings(prev => ({ ...prev, ...patch }))
    
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      api.appSettingsUpdate(appId, patch).catch(console.error)
    }, 500)
  }, [appId])

  // Einzelnen Wert setzen
  const set = useCallback((key, value) => {
    update({ [key]: value })
  }, [update])

  // Reset auf Defaults
  const reset = useCallback(async () => {
    try {
      const result = await api.appSettingsReset(appId)
      setSettings(result)
    } catch (err) {
      setError(err.message)
    }
  }, [appId])

  // Cleanup
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  return { settings, schema, loading, error, update, set, reset }
}

// Default Export — damit BEIDE Import-Varianten funktionieren:
//   import { useAppSettings } from '...'   → Named Export (funktioniert)
//   import useAppSettings from '...'        → Default Export (funktioniert jetzt auch)
export default useAppSettings
