import { ArrowRight, Bot, Cpu, Search, Sparkles, Trash2, Wallet } from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'

import { agentsApi, type AgentSummary, type TenantBillingSummary, tenantsApi } from '../../lib/api'
import { formatCurrency, formatNumber } from '../../lib/utils'
import { getAuthRole } from '../../stores/auth'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Input } from '../ui/input'

interface Props {
  onSelectAgent: (agentId: string) => void
  onNewAgent: () => void
}

const STATUS_CONFIG: Record<string, { label: string; tone: 'slate' | 'blue' | 'amber' | 'green' }> = {
  draft: { label: 'Borrador', tone: 'slate' },
  building: { label: 'Building', tone: 'blue' },
  testing: { label: 'En prueba', tone: 'amber' },
  deployed: { label: 'Desplegado', tone: 'green' },
  archived: { label: 'Archivado', tone: 'slate' },
}

export function AgentDashboard({ onSelectAgent, onNewAgent }: Props) {
  const role = getAuthRole()
  const isViewer = role === 'viewer'
  const [agents, setAgents] = useState<AgentSummary[]>([])
  const [billing, setBilling] = useState<TenantBillingSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const handleDelete = async (e: React.MouseEvent, agentId: string, name: string) => {
    e.stopPropagation()
    if (!window.confirm(`¿Eliminar el agente "${name}"? Esta acción no se puede deshacer.`)) return
    setDeletingId(agentId)
    try {
      await agentsApi.delete(agentId)
      setAgents((prev) => prev.filter((a) => a.agent_id !== agentId))
    } catch {
      setError('No se pudo eliminar el agente.')
    } finally {
      setDeletingId(null)
    }
  }

  useEffect(() => {
    setLoading(true)
    Promise.all([tenantsApi.listAgents(), tenantsApi.billing()])
      .then(([agentList, billingData]) => {
        setAgents(Array.isArray(agentList) ? agentList : [])
        setBilling(billingData)
        setError('')
      })
      .catch(() => setError('No pudimos cargar el dashboard. Revisá el backend e intentá de nuevo.'))
      .finally(() => setLoading(false))
  }, [])

  const filteredAgents = useMemo(() => {
    const term = query.trim().toLowerCase()
    if (!term) return agents
    return agents.filter((agent) => {
      return [agent.name, agent.framework, agent.status, agent.mode].some((value) =>
        value.toLowerCase().includes(term)
      )
    })
  }, [agents, query])

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
        <Card className="overflow-hidden border-slate-200 bg-[linear-gradient(135deg,#111827_0%,#1e1b4b_45%,#312e81_100%)] text-white shadow-[0_22px_65px_rgba(49,46,129,0.25)]">
          <CardContent className="flex h-full flex-col justify-between gap-6 p-8">
            <div className="space-y-4">
              <Badge className="w-fit border-none bg-white/10 text-violet-100" tone="slate">
                Control room
              </Badge>
              <div>
                <h1 className="max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">
                  Diseñá, operá y ajustá tus agentes desde una sola consola.
                </h1>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-200">
                  Tenés una vista unificada de agentes, consumo y estado operativo, con un flujo listo para ir de idea a monitor sin perder contexto.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {!isViewer && (
                <Button onClick={onNewAgent} size="lg">
                  <Sparkles className="h-4 w-4" />
                  Crear agente
                </Button>
              )}
              <Button variant="secondary" size="lg" onClick={() => setQuery('deployed')}>
                Ver desplegados
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200 bg-white/80">
          <CardHeader>
            <CardTitle>Panorama rápido</CardTitle>
            <CardDescription>Lectura operativa del workspace actual.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <MetricLine icon={<Bot className="h-4 w-4" />} label="Agentes totales" value={String(agents.length)} />
            <MetricLine
              icon={<Cpu className="h-4 w-4" />}
              label="Desplegados"
              value={String(agents.filter((agent) => agent.status === 'deployed').length)}
            />
            <MetricLine
              icon={<Wallet className="h-4 w-4" />}
              label="Costo acumulado"
              value={formatCurrency(billing?.total_cost_usd)}
            />
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 md:grid-cols-4">
        <StatCard label="Invocaciones" value={formatNumber(billing?.calls)} />
        <StatCard label="Tokens de entrada" value={formatNumber(billing?.total_tokens_in)} />
        <StatCard label="Tokens de salida" value={formatNumber(billing?.total_tokens_out)} />
        <StatCard label="Costo total" value={formatCurrency(billing?.total_cost_usd)} />
      </section>

      <Card>
        <CardHeader className="gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <CardTitle>Agentes</CardTitle>
            <CardDescription>Buscá, abrí y retomá cualquier agente del workspace.</CardDescription>
          </div>
          <div className="relative w-full md:max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar por nombre, framework o estado"
              className="pl-9"
            />
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {error}
            </div>
          )}

          {filteredAgents.length === 0 ? (
            <EmptyState onNew={onNewAgent} filtered={!!query} canCreate={!isViewer} />
          ) : (
            <div className="grid gap-3">
              {filteredAgents.map((agent) => (
                <button
                  key={agent.agent_id}
                  onClick={() => onSelectAgent(agent.agent_id)}
                  className="group rounded-2xl border border-slate-200 bg-white px-5 py-4 text-left transition hover:border-violet-300 hover:bg-violet-50/40 hover:shadow-sm"
                >
                  <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div className="flex min-w-0 items-start gap-4">
                      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-violet-100 text-violet-700">
                        {agent.mode === 'crew' ? '◫' : '◉'}
                      </div>
                      <div className="min-w-0 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="truncate text-base font-semibold text-slate-950">{agent.name}</h3>
                          <Badge tone={STATUS_CONFIG[agent.status]?.tone || 'slate'}>
                            {STATUS_CONFIG[agent.status]?.label || agent.status}
                          </Badge>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
                          <span>{agent.framework}</span>
                          <span>•</span>
                          <span>{agent.mode === 'crew' ? 'Equipo de agentes' : 'Agente simple'}</span>
                          <span>•</span>
                          <span>{new Date(agent.created_at).toLocaleDateString('es-AR')}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      {!isViewer && (
                        <button
                          onClick={(e) => handleDelete(e, agent.agent_id, agent.name)}
                          disabled={deletingId === agent.agent_id}
                          className="rounded-lg p-2 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600 disabled:opacity-40"
                          title="Eliminar agente"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                      <span className="flex items-center gap-2 text-sm font-medium text-violet-700">
                        Abrir monitor
                        <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
                      </span>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card className="bg-white/90">
      <CardContent className="p-5">
        <div className="text-sm text-slate-500">{label}</div>
        <div className="mt-2 text-2xl font-semibold text-slate-950">{value}</div>
      </CardContent>
    </Card>
  )
}

function MetricLine({
  icon,
  label,
  value,
}: {
  icon: ReactNode
  label: string
  value: string
}) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
      <div className="flex items-center gap-3 text-slate-600">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-white">{icon}</span>
        <span className="text-sm">{label}</span>
      </div>
      <span className="text-lg font-semibold text-slate-950">{value}</span>
    </div>
  )
}

function EmptyState({
  onNew,
  filtered,
  canCreate,
}: {
  onNew: () => void
  filtered: boolean
  canCreate: boolean
}) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-6 py-16 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-100 text-2xl text-violet-700">
        ◉
      </div>
      <h3 className="mt-5 text-lg font-semibold text-slate-900">
        {filtered ? 'No encontramos agentes con ese criterio' : 'Todavía no creaste agentes'}
      </h3>
      <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-slate-500">
        {filtered
          ? 'Probá otra búsqueda o limpiá el filtro para ver todo el workspace.'
          : 'Arrancá desde el wizard y pasá de idea a monitor con un flujo guiado y listo para operar.'}
      </p>
      {!filtered && canCreate && (
        <Button onClick={onNew} className="mt-6">
          Crear mi primer agente
        </Button>
      )}
    </div>
  )
}
