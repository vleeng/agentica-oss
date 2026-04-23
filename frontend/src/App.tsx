import { useState, useEffect } from 'react'
import { RequirementWizard } from './components/wizard/RequirementWizard'
import { AgentMonitor }      from './components/monitor/AgentMonitor'
import { AgentDashboard }    from './components/builder/AgentDashboard'
import { APIKeysPanel }      from './components/builder/APIKeysPanel'
import { UsageDashboard }    from './components/monitor/UsageDashboard'
import { StandaloneChat }    from './components/monitor/StandaloneChat'
import { Login }             from './components/auth/Login'
import { ProvidersPanel }    from './components/builder/ProvidersPanel'
import { CustomToolsPanel } from './components/builder/CustomToolsPanel'
import { SkillsPanel }        from './components/builder/SkillsPanel'
import { MCPPanel }           from './components/builder/MCPPanel'
import { KnowledgeBasesPanel } from './components/builder/KnowledgeBasesPanel'
import { agentsApi, authApi, wizardStateToSpec } from './lib/api'
import type { AgentDesign, WizardState } from './types/agent'

type View = 'dashboard' | 'wizard' | 'monitor' | 'keys' | 'usage' | 'providers' | 'custom_tools' | 'skills' | 'mcp' | 'knowledge_bases'

