import { useState, useEffect } from 'react'
import { knowledgeApi } from '../../lib/api'

interface Props {
  agentId: string
}

export function KnowledgePanel({ agentId }: Props) {
  const [sources, setSources] = useState<string[]>([])
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  
  const [tab, setTab] = useState<'url' | 'file'>('url')
  const [inputUrl, setInputUrl] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [ingesting, setIngesting] = useState(false)

  const loadData = async () => {
    setLoading(true)
    try {
      const [{ sources }, st] = await Promise.all([
        knowledgeApi.getSources(agentId),
        knowledgeApi.getStats(agentId)
      ])
      setSources(sources || [])
      setStats(st)
    } catch (e: any) {
      setError('Error al cargar la base de conocimiento')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [agentId])

  const handleDelete = async (source: string) => {
    if (!confirm(`¿Eliminar ${source}?`)) return
    try {
      await knowledgeApi.deleteSource(agentId, source)
      await loadData()
    } catch (e) {
      alert('Error al eliminar fuente')
    }
  }

  const handleIngestUrl = async () => {
    if (!inputUrl.trim()) return
    setIngesting(true)
    setError('')
    try {
      await knowledgeApi.ingestJson(agentId, [inputUrl.trim()])
      setInputUrl('')
      alert('Ingesta iniciada en background. Actualiza en unos segundos con el botón de refrescar.')
      loadData()
    } catch (e) {
      setError('Error al iniciar ingesta')
    } finally {
      setIngesting(false)
    }
  }

  const handleIngestFile = async () => {
    if (!selectedFile) return
    setIngesting(true)
    setError('')
    try {
      await knowledgeApi.ingestFile(agentId, selectedFile)
      setSelectedFile(null)
      alert('Ingesta de archivo iniciada en background. Actualiza en unos segundos con el botón de refrescar.')
      loadData()
    } catch (e) {
      setError('Error al subir archivo')
    } finally {
      setIngesting(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="flex gap-4">
        <div className="p-4 bg-white border border-gray-200 rounded-xl flex-1">
          <div className="text-sm text-gray-500">Vectores indexados</div>
          <div className="text-2xl font-semibold text-gray-900">{stats?.vectors_count || 0}</div>
        </div>
        <div className="p-4 bg-white border border-gray-200 rounded-xl flex-1">
          <div className="text-sm text-gray-500">Estado de colección</div>
          <div className="text-2xl font-semibold text-gray-900 capitalize">{stats?.status || 'N/A'}</div>
        </div>
      </div>

      {/* Agregar fuente */}
      <div className="p-5 border border-gray-200 bg-gray-50 rounded-xl">
        <h3 className="text-sm font-medium text-gray-900 mb-4">Agregar Nuevo Conocimiento</h3>
        
        <div className="flex gap-2 mb-4 border-b border-gray-200 pb-2">
          <button onClick={() => setTab('url')} className={`text-sm px-2 ${tab==='url' ? 'font-semibold text-violet-700 border-b-2 border-violet-700': 'text-gray-500'}`}>Sitio Web / URL</button>
          <button onClick={() => setTab('file')} className={`text-sm px-2 ${tab==='file' ? 'font-semibold text-violet-700 border-b-2 border-violet-700': 'text-gray-500'}`}>Subir Archivo</button>
        </div>

        {tab === 'url' && (
          <div className="flex gap-2">
            <input type="url" value={inputUrl} onChange={e=>setInputUrl(e.target.value)} placeholder="https://ejemplo.com/doc.pdf o texto plano" className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg" />
            <button onClick={handleIngestUrl} disabled={ingesting || !inputUrl} className="px-4 py-2 bg-violet-600 text-white text-sm rounded-lg hover:bg-violet-700 disabled:opacity-50 transition-colors">
              {ingesting ? 'Procesando...' : 'Indexar'}
            </button>
          </div>
        )}

        {tab === 'file' && (
          <div className="flex gap-2 items-center">
            <input type="file" onChange={e=>setSelectedFile(e.target.files?.[0] || null)} className="flex-1 text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-violet-50 file:text-violet-700 hover:file:bg-violet-100" />
            <button onClick={handleIngestFile} disabled={ingesting || !selectedFile} className="px-4 py-2 bg-violet-600 text-white text-sm rounded-lg hover:bg-violet-700 disabled:opacity-50 transition-colors">
              {ingesting ? 'Subiendo...' : 'Subir e Indexar'}
            </button>
          </div>
        )}
        {error && <div className="mt-2 text-red-600 text-sm">{error}</div>}
      </div>

      {/* Lista de fuentes */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-700">Fuentes Indexadas</h3>
          <button onClick={loadData} className="text-xs text-violet-600 hover:underline">⟳ Actualizar lista</button>
        </div>
        
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden divide-y divide-gray-100">
          {loading ? (
            <div className="p-4 text-center text-sm text-gray-500">Cargando...</div>
          ) : sources.length === 0 ? (
            <div className="p-4 text-center text-sm text-gray-500">No hay fuentes indexadas.</div>
          ) : (
            sources.map(src => (
              <div key={src} className="flex items-center justify-between p-3 hover:bg-gray-50 group">
                <div className="text-sm font-medium text-gray-700 truncate" title={src}>
                  {src.length > 80 ? src.substring(0, 80) + '...' : src}
                </div>
                <button onClick={() => handleDelete(src)} className="p-1.5 text-red-500 hover:bg-red-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100 bg-white shadow-sm border border-red-100" title="Eliminar fuente">
                   <svg className="w-4 h-4" autoCapitalize="none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
