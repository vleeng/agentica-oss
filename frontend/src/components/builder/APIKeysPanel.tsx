import { useEffect, useMemo, useState } from 'react'

import { type APIKey, apiKeysApi, tenantsApi, type AgentSummary } from '../../lib/api'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Field } from '../ui/field'
import { Input, Select } from '../ui/input'
import { useToast } from '../ui/toast'

export function APIKeysPanel() {
  const [keys, setKeys] = useState<APIKey[]>([])
  const [agents, setAgents] = useState<AgentSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [selectedAgentId, setSelectedAgentId] = useState('')
  const [justCreated, setJustCreated] = useState<APIKey | null>(null)
  const [error, setError] = useState('')
  const { push } = useToast()

  const loadKeys = async () => {
    setLoading(true)
    try {
      const data = await apiKeysApi.list()
      setKeys(Array.isArray(data) ? data : [])
      setError('')
    } catch {
      setError('No se pudieron cargar las API keys.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const loadData = async () => {
      try {
        const [agentList] = await Promise.all([tenantsApi.listAgents(), loadKeys()])
        const normalized = Array.isArray(agentList) ? agentList : []
        setAgents(normalized)
        setSelectedAgentId((current) => current || normalized[0]?.agent_id || '')
      } catch {
        setError('No se pudieron cargar los agentes o las API keys.')
      }
    }
    loadData()
  }, [])

  const createKey = async () => {
    if (!newKeyName.trim() || !selectedAgentId) return
    setCreating(true)
    try {
      const data = await apiKeysApi.create(newKeyName.trim(), selectedAgentId)
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
      setKeys((prev) => prev.filter((key) => key.id !== keyId))
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

  const selectedAgent = useMemo(
    () => agents.find((agent) => agent.agent_id === selectedAgentId) || null,
    [agents, selectedAgentId]
  )

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-slate-950">API Keys</h2>
        <p className="mt-1 text-sm text-slate-500">
          Genera llaves públicas atadas a un agente específico para widgets e integraciones.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Nueva key</CardTitle>
          <CardDescription>Elegi el agente, nombrala y usala solo en el canal que corresponda.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-[0.95fr_1.15fr_auto]">
            <Field label="Agente" className="mb-0">
              <Select
                value={selectedAgentId}
                onChange={(event) => setSelectedAgentId(event.target.value)}
                disabled={agents.length === 0}
              >
                {agents.length === 0 ? (
                  <option value="">No hay agentes disponibles</option>
                ) : (
                  agents.map((agent) => (
                    <option key={agent.agent_id} value={agent.agent_id}>
                      {agent.name}
                    </option>
                  ))
                )}
              </Select>
            </Field>
            <Field label="Nombre" className="mb-0">
              <Input
                value={newKeyName}
                onChange={(event) => setNewKeyName(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && createKey()}
                placeholder="Ej: Widget produccion"
              />
            </Field>
            <Button onClick={createKey} disabled={creating || !newKeyName.trim() || !selectedAgentId} className="self-end">
              {creating ? 'Creando...' : 'Crear'}
            </Button>
          </div>

          {selectedAgent && (
            <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              Esta key quedara limitada al agente <span className="font-medium text-slate-900">{selectedAgent.name}</span>.
            </div>
          )}
        </CardContent>
      </Card>

      {justCreated && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="space-y-3 pt-5">
            <p className="text-sm font-medium text-amber-800">
              Copia esta key ahora. No se va a mostrar de nuevo.
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 break-all rounded-lg border border-amber-200 bg-white px-3 py-2 text-xs font-mono">
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
              Ya la guarde
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
          <CardDescription>Cada key queda restringida al agente con el que fue creada.</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
            </div>
          ) : keys.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-400">No tenes API keys todavia.</p>
          ) : (
            <div className="space-y-2">
              {keys.map((key) => (
                <div
                  key={key.id}
                  className="flex items-center gap-3 rounded-xl border border-slate-200 p-4"
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-slate-800">{key.name}</div>
                    <div className="mt-0.5 text-xs text-slate-500">{key.agent_name || 'Agente sin resolver'}</div>
                    <div className="mt-0.5 font-mono text-xs text-slate-400">{key.key_prefix}...</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      {key.scopes.map((scope) => (
                        <span key={scope} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                          {scope}
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
                    className="text-rose-500 hover:bg-rose-50 hover:text-rose-700"
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
