import { useEffect, useState } from 'react'
import { type APIKey, apiKeysApi } from '../../lib/api'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Field } from '../ui/field'
import { Input } from '../ui/input'
import { useToast } from '../ui/toast'

export function APIKeysPanel() {
  const [keys, setKeys]         = useState<APIKey[]>([])
  const [loading, setLoading]   = useState(true)
  const [creating, setCreating] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [justCreated, setJustCreated] = useState<APIKey | null>(null)
  const [error, setError] = useState('')
  const { push } = useToast()

  const loadKeys = async () => {
    setLoading(true)
    try {
      const data = await apiKeysApi.list()
      setKeys(data)
    } catch {
      setError('No se pudieron cargar las API keys.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadKeys() }, [])

  const createKey = async () => {
    if (!newKeyName.trim()) return
    setCreating(true)
    try {
      const data = await apiKeysApi.create(newKeyName.trim())
      setJustCreated(data)
      setNewKeyName('')
      await loadKeys()
    } catch {
      push({ tone: 'error', title: 'Error', description: 'No se pudo crear la API key.' })
    } finally {
      setCreating(false)
    }
  }

  const revokeKey = async (keyId: string, name: string) => {
    if (!window.confirm(`¿Revocar la key "${name}"? No se puede deshacer.`)) return
    try {
      await apiKeysApi.revoke(keyId)
      setKeys(keys.filter(k => k.id !== keyId))
      push({ tone: 'success', title: 'Key revocada', description: `"${name}" fue eliminada.` })
    } catch {
      push({ tone: 'error', title: 'Error', description: 'No se pudo revocar la key.' })
    }
  }

  const copyKey = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value)
      push({ tone: 'success', title: 'Copiado', description: 'Key copiada al portapapeles.' })
    } catch {
      push({ tone: 'error', title: 'Error', description: 'No se pudo copiar.' })
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-slate-950">API Keys</h2>
        <p className="mt-1 text-sm text-slate-500">
          Generá llaves para que tus aplicaciones invoquen agentes vía API.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Nueva key</CardTitle>
          <CardDescription>Dale un nombre descriptivo para identificarla después.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <Field label="" className="flex-1 mb-0">
              <Input
                value={newKeyName}
                onChange={e => setNewKeyName(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && createKey()}
                placeholder="Ej: Widget producción"
              />
            </Field>
            <Button onClick={createKey} disabled={creating || !newKeyName.trim()} className="self-end">
              {creating ? 'Creando...' : 'Crear'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {justCreated && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="pt-5 space-y-3">
            <p className="text-sm font-medium text-amber-800">
              Copiá esta key ahora — no se va a mostrar de nuevo.
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 rounded-lg border border-amber-200 bg-white px-3 py-2 text-xs font-mono break-all">
                {justCreated.key}
              </code>
              <Button variant="secondary" size="sm" onClick={() => copyKey(justCreated.key!)}>
                Copiar
              </Button>
            </div>
            <button
              onClick={() => setJustCreated(null)}
              className="text-xs text-amber-700 hover:text-amber-900"
            >
              Ya la guardé ✓
            </button>
          </CardContent>
        </Card>
      )}

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Keys activas</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
            </div>
          ) : keys.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-400">No tenés API keys todavía.</p>
          ) : (
            <div className="space-y-2">
              {keys.map(key => (
                <div
                  key={key.id}
                  className="flex items-center gap-3 rounded-xl border border-slate-200 p-4"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-slate-800">{key.name}</div>
                    <div className="text-xs text-slate-400 font-mono mt-0.5">{key.key_prefix}...</div>
                    <div className="flex flex-wrap items-center gap-2 mt-1">
                      {key.scopes.map(s => (
                        <span key={s} className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">
                          {s}
                        </span>
                      ))}
                      {key.expires_at && (
                        <span className="text-xs text-slate-400">
                          Expira {new Date(key.expires_at).toLocaleDateString('es-AR')}
                        </span>
                      )}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => revokeKey(key.id, key.name)}
                    className="text-rose-500 hover:text-rose-700 hover:bg-rose-50"
                  >
                    Revocar
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
