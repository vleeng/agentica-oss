// ── Enums ─────────────────────────────────────────────────────────────────────

export type AgentMode = 'single' | 'crew'
export type MemoryType = 'none' | 'session' | 'persistent' | 'summary'
export type CrewProcess = 'sequential' | 'hierarchical' | 'parallel'
export type AutonomyLevel = 'reactive' | 'semi' | 'autonomous'
export type ChannelType = 'web_chat' | 'whatsapp' | 'telegram' | 'slack' | 'rest_api'
export type BuildStatus = 'pending' | 'building' | 'ready' | 'failed'
export type AgentStatus = 'draft' | 'building' | 'testing' | 'deployed' | 'archived'


// ── Sub-specs ─────────────────────────────────────────────────────────────────

export interface ToolRef {
  name: string
  source: 'library' | 'custom'
  config: Record<string, unknown>
}

export interface MemorySpec {
  type: MemoryType
  ttl_seconds?: number
  max_messages: number
}

export interface RAGSpec {
  enabled: boolean
  pack: string
  sources: string[]
  chunk_size: number
  chunk_overlap: number
  top_k: number
  embedding_model: string
}

export interface ModelParams {
  model: string
  provider?: string
  base_url?: string
  temperature: number
  max_tokens: number
  top_p: number
  llm_key_id?: string
}

export interface AgentRoleSpec {
  name: string
  role: string
  goal: string
  backstory: string
  tools: ToolRef[]
  allow_delegation: boolean
  model_params?: ModelParams
}


// ── AgentSpec ─────────────────────────────────────────────────────────────────

export interface AgentSpec {
  tenant_id: string
  name: string
  description: string
  goal: string
  mode: AgentMode
  channels: ChannelType[]
  model_params: ModelParams
  constraints: string[]
  expected_inputs: string[]
  expected_outputs: string[]
  memory: MemorySpec
  rag: RAGSpec
  // single
  tools: ToolRef[]
  autonomy_level: AutonomyLevel
  // crew
  agents: AgentRoleSpec[]
  process: CrewProcess
  manager_model?: string
}


// ── Design output ─────────────────────────────────────────────────────────────

export interface FrameworkSelection {
  framework: 'langchain' | 'crewai'
  agent_type?: 'openai_functions' | 'react'
  process?: CrewProcess
  justification: string
  estimated_complexity: 'low' | 'medium' | 'high'
}

export interface AgentDesign {
  agent_id: string
  tenant_id: string
  spec: AgentSpec
  framework: FrameworkSelection
  system_prompt: string
  graph_blueprint: {
    nodes: Array<{ id: string; type: string; label: string; description: string }>
    edges: Array<{ from: string; to: string; condition: string | null }>
  }
  test_cases: Array<{
    id: number
    description: string
    input: string
    expected_behavior: string
    expected_tools: string[]
    pass_criteria: string
  }>
  mermaid_diagram: string
  version: number
}


// ── Wizard state (frontend) ───────────────────────────────────────────────────

export interface WizardState {
  step: number
  mode?: AgentMode
  name: string
  description: string
  goal: string
  channels: ChannelType[]
  tools: ToolRef[]
  memory: MemorySpec
  rag: RAGSpec
  model_params: ModelParams
  constraints: string[]
  autonomy_level: AutonomyLevel
  // crew
  agents: AgentRoleSpec[]
  process: CrewProcess
}

export const WIZARD_DEFAULTS: WizardState = {
  step: 0,
  name: '',
  description: '',
  goal: '',
  channels: ['web_chat'],
  tools: [],
  memory: { type: 'session', max_messages: 50 },
  rag: {
    enabled: false,
    pack: 'GenericDocsRAG',
    sources: [],
    chunk_size: 500,
    chunk_overlap: 50,
    top_k: 4,
    embedding_model: 'text-embedding-3-small',
  },
  model_params: {
    model: 'claude-sonnet-4-5',
    temperature: 0.3,
    max_tokens: 2048,
    top_p: 1.0,
  },
  constraints: [],
  autonomy_level: 'reactive',
  agents: [],
  process: 'sequential',
}


// ── Skills ────────────────────────────────────────────────────────────────────

