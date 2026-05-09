import { Settings } from 'lucide-react'
import { useEffect, useState } from 'react'

import { llmKeysApi, systemApi, type ProviderKey } from '../../lib/api'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Field } from '../ui/field'
import { Input, Select } from '../ui/input'
import { useToast } from '../ui/toast'

interface BuilderConfigOut {
  provider: string
  model: string
  llm_key_id?: string | null
  configured: boolean
}

export function BuilderConfigPanel() {
  const [keys, setKeys] = useState<ProviderKey[]>([])
  const [config, setConfig] = useState<BuilderConfigOut | null>(null)
  const [selectedKeyId, setSelectedKeyId] = useState<string>('')
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [provider, setProvider] = useState<string>('openrouter')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const { push } = useToast()

  const load = async () => {
    setLoading(true)
    try {
      const [keysData, cfg] = await Promise.all([
        llmKeysApi.list(),
        systemApi.getBuilderConfig(),
      ])
      const keyList = Array.isArray(keysData) ? keysData : []
      setKeys(keyList)
      setConfig(cfg)
      setProvider(cfg.provider || 'openrouter')
      setSelectedKeyId(cfg.llm_key_id || '')
      setSelectedModel(cfg.model || '')
    } catch {
      push({ tone: 'error', title: 'Error', description: 'No se pudo cargar la configuración del builder.' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  // When selected key changes, update provider from that key
  const handleKeyChange = (keyId: string) => {
    setSelectedKeyId(keyId)
    setSelectedModel('')
    if (keyId) {
      const key = keys.find(k => k.id === keyId)
      if (key) setProvider(key.provider)
    }
  }

  const selectedKey = keys.find(k => k.id === selectedKeyId)
  const availableModels = selectedKey?.models ?? []

  const save = async () => {
    setSaving(true)
    try {
      await systemApi.setBuilderConfig({
        provider,
        model: selectedModel,
        llm_key_id: selectedKeyId || undefined,
      })
      push({ tone: 'success', title: 'Configuración guardada', description: 'El builder usará la nueva configuración.' })
      await load()
    } catch (e: any) {
      push({ tone: 'error', title: 'Error', description: e.response?.data?.detail || 'No se pudo guardar.' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="border-violet-200 bg-[linear-gradient(135deg,#ffffff_0%,#f5f3ff_100%)]">
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-100 text-violet-700">
            <Settings className="h-5 w-5" />
          </div>
          <div>
            <CardTitle>Configuracion del Builder</CardTitle>
            <CardDescription>
              LLM que genera los disenos de agentes cuando se crea uno nuevo.
              {config?.configured
                ? ' Configurado desde la base de datos.'
                : ' Usando valores de variables de entorno.'}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex min-h-[8rem] items-center justify-center">
            <div className="h-7 w-7 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
          </div>
        ) : (
          <div className="space-y-4">
            {keys.length === 0 && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                No hay claves en la boveda. Agrega al menos una credencial para poder seleccionarla como builder.
              </div>
            )}

            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Clave de boveda (vault)">
                <Select
                  value={selectedKeyId}
                  onChange={e => handleKeyChange(e.target.value)}
                >
                  <option value="">— Usar variable de entorno —</option>
                  {keys.map(k => (
                    <option key={k.id} value={k.id}>
                      {k.name} ({k.provider})
                    </option>
                  ))}
                </Select>
              </Field>

              <Field label="Modelo">
                {availableModels.length > 0 ? (
                  <Select
                    value={selectedModel}
                    onChange={e => setSelectedModel(e.target.value)}
                  >
                    <option value="">— Selecciona un modelo —</option>
                    {availableModels.map((m) => (
                      <option key={m.id} value={m.id}>{m.id}</option>
                    ))}
                  </Select>
                ) : (
                  <Input
                    value={selectedModel}
                    onChange={e => setSelectedModel(e.target.value)}
                    placeholder={provider === 'anthropic' ? 'claude-3-5-sonnet-20241022' : 'openai/gpt-4o-mini'}
                  />
                )}
              </Field>
            </div>

            {config && (
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500 space-y-1">
                <div><span className="font-medium">Proveedor activo:</span> {config.provider}</div>
                <div><span className="font-medium">Modelo activo:</span> {config.model}</div>
                {config.llm_key_id && (
                  <div><span className="font-medium">Clave vault:</span> {config.llm_key_id}</div>
                )}
              </div>
            )}

            <div className="flex justify-end">
              <Button
                onClick={save}
                disabled={saving || !selectedModel.trim()}
              >
                {saving ? 'Guardando...' : 'Guardar configuracion'}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
