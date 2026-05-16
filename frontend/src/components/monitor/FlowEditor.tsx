import { AlertTriangle, CheckCircle2, GitBranch, Grip, Plus, Save, Shuffle, Trash2, Workflow } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { agentsApi } from '../../lib/api'
import type {
  AgentDesign,
  FlowEdge,
  FlowNode,
  FlowNodeType,
  GraphBlueprint,
  GraphValidationIssue,
  GraphValidationReport,
} from '../../types/agent'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Field } from '../ui/field'
import { Input } from '../ui/input'
import { useToast } from '../ui/toast'

interface Props {
  design: AgentDesign
  onSaved: (nextDesign: AgentDesign) => void
}

const NODE_TYPES: Array<{ value: FlowNodeType; label: string }> = [
  { value: 'start', label: 'Start' },
  { value: 'agent', label: 'Agent' },
  { value: 'decision', label: 'Decision' },
  { value: 'tool', label: 'Tool' },
  { value: 'end', label: 'End' },
]

const NODE_WIDTH = 200
const NODE_HEIGHT = 104
const HANDLE_SIZE = 12
const CANVAS_PADDING = 64

function cloneGraph(graph: GraphBlueprint): GraphBlueprint {
  const cloned = JSON.parse(JSON.stringify(graph ?? {}))
  return {
    nodes: Array.isArray(cloned.nodes) ? cloned.nodes : [],
    edges: Array.isArray(cloned.edges) ? cloned.edges : [],
    meta: cloned.meta ?? { version: 1, layout: 'manual' },
  }
}

function normalizeValidationReport(value: unknown): GraphValidationReport | null {
  if (!value || typeof value !== 'object') return null
  const candidate = value as Partial<GraphValidationReport>
  const errors = Array.isArray(candidate.errors) ? candidate.errors : null
  const warnings = Array.isArray(candidate.warnings) ? candidate.warnings : null
  if (!errors || !warnings) return null
  return {
    ok: Boolean(candidate.ok),
    errors,
    warnings,
  }
}

function asErrorMessage(value: unknown, fallback: string): string {
  if (typeof value === 'string' && value.trim()) return value
  if (value && typeof value === 'object') {
    const candidate = value as {
      message?: unknown
      detail?: unknown
      errors?: Array<{ message?: unknown }>
      warnings?: Array<{ message?: unknown }>
    }
    if (typeof candidate.message === 'string' && candidate.message.trim()) return candidate.message
    if (typeof candidate.detail === 'string' && candidate.detail.trim()) return candidate.detail
    const firstIssue = [...(candidate.errors ?? []), ...(candidate.warnings ?? [])].find(
      (issue) => typeof issue?.message === 'string' && issue.message.trim(),
    )
    if (typeof firstIssue?.message === 'string') return firstIssue.message
    try {
      return JSON.stringify(value)
    } catch {
      return fallback
    }
  }
  return fallback
}

function buildToolOptions(design: AgentDesign) {
  const baseTools = [...(design.spec.tools ?? [])]
  if (design.spec.mode === 'single' && design.spec.rag.enabled && !baseTools.some((tool) => tool.name === 'knowledge_base')) {
    baseTools.push({
      name: 'knowledge_base',
      source: 'library',
      config: { description: 'Consultar la base de conocimientos del agente' },
    })
  }
  return baseTools
}

function defaultNode(type: FlowNodeType, index: number, design: AgentDesign): FlowNode {
  const roleOptions = design.spec.agents ?? []
  const toolOptions = buildToolOptions(design)
  return {
    id: `${type}_${index}`,
    type,
    label:
      type === 'agent'
        ? `Paso ${index}`
        : type === 'decision'
          ? `Revision ${index}`
          : type === 'tool'
            ? `Tool ${index}`
            : type === 'start'
              ? 'Inicio'
              : 'Fin',
    description: '',
    position: { x: 96 + ((index - 1) % 3) * 236, y: 96 + Math.floor((index - 1) / 3) * 148 },
    data: {
      assigned_agent:
        type === 'agent' && design.spec.mode === 'crew' && roleOptions.length
          ? roleOptions[0].name
          : undefined,
      tool_name: type === 'tool' && toolOptions.length ? toolOptions[0].name : undefined,
      allowed_tools: [],
    },
  }
}

function issuesForId(issues: GraphValidationIssue[], kind: 'node' | 'edge', id: string) {
  return issues.filter((issue) => (kind === 'node' ? issue.node_id === id : issue.edge_id === id))
}

