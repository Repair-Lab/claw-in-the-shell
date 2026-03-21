import React from 'react'

/**
 * ErrorBoundary — Fängt Render-Fehler in Kind-Komponenten ab.
 * Verhindert dass ein App-Crash den ganzen Desktop schwarz macht.
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo })
    console.error(`[ErrorBoundary] ${this.props.label || 'App'} crashed:`, error, errorInfo)
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '2rem',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          color: '#ff6b6b',
          background: 'rgba(255,60,60,0.05)',
          fontFamily: 'monospace',
        }}>
          <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>⚠️</div>
          <h3 style={{ margin: '0 0 0.5rem 0', color: '#ff4444' }}>
            {this.props.label || 'App'} — Fehler
          </h3>
          <p style={{ color: '#999', fontSize: '0.85rem', textAlign: 'center', maxWidth: 400 }}>
            {this.state.error?.message || 'Unbekannter Fehler'}
          </p>
          {this.state.errorInfo?.componentStack && (
            <pre style={{
              fontSize: '0.7rem',
              color: '#666',
              maxHeight: 120,
              overflow: 'auto',
              marginTop: '0.5rem',
              padding: '0.5rem',
              background: 'rgba(0,0,0,0.2)',
              borderRadius: 4,
              maxWidth: '90%',
            }}>
              {this.state.errorInfo.componentStack.slice(0, 500)}
            </pre>
          )}
          <button
            onClick={this.handleRetry}
            style={{
              marginTop: '1rem',
              padding: '0.5rem 1.5rem',
              background: '#00f5ff22',
              border: '1px solid #00f5ff',
              color: '#00f5ff',
              borderRadius: 6,
              cursor: 'pointer',
              fontFamily: 'monospace',
            }}
          >
            ↻ Neu laden
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

export default ErrorBoundary