export interface Skill {
  id: string
  name: string
  description: string
  objective: string
  usage_conditions: string
  tools: ToolRef[]
  procedure: string
  quality_rules: string
  output_format: string
  guardrails: string[]
  is_active: boolean
  created_at: string
}

// ── MCP Servers ───────────────────────────────────────────────────────────────

export interface DiscoveredTool {
  name: string
  description: string
  input_schema: Record<string, unknown>
}

export interface MCPServer {
  id: string
  name: string
  endpoint: string
  transport: 'sse' | 'http'
  auth_type: 'none' | 'bearer' | 'basic'
  auth_config: Record<string, string>
  discovered_tools: DiscoveredTool[]
  is_active: boolean
  last_tested_at?: string
}

// ── Knowledge Bases ───────────────────────────────────────────────────────────

export interface KnowledgeBase {
  id: string
  name: string
  description: string
  rag_spec: RAGSpec
  status: 'empty' | 'indexing' | 'ready' | 'error'
  created_at: string
}

// ── Behavior Policy ───────────────────────────────────────────────────────────

export interface BehaviorPolicy {
  id?: string
  agent_id?: string
  tone: string
  escalation_conditions: string[]
  confirmation_triggers: string[]
  format_requirements: string
  custom_rules: string[]
}

// ── Guardrail Rules ───────────────────────────────────────────────────────────

export type GuardrailRuleType = 'input_block' | 'output_filter' | 'length_limit' | 'topic_restrict'
export type GuardrailAction = 'block' | 'warn' | 'transform'

export interface GuardrailRule {
  id?: string
  agent_id?: string
  name: string
  rule_type: GuardrailRuleType
  condition: Record<string, unknown>
  action: GuardrailAction
  priority: number
  is_active: boolean
}

// ── Available tools en la Component Library ──────────────────────────────────

export const AVAILABLE_TOOLS: Array<{ name: string; description: string; category: string }> = [
  { name: 'web_search',    description: 'Buscar información en internet (Tavily)', category: 'información' },
  { name: 'sql_query',     description: 'Consultar bases de datos SQL',            category: 'datos' },
  { name: 'rest_api_call', description: 'Llamar APIs REST externas',               category: 'integración' },
  { name: 'calculator',    description: 'Evaluar expresiones matemáticas',         category: 'utilidad' },
  { name: 'send_email',    description: 'Enviar emails via SMTP',                  category: 'comunicación' },
]

export const AVAILABLE_MODELS: Array<{ id: string; name: string; provider: string; providerId: string }> = [
  { id: 'claude-sonnet-4-5',        name: 'Claude Sonnet 4.5',  provider: 'Anthropic', providerId: 'anthropic' },
  { id: 'claude-opus-4-6',          name: 'Claude Opus 4.6',    provider: 'Anthropic', providerId: 'anthropic' },
  { id: 'claude-haiku-4-5-20251001',name: 'Claude Haiku 4.5',   provider: 'Anthropic', providerId: 'anthropic' },
  { id: 'gpt-4o',                   name: 'GPT-4o',             provider: 'OpenAI',    providerId: 'openai' },
  { id: 'gpt-4o-mini',              name: 'GPT-4o Mini',        provider: 'OpenAI',    providerId: 'openai' },
  { id: 'openrouter:anthropic/claude-3.5-sonnet', name: 'Claude 3.5 Sonnet', provider: 'OpenRouter', providerId: 'openrouter' },
  { id: 'openrouter:deepseek/deepseek-chat',      name: 'DeepSeek Chat',     provider: 'OpenRouter', providerId: 'openrouter' },
  { id: 'deepseek-chat',                         name: 'DeepSeek Chat',      provider: 'DeepSeek',   providerId: 'deepseek' },
  { id: 'qwen-plus',                             name: 'Qwen Plus',          provider: 'Qwen',       providerId: 'qwen' },
  { id: 'moonshot-v1-8k',                        name: 'Kimi Moonshot',      provider: 'Moonshot',   providerId: 'moonshot' },
  { id: 'glm-4-plus',                            name: 'GLM-4 Plus',         provider: 'Zhipu',      providerId: 'zhipu' },
]
