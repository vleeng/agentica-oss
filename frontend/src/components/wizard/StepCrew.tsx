import { useState } from 'react'
import type { AgentRoleSpec, ToolRef, WizardState } from '../../types/agent'
import { AVAILABLE_MODELS, AVAILABLE_TOOLS } from '../../types/agent'

interface Props {
  state: WizardState
  update: (patch: Partial<WizardState>) => void
}

const ROLE_PRESETS = [
  { role: 'Investigador',    goal: 'Buscar y recopilar información relevante sobre el tema',
    backstory: 'Experto en investigación con acceso a múltiples fuentes de información.',
    tools: ['web_search'] },
  { role: 'Analista',       goal: 'Analizar la información recopilada y extraer insights',
    backstory: 'Especialista en análisis de datos con capacidad de síntesis.',
    tools: ['calculator'] },
  { role: 'Redactor',       goal: 'Producir contenido claro y bien estructurado',
    backstory: 'Escritor profesional con habilidad para comunicar ideas complejas.',
    tools: [] },
  { role: 'Coordinador',    goal: 'Coordinar el trabajo del equipo y asegurar coherencia',
    backstory: 'Líder de equipo con visión general del proyecto.',
    tools: [] },
  { role: 'Verificador',    goal: 'Revisar y validar los resultados antes de entregarlos',
    backstory: 'Experto en control de calidad con atención al detalle.',
    tools: ['web_search'] },
]

const PROCESS_OPTIONS = [
  { value: 'sequential',    label: 'Secuencial',    desc: 'Cada agente trabaja en orden, el resultado pasa al siguiente' },
  { value: 'hierarchical',  label: 'Jerárquico',    desc: 'Un agente manager coordina y delega al resto del equipo' },
  { value: 'parallel',      label: 'Paralelo',      desc: 'Todos los agentes trabajan simultáneamente' },
]

