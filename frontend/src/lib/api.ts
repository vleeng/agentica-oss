import axios, { type AxiosInstance } from 'axios'
import type {
  AgentDesign,
  AgentResponse,
  AgentSpec,
  BehaviorPolicy,
  GraphBlueprint,
  GraphUpdateResponse,
  GraphValidationReport,
  GuardrailRule,
  KnowledgeBase,
  MCPServer,
  Skill,
  ToolReadinessStatus,
  WizardState,
} from '../types/agent'
import { clearStoredToken, getAuthToken } from '../stores/auth'

// Vacío = URLs relativas → el browser llama a /api/v1/... en el mismo host/protocolo
const BASE_URL = import.meta.env.VITE_API_URL || ''
const APP_BASE = import.meta.env.BASE_URL || '/'

function logApi(event: string, payload: Record<string, unknown>) {
  console.info(`[Agentica][API] ${event}`, payload)
}

function createClient(): AxiosInstance {
  const client = axios.create({ baseURL: `${BASE_URL}/api/v1` })

  client.interceptors.request.use((cfg) => {
    ;(cfg as any).__startedAt = Date.now()
    const token = getAuthToken()
    if (token) cfg.headers.Authorization = `Bearer ${token}`
    logApi('request', {
      method: cfg.method?.toUpperCase(),
      url: cfg.url,
      has_token: Boolean(token),
      params: cfg.params || null,
      body_keys: cfg.data && typeof cfg.data === 'object' ? Object.keys(cfg.data) : null,
    })
    return cfg
  })

  client.interceptors.response.use(
    (response) => {
      logApi('response', {
        method: response.config.method?.toUpperCase(),
        url: response.config.url,
        status: response.status,
        duration_ms: Date.now() - ((response.config as any).__startedAt || Date.now()),
      })
      return response
    },
    (error) => {
      console.error('[Agentica][API] error', {
        method: error.config?.method?.toUpperCase?.(),
        url: error.config?.url,
        status: error.response?.status,
        duration_ms: Date.now() - ((error.config as any)?.__startedAt || Date.now()),
        detail: error.response?.data?.detail || error.message,
      })
      if (error.response?.status === 401) {
        clearStoredToken()
        window.location.href = APP_BASE
      }
      return Promise.reject(error)
    }
  )

  return client
}

const api = createClient()

export interface AgentSummary {
  agent_id: string
  name: string
  mode: 'single' | 'crew'
  framework: string
  status: string
  created_at: string
}

export interface TenantBillingSummary {
  calls: number
  total_tokens_in: number
  total_tokens_out: number
  total_cost_usd: number
}

export interface ProviderKey {
  id: string
  provider: string
  name: string
  is_default: boolean
  created_at: string
  truncated_key: string
  models: ProviderModel[]
}

export interface ProviderModel {
  id: string
  input_cost_per_million: number
  output_cost_per_million: number
}

export interface UsageSummary {
  plan_id: string
  agents: { used: number; limit: number; pct: number }
  invocations: { used: number; limit: number; pct: number }
  features: { rag: boolean; crew: boolean }
}

export interface BillingDay {
  day: string
  calls: number
  tokens_in: number
  tokens_out: number
  cost_usd: number
}

export interface BillingHistory {
  daily: BillingDay[]
  total_cost_usd: number
  total_calls: number
}

export interface AgentUsage {
  agent_id: string
  name: string
  status: string
  framework: string
  calls: number
  cost_usd: number
}

export interface TenantUser {
  id: string
  tenant_id: string
  email: string
  full_name?: string
  role: 'owner' | 'developer' | 'viewer'
  status: string
  created_at: string
}

export interface AuthMe {
  user_id: string
  tenant_id: string
  role: 'owner' | 'developer' | 'viewer'
  email?: string | null
  full_name?: string | null
  tenant_name?: string | null
  tenant_slug?: string | null
}

export interface ForgotPasswordResult {
  accepted: boolean
  reset_token?: string | null
  expires_in_minutes?: number
  email_sent?: boolean
}