function getNodeTone(type: FlowNodeType) {
  switch (type) {
    case 'start':
      return 'border-emerald-200 bg-emerald-50 text-emerald-700'
    case 'agent':
      return 'border-violet-200 bg-violet-50 text-violet-700'
    case 'decision':
      return 'border-amber-200 bg-amber-50 text-amber-700'
    case 'tool':
      return 'border-sky-200 bg-sky-50 text-sky-700'
    case 'end':
      return 'border-slate-300 bg-slate-100 text-slate-700'
  }
}

function getNodePoint(node: FlowNode, side: 'left' | 'right') {
  const position = node.position ?? { x: 0, y: 0 }
  return {
    x: position.x + (side === 'left' ? 0 : NODE_WIDTH),
    y: position.y + NODE_HEIGHT / 2,
  }
}

function buildEdgePath(source: FlowNode, target: FlowNode) {
  const start = getNodePoint(source, 'right')
  const end = getNodePoint(target, 'left')
  const delta = Math.max(72, Math.abs(end.x - start.x) * 0.5)
  return `M ${start.x} ${start.y} C ${start.x + delta} ${start.y}, ${end.x - delta} ${end.y}, ${end.x} ${end.y}`
}

function autoLayoutGraph(graph: GraphBlueprint): GraphBlueprint {
  if (!graph.nodes.length) return graph

  const nodesById = new Map(graph.nodes.map((node) => [node.id, node]))
  const outgoing = new Map<string, string[]>()
  const indegree = new Map<string, number>()

  for (const node of graph.nodes) {
    outgoing.set(node.id, [])
    indegree.set(node.id, 0)
  }
  for (const edge of graph.edges) {
    outgoing.get(edge.from)?.push(edge.to)
    indegree.set(edge.to, (indegree.get(edge.to) ?? 0) + 1)
  }

  const starts = graph.nodes.filter((node) => node.type === 'start')
  const queue = starts.length ? starts.map((node) => node.id) : [graph.nodes[0].id]
  const visited = new Set<string>()
  const levels = new Map<string, number>()
  queue.forEach((id) => levels.set(id, 0))

  while (queue.length) {
    const current = queue.shift()!
    if (visited.has(current)) continue
    visited.add(current)
    const currentLevel = levels.get(current) ?? 0
    for (const next of outgoing.get(current) ?? []) {
      const nextLevel = Math.max(levels.get(next) ?? 0, currentLevel + 1)
      levels.set(next, nextLevel)
      queue.push(next)
    }
  }

  const unplaced = graph.nodes.filter((node) => !levels.has(node.id))
  for (const node of unplaced) {
    const parentLevel = Math.max(0, ...Array.from(indegree.entries()).filter(([id]) => id === node.id).map(() => 0))
    levels.set(node.id, parentLevel)
  }

  const lanes = new Map<number, FlowNode[]>()
  for (const node of graph.nodes) {
    const level = levels.get(node.id) ?? 0
    const lane = lanes.get(level) ?? []
    lane.push(node)
    lanes.set(level, lane)
  }

  const nextNodes = graph.nodes.map((node) => {
    const level = levels.get(node.id) ?? 0
    const column = lanes.get(level) ?? []
    const row = column.findIndex((item) => item.id === node.id)
    return nodesById.get(node.id)!.id === node.id
      ? {
          ...node,
          position: {
            x: CANVAS_PADDING + level * 248,
            y: CANVAS_PADDING + row * 148,
          },
        }
      : node
  })

  return {
    ...graph,
    nodes: nextNodes,
    meta: { ...(graph.meta ?? { version: 1, layout: 'manual' }), layout: 'auto' },
  }
}

function sortIssues(issues: GraphValidationIssue[]) {
  return [...issues].sort((left, right) => {
    if (left.level !== right.level) return left.level === 'error' ? -1 : 1
    return left.code.localeCompare(right.code)
  })
}