export function StepCrew({ state, update }: Props) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null)

  const addRole = (preset?: typeof ROLE_PRESETS[0]) => {
    const newRole: AgentRoleSpec = {
      name:              `agent_${state.agents.length + 1}`,
      role:              preset?.role || '',
      goal:              preset?.goal || '',
      backstory:         preset?.backstory || '',
      tools:             (preset?.tools || []).map(t => ({ name: t, source: 'library' as const, config: {} })),
      allow_delegation:  false,
    }
    update({ agents: [...state.agents, newRole] })
    setEditingIndex(state.agents.length)
  }

  const updateRole = (i: number, patch: Partial<AgentRoleSpec>) => {
    const updated = state.agents.map((a, idx) => idx === i ? { ...a, ...patch } : a)
    update({ agents: updated })
  }

  const removeRole = (i: number) => {
    update({ agents: state.agents.filter((_, idx) => idx !== i) })
    setEditingIndex(null)
  }

  return (
    <div className="space-y-6">

      {/* Proceso del equipo */}
      <div>
        <label className="text-sm font-medium text-gray-700 block mb-2">Proceso del equipo</label>
        <div className="space-y-2">
          {PROCESS_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => update({ process: opt.value as any })}
              className={`w-full flex items-start gap-3 p-3 rounded-lg border text-left transition-all ${
                state.process === opt.value
                  ? 'border-violet-400 bg-violet-50'
                  : 'border-gray-200 hover:border-violet-200'
              }`}
            >
              <div className={`mt-0.5 w-4 h-4 rounded-full border-2 flex-shrink-0 ${
                state.process === opt.value ? 'border-violet-500 bg-violet-500' : 'border-gray-300'
              }`} />
              <div>
                <div className="text-sm font-medium text-gray-800">{opt.label}</div>
                <div className="text-xs text-gray-500">{opt.desc}</div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Roles del equipo */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium text-gray-700">
            Roles del equipo ({state.agents.length})
          </label>
          <span className="text-xs text-gray-400">Mínimo 2 roles</span>
        </div>

        {/* Roles existentes */}
        <div className="space-y-2 mb-3">
          {state.agents.map((agent, i) => (
            <div key={i}>
              <div
                className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                  editingIndex === i ? 'border-violet-400 bg-violet-50' : 'border-gray-200 hover:border-violet-200'
                }`}
                onClick={() => setEditingIndex(editingIndex === i ? null : i)}
              >
                <div className="w-8 h-8 rounded-full bg-violet-100 text-violet-700 text-xs font-bold flex items-center justify-center flex-shrink-0">
                  {i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800 truncate">
                    {agent.role || 'Sin nombre'}
                  </div>
                  <div className="text-xs text-gray-500 truncate">{agent.goal || 'Sin objetivo'}</div>
                </div>
                <div className="flex items-center gap-2">
                  {agent.tools.length > 0 && (
                    <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                      {agent.tools.length} tool{agent.tools.length > 1 ? 's' : ''}
                    </span>
                  )}
                  <button
                    onClick={e => { e.stopPropagation(); removeRole(i) }}
                    className="text-gray-400 hover:text-red-500 transition-colors text-lg leading-none"
                  >
                    ×
                  </button>
                </div>
              </div>

              {/* Editor inline del rol */}
              {editingIndex === i && (
                <div className="mt-1 p-4 border border-violet-200 rounded-lg bg-white space-y-3">
                  <RoleEditor agent={agent} onChange={patch => updateRole(i, patch)} />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Agregar rol */}
        <div>
          <p className="text-xs text-gray-500 mb-2">Agregar desde preset:</p>
          <div className="flex flex-wrap gap-2 mb-2">
            {ROLE_PRESETS.map(preset => (
              <button
                key={preset.role}
                onClick={() => addRole(preset)}
                className="text-xs px-3 py-1.5 border border-gray-200 rounded-full hover:border-violet-300 hover:bg-violet-50 transition-colors"
              >
                + {preset.role}
              </button>
            ))}
          </div>
          <button
            onClick={() => addRole()}
            className="text-sm text-violet-600 hover:text-violet-800 transition-colors"
          >
            + Crear rol personalizado
          </button>
        </div>
      </div>

      {/* Manager LLM (solo para jerárquico) */}
      {state.process === 'hierarchical' && (
        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">
            Modelo del manager
          </label>
          <p className="text-xs text-gray-500 mb-2">
            El agente manager usará este modelo para coordinar al equipo.
          </p>
          <select
            value={state.model_params.model}
            onChange={e => {
              const model = AVAILABLE_MODELS.find(m => m.id === e.target.value)
              update({
                model_params: {
                  ...state.model_params,
                  model: e.target.value,
                  provider: model?.providerId,
                  llm_key_id: undefined,
                },
              })
            }}
            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
          >
            {AVAILABLE_MODELS.map(model => (
              <option key={model.id} value={model.id}>{model.name} — {model.provider}</option>
            ))}
          </select>
        </div>
      )}
    </div>
  )
}


// ── Editor de un rol individual ───────────────────────────────────────────────

function RoleEditor({
  agent,
  onChange,
}: {
  agent: AgentRoleSpec
  onChange: (patch: Partial<AgentRoleSpec>) => void
}) {
  const inputCls = "w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"

  const toggleTool = (name: string) => {
    const has = agent.tools.some(t => t.name === name)
    if (has) {
      onChange({ tools: agent.tools.filter(t => t.name !== name) })
    } else {
      onChange({ tools: [...agent.tools, { name, source: 'library', config: {} }] })
    }
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Nombre interno</label>
          <input
            value={agent.name}
            onChange={e => onChange({ name: e.target.value.toLowerCase().replace(/\s+/g, '_') })}
            placeholder="ej: researcher"
            className={inputCls}
          />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Rol visible</label>
          <input
            value={agent.role}
            onChange={e => onChange({ role: e.target.value })}
            placeholder="ej: Investigador Senior"
            className={inputCls}
          />
        </div>
      </div>

      <div>
        <label className="text-xs text-gray-500 mb-1 block">Objetivo</label>
        <input
          value={agent.goal}
          onChange={e => onChange({ goal: e.target.value })}
          placeholder="¿Qué debe lograr este agente?"
          className={inputCls}
        />
      </div>

      <div>
        <label className="text-xs text-gray-500 mb-1 block">Backstory (contexto del rol)</label>
        <textarea
          value={agent.backstory}
          onChange={e => onChange({ backstory: e.target.value })}
          rows={2}
          placeholder="Quién es este agente, su experiencia y estilo..."
          className={inputCls}
        />
      </div>

      <div>
        <label className="text-xs text-gray-500 mb-2 block">Herramientas</label>
        <div className="flex flex-wrap gap-2">
          {AVAILABLE_TOOLS.map(tool => {
            const selected = agent.tools.some(t => t.name === tool.name)
            const frameworkState = tool.frameworks.crewai
            const frameworkTone =
              frameworkState === 'ready'
                ? 'border-emerald-200 text-emerald-700 bg-emerald-50'
                : frameworkState === 'limited'
                ? 'border-amber-200 text-amber-700 bg-amber-50'
                : 'border-rose-200 text-rose-700 bg-rose-50'
            return (
              <div key={tool.name} className="space-y-1">
                <button
                  onClick={() => toggleTool(tool.name)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-all ${
                    selected
                      ? 'border-violet-400 bg-violet-50 text-violet-700'
                      : 'border-gray-200 text-gray-600 hover:border-violet-200'
                  }`}
                >
                  {selected ? '✓ ' : ''}{tool.name}
                </button>
                <div className="flex flex-wrap gap-1">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full border ${frameworkTone}`}>
                    CrewAI: {frameworkState === 'ready' ? 'lista' : frameworkState === 'limited' ? 'limitada' : 'no soportada'}
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                    {tool.state_label}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
        <p className="text-[11px] text-gray-500 mt-2">
          Las tools marcadas como limitadas pueden necesitar ajustes de compatibilidad adicionales en CrewAI.
        </p>
      </div>

      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={agent.allow_delegation}
          onChange={e => onChange({ allow_delegation: e.target.checked })}
          className="accent-violet-600"
        />
        <span className="text-xs text-gray-600">
          Puede delegar tareas a otros agentes del equipo
        </span>
      </label>
    </div>
  )
}