export interface FreeAccountRequestPayload {
  first_name: string
  last_name: string
  owner_email: string
  company_name: string
  company_sector: string
  job_title: string
  password: string
}

export interface FreeAccountRequest {
  id: string
  tenant_name: string
  slug: string
  owner_email: string
  owner_name?: string | null
  company_sector?: string | null
  job_title?: string | null
  requested_plan_id: string
  status: 'pending' | 'approved' | 'rejected'
  review_notes?: string | null
  approved_tenant_id?: string | null
  processed_by_user_id?: string | null
  processed_at?: string | null
  created_at: string
}

export interface TenantRegistrationPayload {
  body: {
    name: string
    slug: string
    plan_id?: string
  }
  user: {
    email: string
    password: string
    full_name?: string
  }
}

export interface TenantRegistrationResult {
  access_token: string
  token_type: string
  tenant_id: string
  user_id: string
  role: string
}

export interface PlanDefinition {
  id: string
  name: string
  max_agents: number
  max_invocations_month: number
  price_usd: number
  features: {
    rag?: boolean
    crew?: boolean
  }
}

export interface TenantOverviewUser {
  id: string
  email: string
  full_name?: string | null
  role: 'owner' | 'developer' | 'viewer'
  status: string
  created_at: string
}

export interface TenantOverview {
  tenant_id: string
  name: string
  slug: string
  plan_id: string
  created_at: string
  owner_email?: string | null
  owner_name?: string | null
  user_count: number
  developer_count: number
  viewer_count: number
  agents_used: number
  agents_limit: number
  invocations_used: number
  invocations_limit: number
  users: TenantOverviewUser[]
}

export const authApi = {
  register: (email: string, password: string) =>
    api.post('/auth/register', { email, password }).then((r) => r.data),

  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }).then((r) => r.data),

  me: (): Promise<AuthMe> => api.get('/auth/me').then((r) => r.data),

  changePassword: (currentPassword: string, newPassword: string) =>
    api.post('/auth/change-password', { current_password: currentPassword, new_password: newPassword }).then((r) => r.data),

  forgotPassword: (email: string): Promise<ForgotPasswordResult> =>
    api.post('/auth/forgot-password', { email }).then((r) => r.data),

  resetPassword: (token: string, newPassword: string) =>
    api.post('/auth/reset-password', { token, new_password: newPassword }).then((r) => r.data),

  requestFreeAccount: (payload: FreeAccountRequestPayload): Promise<FreeAccountRequest> =>
    api.post('/auth/free-request', payload).then((r) => r.data),
}

export const agentsApi = {
  createFromSpec: (spec: AgentSpec): Promise<AgentDesign> =>
    api.post('/agents/spec', spec).then((r) => r.data),

  build: (agentId: string) => api.post(`/agents/${agentId}/build`).then((r) => r.data),

  invoke: (agentId: string, input: string, sessionId?: string): Promise<AgentResponse> =>
    api.post(`/agents/${agentId}/invoke`, { input, session_id: sessionId || '' }).then((r) => r.data),

  eval: (agentId: string) => api.post(`/agents/${agentId}/eval`).then((r) => r.data),

  optimize: (agentId: string, evalReport: object, autoRebuild = false) =>
    api.post(`/agents/${agentId}/optimize`, { eval_report: evalReport, auto_rebuild: autoRebuild }).then((r) => r.data),

  deploy: (agentId: string) => api.post(`/agents/${agentId}/deploy`).then((r) => r.data),

  delete: (agentId: string) => api.delete(`/agents/${agentId}`),

  update: (
    agentId: string,
    patch: {
      name?: string
      model?: string
      provider?: string
      llm_key_id?: string
      system_prompt?: string
      temperature?: number
      max_tokens?: number
    }
  ): Promise<AgentDesign> => api.put(`/agents/${agentId}`, patch).then((r) => r.data),

  getDesign: (agentId: string): Promise<AgentDesign> =>
    api.get(`/agents/${agentId}/design`).then((r) => r.data),

  validateGraph: (agentId: string, graphBlueprint: GraphBlueprint): Promise<GraphValidationReport> =>
    api.post(`/agents/${agentId}/graph/validate`, { graph_blueprint: graphBlueprint }).then((r) => r.data),

  updateGraph: (agentId: string, graphBlueprint: GraphBlueprint): Promise<GraphUpdateResponse> =>
    api.put(`/agents/${agentId}/graph`, {
      graph_blueprint: graphBlueprint,
      auto_regenerate_mermaid: true,
    }).then((r) => r.data),

  getState: (agentId: string, sessionId = 'default') =>
    api.get(`/agents/${agentId}/state`, { params: { session_id: sessionId } }).then((r) => r.data),

  resetSession: (agentId: string, sessionId: string) =>
    api.delete(`/agents/${agentId}/session/${sessionId}`),
}

