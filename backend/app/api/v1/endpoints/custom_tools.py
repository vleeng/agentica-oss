from __future__ import annotations

import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import TenantRepo
from app.components.tools.custom_loader import validate_tool_code, build_tool_from_code
from app.core.security import CurrentContext

router = APIRouter()


# ── Schemas de request/response ───────────────────────────────────────────────

class CustomToolCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=60, pattern=r"^[a-z][a-z0-9_]*$",
                      description="Nombre snake_case, ej: consultar_precio_erp")
    description: str = Field(..., min_length=10, max_length=500)
    source_code: str = Field(..., min_length=50)
    config_schema: dict = Field(default_factory=dict,
                                description="JSON Schema de los parámetros configurables")
    test_input: str = Field(default="", description="Input de ejemplo para probar la tool")


class CustomToolUpdate(BaseModel):
    description: str | None = None
    source_code: str | None = None
    config_schema: dict | None = None
    is_active: bool | None = None
    test_input: str | None = None


class CustomToolOut(BaseModel):
    id: str
    name: str
    description: str
    source_code: str | None = None   # solo en GET detalle
    config_schema: dict
    is_active: bool
    test_input: str
    last_error: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: dict, include_source: bool = False) -> "CustomToolOut":
        schema = row.get("config_schema", {})
        if isinstance(schema, str):
            schema = json.loads(schema)
        return cls(
            id=str(row["id"]),
            name=row["name"],
            description=row["description"],
            source_code=row.get("source_code") if include_source else None,
            config_schema=schema,
            is_active=row["is_active"],
            test_input=row.get("test_input", ""),
            last_error=row.get("last_error"),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )


class ValidateRequest(BaseModel):
    source_code: str


class TestRequest(BaseModel):
    input: str = Field(..., description="Input de prueba para la tool")
    config: dict = Field(default_factory=dict, description="Configuración de prueba")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[CustomToolOut])
async def list_custom_tools(ctx: CurrentContext, repo: TenantRepo) -> list[CustomToolOut]:
    """Lista todas las custom tools del tenant."""
    rows = await repo.list_custom_tools()
    return [CustomToolOut.from_row(r) for r in rows]


@router.post("/", response_model=CustomToolOut, status_code=201)
async def create_custom_tool(
    body: CustomToolCreate,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> CustomToolOut:
    """
    Crea una nueva custom tool.
    El código es validado antes de guardarse — no se ejecuta en este paso.
    """
    ctx.require_developer()

    # Validar código antes de persistir
    valid, error = validate_tool_code(body.source_code)
    if not valid:
        raise HTTPException(422, detail=f"Código inválido: {error}")

    # Verificar nombre único
    existing = await repo.get_custom_tool(body.name)
    if existing:
        raise HTTPException(409, detail=f"Ya existe una tool con nombre '{body.name}'")

    row = await repo.create_custom_tool(
        name=body.name,
        description=body.description,
        source_code=body.source_code,
        config_schema=body.config_schema,
        test_input=body.test_input,
    )
    return CustomToolOut.from_row(row)


@router.get("/{tool_id}", response_model=CustomToolOut)
async def get_custom_tool(
    tool_id: str,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> CustomToolOut:
    row = await repo.get_custom_tool_by_id(tool_id)
    if not row:
        raise HTTPException(404, "Tool no encontrada")
    return CustomToolOut.from_row(row, include_source=True)


@router.put("/{tool_id}", response_model=CustomToolOut)
async def update_custom_tool(
    tool_id: str,
    body: CustomToolUpdate,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> CustomToolOut:
    """Actualiza la tool. Si se modifica source_code, se revalida."""
    ctx.require_developer()

    existing = await repo.get_custom_tool_by_id(tool_id)
    if not existing:
        raise HTTPException(404, "Tool no encontrada")

    if body.source_code is not None:
        valid, error = validate_tool_code(body.source_code)
        if not valid:
            raise HTTPException(422, detail=f"Código inválido: {error}")

    row = await repo.update_custom_tool(
        tool_id=tool_id,
        description=body.description,
        source_code=body.source_code,
        config_schema=body.config_schema,
        is_active=body.is_active,
        test_input=body.test_input,
    )
    return CustomToolOut.from_row(row)


@router.delete("/{tool_id}", status_code=204)
async def delete_custom_tool(
    tool_id: str,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> None:
    ctx.require_developer()
    deleted = await repo.delete_custom_tool(tool_id)
    if not deleted:
        raise HTTPException(404, "Tool no encontrada")


@router.post("/validate", status_code=200)
async def validate_tool(
    body: ValidateRequest,
    ctx: CurrentContext,
) -> dict:
    """
    Valida el código Python sin guardarlo ni ejecutarlo.
    Útil para feedback en tiempo real mientras el usuario escribe.
    """
    valid, error = validate_tool_code(body.source_code)
    return {"valid": valid, "error": error if not valid else None}


@router.post("/{tool_id}/test", status_code=200)
async def test_custom_tool(
    tool_id: str,
    body: TestRequest,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> dict:
    """
    Ejecuta la tool con un input de prueba.
    Guarda el resultado o el error en last_error para diagnóstico.
    """
    ctx.require_developer()

    row = await repo.get_custom_tool_by_id(tool_id)
    if not row:
        raise HTTPException(404, "Tool no encontrada")
    if not row["is_active"]:
        raise HTTPException(409, "La tool está desactivada")

    source = row["source_code"]
    config = body.config

    try:
        tool = build_tool_from_code(source, config)
        result = await tool._arun(input=body.input)

        # Limpiar last_error si el test fue exitoso
        await repo.update_custom_tool(tool_id=tool_id, last_error=None)

        return {
            "success": True,
            "input":   body.input,
            "output":  result,
            "tool_name": tool.name,
        }
    except Exception as e:
        error_msg = str(e)
        await repo.update_custom_tool(tool_id=tool_id, last_error=error_msg)
        return {
            "success": False,
            "input":   body.input,
            "error":   error_msg,
        }
