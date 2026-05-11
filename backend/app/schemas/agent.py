from __future__ import annotations
from enum import Enum
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ── Enumeraciones ────────────────────────────────────────────────────────────

class AgentMode(str, Enum):
    single = "single"   # Un agente con tools → LangChain
    crew   = "crew"     # Equipo de agentes con roles → CrewAI


class MemoryType(str, Enum):
    none          = "none"
    session       = "session"       # Redis, se borra al cerrar sesión
    persistent    = "persistent"    # PostgreSQL, persiste entre sesiones
    summary       = "summary"       # Summary buffer sobre persistent


class CrewProcess(str, Enum):
    sequential   = "sequential"
    hierarchical = "hierarchical"
    parallel     = "parallel"


class AutonomyLevel(str, Enum):
    reactive   = "reactive"    # Solo responde cuando lo invocan
    semi       = "semi"        # Puede hacer follow-up, pide confirmación en acciones
    autonomous = "autonomous"  # Ejecuta sin pedir confirmación


class ChannelType(str, Enum):
    web_chat  = "web_chat"
    whatsapp  = "whatsapp"
    telegram  = "telegram"
    slack     = "slack"
    rest_api  = "rest_api"


# ── Sub-specs ────────────────────────────────────────────────────────────────

class ToolRef(BaseModel):
    """Referencia a una tool de la Component Library o custom."""
    name: str
    source: Literal["library", "custom"] = "library"
    config: dict = Field(default_factory=dict)  # parámetros específicos de la tool


class MemorySpec(BaseModel):
    type: MemoryType = MemoryType.session
    ttl_seconds: Optional[int] = None           # None = sin expiración
    max_messages: int = 50                       # ventana de contexto en memoria


class RAGSpec(BaseModel):
    enabled: bool = False
    pack: str = "GenericDocsRAG"                # nombre del RAG pack
    sources: list[str] = Field(default_factory=list)  # URLs, paths, DSNs
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 4                               # fragmentos a recuperar por query
    embedding_model: str = "text-embedding-3-small"


class ModelParams(BaseModel):
    model: str = "claude-3-5-sonnet-20241022"  # o gpt-4o etc
    provider: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = Field(0.3, ge=0.0, le=1.0)
    max_tokens: int = Field(2048, ge=256, le=8192)
    top_p: float = Field(1.0, ge=0.0, le=1.0)
    llm_key_id: Optional[str] = None


class FlowNodeType(str, Enum):
    start = "start"
    agent = "agent"
    decision = "decision"
    tool = "tool"
    end = "end"


class FlowNodePosition(BaseModel):
    x: float = 0.0
    y: float = 0.0


class FlowNodeData(BaseModel):
    description: Optional[str] = None
    assigned_agent: Optional[str] = None
    allowed_tools: list[str] = Field(default_factory=list)
    tool_name: Optional[str] = None
    notes: Optional[str] = None


class FlowNode(BaseModel):
    id: str
    type: FlowNodeType
    label: str
    description: str = ""
    position: Optional[FlowNodePosition] = None
    data: FlowNodeData = Field(default_factory=FlowNodeData)


class FlowEdge(BaseModel):
    id: Optional[str] = None
    from_: str = Field(alias="from")
    to: str
    condition: Optional[str] = None

    model_config = {"populate_by_name": True}

    def model_dump(self, *args, **kwargs):
        kwargs.setdefault("by_alias", True)
        return super().model_dump(*args, **kwargs)


class GraphMeta(BaseModel):
    version: int = 1
    layout: Literal["manual", "auto"] = "manual"


class GraphBlueprint(BaseModel):
    nodes: list[FlowNode] = Field(default_factory=list)
    edges: list[FlowEdge] = Field(default_factory=list)
    meta: GraphMeta = Field(default_factory=GraphMeta)

    def as_dict(self) -> dict:
        return self.model_dump(by_alias=True)