export type WSMessage =
  | { type: 'token'; content: string }
  | { type: 'done'; session_id: string }
  | { type: 'error'; message: string }
  | { type: 'status'; framework?: string; phase?: string; message: string; elapsed_seconds?: number; attempt?: number; retry_from?: string | null }
  | { type: 'trace'; framework?: string; phase?: string; actor?: string | null; kind?: string; message: string }

export function normalizeAgentChatError(message: string): string {
  const text = (message || '').trim()
  const lower = text.toLowerCase()

  if (lower.includes('limite de invocaciones del mes alcanzado') || lower.includes('límite de invocaciones del mes alcanzado')) {
    return 'Este workspace agotó las invocaciones incluidas en su plan mensual. Podés esperar al próximo mes o cambiar de plan para seguir usando el chat.'
  }

  if (lower.includes('rate limit superado')) {
    return 'Se alcanzó un límite temporal de uso. Esperá un momento y volvé a intentar.'
  }

  return text
}

export function createAgentWebSocket(
  agentId: string,
  onToken: (token: string) => void,
  onDone: (sessionId: string) => void,
  onError: (msg: string) => void,
  onStatus: (payload: Extract<WSMessage, { type: 'status' }>) => void = () => {},
  onTrace: (payload: Extract<WSMessage, { type: 'trace' }>) => void = () => {},
  options: { apiKey?: string } = {}
): {
  send: (input: string, sessionId: string) => void
  close: () => void
} {
  // Auto-detecta wss:// o ws:// según el protocolo de la página (https → wss)
  const WS_URL = import.meta.env.VITE_WS_URL ||
    `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`
  const params = new URLSearchParams()
  const token = getAuthToken()
  if (token) params.set('token', token)
  if (options.apiKey) params.set('api_key', options.apiKey)
  const query = params.toString()

  let closedManually = false
  let queue: Array<{ input: string; sessionId: string }> = []
  let ws: WebSocket | null = null

  const connect = () => {
    ws = new WebSocket(`${WS_URL}/api/v1/agents/${agentId}/ws${query ? `?${query}` : ''}`)

    ws.onopen = () => {
      for (const item of queue) {
        ws?.send(JSON.stringify({ input: item.input, session_id: item.sessionId }))
      }
      queue = []
    }

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data)
        if (msg.type === 'token') onToken(msg.content)
        else if (msg.type === 'done') onDone(msg.session_id)
        else if (msg.type === 'error') onError(msg.message)
        else if (msg.type === 'status') onStatus(msg)
        else if (msg.type === 'trace') onTrace(msg)
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = (event) => {
      if (!closedManually) {
        if (event.code === 1008) {
          // Auth failure — don't reconnect, surface the error
          onError('No autorizado: verificá que tu sesión esté activa')
        } else {
          window.setTimeout(connect, 1500)
        }
      }
    }

    ws.onerror = () => onError('Error de conexión WebSocket')
  }

  connect()

  return {
    send: (input: string, sessionId: string) => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ input, session_id: sessionId }))
      } else {
        queue.push({ input, sessionId })
      }
    },
    close: () => {
      closedManually = true
      ws?.close()
    },
  }
}

