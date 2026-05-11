import { AlertTriangle, GitBranch, Plus, Save, Shuffle, Trash2, Workflow } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

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

function cloneGraph(graph: GraphBlueprint): GraphBlueprint {
  return JSON.parse(JSON.stringify(graph))
}

function defaultNode(type: FlowNodeType, index: number, design: AgentDesign): FlowNode {
  const roleOptions = design.spec.agents ?? []
  const toolOptions = design.spec.tools ?? []
  return {
    id: `${type}_${index}`,
    type,
    label: type === 'agent' ? `Paso ${index}` : type === 'decision' ? `Revision ${index}` : type === 'tool' ? `Tool ${index}` : type === 'start' ? 'Inicio' : 'Fin',
    description: '',
    position: { x: 120 + ((index - 1) % 3) * 240, y: 120 + Math.floor((index - 1) / 3) * 140 },
    data: {
      assigned_agent: type === 'agent' && design.spec.mode === 'crew' && roleOptions.length ? roleOptions[0].name : undefined,
      tool_name: type === 'tool' && toolOptions.length ? toolOptions[0].name : undefined,
      allowed_tools: [],
    },
  }
}

function defaultEdge(index: number, graph: GraphBlueprint): FlowEdge {
  const from = graph.nodes[0]?.id ?? ''
  const to = graph.nodes[1]?.id ?? graph.nodes[0]?.id ?? ''
  return { id: `edge_${index}`, from, to, condition: null }
}

function issuesForId(issues: GraphValidationIssue[], kind: 'node' | 'edge', id: string) {
  return issues.filter((issue) => (kind === 'node' ? issue.node_id === id : issue.edge_id === id))
}

