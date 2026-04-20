import { useState, useEffect } from 'react'
import { mcpApi } from '../../lib/api'
import type { MCPServer } from '../../types/agent'

const EMPTY: Omit<MCPServer, 'id' | 'discovered_tools' | 'is_active' | 'last_tested_at'> = {
  name: '', endpoint: '', transport: 'sse', auth_type: 'none', auth_config: {},
}

export function MCPPanel() {
  const [servers, setServers] = useState<MCPServer[]>([])
  const [selected, setSelected] = useState<MCPServer | null>(null)
  const [form, setForm] = useState({ ...EMPTY })
  const [isNew, setIsNew] = useState(false)
  const [testing, setTesting] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [tokenValue, setTokenValue] = useState('')
  const [basicUser, setBasicUser] = useState('')
  const [basicPass, setBasicPass] = useState('')

  useEffect(() => { loadServers() }, [])

  async function loadServers() {
    try { setServers(await mcpApi.list()) } catch { setError('Error cargando servidores MCP') }
  }

  function startNew() {
    setSelected(null)
    setForm({ ...EMPTY })
    setTokenValue('')
    setBasicUser('')
    setBasicPass('')
    setIsNew(true)
    setError('')
  }

  function selectServer(s: MCPServer) {
    setSelected(s)
    setForm({
      name: s.name, endpoint: s.endpoint, transport: s.transport,
      auth_type: s.auth_type, auth_config: s.auth_config,
    })
    setTokenValue(s.auth_config?.token || '')
    setBasicUser(s.auth_config?.user || '')
    setBasicPass(s.auth_config?.pass || '')
    setIsNew(false)
    setError('')
  }

  function buildAuthConfig() {
    if (form.auth_type === 'bearer') return { token: tokenValue }
    if (form.auth_type === 'basic') return { user: basicUser, pass: basicPass }
    return {}
  }

  async function save() {
    if (!form.name || !form.endpoint) { setError('Nombre y endpoint son obligatorios'); return }
    setLoading(true); setError('')
    try {
      const payload = { ...form, auth_config: buildAuthConfig() }
      if (isNew) {
        const created = await mcpApi.create(payload)
        setServers(prev => [created, ...prev])
        setSelected(created)
        setIsNew(false)
      } else if (selected) {
        const updated = await mcpApi.update(selected.id, payload)
        setServers(prev => prev.map(s => s.id === updated.id ? updated : s))
        setSelected(updated)
      }
    } catch { setError('Error guardando servidor MCP') }
    finally { setLoading(false) }
  }

  async function testServer() {
    if (!selected) return
    setTesting(true); setError('')
    try {
      const updated = await mcpApi.test(selected.id)
      setServers(prev => prev.map(s => s.id === updated.id ? updated : s))
      setSelected(updated)
    } catch { setError('Error al conectar al servidor MCP') }
    finally { setTesting(false) }
  }

  async function deleteServer(id: string) {
    if (!confirm('¿Eliminar este servidor MCP?')) return
    try {
      await mcpApi.delete(id)
      setServers(prev => prev.filter(s => s.id !== id))
      if (selected?.id === id) { setSelected(null); setIsNew(false) }
    } catch { setError('Error eliminando servidor') }
  }

  const editing = isNew || selected !== null

  return (
    <div className="flex gap-4 h-full">
      {/* Lista */}
      <div className="w-64 shrink-0 border-r border-gray-100 pr-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-700">Servidores MCP</h3>
          <button onClick={startNew}
            className="text-xs px-2 py-1 bg-violet-600 text-white rounded-lg hover:bg-violet-700">
            + Nuevo
          </button>
        </div>
        {servers.length === 0 && (
          <p className="text-xs text-gray-400 text-center py-6">Sin servidores MCP</p>
        )}
        <div className="space-y-1">
          {servers.map(s => (
            <button key={s.id} onClick={() => selectServer(s)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                selected?.id === s.id ? 'bg-violet-50 text-violet-700 font-medium' : 'hover:bg-gray-50 text-gray-700'
              }`}>
              <div className="font-medium truncate">{s.name}</div>
              <div className="text-xs text-gray-400 truncate">{s.endpoint}</div>
              <div className="text-xs text-gray-400 mt-0.5">
                {s.discovered_tools.length} tools · {s.transport.toUpperCase()}
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
                placeholder="ej: Servidor interno" className={inputCls} />
            </Field>
            <Field label="Transport">
              <select value={form.transport} onChange={e => setForm(p => ({ ...p, transport: e.target.value as 'sse' | 'http' }))}
                className={inputCls}>
                <option value="sse">SSE (Server-Sent Events)</option>
                <option value="http">HTTP Streamable</option>
              </select>
            </Field>
          </div>

          <Field label="Endpoint URL *">
            <input value={form.endpoint} onChange={e => setForm(p => ({ ...p, endpoint: e.target.value }))}
              placeholder="https://mcp.miempresa.com" className={inputCls} />
          </Field>

          <Field label="Autenticación">
            <select value={form.auth_type} onChange={e => setForm(p => ({ ...p, auth_type: e.target.value as any }))}
              className={inputCls}>
              <option value="none">Sin autenticación</option>
              <option value="bearer">Bearer Token</option>
              <option value="basic">Basic Auth</option>
            </select>
          </Field>

          {form.auth_type === 'bearer' && (
            <Field label="Token">
              <input type="password" value={tokenValue} onChange={e => setTokenValue(e.target.value)}
                placeholder="sk-..." className={inputCls} />
            </Field>
          )}
          {form.auth_type === 'basic' && (
            <div className="grid grid-cols-2 gap-3">
              <Field label="Usuario">
                <input value={basicUser} onChange={e => setBasicUser(e.target.value)} className={inputCls} />
              </Field>
              <Field label="Contraseña">
                <input type="password" value={basicPass} onChange={e => setBasicPass(e.target.value)} className={inputCls} />
              </Field>
            </div>
          )}

          {/* Tools descubiertas */}
          {selected && selected.discovered_tools.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-700 mb-2">
                Tools descubiertas ({selected.discovered_tools.length})
              </p>
              <div className="border border-gray-100 rounded-lg divide-y divide-gray-100">
                {selected.discovered_tools.map(t => (
                  <div key={t.name} className="px-3 py-2">
                    <div className="text-sm font-medium text-gray-800">{t.name}</div>
                    <div className="text-xs text-gray-500">{t.description}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-2 pt-2 border-t border-gray-100">
            <button onClick={save} disabled={loading}
              className="px-4 py-2 bg-violet-600 text-white text-sm rounded-lg hover:bg-violet-700 disabled:opacity-40">
              {loading ? 'Guardando...' : (isNew ? 'Registrar' : 'Guardar')}
            </button>
            {!isNew && selected && (
              <>
                <button onClick={testServer} disabled={testing}
                  className="px-4 py-2 text-sm border border-violet-300 text-violet-700 rounded-lg hover:bg-violet-50 disabled:opacity-40">
                  {testing ? 'Probando...' : '⚡ Probar conexión'}
                </button>
                <button onClick={() => deleteServer(selected.id)}
                  className="px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg">
                  Eliminar
                </button>
              </>
            )}
            <button onClick={() => { setSelected(null); setIsNew(false) }}
              className="px-4 py-2 text-sm text-gray-500 hover:bg-gray-50 rounded-lg ml-auto">
              Cancelar
            </button>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
          Seleccioná un servidor o registrá uno nuevo
        </div>
      )}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-gray-700">{label}</label>
      {children}
    </div>
  )
}

const inputCls = "w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent"
