import React, { useRef, useCallback, useState } from 'react'

/**
 * Window — Draggable, resizable OS-Fenster
 */
export default function Window({
  window: win,
  children,
  onClose,
  onFocus,
  onMinimize,
  onMaximize,
  onMove,
  onResize,
}) {
  const headerRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  // ── Drag ──
  const handleMouseDown = useCallback((e) => {
    if (win.state === 'maximized') return
    e.preventDefault()
    onFocus()

    const startX = e.clientX - win.x
    const startY = e.clientY - win.y

    const handleMouseMove = (e) => {
      onMove(e.clientX - startX, e.clientY - startY)
    }

    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      setDragging(false)
    }

    setDragging(true)
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [win.x, win.y, win.state, onFocus, onMove])

  // ── Resize ──
  const handleResizeMouseDown = useCallback((e) => {
    if (win.state === 'maximized') return
    e.preventDefault()
    e.stopPropagation()

    const startX = e.clientX
    const startY = e.clientY
    const startW = win.width
    const startH = win.height

    const handleMouseMove = (e) => {
      const newW = Math.max(320, startW + (e.clientX - startX))
      const newH = Math.max(200, startH + (e.clientY - startY))
      onResize(newW, newH)
    }

    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [win.width, win.height, win.state, onResize])

  const style = win.state === 'maximized'
    ? { zIndex: win.z }
    : {
        left: win.x,
        top: win.y,
        width: win.width,
        height: win.height,
        zIndex: win.z,
      }

  return (
    <div
      className={`window ${win.focused ? 'focused' : ''} ${win.state === 'maximized' ? 'maximized' : ''}`}
      style={style}
      onMouseDown={onFocus}
    >
      {/* Header / Title Bar */}
      <div
        className="window-header"
        ref={headerRef}
        onMouseDown={handleMouseDown}
        onDoubleClick={onMaximize}
      >
        <span className="icon">{win.appIcon}</span>
        <span className="title">{win.appName}</span>
        <div className="window-controls">
          <button className="minimize" onClick={(e) => { e.stopPropagation(); onMinimize() }} title="Minimieren" />
          <button className="maximize" onClick={(e) => { e.stopPropagation(); onMaximize() }} title="Maximieren" />
          <button className="close" onClick={(e) => { e.stopPropagation(); onClose() }} title="Schließen" />
        </div>
      </div>

      {/* Body */}
      <div className="window-body">
        {children}
      </div>

      {/* Resize Handle */}
      {win.state !== 'maximized' && (
        <div
          className="window-resize"
          onMouseDown={handleResizeMouseDown}
        />
      )}
    </div>
  )
}
