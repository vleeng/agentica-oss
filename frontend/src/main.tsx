import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App'
import { ErrorBoundary } from './components/debug/ErrorBoundary'
import { ToastProvider } from './components/ui/toast'
import './index.css'

const routerBase = (() => {
  const raw = import.meta.env.BASE_URL || '/'
  if (!raw || raw === '/') return undefined
  return raw.replace(/\/$/, '')
})()

window.addEventListener('error', (event) => {
  console.error('[Agentica][Window] error', {
    message: event.message,
    filename: event.filename,
    lineno: event.lineno,
    colno: event.colno,
    pathname: window.location.pathname,
  })
})

window.addEventListener('unhandledrejection', (event) => {
  console.error('[Agentica][Window] unhandledrejection', {
    reason: event.reason,
    pathname: window.location.pathname,
  })
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter basename={routerBase}>
      <ToastProvider>
        <ErrorBoundary>
          <App />
        </ErrorBoundary>
      </ToastProvider>
    </BrowserRouter>
  </React.StrictMode>
)
