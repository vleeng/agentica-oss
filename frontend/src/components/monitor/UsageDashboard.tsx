import { BarChart3, Gauge, Layers3, Wallet } from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'

import { type AgentUsage, type BillingHistory, type UsageSummary, usageApi } from '../../lib/api'
import { formatCurrency, formatNumber } from '../../lib/utils'
import { Badge } from '../ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'

const PLAN_TONES: Record<string, 'slate' | 'blue' | 'violet' | 'amber'> = {
  free: 'slate',
  starter: 'blue',
  pro: 'violet',
  enterprise: 'amber',
}

export function UsageDashboard() {
  const [summary, setSummary] = useState<UsageSummary | null>(null)
  const [billing, setBilling] = useState<BillingHistory | null>(null)
  const [agents, setAgents] = useState<AgentUsage[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    Promise.all([usageApi.summary(), usageApi.billing(), usageApi.agents()])
      .then(([summary, billing, agents]) => {
        setSummary(summary)
        setBilling(billing)
        setAgents(agents)
        setError('')
      })
      .catch(() => setError('No pudimos cargar métricas de uso en este momento.'))
      .finally(() => setLoading(false))
  }, [])

  const chartBars = useMemo(() => {
    if (!billing?.daily?.length) return []
    const sample = [...billing.daily].slice(-14)
    const max = Math.max(...sample.map((day) => day.calls), 1)
    return sample.map((day) => ({
      ...day,
      height: Math.max(8, (day.calls / max) * 100),
    }))
  }, [billing])

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
        {error}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-slate-950">Observabilidad</h2>
          <p className="mt-1 text-sm text-slate-500">Uso, límites de plan y desempeño económico del workspace.</p>
        </div>
        {summary && (
          <Badge tone={PLAN_TONES[summary.plan_id] || 'slate'}>
            Plan {summary.plan_id.charAt(0).toUpperCase() + summary.plan_id.slice(1)}
          </Badge>
        )}
      </div>

      {summary && (
        <section className="grid gap-4 md:grid-cols-4">
          <InsightCard icon={<Layers3 className="h-5 w-5" />} label="Agentes activos">
            {formatNumber(summary.agents.used)} / {formatNumber(summary.agents.limit)}
          </InsightCard>
          <InsightCard icon={<BarChart3 className="h-5 w-5" />} label="Invocaciones del mes">
            {formatNumber(summary.invocations.used)} / {formatNumber(summary.invocations.limit)}
          </InsightCard>
          <InsightCard icon={<Wallet className="h-5 w-5" />} label="Costo acumulado">
            {formatCurrency(billing?.total_cost_usd)}
          </InsightCard>
          <InsightCard icon={<Gauge className="h-5 w-5" />} label="Features habilitadas">
            {[summary.features.rag && 'RAG', summary.features.crew && 'Multi-agente'].filter(Boolean).join(' · ') || 'Base'}
          </InsightCard>
        </section>
      )}

      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>Uso del plan</CardTitle>
            <CardDescription>Lectura rápida de capacidad consumida y margen disponible.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {summary && (
              <>
                <UsageMeter label="Capacidad de agentes" value={summary.agents.pct} />
                <UsageMeter label="Capacidad de invocaciones" value={summary.invocations.pct} />
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Billing 14 días</CardTitle>
            <CardDescription>Llamadas diarias con lectura visual directa.</CardDescription>
          </CardHeader>
          <CardContent>
            {chartBars.length === 0 ? (
              <div className="flex h-56 items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
                Sin datos de billing todavía.
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex h-56 items-end gap-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-5">
                  {chartBars.map((day) => (
                    <div key={day.day} className="group flex flex-1 flex-col items-center justify-end gap-2">
                      <div className="text-[11px] text-slate-400 opacity-0 transition group-hover:opacity-100">
                        {day.calls}
                      </div>
                      <div
                        className="w-full rounded-t-md bg-gradient-to-t from-violet-600 to-violet-300"
                        style={{ height: `${day.height}%` }}
                        title={`${day.day}: ${day.calls} llamadas · ${formatCurrency(day.cost_usd)}`}
                      />
                      <div className="text-[11px] text-slate-400">{day.day.slice(5)}</div>
                    </div>
                  ))}
                </div>
                <div className="flex justify-between text-sm text-slate-500">
                  <span>{formatNumber(billing?.total_calls)} llamadas</span>
                  <span>{formatCurrency(billing?.total_cost_usd)}</span>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Uso por agente</CardTitle>
          <CardDescription>Qué agentes están empujando consumo y costo.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {agents.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
              Todavía no hay actividad por agente para mostrar.
            </div>
          ) : (
            agents.map((agent) => (
              <div
                key={agent.agent_id}
                className="flex flex-col gap-3 rounded-xl border border-slate-200 px-4 py-4 md:flex-row md:items-center md:justify-between"
              >
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-slate-950">{agent.name}</span>
                    <Badge tone={agent.status === 'deployed' ? 'green' : agent.status === 'testing' ? 'amber' : 'slate'}>
                      {agent.status}
                    </Badge>
                  </div>
                  <div className="text-sm text-slate-500">{agent.framework}</div>
                </div>
                <div className="flex gap-8 text-sm">
                  <div>
                    <div className="text-slate-400">Llamadas</div>
                    <div className="font-semibold text-slate-950">{formatNumber(agent.calls)}</div>
                  </div>
                  <div>
                    <div className="text-slate-400">Costo</div>
                    <div className="font-semibold text-slate-950">{formatCurrency(agent.cost_usd)}</div>
                  </div>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function InsightCard({
  icon,
  label,
  children,
}: {
  icon: ReactNode
  label: string
  children: ReactNode
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-center gap-3 text-slate-600">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100">{icon}</span>
          <span className="text-sm">{label}</span>
        </div>
        <div className="mt-4 text-xl font-semibold text-slate-950">{children}</div>
      </CardContent>
    </Card>
  )
}

function UsageMeter({ label, value }: { label: string; value: number }) {
  const tone = value >= 90 ? 'from-rose-500 to-rose-400' : value >= 70 ? 'from-amber-500 to-amber-400' : 'from-violet-600 to-violet-400'

  return (
    <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-4">
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-600">{label}</span>
        <span className="font-medium text-slate-950">{value.toFixed(1)}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-200">
        <div className={`h-full rounded-full bg-gradient-to-r ${tone}`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
    </div>
  )
}
