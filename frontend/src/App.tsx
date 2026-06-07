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

import { AccountPanel } from './components/account/AccountPanel'
import { AccessPanel } from './components/admin/AccessPanel'
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
import { ChatWizard } from './components/wizard/ChatWizard'
import { RequirementWizard } from './components/wizard/RequirementWizard'
import { useProductProfile } from './contexts/ProductProfileContext'
import { agentsApi, authApi, wizardStateToSpec } from './lib/api'
import { getProductBranding } from './lib/productBranding'
import { getAuthRole, useAuthStore } from './stores/auth'
import type { AgentDesign, WizardState } from './types/agent'

export default function App() {
  const product = useProductProfile()

  return (
    <Routes>
      <Route path="login" element={<LoginRoute />} />
      <Route path="c/:agentId" element={<StandaloneRoute />} />
      <Route element={<ProtectedLayout />}>
        <Route element={<AppShell />}>
          <Route index element={<DashboardRoute />} />
          <Route path="wizard" element={<DeveloperOnly><WizardRoute /></DeveloperOnly>} />
          <Route path="agents/:agentId" element={<MonitorRoute />} />
          <Route path="usage" element={product.features.billing ? <UsageDashboard /> : <Navigate to="/" replace />} />
          <Route path="account" element={<AccountPanel />} />
          <Route path="access" element={<OwnerOnly><AccessPanel /></OwnerOnly>} />
          <Route path="providers" element={<DeveloperOnly><ProvidersPanel /></DeveloperOnly>} />
          <Route path="custom-tools" element={<DeveloperOnly><CustomToolsPanel /></DeveloperOnly>} />
          <Route path="keys" element={<DeveloperOnly><APIKeysPanel /></DeveloperOnly>} />
          <Route path="skills" element={<DeveloperOnly><PanelPage title="Skills"><SkillsPanel /></PanelPage></DeveloperOnly>} />
          <Route path="mcp" element={<DeveloperOnly><PanelPage title="Servidores MCP"><MCPPanel /></PanelPage></DeveloperOnly>} />
          <Route
            path="knowledge-bases"
            element={<DeveloperOnly><PanelPage title="Bases de conocimiento"><KnowledgeBasesPanel /></PanelPage></DeveloperOnly>}
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

function DeveloperOnly({ children }: { children: ReactNode }) {
  const role = getAuthRole()
  if (role === 'viewer') return <Navigate to="/" replace />
  return <>{children}</>
}

function OwnerOnly({ children }: { children: ReactNode }) {
  const role = getAuthRole()
  if (role !== 'owner') return <Navigate to="/" replace />
  return <>{children}</>
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
  const product = useProductProfile()
  const branding = getProductBranding(product)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [wizardVariant, setWizardVariant] = useState<'classic' | 'chat'>('classic')

  const handleWizardComplete = async (state: WizardState) => {
    setLoading(true)
    setError('')
    try {
      const me = await authApi.me()
      const spec = wizardStateToSpec(state, me.tenant_id)
      const design = await agentsApi.createFromSpec(spec)
      navigate(`/agents/${design.agent_id}`, { state: { design } })
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || 'No se pudo generar el diseno del agente.')
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
          Generando el diseno del agente. Esto puede tardar unos segundos.
        </div>
      )}

      <div className="rounded-[32px] border border-white/60 bg-white/88 p-5 shadow-[0_28px_80px_rgba(15,23,42,0.08)]">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-violet-500">Modo de creacion</p>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <button
            type="button"
            onClick={() => setWizardVariant('classic')}
            className={`rounded-[28px] border px-5 py-5 text-left transition ${
              wizardVariant === 'classic'
                ? 'border-violet-300 bg-violet-50 shadow-[0_16px_45px_rgba(124,58,237,0.12)]'
                : 'border-slate-200 bg-white hover:border-slate-300'
            }`}
          >
            <div className="text-xs font-semibold uppercase tracking-[0.24em] text-violet-500">Wizard clasico</div>
            <h3 className="mt-2 text-xl font-semibold text-slate-950">Formulario paso a paso</h3>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              Ideal si ya sabes que queres definir y preferis controlar cada seccion del spec manualmente.
            </p>
          </button>
          <button
            type="button"
            onClick={() => setWizardVariant('chat')}
            className={`rounded-[28px] border px-5 py-5 text-left transition ${
              wizardVariant === 'chat'
                ? 'border-violet-300 bg-violet-50 shadow-[0_16px_45px_rgba(124,58,237,0.12)]'
                : 'border-slate-200 bg-white hover:border-slate-300'
            }`}
          >
            <div className="text-xs font-semibold uppercase tracking-[0.24em] text-violet-500">Wizard asistido por chat</div>
            <h3 className="mt-2 text-xl font-semibold text-slate-950">Conversacion guiada</h3>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              {branding.appName} te hace preguntas, arma el borrador estructurado y te deja crear el agente cuando quede listo.
            </p>
          </button>
        </div>
      </div>

      {wizardVariant === 'classic' ? (
        <RequirementWizard onComplete={handleWizardComplete} />
      ) : (
        <ChatWizard onComplete={handleWizardComplete} />
      )}
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
        setError('No pudimos cargar el diseno del agente. Puede que todavia no este listo o que necesite recrearse.')
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
        <h2 className="text-lg font-semibold">El monitor todavia no esta disponible</h2>
        <p className="mt-2 text-sm text-amber-800">{error || 'No encontramos el diseno del agente.'}</p>
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
        <p className="mt-1 text-sm text-slate-500">Configuracion avanzada y catalogo operativo.</p>
      </div>
      {children}
    </div>
  )
}
