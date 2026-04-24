import { useState, useEffect, useRef } from 'react'

interface CustomTool {
  id: string
  name: string
  description: string
  config_schema: Record<string, any>
  is_active: boolean
  test_input: string
  last_error: string | null
  created_at: string
  updated_at: string
}

const TOOL_TEMPLATE = `# ── Custom Tool para AGENTICA ────────────────────────────────────────────────
#
# Obligatorio:
#   TOOL_NAME        → nombre snake_case que el agente usa para invocar esta tool
#   TOOL_DESCRIPTION → descripción clara de qué hace y cuándo usarla (el LLM la lee)
#   async def run(input, config) → lógica de la tool
#
# El parámetro 'config' contiene los valores que configuraste en config_schema.
# Podés importar: httpx, json, re, datetime, math, random, base64, hashlib, urllib
# No se permite: os, sys, subprocess, open, exec, eval, socket
# ─────────────────────────────────────────────────────────────────────────────

import httpx
import json

TOOL_NAME = "mi_tool_personalizada"

TOOL_DESCRIPTION = """
Describí acá qué hace esta tool y cuándo el agente debe usarla.
Ejemplo: Consulta el stock de un producto en el sistema ERP de la empresa.
Recibe: el nombre o código del producto.
Retorna: stock disponible, precio y ubicación.
"""

async def run(input: str, config: dict) -> str:
    """
    input  → lo que el agente decidió pasarle a esta tool
    config → los parámetros que configuraste (api_key, base_url, etc.)
    """
    # Ejemplo: llamada a una API externa
    api_url = config.get("api_url", "https://httpbin.org/get")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(api_url, params={"q": input})
        data = resp.json()
    
    return f"Resultado para '{input}': {json.dumps(data, ensure_ascii=False)[:500]}"
`

const headers = () => ({
  Authorization: `Bearer ${localStorage.getItem('agentica_token')}`,
  'Content-Type': 'application/json',
})
const API_BASE = import.meta.env.VITE_API_URL || ''