class GraphValidationIssue(BaseModel):
    level: Literal["error", "warning"]
    code: str
    message: str
    node_id: Optional[str] = None
    edge_id: Optional[str] = None


class GraphValidationReport(BaseModel):
    ok: bool
    errors: list[GraphValidationIssue] = Field(default_factory=list)
    warnings: list[GraphValidationIssue] = Field(default_factory=list)


class GraphUpdateRequest(BaseModel):
    graph_blueprint: GraphBlueprint
    auto_regenerate_mermaid: bool = True


class GraphUpdateResponse(BaseModel):
    graph_blueprint: GraphBlueprint
    mermaid_diagram: str
    validation: GraphValidationReport


# ── AgentRoleSpec (solo para mode=crew) ─────────────────────────────────────

class AgentRoleSpec(BaseModel):
    model_config = {"protected_namespaces": ()}

    name: str                         # identificador interno, ej: "researcher"
    role: str                         # título visible, ej: "Investigador Senior"
    goal: str                         # objetivo del rol
    backstory: str                    # contexto del rol para CrewAI
    tools: list[ToolRef] = Field(default_factory=list)
    allow_delegation: bool = False
    model_params: Optional[ModelParams] = None  # None = usa el del Crew


# ── AgentSpec — el objeto central del Requirement Wizard ────────────────────

class AgentSpec(BaseModel):
    model_config = {"protected_namespaces": ()}

    """
    Producido por el Requirement Wizard.
    Es el único input que necesita el resto del pipeline.
    """
    # Identidad
    tenant_id: str
    name: str
    description: str
    goal: str

    # Modo — determina el framework
    mode: AgentMode

    # Canales de despliegue
    channels: list[ChannelType] = Field(default_factory=lambda: [ChannelType.web_chat])

    # Configuración del modelo base
    model_params: ModelParams = Field(default_factory=ModelParams)

    # Restricciones y contexto
    constraints: list[str] = Field(default_factory=list)
    expected_inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)

    # Memoria y RAG
    memory: MemorySpec = Field(default_factory=MemorySpec)
    rag: RAGSpec = Field(default_factory=RAGSpec)

    # Solo para mode=single
    tools: list[ToolRef] = Field(default_factory=list)
    autonomy_level: AutonomyLevel = AutonomyLevel.reactive

    # Solo para mode=crew
    agents: list[AgentRoleSpec] = Field(default_factory=list)
    process: CrewProcess = CrewProcess.sequential
    manager_model: Optional[str] = None   # para process=hierarchical

    # Referencias a entidades de la librería (asignadas post-creación)
    skill_ids: list[str] = Field(default_factory=list)
    mcp_server_ids: list[str] = Field(default_factory=list)
    knowledge_base_ids: list[str] = Field(default_factory=list)


# ── FrameworkSelection — output del Framework Selector ──────────────────────

class FrameworkSelection(BaseModel):
    framework: Literal["langchain", "crewai"]
    agent_type: Optional[Literal["openai_functions", "react"]] = None  # solo langchain
    process: Optional[CrewProcess] = None                               # solo crewai
    justification: str
    estimated_complexity: Literal["low", "medium", "high"]


# ── AgentDesign — output del Design Generator ───────────────────────────────

class AgentDesign(BaseModel):
    schema_version: int = 1
    agent_id: UUID = Field(default_factory=uuid4)
    tenant_id: str
    spec: AgentSpec
    framework: FrameworkSelection
    system_prompt: str
    graph_blueprint: dict = Field(default_factory=dict)  # nodos y edges del grafo
    test_cases: list[dict] = Field(default_factory=list) # mín 5, generados por LLM
    mermaid_diagram: str = ""
    version: int = 1
    status: str = "draft"  # draft | building | testing | deployed | archived


# ── AgentResponse — output unificado del AgentRuntime ───────────────────────

class AgentResponse(BaseModel):
    output: str
    steps: list[dict] = Field(default_factory=list)  # intermediate steps
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    session_id: str = ""