export default function App() {
  console.log('[Agentica][App] render start', {
    pathname: window.location.pathname,
    baseUrl: import.meta.env.BASE_URL,
    apiUrl: import.meta.env.VITE_API_URL,
    wsUrl: import.meta.env.VITE_WS_URL,
    hasToken: !!localStorage.getItem('agentica_token'),
  })
  // Interceptar ruta standalone
  const path = window.location.pathname
  if (path.startsWith('/c/')) {
    const standaloneAgentId = path.split('/')[2]
    console.log('[Agentica][App] standalone route detected', { standaloneAgentId })
    if (standaloneAgentId) return <StandaloneChat agentId={standaloneAgentId} />
  }

  const [view, setView]       = useState<View>('dashboard')
  const [design, setDesign]   = useState<AgentDesign | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')
  const [authed, setAuthed]   = useState(!!localStorage.getItem('agentica_token'))
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  useEffect(() => {
    console.log('[Agentica][App] auth state changed', { authed })
  }, [authed])

  useEffect(() => {
    console.log('[Agentica][App] view changed', { view, hasDesign: !!design, loading, error })
  }, [view, design, loading, error])

  if (!authed) {
    return <Login onLoginSuccess={() => {
      console.log('[Agentica][App] login success callback')
      setAuthed(true)
    }} />
  }

  const handleWizardComplete = async (state: WizardState) => {
    console.log('[Agentica][App] handleWizardComplete start', { name: state.name, mode: state.mode })
    setLoading(true)
    setError('')
    try {
      const me = await authApi.me()
      console.log('[Agentica][App] authApi.me success', me)
      const spec = wizardStateToSpec(state, me.tenant_id)
      const agentDesign = await agentsApi.createFromSpec(spec)
      console.log('[Agentica][App] createFromSpec success', { agentId: agentDesign.agent_id })
      setDesign(agentDesign)
      setView('monitor')
    } catch (e: any) {
      console.error('[Agentica][App] handleWizardComplete error', e)
      setError(e.response?.data?.detail || e.message || 'Error al crear el agente')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectAgent = async (agentId: string) => {
    console.log('[Agentica][App] handleSelectAgent start', { agentId })
    try {
      const d = await agentsApi.getDesign(agentId)
      console.log('[Agentica][App] getDesign success', { agentId })
      setDesign(d)
      setView('monitor')
    } catch (e) {
      console.error('[Agentica][App] handleSelectAgent error', e)
      // El agente existe en DB pero no tiene runtime activo todavía
      // Mostrar un mensaje claro en lugar de pantalla en blanco
      setError(`El agente seleccionado necesita ser buildeado primero. Crealo nuevamente desde el wizard.`)
    }
  }

  const NAV: Array<{ id: View; label: string; group?: string }> = [
    { id: 'dashboard',   label: 'Agentes' },
    { id: 'usage',       label: 'Uso' },
    { id: 'providers',   label: 'Bóveda IA' },
    { id: 'custom_tools', label: 'Mis Tools' },
    { id: 'keys',        label: 'API Keys' },
    { id: 'skills',         label: 'Skills',      group: 'Librería' },
    { id: 'mcp',            label: 'MCPs',         group: 'Librería' },
    { id: 'knowledge_bases', label: 'Conocimiento', group: 'Librería' },
  ]

  return (
    <div className="flex flex-col md:flex-row h-screen bg-gray-50 overflow-hidden w-full">
      {/* Mobile Top Bar */}
      <div className="md:hidden flex items-center justify-between bg-gray-900 px-4 py-3 shrink-0 border-b border-gray-800">
        <span className="text-lg font-bold text-violet-400 tracking-tight">AGENTICA</span>
        <button onClick={() => setMobileMenuOpen(true)} className="text-gray-400 hover:text-white p-1">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>
        </button>
      </div>

      {/* Mobile Overlay */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-40 bg-gray-900/60 transition-opacity md:hidden" onClick={() => setMobileMenuOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`fixed inset-y-0 left-0 z-50 w-64 bg-gray-900 border-r border-gray-800 flex flex-col flex-shrink-0 transition-transform duration-300 ease-in-out md:relative md:translate-x-0 ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="px-6 py-5 border-b border-gray-800 flex items-center justify-between min-h-[60px]">
          <button onClick={() => { setView('dashboard'); setMobileMenuOpen(false); }}
            className="text-xl font-bold text-violet-400 tracking-tight transition-colors hover:text-violet-300">
            AGENTICA
          </button>
          <button onClick={() => setMobileMenuOpen(false)} className="md:hidden text-gray-400 hover:text-white p-1">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        
        <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
          {/* Navegación principal */}
          {NAV.filter(n => !n.group).map(nav => (
            <button key={nav.id} onClick={() => { setView(nav.id); setMobileMenuOpen(false); }}
              className={`w-full flex items-center px-4 py-2.5 text-sm rounded-lg transition-colors text-left ${
                view === nav.id
                  ? 'bg-violet-600 text-white font-medium shadow-sm'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              }`}>
              {nav.label}
            </button>
          ))}
          {/* Librería */}
          <div className="pt-4">
            <p className="px-4 pb-1 text-xs font-semibold text-gray-600 uppercase tracking-wider">Librería</p>
            {NAV.filter(n => n.group === 'Librería').map(nav => (
              <button key={nav.id} onClick={() => { setView(nav.id); setMobileMenuOpen(false); }}
                className={`w-full flex items-center px-4 py-2.5 text-sm rounded-lg transition-colors text-left ${
                  view === nav.id
                    ? 'bg-violet-600 text-white font-medium shadow-sm'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                }`}>
                {nav.label}
              </button>
            ))}
          </div>
        </nav>
        
        <div className="p-4 border-t border-gray-800">
          <a href="/docs" target="_blank" rel="noopener noreferrer"
            className="flex items-center px-4 py-2 text-sm text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors">
            API Docs ↗
          </a>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 min-w-0 overflow-y-auto w-full">
        <main>

        {loading && (
          <div className="flex flex-col items-center justify-center py-24 gap-3">
            <div className="w-8 h-8 border-2 border-violet-600 border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-gray-500">Generando diseño del agente...</p>
          </div>
        )}

        {!loading && error && (
          <div className="max-w-2xl mx-auto mt-8 px-4">
            <div className="px-4 py-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">{error}</div>
            <button onClick={() => { setError(''); setView('wizard') }}
              className="mt-4 text-sm text-violet-600 hover:text-violet-800">
              ← Volver al wizard
            </button>
          </div>
        )}

        {!loading && !error && view === 'dashboard' && (
          <AgentDashboard onSelectAgent={handleSelectAgent} onNewAgent={() => setView('wizard')} />
        )}
        {!loading && !error && view === 'wizard'    && <RequirementWizard onComplete={handleWizardComplete} />}
        {!loading && !error && view === 'monitor'   && design && <AgentMonitor design={design} onOptimized={setDesign} />}
        {!loading && !error && view === 'providers' && <ProvidersPanel />}
        {!loading && !error && view === 'keys'      && <APIKeysPanel />}
        {!loading && !error && view === 'usage'     && <UsageDashboard />}
        {!loading && !error && view === 'custom_tools'    && <CustomToolsPanel />}
        {!loading && !error && view === 'skills'          && (
          <div className="max-w-4xl mx-auto px-6 py-8">
            <h1 className="text-xl font-semibold text-gray-900 mb-6">Skills</h1>
            <SkillsPanel />
          </div>
        )}
        {!loading && !error && view === 'mcp'             && (
          <div className="max-w-4xl mx-auto px-6 py-8">
            <h1 className="text-xl font-semibold text-gray-900 mb-6">Servidores MCP</h1>
            <MCPPanel />
          </div>
        )}
        {!loading && !error && view === 'knowledge_bases' && (
          <div className="max-w-4xl mx-auto px-6 py-8">
            <h1 className="text-xl font-semibold text-gray-900 mb-6">Bases de Conocimiento</h1>
            <KnowledgeBasesPanel />
          </div>
        )}
        </main>
      </div>
    </div>
  )
}
