from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SubjectRead(BaseModel):
    id: int
    name: str = Field(..., max_length=100)
    code: str = Field(..., max_length=50)
    description: str | None = Field(default=None, max_length=500)
    grade_levels: list[int] = []
    sort_order: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
class KnowledgePointRead(BaseModel):
    id: int
    subject_id: int
    parent_id: int | None = None
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    description: str | None = Field(default=None, max_length=500)
    level: int = Field(..., ge=1, le=5)
    sort_order: int = 0
    is_leaf: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
class KnowledgePointTreeNode(KnowledgePointRead):
    children: list[Any] = []


class KnowledgePointPathItem(BaseModel):
    id: int
    name: str
    code: str
    level: int


class PrerequisiteItem(BaseModel):
    id: int
    name: str
    code: str
