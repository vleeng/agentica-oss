import { KeyRound, Plus, ShieldCheck, Star, X } from 'lucide-react'
import { useEffect, useState } from 'react'

import { llmKeysApi, type ProviderKey } from '../../lib/api'
import { getAuthToken } from '../../stores/auth'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Field } from '../ui/field'
import { Input, Select } from '../ui/input'
import { useToast } from '../ui/toast'
import { BuilderConfigPanel } from './BuilderConfigPanel'

const providers = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'qwen', label: 'Qwen / Alibaba' },
  { value: 'moonshot', label: 'Moonshot / Kimi' },
  { value: 'zhipu', label: 'Zhipu / GLM' },
  { value: 'custom_openai', label: 'OpenAI compatible custom' },
]

function getUserRoleFromToken(): string {
  try {
    const token = getAuthToken()
    if (!token) return ''
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.role || ''
  } catch {
    return ''
  }
}

export function ProvidersPanel() {
  const [keys, setKeys] = useState<ProviderKey[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')
  const [newProv, setNewProv] = useState('openai')
  const [newName, setNewName] = useState('')
  const [newRawKey, setNewRawKey] = useState('')
  const { push } = useToast()
  const isOwner = getUserRoleFromToken() === 'owner'

  const loadKeys = async () => {
    setLoading(true)
    try {
      const data = await llmKeysApi.list()
      setKeys(Array.isArray(data) ? data : [])
      setErrorMsg('')
    } catch {
      setErrorMsg('No pudimos cargar la bóveda. Verificá la conexión con el backend.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadKeys()
  }, [])

  const saveKey = async () => {
    if (!newRawKey.trim() || !newName.trim()) return
    setCreating(true)
    try {
      await llmKeysApi.create({ provider: newProv, name: newName, raw_key: newRawKey })
      push({ tone: 'success', title: 'Clave guardada', description: 'La bóveda cifrada quedó actualizada.' })
      setNewName('')
      setNewRawKey('')
      await loadKeys()
    } catch (e: any) {
      setErrorMsg(e.response?.data?.detail || 'No se pudo guardar la clave.')
    } finally {
      setCreating(false)
    }
  }

  const setDefault = async (keyId: string, provider: string) => {
    try {
      await llmKeysApi.setDefault(keyId, provider)
      push({ tone: 'success', title: 'Clave predeterminada actualizada' })
      await loadKeys()
    } catch {
      setErrorMsg('No se pudo marcar la clave como predeterminada.')
    }
  }

  const removeKey = async (keyId: string) => {
    try {
      await llmKeysApi.remove(keyId)
      push({ tone: 'info', title: 'Clave eliminada' })
      setKeys((prev) => prev.filter((key) => key.id !== keyId))
    } catch {
      setErrorMsg('No se pudo eliminar la clave.')
    }
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-6 lg:grid-cols-[1fr_0.8fr]">
        <Card className="overflow-hidden border-slate-200 bg-[linear-gradient(135deg,#ffffff_0%,#f8fafc_50%,#eef2ff_100%)]">
          <CardContent className="p-8">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-violet-700">
                <ShieldCheck className="h-6 w-6" />
              </div>
              <div className="space-y-3">
                <h2 className="text-2xl font-semibold text-slate-950">Bóveda de proveedores LLM</h2>
                <p className="max-w-2xl text-sm leading-7 text-slate-600">
                  Guardá credenciales cifradas, elegí defaults por proveedor y mantené un acceso ordenado para OpenAI, Claude, OpenRouter y modelos compatibles.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Resumen</CardTitle>
            <CardDescription>Estado operativo de tus credenciales.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <SummaryRow label="Claves guardadas" value={String(keys.length)} />
            <SummaryRow label="Proveedores activos" value={String(new Set(keys.map((key) => key.provider)).size)} />
            <SummaryRow label="Defaults definidos" value={String(keys.filter((key) => key.is_default).length)} />
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Agregar credencial</CardTitle>
          <CardDescription>Las claves se almacenan cifradas y se usan desde el runtime o el wizard.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-[0.9fr_1fr_1.2fr_auto]">
          <Field label="Proveedor">
            <Select value={newProv} onChange={(e) => setNewProv(e.target.value)}>
              {providers.map((provider) => (
                <option key={provider.value} value={provider.value}>
                  {provider.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Alias">
            <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Ej: OpenRouter producción" />
          </Field>
          <Field label="API key">
            <Input
              type="password"
              value={newRawKey}
              onChange={(e) => setNewRawKey(e.target.value)}
              placeholder="sk-..."
            />
          </Field>
          <div className="flex items-end">
            <Button onClick={saveKey} className="w-full xl:w-auto" disabled={creating || !newName || !newRawKey}>
              {creating ? 'Guardando...' : 'Guardar'}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Credenciales disponibles</CardTitle>
          <CardDescription>Podés marcar defaults y revisar rápidamente qué proveedor cubre cada flujo.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {errorMsg && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{errorMsg}</div>
          )}

          {loading ? (
            <div className="flex min-h-[14rem] items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
            </div>
          ) : keys.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-6 py-16 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-100 text-violet-700">
                <KeyRound className="h-6 w-6" />
              </div>
              <h3 className="mt-5 text-lg font-semibold text-slate-900">Tu bóveda todavía está vacía</h3>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                Agregá una clave para empezar a operar modelos desde el wizard y el runtime.
              </p>
            </div>
          ) : (
            keys.map((key) => (
              <KeyRow
                key={key.id}
                providerKey={key}
                onSetDefault={() => setDefault(key.id, key.provider)}
                onRemove={() => removeKey(key.id)}
                onModelsUpdated={loadKeys}
              />
            ))
          )}
        </CardContent>
      </Card>

      {isOwner && <BuilderConfigPanel />}
    </div>
  )
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
      <span className="text-sm text-slate-600">{label}</span>
      <span className="text-lg font-semibold text-slate-950">{value}</span>
    </div>
  )
}

function KeyRow({
  providerKey,
  onSetDefault,
  onRemove,
  onModelsUpdated,
}: {
  providerKey: ProviderKey
  onSetDefault: () => void
  onRemove: () => void
  onModelsUpdated: () => void
}) {
  const [newModel, setNewModel] = useState('')
  const [saving, setSaving] = useState(false)
  const { push } = useToast()

  const addModel = async () => {
    const model = newModel.trim()
    if (!model || providerKey.models.includes(model)) return
    setSaving(true)
    try {
      await llmKeysApi.updateModels(providerKey.id, [...providerKey.models, model])
      setNewModel('')
      onModelsUpdated()
    } catch {
      push({ tone: 'error', title: 'Error', description: 'No se pudo agregar el modelo.' })
    } finally {
      setSaving(false)
    }
  }

  const removeModel = async (model: string) => {
    setSaving(true)
    try {
      await llmKeysApi.updateModels(providerKey.id, providerKey.models.filter(m => m !== model))
      onModelsUpdated()
    } catch {
      push({ tone: 'error', title: 'Error', description: 'No se pudo eliminar el modelo.' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-5 py-4 space-y-4">
      {/* Header de la key */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-start gap-4">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100 text-sm font-semibold text-slate-700">
            {providerKey.provider.slice(0, 2).toUpperCase()}
          </div>
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-slate-950">{providerKey.name}</span>
              <Badge tone="slate">{providerKey.provider}</Badge>
              {providerKey.is_default && (
                <Badge tone="violet">
                  <Star className="mr-1 h-3 w-3" />
                  Predeterminada
                </Badge>
              )}
            </div>
            <div className="font-mono text-sm text-slate-500">{providerKey.truncated_key}</div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {!providerKey.is_default && (
            <Button variant="secondary" onClick={onSetDefault}>Marcar default</Button>
          )}
          <Button variant="ghost" className="text-rose-600 hover:bg-rose-50 hover:text-rose-700" onClick={onRemove}>
            Eliminar
          </Button>
        </div>
      </div>

      {/* Modelos disponibles */}
      <div className="border-t border-slate-100 pt-3 space-y-2">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Modelos disponibles</p>
        <div className="flex flex-wrap gap-2">
          {providerKey.models.length === 0 && (
            <span className="text-xs text-slate-400">Sin modelos — agregá al menos uno para poder usarlo en el Wizard.</span>
          )}
          {providerKey.models.map(model => (
            <span key={model} className="flex items-center gap-1 rounded-full bg-violet-50 border border-violet-200 px-3 py-1 text-xs font-mono text-violet-700">
              {model}
              <button onClick={() => removeModel(model)} disabled={saving} className="ml-1 hover:text-rose-600">
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
        <div className="flex gap-2 mt-2">
          <input
            value={newModel}
            onChange={e => setNewModel(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && addModel()}
            placeholder={`Ej: ${providerKey.provider === 'openrouter' ? 'openai/gpt-4o-mini' : providerKey.provider === 'openai' ? 'gpt-4o' : 'claude-3-5-sonnet-20241022'}`}
            className="flex-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-violet-500"
          />
          <Button size="sm" variant="secondary" onClick={addModel} disabled={saving || !newModel.trim()}>
            <Plus className="h-3.5 w-3.5" />
            Agregar
          </Button>
        </div>
      </div>
    </div>
  )
}
