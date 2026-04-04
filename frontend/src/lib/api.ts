import axios, { type AxiosInstance } from 'axios'
import type { AgentDesign, AgentResponse, AgentSpec, WizardState } from '../types/agent'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ── Instancia axios con interceptor de JWT ────────────────────────────────────

function createClient(): AxiosInstance {
  const client = axios.create({ baseURL: `${BASE_URL}/api/v1` })

  client.interceptors.request.use(cfg => {
    const token = localStorage.getItem('agentica_token')
    if (token) cfg.headers.Authorization = `Bearer ${token}`
    return cfg
  })

  client.interceptors.response.use(
    r => r,
    err => {
      if (err.response?.status === 401) {
        localStorage.removeItem('agentica_token')
        window.location.href = '/login'
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
): {
  send: (input: string, sessionId: string) => void
  close: () => void
} {
  const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'
  const ws = new WebSocket(`${WS_URL}/api/v1/agents/${agentId}/ws`)

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

