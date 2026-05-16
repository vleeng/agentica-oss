import { useState, useEffect, useRef } from 'react'
import { knowledgeBasesApi } from '../../lib/api'
import type { KnowledgeBase } from '../../types/agent'

const STATUS_COLORS: Record<string, string> = {
  empty:    'text-gray-400',
  indexing: 'text-amber-500',
  ready:    'text-green-500',
  error:    'text-red-500',
}
const STATUS_LABELS: Record<string, string> = {
  empty: '○ Vacía', indexing: '⟳ Indexando', ready: '● Lista', error: '✕ Error',
}

export function KnowledgeBasesPanel() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [selected, setSelected] = useState<KnowledgeBase | null>(null)
  const [sources, setSources] = useState<string[]>([])
  const [stats, setStats] = useState<{ vectors_count?: number; status?: string } | null>(null)
  const [form, setForm] = useState({ name: '', description: '', accessMode: 'restricted' as 'global' | 'restricted' })
  const [isNew, setIsNew] = useState(false)
  const [loading, setLoading] = useState(false)
  const [ingesting, setIngesting] = useState(false)
  const [error, setError] = useState('')
  const [urlInput, setUrlInput] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => { loadKbs() }, [])

  async function loadKbs() {
    try { setKbs(await knowledgeBasesApi.list()) } catch { setError('Error cargando bases de conocimiento') }
  }

  async function selectKb(kb: KnowledgeBase) {
    setSelected(kb)
    setForm({ name: kb.name, description: kb.description, accessMode: kb.access_mode })
    setIsNew(false)
    setError('')
    try {
      const data = await knowledgeBasesApi.getSources(kb.id)
      setSources(data.sources || [])
      setStats(data.stats || null)
    } catch {
      setSources([])
      setStats(null)
    }
  }

  function startNew() {
    setSelected(null)
    setForm({ name: '', description: '', accessMode: 'restricted' })
    setSources([])
    setStats(null)
    setIsNew(true)
    setError('')
  }

  async function refreshSelected(kb: KnowledgeBase | null = selected) {
    if (!kb) return
    try {
      const [freshKb, data] = await Promise.all([
        knowledgeBasesApi.get(kb.id),
        knowledgeBasesApi.getSources(kb.id),
      ])
      setSelected(freshKb)
      setForm({ name: freshKb.name, description: freshKb.description, accessMode: freshKb.access_mode })
      setSources(data.sources || [])
      setStats(data.stats || null)
      setKbs(prev => prev.map(item => item.id === freshKb.id ? freshKb : item))
    } catch {
      setError('Error actualizando KB')
    }
  }

  async function save() {
    if (!form.name) { setError('El nombre es obligatorio'); return }
    setLoading(true); setError('')
    try {
      if (isNew) {
        const created = await knowledgeBasesApi.create({
          name: form.name, description: form.description,
          access_mode: form.accessMode,
          rag_spec: { enabled: true, pack: 'GenericDocsRAG', sources: [], chunk_size: 500, chunk_overlap: 50, top_k: 4, embedding_model: 'text-embedding-3-small' },
        })
        setKbs(prev => [created, ...prev])
        setSelected(created)
        setStats(null)
        setSources([])
        setIsNew(false)
      } else if (selected) {
        const updated = await knowledgeBasesApi.update(selected.id, {
          name: form.name, description: form.description, access_mode: form.accessMode, rag_spec: selected.rag_spec,
        })
        setKbs(prev => prev.map(k => k.id === updated.id ? updated : k))
        setSelected(updated)
        setForm({ name: updated.name, description: updated.description, accessMode: updated.access_mode })
      }
    } catch { setError('Error guardando KB') }
    finally { setLoading(false) }
  }

  async function ingestUrl() {
    if (!selected || !urlInput.trim()) return
    setIngesting(true); setError('')
    try {
      await knowledgeBasesApi.update(selected.id, {
        name: selected.name, description: selected.description,
        access_mode: selected.access_mode,
        rag_spec: { ...selected.rag_spec, sources: [...selected.rag_spec.sources, urlInput.trim()] },
      })
      await knowledgeBasesApi.ingest(selected.id)
      setUrlInput('')
      setKbs(prev => prev.map(k => k.id === selected.id ? { ...k, status: 'indexing' } : k))
      setSelected(prev => prev ? { ...prev, status: 'indexing' } : prev)
      await refreshSelected({ ...selected, status: 'indexing' })
    } catch { setError('Error ingiriendo URL') }
    finally { setIngesting(false) }
  }

  async function ingestFile(file: File) {
    if (!selected) return
    setIngesting(true); setError('')
    try {
      await knowledgeBasesApi.ingestFile(selected.id, file)
      setKbs(prev => prev.map(k => k.id === selected.id ? { ...k, status: 'indexing' } : k))
      setSelected(prev => prev ? { ...prev, status: 'indexing' } : prev)
      await refreshSelected({ ...selected, status: 'indexing' })
    } catch { setError('Error ingiriendo archivo') }
    finally { setIngesting(false) }
  }

  async function deleteSource(source: string) {
    if (!selected || !confirm(`¿Eliminar fuente "${source}"?`)) return
    try {
      await knowledgeBasesApi.deleteSource(selected.id, source)
      await refreshSelected(selected)
    } catch { setError('Error eliminando fuente') }
  }

  async function reindexSelected() {
    if (!selected) return
    setIngesting(true); setError('')
    try {
      await knowledgeBasesApi.ingest(selected.id)
      setKbs(prev => prev.map(k => k.id === selected.id ? { ...k, status: 'indexing' } : k))
      setSelected(prev => prev ? { ...prev, status: 'indexing' } : prev)
      await refreshSelected({ ...selected, status: 'indexing' })
    } catch {
      setError('Error reindexando KB')
    } finally {
      setIngesting(false)
    }
  }

  async function deleteKb(id: string) {
    if (!confirm('¿Eliminar esta base de conocimiento y todos sus datos?')) return
    try {
      await knowledgeBasesApi.delete(id)
      setKbs(prev => prev.filter(k => k.id !== id))
      if (selected?.id === id) {
        setSelected(null)
        setSources([])
        setStats(null)
        setIsNew(false)
      }
    } catch { setError('Error eliminando KB') }
  }

  const editing = isNew || selected !== null

  return (
    <div className="flex gap-4 h-full">
      {/* Lista */}
      <div className="w-64 shrink-0 border-r border-gray-100 pr-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-700">Knowledge Bases</h3>
          <button onClick={startNew}
            className="text-xs px-2 py-1 bg-violet-600 text-white rounded-lg hover:bg-violet-700">
            + Nueva
          </button>
        </div>
        {kbs.length === 0 && (
          <p className="text-xs text-gray-400 text-center py-6">Sin KBs aún</p>
        )}
        <div className="space-y-1">
          {kbs.map(kb => (
            <button key={kb.id} onClick={() => selectKb(kb)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                selected?.id === kb.id ? 'bg-violet-50 text-violet-700 font-medium' : 'hover:bg-gray-50 text-gray-700'
              }`}>
              <div className="font-medium truncate">{kb.name}</div>
              <div className={`text-xs mt-0.5 ${STATUS_COLORS[kb.status]}`}>
                {STATUS_LABELS[kb.status]}
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
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Nombre *</label>
              <input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                placeholder="ej: Manual de Producto v3" className={inputCls} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Descripción</label>
              <input value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
                placeholder="Para qué sirve esta KB" className={inputCls} />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Disponibilidad</label>
            <select
              value={form.accessMode}
              onChange={e => {
                const accessMode = e.target.value as 'global' | 'restricted'
                setForm(prev => ({ ...prev, accessMode }))
                setSelected(prev => prev ? { ...prev, access_mode: accessMode } : prev)
              }}
              className={inputCls}
            >
              <option value="restricted">Solo agentes asignados</option>
              <option value="global">Todos los agentes</option>
            </select>
            <p className="text-xs text-gray-500">
              Si es global, todos los agentes podran consultar esta base. Si es restringida, se asigna por agente desde Configurar.
            </p>
          </div>

          <div className="flex gap-2">
            <button onClick={save} disabled={loading}
              className="px-4 py-2 bg-violet-600 text-white text-sm rounded-lg hover:bg-violet-700 disabled:opacity-40">
              {loading ? 'Guardando...' : (isNew ? 'Crear KB' : 'Guardar')}
            </button>
            {!isNew && selected && (
              <button onClick={() => refreshSelected(selected)}
                className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 rounded-lg">
                Actualizar
              </button>
            )}
            {!isNew && selected && (
              <button onClick={reindexSelected} disabled={ingesting}
                className="px-4 py-2 text-sm text-violet-700 hover:bg-violet-50 rounded-lg disabled:opacity-40">
                {ingesting ? 'Reindexando...' : 'Reindexar KB'}
              </button>
            )}
            {!isNew && selected && (
              <button onClick={() => deleteKb(selected.id)}
                className="px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg">
                Eliminar KB
              </button>
            )}
          </div>

          {/* Fuentes — solo en modo edición de KB existente */}
          {!isNew && selected && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-gray-200 bg-white px-4 py-3">
                  <div className="text-xs text-gray-500">Vectores indexados</div>
                  <div className="text-lg font-semibold text-gray-900">{stats?.vectors_count || 0}</div>
                </div>
                <div className="rounded-xl border border-gray-200 bg-white px-4 py-3">
                  <div className="text-xs text-gray-500">Estado de colección</div>
                  <div className="text-lg font-semibold text-gray-900 capitalize">{stats?.status || selected.status || 'N/A'}</div>
                </div>
              </div>

              <div className="border-t border-gray-100 pt-4">
                <p className="text-xs font-semibold text-gray-700 mb-2">Fuentes indexadas ({sources.length})</p>
                {sources.length === 0 && (
                  <p className="text-xs text-gray-400">Sin fuentes. Agregá una URL o subí un archivo.</p>
                )}
                <div className="space-y-1 mb-3">
                  {sources.map(src => (
                    <div key={src} className="flex items-center gap-2 text-xs text-gray-700 bg-gray-50 px-3 py-1.5 rounded-lg">
                      <span className="flex-1 truncate" title={src}>{displaySource(src)}</span>
                      <button onClick={() => deleteSource(src)} className="text-red-400 hover:text-red-600 shrink-0">✕</button>
                    </div>
                  ))}
                </div>

                {/* Ingestar URL */}
                <div className="flex gap-2">
                  <input value={urlInput} onChange={e => setUrlInput(e.target.value)}
                    placeholder="https://docs.ejemplo.com/página" className={`${inputCls} flex-1`}
                    onKeyDown={e => e.key === 'Enter' && ingestUrl()} />
                  <button onClick={ingestUrl} disabled={ingesting || !urlInput.trim()}
                    className="px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg disabled:opacity-40 whitespace-nowrap">
                    {ingesting ? '...' : '+ URL'}
                  </button>
                </div>

                {/* Ingestar archivo */}
                <div className="mt-2">
                  <input ref={fileRef} type="file" accept=".pdf,.txt,.md,.docx" className="hidden"
                    onChange={e => e.target.files?.[0] && ingestFile(e.target.files[0])} />
                  <button onClick={() => fileRef.current?.click()} disabled={ingesting}
                    className="w-full py-2 border border-dashed border-gray-300 text-xs text-gray-500 rounded-lg hover:border-violet-400 hover:text-violet-600 disabled:opacity-40">
                    {ingesting ? 'Ingiriendo...' : '+ Subir archivo (PDF, TXT, MD)'}
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
          Seleccioná una KB o creá una nueva
        </div>
      )}
    </div>
  )
}

const inputCls = "w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent"

function displaySource(source: string): string {
  if (source.startsWith('http://') || source.startsWith('https://')) {
    return source
  }
  const normalized = source.replace(/\\/g, '/')
  const parts = normalized.split('/')
  return parts[parts.length - 1] || source
}