export function FlowEditor({ design, onSaved }: Props) {
  const { push } = useToast()
  const [draft, setDraft] = useState<GraphBlueprint>(cloneGraph(design.graph_blueprint))
  const [validation, setValidation] = useState<GraphValidationReport | null>(null)
  const [saving, setSaving] = useState(false)
  const [validating, setValidating] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null)
  const [pendingConnectionFrom, setPendingConnectionFrom] = useState<string | null>(null)
  const canvasRef = useRef<HTMLDivElement | null>(null)
  const viewportResetRef = useRef(false)
  const dragRef = useRef<{
    nodeId: string
    offsetX: number
    offsetY: number
  } | null>(null)

  useEffect(() => {
    const nextDraft = cloneGraph(design.graph_blueprint)
    setDraft(nextDraft)
    setValidation(null)
    setErrorMsg('')
    setSelectedNodeId(nextDraft.nodes[0]?.id ?? null)
    setSelectedEdgeId(null)
    setPendingConnectionFrom(null)
  }, [design])

  useEffect(() => {
    if (!viewportResetRef.current || !canvasRef.current) return
    viewportResetRef.current = false
    window.requestAnimationFrame(() => {
      canvasRef.current?.scrollTo({ left: 0, top: 0, behavior: 'smooth' })
    })
  }, [draft.nodes])

  useEffect(() => {
    const handleMove = (event: MouseEvent) => {
      if (!dragRef.current || !canvasRef.current) return
      const rect = canvasRef.current.getBoundingClientRect()
      const scrollLeft = canvasRef.current.scrollLeft
      const scrollTop = canvasRef.current.scrollTop
      const nextX = Math.max(
        CANVAS_PADDING / 2,
        Math.round(event.clientX - rect.left + scrollLeft - dragRef.current.offsetX),
      )
      const nextY = Math.max(
        CANVAS_PADDING / 2,
        Math.round(event.clientY - rect.top + scrollTop - dragRef.current.offsetY),
      )
      setDraft((prev) => ({
        ...prev,
        meta: { ...(prev.meta ?? { version: 1, layout: 'manual' }), layout: 'manual' },
        nodes: prev.nodes.map((node) =>
          node.id === dragRef.current?.nodeId
            ? { ...node, position: { x: nextX, y: nextY } }
            : node,
        ),
      }))
    }

    const handleUp = () => {
      dragRef.current = null
    }

    window.addEventListener('mousemove', handleMove)
    window.addEventListener('mouseup', handleUp)
    return () => {
      window.removeEventListener('mousemove', handleMove)
      window.removeEventListener('mouseup', handleUp)
    }
  }, [])

  const isDirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(design.graph_blueprint),
    [draft, design.graph_blueprint],
  )

  const roleOptions = design.spec.agents ?? []
  const toolOptions = buildToolOptions(design)
  const nodesById = useMemo(() => new Map(draft.nodes.map((node) => [node.id, node])), [draft.nodes])

  const allIssues = useMemo(
    () => (validation ? sortIssues([...validation.errors, ...validation.warnings]) : []),
    [validation],
  )

  const canvasBounds = useMemo(() => {
    if (!draft.nodes.length) {
      return { width: 960, height: 540 }
    }
    const maxX = Math.max(...draft.nodes.map((node) => (node.position?.x ?? 0) + NODE_WIDTH))
    const maxY = Math.max(...draft.nodes.map((node) => (node.position?.y ?? 0) + NODE_HEIGHT))
    return {
      width: Math.max(960, maxX + CANVAS_PADDING),
      height: Math.max(540, maxY + CANVAS_PADDING),
    }
  }, [draft.nodes])

  const selectedNode = selectedNodeId ? nodesById.get(selectedNodeId) ?? null : null
  const selectedEdge = selectedEdgeId ? draft.edges.find((edge) => edge.id === selectedEdgeId) ?? null : null
  const selectedNodeIssues = selectedNode ? issuesForId(allIssues, 'node', selectedNode.id) : []
  const selectedEdgeIssues = selectedEdge ? issuesForId(allIssues, 'edge', selectedEdge.id) : []

  const getNodeDisplayName = (nodeId: string) => {
    const node = nodesById.get(nodeId)
    if (!node) return nodeId
    return `${node.label || node.id} (${node.id})`
  }

  const updateNode = (nodeId: string, updater: (node: FlowNode) => FlowNode) => {
    setDraft((prev) => ({
      ...prev,
      nodes: prev.nodes.map((node) => (node.id === nodeId ? updater(node) : node)),
    }))
  }

  const renameNode = (nodeId: string, nextIdRaw: string) => {
    const nextId = nextIdRaw.trim()
    if (!nextId || nextId === nodeId || draft.nodes.some((node) => node.id === nextId)) return
    setDraft((prev) => ({
      ...prev,
      nodes: prev.nodes.map((node) => (node.id === nodeId ? { ...node, id: nextId } : node)),
      edges: prev.edges.map((edge) => ({
        ...edge,
        from: edge.from === nodeId ? nextId : edge.from,
        to: edge.to === nodeId ? nextId : edge.to,
      })),
    }))
    if (selectedNodeId === nodeId) setSelectedNodeId(nextId)
    if (pendingConnectionFrom === nodeId) setPendingConnectionFrom(nextId)
  }

  const updateEdge = (edgeId: string, updater: (edge: FlowEdge) => FlowEdge) => {
    setDraft((prev) => ({
      ...prev,
      edges: prev.edges.map((edge) => (edge.id === edgeId ? updater(edge) : edge)),
    }))
  }

  const renameEdge = (edgeId: string, nextIdRaw: string) => {
    const nextId = nextIdRaw.trim()
    if (!nextId || nextId === edgeId || draft.edges.some((edge) => edge.id === nextId)) return
    setDraft((prev) => ({
      ...prev,
      edges: prev.edges.map((edge) => (edge.id === edgeId ? { ...edge, id: nextId } : edge)),
    }))
    if (selectedEdgeId === edgeId) setSelectedEdgeId(nextId)
  }

  const handleAddNode = (type: FlowNodeType) => {
    const nextNode = defaultNode(type, draft.nodes.length + 1, design)
    setDraft((prev) => ({
      ...prev,
      nodes: [...prev.nodes, nextNode],
    }))
    setSelectedNodeId(nextNode.id)
    setSelectedEdgeId(null)
  }

  const handleDeleteNode = (nodeId: string) => {
    setDraft((prev) => ({
      ...prev,
      nodes: prev.nodes.filter((node) => node.id !== nodeId),
      edges: prev.edges.filter((edge) => edge.from !== nodeId && edge.to !== nodeId),
    }))
    if (selectedNodeId === nodeId) setSelectedNodeId(null)
    if (pendingConnectionFrom === nodeId) setPendingConnectionFrom(null)
    setSelectedEdgeId(null)
  }

  const handleDeleteEdge = (edgeId: string) => {
    setDraft((prev) => ({
      ...prev,
      edges: prev.edges.filter((edge) => edge.id !== edgeId),
    }))
    if (selectedEdgeId === edgeId) setSelectedEdgeId(null)
  }

  const handleBeginConnection = (nodeId: string) => {
    setPendingConnectionFrom((current) => (current === nodeId ? null : nodeId))
    setSelectedNodeId(nodeId)
    setSelectedEdgeId(null)
  }

  const handleCompleteConnection = (targetId: string) => {
    if (!pendingConnectionFrom || pendingConnectionFrom === targetId) return
    const existingEdge = draft.edges.find((edge) => edge.from === pendingConnectionFrom && edge.to === targetId)
    if (existingEdge) {
      setPendingConnectionFrom(null)
      setSelectedEdgeId(existingEdge.id)
      setSelectedNodeId(null)
      return
    }
    const edgeId = `edge_${draft.edges.length + 1}`
    const nextEdge: FlowEdge = {
      id: edgeId,
      from: pendingConnectionFrom,
      to: targetId,
      condition: null,
    }
    setDraft((prev) => ({
      ...prev,
      edges: [...prev.edges, nextEdge],
    }))
    setPendingConnectionFrom(null)
    setSelectedEdgeId(edgeId)
    setSelectedNodeId(null)
  }

  const handleAutoLayout = () => {
    viewportResetRef.current = true
    setDraft((prev) => autoLayoutGraph(prev))
    push({
      tone: 'info',
      title: 'Flujo reordenado',
      description: 'Se aplico un layout automatico para acomodar el esquema.',
    })
  }

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const tagName = target?.tagName ?? ''
      if (tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'SELECT') return

      if (event.key === 'Escape') {
        setPendingConnectionFrom(null)
        return
      }

      if (event.key !== 'Delete' && event.key !== 'Backspace') return
      if (selectedEdgeId) {
        event.preventDefault()
        handleDeleteEdge(selectedEdgeId)
      } else if (selectedNodeId) {
        event.preventDefault()
        handleDeleteNode(selectedNodeId)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [selectedEdgeId, selectedNodeId])

  const handleValidate = async () => {
    setValidating(true)
    setErrorMsg('')
    try {
      const report = normalizeValidationReport(await agentsApi.validateGraph(design.agent_id, draft)) ?? {
        ok: false,
        errors: [],
        warnings: [],
      }
      setValidation(report)
      push({
        tone: report.ok ? 'success' : 'info',
        title: report.ok ? 'Flujo valido' : 'Hay observaciones en el flujo',
        description: report.ok
          ? 'La estructura del proceso quedo lista para guardar.'
          : `${report.errors.length} errores y ${report.warnings.length} warnings para revisar.`,
      })
    } catch (e: any) {
      const detail = e?.response?.data?.detail ?? e?.response?.data
      const report = normalizeValidationReport(detail)
      if (report) setValidation(report)
      setErrorMsg(asErrorMessage(detail, 'No se pudo validar el flujo.'))
    } finally {
      setValidating(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setErrorMsg('')
    try {
      const result = await agentsApi.updateGraph(design.agent_id, draft)
      const nextDesign: AgentDesign = {
        ...design,
        graph_blueprint: result.graph_blueprint,
        mermaid_diagram: result.mermaid_diagram,
      }
      setDraft(cloneGraph(result.graph_blueprint))
      setValidation(result.validation)
      push({
        tone: 'success',
        title: 'Flujo guardado',
        description: 'El blueprint quedo persistido y Mermaid se regenero.',
      })
      onSaved(nextDesign)
    } catch (e: any) {
      const detail = e?.response?.data?.detail ?? e?.response?.data
      const report = normalizeValidationReport(detail)
      if (report) {
        setValidation(report)
        setErrorMsg('El flujo tiene errores de validacion. Revisalos antes de guardar.')
      } else {
        setErrorMsg(asErrorMessage(detail, 'No se pudo guardar el flujo.'))
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Editor visual de flujo</CardTitle>
          <CardDescription>
            Arrastra nodos sobre el canvas, conectalos desde los handles laterales y edita el
            <code> graph_blueprint </code>
            real del agente.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {NODE_TYPES.map((nodeType) => (
              <Button
                key={nodeType.value}
                variant="secondary"
                onClick={() => handleAddNode(nodeType.value)}
              >
                <Plus className="h-4 w-4" />
                {nodeType.label}
              </Button>
            ))}
            <Button variant="secondary" onClick={handleAutoLayout} disabled={!draft.nodes.length}>
              <Workflow className="h-4 w-4" />
              Autoordenar
            </Button>
            <Button variant="secondary" onClick={handleValidate} disabled={validating}>
              <Shuffle className="h-4 w-4" />
              {validating ? 'Validando...' : 'Validar flujo'}
            </Button>
            <Button onClick={handleSave} disabled={saving || !isDirty}>
              <Save className="h-4 w-4" />
              {saving ? 'Guardando...' : 'Guardar flujo'}
            </Button>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <Badge tone={design.spec.mode === 'crew' ? 'violet' : 'blue'}>
              {design.spec.mode === 'crew' ? 'CrewAI' : 'LangChain'}
            </Badge>
            <Badge tone={validation?.ok ? 'green' : validation ? 'amber' : 'slate'}>
              {validation ? (validation.ok ? 'Valido' : 'Con observaciones') : 'Sin validar'}
            </Badge>
            {isDirty && <span>Cambios sin guardar</span>}
            {pendingConnectionFrom && (
              <span className="rounded-full border border-sky-200 bg-sky-50 px-2 py-1 text-sky-700">
                Conectando desde {pendingConnectionFrom}. Hace click en la entrada del nodo destino.
              </span>
            )}
            <span>Supr/Backspace elimina lo seleccionado</span>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 2xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>Canvas del flujo</CardTitle>
            <CardDescription>
              Click en un nodo para inspeccionarlo. Arrastra desde el grip para moverlo.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div
              ref={canvasRef}
              className="overflow-auto rounded-2xl border border-slate-200 bg-[radial-gradient(circle_at_1px_1px,#e2e8f0_1px,transparent_0)] [background-size:24px_24px]"
            >
              <div
                className="relative"
                style={{ width: canvasBounds.width, height: canvasBounds.height }}
                onClick={() => {
                  setSelectedNodeId(null)
                  setSelectedEdgeId(null)
                }}
              >
                <svg className="absolute inset-0 h-full w-full overflow-visible">
                  {draft.edges.map((edge) => {
                    const source = nodesById.get(edge.from)
                    const target = nodesById.get(edge.to)
                    if (!source || !target) return null
                    const path = buildEdgePath(source, target)
                    const selected = selectedEdgeId === edge.id
                    const edgeIssues = issuesForId(allIssues, 'edge', edge.id)
                    return (
                      <g key={edge.id}>
                        <path
                          d={path}
                          fill="none"
                          stroke={selected ? '#7c3aed' : edgeIssues.some((issue) => issue.level === 'error') ? '#e11d48' : '#94a3b8'}
                          strokeWidth={selected ? 3 : 2}
                          strokeDasharray={edge.condition ? '7 5' : undefined}
                        />
                        <path
                          d={path}
                          fill="none"
                          stroke="transparent"
                          strokeWidth={18}
                          className="cursor-pointer"
                          onClick={(event) => {
                            event.stopPropagation()
                            setSelectedEdgeId(edge.id)
                            setSelectedNodeId(null)
                          }}
                        />
                        {edge.condition && (
                          <text
                            x={(getNodePoint(source, 'right').x + getNodePoint(target, 'left').x) / 2}
                            y={(getNodePoint(source, 'right').y + getNodePoint(target, 'left').y) / 2 - 8}
                            textAnchor="middle"
                            className="fill-slate-500 text-[11px]"
                          >
                            {edge.condition}
                          </text>
                        )}
                      </g>
                    )
                  })}
                </svg>

                {draft.nodes.map((node) => {
                  const position = node.position ?? { x: 0, y: 0 }
                  const selected = selectedNodeId === node.id
                  const nodeIssues = issuesForId(allIssues, 'node', node.id)
                  const errorCount = nodeIssues.filter((issue) => issue.level === 'error').length
                  const warningCount = nodeIssues.filter((issue) => issue.level === 'warning').length

                  return (
                    <div
                      key={node.id}
                      className={`absolute rounded-xl border bg-white shadow-sm transition ${
                        selected ? 'border-violet-400 ring-2 ring-violet-200' : 'border-slate-200 hover:border-slate-300'
                      }`}
                      style={{
                        width: NODE_WIDTH,
                        height: NODE_HEIGHT,
                        left: position.x,
                        top: position.y,
                      }}
                      onClick={(event) => {
                        event.stopPropagation()
                        setSelectedNodeId(node.id)
                        setSelectedEdgeId(null)
                      }}
                    >
                      <button
                        type="button"
                        className="absolute left-[-6px] top-[calc(50%-6px)] h-3 w-3 rounded-full border-2 border-white bg-slate-400 shadow"
                        onClick={(event) => {
                          event.stopPropagation()
                          handleCompleteConnection(node.id)
                        }}
                        title={pendingConnectionFrom ? 'Conectar aqui' : 'Entrada'}
                      />
                      <button
                        type="button"
                        className={`absolute right-[-6px] top-[calc(50%-6px)] h-3 w-3 rounded-full border-2 border-white shadow ${
                          pendingConnectionFrom === node.id ? 'bg-violet-600' : 'bg-sky-500'
                        }`}
                        onClick={(event) => {
                          event.stopPropagation()
                          handleBeginConnection(node.id)
                        }}
                        title="Crear conexion desde este nodo"
                      />

                      <div className="flex h-full flex-col">
                        <div
                          className="flex cursor-move items-center justify-between gap-2 rounded-t-xl border-b border-slate-100 px-2.5 py-1.5"
                          onMouseDown={(event) => {
                            if (!canvasRef.current) return
                            const rect = canvasRef.current.getBoundingClientRect()
                            const scrollLeft = canvasRef.current.scrollLeft
                            const scrollTop = canvasRef.current.scrollTop
                            dragRef.current = {
                              nodeId: node.id,
                              offsetX: event.clientX - rect.left + scrollLeft - position.x,
                              offsetY: event.clientY - rect.top + scrollTop - position.y,
                            }
                          }}
                        >
                          <div className="flex items-center gap-2">
                            <Grip className="h-3.5 w-3.5 text-slate-400" />
                            <Badge className={getNodeTone(node.type)}>{node.type}</Badge>
                          </div>
                          <div className="flex items-center gap-1">
                            {(errorCount > 0 || warningCount > 0) && (
                              <div className="flex items-center gap-1 text-[10px] text-slate-500">
                                {errorCount > 0 && <span className="rounded-full bg-rose-100 px-1.5 py-0.5 text-rose-700">{errorCount} err</span>}
                                {warningCount > 0 && <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-amber-700">{warningCount} warn</span>}
                              </div>
                            )}
                            <button
                              type="button"
                              className="rounded-md p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                              onClick={(event) => {
                                event.stopPropagation()
                                handleDeleteNode(node.id)
                              }}
                              title="Borrar nodo"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                        <div className="flex flex-1 flex-col justify-between px-2.5 py-2.5">
                          <div>
                            <div className="line-clamp-1 text-sm font-semibold text-slate-950">{node.label}</div>
                            <div className="mt-1 line-clamp-2 text-[11px] leading-4 text-slate-500">
                              {node.description || node.data?.description || 'Sin descripcion operativa.'}
                            </div>
                          </div>
                          <div className="mt-2 flex items-center justify-between gap-2 text-[10px] text-slate-400">
                            <span className="truncate">{node.id}</span>
                            {node.type === 'agent' && design.spec.mode === 'crew' && (
                              <span className="truncate">{node.data?.assigned_agent || 'Sin agente'}</span>
                            )}
                            {node.type === 'tool' && design.spec.mode === 'single' && (
                              <span className="truncate">{node.data?.tool_name || 'Sin tool'}</span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Inspector</CardTitle>
              <CardDescription>
                Edita el nodo o la conexion seleccionada. Todo impacta sobre el esquema real.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium text-slate-900">Conexiones</div>
                  <Badge tone="slate">{draft.edges.length}</Badge>
                </div>
                {draft.edges.length === 0 ? (
                  <div className="text-xs text-slate-500">Todavia no hay conexiones creadas.</div>
                ) : (
                  <div className="space-y-2">
                    {draft.edges.map((edge) => {
                      const selected = selectedEdgeId === edge.id
                      return (
                        <div
                          key={edge.id}
                          className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs ${
                            selected ? 'border-violet-300 bg-violet-50' : 'border-slate-200 bg-white'
                          }`}
                        >
                          <button
                            type="button"
                            className="flex-1 text-left text-slate-700"
                            onClick={() => {
                              setSelectedEdgeId(edge.id)
                              setSelectedNodeId(null)
                            }}
                          >
                            <div className="font-medium text-slate-900">{edge.id}</div>
                            <div className="text-slate-500">
                              {getNodeDisplayName(edge.from)} {'->'} {getNodeDisplayName(edge.to)}
                            </div>
                          </button>
                          <button
                            type="button"
                            className="rounded-md p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                            onClick={() => handleDeleteEdge(edge.id)}
                            title="Borrar conexion"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              {!selectedNode && !selectedEdge && (
                <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-sm text-slate-500">
                  Selecciona un nodo o una conexion para editar propiedades. Si quieres empezar
                  rapido, agrega un nodo y arrastralo al canvas.
                </div>
              )}

              {selectedNode && (
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-slate-950">{selectedNode.label || selectedNode.id}</div>
                      <div className="text-xs text-slate-500">{selectedNode.id}</div>
                    </div>
                    <Button variant="ghost" onClick={() => handleDeleteNode(selectedNode.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>

                  <Field label="ID">
                    <Input
                      value={selectedNode.id}
                      onChange={(event) => renameNode(selectedNode.id, event.target.value)}
                    />
                  </Field>

                  <Field label="Tipo">
                    <select
                      value={selectedNode.type}
                      onChange={(event) =>
                        updateNode(selectedNode.id, (current) => ({
                          ...current,
                          type: event.target.value as FlowNodeType,
                        }))
                      }
                      className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500"
                    >
                      {NODE_TYPES.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </Field>

                  <Field label="Label">
                    <Input
                      value={selectedNode.label}
                      onChange={(event) =>
                        updateNode(selectedNode.id, (current) => ({ ...current, label: event.target.value }))
                      }
                    />
                  </Field>

                  <Field label="Descripcion">
                    <textarea
                      value={selectedNode.description}
                      onChange={(event) =>
                        updateNode(selectedNode.id, (current) => ({
                          ...current,
                          description: event.target.value,
                          data: { ...current.data, description: event.target.value || undefined },
                        }))
                      }
                      rows={5}
                      className="w-full resize-y rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500"
                    />
                  </Field>

                  {design.spec.mode === 'crew' && selectedNode.type === 'agent' && (
                    <Field label="Agente asignado">
                      <select
                        value={selectedNode.data?.assigned_agent ?? ''}
                        onChange={(event) =>
                          updateNode(selectedNode.id, (current) => ({
                            ...current,
                            data: { ...current.data, assigned_agent: event.target.value || undefined },
                          }))
                        }
                        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500"
                      >
                        <option value="">- selecciona un agente -</option>
                        {roleOptions.map((role) => (
                          <option key={role.name} value={role.name}>
                            {role.role}
                          </option>
                        ))}
                      </select>
                    </Field>
                  )}

                  {design.spec.mode === 'single' && selectedNode.type === 'tool' && (
                    <Field label="Tool asociada">
                      <select
                        value={selectedNode.data?.tool_name ?? ''}
                        onChange={(event) =>
                          updateNode(selectedNode.id, (current) => ({
                            ...current,
                            data: { ...current.data, tool_name: event.target.value || undefined },
                          }))
                        }
                        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500"
                      >
                        <option value="">- selecciona una tool -</option>
                        {toolOptions.map((tool) => (
                          <option key={tool.name} value={tool.name}>
                            {tool.name}
                          </option>
                        ))}
                      </select>
                    </Field>
                  )}

                  {selectedNodeIssues.length > 0 && (
                    <div className="space-y-2">
                      {selectedNodeIssues.map((issue, index) => (
                        <div
                          key={`${issue.code}_${index}`}
                          className={`rounded-lg px-3 py-2 text-xs ${
                            issue.level === 'error'
                              ? 'border border-rose-200 bg-rose-50 text-rose-700'
                              : 'border border-amber-200 bg-amber-50 text-amber-700'
                          }`}
                        >
                          {issue.message}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {selectedEdge && (
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-slate-950">Conexion {selectedEdge.id}</div>
                      <div className="text-xs text-slate-500">
                        {selectedEdge.from}{' -> '}{selectedEdge.to}
                      </div>
                    </div>
                    <Button variant="ghost" onClick={() => handleDeleteEdge(selectedEdge.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>

                  <Field label="ID">
                    <Input
                      value={selectedEdge.id}
                      onChange={(event) => renameEdge(selectedEdge.id, event.target.value)}
                    />
                  </Field>

                  <Field label="Desde">
                    <select
                      value={selectedEdge.from}
                      onChange={(event) =>
                        updateEdge(selectedEdge.id, (current) => ({ ...current, from: event.target.value }))
                      }
                      className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500"
                    >
                      {draft.nodes.map((node) => (
                        <option key={node.id} value={node.id}>
                          {node.label} ({node.id})
                        </option>
                      ))}
                    </select>
                  </Field>

                  <Field label="Hacia">
                    <select
                      value={selectedEdge.to}
                      onChange={(event) =>
                        updateEdge(selectedEdge.id, (current) => ({ ...current, to: event.target.value }))
                      }
                      className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500"
                    >
                      {draft.nodes.map((node) => (
                        <option key={node.id} value={node.id}>
                          {node.label} ({node.id})
                        </option>
                      ))}
                    </select>
                  </Field>

                  <Field label="Condicion">
                    <Input
                      value={selectedEdge.condition ?? ''}
                      onChange={(event) =>
                        updateEdge(selectedEdge.id, (current) => ({
                          ...current,
                          condition: event.target.value || null,
                        }))
                      }
                      placeholder="Ej: Resultado aprobado"
                    />
                  </Field>

                  {selectedEdgeIssues.length > 0 && (
                    <div className="space-y-2">
                      {selectedEdgeIssues.map((issue, index) => (
                        <div
                          key={`${issue.code}_${index}`}
                          className={`rounded-lg px-3 py-2 text-xs ${
                            issue.level === 'error'
                              ? 'border border-rose-200 bg-rose-50 text-rose-700'
                              : 'border border-amber-200 bg-amber-50 text-amber-700'
                          }`}
                        >
                          {issue.message}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Validacion</CardTitle>
              <CardDescription>Feedback estructural del blueprint actual.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {errorMsg && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  {errorMsg}
                </div>
              )}

              {!validation && !errorMsg && (
                <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">
                  Todavia no validaste este flujo. Puedes mover nodos, conectar pasos y validar
                  antes de guardar.
                </div>
              )}

              {validation && (
                <>
                  <div className="flex items-center gap-2 text-sm">
                    {validation.ok ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                    ) : (
                      <AlertTriangle className="h-4 w-4 text-amber-600" />
                    )}
                    <Badge tone={validation.ok ? 'green' : 'amber'}>
                      {validation.ok ? 'Listo' : 'Revisar'}
                    </Badge>
                    <span className="text-slate-600">
                      {validation.errors.length} errores · {validation.warnings.length} warnings
                    </span>
                  </div>

                  {allIssues.map((issue, index) => (
                    <button
                      key={`${issue.code}_${index}`}
                      type="button"
                      onClick={() => {
                        if (issue.node_id) {
                          setSelectedNodeId(issue.node_id)
                          setSelectedEdgeId(null)
                        } else if (issue.edge_id) {
                          setSelectedEdgeId(issue.edge_id)
                          setSelectedNodeId(null)
                        }
                      }}
                      className={`flex w-full items-start gap-3 rounded-xl px-4 py-3 text-left text-sm ${
                        issue.level === 'error'
                          ? 'border border-rose-200 bg-rose-50 text-rose-700'
                          : 'border border-amber-200 bg-amber-50 text-amber-700'
                      }`}
                    >
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                      <div>
                        <div className="font-medium">{issue.code}</div>
                        <div>{issue.message}</div>
                      </div>
                    </button>
                  ))}
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
