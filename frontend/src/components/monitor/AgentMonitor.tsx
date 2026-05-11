import { ExternalLink, Gauge, Play, RefreshCcw, Rocket, Sparkles, Wand2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import type { AgentDesign } from '../../types/agent'
import { agentsApi, createAgentWebSocket } from '../../lib/api'
import { KnowledgePanel } from './KnowledgePanel'
import { AgentConfigPanel } from './AgentConfigPanel'
import { AgentEditPanel } from './AgentEditPanel'
import { FlowEditor } from './FlowEditor'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { MermaidDiagram } from '../visual/MermaidDiagram'
import { RichText } from '../visual/RichText'

interface Props {
  design: AgentDesign
  onOptimized?: (newDesign: AgentDesign) => void
}

type Phase = 'idle' | 'building' | 'ready' | 'evaluating' | 'optimizing' | 'deploying'
type TabId = 'sandbox' | 'eval' | 'design' | 'knowledge' | 'config' | 'edit'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
}

function stripMermaidFromPrompt(prompt: string) {
  if (!prompt) return ''

  const mermaidStart = /^\s*(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram|erDiagram|journey|gantt|pie|mindmap|timeline)\b/im
  const match = prompt.match(mermaidStart)
  if (!match || match.index == null) return prompt.trim()

  const before = prompt.slice(0, match.index).trim()
  const after = prompt.slice(match.index).trim()
  const nextSectionIndex = after.search(/\n\s*\n/)
  const trailing = nextSectionIndex >= 0 ? after.slice(nextSectionIndex).trim() : ''

  return [before, trailing].filter(Boolean).join('\n\n').trim()
}

