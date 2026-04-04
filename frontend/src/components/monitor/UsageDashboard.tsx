import { useEffect, useState } from 'react'

interface UsageSummary {
  plan_id: string
  agents: { used: number; limit: number; pct: number }
  invocations: { used: number; limit: number; pct: number }
  features: { rag: boolean; crew: boolean }
}

interface BillingDay {
  day: string
  calls: number
  tokens_in: number
  tokens_out: number
  cost_usd: number
}

interface AgentUsage {
  agent_id: string
  name: string
  status: string
  framework: string
  calls: number
  cost_usd: number
}

const PLAN_COLORS: Record<string, string> = {
  free:       'bg-gray-100 text-gray-700',
  starter:    'bg-blue-100 text-blue-700',
  pro:        'bg-violet-100 text-violet-700',
  enterprise: 'bg-amber-100 text-amber-800',
}

export function UsageDashboard() {
  const [summary, setSummary]   = useState<UsageSummary | null>(null)
  const [billing, setBilling]   = useState<{ daily: BillingDay[]; total_cost_usd: number; total_calls: number } | null>(null)
  const [agents, setAgents]     = useState<AgentUsage[]>([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState('')

  const headers = () => ({
    Authorization: `Bearer ${localStorage.getItem('agentica_token')}`,
  })

  useEffect(() => { loadAll() }, [])

  const loadAll = async () => {
    setLoading(true)
    try {
      const [s, b, a] = await Promise.all([
        fetch('/api/v1/usage/summary',  { headers: headers() }).then(r => r.json()),
        fetch('/api/v1/usage/billing?days=30', { headers: headers() }).then(r => r.json()),
        fetch('/api/v1/usage/agents',   { headers: headers() }).then(r => r.json()),
      ])
      setSummary(s)
      setBilling(b)
      setAgents(Array.isArray(a) ? a : [])
    } catch {
      setError('Error al cargar métricas')
    } finally {
      setLoading(false)
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center py-24">
      <div className="w-6 h-6 border-2 border-violet-600 border-t-transparent rounded-full animate-spin" />
    </div>
  )

  if (error) return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="px-4 py-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">{error}</div>
    </div>
  )

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">

      {/* Plan badge */}
      {summary && (
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-gray-900">Observabilidad</h1>
          <span className={`text-sm font-medium px-3 py-1 rounded-full ${PLAN_COLORS[summary.plan_id] || PLAN_COLORS.free}`}>
            Plan {summary.plan_id.charAt(0).toUpperCase() + summary.plan_id.slice(1)}
          </span>
        </div>
      )}

      {/* Límites de plan */}
      {summary && (
        <section>
          <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">Uso del plan</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <UsageBar
              label="Agentes"
              used={summary.agents.used}
              limit={summary.agents.limit}
              pct={summary.agents.pct}
            />
            <UsageBar
              label="Invocaciones este mes"
              used={summary.invocations.used}
              limit={summary.invocations.limit}
              pct={summary.invocations.pct}
            />
          </div>
          <div className="mt-3 flex gap-4">
            <FeatureBadge label="RAG"           enabled={summary.features.rag} />
            <FeatureBadge label="Multi-agente"  enabled={summary.features.crew} />
          </div>
        </section>
      )}

      {/* Billing mensual */}
      {billing && (
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide">Billing — últimos 30 días</h2>
            <div className="text-sm text-gray-500">
              <span className="font-semibold text-gray-900">{billing.total_calls.toLocaleString()}</span> llamadas ·{' '}
              <span className="font-semibold text-gray-900">${billing.total_cost_usd.toFixed(4)}</span> USD
            </div>
          </div>
          <BillingChart days={billing.daily} />
        </section>
      )}

      {/* Uso por agente */}
      {agents.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">Uso por agente</h2>
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">Agente</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">Framework</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">Estado</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-500">Llamadas</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-500">Costo</th>
                </tr>
              </thead>
              <tbody>
                {agents.map((a, i) => (
                  <tr key={a.agent_id} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                    <td className="px-4 py-3 font-medium text-gray-800">{a.name}</td>
                    <td className="px-4 py-3 text-gray-500">{a.framework}</td>
                    <td className="px-4 py-3">
                      <StatusDot status={a.status} />
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700">{a.calls.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-gray-700">${a.cost_usd.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}


// ── Sub-componentes ────────────────────────────────────────────────────────────

function UsageBar({ label, used, limit, pct }: { label: string; used: number; limit: number; pct: number }) {
  const color = pct >= 90 ? 'bg-red-500' : pct >= 70 ? 'bg-amber-500' : 'bg-violet-500'
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4">
      <div className="flex justify-between items-baseline mb-2">
        <span className="text-sm text-gray-600">{label}</span>
        <span className="text-xs text-gray-400">{used.toLocaleString()} / {limit.toLocaleString()}</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
      <div className="text-xs text-gray-400 mt-1 text-right">{pct.toFixed(1)}% usado</div>
    </div>
  )
}

function FeatureBadge({ label, enabled }: { label: string; enabled: boolean }) {
  return (
    <span className={`text-xs px-3 py-1 rounded-full border ${
      enabled
        ? 'border-green-200 bg-green-50 text-green-700'
        : 'border-gray-200 bg-gray-50 text-gray-400'
    }`}>
      {enabled ? '✓' : '✗'} {label}
    </span>
  )
}

function StatusDot({ status }: { status: string }) {
  const cfg: Record<string, { dot: string; label: string }> = {
    deployed: { dot: 'bg-green-400',  label: 'Desplegado' },
    testing:  { dot: 'bg-amber-400',  label: 'En prueba' },
    draft:    { dot: 'bg-gray-300',   label: 'Borrador' },
    building: { dot: 'bg-blue-400',   label: 'Building' },
    archived: { dot: 'bg-gray-200',   label: 'Archivado' },
  }
  const { dot, label } = cfg[status] ?? { dot: 'bg-gray-300', label: status }
  return (
    <span className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${dot}`} />
      <span className="text-xs text-gray-500">{label}</span>
    </span>
  )
}

function BillingChart({ days }: { days: BillingDay[] }) {
  if (!days.length) return (
    <div className="h-32 flex items-center justify-center text-sm text-gray-400 bg-gray-50 rounded-xl border border-gray-200">
      Sin datos de billing todavía
    </div>
  )

  const maxCalls = Math.max(...days.map(d => d.calls), 1)
  const last14   = [...days].slice(0, 14).reverse()

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4">
      <div className="flex items-end gap-1.5 h-32">
        {last14.map(d => (
          <div key={d.day} className="flex-1 flex flex-col items-center gap-1 group">
            <div
              className="w-full bg-violet-200 rounded-t group-hover:bg-violet-400 transition-colors"
              style={{ height: `${Math.max(4, (d.calls / maxCalls) * 100)}%` }}
              title={`${d.day}: ${d.calls} llamadas · $${d.cost_usd.toFixed(4)}`}
            />
          </div>
        ))}
      </div>
      <div className="flex justify-between text-xs text-gray-400 mt-2">
        <span>{last14[0]?.day?.slice(5)}</span>
        <span>hoy</span>
      </div>
    </div>
  )
}
