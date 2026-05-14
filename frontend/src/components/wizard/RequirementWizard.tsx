import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  AgentMode, WizardState, WIZARD_DEFAULTS,
  applyToolReadiness, AVAILABLE_TOOLS, AVAILABLE_MODELS, ChannelType, ToolReadinessStatus, ToolRef,
  WizardAdvisorResponse,
} from '../../types/agent'
import { StepCrew } from './StepCrew'
import { WizardAdvisorPanel } from './WizardAdvisorPanel'

// ── Pasos del wizard ──────────────────────────────────────────────────────────
const STEPS_SINGLE = [
  { id: 0, title: 'Tipo de agente',    description: 'Elegí cómo querés que funcione' },
  { id: 1, title: 'Identidad',         description: 'Nombre, objetivo y descripción' },
  { id: 2, title: 'Herramientas',      description: 'Qué puede hacer el agente' },
  { id: 3, title: 'Memoria y canales', description: 'Cómo recuerda y dónde se despliega' },
  { id: 4, title: 'Modelo',            description: 'LLM y parámetros de generación' },
  { id: 5, title: 'Revisión',          description: 'Confirmá antes de generar el diseño' },
]

const STEPS_CREW = [
  { id: 0, title: 'Tipo de agente',    description: 'Elegí cómo querés que funcione' },
  { id: 1, title: 'Identidad',         description: 'Nombre y objetivo del equipo' },
  { id: 2, title: 'Equipo de agentes', description: 'Roles, objetivos y herramientas' },
  { id: 3, title: 'Memoria y canales', description: 'Cómo recuerda y dónde se despliega' },
  { id: 4, title: 'Modelo',            description: 'LLM base del equipo' },
  { id: 5, title: 'Revisión',          description: 'Confirmá antes de generar el diseño' },
]

interface Props {
  onComplete: (state: WizardState) => void
}

