import axios, { type AxiosInstance } from 'axios'
import type {
  AgentDesign, AgentResponse, AgentSpec, WizardState,
  Skill, MCPServer, KnowledgeBase, BehaviorPolicy, GuardrailRule,
} from '../types/agent'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const APP_BASE = import.meta.env.BASE_URL || '/'

// ── Instancia axios con interceptor de JWT ────────────────────────────────────

function createClient(): AxiosInstance {
  const client = axios.create({ baseURL: `${BASE_URL}/api/v1` })

  client.interceptors.request.use(cfg => {
    const token = localStorage.getItem('agentica_token')
    if (token) cfg.headers.Authorization = `Bearer ${token}`
    console.log('[Agentica][API] request', {
      method: cfg.method,
      baseURL: cfg.baseURL,
      url: cfg.url,
      hasToken: !!token,
    })
    return cfg
  })

  client.interceptors.response.use(
    r => {
      console.log('[Agentica][API] response', {
        status: r.status,
        url: r.config?.url,
      })
      return r
    },
    err => {
      console.error('[Agentica][API] error', {
        status: err.response?.status,
        url: err.config?.url,
        data: err.response?.data,
        message: err.message,
      })
      if (err.response?.status === 401) {
        localStorage.removeItem('agentica_token')
        window.location.href = APP_BASE
      }
      return Promise.reject(err)
    }
  )

  return client
}

const api = createClient()


// ── Auth ──────────────────────────────────────────────────────────────────────

export const authApi = {
  register: (email: string, password: string) =>
    api.post('/auth/register', { email, password }).then(r => r.data),

  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }).then(r => r.data),

  me: () => api.get('/auth/me').then(r => r.data),
}


// ── Agents ────────────────────────────────────────────────────────────────────

export const agentsApi = {
  createFromSpec: (spec: AgentSpec): Promise<AgentDesign> =>
    api.post('/agents/spec', spec).then(r => r.data),

  build: (agentId: string) =>
    api.post(`/agents/${agentId}/build`).then(r => r.data),

  invoke: (agentId: string, input: string, sessionId?: string): Promise<AgentResponse> =>
    api.post(`/agents/${agentId}/invoke`, { input, session_id: sessionId || '' }).then(r => r.data),

  eval: (agentId: string) =>
    api.post(`/agents/${agentId}/eval`).then(r => r.data),

  optimize: (agentId: string, evalReport: object, autoRebuild = false) =>
    api.post(`/agents/${agentId}/optimize`, { eval_report: evalReport, auto_rebuild: autoRebuild }).then(r => r.data),

  getDesign: (agentId: string): Promise<AgentDesign> =>
    api.get(`/agents/${agentId}/design`).then(r => r.data),

  getState: (agentId: string, sessionId = 'default') =>
    api.get(`/agents/${agentId}/state`, { params: { session_id: sessionId } }).then(r => r.data),

  resetSession: (agentId: string, sessionId: string) =>
    api.delete(`/agents/${agentId}/session/${sessionId}`),
}


// ── WebSocket helper ──────────────────────────────────────────────────────────

export type WSMessage =
  | { type: 'token';  content: string }
  | { type: 'done';   session_id: string }
  | { type: 'error';  message: string }

export function createAgentWebSocket(
  agentId: string,
  onToken: (token: string) => void,
  onDone: (sessionId: string) => void,
  onError: (msg: string) => void,
  options: { apiKey?: string } = {},
): {
  send: (input: string, sessionId: string) => void
  close: () => void
} {
  const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'
  const params = new URLSearchParams()
  const token = localStorage.getItem('agentica_token')
  if (token) params.set('token', token)
  if (options.apiKey) params.set('api_key', options.apiKey)
  const query = params.toString()
  const ws = new WebSocket(`${WS_URL}/api/v1/agents/${agentId}/ws${query ? `?${query}` : ''}`)

  ws.onmessage = (ev) => {
    try {
      const msg: WSMessage = JSON.parse(ev.data)
      if (msg.type === 'token') onToken(msg.content)
      else if (msg.type === 'done') onDone(msg.session_id)
      else if (msg.type === 'error') onError(msg.message)
    } catch { /* ignorar parse errors */ }
  }

  ws.onerror = () => onError('Error de conexión WebSocket')

  return {
    send: (input: string, sessionId: string) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ input, session_id: sessionId }))
      }
    },
    close: () => ws.close(),
  }
}


