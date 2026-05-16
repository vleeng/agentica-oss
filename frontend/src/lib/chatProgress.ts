import type { WSMessage } from './api'

type ProgressEvent = Extract<WSMessage, { type: 'status' | 'trace' }>

export function appendProgressEntry(entries: string[] | undefined, nextEntry: string | null, limit = 8): string[] {
  const label = String(nextEntry || '').trim()
  const current = Array.isArray(entries) ? [...entries] : []
  if (!label) return current
  if (current[current.length - 1] === label) return current
  current.push(label)
  if (current.length > limit) {
    return current.slice(current.length - limit)
  }
  return current
}

export function summarizeAgentProgress(event: ProgressEvent): string | null {
  const phase = String(event.phase || '').toLowerCase()
  const kind = String(('kind' in event ? event.kind : '') || '').toLowerCase()
  const actor = String(('actor' in event ? event.actor : '') || '').trim()
  const query = String(('query' in event ? event.query : '') || '').trim()
  const titles = Array.isArray('titles' in event ? event.titles : undefined)
    ? (event.titles as string[]).filter(Boolean)
    : []
  const message = String(event.message || '').trim()
  const lowered = message.toLowerCase()

  if (kind === 'rag_result') {
    if (titles.length > 0) {
      const preview = titles.slice(0, 3).join(', ')
      return `Encontre en conocimientos: ${preview}${titles.length > 3 ? ` y ${titles.length - 3} mas` : ''}`
    }
    return message || 'Revise los conocimientos disponibles'
  }

  if (kind === 'tool') {
    if (actor === 'knowledge_base') {
      return query ? `Buscando en conocimientos: ${query}` : 'Buscando en conocimientos'
    }
    return actor ? `Usando ${actor}` : 'Usando herramienta'
  }

  if (kind === 'decision') {
    if (message.toLowerCase().startsWith('pensando:')) {
      return message
    }
    if (message.toLowerCase().startsWith('decision:')) {
      return `Pensando: ${message.slice('Decision:'.length).trim()}`
    }
    return message || 'Pensando'
  }

  if (kind === 'answer') {
    return message || 'Redactando respuesta'
  }

  if (phase === 'preparing') {
    return message || 'Pensando'
  }

  if (phase === 'completed') {
    return 'Respuesta lista'
  }

  if (lowered.includes('usando herramienta') || lowered.includes('ejecutando herramienta')) {
    const label = actor || message.split(':').slice(1).join(':').trim()
    return label ? `Usando ${label}` : 'Usando herramienta'
  }

  if (lowered.includes('buscando en conocimientos')) {
    return message
  }

  if (lowered.includes('encontre en conocimientos') || lowered.includes('no encontre informacion relevante en conocimientos')) {
    return message
  }

  if (
    lowered.includes('pensando')
    || lowered.includes('resolviendo decision')
    || lowered.includes('ejecutando paso')
    || lowered.includes('entrando al flujo')
  ) {
    return message || 'Pensando'
  }

  if (lowered.includes('armando la respuesta') || lowered.includes('redactando la respuesta')) {
    return message || 'Redactando respuesta'
  }

  return null
}
