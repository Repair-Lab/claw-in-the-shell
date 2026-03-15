import React, { useState, useEffect, useRef } from 'react'
import { api } from '../api'

/**
 * Boot-Screen — BIOS/Kernel-Animation
 * Holt die Boot-Sequenz aus der DB und zeigt sie Zeile für Zeile an.
 */
export default function BootScreen({ onComplete }) {
  const [lines, setLines] = useState([])
  const [bootData, setBootData] = useState([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const containerRef = useRef(null)

  // Boot-Sequenz von der API laden
  useEffect(() => {
    api.bootSequence()
      .then(data => setBootData(data))
      .catch(() => {
        // Fallback Boot-Sequenz wenn API nicht erreichbar
        setBootData([
          { step: 1, phase: 'bios', message: 'Initializing DBAI Kernel v0.3.0...', delay_ms: 200 },
          { step: 2, phase: 'bios', message: 'POST: Hardware check...', delay_ms: 150 },
          { step: 3, phase: 'kernel', message: 'Loading PostgreSQL Kernel...', delay_ms: 300 },
          { step: 4, phase: 'kernel', message: 'Mounting Database: dbai', delay_ms: 200 },
          { step: 5, phase: 'services', message: 'Starting services...', delay_ms: 200 },
          { step: 6, phase: 'ghost', message: 'Detecting Ghost Models...', delay_ms: 300 },
          { step: 7, phase: 'ghost', message: 'Synaptic Bridge established...', delay_ms: 250 },
          { step: 8, phase: 'ready', message: '═══════════════════════════════════════════', delay_ms: 50 },
          { step: 9, phase: 'ready', message: '  DBAI — Database AI Operating System', delay_ms: 50 },
          { step: 10, phase: 'ready', message: '  "The Ghost in the Database"', delay_ms: 50 },
          { step: 11, phase: 'ready', message: '═══════════════════════════════════════════', delay_ms: 50 },
          { step: 12, phase: 'ready', message: 'System ready. Welcome.', delay_ms: 500 },
        ])
      })
  }, [])

  // Zeilen nacheinander anzeigen
  useEffect(() => {
    if (bootData.length === 0 || currentIndex >= bootData.length) return

    const step = bootData[currentIndex]
    const delay = step.delay_ms || 100

    const timer = setTimeout(() => {
      const prefix = step.phase === 'bios' ? '  ' :
                     step.phase === 'ready' ? '' :
                     '[OK] '
      setLines(prev => [...prev, { ...step, display: prefix + (step.message || '...') }])
      setCurrentIndex(prev => prev + 1)
    }, delay)

    return () => clearTimeout(timer)
  }, [bootData, currentIndex])

  // Auto-scroll
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [lines])

  // Boot fertig → Weiter nach kurzer Pause
  useEffect(() => {
    if (bootData.length > 0 && currentIndex >= bootData.length) {
      const timer = setTimeout(onComplete, 1500)
      return () => clearTimeout(timer)
    }
  }, [currentIndex, bootData, onComplete])

  // Skip-Möglichkeit
  const handleSkip = () => onComplete()

  return (
    <div className="boot-screen" onClick={handleSkip}>
      <div ref={containerRef} style={{ flex: 1, overflow: 'auto' }}>
        {lines.map((line, i) => (
          <div key={i} className={`boot-line phase-${line.phase}`}>
            {line.display}
          </div>
        ))}
        {currentIndex < bootData.length && (
          <div className="boot-line phase-bios" style={{ opacity: 0.5 }}>
            █
          </div>
        )}
      </div>

      <div className="boot-logo">DBAI</div>

      <div style={{
        position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)',
        fontSize: '11px', color: '#444', fontFamily: 'var(--font-mono)'
      }}>
        Klicke um zu überspringen
      </div>
    </div>
  )
}
