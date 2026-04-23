import React from 'react'

interface Props {
  children: React.ReactNode
}

interface State {
  hasError: boolean
  errorMessage: string
}

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = {
    hasError: false,
    errorMessage: '',
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      errorMessage: error?.message || 'Error desconocido en frontend',
    }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[Agentica][ErrorBoundary] Render error', {
      message: error?.message,
      stack: error?.stack,
      componentStack: errorInfo.componentStack,
      pathname: window.location.pathname,
    })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-red-50 text-red-900 flex items-center justify-center p-6">
          <div className="max-w-2xl w-full bg-white border border-red-200 rounded-lg p-6 shadow-sm">
            <h1 className="text-lg font-semibold mb-3">Frontend error</h1>
            <p className="text-sm mb-2">La app encontró un error de renderizado.</p>
            <pre className="text-xs whitespace-pre-wrap bg-red-50 border border-red-100 rounded p-3 overflow-auto">
              {this.state.errorMessage}
            </pre>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
