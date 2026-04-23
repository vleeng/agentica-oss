import { useEffect, useState } from 'react'
import { agentsApi } from '../../lib/api'

const API_BASE = import.meta.env.VITE_API_URL || ''

interface AgentSummary {
  agent_id: string
  name: string
  mode: 'single' | 'crew'
  framework: string
  status: string
  created_at: string
}

interface Props {
  onSelectAgent: (agentId: string) => void
  onNewAgent: () => void
}

const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  draft:    { label: 'Borrador',   cls: 'bg-gray-100 text-gray-600' },
  building: { label: 'Building',   cls: 'bg-blue-100 text-blue-700' },
  testing:  { label: 'En prueba',  cls: 'bg-amber-100 text-amber-700' },
  deployed: { label: 'Desplegado', cls: 'bg-green-100 text-green-700' },
  archived: { label: 'Archivado',  cls: 'bg-gray-100 text-gray-400' },
}

export function AgentDashboard({ onSelectAgent, onNewAgent }: Props) {
  const [agents, setAgents]     = useState<AgentSummary[]>([])
  const [billing, setBilling]   = useState<any>(null)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState('')

  useEffect(() => {
    console.log('[Agentica][Dashboard] mounted', { apiBase: API_BASE })
    loadData()
  }, [])

  const loadData = async () => {
    console.log('[Agentica][Dashboard] loadData start')
    setLoading(true)
    try {
      const token = localStorage.getItem('agentica_token')
      const headers = { Authorization: `Bearer ${token}` }
      console.log('[Agentica][Dashboard] request headers ready', { hasToken: !!token })

      const [agentsRes, billingRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/tenants/me/agents`, { headers }),
        fetch(`${API_BASE}/api/v1/tenants/me/billing`, { headers }),
      ])

      console.log('[Agentica][Dashboard] responses', {
        agentsStatus: agentsRes.status,
        billingStatus: billingRes.status,
        agentsOk: agentsRes.ok,
        billingOk: billingRes.ok,
      })

      if (!agentsRes.ok || !billingRes.ok) {
        throw new Error('No se pudieron cargar los datos del dashboard')
      }

      const [agentList, billingData] = await Promise.all([
        agentsRes.json(),
        billingRes.json(),
      ])
      console.log('[Agentica][Dashboard] payloads', {
        agentListType: Array.isArray(agentList) ? 'array' : typeof agentList,
        agentCount: Array.isArray(agentList) ? agentList.length : -1,
        billingKeys: billingData && typeof billingData === 'object' ? Object.keys(billingData) : [],
      })
      setAgents(Array.isArray(agentList) ? agentList : [])
      setBilling(billingData)
    } catch (e: any) {
      console.error('[Agentica][Dashboard] loadData error', e)
      setError('Error al cargar los datos')
    } finally {
      console.log('[Agentica][Dashboard] loadData end')
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-6 h-6 border-2 border-violet-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">

      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Mis agentes</h1>
          <p className="text-sm text-gray-500 mt-1">
            {agents.length} agente{agents.length !== 1 ? 's' : ''} en tu workspace
          </p>
        </div>
        <button
          onClick={onNewAgent}
          className="px-4 py-2 bg-violet-600 text-white text-sm rounded-lg hover:bg-violet-700 transition-colors"
        >
          + Nuevo agente
        </button>
      </div>

      {/* Billing summary */}
      {billing && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Invocaciones',   value: billing.calls?.toLocaleString() ?? '0' },
            { label: 'Tokens entrada', value: (billing.total_tokens_in ?? 0).toLocaleString() },
            { label: 'Tokens salida',  value: (billing.total_tokens_out ?? 0).toLocaleString() },
            { label: 'Costo total',    value: `$${(billing.total_cost_usd ?? 0).toFixed(4)}` },
          ].map(stat => (
            <div key={stat.label} className="bg-white border border-gray-200 rounded-xl p-4">
              <div className="text-xs text-gray-500">{stat.label}</div>
              <div className="text-xl font-semibold text-gray-900 mt-1">{stat.value}</div>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">
          {error}
        </div>
      )}

      {/* Agent list */}
      {agents.length === 0 ? (
        <EmptyState onNew={onNewAgent} />
      ) : (
        <div className="space-y-3">
          {agents.map(agent => (
            <AgentCard
              key={agent.agent_id}
              agent={agent}
              onSelect={() => onSelectAgent(agent.agent_id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}


// ── AgentCard ─────────────────────────────────────────────────────────────────

function AgentCard({
  agent,
  onSelect,
}: {
  agent: AgentSummary
  onSelect: () => void
}) {
  const status = STATUS_CONFIG[agent.status] ?? { label: agent.status, cls: 'bg-gray-100 text-gray-600' }
  const date = new Date(agent.created_at).toLocaleDateString('es-AR', {
    day: '2-digit', month: 'short', year: 'numeric'
  })

  return (
    <div
      onClick={onSelect}
      className="flex items-center gap-4 p-4 bg-white border border-gray-200 rounded-xl hover:border-violet-300 hover:shadow-sm cursor-pointer transition-all"
    >
      {/* Mode icon */}
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg flex-shrink-0 ${
        agent.mode === 'crew' ? 'bg-teal-50 text-teal-600' : 'bg-violet-50 text-violet-600'
      }`}>
        {agent.mode === 'crew' ? '⬡' : '◎'}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-gray-900 truncate">{agent.name}</span>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${status.cls}`}>
            {status.label}
          </span>
        </div>
        <div className="text-xs text-gray-500 mt-0.5 flex items-center gap-3">
          <span>{agent.framework}</span>
          <span>·</span>
          <span>{agent.mode === 'crew' ? 'Equipo' : 'Agente simple'}</span>
          <span>·</span>
          <span>{date}</span>
        </div>
      </div>

      {/* Arrow */}
      <span className="text-gray-400 flex-shrink-0">→</span>
    </div>
  )
}


// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState({ onNew }: { onNew: () => void }) {
  return (
    <div className="text-center py-20 border-2 border-dashed border-gray-200 rounded-2xl">
      <div className="text-4xl mb-4">◎</div>
      <h3 className="text-lg font-medium text-gray-700 mb-2">No tenés agentes todavía</h3>
      <p className="text-sm text-gray-500 mb-6 max-w-xs mx-auto">
        Creá tu primer agente IA en minutos con el wizard guiado.
      </p>
      <button
        onClick={onNew}
        className="px-5 py-2.5 bg-violet-600 text-white text-sm rounded-lg hover:bg-violet-700 transition-colors"
      >
        Crear mi primer agente
      </button>
    </div>
  )
}
