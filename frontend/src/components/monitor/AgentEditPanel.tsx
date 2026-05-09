import { Save } from 'lucide-react'
import { useEffect, useState } from 'react'

import type { AgentDesign } from '../../types/agent'
import { agentsApi, llmKeysApi, type ProviderKey } from '../../lib/api'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Field } from '../ui/field'
import { Input } from '../ui/input'
import { useToast } from '../ui/toast'

interface Props {
  design: AgentDesign
  onUpdated: (newDesign: AgentDesign) => void
}

export function AgentEditPanel({ design, onUpdated }: Props) {
  const { push } = useToast()

  // Form state
  const [name, setName]               = useState(design.spec.name)
  const [systemPrompt, setSystemPrompt] = useState(design.system_prompt ?? '')
  const [model, setModel]             = useState(design.spec.model_params?.model ?? '')
  const [llmKeyId, setLlmKeyId]       = useState(design.spec.model_params?.llm_key_id ?? '')
  const [temperature, setTemperature] = useState(design.spec.model_params?.temperature ?? 0.3)
  const [maxTokens, setMaxTokens]     = useState(design.spec.model_params?.max_tokens ?? 2048)

  // Vault keys + available models
  const [keys, setKeys]         = useState<ProviderKey[]>([])
  const [saving, setSaving]     = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    llmKeysApi.list().then(setKeys).catch(() => {})
  }, [])

  // Flat list of {keyId, modelId} options
  const modelOptions = keys.flatMap((k) =>
    (k.models ?? []).map((m) => ({ keyId: k.id, modelId: m.id, keyName: k.name, provider: k.provider }))
  )

  const selectedOption = modelOptions.find((o) => o.modelId === model && o.keyId === llmKeyId)

  // When model select changes, set both model id and key id
  const handleModelChange = (value: string) => {
    const opt = modelOptions.find((o) => o.modelId === value)
    setModel(value)
    if (opt) setLlmKeyId(opt.keyId)
  }

  const handleSave = async () => {
    if (!name.trim()) {
      setErrorMsg('El nombre del agente no puede estar vacío.')
      return
    }
    setSaving(true)
    setErrorMsg('')
    try {
      const updated = await agentsApi.update(design.agent_id, {
        name:          name.trim(),
        model:         model || undefined,
        provider:      selectedOption?.provider,
        llm_key_id:    llmKeyId || undefined,
        system_prompt: systemPrompt,
        temperature,
        max_tokens:    maxTokens,
      })
      push({
        tone: 'success',
        title: 'Agente actualizado',
        description: 'El runtime fue reconstruido con la nueva configuración.',
      })
      onUpdated(updated)
    } catch (e: any) {
      setErrorMsg(e.response?.data?.detail || 'No se pudo actualizar el agente.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Identity */}
      <Card>
        <CardHeader>
          <CardTitle>Identidad</CardTitle>
          <CardDescription>Nombre y descripción visible en el dashboard.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <Field label="Nombre del agente">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ej: Asistente de ventas"
            />
          </Field>
          <div />
          <Field label="System prompt" className="md:col-span-2">
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={6}
              placeholder="Instrucciones de comportamiento del agente..."
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-violet-500 resize-y"
            />
          </Field>
        </CardContent>
      </Card>

      {/* Model */}
      <Card>
        <CardHeader>
          <CardTitle>Modelo LLM</CardTitle>
          <CardDescription>
            Elegí el modelo desde tu bóveda. Si no ves opciones, agregá modelos en{' '}
            <span className="font-medium text-violet-700">Bóveda IA</span>.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <Field label="Modelo">
            {modelOptions.length === 0 ? (
              <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
                No hay modelos configurados en la bóveda. Agregá al menos uno para poder cambiar el modelo.
              </p>
            ) : (
              <select
                value={model}
                onChange={(e) => handleModelChange(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500"
              >
                <option value="">— seleccioná un modelo —</option>
                {modelOptions.map((o) => (
                  <option key={`${o.keyId}__${o.modelId}`} value={o.modelId}>
                    {o.modelId} ({o.keyName})
                  </option>
                ))}
              </select>
            )}
          </Field>

          <div />

          {/* Temperature */}
          <Field label={`Temperature: ${temperature.toFixed(2)}`}>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="w-full accent-violet-600"
            />
            <div className="flex justify-between text-xs text-slate-400 mt-1">
              <span>0 — preciso</span>
              <span>1 — creativo</span>
            </div>
          </Field>

          {/* Max tokens */}
          <Field label="Max tokens de respuesta">
            <Input
              type="number"
              min={256}
              max={8192}
              step={256}
              value={maxTokens}
              onChange={(e) => setMaxTokens(parseInt(e.target.value, 10))}
            />
          </Field>
        </CardContent>
      </Card>

      {/* Actions */}
      {errorMsg && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {errorMsg}
        </div>
      )}

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving}>
          <Save className="h-4 w-4" />
          {saving ? 'Guardando y rebuildeando...' : 'Guardar cambios'}
        </Button>
      </div>
    </div>
  )
}
