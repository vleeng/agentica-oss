import { useEffect, useMemo, useRef, useState } from 'react'

import { knowledgeBasesApi, wizardChatApi } from '../../lib/api'
import type { KnowledgeBase, WizardChatSession, WizardState } from '../../types/agent'

interface ChatWizardProps {
  onComplete: (state: WizardState) => void
}

const focusLabels: Record<string, string> = {
  intro: 'Objetivo y tipo',
  execution: 'Modo de ejecucion',
  name: 'Nombre operativo',
  behavior: 'Modo y estructura',
  knowledge: 'Conocimiento interno',
  channels: 'Canales',
  review: 'Revision final',
}

export function ChatWizard({ onComplete }: ChatWizardProps) {
  const [session, setSession] = useState<WizardChatSession | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([])
  const scrollRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    wizardChatApi
      .start()
      .then((data) => {
        if (!cancelled) {
          setSession(data)
          setError('')
        }
      })
      .catch((err: any) => {
        if (!cancelled) {
          setError(err.response?.data?.detail || err.message || 'No pudimos iniciar el wizard asistido.')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    knowledgeBasesApi
      .list()
      .then((rows) => setKnowledgeBases(Array.isArray(rows) ? rows : []))
      .catch(() => setKnowledgeBases([]))
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [session?.messages.length, sending])

  const draft = session?.draft_state
  const summaryItems = useMemo(() => {
    if (!draft) return []
    const selectedKnowledgeBases = knowledgeBases.filter((kb) => draft.knowledge_base_ids?.includes(kb.id))
    return [
      { label: 'Modo', value: draft.mode === 'crew' ? 'Equipo de agentes' : draft.mode === 'single' ? 'Agente simple' : 'Pendiente' },
      {
        label: 'Ejecucion',
        value:
          draft.execution_mode === 'scheduled'
            ? 'Programado'
            : draft.execution_mode === 'agentic'
              ? 'Agentico'
              : 'Reactivo',
      },
      { label: 'Nombre', value: draft.name || 'Pendiente' },
      { label: 'Objetivo', value: draft.goal || 'Pendiente' },
      {
        label: 'Comportamiento',
        value:
          draft.mode === 'single'
            ? draft.single_agent_mode === 'direct'
              ? 'Respuesta inmediata'
              : 'ReAct con herramientas'
            : draft.agents?.length
              ? `${draft.agents.length} roles definidos`
              : 'Pendiente',
      },
      {
        label: 'Tools',
        value: draft.tools?.length ? draft.tools.map((tool) => tool.name).join(', ') : 'Sin tools seleccionadas',
      },
      {
        label: 'Conocimiento',
        value: draft.rag?.enabled
          ? selectedKnowledgeBases.length
            ? selectedKnowledgeBases.map((kb) => kb.name).join(', ')
            : 'Necesita asociar una base'
          : 'Sin RAG',
      },
      {
        label: 'Canales',
        value: draft.channels?.length ? draft.channels.join(', ') : 'Pendiente',
      },
    ]
  }, [draft, knowledgeBases])

  const knowledgeMissing = Boolean(draft?.rag?.enabled && !(draft?.knowledge_base_ids?.length))

  const handleSend = async () => {
    const message = input.trim()
    if (!message || !session) return
    setSending(true)
    setError('')
    setInput('')
    try {
      const updated = await wizardChatApi.message(session.session_id, message)
      setSession(updated)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'No pudimos continuar la conversacion.')
      setInput(message)
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void handleSend()
    }
  }

  const handleRestart = async () => {
    setLoading(true)
    setError('')
    try {
      const fresh = await wizardChatApi.start({ initial_mode: draft?.mode as 'single' | 'crew' | undefined })
      setSession(fresh)
      setInput('')
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'No pudimos reiniciar la conversacion.')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="rounded-[32px] border border-white/60 bg-white/85 p-8 shadow-[0_28px_80px_rgba(15,23,42,0.08)]">
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
          Preparando wizard asistido por chat...
        </div>
      </div>
    )
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_360px]">
      <section className="rounded-[32px] border border-white/60 bg-white/90 p-6 shadow-[0_28px_80px_rgba(15,23,42,0.08)]">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-violet-500">Wizard asistido por chat</p>
            <h2 className="mt-2 text-3xl font-semibold text-slate-950">Conversacion guiada para definir el agente</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              Te voy haciendo preguntas, completo el borrador estructurado por debajo y cuando quede listo podes crear el agente.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="rounded-full border border-violet-200 bg-violet-50 px-4 py-2 text-sm font-medium text-violet-700">
              {session?.completion ?? 0}% completo
            </div>
            <button
              type="button"
              onClick={handleRestart}
              className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            >
              Reiniciar
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        <div className="mt-6 space-y-4 rounded-[28px] bg-slate-950/[0.03] p-4">
          {session?.messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-[24px] px-4 py-3 text-sm leading-6 shadow-sm ${
                  message.role === 'user'
                    ? 'bg-violet-600 text-white'
                    : 'border border-slate-200 bg-white text-slate-700'
                }`}
              >
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.22em] opacity-70">
                  {message.role === 'user' ? 'Vos' : 'Agentica'}
                </div>
                <p className="whitespace-pre-wrap">{message.content}</p>
              </div>
            </div>
          ))}

          {sending && (
            <div className="flex justify-start">
              <div className="rounded-[24px] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
                Agentica esta pensando la siguiente pregunta...
              </div>
            </div>
          )}
          <div ref={scrollRef} />
        </div>

        <div className="mt-6 rounded-[28px] border border-slate-200 bg-white p-4">
          <label className="text-sm font-medium text-slate-700">
            Respuesta
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Escribi tu respuesta. Enter envia y Shift+Enter agrega una nueva linea."
              className="mt-3 min-h-[120px] w-full resize-y rounded-[20px] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100"
            />
          </label>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div className="text-xs uppercase tracking-[0.24em] text-slate-400">
              Siguiente foco: {focusLabels[session?.next_focus || 'review'] || 'Revision'}
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                disabled={!session?.ready_to_create || knowledgeMissing}
                onClick={() => session && onComplete(session.draft_state)}
                className="rounded-full border border-violet-200 bg-violet-50 px-5 py-2.5 text-sm font-semibold text-violet-700 transition hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Crear agente con este borrador
              </button>
              <button
                type="button"
                onClick={() => void handleSend()}
                disabled={!input.trim() || sending || !session}
                className="rounded-full bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Enviar
              </button>
            </div>
          </div>
          {knowledgeMissing && (
            <div className="mt-3 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              Este agente necesita al menos una base de conocimiento asociada antes de crearse.
            </div>
          )}
        </div>
      </section>

      <aside className="space-y-4">
        <section className="rounded-[30px] border border-white/60 bg-white/90 p-5 shadow-[0_24px_70px_rgba(15,23,42,0.08)]">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-violet-500">Resumen vivo</p>
          <h3 className="mt-2 text-xl font-semibold text-slate-950">Borrador estructurado</h3>
          <div className="mt-5 space-y-4">
            {summaryItems.map((item) => (
              <div key={item.label} className="rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3">
                <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">{item.label}</div>
                <div className="mt-2 text-sm leading-6 text-slate-700">{item.value}</div>
              </div>
            ))}
          </div>
        </section>

        {draft?.rag?.enabled && (
          <section className="rounded-[30px] border border-violet-200 bg-violet-50/80 p-5 shadow-[0_18px_50px_rgba(124,58,237,0.12)]">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-violet-500">Bases de conocimiento</p>
            <h3 className="mt-2 text-lg font-semibold text-slate-950">Asociacion requerida</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Como el agente va a usar conocimiento interno, necesita al menos una base asociada antes de crearse.
            </p>

            <div className="mt-4 space-y-2">
              {knowledgeBases.length === 0 ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                  No hay bases disponibles. Crea una en Libreria -&gt; Conocimiento.
                </div>
              ) : (
                knowledgeBases.map((kb) => {
                  const selected = draft.knowledge_base_ids?.includes(kb.id)
                  return (
                    <button
                      key={kb.id}
                      type="button"
                      onClick={() => setSession((prev) => prev ? ({
                        ...prev,
                        draft_state: {
                          ...prev.draft_state,
                          knowledge_base_ids: selected
                            ? prev.draft_state.knowledge_base_ids.filter((id) => id !== kb.id)
                            : [...prev.draft_state.knowledge_base_ids, kb.id],
                        },
                      }) : prev)}
                      className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                        selected ? 'border-violet-400 bg-white shadow-sm' : 'border-violet-200 bg-white/70 hover:border-violet-300'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-sm font-semibold text-slate-900">{kb.name}</div>
                          <div className="mt-1 text-xs text-slate-500">
                            {kb.access_mode === 'global' ? 'Global' : 'Asignada'} · Estado: {kb.status}
                          </div>
                        </div>
                        {selected && <span className="text-sm font-semibold text-violet-600">OK</span>}
                      </div>
                    </button>
                  )
                })
              )}
            </div>
          </section>
        )}

        <section className="rounded-[30px] border border-violet-200 bg-violet-50/80 p-5 text-sm leading-6 text-violet-900 shadow-[0_18px_50px_rgba(124,58,237,0.12)]">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-violet-500">Como funciona</p>
          <ul className="mt-3 space-y-2">
            <li>El chat completa el mismo contrato estructurado que usa el wizard clasico.</li>
            <li>Podes crear el agente apenas el borrador tenga lo esencial.</li>
            <li>Si queres seguir afinando, la conversacion puede continuar aun despues de quedar listo.</li>
          </ul>
        </section>
      </aside>
    </div>
  )
}