export const tenantsApi = {
  listAgents: (): Promise<AgentSummary[]> => api.get('/tenants/me/agents').then((r) => r.data),
  billing: (): Promise<TenantBillingSummary> => api.get('/tenants/me/billing').then((r) => r.data),
  register: (payload: TenantRegistrationPayload): Promise<TenantRegistrationResult> =>
    api.post('/tenants/register', payload).then((r) => r.data),
}

export const usersApi = {
  list: (): Promise<TenantUser[]> => api.get('/auth/users').then((r) => r.data),
  create: (payload: {
    email: string
    password: string
    full_name?: string
    role: 'developer' | 'viewer'
  }): Promise<TenantUser> => api.post('/auth/users', payload).then((r) => r.data),
}

export const llmKeysApi = {
  list: (): Promise<ProviderKey[]> => api.get('/keys/llm').then((r) => r.data),
  create: (payload: { provider: string; name: string; raw_key: string }) =>
    api.post('/keys/llm', payload).then((r) => r.data),
  remove: (keyId: string) => api.delete(`/keys/llm/${keyId}`).then((r) => r.data),
  setDefault: (keyId: string, provider: string) =>
    api.put(`/keys/llm/${keyId}/default`, undefined, { params: { provider } }).then((r) => r.data),
  updateModels: (keyId: string, models: ProviderModel[]) =>
    api.put(`/keys/llm/${keyId}/models`, { models }).then((r) => r.data),
}

export const usageApi = {
  summary: (): Promise<UsageSummary> => api.get('/usage/summary').then((r) => r.data),
  billing: (days = 30): Promise<BillingHistory> =>
    api.get('/usage/billing', { params: { days } }).then((r) => r.data),
  agents: (): Promise<AgentUsage[]> => api.get('/usage/agents').then((r) => r.data),
}

export const knowledgeApi = {
  getSources: (agentId: string) => api.get(`/knowledge/${agentId}/sources`).then((r) => r.data),
  deleteSource: (agentId: string, source: string) =>
    api.delete(`/knowledge/${agentId}/source`, { data: { source } }).then((r) => r.data),
  ingestJson: (agentId: string, sources: string[], chunk_size = 500, chunk_overlap = 50) =>
    api
      .post(`/knowledge/${agentId}/ingest`, { agent_id: agentId, rag_spec: { sources, chunk_size, chunk_overlap } })
      .then((r) => r.data),
  ingestFile: (agentId: string, file: File, chunk_size = 500, chunk_overlap = 50) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('chunk_size', chunk_size.toString())
    formData.append('chunk_overlap', chunk_overlap.toString())
    return api
      .post(`/knowledge/${agentId}/ingest/file`, formData, { headers: { 'Content-Type': 'multipart/form-data' } })
      .then((r) => r.data)
  },
  getStats: (agentId: string) => api.get(`/knowledge/${agentId}/stats`).then((r) => r.data),
  retrieve: (agentId: string, query: string, top_k = 4) =>
    api.post(`/knowledge/${agentId}/retrieve`, { query, top_k }).then((r) => r.data),
}

export const apiKeysApi = {
  list: () => api.get('/keys/').then((r) => r.data as APIKey[]),
  create: (name: string, agentId: string, scopes = ['invoke']) =>
    api.post('/keys/', { name, agent_id: agentId, scopes }).then((r) => r.data as APIKey),
  revoke: (keyId: string) => api.delete(`/keys/${keyId}`).then((r) => r.data),
}

export interface APIKey {
  id: string
  agent_id: string
  agent_name?: string | null
  name: string
  key?: string
  key_prefix: string
  scopes: string[]
  expires_at: string | null
  created_at: string
}