export function CustomToolsPanel() {
  const [tools, setTools]         = useState<CustomTool[]>([])
  const [loading, setLoading]     = useState(true)
  const [selected, setSelected]   = useState<CustomTool | null>(null)
  const [isNew, setIsNew]         = useState(false)
  const [saving, setSaving]       = useState(false)
  const [testing, setTesting]     = useState(false)
  const [testResult, setTestResult] = useState<any>(null)
  const [validation, setValidation] = useState<{ valid: boolean; error: string | null } | null>(null)
  const [validating, setValidating] = useState(false)
  const [error, setError]         = useState('')

  // Form state
  const [formName, setFormName]           = useState('')
  const [formDesc, setFormDesc]           = useState('')
  const [formCode, setFormCode]           = useState(TOOL_TEMPLATE)
  const [formSchema, setFormSchema]       = useState('{}')
  const [formTestInput, setFormTestInput] = useState('')
  const [formTestConfig, setFormTestConfig] = useState('{}')

  const validateTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const loadTools = async () => {
    setLoading(true)
    try {
      const r = await fetch(`${API_BASE}/api/v1/tools/custom/`, { headers: headers() })
      const data = await r.json()
      setTools(Array.isArray(data) ? data : [])
    } catch {
      setError('Error al cargar tools')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadTools() }, [])

  // Validación en tiempo real con debounce
  useEffect(() => {
    if (!formCode || formCode === TOOL_TEMPLATE) return
    if (validateTimer.current) clearTimeout(validateTimer.current)
    validateTimer.current = setTimeout(async () => {
      setValidating(true)
      try {
        const r = await fetch(`${API_BASE}/api/v1/tools/custom/validate`, {
          method: 'POST', headers: headers(),
          body: JSON.stringify({ source_code: formCode }),
        })
        setValidation(await r.json())
      } catch { /* ignore */ }
      finally { setValidating(false) }
    }, 800)
  }, [formCode])

  const openNew = () => {
    setIsNew(true)
    setSelected(null)
    setFormName(''); setFormDesc(''); setFormCode(TOOL_TEMPLATE)
    setFormSchema('{}'); setFormTestInput(''); setFormTestConfig('{}')
    setValidation(null); setTestResult(null); setError('')
  }

  const openEdit = (tool: CustomTool) => {
    setIsNew(false)
    setSelected(tool)
    setFormName(tool.name)
    setFormDesc(tool.description)
    setFormCode('')   // se carga del server
    setFormSchema(JSON.stringify(tool.config_schema, null, 2))
    setFormTestInput(tool.test_input || '')
    setFormTestConfig('{}')
    setValidation(null); setTestResult(null); setError('')
    // Cargar source_code completo
    fetch(`${API_BASE}/api/v1/tools/custom/${tool.id}`, { headers: headers() })
      .then(r => r.json())
      .then(d => {
        // El endpoint actual no retorna source_code en el listado por seguridad
        // Para el editor, hacemos un GET al detalle
        setFormCode(d.source_code || TOOL_TEMPLATE)
      })
      .catch(() => setFormCode(TOOL_TEMPLATE))
  }

  const handleSave = async () => {
    if (!formName || !formDesc || !formCode) {
      setError('Nombre, descripción y código son obligatorios')
      return
    }
    let schema: Record<string, any> = {}
    try { schema = JSON.parse(formSchema) } catch { setError('config_schema no es JSON válido'); return }

    setSaving(true); setError('')
    try {
      const url = isNew ? `${API_BASE}/api/v1/tools/custom/` : `${API_BASE}/api/v1/tools/custom/${selected?.id}`
      const method = isNew ? 'POST' : 'PUT'
      const r = await fetch(url, {
        method, headers: headers(),
        body: JSON.stringify({
          name: formName, description: formDesc,
          source_code: formCode, config_schema: schema,
          test_input: formTestInput,
        }),
      })
      if (!r.ok) {
        const err = await r.json()
        setError(err.detail || 'Error al guardar')
        return
      }
      await loadTools()
      setIsNew(false)
      setSelected(null)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    if (!selected) return
    let config: Record<string, any> = {}
    try { config = JSON.parse(formTestConfig) } catch { setError('config de test no es JSON válido'); return }

    setTesting(true); setTestResult(null); setError('')
    try {
      const r = await fetch(`${API_BASE}/api/v1/tools/custom/${selected.id}/test`, {
        method: 'POST', headers: headers(),
        body: JSON.stringify({ input: formTestInput, config }),
      })
      setTestResult(await r.json())
    } catch (e: any) {
      setError(e.message)
    } finally {
      setTesting(false)
    }
  }

  const handleToggleActive = async (tool: CustomTool) => {
    await fetch(`${API_BASE}/api/v1/tools/custom/${tool.id}`, {
      method: 'PUT', headers: headers(),
      body: JSON.stringify({ is_active: !tool.is_active }),
    })
    await loadTools()
  }

  const handleDelete = async (tool: CustomTool) => {
    if (!confirm(`¿Eliminar la tool "${tool.name}"? Los agentes que la usen dejarán de funcionar.`)) return
    await fetch(`${API_BASE}/api/v1/tools/custom/${tool.id}`, { method: 'DELETE', headers: headers() })
    if (selected?.id === tool.id) setSelected(null)
    await loadTools()
  }

  const isEditing = isNew || selected !== null

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Mis Tools</h2>
          <p className="text-sm text-gray-500 mt-1">
            Escribí tools personalizadas en Python y usálas en cualquier agente
          </p>
        </div>
        <button onClick={openNew}
          className="px-4 py-2 bg-violet-600 text-white text-sm font-medium rounded-lg hover:bg-violet-700 transition-colors shadow-sm">
          + Nueva Tool
        </button>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg flex justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')} className="text-red-400 hover:text-red-600 font-bold ml-4">✕</button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* ── Lista de tools ──────────────────────────────────────────────── */}
        <div className="lg:col-span-1 space-y-2">
          {loading ? (
            <div className="p-4 text-center text-sm text-gray-400">Cargando...</div>
          ) : tools.length === 0 && !isNew ? (
            <div className="p-6 text-center bg-gray-50 border border-dashed border-gray-300 rounded-xl">
              <p className="text-sm text-gray-500">No tenés tools creadas todavía.</p>
              <button onClick={openNew} className="mt-2 text-sm text-violet-600 hover:underline">
                Crear la primera
              </button>
            </div>
          ) : (
            <>
              {isNew && (
                <div className="p-3 bg-violet-50 border-2 border-violet-400 rounded-xl">
                  <div className="text-sm font-semibold text-violet-700">✏️ Nueva tool</div>
                  <div className="text-xs text-violet-500 mt-0.5">Sin guardar</div>
                </div>
              )}
              {tools.map(tool => (
                <button key={tool.id} onClick={() => openEdit(tool)}
                  className={`w-full text-left p-3 rounded-xl border transition-all ${
                    selected?.id === tool.id
                      ? 'border-violet-400 bg-violet-50'
                      : 'border-gray-200 bg-white hover:border-violet-200 hover:bg-gray-50'
                  }`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${tool.is_active ? 'bg-green-400' : 'bg-gray-300'}`} />
                        <span className="text-sm font-mono font-medium text-gray-800 truncate">{tool.name}</span>
                      </div>
                      <p className="text-xs text-gray-500 mt-1 line-clamp-2 pl-4">{tool.description}</p>
                      {tool.last_error && (
                        <p className="text-xs text-red-500 mt-1 pl-4 truncate" title={tool.last_error}>
                          ⚠ {tool.last_error.slice(0, 60)}
                        </p>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </>
          )}
        </div>

        {/* ── Editor ──────────────────────────────────────────────────────── */}
        {isEditing ? (
          <div className="lg:col-span-2 space-y-4">

            {/* Nombre y descripción */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Nombre <span className="text-gray-400">(snake_case)</span>
                </label>
                <input value={formName} onChange={e => setFormName(e.target.value)}
                  disabled={!isNew}
                  placeholder="consultar_precio_erp"
                  className="w-full px-3 py-2 text-sm font-mono border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500 disabled:bg-gray-50 disabled:text-gray-400" />
              </div>
              <div className="flex items-end gap-2">
                {!isNew && selected && (
                  <>
                    <button onClick={() => handleToggleActive(selected)}
                      className={`px-3 py-2 text-xs font-medium rounded-lg border transition-colors ${
                        selected.is_active
                          ? 'border-green-200 bg-green-50 text-green-700 hover:bg-green-100'
                          : 'border-gray-200 bg-gray-50 text-gray-500 hover:bg-gray-100'
                      }`}>
                      {selected.is_active ? '✓ Activa' : '○ Inactiva'}
                    </button>
                    <button onClick={() => handleDelete(selected)}
                      className="px-3 py-2 text-xs font-medium rounded-lg border border-red-200 bg-red-50 text-red-600 hover:bg-red-100 transition-colors">
                      Eliminar
                    </button>
                  </>
                )}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Descripción</label>
              <textarea value={formDesc} onChange={e => setFormDesc(e.target.value)} rows={2}
                placeholder="Qué hace esta tool y cuándo el agente debe usarla..."
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500 resize-none" />
            </div>

            {/* Editor de código */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-medium text-gray-700">Código Python</label>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  validating ? 'bg-gray-100 text-gray-400' :
                  validation === null ? 'bg-gray-100 text-gray-400' :
                  validation.valid ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                }`}>
                  {validating ? '⟳ Validando...' : validation === null ? '— Sin validar' :
                   validation.valid ? '✓ Código válido' : '✗ ' + (validation.error?.slice(0, 60) || 'Error')}
                </span>
              </div>
              <textarea value={formCode} onChange={e => setFormCode(e.target.value)}
                rows={18} spellCheck={false}
                className="w-full px-4 py-3 text-xs font-mono bg-gray-900 text-gray-100 border border-gray-700 rounded-xl focus:ring-2 focus:ring-violet-500 focus:border-violet-500 resize-y leading-relaxed" />
            </div>

            {/* Config schema */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Config Schema <span className="text-gray-400">(JSON — parámetros configurables)</span>
              </label>
              <textarea value={formSchema} onChange={e => setFormSchema(e.target.value)} rows={3}
                className="w-full px-3 py-2 text-xs font-mono border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500 resize-none"
                placeholder='{ "api_url": "https://...", "api_key": "" }' />
            </div>

            {/* Test */}
            <div className="p-4 bg-gray-50 border border-gray-200 rounded-xl space-y-3">
              <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Probar tool</h4>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Input de prueba</label>
                  <input value={formTestInput} onChange={e => setFormTestInput(e.target.value)}
                    placeholder="producto ABC123"
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg" />
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Config de prueba (JSON)</label>
                  <input value={formTestConfig} onChange={e => setFormTestConfig(e.target.value)}
                    placeholder='{"api_url": "https://..."}'
                    className="w-full px-3 py-2 text-sm font-mono border border-gray-300 rounded-lg" />
                </div>
              </div>

              {!isNew && selected && (
                <button onClick={handleTest} disabled={testing || !formTestInput}
                  className="px-4 py-2 bg-gray-800 text-white text-sm rounded-lg hover:bg-gray-900 disabled:opacity-50 transition-colors">
                  {testing ? '⟳ Ejecutando...' : '▶ Ejecutar test'}
                </button>
              )}

              {testResult && (
                <div className={`p-3 rounded-lg text-xs font-mono ${
                  testResult.success ? 'bg-green-50 border border-green-200 text-green-800' : 'bg-red-50 border border-red-200 text-red-800'
                }`}>
                  <div className="font-bold mb-1">{testResult.success ? '✓ Éxito' : '✗ Error'}</div>
                  <div className="whitespace-pre-wrap break-all">
                    {testResult.success ? testResult.output : testResult.error}
                  </div>
                </div>
              )}
            </div>

            {/* Acciones */}
            <div className="flex gap-3 pt-2">
              <button onClick={handleSave} disabled={saving || validating || validation?.valid === false}
                className="px-5 py-2.5 bg-violet-600 text-white text-sm font-medium rounded-lg hover:bg-violet-700 disabled:opacity-50 transition-colors shadow-sm">
                {saving ? 'Guardando...' : isNew ? 'Crear Tool' : 'Guardar Cambios'}
              </button>
              <button onClick={() => { setSelected(null); setIsNew(false); setError('') }}
                className="px-5 py-2.5 text-gray-600 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
                Cancelar
              </button>
            </div>
          </div>
        ) : (
          <div className="lg:col-span-2 flex items-center justify-center p-12 bg-gray-50 border-2 border-dashed border-gray-300 rounded-xl">
            <div className="text-center text-gray-400">
              <div className="text-4xl mb-3">🔧</div>
              <p className="text-sm">Seleccioná una tool para editarla</p>
              <p className="text-xs mt-1">o creá una nueva con el botón de arriba</p>
            </div>
          </div>
        )}
      </div>

      {/* Documentación inline */}
      <div className="mt-8 p-5 bg-blue-50 border border-blue-200 rounded-xl">
        <h3 className="text-sm font-semibold text-blue-800 mb-3">📖 Cómo usar una Custom Tool en un agente</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-blue-700">
          <div>
            <p className="font-medium mb-1">1. Crear la tool</p>
            <p>Escribí el código con TOOL_NAME, TOOL_DESCRIPTION y async def run(). Validá y guardá.</p>
          </div>
          <div>
            <p className="font-medium mb-1">2. Probar</p>
            <p>Usá el panel de test para verificar que devuelve el resultado esperado antes de asignarla a un agente.</p>
          </div>
          <div>
            <p className="font-medium mb-1">3. Asignar al agente</p>
            <p>En el Requirement Wizard, seleccioná "Mis Tools" en el paso de configuración de tools y elegí la que creaste.</p>
          </div>
        </div>
      </div>
    </div>
  )
}
