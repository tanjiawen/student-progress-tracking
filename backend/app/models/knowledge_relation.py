"""Knowledge point relation model (graph edges)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class RelationType(str, Enum):
    """Types of knowledge point relations."""

    prerequisite = "prerequisite"
    contains = "contains"
    related = "related"
    extends = "extends"


class KnowledgeRelation(SQLModel, table=True):
    """知识点关系表（图关系）.

    联合唯一约束：(source_kp_id, target_kp_id, relation_type)
    """

    __tablename__ = "knowledge_relations"

    id: int | None = Field(default=None, primary_key=True)
    source_kp_id: int = Field(foreign_key="knowledge_points.id")
    target_kp_id: int = Field(foreign_key="knowledge_points.id")
    relation_type: RelationType = Field(sa_column=Column(SAEnum(RelationType), nullable=False))
    weight: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    source_kp: KnowledgePoint = Relationship(
        back_populates="outgoing_relations",
        sa_relationship_kwargs={"foreign_keys": "KnowledgeRelation.source_kp_id"},
    )
    target_kp: KnowledgePoint = Relationship(
        back_populates="incoming_relations",
        sa_relationship_kwargs={"foreign_keys": "KnowledgeRelation.target_kp_id"},
    )

    __table_args__ = (
        UniqueConstraint(
            "source_kp_id",
            "target_kp_id",
            "relation_type",
            name="uix_kp_relation",
        ),
    )
