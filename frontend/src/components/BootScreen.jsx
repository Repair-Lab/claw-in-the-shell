import React, { useState, useEffect, useRef, useMemo } from 'react'
import { api } from '../api'

/**
 * Boot-Screen — Elegantes Bare-Metal Boot-Erlebnis
 * Pulsierender Kern, konzentrische Ringe, fließende Boot-Meldungen.
 * Rein CSS-basiert — kein WebGL/Three.js nötig.
 */
export default function BootScreen({ onComplete }) {
  const [lines, setLines] = useState([])
  const [bootData, setBootData] = useState([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [phase, setPhase] = useState('init')       // init → boot → ready → fade
  const [progress, setProgress] = useState(0)
  const containerRef = useRef(null)

  // Zufällige Partikel generieren (einmal, memo)
  const particles = useMemo(() =>
    Array.from({ length: 30 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: 1 + Math.random() * 2,
      delay: Math.random() * 6,
      duration: 4 + Math.random() * 8,
    })), [])

  // Boot-Sequenz von der API laden
  useEffect(() => {
    api.bootSequence()
      .then(data => setBootData(data))
      .catch(() => {
        setBootData([
          { step: 1, phase: 'bios',     message: 'POST: Hardware Enumeration',              delay_ms: 180 },
          { step: 2, phase: 'bios',     message: 'Memory: 64 GB DDR5 @ 4800 MHz',           delay_ms: 120 },
          { step: 3, phase: 'bios',     message: 'GPU: NVIDIA RTX PRO 6000 (96 GB VRAM)',    delay_ms: 140 },
          { step: 4, phase: 'kernel',   message: 'Loading PostgreSQL Kernel 17.4',           delay_ms: 280 },
          { step: 5, phase: 'kernel',   message: 'Mounting tablespace: dbai_core',           delay_ms: 160 },
          { step: 6, phase: 'kernel',   message: 'WAL journal: synchronized',               delay_ms: 120 },
          { step: 7, phase: 'services', message: 'Starting event_dispatcher',                delay_ms: 140 },
          { step: 8, phase: 'services', message: 'Starting hardware_monitor',                delay_ms: 120 },
          { step: 9, phase: 'services', message: 'Starting ghost_dispatcher',                delay_ms: 160 },
          { step: 10, phase: 'ghost',   message: 'Neural Bridge: establishing link',         delay_ms: 240 },
          { step: 11, phase: 'ghost',   message: 'Ghost: models loaded (171 detected)',      delay_ms: 200 },
          { step: 12, phase: 'ghost',   message: 'Synaptic handshake: complete',             delay_ms: 180 },
          { step: 13, phase: 'ready',   message: 'All subsystems nominal',                   delay_ms: 100 },
          { step: 14, phase: 'ready',   message: 'System ready.',                            delay_ms: 600 },
        ])
      })

    // Init-Phase kurz zeigen, dann Boot starten
    const t = setTimeout(() => setPhase('boot'), 800)
    return () => clearTimeout(t)
  }, [])

  // Zeilen nacheinander anzeigen
  useEffect(() => {
    if (phase !== 'boot' || bootData.length === 0 || currentIndex >= bootData.length) return

    const step = bootData[currentIndex]
    const delay = step.delay_ms || 100

    const timer = setTimeout(() => {
      const icons = { bios: '›', kernel: '◆', services: '▸', ghost: '⟡', ready: '✦' }
      const icon = icons[step.phase] || '›'
      setLines(prev => [...prev, { ...step, display: `${icon}  ${step.message || '...'}` }])
      setCurrentIndex(prev => prev + 1)
      setProgress(((currentIndex + 1) / bootData.length) * 100)
    }, delay)

    return () => clearTimeout(timer)
  }, [phase, bootData, currentIndex])

  // Auto-scroll
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [lines])

  // Boot fertig → Fade-out → Login
  useEffect(() => {
    if (bootData.length > 0 && currentIndex >= bootData.length && phase === 'boot') {
      setProgress(100)
      const t1 = setTimeout(() => setPhase('ready'), 400)
      return () => clearTimeout(t1)
    }
  }, [currentIndex, bootData, phase])

  useEffect(() => {
    if (phase === 'ready') {
      const t = setTimeout(() => setPhase('fade'), 1200)
      return () => clearTimeout(t)
    }
    if (phase === 'fade') {
      const t = setTimeout(onComplete, 800)
      return () => clearTimeout(t)
    }
  }, [phase, onComplete])

  const handleSkip = () => onComplete()

  return (
    <div className={`boot-screen ${phase === 'fade' ? 'boot-fade-out' : ''}`} onClick={handleSkip}>

      {/* Hintergrund-Partikel */}
      <div className="boot-particles" aria-hidden>
        {particles.map(p => (
          <span
            key={p.id}
            className="boot-particle"
            style={{
              left: `${p.x}%`,
              top: `${p.y}%`,
              width: p.size,
              height: p.size,
              animationDelay: `${p.delay}s`,
              animationDuration: `${p.duration}s`,
            }}
          />
        ))}
      </div>

      {/* Zentrale Visualisierung */}
      <div className="boot-center">
        <div className="boot-rings">
          <div className="boot-ring boot-ring-1" />
          <div className="boot-ring boot-ring-2" />
          <div className="boot-ring boot-ring-3" />
        </div>
        <div className={`boot-core ${phase === 'ready' ? 'boot-core-ready' : ''}`}>
          <span className="boot-core-text">DBAI</span>
        </div>
        <div className="boot-subtitle">
          {phase === 'init' && 'Initializing...'}
          {phase === 'boot' && 'Booting System'}
          {(phase === 'ready' || phase === 'fade') && 'The Ghost in the Database'}
        </div>
      </div>

      {/* Boot-Log (klein, unten links) */}
      <div className="boot-log" ref={containerRef}>
        {lines.map((line, i) => (
          <div key={i} className={`boot-line phase-${line.phase}`}>
            {line.display}
          </div>
        ))}
        {phase === 'boot' && currentIndex < bootData.length && (
          <div className="boot-line boot-cursor">█</div>
        )}
      </div>

      {/* Progress Bar */}
      <div className="boot-progress-track">
        <div className="boot-progress-bar" style={{ width: `${progress}%` }} />
      </div>

      {/* Skip-Hint */}
      <div className="boot-skip-hint">
        {phase !== 'fade' && 'Klicke um zu überspringen'}
      </div>
    </div>
  )
}