// ── Knowledge ─────────────────────────────────────────────────────────────────

export const knowledgeApi = {
  getSources: (agentId: string) =>
    api.get(`/knowledge/${agentId}/sources`).then(r => r.data),

  deleteSource: (agentId: string, source: string) =>
    api.delete(`/knowledge/${agentId}/source`, { data: { source } }).then(r => r.data),

  ingestJson: (agentId: string, sources: string[], chunk_size = 500, chunk_overlap = 50) =>
    api.post(`/knowledge/${agentId}/ingest`, {
      agent_id: agentId,
      rag_spec: { sources, chunk_size, chunk_overlap }
    }).then(r => r.data),

  ingestFile: (agentId: string, file: File, chunk_size = 500, chunk_overlap = 50) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('chunk_size', chunk_size.toString())
    formData.append('chunk_overlap', chunk_overlap.toString())
    return api.post(`/knowledge/${agentId}/ingest/file`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }).then(r => r.data)
  },

  getStats: (agentId: string) =>
    api.get(`/knowledge/${agentId}/stats`).then(r => r.data),

  retrieve: (agentId: string, query: string, top_k = 4) =>
    api.post(`/knowledge/${agentId}/retrieve`, { query, top_k }).then(r => r.data),
}


// ── Helpers ───────────────────────────────────────────────────────────────────

export function wizardStateToSpec(state: WizardState, tenantId: string): AgentSpec {
  return {
    tenant_id: tenantId,
    name: state.name,
    description: state.description,
    goal: state.goal,
    mode: state.mode!,
    channels: state.channels,
    model_params: state.model_params,
    constraints: state.constraints,
    expected_inputs: [],
    expected_outputs: [],
    memory: state.memory,
    rag: state.rag,
    tools: state.tools,
    autonomy_level: state.autonomy_level,
    agents: state.agents,
    process: state.process,
  }
}

// ── Custom Tools ──────────────────────────────────────────────────────────────

export const customToolsApi = {
  list: () =>
    api.get('/tools/custom/').then(r => r.data),

  get: (id: string) =>
    api.get(`/tools/custom/${id}`).then(r => r.data),

  create: (data: {
    name: string; description: string; source_code: string;
    config_schema?: Record<string, any>; test_input?: string
  }) => api.post('/tools/custom/', data).then(r => r.data),

  update: (id: string, data: Partial<{
    description: string; source_code: string;
    config_schema: Record<string, any>; is_active: boolean; test_input: string
  }>) => api.put(`/tools/custom/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/tools/custom/${id}`).then(r => r.data),

  validate: (source_code: string) =>
    api.post('/tools/custom/validate', { source_code }).then(r => r.data),

  test: (id: string, input: string, config: Record<string, any> = {}) =>
    api.post(`/tools/custom/${id}/test`, { input, config }).then(r => r.data),
}


// ── Skills ────────────────────────────────────────────────────────────────────

export const skillsApi = {
  list: (): Promise<Skill[]> =>
    api.get('/skills/').then(r => r.data),

  get: (id: string): Promise<Skill> =>
    api.get(`/skills/${id}`).then(r => r.data),

  create: (data: Omit<Skill, 'id' | 'is_active' | 'created_at'>): Promise<Skill> =>
    api.post('/skills/', data).then(r => r.data),

  update: (id: string, data: Omit<Skill, 'id' | 'is_active' | 'created_at'>): Promise<Skill> =>
    api.put(`/skills/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/skills/${id}`),

  forAgent: (agentId: string): Promise<Skill[]> =>
    api.get(`/agents/${agentId}/skills`).then(r => r.data),

  assignToAgent: (agentId: string, skillId: string) =>
    api.post(`/agents/${agentId}/skills/${skillId}`),

  unassignFromAgent: (agentId: string, skillId: string) =>
    api.delete(`/agents/${agentId}/skills/${skillId}`),
}


// ── MCP Servers ───────────────────────────────────────────────────────────────