export function FlowEditor({ design, onSaved }: Props) {
  const { push } = useToast()
  const [draft, setDraft] = useState<GraphBlueprint>(cloneGraph(design.graph_blueprint))
  const [validation, setValidation] = useState<GraphValidationReport | null>(null)
  const [saving, setSaving] = useState(false)
  const [validating, setValidating] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    setDraft(cloneGraph(design.graph_blueprint))
    setValidation(null)
    setErrorMsg('')
  }, [design])

  const isDirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(design.graph_blueprint),
    [draft, design.graph_blueprint],
  )

  const roleOptions = design.spec.agents ?? []
  const toolOptions = design.spec.tools ?? []

  const updateNode = (nodeId: string, updater: (node: FlowNode) => FlowNode) => {
    setDraft((prev) => ({
      ...prev,
      nodes: prev.nodes.map((node) => (node.id === nodeId ? updater(node) : node)),
    }))
  }

  const updateEdge = (edgeId: string, updater: (edge: FlowEdge) => FlowEdge) => {
    setDraft((prev) => ({
      ...prev,
      edges: prev.edges.map((edge) => (edge.id === edgeId ? updater(edge) : edge)),
    }))
  }

  const handleAddNode = (type: FlowNodeType) => {
    setDraft((prev) => ({
      ...prev,
      nodes: [...prev.nodes, defaultNode(type, prev.nodes.length + 1, design)],
    }))
  }

  const handleDeleteNode = (nodeId: string) => {
    setDraft((prev) => ({
      ...prev,
      nodes: prev.nodes.filter((node) => node.id !== nodeId),
      edges: prev.edges.filter((edge) => edge.from !== nodeId && edge.to !== nodeId),
    }))
  }

  const handleAddEdge = () => {
    setDraft((prev) => ({
      ...prev,
      edges: [...prev.edges, defaultEdge(prev.edges.length + 1, prev)],
    }))
  }

  const handleDeleteEdge = (edgeId: string) => {
    setDraft((prev) => ({
      ...prev,
      edges: prev.edges.filter((edge) => edge.id !== edgeId),
    }))
  }

  const handleValidate = async () => {
    setValidating(true)
    setErrorMsg('')
    try {
      const report = await agentsApi.validateGraph(design.agent_id, draft)
      setValidation(report)
      push({
        tone: report.ok ? 'success' : 'info',
        title: report.ok ? 'Flujo válido' : 'Hay observaciones en el flujo',
        description: report.ok
          ? 'La estructura del proceso quedó lista para guardar.'
          : `${report.errors.length} errores y ${report.warnings.length} warnings para revisar.`,
      })
    } catch (e: any) {
      setErrorMsg(e.response?.data?.detail || 'No se pudo validar el flujo.')
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
        description: 'El blueprint quedó persistido y el Mermaid se regeneró.',
      })
      onSaved(nextDesign)
    } catch (e: any) {
      const detail = e.response?.data?.detail
      if (detail?.errors || detail?.warnings) {
        setValidation(detail)
        setErrorMsg('El flujo tiene errores de validación. Revisalos antes de guardar.')
      } else {
        setErrorMsg(detail || 'No se pudo guardar el flujo.')
      }
    } finally {
      setSaving(false)
    }
  }

  const allIssues = validation ? [...validation.errors, ...validation.warnings] : []

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Editor de flujo</CardTitle>
          <CardDescription>
            Esta etapa usa un editor estructurado de nodos y conexiones sobre el <code>graph_blueprint</code>. Mermaid queda como vista derivada.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {NODE_TYPES.map((nodeType) => (
              <Button key={nodeType.value} variant="secondary" onClick={() => handleAddNode(nodeType.value)}>
                <Plus className="h-4 w-4" />
                {nodeType.label}
              </Button>
            ))}
            <Button variant="secondary" onClick={handleAddEdge} disabled={draft.nodes.length < 2}>
              <GitBranch className="h-4 w-4" />
              Agregar conexión
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
              {validation ? (validation.ok ? 'Válido' : 'Con observaciones') : 'Sin validar'}
            </Badge>
            {isDirty && <span>Cambios sin guardar</span>}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>Nodos</CardTitle>
            <CardDescription>Definen los pasos reales del flujo.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {draft.nodes.map((node, index) => {
              const nodeIssues = issuesForId(allIssues, 'node', node.id)
              return (
                <div key={node.id} className="rounded-xl border border-slate-200 p-4">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <Workflow className="h-4 w-4 text-violet-600" />
                      <span className="font-medium text-slate-950">{node.label || `Nodo ${index + 1}`}</span>
                      <Badge tone="slate">{node.type}</Badge>
                    </div>
                    <Button variant="ghost" onClick={() => handleDeleteNode(node.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <Field label="ID">
                      <Input value={node.id} onChange={(e) => updateNode(node.id, (current) => ({ ...current, id: e.target.value }))} />
                    </Field>
                    <Field label="Tipo">
                      <select
                        value={node.type}
                        onChange={(e) => updateNode(node.id, (current) => ({ ...current, type: e.target.value as FlowNodeType }))}
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
                      <Input value={node.label} onChange={(e) => updateNode(node.id, (current) => ({ ...current, label: e.target.value }))} />
                    </Field>
                    <Field label="Descripción">
                      <textarea
                        value={node.description}
                        onChange={(e) => updateNode(node.id, (current) => ({ ...current, description: e.target.value }))}
                        rows={3}
                        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500 resize-y"
                      />
                    </Field>

                    {design.spec.mode === 'crew' && node.type === 'agent' && (
                      <Field label="Agente asignado" className="md:col-span-2">
                        <select
                          value={node.data?.assigned_agent ?? ''}
                          onChange={(e) =>
                            updateNode(node.id, (current) => ({
                              ...current,
                              data: { ...current.data, assigned_agent: e.target.value || undefined },
                            }))
                          }
                          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500"
                        >
                          <option value="">— seleccioná un agente —</option>
                          {roleOptions.map((role) => (
                            <option key={role.name} value={role.name}>
                              {role.role}
                            </option>
                          ))}
                        </select>
                      </Field>
                    )}

                    {design.spec.mode === 'single' && node.type === 'tool' && (
                      <Field label="Tool asociada" className="md:col-span-2">
                        <select
                          value={node.data?.tool_name ?? ''}
                          onChange={(e) =>
                            updateNode(node.id, (current) => ({
                              ...current,
                              data: { ...current.data, tool_name: e.target.value || undefined },
                            }))
                          }
                          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500"
                        >
                          <option value="">— seleccioná una tool —</option>
                          {toolOptions.map((tool) => (
                            <option key={tool.name} value={tool.name}>
                              {tool.name}
                            </option>
                          ))}
                        </select>
                      </Field>
                    )}
                  </div>

                  {nodeIssues.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {nodeIssues.map((issue, issueIndex) => (
                        <div
                          key={`${node.id}_${issueIndex}`}
                          className={`rounded-lg px-3 py-2 text-xs ${issue.level === 'error' ? 'border border-rose-200 bg-rose-50 text-rose-700' : 'border border-amber-200 bg-amber-50 text-amber-700'}`}
                        >
                          {issue.message}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Conexiones</CardTitle>
              <CardDescription>Definen cómo avanza o vuelve el proceso.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {draft.edges.map((edge, index) => {
                const edgeIssues = issuesForId(allIssues, 'edge', edge.id)
                return (
                  <div key={edge.id} className="rounded-xl border border-slate-200 p-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <GitBranch className="h-4 w-4 text-sky-600" />
                        <span className="font-medium text-slate-950">Conexión {index + 1}</span>
                      </div>
                      <Button variant="ghost" onClick={() => handleDeleteEdge(edge.id)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>

                    <div className="grid gap-4">
                      <Field label="ID">
                        <Input value={edge.id} onChange={(e) => updateEdge(edge.id, (current) => ({ ...current, id: e.target.value }))} />
                      </Field>
                      <Field label="Desde">
                        <select
                          value={edge.from}
                          onChange={(e) => updateEdge(edge.id, (current) => ({ ...current, from: e.target.value }))}
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
                          value={edge.to}
                          onChange={(e) => updateEdge(edge.id, (current) => ({ ...current, to: e.target.value }))}
                          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500"
                        >
                          {draft.nodes.map((node) => (
                            <option key={node.id} value={node.id}>
                              {node.label} ({node.id})
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field label="Condición">
                        <Input
                          value={edge.condition ?? ''}
                          onChange={(e) => updateEdge(edge.id, (current) => ({ ...current, condition: e.target.value || null }))}
                          placeholder="Ej: Resultado aprobado"
                        />
                      </Field>
                    </div>

                    {edgeIssues.length > 0 && (
                      <div className="mt-3 space-y-2">
                        {edgeIssues.map((issue, issueIndex) => (
                          <div
                            key={`${edge.id}_${issueIndex}`}
                            className={`rounded-lg px-3 py-2 text-xs ${issue.level === 'error' ? 'border border-rose-200 bg-rose-50 text-rose-700' : 'border border-amber-200 bg-amber-50 text-amber-700'}`}
                          >
                            {issue.message}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Validación</CardTitle>
              <CardDescription>Feedback estructural del blueprint.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {errorMsg && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  {errorMsg}
                </div>
              )}

              {!validation && !errorMsg && (
                <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">
                  Todavía no validaste este flujo. Podés editar, validar y recién después guardarlo.
                </div>
              )}

              {validation && (
                <>
                  <div className="flex items-center gap-2 text-sm">
                    <Badge tone={validation.ok ? 'green' : 'amber'}>{validation.ok ? 'Listo' : 'Revisar'}</Badge>
                    <span className="text-slate-600">
                      {validation.errors.length} errores · {validation.warnings.length} warnings
                    </span>
                  </div>

                  {[...validation.errors, ...validation.warnings].map((issue, index) => (
                    <div
                      key={`${issue.code}_${index}`}
                      className={`flex items-start gap-3 rounded-xl px-4 py-3 text-sm ${issue.level === 'error' ? 'border border-rose-200 bg-rose-50 text-rose-700' : 'border border-amber-200 bg-amber-50 text-amber-700'}`}
                    >
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                      <div>
                        <div className="font-medium">{issue.code}</div>
                        <div>{issue.message}</div>
                      </div>
                    </div>
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