export function AgentMonitor({ design, onOptimized }: Props) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [evalReport, setEvalReport] = useState<any>(null)
  const [optimizeResult, setOptimizeResult] = useState<any>(null)
  const [isDeployed, setIsDeployed] = useState(design.status === 'deployed')
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<TabId>('sandbox')
  const [currentDesign, setCurrentDesign] = useState<AgentDesign>(design)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [showFlowEditor, setShowFlowEditor] = useState(false)
  const sessionId = useRef(`sandbox_${design.agent_id}_${Date.now()}`)
  const wsRef = useRef<ReturnType<typeof createAgentWebSocket> | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  // Refs so the stable WS callbacks always target the current message
  const onTokenRef = useRef<(token: string) => void>(() => {})
  const onDoneRef  = useRef<(sid: string) => void>(() => {})
  const onErrorRef = useRef<(msg: string) => void>(() => {})

  useEffect(() => {
    handleBuild()
    return () => wsRef.current?.close()
  }, [design.agent_id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleBuild = async () => {
    setPhase('building')
    setError('')
    try {
      await agentsApi.build(design.agent_id)
      setPhase('ready')
    } catch (e: any) {
      setError(e.response?.data?.detail || 'No se pudo construir el runtime del agente.')
      setPhase('idle')
    }
  }

  const sendMessage = () => {
    if (!input.trim() || sending || phase !== 'ready') return

    const userText = input.trim()
    const assistantId = `assistant_${Date.now()}`

    setInput('')
    setSending(true)
    setMessages((prev) => [
      ...prev,
      { id: `user_${Date.now()}`, role: 'user', content: userText },
      { id: assistantId, role: 'assistant', content: '', streaming: true },
    ])

    // Update refs so the stable WS callbacks always point to the current message
    onTokenRef.current = (token) => {
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + token } : m))
      )
    }
    onDoneRef.current = () => {
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m))
      )
      setSending(false)
    }
    onErrorRef.current = (msg) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, content: `Error: ${msg}`, streaming: false } : m
        )
      )
      setSending(false)
    }

    if (!wsRef.current) {
      wsRef.current = createAgentWebSocket(
        design.agent_id,
        (token) => onTokenRef.current(token),
        (sid)   => onDoneRef.current(sid),
        (msg)   => onErrorRef.current(msg)
      )
    }

    wsRef.current.send(userText, sessionId.current)
  }

  const handleEval = async () => {
    setPhase('evaluating')
    setError('')
    try {
      const report = await agentsApi.eval(design.agent_id)
      setEvalReport(report)
      setActiveTab('eval')
    } catch (e: any) {
      setError(e.response?.data?.detail || 'No se pudo ejecutar la evaluación.')
    } finally {
      setPhase('ready')
    }
  }

  const handleOptimize = async () => {
    if (!evalReport) return
    setPhase('optimizing')
    setError('')
    try {
      const result = await agentsApi.optimize(design.agent_id, evalReport, true)
      setOptimizeResult(result)
      if (onOptimized) {
        const refreshed = await agentsApi.getDesign(design.agent_id)
        onOptimized(refreshed)
      }
    } catch (e: any) {
      setError(e.response?.data?.detail || 'No se pudo optimizar el agente.')
    } finally {
      setPhase('ready')
    }
  }

  const handleDeploy = async () => {
    setPhase('deploying')
    setError('')
    try {
      await agentsApi.deploy(design.agent_id)
      setIsDeployed(true)
    } catch (e: any) {
      setError(e.response?.data?.detail || 'No se pudo desplegar el agente.')
    } finally {
      setPhase('ready')
    }
  }

  const tabs: Array<{ id: TabId; label: string }> = [
    { id: 'sandbox', label: 'Sandbox' },
    { id: 'eval', label: 'Evaluación' },
    { id: 'design', label: 'Diseño' },
    { id: 'knowledge', label: 'Conocimiento' },
    { id: 'config', label: 'Configurar' },
    { id: 'edit', label: 'Editar' },
  ]

  const handleAgentUpdated = (newDesign: AgentDesign) => {
    setCurrentDesign(newDesign)
    if (onOptimized) onOptimized(newDesign)
    // Rebuild was triggered server-side; put the monitor back in ready state
    setPhase('ready')
    setActiveTab('sandbox')
  }

  const handleFlowSaved = (newDesign: AgentDesign) => {
    setCurrentDesign(newDesign)
    if (onOptimized) onOptimized(newDesign)
  }

  const displaySystemPrompt = stripMermaidFromPrompt(currentDesign.system_prompt)

  return (
    <div className="space-y-6">
      <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <Card className="overflow-hidden border-slate-200 bg-[linear-gradient(135deg,#ffffff_0%,#f8fafc_50%,#ede9fe_100%)]">
          <CardContent className="flex h-full flex-col justify-between gap-6 p-8">
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={isDeployed ? 'green' : phase === 'ready' ? 'green' : phase === 'building' ? 'blue' : phase === 'evaluating' ? 'amber' : 'violet'}>
                  {isDeployed
                    ? 'Desplegado'
                    : phase === 'ready'
                    ? 'Runtime listo'
                    : phase === 'building'
                    ? 'Construyendo'
                    : phase === 'evaluating'
                    ? 'Evaluando'
                    : phase === 'optimizing'
                    ? 'Optimizando'
                    : phase === 'deploying'
                    ? 'Desplegando'
                    : 'Pendiente'}
                </Badge>
                <Badge tone="slate">{design.framework.framework}</Badge>
                <Badge tone="violet">v{design.version}</Badge>
              </div>

              <div>
                <h1 className="text-3xl font-semibold tracking-tight text-slate-950">{currentDesign.spec.name}</h1>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">{currentDesign.spec.goal}</p>
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button onClick={handleBuild} variant="secondary">
                <RefreshCcw className="h-4 w-4" />
                Rebuild
              </Button>
              <Button onClick={handleEval} disabled={phase !== 'ready'}>
                <Gauge className="h-4 w-4" />
                Evaluar
              </Button>
              <Button onClick={handleOptimize} variant="secondary" disabled={phase !== 'ready' || !evalReport || evalReport.pass_threshold}>
                <Wand2 className="h-4 w-4" />
                Optimizar
              </Button>
              <Button
                onClick={handleDeploy}
                variant={isDeployed ? 'secondary' : 'primary'}
                disabled={phase !== 'ready' || isDeployed}
              >
                <Rocket className="h-4 w-4" />
                {isDeployed ? 'Desplegado ✓' : phase === 'deploying' ? 'Desplegando…' : 'Deploy'}
              </Button>

              {isDeployed && (
                <a
                  href={`${import.meta.env.BASE_URL}c/${design.agent_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-700 transition hover:bg-emerald-100"
                >
                  <ExternalLink className="h-4 w-4" />
                  Abrir chat
                </a>
              )}
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
          <MonitorMetric title="Modelo base" value={currentDesign.spec.model_params.model} />
          <MonitorMetric title="Modo" value={currentDesign.spec.mode === 'crew' ? 'Equipo de agentes' : 'Agente simple'} />
          <MonitorMetric title="Tools" value={String(currentDesign.spec.tools.length)} />
        </div>
      </section>

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
      )}

      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-3">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
              activeTab === tab.id
                ? 'bg-violet-600 text-white'
                : 'text-slate-500 hover:bg-slate-100 hover:text-slate-900'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'sandbox' && (
        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle>Sandbox conversacional</CardTitle>
            <CardDescription>Probá el agente en vivo antes de desplegarlo.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="h-[28rem] space-y-4 overflow-y-auto rounded-2xl border border-slate-200 bg-slate-50 p-4">
              {messages.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-100 text-violet-700">
                    <Sparkles className="h-6 w-6" />
                  </div>
                  <h3 className="mt-4 text-lg font-semibold text-slate-900">Todavía no arrancó la conversación</h3>
                  <p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">
                    Mandale una instrucción, hacé pruebas de contexto y validá el comportamiento antes de pasarlo a producción.
                  </p>
                </div>
              ) : (
                messages.map((message) => (
                  <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-2xl rounded-2xl px-4 py-3 shadow-sm ${
                        message.role === 'user'
                          ? 'bg-violet-600 text-white'
                          : 'border border-slate-200 bg-white text-slate-800'
                      }`}
                    >
                      {message.role === 'user' ? (
                        <p className="whitespace-pre-wrap text-sm leading-7">{message.content}</p>
                      ) : (
                        <>
                          {message.content ? <RichText content={message.content} /> : message.streaming && <span className="animate-pulse">●</span>}
                        </>
                      )}
                    </div>
                  </div>
                ))
              )}
              <div ref={bottomRef} />
            </div>

            <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-3 md:flex-row">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    sendMessage()
                  }
                }}
                placeholder={phase === 'building' ? 'Construyendo runtime...' : 'Escribí una prueba, instrucción o caso de uso'}
                disabled={phase !== 'ready' || sending}
                className="min-h-[92px] flex-1 resize-none rounded-xl border border-slate-200 px-3 py-3 text-sm outline-none transition focus:border-violet-400 focus:ring-2 focus:ring-violet-500/20 disabled:bg-slate-50"
              />
              <div className="flex md:w-44 md:flex-col">
                <Button className="w-full" onClick={sendMessage} disabled={phase !== 'ready' || sending || !input.trim()}>
                  <Play className="h-4 w-4" />
                  Enviar
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === 'eval' && (
        <EvalDashboard report={evalReport} optimizeResult={optimizeResult} phase={phase} onOptimize={handleOptimize} />
      )}

      {activeTab === 'design' && (
        <div className="space-y-6">
          <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <Card>
            <CardHeader>
              <CardTitle>System prompt</CardTitle>
              <CardDescription>Base operativa generada para el runtime.</CardDescription>
            </CardHeader>
            <CardContent>
              {displaySystemPrompt ? (
                <pre className="max-h-[26rem] overflow-y-auto whitespace-pre-wrap rounded-xl bg-slate-50 p-4 text-xs leading-6 text-slate-700">
                  {displaySystemPrompt}
                </pre>
              ) : (
                <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-500">
                  El detalle visual del flujo se muestra en el diagrama. Este prompt no agrega texto operativo adicional en la vista de diseño.
                </div>
              )}
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Decisión de framework</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-7 text-slate-600">{currentDesign.framework.justification}</p>
              </CardContent>
            </Card>

              {currentDesign.mermaid_diagram && (
              <MermaidDiagram
                chart={currentDesign.mermaid_diagram}
                actions={
                  <Button variant="secondary" onClick={() => setShowFlowEditor((prev) => !prev)}>
                    {showFlowEditor ? 'Ocultar editor' : 'Editar flujo'}
                  </Button>
                }
              />
              )}

            <Card>
              <CardHeader>
                <CardTitle>Casos de prueba</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {currentDesign.test_cases.map((testCase: any) => (
                  <div key={testCase.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <div className="font-medium text-slate-950">{testCase.description}</div>
                    <div className="mt-2 text-sm text-slate-600">Input: {testCase.input}</div>
                    <div className="mt-1 text-sm text-slate-500">Criterio: {testCase.pass_criteria}</div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
          </div>

          {showFlowEditor && (
            <FlowEditor design={currentDesign} onSaved={handleFlowSaved} />
          )}
        </div>
      )}

      {activeTab === 'knowledge' && <KnowledgePanel agentId={currentDesign.agent_id} />}

      {activeTab === 'config' && <AgentConfigPanel agentId={currentDesign.agent_id} />}

      {activeTab === 'edit' && (
        <AgentEditPanel design={currentDesign} onUpdated={handleAgentUpdated} />
      )}
    </div>
  )
}

function MonitorMetric({ title, value }: { title: string; value: string }) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="text-sm text-slate-500">{title}</div>
        <div className="mt-2 break-all text-lg font-semibold text-slate-950">{value}</div>
      </CardContent>
    </Card>
  )
}

