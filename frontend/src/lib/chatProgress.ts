import type { WSMessage } from './api'

type ProgressEvent = Extract<WSMessage, { type: 'status' | 'trace' }>

export function summarizeAgentProgress(event: ProgressEvent): string | null {
  const phase = String(event.phase || '').toLowerCase()
  const kind = String(('kind' in event ? event.kind : '') || '').toLowerCase()
  const actor = String(('actor' in event ? event.actor : '') || '').trim()
  const message = String(event.message || '').trim()
  const lowered = message.toLowerCase()

  if (kind === 'tool') {
    return actor ? `Usando ${actor}` : 'Usando herramienta'
  }

  if (kind === 'decision') {
    return 'Pensando'
  }

  if (kind === 'answer') {
    return 'Redactando respuesta'
  }

  if (phase === 'preparing') {
    return 'Pensando'
  }

  if (phase === 'completed') {
    return 'Respuesta lista'
  }

  if (lowered.includes('usando herramienta') || lowered.includes('ejecutando herramienta')) {
    const label = actor || message.split(':').slice(1).join(':').trim()
    return label ? `Usando ${label}` : 'Usando herramienta'
  }

  if (
    lowered.includes('pensando')
    || lowered.includes('resolviendo decision')
    || lowered.includes('ejecutando paso')
    || lowered.includes('entrando al flujo')
  ) {
    return 'Pensando'
  }

  if (lowered.includes('armando la respuesta') || lowered.includes('redactando la respuesta')) {
    return 'Redactando respuesta'
  }

  return null
}
