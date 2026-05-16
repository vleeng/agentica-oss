import { useState, useEffect } from 'react'
import {
  skillsApi, mcpApi, knowledgeBasesApi, policiesApi, guardrailsApi,
} from '../../lib/api'
import type {
  Skill, MCPServer, KnowledgeBase, BehaviorPolicy, GuardrailRule,
  GuardrailRuleType, GuardrailAction,
} from '../../types/agent'

interface Props { agentId: string }

// ── Sección colapsable ────────────────────────────────────────────────────────
function Section({ title, badge, children }: { title: string; badge?: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true)
  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors">
        <span className="text-sm font-semibold text-gray-800 flex items-center gap-2">
          {title}
          {badge && <span className="text-xs font-normal bg-violet-100 text-violet-700 px-1.5 py-0.5 rounded-full">{badge}</span>}
        </span>
        <span className="text-gray-400">{open ? '▲' : '▼'}</span>
      </button>
      {open && <div className="p-4">{children}</div>}
    </div>
  )
}

// ── AgentConfigPanel ──────────────────────────────────────────────────────────
export function AgentConfigPanel({ agentId }: Props) {
  // Skills
  const [allSkills, setAllSkills] = useState<Skill[]>([])
  const [assignedSkills, setAssignedSkills] = useState<Skill[]>([])

  // MCPs
  const [allMcp, setAllMcp] = useState<MCPServer[]>([])
  const [assignedMcp, setAssignedMcp] = useState<MCPServer[]>([])

  // KBs
  const [allKbs, setAllKbs] = useState<KnowledgeBase[]>([])
  const [assignedKbs, setAssignedKbs] = useState<KnowledgeBase[]>([])

  // Policy
  const [policy, setPolicy] = useState<BehaviorPolicy>({
    tone: 'profesional', escalation_conditions: [], confirmation_triggers: [],
    format_requirements: '', custom_rules: [],
  })
  const [policyLoaded, setPolicyLoaded] = useState(false)
  const [savingPolicy, setSavingPolicy] = useState(false)

  // Guardrails
  const [rules, setRules] = useState<GuardrailRule[]>([])
  const [showRuleForm, setShowRuleForm] = useState(false)
  const [ruleForm, setRuleForm] = useState<Omit<GuardrailRule, 'id' | 'agent_id' | 'is_active'>>({
    name: '', rule_type: 'input_block', condition: {}, action: 'block', priority: 0,
  })
  const [conditionInput, setConditionInput] = useState('{"keywords": []}')
  const [condError, setCondError] = useState('')
  const [loading, setLoading] = useState(false)

  const [error, setError] = useState('')

  async function loadConfig() {
    setLoading(true)
    setError('')
    try {
      const [all, asgn, allM, asgnM, allK, asgnK, grs] = await Promise.all([
        skillsApi.list(), skillsApi.forAgent(agentId),
        mcpApi.list(), mcpApi.forAgent(agentId),
        knowledgeBasesApi.list(), knowledgeBasesApi.forAgent(agentId),
        guardrailsApi.list(agentId),
      ])
      setAllSkills(all); setAssignedSkills(asgn)
      setAllMcp(allM); setAssignedMcp(asgnM)
      setAllKbs(allK); setAssignedKbs(asgnK)
      setRules(grs)
    } catch {
      setError('Error cargando configuración')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadConfig()
    Promise.all([
      skillsApi.list(), skillsApi.forAgent(agentId),
      mcpApi.list(), mcpApi.forAgent(agentId),
      knowledgeBasesApi.list(), knowledgeBasesApi.forAgent(agentId),
      guardrailsApi.list(agentId),
    ]).then(([all, asgn, allM, asgnM, allK, asgnK, grs]) => {
      setAllSkills(all); setAssignedSkills(asgn)
      setAllMcp(allM); setAssignedMcp(asgnM)
      setAllKbs(allK); setAssignedKbs(asgnK)
      setRules(grs)
    }).catch(() => setError('Error cargando configuración'))

    policiesApi.get(agentId)
      .then(p => { setPolicy(p); setPolicyLoaded(true) })
      .catch(() => setPolicyLoaded(true)) // 404 es ok, usamos defaults
  }, [agentId])

  // ── Skills ────────────────────────────────────────────────────────────────
  async function toggleSkill(skill: Skill) {
    const isAssigned = assignedSkills.some(s => s.id === skill.id)
    try {
      if (isAssigned) {
        await skillsApi.unassignFromAgent(agentId, skill.id)
        setAssignedSkills(prev => prev.filter(s => s.id !== skill.id))
      } else {
        await skillsApi.assignToAgent(agentId, skill.id)
        setAssignedSkills(prev => [...prev, skill])
      }
    } catch { setError('Error actualizando skill') }
  }

  // ── MCPs ──────────────────────────────────────────────────────────────────
  async function toggleMcp(server: MCPServer) {
    const isAssigned = assignedMcp.some(s => s.id === server.id)
    try {
      if (isAssigned) {
        await mcpApi.unassignFromAgent(agentId, server.id)
        setAssignedMcp(prev => prev.filter(s => s.id !== server.id))
      } else {
        await mcpApi.assignToAgent(agentId, server.id)
        setAssignedMcp(prev => [...prev, server])
      }
    } catch { setError('Error actualizando servidor MCP') }
  }

  // ── KBs ───────────────────────────────────────────────────────────────────
  async function toggleKb(kb: KnowledgeBase) {
    if (kb.access_mode === 'global') return
    const isAssigned = assignedKbs.some(k => k.id === kb.id)
    try {
      if (isAssigned) {
        await knowledgeBasesApi.unassignFromAgent(agentId, kb.id)
      } else {
        await knowledgeBasesApi.assignToAgent(agentId, kb.id)
      }
      await loadConfig()
    } catch { setError('Error actualizando knowledge base') }
  }

  // ── Policy ────────────────────────────────────────────────────────────────
  async function savePolicy() {
    setSavingPolicy(true)
    try {
      const saved = await policiesApi.upsert(agentId, policy)
      setPolicy(saved)
    } catch { setError('Error guardando política') }
    finally { setSavingPolicy(false) }
  }

  // ── Guardrails ────────────────────────────────────────────────────────────
  async function createRule() {
    setCondError('')
    let cond: Record<string, unknown> = {}
    try { cond = JSON.parse(conditionInput) } catch { setCondError('JSON inválido'); return }
    try {
      const created = await guardrailsApi.create(agentId, { ...ruleForm, condition: cond })
      setRules(prev => [...prev, created])
      setShowRuleForm(false)
      setRuleForm({ name: '', rule_type: 'input_block', condition: {}, action: 'block', priority: 0 })
      setConditionInput('{"keywords": []}')
    } catch { setError('Error creando guardrail') }
  }

  async function toggleRule(rule: GuardrailRule) {
    try {
      const updated = await guardrailsApi.toggle(agentId, rule.id!)
      setRules(prev => prev.map(r => r.id === updated.id ? updated : r))
    } catch { setError('Error cambiando estado del guardrail') }
  }

  async function deleteRule(ruleId: string) {
    if (!confirm('¿Eliminar esta regla?')) return
    try {
      await guardrailsApi.delete(agentId, ruleId)
      setRules(prev => prev.filter(r => r.id !== ruleId))
    } catch { setError('Error eliminando guardrail') }
  }

  const RULE_TYPE_HINTS: Record<GuardrailRuleType, string> = {
    input_block:   '{"keywords": ["insulto", "hack"]}',
    output_filter: '{"keywords": ["confidencial", "precio"]}',
    length_limit:  '{"max_chars": 2000}',
    topic_restrict:'{"topics": ["política", "religión"]}',
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="flex justify-end">
        <button
          onClick={loadConfig}
          disabled={loading}
          className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50 rounded-lg disabled:opacity-40"
        >
          {loading ? 'Actualizando...' : 'Actualizar configuración'}
        </button>
      </div>
      {error && (
        <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg flex justify-between">
          {error}
          <button onClick={() => setError('')} className="text-red-400">✕</button>
        </div>
      )}

      {/* ── Skills ── */}
      <Section title="Skills" badge={`${assignedSkills.length} asignadas`}>
        {allSkills.length === 0 ? (
          <p className="text-xs text-gray-400">Sin skills en la librería. Creá una en <strong>Librería → Skills</strong>.</p>
        ) : (
          <div className="space-y-2">
            {allSkills.map(skill => {
              const assigned = assignedSkills.some(s => s.id === skill.id)
              return (
                <div key={skill.id} className={`flex items-start gap-3 p-3 rounded-lg border transition-all ${
                  assigned ? 'border-violet-400 bg-violet-50' : 'border-gray-200'
                }`}>
                  <button onClick={() => toggleSkill(skill)}
                    className={`w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 mt-0.5 ${
                      assigned ? 'border-violet-500 bg-violet-500' : 'border-gray-300'
                    }`}>
                    {assigned && <span className="text-white text-xs">✓</span>}
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-800">{skill.name}</div>
                    <div className="text-xs text-gray-500 truncate">{skill.objective}</div>
                    {skill.tools.length > 0 && (
                      <div className="text-xs text-violet-600 mt-0.5">
                        Tools: {skill.tools.map(t => t.name).join(', ')}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Section>

      {/* ── MCP Servers ── */}
      <Section title="Servidores MCP" badge={`${assignedMcp.length} asignados`}>
        {allMcp.length === 0 ? (
          <p className="text-xs text-gray-400">Sin servidores MCP. Registrá uno en <strong>Librería → MCPs</strong>.</p>
        ) : (
          <div className="space-y-2">
            {allMcp.map(server => {
              const assigned = assignedMcp.some(s => s.id === server.id)
              return (
                <div key={server.id} className={`flex items-start gap-3 p-3 rounded-lg border transition-all ${
                  assigned ? 'border-violet-400 bg-violet-50' : 'border-gray-200'
                }`}>
                  <button onClick={() => toggleMcp(server)}
                    className={`w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 mt-0.5 ${
                      assigned ? 'border-violet-500 bg-violet-500' : 'border-gray-300'
                    }`}>
                    {assigned && <span className="text-white text-xs">✓</span>}
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-800">{server.name}</div>
                    <div className="text-xs text-gray-500 truncate">{server.endpoint}</div>
                    <div className="text-xs text-gray-400">
                      {server.discovered_tools.length} tools · {server.transport.toUpperCase()}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Section>

      {/* ── Knowledge Bases ── */}
      <Section title="Bases de Conocimiento" badge={`${assignedKbs.length} disponibles`}>
        {allKbs.length === 0 ? (
          <p className="text-xs text-gray-400">Sin bases disponibles en este tenant. Si acabás de crear o editar una, usá <strong>Actualizar configuración</strong>.</p>
        ) : (
          <div className="space-y-2">
            {allKbs.map(kb => {
              const assigned = assignedKbs.some(k => k.id === kb.id)
              const isGlobal = kb.access_mode === 'global'
              const statusColor = { empty: 'text-gray-400', indexing: 'text-amber-500', ready: 'text-green-500', error: 'text-red-500' }[kb.status]
              return (
                <div key={kb.id} className={`flex items-start gap-3 p-3 rounded-lg border transition-all ${
                  assigned ? 'border-violet-400 bg-violet-50' : 'border-gray-200'
                }`}>
                  <button onClick={() => toggleKb(kb)}
                    disabled={isGlobal}
                    className={`w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 mt-0.5 ${
                      assigned ? 'border-violet-500 bg-violet-500' : 'border-gray-300'
                    } ${isGlobal ? 'cursor-not-allowed opacity-70' : ''}`}>
                    {assigned && <span className="text-white text-xs">✓</span>}
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-800">{kb.name}</div>
                    <div className={`text-xs ${statusColor}`}>{kb.status}</div>
                    <div className="text-xs text-gray-500">
                      {isGlobal ? 'Disponible para todos los agentes' : 'Disponible solo para agentes asignados'}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Section>

      {/* ── Behavior Policy ── */}
      <Section title="Política de Comportamiento">
        {policyLoaded && (
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Tono</label>
              <select value={policy.tone} onChange={e => setPolicy(p => ({ ...p, tone: e.target.value }))}
                className={inputCls}>
                <option value="profesional">Profesional</option>
                <option value="amigable">Amigable y cercano</option>
                <option value="formal">Formal y técnico</option>
                <option value="conciso">Conciso y directo</option>
                <option value="empático">Empático y cálido</option>
              </select>
            </div>

            <ListEditor
              label="Escalar a humano cuando"
              placeholder="ej: El usuario menciona emergencias médicas"
              items={policy.escalation_conditions}
              onChange={v => setPolicy(p => ({ ...p, escalation_conditions: v }))}
            />

            <ListEditor
              label="Pedir confirmación antes de"
              placeholder="ej: Enviar un email"
              items={policy.confirmation_triggers}
              onChange={v => setPolicy(p => ({ ...p, confirmation_triggers: v }))}
            />

            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Formato de respuesta</label>
              <textarea
                value={policy.format_requirements}
                onChange={e => setPolicy(p => ({ ...p, format_requirements: e.target.value }))}
                rows={2} className={inputCls}
                placeholder="ej: Usar Markdown, máximo 3 párrafos, incluir un resumen al inicio"
              />
            </div>

            <ListEditor
              label="Reglas adicionales"
              placeholder="ej: No revelar información de otros clientes"
              items={policy.custom_rules}
              onChange={v => setPolicy(p => ({ ...p, custom_rules: v }))}
            />

            <button onClick={savePolicy} disabled={savingPolicy}
              className="px-4 py-2 bg-violet-600 text-white text-sm rounded-lg hover:bg-violet-700 disabled:opacity-40">
              {savingPolicy ? 'Guardando...' : 'Guardar política'}
            </button>
          </div>
        )}
      </Section>

      {/* ── Guardrails ── */}
      <Section title="Guardrails" badge={`${rules.length} reglas`}>
        <div className="space-y-2 mb-3">
          {rules.length === 0 && !showRuleForm && (
            <p className="text-xs text-gray-400">Sin reglas de seguridad. Creá una para controlar inputs y outputs del agente.</p>
          )}
          {rules.map(rule => (
            <div key={rule.id} className={`flex items-center gap-3 px-3 py-2 rounded-lg border ${
              rule.is_active ? 'border-gray-200 bg-white' : 'border-gray-100 bg-gray-50 opacity-60'
            }`}>
              <button onClick={() => toggleRule(rule)}
                title={rule.is_active ? 'Desactivar' : 'Activar'}
                className={`w-3 h-3 rounded-full shrink-0 ${rule.is_active ? 'bg-green-500' : 'bg-gray-300'}`} />
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-gray-800">{rule.name}</span>
                <span className="ml-2 text-xs text-gray-400">{rule.rule_type}</span>
              </div>
              <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                rule.action === 'block' ? 'bg-red-100 text-red-600' :
                rule.action === 'warn'  ? 'bg-amber-100 text-amber-600' : 'bg-blue-100 text-blue-600'
              }`}>{rule.action}</span>
              <button onClick={() => deleteRule(rule.id!)} className="text-gray-300 hover:text-red-400 text-xs">✕</button>
            </div>
          ))}
        </div>

        {showRuleForm ? (
          <div className="border border-gray-200 rounded-lg p-3 space-y-3 bg-gray-50">
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-700">Nombre</label>
                <input value={ruleForm.name} onChange={e => setRuleForm(p => ({ ...p, name: e.target.value }))}
                  placeholder="ej: Bloquear insultos" className={inputCls} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-700">Tipo</label>
                <select value={ruleForm.rule_type}
                  onChange={e => {
                    const rt = e.target.value as GuardrailRuleType
                    setRuleForm(p => ({ ...p, rule_type: rt }))
                    setConditionInput(RULE_TYPE_HINTS[rt])
                  }}
                  className={inputCls}>
                  <option value="input_block">input_block — bloquea inputs con keywords</option>
                  <option value="output_filter">output_filter — filtra outputs con keywords</option>
                  <option value="length_limit">length_limit — limita longitud del texto</option>
                  <option value="topic_restrict">topic_restrict — restringe temas</option>
                </select>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Condición (JSON)</label>
              <textarea value={conditionInput}
                onChange={e => setConditionInput(e.target.value)}
                rows={2} className={`${inputCls} font-mono text-xs`} />
              {condError && <p className="text-xs text-red-500">{condError}</p>}
              <p className="text-xs text-gray-400">Ejemplo: {RULE_TYPE_HINTS[ruleForm.rule_type]}</p>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-700">Acción</label>
                <select value={ruleForm.action} onChange={e => setRuleForm(p => ({ ...p, action: e.target.value as GuardrailAction }))}
                  className={inputCls}>
                  <option value="block">block — bloquea la solicitud</option>
                  <option value="warn">warn — permite pero registra</option>
                  <option value="transform">transform — modifica el texto</option>
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-700">Prioridad</label>
                <input type="number" value={ruleForm.priority}
                  onChange={e => setRuleForm(p => ({ ...p, priority: parseInt(e.target.value) || 0 }))}
                  min={0} max={100} className={inputCls} />
              </div>
            </div>

            <div className="flex gap-2">
              <button onClick={createRule}
                className="px-3 py-1.5 bg-violet-600 text-white text-xs rounded-lg hover:bg-violet-700">
                Crear regla
              </button>
              <button onClick={() => setShowRuleForm(false)}
                className="px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-100 rounded-lg">
                Cancelar
              </button>
            </div>
          </div>
        ) : (
          <button onClick={() => setShowRuleForm(true)}
            className="w-full py-2 border border-dashed border-gray-300 text-xs text-gray-500 rounded-lg hover:border-violet-400 hover:text-violet-600">
            + Nueva regla
          </button>
        )}
      </Section>
    </div>
  )
}

// ── Helper: lista editable con items de texto libre ───────────────────────────
function ListEditor({
  label, placeholder, items, onChange,
}: {
  label: string; placeholder: string; items: string[]; onChange: (v: string[]) => void
}) {
  const [draft, setDraft] = useState('')

  function add() {
    if (!draft.trim()) return
    onChange([...items, draft.trim()])
    setDraft('')
  }

  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-gray-700">{label}</label>
      <div className="space-y-1">
        {items.map((item, i) => (
          <div key={i} className="flex items-center gap-2 text-xs text-gray-700 bg-white border border-gray-200 px-2 py-1.5 rounded-lg">
            <span className="flex-1">{item}</span>
            <button onClick={() => onChange(items.filter((_, j) => j !== i))} className="text-gray-300 hover:text-red-400">✕</button>
          </div>
        ))}
      </div>
      <div className="flex gap-1">
        <input value={draft} onChange={e => setDraft(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && add()}
          placeholder={placeholder} className={`${inputCls} text-xs`} />
        <button onClick={add} className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded-lg whitespace-nowrap">+ Agregar</button>
      </div>
    </div>
  )
}

const inputCls = "w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent"
