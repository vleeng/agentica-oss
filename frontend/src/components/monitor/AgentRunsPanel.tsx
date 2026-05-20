import { Bot, RefreshCcw } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { agentsApi } from '../../lib/api'
import type { AgentRunEvent, AgentRunSummary, AgentRunTrace } from '../../types/agent'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Input } from '../ui/input'
import { RichText } from '../visual/RichText'

interface Props {
  agentId: string
}

const timeFormatter = new Intl.DateTimeFormat('es-AR', {
  dateStyle: 'short',
  timeStyle: 'short',
})

export function AgentRunsPanel({ agentId }: Props) {
  const [runs, setRuns] = useState<AgentRunSummary[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string>('')
  const [trace, setTrace] = useState<AgentRunTrace | null>(null)
  const [loadingRuns, setLoadingRuns] = useState(false)
  const [loadingTrace, setLoadingTrace] = useState(false)
  const [error, setError] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | AgentRunSummary['status']>('all')
  const [search, setSearch] = useState('')
  const [onlyKnowledge, setOnlyKnowledge] = useState(false)
  const [onlyWeb, setOnlyWeb] = useState(false)
  const [onlyErrors, setOnlyErrors] = useState(false)

  const refreshRuns = async (preferredRunId?: string) => {
    setLoadingRuns(true)
    setError('')
    try {
      const rows = await agentsApi.getRuns(agentId, 30)
      setRuns(rows)
      const nextSelected = preferredRunId || selectedRunId || rows[0]?.conversation_id || ''
      setSelectedRunId(nextSelected)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'No se pudieron cargar las ejecuciones.')
    } finally {
      setLoadingRuns(false)
    }
  }

  useEffect(() => {
    refreshRuns()
  }, [agentId])

  useEffect(() => {
    if (!selectedRunId) {
      setTrace(null)
      return
    }
    setLoadingTrace(true)
    setError('')
    agentsApi
      .getRunTrace(agentId, selectedRunId)
      .then((result) => setTrace(result))
      .catch((err: any) => setError(err.response?.data?.detail || err.message || 'No se pudo cargar la traza de la ejecucion.'))
      .finally(() => setLoadingTrace(false))
  }, [agentId, selectedRunId])

  const responseMessages = useMemo(
    () => (trace?.messages || []).filter((message) => message.role === 'assistant' && message.content.trim()),
    [trace],
  )

  const eventItems = useMemo(() => (trace?.events || []).filter((event) => event.message.trim()), [trace])

  const filteredRuns = useMemo(() => {
    const term = search.trim().toLowerCase()
    return runs.filter((run) => {
      if (statusFilter !== 'all' && run.status !== statusFilter) return false
      if (onlyKnowledge && run.kb_events <= 0) return false
      if (onlyWeb && run.web_events <= 0) return false
      if (onlyErrors && run.error_events <= 0) return false
      if (!term) return true
      const haystack = [run.channel, run.last_user_message, run.last_assistant_message, run.session_id].join(' ').toLowerCase()
      return haystack.includes(term)
    })
  }, [onlyErrors, onlyKnowledge, onlyWeb, runs, search, statusFilter])

  const runMetrics = useMemo(() => {
    const failed = runs.filter((run) => run.status === 'failed').length
    const withIssues = runs.filter((run) => run.status === 'completed_with_issues').length
    const withKnowledge = runs.filter((run) => run.kb_events > 0).length
    const withWeb = runs.filter((run) => run.web_events > 0).length
    return { failed, withIssues, withKnowledge, withWeb }
  }, [runs])

  return (
    <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
      <Card className="overflow-hidden">
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle>Ejecuciones recientes</CardTitle>
            <CardDescription>Runs del agente con tools, KBs, skills y respuesta final.</CardDescription>
          </div>
          <Button variant="secondary" size="sm" onClick={() => refreshRuns()} disabled={loadingRuns}>
            <RefreshCcw className={`h-4 w-4 ${loadingRuns ? 'animate-spin' : ''}`} />
            Actualizar
          </Button>
        </CardHeader>
        <CardContent>
          <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <RunMetric title="Runs" value={String(runs.length)} />
            <RunMetric title="Fallidas" value={String(runMetrics.failed)} tone="rose" />
            <RunMetric title="Con KB" value={String(runMetrics.withKnowledge)} tone="violet" />
            <RunMetric title="Con web" value={String(runMetrics.withWeb)} tone="blue" />
          </div>

          <div className="mb-5 space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Buscar por mensaje, canal o session_id"
            />
            <div className="flex flex-wrap gap-2">
              {(
                [
                  ['all', 'Todos'],
                  ['completed', 'Completados'],
                  ['completed_with_issues', 'Con incidencias'],
                  ['failed', 'Fallidos'],
                  ['in_progress', 'En progreso'],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setStatusFilter(value)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                    statusFilter === value
                      ? 'border-violet-300 bg-violet-100 text-violet-700'
                      : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <FilterChip active={onlyKnowledge} onClick={() => setOnlyKnowledge((current) => !current)} label="Solo con KB" />
              <FilterChip active={onlyWeb} onClick={() => setOnlyWeb((current) => !current)} label="Solo con web" />
              <FilterChip active={onlyErrors} onClick={() => setOnlyErrors((current) => !current)} label="Solo con errores" tone="rose" />
            </div>
          </div>

          {error && !runs.length ? (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
          ) : runs.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">
              Todavia no hay ejecuciones registradas para este agente.
            </div>
          ) : filteredRuns.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">
              No hay ejecuciones que coincidan con los filtros actuales.
            </div>
          ) : (
            <div className="space-y-3">
              {filteredRuns.map((run) => {
                const selected = run.conversation_id === selectedRunId
                return (
                  <button
                    key={run.conversation_id}
                    type="button"
                    onClick={() => setSelectedRunId(run.conversation_id)}
                    className={`w-full rounded-2xl border p-4 text-left transition ${
                      selected
                        ? 'border-violet-300 bg-violet-50 shadow-sm'
                        : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={toneForStatus(run.status)}>{labelForStatus(run.status)}</Badge>
                      <Badge tone={selected ? 'violet' : 'slate'}>{run.channel}</Badge>
                      {run.error_events > 0 && <Badge tone="rose">{run.error_events} errores</Badge>}
                      <span className="text-xs text-slate-500">{timeFormatter.format(new Date(run.last_activity_at))}</span>
                    </div>
                    <div className="mt-3 text-sm font-semibold text-slate-900">{truncate(run.last_user_message || 'Sin mensaje de usuario')}</div>
                    <p className="mt-2 text-xs leading-5 text-slate-500">{truncate(run.last_assistant_message || 'Todavia sin respuesta final', 180)}</p>
                    <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-500">
                      <span>{run.message_count} mensajes</span>
                      <span>{run.event_count} eventos</span>
                      {run.error_events > 0 && <span>{run.error_events} errores</span>}
                      {run.tool_events > 0 && <span>{run.tool_events} tools</span>}
                      {run.kb_events > 0 && <span>{run.kb_events} accesos KB</span>}
                      {run.web_events > 0 && <span>{run.web_events} busquedas web</span>}
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="overflow-hidden">
        <CardHeader>
          <CardTitle>Timeline de ejecucion</CardTitle>
          <CardDescription>Detalle cronologico de skills, conocimiento, tools y respuesta.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {error && runs.length > 0 && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
          )}

          {!selectedRunId ? (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">
              Elegi una ejecucion para ver el detalle.
            </div>
          ) : loadingTrace ? (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">
              Cargando timeline de la ejecucion...
            </div>
          ) : trace ? (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                <RunMetric title="Canal" value={trace.channel} />
                <RunMetric title="Inicio" value={timeFormatter.format(new Date(trace.created_at))} />
                <RunMetric title="Ultima actividad" value={timeFormatter.format(new Date(trace.last_activity_at))} />
              </div>

              <div className="space-y-3">
                {eventItems.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">
                    Esta ejecucion no dejo eventos operativos todavia.
                  </div>
                ) : (
                  eventItems.map((event) => (
                    <div key={event.id} className="rounded-xl border border-slate-200 bg-white p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={toneForEvent(event)}>{labelForEvent(event)}</Badge>
                        {event.actor && <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{event.actor}</span>}
                        <span className="text-xs text-slate-400">{timeFormatter.format(new Date(event.created_at))}</span>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-700">{event.message}</p>
                      {renderEventPayload(event)}
                    </div>
                  ))
                )}
              </div>

              {responseMessages.length > 0 && (
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <Bot className="h-4 w-4 text-violet-600" />
                    Ultima respuesta del agente
                  </div>
                  <RichText content={responseMessages[responseMessages.length - 1].content} />
                </div>
              )}
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}

function RunMetric({
  title,
  value,
  tone = 'slate',
}: {
  title: string
  value: string
  tone?: 'slate' | 'violet' | 'blue' | 'rose'
}) {
  return (
    <div
      className={`rounded-xl border p-4 ${
        tone === 'rose'
          ? 'border-rose-200 bg-rose-50'
          : tone === 'violet'
            ? 'border-violet-200 bg-violet-50'
            : tone === 'blue'
              ? 'border-blue-200 bg-blue-50'
              : 'border-slate-200 bg-slate-50'
      }`}
    >
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</div>
      <div className="mt-2 text-sm font-medium text-slate-900">{value}</div>
    </div>
  )
}

function FilterChip({
  active,
  onClick,
  label,
  tone = 'violet',
}: {
  active: boolean
  onClick: () => void
  label: string
  tone?: 'violet' | 'rose'
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
        active
          ? tone === 'rose'
            ? 'border-rose-300 bg-rose-100 text-rose-700'
            : 'border-violet-300 bg-violet-100 text-violet-700'
          : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
      }`}
    >
      {label}
    </button>
  )
}

function labelForStatus(status: AgentRunSummary['status']) {
  if (status === 'completed') return 'Completado'
  if (status === 'completed_with_issues') return 'Con incidencias'
  if (status === 'failed') return 'Fallido'
  return 'En progreso'
}

function toneForStatus(status: AgentRunSummary['status']): 'slate' | 'violet' | 'blue' | 'green' | 'amber' | 'rose' {
  if (status === 'completed') return 'green'
  if (status === 'completed_with_issues') return 'amber'
  if (status === 'failed') return 'rose'
  return 'slate'
}

function labelForEvent(event: AgentRunEvent): string {
  if (event.kind === 'runtime_error' || event.event_type === 'runtime_error') return 'Error'
  if (event.kind === 'kb_context') return 'KBs activas'
  if (event.kind === 'skill_context') return 'Skills activados'
  if (event.kind === 'rag_result' || event.kind === 'rag_preview') return 'Conocimiento'
  if (event.kind === 'web_result' || event.kind === 'web_error') return 'Busqueda web'
  if (event.event_type === 'response_final') return 'Respuesta'
  if (event.event_type === 'invoke_start') return 'Inicio'
  return event.phase || event.event_type
}

function toneForEvent(event: AgentRunEvent): 'slate' | 'violet' | 'blue' | 'green' | 'amber' | 'rose' {
  if (event.kind === 'runtime_error' || event.event_type === 'runtime_error' || event.kind === 'web_error') return 'rose'
  if (event.kind === 'rag_result' || event.kind === 'rag_preview' || event.kind === 'kb_context') return 'violet'
  if (event.kind === 'web_result') return 'blue'
  if (event.kind === 'skill_context') return 'amber'
  if (event.event_type === 'response_final') return 'green'
  return 'slate'
}

function renderEventPayload(event: AgentRunEvent) {
  const payload = event.payload || {}
  const resultCount =
    typeof payload.result_count === 'number'
      ? payload.result_count
      : typeof payload.result_count === 'string' && payload.result_count.trim()
        ? Number(payload.result_count)
        : null

  if (event.kind === 'rag_result' && Array.isArray(payload.titles) && payload.titles.length > 0) {
    return (
      <>
        {Number.isFinite(resultCount) && resultCount !== null ? (
          <p className="mt-2 text-xs leading-5 text-slate-500">Resultados: {resultCount}</p>
        ) : null}
        <p className="mt-1 text-xs leading-5 text-slate-500">Titulos: {payload.titles.slice(0, 3).join(' | ')}</p>
      </>
    )
  }
  if (event.kind === 'web_result') {
    return Number.isFinite(resultCount) && resultCount !== null ? (
      <p className="mt-2 text-xs leading-5 text-slate-500">Resultados: {resultCount}</p>
    ) : null
  }
  if (event.kind === 'rag_preview') {
    return null
  }
  if (event.kind === 'web_error' && typeof payload.raw_output === 'string' && payload.raw_output.trim()) {
    return <p className="mt-2 text-xs leading-5 text-rose-600">{truncate(payload.raw_output, 220)}</p>
  }
  if ((event.kind === 'runtime_error' || event.event_type === 'runtime_error') && typeof payload.error === 'string' && payload.error.trim()) {
    return <p className="mt-2 text-xs leading-5 text-rose-600">{truncate(payload.error, 220)}</p>
  }
  if (event.kind === 'kb_context' && Array.isArray(payload.knowledge_bases) && payload.knowledge_bases.length > 0) {
    return <p className="mt-2 text-xs leading-5 text-slate-500">{payload.knowledge_bases.map((kb: any) => kb?.name).filter(Boolean).join(' | ')}</p>
  }
  if (event.kind === 'skill_context' && Array.isArray(payload.skills) && payload.skills.length > 0) {
    return <p className="mt-2 text-xs leading-5 text-slate-500">{payload.skills.join(' | ')}</p>
  }
  return null
}

function truncate(value: unknown, maxLength = 120) {
  const text = String(value || '').trim()
  if (!text) return ''
  return text.length > maxLength ? `${text.slice(0, maxLength - 3)}...` : text
}