function EvalDashboard({
  report,
  onOptimize,
  optimizeResult,
  phase,
}: {
  report: any
  onOptimize: () => void
  optimizeResult: any
  phase: Phase
}) {
  if (!report) {
    return (
      <Card>
        <CardContent className="flex min-h-[18rem] flex-col items-center justify-center text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-100 text-violet-700">
            <Gauge className="h-6 w-6" />
          </div>
          <h3 className="mt-4 text-lg font-semibold text-slate-950">Todavía no corriste la evaluación</h3>
          <p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">
            Ejecutá el benchmark del agente para medir completitud, latencia, costo y calidad de herramientas.
          </p>
        </CardContent>
      </Card>
    )
  }

  const metrics = [
    { label: 'Completitud', value: `${(report.task_completion_rate * 100).toFixed(0)}%` },
    { label: 'Tools', value: `${(report.tool_accuracy * 100).toFixed(0)}%` },
    { label: 'Latencia p95', value: `${report.p95_latency_ms.toFixed(0)}ms` },
    { label: 'Costo estimado', value: `$${report.estimated_cost_usd.toFixed(4)}` },
    { label: 'Hallucination', value: `${(report.hallucination_score * 100).toFixed(0)}%` },
  ]

  return (
    <div className="space-y-6">
      <section className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <CardContent className="flex h-full flex-col items-center justify-center p-8 text-center">
            <div className={`text-6xl font-semibold ${report.pass_threshold ? 'text-emerald-600' : 'text-amber-600'}`}>
              {(report.overall_score * 100).toFixed(0)}
            </div>
            <div className="mt-2 text-sm text-slate-500">Score general sobre 100</div>
            <Badge className="mt-4" tone={report.pass_threshold ? 'green' : 'amber'}>
              {report.pass_threshold ? 'Listo para producción' : 'Requiere optimización'}
            </Badge>
          </CardContent>
        </Card>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {metrics.map((metric) => (
            <Card key={metric.label}>
              <CardContent className="p-5">
                <div className="text-sm text-slate-500">{metric.label}</div>
                <div className="mt-2 text-xl font-semibold text-slate-950">{metric.value}</div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {report.notes && (
        <Card>
          <CardHeader>
            <CardTitle>Observaciones</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-7 text-slate-600">{report.notes}</p>
          </CardContent>
        </Card>
      )}

      {optimizeResult && (
        <Card className="border-violet-200 bg-violet-50">
          <CardHeader>
            <CardTitle>Optimización aplicada</CardTitle>
            <CardDescription>Versión nueva: {optimizeResult.new_version}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-700">
            {optimizeResult.patch.system_prompt_changed && <div>• Se regeneró el system prompt.</div>}
            {optimizeResult.patch.temperature != null && <div>• Temperatura → {optimizeResult.patch.temperature}</div>}
            {optimizeResult.patch.max_tokens != null && <div>• Max tokens → {optimizeResult.patch.max_tokens}</div>}
            {optimizeResult.patch.tools_added?.length > 0 && <div>• Tools agregadas: {optimizeResult.patch.tools_added.join(', ')}</div>}
            <div className="pt-2 text-slate-500">{optimizeResult.patch.reasoning}</div>
          </CardContent>
        </Card>
      )}

      {!report.pass_threshold && (
        <div className="flex justify-end">
          <Button onClick={onOptimize} disabled={phase !== 'ready'}>
            <Wand2 className="h-4 w-4" />
            Optimizar ahora
          </Button>
        </div>
      )}
    </div>
  )
}
