import { useState, useEffect } from 'react'
import { skillsApi } from '../../lib/api'
import type { Skill } from '../../types/agent'
import { AVAILABLE_TOOLS } from '../../types/agent'

const EMPTY_SKILL: Omit<Skill, 'id' | 'is_active' | 'created_at'> = {
  name: '', description: '', objective: '', usage_conditions: '',
  tools: [], procedure: '', quality_rules: '', output_format: '', guardrails: [],
}

export function SkillsPanel() {
  const [skills, setSkills] = useState<Skill[]>([])
  const [selected, setSelected] = useState<Skill | null>(null)
  const [form, setForm] = useState({ ...EMPTY_SKILL })
  const [isNew, setIsNew] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { loadSkills() }, [])

  async function loadSkills() {
    try { setSkills(await skillsApi.list()) } catch { setError('Error cargando skills') }
  }

  function startNew() {
    setSelected(null)
    setForm({ ...EMPTY_SKILL })
    setIsNew(true)
    setError('')
  }

  function selectSkill(s: Skill) {
    setSelected(s)
    setForm({
      name: s.name, description: s.description, objective: s.objective,
      usage_conditions: s.usage_conditions, tools: s.tools, procedure: s.procedure,
      quality_rules: s.quality_rules, output_format: s.output_format, guardrails: s.guardrails,
    })
    setIsNew(false)
    setError('')
  }

  function toggleTool(name: string) {
    setForm(prev => {
      const has = prev.tools.some(t => t.name === name)
      return {
        ...prev,
        tools: has
          ? prev.tools.filter(t => t.name !== name)
          : [...prev.tools, { name, source: 'library' as const, config: {} }],
      }
    })
  }

  async function save() {
    if (!form.name || !form.objective || !form.procedure) {
      setError('Nombre, objetivo y procedimiento son obligatorios')
      return
    }
    setLoading(true)
    setError('')
    try {
      if (isNew) {
        const created = await skillsApi.create(form)
        setSkills(prev => [created, ...prev])
        setSelected(created)
        setIsNew(false)
      } else if (selected) {
        const updated = await skillsApi.update(selected.id, form)
        setSkills(prev => prev.map(s => s.id === updated.id ? updated : s))
        setSelected(updated)
      }
    } catch { setError('Error guardando skill') }
    finally { setLoading(false) }
  }

  async function deleteSkill(id: string) {
    if (!confirm('¿Eliminar esta skill?')) return
    try {
      await skillsApi.delete(id)
      setSkills(prev => prev.filter(s => s.id !== id))
      if (selected?.id === id) { setSelected(null); setIsNew(false) }
    } catch { setError('Error eliminando skill') }
  }

  const editing = isNew || selected !== null

  return (
    <div className="flex gap-4 h-full">
      {/* Lista */}
      <div className="w-64 shrink-0 border-r border-gray-100 pr-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-700">Skills</h3>
          <button onClick={startNew}
            className="text-xs px-2 py-1 bg-violet-600 text-white rounded-lg hover:bg-violet-700">
            + Nueva
          </button>
        </div>
        {skills.length === 0 && (
          <p className="text-xs text-gray-400 text-center py-6">Sin skills aún</p>
        )}
        <div className="space-y-1">
          {skills.map(s => (
            <button key={s.id} onClick={() => selectSkill(s)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                selected?.id === s.id ? 'bg-violet-50 text-violet-700 font-medium' : 'hover:bg-gray-50 text-gray-700'
              }`}>
              <div className="font-medium truncate">{s.name}</div>
              <div className="text-xs text-gray-400 truncate">{s.objective}</div>
              <div className={`text-xs mt-0.5 ${s.is_active ? 'text-green-500' : 'text-gray-400'}`}>
                {s.is_active ? '● Activa' : '○ Inactiva'}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Editor */}
      {editing ? (
        <div className="flex-1 overflow-y-auto space-y-4">
          {error && <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</div>}

          <div className="grid grid-cols-2 gap-3">
            <Field label="Nombre *">
              <input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                placeholder="ej: research_skill" className={inputCls} />
            </Field>
            <Field label="Descripción">
              <input value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
                placeholder="Breve descripción" className={inputCls} />
            </Field>
          </div>

          <Field label="Objetivo *" hint="¿Qué logra esta skill?">
            <textarea value={form.objective} onChange={e => setForm(p => ({ ...p, objective: e.target.value }))}
              rows={2} className={inputCls} placeholder="ej: Investigar y resumir información web sobre cualquier tema" />
          </Field>

          <Field label="Condiciones de uso" hint="¿Cuándo debe usarse esta skill?">
            <textarea value={form.usage_conditions} onChange={e => setForm(p => ({ ...p, usage_conditions: e.target.value }))}
              rows={2} className={inputCls} placeholder="ej: Cuando el usuario pide investigar o buscar información actualizada" />
          </Field>

          <Field label="Procedimiento *" hint="Instrucciones paso a paso">
            <textarea value={form.procedure} onChange={e => setForm(p => ({ ...p, procedure: e.target.value }))}
              rows={4} className={inputCls}
              placeholder={"1. Buscar en web usando web_search\n2. Analizar resultados\n3. Sintetizar en respuesta estructurada"} />
          </Field>

          <Field label="Herramientas habilitadas">
            <div className="grid grid-cols-2 gap-1.5 mt-1">
              {AVAILABLE_TOOLS.map(t => {
                const active = form.tools.some(ft => ft.name === t.name)
                return (
                  <button key={t.name} onClick={() => toggleTool(t.name)}
                    className={`text-left px-3 py-2 rounded-lg border text-xs transition-all ${
                      active ? 'border-violet-400 bg-violet-50 text-violet-700' : 'border-gray-200 hover:border-violet-200 text-gray-600'
                    }`}>
                    <span className="font-medium">{t.name}</span>
                    <span className="text-gray-400 ml-1">({t.category})</span>
                    <span className="ml-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600">
                      {t.state_label}
                    </span>
                  </button>
                )
              })}
            </div>
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Reglas de calidad">
              <textarea value={form.quality_rules} onChange={e => setForm(p => ({ ...p, quality_rules: e.target.value }))}
                rows={2} className={inputCls} placeholder="ej: Citar fuentes, máximo 3 párrafos" />
            </Field>
            <Field label="Formato de salida">
              <textarea value={form.output_format} onChange={e => setForm(p => ({ ...p, output_format: e.target.value }))}
                rows={2} className={inputCls} placeholder="ej: Markdown con subtítulos y bullet points" />
            </Field>
          </div>

          <Field label="Límites / Guardrails" hint="Una restricción por línea">
            <textarea
              value={form.guardrails.join('\n')}
              onChange={e => setForm(p => ({ ...p, guardrails: e.target.value.split('\n').filter(Boolean) }))}
              rows={2} className={inputCls}
              placeholder={"No inventar datos\nNo acceder a fuentes de pago"} />
          </Field>

          <div className="flex gap-2 pt-2 border-t border-gray-100">
            <button onClick={save} disabled={loading}
              className="px-4 py-2 bg-violet-600 text-white text-sm rounded-lg hover:bg-violet-700 disabled:opacity-40">
              {loading ? 'Guardando...' : (isNew ? 'Crear skill' : 'Guardar cambios')}
            </button>
            {!isNew && selected && (
              <button onClick={() => deleteSkill(selected.id)}
                className="px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg">
                Eliminar
              </button>
            )}
            <button onClick={() => { setSelected(null); setIsNew(false) }}
              className="px-4 py-2 text-sm text-gray-500 hover:bg-gray-50 rounded-lg ml-auto">
              Cancelar
            </button>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
          Seleccioná una skill o creá una nueva
        </div>
      )}
    </div>
  )
}

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-gray-700">{label}</label>
      {hint && <p className="text-xs text-gray-400">{hint}</p>}
      {children}
    </div>
  )
}

const inputCls = "w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent"
