import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  AgentMode, WizardState, WIZARD_DEFAULTS,
  AVAILABLE_TOOLS, AVAILABLE_MODELS, ChannelType, ToolRef
} from '../../types/agent'
import { StepCrew } from './StepCrew'

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

  const STEPS = state.mode === 'crew' ? STEPS_CREW : STEPS_SINGLE

  const update = (patch: Partial<WizardState>) =>
    setState(prev => ({ ...prev, ...patch }))

  const next = () => setState(prev => ({ ...prev, step: Math.min(prev.step + 1, STEPS.length - 1) }))
  const back = () => setState(prev => ({ ...prev, step: Math.max(prev.step - 1, 0) }))

  const handleSubmit = async () => {
    setGenerating(true)
    onComplete(state)
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
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
          {state.step === 2 && state.mode === 'single' && <StepTools state={state} update={update} />}
          {state.step === 2 && state.mode === 'crew'   && <StepCrew  state={state} update={update} />}
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

function StepTools({ state, update }: StepProps) {
  const [customTools, setCustomTools] = useState<Array<{ id: string; name: string; description: string; is_active: boolean }>>([])

  useEffect(() => {
    fetch('/api/v1/tools/custom/', {
      headers: { Authorization: `Bearer ${localStorage.getItem('agentica_token')}` }
    })
      .then(r => r.json())
      .then(data => { if (Array.isArray(data)) setCustomTools(data.filter((t: any) => t.is_active)) })
      .catch(() => {})
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

      {/* Tools de librería */}
      <div>
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Librería built-in</p>
        <div className="space-y-2">
          {AVAILABLE_TOOLS.map(tool => {
            const selected = state.tools.some(t => t.name === tool.name)
            return (
              <button
                key={tool.name}
                onClick={() => toggleTool(tool.name, 'library')}
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
                <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                  {tool.category}
                </span>
              </button>
            )
          })}
        </div>
      </div>

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

      {state.mode === 'single' && (
        <Field label="Nivel de autonomía" hint="Qué tanto decide el agente sin pedir confirmación">
          <select
            value={state.autonomy_level}
            onChange={e => update({ autonomy_level: e.target.value as typeof state.autonomy_level })}
            className={inputCls}
          >
            <option value="reactive">Reactivo — solo responde cuando lo invocan</option>
            <option value="semi">Semi-autónomo — puede hacer follow-up, pide confirmación en acciones importantes</option>
            <option value="autonomous">Autónomo — ejecuta sin pedir confirmación</option>
          </select>
        </Field>
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

  // Cargar llaves para mostrar
  useEffect(() => {
    fetch('/api/v1/keys/llm', {
      headers: { Authorization: `Bearer ${localStorage.getItem('agentica_token')}` }
    })
      .then(r => r.json())
      .then(data => {
        if (Array.isArray(data)) setKeys(data)
      })
      .catch(() => {})
  }, [])

  // Filtrar llaves segun el proveedor del modelo seleccionado
  const selectedProvider = state.model_params.model.startsWith('gpt') ? 'openai' : 'anthropic'
  const availableKeys = keys.filter(k => k.provider === selectedProvider)

  return (
    <div className="space-y-5">
      <Field label="Modelo LLM">
        <select
          value={state.model_params.model}
          onChange={e => update({ model_params: { ...state.model_params, model: e.target.value } })}
          className={inputCls}
        >
          {AVAILABLE_MODELS.map(m => (
            <option key={m.id} value={m.id}>{m.name} — {m.provider}</option>
          ))}
        </select>
      </Field>

      <Field label="Llave de IA (Opcional)" hint="Si no elige ninguna, se intentará usar la predeterminada del sistema.">
        <select
          value={state.model_params.llm_key_id || ''}
          onChange={e => update({ model_params: { ...state.model_params, llm_key_id: e.target.value || undefined } })}
          className={inputCls}
        >
          <option value="">-- Usar la llave predeterminada --</option>
          {availableKeys.map(k => (
            <option key={k.id} value={k.id}>{k.name} ({k.truncated_key}) {k.is_default && '★'}</option>
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
