import { useEffect, useState, type ReactNode } from 'react'
import {
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from 'react-router-dom'

import { Login } from './components/auth/Login'
import { AgentDashboard } from './components/builder/AgentDashboard'
import { APIKeysPanel } from './components/builder/APIKeysPanel'
import { CustomToolsPanel } from './components/builder/CustomToolsPanel'
import { KnowledgeBasesPanel } from './components/builder/KnowledgeBasesPanel'
import { MCPPanel } from './components/builder/MCPPanel'
import { ProvidersPanel } from './components/builder/ProvidersPanel'
import { SkillsPanel } from './components/builder/SkillsPanel'
import { AppShell } from './components/layout/AppShell'
import { AgentMonitor } from './components/monitor/AgentMonitor'
import { StandaloneChat } from './components/monitor/StandaloneChat'
import { UsageDashboard } from './components/monitor/UsageDashboard'
import { RequirementWizard } from './components/wizard/RequirementWizard'
import { agentsApi, authApi, wizardStateToSpec } from './lib/api'
import { useAuthStore } from './stores/auth'
import type { AgentDesign, WizardState } from './types/agent'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />
      <Route path="/c/:agentId" element={<StandaloneRoute />} />
      <Route element={<ProtectedLayout />}>
        <Route element={<AppShell />}>
          <Route index element={<DashboardRoute />} />
          <Route path="/wizard" element={<WizardRoute />} />
          <Route path="/agents/:agentId" element={<MonitorRoute />} />
          <Route path="/usage" element={<UsageDashboard />} />
          <Route path="/providers" element={<ProvidersPanel />} />
          <Route path="/custom-tools" element={<CustomToolsPanel />} />
          <Route path="/keys" element={<APIKeysPanel />} />
          <Route path="/skills" element={<PanelPage title="Skills"><SkillsPanel /></PanelPage>} />
          <Route path="/mcp" element={<PanelPage title="Servidores MCP"><MCPPanel /></PanelPage>} />
          <Route
            path="/knowledge-bases"
            element={<PanelPage title="Bases de conocimiento"><KnowledgeBasesPanel /></PanelPage>}
          />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function ProtectedLayout() {
  const token = useAuthStore((state) => state.token)
  const location = useLocation()

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <Outlet />
}

function LoginRoute() {
  const token = useAuthStore((state) => state.token)
  const navigate = useNavigate()

  if (token) return <Navigate to="/" replace />

  return <Login onLoginSuccess={() => navigate('/')} />
}

function DashboardRoute() {
  const navigate = useNavigate()

  return (
    <AgentDashboard
      onNewAgent={() => navigate('/wizard')}
      onSelectAgent={(agentId) => navigate(`/agents/${agentId}`)}
    />
  )
}

function WizardRoute() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleWizardComplete = async (state: WizardState) => {
    setLoading(true)
    setError('')
    try {
      const me = await authApi.me()
      const spec = wizardStateToSpec(state, me.tenant_id)
      const design = await agentsApi.createFromSpec(spec)
      navigate(`/agents/${design.agent_id}`, { state: { design } })
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || 'No se pudo generar el diseño del agente.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}
      {loading && (
        <div className="rounded-xl border border-violet-200 bg-violet-50 px-4 py-3 text-sm text-violet-700">
          Generando el diseño del agente. Esto puede tardar unos segundos.
        </div>
      )}
      <RequirementWizard onComplete={handleWizardComplete} />
    </div>
  )
}

function MonitorRoute() {
  const { agentId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const [design, setDesign] = useState<AgentDesign | null>((location.state as any)?.design ?? null)
  const [loading, setLoading] = useState(!design)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!agentId || design?.agent_id === agentId) return

    setLoading(true)
    agentsApi
      .getDesign(agentId)
      .then((data) => {
        setDesign(data)
        setError('')
      })
      .catch(() => {
        setError('No pudimos cargar el diseño del agente. Puede que todavía no esté listo o que necesite recrearse.')
      })
      .finally(() => setLoading(false))
  }, [agentId, design?.agent_id])

  if (!agentId) return <Navigate to="/" replace />

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
      </div>
    )
  }

  if (error || !design) {
    return (
      <div className="mx-auto max-w-2xl rounded-2xl border border-amber-200 bg-amber-50 px-6 py-6 text-amber-900">
        <h2 className="text-lg font-semibold">El monitor todavía no está disponible</h2>
        <p className="mt-2 text-sm text-amber-800">{error || 'No encontramos el diseño del agente.'}</p>
        <button
          onClick={() => navigate('/wizard')}
          className="mt-5 rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700"
        >
          Crear otro agente
        </button>
      </div>
    )
  }

  return <AgentMonitor design={design} onOptimized={setDesign} />
}

function StandaloneRoute() {
  const { agentId } = useParams()
  if (!agentId) return <Navigate to="/" replace />
  return <StandaloneChat agentId={agentId} />
}

function PanelPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold text-slate-950">{title}</h2>
        <p className="mt-1 text-sm text-slate-500">Configuración avanzada y catálogo operativo.</p>
      </div>
      {children}
    </div>
  )
}
