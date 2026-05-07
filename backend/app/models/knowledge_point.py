"""Knowledge point model with tree structure (adjacency list)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel


class KnowledgePoint(SQLModel, table=True):
    """知识点表，树形结构（邻接表）.

    支持软删除：is_deleted 标记删除状态，实际数据保留。
    """

    __tablename__ = "knowledge_points"

    id: int | None = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="subjects.id")
    parent_id: int | None = Field(default=None, foreign_key="knowledge_points.id")
    code: str = Field(index=True, unique=True, max_length=50)
    name: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=500)
    level: int = Field(ge=1, le=5)
    sort_order: int = Field(default=0)
    is_leaf: bool = Field(default=False)
    is_deleted: bool = Field(default=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    subject: Subject = Relationship(back_populates="knowledge_points")
    parent: KnowledgePoint = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "KnowledgePoint.id"},
    )
    children: KnowledgePoint = Relationship(back_populates="parent")
    outgoing_relations: KnowledgeRelation = Relationship(
        back_populates="source_kp",
        sa_relationship_kwargs={"foreign_keys": "KnowledgeRelation.source_kp_id"},
    )
    student_states: StudentKnowledgeState = Relationship(back_populates="knowledge_point")
    incoming_relations: KnowledgeRelation = Relationship(
        back_populates="target_kp",
        sa_relationship_kwargs={"foreign_keys": "KnowledgeRelation.target_kp_id"},
    )
