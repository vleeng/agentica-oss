export function formatApiError(detail: unknown, fallback: string): string {
  if (!detail) return fallback

  if (typeof detail === 'string') return detail

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object' && 'msg' in item) {
          return String((item as { msg?: unknown }).msg || '')
        }
        return ''
      })
      .filter(Boolean)

    return messages.length ? messages.join(' | ') : fallback
  }

  if (typeof detail === 'object' && detail !== null && 'msg' in detail) {
    return String((detail as { msg?: unknown }).msg || fallback)
  }

  return fallback
}