export const customToolsApi = {
  list: () => api.get('/tools/custom/').then((r) => r.data),
  get: (id: string) => api.get(`/tools/custom/${id}`).then((r) => r.data),
  create: (payload: object) => api.post('/tools/custom/', payload).then((r) => r.data),
  update: (id: string, payload: object) => api.put(`/tools/custom/${id}`, payload).then((r) => r.data),
  delete: (id: string) => api.delete(`/tools/custom/${id}`).then((r) => r.data),
  validate: (source_code: string) =>
    api.post('/tools/custom/validate', { source_code }).then((r) => r.data),
  test: (id: string, input: string, config: object) =>
    api.post(`/tools/custom/${id}/test`, { input, config }).then((r) => r.data),
  toggleActive: (id: string, is_active: boolean) =>
    api.put(`/tools/custom/${id}`, { is_active }).then((r) => r.data),
}

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
    autonomy_level: 'reactive',
    agents: state.agents,
    process: state.process,
  }
}


export const skillsApi = {
  list: (): Promise<Skill[]> => api.get('/skills/').then((r) => r.data),
  get: (id: string): Promise<Skill> => api.get(`/skills/${id}`).then((r) => r.data),
  create: (data: Omit<Skill, 'id' | 'is_active' | 'created_at'>): Promise<Skill> =>
    api.post('/skills/', data).then((r) => r.data),
  update: (id: string, data: Omit<Skill, 'id' | 'is_active' | 'created_at'>): Promise<Skill> =>
    api.put(`/skills/${id}`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/skills/${id}`),
  forAgent: (agentId: string): Promise<Skill[]> => api.get(`/agents/${agentId}/skills`).then((r) => r.data),
  assignToAgent: (agentId: string, skillId: string) => api.post(`/agents/${agentId}/skills/${skillId}`),
  unassignFromAgent: (agentId: string, skillId: string) => api.delete(`/agents/${agentId}/skills/${skillId}`),
}

export const mcpApi = {
  list: (): Promise<MCPServer[]> => api.get('/mcp/').then((r) => r.data),
  get: (id: string): Promise<MCPServer> => api.get(`/mcp/${id}`).then((r) => r.data),
  create: (data: Pick<MCPServer, 'name' | 'endpoint' | 'transport' | 'auth_type' | 'auth_config'>): Promise<MCPServer> =>
    api.post('/mcp/', data).then((r) => r.data),
  update: (id: string, data: Pick<MCPServer, 'name' | 'endpoint' | 'transport' | 'auth_type' | 'auth_config'>): Promise<MCPServer> =>
    api.put(`/mcp/${id}`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/mcp/${id}`),
  test: (id: string): Promise<MCPServer> => api.post(`/mcp/${id}/test`).then((r) => r.data),
  forAgent: (agentId: string): Promise<MCPServer[]> => api.get(`/agents/${agentId}/mcp`).then((r) => r.data),
  assignToAgent: (agentId: string, serverId: string) => api.post(`/agents/${agentId}/mcp/${serverId}`),
  unassignFromAgent: (agentId: string, serverId: string) => api.delete(`/agents/${agentId}/mcp/${serverId}`),
}

