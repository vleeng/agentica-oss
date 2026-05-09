from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-z0-9\-]+$")
    plan_id: str = "free"


class TenantOut(BaseModel):
    id: UUID
    name: str
    slug: str
    plan_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None


class LoginInput(BaseModel):
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserOut(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    full_name: Optional[str]
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    user_id: str
    role: str


class LLMProviderKeyCreate(BaseModel):
    provider: str
    name: str
    raw_key: str

class LLMProviderModel(BaseModel):
    id: str = Field(..., min_length=1)
    input_cost_per_million: float = Field(0.0, ge=0.0)
    output_cost_per_million: float = Field(0.0, ge=0.0)

class LLMProviderKeyOut(BaseModel):
    id: UUID
    provider: str
    name: str
    is_default: bool
    created_at: datetime
    truncated_key: str
    models: list[LLMProviderModel] = Field(default_factory=list)
