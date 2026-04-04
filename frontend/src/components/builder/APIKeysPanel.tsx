import { useEffect, useState } from 'react'

interface APIKey {
  id: string
  name: string
  key?: string
  key_prefix: string
  scopes: string[]
  expires_at: string | null
  created_at: string
}

export function APIKeysPanel() {
  const [keys, setKeys]         = useState<APIKey[]>([])
  const [loading, setLoading]   = useState(true)
  const [creating, setCreating] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [justCreated, setJustCreated] = useState<APIKey | null>(null)

  const headers = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('agentica_token')}`,
  })

  const loadKeys = async () => {
    const r = await fetch('/api/v1/keys/', { headers: headers() })
    const data = await r.json()
    setKeys(Array.isArray(data) ? data : [])
    setLoading(false)
  }

  useEffect(() => { loadKeys() }, [])

  const createKey = async () => {
    if (!newKeyName.trim()) return
    setCreating(true)
    try {
      const r = await fetch('/api/v1/keys/', {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ name: newKeyName, scopes: ['invoke'] }),
      })
      const data = await r.json()
      setJustCreated(data)
      setNewKeyName('')
      await loadKeys()
    } finally {
      setCreating(false)
    }
  }

  const revokeKey = async (keyId: string) => {
    if (!confirm('¿Revocar esta API key? No se puede deshacer.')) return
    await fetch(`/api/v1/keys/${keyId}`, { method: 'DELETE', headers: headers() })
    setKeys(keys.filter(k => k.id !== keyId))
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h2 className="text-xl font-semibold text-gray-900 mb-6">API Keys</h2>

      {/* Crear nueva */}
      <div className="flex gap-3 mb-6">
        <input
          type="text"
          value={newKeyName}
          onChange={e => setNewKeyName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && createKey()}
          placeholder="Nombre de la key, ej: Widget producción"
          className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
        />
        <button
          onClick={createKey}
          disabled={creating || !newKeyName.trim()}
          className="px-4 py-2 bg-violet-600 text-white text-sm rounded-lg hover:bg-violet-700 disabled:opacity-40 transition-colors"
        >
          {creating ? '...' : 'Crear'}
        </button>
      </div>

      {/* Key recién creada — única vez que se muestra */}
      {justCreated && (
        <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <div className="text-sm font-medium text-amber-800 mb-2">
            Copiá esta key ahora — no se va a mostrar de nuevo
          </div>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs bg-white border border-amber-200 rounded px-3 py-2 font-mono break-all">
              {justCreated.key}
            </code>
            <button
              onClick={() => {
                navigator.clipboard.writeText(justCreated.key!)
                alert('Copiado!')
              }}
              className="px-3 py-2 text-xs border border-amber-300 rounded-lg hover:bg-amber-100 transition-colors"
            >
              Copiar
            </button>
          </div>
          <button
            onClick={() => setJustCreated(null)}
            className="mt-2 text-xs text-amber-600 hover:text-amber-800"
          >
            Ya la guardé ✓
          </button>
        </div>
      )}

      {/* Lista de keys */}
      {loading ? (
        <div className="text-center py-8 text-gray-400 text-sm">Cargando...</div>
      ) : keys.length === 0 ? (
        <div className="text-center py-8 text-gray-400 text-sm">
          No tenés API keys todavía.
        </div>
      ) : (
        <div className="space-y-2">
          {keys.map(key => (
            <div key={key.id}
              className="flex items-center gap-3 p-4 bg-white border border-gray-200 rounded-xl"
            >
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-800">{key.name}</div>
                <div className="text-xs text-gray-500 font-mono mt-0.5">
                  {key.key_prefix}...
                </div>
                <div className="flex items-center gap-2 mt-1">
                  {key.scopes.map(s => (
                    <span key={s} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                      {s}
                    </span>
                  ))}
                  {key.expires_at && (
                    <span className="text-xs text-gray-400">
                      Expira {new Date(key.expires_at).toLocaleDateString('es-AR')}
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={() => revokeKey(key.id)}
                className="text-sm text-red-500 hover:text-red-700 transition-colors px-3 py-1.5 rounded-lg hover:bg-red-50"
              >
                Revocar
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