export function RequirementWizard({ onComplete }: Props) {
  const [state, setState] = useState<WizardState>(WIZARD_DEFAULTS)
  const [generating, setGenerating] = useState(false)
  const [toolReadiness, setToolReadiness] = useState<Record<string, ToolReadinessStatus>>({})
  const [toolReadinessRows, setToolReadinessRows] = useState<ToolReadinessStatus[]>([])
  const [aiAssistEnabled, setAiAssistEnabled] = useState(false)
  const [advisorLoading, setAdvisorLoading] = useState(false)
  const [advisorError, setAdvisorError] = useState('')
  const [advisorResult, setAdvisorResult] = useState<WizardAdvisorResponse | null>(null)

  const STEPS = state.mode === 'crew' ? STEPS_CREW : STEPS_SINGLE
  const toolsCatalog = AVAILABLE_TOOLS.map(tool => applyToolReadiness(tool, toolReadiness))

  const update = (patch: Partial<WizardState>) =>
    setState(prev => mergeWizardPatch(prev, patch))

  const next = () => setState(prev => ({ ...prev, step: Math.min(prev.step + 1, STEPS.length - 1) }))
  const back = () => setState(prev => ({ ...prev, step: Math.max(prev.step - 1, 0) }))

  const handleSubmit = async () => {
    setGenerating(true)
    onComplete(state)
  }

  const analyzeWithAdvisor = async (finalReview = false) => {
    setAdvisorLoading(true)
    setAdvisorError('')
    try {
      const { wizardAdvisorApi } = await import('../../lib/api')
      const result = await wizardAdvisorApi.analyze({
        step: state.step,
        step_key: getStepKey(STEPS[state.step]?.title || ''),
        final_review: finalReview,
        wizard_state: state,
        available_tools: toolsCatalog,
        tool_readiness: toolReadinessRows,
        available_models: AVAILABLE_MODELS,
      })
      setAdvisorResult(result)
    } catch (e: any) {
      setAdvisorError(e.response?.data?.detail || 'No se pudo analizar el diseño con IA.')
    } finally {
      setAdvisorLoading(false)
    }
  }

  const applyAdvisorPatch = (patch: Partial<WizardState>) => {
    update(patch)
    setAdvisorResult(null)
  }

  useEffect(() => {
    import('../../lib/api').then(({ systemApi }) =>
      systemApi.getToolReadiness()
        .then((rows) => {
          setToolReadinessRows(Array.isArray(rows) ? rows : [])
          const readinessMap = Object.fromEntries(
            (Array.isArray(rows) ? rows : []).map((row) => [row.name, row] as const)
          )
          setToolReadiness(readinessMap)
        })
        .catch(() => {
          setToolReadiness({})
        })
    )
  }, [])

  return (
    <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 lg:grid-cols-[minmax(0,42rem)_20rem]">
      <div>
      {/* Stepper */}
      <div className="flex items-center gap-1 mb-10">
        {STEPS.map((s, i) => (
          <div key={s.id} className="flex items-center flex-1">
            <button
              onClick={() => i < state.step && update({ step: i })}
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                i === state.step
                  ? 'bg-violet-600 text-white'
                  : i < state.step
                  ? 'bg-violet-200 text-violet-700 cursor-pointer'
                  : 'bg-gray-100 text-gray-400'
              }`}
            >
              {i < state.step ? '✓' : i + 1}
            </button>
            {i < STEPS.length - 1 && (
              <div className={`h-0.5 flex-1 mx-1 ${i < state.step ? 'bg-violet-300' : 'bg-gray-200'}`} />
            )}
          </div>
        ))}
      </div>

      {/* Step title */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-gray-900">{STEPS[state.step].title}</h2>
        <p className="text-sm text-gray-500 mt-1">{STEPS[state.step].description}</p>
      </div>

      {/* Step content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={state.step}
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -16 }}
          transition={{ duration: 0.18 }}
        >
          {state.step === 0 && <StepMode state={state} update={update} />}
          {state.step === 1 && <StepIdentity state={state} update={update} />}
          {state.step === 2 && state.mode === 'single' && <StepTools state={state} update={update} toolsCatalog={toolsCatalog} />}
          {state.step === 2 && state.mode === 'crew'   && <StepCrew  state={state} update={update} toolsCatalog={toolsCatalog} />}
          {state.step === 3 && <StepMemoryChannels state={state} update={update} />}
          {state.step === 4 && <StepModel state={state} update={update} />}
          {state.step === 5 && <StepReview state={state} />}
        </motion.div>
      </AnimatePresence>

      {/* Navigation */}
      <div className="flex justify-between mt-8 pt-4 border-t border-gray-100">
        <button
          onClick={back}
          disabled={state.step === 0}
          className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-30 transition-colors"
        >
          ← Anterior
        </button>

        {state.step < STEPS.length - 1 ? (
          <button
            onClick={next}
            disabled={!isStepValid(state)}
            className="px-5 py-2 bg-violet-600 text-white text-sm rounded-lg hover:bg-violet-700 disabled:opacity-40 transition-colors"
          >
            Siguiente →
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={generating}
            className="px-5 py-2 bg-violet-600 text-white text-sm rounded-lg hover:bg-violet-700 disabled:opacity-40 transition-colors flex items-center gap-2"
          >
            {generating ? (
              <><span className="animate-spin">⟳</span> Generando diseño...</>
            ) : (
              'Generar diseño →'
            )}
          </button>
        )}
      </div>
      </div>

      <WizardAdvisorPanel
        enabled={aiAssistEnabled}
        loading={advisorLoading}
        result={advisorResult}
        error={advisorError}
        onToggle={setAiAssistEnabled}
        onAnalyze={analyzeWithAdvisor}
        onApplyPatch={applyAdvisorPatch}
      />
    </div>
  )
}


// ── Paso 0: Tipo de agente ────────────────────────────────────────────────────

function StepMode({ state, update }: StepProps) {
  const options: Array<{ mode: AgentMode; title: string; description: string; icon: string }> = [
    {
      mode: 'single',
      title: 'Agente simple',
      description: 'Un agente con herramientas que responde preguntas, ejecuta tareas y usa APIs. Ideal para asistentes, bots de soporte, automatizaciones.',
      icon: '◎',
    },
    {
      mode: 'crew',
      title: 'Equipo de agentes',
      description: 'Varios agentes con roles especializados que colaboran para resolver tareas complejas. Ideal para investigación, análisis multi-paso, workflows largos.',
      icon: '⬡',
    },
  ]

  return (
    <div className="space-y-3">
      {options.map(opt => (
        <button
          key={opt.mode}
          onClick={() => update({ mode: opt.mode })}
          className={`w-full text-left p-5 rounded-xl border-2 transition-all ${
            state.mode === opt.mode
              ? 'border-violet-500 bg-violet-50'
              : 'border-gray-200 hover:border-violet-300 bg-white'
          }`}
        >
          <div className="flex items-start gap-3">
            <span className="text-2xl mt-0.5">{opt.icon}</span>
            <div>
              <div className="font-semibold text-gray-900">{opt.title}</div>
              <div className="text-sm text-gray-500 mt-1 leading-relaxed">{opt.description}</div>
            </div>
            {state.mode === opt.mode && (
              <span className="ml-auto text-violet-500 text-lg">✓</span>
            )}
          </div>
        </button>
      ))}
    </div>
  )
}


// ── Paso 1: Identidad ─────────────────────────────────────────────────────────

function StepIdentity({ state, update }: StepProps) {
  return (
    <div className="space-y-5">
      <Field label="Nombre del agente" required>
        <input
          type="text"
          value={state.name}
          onChange={e => update({ name: e.target.value })}
          placeholder="ej: Asistente de soporte técnico"
          className={inputCls}
        />
      </Field>

      <Field label="Objetivo principal" required hint="¿Qué problema resuelve este agente?">
        <textarea
          value={state.goal}
          onChange={e => update({ goal: e.target.value })}
          placeholder="ej: Responder consultas técnicas de clientes sobre productos industriales, escalar a humanos cuando no puede resolver."
          rows={3}
          className={inputCls}
        />
      </Field>

      <Field label="Descripción" hint="Contexto adicional para el diseño (opcional)">
        <textarea
          value={state.description}
          onChange={e => update({ description: e.target.value })}
          placeholder="ej: El agente atiende a operadores de planta. Tiene acceso a manuales técnicos y a la base de datos de tickets."
          rows={2}
          className={inputCls}
        />
      </Field>

      <Field label="Restricciones" hint="Una por línea. Ej: No revelar precios, no modificar datos de producción">
        <textarea
          value={state.constraints.join('\n')}
          onChange={e => update({ constraints: e.target.value.split('\n').filter(Boolean) })}
          rows={2}
          className={inputCls}
          placeholder="No revelar información confidencial&#10;Solo responder en español"
        />
      </Field>
    </div>
  )
}


// ── Paso 2: Herramientas ──────────────────────────────────────────────────────

function StepTools({ state, update, toolsCatalog }: StepProps & { toolsCatalog: typeof AVAILABLE_TOOLS }) {
  const [customTools, setCustomTools] = useState<Array<{ id: string; name: string; description: string; is_active: boolean }>>([])
  const [loadError, setLoadError] = useState('')
  const selectedBuiltinTools = toolsCatalog.filter(tool => state.tools.some(t => t.name === tool.name))
  const selectedNeedsSetup = selectedBuiltinTools.filter(tool => tool.state === 'needs_config')
  const selectedLimited = selectedBuiltinTools.filter(tool => tool.frameworks.langchain === 'limited')

  useEffect(() => {
    import('../../lib/api').then(({ customToolsApi }) =>
      customToolsApi.list()
        .then(data => { if (Array.isArray(data)) setCustomTools(data.filter((t: any) => t.is_active)) })
        .catch(() => setLoadError('No se pudieron cargar las custom tools. Las tools de librería siguen disponibles.'))
    )
  }, [])

  const toggleTool = (name: string, source: 'library' | 'custom') => {
    const exists = state.tools.find(t => t.name === name)
    if (exists) {
      update({ tools: state.tools.filter(t => t.name !== name) })
    } else {
      const newTool: ToolRef = { name, source, config: {} }
      update({ tools: [...state.tools, newTool] })
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500">
        Seleccioná las herramientas que el agente puede usar.
      </p>

      {loadError && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
          {loadError}
        </div>
      )}

      {/* Tools de librería */}
      <div>
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Librería built-in</p>
        <div className="space-y-2">
          {toolsCatalog.map(tool => {
            const selected = state.tools.some(t => t.name === tool.name)
            const frameworkState = tool.frameworks.langchain
            const unsupported = frameworkState === 'unsupported'
            const frameworkTone =
              frameworkState === 'ready'
                ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
                : frameworkState === 'limited'
                ? 'text-amber-700 bg-amber-50 border-amber-200'
                : 'text-rose-700 bg-rose-50 border-rose-200'
            return (
              <button
                key={tool.name}
                type="button"
                onClick={() => toggleTool(tool.name, 'library')}
                disabled={unsupported}
                className={`w-full flex items-center gap-3 p-4 rounded-lg border transition-all ${
                  selected ? 'border-violet-400 bg-violet-50' : 'border-gray-200 hover:border-violet-200'
                } ${unsupported ? 'opacity-50 cursor-not-allowed hover:border-gray-200' : ''}`}
              >
                <div className={`w-4 h-4 rounded border-2 flex items-center justify-center ${
                  selected ? 'border-violet-500 bg-violet-500' : 'border-gray-300'
                }`}>
                  {selected && <span className="text-white text-xs">✓</span>}
                </div>
                <div className="text-left flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-medium text-gray-800">{tool.name}</div>
                    <span className="text-[11px] text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                      {tool.category}
                    </span>
                    <span className={`text-[11px] px-2 py-0.5 rounded-full border ${frameworkTone}`}>
                      LangChain: {frameworkState === 'ready' ? 'lista' : frameworkState === 'limited' ? 'limitada' : 'no soportada'}
                    </span>
                    <span className="text-[11px] text-slate-600 bg-slate-100 px-2 py-0.5 rounded-full">
                      {tool.state_label}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500 mt-1">{tool.description}</div>
                  {tool.setup_hint && <div className="text-[11px] text-amber-700 mt-1">{tool.setup_hint}</div>}
                  {unsupported && (
                    <div className="text-[11px] text-rose-700 mt-1">
                      Esta tool no está disponible para agentes simples con LangChain.
                    </div>
                  )}
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {(selectedNeedsSetup.length > 0 || selectedLimited.length > 0) && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-800 space-y-1">
          {selectedNeedsSetup.length > 0 && (
            <div>
              Tools con configuraciÃ³n pendiente: <strong>{selectedNeedsSetup.map(tool => tool.name).join(', ')}</strong>.
            </div>
          )}
          {selectedLimited.length > 0 && (
            <div>
              Algunas tools tienen compatibilidad parcial en este framework: <strong>{selectedLimited.map(tool => tool.name).join(', ')}</strong>.
            </div>
          )}
        </div>
      )}

      {/* Custom tools del tenant */}
      {customTools.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Mis Tools</p>
          <div className="space-y-2">
            {customTools.map(tool => {
              const selected = state.tools.some(t => t.name === tool.name)
              return (
                <button
                  key={tool.name}
                  onClick={() => toggleTool(tool.name, 'custom')}
                  className={`w-full flex items-center gap-3 p-4 rounded-lg border transition-all ${
                    selected ? 'border-violet-400 bg-violet-50' : 'border-gray-200 hover:border-violet-200'
                  }`}
                >
                  <div className={`w-4 h-4 rounded border-2 flex items-center justify-center ${
                    selected ? 'border-violet-500 bg-violet-500' : 'border-gray-300'
                  }`}>
                    {selected && <span className="text-white text-xs">✓</span>}
                  </div>
                  <div className="text-left flex-1">
                    <div className="text-sm font-medium text-gray-800">{tool.name}</div>
                    <div className="text-xs text-gray-500">{tool.description}</div>
                  </div>
                  <span className="text-xs text-violet-600 bg-violet-50 border border-violet-200 px-2 py-0.5 rounded-full">
                    custom
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      )}

    </div>
  )
}


// ── Paso 3: Memoria y canales ─────────────────────────────────────────────────

function StepMemoryChannels({ state, update }: StepProps) {
  const channels: Array<{ id: ChannelType; label: string; badge?: string }> = [
    { id: 'web_chat',  label: 'Web chat embebible' },
    { id: 'whatsapp',  label: 'WhatsApp',  badge: 'Requiere Twilio' },
    { id: 'telegram',  label: 'Telegram',  badge: 'Requiere bot token' },
    { id: 'slack',     label: 'Slack',     badge: 'v2' },
    { id: 'rest_api',  label: 'Solo API REST' },
  ]

  const toggleChannel = (ch: ChannelType) => {
    const has = state.channels.includes(ch)
    if (has) {
      update({ channels: state.channels.filter(c => c !== ch) })
    } else {
      update({ channels: [...state.channels, ch] })
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <label className="text-sm font-medium text-gray-700">Canales de despliegue</label>
        <div className="mt-2 space-y-2">
          {channels.map(ch => (
            <button
              key={ch.id}
              onClick={() => toggleChannel(ch.id)}
              className={`w-full flex items-center gap-3 p-3 rounded-lg border transition-all ${
                state.channels.includes(ch.id)
                  ? 'border-violet-400 bg-violet-50'
                  : 'border-gray-200 hover:border-violet-200'
              }`}
            >
              <div className={`w-4 h-4 rounded border-2 flex items-center justify-center ${
                state.channels.includes(ch.id) ? 'border-violet-500 bg-violet-500' : 'border-gray-300'
              }`}>
                {state.channels.includes(ch.id) && <span className="text-white text-xs">✓</span>}
              </div>
              <span className="text-sm text-gray-800 flex-1 text-left">{ch.label}</span>
              {ch.badge && (
                <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">{ch.badge}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      <Field label="Memoria">
        <select
          value={state.memory.type}
          onChange={e => update({ memory: { ...state.memory, type: e.target.value as MemoryType } })}
          className={inputCls}
        >
          <option value="none">Sin memoria — cada mensaje es independiente</option>
          <option value="session">Por sesión — recuerda mientras la conversación está activa (Redis)</option>
          <option value="persistent">Persistente — recuerda entre sesiones (PostgreSQL)</option>
        </select>
      </Field>

      <div className="flex items-center gap-3 p-4 rounded-lg border border-gray-200">
        <input
          type="checkbox"
          id="rag-enabled"
          checked={state.rag.enabled}
          onChange={e => update({ rag: { ...state.rag, enabled: e.target.checked } })}
          className="w-4 h-4 accent-violet-600"
        />
        <label htmlFor="rag-enabled" className="text-sm text-gray-800 cursor-pointer">
          <span className="font-medium">Habilitar RAG</span>
          <span className="text-gray-500 ml-2">— el agente podrá consultar documentos o datos propios</span>
        </label>
      </div>
    </div>
  )
}


// ── Paso 4: Modelo ────────────────────────────────────────────────────────────

function StepModel({ state, update }: StepProps) {
  const [keys, setKeys] = useState<any[]>([])
  const [keysError, setKeysError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    import('../../lib/api').then(({ llmKeysApi }) =>
      llmKeysApi.list()
        .then(data => { if (Array.isArray(data)) setKeys(data) })
        .catch(() => setKeysError('No se pudieron cargar las llaves de la Bóveda IA.'))
        .finally(() => setLoading(false))
    )
  }, [])

  // Construir lista de modelos desde la Bóveda: { id, name, providerId, keyId }
  const availableModels = keys.flatMap(k =>
    (k.models || []).map(model => ({
      id: model.id,
      name: model.id,
      providerId: k.provider,
      keyId: k.id,
      keyName: k.name,
      isDefault: k.is_default,
    }))
  )

  // Llave seleccionada: la que corresponde al modelo elegido
  const selectedModelEntry = availableModels.find(m => m.id === state.model_params.model)
  const keysForProvider = selectedModelEntry
    ? keys.filter(k => k.provider === selectedModelEntry.providerId)
    : []

  // Si el modelo actual ya no está disponible, resetear al primero
  useEffect(() => {
    if (!loading && availableModels.length > 0 && !availableModels.find(m => m.id === state.model_params.model)) {
      const first = availableModels[0]
      update({ model_params: { ...state.model_params, model: first.id, provider: first.providerId, llm_key_id: undefined } })
    }
  }, [loading])

  return (
    <div className="space-y-5">
      {keysError && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
          {keysError}
        </div>
      )}

      {!loading && availableModels.length === 0 && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          No tenés ninguna llave de proveedor LLM configurada.{' '}
          <strong>Andá a Bóveda IA</strong> y agregá al menos una antes de continuar.
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-6">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
        </div>
      ) : (
        <>
          <Field label="Modelo LLM">
            <select
              value={state.model_params.model}
              onChange={e => {
                const model = availableModels.find(m => m.id === e.target.value)
                update({
                  model_params: {
                    ...state.model_params,
                    model: e.target.value,
                    provider: model?.providerId,
                    llm_key_id: undefined,
                  },
                })
              }}
              className={inputCls}
              disabled={availableModels.length === 0}
            >
              {availableModels.length === 0
                ? <option value="">— Sin modelos — agregá en Bóveda IA —</option>
                : availableModels.map(m => (
                    <option key={`${m.keyId}-${m.id}`} value={m.id}>
                      {m.id} ({m.keyName})
                    </option>
                  ))
              }
            </select>
          </Field>

          <Field label="Llave de IA" hint="La llave predeterminada del proveedor se usa automáticamente.">
            <select
              value={state.model_params.llm_key_id || ''}
              onChange={e => update({ model_params: { ...state.model_params, llm_key_id: e.target.value || undefined } })}
              className={inputCls}
            >
              <option value="">★ Usar la llave predeterminada</option>
              {keysForProvider.map(k => (
                <option key={k.id} value={k.id}>{k.name} ({k.truncated_key}){k.is_default ? ' ★' : ''}</option>
              ))}
            </select>
          </Field>

          <Field label={`Temperatura: ${state.model_params.temperature}`} hint="0 = determinístico · 1 = creativo">
            <input
              type="range" min="0" max="1" step="0.05"
              value={state.model_params.temperature}
              onChange={e => update({ model_params: { ...state.model_params, temperature: parseFloat(e.target.value) } })}
              className="w-full accent-violet-600"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>Preciso</span><span>Balanceado</span><span>Creativo</span>
            </div>
          </Field>

          <Field label={`Máximo de tokens: ${state.model_params.max_tokens}`}>
            <input
              type="range" min="256" max="8192" step="256"
              value={state.model_params.max_tokens}
              onChange={e => update({ model_params: { ...state.model_params, max_tokens: parseInt(e.target.value) } })}
              className="w-full accent-violet-600"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>256</span><span>4096</span><span>8192</span>
            </div>
          </Field>
        </>
      )}
    </div>
  )
}


// ── Paso 5: Revisión ──────────────────────────────────────────────────────────

function StepReview({ state }: { state: WizardState }) {
  const rows: Array<{ label: string; value: string }> = [
    { label: 'Nombre',      value: state.name || '—' },
    { label: 'Modo',        value: state.mode === 'single' ? 'Agente simple' : 'Equipo de agentes' },
    { label: 'Objetivo',    value: state.goal || '—' },
    { label: 'Herramientas', value: state.tools.map(t => t.name).join(', ') || 'Ninguna' },
    { label: 'Memoria',     value: state.memory.type },
    { label: 'Canales',     value: state.channels.join(', ') },
    { label: 'RAG',         value: state.rag.enabled ? 'Sí' : 'No' },
    { label: 'Modelo',      value: state.model_params.model },
    { label: 'Temperatura', value: String(state.model_params.temperature) },
  ]
  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-500 mb-4">
        Revisá la configuración antes de que el sistema genere el diseño del agente. Este proceso puede demorar unos segundos.
      </p>
      <div className="rounded-xl border border-gray-200 overflow-hidden">
        {rows.map((row, i) => (
          <div key={row.label} className={`flex px-4 py-3 text-sm ${i % 2 === 0 ? 'bg-gray-50' : 'bg-white'}`}>
            <span className="text-gray-500 w-36 shrink-0">{row.label}</span>
            <span className="text-gray-900 font-medium">{row.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}


// ── Helpers ───────────────────────────────────────────────────────────────────

type MemoryType = 'none' | 'session' | 'persistent' | 'summary'

interface StepProps {
  state: WizardState
  update: (patch: Partial<WizardState>) => void
}

function Field({ label, children, hint, required }: {
  label: string; children: React.ReactNode; hint?: string; required?: boolean
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-gray-700">
        {label} {required && <span className="text-red-400">*</span>}
      </label>
      {hint && <p className="text-xs text-gray-400">{hint}</p>}
      {children}
    </div>
  )
}

const inputCls = "w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-shadow"

function isStepValid(state: WizardState): boolean {
  switch (state.step) {
    case 0: return !!state.mode
    case 1: return state.name.length >= 2 && state.goal.length >= 10
    default: return true
  }
}

function mergeWizardPatch(prev: WizardState, patch: Partial<WizardState>): WizardState {
  return {
    ...prev,
    ...patch,
    memory: patch.memory ? { ...prev.memory, ...patch.memory } : prev.memory,
    rag: patch.rag ? { ...prev.rag, ...patch.rag } : prev.rag,
    model_params: patch.model_params ? { ...prev.model_params, ...patch.model_params } : prev.model_params,
  }
}

function getStepKey(title: string): string {
  return title
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '') || 'unknown'
}