export const mcpApi = {
  list: (): Promise<MCPServer[]> =>
    api.get('/mcp/').then(r => r.data),

  get: (id: string): Promise<MCPServer> =>
    api.get(`/mcp/${id}`).then(r => r.data),

  create: (data: Pick<MCPServer, 'name' | 'endpoint' | 'transport' | 'auth_type' | 'auth_config'>): Promise<MCPServer> =>
    api.post('/mcp/', data).then(r => r.data),

  update: (id: string, data: Pick<MCPServer, 'name' | 'endpoint' | 'transport' | 'auth_type' | 'auth_config'>): Promise<MCPServer> =>
    api.put(`/mcp/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/mcp/${id}`),

  test: (id: string): Promise<MCPServer> =>
    api.post(`/mcp/${id}/test`).then(r => r.data),

  forAgent: (agentId: string): Promise<MCPServer[]> =>
    api.get(`/agents/${agentId}/mcp`).then(r => r.data),

  assignToAgent: (agentId: string, serverId: string) =>
    api.post(`/agents/${agentId}/mcp/${serverId}`),

  unassignFromAgent: (agentId: string, serverId: string) =>
    api.delete(`/agents/${agentId}/mcp/${serverId}`),
}


// ── Knowledge Bases ───────────────────────────────────────────────────────────

export const knowledgeBasesApi = {
  list: (): Promise<KnowledgeBase[]> =>
    api.get('/knowledge-bases/').then(r => r.data),

  get: (id: string): Promise<KnowledgeBase> =>
    api.get(`/knowledge-bases/${id}`).then(r => r.data),

  create: (data: Pick<KnowledgeBase, 'name' | 'description' | 'rag_spec'>): Promise<KnowledgeBase> =>
    api.post('/knowledge-bases/', data).then(r => r.data),

  update: (id: string, data: Pick<KnowledgeBase, 'name' | 'description' | 'rag_spec'>): Promise<KnowledgeBase> =>
    api.put(`/knowledge-bases/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/knowledge-bases/${id}`),

  ingest: (id: string) =>
    api.post(`/knowledge-bases/${id}/ingest`).then(r => r.data),

  ingestFile: (id: string, file: File, chunk_size = 500, chunk_overlap = 50) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('chunk_size', chunk_size.toString())
    formData.append('chunk_overlap', chunk_overlap.toString())
    return api.post(`/knowledge-bases/${id}/ingest/file`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },

  getSources: (id: string) =>
    api.get(`/knowledge-bases/${id}/sources`).then(r => r.data),

  deleteSource: (id: string, source: string) =>
    api.delete(`/knowledge-bases/${id}/sources`, { data: { source } }).then(r => r.data),

  forAgent: (agentId: string): Promise<KnowledgeBase[]> =>
    api.get(`/agents/${agentId}/knowledge-bases`).then(r => r.data),

  assignToAgent: (agentId: string, kbId: string) =>
    api.post(`/agents/${agentId}/knowledge-bases/${kbId}`),

  unassignFromAgent: (agentId: string, kbId: string) =>
    api.delete(`/agents/${agentId}/knowledge-bases/${kbId}`),
}


// ── Behavior Policies ─────────────────────────────────────────────────────────

export const policiesApi = {
  get: (agentId: string): Promise<BehaviorPolicy> =>
    api.get(`/agents/${agentId}/policy`).then(r => r.data),

  upsert: (agentId: string, data: Omit<BehaviorPolicy, 'id' | 'agent_id'>): Promise<BehaviorPolicy> =>
    api.put(`/agents/${agentId}/policy`, data).then(r => r.data),

  delete: (agentId: string) =>
    api.delete(`/agents/${agentId}/policy`),
}


// ── Guardrails ────────────────────────────────────────────────────────────────

export const guardrailsApi = {
  list: (agentId: string): Promise<GuardrailRule[]> =>
    api.get(`/agents/${agentId}/guardrails`).then(r => r.data),

  create: (agentId: string, data: Omit<GuardrailRule, 'id' | 'agent_id' | 'is_active'>): Promise<GuardrailRule> =>
    api.post(`/agents/${agentId}/guardrails`, data).then(r => r.data),

  update: (agentId: string, ruleId: string, data: Omit<GuardrailRule, 'id' | 'agent_id' | 'is_active'>): Promise<GuardrailRule> =>
    api.put(`/agents/${agentId}/guardrails/${ruleId}`, data).then(r => r.data),

  toggle: (agentId: string, ruleId: string): Promise<GuardrailRule> =>
    api.patch(`/agents/${agentId}/guardrails/${ruleId}/toggle`).then(r => r.data),

  delete: (agentId: string, ruleId: string) =>
    api.delete(`/agents/${agentId}/guardrails/${ruleId}`),
}
