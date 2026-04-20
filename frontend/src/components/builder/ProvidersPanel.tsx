import { useEffect, useState } from 'react'

interface ProviderKey {
  id: string
  provider: string
  name: string
  is_default: boolean
  created_at: string
  truncated_key: string
}

const API_BASE = import.meta.env.VITE_API_URL || ''

export function ProvidersPanel() {
  const [keys, setKeys] = useState<ProviderKey[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')
  
  const [newProv, setNewProv] = useState('openai')
  const [newName, setNewName] = useState('')
  const [newRawKey, setNewRawKey] = useState('')

  const headers = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('agentica_token')}`,
  })

  const loadKeys = async () => {
    try {
      const r = await fetch(`${API_BASE}/api/v1/keys/llm`, { headers: headers() })
      if (!r.ok) throw new Error('Network response was not ok')
      const data = await r.json()
      setKeys(Array.isArray(data) ? data : [])
    } catch {
      setErrorMsg('Error de conexión al cargar la Bóveda — favor verificar que el API responda')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadKeys() }, [])

  const saveKey = async () => {
    if (!newRawKey.trim() || !newName.trim()) return
    setCreating(true)
    try {
      const r = await fetch(`${API_BASE}/api/v1/keys/llm`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ provider: newProv, name: newName, raw_key: newRawKey }),
      })
      if (!r.ok) {
        const err = await r.json()
        setErrorMsg(err.detail || 'Error al guardar la clave')
        return
      }
      setNewName('')
      setNewRawKey('')
      await loadKeys()
    } catch {
      setErrorMsg('Error de conexión — verificá que el servidor backend esté activo')
    } finally {
      setCreating(false)
    }
  }

  const setDefault = async (keyId: string, provider: string) => {
    try {
      const r = await fetch(`${API_BASE}/api/v1/keys/llm/${keyId}/default?provider=${provider}`, { method: 'PUT', headers: headers() })
      if (!r.ok) throw new Error('No se pudo establecer la clave por defecto')
      await loadKeys()
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'Error de conexión')
    }
  }

  const removeKey = async (keyId: string) => {
    if (!confirm('¿Eliminar esta clave? Los agentes que la usen fallarán.')) return
    try {
      const r = await fetch(`${API_BASE}/api/v1/keys/llm/${keyId}`, { method: 'DELETE', headers: headers() })
      if (!r.ok) throw new Error('No se pudo eliminar la clave')
      setKeys(keys.filter(k => k.id !== keyId))
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'Error de conexión')
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Bóveda de IA (Providers)</h2>
      <p className="text-gray-500 mb-8 text-sm">
        Administra tus llaves de Anthropic, OpenAI, OpenRouter y proveedores compatibles con OpenAI. Las llaves se guardan cifradas.
      </p>

      {/* Agregar Nueva */}
      <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm mb-8 flex flex-wrap gap-4 items-end">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs font-medium text-gray-700 mb-1">Proveedor</label>
          <select 
            value={newProv} onChange={e => setNewProv(e.target.value)}
            className="w-full rounded-lg border-gray-300 shadow-sm focus:border-violet-500 focus:ring-violet-500 sm:text-sm"
          >
            <option value="openai">OpenAI (ChatGPT)</option>
            <option value="anthropic">Anthropic (Claude)</option>
            <option value="openrouter">OpenRouter</option>
            <option value="deepseek">DeepSeek</option>
            <option value="qwen">Qwen / Alibaba</option>
            <option value="moonshot">Moonshot / Kimi</option>
            <option value="zhipu">Zhipu / GLM</option>
            <option value="custom_openai">OpenAI compatible custom</option>
          </select>
        </div>
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs font-medium text-gray-700 mb-1">Alias (Ej: Marketing OpenAI)</label>
          <input 
            type="text" value={newName} onChange={e => setNewName(e.target.value)}
            placeholder="Alias amigable"
            className="w-full rounded-lg border-gray-300 shadow-sm focus:border-violet-500 focus:ring-violet-500 sm:text-sm"
          />
        </div>
        <div className="flex-[2] min-w-[300px]">
          <label className="block text-xs font-medium text-gray-700 mb-1">API Key</label>
          <input 
            type="password" value={newRawKey} onChange={e => setNewRawKey(e.target.value)}
            placeholder="sk-..."
            className="w-full rounded-lg border-gray-300 shadow-sm focus:border-violet-500 focus:ring-violet-500 sm:text-sm"
          />
        </div>
        <button 
          onClick={saveKey}
          disabled={creating || !newRawKey || !newName}
          className="px-5 py-2.5 bg-violet-600 text-white font-medium rounded-lg hover:bg-violet-700 disabled:opacity-50 transition-colors"
        >
          {creating ? 'Guardando...' : 'Guardar Cifrado'}
        </button>
      </div>

      {/* Lista */}
      <div className="space-y-4">
        {errorMsg && (
          <div className="p-3 mb-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg flex justify-between items-center animate-in fade-in zoom-in-95 duration-200">
            <span>{errorMsg}</span>
            <button onClick={() => setErrorMsg('')} className="text-red-400 hover:text-red-600 font-bold ml-4">✕</button>
          </div>
        )}

        {loading ? (
          <div className="animate-pulse flex space-x-4">
            <div className="flex-1 space-y-4 py-1">
              <div className="h-4 bg-slate-200 rounded w-3/4"></div>
              <div className="h-4 bg-slate-200 rounded"></div>
            </div>
          </div>
        ) : keys.length === 0 ? (
          <div className="text-center py-10 bg-gray-50 rounded-2xl border border-dashed border-gray-300">
            <p className="text-gray-500 text-sm">Tu bóveda está vacía. Añade tu primera llave arriba.</p>
          </div>
        ) : (
          keys.map(key => (
            <div key={key.id} className="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-xl shadow-sm hover:border-violet-200 transition-colors">
              <div className="flex items-center gap-4">
                <div className={`flex items-center justify-center w-10 h-10 rounded-lg text-white font-bold text-xs ${key.provider === 'openai' ? 'bg-emerald-500' : key.provider === 'anthropic' ? 'bg-orange-500' : 'bg-indigo-500'}`}>
                  {key.provider.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-gray-900">{key.name}</h3>
                    {key.is_default && (
                      <span className="bg-violet-100 text-violet-700 text-[10px] uppercase font-bold px-2 py-0.5 rounded-full">
                        Predeterminada
                      </span>
                    )}
                  </div>
                  <div className="text-xs font-mono text-gray-500 mt-1">{key.truncated_key}</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {!key.is_default && (
                  <button 
                    onClick={() => setDefault(key.id, key.provider)}
                    className="text-xs font-medium text-gray-600 hover:text-violet-600 px-3 py-1.5 rounded-lg hover:bg-violet-50 transition-colors"
                  >
                    Hacer predeterminada
                  </button>
                )}
                <button 
                  onClick={() => removeKey(key.id)}
                  className="text-xs font-medium text-red-600 hover:text-red-800 px-3 py-1.5 rounded-lg hover:bg-red-50 transition-colors"
                >
                  Eliminar
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