export const knowledgeBasesApi = {
  list: (): Promise<KnowledgeBase[]> => api.get('/knowledge-bases/').then((r) => r.data),
  get: (id: string): Promise<KnowledgeBase> => api.get(`/knowledge-bases/${id}`).then((r) => r.data),
  create: (data: Pick<KnowledgeBase, 'name' | 'description' | 'rag_spec'>): Promise<KnowledgeBase> =>
    api.post('/knowledge-bases/', data).then((r) => r.data),
  update: (id: string, data: Pick<KnowledgeBase, 'name' | 'description' | 'rag_spec'>): Promise<KnowledgeBase> =>
    api.put(`/knowledge-bases/${id}`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/knowledge-bases/${id}`),
  ingest: (id: string) => api.post(`/knowledge-bases/${id}/ingest`).then((r) => r.data),
  ingestFile: (id: string, file: File, chunk_size = 500, chunk_overlap = 50) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('chunk_size', chunk_size.toString())
    formData.append('chunk_overlap', chunk_overlap.toString())
    return api
      .post(`/knowledge-bases/${id}/ingest/file`, formData, { headers: { 'Content-Type': 'multipart/form-data' } })
      .then((r) => r.data)
  },
  getSources: (id: string) => api.get(`/knowledge-bases/${id}/sources`).then((r) => r.data),
  deleteSource: (id: string, source: string) =>
    api.delete(`/knowledge-bases/${id}/sources`, { data: { source } }).then((r) => r.data),
  forAgent: (agentId: string): Promise<KnowledgeBase[]> =>
    api.get(`/agents/${agentId}/knowledge-bases`).then((r) => r.data),
  assignToAgent: (agentId: string, kbId: string) => api.post(`/agents/${agentId}/knowledge-bases/${kbId}`),
  unassignFromAgent: (agentId: string, kbId: string) => api.delete(`/agents/${agentId}/knowledge-bases/${kbId}`),
}

export const policiesApi = {
  get: (agentId: string): Promise<BehaviorPolicy> => api.get(`/agents/${agentId}/policy`).then((r) => r.data),
  upsert: (agentId: string, data: Omit<BehaviorPolicy, 'id' | 'agent_id'>): Promise<BehaviorPolicy> =>
    api.put(`/agents/${agentId}/policy`, data).then((r) => r.data),
  delete: (agentId: string) => api.delete(`/agents/${agentId}/policy`),
}

export const systemApi = {
  getBuilderConfig: () => api.get('/system/builder').then(r => r.data),
  setBuilderConfig: (body: { provider: string; model: string; llm_key_id?: string }) =>
    api.put('/system/builder', body).then(r => r.data),
  getToolReadiness: (): Promise<ToolReadinessStatus[]> => api.get('/system/tool-readiness').then(r => r.data),
  listPlans: (): Promise<PlanDefinition[]> => api.get('/system/plans').then(r => r.data),
  updatePlan: (planId: string, body: PlanDefinition): Promise<PlanDefinition> =>
    api.put(`/system/plans/${planId}`, body).then(r => r.data),
  listFreeRequests: (status?: 'pending' | 'approved' | 'rejected'): Promise<FreeAccountRequest[]> =>
    api.get('/system/free-requests', { params: status ? { status } : undefined }).then(r => r.data),
  approveFreeRequest: (requestId: string, body?: { notes?: string; plan_id?: string }): Promise<FreeAccountRequest> =>
    api.post(`/system/free-requests/${requestId}/approve`, body || {}).then(r => r.data),
  rejectFreeRequest: (requestId: string, body?: { notes?: string }): Promise<FreeAccountRequest> =>
    api.post(`/system/free-requests/${requestId}/reject`, body || {}).then(r => r.data),
  getOverview: (): Promise<TenantOverview[]> => api.get('/system/overview').then(r => r.data),
}

export const guardrailsApi = {
  list: (agentId: string): Promise<GuardrailRule[]> => api.get(`/agents/${agentId}/guardrails`).then((r) => r.data),
  create: (agentId: string, data: Omit<GuardrailRule, 'id' | 'agent_id' | 'is_active'>): Promise<GuardrailRule> =>
    api.post(`/agents/${agentId}/guardrails`, data).then((r) => r.data),
  update: (
    agentId: string,
    ruleId: string,
    data: Omit<GuardrailRule, 'id' | 'agent_id' | 'is_active'>
  ): Promise<GuardrailRule> => api.put(`/agents/${agentId}/guardrails/${ruleId}`, data).then((r) => r.data),
  toggle: (agentId: string, ruleId: string): Promise<GuardrailRule> =>
    api.patch(`/agents/${agentId}/guardrails/${ruleId}/toggle`).then((r) => r.data),
  delete: (agentId: string, ruleId: string) => api.delete(`/agents/${agentId}/guardrails/${ruleId}`),
}
