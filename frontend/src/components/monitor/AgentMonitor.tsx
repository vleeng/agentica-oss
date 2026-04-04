import { useState, useEffect, useRef } from 'react'
import type { AgentDesign } from '../../types/agent'
import { agentsApi, createAgentWebSocket } from '../../lib/api'
import { KnowledgePanel } from './KnowledgePanel'

interface Props {
  design: AgentDesign
  onOptimized?: (newDesign: AgentDesign) => void
}

type Phase = 'idle' | 'building' | 'ready' | 'evaluating' | 'optimizing'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
}

export function AgentMonitor({ design, onOptimized }: Props) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [evalReport, setEvalReport]   = useState<any>(null)
  const [optimizeResult, setOptimize] = useState<any>(null)
  const [error, setError]             = useState<string>('')
  const [activeTab, setActiveTab]     = useState<'sandbox' | 'eval' | 'design' | 'knowledge'>('sandbox')

  // Sandbox chat
  const [messages, setMessages]   = useState<ChatMessage[]>([])
  const [input, setInput]         = useState('')
  const [sending, setSending]     = useState(false)
  const sessionId = useRef(`sandbox_${design.agent_id}_${Date.now()}`)
  const wsRef     = useRef<ReturnType<typeof createAgentWebSocket> | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const agentId = design.agent_id

  // ── Iniciar build al montar ───────────────────────────────────────────────

  useEffect(() => {
    handleBuild()
    return () => wsRef.current?.close()
  }, [agentId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── Build ─────────────────────────────────────────────────────────────────

  const handleBuild = async () => {
    setPhase('building')
    setError('')
    try {
      await agentsApi.build(agentId)
      setPhase('ready')
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Error en el build')
      setPhase('idle')
    }
  }

  // ── Sandbox chat ──────────────────────────────────────────────────────────

  const sendMessage = () => {
    if (!input.trim() || sending || phase !== 'ready') return
    const userMsg = input.trim()
    setInput('')
    setSending(true)

    setMessages(prev => [...prev, {
      id: `u_${Date.now()}`,
      role: 'user',
      content: userMsg,
    }])

    const assistantId = `a_${Date.now()}`
    setMessages(prev => [...prev, {
      id: assistantId,
      role: 'assistant',
      content: '',
      streaming: true,
    }])

    // Crear WebSocket si no existe
    if (!wsRef.current) {
      wsRef.current = createAgentWebSocket(
        agentId,
        (token) => {
          setMessages(prev => prev.map(m =>
            m.id === assistantId ? { ...m, content: m.content + token } : m
          ))
        },
        () => {
          setMessages(prev => prev.map(m =>
            m.id === assistantId ? { ...m, streaming: false } : m
          ))
          setSending(false)
        },
        (err) => {
          setMessages(prev => prev.map(m =>
            m.id === assistantId ? { ...m, content: `Error: ${err}`, streaming: false } : m
          ))
          setSending(false)
        },
      )
    }

    wsRef.current.send(userMsg, sessionId.current)
  }

  // ── Evaluación ────────────────────────────────────────────────────────────

  const handleEval = async () => {
    setPhase('evaluating')
    setError('')
    try {
      const report = await agentsApi.eval(agentId)
      setEvalReport(report)
      setActiveTab('eval')
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Error en la evaluación')
    } finally {
      setPhase('ready')
    }
  }

  // ── Optimización ──────────────────────────────────────────────────────────

  const handleOptimize = async () => {
    if (!evalReport) return
    setPhase('optimizing')
    try {
      const result = await agentsApi.optimize(agentId, evalReport, true)
      setOptimize(result)
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Error en la optimización')
    } finally {
      setPhase('ready')
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">{design.spec.name}</h1>
          <div className="flex items-center gap-3 mt-1">
            <PhaseBadge phase={phase} />
            <span className="text-xs text-gray-400">
              {design.framework.framework} · {design.spec.mode} · v{design.version}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleEval}
            disabled={phase !== 'ready'}
            className="px-4 py-2 text-sm border border-violet-300 text-violet-700 rounded-lg hover:bg-violet-50 disabled:opacity-40 transition-colors"
          >
            {phase === 'evaluating' ? '⟳ Evaluando...' : 'Evaluar'}
          </button>
          {evalReport && !evalReport.pass_threshold && (
            <button
              onClick={handleOptimize}
              disabled={phase !== 'ready'}
              className="px-4 py-2 text-sm bg-amber-500 text-white rounded-lg hover:bg-amber-600 disabled:opacity-40 transition-colors"
            >
              {phase === 'optimizing' ? '⟳ Optimizando...' : 'Optimizar'}
            </button>
          )}
          {evalReport?.pass_threshold && (
            <button className="px-4 py-2 text-sm bg-violet-600 text-white rounded-lg hover:bg-violet-700 transition-colors">
              Desplegar →
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200">
        {(['sandbox', 'eval', 'design', 'knowledge'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm transition-colors -mb-px ${
              activeTab === tab
                ? 'border-b-2 border-violet-500 text-violet-700 font-medium'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab === 'sandbox' ? 'Sandbox' : tab === 'eval' ? 'Evaluación' : tab === 'knowledge' ? 'Conocimiento' : 'Diseño'}
          </button>
        ))}
      </div>

      {/* ── Tab: Sandbox chat ─────────────────────────────────────────────── */}
      {activeTab === 'sandbox' && (
        <div className="border border-gray-200 rounded-xl overflow-hidden">
          {/* Messages */}
          <div className="h-96 overflow-y-auto p-4 space-y-3 bg-gray-50">
            {messages.length === 0 && (
              <p className="text-center text-sm text-gray-400 mt-16">
                Probá el agente escribiendo un mensaje abajo
              </p>
            )}
            {messages.map(msg => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-lg px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-violet-600 text-white'
                    : 'bg-white border border-gray-200 text-gray-900'
                }`}>
                  {msg.content || (msg.streaming ? <span className="animate-pulse">●</span> : '')}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
          {/* Input */}
          <div className="flex gap-2 p-3 bg-white border-t border-gray-200">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
              placeholder={phase === 'building' ? 'Construyendo agente...' : 'Escribí un mensaje...'}
              disabled={phase !== 'ready' || sending}
              className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 disabled:bg-gray-50"
            />
            <button
              onClick={sendMessage}
              disabled={phase !== 'ready' || sending || !input.trim()}
              className="px-4 py-2 bg-violet-600 text-white text-sm rounded-lg hover:bg-violet-700 disabled:opacity-40 transition-colors"
            >
              Enviar
            </button>
          </div>
        </div>
      )}

      {/* ── Tab: Evaluación ────────────────────────────────────────────────── */}
      {activeTab === 'eval' && (
        <div>
          {!evalReport ? (
            <div className="text-center py-16 text-gray-400 text-sm">
              <p>Aún no se corrió la evaluación.</p>
              <button onClick={handleEval} disabled={phase !== 'ready'}
                className="mt-4 px-4 py-2 bg-violet-600 text-white rounded-lg text-sm disabled:opacity-40">
                Correr evaluación
              </button>
            </div>
          ) : (
            <EvalDashboard report={evalReport} onOptimize={handleOptimize}
              optimizeResult={optimizeResult} phase={phase} />
          )}
        </div>
      )}

      {/* ── Tab: Diseño ─────────────────────────────────────────────────────── */}
      {activeTab === 'design' && (
        <div className="space-y-4">
          <Section title="System prompt">
            <pre className="text-xs text-gray-700 whitespace-pre-wrap bg-gray-50 p-4 rounded-lg border border-gray-200 max-h-48 overflow-y-auto">
              {design.system_prompt}
            </pre>
          </Section>
          <Section title="Justificación del framework">
            <p className="text-sm text-gray-600">{design.framework.justification}</p>
          </Section>
          <Section title="Diagrama de flujo">
            <pre className="text-xs text-gray-500 font-mono bg-gray-50 p-3 rounded-lg">
              {design.mermaid_diagram}
            </pre>
          </Section>
          <Section title={`Test cases (${design.test_cases.length})`}>
            <div className="space-y-2">
              {design.test_cases.map((tc: any) => (
                <div key={tc.id} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                  <div className="text-xs font-medium text-gray-700">{tc.description}</div>
                  <div className="text-xs text-gray-500 mt-1">Input: {tc.input}</div>
                  <div className="text-xs text-gray-400 mt-0.5">Criterio: {tc.pass_criteria}</div>
                </div>
              ))}
            </div>
          </Section>
        </div>
      )}

      {/* ── Tab: Conocimiento ───────────────────────────────────────────────── */}
      {activeTab === 'knowledge' && (
        <KnowledgePanel agentId={agentId} />
      )}
    </div>
  )
}


// ── Sub-componentes ────────────────────────────────────────────────────────────

function PhaseBadge({ phase }: { phase: Phase }) {
  const cfg: Record<Phase, { label: string; cls: string }> = {
    idle:       { label: 'Sin build',    cls: 'bg-gray-100 text-gray-600' },
    building:   { label: 'Construyendo', cls: 'bg-blue-100 text-blue-700' },
    ready:      { label: 'Listo',        cls: 'bg-green-100 text-green-700' },
    evaluating: { label: 'Evaluando',    cls: 'bg-amber-100 text-amber-700' },
    optimizing: { label: 'Optimizando',  cls: 'bg-purple-100 text-purple-700' },
  }
  const { label, cls } = cfg[phase]
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${cls}`}>{label}</span>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-sm font-medium text-gray-700 mb-2">{title}</h3>
      {children}
    </div>
  )
}

function EvalDashboard({ report, onOptimize, optimizeResult, phase }: {
  report: any; onOptimize: () => void; optimizeResult: any; phase: Phase
}) {
  const metrics = [
    { label: 'Completitud',   value: report.task_completion_rate, fmt: 'pct' },
    { label: 'Precisión tools', value: report.tool_accuracy,       fmt: 'pct' },
    { label: 'Latencia p95',  value: report.p95_latency_ms,        fmt: 'ms' },
    { label: 'Costo estimado', value: report.estimated_cost_usd,   fmt: 'usd' },
    { label: 'Hallucination', value: report.hallucination_score,   fmt: 'pct_inv' },
  ]

  const fmt = (value: number, type: string) => {
    if (type === 'pct')     return `${(value * 100).toFixed(0)}%`
    if (type === 'pct_inv') return `${(value * 100).toFixed(0)}%`
    if (type === 'ms')      return `${value.toFixed(0)}ms`
    if (type === 'usd')     return `$${value.toFixed(4)}`
    return String(value)
  }

  const scoreColor = report.overall_score >= 0.75
    ? 'text-green-600' : report.overall_score >= 0.5
    ? 'text-amber-600' : 'text-red-600'

  return (
    <div className="space-y-5">
      {/* Score general */}
      <div className={`text-center py-5 rounded-xl border ${
        report.pass_threshold ? 'border-green-200 bg-green-50' : 'border-amber-200 bg-amber-50'
      }`}>
        <div className={`text-4xl font-bold ${scoreColor}`}>
          {(report.overall_score * 100).toFixed(0)}
        </div>
        <div className="text-sm text-gray-500 mt-1">Score general / 100</div>
        <div className={`text-sm font-medium mt-2 ${report.pass_threshold ? 'text-green-700' : 'text-amber-700'}`}>
          {report.pass_threshold ? '✓ Listo para producción' : '⚠ Requiere optimización'}
        </div>
      </div>

      {/* Métricas */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {metrics.map(m => (
          <div key={m.label} className="p-4 rounded-xl border border-gray-200 bg-white">
            <div className="text-xs text-gray-500">{m.label}</div>
            <div className="text-lg font-semibold text-gray-900 mt-1">{fmt(m.value, m.fmt)}</div>
          </div>
        ))}
      </div>

      {/* Notas */}
      {report.notes && (
        <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
          <div className="text-xs font-medium text-gray-500 mb-1">Observaciones</div>
          <p className="text-sm text-gray-700">{report.notes}</p>
        </div>
      )}

      {/* Optimize result */}
      {optimizeResult && (
        <div className="p-4 bg-violet-50 rounded-lg border border-violet-200">
          <div className="text-xs font-medium text-violet-700 mb-2">Optimización aplicada (v{optimizeResult.new_version})</div>
          <div className="text-xs text-gray-600 space-y-0.5">
            {optimizeResult.patch.system_prompt_changed && <div>• System prompt regenerado</div>}
            {optimizeResult.patch.temperature != null && <div>• Temperatura → {optimizeResult.patch.temperature}</div>}
            {optimizeResult.patch.max_tokens != null && <div>• Max tokens → {optimizeResult.patch.max_tokens}</div>}
            {optimizeResult.patch.tools_added?.length > 0 && <div>• Tools agregadas: {optimizeResult.patch.tools_added.join(', ')}</div>}
          </div>
          <p className="text-xs text-gray-500 mt-2">{optimizeResult.patch.reasoning}</p>
        </div>
      )}
    </div>
  )
}
