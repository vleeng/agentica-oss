import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { ErrorBoundary } from './components/debug/ErrorBoundary'
import './index.css'

window.addEventListener('error', (event) => {
  console.error('[Agentica][window.error]', {
    message: event.message,
    filename: event.filename,
    lineno: event.lineno,
    colno: event.colno,
    error: event.error,
  })
})

window.addEventListener('unhandledrejection', (event) => {
  console.error('[Agentica][unhandledrejection]', event.reason)
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
)
