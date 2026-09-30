import React, { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div style={{
          padding: '20px',
          margin: '20px 0',
          border: '1px solid var(--rejected)',
          borderRadius: '8px',
          backgroundColor: 'var(--card2)',
        }}>
          <h3 style={{ color: 'var(--rejected)', margin: '0 0 10px' }}>
            Something went wrong
          </h3>
          <p style={{ color: 'var(--muted)', margin: '0 0 10px' }}>
            This view encountered an error and could not be displayed.
          </p>
          {this.state.error && (
            <details style={{ marginTop: '10px' }}>
              <summary style={{ cursor: 'pointer', color: 'var(--muted)' }}>
                Error details
              </summary>
              <pre style={{
                marginTop: '10px',
                padding: '10px',
                backgroundColor: 'var(--card3)',
                borderRadius: '4px',
                overflow: 'auto',
                fontSize: '12px',
                color: 'var(--muted2)',
              }}>
                {this.state.error.toString()}
                {this.state.error.stack && `\n\n${this.state.error.stack}`}
              </pre>
            </details>
          )}
        </div>
      )
    }

    return this.props.children
  }
}